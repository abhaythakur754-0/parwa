/**
 * Monitoring Page (/dashboard/monitoring) — Phase 5 Upgrade
 *
 * Real-time system health and performance monitoring using Jarvis awareness data.
 */

'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { cn } from '@/lib/utils';
import { MetricCard } from '@/components/jarvis-cc/MetricCard';
import { JarvisAwarenessOverview } from '@/components/jarvis-cc/JarvisAwarenessOverview';
import { JarvisAwarenessFeed } from '@/components/jarvis-cc/JarvisAwarenessFeed';
import { ccAwarenessApi, ccAlertApi, ccSessionApi } from '@/lib/jarvis-cc-api';
import type { AwarenessState, ProactiveAlert } from '@/types/jarvis-cc';

// ── Types ───────────────────────────────────────────────────────────

interface MonitoringMetric {
  label: string;
  value: string;
  status: 'healthy' | 'degraded' | 'unhealthy';
}

// ── Monitoring Page ─────────────────────────────────────────────────

export default function MonitoringPage() {
  const [awarenessState, setAwarenessState] = useState<AwarenessState | null>(null);
  const [alerts, setAlerts] = useState<ProactiveAlert[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'overview' | 'alerts' | 'performance'>('overview');

  // Initialize session
  useEffect(() => {
    const init = async () => {
      try {
        // Try existing session first
        const savedId = localStorage.getItem('jarvis_cc_session_id');
        if (savedId) {
          setSessionId(savedId);
        } else {
          const session = await ccSessionApi.create();
          if (session?.id) {
            setSessionId(session.id);
            localStorage.setItem('jarvis_cc_session_id', session.id);
          }
        }
      } catch {
        // Session creation may fail if backend is not running
      }
    };
    init();
  }, []);

  const fetchData = useCallback(async () => {
    if (!sessionId) {
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    try {
      const [snapshotResult, alertsResult] = await Promise.allSettled([
        ccAwarenessApi.snapshot(sessionId),
        ccAlertApi.list(sessionId, { limit: 50 }),
      ]);
      if (snapshotResult.status === 'fulfilled' && snapshotResult.value) {
        setAwarenessState(snapshotResult.value.state);
      }
      if (alertsResult.status === 'fulfilled' && alertsResult.value) {
        setAlerts(alertsResult.value.alerts);
      }
    } catch {
      setError('Failed to fetch monitoring data');
    } finally {
      setIsLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    fetchData();
    // Auto-refresh every 30s
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const handleAlertAction = async (alertId: string, action: 'acknowledge' | 'dismiss' | 'resolve') => {
    if (!sessionId) return;
    try {
      const apiFn = action === 'acknowledge' ? ccAlertApi.acknowledge
        : action === 'dismiss' ? ccAlertApi.dismiss
        : ccAlertApi.resolve;
      await apiFn(sessionId, { alert_id: alertId });
      await fetchData();
    } catch {
      // Silent fail
    }
  };

  const triggerTick = async () => {
    if (!sessionId) return;
    try {
      await ccAwarenessApi.tick({ session_id: sessionId, tick_type: 'manual' });
      await fetchData();
    } catch {
      // Silent fail
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between pb-4 border-b border-white/[0.06]">
        <div>
          <h1 className="text-xl font-bold text-white">Monitoring</h1>
          <p className="text-sm text-zinc-500 mt-0.5">
            Real-time system health and performance monitoring
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={triggerTick}
            disabled={isLoading}
            className="text-xs px-3 py-1.5 rounded-lg bg-white/[0.04] text-zinc-400 hover:text-white hover:bg-white/[0.08] transition-colors disabled:opacity-50"
          >
            {isLoading ? 'Loading...' : 'Refresh'}
          </button>
          <a
            href="/dashboard/jarvis"
            className="text-xs px-3 py-1.5 rounded-lg bg-gradient-to-r from-orange-500 to-amber-400 text-white font-medium shadow-lg shadow-orange-500/20 hover:shadow-orange-500/30 transition-all"
          >
            Open Jarvis CC
          </a>
        </div>
      </div>

      {/* Tab navigation */}
      <div className="flex items-center gap-1 bg-[#1A1A1A] rounded-lg p-1 w-fit">
        {(['overview', 'alerts', 'performance'] as const).map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={cn(
              'text-xs px-3 py-1.5 rounded-md transition-colors capitalize',
              activeTab === tab
                ? 'bg-white/10 text-white'
                : 'text-zinc-500 hover:text-zinc-300'
            )}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Overview Tab */}
      {activeTab === 'overview' && (
        <JarvisAwarenessOverview
          state={awarenessState}
          isLoading={isLoading}
          onRefresh={triggerTick}
        />
      )}

      {/* Alerts Tab */}
      {activeTab === 'alerts' && (
        <div className="max-w-2xl">
          <JarvisAwarenessFeed
            alerts={alerts}
            onAcknowledge={(id) => handleAlertAction(id, 'acknowledge')}
            onDismiss={(id) => handleAlertAction(id, 'dismiss')}
            onResolve={(id) => handleAlertAction(id, 'resolve')}
          />
        </div>
      )}

      {/* Performance Tab */}
      {activeTab === 'performance' && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <MetricCard
              label="System Health"
              value={awarenessState?.system_health ? awarenessState.system_health.charAt(0).toUpperCase() + awarenessState.system_health.slice(1) : '--'}
              variant={awarenessState?.system_health === 'healthy' ? 'success' : awarenessState?.system_health === 'degraded' ? 'warning' : 'danger'}
            />
            <MetricCard
              label="Quality Score"
              value={awarenessState ? `${Math.round(awarenessState.quality_score * 100)}%` : '--'}
              variant={awarenessState ? (awarenessState.quality_score >= 0.7 ? 'success' : awarenessState.quality_score >= 0.5 ? 'warning' : 'danger') : 'default'}
            />
            <MetricCard
              label="Drift Score"
              value={awarenessState ? `${Math.round(awarenessState.drift_score * 100)}%` : '--'}
              variant={awarenessState ? (awarenessState.drift_score <= 0.3 ? 'success' : awarenessState.drift_score <= 0.6 ? 'warning' : 'danger') : 'default'}
            />
            <MetricCard
              label="Active Alerts"
              value={alerts.filter(a => a.status === 'active').length}
              variant={alerts.some(a => a.severity === 'critical' || a.severity === 'emergency') ? 'danger' : 'default'}
            />
          </div>

          {/* Agent Pool Details */}
          {awarenessState && (
            <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-4">
              <h3 className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-3">Agent Pool Performance</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <span className="text-zinc-600 text-xs">Active Agents</span>
                  <p className="text-lg font-bold text-white">{awarenessState.active_agents}</p>
                </div>
                <div>
                  <span className="text-zinc-600 text-xs">Pool Capacity</span>
                  <p className="text-lg font-bold text-white">{awarenessState.agent_pool_capacity}</p>
                </div>
                <div>
                  <span className="text-zinc-600 text-xs">Utilization</span>
                  <p className={cn(
                    'text-lg font-bold',
                    awarenessState.agent_pool_utilization >= 0.9 ? 'text-red-400' :
                    awarenessState.agent_pool_utilization >= 0.8 ? 'text-amber-400' : 'text-emerald-400'
                  )}>
                    {Math.round(awarenessState.agent_pool_utilization * 100)}%
                  </p>
                </div>
                <div>
                  <span className="text-zinc-600 text-xs">Ticket Volume</span>
                  <p className="text-lg font-bold text-white">
                    {awarenessState.ticket_volume_today}
                    {awarenessState.ticket_volume_spike && (
                      <span className="text-amber-400 text-xs ml-1">SPIKE</span>
                    )}
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Plan & Subscription */}
          {awarenessState && (
            <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-4">
              <h3 className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-3">Subscription & Usage</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <span className="text-zinc-600 text-xs">Current Plan</span>
                  <p className="text-sm font-semibold text-white capitalize">{awarenessState.current_plan || '--'}</p>
                </div>
                <div>
                  <span className="text-zinc-600 text-xs">Plan Usage Today</span>
                  <p className="text-sm font-semibold text-white">
                    {awarenessState.plan_usage_today !== null ? `${Math.round(awarenessState.plan_usage_today * 100)}%` : '--'}
                  </p>
                </div>
                <div>
                  <span className="text-zinc-600 text-xs">Subscription</span>
                  <p className="text-sm font-semibold text-white capitalize">{awarenessState.subscription_status || '--'}</p>
                </div>
                <div>
                  <span className="text-zinc-600 text-xs">Days Until Renewal</span>
                  <p className={cn(
                    'text-sm font-semibold',
                    awarenessState.days_until_renewal !== null && awarenessState.days_until_renewal <= 7
                      ? 'text-amber-400' : 'text-white'
                  )}>
                    {awarenessState.days_until_renewal !== null ? awarenessState.days_until_renewal : '--'}
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* No backend message */}
      {!isLoading && !awarenessState && (
        <div className="flex flex-col items-center justify-center py-20 bg-[#1A1A1A] rounded-xl border border-white/[0.06]">
          <div className="w-12 h-12 rounded-xl bg-orange-500/10 flex items-center justify-center mb-4">
            <svg className="w-6 h-6 text-orange-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="m3.75 13.5 10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75Z" />
            </svg>
          </div>
          <h3 className="text-lg font-medium text-white mb-2">Monitoring Data</h3>
          <p className="text-sm text-zinc-500 mb-6 text-center max-w-sm">
            Start a Jarvis CC session to initialize awareness monitoring. The backend collects system health, agent pool, quality, and drift data every 30 seconds.
          </p>
          <a
            href="/dashboard/jarvis"
            className="text-xs px-4 py-2 rounded-lg bg-gradient-to-r from-orange-500 to-amber-400 text-white font-medium shadow-lg shadow-orange-500/20 hover:shadow-orange-500/30 transition-all"
          >
            Start Jarvis CC
          </a>
        </div>
      )}
    </div>
  );
}
