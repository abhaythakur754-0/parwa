/**
 * PARWA Dashboard Real-time Widgets
 *
 * Real-time dashboard widgets for ticket metrics.
 * Shows live updates for open tickets, SLA status, agent load, etc.
 *
 * Day 7 — Real-time Updates & Dashboard Integration
 */

'use client';

import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { cn } from '@/lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useSocket } from '@/contexts/SocketContext';
import { useTicketRealtime } from './useTicketRealtime';

// ── Types ─────────────────────────────────────────────────────────────────

interface WidgetMetric {
  value: number;
  change?: number;
  changeDirection?: 'up' | 'down' | 'neutral';
  trend?: number[];
}

interface DashboardMetrics {
  openTickets: WidgetMetric;
  resolvedToday: WidgetMetric;
  avgResponseTime: WidgetMetric;
  slaAtRisk: WidgetMetric;
  escalated: WidgetMetric;
  aiHandled: WidgetMetric;
  pendingApprovals: WidgetMetric;
  activeAgents: WidgetMetric;
}

interface RealtimeWidgetProps {
  title: string;
  metric: WidgetMetric;
  icon: React.ReactNode;
  format?: 'number' | 'duration' | 'percent';
  trend?: 'good' | 'bad' | 'neutral';
  className?: string;
  onClick?: () => void;
}

interface DashboardWidgetsProps {
  /** Show all widgets or just summary */
  variant?: 'full' | 'compact' | 'summary';
  /** Refresh interval for polling fallback (ms) */
  refreshInterval?: number;
  /** Additional CSS classes */
  className?: string;
  /** Callback when widget is clicked */
  onWidgetClick?: (widget: string) => void;
}

// ── Format Helpers ────────────────────────────────────────────────────────

function formatDuration(minutes: number): string {
  if (minutes < 60) return `${Math.round(minutes)}m`;
  const hours = Math.floor(minutes / 60);
  const mins = Math.round(minutes % 60);
  return mins > 0 ? `${hours}h ${mins}m` : `${hours}h`;
}

function formatValue(value: number, format: 'number' | 'duration' | 'percent'): string {
  switch (format) {
    case 'duration':
      return formatDuration(value);
    case 'percent':
      return `${Math.round(value)}%`;
    default:
      return value.toLocaleString();
  }
}

// ── Sparkline Component ───────────────────────────────────────────────────

interface SparklineProps {
  data: number[];
  width?: number;
  height?: number;
  color?: string;
}

