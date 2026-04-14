'use client';

import React, { useState, useEffect, useCallback } from 'react';
import toast from 'react-hot-toast';
import { cn } from '@/lib/utils';
import DashboardHeader from '@/components/dashboard/DashboardHeader';
import KPICard from '@/components/dashboard/KPICard';
import ActivityFeed from '@/components/dashboard/ActivityFeed';
import DashboardAlerts from '@/components/dashboard/DashboardAlerts';
import SavingsCounter from '@/components/dashboard/SavingsCounter';
import WorkforceAllocation from '@/components/dashboard/WorkforceAllocation';
import { dashboardApi } from '@/lib/analytics-api';
import { getErrorMessage } from '@/lib/api';
import type { DashboardHomeData, AnomalyAlert } from '@/types/analytics';

// ── Icons (inline SVGs) ──────────────────────────────────────────────

const Icons = {
  tickets: (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 6v.75m0 3v.75m0 3v.75m0 3V18m-9-5.25h5.25M7.5 15h3M3.375 5.25c-.621 0-1.125.504-1.125 1.125v3.026a2.999 2.999 0 0 1 0 5.198v3.026c0 .621.504 1.125 1.125 1.125h17.25c.621 0 1.125-.504 1.125-1.125v-3.026a2.999 2.999 0 0 1 0-5.198V6.375c0-.621-.504-1.125-1.125-1.125H3.375Z" />
    </svg>
  ),
  open: (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
    </svg>
  ),
  resolved: (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
    </svg>
  ),
  responseTime: (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75Z" />
    </svg>
  ),
  resolutionRate: (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18 9 11.25l4.306 4.306a11.95 11.95 0 0 1 5.814-5.518l2.74-1.22m0 0-5.94-2.281m5.94 2.28-2.28 5.941" />
    </svg>
  ),
  csat: (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M11.48 3.499a.562.562 0 0 1 1.04 0l2.125 5.111a.563.563 0 0 0 .475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 0 0-.182.557l1.285 5.385a.562.562 0 0 1-.84.61l-4.725-2.885a.562.562 0 0 0-.586 0L6.982 20.54a.562.562 0 0 1-.84-.61l1.285-5.386a.562.562 0 0 0-.182-.557l-4.204-3.602a.562.562 0 0 1 .321-.988l5.518-.442a.563.563 0 0 0 .475-.345L11.48 3.5Z" />
    </svg>
  ),
  awaiting: (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
    </svg>
  ),
  breached: (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
    </svg>
  ),
  compliance: (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75m-3-7.036A11.959 11.959 0 0 1 3.598 6 11.99 11.99 0 0 0 3 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285Z" />
    </svg>
  ),
};

// ── Helper: Format numbers ────────────────────────────────────────────

function formatNumber(n: number): string {
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return n.toLocaleString();
}

function formatHours(hours: number): string {
  if (hours < 1) return `${Math.round(hours * 60)}m`;
  return `${hours.toFixed(1)}h`;
}

function formatPercent(n: number): string {
  return `${n.toFixed(1)}%`;
}

// ── Period mapping for date presets ───────────────────────────────────

const PERIOD_DAYS_MAP: Record<string, number> = {
  'today': 1,
  '7d': 7,
  '30d': 30,
  '90d': 90,
  'custom': 30,
};

// ── Dashboard Page ────────────────────────────────────────────────────

