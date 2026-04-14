'use client';

import React, { useState, useEffect, useCallback } from 'react';
import toast from 'react-hot-toast';
import { useAuth } from '@/hooks/useAuth';
import {
  WelcomeCard,
  TrendChart,
  CategoryChart,
  SLAChart,
  AgentPerformanceTable,
  ResponseTimeChart,
} from '@/components/dashboard';
import DashboardHeader from '@/components/dashboard/DashboardHeader';
import KPICard from '@/components/dashboard/KPICard';
import ActivityFeed from '@/components/dashboard/ActivityFeed';
import AlertBanner from '@/components/dashboard/AlertBanner';
import { analyticsApi } from '@/lib/analytics-api';
import { dashboardApi, type DashboardHomeResponse } from '@/lib/dashboard-api';
import { getErrorMessage } from '@/lib/api';
import type { DashboardData, AgentMetrics, DateRange } from '@/types/analytics';

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

// ── Helper Functions ──────────────────────────────────────────────────

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

// ── Dashboard Page ────────────────────────────────────────────────────

export default function DashboardPage() {
  const { user } = useAuth();
  const [data, setData] = useState<DashboardData | null>(null);
  const [agentData, setAgentData] = useState<AgentMetrics[]>([]);
  const [dateRange, setDateRange] = useState<Partial<DateRange>>({});
  const [datePreset, setDatePreset] = useState('30d');
  const [isRefreshing, setIsRefreshing] = useState(false);

  // ── NEW: Dashboard Home data (anomalies + activity feed) ─────────
  const [homeData, setHomeData] = useState<DashboardHomeResponse | null>(null);

  // ── Fetch Dashboard Data (existing — old analytics endpoint) ──────

  const fetchDashboard = useCallback(async () => {
    try {
      setIsRefreshing(true);
      const dashboardData = await analyticsApi.getDashboard(dateRange);
      setData(dashboardData);
    } catch (error) {
      console.error('Failed to fetch dashboard data:', error);
      toast.error(getErrorMessage(error));
    } finally {
      setIsRefreshing(false);
    }
  }, [dateRange]);

  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  // ── Fetch NEW Dashboard Home data (anomalies + activity) ──────────

  useEffect(() => {
    dashboardApi
      .getHome(30)
      .then((home) => setHomeData(home))
      .catch(() => {
        // Silent fail — new features are supplementary
      });
  }, []);

  // ── Fetch Agent Data (separate endpoint) ──────────────────────────

  useEffect(() => {
    analyticsApi
      .getAgents(50, dateRange)
      .then((agents) => setAgentData(agents))
      .catch(() => {
        // Silent fail — agent data is secondary
      });
  }, [dateRange]);

  // ── Handle Date Change ────────────────────────────────────────────

  const handleDateChange = useCallback((range: { start_date: string; end_date: string }) => {
    setDateRange(range);
    const today = new Date().toISOString().split('T')[0];
    const sevenDaysAgo = new Date(Date.now() - 7 * 86400000).toISOString().split('T')[0];
    const thirtyDaysAgo = new Date(Date.now() - 30 * 86400000).toISOString().split('T')[0];

    if (range.start_date === today) setDatePreset('today');
    else if (range.start_date === sevenDaysAgo) setDatePreset('7d');
    else if (range.start_date === thirtyDaysAgo) setDatePreset('30d');
    else setDatePreset('custom');
  }, []);

  // ── Render ─────────────────────────────────────────────────────────

  return (
    <div className="space-y-6">
      {/* Welcome Card */}
      <WelcomeCard
        userName={user?.full_name}
        companyName={user?.company_name}
        industry="Support"
        variantCount={data?.summary.resolved ?? 0}
        resolutionRate={data ? formatPercent(data.summary.resolution_rate) : '0%'}
      />

      {/* Header */}
      <DashboardHeader
        title="Performance Overview"
        subtitle="Key metrics for your support team"
        datePreset={datePreset}
        onDateChange={handleDateChange}
        onRefresh={fetchDashboard}
        isRefreshing={isRefreshing}
      />

      {/* ── Alert Banners (NEW — W16D1) ───────────────────────────── */}
      {homeData?.anomalies && homeData.anomalies.length > 0 && (
        <AlertBanner anomalies={homeData.anomalies} />
      )}

      {/* ── KPI Cards Row 1: Primary Metrics ────────────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
        <KPICard
          title="Total Tickets"
          value={data ? formatNumber(data.summary.total_tickets) : '—'}
          subtitle="All time in range"
          icon={Icons.tickets}
          variant="default"
          isLoading={!data}
        />
        <KPICard
          title="Open Tickets"
          value={data ? formatNumber(data.summary.open + data.summary.in_progress) : '—'}
          subtitle={`${data ? formatNumber(data.summary.in_progress) : '—'} in progress`}
          icon={Icons.open}
          variant="info"
          isLoading={!data}
        />
        <KPICard
          title="Resolved"
          value={data ? formatNumber(data.summary.resolved) : '—'}
          subtitle={`${data ? formatPercent(data.summary.resolution_rate) : '—'} rate`}
          icon={Icons.resolved}
          variant="success"
          isLoading={!data}
        />
        <KPICard
          title="Avg Response"
          value={data ? formatHours(data.summary.avg_first_response_time_hours) : '—'}
          subtitle="First response time"
          icon={Icons.responseTime}
          variant={data && data.summary.avg_first_response_time_hours > 2 ? 'warning' : 'default'}
          isLoading={!data}
        />
        <KPICard
          title="Resolution Rate"
          value={data ? formatPercent(data.summary.resolution_rate) : '—'}
          subtitle="Tickets resolved successfully"
          icon={Icons.resolutionRate}
          variant={data && data.summary.resolution_rate >= 80 ? 'success' : 'warning'}
          isLoading={!data}
        />
        <KPICard
          title="CSAT Score"
          value="—"
          subtitle="Customer satisfaction"
          icon={Icons.csat}
          variant="default"
          isLoading={!data}
        />
      </div>

      {/* ── KPI Cards Row 2: Priority + SLA ───────────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
        <KPICard
          title="Critical"
          value={data ? formatNumber(data.summary.critical) : '—'}
          icon={<span className="w-3 h-3 rounded-full bg-red-500" />}
          variant="danger"
          isLoading={!data}
        />
        <KPICard
          title="High Priority"
          value={data ? formatNumber(data.summary.high) : '—'}
          icon={<span className="w-3 h-3 rounded-full bg-orange-500" />}
          variant="warning"
          isLoading={!data}
        />
        <KPICard
          title="Awaiting Client"
          value={data ? formatNumber(data.summary.awaiting_client) : '—'}
          icon={Icons.open}
          variant="default"
          isLoading={!data}
        />

        <KPICard
          title="Avg Resolution"
          value={data ? formatHours(data.summary.avg_resolution_time_hours) : '—'}
          subtitle="Time to resolve"
          icon={Icons.responseTime}
          variant="default"
          isLoading={!data}
        />
        <KPICard
          title="SLA Breached"
          value={data ? formatNumber(data.sla.breached_count) : '—'}
          subtitle={`of ${data ? formatNumber(data.sla.total_tickets_with_sla) : '—'} tickets`}
          icon={Icons.breached}
          variant={data && data.sla.breached_count > 0 ? 'danger' : 'success'}
          isLoading={!data}
        />
        <KPICard
          title="SLA Compliance"
          value={data ? formatPercent(data.sla.compliance_rate) : '—'}
          subtitle={`${data ? formatNumber(data.sla.approaching_count) : '—'} approaching`}
          icon={Icons.compliance}
          variant={data && data.sla.compliance_rate >= 95 ? 'success' : data && data.sla.compliance_rate >= 80 ? 'warning' : 'danger'}
          isLoading={!data}
        />
      </div>

      {/* ── Row 3: Ticket Trends (full width area chart) ───────────── */}
      {data ? (
        <TrendChart data={data.trend} />
      ) : (
        <div className="rounded-xl bg-[#1A1A1A]/50 border border-white/[0.06] p-6 h-[332px] animate-pulse" />
      )}

      {/* ── Row 4: Category Chart + SLA Chart ──────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {data ? (
          <CategoryChart data={data.by_category} />
        ) : (
          <div className="rounded-xl bg-[#1A1A1A]/50 border border-white/[0.06] p-6 h-[420px] animate-pulse" />
        )}

        {data ? (
          <SLAChart data={data.sla} />
        ) : (
          <div className="rounded-xl bg-[#1A1A1A]/50 border border-white/[0.06] p-6 h-[420px] animate-pulse" />
        )}
      </div>

      {/* ── Row 5: Response Time Distribution ──────────────────────── */}
      <ResponseTimeChart dateRange={dateRange} />

      {/* ── Row 6: Activity Feed + Placeholder (NEW — W16D1) ─────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Activity Feed */}
        <ActivityFeed
          initialEvents={homeData?.activity_feed}
          isLoading={!homeData}
        />

        {/* Placeholder for future widgets */}
        <div className="bg-[#1A1A1A] border border-white/[0.06] rounded-xl flex flex-col items-center justify-center min-h-[320px]">
          <div className="w-12 h-12 rounded-xl bg-white/[0.03] border border-white/[0.06] flex items-center justify-center mb-3">
            <svg className="w-6 h-6 text-zinc-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 3v11.25A2.25 2.25 0 0 0 6 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0 1 18 16.5h-2.25m-7.5 0h7.5m-7.5 0-1 3m8.5-3 1 3m0 0 .5 1.5m-.5-1.5h-9.5m0 0-.5 1.5m.75-9 3-3 2.148 2.148A12.061 12.061 0 0 1 16.5 7.605" />
            </svg>
          </div>
          <p className="text-sm text-zinc-500 font-medium">AI Insights</p>
          <p className="text-xs text-zinc-600 mt-1 text-center max-w-[200px]">
            Intelligent ticket analysis and recommendations coming soon
          </p>
        </div>
      </div>

      {/* ── Row 7: Agent Performance Table ─────────────────────────── */}
      <AgentPerformanceTable data={agentData} />
    </div>
  );
}
