/**
 * PARWA useShadowMode Hook (Day 3 — Jarvis Context + Memory Integration)
 *
 * React hook providing real-time shadow mode state for dashboard components.
 * Syncs between UI actions and Jarvis conversational commands via WebSocket.
 *
 * Features:
 *   - Current mode (shadow/supervised/graduated) with real-time updates
 *   - Preferences per action category
 *   - Shadow stats (approval rate, avg risk, pending count)
 *   - Actions: switch mode, set preference, approve/reject/undo
 *   - WebSocket sync: mode/preference changes from Jarvis reflect in UI
 *
 * Uses:
 *   - shadowApi for HTTP calls
 *   - SocketContext for real-time event listening
 */

'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { shadowApi, type SystemMode, type ShadowStats, type ShadowPreference, type ShadowLogEntry } from '@/lib/shadow-api';
import { useSocket } from '@/contexts/SocketContext';

// ── Types ──────────────────────────────────────────────────────────────

export interface UseShadowModeReturn {
  /** Current global shadow mode */
  mode: SystemMode | null;
  /** Whether mode is loading */
  isLoadingMode: boolean;
  /** All client preferences */
  preferences: ShadowPreference[];
  /** Whether preferences are loading */
  isLoadingPreferences: boolean;
  /** Shadow mode statistics */
  stats: ShadowStats | null;
  /** Whether stats are loading */
  isLoadingStats: boolean;
  /** Error state */
  error: string | null;
  /** Switch global system mode */
  switchMode: (mode: SystemMode) => Promise<void>;
  /** Set preference for an action category */
  setPreference: (category: string, mode: SystemMode) => Promise<void>;
  /** Delete a preference (reset to default) */
  deletePreference: (category: string) => Promise<void>;
  /** Approve a shadow action */
  approveAction: (id: string, note?: string) => Promise<void>;
  /** Reject a shadow action */
  rejectAction: (id: string, note?: string) => Promise<void>;
  /** Undo an auto-approved action */
  undoAction: (id: string, reason: string) => Promise<void>;
  /** Refresh all shadow mode data */
  refreshAll: () => Promise<void>;
  /** Clear error */
  clearError: () => void;
}

// ── Hook ───────────────────────────────────────────────────────────────

