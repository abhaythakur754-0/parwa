'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import toast from 'react-hot-toast';
import { getErrorMessage } from '@/lib/api';
import apiClient from '@/lib/api';
import { cn } from '@/lib/utils';
import { dashboardApi, type KPIData, type MetricsResponse } from '@/lib/dashboard-api';
import {
  ROIDashboard,
  ConfidenceTrend,
  AdaptationTracker,
  CSATTrends,
  DriftDetection,
  QAScores,
  TicketForecast,
  GrowthNudge,
  DateRangeSelector,
} from '@/components/dashboard';

// ── Skeleton Helper ────────────────────────────────────────────────────

function Skeleton({ className }: { className?: string }) {
  return <div className={cn('animate-pulse rounded-lg bg-white/[0.06]', className)} />;
}

// ── Inline SVG Icons ───────────────────────────────────────────────────

function ChartBarSquareIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 14.25v2.25m3-4.5v4.5m3-6.75v6.75m3-9v9M6 20.25h12A2.25 2.25 0 0020.25 18V6A2.25 2.25 0 0018 3.75H6A2.25 2.25 0 003.75 6v12A2.25 2.25 0 006 20.25z" />
    </svg>
  );
}

function ArrowTrendingUpIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18L9 11.25l4.306 4.307a11.95 11.95 0 015.814-5.519l2.74-1.22m0 0l-5.94-2.28m5.94 2.28l-2.28 5.941" />
    </svg>
  );
}

function ArrowTrendingDownIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 6L9 12.75l4.286-4.286a11.948 11.948 0 014.306 6.43l.776 2.898m0 0l3.182-5.511m-3.182 5.51l-5.511-3.181" />
    </svg>
  );
}

function MinusSmallIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M18 12H6" />
    </svg>
  );
}

function DocumentArrowDownIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
    </svg>
  );
}

function SpinnerIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" className={className}>
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  );
}

function CheckCircleIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}

function ExclamationCircleIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
    </svg>
  );
}

// ── Export Report Types ────────────────────────────────────────────────

type ReportType = 'summary' | 'tickets' | 'agents' | 'sla' | 'csat' | 'forecast' | 'full';
type ExportFormat = 'csv' | 'pdf';

const REPORT_TYPE_OPTIONS: { label: string; value: ReportType }[] = [
  { label: 'Summary', value: 'summary' },
  { label: 'Tickets', value: 'tickets' },
  { label: 'Agents', value: 'agents' },
  { label: 'SLA', value: 'sla' },
  { label: 'CSAT', value: 'csat' },
  { label: 'Forecast', value: 'forecast' },
  { label: 'Full Report', value: 'full' },
];

const FORMAT_OPTIONS: { label: string; value: ExportFormat }[] = [
  { label: 'CSV', value: 'csv' },
  { label: 'PDF', value: 'pdf' },
];

// ── Helper: Format metric value ────────────────────────────────────────

function formatMetricValue(kpi: KPIData): string {
  const val = kpi.value;
  if (typeof val === 'number') {
    if (kpi.unit === '%' || kpi.key.includes('rate') || kpi.key.includes('pct')) {
      return `${val.toFixed(1)}%`;
    }
    if (val >= 1000000) return `${(val / 1000000).toFixed(1)}M`;
    if (val >= 1000) return `${(val / 1000).toFixed(1)}K`;
    if (kpi.unit === '$') return `$${val.toLocaleString()}`;
    return val.toLocaleString();
  }
  return String(val ?? '—');
}

// ── Stat Card ──────────────────────────────────────────────────────────

