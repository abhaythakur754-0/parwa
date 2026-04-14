/**
 * PARWA GrowthNudge — Week 16 Day 4 (F-042)
 *
 * Growth nudge alert panel showing actionable recommendations
 * based on usage pattern analysis. Sorted by severity.
 */

'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import {
  dashboardApi,
  type GrowthNudge,
  type GrowthNudgeResponse,
} from '@/lib/dashboard-api';

// ── Severity Config ───────────────────────────────────────────────────

const SEVERITY_CONFIG: Record<
  string,
  { icon: React.ReactNode; borderColor: string; bgColor: string; badgeColor: string; label: string }
> = {
  urgent: {
    borderColor: 'border-red-500/30',
    bgColor: 'bg-red-500/[0.04]',
    badgeColor: 'bg-red-500/15 text-red-400 border-red-500/20',
    label: 'Urgent',
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
      </svg>
    ),
  },
  recommendation: {
    borderColor: 'border-amber-500/25',
    bgColor: 'bg-amber-500/[0.03]',
    badgeColor: 'bg-amber-500/15 text-amber-400 border-amber-500/20',
    label: 'Recommendation',
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 18v-5.25m0 0a6.01 6.01 0 0 0 1.5-.189m-1.5.189a6.01 6.01 0 0 1-1.5-.189m3.75 7.478a12.06 12.06 0 0 1-4.5 0m3.75 2.383a14.406 14.406 0 0 1-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 1 0-7.517 0c.85.493 1.509 1.333 1.509 2.316V18" />
      </svg>
    ),
  },
  suggestion: {
    borderColor: 'border-sky-500/20',
    bgColor: 'bg-sky-500/[0.03]',
    badgeColor: 'bg-sky-500/15 text-sky-400 border-sky-500/20',
    label: 'Suggestion',
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 18.75a6 6 0 0 0 6-6v-1.5m-6 7.5a6 6 0 0 1-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 0 1-3-3V4.5a3 3 0 1 1 6 0v8.25a3 3 0 0 1-3 3Z" />
      </svg>
    ),
  },
  info: {
    borderColor: 'border-zinc-500/20',
    bgColor: 'bg-zinc-500/[0.03]',
    badgeColor: 'bg-zinc-500/15 text-zinc-400 border-zinc-500/20',
    label: 'Info',
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="m11.25 11.25.041-.02a.75.75 0 0 1 1.063.852l-.708 2.836a.75.75 0 0 0 1.063.853l.041-.021M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9-3.75h.008v.008H12V8.25Z" />
      </svg>
    ),
  },
};

const DEFAULT_CONFIG = SEVERITY_CONFIG.info;

// ── Skeleton ──────────────────────────────────────────────────────────

function NudgeSkeleton() {
  return (
    <div className="p-5 space-y-3">
      <Skeleton className="h-4 w-40 bg-white/[0.06]" />
      <div className="space-y-2.5">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-20 w-full rounded-lg bg-white/[0.04]" />
        ))}
      </div>
    </div>
  );
}

// ── Empty State ───────────────────────────────────────────────────────

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div className="w-12 h-12 rounded-xl bg-white/[0.03] border border-white/[0.06] flex items-center justify-center mb-3">
        <svg className="w-6 h-6 text-zinc-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09Z" />
        </svg>
      </div>
      <p className="text-sm text-zinc-500 font-medium">All good!</p>
      <p className="text-xs text-zinc-600 mt-1">
        No growth nudges detected at this time
      </p>
    </div>
  );
}

// ── Single Nudge Card ─────────────────────────────────────────────────

