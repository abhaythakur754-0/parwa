/**
 * PARWA OfflineBanner
 *
 * Full-width banner that appears when the browser goes offline.
 * Disappears automatically when connectivity is restored.
 * Accessible: role="alert", aria-live announcements, keyboard dismiss.
 */

'use client';

import React, { useEffect, useState } from 'react';
import { useNetworkStatus } from '@/hooks/useNetworkStatus';

export function OfflineBanner() {
  const { isOffline, wasOffline, lastChange } = useNetworkStatus();
  const [showBackOnline, setShowBackOnline] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  // When we come back online after being offline, show "Back online" briefly
  useEffect(() => {
    if (wasOffline && lastChange === 'online') {
      setShowBackOnline(true);
      setDismissed(false);
      const timer = setTimeout(() => setShowBackOnline(false), 3000);
      return () => clearTimeout(timer);
    }
  }, [wasOffline, lastChange]);

  // Reset dismissed when going offline again
  useEffect(() => {
    if (isOffline) {
      setDismissed(false);
    }
  }, [isOffline]);

  const handleDismiss = () => {
    setDismissed(true);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape' || e.key === 'Enter') {
      setDismissed(true);
    }
  };

  // Don't show if online and no "back online" message
  if (!isOffline && !showBackOnline) return null;

  // Don't show if dismissed
  if (dismissed) return null;

  // Back online state
  if (showBackOnline && !isOffline) {
    return (
      <div
        role="status"
        aria-live="polite"
        data-testid="offline-banner"
        className="fixed top-0 left-0 right-0 z-[200] flex items-center justify-between px-4 py-2 bg-emerald-500/95 backdrop-blur-sm text-white text-sm"
      >
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
          </svg>
          <span className="font-medium">Back online</span>
        </div>
      </div>
    );
  }

  // Offline state
  return (
    <div
      role="alert"
      aria-live="assertive"
      data-testid="offline-banner"
      className="fixed top-0 left-0 right-0 z-[200] flex items-center justify-between px-4 py-2 bg-red-500/95 backdrop-blur-sm text-white text-sm"
    >
      <div className="flex items-center gap-2">
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
        </svg>
        <span className="font-medium">You are offline — changes will sync when you reconnect</span>
      </div>
      <button
        onClick={handleDismiss}
        onKeyDown={handleKeyDown}
        className="p-1 rounded hover:bg-white/20 transition-colors"
        aria-label="Dismiss offline banner"
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
}

export default OfflineBanner;
