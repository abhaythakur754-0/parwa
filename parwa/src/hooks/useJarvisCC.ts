/**
 * PARWA Jarvis CC Hooks (Phase 5)
 *
 * React hooks for managing Jarvis Customer Care state.
 * Uses React Query for server state and local state for UI.
 */

'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import { ccSessionApi, ccMessageApi, ccAwarenessApi, ccAlertApi, ccCommandApi } from '@/lib/jarvis-cc-api';
import type {
  JarvisCCSession,
  JarvisCCMessage,
  ProactiveAlert,
  AwarenessSnapshot,
  AwarenessTickResult,
  QuickCommandItem,
  CommandResponse,
  AlertSeverity,
  CCChannel,
} from '@/types/jarvis-cc';

// ── FetchState Type ─────────────────────────────────────────────────

export type FetchState<T> = {
  status: 'idle' | 'loading' | 'error' | 'success';
  data: T | null;
  error: string | null;
};

// ── useJarvisCCSession Hook ─────────────────────────────────────────

export function useJarvisCCSession() {
  const [session, setSession] = useState<JarvisCCSession | null>(null);
  const [state, setState] = useState<FetchState<JarvisCCSession>>({ status: 'idle', data: null, error: null });

  const createSession = useCallback(async () => {
    setState({ status: 'loading', data: null, error: null });
    try {
      const result = await ccSessionApi.create();
      setSession(result);
      setState({ status: 'success', data: result, error: null });
      return result;
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to create session';
      setState({ status: 'error', data: null, error: msg });
      return null;
    }
  }, []);

  const resumeSession = useCallback(async (sessionId: string) => {
    setState({ status: 'loading', data: null, error: null });
    try {
      const result = await ccSessionApi.get(sessionId);
      setSession(result);
      setState({ status: 'success', data: result, error: null });
      return result;
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to resume session';
      setState({ status: 'error', data: null, error: msg });
      return null;
    }
  }, []);

  return { session, state, createSession, resumeSession, setSession };
}

// ── useJarvisCCChat Hook ────────────────────────────────────────────

export function useJarvisCCChat(sessionId: string | null) {
  const [messages, setMessages] = useState<JarvisCCMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadHistory = useCallback(async () => {
    if (!sessionId) return;
    setIsLoading(true);
    try {
      const result = await ccMessageApi.history(sessionId, 100, 0);
      setMessages(result.messages);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load history');
    } finally {
      setIsLoading(false);
    }
  }, [sessionId]);

  const sendMessage = useCallback(async (content: string, ticketId?: string, channel?: CCChannel) => {
    if (!sessionId) return null;
    setIsLoading(true);
    setError(null);
    try {
      // Add optimistic user message
      const optimisticUserMsg: JarvisCCMessage = {
        id: `temp-${Date.now()}`,
        session_id: sessionId,
        role: 'user',
        content,
        message_type: 'text',
        metadata: {},
        timestamp: new Date().toISOString(),
      };
      setMessages(prev => [...prev, optimisticUserMsg]);

      const response = await ccMessageApi.send({
        content,
        session_id: sessionId,
        ticket_id: ticketId,
        channel,
      });

      setMessages(prev => [...prev, response]);
      return response;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send message');
      return null;
    } finally {
      setIsLoading(false);
    }
  }, [sessionId]);

  const sendCommand = useCallback(async (rawInput: string) => {
    if (!sessionId) return null;
    setIsLoading(true);
    setError(null);
    try {
      const result = await ccCommandApi.send({
        session_id: sessionId,
        raw_input: rawInput,
        source: 'chat',
      });

      // Add command result as a system message
      const cmdMessage: JarvisCCMessage = {
        id: `cmd-${result.command_id}`,
        session_id: sessionId,
        role: 'jarvis',
        content: result.error
          ? `Command failed: ${result.error}`
          : result.suggestion || `Command "${result.action}" executed successfully.`,
        message_type: 'command_response',
        metadata: {
          command_id: result.command_id,
          intent: result.intent,
          action: result.action,
          status: result.status,
          undo_available: result.undo_available,
          result: result.result,
        },
        timestamp: new Date().toISOString(),
      };
      setMessages(prev => [...prev, cmdMessage]);
      return result;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Command failed');
      return null;
    } finally {
      setIsLoading(false);
    }
  }, [sessionId]);

  return { messages, isLoading, error, loadHistory, sendMessage, sendCommand, setMessages, setError };
}

// ── useJarvisAwareness Hook ─────────────────────────────────────────