function NudgeCard({ nudge, onDismiss }: { nudge: GrowthNudge; onDismiss: (id: string) => void }) {
  const config = SEVERITY_CONFIG[nudge.severity] ?? DEFAULT_CONFIG;

  return (
    <div
      className={cn(
        'rounded-lg border p-4 transition-all duration-200',
        'hover:bg-white/[0.01]',
        config.borderColor,
        config.bgColor
      )}
    >
      <div className="flex items-start gap-3">
        {/* Icon */}
        <div className="mt-0.5 text-zinc-500 shrink-0">
          {config.icon}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0 space-y-1.5">
          {/* Title + badge */}
          <div className="flex items-center gap-2 flex-wrap">
            <h4 className="text-sm font-semibold text-zinc-200">{nudge.title}</h4>
            <span
              className={cn(
                'inline-flex px-2 py-0.5 rounded-md text-[10px] font-medium border',
                config.badgeColor
              )}
            >
              {config.label}
            </span>
          </div>

          {/* Message */}
          <p className="text-xs text-zinc-400 leading-relaxed">
            {nudge.message}
          </p>

          {/* Action row */}
          <div className="flex items-center gap-2 pt-1">
            {nudge.action_label && nudge.action_url && (
              <a
                href={nudge.action_url}
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-[11px] font-medium bg-[#FF7F11]/10 text-[#FF7F11] hover:bg-[#FF7F11]/20 transition-colors"
              >
                {nudge.action_label}
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 19.5 15-15m0 0H8.25m11.25 0v11.25" />
                </svg>
              </a>
            )}
            <button
              onClick={() => onDismiss(nudge.nudge_id)}
              className="text-[11px] text-zinc-600 hover:text-zinc-400 transition-colors ml-auto"
            >
              Dismiss
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── GrowthNudge Component ─────────────────────────────────────────────

interface GrowthNudgeProps {
  initialData?: GrowthNudgeResponse;
  isLoading?: boolean;
  className?: string;
}

export default function GrowthNudge({
  initialData,
  isLoading = false,
  className,
}: GrowthNudgeProps) {
  const [data, setData] = useState<GrowthNudgeResponse | null>(initialData ?? null);
  const [dismissedIds, setDismissedIds] = useState<Set<string>>(new Set());
  const [isFetching, setIsFetching] = useState(false);

  useEffect(() => {
    if (initialData) setData(initialData);
  }, [initialData]);

  const fetchData = useCallback(async () => {
    if (isFetching) return;
    setIsFetching(true);
    try {
      const result = await dashboardApi.getGrowthNudges();
      setData(result);
    } catch {
      // Silent fail
    } finally {
      setIsFetching(false);
    }
  }, [isFetching]);

  useEffect(() => {
    if (!initialData) fetchData();
  }, [initialData, fetchData]);

  const handleDismiss = useCallback((id: string) => {
    setDismissedIds((prev) => new Set(prev).add(id));
  }, []);

  if (isLoading || (!data && isFetching)) {
    return (
      <div className={cn('bg-[#1A1A1A] border border-white/[0.06] rounded-xl overflow-hidden', className)}>
        <NudgeSkeleton />
      </div>
    );
  }

  const visibleNudges = data?.nudges?.filter((n) => !dismissedIds.has(n.nudge_id)) ?? [];

  return (
    <div className={cn('bg-[#1A1A1A] border border-white/[0.06] rounded-xl overflow-hidden', className)}>
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-white/[0.06]">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center">
            <svg className="w-4 h-4 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 3v11.25A2.25 2.25 0 0 0 6 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0 1 18 16.5h-2.25m-7.5 0h7.5m-7.5 0-1 3m8.5-3 1 3m0 0 .5 1.5m-.5-1.5h-9.5m0 0-.5 1.5m.75-9 3-3 2.148 2.148A12.061 12.061 0 0 1 16.5 7.605" />
            </svg>
          </div>
          <div>
            <h3 className="text-sm font-semibold text-zinc-200">Growth Insights</h3>
            <p className="text-[11px] text-zinc-500">Personalized recommendations</p>
          </div>
        </div>
        {data && data.total > 0 && (
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-medium">
            {data.total} {data.total === 1 ? 'nudge' : 'nudges'}
          </span>
        )}
      </div>

      {/* Nudge List */}
      <div className="p-4 space-y-2.5">
        {visibleNudges.length === 0 ? (
          <EmptyState />
        ) : (
          visibleNudges.map((nudge) => (
            <NudgeCard key={nudge.nudge_id} nudge={nudge} onDismiss={handleDismiss} />
          ))
        )}
      </div>
    </div>
  );
}