export default function DashboardPage() {
  const [data, setData] = useState<DashboardHomeData | null>(null);
  const [datePreset, setDatePreset] = useState('30d');
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [alerts, setAlerts] = useState<AnomalyAlert[]>([]);

  // ── Fetch Dashboard Data (unified F-036 endpoint) ──────────────────

  const fetchDashboard = useCallback(async () => {
    try {
      setIsRefreshing(true);
      const periodDays = PERIOD_DAYS_MAP[datePreset] || 30;
      const dashboardData = await dashboardApi.getHome(periodDays);

      if (dashboardData.error) {
        console.warn('Dashboard returned error:', dashboardData.error);
        toast.error('Some dashboard data could not be loaded');
      }

      setData(dashboardData);
      setAlerts(dashboardData.anomalies || []);
    } catch (error) {
      console.error('Failed to fetch dashboard data:', error);
      toast.error(getErrorMessage(error));
    } finally {
      setIsRefreshing(false);
    }
  }, [datePreset]);

  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  // ── Handle Date Preset Change ───────────────────────────────────────

  const handleDateChange = useCallback((range: { start_date: string; end_date: string }) => {
    const today = new Date().toISOString().split('T')[0];
    const sevenDaysAgo = new Date(Date.now() - 7 * 86400000).toISOString().split('T')[0];
    const thirtyDaysAgo = new Date(Date.now() - 30 * 86400000).toISOString().split('T')[0];

    if (range.start_date === today) setDatePreset('today');
    else if (range.start_date === sevenDaysAgo) setDatePreset('7d');
    else if (range.start_date === thirtyDaysAgo) setDatePreset('30d');
    else setDatePreset('custom');
  }, []);

  // ── Handle Alert Dismiss ────────────────────────────────────────────

  const handleAlertDismiss = useCallback((index: number) => {
    setAlerts(prev => prev.filter((_, i) => i !== index));
  }, []);

  // ── Safe data accessors ─────────────────────────────────────────────

  const summary = data?.summary;
  const sla = data?.sla;
  const trend = data?.trend || [];
  const byCategory = data?.by_category || [];
  const activityFeed = data?.activity_feed || [];
  const csat = data?.csat;

  return (
    <div className="min-h-screen jarvis-page-body">
      <div className="p-6 lg:p-8 space-y-6">
        {/* Header */}
        <DashboardHeader
          title="Dashboard"
          subtitle="Overview of your support performance"
          datePreset={datePreset}
          onDateChange={handleDateChange}
          onRefresh={fetchDashboard}
          isRefreshing={isRefreshing}
        />

        {/* ── F-036: Dashboard Alerts Banner ──────────────────────────── */}
        <DashboardAlerts
          alerts={alerts}
          onDismiss={handleAlertDismiss}
        />

        {/* ── KPI Cards Row 1 ───────────────────────────────────────── */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
          <KPICard
            title="Total Tickets"
            value={summary ? formatNumber(summary.total_tickets) : '—'}
            subtitle="All time in range"
            icon={Icons.tickets}
            variant="default"
            isLoading={!data}
          />
          <KPICard
            title="Open Tickets"
            value={summary ? formatNumber(summary.open + summary.in_progress) : '—'}
            subtitle={`${summary ? formatNumber(summary.in_progress) : '—'} in progress`}
            icon={Icons.open}
            variant="info"
            isLoading={!data}
          />
          <KPICard
            title="Resolved"
            value={summary ? formatNumber(summary.resolved) : '—'}
            subtitle={`${summary ? formatPercent(summary.resolution_rate * 100) : '—'} resolution rate`}
            icon={Icons.resolved}
            variant="success"
            isLoading={!data}
          />
          <KPICard
            title="Avg Response"
            value={summary ? formatHours(summary.avg_first_response_time_hours) : '—'}
            subtitle="First response time"
            icon={Icons.responseTime}
            variant={summary && summary.avg_first_response_time_hours > 2 ? 'warning' : 'default'}
            isLoading={!data}
          />
          <KPICard
            title="Resolution Rate"
            value={summary ? formatPercent(summary.resolution_rate * 100) : '—'}
            subtitle="Tickets resolved"
            icon={Icons.resolutionRate}
            variant={summary && summary.resolution_rate >= 0.8 ? 'success' : 'warning'}
            isLoading={!data}
          />
          <KPICard
            title="CSAT Score"
            value={csat ? `${csat.avg_rating.toFixed(1)}/5` : '—'}
            subtitle={csat ? `${csat.total_ratings} ratings` : 'Customer satisfaction'}
            icon={Icons.csat}
            variant={csat && csat.avg_rating >= 4 ? 'success' : 'default'}
            isLoading={!data}
          />
        </div>

        {/* ── KPI Cards Row 2: Priority + SLA ───────────────────────── */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-6 gap-4">
          <KPICard
            title="Critical"
            value={summary ? formatNumber(summary.critical) : '—'}
            icon={(
              <span className="w-3 h-3 rounded-full bg-red-500" />
            )}
            variant="danger"
            isLoading={!data}
          />
          <KPICard
            title="High Priority"
            value={summary ? formatNumber(summary.high) : '—'}
            icon={(
              <span className="w-3 h-3 rounded-full bg-orange-500" />
            )}
            variant="warning"
            isLoading={!data}
          />
          <KPICard
            title="Awaiting Client"
            value={summary ? formatNumber(summary.awaiting_client) : '—'}
            icon={Icons.awaiting}
            variant="default"
            isLoading={!data}
          />
          <KPICard
            title="Avg Resolution"
            value={summary ? formatHours(summary.avg_resolution_time_hours) : '—'}
            subtitle="Time to resolve"
            icon={Icons.responseTime}
            variant="default"
            isLoading={!data}
          />
          <KPICard
            title="SLA Breached"
            value={sla ? formatNumber(sla.breached_count) : '—'}
            subtitle={`of ${sla ? formatNumber(sla.total_tickets_with_sla) : '—'} tickets`}
            icon={Icons.breached}
            variant={sla && sla.breached_count > 0 ? 'danger' : 'success'}
            isLoading={!data}
          />
          <KPICard
            title="SLA Compliance"
            value={sla ? formatPercent(sla.compliance_rate) : '—'}
            subtitle={`${sla ? formatNumber(sla.approaching_count) : '—'} approaching`}
            icon={Icons.compliance}
            variant={sla && sla.compliance_rate >= 95 ? 'success' : sla && sla.compliance_rate >= 80 ? 'warning' : 'danger'}
            isLoading={!data}
          />
        </div>

        {/* ── Charts + Activity Feed Row ─────────────────────────────── */}
        {data && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-2">
            {/* Ticket Trend Chart (placeholder for Day 2) */}
            <div className="lg:col-span-2 rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-6">
              <h3 className="text-sm font-semibold text-zinc-300 mb-1">Ticket Trends</h3>
              <p className="text-xs text-zinc-600 mb-4">Volume over time</p>
              <div className="h-[260px] flex items-center justify-center text-zinc-600 text-sm">
                <div className="text-center space-y-2">
                  <svg className="w-10 h-10 mx-auto text-zinc-700" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 0 1 3 19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V8.625ZM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V4.125Z" />
                  </svg>
                  <p>Trend chart coming in Day 2</p>
                  <p className="text-xs text-zinc-700">{trend.length} data points available</p>
                </div>
              </div>
            </div>

            {/* F-037: Activity Feed */}
            <ActivityFeed
              initialEvents={activityFeed}
              showFilters={true}
            />
          </div>
        )}

        {/* ── Savings + Workforce Row (F-040 + F-041) ─────────────── */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <SavingsCounter
            initialData={data?.savings ? { ...data.savings } : undefined}
          />
          <WorkforceAllocation
            initialData={data?.workforce ? { ...data.workforce } : undefined}
          />
        </div>

        {/* ── Bottom Row: Category + Agent Performance ───────────────── */}
        {data && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Category Distribution */}
            <div className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-6">
              <h3 className="text-sm font-semibold text-zinc-300 mb-1">Category Distribution</h3>
              <p className="text-xs text-zinc-600 mb-4">Tickets by category</p>
              <div className="space-y-3">
                {byCategory.map((cat) => (
                  <div key={cat.category} className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-zinc-400">{cat.category}</span>
                      <span className="text-xs text-zinc-500">
                        {cat.count} tickets ({cat.percentage.toFixed(1)}%)
                      </span>
                    </div>
                    <div className="h-2 bg-white/[0.05] rounded-full overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-[#FF7F11]/60 to-[#FF7F11]/40 rounded-full transition-all duration-500"
                        style={{ width: `${Math.min(cat.percentage, 100)}%` }}
                      />
                    </div>
                  </div>
                ))}
                {byCategory.length === 0 && (
                  <p className="text-zinc-600 text-sm text-center py-8">No category data yet</p>
                )}
              </div>
            </div>

            {/* Agent Performance (placeholder for Day 2) */}
            <div className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-6">
              <h3 className="text-sm font-semibold text-zinc-300 mb-4">Quick Agent Overview</h3>
              <div className="text-zinc-600 text-sm text-center py-6">
                Agent performance table coming in Day 2
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
