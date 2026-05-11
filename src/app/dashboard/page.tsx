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
import { analyticsApi } from '@/lib/analytics-api';
import { get, getErrorMessage } from '@/lib/api';
import type { DashboardData, AgentMetrics, DateRange } from '@/types/analytics';

// ── Inline Types for AI/Cost/Sentiment APIs ───────────────────────────

interface VariantInstance {
  id: string;
  name: string;
  variant_type: string;
  status: string;
  channel_assignment: string;
  capacity_config: { max_concurrent: number };
  current_load: number;
  accuracy_rate: number;
  avg_latency_ms: number;
  cost_per_query: number;
  technique_tier: number;
  model: string;
}

interface ROISnapshot {
  tickets_ai_resolved: number;
  tickets_human_resolved: number;
  avg_ai_cost: number;
  avg_human_cost: number;
  total_savings: number;
  savings_percentage: number;
  ai_accuracy_pct: number;
  automation_rate: number;
}

interface CostBudget {
  total_budget: number;
  used_budget: number;
  remaining_budget: number;
  tokens_used: number;
  estimated_cost: number;
}

interface SentimentOverview {
  avg_frustration_score: number;
  emotion_distribution: Record<string, number>;
  escalation_count: number;
  total_analyzed: number;
  positive_ratio: number;
  negative_ratio: number;
}

// ── API fetch state type ──────────────────────────────────────────────

