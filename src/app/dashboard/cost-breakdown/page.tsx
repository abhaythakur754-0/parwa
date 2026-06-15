'use client';

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { cn } from '@/lib/utils';
import {
  type VariantTier,
  type AddOn,
  VARIANT_PRICES,
  VARIANT_DISPLAY_NAMES,
  VARIANT_TAGLINES,
  VARIANT_LIMITS,
  VARIANT_AI_INFO,
  VARIANT_TIER_ORDER,
  ADD_ONS,
  OVERAGE_PRICE_PER_TICKET,
  AGENT_COST_MONTHLY,
  TICKETS_PER_AGENT,
  calculateCostBreakdown,
  calculateWhatIfUpgrade,
  type CostBreakdownResult,
  type WhatIfPreview,
  normalizeTier,
  CANONICAL_TO_LEGACY,
} from '@/lib/pricing-config';
import {
  Receipt,
  Plus,
  Minus,
  TrendingDown,
  Shield,
  Sparkles,
  AlertTriangle,
  ChevronRight,
  Brain,
  Users,
  TicketCheck,
  Mic,
  Plug,
  Zap,
  ArrowUpRight,
  Info,
  BarChart3,
  Calculator,
  PiggyBank,
} from 'lucide-react';
import { toast } from '@/lib/dynamic-toast';

// ── Types ──────────────────────────────────────────────────────────

type BillingCycle = 'monthly' | 'annual';

interface UsageData {
  ticketsUsed: number;
  agentsUsed: number;
  docsUsed: number;
}

// ── Helpers ────────────────────────────────────────────────────────

function fmt(n: number): string {
  return n.toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  });
}

function fmtNum(n: number): string {
  return n.toLocaleString('en-US', { maximumFractionDigits: 0 });
}

function fmtPct(n: number): string {
  return `${Math.round(n)}%`;
}

// ── Usage Bar Component ────────────────────────────────────────────

function UsageBar({
  used,
  total,
  label,
  unit,
  color,
  overageRate,
}: {
  used: number;
  total: number;
  label: string;
  unit: string;
  color: string;
  overageRate?: string;
}) {
  const pct = total > 0 ? Math.min((used / total) * 100, 100) : 0;
  const isNearLimit = pct >= 80;
  const isOverLimit = used > total;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-xs text-zinc-400">{label}</span>
        <span
          className={cn(
            'text-xs font-medium',
            isOverLimit ? 'text-red-400' : isNearLimit ? 'text-amber-400' : 'text-zinc-300'
          )}
        >
          {fmtNum(used)} / {fmtNum(total)} {unit}
        </span>
      </div>
      <div className="h-2 bg-white/5 rounded-full overflow-hidden relative">
        <div className={cn('h-full rounded-full transition-all duration-700', color)} style={{ width: `${pct}%` }} />
        {isOverLimit && (
          <div
            className="absolute top-0 h-full bg-red-500/30 rounded-r-full"
            style={{ left: '100%', width: `${Math.min(((used - total) / total) * 100, 50)}%` }}
          />
        )}
      </div>
      {isOverLimit && overageRate && (
        <p className="text-[10px] text-red-400 flex items-center gap-1">
          <AlertTriangle className="w-3 h-3" />
          Over limit — {fmtNum(used - total)} overage tickets at {overageRate}/ticket
        </p>
      )}
      {isNearLimit && !isOverLimit && (
        <p className="text-[10px] text-amber-400 flex items-center gap-1">
          <AlertTriangle className="w-3 h-3" />
          Approaching limit — {fmtPct(pct)} used
        </p>
      )}
    </div>
  );
}

// ── Variant Mixer Card ─────────────────────────────────────────────

