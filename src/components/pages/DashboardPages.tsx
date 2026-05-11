'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useAppStore, type Page } from '@/lib/store';
import { DashboardLayout } from '@/components/dashboard';
import {
  KPICard,
  TrendChart,
  CategoryChart,
  SLAChart,
  AgentPerformanceTable,
  ResponseTimeChart,
  DashboardHeader,
  DateRangeSelector,
} from '@/components/dashboard';
import { analyticsApi } from '@/lib/analytics-api';
import type {
  TicketSummary,
  SLAMetrics,
  TrendPoint,
  CategoryDistribution,
  AgentMetrics,
} from '@/types/analytics';

// ── Sub-page imports ───────────────────────────────────────────────
import AgentsPage from './AgentsPage';
import TicketsPage from './TicketsPage';
import ChannelsPage from './ChannelsPage';
import MonitoringPage from './MonitoringPage';
import BillingPage from './BillingPage';
import KnowledgePage from './KnowledgePage';
import SettingsPage from './SettingsPage';
import VariantsPage from './VariantsPage';

// ── Icons for KPI cards ────────────────────────────────────────────

const TicketIcon = (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 6v.75m0 3v.75m0 3v.75m0 3V18m-9-5.25h5.25M7.5 15h3M3.375 5.25c-.621 0-1.125.504-1.125 1.125v3.026a2.999 2.999 0 0 1 0 5.198v3.026c0 .621.504 1.125 1.125 1.125h17.25c.621 0 1.125-.504 1.125-1.125v-3.026a2.999 2.999 0 0 1 0-5.198V6.375c0-.621-.504-1.125-1.125-1.125H3.375Z" />
  </svg>
);

const ResolutionIcon = (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
  </svg>
);

const ResponseIcon = (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
  </svg>
);

const AgentIcon = (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M15 19.128a9.38 9.38 0 0 0 2.625.372 9.337 9.337 0 0 0 4.121-.952 4.125 4.125 0 0 0-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 0 1 8.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0 1 11.964-3.07M12 6.375a3.375 3.375 0 1 1-6.75 0 3.375 3.375 0 0 1 6.75 0Zm8.25 2.25a2.625 2.625 0 1 1-5.25 0 2.625 2.625 0 0 1 5.25 0Z" />
  </svg>
);

// ── LLM Tier Types & Mock Data ─────────────────────────────────────

interface LLMTier {
  name: string;
  tier: 'light' | 'medium' | 'heavy';
  model: string;
  description: string;
  tasks: string[];
  costPerTicket: number;
  humanCostPerTicket: number;
  savingsPerTicket: number;
  tokensPerQuery: number;
  avgResponseTime: string;
  ticketsProcessed: number;
  accuracy: number;
  quota: number;
}

function getLLMTiers(): LLMTier[] {
  const HUMAN_COST = 12.5; // $20/hr * 37.5min avg
  return [
    {
      name: 'Light LLM',
      tier: 'light',
      model: 'Gemini Flash',
      description: 'For simple queries that follow known patterns',
      tasks: ['FAQ lookups', 'Order status checks', 'Password resets', 'Account info'],
      costPerTicket: 0.002,
      humanCostPerTicket: HUMAN_COST,
      savingsPerTicket: HUMAN_COST - 0.002,
      tokensPerQuery: 500,
      avgResponseTime: '<2s',
      ticketsProcessed: 680,
      accuracy: 95.2,
      quota: 3000,
    },
    {
      name: 'Medium LLM',
      tier: 'medium',
      model: 'Gemini Pro',
      description: 'For complex queries requiring reasoning',
      tasks: ['Troubleshooting', 'Policy decisions', 'Refund processing', 'Multi-step issues'],
      costPerTicket: 0.015,
      humanCostPerTicket: HUMAN_COST,
      savingsPerTicket: HUMAN_COST - 0.015,
      tokensPerQuery: 2000,
      avgResponseTime: '~5s',
      ticketsProcessed: 342,
      accuracy: 89.7,
      quota: 1500,
    },
    {
      name: 'Heavy LLM',
      tier: 'heavy',
      model: 'Claude 3.5',
      description: 'For critical & VIP queries requiring deep analysis',
      tasks: ['Churn prevention', 'Fraud analysis', 'Escalations', 'VIP support'],
      costPerTicket: 0.05,
      humanCostPerTicket: HUMAN_COST,
      savingsPerTicket: HUMAN_COST - 0.05,
      tokensPerQuery: 5000,
      avgResponseTime: '~8s',
      ticketsProcessed: 48,
      accuracy: 93.1,
      quota: 500,
    },
  ];
}

// ── DashboardHomePage ───────────────────────────────────────────────

