/**
 * PARWA DriftDetection — Week 16 Day 5 (F-116)
 *
 * Model drift detection report panel showing drift alerts
 * with severity badges, metric drift percentages, status,
 * and recovery actions.
 */

'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import {
  dashboardApi,
  type DriftReportsResponse,
  type DriftReport,
} from '@/lib/dashboard-api';

// ── Severity Config ───────────────────────────────────────────────────

const SEVERITY_CONFIG: Record<string, { borderColor: string; bgColor: string; badgeColor: string; label: string; dotColor: string }> = {
  critical: {
    borderColor: 'border-red-500/30',
    bgColor: 'bg-red-500/[0.04]',
    badgeColor: 'bg-red-500/15 text-red-400 border-red-500/20',
    label: 'Critical',
    dotColor: 'bg-red-500',
  },
  warning: {
    borderColor: 'border-amber-500/25',
    bgColor: 'bg-amber-500/[0.03]',
    badgeColor: 'bg-amber-500/15 text-amber-400 border-amber-500/20',
    label: 'Warning',
    dotColor: 'bg-amber-500',
  },
  info: {
    borderColor: 'border-sky-500/20',
    bgColor: 'bg-sky-500/[0.03]',
    badgeColor: 'bg-sky-500/15 text-sky-400 border-sky-500/20',
    label: 'Info',
    dotColor: 'bg-sky-500',
  },
};

const STATUS_STYLES: Record<string, string> = {
  active: 'text-red-400',
  investigating: 'text-amber-400',
  resolved: 'text-emerald-400',
};

// ── Skeleton ──────────────────────────────────────────────────────────

function ReportSkeleton() {
  return (
    <div className="p-5 space-y-3">
      <Skeleton className="h-4 w-44 bg-white/[0.06]" />
      <div className="space-y-2.5">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-16 w-full rounded-lg bg-white/[0.04]" />
        ))}
      </div>
    </div>
  );
}

// ── Empty State ───────────────────────────────────────────────────────

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div className="w-12 h-12 rounded-xl bg-white/[0.03] border border-white/[0.06] flex items-center justify-center mb-3">
        <svg className="w-6 h-6 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75m-3-7.036A11.959 11.959 0 0 1 3.598 6 11.99 11.99 0 0 0 3 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285Z" />
        </svg>
      </div>
      <p className="text-sm text-zinc-500 font-medium">No drift detected</p>
      <p className="text-xs text-zinc-600 mt-1">Model performance is stable</p>
    </div>
  );
}

// ── Single Drift Card ─────────────────────────────────────────────────

function DriftCard({ report }: { report: DriftReport }) {
  const config = SEVERITY_CONFIG[report.severity] ?? SEVERITY_CONFIG.info;
  const isPositive = report.drift_pct <= 0;

  return (
    <div
      className={cn(
        'rounded-lg border p-3.5 transition-all duration-200',
        'hover:bg-white/[0.01]',
        config.borderColor,
        config.bgColor
      )}
    >
      {/* Top row: metric + severity + status */}
      <div className="flex items-center gap-2 mb-2">
        <span className={cn('w-1.5 h-1.5 rounded-full', config.dotColor)} />
        <span className="text-sm font-semibold text-zinc-200 flex-1 truncate">
          {report.metric_name}
        </span>
        <span className={cn('inline-flex px-2 py-0.5 rounded-md text-[10px] font-medium border', config.badgeColor)}>
          {config.label}
        </span>
        <span className={cn('text-[10px] font-medium capitalize', STATUS_STYLES[report.status] ?? 'text-zinc-500')}>
          {report.status}
        </span>
      </div>

      {/* Description */}
      <p className="text-xs text-zinc-400 leading-relaxed mb-2.5">
        {report.description}
      </p>

      {/* Metrics row */}
      <div className="flex items-center gap-4 text-xs">
        <div className="flex items-center gap-1.5">
          <span className="text-zinc-500">Drift:</span>
          <span className={cn('font-semibold', isPositive ? 'text-emerald-400' : 'text-red-400')}>
            {isPositive ? '' : '+'}{report.drift_pct.toFixed(1)}%
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-zinc-500">Baseline:</span>
          <span className="text-zinc-300">{report.baseline_value.toFixed(2)}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-zinc-500">Current:</span>
          <span className="text-zinc-300">{report.metric_value.toFixed(2)}</span>
        </div>
      </div>

      {/* Recovery action (if any) */}
      {report.recovery_action && (
        <div className="mt-2 pt-2 border-t border-white/[0.04]">
          <p className="text-[10px] text-zinc-500">
            <span className="text-zinc-400 font-medium">Recovery:</span>{' '}
            {report.recovery_action}
          </p>
        </div>
      )}
    </div>
  );
}

