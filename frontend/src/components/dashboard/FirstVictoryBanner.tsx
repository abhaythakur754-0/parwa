/**
 * PARWA FirstVictoryBanner — Day 2 (O1.5)
 *
 * Celebration banner shown when AI resolves its first ticket.
 * "Your AI just resolved its first ticket! In 47 seconds."
 * Dismissible for 24h. Animated entry.
 */

'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { cn } from '@/lib/utils';
import { get, post } from '@/lib/api';

// ── Types ──────────────────────────────────────────────────────────────

interface VictoryData {
  achieved: boolean;
  ticket_id?: string;
  resolution_time_seconds?: number;
  achieved_at?: string;
  dismissed: boolean;
}

const DISMISS_KEY = 'parwa_first_victory_dismissed';

// ── Component ──────────────────────────────────────────────────────────

export default function FirstVictoryBanner() {
  const [data, setData] = useState<VictoryData | null>(null);
  const [isDismissed, setIsDismissed] = useState(false);
  const [isVisible, setIsVisible] = useState(false);

  const fetchVictory = useCallback(async () => {
    try {
      const result = await get<VictoryData>('/api/onboarding/first-victory');
      setData(result);

      // Check if previously dismissed
      const dismissedUntil = localStorage.getItem(DISMISS_KEY);
      if (dismissedUntil) {
        const until = new Date(dismissedUntil);
        if (new Date() < until) {
          setIsDismissed(true);
          return;
        }
        localStorage.removeItem(DISMISS_KEY);
      }

      if (result.achieved && !result.dismissed) {
        // Delay appearance for animation
        setTimeout(() => setIsVisible(true), 300);
      }
    } catch {
      // Endpoint not available yet
    }
  }, []);

  useEffect(() => {
    fetchVictory();
  }, [fetchVictory]);

  const handleDismiss = useCallback(async () => {
    setIsVisible(false);
    setIsDismissed(true);

    // Store dismissal for 24h
    const tomorrow = new Date(Date.now() + 24 * 60 * 60 * 1000);
    localStorage.setItem(DISMISS_KEY, tomorrow.toISOString());

    try {
      await post('/api/onboarding/first-victory', {});
    } catch {
      // Silently fail
    }
  }, []);

  // Don't render if not achieved, dismissed, or no data
  if (!data?.achieved || isDismissed || !isVisible) return null;

  const resolutionTime = data.resolution_time_seconds
    ? data.resolution_time_seconds < 60
      ? `${Math.round(data.resolution_time_seconds)} seconds`
      : `${(data.resolution_time_seconds / 60).toFixed(1)} minutes`
    : null;

  return (
    <div
      className={cn(
        'relative overflow-hidden rounded-xl border border-emerald-500/20 bg-gradient-to-r from-emerald-500/[0.08] via-emerald-500/[0.04] to-[#FF7F11]/[0.04] p-4 transition-all duration-500',
        isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 -translate-y-2'
      )}
    >
      {/* Animated confetti sparkle (CSS only) */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        <div className="absolute -top-4 -right-4 w-20 h-20 bg-emerald-400/10 rounded-full blur-2xl animate-pulse" />
        <div className="absolute -bottom-2 -left-2 w-16 h-16 bg-[#FF7F11]/10 rounded-full blur-2xl animate-pulse" style={{ animationDelay: '1s' }} />
      </div>

      <div className="relative flex items-center justify-between gap-4">
        {/* Left: Content */}
        <div className="flex items-center gap-3">
          {/* Celebration icon */}
          <div className="w-10 h-10 rounded-xl bg-emerald-500/15 flex items-center justify-center shrink-0">
            <svg className="w-5 h-5 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09ZM18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 0 0-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 0 0 2.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 0 0 2.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 0 0-2.456 2.456ZM16.894 20.567 16.5 21.75l-.394-1.183a2.25 2.25 0 0 0-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 0 0 1.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 0 0 1.423 1.423l1.183.394-1.183.394a2.25 2.25 0 0 0-1.423 1.423Z" />
            </svg>
          </div>

          <div>
            <p className="text-sm font-semibold text-emerald-300">
              Your AI just resolved its first ticket!
            </p>
            {resolutionTime && (
              <p className="text-xs text-zinc-400 mt-0.5">
                Resolved in <span className="text-emerald-400 font-medium">{resolutionTime}</span>
              </p>
            )}
          </div>
        </div>

        {/* Dismiss */}
        <button
          onClick={handleDismiss}
          className="w-7 h-7 rounded-lg flex items-center justify-center text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.06] transition-colors shrink-0"
          title="Dismiss"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>
  );
}