function StatCard({ kpi, loading }: { kpi: KPIData | undefined; loading: boolean }) {
  if (loading) return <Skeleton className="h-28" />;

  if (!kpi) {
    return (
      <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-5">
        <div className="text-zinc-500 text-sm">No data</div>
      </div>
    );
  }

  const change = kpi.change_pct;
  const direction = kpi.change_direction;

  return (
    <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-5 hover:border-white/[0.1] transition-colors">
      <div className="flex items-start justify-between">
        <p className="text-xs font-medium text-zinc-500 uppercase tracking-wider">{kpi.label}</p>
        {kpi.is_anomaly && (
          <span className="rounded-full bg-amber-500/15 text-amber-400 text-[9px] font-bold px-1.5 py-0.5 uppercase">
            Anomaly
          </span>
        )}
      </div>
      <p className="mt-2 text-2xl font-bold text-white">{formatMetricValue(kpi)}</p>
      {change != null && direction && direction !== 'neutral' && (
        <div className={cn('mt-1.5 flex items-center gap-1 text-xs font-medium', direction === 'up' ? 'text-emerald-400' : 'text-red-400')}>
          {direction === 'up' ? <ArrowTrendingUpIcon className="h-3.5 w-3.5" /> : <ArrowTrendingDownIcon className="h-3.5 w-3.5" />}
          <span>{change >= 0 ? '+' : ''}{change.toFixed(1)}%</span>
          <span className="text-zinc-600 ml-1">vs prev period</span>
        </div>
      )}
      {(!change || direction === 'neutral') && (
        <div className="mt-1.5 flex items-center gap-1 text-xs text-zinc-600">
          <MinusSmallIcon className="h-3.5 w-3.5" />
          <span>No change</span>
        </div>
      )}
    </div>
  );
}

// ── Section Wrapper ────────────────────────────────────────────────────

function SectionCard({ title, children, className }: { title?: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={cn('rounded-xl border border-white/[0.06] bg-[#1A1A1A] overflow-hidden', className)}>
      {title && (
        <div className="px-5 py-3.5 border-b border-white/[0.04]">
          <h3 className="text-sm font-semibold text-zinc-200">{title}</h3>
        </div>
      )}
      <div className="p-5">{children}</div>
    </div>
  );
}

// ════════════════════════════════════════════════════════════════════════
// Main Analytics Page Component
// ════════════════════════════════════════════════════════════════════════

