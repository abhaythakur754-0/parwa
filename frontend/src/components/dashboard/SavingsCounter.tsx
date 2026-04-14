'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { cn } from '@/lib/utils';
import { get } from '@/lib/api';

// ── Types ─────────────────────────────────────────────────────────────

interface SavingsSnapshot {
  period: string;
  date: string;
  tickets_ai: number;
  tickets_human: number;
  ai_cost: number;
  human_cost: number;
  savings: number;
  cumulative_savings: number;
}

interface SavingsData {
  current_month: SavingsSnapshot;
  previous_month: SavingsSnapshot;
  all_time_savings: number;
  all_time_tickets_ai: number;
  all_time_tickets_human: number;
  monthly_trend: SavingsSnapshot[];
  avg_cost_per_ticket_ai: number;
  avg_cost_per_ticket_human: number;
  savings_pct: number;
}

// ── Props ─────────────────────────────────────────────────────────────

interface SavingsCounterProps {
  initialData?: Partial<SavingsData>;
  className?: string;
}

// ── Formatters ────────────────────────────────────────────────────────

function formatCurrency(amount: number): string {
  if (amount >= 1000000) return `$${(amount / 1000000).toFixed(1)}M`;
  if (amount >= 1000) return `$${(amount / 1000).toFixed(1)}K`;
  return `$${amount.toFixed(2)}`;
}

function formatNumber(n: number): string {
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return n.toLocaleString();
}

// ── Animated Counter ──────────────────────────────────────────────────

function AnimatedValue({ value, prefix = '', suffix = '', decimals = 0 }: {
  value: number;
  prefix?: string;
  suffix?: string;
  decimals?: number;
}) {
  const [displayed, setDisplayed] = useState(0);

  useEffect(() => {
    const duration = 800;
    const steps = 30;
    const stepTime = duration / steps;
    const increment = value / steps;
    let current = 0;
    let step = 0;

    const timer = setInterval(() => {
      step++;
      current = Math.min(value, increment * step);
      // Ease-out
      const progress = step / steps;
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplayed(value * eased);
      if (step >= steps) {
        setDisplayed(value);
        clearInterval(timer);
      }
    }, stepTime);

    return () => clearInterval(timer);
  }, [value]);

  const formatted = displayed.toFixed(decimals);
  const parts = formatted.split('.');
  const intPart = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ',');

  return (
    <span className="tabular-nums">
      {prefix}{intPart}{parts[1] ? `.${parts[1]}` : ''}{suffix}
    </span>
  );
}

// ── SavingsCounter Component ──────────────────────────────────────────

