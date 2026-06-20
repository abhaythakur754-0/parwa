'use client';

import { useJarvisStatus } from '@/hooks/useJarvisStatus';
import { useEffect, useState } from 'react';

function formatUptime(seconds: number): string {
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (d > 0) return `${d}d ${h}h ${m}m`;
  return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

function statusColor(status: string): { text: string; bg: string; border: string; glow: string } {
  switch (status?.toUpperCase()) {
    case 'OPTIMAL':
      return { text: 'text-jarvis-green', bg: 'bg-green-900/20', border: 'border-green-500/30', glow: 'shadow-[0_0_30px_rgba(0,255,136,0.15)]' };
    case 'DEGRADED':
      return { text: 'text-jarvis-yellow', bg: 'bg-yellow-900/20', border: 'border-yellow-500/30', glow: 'shadow-[0_0_30px_rgba(245,158,11,0.15)]' };
    case 'CRITICAL':
      return { text: 'text-jarvis-red', bg: 'bg-red-900/20', border: 'border-red-500/30', glow: 'shadow-[0_0_30px_rgba(239,68,68,0.2)]' };
    default:
      return { text: 'text-jarvis-muted', bg: 'bg-gray-900/20', border: 'border-gray-500/30', glow: '' };
  }
}

function modeColor(mode: string): string {
  switch (mode?.toUpperCase()) {
    case 'SHADOW': return 'jarvis-badge-cyan';
    case 'SUPERVISED': return 'jarvis-badge-yellow';
    case 'GRADUATED': return 'jarvis-badge-green';
    default: return 'jarvis-badge';
  }
}

function modeDescription(mode: string): string {
  switch (mode?.toUpperCase()) {
    case 'SHADOW': return 'Observing all actions without executing';
    case 'SUPERVISED': return 'Acting with human approval required';
    case 'GRADUATED': return 'Fully autonomous operation';
    default: return 'Unknown mode';
  }
}

export default function SystemStatusBar() {
  const { data: status, isLoading, error } = useJarvisStatus();
  const [uptime, setUptime] = useState(0);

  useEffect(() => {
    if (status?.uptime_seconds) {
      setUptime(status.uptime_seconds);
    }
  }, [status?.uptime_seconds]);

  useEffect(() => {
    const interval = setInterval(() => {
      setUptime((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  if (isLoading) {
    return (
      <div className="jarvis-card animate-pulse">
        <div className="skeleton h-4 w-48 rounded mb-3" />
        <div className="skeleton h-3 w-32 rounded" />
      </div>
    );
  }

  if (error || !status) {
    return (
      <div className="jarvis-card border-jarvis-red/30">
        <div className="flex items-center gap-2 text-jarvis-red">
          <span>⚠</span>
          <span className="text-sm">Unable to reach JARVIS backend</span>
        </div>
        <p className="text-xs text-jarvis-muted mt-1">{error?.message || 'Connection refused'}</p>
      </div>
    );
  }

  const sc = statusColor(status.system_status || 'OPTIMAL');
  const mc = modeColor(status.mode || 'SHADOW');

  return (
    <div className={`jarvis-card ${sc.bg} ${sc.border} ${sc.glow}`}>
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <span className={`text-2xl ${sc.text} font-bold tracking-wider`}>
              {(status.system_status || 'OPTIMAL').toUpperCase()}
            </span>
            {status.system_status?.toUpperCase() === 'CRITICAL' && (
              <span className="inline-flex w-2 h-2 rounded-full bg-jarvis-red animate-pulse" />
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className={`jarvis-badge ${mc}`}>
              MODE: {((status.mode || 'SHADOW') as string).toUpperCase()}
            </span>
            <span className="text-[10px] text-jarvis-muted">{modeDescription(status.mode || 'SHADOW')}</span>
          </div>
        </div>

        <div className="text-right space-y-1">
          <div className="text-[10px] text-jarvis-muted tracking-widest uppercase">System Uptime</div>
          <div className={`text-xl font-bold tabular-nums ${sc.text} glow-green`}>
            {formatUptime(uptime)}
          </div>
          {status.active_agents !== undefined && (
            <div className="text-[10px] text-jarvis-muted">
              {status.active_agents} agent{status.active_agents !== 1 ? 's' : ''} active
            </div>
          )}
        </div>
      </div>

      {/* Status details row */}
      {status.last_heartbeat && (
        <div className="mt-3 pt-3 border-t border-jarvis-border/50 flex items-center gap-2 text-[10px] text-jarvis-muted">
          <span className="inline-flex w-1.5 h-1.5 rounded-full bg-jarvis-green animate-pulse" />
          <span>Last heartbeat: {new Date(status.last_heartbeat).toLocaleTimeString()}</span>
        </div>
      )}
    </div>
  );
}