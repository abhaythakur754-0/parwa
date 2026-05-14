/**
 * PARWA Polling Fallback Hook
 *
 * When Socket.io is disconnected, automatically falls back to
 * HTTP polling at a configurable interval. Stops polling when
 * Socket.io reconnects.
 *
 * Usage:
 *   usePollingFallback('/api/v1/tickets', { interval: 10000, enabled: !isConnected })
 */

import { useEffect, useRef, useCallback, useState } from 'react';

interface PollingOptions {
  /** Polling interval in ms (default: 10000) */
  interval?: number;
  /** Whether polling is active (default: true) */
  enabled?: boolean;
  /** Callback when data is received */
  onData?: (data: unknown) => void;
  /** Callback on error */
  onError?: (error: Error) => void;
}

interface PollingState {
  isPolling: boolean;
  lastPolledAt: string | null;
  pollCount: number;
  error: Error | null;
}

export function usePollingFallback(
  endpoint: string,
  options: PollingOptions = {}
): PollingState & { refetch: () => Promise<void> } {
  const { interval = 10000, enabled = true, onData, onError } = options;
  const [state, setState] = useState<PollingState>({
    isPolling: false,
    lastPolledAt: null,
    pollCount: 0,
    error: null,
  });

  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const mountedRef = useRef(true);

  const fetchEndpoint = useCallback(async () => {
    const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    try {
      const res = await fetch(`${API_BASE}${endpoint}`, {
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
      });

      if (!mountedRef.current) return;

      if (res.ok) {
        const data = await res.json();
        onData?.(data);
        setState(prev => ({
          isPolling: true,
          lastPolledAt: new Date().toISOString(),
          pollCount: prev.pollCount + 1,
          error: null,
        }));
      } else {
        const err = new Error(`Poll failed: ${res.status}`);
        onError?.(err);
        setState(prev => ({ ...prev, error: err }));
      }
    } catch (err) {
      if (!mountedRef.current) return;
      const error = err instanceof Error ? err : new Error(String(err));
      onError?.(error);
      setState(prev => ({ ...prev, error }));
    }
  }, [endpoint, onData, onError]);

  // Start/stop polling based on enabled flag
  useEffect(() => {
    if (!enabled) {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
      setState(prev => ({ ...prev, isPolling: false }));
      return;
    }

    // Initial fetch
    fetchEndpoint();

    // Set up interval
    timerRef.current = setInterval(fetchEndpoint, interval);
    setState(prev => ({ ...prev, isPolling: true }));

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [enabled, interval, fetchEndpoint]);

  // Cleanup on unmount
  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  return {
    ...state,
    refetch: fetchEndpoint,
  };
}
