/**
 * PARWA ROIDashboard — Week 16 Day 6 (F-113)
 *
 * Return on Investment dashboard showing AI cost savings vs human,
 * monthly trend chart, per-ticket cost comparison, cumulative savings,
 * and ticket split metrics.
 */

'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  AreaChart,
  Area,
} from 'recharts';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import {
  dashboardApi,
  type ROIDashboardResponse,
} from '@/lib/dashboard-api';

// ── Colors ────────────────────────────────────────────────────────────

const COLORS = {
  ai: '#FF7F11',
  human: '#71717A',
  savings: '#22C55E',
  grid: 'rgba(255,255,255,0.04)',
};

// ── Formatters ────────────────────────────────────────────────────────

function formatCurrency(n: number): string {
  if (n >= 1000000) return `$${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `$${(n / 1000).toFixed(1)}K`;
  return `$${n.toFixed(2)}`;
}

function formatCount(n: number): string {
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return n.toLocaleString();
}

// ── Custom Tooltip (Savings Bar) ──────────────────────────────────────

function SavingsTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ value: number; dataKey: string; color: string; name: string }>;
  label?: string;
}) {
  if (!active || !payload?.length) return null;

  return (
    <div className="bg-[#222] border border-white/[0.08] rounded-lg px-3 py-2 shadow-xl">
      <p className="text-xs font-medium text-zinc-400 mb-1.5">{label}</p>
      {payload.map((entry, i) => (
        <div key={i} className="flex items-center gap-2 text-xs">
          <span className="w-2 h-2 rounded-full" style={{ backgroundColor: entry.color }} />
          <span className="text-zinc-400">{entry.name}</span>
          <span className="text-zinc-200 font-semibold ml-auto">
            ${Math.round(entry.value).toLocaleString()}
          </span>
        </div>
      ))}
    </div>
  );
}

// ── Custom Tooltip (Cumulative) ───────────────────────────────────────

function CumulativeTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ value: number; dataKey: string; color: string }>;
  label?: string;
}) {
  if (!active || !payload?.length) return null;

  const cumulative = payload.find((p) => p.dataKey === 'cumulative_savings');
  if (!cumulative) return null;

  return (
    <div className="bg-[#222] border border-white/[0.08] rounded-lg px-3 py-2 shadow-xl">
      <p className="text-xs font-medium text-zinc-400 mb-1.5">{label}</p>
      <div className="flex items-center gap-2 text-xs">
        <span className="w-2 h-2 rounded-full" style={{ backgroundColor: cumulative.color }} />
        <span className="text-zinc-400">Cumulative Savings</span>
        <span className="text-emerald-400 font-semibold ml-auto">
          ${Math.round(cumulative.value).toLocaleString()}
        </span>
      </div>
    </div>
  );
}

// ── Stat Card ─────────────────────────────────────────────────────────

function StatCard({ label, value, subtext, color }: {
  label: string;
  value: string;
  subtext: string;
  color?: string;
}) {
  return (
    <div className="rounded-lg border border-white/[0.06] p-4">
      <p className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider">{label}</p>
      <p className={cn('text-xl font-bold mt-1', color ?? 'text-zinc-100')}>{value}</p>
      <p className="text-[10px] text-zinc-600 mt-0.5">{subtext}</p>
    </div>
  );
}

// ── Skeleton ──────────────────────────────────────────────────────────

function DashboardSkeleton() {
  return (
    <div className="p-5 space-y-4">
      <div className="flex items-center gap-3">
        <Skeleton className="w-9 h-9 rounded-lg bg-white/[0.06]" />
        <div className="space-y-1.5">
          <Skeleton className="h-4 w-36 bg-white/[0.06]" />
          <Skeleton className="h-3 w-48 bg-white/[0.04]" />
        </div>
      </div>
      <div className="grid grid-cols-4 gap-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-20 rounded-lg bg-white/[0.04]" />
        ))}
      </div>
      <Skeleton className="w-full h-[240px] rounded-lg bg-white/[0.04]" />
      <Skeleton className="w-full h-[200px] rounded-lg bg-white/[0.04]" />
    </div>
  );
}

// ── Empty State ───────────────────────────────────────────────────────

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="w-14 h-14 rounded-xl bg-white/[0.03] border border-white/[0.06] flex items-center justify-center mb-4">
        <svg className="w-7 h-7 text-zinc-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v12m-3-2.818.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
        </svg>
      </div>
      <p className="text-sm text-zinc-500 font-medium">No ROI data yet</p>
      <p className="text-xs text-zinc-600 mt-1 max-w-xs">
        ROI metrics will appear once AI has resolved tickets and cost data is available
      </p>
    </div>
  );
}

// ── ROIDashboard Component ────────────────────────────────────────────

interface ROIDashboardProps {
  initialData?: ROIDashboardResponse;
  isLoading?: boolean;
  className?: string;
}

export default function ROIDashboard({
  initialData,
  isLoading = false,
  className,
}: ROIDashboardProps) {
  const [data, setData] = useState<ROIDashboardResponse | null>(initialData ?? null);
  const [isFetching, setIsFetching] = useState(false);

  useEffect(() => {
    if (initialData) setData(initialData);
  }, [initialData]);

  const fetchData = useCallback(async () => {
    if (isFetching) return;
    setIsFetching(true);
    try {
      const result = await dashboardApi.getROIDashboard(12);
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
        <DashboardSkeleton />
      </div>
    );
  }

  if (!data || !data.monthly_trend?.length) {
    return (
      <div className={cn('bg-[#1A1A1A] border border-white/[0.06] rounded-xl overflow-hidden', className)}>
        {/* Header */}
        <div className="flex items-center gap-2.5 px-5 py-3 border-b border-white/[0.06]">
          <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center">
            <svg className="w-4 h-4 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v12m-3-2.818.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
            </svg>
          </div>
          <div>
            <h3 className="text-sm font-semibold text-zinc-200">ROI Dashboard</h3>
            <p className="text-[11px] text-zinc-500">AI cost savings & return on investment</p>
          </div>
        </div>
        <EmptyState />
      </div>
    );
  }

  // Bar chart data: AI cost vs Human cost per month
  const barData = data.monthly_trend.map((m) => ({
    period: m.period.slice(0, 7), // "2026-04"
    'AI Cost': m.ai_cost,
    'Human Cost': m.human_cost,
  }));

  // Cumulative savings line chart
  const cumulativeData = data.monthly_trend.map((m) => ({
    period: m.period.slice(0, 7),
    cumulative_savings: m.cumulative_savings,
    monthly_savings: m.savings,
  }));

  const totalTickets = data.all_time_tickets_ai + data.all_time_tickets_human;
  const aiPct = totalTickets > 0 ? ((data.all_time_tickets_ai / totalTickets) * 100).toFixed(0) : '0';
  const costRatio = data.avg_cost_per_ticket_human > 0
    ? (data.avg_cost_per_ticket_human / Math.max(data.avg_cost_per_ticket_ai, 0.01)).toFixed(1)
    : '0';

  return (
    <div className={cn('bg-[#1A1A1A] border border-white/[0.06] rounded-xl overflow-hidden', className)}>
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-white/[0.06]">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center">
            <svg className="w-4 h-4 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v12m-3-2.818.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
            </svg>
          </div>
          <div>
            <h3 className="text-sm font-semibold text-zinc-200">ROI Dashboard</h3>
            <p className="text-[11px] text-zinc-500">AI cost savings & return on investment</p>
          </div>
        </div>
        <span className="text-lg font-bold text-emerald-400">
          {formatCurrency(data.all_time_savings)}
        </span>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-2.5 px-5 py-4 border-b border-white/[0.04]">
        <StatCard
          label="This Month Savings"
          value={formatCurrency(data.current_month.savings)}
          subtext={`${formatCount(data.current_month.tickets_ai)} AI tickets`}
          color="text-emerald-400"
        />
        <StatCard
          label="AI Ticket Cost"
          value={formatCurrency(data.avg_cost_per_ticket_ai)}
          subtext={`${formatCount(data.all_time_tickets_ai)} total AI`}
          color="text-[#FF7F11]"
        />
        <StatCard
          label="Human Ticket Cost"
          value={formatCurrency(data.avg_cost_per_ticket_human)}
          subtext={`${formatCount(data.all_time_tickets_human)} total human`}
        />
        <StatCard
          label="Cost Ratio"
          value={`${costRatio}x cheaper`}
          subtext={`${aiPct}% resolved by AI`}
          color="text-sky-400"
        />
      </div>

      {/* Cost Comparison Bar Chart */}
      <div className="px-5 pt-4 pb-2">
        <p className="text-xs font-medium text-zinc-400 mb-2">Monthly Cost Comparison: AI vs Human</p>
        <div className="h-[240px]" role="img" aria-label="Monthly AI vs human cost comparison bar chart">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={barData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={COLORS.grid} />
              <XAxis
                dataKey="period"
                tick={{ fontSize: 10, fill: '#71717A' }}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                tick={{ fontSize: 10, fill: '#71717A' }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v: number) => `$${(v / 1000).toFixed(0)}K`}
              />
              <Tooltip content={<SavingsTooltip />} />
              <Legend
                wrapperStyle={{ fontSize: 11, paddingTop: 8 }}
                formatter={(value: string) => (
                  <span className="text-zinc-400">{value}</span>
                )}
              />
              <Bar dataKey="AI Cost" fill={COLORS.ai} radius={[3, 3, 0, 0]} barSize={16} />
              <Bar dataKey="Human Cost" fill={COLORS.human} radius={[3, 3, 0, 0]} barSize={16} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Cumulative Savings Line Chart */}
      <div className="px-5 pt-4 pb-4 border-t border-white/[0.04]">
        <p className="text-xs font-medium text-zinc-400 mb-2">Cumulative Savings Over Time</p>
        <div className="h-[200px]" role="img" aria-label="Cumulative savings trend chart">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={cumulativeData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="cumGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={COLORS.savings} stopOpacity={0.15} />
                  <stop offset="100%" stopColor={COLORS.savings} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke={COLORS.grid} />
              <XAxis
                dataKey="period"
                tick={{ fontSize: 10, fill: '#71717A' }}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                tick={{ fontSize: 10, fill: '#71717A' }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v: number) => `$${(v / 1000).toFixed(0)}K`}
              />
              <Tooltip content={<CumulativeTooltip />} />
              <Area
                type="monotone"
                dataKey="cumulative_savings"
                stroke={COLORS.savings}
                strokeWidth={2.5}
                fill="url(#cumGrad)"
                dot={false}
                activeDot={{ r: 4, strokeWidth: 0, fill: COLORS.savings }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