export function useJarvisAwareness(sessionId: string | null) {
  const [snapshot, setSnapshot] = useState<AwarenessSnapshot | null>(null);
  const [alerts, setAlerts] = useState<ProactiveAlert[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [tickResult, setTickResult] = useState<AwarenessTickResult | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchSnapshot = useCallback(async () => {
    if (!sessionId) return;
    try {
      const result = await ccAwarenessApi.snapshot(sessionId);
      setSnapshot(result);
    } catch {
      // Silent fail — awareness is supplementary
    }
  }, [sessionId]);

  const fetchAlerts = useCallback(async () => {
    if (!sessionId) return;
    try {
      const result = await ccAlertApi.list(sessionId, { limit: 50 });
      setAlerts(result.alerts);
    } catch {
      // Silent fail
    }
  }, [sessionId]);

  const triggerTick = useCallback(async (tickType: 'periodic' | 'manual' | 'emergency' = 'manual') => {
    if (!sessionId) return;
    setIsLoading(true);
    try {
      const result = await ccAwarenessApi.tick({ session_id: sessionId, tick_type: tickType });
      setTickResult(result);
      // Refresh alerts after tick
      await fetchAlerts();
      await fetchSnapshot();
      return result;
    } catch {
      return null;
    } finally {
      setIsLoading(false);
    }
  }, [sessionId, fetchAlerts, fetchSnapshot]);

  const handleAlertAction = useCallback(async (alertId: string, action: 'acknowledge' | 'dismiss' | 'resolve') => {
    if (!sessionId) return;
    try {
      const apiFn = action === 'acknowledge' ? ccAlertApi.acknowledge
        : action === 'dismiss' ? ccAlertApi.dismiss
        : ccAlertApi.resolve;
      await apiFn(sessionId, { alert_id: alertId });
      await fetchAlerts();
    } catch {
      // Silent fail
    }
  }, [sessionId, fetchAlerts]);

  // Auto-poll awareness every 30s
  const startPolling = useCallback(() => {
    if (pollRef.current) return;
    fetchSnapshot();
    fetchAlerts();
    pollRef.current = setInterval(() => {
      fetchSnapshot();
      fetchAlerts();
    }, 30000);
  }, [fetchSnapshot, fetchAlerts]);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => stopPolling();
  }, [stopPolling]);

  return {
    snapshot,
    alerts,
    isLoading,
    tickResult,
    fetchSnapshot,
    fetchAlerts,
    triggerTick,
    handleAlertAction,
    startPolling,
    stopPolling,
  };
}

// ── useJarvisCommands Hook ──────────────────────────────────────────

export function useJarvisCommands(sessionId: string | null) {
  const [quickCommands, setQuickCommands] = useState<QuickCommandItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const fetchQuickCommands = useCallback(async () => {
    if (!sessionId) return;
    try {
      const result = await ccCommandApi.quickCommands(sessionId);
      setQuickCommands(result.commands);
    } catch {
      // Silent fail
    }
  }, [sessionId]);

  const executeQuickCommand = useCallback(async (quickCommandId: string) => {
    if (!sessionId) return null;
    setIsLoading(true);
    try {
      const result = await ccCommandApi.quick({ session_id: sessionId, quick_command_id: quickCommandId });
      return result;
    } catch {
      return null;
    } finally {
      setIsLoading(false);
    }
  }, [sessionId]);

  const undoCommand = useCallback(async (commandId: string) => {
    if (!sessionId) return null;
    setIsLoading(true);
    try {
      const result = await ccCommandApi.undo({ session_id: sessionId, command_id: commandId });
      return result;
    } catch {
      return null;
    } finally {
      setIsLoading(false);
    }
  }, [sessionId]);

  return { quickCommands, isLoading, fetchQuickCommands, executeQuickCommand, undoCommand };
}

// ── useCommandPalette Hook ──────────────────────────────────────────

export function useCommandPalette() {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState('');

  const open = useCallback(() => {
    setIsOpen(true);
    setQuery('');
  }, []);

  const close = useCallback(() => {
    setIsOpen(false);
    setQuery('');
  }, []);

  const toggle = useCallback(() => {
    setIsOpen(prev => {
      if (!prev) setQuery('');
      return !prev;
    });
  }, []);

  // Cmd+K / Ctrl+K shortcut
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        toggle();
      }
      if (e.key === 'Escape' && isOpen) {
        close();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [toggle, isOpen, close]);

  return { isOpen, query, setQuery, open, close, toggle };
}

// ── Severity helpers ────────────────────────────────────────────────

export function severityColor(severity: AlertSeverity): string {
  switch (severity) {
    case 'emergency': return 'text-red-400 bg-red-500/10 border-red-500/20';
    case 'critical': return 'text-red-400 bg-red-500/10 border-red-500/20';
    case 'warning': return 'text-amber-400 bg-amber-500/10 border-amber-500/20';
    case 'info': return 'text-blue-400 bg-blue-500/10 border-blue-500/20';
    default: return 'text-zinc-400 bg-zinc-500/10 border-zinc-500/20';
  }
}

export function severityIcon(severity: AlertSeverity): string {
  switch (severity) {
    case 'emergency': return '🚨';
    case 'critical': return '🔴';
    case 'warning': return '⚠️';
    case 'info': return 'ℹ️';
    default: return '•';
  }
}

export function healthColor(health: string | null): string {
  if (!health) return 'text-zinc-500';
  switch (health.toLowerCase()) {
    case 'healthy': return 'text-emerald-400';
    case 'degraded': return 'text-amber-400';
    case 'unhealthy': return 'text-red-400';
    default: return 'text-zinc-400';
  }
}

export function utilizationColor(util: number): string {
  if (util >= 0.95) return 'text-red-400';
  if (util >= 0.80) return 'text-amber-400';
  return 'text-emerald-400';
}
