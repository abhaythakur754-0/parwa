/**
 * PARWA AlertBanner — Week 16 Day 1 (F-036)
 *
 * Dashboard anomaly alert banners.
 * Shows detected anomalies with severity badges,
 * auto-dismiss after 30 seconds, and smooth collapse animation.
 */

'use client';

import React, { useState, useCallback } from 'react';
import { cn } from '@/lib/utils';
import type { AnomalyItem } from '@/lib/dashboard-api';

// ── Severity Badge Config ────────────────────────────────────────────

const SEVERITY_STYLES: Record<
  string,
  { badgeBg: string; badgeText: string; borderColor: string }
> = {
  high: {
    badgeBg: 'bg-red-500/15 border-red-500/30',
    badgeText: 'text-red-400',
    borderColor: 'border-l-red-500',
  },
  medium: {
    badgeBg: 'bg-amber-500/15 border-amber-500/30',
    badgeText: 'text-amber-400',
    borderColor: 'border-l-amber-500',
  },
  low: {
    badgeBg: 'bg-sky-500/15 border-sky-500/30',
    badgeText: 'text-sky-400',
    borderColor: 'border-l-sky-500',
  },
};

const DEFAULT_SEVERITY = {
  badgeBg: 'bg-zinc-500/15 border-zinc-500/30',
  badgeText: 'text-zinc-400',
  borderColor: 'border-l-zinc-500',
};

// ── Auto-dismiss timing (ms) ─────────────────────────────────────────

const AUTO_DISMISS_MS = 30_000;

// ── Single Alert Item ────────────────────────────────────────────────

interface AlertItemProps {
  anomaly: AnomalyItem;
  onDismiss: (id: string) => void;
}

function AlertItem({ anomaly, onDismiss }: AlertItemProps) {
  const [isDismissing, setIsDismissing] = useState(false);
  const styles = SEVERITY_STYLES[anomaly.severity] ?? DEFAULT_SEVERITY;

  const handleDismiss = useCallback(() => {
    setIsDismissing(true);
    // Wait for collapse animation to finish, then remove
    setTimeout(() => onDismiss(anomaly.detected_at), 300);
  }, [anomaly.detected_at, onDismiss]);

  // Auto-dismiss
  useEffect(() => {
    const timer = setTimeout(handleDismiss, AUTO_DISMISS_MS);
    return () => clearTimeout(timer);
  }, [handleDismiss]);

  // Time until auto-dismiss for display
  const [timeLeft, setTimeLeft] = useState(AUTO_DISMISS_MS / 1000);

  useEffect(() => {
    const countdown = setInterval(() => {
      setTimeLeft((prev) => Math.max(0, prev - 1));
    }, 1000);
    return () => clearInterval(countdown);
  }, []);

  return (
    <div
      className={cn(
        'flex items-start gap-3 px-4 py-3 transition-all duration-300',
        isDismissing
          ? 'opacity-0 max-h-0 overflow-hidden py-0 px-0 my-0'
          : 'opacity-100 max-h-[120px]'
      )}
    >
      {/* Warning icon */}
      <div className="shrink-0 mt-0.5">
        <svg
          className="w-4.5 h-4.5"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1.8}
          style={{ color: anomaly.severity === 'high' ? '#ef4444' : '#f59e0b' }}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z"
          />
        </svg>
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          {/* Severity badge */}
          <span
            className={cn(
              'inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border',
              styles.badgeBg,
              styles.badgeText
            )}
          >
            {anomaly.severity}
          </span>

          {/* Alert type label */}
          <span className="text-[10px] text-zinc-600 uppercase tracking-wider">
            {anomaly.type.replace(/_/g, ' ')}
          </span>
        </div>

        <p className="text-sm text-zinc-300 mt-1 leading-relaxed">
          {anomaly.message}
        </p>
      </div>

      {/* Dismiss button */}
      <button
        onClick={handleDismiss}
        className="shrink-0 p-1 rounded-md text-zinc-600 hover:text-zinc-400 hover:bg-white/[0.05] transition-colors"
        aria-label="Dismiss alert"
      >
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
}

// ── AlertBanner Component ────────────────────────────────────────────

interface AlertBannerProps {
  anomalies: AnomalyItem[];
  className?: string;
}

export default function AlertBanner({
  anomalies,
  className,
}: AlertBannerProps) {
  // Track dismissed anomaly IDs to allow the user to hide individual alerts
  const [dismissedIds, setDismissedIds] = useState<Set<string>>(new Set());

  // Derive visible anomalies from props + dismissed state
  const visibleAnomalies = anomalies.filter(
    (a) => !dismissedIds.has(a.detected_at)
  );

  const isVisible = visibleAnomalies.length > 0;

  // Dismiss a single alert by its detected_at timestamp
  const handleDismiss = useCallback((detectedAt: string) => {
    setDismissedIds((prev) => {
      const next = new Set(prev);
      next.add(detectedAt);
      return next;
    });
  }, []);

  // Don't render if no anomalies or all dismissed
  if (!isVisible) {
    return null;
  }

  return (
    <div className={cn('space-y-2', className)}>
      {visibleAnomalies.map((anomaly) => {
        const styles = SEVERITY_STYLES[anomaly.severity] ?? DEFAULT_SEVERITY;

        return (
          <div
            key={anomaly.detected_at}
            className={cn(
              'bg-[#1A1A1A] border border-white/[0.06] rounded-xl overflow-hidden',
              'border-l-4',
              styles.borderColor,
              'animate-[alertSlideDown_0.4s_ease-out]'
            )}
          >
            <AlertItem anomaly={anomaly} onDismiss={handleDismiss} />
          </div>
        );
      })}
    </div>
  );
}