// ── DriftDetection Component ──────────────────────────────────────────

interface DriftDetectionProps {
  initialData?: DriftReportsResponse;
  isLoading?: boolean;
  className?: string;
}

export default function DriftDetection({
  initialData,
  isLoading = false,
  className,
}: DriftDetectionProps) {
  const [data, setData] = useState<DriftReportsResponse | null>(initialData ?? null);
  const [filter, setFilter] = useState<'all' | 'active' | 'resolved'>('all');
  const [isFetching, setIsFetching] = useState(false);

  useEffect(() => {
    if (initialData) setData(initialData);
  }, [initialData]);

  const fetchData = useCallback(async () => {
    if (isFetching) return;
    setIsFetching(true);
    try {
      const result = await dashboardApi.getDriftReports(20);
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
        <ReportSkeleton />
      </div>
    );
  }

  if (!data || !data.reports?.length) {
    return (
      <div className={cn('bg-[#1A1A1A] border border-white/[0.06] rounded-xl overflow-hidden', className)}>
        {/* Header */}
        <div className="flex items-center gap-2.5 px-5 py-3 border-b border-white/[0.06]">
          <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center">
            <svg className="w-4 h-4 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75m-3-7.036A11.959 11.959 0 0 1 3.598 6 11.99 11.99 0 0 0 3 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285Z" />
            </svg>
          </div>
          <div>
            <h3 className="text-sm font-semibold text-zinc-200">Drift Detection</h3>
            <p className="text-[11px] text-zinc-500">Model performance monitoring</p>
          </div>
        </div>
        <EmptyState />
      </div>
    );
  }

  const filteredReports = filter === 'all'
    ? data.reports
    : data.reports.filter((r) => r.status === filter);

  const FILTER_TABS = [
    { key: 'all' as const, label: 'All' },
    { key: 'active' as const, label: `Active (${data.active_count})` },
    { key: 'resolved' as const, label: 'Resolved' },
  ];

  return (
    <div className={cn('bg-[#1A1A1A] border border-white/[0.06] rounded-xl overflow-hidden', className)}>
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-white/[0.06]">
        <div className="flex items-center gap-2.5">
          <div className={cn(
            'w-8 h-8 rounded-lg flex items-center justify-center',
            data.most_severe === 'critical' ? 'bg-red-500/10' :
            data.most_severe === 'warning' ? 'bg-amber-500/10' : 'bg-emerald-500/10'
          )}>
            <svg className={cn(
              'w-4 h-4',
              data.most_severe === 'critical' ? 'text-red-400' :
              data.most_severe === 'warning' ? 'text-amber-400' : 'text-emerald-400'
            )} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
            </svg>
          </div>
          <div>
            <h3 className="text-sm font-semibold text-zinc-200">Drift Detection</h3>
            <p className="text-[11px] text-zinc-500">Model performance monitoring</p>
          </div>
        </div>
        <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/[0.06] text-zinc-400 border border-white/[0.08] font-medium">
          {data.total} reports
        </span>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center gap-0.5 px-5 py-2 border-b border-white/[0.04]" role="tablist" aria-label="Drift report filter">
        {FILTER_TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setFilter(tab.key)}
            role="tab"
            aria-selected={filter === tab.key}
            className={cn(
              'px-2.5 py-1 rounded-md text-xs font-medium transition-all duration-200',
              filter === tab.key
                ? 'bg-white/[0.08] text-zinc-200'
                : 'text-zinc-500 hover:text-zinc-400 hover:bg-white/[0.03]'
            )}
          >
            {tab.label}
          </button>
        ))}
        {data.last_detected_at && (
          <span className="ml-auto text-[10px] text-zinc-600">
            Last: {new Date(data.last_detected_at).toLocaleDateString()}
          </span>
        )}
      </div>

      {/* Report List */}
      <div className="p-4 space-y-2.5 max-h-[400px] overflow-y-auto" role="list" aria-label="Drift reports">
        {filteredReports.length === 0 ? (
          <div className="text-center py-8">
            <p className="text-xs text-zinc-600">No {filter} reports</p>
          </div>
        ) : (
          filteredReports.map((report) => (
            <DriftCard key={report.report_id} report={report} />
          ))
        )}
      </div>
    </div>
  );
}