type FetchState<T> =
  | { status: 'loading'; data: null }
  | { status: 'error'; data: null }
  | { status: 'success'; data: T };

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
  savings: (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18.75a60.07 60.07 0 0 1 15.797 2.101c.727.198 1.453-.342 1.453-1.096V18.75M3.75 4.5v.75A.75.75 0 0 1 3 6h-.75m0 0v-.375c0-.621.504-1.125 1.125-1.125H20.25M2.25 6v9m18-10.5v.75c0 .414.336.75.75.75h.75m-1.5-1.5h.375c.621 0 1.125.504 1.125 1.125v9.75c0 .621-.504 1.125-1.125 1.125h-.375m1.5-1.5H21a.75.75 0 0 0-.75.75v.75m0 0H3.75m0 0h-.375a1.125 1.125 0 0 1-1.125-1.125V15m1.5 1.5v-.75A.75.75 0 0 0 3 15h-.75M15 10.5a3 3 0 1 1-6 0 3 3 0 0 1 6 0Zm3 0h.008v.008H18V10.5Zm-12 0h.008v.008H6V10.5Z" />
    </svg>
  ),
  robot: (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 3v1.5M4.5 8.25H3m18 0h-1.5M4.5 12H3m18 0h-1.5m-15 3.75H3m18 0h-1.5M8.25 19.5V21M12 3v1.5m0 15V21m3.75-18v1.5m0 15V21m-9-1.5h10.5a2.25 2.25 0 0 0 2.25-2.25V6.75a2.25 2.25 0 0 0-2.25-2.25H6.75A2.25 2.25 0 0 0 4.5 6.75v10.5a2.25 2.25 0 0 0 2.25 2.25Zm.75-12h9v9h-9v-9Z" />
    </svg>
  ),
  accuracy: (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75m-3-7.036A11.959 11.959 0 0 1 3.598 6 11.99 11.99 0 0 0 3 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285Z" />
    </svg>
  ),
  sentiment: (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M15.182 15.182a4.5 4.5 0 0 1-6.364 0M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0ZM9.75 9.75c0 .414-.168.75-.375.75S9 10.164 9 9.75 9.168 9 9.375 9s.375.336.375.75Zm-.375 0h.008v.015h-.008V9.75Zm5.625 0c0 .414-.168.75-.375.75s-.375-.336-.375-.75.168-.75.375-.75.375.336.375.75Zm-.375 0h.008v.015h-.008V9.75Z" />
    </svg>
  ),
  variant: (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M21 7.5l-2.25-1.313M21 7.5v2.25m0-2.25l-2.25 1.313M3 7.5l2.25-1.313M3 7.5l2.25 1.313M3 7.5v2.25m9 3l2.25-1.313M12 12.75l-2.25-1.313M12 12.75V15m0 6.75l2.25-1.313M12 21.75V19.5m0 2.25l-2.25-1.313m0-16.875L12 2.25l2.25 1.313M21 14.25v2.25l-2.25 1.313m-13.5 0L3 16.5v-2.25" />
    </svg>
  ),
  escalation: (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m0-10.036A11.959 11.959 0 0 1 3.598 6 11.99 11.99 0 0 0 3 9.75c0 5.592 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.57-.598-3.75h-.152c-3.196 0-6.1-1.249-8.25-3.286Zm0 13.036h.008v.008H12v-.008Z" />
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

function formatCurrency(n: number): string {
  if (n >= 1) return `$${n.toFixed(2)}`;
  return `$${n.toFixed(4)}`;
}

// ── Variant type badge colors ─────────────────────────────────────────

const variantTypeColors: Record<string, { bg: string; text: string }> = {
  mini_parwa: { bg: 'bg-emerald-500/10', text: 'text-emerald-400' },
  parwa: { bg: 'bg-sky-500/10', text: 'text-sky-400' },
  parwa_high: { bg: 'bg-amber-500/10', text: 'text-amber-400' },
};

const statusColors: Record<string, { dot: string; text: string }> = {
  active: { dot: 'bg-emerald-400', text: 'text-emerald-400' },
  idle: { dot: 'bg-zinc-400', text: 'text-zinc-400' },
  error: { dot: 'bg-red-400', text: 'text-red-400' },
  paused: { dot: 'bg-amber-400', text: 'text-amber-400' },
};

// ── Skeleton Card ─────────────────────────────────────────────────────

function SkeletonCard({ className = '' }: { className?: string }) {
  return (
    <div className={`rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-5 animate-pulse ${className}`}>
      <div className="flex items-start justify-between">
        <div className="space-y-2 flex-1">
          <div className="h-3 w-20 bg-white/[0.06] rounded" />
          <div className="h-7 w-28 bg-white/[0.06] rounded" />
          <div className="h-3 w-16 bg-white/[0.06] rounded" />
        </div>
        <div className="w-10 h-10 rounded-lg bg-white/[0.06]" />
      </div>
    </div>
  );
}

function SkeletonSection({ rows = 2, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
      {Array.from({ length: rows * cols }).map((_, i) => (
        <SkeletonCard key={i} />
      ))}
    </div>
  );
}

// ── Dashboard Page ────────────────────────────────────────────────────

export default function DashboardPage() {
  const { user } = useAuth();
  const [data, setData] = useState<DashboardData | null>(null);
  const [agentData, setAgentData] = useState<AgentMetrics[]>([]);
  const [dateRange, setDateRange] = useState<Partial<DateRange>>({});
  const [datePreset, setDatePreset] = useState('30d');
  const [isRefreshing, setIsRefreshing] = useState(false);

  // ── AI / Cost / Sentiment state ──────────────────────────────────
  const [roiState, setRoiState] = useState<FetchState<ROISnapshot>>({ status: 'loading', data: null });
  const [costBudgetState, setCostBudgetState] = useState<FetchState<CostBudget>>({ status: 'loading', data: null });
  const [variantsState, setVariantsState] = useState<FetchState<VariantInstance[]>>({ status: 'loading', data: null });
  const [sentimentState, setSentimentState] = useState<FetchState<SentimentOverview>>({ status: 'loading', data: null });

  // ── Fetch Dashboard Data ──────────────────────────────────────────

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

  // ── Fetch Agent Data (separate endpoint) ──────────────────────────

  useEffect(() => {
    analyticsApi
      .getAgents(50, dateRange)
      .then((agents) => setAgentData(agents))
      .catch(() => {
        // Silent fail — agent data is secondary
      });
  }, [dateRange]);

  // ── Fetch Cost Budget + ROI ───────────────────────────────────────

  useEffect(() => {
    get<CostBudget>('/api/ai/cost/budget')
      .then((budget) => setCostBudgetState({ status: 'success', data: budget }))
      .catch(() => setCostBudgetState({ status: 'error', data: null }));

    get<ROISnapshot>('/api/v1/admin/roi')
      .then((roi) => setRoiState({ status: 'success', data: roi }))
      .catch(() => setRoiState({ status: 'error', data: null }));
  }, []);

  // ── Fetch Variant Instances ───────────────────────────────────────

  useEffect(() => {
    get<VariantInstance[]>('/api/ai/instances')
      .then((variants) => setVariantsState({ status: 'success', data: variants }))
      .catch(() => setVariantsState({ status: 'error', data: null }));
  }, []);

  // ── Fetch Sentiment Overview ──────────────────────────────────────

  useEffect(() => {
    get<SentimentOverview>('/api/v1/admin/sentiment')
      .then((sentiment) => setSentimentState({ status: 'success', data: sentiment }))
      .catch(() => setSentimentState({ status: 'error', data: null }));
  }, []);

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

  // ── Derived ROI data ──────────────────────────────────────────────

  const hasRoiData = roiState.status === 'success' && roiState.data;
  const hasBudgetData = costBudgetState.status === 'success' && costBudgetState.data;
  const hasCostSectionData = hasRoiData || hasBudgetData;
  const isCostLoading = roiState.status === 'loading' || costBudgetState.status === 'loading';

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

      {/* ── Cost Savings / ROI Section ──────────────────────────────── */}
      {isCostLoading ? (
        <div className="space-y-4">
          <h2 className="text-sm font-medium text-zinc-500 uppercase tracking-wider">AI Cost Savings & ROI</h2>
          <SkeletonSection rows={1} cols={4} />
        </div>
      ) : hasCostSectionData ? (
        <div className="space-y-4">
          <h2 className="text-sm font-medium text-zinc-500 uppercase tracking-wider">AI Cost Savings & ROI</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
            {/* Total Savings */}
            <KPICard
              title="Total Savings"
              value={hasRoiData ? formatCurrency(roiState.data!.total_savings) : '—'}
              subtitle={hasRoiData ? `${formatPercent(roiState.data!.savings_percentage)} saved` : 'ROI data unavailable'}
              icon={Icons.savings}
              variant="success"
            />
            {/* AI vs Human Cost */}
            <KPICard
              title="AI vs Human Cost"
              value={hasRoiData ? `${formatCurrency(roiState.data!.avg_ai_cost)} vs ${formatCurrency(roiState.data!.avg_human_cost)}` : '—'}
              subtitle={hasRoiData ? `${formatNumber(roiState.data!.tickets_ai_resolved)} AI · ${formatNumber(roiState.data!.tickets_human_resolved)} human` : '—'}
              icon={Icons.robot}
              variant="info"
            />
            {/* Automation Rate */}
            <KPICard
              title="Automation Rate"
              value={hasRoiData ? formatPercent(roiState.data!.automation_rate) : '—'}
              subtitle="Tickets auto-resolved"
              icon={Icons.responseTime}
              variant={hasRoiData && roiState.data!.automation_rate >= 60 ? 'success' : 'default'}
            />
            {/* AI Accuracy */}
            <KPICard
              title="AI Accuracy"
              value={hasRoiData ? formatPercent(roiState.data!.ai_accuracy_pct) : '—'}
              subtitle={hasBudgetData ? `${formatNumber(costBudgetState.data!.tokens_used)} tokens used` : '—'}
              icon={Icons.accuracy}
              variant={hasRoiData && roiState.data!.ai_accuracy_pct >= 90 ? 'success' : 'warning'}
            />
          </div>
          {/* Budget bar */}
          {hasBudgetData && costBudgetState.data!.total_budget > 0 && (
            <div className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-5">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-medium text-zinc-500 uppercase tracking-wider">Token Budget Usage</span>
                <span className="text-xs text-zinc-400">
                  {formatCurrency(costBudgetState.data!.estimated_cost)} / {formatCurrency(costBudgetState.data!.total_budget)}
                </span>
              </div>
              <div className="h-2 bg-white/[0.06] rounded-full overflow-hidden">
                <div
                  className="h-full bg-emerald-500/80 rounded-full transition-all duration-500"
                  style={{
                    width: `${Math.min(100, (costBudgetState.data!.used_budget / costBudgetState.data!.total_budget) * 100)}%`,
                  }}
                />
              </div>
              <div className="flex items-center justify-between mt-2">
                <span className="text-xs text-zinc-500">
                  {((costBudgetState.data!.used_budget / costBudgetState.data!.total_budget) * 100).toFixed(1)}% used
                </span>
                <span className="text-xs text-zinc-500">
                  {formatCurrency(costBudgetState.data!.remaining_budget)} remaining
                </span>
              </div>
            </div>
          )}
        </div>
      ) : (
        /* Error / no backend — show connect message */
        <div className="space-y-4">
          <h2 className="text-sm font-medium text-zinc-500 uppercase tracking-wider">AI Cost Savings & ROI</h2>
          <div className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-8 flex flex-col items-center justify-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-white/[0.05] flex items-center justify-center text-zinc-600">
              {Icons.savings}
            </div>
            <p className="text-sm text-zinc-500 text-center">Connect backend to view cost savings & ROI data</p>
          </div>
        </div>
      )}

      {/* ── Active Variants Status ─────────────────────────────────── */}
      {variantsState.status === 'loading' ? (
        <div className="space-y-4">
          <h2 className="text-sm font-medium text-zinc-500 uppercase tracking-wider">Active Variants</h2>
          <SkeletonSection rows={1} cols={3} />
        </div>
      ) : variantsState.status === 'success' && variantsState.data && variantsState.data.length > 0 ? (
        <div className="space-y-4">
          <h2 className="text-sm font-medium text-zinc-500 uppercase tracking-wider">
            Active Variants
            <span className="ml-2 text-xs text-zinc-600 normal-case tracking-normal">
              ({variantsState.data.length} running)
            </span>
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
            {variantsState.data.map((variant) => {
              const typeColor = variantTypeColors[variant.variant_type] ?? { bg: 'bg-zinc-500/10', text: 'text-zinc-400' };
              const statusColor = statusColors[variant.status] ?? statusColors.idle;
              const loadPct = Math.min(100, variant.current_load);
              const loadColor = loadPct >= 90 ? 'bg-red-500/80' : loadPct >= 70 ? 'bg-amber-500/80' : 'bg-emerald-500/80';

              return (
                <div
                  key={variant.id}
                  className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-5 transition-all duration-300 hover:shadow-lg hover:shadow-black/20 hover:border-white/[0.1]"
                >
                  {/* Header: name + status */}
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <h3 className="text-sm font-semibold text-white truncate">{variant.name}</h3>
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-semibold uppercase tracking-wider ${typeColor.bg} ${typeColor.text}`}>
                          {variant.variant_type.replace('_', ' ')}
                        </span>
                      </div>
                      <div className="flex items-center gap-1.5 text-xs text-zinc-500">
                        <span className={`w-1.5 h-1.5 rounded-full ${statusColor.dot}`} />
                        <span className={statusColor.text}>{variant.status}</span>
                        <span className="text-zinc-700">·</span>
                        <span>{variant.channel_assignment}</span>
                      </div>
                    </div>
                    <div className="w-9 h-9 rounded-lg bg-white/[0.05] flex items-center justify-center text-zinc-500 shrink-0">
                      {Icons.variant}
                    </div>
                  </div>

                  {/* Metrics grid */}
                  <div className="grid grid-cols-2 gap-3 mb-4">
                    <div>
                      <p className="text-[10px] text-zinc-600 uppercase tracking-wider mb-0.5">Load</p>
                      <p className="text-sm font-semibold text-white tabular-nums">
                        {loadPct}%
                        <span className="text-[10px] text-zinc-600 ml-1">/ {variant.capacity_config.max_concurrent}</span>
                      </p>
                    </div>
                    <div>
                      <p className="text-[10px] text-zinc-600 uppercase tracking-wider mb-0.5">Quality</p>
                      <p className="text-sm font-semibold text-white tabular-nums">{formatPercent(variant.accuracy_rate)}</p>
                    </div>
                    <div>
                      <p className="text-[10px] text-zinc-600 uppercase tracking-wider mb-0.5">Latency</p>
                      <p className="text-sm font-semibold text-white tabular-nums">{variant.avg_latency_ms}ms</p>
                    </div>
                    <div>
                      <p className="text-[10px] text-zinc-600 uppercase tracking-wider mb-0.5">Cost/Q</p>
                      <p className="text-sm font-semibold text-white tabular-nums">{formatCurrency(variant.cost_per_query)}</p>
                    </div>
                  </div>

                  {/* Load bar */}
                  <div className="h-1.5 bg-white/[0.06] rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${loadColor}`}
                      style={{ width: `${loadPct}%` }}
                    />
                  </div>

                  {/* Footer */}
                  <div className="flex items-center justify-between mt-3 pt-3 border-t border-white/[0.04]">
                    <span className="text-[10px] text-zinc-600">Tier {variant.technique_tier}</span>
                    <span className="text-[10px] text-zinc-600 font-mono">{variant.model}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ) : variantsState.status === 'success' && variantsState.data && variantsState.data.length === 0 ? (
        <div className="space-y-4">
          <h2 className="text-sm font-medium text-zinc-500 uppercase tracking-wider">Active Variants</h2>
          <div className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-8 flex flex-col items-center justify-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-white/[0.05] flex items-center justify-center text-zinc-600">
              {Icons.variant}
            </div>
            <p className="text-sm text-zinc-500 text-center">No active variants found</p>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          <h2 className="text-sm font-medium text-zinc-500 uppercase tracking-wider">Active Variants</h2>
          <div className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-8 flex flex-col items-center justify-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-white/[0.05] flex items-center justify-center text-zinc-600">
              {Icons.variant}
            </div>
            <p className="text-sm text-zinc-500 text-center">Connect backend to view active variants</p>
          </div>
        </div>
      )}

      {/* Header */}
      <DashboardHeader
        title="Performance Overview"
        subtitle="Key metrics for your support team"
        datePreset={datePreset}
        onDateChange={handleDateChange}
        onRefresh={fetchDashboard}
        isRefreshing={isRefreshing}
      />

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

      {/* ── Row 5: Response Time Distribution + Sentiment Overview ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ResponseTimeChart dateRange={dateRange} />

        {/* ── Sentiment Overview ──────────────────────────────────── */}
        {sentimentState.status === 'loading' ? (
          <div className="rounded-xl bg-[#1A1A1A]/50 border border-white/[0.06] p-6 h-[420px] animate-pulse" />
        ) : sentimentState.status === 'success' && sentimentState.data ? (
          <div className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-6">
            <div className="flex items-center gap-2 mb-6">
              <div className="w-8 h-8 rounded-lg bg-purple-500/10 flex items-center justify-center text-purple-400">
                {Icons.sentiment}
              </div>
              <div>
                <h3 className="text-sm font-semibold text-white">Sentiment Overview</h3>
                <p className="text-[10px] text-zinc-600">
                  {formatNumber(sentimentState.data.total_analyzed)} tickets analyzed
                </p>
              </div>
            </div>

            {/* KPI Row */}
            <div className="grid grid-cols-3 gap-4 mb-6">
              <div className="space-y-1">
                <p className="text-[10px] text-zinc-600 uppercase tracking-wider">Frustration</p>
                <p className="text-xl font-bold text-white tabular-nums">
                  {sentimentState.data.avg_frustration_score.toFixed(1)}
                  <span className="text-xs text-zinc-600">/10</span>
                </p>
              </div>
              <div className="space-y-1">
                <p className="text-[10px] text-zinc-600 uppercase tracking-wider">Escalations</p>
                <p className="text-xl font-bold text-white tabular-nums">
                  {formatNumber(sentimentState.data.escalation_count)}
                </p>
              </div>
              <div className="space-y-1">
                <p className="text-[10px] text-zinc-600 uppercase tracking-wider">Positive</p>
                <p className="text-xl font-bold tabular-nums text-emerald-400">
                  {formatPercent(sentimentState.data.positive_ratio * 100)}
                </p>
              </div>
            </div>

            {/* Emotion Distribution */}
            <div className="space-y-3">
              <p className="text-[10px] text-zinc-600 uppercase tracking-wider">Emotion Distribution</p>
              {Object.entries(sentimentState.data.emotion_distribution).map(([emotion, pct]) => {
                const emotionColors: Record<string, string> = {
                  joy: 'bg-emerald-500/80',
                  neutral: 'bg-zinc-500/80',
                  frustration: 'bg-amber-500/80',
                  anger: 'bg-red-500/80',
                  sadness: 'bg-blue-500/80',
                  confusion: 'bg-purple-500/80',
                  satisfaction: 'bg-emerald-400/80',
                  anxiety: 'bg-orange-500/80',
                };
                const barColor = emotionColors[emotion.toLowerCase()] ?? 'bg-zinc-500/80';
                const value = typeof pct === 'number' ? pct : 0;

                return (
                  <div key={emotion} className="space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-zinc-400 capitalize">{emotion}</span>
                      <span className="text-xs text-zinc-500 tabular-nums">{value.toFixed(1)}%</span>
                    </div>
                    <div className="h-1.5 bg-white/[0.06] rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${barColor}`}
                        style={{ width: `${Math.min(100, value)}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Negative ratio footer */}
            <div className="flex items-center justify-between mt-5 pt-4 border-t border-white/[0.04]">
              <div className="flex items-center gap-2">
                <div className="w-6 h-6 rounded-md bg-red-500/10 flex items-center justify-center text-red-400">
                  {Icons.escalation}
                </div>
                <span className="text-xs text-zinc-400">Negative ratio</span>
              </div>
              <span className="text-sm font-semibold tabular-nums text-red-400">
                {formatPercent(sentimentState.data.negative_ratio * 100)}
              </span>
            </div>
          </div>
        ) : (
          <div className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-8 flex flex-col items-center justify-center gap-3 min-h-[420px]">
            <div className="w-12 h-12 rounded-xl bg-white/[0.05] flex items-center justify-center text-zinc-600">
              {Icons.sentiment}
            </div>
            <p className="text-sm text-zinc-500 text-center">Connect backend to view sentiment data</p>
          </div>
        )}
      </div>

      {/* ── Row 6: Agent Performance Table ─────────────────────────── */}
      <AgentPerformanceTable data={agentData} />
    </div>
  );
}