function Sparkline({ data, width = 60, height = 24, color = '#3B82F6' }: SparklineProps) {
  if (!data.length) return null;

  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;

  const points = data
    .map((v, i) => {
      const x = (i / (data.length - 1)) * width;
      const y = height - ((v - min) / range) * height;
      return `${x},${y}`;
    })
    .join(' ');

  return (
    <svg width={width} height={height} className="inline-block">
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

// ── Real-time Widget Component ────────────────────────────────────────────

function RealtimeWidget({
  title,
  metric,
  icon,
  format = 'number',
  trend,
  className,
  onClick,
}: RealtimeWidgetProps) {
  const trendColor = trend === 'good' ? 'text-emerald-400' : trend === 'bad' ? 'text-red-400' : 'text-zinc-400';
  const sparklineColor = trend === 'good' ? '#10B981' : trend === 'bad' ? '#EF4444' : '#71717A';

  return (
    <Card
      className={cn(
        'bg-[#1A1A1A] border-white/[0.06] hover:border-white/[0.12] transition-all duration-200',
        onClick && 'cursor-pointer',
        className
      )}
      onClick={onClick}
    >
      <CardContent className="p-4">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-white/[0.03] border border-white/[0.06] flex items-center justify-center text-zinc-400">
              {icon}
            </div>
            <div>
              <p className="text-xs text-zinc-500 font-medium">{title}</p>
              <p className="text-2xl font-semibold text-zinc-100 mt-0.5">
                {formatValue(metric.value, format)}
              </p>
            </div>
          </div>

          {metric.trend && <Sparkline data={metric.trend} color={sparklineColor} />}
        </div>

        {metric.change !== undefined && (
          <div className="flex items-center gap-1 mt-2">
            <span
              className={cn(
                'text-xs font-medium',
                metric.changeDirection === 'up'
                  ? trend === 'good'
                    ? 'text-emerald-400'
                    : 'text-red-400'
                  : metric.changeDirection === 'down'
                  ? trend === 'good'
                    ? 'text-red-400'
                    : 'text-emerald-400'
                  : 'text-zinc-400'
              )}
            >
              {metric.changeDirection === 'up' ? '↑' : metric.changeDirection === 'down' ? '↓' : '→'}{' '}
              {Math.abs(metric.change)}
              {format === 'percent' ? '%' : ''}
            </span>
            <span className="text-xs text-zinc-600">vs last hour</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ── Live Badge Component ───────────────────────────────────────────────────

function LiveBadge({ isConnected }: { isConnected: boolean }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-medium',
        isConnected
          ? 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-400'
          : 'bg-amber-500/10 border border-amber-500/20 text-amber-400'
      )}
    >
      <span className={cn('w-1.5 h-1.5 rounded-full', isConnected ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500')} />
      {isConnected ? 'LIVE' : 'RECONNECTING'}
    </span>
  );
}

// ── Summary Widget ─────────────────────────────────────────────────────────

interface SummaryWidgetProps {
  metrics: DashboardMetrics;
  isConnected: boolean;
  className?: string;
}

function SummaryWidget({ metrics, isConnected, className }: SummaryWidgetProps) {
  return (
    <div
      className={cn(
        'bg-[#1A1A1A] border border-white/[0.06] rounded-xl p-4',
        className
      )}
    >
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-zinc-200">Live Stats</h3>
        <LiveBadge isConnected={isConnected} />
      </div>

      <div className="grid grid-cols-4 gap-4">
        <div className="text-center">
          <p className="text-2xl font-bold text-zinc-100">{metrics.openTickets.value}</p>
          <p className="text-xs text-zinc-500 mt-0.5">Open</p>
        </div>
        <div className="text-center">
          <p className="text-2xl font-bold text-emerald-400">{metrics.resolvedToday.value}</p>
          <p className="text-xs text-zinc-500 mt-0.5">Resolved Today</p>
        </div>
        <div className="text-center">
          <p className="text-2xl font-bold text-amber-400">{metrics.slaAtRisk.value}</p>
          <p className="text-xs text-zinc-500 mt-0.5">SLA at Risk</p>
        </div>
        <div className="text-center">
          <p className="text-2xl font-bold text-red-400">{metrics.escalated.value}</p>
          <p className="text-xs text-zinc-500 mt-0.5">Escalated</p>
        </div>
      </div>
    </div>
  );
}

// ── Main Dashboard Widgets Component ───────────────────────────────────────

export default function DashboardWidgets({
  variant = 'full',
  refreshInterval = 30000,
  className,
  onWidgetClick,
}: DashboardWidgetsProps) {
  const { isConnected, badgeCounts } = useSocket();
  const { newTicketCount, statusChangeCount, escalationCount } = useTicketRealtime();

  // Initialize metrics with default values
  const [metrics, setMetrics] = useState<DashboardMetrics>({
    openTickets: { value: 0, change: 0, changeDirection: 'neutral', trend: [] },
    resolvedToday: { value: 0, change: 0, changeDirection: 'neutral', trend: [] },
    avgResponseTime: { value: 0, change: 0, changeDirection: 'neutral', trend: [] },
    slaAtRisk: { value: 0, change: 0, changeDirection: 'neutral', trend: [] },
    escalated: { value: 0, change: 0, changeDirection: 'neutral', trend: [] },
    aiHandled: { value: 0, change: 0, changeDirection: 'neutral', trend: [] },
    pendingApprovals: { value: 0, change: 0, changeDirection: 'neutral', trend: [] },
    activeAgents: { value: 0, change: 0, changeDirection: 'neutral', trend: [] },
  });

  // Fetch metrics from API
  const fetchMetrics = useCallback(async () => {
    try {
      const response = await fetch('/api/tickets/dashboard-metrics', {
        credentials: 'include',
      });
      if (response.ok) {
        const data = await response.json();
        setMetrics((prev) => ({
          openTickets: { ...prev.openTickets, ...data.openTickets },
          resolvedToday: { ...prev.resolvedToday, ...data.resolvedToday },
          avgResponseTime: { ...prev.avgResponseTime, ...data.avgResponseTime },
          slaAtRisk: { ...prev.slaAtRisk, ...data.slaAtRisk },
          escalated: { ...prev.escalated, ...data.escalated },
          aiHandled: { ...prev.aiHandled, ...data.aiHandled },
          pendingApprovals: { ...prev.pendingApprovals, ...data.pendingApprovals },
          activeAgents: { ...prev.activeAgents, ...data.activeAgents },
        }));
      }
    } catch (error) {
      // Silent fail - use existing metrics
    }
  }, []);

  // Initial fetch and polling
  useEffect(() => {
    fetchMetrics();
    const interval = setInterval(fetchMetrics, refreshInterval);
    return () => clearInterval(interval);
  }, [fetchMetrics, refreshInterval]);

  // Update metrics in real-time based on socket events
  // Use refs to track processed counts to avoid compounding on repeated events
  const processedNewTicketCount = useRef(0);
  const processedEscalationCount = useRef(0);

  useEffect(() => {
    if (newTicketCount > processedNewTicketCount.current) {
      const delta = newTicketCount - processedNewTicketCount.current;
      processedNewTicketCount.current = newTicketCount;
      setMetrics((prev) => ({
        ...prev,
        openTickets: {
          ...prev.openTickets,
          value: prev.openTickets.value + delta,
          change: delta,
          changeDirection: delta > 0 ? 'up' : 'neutral',
        },
      }));
    }
  }, [newTicketCount]);

  useEffect(() => {
    if (escalationCount > processedEscalationCount.current) {
      const delta = escalationCount - processedEscalationCount.current;
      processedEscalationCount.current = escalationCount;
      setMetrics((prev) => ({
        ...prev,
        escalated: {
          ...prev.escalated,
          value: prev.escalated.value + delta,
          change: delta,
          changeDirection: 'up',
        },
      }));
    }
  }, [escalationCount]);

  // Update pending approvals from badge counts
  useEffect(() => {
    setMetrics((prev) => ({
      ...prev,
      pendingApprovals: {
        ...prev.pendingApprovals,
        value: badgeCounts.approvals,
      },
    }));
  }, [badgeCounts.approvals]);

  // Icons
  const icons = {
    openTickets: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M16.5 6v.75m0 3v.75m0 3v.75m0 3V18m-9-5.25h5.25M7.5 15h3M3.375 5.25c-.621 0-1.125.504-1.125 1.125v3.026a2.999 2.999 0 0 1 0 5.198v3.026c0 .621.504 1.125 1.125 1.125h17.25c.621 0 1.125-.504 1.125-1.125v-3.026a2.999 2.999 0 0 1 0-5.198V6.375c0-.621-.504-1.125-1.125-1.125H3.375Z"
        />
      </svg>
    ),
    resolved: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
      </svg>
    ),
    responseTime: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
      </svg>
    ),
    sla: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M12 9v3.75m9-.75a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 3.75h.008v.008H12v-.008Z"
        />
      </svg>
    ),
    escalated: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 0 1 3 19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V8.625ZM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V4.125Z"
        />
      </svg>
    ),
    ai: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M9.75 3.104v5.714a2.25 2.25 0 0 1-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 0 1 4.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0 1 12 15a9.065 9.065 0 0 0-6.23.693L5 14.5m14.8.8 1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0 1 12 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5"
        />
      </svg>
    ),
    approvals: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M9 12.75 11.25 15 15 9.75M21 12c0 1.268-.63 2.39-1.593 3.068a3.745 3.745 0 0 1-1.043 3.296 3.745 3.745 0 0 1-3.296 1.043A3.745 3.745 0 0 1 12 21c-1.268 0-2.39-.63-3.068-1.593a3.746 3.746 0 0 1-3.296-1.043 3.745 3.745 0 0 1-1.043-3.296A3.745 3.745 0 0 1 3 12c0-1.268.63-2.39 1.593-3.068a3.745 3.745 0 0 1 1.043-3.296 3.746 3.746 0 0 1 3.296-1.043A3.746 3.746 0 0 1 12 3c1.268 0 2.39.63 3.068 1.593a3.746 3.746 0 0 1 3.296 1.043 3.746 3.746 0 0 1 1.043 3.296A3.745 3.745 0 0 1 21 12Z"
        />
      </svg>
    ),
    agents: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M15 19.128a9.38 9.38 0 0 0 2.625.372 9.337 9.337 0 0 0 4.121-.952 4.125 4.125 0 0 0-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 0 1 8.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0 1 11.964-3.07M12 6.375a3.375 3.375 0 1 1-6.75 0 3.375 3.375 0 0 1 6.75 0Zm8.25 2.25a2.625 2.625 0 1 1-5.25 0 2.625 2.625 0 0 1 5.25 0Z"
        />
      </svg>
    ),
  };

  // Compact variant - just key metrics
  if (variant === 'compact') {
    return (
      <div className={cn('grid grid-cols-2 gap-3', className)}>
        <RealtimeWidget
          title="Open Tickets"
          metric={metrics.openTickets}
          icon={icons.openTickets}
          trend="neutral"
          onClick={() => onWidgetClick?.('openTickets')}
        />
        <RealtimeWidget
          title="SLA at Risk"
          metric={metrics.slaAtRisk}
          icon={icons.sla}
          trend="bad"
          onClick={() => onWidgetClick?.('slaAtRisk')}
        />
      </div>
    );
  }

  // Summary variant - single card with key stats
  if (variant === 'summary') {
    return <SummaryWidget metrics={metrics} isConnected={isConnected} className={className} />;
  }

  // Full variant - all widgets
  return (
    <div className={cn('space-y-4', className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-zinc-200">Real-time Dashboard</h2>
        <LiveBadge isConnected={isConnected} />
      </div>

      {/* Primary Metrics */}
      <div className="grid grid-cols-4 gap-3">
        <RealtimeWidget
          title="Open Tickets"
          metric={metrics.openTickets}
          icon={icons.openTickets}
          trend="neutral"
          onClick={() => onWidgetClick?.('openTickets')}
        />
        <RealtimeWidget
          title="Resolved Today"
          metric={metrics.resolvedToday}
          icon={icons.resolved}
          trend="good"
          onClick={() => onWidgetClick?.('resolvedToday')}
        />
        <RealtimeWidget
          title="Avg Response"
          metric={metrics.avgResponseTime}
          icon={icons.responseTime}
          format="duration"
          trend="good"
          onClick={() => onWidgetClick?.('avgResponseTime')}
        />
        <RealtimeWidget
          title="SLA at Risk"
          metric={metrics.slaAtRisk}
          icon={icons.sla}
          trend="bad"
          onClick={() => onWidgetClick?.('slaAtRisk')}
        />
      </div>

      {/* Secondary Metrics */}
      <div className="grid grid-cols-4 gap-3">
        <RealtimeWidget
          title="Escalated"
          metric={metrics.escalated}
          icon={icons.escalated}
          trend="bad"
          onClick={() => onWidgetClick?.('escalated')}
        />
        <RealtimeWidget
          title="AI Handled"
          metric={metrics.aiHandled}
          icon={icons.ai}
          format="percent"
          trend="good"
          onClick={() => onWidgetClick?.('aiHandled')}
        />
        <RealtimeWidget
          title="Pending Approvals"
          metric={metrics.pendingApprovals}
          icon={icons.approvals}
          trend="neutral"
          onClick={() => onWidgetClick?.('pendingApprovals')}
        />
        <RealtimeWidget
          title="Active Agents"
          metric={metrics.activeAgents}
          icon={icons.agents}
          trend="neutral"
          onClick={() => onWidgetClick?.('activeAgents')}
        />
      </div>
    </div>
  );
}
