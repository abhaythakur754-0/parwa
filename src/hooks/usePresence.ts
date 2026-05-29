/**
 * PARWA usePresence Hook
 *
 * Provides reactive presence state showing which users/agents are currently online.
 * Connects to the usePresenceStore Zustand store and uses useSocket for real-time
 * event subscription with automatic cleanup.
 *
 * Socket.io events (new format):
 *   presence:join       — { userId, userName, avatar?, status? }
 *   presence:leave      — { userId }
 *   presence:heartbeat  — { userId, status? }
 *
 * Also compatible with existing events (legacy format):
 *   presence:online     — { agent_id, name, avatar?, status? }
 *   presence:offline    — { agent_id }
 *   presence:status     — { agent_id, status }
 *   presence:bulk       — { agents: [...] }
 *
 * Features:
 *   - Auto-subscribe on mount, unsubscribe on unmount
 *   - Fetches initial presence data on mount
 *   - Reactive: re-renders when online users change
 */

'use client';

import { useCallback, useEffect, useMemo } from 'react';
import { usePresenceStore, AgentPresence } from '@/lib/presence-store';
import { useSocket } from '@/hooks/useSocket';

// ── Types ────────────────────────────────────────────────────────────

export interface UsePresenceReturn {
  /** List of currently online users/agents */
  onlineUsers: AgentPresence[];
  /** Check if a specific user is online */
  isOnline: (userId: string) => boolean;
  /** Number of currently online users */
  onlineCount: number;
}

// ── Payload Normalizers ──────────────────────────────────────────────

/**
 * Normalize a presence:join payload.
 * Supports both new format (userId, userName) and legacy format (agent_id, name).
 */
function normalizeJoinPayload(data: unknown): {
  agentId: string;
  name: string;
  avatar?: string;
  status?: string;
  currentTicketId?: string;
} | null {
  if (!data || typeof data !== 'object') return null;

  const d = data as Record<string, unknown>;

  const agentId = (d.userId as string) || (d.agent_id as string);
  const name = (d.userName as string) || (d.name as string) || '';

  if (!agentId) return null;

  return {
    agentId,
    name,
    avatar: (d.avatar as string) || undefined,
    status: (d.status as string) || undefined,
    currentTicketId: (d.currentTicketId as string) || (d.current_ticket_id as string) || undefined,
  };
}

/**
 * Normalize a presence:leave payload.
 * Supports both new format (userId) and legacy format (agent_id).
 */
function normalizeLeavePayload(data: unknown): string | null {
  if (!data || typeof data !== 'object') return null;

  const d = data as Record<string, unknown>;
  return (d.userId as string) || (d.agent_id as string) || null;
}

/**
 * Normalize a presence:heartbeat payload.
 * Heartbeat refreshes the user's lastSeen timestamp and optionally updates status.
 */
function normalizeHeartbeatPayload(data: unknown): {
  agentId: string;
  status?: string;
} | null {
  if (!data || typeof data !== 'object') return null;

  const d = data as Record<string, unknown>;
  const agentId = (d.userId as string) || (d.agent_id as string);

  if (!agentId) return null;

  return {
    agentId,
    status: (d.status as string) || undefined,
  };
}

// ── Hook ─────────────────────────────────────────────────────────────

/**
 * Subscribe to presence events and provide reactive online user state.
 * Auto-subscribes on mount and unsubscribes on unmount.
 */
export function usePresence(): UsePresenceReturn {
  // ── Subscribe to Socket.io Events ──────────────────────────────────

  // New format: presence:join
  useSocket('presence:join', (...args: unknown[]) => {
    const payload = normalizeJoinPayload(args[0]);
    if (!payload) return;

    usePresenceStore.getState().setOnline({
      agent_id: payload.agentId,
      name: payload.name,
      avatar: payload.avatar,
      status: (payload.status as 'available' | 'busy' | 'away') || undefined,
      current_ticket_id: payload.currentTicketId,
    });
  });

  // Legacy format: presence:online
  useSocket('presence:online', (...args: unknown[]) => {
    const data = args[0] as Record<string, unknown> | undefined;
    if (!data?.agent_id) return;

    usePresenceStore.getState().setOnline({
      agent_id: data.agent_id as string,
      name: (data.name as string) || '',
      avatar: data.avatar as string | undefined,
      status: data.status as 'available' | 'busy' | 'away' | undefined,
      current_ticket_id: data.current_ticket_id as string | undefined,
    });
  });

  // New format: presence:leave
  useSocket('presence:leave', (...args: unknown[]) => {
    const agentId = normalizeLeavePayload(args[0]);
    if (!agentId) return;

    usePresenceStore.getState().setOffline(agentId);
  });

  // Legacy format: presence:offline
  useSocket('presence:offline', (...args: unknown[]) => {
    const data = args[0] as Record<string, unknown> | undefined;
    if (!data?.agent_id) return;

    usePresenceStore.getState().setOffline(data.agent_id as string);
  });

  // New format: presence:heartbeat
  useSocket('presence:heartbeat', (...args: unknown[]) => {
    const payload = normalizeHeartbeatPayload(args[0]);
    if (!payload) return;

    const store = usePresenceStore.getState();

    // Refresh lastSeen by calling setOnline with existing data
    const existing = store.getAgent(payload.agentId);
    if (existing) {
      store.setOnline({
        agent_id: payload.agentId,
        name: existing.name,
        avatar: existing.avatar,
        status: payload.status
          ? (payload.status as 'available' | 'busy' | 'away')
          : existing.status,
        current_ticket_id: existing.currentTicketId,
      });
    }
  });

  // Legacy format: presence:status
  useSocket('presence:status', (...args: unknown[]) => {
    const data = args[0] as Record<string, unknown> | undefined;
    if (!data?.agent_id || !data?.status) return;

    usePresenceStore.getState().updateStatus(
      data.agent_id as string,
      data.status as 'available' | 'busy' | 'away'
    );
  });

  // Legacy format: presence:bulk
  useSocket('presence:bulk', (...args: unknown[]) => {
    const data = args[0] as { agents: unknown[] } | undefined;
    if (!data?.agents || !Array.isArray(data.agents)) return;

    usePresenceStore.getState().setBulk(
      data.agents as Array<{
        agent_id: string;
        name: string;
        avatar?: string;
        status: 'available' | 'busy' | 'away';
        last_seen?: string;
        current_ticket_id?: string;
      }>
    );
  });

  // ── Fetch Initial Presence Data ────────────────────────────────────

  useEffect(() => {
    usePresenceStore.getState().fetchPresence();
  }, []);

  // ── Reactive Store State ───────────────────────────────────────────

  const agents = usePresenceStore((state) => state.agents);
  const onlineCount = usePresenceStore((state) => state.onlineCount);

  const onlineUsers = useMemo<AgentPresence[]>(
    () => [...agents.values()].filter((a) => a.status !== 'offline'),
    [agents]
  );

  // ── Derived Functions ──────────────────────────────────────────────

  const isOnline = useCallback(
    (userId: string): boolean => {
      return usePresenceStore.getState().isOnline(userId);
    },
    []
  );

  return {
    onlineUsers,
    isOnline,
    onlineCount,
  };
}

export default usePresence;
