/**
 * PARWA FirstVictoryBanner — Day 2 (O1.5)
 *
 * Celebration banner shown when the AI resolves its first ticket.
 * Displays: "Your AI just resolved its first ticket! In X seconds."
 * Appears for 24 hours with dismiss option.
 * Animated entry with confetti-like accent styling.
 * Checks onboarding state via API.
 */

'use client';

import React, { useState, useEffect } from 'react';
import { get, post } from '@/lib/api';
import toast from 'react-hot-toast';

// ── Types ──────────────────────────────────────────────────────────────

interface FirstVictoryData {
  achieved: boolean;
  ticket_id?: string;
  ticket_subject?: string;
  resolution_time_seconds?: number;
  achieved_at?: string;
  dismissed: boolean;
}

// ── Component ──────────────────────────────────────────────────────────

export default function FirstVictoryBanner() {
  const [victory, setVictory] = useState<FirstVictoryData | null>(null);
  const [isVisible, setIsVisible] = useState(false);
  const [isDismissing, setIsDismissing] = useState(false);

  useEffect(() => {
    // Check if victory has been achieved and not dismissed
    get<FirstVictoryData>('/api/onboarding/first-victory')
      .then((data) => {
        setVictory(data);
        // Show banner if achieved and not dismissed
        if (data?.achieved && !data?.dismissed) {
          // Check if within 24 hours
          if (data.achieved_at) {
            const elapsed = Date.now() - new Date(data.achieved_at).getTime();
            const twentyFourHours = 24 * 60 * 60 * 1000;
            if (elapsed < twentyFourHours) {
              // Slight delay for animation effect
              setTimeout(() => setIsVisible(true), 500);
            }
          }
        }
      })
      .catch(() => {
        // Endpoint may not exist yet — silent fail
      });
  }, []);

  const handleDismiss = async () => {
    setIsDismissing(true);
    try {
      await post('/api/onboarding/first-victory/dismiss', {});
    } catch {
      // Store in localStorage as fallback
      localStorage.setItem('parwa_first_victory_dismissed', 'true');
    }
    setTimeout(() => setIsVisible(false), 300);
  };

  if (!isVisible || !victory?.achieved) return null;

  const seconds = victory.resolution_time_seconds || 0;
  const formattedTime = seconds < 60
    ? `${seconds}s`
    : `${Math.floor(seconds / 60)}m ${seconds % 60}s`;

  return (
    <div
      className={`relative overflow-hidden rounded-xl border border-orange-500/20 bg-gradient-to-r from-orange-500/10 via-amber-500/5 to-orange-500/10 p-5 transition-all duration-500 ${
        isDismissing ? 'opacity-0 -translate-y-2' : 'opacity-100 translate-y-0'
      }`}
    >
      {/* Animated gradient overlay */}
      <div className="absolute inset-0 bg-gradient-to-r from-orange-500/5 to-transparent animate-pulse pointer-events-none" />

      {/* Content */}
      <div className="relative flex items-start justify-between gap-4">
        <div className="flex items-start gap-4">
          {/* Trophy icon */}
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-orange-500 to-amber-400 flex items-center justify-center shadow-lg shadow-orange-500/20 shrink-0">
            <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 18.75h-9m9 0a3 3 0 0 1 3 3h-15a3 3 0 0 1 3-3m9 0v-3.375c0-.621-.503-1.125-1.125-1.125h-.871M7.5 18.75v-3.375c0-.621.504-1.125 1.125-1.125h.872m5.007 0H9.497m5.007 0a7.454 7.454 0 0 1-.982-3.172M9.497 14.25a7.454 7.454 0 0 0 .981-3.172M5.25 4.236c-.982.143-1.954.317-2.916.52A6.003 6.003 0 0 0 7.73 9.728M5.25 4.236V4.5c0 2.108.966 3.99 2.48 5.228M5.25 4.236V2.721C7.456 2.41 9.71 2.25 12 2.25c2.291 0 4.545.16 6.75.47v1.516M18.75 4.236c.982.143 1.954.317 2.916.52A6.003 6.003 0 0 1 16.27 9.728M18.75 4.236V4.5c0 2.108-.966 3.99-2.48 5.228m0 0a6.023 6.023 0 0 1-2.77.853m0 0H10.5m2.27-.853a6.02 6.02 0 0 1-1.424-.856" />
            </svg>
          </div>

          <div>
            <h3 className="text-base font-bold text-white">
              First Victory! 🎉
            </h3>
            <p className="text-sm text-zinc-300 mt-1">
              Your AI just resolved its first ticket{victory.ticket_subject ? ` — "${victory.ticket_subject}"` : ''} in{' '}
              <span className="font-bold text-orange-400">{formattedTime}</span>.
            </p>
            <p className="text-xs text-zinc-500 mt-1">
              This is just the beginning. Your AI will get faster and more accurate with every interaction.
            </p>
          </div>
        </div>

        {/* Dismiss button */}
        <button
          onClick={handleDismiss}
          className="shrink-0 w-8 h-8 rounded-lg flex items-center justify-center text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.05] transition-colors"
          title="Dismiss"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>
  );
}
