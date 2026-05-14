/**
 * PARWA useSocket Hook
 *
 * Component-level Socket.io event subscription with automatic cleanup.
 *
 * Usage:
 *   const { isConnected, isReconnecting } = useSocket('ticket:new', (data) => {
 *     console.log('New ticket:', data);
 *   });
 *
 * - Registers event listener on mount
 * - Removes event listener on unmount
 * - Guards against calling without SocketProvider
 * - Returns connection state from SocketProvider context
 */

'use client';

import { useCallback, useEffect, useRef } from 'react';
import { socketClient } from '@/lib/socket-client';
import { useSocketContext } from '@/providers/SocketProvider';

// ── Types ────────────────────────────────────────────────────────────

export interface UseSocketReturn {
  /** Whether the socket is currently connected */
  isConnected: boolean;
  /** Whether the socket is attempting to reconnect */
  isReconnecting: boolean;
  /** ISO timestamp of the last successful connection */
  lastConnected: string | null;
}

// ── Hook ─────────────────────────────────────────────────────────────

/**
 * Subscribe to a Socket.io event with automatic cleanup on unmount.
 *
 * @param event - The Socket.io event name (e.g., 'ticket:new')
 * @param callback - Handler function invoked when the event fires
 * @returns Connection state from the SocketProvider context
 */
export function useSocket(
  event: string,
  callback: (...args: unknown[]) => void
): UseSocketReturn {
  // Try to access SocketProvider context; fall back to defaults if
  // the component is not wrapped in a provider (graceful degradation).
  let contextValue: UseSocketReturn;
  try {
    const ctx = useSocketContext();
    contextValue = {
      isConnected: ctx.isConnected,
      isReconnecting: ctx.isReconnecting,
      lastConnected: ctx.lastConnected,
    };
  } catch {
    // No SocketProvider — return safe defaults
    contextValue = {
      isConnected: false,
      isReconnecting: false,
      lastConnected: null,
    };
  }

  // ── Stable callback ref ──────────────────────────────────────────

  // Store the callback in a ref so we always call the latest version
  // without needing to re-register the socket listener on every render.
  const callbackRef = useRef(callback);
  callbackRef.current = callback;

  // Stable wrapper that delegates to the current callback ref
  const stableCallback = useCallback((...args: unknown[]) => {
    callbackRef.current(...args);
  }, []);

  // ── Subscribe / Unsubscribe ──────────────────────────────────────

  useEffect(() => {
    // Register the event listener
    socketClient.on(event, stableCallback);

    if (process.env.NODE_ENV === 'development') {
      console.log(`[useSocket] Subscribed to "${event}"`);
    }

    // Cleanup on unmount or when event/callback changes
    return () => {
      socketClient.off(event, stableCallback);

      if (process.env.NODE_ENV === 'development') {
        console.log(`[useSocket] Unsubscribed from "${event}"`);
      }
    };
  }, [event, stableCallback]);

  return contextValue;
}

export default useSocket;