function VariantMixerCard({
  tier,
  isActive,
  onToggle,
}: {
  tier: VariantTier;
  isActive: boolean;
  onToggle: () => void;
}) {
  const limits = VARIANT_LIMITS[tier];
  const aiInfo = VARIANT_AI_INFO[tier];
  const price = VARIANT_PRICES[tier];

  return (
    <button
      onClick={onToggle}
      className={cn(
        'w-full text-left rounded-xl border p-4 transition-all duration-300',
        isActive
          ? 'border-orange-500/30 bg-orange-500/5 shadow-sm shadow-orange-500/10'
          : 'border-white/[0.06] bg-white/[0.02] hover:border-white/[0.12] hover:bg-white/[0.04]'
      )}
    >
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="flex items-center gap-2">
            <h4 className="text-sm font-semibold text-white">{VARIANT_DISPLAY_NAMES[tier]}</h4>
            {isActive && (
              <span className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                Active
              </span>
            )}
          </div>
          <p className="text-[10px] text-zinc-500 mt-0.5">{VARIANT_TAGLINES[tier]}</p>
        </div>
        <div className="text-right">
          <span className="text-base font-bold text-white">{fmt(price)}</span>
          <span className="text-[10px] text-zinc-500">/mo</span>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2 mb-3">
        <div className="rounded-lg p-2 bg-white/[0.03]">
          <p className="text-[9px] text-zinc-500 uppercase tracking-wider">Pipeline</p>
          <p className="text-xs font-medium text-white">{aiInfo.pipelineSteps}-step</p>
        </div>
        <div className="rounded-lg p-2 bg-white/[0.03]">
          <p className="text-[9px] text-zinc-500 uppercase tracking-wider">Tickets</p>
          <p className="text-xs font-medium text-white">{fmtNum(limits.monthlyTickets)}/mo</p>
        </div>
        <div className="rounded-lg p-2 bg-white/[0.03]">
          <p className="text-[9px] text-zinc-500 uppercase tracking-wider">AI Resolve</p>
          <p className="text-xs font-medium text-white">{fmtPct(aiInfo.aiResolution * 100)}</p>
        </div>
      </div>

      {/* Toggle button */}
      <div className="flex items-center justify-center">
        <div
          className={cn(
            'w-full h-9 rounded-lg flex items-center justify-center gap-2 text-xs font-medium transition-all duration-200',
            isActive
              ? 'bg-orange-500/10 text-orange-400 border border-orange-500/20'
              : 'bg-gradient-to-r from-orange-500 to-amber-400 text-[#1A1A1A] shadow-lg shadow-orange-500/20'
          )}
        >
          {isActive ? (
            <>
              <Minus className="w-3.5 h-3.5" />
              Remove Variant
            </>
          ) : (
            <>
              <Plus className="w-3.5 h-3.5" />
              Add Variant
            </>
          )}
        </div>
      </div>
    </button>
  );
}

// ── What If Preview Card ───────────────────────────────────────────

function WhatIfCard({
  preview,
  targetTier,
  onAdd,
}: {
  preview: WhatIfPreview;
  targetTier: VariantTier;
  onAdd: () => void;
}) {
  return (
    <div className="rounded-xl border border-purple-500/20 bg-purple-500/5 p-4 transition-all hover:border-purple-500/30">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-purple-400" />
          <span className="text-sm font-semibold text-white">Add {VARIANT_DISPLAY_NAMES[targetTier]}</span>
        </div>
        <span className="text-xs font-medium text-purple-400">+{fmt(preview.difference)}/mo</span>
      </div>
      <div className="space-y-1.5 mb-3">
        <div className="flex items-center justify-between text-xs">
          <span className="text-zinc-400">Ticket capacity</span>
          <span className="text-emerald-400">+{fmtNum(preview.ticketIncrease)}/mo</span>
        </div>
        <div className="flex items-center justify-between text-xs">
          <span className="text-zinc-400">New total</span>
          <span className="text-white font-medium">{fmt(preview.newTotal)}/mo</span>
        </div>
        <div className="flex items-center justify-between text-xs">
          <span className="text-zinc-400">Still saving vs humans</span>
          <span className="text-emerald-400 font-medium">{fmt(preview.savingsVsHumans)}/mo</span>
        </div>
      </div>
      <button
        onClick={onAdd}
        className="w-full h-8 rounded-lg bg-purple-500/10 text-purple-400 border border-purple-500/20 text-xs font-medium hover:bg-purple-500/20 transition-colors flex items-center justify-center gap-1.5"
      >
        <Plus className="w-3.5 h-3.5" />
        Add {VARIANT_DISPLAY_NAMES[targetTier]}
      </button>
    </div>
  );
}

// ── Main Page ──────────────────────────────────────────────────────

