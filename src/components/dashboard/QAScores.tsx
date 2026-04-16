/**
 * PARWA QAScores — Week 16 Day 5 (F-119)
 *
 * Response quality assurance scores with daily trend chart,
 * dimension breakdown bars, pass rates, and threshold indicators.
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
} from 'recharts';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import {
  dashboardApi,
  type QAScoresResponse,
} from '@/lib/dashboard-api';

// ── Colors ────────────────────────────────────────────────────────────

const TREND_COLORS = {
  improving: '#22C55E',
  declining: '#EF4444',
  stable: '#71717A',
};

// ── Custom Tooltip ────────────────────────────────────────────────────

function QATooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ value: number; dataKey: string; color: string }>;
  label?: string;
}) {
  if (!active || !payload?.length) return null;

  const overall = payload.find((p) => p.dataKey === 'overall_score');
  if (!overall) return null;

  return (
    <div className="bg-[#222] border border-white/[0.08] rounded-lg px-3 py-2 shadow-xl">
      <p className="text-xs font-medium text-zinc-400 mb-1.5">{label}</p>
      <div className="flex items-center gap-2 text-xs">
        <span className="w-2 h-2 rounded-full" style={{ backgroundColor: overall.color }} />
        <span className="text-zinc-400">QA Score</span>
        <span className="text-zinc-200 font-semibold ml-auto">
          {(overall.value * 100).toFixed(1)}%
        </span>
      </div>
      <p className="text-[10px] text-zinc-500 mt-1">
        {payload.find((p) => p.dataKey === 'total_evaluated')?.value ?? 0} evaluated
      </p>
    </div>
  );
}

// ── Dimension Bar ─────────────────────────────────────────────────────

function DimensionBar({ name, score, passRate, trend }: {
  name: string;
  score: number;
  passRate: number;
  trend: string;
}) {
  const barColor = score >= 0.8 ? '#22C55E' : score >= 0.6 ? '#F59E0B' : '#EF4444';
  const trendArrow = trend === 'improving' ? '↑' : trend === 'declining' ? '↓' : '→';
  const trendColor = TREND_COLORS[trend as keyof typeof TREND_COLORS] ?? TREND_COLORS.stable;

  return (
    <div className="flex items-center gap-3 py-1.5 px-2 rounded-md hover:bg-white/[0.02] transition-colors">
      <span className="text-xs text-zinc-400 truncate w-28 shrink-0">{name}</span>
      <div className="flex-1 h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${score * 100}%`, backgroundColor: barColor }}
        />
      </div>
      <span className="text-xs font-semibold text-zinc-300 w-12 text-right shrink-0">
        {(score * 100).toFixed(1)}%
      </span>
      <span className="text-[10px] w-12 text-right shrink-0" style={{ color: trendColor }}>
        {trendArrow} {(passRate * 100).toFixed(0)}%
      </span>
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
          <Skeleton className="h-4 w-36 bg-white/[0.06]" />
          <Skeleton className="h-3 w-48 bg-white/[0.04]" />
        </div>
      </div>
      <Skeleton className="w-full h-[180px] rounded-lg bg-white/[0.04]" />
      <div className="grid grid-cols-3 gap-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-14 rounded-lg bg-white/[0.04]" />
        ))}
      </div>
    </div>
  );
}

// ── QAScores Component ────────────────────────────────────────────────

interface QAScoresProps {
  initialData?: QAScoresResponse;
  isLoading?: boolean;
  className?: string;
}

export default function QAScores({
  initialData,
  isLoading = false,
  className,
}: QAScoresProps) {
  const [data, setData] = useState<QAScoresResponse | null>(initialData ?? null);
  const [isFetching, setIsFetching] = useState(false);

  useEffect(() => {
    if (initialData) setData(initialData);
  }, [initialData]);

  const fetchData = useCallback(async () => {
    if (isFetching) return;
    setIsFetching(true);
    try {
      const result = await dashboardApi.getQAScores(30);
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
              <path strokeLinecap="round" strokeLinejoin="round" d="M11.48 3.499a.562.562 0 0 1 1.04 0l2.125 5.111a.563.563 0 0 0 .475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 0 0-.182.557l1.285 5.385a.562.562 0 0 1-.84.61l-4.725-2.885a.562.562 0 0 0-.586 0L6.982 20.54a.562.562 0 0 1-.84-.61l1.285-5.386a.562.562 0 0 0-.182-.557l-4.204-3.602a.562.562 0 0 1 .321-.988l5.518-.442a.563.563 0 0 0 .475-.345L11.48 3.5Z" />
            </svg>
          </div>
          <p className="text-sm text-zinc-500 font-medium">No QA data yet</p>
          <p className="text-xs text-zinc-600 mt-1">Quality scores will appear as responses are evaluated</p>
        </div>
      </div>
    );
  }

  const chartData = data.daily_trend.map((d) => ({
    date: d.date.slice(5),
    overall_score: d.overall_score,
    total_evaluated: d.total_evaluated,
  }));

  const trendColor = TREND_COLORS[data.trend_direction] ?? TREND_COLORS.stable;
  const passScore = data.current_overall * 100;

  return (
    <div className={cn('bg-[#1A1A1A] border border-white/[0.06] rounded-xl overflow-hidden', className)}>
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-white/[0.06]">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-purple-500/10 flex items-center justify-center">
            <svg className="w-4 h-4 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M11.48 3.499a.562.562 0 0 1 1.04 0l2.125 5.111a.563.563 0 0 0 .475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 0 0-.182.557l1.285 5.385a.562.562 0 0 1-.84.61l-4.725-2.885a.562.562 0 0 0-.586 0L6.982 20.54a.562.562 0 0 1-.84-.61l1.285-5.386a.562.562 0 0 0-.182-.557l-4.204-3.602a.562.562 0 0 1 .321-.988l5.518-.442a.563.563 0 0 0 .475-.345L11.48 3.5Z" />
            </svg>
          </div>
          <div>
            <h3 className="text-sm font-semibold text-zinc-200">QA Scores</h3>
            <p className="text-[11px] text-zinc-500">Response quality assurance</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-lg font-bold" style={{ color: trendColor }}>
            {passScore.toFixed(1)}%
          </span>
          <div className="text-right">
            <p className="text-[10px] text-zinc-600">
              {data.change_vs_previous_period !== null
                ? `${data.change_vs_previous_period >= 0 ? '+' : ''}${(data.change_vs_previous_period * 100).toFixed(1)}% vs prev`
                : '—'
              }
            </p>
            <p className="text-[10px] text-zinc-500">
              {data.total_evaluated.toLocaleString()} evaluated
            </p>
          </div>
        </div>
      </div>

      {/* Chart */}
      <div className="px-5 pt-4 pb-2">
        <div className="h-[180px]" role="img" aria-label="QA scores trend chart over 30 days">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="qaGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#A855F7" stopOpacity={0.2} />
                  <stop offset="100%" stopColor="#A855F7" stopOpacity={0} />
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
                domain={[0, 1]}
                tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
                tick={{ fontSize: 10, fill: '#71717A' }}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip content={<QATooltip />} />
              <Area
                type="monotone"
                dataKey="overall_score"
                stroke="#A855F7"
                strokeWidth={2.5}
                fill="url(#qaGrad)"
                dot={false}
                activeDot={{ r: 4, strokeWidth: 0, fill: '#A855F7' }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-3 gap-2.5 px-5 py-3 border-t border-white/[0.04]">
        <div className="rounded-lg border border-white/[0.06] p-3">
          <p className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider">Pass Rate</p>
          <p className={cn(
            'text-lg font-bold',
            data.pass_rate >= 0.8 ? 'text-emerald-400' : data.pass_rate >= 0.6 ? 'text-amber-400' : 'text-red-400'
          )}>
            {(data.pass_rate * 100).toFixed(1)}%
          </p>
          <p className="text-[10px] text-zinc-600">above {(data.threshold_pass * 100).toFixed(0)}% threshold</p>
        </div>
        <div className="rounded-lg border border-white/[0.06] p-3">
          <p className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider">Overall Avg</p>
          <p className="text-lg font-bold text-zinc-100">{(data.overall_avg * 100).toFixed(1)}%</p>
          <p className="text-[10px] text-zinc-600">30-day average</p>
        </div>
        <div className="rounded-lg border border-white/[0.06] p-3">
          <p className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider">Evaluated</p>
          <p className="text-lg font-bold text-zinc-100">{data.total_evaluated.toLocaleString()}</p>
          <p className="text-[10px] text-zinc-600">total responses</p>
        </div>
      </div>

      {/* Dimension Breakdown */}
      {data.dimensions?.length > 0 && (
        <div className="border-t border-white/[0.04]">
          <div className="px-5 py-2 border-b border-white/[0.04]">
            <p className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider">Quality Dimensions</p>
          </div>
          <div className="p-3 space-y-0.5">
            {data.dimensions.map((dim) => (
              <DimensionBar
                key={dim.dimension_name}
                name={dim.dimension_name}
                score={dim.avg_score}
                passRate={dim.pass_rate}
                trend={dim.trend}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