export default function SavingsCounter({
  initialData,
  className,
}: SavingsCounterProps) {
  const [data, setData] = useState<SavingsData | null>(null);
  const [isLoading, setIsLoading] = useState(!initialData);
  const [view, setView] = useState<'overview' | 'trend'>('overview');

  // Fetch savings data
  const fetchSavings = useCallback(async () => {
    try {
      setIsLoading(true);
      const result = await get<SavingsData>('/api/analytics/savings?months=12');
      setData(result);
    } catch (error) {
      console.error('Failed to fetch savings data:', error);
      // Use initial data as fallback
      if (initialData) {
        setData(initialData as SavingsData);
      }
    } finally {
      setIsLoading(false);
    }
  }, [initialData]);

  useEffect(() => {
    if (initialData && Object.keys(initialData).length > 0) {
      setData(initialData as SavingsData);
      setIsLoading(false);
    } else {
      fetchSavings();
    }
  }, [fetchSavings, initialData]);

  const d = data;
  const monthOverMonthChange = d
    ? d.current_month.savings - d.previous_month.savings
    : 0;
  const momPct = d && d.previous_month.savings > 0
    ? ((monthOverMonthChange / d.previous_month.savings) * 100).toFixed(1)
    : null;

  return (
    <div className={cn(
      'rounded-xl bg-[#1A1A1A] border border-white/[0.06] overflow-hidden',
      className
    )}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.06]">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-md bg-emerald-500/10 flex items-center justify-center">
            <svg className="w-3.5 h-3.5 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v12m-3-2.818.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
            </svg>
          </div>
          <h3 className="text-sm font-semibold text-zinc-300">AI Savings</h3>
        </div>

        <div className="flex items-center gap-0.5 bg-white/[0.03] rounded-lg p-0.5">
          <button
            onClick={() => setView('overview')}
            className={cn(
              'px-2 py-1 text-[11px] font-medium rounded-md transition-all duration-150',
              view === 'overview'
                ? 'bg-[#FF7F11]/15 text-[#FF7F11]'
                : 'text-zinc-500 hover:text-zinc-400'
            )}
          >
            Overview
          </button>
          <button
            onClick={() => setView('trend')}
            className={cn(
              'px-2 py-1 text-[11px] font-medium rounded-md transition-all duration-150',
              view === 'trend'
                ? 'bg-[#FF7F11]/15 text-[#FF7F11]'
                : 'text-zinc-500 hover:text-zinc-400'
            )}
          >
            Trend
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="p-4">
        {isLoading ? (
          <div className="space-y-4 animate-pulse">
            <div className="h-10 w-48 bg-white/[0.06] rounded" />
            <div className="h-4 w-32 bg-white/[0.06] rounded" />
            <div className="grid grid-cols-2 gap-3 mt-4">
              <div className="h-16 bg-white/[0.06] rounded-lg" />
              <div className="h-16 bg-white/[0.06] rounded-lg" />
            </div>
          </div>
        ) : !d ? (
          <div className="text-center py-8">
            <p className="text-sm text-zinc-600">No savings data yet</p>
            <p className="text-xs text-zinc-700 mt-1">Data will appear as AI resolves tickets</p>
          </div>
        ) : view === 'overview' ? (
          <div className="space-y-4">
            {/* Main Savings Amount */}
            <div>
              <p className="text-xs text-zinc-500 mb-1">Total Savings (All Time)</p>
              <div className="flex items-baseline gap-2">
                <span className="text-3xl font-bold text-emerald-400">
                  <AnimatedValue value={d.all_time_savings} prefix="$" decimals={2} />
                </span>
                {momPct && (
                  <span className={cn(
                    'text-xs font-semibold',
                    Number(momPct) >= 0 ? 'text-emerald-400' : 'text-red-400'
                  )}>
                    {Number(momPct) >= 0 ? '+' : ''}{momPct}% MoM
                  </span>
                )}
              </div>
            </div>

            {/* Cost Comparison Row */}
            <div className="grid grid-cols-2 gap-3">
              {/* AI Cost */}
              <div className="rounded-lg bg-white/[0.03] border border-white/[0.04] p-3">
                <div className="flex items-center gap-1.5 mb-2">
                  <div className="w-2 h-2 rounded-full bg-[#FF7F11]" />
                  <span className="text-[11px] text-zinc-500 uppercase tracking-wider">AI Cost/ticket</span>
                </div>
                <p className="text-lg font-bold text-white tabular-nums">
                  ${d.avg_cost_per_ticket_ai.toFixed(2)}
                </p>
                <p className="text-[11px] text-zinc-600 mt-0.5">
                  {formatNumber(d.all_time_tickets_ai)} tickets handled
                </p>
              </div>

              {/* Human Cost */}
              <div className="rounded-lg bg-white/[0.03] border border-white/[0.04] p-3">
                <div className="flex items-center gap-1.5 mb-2">
                  <div className="w-2 h-2 rounded-full bg-zinc-500" />
                  <span className="text-[11px] text-zinc-500 uppercase tracking-wider">Human Cost/ticket</span>
                </div>
                <p className="text-lg font-bold text-white tabular-nums">
                  ${d.avg_cost_per_ticket_human.toFixed(2)}
                </p>
                <p className="text-[11px] text-zinc-600 mt-0.5">
                  {formatNumber(d.all_time_tickets_human)} tickets handled
                </p>
              </div>
            </div>

            {/* Savings Percentage Bar */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-[11px] text-zinc-500">Cost Reduction</span>
                <span className="text-sm font-semibold text-emerald-400">{d.savings_pct}%</span>
              </div>
              <div className="h-2 bg-white/[0.05] rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-emerald-500/60 to-emerald-400/40 rounded-full transition-all duration-700"
                  style={{ width: `${Math.min(d.savings_pct, 100)}%` }}
                />
              </div>
            </div>

            {/* This Month Snapshot */}
            {d.current_month.tickets_ai + d.current_month.tickets_human > 0 && (
              <div className="pt-3 border-t border-white/[0.04]">
                <p className="text-[11px] text-zinc-500 mb-2">This Month</p>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-zinc-400">
                    <span className="text-white font-medium">{d.current_month.tickets_ai}</span> AI
                    <span className="text-zinc-600 mx-1.5">vs</span>
                    <span className="text-white font-medium">{d.current_month.tickets_human}</span> Human
                  </span>
                  <span className="text-emerald-400 font-medium">
                    +{formatCurrency(d.current_month.savings)} saved
                  </span>
                </div>
              </div>
            )}
          </div>
        ) : (
          /* Trend View */
          <div className="space-y-1.5 max-h-[280px] overflow-y-auto scrollbar-thin">
            {d.monthly_trend.map((month) => (
              <div
                key={month.period}
                className="flex items-center justify-between px-2 py-1.5 rounded-lg hover:bg-white/[0.03] transition-colors"
              >
                <div className="flex items-center gap-2">
                  <span className="text-xs text-zinc-500 w-16">{month.period}</span>
                  <div className="flex items-center gap-1.5 text-[11px]">
                    <span className="text-[#FF7F11]">{month.tickets_ai} AI</span>
                    <span className="text-zinc-600">/</span>
                    <span className="text-zinc-500">{month.tickets_human} human</span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className={cn(
                    'text-xs font-medium tabular-nums',
                    month.savings >= 0 ? 'text-emerald-400' : 'text-red-400'
                  )}>
                    {month.savings >= 0 ? '+' : ''}{formatCurrency(month.savings)}
                  </span>
                  <span className="text-[11px] text-zinc-600 tabular-nums w-20 text-right">
                    {formatCurrency(month.cumulative_savings)}
                  </span>
                </div>
              </div>
            ))}
            {d.monthly_trend.length === 0 && (
              <p className="text-zinc-600 text-sm text-center py-6">No trend data yet</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
