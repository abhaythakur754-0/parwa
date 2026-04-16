/**
 * PARWA ConfidenceTrend — Week 16 Day 5 (F-115)
 *
 * AI confidence score trend chart with distribution buckets,
 * thresholds, and daily min/max range bands.
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
  ReferenceLine,
} from 'recharts';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import {
  dashboardApi,
  type ConfidenceTrendResponse,
} from '@/lib/dashboard-api';

// ── Colors ────────────────────────────────────────────────────────────

const COLORS = {
  avg: '#FF7F11',
  minMax: 'rgba(255,127,17,0.08)',
  grid: 'rgba(255,255,255,0.04)',
  threshold: '#EF4444',
  low: '#F59E0B',
};

// ── Custom Tooltip ────────────────────────────────────────────────────

function ConfidenceTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ value: number; dataKey: string; color: string }>;
  label?: string;
}) {
  if (!active || !payload?.length) return null;

  const avg = payload.find((p) => p.dataKey === 'avg_confidence');
  const min = payload.find((p) => p.dataKey === 'min_confidence');
  const max = payload.find((p) => p.dataKey === 'max_confidence');
  const low = payload.find((p) => p.dataKey === 'low_confidence_count');

  return (
    <div className="bg-[#222] border border-white/[0.08] rounded-lg px-3 py-2 shadow-xl">
      <p className="text-xs font-medium text-zinc-400 mb-1.5">{label}</p>
      {avg && (
        <div className="flex items-center gap-2 text-xs">
          <span className="w-2 h-2 rounded-full" style={{ backgroundColor: avg.color }} />
          <span className="text-zinc-400">Avg Confidence</span>
          <span className="text-zinc-200 font-semibold ml-auto">
            {(avg.value * 100).toFixed(1)}%
          </span>
        </div>
      )}
      {min && max && (
        <p className="text-[10px] text-zinc-500 mt-1">
          Range: {(min.value * 100).toFixed(0)}% — {(max.value * 100).toFixed(0)}%
        </p>
      )}
      {low && low.value > 0 && (
        <p className="text-[10px] text-amber-400 mt-0.5">
          {low.value} below threshold
        </p>
      )}
    </div>
  );
}

// ── Distribution Bar ──────────────────────────────────────────────────

const BUCKET_COLORS: Record<string, string> = {
  '0-20': '#EF4444',
  '20-40': '#F97316',
  '40-60': '#F59E0B',
  '60-80': '#22C55E',
  '80-100': '#10B981',
};

function DistributionBar({ distribution }: { distribution: ConfidenceTrendResponse['distribution'] }) {
  if (!distribution?.length) return null;

  return (
    <div className="flex gap-1 h-4 rounded-md overflow-hidden">
      {distribution.map((bucket) => {
        const color = BUCKET_COLORS[bucket.range] ?? '#71717A';
        return (
          <div
            key={bucket.range}
            className="rounded-sm transition-all duration-500"
            style={{
              width: `${Math.max(bucket.percentage, 1)}%`,
              backgroundColor: color,
              minWidth: '2px',
            }}
            title={`${bucket.range}%: ${bucket.count} (${bucket.percentage.toFixed(1)}%)`}
          />
        );
      })}
    </div>
  );
}

// ── Skeleton ──────────────────────────────────────────────────────────

function ChartSkeleton() {
  return (
    <div className="p-5 space-y-4">
      <div className="flex items-center gap-3">
        <Skeleton className="w-9 h-9 rounded-lg bg-white/[0.06]" />
        <div className="space-y-1.5">
          <Skeleton className="h-4 w-40 bg-white/[0.06]" />
          <Skeleton className="h-3 w-48 bg-white/[0.04]" />
        </div>
      </div>
      <Skeleton className="w-full h-[240px] rounded-lg bg-white/[0.04]" />
      <div className="grid grid-cols-3 gap-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-14 rounded-lg bg-white/[0.04]" />
        ))}
      </div>
    </div>
  );
}

// ── ConfidenceTrend Component ─────────────────────────────────────────

interface ConfidenceTrendProps {
  initialData?: ConfidenceTrendResponse;
  isLoading?: boolean;
  className?: string;
}

export default function ConfidenceTrend({
  initialData,
  isLoading = false,
  className,
}: ConfidenceTrendProps) {
  const [data, setData] = useState<ConfidenceTrendResponse | null>(initialData ?? null);
  const [isFetching, setIsFetching] = useState(false);

  useEffect(() => {
    if (initialData) setData(initialData);
  }, [initialData]);

  const fetchData = useCallback(async () => {
    if (isFetching) return;
    setIsFetching(true);
    try {
      const result = await dashboardApi.getConfidenceTrend(30);
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

  if (isLoading || (!data && isFetching)) {
    return (
      <div className={cn('bg-[#1A1A1A] border border-white/[0.06] rounded-xl overflow-hidden', className)}>
        <ChartSkeleton />
      </div>
    );
  }

  if (!data || !data.daily_trend?.length) {
    return (
      <div className={cn('bg-[#1A1A1A] border border-white/[0.06] rounded-xl overflow-hidden', className)}>
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <div className="w-12 h-12 rounded-xl bg-white/[0.03] border border-white/[0.06] flex items-center justify-center mb-3">
            <svg className="w-6 h-6 text-zinc-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 0 1 3 19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V8.625ZM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V4.125Z" />
            </svg>
          </div>
          <p className="text-sm text-zinc-500 font-medium">No confidence data</p>
          <p className="text-xs text-zinc-600 mt-1">AI confidence metrics will appear here</p>
        </div>
      </div>
    );
  }

  const chartData = data.daily_trend.map((d) => ({
    date: d.date.slice(5),
    avg_confidence: d.avg_confidence,
    min_confidence: d.min_confidence,
    max_confidence: d.max_confidence,
    low_confidence_count: d.low_confidence_count,
  }));

  const trendColors = {
    improving: '#22C55E',
    declining: '#EF4444',
    stable: '#71717A',
  };

  const trendColor = trendColors[data.trend_direction] ?? trendColors.stable;

  return (
    <div className={cn('bg-[#1A1A1A] border border-white/[0.06] rounded-xl overflow-hidden', className)}>
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-white/[0.06]">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-sky-500/10 flex items-center justify-center">
            <svg className="w-4 h-4 text-sky-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75m-3-7.036A11.959 11.959 0 0 1 3.598 6 11.99 11.99 0 0 0 3 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285Z" />
            </svg>
          </div>
          <div>
            <h3 className="text-sm font-semibold text-zinc-200">AI Confidence Trend</h3>
            <p className="text-[11px] text-zinc-500">Model prediction confidence</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-lg font-bold" style={{ color: trendColor }}>
            {(data.current_avg * 100).toFixed(1)}%
          </span>
          <div className="text-right">
            <p className="text-[10px] text-zinc-600">
              {data.change_vs_previous_period >= 0 ? '+' : ''}{(data.change_vs_previous_period * 100).toFixed(1)}% vs prev
            </p>
            <p className="text-[10px] text-zinc-500">
              {data.total_predictions.toLocaleString()} predictions
            </p>
          </div>
        </div>
      </div>

      {/* Chart */}
      <div className="px-5 pt-4 pb-2">
        <div className="h-[240px]" role="img" aria-label="AI confidence trend chart over 30 days">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="confGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={COLORS.avg} stopOpacity={0.15} />
                  <stop offset="100%" stopColor={COLORS.avg} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke={COLORS.grid} />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 10, fill: '#71717A' }}
                tickLine={false}
                axisLine={false}
                interval="preserveStartEnd"
              />
              <YAxis
                domain={[0, 1]}
                tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
                tick={{ fontSize: 10, fill: '#71717A' }}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip content={<ConfidenceTooltip />} />
              <Legend
                wrapperStyle={{ fontSize: 11, paddingTop: 8 }}
                formatter={(value: string) => (
                  <span className="text-zinc-400 capitalize">{value.replace(/_/g, ' ')}</span>
                )}
              />
              {/* Threshold lines */}
              <ReferenceLine
                y={data.low_confidence_threshold}
                stroke={COLORS.low}
                strokeDasharray="6 4"
                strokeWidth={1}
                label={{ value: 'Low', position: 'right', fill: COLORS.low, fontSize: 9 }}
              />
              <ReferenceLine
                y={data.critical_threshold}
                stroke={COLORS.threshold}
                strokeDasharray="6 4"
                strokeWidth={1}
                label={{ value: 'Critical', position: 'right', fill: COLORS.threshold, fontSize: 9 }}
              />
              {/* Range band */}
              <Area type="monotone" dataKey="max_confidence" stroke="none" fill={COLORS.minMax} />
              <Area type="monotone" dataKey="min_confidence" stroke="none" fill="#1A1A1A" />
              {/* Average line */}
              <Area
                type="monotone"
                dataKey="avg_confidence"
                stroke={COLORS.avg}
                strokeWidth={2}
                fill="url(#confGrad)"
                dot={false}
                activeDot={{ r: 4, strokeWidth: 0, fill: COLORS.avg }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Distribution */}
      <div className="px-5 py-3 border-t border-white/[0.04]">
        <p className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider mb-2">Confidence Distribution</p>
        <DistributionBar distribution={data.distribution} />
        <div className="flex justify-between mt-1.5">
          {['0-20', '20-40', '40-60', '60-80', '80-100'].map((range) => (
            <div key={range} className="flex items-center gap-1">
              <div className="w-2 h-2 rounded-full" style={{ backgroundColor: BUCKET_COLORS[range] }} />
              <span className="text-[10px] text-zinc-600">{range}%</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
