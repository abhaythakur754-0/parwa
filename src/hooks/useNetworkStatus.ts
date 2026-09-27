/**
 * PARWA useNetworkStatus Hook
 *
 * Tracks browser online/offline state using navigator.onLine
 * and listens for 'online'/'offline' events.
 *
 * Also tracks the last time connectivity changed and provides
 * a wasOffline flag for recovery scenarios.
 *
 * Usage:
 *   const { isOnline, isOffline, wasOffline, lastChangedAt } = useNetworkStatus();
 */

'use client';

import { useState, useEffect, useCallback, useRef } from 'react';

export interface NetworkStatus {
  /** Whether the browser reports being online */
  isOnline: boolean;
  /** Whether the browser reports being offline */
  isOffline: boolean;
  /** Whether the browser was offline at any point since mount (resets on manual reset) */
  wasOffline: boolean;
  /** ISO timestamp of the last connectivity change */
  lastChangedAt: string | null;
  /** The type of the last connectivity change */
  lastChange: 'online' | 'offline' | null;
  /** Number of times connectivity was lost since mount */
  offlineCount: number;
  /** Reset wasOffline flag */
  resetWasOffline: () => void;
}

export function useNetworkStatus(): NetworkStatus {
  const [isOnline, setIsOnline] = useState<boolean>(() => {
    if (typeof navigator !== 'undefined') {
      return navigator.onLine;
    }
    return true; // SSR default
  });

  const [lastChangedAt, setLastChangedAt] = useState<string | null>(null);
  const [lastChange, setLastChange] = useState<'online' | 'offline' | null>(null);
  const [offlineCount, setOfflineCount] = useState(0);
  const [wasOffline, setWasOffline] = useState(false);
  const mountedRef = useRef(true);

  const resetWasOffline = useCallback(() => {
    setWasOffline(false);
  }, []);

  useEffect(() => {
    mountedRef.current = true;

    const handleOnline = () => {
      if (!mountedRef.current) return;
      setIsOnline(true);
      setLastChangedAt(new Date().toISOString());
      setLastChange('online');
    };

    const handleOffline = () => {
      if (!mountedRef.current) return;
      setIsOnline(false);
      setWasOffline(true);
      setOfflineCount((prev) => prev + 1);
      setLastChangedAt(new Date().toISOString());
      setLastChange('offline');
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      mountedRef.current = false;
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  return {
    isOnline,
    isOffline: !isOnline,
    wasOffline,
    lastChangedAt,
    lastChange,
    offlineCount,
    resetWasOffline,
  };
}
