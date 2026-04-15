/**
 * PARWA SystemHealthStrip — Day 2 (O1.1)
 *
 * Horizontal strip at the top of the dashboard showing health of all services:
 * LLM, Redis, PostgreSQL, Email, SMS, Chat, Voice.
 * Auto-updates via Socket.io system.status events.
 * Click any item for details dropdown.
 */

'use client';

import React, { useState } from 'react';
import { useSocket } from '@/lib/socket';

// ── Types ──────────────────────────────────────────────────────────────

interface ServiceHealth {
  name: string;
  status: 'healthy' | 'degraded' | 'down' | 'unknown';
  latency_ms?: number;
  detail?: string;
}

// ── Default services to show ───────────────────────────────────────────

const DEFAULT_SERVICES: ServiceHealth[] = [
  { name: 'LLM', status: 'unknown' },
  { name: 'Redis', status: 'unknown' },
  { name: 'Database', status: 'unknown' },
  { name: 'Email', status: 'unknown' },
  { name: 'SMS', status: 'unknown' },
  { name: 'Chat', status: 'unknown' },
  { name: 'Voice', status: 'unknown' },
];

// ── Icons ──────────────────────────────────────────────────────────────

function StatusIcon({ status }: { status: string }) {
  if (status === 'healthy') {
    return (
      <svg className="w-3.5 h-3.5 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
      </svg>
    );
  }
  if (status === 'degraded') {
    return (
      <svg className="w-3.5 h-3.5 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 3.75h.008v.008H12v-.008Z" />
      </svg>
    );
  }
  return (
    <svg className="w-3.5 h-3.5 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
    </svg>
  );
}

// ── Component ──────────────────────────────────────────────────────────

export default function SystemHealthStrip() {
  const { systemStatus, isConnected } = useSocket();
  const [expandedService, setExpandedService] = useState<string | null>(null);

  // Merge Socket.io status with defaults
  const services: ServiceHealth[] = DEFAULT_SERVICES.map((svc) => {
    if (systemStatus?.services) {
      const key = svc.name.toLowerCase();
      const remote = systemStatus.services[key] || systemStatus.services[svc.name];
      if (remote) {
        return {
          ...svc,
          status: remote.status as ServiceHealth['status'],
          latency_ms: remote.latency_ms,
        };
      }
    }
    // If overall status is healthy and no per-service data, assume healthy when connected
    if (isConnected && systemStatus?.status === 'healthy') {
      return { ...svc, status: 'healthy' };
    }
    return svc;
  });

  const overallStatus = systemStatus?.status || (isConnected ? 'healthy' : 'down');

  return (
    <div className="rounded-xl bg-[#141414] border border-white/[0.06] p-3">
      {/* Header row */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${
            overallStatus === 'healthy' ? 'bg-emerald-400' :
            overallStatus === 'degraded' ? 'bg-amber-400' : 'bg-red-400'
          }`} />
          <span className="text-xs font-medium text-zinc-400">System Health</span>
        </div>
        <span className="text-[11px] text-zinc-600">
          {isConnected ? 'Live' : 'Reconnecting...'}
        </span>
      </div>

      {/* Service indicators */}
      <div className="flex flex-wrap items-center gap-3">
        {services.map((svc) => (
          <button
            key={svc.name}
            onClick={() => setExpandedService(expandedService === svc.name ? null : svc.name)}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium transition-all hover:bg-white/[0.05] ${
              svc.status === 'healthy'
                ? 'text-zinc-300'
                : svc.status === 'degraded'
                  ? 'text-amber-400 bg-amber-500/5'
                  : svc.status === 'down'
                    ? 'text-red-400 bg-red-500/5'
                    : 'text-zinc-600'
            }`}
          >
            <StatusIcon status={svc.status} />
            <span>{svc.name}</span>
            {svc.latency_ms !== undefined && (
              <span className="text-[10px] text-zinc-500 ml-1">
                {svc.latency_ms}ms
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Expanded detail */}
      {expandedService && (
        <div className="mt-2 pt-2 border-t border-white/[0.04]">
          <div className="flex items-center justify-between">
            <span className="text-xs text-zinc-400">
              {services.find(s => s.name === expandedService)?.name}:
              {' '}
              {services.find(s => s.name === expandedService)?.status}
            </span>
            <span className="text-[11px] text-zinc-600">
              {services.find(s => s.name === expandedService)?.latency_ms
                ? `${services.find(s => s.name === expandedService)?.latency_ms}ms response time`
                : 'No latency data'}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