export default function CostBreakdownPage() {
  const [isLoading, setIsLoading] = useState(true);
  const [activeVariants, setActiveVariants] = useState<VariantTier[]>(['starter']);
  const [addOns, setAddOns] = useState<{ voice: boolean; customApi: boolean }>({
    voice: false,
    customApi: false,
  });
  const [billingCycle, setBillingCycle] = useState<BillingCycle>('monthly');
  const [usageData, setUsageData] = useState<UsageData>({
    ticketsUsed: 0,
    agentsUsed: 0,
    docsUsed: 0,
  });

  // Fetch usage data on mount
  useEffect(() => {
    const fetchData = async () => {
      try {
        // Try to get current subscription tier and usage
        const subRes = await fetch('/api/billing/subscription', {
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
        });
        if (subRes.ok) {
          const subData = await subRes.json();
          const tier = normalizeTier(subData.variant_tier || subData.tier || 'mini');
          setActiveVariants([tier]);
        }

        // Try to get usage
        const usageRes = await fetch('/api/billing/usage', {
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
        });
        if (usageRes.ok) {
          const data = await usageRes.json();
          setUsageData({
            ticketsUsed: Number(data.tickets_used ?? data.ticketsUsed ?? 0),
            agentsUsed: Number(data.agents_used ?? data.agentsUsed ?? 0),
            docsUsed: Number(data.docs_used ?? data.docsUsed ?? 0),
          });
        }

        // Try localStorage for onboarding context
        try {
          const stored = localStorage.getItem('parwa_pricing_context');
          if (stored) {
            const ctx = JSON.parse(stored);
            if (ctx.variant) {
              const tier = normalizeTier(ctx.variant);
              if (!activeVariants.includes(tier)) {
                setActiveVariants([tier]);
              }
            }
            if (ctx.addOns) {
              setAddOns(ctx.addOns);
            }
          }
        } catch {
          // ignore
        }
      } catch {
        // Use defaults
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, []);

  // Toggle variant
  const toggleVariant = useCallback((tier: VariantTier) => {
    setActiveVariants((prev) => {
      if (prev.includes(tier)) {
        // Don't allow removing the last variant
        if (prev.length <= 1) {
          toast.error('You must have at least one active variant');
          return prev;
        }
        return prev.filter((t) => t !== tier);
      }
      return [...prev, tier];
    });
  }, []);

  // Toggle add-on
  const toggleAddOn = useCallback((key: 'voice' | 'customApi') => {
    setAddOns((prev) => ({ ...prev, [key]: !prev[key] }));
  }, []);

  // Calculated cost breakdown
  const costBreakdown = useMemo(
    () => calculateCostBreakdown(activeVariants, addOns, usageData.ticketsUsed),
    [activeVariants, addOns, usageData.ticketsUsed]
  );

  // What-if previews for tiers not currently active
  const whatIfPreviews = useMemo(() => {
    const allTiers: VariantTier[] = ['starter', 'growth', 'high'];
    return allTiers
      .filter((tier) => !activeVariants.includes(tier))
      .map((tier) => ({
        tier,
        preview: calculateWhatIfUpgrade(activeVariants, addOns, usageData.ticketsUsed, tier),
      }));
  }, [activeVariants, addOns, usageData.ticketsUsed]);

  // Annual calculation
  const annualTotal = costBreakdown.totalMonthly * 12;

  // Active price for display
  const displayTotal = billingCycle === 'annual' ? annualTotal / 12 : costBreakdown.totalMonthly;

  // ── Loading State ───────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="pb-6 border-b border-white/[0.06]">
          <div className="h-6 w-40 bg-white/5 rounded animate-pulse" />
          <div className="h-4 w-72 bg-white/5 rounded mt-2 animate-pulse" />
        </div>
        <div className="h-64 bg-white/5 rounded-xl animate-pulse" />
        <div className="h-48 bg-white/5 rounded-xl animate-pulse" />
      </div>
    );
  }

  // ── Render ──────────────────────────────────────────────────────

  return (
    <div className="space-y-6">
      {/* ─── Header ─────────────────────────────────────────────── */}
      <div className="flex items-center justify-between pb-6 border-b border-white/[0.06]">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <Calculator className="w-5 h-5 text-orange-400" />
            Cost Breakdown
          </h1>
          <p className="text-sm text-zinc-500 mt-0.5">
            Pure math. No hidden fees. Need more? Add another variant.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* Billing cycle toggle */}
          <div className="flex items-center gap-2 bg-white/[0.03] border border-white/[0.06] rounded-lg px-3 py-1.5">
            <span
              className={cn('text-xs font-medium', billingCycle === 'monthly' ? 'text-white' : 'text-zinc-500')}
            >
              Monthly
            </span>
            <button
              onClick={() => setBillingCycle((prev) => (prev === 'monthly' ? 'annual' : 'monthly'))}
              className={cn(
                'relative w-9 h-5 rounded-full transition-colors',
                billingCycle === 'annual' ? 'bg-orange-500' : 'bg-white/10'
              )}
              aria-label="Toggle billing cycle"
            >
              <span
                className={cn(
                  'absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform',
                  billingCycle === 'annual' ? 'translate-x-4' : 'translate-x-0.5'
                )}
              />
            </button>
            <span
              className={cn('text-xs font-medium', billingCycle === 'annual' ? 'text-white' : 'text-zinc-500')}
            >
              Annual
            </span>
          </div>
        </div>
      </div>

      {/* ─── 1. Variant Mixer ──────────────────────────────────── */}
      <div>
        <div className="flex items-center gap-2 mb-4">
          <Brain className="w-4 h-4 text-orange-400" />
          <h2 className="text-sm font-semibold text-white">Active Variants</h2>
          <span className="text-[10px] text-zinc-500">
            Each variant adds its own ticket allocation and AI pipeline
          </span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {(['starter', 'growth', 'high'] as VariantTier[]).map((tier) => (
            <VariantMixerCard
              key={tier}
              tier={tier}
              isActive={activeVariants.includes(tier)}
              onToggle={() => toggleVariant(tier)}
            />
          ))}
        </div>
      </div>

      {/* ─── 2. Usage & Overage ────────────────────────────────── */}
      <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-6">
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-orange-400" />
            <h2 className="text-sm font-semibold text-white">Live Usage & Overage Projection</h2>
          </div>
          <span className="text-[10px] text-zinc-500 uppercase tracking-wider">Current Period</span>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left: Usage bars */}
          <div className="space-y-5">
            <UsageBar
              used={usageData.ticketsUsed}
              total={costBreakdown.totalTicketLimit}
              label="Ticket Usage"
              unit="tickets"
              color={
                usageData.ticketsUsed > costBreakdown.totalTicketLimit
                  ? 'bg-gradient-to-r from-red-500 to-red-400'
                  : usageData.ticketsUsed / costBreakdown.totalTicketLimit >= 0.8
                    ? 'bg-gradient-to-r from-amber-500 to-red-500'
                    : 'bg-gradient-to-r from-emerald-500 to-emerald-400'
              }
              overageRate={`$${OVERAGE_PRICE_PER_TICKET}`}
            />
            <UsageBar
              used={usageData.agentsUsed}
              total={activeVariants.reduce((sum, t) => sum + VARIANT_LIMITS[t].aiAgents, 0)}
              label="AI Agents"
              unit="agents"
              color="bg-gradient-to-r from-purple-500 to-purple-400"
            />
            <UsageBar
              used={usageData.docsUsed}
              total={activeVariants.reduce((sum, t) => sum + VARIANT_LIMITS[t].kbDocs, 0)}
              label="Knowledge Base Documents"
              unit="docs"
              color="bg-gradient-to-r from-blue-500 to-blue-400"
            />

            {/* Overage projection */}
            {costBreakdown.overageCost > 0 && (
              <div className="rounded-lg border border-red-500/20 bg-red-500/5 p-3">
                <div className="flex items-center gap-2 mb-1">
                  <AlertTriangle className="w-4 h-4 text-red-400" />
                  <span className="text-xs font-semibold text-red-400">Overage Projected</span>
                </div>
                <p className="text-[10px] text-zinc-400">
                  Based on current usage, projected overage:{' '}
                  <span className="text-red-400 font-medium">{fmt(costBreakdown.overageCost)}</span> (
                  {fmtNum(usageData.ticketsUsed - costBreakdown.totalTicketLimit)} tickets x $
                  {OVERAGE_PRICE_PER_TICKET}/ticket). Overage charged at end of billing cycle.
                </p>
              </div>
            )}

            {costBreakdown.overageCost === 0 && usageData.ticketsUsed > 0 && (
              <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-3">
                <div className="flex items-center gap-2 mb-1">
                  <Shield className="w-4 h-4 text-emerald-400" />
                  <span className="text-xs font-semibold text-emerald-400">Within Limits</span>
                </div>
                <p className="text-[10px] text-zinc-400">
                  You are using{' '}
                  <span className="text-emerald-400 font-medium">
                    {fmtPct((usageData.ticketsUsed / costBreakdown.totalTicketLimit) * 100)}
                  </span>{' '}
                  of your ticket allocation. No overage charges projected.
                </p>
              </div>
            )}
          </div>

          {/* Right: Cost Summary */}
          <div className="bg-[#0A0A0A] rounded-lg p-5 border border-white/[0.04] space-y-3">
            <h3 className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-4">
              Cost Breakdown
            </h3>

            {/* Per-variant breakdown */}
            {activeVariants.map((tier) => (
              <div key={tier} className="flex items-center justify-between">
                <span className="text-xs text-zinc-400 flex items-center gap-1.5">
                  <div
                    className={cn(
                      'w-2 h-2 rounded-full',
                      tier === 'starter'
                        ? 'bg-blue-400'
                        : tier === 'growth'
                          ? 'bg-purple-400'
                          : 'bg-orange-400'
                    )}
                  />
                  {VARIANT_DISPLAY_NAMES[tier]}
                </span>
                <span className="text-xs text-zinc-300 font-medium">
                  {fmt(VARIANT_PRICES[tier])}/mo
                </span>
              </div>
            ))}

            {/* Add-ons */}
            {costBreakdown.addOns.voice > 0 && (
              <div className="flex items-center justify-between">
                <span className="text-xs text-zinc-400 flex items-center gap-1.5">
                  <Mic className="w-3 h-3 text-zinc-500" />
                  Voice Channel
                </span>
                <span className="text-xs text-zinc-300 font-medium">
                  {fmt(costBreakdown.addOns.voice)}/mo
                </span>
              </div>
            )}
            {costBreakdown.addOns.customApi > 0 && (
              <div className="flex items-center justify-between">
                <span className="text-xs text-zinc-400 flex items-center gap-1.5">
                  <Plug className="w-3 h-3 text-zinc-500" />
                  Custom API Connector
                </span>
                <span className="text-xs text-zinc-300 font-medium">
                  {fmt(costBreakdown.addOns.customApi)}/mo
                </span>
              </div>
            )}

            {/* Overage line */}
            {costBreakdown.overageCost > 0 && (
              <div className="flex items-center justify-between">
                <span className="text-xs text-red-400 flex items-center gap-1.5">
                  <AlertTriangle className="w-3 h-3" />
                  Projected Overage
                </span>
                <span className="text-xs text-red-400 font-medium">
                  {fmt(costBreakdown.overageCost)}
                </span>
              </div>
            )}

            {/* Integrations = $0 */}
            <div className="flex items-center justify-between">
              <span className="text-xs text-zinc-400 flex items-center gap-1.5">
                <Zap className="w-3 h-3 text-zinc-500" />
                Integrations
              </span>
              <span className="text-xs text-emerald-400 font-medium">$0 (free)</span>
            </div>

            {/* Divider */}
            <div className="border-t border-white/[0.06] pt-3 mt-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-white font-semibold">Total Monthly</span>
                <span className="text-lg text-orange-400 font-bold">
                  {fmt(displayTotal)}
                  <span className="text-xs text-zinc-500 font-normal">/mo</span>
                </span>
              </div>
              {billingCycle === 'annual' && (
                <div className="flex items-center justify-between mt-1">
                  <span className="text-xs text-zinc-500">Annual total</span>
                  <span className="text-xs text-zinc-400 font-medium">{fmt(annualTotal)}/yr</span>
                </div>
              )}
            </div>

            {/* Per-ticket cost */}
            <div className="border-t border-white/[0.06] pt-3 mt-1">
              <div className="flex items-center justify-between">
                <span className="text-[10px] text-zinc-500">Effective cost per ticket</span>
                <span className="text-[10px] text-zinc-400 font-medium">
                  {costBreakdown.totalTicketLimit > 0
                    ? fmt(costBreakdown.totalMonthly / costBreakdown.totalTicketLimit)
                    : '$0'}
                  /ticket
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-[10px] text-zinc-500">Overage rate</span>
                <span className="text-[10px] text-zinc-400 font-medium">
                  ${OVERAGE_PRICE_PER_TICKET}/ticket
                </span>
              </div>
            </div>

            {/* D13 Banner */}
            <div className="flex items-center justify-center gap-1.5 pt-2 text-[10px] text-zinc-600">
              <Shield className="w-3 h-3" />
              <span>No hidden fees. Need more? Add another variant.</span>
            </div>
          </div>
        </div>
      </div>

      {/* ─── 3. Add-Ons Section ────────────────────────────────── */}
      <div>
        <div className="flex items-center gap-2 mb-4">
          <Plug className="w-4 h-4 text-orange-400" />
          <h2 className="text-sm font-semibold text-white">Optional Add-Ons</h2>
          <span className="text-[10px] text-zinc-500">Enhance your plan with additional capabilities</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {ADD_ONS.map((addOn) => {
            const isSelected = addOns[addOn.key];
            const isIncluded = activeVariants.some((t) => addOn.includedIn.includes(t));
            const showPrice = !isIncluded;

            return (
              <button
                key={addOn.key}
                onClick={() => toggleAddOn(addOn.key)}
                className={cn(
                  'text-left p-4 rounded-xl border transition-all duration-200',
                  isSelected || isIncluded
                    ? 'border-orange-500/20 bg-orange-500/5'
                    : 'border-white/[0.06] bg-white/[0.02] hover:border-white/[0.12]'
                )}
              >
                <div className="flex items-start gap-3">
                  <div
                    className={cn(
                      'w-9 h-9 rounded-lg flex items-center justify-center shrink-0',
                      isSelected || isIncluded ? 'bg-orange-500/10' : 'bg-white/[0.04]'
                    )}
                  >
                    <addOn.icon
                      className={cn(
                        'w-4 h-4',
                        isSelected || isIncluded ? 'text-orange-400' : 'text-zinc-500'
                      )}
                    />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span
                        className={cn(
                          'text-sm font-medium',
                          isSelected || isIncluded ? 'text-orange-400' : 'text-white'
                        )}
                      >
                        {addOn.name}
                      </span>
                      {isIncluded && (
                        <span className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                          Included
                        </span>
                      )}
                    </div>
                    <p className="text-[10px] text-zinc-500 mt-0.5">{addOn.description}</p>
                    {showPrice && (
                      <p className="text-xs font-semibold text-white mt-1">{fmt(addOn.price)}/mo</p>
                    )}
                  </div>
                  <div
                    className={cn(
                      'w-8 h-5 rounded-full flex items-center px-0.5 transition-colors duration-200',
                      isSelected || isIncluded
                        ? 'bg-gradient-to-r from-orange-500 to-amber-400'
                        : 'bg-white/10'
                    )}
                  >
                    <div
                      className={cn(
                        'w-4 h-4 rounded-full bg-white shadow-sm transition-transform duration-200',
                        isSelected || isIncluded ? 'translate-x-3' : 'translate-x-0'
                      )}
                    />
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* ─── 4. Savings vs Humans ──────────────────────────────── */}
      <div
        className="rounded-xl border border-emerald-500/20 p-5"
        style={{ background: 'rgba(16,185,129,0.04)' }}
      >
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-xl bg-emerald-500/10 flex items-center justify-center shrink-0">
            <PiggyBank className="w-5 h-5 text-emerald-400" />
          </div>
          <div className="flex-1">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-semibold text-emerald-400">
                Save {costBreakdown.savingsPercent}% vs human agents
              </h3>
              <span className="text-2xl font-bold text-emerald-400">
                {fmt(costBreakdown.savingsVsHumans)}
                <span className="text-sm text-zinc-500 font-normal">/mo</span>
              </span>
            </div>
            <p className="text-xs text-zinc-400 leading-relaxed">
              Your {activeVariants.length} variant{activeVariants.length > 1 ? 's handle' : ' handles'}{' '}
              {fmtNum(costBreakdown.totalTicketLimit)} tickets/mo — equivalent to{' '}
              {costBreakdown.agentsReplaced} full-time support agent
              {costBreakdown.agentsReplaced > 1 ? 's' : ''} at ~{fmt(AGENT_COST_MONTHLY)}/mo each.
              That&apos;s {fmt(costBreakdown.agentsReplaced * AGENT_COST_MONTHLY)}/mo in human costs vs{' '}
              {fmt(costBreakdown.totalMonthly)}/mo with PARWA.
            </p>
          </div>
        </div>
      </div>

      {/* ─── 5. What If Upgrade Previews ───────────────────────── */}
      {whatIfPreviews.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-4">
            <Sparkles className="w-4 h-4 text-purple-400" />
            <h2 className="text-sm font-semibold text-white">&quot;What If&quot; Upgrade Previews</h2>
            <span className="text-[10px] text-zinc-500">
              See exactly what adding another variant would cost and provide
            </span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {whatIfPreviews.map(({ tier, preview }) => (
              <WhatIfCard
                key={tier}
                preview={preview}
                targetTier={tier}
                onAdd={() => toggleVariant(tier)}
              />
            ))}
          </div>
        </div>
      )}

      {/* ─── 6. Connected Integrations Impact ────────────────────── */}
      <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-6">
        <div className="flex items-center gap-2 mb-4">
          <Zap className="w-4 h-4 text-orange-400" />
          <h2 className="text-sm font-semibold text-white">Integrations Impact</h2>
          <span className="text-[10px] text-zinc-500">All integrations are free to connect and use</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="rounded-lg p-4 bg-white/[0.02] border border-white/[0.04] text-center">
            <div className="text-2xl font-bold text-emerald-400 mb-1">$0</div>
            <div className="text-[10px] text-zinc-500 uppercase tracking-wider">Cost per integration</div>
            <div className="text-[10px] text-zinc-600 mt-1">Connect unlimited integrations for free</div>
          </div>
          <div className="rounded-lg p-4 bg-white/[0.02] border border-white/[0.04] text-center">
            <div className="text-2xl font-bold text-emerald-400 mb-1">$0</div>
            <div className="text-[10px] text-zinc-500 uppercase tracking-wider">Per API call</div>
            <div className="text-[10px] text-zinc-600 mt-1">AI calls to external APIs included in subscription</div>
          </div>
          <div className="rounded-lg p-4 bg-white/[0.02] border border-white/[0.04] text-center">
            <div className="text-2xl font-bold text-emerald-400 mb-1">$0</div>
            <div className="text-[10px] text-zinc-500 uppercase tracking-wider">Add/Remove fee</div>
            <div className="text-[10px] text-zinc-600 mt-1">No charges for connecting or disconnecting</div>
          </div>
        </div>

        <div className="mt-4 p-3 rounded-lg border border-blue-500/20 bg-blue-500/5 flex items-start gap-2">
          <Info className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
          <div>
            <p className="text-xs text-blue-300 font-medium">Per D13: No extra billing calls</p>
            <p className="text-[10px] text-zinc-500 mt-0.5">
              Integrations cost nothing. If you need more ticket capacity, add another variant.
              Custom API Connector is the only integration-related add-on at $49/mo (included in PARWA &amp; PARWA High).
            </p>
          </div>
        </div>
      </div>

      {/* ─── 7. Detailed Line Items Table ────────────────────────── */}
      <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] overflow-hidden">
        <div className="flex items-center justify-between p-5 border-b border-white/[0.06]">
          <div className="flex items-center gap-2">
            <Receipt className="w-4 h-4 text-orange-400" />
            <h2 className="text-sm font-semibold text-white">Detailed Line Items</h2>
          </div>
          <span className="text-[10px] text-zinc-500 uppercase tracking-wider">
            {billingCycle === 'annual' ? 'Annual breakdown' : 'Monthly breakdown'}
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-white/[0.06]">
                <th className="text-left px-5 py-3 text-zinc-500 font-medium uppercase tracking-wider">
                  Item
                </th>
                <th className="text-left px-5 py-3 text-zinc-500 font-medium uppercase tracking-wider">
                  Details
                </th>
                <th className="text-right px-5 py-3 text-zinc-500 font-medium uppercase tracking-wider">
                  Monthly
                </th>
                {billingCycle === 'annual' && (
                  <th className="text-right px-5 py-3 text-zinc-500 font-medium uppercase tracking-wider">
                    Annual
                  </th>
                )}
              </tr>
            </thead>
            <tbody>
              {/* Variant subscriptions */}
              {activeVariants.map((tier) => (
                <tr key={tier} className="border-b border-white/[0.03] hover:bg-white/[0.02] transition-colors">
                  <td className="px-5 py-3 text-zinc-300 font-medium">
                    <div className="flex items-center gap-2">
                      <div
                        className={cn(
                          'w-2 h-2 rounded-full',
                          tier === 'starter' ? 'bg-blue-400' : tier === 'growth' ? 'bg-purple-400' : 'bg-orange-400'
                        )}
                      />
                      {VARIANT_DISPLAY_NAMES[tier]}
                    </div>
                  </td>
                  <td className="px-5 py-3 text-zinc-500">
                    {fmtNum(VARIANT_LIMITS[tier].monthlyTickets)} tickets,{' '}
                    {VARIANT_AI_INFO[tier].pipelineSteps}-step AI,{' '}
                    {fmtPct(VARIANT_AI_INFO[tier].aiResolution * 100)} resolution
                  </td>
                  <td className="px-5 py-3 text-zinc-300 font-medium text-right">
                    {fmt(VARIANT_PRICES[tier])}
                  </td>
                  {billingCycle === 'annual' && (
                    <td className="px-5 py-3 text-zinc-400 text-right">
                      {fmt(VARIANT_PRICES[tier] * 12)}
                    </td>
                  )}
                </tr>
              ))}

              {/* Add-ons */}
              {costBreakdown.addOns.voice > 0 && (
                <tr className="border-b border-white/[0.03] hover:bg-white/[0.02] transition-colors">
                  <td className="px-5 py-3 text-zinc-300 font-medium">Voice Channel</td>
                  <td className="px-5 py-3 text-zinc-500">AI-powered voice calls</td>
                  <td className="px-5 py-3 text-zinc-300 font-medium text-right">
                    {fmt(costBreakdown.addOns.voice)}
                  </td>
                  {billingCycle === 'annual' && (
                    <td className="px-5 py-3 text-zinc-400 text-right">
                      {fmt(costBreakdown.addOns.voice * 12)}
                    </td>
                  )}
                </tr>
              )}
              {costBreakdown.addOns.customApi > 0 && (
                <tr className="border-b border-white/[0.03] hover:bg-white/[0.02] transition-colors">
                  <td className="px-5 py-3 text-zinc-300 font-medium">Custom API Connector</td>
                  <td className="px-5 py-3 text-zinc-500">Connect any REST API</td>
                  <td className="px-5 py-3 text-zinc-300 font-medium text-right">
                    {fmt(costBreakdown.addOns.customApi)}
                  </td>
                  {billingCycle === 'annual' && (
                    <td className="px-5 py-3 text-zinc-400 text-right">
                      {fmt(costBreakdown.addOns.customApi * 12)}
                    </td>
                  )}
                </tr>
              )}

              {/* Overage */}
              <tr className="border-b border-white/[0.03] hover:bg-white/[0.02] transition-colors">
                <td className="px-5 py-3 text-zinc-300 font-medium">Projected Overage</td>
                <td className="px-5 py-3 text-zinc-500">
                  {costBreakdown.overageCost > 0
                    ? `${fmtNum(usageData.ticketsUsed - costBreakdown.totalTicketLimit)} tickets × $${OVERAGE_PRICE_PER_TICKET}/ticket`
                    : 'Within limits'}
                </td>
                <td
                  className={cn(
                    'px-5 py-3 font-medium text-right',
                    costBreakdown.overageCost > 0 ? 'text-red-400' : 'text-emerald-400'
                  )}
                >
                  {costBreakdown.overageCost > 0 ? fmt(costBreakdown.overageCost) : '$0'}
                </td>
                {billingCycle === 'annual' && (
                  <td
                    className={cn(
                      'px-5 py-3 text-right',
                      costBreakdown.overageCost > 0 ? 'text-red-400' : 'text-emerald-400'
                    )}
                  >
                    {costBreakdown.overageCost > 0 ? fmt(costBreakdown.overageCost * 12) : '$0'}
                  </td>
                )}
              </tr>

              {/* Free items */}
              <tr className="border-b border-white/[0.03]">
                <td className="px-5 py-3 text-zinc-400">Integrations</td>
                <td className="px-5 py-3 text-zinc-500">Connect unlimited integrations</td>
                <td className="px-5 py-3 text-emerald-400 font-medium text-right">$0</td>
                {billingCycle === 'annual' && (
                  <td className="px-5 py-3 text-emerald-400 text-right">$0</td>
                )}
              </tr>
              <tr className="border-b border-white/[0.03]">
                <td className="px-5 py-3 text-zinc-400">Knowledge Base</td>
                <td className="px-5 py-3 text-zinc-500">Upload and search documents</td>
                <td className="px-5 py-3 text-emerald-400 font-medium text-right">$0</td>
                {billingCycle === 'annual' && (
                  <td className="px-5 py-3 text-emerald-400 text-right">$0</td>
                )}
              </tr>

              {/* Total */}
              <tr className="bg-white/[0.04]">
                <td className="px-5 py-4 text-white font-bold" colSpan={2}>
                  Total
                </td>
                <td className="px-5 py-4 text-orange-400 font-bold text-base text-right">
                  {fmt(costBreakdown.totalMonthly)}
                  <span className="text-xs text-zinc-500 font-normal">/mo</span>
                </td>
                {billingCycle === 'annual' && (
                  <td className="px-5 py-4 text-orange-400 font-bold text-base text-right">
                    {fmt(annualTotal)}
                    <span className="text-xs text-zinc-500 font-normal">/yr</span>
                  </td>
                )}
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
