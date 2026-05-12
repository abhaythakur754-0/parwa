/**
 * JarvisAwarenessOverview — Dashboard overview of awareness state
 *
 * Shows system health, ticket volume, agent pool, quality/drift scores.
 */

'use client';

import React from 'react';
import { cn } from '@/lib/utils';
import { MetricCard } from './MetricCard';
import type { AwarenessState } from '@/types/jarvis-cc';
import { healthColor, utilizationColor } from '@/hooks/useJarvisCC';

export interface JarvisAwarenessOverviewProps {
  state: AwarenessState | null;
  isLoading?: boolean;
  onRefresh?: () => void;
  className?: string;
}

export function JarvisAwarenessOverview({ state, isLoading, onRefresh, className }: JarvisAwarenessOverviewProps) {
  if (!state) {
    return (
      <div className={cn('flex flex-col items-center justify-center py-12 text-zinc-600', className)}>
        <svg className="w-10 h-10 mb-3 animate-pulse" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09Z" />
        </svg>
        <p className="text-sm">Loading awareness data...</p>
        {onRefresh && (
          <button onClick={onRefresh} className="text-xs text-orange-400 mt-2 hover:underline">
            Refresh now
          </button>
        )}
      </div>
    );
  }

  const healthClass = healthColor(state.system_health);
  const utilClass = utilizationColor(state.agent_pool_utilization);
  const qualityVariant = state.quality_score >= 0.7 ? 'success' : state.quality_score >= 0.5 ? 'warning' : 'danger';
  const driftVariant = state.drift_score > 0.6 ? 'danger' : state.drift_score > 0.3 ? 'warning' : 'success';

  return (
    <div className={cn('space-y-4', className)}>
      {/* System Health Bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={cn('w-2.5 h-2.5 rounded-full', state.system_health === 'healthy' ? 'bg-emerald-400' : state.system_health === 'degraded' ? 'bg-amber-400' : 'bg-red-400')} />
          <span className="text-sm text-zinc-400">System Status:</span>
          <span className={cn('text-sm font-semibold capitalize', healthClass)}>
            {state.system_health || 'Unknown'}
          </span>
        </div>
        {onRefresh && (
          <button
            onClick={onRefresh}
            disabled={isLoading}
            className="text-[10px] text-zinc-500 hover:text-orange-400 transition-colors disabled:opacity-50"
          >
            {isLoading ? 'Refreshing...' : 'Refresh'}
          </button>
        )}
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <MetricCard
          label="Tickets Today"
          value={state.ticket_volume_today}
          subtitle={state.ticket_volume_spike ? 'Spike detected!' : `Avg: ${state.ticket_volume_avg}`}
          variant={state.ticket_volume_spike ? 'warning' : 'default'}
          trend={state.ticket_volume_spike ? 'up' : 'flat'}
          trendValue={state.ticket_volume_spike ? '2x+' : undefined}
        />
        <MetricCard
          label="Quality Score"
          value={`${Math.round(state.quality_score * 100)}%`}
          variant={qualityVariant}
          trend={state.quality_score < 0.7 ? 'down' : 'flat'}
        />
        <MetricCard
          label="Agent Utilization"
          value={`${Math.round(state.agent_pool_utilization * 100)}%`}
          subtitle={`${state.active_agents}/${state.agent_pool_capacity} agents`}
          variant={state.agent_pool_utilization >= 0.95 ? 'danger' : state.agent_pool_utilization >= 0.8 ? 'warning' : 'default'}
        />
        <MetricCard
          label="Drift Score"
          value={`${Math.round(state.drift_score * 100)}%`}
          variant={driftVariant}
          trend={state.drift_score > 0.3 ? 'up' : 'flat'}
        />
      </div>

      {/* Channel Health */}
      {Object.keys(state.channel_health).length > 0 && (
        <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-3">
          <h4 className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-2">Channel Health</h4>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {Object.entries(state.channel_health).map(([channel, health]) => (
              <div key={channel} className="flex items-center gap-2">
                <span className={cn('w-1.5 h-1.5 rounded-full', health === 'healthy' ? 'bg-emerald-400' : health === 'degraded' ? 'bg-amber-400' : 'bg-red-400')} />
                <span className="text-xs text-zinc-400 capitalize">{channel}</span>
                <span className={cn('text-[10px] font-medium capitalize', healthColor(health))}>{health}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent Errors */}
      {state.last_5_errors.length > 0 && (
        <div className="rounded-xl border border-red-500/10 bg-red-500/5 p-3">
          <h4 className="text-xs font-medium text-red-400 uppercase tracking-wider mb-2">Recent Errors</h4>
          <div className="space-y-1">
            {state.last_5_errors.slice(0, 3).map((err, i) => (
              <div key={i} className="flex items-center gap-2 text-xs">
                <span className="text-zinc-600 shrink-0">{err.timestamp ? new Date(err.timestamp).toLocaleTimeString() : '--'}</span>
                <span className="text-red-300 truncate">{err.error}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
