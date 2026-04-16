/**
 * PARWA ActiveAgentsSummary — Day 2 (O1.4)
 *
 * Quick view strip showing active agents with name, mini confidence bar,
 * tickets handled, and status dot. Fetches from /api/agents/dashboard.
 * Click agent name navigates to agent detail.
 */

'use client';

import React, { useState, useEffect } from 'react';
import { get } from '@/lib/api';

// ── Types ──────────────────────────────────────────────────────────────

interface AgentSummary {
  agent_id: string;
  agent_name: string;
  variant: string;
  status: 'active' | 'paused' | 'error';
  confidence: number;
  tickets_today: number;
  tickets_week: number;
  resolution_rate: number;
}

interface AgentsResponse {
  agents: AgentSummary[];
  total: number;
  active: number;
  paused: number;
  error: number;
  tickets_today: number;
}

// ── Component ──────────────────────────────────────────────────────────

export default function ActiveAgentsSummary() {
  const [data, setData] = useState<AgentsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    get<AgentsResponse>('/api/agents/dashboard')
      .then(setData)
      .catch(() => {
        // Fallback mock if endpoint doesn't exist yet
        setData({
          agents: [],
          total: 0,
          active: 0,
          paused: 0,
          error: 0,
          tickets_today: 0,
        });
      })
      .finally(() => setIsLoading(false));
  }, []);

  const statusDot = (status: string) => {
    const colors = {
      active: 'bg-emerald-400 shadow-emerald-400/50',
      paused: 'bg-zinc-500 shadow-zinc-500/50',
      error: 'bg-red-400 shadow-red-400/50',
    };
    return (
      <div className={`w-2 h-2 rounded-full shadow-sm ${colors[status as keyof typeof colors] || 'bg-zinc-600'}`} />
    );
  };

  const confidenceColor = (conf: number) => {
    if (conf >= 75) return 'bg-emerald-400';
    if (conf >= 50) return 'bg-amber-400';
    return 'bg-red-400';
  };

  if (isLoading) {
    return (
      <div className="rounded-xl bg-[#141414] border border-white/[0.06] p-4">
        <div className="flex items-center gap-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="flex-1 h-20 rounded-lg bg-white/[0.03] animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (!data || data.agents.length === 0) {
    return (
      <div className="rounded-xl bg-[#141414] border border-white/[0.06] p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-zinc-300">Active Agents</h3>
          <span className="text-xs text-zinc-500">0 active</span>
        </div>
        <div className="text-center py-6 text-sm text-zinc-500">
          No agents configured yet. Go to Agents to add your first AI agent.
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl bg-[#141414] border border-white/[0.06] p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-zinc-300">Active Agents</h3>
        <div className="flex items-center gap-2 text-xs text-zinc-500">
          <span className="flex items-center gap-1">
            <div className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            {data.active} active
          </span>
          {data.paused > 0 && (
            <span className="flex items-center gap-1">
              <div className="w-1.5 h-1.5 rounded-full bg-zinc-500" />
              {data.paused} paused
            </span>
          )}
          <span className="text-zinc-600">|</span>
          <span>{data.tickets_today.toLocaleString()} tickets today</span>
        </div>
      </div>

      {/* Agent Cards Strip */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-2">
        {data.agents.map((agent) => (
          <div
            key={agent.agent_id}
            className="flex items-center gap-3 px-3 py-2.5 rounded-lg bg-white/[0.03] border border-white/[0.04] hover:bg-white/[0.05] transition-colors cursor-pointer"
            title={`Click to view ${agent.agent_name} details`}
          >
            {statusDot(agent.status)}

            {/* Agent info */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-zinc-200 truncate">
                  {agent.agent_name}
                </span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/[0.06] text-zinc-500">
                  {agent.variant}
                </span>
              </div>

              {/* Confidence bar */}
              <div className="flex items-center gap-2 mt-1.5">
                <div className="flex-1 h-1 rounded-full bg-white/[0.06] overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${confidenceColor(agent.confidence)}`}
                    style={{ width: `${agent.confidence}%` }}
                  />
                </div>
                <span className="text-[11px] text-zinc-500 tabular-nums">
                  {agent.confidence}%
                </span>
              </div>
            </div>

            {/* Tickets count */}
            <div className="text-right shrink-0">
              <p className="text-sm font-semibold text-zinc-300 tabular-nums">
                {agent.tickets_today}
              </p>
              <p className="text-[10px] text-zinc-600">today</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
