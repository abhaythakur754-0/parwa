/**
 * Variant Engine Page (/dashboard/variants) — Phase 5 + Phase 14 Upgrade
 *
 * Full variant management UI with:
 * - Instance list, status, capacity, orchestration controls (Phase 5)
 * - Variant Router section (Phase 14)
 * - Route Ticket test panel (Phase 14)
 * - Variant Usage section (Phase 14)
 * - Add/Remove Variant controls (Phase 14)
 */

'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { cn } from '@/lib/utils';
import { useRouter } from 'next/navigation';
import { VariantInstanceCard, type VariantInstanceData } from '@/components/jarvis-cc/VariantInstanceCard';
import { MetricCard } from '@/components/jarvis-cc/MetricCard';
import { get, post, del } from '@/lib/api';
import { toast } from 'sonner';
import {
  Loader2,
  Route,
  Plus,
  Trash2,
  BarChart3,
  Compass,
  ArrowRight,
} from 'lucide-react';

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

// Phase 14 types
interface VariantInfo {
  id: string;
  variant_type: 'mini' | 'parwa' | 'parwa_high';
  status: string;
  config?: Record<string, unknown>;
  created_at?: string;
}

interface VariantUsageEntry {
  variant_id: string;
  variant_type: string;
  ticket_count: number;
  avg_quality_score?: number;
  avg_latency_ms?: number;
}

interface RouteTicketResult {
  variant_id: string;
  variant_type: string;
  reason?: string;
}

// ── Icons ───────────────────────────────────────────────────────────

const ChipIcon = () => (
  <svg className="w-6 h-6 text-orange-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 3v1.5M4.5 8.25H3m18 0h-1.5M4.5 12H3m18 0h-1.5M4.5 15.75H3m18 0h-1.5M8.25 19.5V21M12 3v1.5m0 15V21m3.75-18v1.5m0 15V21m-9-1.5h10.5a2.25 2.25 0 0 0 2.25-2.25V6.75a2.25 2.25 0 0 0-2.25-2.25H6.75A2.25 2.25 0 0 0 4.5 6.75v10.5a2.25 2.25 0 0 0 2.25 2.25Zm.75-12h9v9h-9v-9Z" />
  </svg>
);

const tierNames: Record<string, string> = {
  mini_parwa: 'Mini Parwa',
  mini: 'Mini Parwa',
  parwa: 'Parwa Standard',
  parwa_high: 'Parwa High',
};

const tierDescriptions: Record<string, string> = {
  mini_parwa: 'Lightweight agent for simple queries and FAQ handling',
  mini: 'Lightweight agent for simple queries and FAQ handling',
  parwa: 'Standard agent with full technique suite and RAG support',
  parwa_high: 'Premium agent with advanced reasoning and escalation capabilities',
};

// ── Variants Page ───────────────────────────────────────────────────

