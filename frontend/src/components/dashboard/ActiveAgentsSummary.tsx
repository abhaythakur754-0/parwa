/**
 * PARWA ActiveAgentsSummary — Day 2 (O1.4)
 *
 * Quick view strip showing active AI agents with:
 * agent name, confidence bar, tickets handled, status dot.
 * Click navigates to agent detail.
 */

'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { cn } from '@/lib/utils';
import { get } from '@/lib/api';

// ── Types ──────────────────────────────────────────────────────────────

interface AgentCard {
  agent_id: string;
  agent_name: string;
  agent_type: 'ai' | 'human';
  status: 'active' | 'idle' | 'paused' | 'offline';
  confidence?: number;
  tickets_assigned: number;
  tickets_resolved: number;
  avg_resolution_time_hours?: number;
  csat_avg?: number;
}

interface AgentDashboardData {
  agents: AgentCard[];
  status_counts: {
    active: number;
    idle: number;
    paused: number;
    offline: number;
  };
}

// ── Component ──────────────────────────────────────────────────────────

export default function ActiveAgentsSummary() {
  const [data, setData] = useState<AgentDashboardData | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchAgents = useCallback(async () => {
    try {
      setIsLoading(true);
      const result = await get<AgentDashboardData>('/api/agents/dashboard');
      setData(result);
    } catch (error) {
      console.error('Failed to fetch agent dashboard:', error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAgents();
  }, [fetchAgents]);

  const statusConfig: Record<string, { color: string; label: string }> = {
    active: { color: 'bg-emerald-400', label: 'Active' },
    idle: { color: 'bg-zinc-500', label: 'Idle' },
    paused: { color: 'bg-amber-400', label: 'Paused' },
    offline: { color: 'bg-red-400', label: 'Offline' },
  };

  if (isLoading) {
    return (
      <div className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-5">
        <div className="flex items-center gap-2 mb-4">
          <div className="w-6 h-6 rounded-md bg-white/[0.06] animate-pulse" />
          <div className="h-4 w-32 bg-white/[0.06] rounded animate-pulse" />
        </div>
        <div className="flex gap-3 overflow-hidden">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="w-40 shrink-0 h-20 bg-white/[0.04] rounded-lg animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (!data || data.agents.length === 0) {
    return (
      <div className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-5">
        <div className="flex items-center gap-2 mb-4">
          <div className="w-6 h-6 rounded-md bg-[#FF7F11]/10 flex items-center justify-center">
            <svg className="w-3.5 h-3.5 text-[#FF7F11]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19.128a9.38 9.38 0 0 0 2.625.372 9.337 9.337 0 0 0 4.121-.952 4.125 4.125 0 0 0-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 0 1 8.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0 1 11.964-3.07M12 6.375a3.375 3.375 0 1 1-6.75 0 3.375 3.375 0 0 1 6.75 0Zm8.25 2.25a2.625 2.625 0 1 1-5.25 0 2.625 2.625 0 0 1 5.25 0Z" />
            </svg>
          </div>
          <h3 className="text-sm font-semibold text-zinc-300">Active Agents</h3>
        </div>
        <div className="flex flex-col items-center justify-center py-6 text-center">
          <p className="text-sm text-zinc-600">No agents configured yet</p>
          <p className="text-xs text-zinc-700 mt-1">Agents will appear here once configured</p>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.06]">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-md bg-[#FF7F11]/10 flex items-center justify-center">
            <svg className="w-3.5 h-3.5 text-[#FF7F11]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19.128a9.38 9.38 0 0 0 2.625.372 9.337 9.337 0 0 0 4.121-.952 4.125 4.125 0 0 0-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 0 1 8.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0 1 11.964-3.07M12 6.375a3.375 3.375 0 1 1-6.75 0 3.375 3.375 0 0 1 6.75 0Zm8.25 2.25a2.625 2.625 0 1 1-5.25 0 2.625 2.625 0 0 1 5.25 0Z" />
            </svg>
          </div>
          <h3 className="text-sm font-semibold text-zinc-300">Active Agents</h3>
          {data.status_counts && (
            <div className="flex items-center gap-2 ml-2">
              <span className="flex items-center gap-1 text-[10px] text-emerald-400">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                {data.status_counts.active}
              </span>
              <span className="flex items-center gap-1 text-[10px] text-zinc-500">
                <span className="w-1.5 h-1.5 rounded-full bg-zinc-500" />
                {data.status_counts.idle}
              </span>
              {data.status_counts.paused > 0 && (
                <span className="flex items-center gap-1 text-[10px] text-amber-400">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                  {data.status_counts.paused}
                </span>
              )}
            </div>
          )}
        </div>
        <a
          href="/dashboard/agents"
          className="text-[11px] text-[#FF7F11] hover:text-[#FF7F11]/80 transition-colors"
        >
          View all
        </a>
      </div>

      {/* Agent cards horizontal scroll */}
      <div className="flex gap-3 p-4 overflow-x-auto scrollbar-thin">
        {data.agents.map(agent => {
          const config = statusConfig[agent.status] || statusConfig.offline;
          return (
            <div
              key={agent.agent_id}
              className="shrink-0 w-48 rounded-lg bg-white/[0.03] border border-white/[0.04] p-3 hover:bg-white/[0.05] transition-colors cursor-pointer group"
            >
              {/* Top: Name + Status */}
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2 min-w-0">
                  <div className={cn('w-2 h-2 rounded-full shrink-0', config.color)} />
                  <span className="text-xs font-medium text-zinc-200 truncate">{agent.agent_name}</span>
                </div>
                {agent.agent_type === 'ai' && (
                  <span className="text-[9px] text-[#FF7F11] bg-[#FF7F11]/10 px-1.5 py-0.5 rounded font-medium">AI</span>
                )}
              </div>

              {/* Confidence bar (AI only) */}
              {agent.agent_type === 'ai' && agent.confidence != null && (
                <div className="mb-2">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[10px] text-zinc-500">Confidence</span>
                    <span className={cn(
                      'text-[10px] font-medium',
                      agent.confidence >= 80 ? 'text-emerald-400'
                      : agent.confidence >= 50 ? 'text-amber-400'
                      : 'text-red-400'
                    )}>
                      {agent.confidence.toFixed(0)}%
                    </span>
                  </div>
                  <div className="h-1.5 bg-white/[0.05] rounded-full overflow-hidden">
                    <div
                      className={cn(
                        'h-full rounded-full transition-all duration-500',
                        agent.confidence >= 80 ? 'bg-emerald-400/60'
                        : agent.confidence >= 50 ? 'bg-amber-400/60'
                        : 'bg-red-400/60'
                      )}
                      style={{ width: `${agent.confidence}%` }}
                    />
                  </div>
                </div>
              )}

              {/* Stats */}
              <div className="flex items-center justify-between text-[10px]">
                <span className="text-zinc-500">
                  <span className="text-zinc-300 font-medium">{agent.tickets_assigned}</span> assigned
                </span>
                <span className="text-zinc-500">
                  <span className="text-zinc-300 font-medium">{agent.tickets_resolved}</span> resolved
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
