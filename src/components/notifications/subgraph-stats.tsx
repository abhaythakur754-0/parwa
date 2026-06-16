/**
 * SubgraphStats — Displays resolution rate performance per subgraph.
 *
 * Shows the current and previous resolution rates for each subgraph
 * (refund, tech, billing, general) with visual progress indicators
 * and trend arrows. Follows PARWA dark dashboard style.
 */

'use client';

import React from 'react';
import { cn } from '@/lib/utils';

// ── Types ────────────────────────────────────────────────────────────

export interface SubgraphStat {
  name: string;
  key: string;
  resolutionRate: number; // 0–1
  previousRate: number; // 0–1
  totalTickets: number;
  resolvedTickets: number;
  escalatedTickets: number;
  avgLatencyMs: number;
}

// ── Trend Indicator ──────────────────────────────────────────────────

function TrendArrow({ current, previous }: { current: number; previous: number }) {
  const diff = current - previous;
  if (Math.abs(diff) < 0.005) {
    return (
      <span className="text-zinc-500 text-xs flex items-center gap-0.5">
        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M18 12H6" />
        </svg>
        Flat
      </span>
    );
  }
  if (diff > 0) {
    return (
      <span className="text-emerald-400 text-xs flex items-center gap-0.5">
        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 19.5l7.5-7.5 7.5 7.5" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12l7.5-7.5L19.5 12" />
        </svg>
        +{(diff * 100).toFixed(1)}%
      </span>
    );
  }
  return (
    <span className="text-red-400 text-xs flex items-center gap-0.5">
      <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 4.5l-7.5 7.5-7.5-7.5" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 12l-7.5 7.5L4.5 12" />
      </svg>
      {(diff * 100).toFixed(1)}%
    </span>
  );
}

// ── Progress Bar ─────────────────────────────────────────────────────

function RateBar({ value, color }: { value: number; color: string }) {
  const pct = Math.round(value * 100);
  return (
    <div className="w-full h-1.5 bg-zinc-800 rounded-full overflow-hidden">
      <div
        className={cn('h-full rounded-full transition-all duration-500', color)}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

// ── Subgraph Color Mapping ───────────────────────────────────────────

const SUBGRAPH_COLORS: Record<string, { bar: string; icon: string; bg: string }> = {
  refund: {
    bar: 'bg-emerald-400',
    icon: 'text-emerald-400',
    bg: 'bg-emerald-500/10',
  },
  tech: {
    bar: 'bg-sky-400',
    icon: 'text-sky-400',
    bg: 'bg-sky-500/10',
  },
  billing: {
    bar: 'bg-amber-400',
    icon: 'text-amber-400',
    bg: 'bg-amber-500/10',
  },
  general: {
    bar: 'bg-purple-400',
    icon: 'text-purple-400',
    bg: 'bg-purple-500/10',
  },
};

const SUBGRAPH_ICONS: Record<string, React.ReactNode> = {
  refund: (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18.75a60.07 60.07 0 0115.797 2.101c.727.198 1.453-.342 1.453-1.096V18.75M3.75 4.5v.75A.75.75 0 013 6h-.75m0 0v-.375c0-.621.504-1.125 1.125-1.125H20.25M2.25 6v9m18-10.5v.75c0 .414.336.75.75.75h.75m-1.5-1.5h.375c.621 0 1.125.504 1.125 1.125v9.75c0 .621-.504 1.125-1.125 1.125h-.375m1.5-1.5H21a.75.75 0 00-.75.75v.75m0 0H3.75m0 0h-.375a1.125 1.125 0 01-1.125-1.125V15m1.5 1.5v-.75A.75.75 0 003 15h-.75M15 10.5a3 3 0 11-6 0 3 3 0 016 0zm3 0h.008v.008H18V10.5zm-12 0h.008v.008H6V10.5z" />
    </svg>
  ),
  tech: (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M11.42 15.17 17.25 21A2.652 2.652 0 0021 17.25l-5.877-5.877M11.42 15.17l2.496-3.03c.317-.384.74-.626 1.208-.766M11.42 15.17l-4.655 5.653a2.548 2.548 0 11-3.586-3.586l6.837-5.63m5.108-.233c.55-.164 1.163-.188 1.743-.14a4.5 4.5 0 004.486-6.336l-3.276 3.277a3.004 3.004 0 01-2.25-2.25l3.276-3.276a4.5 4.5 0 00-6.336 4.486c.091 1.076-.071 2.264-.904 2.95l-.102.085" />
    </svg>
  ),
  billing: (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 8.25h19.5M2.25 9h19.5m-16.5 5.25h6m-6 2.25h3m-3.75 3h15a2.25 2.25 0 002.25-2.25V6.75A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25v10.5A2.25 2.25 0 004.5 19.5z" />
    </svg>
  ),
  general: (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z" />
    </svg>
  ),
};

// ── SubgraphStats Component ──────────────────────────────────────────

interface SubgraphStatsProps {
  stats: SubgraphStat[];
}

export function SubgraphStats({ stats }: SubgraphStatsProps) {
  return (
    <div className="space-y-3">
      {stats.map((stat) => {
        const colors = SUBGRAPH_COLORS[stat.key] || SUBGRAPH_COLORS.general;
        const pct = Math.round(stat.resolutionRate * 100);

        return (
          <div
            key={stat.key}
            className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-4"
          >
            {/* Header row */}
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2.5">
                <div
                  className={cn(
                    'w-7 h-7 rounded-lg flex items-center justify-center',
                    colors.bg
                  )}
                >
                  <span className={colors.icon}>
                    {SUBGRAPH_ICONS[stat.key] || SUBGRAPH_ICONS.general}
                  </span>
                </div>
                <div>
                  <p className="text-sm font-medium text-white capitalize">
                    {stat.name}
                  </p>
                  <p className="text-[10px] text-zinc-600">
                    {stat.resolvedTickets}/{stat.totalTickets} resolved
                  </p>
                </div>
              </div>
              <div className="text-right">
                <p className="text-lg font-bold text-white">{pct}%</p>
                <TrendArrow
                  current={stat.resolutionRate}
                  previous={stat.previousRate}
                />
              </div>
            </div>

            {/* Progress bar */}
            <RateBar value={stat.resolutionRate} color={colors.bar} />

            {/* Detail row */}
            <div className="flex items-center gap-4 mt-3 text-[10px] text-zinc-500">
              <span className="flex items-center gap-1">
                <svg className="w-3 h-3 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
                </svg>
                {stat.escalatedTickets} escalated
              </span>
              <span className="flex items-center gap-1">
                <svg className="w-3 h-3 text-zinc-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                {stat.avgLatencyMs}ms avg
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default SubgraphStats;
