/**
 * PARWA AdaptationTracker — Week 16 Day 3 (F-039)
 *
 * 30-day AI learning progress tracker with dual-line chart
 * comparing AI vs human CSAT accuracy over time.
 * Shows improvement %, best/worst days, mistake rates,
 * training runs, and drift reports.
 */

'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import {
  dashboardApi,
  type AdaptationDayData,
  type AdaptationTrackerResponse,
} from '@/lib/dashboard-api';

// ── Color Palette ─────────────────────────────────────────────────────

const COLORS = {
  ai: '#FF7F11',        // Primary orange — AI accuracy line
  human: '#3B82F6',     // Blue — Human accuracy line
  gap: '#22C55E',       // Green — Gap fill
  improvement: '#22C55E',
  decline: '#EF4444',
  neutral: '#71717A',
  bg: '#1A1A1A',
  border: 'rgba(255,255,255,0.06)',
};

// ── Skeleton Loader ───────────────────────────────────────────────────

function ChartSkeleton() {
  return (
    <div className="p-5 space-y-4">
      <div className="flex items-center gap-3">
        <Skeleton className="w-9 h-9 rounded-lg bg-white/[0.06]" />
        <div className="space-y-1.5">
          <Skeleton className="h-4 w-36 bg-white/[0.06]" />
          <Skeleton className="h-3 w-48 bg-white/[0.04]" />
        </div>
      </div>
      <Skeleton className="w-full h-[240px] rounded-lg bg-white/[0.04]" />
      <div className="grid grid-cols-4 gap-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-16 rounded-lg bg-white/[0.04]" />
        ))}
      </div>
    </div>
  );
}

// ── Empty State ───────────────────────────────────────────────────────

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="w-12 h-12 rounded-xl bg-white/[0.03] border border-white/[0.06] flex items-center justify-center mb-3">
        <svg className="w-6 h-6 text-zinc-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 0 1 3 19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V8.625ZM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V4.125Z" />
        </svg>
      </div>
      <p className="text-sm text-zinc-500 font-medium">No adaptation data yet</p>
      <p className="text-xs text-zinc-600 mt-1">
        AI accuracy metrics will appear once tickets are resolved
      </p>
    </div>
  );
}

// ── Metric Card ───────────────────────────────────────────────────────

function MetricCard({
  label,
  value,
  sublabel,
  icon,
  variant = 'default',
}: {
  label: string;
  value: string;
  sublabel?: string;
  icon: React.ReactNode;
  variant?: 'default' | 'success' | 'warning' | 'danger';
}) {
  const variantStyles = {
    default: 'border-white/[0.06]',
    success: 'border-emerald-500/20 bg-emerald-500/[0.03]',
    warning: 'border-amber-500/20 bg-amber-500/[0.03]',
    danger: 'border-red-500/20 bg-red-500/[0.03]',
  };

  return (
    <div
      className={cn(
        'rounded-lg border p-3 space-y-1',
        variantStyles[variant]
      )}
    >
      <div className="flex items-center gap-2">
        <span className="text-zinc-500">{icon}</span>
        <span className="text-[11px] font-medium text-zinc-500 uppercase tracking-wider">
          {label}
        </span>
      </div>
      <p className="text-lg font-bold text-zinc-100">{value}</p>
      {sublabel && (
        <p className="text-[11px] text-zinc-500">{sublabel}</p>
      )}
    </div>
  );
}

// ── Custom Tooltip ────────────────────────────────────────────────────

function CustomTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ value: number; dataKey: string; color: string }>;
  label?: string;
}) {
  if (!active || !payload?.length) return null;

  return (
    <div className="bg-[#222] border border-white/[0.08] rounded-lg px-3 py-2 shadow-xl">
      <p className="text-xs font-medium text-zinc-400 mb-1.5">{label}</p>
      {payload.map((entry) => (
        <div key={entry.dataKey} className="flex items-center gap-2 text-xs">
          <span
            className="w-2 h-2 rounded-full"
            style={{ backgroundColor: entry.color }}
          />
          <span className="text-zinc-400 capitalize">
            {entry.dataKey.replace(/_/g, ' ')}
          </span>
          <span className="text-zinc-200 font-semibold ml-auto">
            {entry.value.toFixed(1)}{' '}
            <span className="text-zinc-500 font-normal">/ 5.0</span>
          </span>
        </div>
      ))}
    </div>
  );
}

// ── Mistake Rate Bar ──────────────────────────────────────────────────

function MistakeRateBar({ rate }: { rate: number }) {
  const color =
    rate === 0 ? COLORS.neutral :
    rate < 5 ? COLORS.improvement :
    rate < 10 ? '#F59E0B' :
    COLORS.decline;

  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{
            width: `${Math.min(rate * 5, 100)}%`,
            backgroundColor: color,
          }}
        />
      </div>
      <span className="text-xs font-medium" style={{ color }}>
        {rate.toFixed(1)}%
      </span>
    </div>
  );
}

