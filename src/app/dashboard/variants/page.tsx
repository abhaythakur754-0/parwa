/**
 * Variant Engine Page (/dashboard/variants) — Phase 5 Upgrade
 *
 * Replaces "Coming Soon" with full variant management UI.
 * Instance list, status, capacity, orchestration controls.
 */

'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { cn } from '@/lib/utils';
import { VariantInstanceCard, type VariantInstanceData } from '@/components/jarvis-cc/VariantInstanceCard';
import { MetricCard } from '@/components/jarvis-cc/MetricCard';
import { get } from '@/lib/api';

// ── Types ───────────────────────────────────────────────────────────

interface VariantInstance {
  id: string;
  variant_tier: 'mini_parwa' | 'parwa' | 'parwa_high';
  status: string;
  active_tickets: number;
  capacity: number;
  quality_score: number | null;
  latency_ms: number | null;
  company_id: string;
  created_at: string;
}

// ── Icons ───────────────────────────────────────────────────────────

const ChipIcon = () => (
  <svg className="w-6 h-6 text-orange-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 3v1.5M4.5 8.25H3m18 0h-1.5M4.5 12H3m18 0h-1.5M4.5 15.75H3m18 0h-1.5M8.25 19.5V21M12 3v1.5m0 15V21m3.75-18v1.5m0 15V21m-9-1.5h10.5a2.25 2.25 0 0 0 2.25-2.25V6.75a2.25 2.25 0 0 0-2.25-2.25H6.75A2.25 2.25 0 0 0 4.5 6.75v10.5a2.25 2.25 0 0 0 2.25 2.25Zm.75-12h9v9h-9v-9Z" />
  </svg>
);

const tierNames: Record<string, string> = {
  mini_parwa: 'Mini Parwa',
  parwa: 'Parwa Standard',
  parwa_high: 'Parwa High',
};

const tierDescriptions: Record<string, string> = {
  mini_parwa: 'Lightweight agent for simple queries and FAQ handling',
  parwa: 'Standard agent with full technique suite and RAG support',
  parwa_high: 'Premium agent with advanced reasoning and escalation capabilities',
};

// ── Variants Page ───────────────────────────────────────────────────

