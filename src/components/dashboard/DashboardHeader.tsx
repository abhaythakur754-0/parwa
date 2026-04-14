'use client';

import React from 'react';
import { cn } from '@/lib/utils';
import DateRangeSelector from './DateRangeSelector';

// ── Props ─────────────────────────────────────────────────────────────

interface DashboardHeaderProps {
  title: string;
  subtitle?: string;
  datePreset?: string;
  onDateChange?: (range: { start_date: string; end_date: string }) => void;
  children?: React.ReactNode;
  onRefresh?: () => void;
  isRefreshing?: boolean;
}

// ── DashboardHeader Component ─────────────────────────────────────────

export default function DashboardHeader({
  title,
  subtitle,
  datePreset = '30d',
  onDateChange,
  children,
  onRefresh,
  isRefreshing = false,
}: DashboardHeaderProps) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-white/[0.06]">
      {/* Left: Title + Subtitle */}
      <div>
        <h1 className="text-xl font-bold text-white">{title}</h1>
        {subtitle && (
          <p className="text-sm text-zinc-500 mt-0.5">{subtitle}</p>
        )}
      </div>

      {/* Right: Date Range + Actions */}
      <div className="flex items-center gap-3">
        {onDateChange && (
          <DateRangeSelector value={datePreset} onChange={onDateChange} />
        )}

        {onRefresh && (
          <button
            onClick={onRefresh}
            disabled={isRefreshing}
            className="w-9 h-9 rounded-lg flex items-center justify-center text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.05] transition-all duration-200 disabled:opacity-50"
            title="Refresh data"
          >
            <svg
              className={cn('w-4 h-4', isRefreshing && 'animate-spin')}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182" />
            </svg>
          </button>
        )}

        {children}
      </div>
    </div>
  );
}


