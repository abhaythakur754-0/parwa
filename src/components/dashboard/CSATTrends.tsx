/**
 * PARWA CSATTrends — Week 16 Day 4 (F-044)
 *
 * Customer satisfaction trend analytics with daily chart,
 * rating distribution bars, and dimension breakdowns.
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
  type CSATTrendsResponse,
} from '@/lib/dashboard-api';

// ── Colors ────────────────────────────────────────────────────────────

const RATING_COLORS: Record<number, string> = {
  5: '#22C55E',
  4: '#10B981',
  3: '#F59E0B',
  2: '#F97316',
  1: '#EF4444',
};

const TREND_COLORS = {
  improving: '#22C55E',
  declining: '#EF4444',
  stable: '#71717A',
};

// ── Custom Tooltip ────────────────────────────────────────────────────

function CSATTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ value: number; dataKey: string; color: string }>;
  label?: string;
}) {
  if (!active || !payload?.length) return null;

  const rating = payload.find((p) => p.dataKey === 'avg_rating');
  if (!rating) return null;

  return (
    <div className="bg-[#222] border border-white/[0.08] rounded-lg px-3 py-2 shadow-xl">
      <p className="text-xs font-medium text-zinc-400 mb-1">{label}</p>
      <div className="flex items-center gap-2 text-xs">
        <span className="w-2 h-2 rounded-full" style={{ backgroundColor: rating.color }} />
        <span className="text-zinc-400">CSAT</span>
        <span className="text-zinc-200 font-semibold ml-auto">
          {rating.value.toFixed(2)}{' '}
          <span className="text-zinc-500 font-normal">/ 5.0</span>
        </span>
      </div>
    </div>
  );
}

// ── Distribution Bar ──────────────────────────────────────────────────

function DistributionBar({ distribution }: { distribution: Record<string, number> }) {
  const total = Object.values(distribution).reduce((a, b) => a + b, 0);
  if (total === 0) return null;

  return (
    <div className="flex gap-0.5 h-3 rounded-full overflow-hidden">
      {[5, 4, 3, 2, 1].map((rating) => {
        const count = distribution[String(rating)] ?? 0;
        const pct = (count / total) * 100;
        if (pct === 0) return null;
        return (
          <div
            key={rating}
            className="rounded-full transition-all duration-500"
            style={{
              width: `${pct}%`,
              backgroundColor: RATING_COLORS[rating],
              minWidth: pct > 0 ? '4px' : '0',
            }}
            title={`${rating}-star: ${count} (${pct.toFixed(0)}%)`}
          />
        );
      })}
    </div>
  );
}

// ── Dimension Table ───────────────────────────────────────────────────

type DimensionTab = 'agent' | 'category' | 'channel';

const DIMENSION_TABS: { key: DimensionTab; label: string }[] = [
  { key: 'agent', label: 'By Agent' },
  { key: 'category', label: 'By Category' },
  { key: 'channel', label: 'By Channel' },
];

function DimensionTable({
  data,
  tab,
}: {
  data: CSATTrendsResponse;
  tab: DimensionTab;
}) {
  const items = data.by_agent && tab === 'agent'
    ? data.by_agent
    : data.by_category && tab === 'category'
    ? data.by_category
    : data.by_channel ?? [];

  if (items.length === 0) {
    return (
      <div className="text-center py-6">
        <p className="text-xs text-zinc-600">No data available</p>
      </div>
    );
  }

  return (
    <div className="space-y-1.5">
      {items.slice(0, 8).map((item, i) => (
        <div key={i} className="flex items-center gap-3 py-1.5 px-2 rounded-md hover:bg-white/[0.02] transition-colors">
          <span className="text-xs text-zinc-400 truncate w-24 shrink-0" title={item.dimension_name}>
            {item.dimension_name}
          </span>
          <div className="flex-1 h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${(item.avg_rating / 5) * 100}%`,
                backgroundColor:
                  item.avg_rating >= 4 ? '#22C55E' :
                  item.avg_rating >= 3 ? '#F59E0B' :
                  '#EF4444',
              }}
            />
          </div>
          <span className="text-xs font-semibold text-zinc-300 w-10 text-right shrink-0">
            {item.avg_rating.toFixed(1)}
          </span>
          <span className="text-[10px] text-zinc-600 w-14 text-right shrink-0">
            {item.total_ratings} ratings
          </span>
        </div>
      ))}
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
      <Skeleton className="w-full h-[200px] rounded-lg bg-white/[0.04]" />
      <Skeleton className="w-full h-6 rounded-full bg-white/[0.04]" />
      <Skeleton className="w-full h-[120px] rounded-lg bg-white/[0.04]" />
    </div>
  );
}

// ── CSATTrends Component ──────────────────────────────────────────────

interface CSATTrendsProps {
  initialData?: CSATTrendsResponse;
  isLoading?: boolean;
  className?: string;
}

export default function CSATTrends({
  initialData,
  isLoading = false,
  className,
}: CSATTrendsProps) {
  const [data, setData] = useState<CSATTrendsResponse | null>(initialData ?? null);
  const [isFetching, setIsFetching] = useState(false);
  const [activeTab, setActiveTab] = useState<DimensionTab>('agent');

  useEffect(() => {
    if (initialData) setData(initialData);
  }, [initialData]);

  const fetchData = useCallback(async () => {
    if (isFetching) return;
    setIsFetching(true);
    try {
      const result = await dashboardApi.getCSATTrends(30);
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
          <p className="text-sm text-zinc-500 font-medium">No CSAT data yet</p>
          <p className="text-xs text-zinc-600 mt-1">Customer ratings will appear here</p>
        </div>
      </div>
    );
  }

  // Aggregate distribution from all days
  const totalDistribution: Record<string, number> = { '1': 0, '2': 0, '3': 0, '4': 0, '5': 0 };
  data.daily_trend.forEach((day) => {
    Object.entries(day.distribution).forEach(([k, v]) => {
      totalDistribution[k] = (totalDistribution[k] ?? 0) + v;
    });
  });

  const chartData = data.daily_trend.map((d) => ({
    date: d.date.slice(5),
    avg_rating: d.avg_rating,
  }));

  const trendColor = TREND_COLORS[data.trend_direction] ?? TREND_COLORS.stable;

  return (
    <div className={cn('bg-[#1A1A1A] border border-white/[0.06] rounded-xl overflow-hidden', className)}>
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-white/[0.06]">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-[#FF7F11]/10 flex items-center justify-center">
            <svg className="w-4 h-4 text-[#FF7F11]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M11.48 3.499a.562.562 0 0 1 1.04 0l2.125 5.111a.563.563 0 0 0 .475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 0 0-.182.557l1.285 5.385a.562.562 0 0 1-.84.61l-4.725-2.885a.562.562 0 0 0-.586 0L6.982 20.54a.562.562 0 0 1-.84-.61l1.285-5.386a.562.562 0 0 0-.182-.557l-4.204-3.602a.562.562 0 0 1 .321-.988l5.518-.442a.563.563 0 0 0 .475-.345L11.48 3.5Z" />
            </svg>
          </div>
          <div>
            <h3 className="text-sm font-semibold text-zinc-200">CSAT Trends</h3>
            <p className="text-[11px] text-zinc-500">Customer satisfaction analytics</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-lg font-bold" style={{ color: trendColor }}>
            {data.overall_avg.toFixed(1)}
          </span>
          <div className="text-right">
            <p className="text-[10px] text-zinc-600">of 5.0</p>
            <p className="text-[10px] text-zinc-500">
              {data.overall_total.toLocaleString()} ratings
            </p>
          </div>
        </div>
      </div>

      {/* Chart */}
      <div className="px-5 pt-4 pb-2">
        <div className="h-[200px]" role="img" aria-label="CSAT trend chart over 30 days">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="csatGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#FF7F11" stopOpacity={0.2} />
                  <stop offset="100%" stopColor="#FF7F11" stopOpacity={0} />
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
              />
              <Tooltip content={<CSATTooltip />} />
              <Area
                type="monotone"
                dataKey="avg_rating"
                stroke="#FF7F11"
                strokeWidth={2.5}
                fill="url(#csatGradient)"
                dot={false}
                activeDot={{ r: 4, strokeWidth: 0, fill: '#FF7F11' }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Distribution Bar */}
      <div className="px-5 py-3 border-t border-white/[0.04]">
        <p className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider mb-2">Rating Distribution</p>
        <DistributionBar distribution={totalDistribution} />
        <div className="flex justify-between mt-1.5">
          {[5, 4, 3, 2, 1].map((r) => (
            <div key={r} className="flex items-center gap-1">
              <div className="w-2 h-2 rounded-full" style={{ backgroundColor: RATING_COLORS[r] }} />
              <span className="text-[10px] text-zinc-600">{r}★</span>
            </div>
          ))}
        </div>
      </div>

      {/* Dimension Breakdown */}
      <div className="border-t border-white/[0.04]">
        <div className="flex items-center gap-0.5 px-5 py-2 border-b border-white/[0.04]">
          {DIMENSION_TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={cn(
                'px-2.5 py-1 rounded-md text-xs font-medium transition-all duration-200',
                activeTab === tab.key
                  ? 'bg-white/[0.08] text-zinc-200'
                  : 'text-zinc-500 hover:text-zinc-400 hover:bg-white/[0.03]'
              )}
            >
              {tab.label}
            </button>
          ))}
          {data.change_vs_previous_period !== null && data.change_vs_previous_period !== undefined && (
            <span className={cn(
              'ml-auto text-[11px] font-medium',
              data.change_vs_previous_period > 0 ? 'text-emerald-400' :
              data.change_vs_previous_period < 0 ? 'text-red-400' :
              'text-zinc-500'
            )}>
              {data.change_vs_previous_period > 0 ? '+' : ''}{data.change_vs_previous_period.toFixed(2)} vs prev
            </span>
          )}
        </div>
        <div className="p-3">
          <DimensionTable data={data} tab={activeTab} />
        </div>
      </div>
    </div>
  );
}
