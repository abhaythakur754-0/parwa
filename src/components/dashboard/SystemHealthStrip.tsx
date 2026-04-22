/**
 * PARWA SystemHealthStrip — Day 2 (O1.1)
 *
 * Horizontal health bar showing status of all system services:
 * LLM, Redis, Database, Email, SMS, Chat, Voice.
 * Auto-updates via Socket.io system events.
 * Polls /api/system/status every 30s as fallback.
 */

'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { cn } from '@/lib/utils';
import { get } from '@/lib/api';
import { useSocket } from '@/contexts/SocketContext';

// ── Types ──────────────────────────────────────────────────────────────

interface ServiceStatus {
  status: string;
  latency_ms?: number;
}

interface SystemHealthData {
  status: 'healthy' | 'degraded' | 'down';
  services: Record<string, ServiceStatus>;
  message?: string;
}

const SERVICE_LABELS: Record<string, { label: string; icon: string }> = {
  llm: { label: 'LLM', icon: 'AI' },
  redis: { label: 'Redis', icon: 'DB' },
  postgres: { label: 'Database', icon: 'PG' },
  email: { label: 'Email', icon: 'EM' },
  sms: { label: 'SMS', icon: 'SM' },
  chat: { label: 'Chat', icon: 'CH' },
  voice: { label: 'Voice', icon: 'VO' },
  celery: { label: 'Worker', icon: 'WK' },
  socketio: { label: 'WebSocket', icon: 'WS' },
};

// ── Component ──────────────────────────────────────────────────────────

export default function SystemHealthStrip() {
  const { isConnected, systemStatus } = useSocket();
  const [healthData, setHealthData] = useState<SystemHealthData | null>(null);
  const [isExpanded, setIsExpanded] = useState(false);
  const [isPolling, setIsPolling] = useState(false);

  const fetchHealth = useCallback(async () => {
    try {
      setIsPolling(true);
      const data = await get<SystemHealthData>('/api/system/status');
      setHealthData(data);
    } catch {
      // API not available — use Socket.io data
    } finally {
      setIsPolling(false);
    }
  }, []);

  // Initial fetch + 30s polling
  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 30000);
    return () => clearInterval(interval);
  }, [fetchHealth]);

  // Derive effective status
  const effectiveStatus = isConnected ? systemStatus.status : (healthData?.status || 'degraded');
  const services = healthData?.services || {};

  const hasIssues = effectiveStatus !== 'healthy';
  const serviceEntries = Object.entries(SERVICE_LABELS);

  return (
    <div className={cn(
      'rounded-xl border overflow-hidden transition-all duration-300',
      hasIssues
        ? 'bg-red-500/[0.04] border-red-500/15'
        : 'bg-[#1A1A1A] border-white/[0.06]'
    )}>
      {/* Compact bar */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between px-4 py-2.5 hover:bg-white/[0.02] transition-colors"
      >
        <div className="flex items-center gap-3">
          {/* Overall status dot */}
          <div className="flex items-center gap-1.5">
            <div className={cn(
              'w-2 h-2 rounded-full',
              effectiveStatus === 'healthy' ? 'bg-emerald-400'
              : effectiveStatus === 'degraded' ? 'bg-amber-400 animate-pulse'
              : 'bg-red-400 animate-pulse'
            )} />
            <span className={cn(
              'text-[11px] font-medium',
              effectiveStatus === 'healthy' ? 'text-emerald-400'
              : effectiveStatus === 'degraded' ? 'text-amber-400'
              : 'text-red-400'
            )}>
              {effectiveStatus === 'healthy' ? 'All Systems Operational' : hasIssues ? 'System Issues Detected' : 'Checking...'}
            </span>
          </div>

          {/* Service dots */}
          <div className="hidden sm:flex items-center gap-1.5 ml-2">
            {serviceEntries.slice(0, 7).map(([key, { label }]) => {
              const svc = services[key];
              const status = svc?.status || 'unknown';
              return (
                <div
                  key={key}
                  className="flex items-center gap-1"
                  title={`${label}: ${status}`}
                >
                  <div className={cn(
                    'w-1.5 h-1.5 rounded-full',
                    status === 'healthy' || status === 'ok' ? 'bg-emerald-400'
                    : status === 'degraded' || status === 'warning' ? 'bg-amber-400'
                    : status === 'down' || status === 'error' ? 'bg-red-400'
                    : 'bg-zinc-600'
                  )} />
                  <span className="text-[9px] text-zinc-600">{label}</span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Expand toggle */}
        <svg
          className={cn('w-3.5 h-3.5 text-zinc-500 transition-transform duration-200', isExpanded && 'rotate-180')}
          fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
        </svg>
      </button>

      {/* Expanded detail */}
      {isExpanded && (
        <div className="px-4 py-3 border-t border-white/[0.04]">
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-5 gap-2">
            {serviceEntries.map(([key, { label, icon }]) => {
              const svc = services[key];
              const status = svc?.status || 'unknown';
              const latency = svc?.latency_ms;

              return (
                <div
                  key={key}
                  className="flex items-center gap-2.5 px-3 py-2 rounded-lg bg-white/[0.02] border border-white/[0.04]"
                >
                  <div className={cn(
                    'w-2 h-2 rounded-full shrink-0',
                    status === 'healthy' || status === 'ok' ? 'bg-emerald-400'
                    : status === 'degraded' || status === 'warning' ? 'bg-amber-400'
                    : status === 'down' || status === 'error' ? 'bg-red-400'
                    : 'bg-zinc-600'
                  )} />
                  <div className="flex-1 min-w-0">
                    <p className="text-xs text-zinc-300 font-medium">{label}</p>
                    <p className="text-[10px] text-zinc-600">
                      {status === 'healthy' || status === 'ok' ? 'Healthy'
                        : status === 'degraded' || status === 'warning' ? 'Degraded'
                        : status === 'down' || status === 'error' ? 'Down'
                        : 'Unknown'}
                      {latency != null && ` · ${latency}ms`}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
          {healthData?.message && (
            <p className="text-[11px] text-zinc-500 mt-2">{healthData.message}</p>
          )}
        </div>
      )}
    </div>
  );
}