export default function AnalyticsPage() {
  // ── State: Date Range ─────────────────────────────────────────────────
  const [datePreset, setDatePreset] = useState<string>('30d');
  const [dateRange, setDateRange] = useState<{ start_date: string; end_date: string }>({
    start_date: '',
    end_date: '',
  });
  const [refreshKey, setRefreshKey] = useState(0);

  // ── State: KPI Metrics ───────────────────────────────────────────────
  const [kpis, setKpis] = useState<KPIData[]>([]);
  const [kpisLoading, setKpisLoading] = useState(true);

  // ── State: Export Report ──────────────────────────────────────────────
  const [reportType, setReportType] = useState<ReportType>('summary');
  const [exportFormat, setExportFormat] = useState<ExportFormat>('csv');
  const [exportStartDate, setExportStartDate] = useState('');
  const [exportEndDate, setExportEndDate] = useState('');
  const [exportLoading, setExportLoading] = useState(false);
  const [exportJobId, setExportJobId] = useState<string | null>(null);
  const [exportStatus, setExportStatus] = useState<'idle' | 'queued' | 'processing' | 'completed' | 'failed'>('idle');
  const [exportProgress, setExportProgress] = useState<string>('');
  const pollingRef = useRef<NodeJS.Timeout | null>(null);

  // ── Load KPI Metrics ─────────────────────────────────────────────────

  const loadMetrics = useCallback(async () => {
    setKpisLoading(true);
    try {
      const periodMap: Record<string, string> = {
        today: 'today',
        '7d': 'last_7d',
        '30d': 'last_30d',
        '90d': 'last_90d',
      };
      const period = periodMap[datePreset] || 'last_30d';
      const data: MetricsResponse = await dashboardApi.getMetrics(period);
      setKpis(data.kpis);
    } catch {
      /* silent — individual cards will show empty state */
    } finally {
      setKpisLoading(false);
    }
  }, [datePreset]);

  useEffect(() => {
    loadMetrics();
  }, [loadMetrics, refreshKey]);

  // ── Date Range Handler ───────────────────────────────────────────────

  const handleDateRangeChange = useCallback((range: { start_date: string; end_date: string }) => {
    setDateRange(range);
    setRefreshKey(prev => prev + 1);
  }, []);

  // ── Export Report Handler ────────────────────────────────────────────

  const handleExport = async () => {
    setExportLoading(true);
    setExportStatus('idle');
    setExportJobId(null);
    setExportProgress('Submitting export request...');

    try {
      const { data } = await apiClient.post('/api/reports/export', {
        report_type: reportType,
        format: exportFormat,
        date_range_start: exportStartDate || undefined,
        date_range_end: exportEndDate || undefined,
      });

      const jobId = data?.job_id;
      if (!jobId) {
        toast.error('Export failed — no job ID returned');
        setExportLoading(false);
        setExportStatus('failed');
        setExportProgress('No job ID returned from server');
        return;
      }

      setExportJobId(jobId);
      setExportStatus('queued');
      setExportProgress('Report queued for generation...');

      // Start polling
      startPolling(jobId);
    } catch (error) {
      toast.error(getErrorMessage(error));
      setExportLoading(false);
      setExportStatus('failed');
      setExportProgress('Export request failed');
    }
  };

  const startPolling = (jobId: string) => {
    // Clear any existing polling
    if (pollingRef.current) clearInterval(pollingRef.current);

    let attempts = 0;
    const maxAttempts = 60; // 5 minutes at 5s intervals

    pollingRef.current = setInterval(async () => {
      attempts++;
      if (attempts > maxAttempts) {
        if (pollingRef.current) clearInterval(pollingRef.current);
        setExportStatus('failed');
        setExportProgress('Export timed out. Please try again.');
        setExportLoading(false);
        return;
      }

      try {
        const { data: status } = await apiClient.get(`/api/reports/jobs/${jobId}`);

        if (status.status === 'completed') {
          if (pollingRef.current) clearInterval(pollingRef.current);
          setExportStatus('completed');
          setExportProgress('Report ready for download!');
          setExportLoading(false);
          toast.success('Report generated successfully!');

          // Auto-download
          window.open(`/api/reports/download/${jobId}`, '_blank');
        } else if (status.status === 'failed') {
          if (pollingRef.current) clearInterval(pollingRef.current);
          setExportStatus('failed');
          setExportProgress(status.error || 'Export failed on server');
          setExportLoading(false);
          toast.error('Report generation failed');
        } else {
          setExportStatus(status.status === 'processing' ? 'processing' : 'queued');
          setExportProgress(
            status.status === 'processing'
              ? 'Generating report, please wait...'
              : `In queue — position ${status.position ?? '?'}...`
          );
        }
      } catch {
        // Network error during polling — keep trying
      }
    }, 5000);
  };

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, []);

  // ── Top 4 KPIs for Stats Strip ──────────────────────────────────────
  const statKpis = kpis.slice(0, 4);

  // ══════════════════════════════════════════════════════════════════════
  // Render
  // ══════════════════════════════════════════════════════════════════════

  return (
    <div className="jarvis-page-body min-h-screen bg-[#0A0A0A]">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        {/* ── Page Header ────────────────────────────────────────────── */}
        <div className="mb-8">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <div className="flex items-center gap-3 mb-2">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#FF7F11]/10">
                  <ChartBarSquareIcon className="h-5 w-5 text-[#FF7F11]" />
                </div>
                <h1 className="text-2xl font-bold text-white">Analytics</h1>
              </div>
              <p className="text-sm text-zinc-500 ml-[52px]">
                Deep insights into AI performance, customer satisfaction, and operational efficiency.
              </p>
            </div>
            <DateRangeSelector
              value={datePreset}
              onChange={(range) => {
                // Determine preset from returned range
                const daysDiff = range.start_date
                  ? Math.floor((new Date(range.end_date).getTime() - new Date(range.start_date).getTime()) / 86400000)
                  : 30;
                let preset = '30d';
                if (daysDiff <= 1) preset = 'today';
                else if (daysDiff <= 7) preset = '7d';
                else if (daysDiff <= 30) preset = '30d';
                else preset = '90d';
                setDatePreset(preset);
                handleDateRangeChange(range);
              }}
            />
          </div>
        </div>

        {/* ── Stats Strip: 4 Summary Cards ───────────────────────────── */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <StatCard kpi={statKpis[0]} loading={kpisLoading} />
          <StatCard kpi={statKpis[1]} loading={kpisLoading} />
          <StatCard kpi={statKpis[2]} loading={kpisLoading} />
          <StatCard kpi={statKpis[3]} loading={kpisLoading} />
        </div>

        {/* ── Chart Grid ─────────────────────────────────────────────── */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Row 1: ROI (2/3) + Growth Nudge (1/3) */}
          <div className="lg:col-span-2">
            <SectionCard title="Return on Investment">
              <ROIDashboard />
            </SectionCard>
          </div>
          <div className="lg:col-span-1">
            <SectionCard title="Smart Insights">
              <GrowthNudge />
            </SectionCard>
          </div>

          {/* Row 2: Ticket Forecast (2/3) + Confidence Trend (1/3) */}
          <div className="lg:col-span-2">
            <SectionCard title="Ticket Volume Forecast">
              <TicketForecast />
            </SectionCard>
          </div>
          <div className="lg:col-span-1">
            <SectionCard title="AI Confidence Trend">
              <ConfidenceTrend />
            </SectionCard>
          </div>

          {/* Row 3: CSAT Trends (2/3) + Adaptation Tracker (1/3) */}
          <div className="lg:col-span-2">
            <SectionCard title="Customer Satisfaction">
              <CSATTrends />
            </SectionCard>
          </div>
          <div className="lg:col-span-1">
            <SectionCard title="AI Learning Progress">
              <AdaptationTracker />
            </SectionCard>
          </div>

          {/* Row 4: QA Scores (2/3) + Drift Detection (1/3) */}
          <div className="lg:col-span-2">
            <SectionCard title="Quality Assurance">
              <QAScores />
            </SectionCard>
          </div>
          <div className="lg:col-span-1">
            <SectionCard title="Model Drift Detection">
              <DriftDetection />
            </SectionCard>
          </div>
        </div>

        {/* ── Export Report Section (AN10) ────────────────────────────── */}
        <div className="mt-8">
          <SectionCard title="Export Reports">
            <div className="space-y-5">
              {/* Report Type Selector */}
              <div>
                <label className="block text-xs font-medium text-zinc-400 uppercase tracking-wider mb-2">
                  Report Type
                </label>
                <div className="flex flex-wrap gap-2">
                  {REPORT_TYPE_OPTIONS.map((opt) => (
                    <button
                      key={opt.value}
                      onClick={() => setReportType(opt.value)}
                      className={cn(
                        'px-3.5 py-2 rounded-lg text-xs font-medium transition-all duration-200 border',
                        reportType === opt.value
                          ? 'bg-[#FF7F11]/15 text-[#FF7F11] border-[#FF7F11]/30 shadow-sm shadow-[#FF7F11]/5'
                          : 'bg-white/[0.03] text-zinc-400 border-white/[0.06] hover:bg-white/[0.06] hover:text-zinc-300'
                      )}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Format Selector */}
              <div>
                <label className="block text-xs font-medium text-zinc-400 uppercase tracking-wider mb-2">
                  Format
                </label>
                <div className="flex gap-2">
                  {FORMAT_OPTIONS.map((opt) => (
                    <button
                      key={opt.value}
                      onClick={() => setExportFormat(opt.value)}
                      className={cn(
                        'px-4 py-2 rounded-lg text-xs font-medium transition-all duration-200 border',
                        exportFormat === opt.value
                          ? 'bg-[#FF7F11]/15 text-[#FF7F11] border-[#FF7F11]/30 shadow-sm shadow-[#FF7F11]/5'
                          : 'bg-white/[0.03] text-zinc-400 border-white/[0.06] hover:bg-white/[0.06] hover:text-zinc-300'
                      )}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Date Range Inputs */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-zinc-400 uppercase tracking-wider mb-2">
                    Start Date
                  </label>
                  <input
                    type="date"
                    value={exportStartDate}
                    onChange={(e) => setExportStartDate(e.target.value)}
                    className="w-full rounded-lg border border-white/[0.08] bg-[#141414] px-3.5 py-2.5 text-sm text-zinc-300 placeholder-zinc-600 focus:outline-none focus:border-[#FF7F11]/40 focus:ring-1 focus:ring-[#FF7F11]/20 transition-colors"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-zinc-400 uppercase tracking-wider mb-2">
                    End Date
                  </label>
                  <input
                    type="date"
                    value={exportEndDate}
                    onChange={(e) => setExportEndDate(e.target.value)}
                    className="w-full rounded-lg border border-white/[0.08] bg-[#141414] px-3.5 py-2.5 text-sm text-zinc-300 placeholder-zinc-600 focus:outline-none focus:border-[#FF7F11]/40 focus:ring-1 focus:ring-[#FF7F11]/20 transition-colors"
                  />
                </div>
              </div>

              {/* Status / Progress */}
              {(exportStatus !== 'idle' || exportLoading) && (
                <div className={cn(
                  'rounded-lg border px-4 py-3 flex items-center gap-3',
                  exportStatus === 'completed'
                    ? 'bg-emerald-500/5 border-emerald-500/20'
                    : exportStatus === 'failed'
                    ? 'bg-red-500/5 border-red-500/20'
                    : 'bg-white/[0.03] border-white/[0.06]'
                )}>
                  {exportStatus === 'completed' ? (
                    <CheckCircleIcon className="h-5 w-5 text-emerald-400 shrink-0" />
                  ) : exportStatus === 'failed' ? (
                    <ExclamationCircleIcon className="h-5 w-5 text-red-400 shrink-0" />
                  ) : (
                    <SpinnerIcon className="h-5 w-5 text-[#FF7F11] shrink-0 animate-spin" />
                  )}
                  <div className="flex-1 min-w-0">
                    <p className={cn(
                      'text-sm font-medium',
                      exportStatus === 'completed' ? 'text-emerald-300'
                        : exportStatus === 'failed' ? 'text-red-300'
                        : 'text-zinc-300'
                    )}>
                      {exportStatus === 'completed' ? 'Report Ready'
                        : exportStatus === 'failed' ? 'Export Failed'
                        : exportStatus === 'processing' ? 'Processing...'
                        : 'Queued...'}
                    </p>
                    <p className="text-xs text-zinc-500 mt-0.5">{exportProgress}</p>
                  </div>
                  {exportStatus === 'completed' && exportJobId && (
                    <button
                      onClick={() => window.open(`/api/reports/download/${exportJobId}`, '_blank')}
                      className="shrink-0 inline-flex items-center gap-1.5 rounded-lg bg-emerald-500/15 border border-emerald-500/30 px-3 py-1.5 text-xs font-medium text-emerald-400 hover:bg-emerald-500/25 transition-colors"
                    >
                      <DocumentArrowDownIcon className="h-3.5 w-3.5" />
                      Download
                    </button>
                  )}
                </div>
              )}

              {/* Submit Button */}
              <div className="flex justify-end pt-1">
                <button
                  onClick={handleExport}
                  disabled={exportLoading}
                  className={cn(
                    'inline-flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-semibold transition-all duration-200',
                    exportLoading
                      ? 'bg-zinc-700 text-zinc-400 cursor-not-allowed'
                      : 'bg-[#FF7F11] text-white hover:bg-[#FF7F11]/90 shadow-lg shadow-[#FF7F11]/20'
                  )}
                >
                  {exportLoading ? (
                    <>
                      <SpinnerIcon className="h-4 w-4 animate-spin" />
                      Generating...
                    </>
                  ) : (
                    <>
                      <DocumentArrowDownIcon className="h-4 w-4" />
                      Export Report
                    </>
                  )}
                </button>
              </div>
            </div>
          </SectionCard>
        </div>
      </div>
    </div>
  );
}