/**
 * Main dashboard view with KPIs, charts, and agent performance table.
 * Fetches data from the analytics API (with mock fallback) and passes
 * it to all child chart components.
 */
function DashboardHomePage() {
  const [datePreset, setDatePreset] = useState('30d');
  const [dateRange, setDateRange] = useState<{
    start_date: string;
    end_date: string;
  }>({
    start_date: new Date(Date.now() - 30 * 86400000).toISOString().split('T')[0],
    end_date: new Date().toISOString().split('T')[0],
  });
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Data states
  const [summary, setSummary] = useState<TicketSummary | null>(null);
  const [sla, setSla] = useState<SLAMetrics | null>(null);
  const [trends, setTrends] = useState<TrendPoint[]>([]);
  const [categories, setCategories] = useState<CategoryDistribution[]>([]);
  const [agents, setAgents] = useState<AgentMetrics[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Fetch all dashboard data
  const fetchDashboardData = useCallback(async (range?: { start_date: string; end_date: string }) => {
    setIsLoading(true);
    try {
      const [summaryRes, slaRes, trendsRes, catsRes, agentsRes] = await Promise.all([
        analyticsApi.getSummary(range),
        analyticsApi.getSLA(range),
        analyticsApi.getTrends('day', range),
        analyticsApi.getCategories(range),
        analyticsApi.getAgents(50, range),
      ]);

      setSummary(summaryRes.summary);
      setSla(slaRes.sla);
      setTrends(trendsRes.trend);
      setCategories(catsRes.categories);
      setAgents(agentsRes);
    } catch (error) {
      console.error('Failed to fetch dashboard data:', error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Initial load
  useEffect(() => {
    fetchDashboardData(dateRange);
  }, [dateRange, fetchDashboardData]);

  // Handle date range change
  const handleDateChange = useCallback((range: { start_date: string; end_date: string }) => {
    setDateRange(range);
  }, []);

  // Handle refresh
  const handleRefresh = useCallback(async () => {
    setIsRefreshing(true);
    await fetchDashboardData(dateRange);
    setIsRefreshing(false);
  }, [fetchDashboardData, dateRange]);

  return (
    <div className="space-y-6">
      <DashboardHeader
        title="Dashboard"
        subtitle="Overview of your support operations"
        datePreset={datePreset}
        onDateChange={(range) => {
          setDatePreset('custom');
          handleDateChange(range);
        }}
        onRefresh={handleRefresh}
        isRefreshing={isRefreshing}
      />

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard
          title="Total Tickets"
          value={summary ? summary.total_tickets.toLocaleString() : '—'}
          icon={TicketIcon}
          trend={summary ? { value: 12.5, label: 'vs last period' } : undefined}
          variant="default"
          isLoading={isLoading}
        />
        <KPICard
          title="Resolution Rate"
          value={summary ? `${summary.resolution_rate}%` : '—'}
          icon={ResolutionIcon}
          trend={summary ? { value: 3.2, label: 'vs last period' } : undefined}
          variant="success"
          isLoading={isLoading}
        />
        <KPICard
          title="Avg Response"
          value={summary ? `${Math.round(summary.avg_first_response_time_hours * 60)} min` : '—'}
          icon={ResponseIcon}
          trend={summary ? { value: -15.0, label: 'faster is better' } : undefined}
          variant="info"
          isLoading={isLoading}
        />
        <KPICard
          title="Active Agents"
          value={agents.length > 0 ? String(agents.length) : '—'}
          icon={AgentIcon}
          trend={agents.length > 0 ? { value: 2, label: 'agents online' } : undefined}
          variant="warning"
          isLoading={isLoading}
        />
      </div>

      {/* ── AI Model Tiers & Cost Intelligence ── */}
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center">
            <svg className="w-4 h-4 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09ZM18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 0 0-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 0 0 2.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 0 0 2.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 0 0-2.456 2.456ZM16.894 20.567 16.5 21.75l-.394-1.183a2.25 2.25 0 0 0-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 0 0 1.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 0 0 1.423 1.423l1.183.394-1.183.394a2.25 2.25 0 0 0-1.423 1.423Z" />
            </svg>
          </div>
          <div>
            <h2 className="text-white text-lg font-semibold">AI Model Tiers & Cost Intelligence</h2>
            <p className="text-zinc-500 text-xs">3-tier LLM routing with real-time cost tracking</p>
          </div>
        </div>

        {/* Tier Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {getLLMTiers().map((t) => {
            const pct = Math.min(100, Math.round((t.ticketsProcessed / t.quota) * 100));
            const tierColors = {
              light: {
                accent: 'border-zinc-500/30',
                badge: 'bg-zinc-500/10 text-zinc-300',
                bar: 'bg-zinc-400',
                barBg: 'bg-zinc-500/10',
              },
              medium: {
                accent: 'border-sky-500/30',
                badge: 'bg-sky-500/10 text-sky-300',
                bar: 'bg-sky-400',
                barBg: 'bg-sky-500/10',
              },
              heavy: {
                accent: 'border-orange-500/30',
                badge: 'bg-orange-500/10 text-orange-300',
                bar: 'bg-orange-400',
                barBg: 'bg-orange-500/10',
              },
            };
            const c = tierColors[t.tier];
            return (
              <div
                key={t.tier}
                className={`rounded-xl bg-[#1A1A1A] border border-white/[0.06] ${c.accent} p-5 space-y-4`}
              >
                {/* Header */}
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${c.badge}`}>{t.tier.toUpperCase()}</span>
                      <span className="text-white font-semibold text-sm">{t.name}</span>
                    </div>
                    <p className="text-zinc-500 text-xs mt-1">{t.model} · {t.description}</p>
                  </div>
                  <div className="text-right">
                    <div className="text-emerald-400 text-lg font-bold">${t.savingsPerTicket.toFixed(3)}</div>
                    <div className="text-zinc-500 text-[10px]">saved/ticket</div>
                  </div>
                </div>

                {/* Tasks */}
                <div className="flex flex-wrap gap-1.5">
                  {t.tasks.map((task) => (
                    <span key={task} className="text-[10px] text-zinc-400 bg-white/[0.04] px-2 py-0.5 rounded-md">
                      {task}
                    </span>
                  ))}
                </div>

                {/* Metrics Grid */}
                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div className="space-y-0.5">
                    <div className="text-zinc-500">AI Cost</div>
                    <div className="text-white font-medium">${t.costPerTicket.toFixed(3)}/ticket</div>
                  </div>
                  <div className="space-y-0.5">
                    <div className="text-zinc-500">Human Cost</div>
                    <div className="text-zinc-300 font-medium">${t.humanCostPerTicket.toFixed(2)}/ticket</div>
                  </div>
                  <div className="space-y-0.5">
                    <div className="text-zinc-500">Tokens</div>
                    <div className="text-zinc-300 font-medium">~{t.tokensPerQuery.toLocaleString()}</div>
                  </div>
                  <div className="space-y-0.5">
                    <div className="text-zinc-500">Response</div>
                    <div className="text-zinc-300 font-medium">{t.avgResponseTime}</div>
                  </div>
                </div>

                {/* Quota Progress */}
                <div className="space-y-1.5">
                  <div className="flex justify-between text-xs">
                    <span className="text-zinc-400">Quota used</span>
                    <span className="text-zinc-300">{t.ticketsProcessed.toLocaleString()} / {t.quota.toLocaleString()}</span>
                  </div>
                  <div className={`h-1.5 rounded-full ${c.barBg} overflow-hidden`}>
                    <div
                      className={`h-full rounded-full ${c.bar} transition-all`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <div className="flex justify-between text-[10px]">
                    <span className="text-zinc-500">{pct}% used</span>
                    <span className="text-emerald-400">{t.accuracy}% accuracy</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Cost Savings Summary KPI Row */}
        {(() => {
          const tiers = getLLMTiers();
          const totalTickets = tiers.reduce((s, t) => s + t.ticketsProcessed, 0);
          const totalSavings = tiers.reduce((s, t) => s + t.savingsPerTicket * t.ticketsProcessed, 0);
          const totalHumanCost = tiers.reduce((s, t) => s + t.humanCostPerTicket * t.ticketsProcessed, 0);
          const totalAiCost = tiers.reduce((s, t) => s + t.costPerTicket * t.ticketsProcessed, 0);
          const weightedAccuracy = tiers.reduce((s, t) => s + t.accuracy * t.ticketsProcessed, 0) / totalTickets;
          const savingsPerTicket = totalSavings / totalTickets;

          return (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <KPICard
                title="Savings This Month"
                value={`$${totalSavings.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
                icon={
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v12m-3-2.818.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
                  </svg>
                }
                subtitle={`${totalTickets.toLocaleString()} tickets resolved by AI`}
                variant="success"
              />
              <KPICard
                title="Savings Per Ticket"
                value={`$${savingsPerTicket.toFixed(2)}`}
                icon={
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 0 1 3 19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V8.625ZM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V4.125Z" />
                  </svg>
                }
                subtitle="vs $12.50 human equivalent"
                variant="success"
              />
              <KPICard
                title="Human Equiv. Cost"
                value={`$${totalHumanCost.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
                icon={
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15 19.128a9.38 9.38 0 0 0 2.625.372 9.337 9.337 0 0 0 4.121-.952 4.125 4.125 0 0 0-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 0 1 8.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0 1 11.964-3.07M12 6.375a3.375 3.375 0 1 1-6.75 0 3.375 3.375 0 0 1 6.75 0Zm8.25 2.25a2.625 2.625 0 1 1-5.25 0 2.625 2.625 0 0 1 5.25 0Z" />
                  </svg>
                }
                subtitle={`Actual AI cost: $${totalAiCost.toFixed(2)}`}
                variant="warning"
              />
              <KPICard
                title="AI Accuracy"
                value={`${weightedAccuracy.toFixed(1)}%`}
                icon={
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
                  </svg>
                }
                subtitle="Weighted across all tiers"
                variant="info"
              />
            </div>
          );
        })()}

        {/* Ticket Quota & Usage */}
        {(() => {
          const tiers = getLLMTiers();
          const totalProcessed = tiers.reduce((s, t) => s + t.ticketsProcessed, 0);
          const totalQuota = tiers.reduce((s, t) => s + t.quota, 0);
          const overallPct = Math.min(100, Math.round((totalProcessed / totalQuota) * 100));

          return (
            <div className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-5 space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <svg className="w-4 h-4 text-zinc-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 0 1 3 19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V8.625ZM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V4.125Z" />
                  </svg>
                  <h3 className="text-white text-sm font-semibold">Ticket Quota & Usage</h3>
                </div>
                <span className="text-zinc-400 text-xs">{totalProcessed.toLocaleString()} / {totalQuota.toLocaleString()} tickets used this month</span>
              </div>

              {/* Overall Progress */}
              <div className="space-y-1.5">
                <div className="h-2.5 rounded-full bg-white/[0.04] overflow-hidden">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-emerald-400 transition-all"
                    style={{ width: `${overallPct}%` }}
                  />
                </div>
                <div className="flex justify-between text-[10px] text-zinc-500">
                  <span>{overallPct}% of monthly quota used</span>
                  <span>{(totalQuota - totalProcessed).toLocaleString()} remaining</span>
                </div>
              </div>

              {/* Per-Tier Breakdown */}
              <div className="grid grid-cols-3 gap-3 pt-2 border-t border-white/[0.06]">
                {tiers.map((t) => {
                  const tierPct = totalProcessed > 0 ? Math.round((t.ticketsProcessed / totalProcessed) * 100) : 0;
                  const tierColors = {
                    light: 'text-zinc-400',
                    medium: 'text-sky-400',
                    heavy: 'text-orange-400',
                  };
                  return (
                    <div key={t.tier} className="text-center space-y-1">
                      <div className={`text-xs font-medium ${tierColors[t.tier]}`}>{t.name}</div>
                      <div className="text-white text-lg font-bold">{tierPct}%</div>
                      <div className="text-zinc-500 text-[10px]">{t.ticketsProcessed.toLocaleString()} tickets</div>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })()}
      </div>

      {/* Charts Row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <TrendChart data={trends} />
        <CategoryChart data={categories} />
      </div>

      {/* Charts Row 2 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {sla ? <SLAChart data={sla} /> : (
          <div className="rounded-xl bg-[#1A1A1A]/50 border border-white/[0.06] p-6 h-[340px] flex items-center justify-center text-zinc-600 text-sm animate-pulse">
            Loading SLA data...
          </div>
        )}
        <ResponseTimeChart dateRange={dateRange} />
      </div>

      {/* Agent Performance */}
      <AgentPerformanceTable data={agents} />
    </div>
  );
}

// ── Page Router ─────────────────────────────────────────────────────

const SUB_PAGE_MAP: Partial<Record<Page, React.ComponentType>> = {
  'dashboard-agents': AgentsPage,
  'dashboard-tickets': TicketsPage,
  'dashboard-channels': ChannelsPage,
  'dashboard-monitoring': MonitoringPage,
  'dashboard-billing': BillingPage,
  'dashboard-knowledge': KnowledgePage,
  'dashboard-settings': SettingsPage,
  'dashboard-variants': VariantsPage,
};

/**
 * DashboardPageRenderer — wraps content in DashboardLayout and routes
 * to the correct sub-page based on Zustand store state.
 */
export default function DashboardPageRenderer() {
  const currentPage = useAppStore((s) => s.currentPage);

  const SubPageComponent = SUB_PAGE_MAP[currentPage];
  const content = SubPageComponent ? <SubPageComponent /> : <DashboardHomePage />;

  return <DashboardLayout>{content}</DashboardLayout>;
}
