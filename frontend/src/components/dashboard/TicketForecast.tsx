/**
 * PARWA TicketForecast — Week 16 Day 4 (F-043)
 *
 * Ticket volume forecast chart using linear regression.
 * Shows historical actuals + predicted future with confidence bounds.
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
  type TicketForecastResponse,
} from '@/lib/dashboard-api';

// ── Colors ────────────────────────────────────────────────────────────

const COLORS = {
  actual: '#FF7F11',
  forecast: '#22C55E',
  upperBound: 'rgba(34,197,94,0.15)',
  lowerBound: 'rgba(34,197,94,0.15)',
  grid: 'rgba(255,255,255,0.04)',
};

// ── Custom Tooltip ────────────────────────────────────────────────────

function ForecastTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ value: number; dataKey: string; color: string }>;
  label?: string;
}) {
  if (!active || !payload?.length) return null;

  const predicted = payload.find((p) => p.dataKey === 'predicted');
  const upper = payload.find((p) => p.dataKey === 'upper_bound');
  const lower = payload.find((p) => p.dataKey === 'lower_bound');

  return (
    <div className="bg-[#222] border border-white/[0.08] rounded-lg px-3 py-2 shadow-xl">
      <p className="text-xs font-medium text-zinc-400 mb-1.5">{label}</p>
      {predicted && (
        <div className="flex items-center gap-2 text-xs">
          <span className="w-2 h-2 rounded-full" style={{ backgroundColor: predicted.color }} />
          <span className="text-zinc-400">
            {upper && lower ? 'Forecast' : 'Actual'}
          </span>
          <span className="text-zinc-200 font-semibold ml-auto">
            {Math.round(predicted.value)}
          </span>
        </div>
      )}
      {upper && lower && (
        <p className="text-[10px] text-zinc-500 mt-1">
          Range: {Math.round(lower.value)} - {Math.round(upper.value)}
        </p>
      )}
    </div>
  );
}

// ── Trend Badge ───────────────────────────────────────────────────────

function TrendBadge({ direction }: { direction: string }) {
  const config: Record<string, { color: string; label: string; arrow: string }> = {
    increasing: { color: 'text-emerald-400', label: 'Trending Up', arrow: '↑' },
    decreasing: { color: 'text-red-400', label: 'Trending Down', arrow: '↓' },
    stable: { color: 'text-zinc-400', label: 'Stable', arrow: '→' },
  };
  const c = config[direction] ?? config.stable;

  return (
    <span className={cn('inline-flex items-center gap-1 text-xs font-medium', c.color)}>
      <span>{c.arrow}</span>
      <span>{c.label}</span>
    </span>
  );
}

// ── Skeleton ──────────────────────────────────────────────────────────

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
      <Skeleton className="w-full h-[260px] rounded-lg bg-white/[0.04]" />
      <div className="grid grid-cols-3 gap-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-14 rounded-lg bg-white/[0.04]" />
        ))}
      </div>
    </div>
  );
}

// ── TicketForecast Component ──────────────────────────────────────────

interface TicketForecastProps {
  initialData?: TicketForecastResponse;
  isLoading?: boolean;
  className?: string;
}

export default function TicketForecast({
  initialData,
  isLoading = false,
  className,
}: TicketForecastProps) {
  const [data, setData] = useState<TicketForecastResponse | null>(initialData ?? null);
  const [isFetching, setIsFetching] = useState(false);

  useEffect(() => {
    if (initialData) setData(initialData);
  }, [initialData]);

  const fetchData = useCallback(async () => {
    if (isFetching) return;
    setIsFetching(true);
    try {
      const result = await dashboardApi.getTicketForecast(14, 30);
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

  if (!data || (!data.historical.length && !data.forecast.length)) {
    return (
      <div className={cn('bg-[#1A1A1A] border border-white/[0.06] rounded-xl overflow-hidden', className)}>
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <div className="w-12 h-12 rounded-xl bg-white/[0.03] border border-white/[0.06] flex items-center justify-center mb-3">
            <svg className="w-6 h-6 text-zinc-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18 9 11.25l4.306 4.306a11.95 11.95 0 0 1 5.814-5.518l2.74-1.22m0 0-5.94-2.281m5.94 2.28-2.28 5.941" />
            </svg>
          </div>
          <p className="text-sm text-zinc-500 font-medium">No forecast data</p>
          <p className="text-xs text-zinc-600 mt-1">Ticket volume data will populate over time</p>
        </div>
      </div>
    );
  }

  // Merge historical + forecast into single chart data
  const chartData = [
    ...data.historical.map((h) => ({
      date: h.date.slice(5),
      predicted: h.actual ?? h.predicted,
      actual: h.actual,
    })),
    ...data.forecast.map((f) => ({
      date: f.date.slice(5),
      predicted: f.predicted,
      upper_bound: f.upper_bound,
      lower_bound: f.lower_bound,
    })),
  ];

  return (
    <div className={cn('bg-[#1A1A1A] border border-white/[0.06] rounded-xl overflow-hidden', className)}>
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-white/[0.06]">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-violet-500/10 flex items-center justify-center">
            <svg className="w-4 h-4 text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 0 1 3 19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V8.625ZM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V4.125Z" />
            </svg>
          </div>
          <div>
            <h3 className="text-sm font-semibold text-zinc-200">Ticket Forecast</h3>
            <p className="text-[11px] text-zinc-500">Predicted volume for next 14 days</p>
          </div>
        </div>
        <TrendBadge direction={data.trend_direction} />
      </div>

      {/* Chart */}
      <div className="px-5 pt-4 pb-2">
        <div className="h-[260px]" role="img" aria-label="Ticket volume forecast chart">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="forecastGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={COLORS.forecast} stopOpacity={0.15} />
                  <stop offset="100%" stopColor={COLORS.forecast} stopOpacity={0} />
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
                tick={{ fontSize: 10, fill: '#71717A' }}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip content={<ForecastTooltip />} />
              <Legend
                wrapperStyle={{ fontSize: 11, paddingTop: 8 }}
                formatter={(value: string) => (
                  <span className="text-zinc-400 capitalize">{value.replace(/_/g, ' ')}</span>
                )}
              />
              {/* Confidence bounds */}
              <Area
                type="monotone"
                dataKey="upper_bound"
                stroke="none"
                fill={COLORS.upperBound}
              />
              <Area
                type="monotone"
                dataKey="lower_bound"
                stroke="none"
                fill={COLORS.lowerBound}
              />
              {/* Forecast line */}
              <Area
                type="monotone"
                dataKey="predicted"
                stroke={COLORS.forecast}
                strokeWidth={2}
                fill="url(#forecastGradient)"
                dot={false}
                activeDot={{ r: 4, strokeWidth: 0, fill: COLORS.forecast }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-3 gap-2.5 px-5 py-3 border-t border-white/[0.04]">
        <div className="rounded-lg border border-white/[0.06] p-3">
          <p className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider">Avg Daily</p>
          <p className="text-lg font-bold text-zinc-100">{Math.round(data.avg_daily_volume)}</p>
          <p className="text-[10px] text-zinc-600">tickets/day</p>
        </div>
        <div className="rounded-lg border border-white/[0.06] p-3">
          <p className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider">Model</p>
          <p className="text-sm font-bold text-zinc-100 capitalize">{data.model_type.replace('_', ' ')}</p>
          <p className="text-[10px] text-zinc-600">{Math.round(data.confidence_level * 100)}% confidence</p>
        </div>
        <div className="rounded-lg border border-white/[0.06] p-3">
          <p className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider">Seasonality</p>
          <p className={cn('text-sm font-bold', data.seasonality_detected ? 'text-amber-400' : 'text-zinc-500')}>
            {data.seasonality_detected ? 'Detected' : 'None'}
          </p>
          <p className="text-[10px] text-zinc-600">day-of-week pattern</p>
        </div>
      </div>
    </div>
  );
}
