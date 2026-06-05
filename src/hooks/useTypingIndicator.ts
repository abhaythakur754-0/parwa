/**
 * PARWA useTypingIndicator Hook
 *
 * Provides reactive typing indicator state for a given context (ticket, chat, etc.).
 * Connects to the useTypingStore Zustand store and uses useSocket for real-time
 * event subscription with automatic cleanup.
 *
 * Socket.io events:
 *   typing:start  — { contextId, userId, userName }
 *   typing:stop   — { contextId, userId, userName }
 *
 * Also compatible with existing events:
 *   typing:start  — { ticket_id, user_id, user_name }
 *   typing:stop   — { ticket_id, user_id }
 *
 * Features:
 *   - Auto-cleanup: stops typing on unmount
 *   - Auto-clear: typing indicators expire after 3 seconds of no update
 *   - Reactive: re-renders when typing state changes for the given context
 */

'use client';

import { useCallback, useEffect, useRef, useMemo } from 'react';
import { useTypingStore } from '@/lib/typing-store';
import { useSocket } from '@/hooks/useSocket';
import { socketClient } from '@/lib/socket-client';

// ── Types ────────────────────────────────────────────────────────────

export interface TypingUser {
  userId: string;
  userName: string;
  startedAt: number;
}

export interface UseTypingIndicatorOptions {
  /** Current user ID (for emitting typing events). Falls back to useAuth if not provided. */
  userId?: string;
  /** Current user name (for emitting typing events). Falls back to useAuth if not provided. */
  userName?: string;
}

export interface UseTypingIndicatorReturn {
  /** List of users currently typing in the given context */
  typingUsers: TypingUser[];
  /** Whether anyone is currently typing in the given context */
  isTyping: boolean;
  /** Emit a typing:start event for a context */
  startTyping: (contextId: string) => void;
  /** Emit a typing:stop event for a context */
  stopTyping: (contextId: string) => void;
}

// ── Constants ────────────────────────────────────────────────────────

/** Typing indicators expire after 3 seconds of no update */
const TYPING_EXPIRY_MS = 3000;

/** How often to check for expired typing indicators */
const EXPIRY_CHECK_INTERVAL_MS = 500;

// ── Payload Normalizer ───────────────────────────────────────────────

/**
 * Normalize incoming typing event payloads.
 * Supports both the new format (contextId, userId, userName) and the
 * legacy format (ticket_id, user_id, user_name).
 */
function normalizeTypingPayload(data: unknown): {
  contextId: string;
  userId: string;
  userName: string;
} | null {
  if (!data || typeof data !== 'object') return null;

  const d = data as Record<string, unknown>;

  const contextId = (d.contextId as string) || (d.ticket_id as string);
  const userId = (d.userId as string) || (d.user_id as string);
  const userName = (d.userName as string) || (d.user_name as string) || '';

  if (!contextId || !userId) return null;

  return { contextId, userId, userName };
}

// ── Hook ─────────────────────────────────────────────────────────────

/**
 * Subscribe to typing indicator events and provide reactive state
 * for a given context (ticket, chat, etc.).
 *
 * @param contextId - The context to track typing for (e.g., ticket ID). If omitted, typingUsers/isTyping will be empty.
 * @param options - Optional userId/userName for emitting typing events.
 */