export function useShadowMode(): UseShadowModeReturn {
  const { aiMode, socket } = useSocket();
  const mountedRef = useRef(true);

  // ── State ────────────────────────────────────────────────────────────

  const [mode, setMode] = useState<SystemMode | null>(null);
  const [isLoadingMode, setIsLoadingMode] = useState(false);
  const [preferences, setPreferences] = useState<ShadowPreference[]>([]);
  const [isLoadingPreferences, setIsLoadingPreferences] = useState(false);
  const [stats, setStats] = useState<ShadowStats | null>(null);
  const [isLoadingStats, setIsLoadingStats] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ── Data Fetchers ────────────────────────────────────────────────────

  const fetchMode = useCallback(async () => {
    try {
      setIsLoadingMode(true);
      const response = await shadowApi.getMode();
      if (mountedRef.current) {
        setMode(response.mode);
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err instanceof Error ? err.message : 'Failed to fetch shadow mode');
      }
    } finally {
      if (mountedRef.current) setIsLoadingMode(false);
    }
  }, []);

  const fetchPreferences = useCallback(async () => {
    try {
      setIsLoadingPreferences(true);
      const response = await shadowApi.getPreferences();
      if (mountedRef.current) {
        setPreferences(response.preferences || []);
      }
    } catch (err) {
      if (mountedRef.current) {
        // Non-critical — preferences are optional
        console.warn('[useShadowMode] Failed to fetch preferences:', err);
      }
    } finally {
      if (mountedRef.current) setIsLoadingPreferences(false);
    }
  }, []);

  const fetchStats = useCallback(async () => {
    try {
      setIsLoadingStats(true);
      const response = await shadowApi.getStats();
      if (mountedRef.current) {
        setStats(response);
      }
    } catch (err) {
      if (mountedRef.current) {
        console.warn('[useShadowMode] Failed to fetch stats:', err);
      }
    } finally {
      if (mountedRef.current) setIsLoadingStats(false);
    }
  }, []);

  // ── Actions ──────────────────────────────────────────────────────────

  const switchMode = useCallback(async (newMode: SystemMode) => {
    setError(null);
    try {
      await shadowApi.setMode(newMode);
      if (mountedRef.current) {
        setMode(newMode);
      }
      // Stats may change after mode switch
      fetchStats();
    } catch (err) {
      if (mountedRef.current) {
        setError(err instanceof Error ? err.message : 'Failed to switch mode');
      }
    }
  }, [fetchStats]);

  const setPreference = useCallback(async (category: string, prefMode: SystemMode) => {
    setError(null);
    try {
      await shadowApi.setPreference(category, prefMode);
      if (mountedRef.current) {
        // Refresh preferences to get updated list
        fetchPreferences();
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err instanceof Error ? err.message : 'Failed to set preference');
      }
    }
  }, [fetchPreferences]);

  const deletePreference = useCallback(async (category: string) => {
    setError(null);
    try {
      await shadowApi.deletePreference(category);
      if (mountedRef.current) {
        fetchPreferences();
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err instanceof Error ? err.message : 'Failed to delete preference');
      }
    }
  }, [fetchPreferences]);

  const approveAction = useCallback(async (id: string, note?: string) => {
    setError(null);
    try {
      await shadowApi.approve(id, note);
      // Stats and pending count change after approval
      fetchStats();
    } catch (err) {
      if (mountedRef.current) {
        setError(err instanceof Error ? err.message : 'Failed to approve action');
      }
    }
  }, [fetchStats]);

  const rejectAction = useCallback(async (id: string, note?: string) => {
    setError(null);
    try {
      await shadowApi.reject(id, note);
      fetchStats();
    } catch (err) {
      if (mountedRef.current) {
        setError(err instanceof Error ? err.message : 'Failed to reject action');
      }
    }
  }, [fetchStats]);

  const undoAction = useCallback(async (id: string, reason: string) => {
    setError(null);
    try {
      await shadowApi.undo(id, reason);
      fetchStats();
    } catch (err) {
      if (mountedRef.current) {
        setError(err instanceof Error ? err.message : 'Failed to undo action');
      }
    }
  }, [fetchStats]);

  const refreshAll = useCallback(async () => {
    await Promise.all([fetchMode(), fetchPreferences(), fetchStats()]);
  }, [fetchMode, fetchPreferences, fetchStats]);

  const clearError = useCallback(() => setError(null), []);

  // ── Initial Load ────────────────────────────────────────────────────

  useEffect(() => {
    mountedRef.current = true;
    refreshAll();
    return () => {
      mountedRef.current = false;
    };
  }, [refreshAll]);

  // ── WebSocket Real-time Sync ─────────────────────────────────────────
  // Listens for shadow mode events emitted by the backend (from both
  // UI actions and Jarvis conversational commands).  This ensures the
  // dashboard stays in sync with the backend regardless of how the
  // change was initiated (SM-6: UI and Jarvis sync in real-time).

  useEffect(() => {
    if (!socket) return;

    const handlers: Array<[string, (...args: any[]) => void]> = [
      ['shadow:mode_changed', (data: any) => {
        if (data?.mode && mountedRef.current) {
          setMode(data.mode as SystemMode);
          fetchStats();
        }
      }],
      ['shadow:preference_changed', (_data: any) => {
        if (mountedRef.current) {
          fetchPreferences();
        }
      }],
      ['shadow:action_resolved', (_data: any) => {
        if (mountedRef.current) {
          fetchStats();
        }
      }],
      ['shadow:action_undone', (_data: any) => {
        if (mountedRef.current) {
          fetchStats();
        }
      }],
    ];

    // Register all handlers
    for (const [event, handler] of handlers) {
      socket.on(event, handler);
    }

    // Cleanup on unmount or socket change
    return () => {
      for (const [event, handler] of handlers) {
        socket.off(event, handler);
      }
    };
  }, [socket, fetchPreferences, fetchStats]);

  // ── Sync aiMode from SocketContext if no mode loaded yet ─────────────
  // The SocketContext has its own aiMode state that may update before
  // our fetch completes. Use it as a fallback.

  useEffect(() => {
    if (aiMode && !mode && !isLoadingMode) {
      setMode(aiMode);
    }
  }, [aiMode, mode, isLoadingMode]);

  // ── Return ───────────────────────────────────────────────────────────

  return {
    mode,
    isLoadingMode,
    preferences,
    isLoadingPreferences,
    stats,
    isLoadingStats,
    error,
    switchMode,
    setPreference,
    deletePreference,
    approveAction,
    rejectAction,
    undoAction,
    refreshAll,
    clearError,
  };
}

export default useShadowMode;