export default function VariantsPage() {
  const [instances, setInstances] = useState<VariantInstance[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchInstances = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await get<VariantInstance[]>('/api/ai/instances');
      setInstances(Array.isArray(result) ? result : []);
    } catch {
      // Fallback: try the awareness snapshot for variant data
      try {
        const sessionId = localStorage.getItem('jarvis_cc_session_id');
        if (sessionId) {
          const snap = await get<{ state: { active_agents: number; agent_pool_capacity: number; agent_pool_utilization: number } }>(`/api/jarvis/cc/awareness/snapshot?session_id=${sessionId}`);
          // We got awareness data but not instance details — show overview
          setInstances([]);
        }
      } catch {
        // No data available
        setInstances([]);
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchInstances();
  }, [fetchInstances]);

  // Compute metrics
  const totalActive = instances.filter(i => i.status === 'active').length;
  const totalCapacity = instances.reduce((sum, i) => sum + (i.capacity || 0), 0);
  const totalTickets = instances.reduce((sum, i) => sum + (i.active_tickets || 0), 0);
  const avgQuality = instances.length > 0
    ? instances.reduce((sum, i) => sum + (i.quality_score || 0), 0) / instances.filter(i => i.quality_score !== null).length
    : null;
  const utilization = totalCapacity > 0 ? totalTickets / totalCapacity : 0;

  // Map to card data
  const cardInstances: VariantInstanceData[] = instances.map(i => ({
    id: i.id,
    name: tierNames[i.variant_tier] || i.variant_tier,
    tier: i.variant_tier,
    status: (i.status === 'active' ? 'active' : i.status === 'idle' ? 'idle' : i.status === 'paused' ? 'paused' : 'error') as VariantInstanceData['status'],
    capacity: i.capacity || 0,
    activeTickets: i.active_tickets || 0,
    qualityScore: i.quality_score,
    latencyMs: i.latency_ms,
  }));

  // Group by tier
  const groupedInstances = cardInstances.reduce((acc, inst) => {
    if (!acc[inst.tier]) acc[inst.tier] = [];
    acc[inst.tier].push(inst);
    return acc;
  }, {} as Record<string, VariantInstanceData[]>);

  const handleEscalate = (instanceId: string) => {
    // TODO: Call escalation API
    console.log('Escalating instance:', instanceId);
  };

  const handleRebalance = (instanceId: string) => {
    // TODO: Call rebalance API
    console.log('Rebalancing instance:', instanceId);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between pb-4 border-b border-white/[0.06]">
        <div>
          <h1 className="text-xl font-bold text-white">Variant Engine</h1>
          <p className="text-sm text-zinc-500 mt-0.5">
            Configure and monitor your AI variant instances
          </p>
        </div>
        <button
          onClick={fetchInstances}
          disabled={isLoading}
          className="text-xs px-3 py-1.5 rounded-lg bg-white/[0.04] text-zinc-400 hover:text-white hover:bg-white/[0.08] transition-colors disabled:opacity-50"
        >
          {isLoading ? 'Loading...' : 'Refresh'}
        </button>
      </div>

      {/* Summary Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard
          label="Active Instances"
          value={`${totalActive}/${instances.length}`}
          variant={totalActive === 0 && instances.length > 0 ? 'warning' : 'default'}
        />
        <MetricCard
          label="Total Capacity"
          value={totalCapacity}
          subtitle="tickets"
        />
        <MetricCard
          label="Active Tickets"
          value={totalTickets}
          variant={utilization >= 0.9 ? 'danger' : utilization >= 0.7 ? 'warning' : 'default'}
        />
        <MetricCard
          label="Avg Quality"
          value={avgQuality !== null ? `${Math.round(avgQuality * 100)}%` : '--'}
          variant={avgQuality !== null ? (avgQuality >= 0.7 ? 'success' : avgQuality >= 0.5 ? 'warning' : 'danger') : 'default'}
        />
      </div>

      {/* Utilization Overview */}
      <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-4">
        <h3 className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-3">Pool Utilization</h3>
        <div className="h-3 bg-white/5 rounded-full overflow-hidden">
          <div
            className={cn(
              'h-full rounded-full transition-all duration-700',
              utilization >= 0.9 ? 'bg-red-500' : utilization >= 0.7 ? 'bg-gradient-to-r from-amber-500 to-orange-500' : 'bg-gradient-to-r from-emerald-500 to-emerald-400'
            )}
            style={{ width: `${Math.min(utilization * 100, 100)}%` }}
          />
        </div>
        <div className="flex items-center justify-between mt-2 text-xs text-zinc-500">
          <span>{totalTickets} active tickets</span>
          <span>{Math.round(utilization * 100)}% utilized</span>
        </div>
      </div>

      {/* Instance List by Tier */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <div className="flex flex-col items-center gap-3">
            <div className="w-8 h-8 rounded-full border-2 border-orange-500 border-t-transparent animate-spin" />
            <p className="text-sm text-zinc-500">Loading instances...</p>
          </div>
        </div>
      ) : instances.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 bg-[#1A1A1A] rounded-xl border border-white/[0.06]">
          <div className="w-12 h-12 rounded-xl bg-orange-500/10 flex items-center justify-center mb-4">
            <ChipIcon />
          </div>
          <h3 className="text-lg font-medium text-white mb-2">No Variant Instances</h3>
          <p className="text-sm text-zinc-500 mb-4 text-center max-w-sm">
            Variant instances are created when your subscription is active. Start a Jarvis CC session to initialize your agent pool.
          </p>
          <a
            href="/dashboard/jarvis"
            className="text-xs px-4 py-2 rounded-lg bg-gradient-to-r from-orange-500 to-amber-400 text-white font-medium shadow-lg shadow-orange-500/20 hover:shadow-orange-500/30 transition-all"
          >
            Start Jarvis CC
          </a>
        </div>
      ) : (
        Object.entries(groupedInstances).map(([tier, insts]) => (
          <div key={tier}>
            <div className="flex items-center gap-2 mb-3">
              <h3 className="text-sm font-semibold text-white">{tierNames[tier] || tier}</h3>
              <span className="text-[10px] text-zinc-600">{tierDescriptions[tier]}</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {insts.map(inst => (
                <VariantInstanceCard
                  key={inst.id}
                  instance={inst}
                  onEscalate={handleEscalate}
                  onRebalance={handleRebalance}
                />
              ))}
            </div>
          </div>
        ))
      )}

      {/* Tier Comparison Table */}
      <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] overflow-hidden">
        <div className="px-4 py-3 border-b border-white/[0.06]">
          <h3 className="text-sm font-semibold text-white">Tier Comparison</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-white/[0.06]">
                <th className="text-left px-4 py-2.5 text-zinc-500 font-medium">Feature</th>
                <th className="text-center px-4 py-2.5 text-zinc-400 font-medium">Mini</th>
                <th className="text-center px-4 py-2.5 text-orange-400 font-medium">Standard</th>
                <th className="text-center px-4 py-2.5 text-purple-400 font-medium">High</th>
              </tr>
            </thead>
            <tbody className="text-zinc-400">
              <tr className="border-b border-white/[0.03]">
                <td className="px-4 py-2">Techniques</td>
                <td className="px-4 py-2 text-center">5</td>
                <td className="px-4 py-2 text-center">15</td>
                <td className="px-4 py-2 text-center">27</td>
              </tr>
              <tr className="border-b border-white/[0.03]">
                <td className="px-4 py-2">RAG Support</td>
                <td className="px-4 py-2 text-center text-zinc-600">--</td>
                <td className="px-4 py-2 text-center text-emerald-400">Yes</td>
                <td className="px-4 py-2 text-center text-emerald-400">Yes</td>
              </tr>
              <tr className="border-b border-white/[0.03]">
                <td className="px-4 py-2">Escalation</td>
                <td className="px-4 py-2 text-center text-zinc-600">--</td>
                <td className="px-4 py-2 text-center">Basic</td>
                <td className="px-4 py-2 text-center text-emerald-400">Advanced</td>
              </tr>
              <tr className="border-b border-white/[0.03]">
                <td className="px-4 py-2">Reasoning</td>
                <td className="px-4 py-2 text-center">Simple</td>
                <td className="px-4 py-2 text-center">Standard</td>
                <td className="px-4 py-2 text-center text-emerald-400">Deep</td>
              </tr>
              <tr>
                <td className="px-4 py-2">Max Tickets/Day</td>
                <td className="px-4 py-2 text-center">500</td>
                <td className="px-4 py-2 text-center">5,000</td>
                <td className="px-4 py-2 text-center text-emerald-400">Unlimited</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