export function useTypingIndicator(
  contextId?: string,
  options?: UseTypingIndicatorOptions
): UseTypingIndicatorReturn {
  // ── Refs for stable callbacks ──────────────────────────────────────

  const contextRef = useRef(contextId);
  contextRef.current = contextId;

  const userIdRef = useRef(options?.userId);
  const userNameRef = useRef(options?.userName);
  userIdRef.current = options?.userId;
  userNameRef.current = options?.userName;

  // Track whether we've started typing (for auto-cleanup on unmount)
  const activeTypingContextRef = useRef<string | null>(null);

  // ── Subscribe to Socket.io Events ──────────────────────────────────

  useSocket('typing:start', (...args: unknown[]) => {
    const payload = normalizeTypingPayload(args[0]);
    if (!payload) return;

    const store = useTypingStore.getState();
    // Only update if it's for our context or if we're tracking all contexts
    if (!contextRef.current || payload.contextId === contextRef.current) {
      store.startTyping(payload.contextId, payload.userId, payload.userName);
    } else {
      // Still update the store for other contexts so data is available
      store.startTyping(payload.contextId, payload.userId, payload.userName);
    }
  });

  useSocket('typing:stop', (...args: unknown[]) => {
    const payload = normalizeTypingPayload(args[0]);
    if (!payload) return;

    const store = useTypingStore.getState();
    store.stopTyping(payload.contextId, payload.userId);
  });

  // ── Reactive Store State ───────────────────────────────────────────

  // Subscribe to the typingUsers map for reactivity
  const typingUsersMap = useTypingStore((state) => state.typingUsers);

  const typingUsers = useMemo<TypingUser[]>(() => {
    if (!contextId) return [];
    return (typingUsersMap.get(contextId) || []) as TypingUser[];
  }, [typingUsersMap, contextId]);

  const isTyping = typingUsers.length > 0;

  // ── Auto-Clear: Expire Stale Typing Indicators ─────────────────────

  useEffect(() => {
    if (!contextId) return;

    const interval = setInterval(() => {
      const store = useTypingStore.getState();
      const users = store.getTypingUsers(contextId);
      const now = Date.now();

      for (const user of users) {
        if (now - user.startedAt > TYPING_EXPIRY_MS) {
          store.stopTyping(contextId, user.userId);
        }
      }
    }, EXPIRY_CHECK_INTERVAL_MS);

    return () => clearInterval(interval);
  }, [contextId]);

  // ── Action: Start Typing ───────────────────────────────────────────

  const startTyping = useCallback(
    (targetContextId: string) => {
      const uid = userIdRef.current;
      const uname = userNameRef.current;

      if (!uid) {
        if (process.env.NODE_ENV === 'development') {
          console.warn('[useTypingIndicator] Cannot start typing — no userId provided');
        }
        return;
      }

      // Track for auto-cleanup
      activeTypingContextRef.current = targetContextId;

      // Update local store
      const store = useTypingStore.getState();
      store.startTyping(targetContextId, uid, uname || '');

      // Emit to other users via Socket.io
      socketClient.emit('typing:start', {
        contextId: targetContextId,
        userId: uid,
        userName: uname || '',
        // Also send legacy fields for backward compatibility
        ticket_id: targetContextId,
        user_id: uid,
        user_name: uname || '',
      });
    },
    []
  );

  // ── Action: Stop Typing ────────────────────────────────────────────

  const stopTyping = useCallback(
    (targetContextId: string) => {
      const uid = userIdRef.current;

      if (!uid) return;

      // Clear active tracking
      if (activeTypingContextRef.current === targetContextId) {
        activeTypingContextRef.current = null;
      }

      // Update local store
      const store = useTypingStore.getState();
      store.stopTyping(targetContextId, uid);

      // Emit to other users via Socket.io
      socketClient.emit('typing:stop', {
        contextId: targetContextId,
        userId: uid,
        // Also send legacy fields for backward compatibility
        ticket_id: targetContextId,
        user_id: uid,
      });
    },
    []
  );

  // ── Auto-Cleanup on Unmount ────────────────────────────────────────

  useEffect(() => {
    return () => {
      const activeContext = activeTypingContextRef.current;
      const uid = userIdRef.current;

      if (activeContext && uid) {
        // Update local store
        const store = useTypingStore.getState();
        store.stopTyping(activeContext, uid);

        // Emit stop to other users
        socketClient.emit('typing:stop', {
          contextId: activeContext,
          userId: uid,
          ticket_id: activeContext,
          user_id: uid,
        });

        activeTypingContextRef.current = null;
      }
    };
  }, []);

  return {
    typingUsers,
    isTyping,
    startTyping,
    stopTyping,
  };
}

export default useTypingIndicator;
