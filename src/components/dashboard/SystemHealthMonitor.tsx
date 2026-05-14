/**
 * PARWA SystemHealthMonitor
 *
 * Real-time system health dashboard showing service statuses,
 * queue metrics, and active alerts. All data updates via Socket.io.
 */

'use client';

import React, { useEffect } from 'react';
import {
  useSystemHealthStore,
  ServiceHealth,
  ServiceName,
  HealthStatus,
} from '@/lib/system-health-store';
import {
  SERVICE_LABELS,
  HEALTH_STATUS_LABELS,
  HEALTH_STATUS_COLORS,
  HEALTH_STATUS_DOT_COLORS,
} from '@/lib/system-health-store';

// ── Status Dot ────────────────────────────────────────────────────────

function StatusDot({ status }: { status: HealthStatus }) {
  const dotColors: Record<HealthStatus, string> = {
    healthy: 'bg-emerald-400 shadow-emerald-400/50',
    degraded: 'bg-amber-400 shadow-amber-400/50',
    down: 'bg-red-400 shadow-red-400/50 animate-pulse',
  };

  return (
    <span
      className={`w-2 h-2 rounded-full ${dotColors[status]} shadow-sm`}
      title={HEALTH_STATUS_LABELS[status]}
    />
  );
}

// ── Service Row ───────────────────────────────────────────────────────

function ServiceRow({ service }: { service: ServiceHealth }) {
  const latencyColor =
    service.latencyMs < 100
      ? 'text-emerald-400'
      : service.latencyMs < 500
        ? 'text-amber-400'
        : 'text-red-400';

  return (
    <div className="flex items-center gap-3 py-1.5">
      <StatusDot status={service.status} />
      <span className="text-xs text-zinc-300 flex-1">
        {SERVICE_LABELS[service.name] || service.name}
      </span>
      <span className={`text-[10px] font-mono ${latencyColor}`}>
        {service.latencyMs}ms
      </span>
      <span className="text-[10px] text-zinc-600 w-12 text-right">
        {service.uptime}%
      </span>
    </div>
  );
}

// ── SystemHealthMonitor Component ─────────────────────────────────────

export function SystemHealthMonitor() {
  const overallStatus = useSystemHealthStore((s) => s.overallStatus);
  const services = useSystemHealthStore((s) => s.services);
  const queues = useSystemHealthStore((s) => s.queues);
  const alerts = useSystemHealthStore((s) => s.getActiveAlerts());
  const isMaintenance = useSystemHealthStore((s) => s.isMaintenance);
  const maintenanceMessage = useSystemHealthStore((s) => s.maintenanceMessage);
  const lastUpdated = useSystemHealthStore((s) => s.lastUpdated);
  const fetchSystemHealth = useSystemHealthStore((s) => s.fetchSystemHealth);
  const acknowledgeAlert = useSystemHealthStore((s) => s.acknowledgeAlert);

  // Fetch initial health data on mount
  useEffect(() => {
    fetchSystemHealth();
  }, [fetchSystemHealth]);

  const overallColorMap: Record<HealthStatus, string> = {
    healthy: 'text-emerald-400',
    degraded: 'text-amber-400',
    down: 'text-red-400',
  };

  return (
    <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.06]">
        <div className="flex items-center gap-2">
          <StatusDot status={overallStatus} />
          <h3 className="text-sm font-semibold text-white">System Health</h3>
        </div>
        <span className={`text-xs font-medium ${overallColorMap[overallStatus]}`}>
          {HEALTH_STATUS_LABELS[overallStatus]}
        </span>
      </div>

      {/* Maintenance Banner */}
      {isMaintenance && (
        <div className="px-4 py-2 bg-amber-500/10 border-b border-amber-500/20 flex items-center gap-2">
          <svg className="w-4 h-4 text-amber-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M11.42 15.17 17.25 21A2.652 2.652 0 0 0 21 17.25l-5.877-5.877M11.42 15.17l2.496-3.03c.317-.384.74-.626 1.208-.766M11.42 15.17l-4.655 5.653a2.548 2.548 0 1 1-3.586-3.586l6.837-5.63m5.108-.233c.55-.164 1.163-.188 1.743-.14a4.5 4.5 0 0 0 4.486-6.336l-3.276 3.277a3.004 3.004 0 0 1-2.25-2.25l3.276-3.276a4.5 4.5 0 0 0-6.336 4.486c.091 1.076-.071 2.264-.904 2.95l-.102.085m-1.745 1.437L5.909 7.5H4.5L2.25 3.75l1.5-1.5L7.5 4.5v1.409l4.26 4.26m-1.745 1.437 1.745-1.437m6.615 8.206L15.75 15.75M4.867 19.125h.008v.008h-.008v-.008Z" />
          </svg>
          <p className="text-xs text-amber-300">
            {maintenanceMessage || 'System is under maintenance'}
          </p>
        </div>
      )}

      {/* Services */}
      {services.length > 0 && (
        <div className="px-4 py-3 border-b border-white/[0.04]">
          <p className="text-[10px] text-zinc-600 uppercase tracking-wider mb-2">Services</p>
          <div className="space-y-0.5">
            {services.map((service) => (
              <ServiceRow key={service.name} service={service} />
            ))}
          </div>
        </div>
      )}

      {/* Queue Metrics */}
      {queues.length > 0 && (
        <div className="px-4 py-3 border-b border-white/[0.04]">
          <p className="text-[10px] text-zinc-600 uppercase tracking-wider mb-2">Queue Metrics</p>
          <div className="space-y-1.5">
            {queues.map((queue) => (
              <div key={queue.queueName} className="flex items-center gap-2">
                <span className="text-xs text-zinc-400 flex-1 truncate">{queue.queueName}</span>
                <div className="flex items-center gap-3 text-[10px]">
                  <span className="text-amber-400">{queue.pending} pending</span>
                  <span className="text-sky-400">{queue.active} active</span>
                  <span className="text-emerald-400">{queue.completed} done</span>
                  {queue.failed > 0 && (
                    <span className="text-red-400">{queue.failed} failed</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Active Alerts */}
      {alerts.length > 0 && (
        <div className="px-4 py-3">
          <p className="text-[10px] text-zinc-600 uppercase tracking-wider mb-2">Active Alerts</p>
          <div className="space-y-1.5">
            {alerts.slice(0, 5).map((alert) => (
              <div
                key={alert.id}
                className="flex items-start gap-2 p-2 rounded-lg bg-white/[0.02] border border-white/[0.04]"
              >
                <span className={`w-1.5 h-1.5 rounded-full mt-1.5 shrink-0 ${
                  alert.type === 'error' ? 'bg-red-400' : alert.type === 'warning' ? 'bg-amber-400' : 'bg-zinc-400'
                }`} />
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-zinc-300">{alert.title}</p>
                  {alert.message && (
                    <p className="text-[10px] text-zinc-500 mt-0.5 truncate">{alert.message}</p>
                  )}
                </div>
                <button
                  onClick={() => acknowledgeAlert(alert.id)}
                  className="text-[10px] text-zinc-600 hover:text-zinc-300 transition-colors shrink-0"
                  title="Acknowledge"
                >
                  Dismiss
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Last Updated */}
      {lastUpdated && (
        <div className="px-4 py-2 border-t border-white/[0.04]">
          <p className="text-[10px] text-zinc-600">
            Last updated: {new Date(lastUpdated).toLocaleTimeString()}
          </p>
        </div>
      )}
    </div>
  );
}

export default SystemHealthMonitor;
