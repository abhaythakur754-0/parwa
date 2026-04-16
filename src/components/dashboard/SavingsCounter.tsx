/**
 * PARWA SavingsCounter — Day 2 (O1.10)
 *
 * Animated savings counter showing cumulative savings vs human agents.
 * Compares PARWA AI cost to equivalent human agent cost.
 * Shows daily, weekly, monthly breakdown. Animated counting effect.
 * Uses real data from /api/analytics/savings.
 */

'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { dashboardApi, type ROIDashboardResponse } from '@/lib/dashboard-api';

// ── Helpers ────────────────────────────────────────────────────────────

function formatCurrency(n: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(n);
}

// ── Animated number counter ────────────────────────────────────────────

function AnimatedNumber({ value, prefix = '$', duration = 1500 }: { value: number; prefix?: string; duration?: number }) {
  const [display, setDisplay] = useState(0);
  const prevValue = useRef(0);

  useEffect(() => {
    const start = prevValue.current;
    const end = value;
    const startTime = performance.now();

    function animate(currentTime: number) {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      // Ease out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(start + (end - start) * eased);

      if (progress < 1) {
        requestAnimationFrame(animate);
      } else {
        prevValue.current = end;
      }
    }

    requestAnimationFrame(animate);
  }, [value, duration]);

  return (
    <span className="tabular-nums">
      {prefix}{display.toLocaleString('en-US', { maximumFractionDigits: 0 })}
    </span>
  );
}

// ── Component ──────────────────────────────────────────────────────────

export default function SavingsCounter() {
  const [data, setData] = useState<ROIDashboardResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [period, setPeriod] = useState<'month' | 'year'>('month');

  const fetchData = useCallback(() => {
    dashboardApi.getROIDashboard(12)
      .then(setData)
      .catch(() => {
        // Silent fail
      })
      .finally(() => setIsLoading(false));
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (isLoading) {
    return (
      <div className="rounded-xl bg-[#141414] border border-white/[0.06] p-5">
        <div className="h-4 w-32 rounded bg-white/[0.04] animate-pulse mb-4" />
        <div className="h-10 w-48 rounded bg-white/[0.04] animate-pulse mb-3" />
        <div className="h-3 w-40 rounded bg-white/[0.04] animate-pulse" />
      </div>
    );
  }

  const monthly = data?.current_month;
  const yearlySavings = data?.all_time_savings || 0;

  const humanCostMonthly = monthly?.human_cost || 0;
  const aiCostMonthly = monthly?.ai_cost || 0;
  const savedMonthly = monthly?.savings || 0;
  const savingsPct = data?.savings_pct || 0;

  const displaySaved = period === 'month' ? savedMonthly : yearlySavings;
  const displayHuman = period === 'month' ? humanCostMonthly : humanCostMonthly * 12;
  const displayAI = period === 'month' ? aiCostMonthly : aiCostMonthly * 12;

  return (
    <div className="rounded-xl bg-gradient-to-br from-[#141414] to-[#111111] border border-white/[0.06] p-5 relative overflow-hidden">
      {/* Subtle glow accent */}
      <div className="absolute -top-20 -right-20 w-40 h-40 bg-emerald-500/5 rounded-full blur-3xl pointer-events-none" />

      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-zinc-300">You&apos;re Saving</h3>
        <div className="flex items-center rounded-lg border border-white/[0.06] bg-white/[0.03] p-0.5">
          <button
            onClick={() => setPeriod('month')}
            className={`px-2 py-0.5 rounded-md text-[11px] font-medium transition-all ${
              period === 'month'
                ? 'bg-emerald-500/15 text-emerald-400'
                : 'text-zinc-500 hover:text-zinc-300'
            }`}
          >
            Monthly
          </button>
          <button
            onClick={() => setPeriod('year')}
            className={`px-2 py-0.5 rounded-md text-[11px] font-medium transition-all ${
              period === 'year'
                ? 'bg-emerald-500/15 text-emerald-400'
                : 'text-zinc-500 hover:text-zinc-300'
            }`}
          >
            Yearly
          </button>
        </div>
      </div>

      {/* Big savings number */}
      <div className="mb-4">
        <p className="text-3xl font-bold text-emerald-400 tracking-tight">
          <AnimatedNumber value={displaySaved} />
        </p>
        <p className="text-xs text-zinc-500 mt-1">
          vs hiring human agents this {period}
        </p>
      </div>

      {/* Comparison breakdown */}
      <div className="space-y-2">
        {/* PARWA AI cost */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-orange-400" />
            <span className="text-xs text-zinc-400">PARWA AI</span>
          </div>
          <span className="text-sm font-medium text-zinc-300 tabular-nums">
            {formatCurrency(displayAI)}
          </span>
        </div>

        {/* Human cost */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-zinc-500" />
            <span className="text-xs text-zinc-400">Human Agents</span>
          </div>
          <span className="text-sm font-medium text-zinc-300 tabular-nums line-through decoration-zinc-600">
            {formatCurrency(displayHuman)}
          </span>
        </div>

        {/* Savings bar */}
        <div className="mt-2 pt-2 border-t border-white/[0.04]">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[11px] text-zinc-500">Savings Rate</span>
            <span className="text-sm font-bold text-emerald-400 tabular-nums">{savingsPct.toFixed(1)}%</span>
          </div>
          <div className="h-2 rounded-full bg-white/[0.06] overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-emerald-400 transition-all duration-1000"
              style={{ width: `${Math.min(savingsPct, 100)}%` }}
            />
          </div>
        </div>
      </div>

      {/* Tickets handled */}
      {data && (
        <div className="mt-3 pt-3 border-t border-white/[0.04] flex items-center justify-between">
          <span className="text-[11px] text-zinc-500">AI Tickets Handled</span>
          <span className="text-xs font-medium text-zinc-400 tabular-nums">
            {period === 'month'
              ? (data.current_month?.tickets_ai || 0).toLocaleString()
              : (data.all_time_tickets_ai || 0).toLocaleString()}
          </span>
        </div>
      )}
    </div>
  );
}