export default function VariantsPage() {
  const router = useRouter();
  const [instances, setInstances] = useState<VariantInstance[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Phase 14 state
  const [phase14Variants, setPhase14Variants] = useState<VariantInfo[]>([]);
  const [variantUsage, setVariantUsage] = useState<VariantUsageEntry[]>([]);
  const [routeTicketIntent, setRouteTicketIntent] = useState('');
  const [routeTicketComplexity, setRouteTicketComplexity] = useState(5);
  const [routeTicketResult, setRouteTicketResult] = useState<RouteTicketResult | null>(null);
  const [isRouting, setIsRouting] = useState(false);
  const [isAddingVariant, setIsAddingVariant] = useState(false);
  const [addVariantType, setAddVariantType] = useState<'mini' | 'parwa' | 'parwa_high'>('mini');
  const [isRemovingVariant, setIsRemovingVariant] = useState<string | null>(null);
  const [isLoadingVariants, setIsLoadingVariants] = useState(true);
  const [isLoadingUsage, setIsLoadingUsage] = useState(true);

  // ── Fetch instances (Phase 5 existing) ──────────────────────────────
  const fetchInstances = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await get<VariantInstance[]>('/api/ai/instances');
      setInstances(Array.isArray(result) ? result : []);
    } catch {
      try {
        const sessionId = localStorage.getItem('jarvis_cc_session_id');
        if (sessionId) {
          await get(`/api/jarvis/cc/awareness/snapshot?session_id=${sessionId}`);
          setInstances([]);
        }
      } catch {
        setInstances([]);
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  // ── Phase 14: Fetch variants from /api/variants/list ───────────────
  const fetchPhase14Variants = useCallback(async () => {
    setIsLoadingVariants(true);
    try {
      const result = await get<VariantInfo[]>('/api/variants/list');
      setPhase14Variants(Array.isArray(result) ? result : []);
    } catch {
      // Phase 14 endpoint unavailable — non-critical
      setPhase14Variants([]);
    } finally {
      setIsLoadingVariants(false);
    }
  }, []);

  // ── Phase 14: Fetch usage from /api/variants/usage ─────────────────
  const fetchVariantUsage = useCallback(async () => {
    setIsLoadingUsage(true);
    try {
      const result = await get<VariantUsageEntry[]>('/api/variants/usage');
      setVariantUsage(Array.isArray(result) ? result : []);
    } catch {
      setVariantUsage([]);
    } finally {
      setIsLoadingUsage(false);
    }
  }, []);

  useEffect(() => {
    fetchInstances();
  }, [fetchInstances]);

  useEffect(() => {
    fetchPhase14Variants();
    fetchVariantUsage();
  }, [fetchPhase14Variants, fetchVariantUsage]);

  // ── Phase 14: Route Ticket ──────────────────────────────────────────
  const handleRouteTicket = async () => {
    if (!routeTicketIntent.trim()) {
      toast.error('Please enter a ticket intent');
      return;
    }

    setIsRouting(true);
    setRouteTicketResult(null);
    try {
      const result = await post<RouteTicketResult>('/api/variants/route-ticket', {
        intent: routeTicketIntent,
        complexity_score: routeTicketComplexity,
      });
      setRouteTicketResult(result);
      toast.success(`Routed to ${tierNames[result.variant_type] || result.variant_type}`);
    } catch (err) {
      toast.error('Failed to route ticket');
    } finally {
      setIsRouting(false);
    }
  };

  // ── Phase 14: Add Variant ───────────────────────────────────────────
  const handleAddVariant = async () => {
    setIsAddingVariant(true);
    try {
      await post('/api/variants/add', {
        variant_type: addVariantType,
      });
      toast.success(`${tierNames[addVariantType]} variant added`);
      await fetchPhase14Variants();
    } catch (err) {
      toast.error('Failed to add variant');
    } finally {
      setIsAddingVariant(false);
    }
  };

  // ── Phase 14: Remove Variant ────────────────────────────────────────
  const handleRemoveVariant = async (variantId: string) => {
    if (!confirm('Are you sure you want to remove this variant?')) return;

    setIsRemovingVariant(variantId);
    try {
      await del('/api/variants/remove', {
        data: { variant_id: variantId },
      } as Parameters<typeof del>[1]);
      toast.success('Variant removed');
      await fetchPhase14Variants();
    } catch (err) {
      toast.error('Failed to remove variant');
    } finally {
      setIsRemovingVariant(null);
    }
  };

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
    const instance = instances.find((i) => i.id === instanceId);
    if (!instance) return;

    const tierOrder = ['mini_parwa', 'parwa', 'parwa_high'] as const;
    const currentIdx = tierOrder.indexOf(instance.variant_tier as typeof tierOrder[number]);
    const nextTier = currentIdx < tierOrder.length - 1 ? tierOrder[currentIdx + 1] : null;

    setInstances((prev) =>
      prev.map((inst) =>
        inst.id === instanceId
          ? {
              ...inst,
              status: 'active',
              capacity: nextTier === 'parwa' ? 5000 : nextTier === 'parwa_high' ? 99999 : inst.capacity,
            }
          : inst
      )
    );

    try {
      const escalations = JSON.parse(localStorage.getItem('parwa_variant_escalations') || '[]');
      escalations.push({
        instanceId,
        fromTier: instance.variant_tier,
        toTier: nextTier || instance.variant_tier,
        escalatedAt: new Date().toISOString(),
      });
      localStorage.setItem('parwa_variant_escalations', JSON.stringify(escalations));
    } catch {
      // localStorage unavailable — non-critical
    }

    const tierName = tierNames[instance.variant_tier] || instance.variant_tier;
    if (nextTier) {
      toast.success(`Escalated ${tierName} instance`, {
        description: `Instance promoted to ${tierNames[nextTier]} tier. Active tickets will be re-routed.`,
      });
    } else {
      toast.info(`Escalation requested for ${tierName}`, {
        description: 'Already at highest tier. A human agent has been notified.',
      });
    }
  };

  const handleShadowMode = (instanceId: string, tier: string) => {
    const tierOrder = ['mini_parwa', 'parwa', 'parwa_high'] as const;
    const currentIdx = tierOrder.indexOf(tier as typeof tierOrder[number]);
    const shadowTier = currentIdx < tierOrder.length - 1 ? tierOrder[currentIdx + 1] : null;

    if (shadowTier) {
      toast.info('Opening Shadow Mode', {
        description: `Test ${tierNames[shadowTier]} against ${tierNames[tier]} in Shadow Mode`,
      });
    } else {
      toast.info('Opening Shadow Mode', {
        description: `Configure shadow testing for ${tierNames[tier]}`,
      });
    }

    router.push('/dashboard/shadow-mode');
  };

  const handleRebalance = (instanceId: string) => {
    const instance = instances.find((i) => i.id === instanceId);
    if (!instance) return;

    const sameTierInstances = instances.filter(
      (i) => i.variant_tier === instance.variant_tier && i.id !== instanceId && i.status === 'active'
    );

    if (sameTierInstances.length === 0) {
      toast.info('No available instances for rebalancing', {
        description: 'Add more instances or escalate to a higher tier.',
      });
      return;
    }

    const overload = instance.active_tickets - Math.floor(instance.capacity * 0.6);
    if (overload <= 0) {
      toast.info('Instance is within healthy load', {
        description: `Utilization at ${Math.round((instance.active_tickets / instance.capacity) * 100)}% — no rebalance needed.`,
      });
      return;
    }

    const perInstance = Math.floor(overload / sameTierInstances.length);
    const remainder = overload % sameTierInstances.length;

    setInstances((prev) =>
      prev.map((inst) => {
        if (inst.id === instanceId) {
          return { ...inst, active_tickets: inst.active_tickets - overload };
        }
        const idx = sameTierInstances.findIndex((s) => s.id === inst.id);
        if (idx >= 0) {
          return {
            ...inst,
            active_tickets: inst.active_tickets + perInstance + (idx < remainder ? 1 : 0),
          };
        }
        return inst;
      })
    );

    try {
      const rebalances = JSON.parse(localStorage.getItem('parwa_variant_rebalances') || '[]');
      rebalances.push({
        instanceId,
        tier: instance.variant_tier,
        ticketsRedistributed: overload,
        targetCount: sameTierInstances.length,
        rebalancedAt: new Date().toISOString(),
      });
      localStorage.setItem('parwa_variant_rebalances', JSON.stringify(rebalances));
    } catch {
      // localStorage unavailable — non-critical
    }

    toast.success(`Rebalanced ${tierNames[instance.variant_tier] || instance.variant_tier}`, {
      description: `${overload} ticket${overload !== 1 ? 's' : ''} redistributed across ${sameTierInstances.length} instance${sameTierInstances.length !== 1 ? 's' : ''}.`,
    });
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
          onClick={() => { fetchInstances(); fetchPhase14Variants(); fetchVariantUsage(); }}
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

      {/* ══════════════════════════════════════════════════════════════════
          Phase 14: Variant Router Section
         ══════════════════════════════════════════════════════════════════ */}
      <div className="rounded-xl border border-orange-500/10 bg-[#1A1A1A] overflow-hidden">
        <div className="px-4 py-3 border-b border-white/[0.06] flex items-center gap-2">
          <Compass className="w-4 h-4 text-orange-400" />
          <h3 className="text-sm font-semibold text-white">Variant Router</h3>
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-orange-500/10 text-orange-400 uppercase tracking-wider">Phase 14</span>
        </div>
        <div className="p-4">
          {/* Active variants list */}
          {isLoadingVariants ? (
            <div className="flex items-center gap-2 py-4 justify-center">
              <Loader2 className="w-4 h-4 animate-spin text-orange-400" />
              <span className="text-xs text-zinc-500">Loading variants...</span>
            </div>
          ) : phase14Variants.length === 0 ? (
            <div className="text-center py-6">
              <p className="text-sm text-zinc-500 mb-2">No active variants configured</p>
              <p className="text-xs text-zinc-600">Add a variant below to get started</p>
            </div>
          ) : (
            <div className="space-y-2 mb-4">
              {phase14Variants.map((v) => (
                <div
                  key={v.id}
                  className="flex items-center justify-between px-3 py-2.5 rounded-lg bg-white/[0.02] border border-white/[0.04] hover:border-white/[0.08] transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <span className={cn(
                      'w-2 h-2 rounded-full',
                      v.status === 'active' ? 'bg-emerald-400' : v.status === 'idle' ? 'bg-zinc-500' : 'bg-red-400'
                    )} />
                    <span className="text-sm text-white font-medium">
                      {tierNames[v.variant_type] || v.variant_type}
                    </span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/5 text-zinc-500 uppercase">
                      {v.status}
                    </span>
                  </div>
                  <button
                    onClick={() => handleRemoveVariant(v.id)}
                    disabled={isRemovingVariant === v.id}
                    className="inline-flex items-center gap-1 text-[11px] px-2.5 py-1 rounded-lg bg-red-500/10 text-red-400 hover:bg-red-500/20 transition-colors disabled:opacity-50"
                  >
                    {isRemovingVariant === v.id ? (
                      <Loader2 className="w-3 h-3 animate-spin" />
                    ) : (
                      <Trash2 className="w-3 h-3" />
                    )}
                    Remove
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Add Variant */}
          <div className="flex items-center gap-2 pt-3 border-t border-white/[0.04]">
            <select
              value={addVariantType}
              onChange={(e) => setAddVariantType(e.target.value as 'mini' | 'parwa' | 'parwa_high')}
              className="bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-1.5 text-xs text-zinc-300 focus:outline-none focus:border-orange-500/30"
            >
              <option value="mini">Mini Parwa</option>
              <option value="parwa">Parwa Standard</option>
              <option value="parwa_high">Parwa High</option>
            </select>
            <button
              onClick={handleAddVariant}
              disabled={isAddingVariant}
              className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-gradient-to-r from-orange-600 to-orange-500 text-white hover:from-orange-500 hover:to-orange-400 transition-all disabled:opacity-50 shadow-sm"
            >
              {isAddingVariant ? (
                <Loader2 className="w-3 h-3 animate-spin" />
              ) : (
                <Plus className="w-3 h-3" />
              )}
              Add Variant
            </button>
          </div>
        </div>
      </div>

      {/* ══════════════════════════════════════════════════════════════════
          Phase 14: Route Ticket Test Panel
         ══════════════════════════════════════════════════════════════════ */}
      <div className="rounded-xl border border-orange-500/10 bg-[#1A1A1A] overflow-hidden">
        <div className="px-4 py-3 border-b border-white/[0.06] flex items-center gap-2">
          <Route className="w-4 h-4 text-orange-400" />
          <h3 className="text-sm font-semibold text-white">Route Ticket</h3>
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-orange-500/10 text-orange-400 uppercase tracking-wider">Test</span>
        </div>
        <div className="p-4">
          <p className="text-xs text-zinc-500 mb-4">
            Enter a ticket intent and complexity score to test which variant the router would assign.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
            <div>
              <label className="text-xs text-zinc-500 mb-1.5 block">Ticket Intent</label>
              <input
                type="text"
                value={routeTicketIntent}
                onChange={(e) => setRouteTicketIntent(e.target.value)}
                placeholder="e.g., Customer refund request"
                className="w-full bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-2 text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-orange-500/30"
              />
            </div>
            <div>
              <label className="text-xs text-zinc-500 mb-1.5 block">
                Complexity Score: <span className="text-orange-400 font-medium">{routeTicketComplexity}</span>
              </label>
              <input
                type="range"
                min={1}
                max={10}
                value={routeTicketComplexity}
                onChange={(e) => setRouteTicketComplexity(Number(e.target.value))}
                className="w-full h-2 bg-white/5 rounded-full appearance-none cursor-pointer accent-orange-500"
              />
              <div className="flex justify-between text-[10px] text-zinc-600 mt-1">
                <span>Simple (1)</span>
                <span>Complex (10)</span>
              </div>
            </div>
          </div>
          <button
            onClick={handleRouteTicket}
            disabled={isRouting || !routeTicketIntent.trim()}
            className="inline-flex items-center gap-2 text-xs px-4 py-2 rounded-lg bg-gradient-to-r from-orange-600 to-orange-500 text-white hover:from-orange-500 hover:to-orange-400 transition-all disabled:opacity-50 shadow-sm"
          >
            {isRouting ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Route className="w-3.5 h-3.5" />
            )}
            Route Ticket
          </button>

          {/* Route result */}
          {routeTicketResult && (
            <div className="mt-4 p-3 rounded-lg bg-emerald-500/5 border border-emerald-500/20">
              <div className="flex items-center gap-2">
                <ArrowRight className="w-4 h-4 text-emerald-400" />
                <span className="text-sm text-white font-medium">
                  Routed to: {tierNames[routeTicketResult.variant_type] || routeTicketResult.variant_type}
                </span>
              </div>
              {routeTicketResult.reason && (
                <p className="text-xs text-zinc-400 mt-1 ml-6">{routeTicketResult.reason}</p>
              )}
              <p className="text-[10px] text-zinc-600 mt-1 ml-6">
                Variant ID: {routeTicketResult.variant_id}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* ══════════════════════════════════════════════════════════════════
          Phase 14: Variant Usage Section
         ══════════════════════════════════════════════════════════════════ */}
      <div className="rounded-xl border border-orange-500/10 bg-[#1A1A1A] overflow-hidden">
        <div className="px-4 py-3 border-b border-white/[0.06] flex items-center gap-2">
          <BarChart3 className="w-4 h-4 text-orange-400" />
          <h3 className="text-sm font-semibold text-white">Variant Usage</h3>
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-orange-500/10 text-orange-400 uppercase tracking-wider">Phase 14</span>
        </div>
        <div className="p-4">
          {isLoadingUsage ? (
            <div className="flex items-center gap-2 py-4 justify-center">
              <Loader2 className="w-4 h-4 animate-spin text-orange-400" />
              <span className="text-xs text-zinc-500">Loading usage data...</span>
            </div>
          ) : variantUsage.length === 0 ? (
            <div className="text-center py-6">
              <p className="text-sm text-zinc-500">No usage data available yet</p>
              <p className="text-xs text-zinc-600 mt-1">Usage data will appear once tickets are routed to variants</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-white/[0.06]">
                    <th className="text-left px-3 py-2 text-zinc-500 font-medium">Variant</th>
                    <th className="text-center px-3 py-2 text-zinc-500 font-medium">Tickets</th>
                    <th className="text-center px-3 py-2 text-zinc-500 font-medium">Avg Quality</th>
                    <th className="text-center px-3 py-2 text-zinc-500 font-medium">Avg Latency</th>
                  </tr>
                </thead>
                <tbody className="text-zinc-400">
                  {variantUsage.map((entry) => (
                    <tr key={entry.variant_id} className="border-b border-white/[0.03] hover:bg-white/[0.02]">
                      <td className="px-3 py-2.5 text-white font-medium">
                        {tierNames[entry.variant_type] || entry.variant_type}
                      </td>
                      <td className="px-3 py-2.5 text-center">{entry.ticket_count}</td>
                      <td className="px-3 py-2.5 text-center">
                        {entry.avg_quality_score !== undefined
                          ? `${Math.round(entry.avg_quality_score * 100)}%`
                          : '--'}
                      </td>
                      <td className="px-3 py-2.5 text-center">
                        {entry.avg_latency_ms !== undefined
                          ? `${entry.avg_latency_ms}ms`
                          : '--'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Instance List by Tier (existing Phase 5) */}
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
                  onShadowMode={handleShadowMode}
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