// ── AdaptationTracker Component ───────────────────────────────────────

interface AdaptationTrackerProps {
  /** Pre-loaded data (from parent) */
  initialData?: AdaptationTrackerResponse;
  /** Whether parent is still loading */
  isLoading?: boolean;
  /** Additional CSS classes */
  className?: string;
}

export default function AdaptationTracker({
  initialData,
  isLoading = false,
  className,
}: AdaptationTrackerProps) {
  const [data, setData] = useState<AdaptationTrackerResponse | null>(
    initialData ?? null
  );
  const [isFetching, setIsFetching] = useState(false);

  // Sync initial data
  useEffect(() => {
    if (initialData) setData(initialData);
  }, [initialData]);

  // Fetch adaptation data
  const fetchData = useCallback(async () => {
    if (isFetching) return;
    setIsFetching(true);

    try {
      const result = await dashboardApi.getAdaptationTracker(30);
      setData(result);
    } catch {
      // Silent fail — supplementary widget
    } finally {
      setIsFetching(false);
    }
  }, [isFetching]);

  useEffect(() => {
    if (!initialData) fetchData();
  }, [initialData, fetchData]);

  // ── Render ─────────────────────────────────────────────────────────

  if (isLoading || (!data && isFetching)) {
    return (
      <div
        className={cn(
          'bg-[#1A1A1A] border border-white/[0.06] rounded-xl overflow-hidden',
          className
        )}
      >
        <ChartSkeleton />
      </div>
    );
  }

  if (!data || !data.daily_data?.length) {
    return (
      <div
        className={cn(
          'bg-[#1A1A1A] border border-white/[0.06] rounded-xl overflow-hidden',
          className
        )}
      >
        <EmptyState />
      </div>
    );
  }

  const { daily_data, overall_improvement_pct, current_accuracy, best_day, worst_day, training_runs_count, drift_reports_count } = data;

  // Calculate latest mistake rate
  const latestDay = daily_data[daily_data.length - 1];
  const avgMistakeRate = daily_data.length > 0
    ? daily_data.reduce((sum, d) => sum + d.mistake_rate, 0) / daily_data.length
    : 0;

  // Improvement direction
  const improvementDirection =
    overall_improvement_pct > 0 ? 'up' :
    overall_improvement_pct < 0 ? 'down' : 'neutral';

  // Chart data: combine AI and human accuracy
  const chartData = daily_data.map((d) => ({
    date: d.date.slice(5), // MM-DD format for x-axis
    ai_accuracy: d.ai_accuracy,
    human_accuracy: d.human_accuracy,
    gap: d.gap,
    mistake_rate: d.mistake_rate,
  }));

  return (
    <div
      className={cn(
        'bg-[#1A1A1A] border border-white/[0.06] rounded-xl overflow-hidden',
        className
      )}
    >
      {/* ── Header ────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-white/[0.06]">
        <div className="flex items-center gap-2.5">
          {/* Brain icon */}
          <div className="w-8 h-8 rounded-lg bg-[#FF7F11]/10 flex items-center justify-center">
            <svg className="w-4.5 h-4.5 text-[#FF7F11]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09ZM18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 0 0-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 0 0 2.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 0 0 2.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 0 0-2.455 2.456ZM16.894 20.567 16.5 21.75l-.394-1.183a2.25 2.25 0 0 0-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 0 0 1.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 0 0 1.423 1.423l1.183.394-1.183.394a2.25 2.25 0 0 0-1.423 1.423Z" />
            </svg>
          </div>
          <div>
            <h3 className="text-sm font-semibold text-zinc-200">AI Adaptation Tracker</h3>
            <p className="text-[11px] text-zinc-500">30-day AI learning progress</p>
          </div>
        </div>

        {/* Refresh button */}
        <button
          onClick={fetchData}
          disabled={isFetching}
          aria-label="Refresh adaptation data"
          className="p-1.5 rounded-md hover:bg-white/[0.04] text-zinc-500 hover:text-zinc-400 transition-all disabled:opacity-40"
        >
          <svg
            className={cn('w-4 h-4', isFetching && 'animate-spin')}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182" />
          </svg>
        </button>
      </div>

      {/* ── Chart Area ────────────────────────────────────────────── */}
      <div className="px-5 pt-4 pb-2">
        <div className="h-[240px]" role="img" aria-label="AI vs Human accuracy chart over 30 days">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="aiGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={COLORS.ai} stopOpacity={0.2} />
                  <stop offset="100%" stopColor={COLORS.ai} stopOpacity={0} />
                </linearGradient>
                <linearGradient id="humanGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={COLORS.human} stopOpacity={0.1} />
                  <stop offset="100%" stopColor={COLORS.human} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 10, fill: '#71717A' }}
                tickLine={false}
                axisLine={false}
                interval="preserveStartEnd"
              />
              <YAxis
                domain={[0, 5]}
                tick={{ fontSize: 10, fill: '#71717A' }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v: number) => `${v.toFixed(0)}`}
              />
              <Tooltip content={<CustomTooltip />} />
              <Legend
                wrapperStyle={{ fontSize: 11, paddingTop: 8 }}
                formatter={(value: string) => (
                  <span className="text-zinc-400 capitalize">
                    {value.replace(/_/g, ' ')}
                  </span>
                )}
              />
              <Area
                type="monotone"
                dataKey="ai_accuracy"
                stroke={COLORS.ai}
                strokeWidth={2.5}
                fill="url(#aiGradient)"
                dot={false}
                activeDot={{ r: 4, strokeWidth: 0, fill: COLORS.ai }}
              />
              <Area
                type="monotone"
                dataKey="human_accuracy"
                stroke={COLORS.human}
                strokeWidth={2}
                fill="url(#humanGradient)"
                dot={false}
                activeDot={{ r: 4, strokeWidth: 0, fill: COLORS.human }}
                strokeDasharray="5 5"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* ── Metric Cards ──────────────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-2.5 px-5 py-3 border-t border-white/[0.04]">
        {/* Overall Improvement */}
        <MetricCard
          label="Improvement"
          value={`${overall_improvement_pct > 0 ? '+' : ''}${overall_improvement_pct.toFixed(1)}%`}
          sublabel={`${data.starting_accuracy.toFixed(1)}% → ${current_accuracy.toFixed(1)}%`}
          variant={overall_improvement_pct > 0 ? 'success' : overall_improvement_pct < 0 ? 'danger' : 'default'}
          icon={
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              {improvementDirection === 'up' ? (
                <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18 9 11.25l4.306 4.306a11.95 11.95 0 0 1 5.814-5.518l2.74-1.22m0 0-5.94-2.281m5.94 2.28-2.28 5.941" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 6 9 12.75l4.286-4.286a11.948 11.948 0 0 1 4.306 6.43l.776 2.898m0 0 3.182-5.511m-3.182 5.51-5.511-3.181" />
              )}
            </svg>
          }
        />

        {/* Current AI Accuracy */}
        <MetricCard
          label="AI Accuracy"
          value={`${current_accuracy.toFixed(1)}`}
          sublabel={`out of 5.0`}
          variant={current_accuracy >= 4.0 ? 'success' : current_accuracy >= 3.0 ? 'default' : 'warning'}
          icon={
            <svg className="w-3.5 h-3.5 text-[#FF7F11]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09Z" />
            </svg>
          }
        />

        {/* Best Day */}
        <MetricCard
          label="Best Day"
          value={best_day ? best_day.ai_accuracy.toFixed(1) : '—'}
          sublabel={best_day ? best_day.date : 'No data'}
          variant="success"
          icon={
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M11.48 3.499a.562.562 0 0 1 1.04 0l2.125 5.111a.563.563 0 0 0 .475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 0 0-.182.557l1.285 5.385a.562.562 0 0 1-.84.61l-4.725-2.885a.562.562 0 0 0-.586 0L6.982 20.54a.562.562 0 0 1-.84-.61l1.285-5.386a.562.562 0 0 0-.182-.557l-4.204-3.602a.562.562 0 0 1 .321-.988l5.518-.442a.563.563 0 0 0 .475-.345L11.48 3.5Z" />
            </svg>
          }
        />

        {/* Mistake Rate */}
        <div className="rounded-lg border border-white/[0.06] p-3 space-y-2">
          <div className="flex items-center gap-2">
            <svg className="w-3.5 h-3.5 text-zinc-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
            </svg>
            <span className="text-[11px] font-medium text-zinc-500 uppercase tracking-wider">
              Mistake Rate
            </span>
          </div>
          {latestDay && (
            <MistakeRateBar rate={latestDay.mistake_rate} />
          )}
          <p className="text-[10px] text-zinc-600">
            Avg: {avgMistakeRate.toFixed(1)}% over 30 days
          </p>
        </div>
      </div>

      {/* ── Footer: Training + Drift ──────────────────────────────── */}
      {(training_runs_count > 0 || drift_reports_count > 0) && (
        <div className="flex items-center gap-4 px-5 py-2.5 border-t border-white/[0.04] bg-white/[0.01]">
          {training_runs_count > 0 && (
            <div className="flex items-center gap-1.5">
              <div className="w-1.5 h-1.5 rounded-full bg-violet-500" />
              <span className="text-[11px] text-zinc-400">
                <span className="font-semibold text-zinc-300">{training_runs_count}</span>{' '}
                training runs
              </span>
            </div>
          )}
          {drift_reports_count > 0 && (
            <div className="flex items-center gap-1.5">
              <div className="w-1.5 h-1.5 rounded-full bg-amber-500" />
              <span className="text-[11px] text-zinc-400">
                <span className="font-semibold text-zinc-300">{drift_reports_count}</span>{' '}
                drift reports
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
