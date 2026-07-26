'use client';

import React, { useState, useEffect, useMemo } from 'react';
import {
  Receipt,
  ArrowRight,
  Loader2,
  Mic,
  Plug,
  TrendingDown,
  Shield,
  AlertCircle,
  ExternalLink,
  Plus,
  Minus,
  AlertTriangle,
  Sparkles,
  Brain,
  BarChart3,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { cn } from '@/lib/utils';
import type { ParwaVariant } from './IndustryVariantStep';
import type { PricingContext } from './IndustryVariantStep';
import {
  VARIANT_PRICES,
  VARIANT_DISPLAY_NAMES,
  VARIANT_LIMITS,
  VARIANT_AI_INFO,
  ADD_ONS as SHARED_ADD_ONS,
  AGENT_COST_MONTHLY,
  TICKETS_PER_AGENT,
  OVERAGE_PRICE_PER_TICKET,
  type VariantTier,
} from '@/lib/pricing-config';

// ── Variant Display Data (sourced from pricing-config.ts) ──────────────

const VARIANT_DISPLAY: Record<VariantTier, {
  name: string;
  price: number;
  priceLabel: string;
  aiPipeline: number;
  ticketVolume: number;
  tagline: string;
}> = {
  parwa: {
    name: VARIANT_DISPLAY_NAMES.parwa,
    price: VARIANT_PRICES.parwa,
    priceLabel: `$${VARIANT_PRICES.parwa.toLocaleString()}/mo`,
    aiPipeline: VARIANT_AI_INFO.parwa.pipelineSteps,
    ticketVolume: VARIANT_LIMITS.parwa.monthlyTickets,
    tagline: VARIANT_AI_INFO.parwa.techniques,
  },
  high: {
    name: VARIANT_DISPLAY_NAMES.high,
    price: VARIANT_PRICES.high,
    priceLabel: `$${VARIANT_PRICES.high.toLocaleString()}/mo`,
    aiPipeline: VARIANT_AI_INFO.high.pipelineSteps,
    ticketVolume: VARIANT_LIMITS.high.monthlyTickets,
    tagline: VARIANT_AI_INFO.high.techniques,
  },
};

// ── Add-Ons ────────────────────────────────────────────────────────────

interface AddOn {
  key: 'voice' | 'customApi';
  name: string;
  description: string;
  price: number;
  icon: React.ElementType;
  /** Which variants already include this feature (no extra charge) */
  includedIn: VariantTier[];
}

const ADD_ONS: AddOn[] = [
  {
    key: 'voice',
    name: 'Voice Channel',
    description: 'AI-powered inbound & outbound voice calls with real-time transcription.',
    price: 199,
    icon: Mic,
    includedIn: ['parwa', 'high'],
  },
  {
    key: 'customApi',
    name: 'Custom API Connector',
    description: 'Connect any REST API with custom auth and schema mapping.',
    price: 49,
    icon: Plug,
    includedIn: ['parwa', 'high'],
  },
];

// ── Savings Calculation (uses AGENT_COST_MONTHLY from pricing-config) ──

function estimateSavings(ticketVolume: number, monthlyCost: number): {
  agentsReplaced: number;
  humanCost: number;
  savings: number;
  savingsPercent: number;
} {
  const agentsReplaced = Math.max(1, Math.round(ticketVolume / TICKETS_PER_AGENT));
  const humanCost = agentsReplaced * AGENT_COST_MONTHLY;
  const savings = Math.max(0, humanCost - monthlyCost);
  const savingsPercent = humanCost > 0 ? Math.round((savings / humanCost) * 100) : 0;
  return { agentsReplaced, humanCost, savings, savingsPercent };
}

// ── Usage Bar Component ────────────────────────────────────────────────

function UsageBar({
  used,
  total,
  label,
  unit,
  overageRate,
}: {
  used: number;
  total: number;
  label: string;
  unit: string;
  overageRate?: string;
}) {
  const pct = total > 0 ? Math.min((used / total) * 100, 100) : 0;
  const isOverLimit = used > total;

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="text-[10px] text-orange-200/40">{label}</span>
        <span className={cn(
          'text-[10px] font-medium',
          isOverLimit ? 'text-red-400' : 'text-orange-200/50'
        )}>
          {used.toLocaleString()} / {total.toLocaleString()} {unit}
        </span>
      </div>
      <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
        <div
          className={cn(
            'h-full rounded-full transition-all duration-700',
            isOverLimit ? 'bg-gradient-to-r from-red-500 to-red-400' : 'bg-gradient-to-r from-emerald-500 to-emerald-400'
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
      {isOverLimit && overageRate && (
        <p className="text-[9px] text-red-400 flex items-center gap-1">
          <AlertTriangle className="w-2.5 h-2.5" />
          Over limit — {(used - total).toLocaleString()} overage at {overageRate}/ticket
        </p>
      )}
    </div>
  );
}

// ── Variant Mixer Card ─────────────────────────────────────────────────

function VariantMixerCard({
  tier,
  isActive,
  onToggle,
}: {
  tier: VariantTier;
  isActive: boolean;
  onToggle: () => void;
}) {
  const info = VARIANT_DISPLAY[tier];
  const limits = VARIANT_LIMITS[tier];
  const aiInfo = VARIANT_AI_INFO[tier];

  return (
    <button
      onClick={onToggle}
      className={cn(
        'w-full text-left p-4 rounded-xl border transition-all duration-200',
        isActive
          ? 'border-orange-500/30 bg-orange-500/5'
          : 'border-white/[0.06] hover:border-orange-500/15'
      )}
      style={!isActive ? { background: 'rgba(255,255,255,0.03)' } : undefined}
    >
      <div className="flex items-center justify-between mb-2">
        <div>
          <div className="flex items-center gap-2">
            <span className={cn(
              'text-sm font-semibold',
              isActive ? 'text-orange-400' : 'text-white'
            )}>
              {info.name}
            </span>
            {isActive && (
              <span className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400">
                Active
              </span>
            )}
          </div>
        </div>
        <span className="text-base font-bold text-white">{info.priceLabel}</span>
      </div>

      <div className="grid grid-cols-3 gap-2 mb-3">
        <div className="rounded-lg p-2" style={{ background: 'rgba(255,255,255,0.03)' }}>
          <p className="text-[9px] text-orange-200/30 uppercase tracking-wider">Pipeline</p>
          <p className="text-xs font-medium text-white">{aiInfo.pipelineSteps}-step</p>
        </div>
        <div className="rounded-lg p-2" style={{ background: 'rgba(255,255,255,0.03)' }}>
          <p className="text-[9px] text-orange-200/30 uppercase tracking-wider">Tickets</p>
          <p className="text-xs font-medium text-white">{limits.monthlyTickets.toLocaleString()}/mo</p>
        </div>
        <div className="rounded-lg p-2" style={{ background: 'rgba(255,255,255,0.03)' }}>
          <p className="text-[9px] text-orange-200/30 uppercase tracking-wider">AI Resolve</p>
          <p className="text-xs font-medium text-white">{Math.round(aiInfo.aiResolution * 100)}%</p>
        </div>
      </div>

      <div className={cn(
        'w-full h-8 rounded-lg flex items-center justify-center gap-1.5 text-xs font-medium transition-all',
        isActive
          ? 'bg-orange-500/10 text-orange-400 border border-orange-500/20'
          : 'bg-gradient-to-r from-orange-500 to-amber-400 text-[#1A1A1A] shadow-lg shadow-orange-500/20'
      )}>
        {isActive ? (
          <><Minus className="w-3.5 h-3.5" /> Remove</>
        ) : (
          <><Plus className="w-3.5 h-3.5" /> Add Variant</>
        )}
      </div>
    </button>
  );
}

// ── Props ──────────────────────────────────────────────────────────────

interface CostBreakdownStepProps {
  variant: ParwaVariant;
  industry?: string;
  onComplete: () => void;
}

// ── Component ──────────────────────────────────────────────────────────

export function CostBreakdownStep({ variant, onComplete }: CostBreakdownStepProps) {
  const initialTier: VariantTier = variant || 'parwa';
  const [activeVariants, setActiveVariants] = useState<VariantTier[]>([initialTier]);
  const [addOns, setAddOns] = useState<{ voice: boolean; customApi: boolean }>({ voice: false, customApi: false });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [checkoutError, setCheckoutError] = useState<string | null>(null);

  // Restore add-ons from localStorage
  useEffect(() => {
    try {
      const stored = localStorage.getItem('parwa_pricing_context');
      if (stored) {
        const ctx = JSON.parse(stored) as PricingContext;
        if (ctx.addOns) {
          setAddOns(ctx.addOns);
        }
      }
    } catch {
      // ignore
    }
  }, []);

  // NOTE: Paddle was removed — payments are now handled by Razorpay via
  // the server-side /api/onboarding/checkout endpoint. No client-side
  // payment SDK is required.

  // ── Calculations (pure math — D7, D10) ──────────────────────────────

  const totalTicketLimit = useMemo(
    () => activeVariants.reduce((sum, tier) => sum + VARIANT_LIMITS[tier].monthlyTickets, 0),
    [activeVariants]
  );

  const baseSubscription = useMemo(
    () => activeVariants.reduce((sum, tier) => sum + VARIANT_PRICES[tier], 0),
    [activeVariants]
  );

  const addOnTotal = useMemo(() => {
    let total = 0;
    if (addOns.voice) {
      const voiceAddOn = ADD_ONS.find((a) => a.key === 'voice')!;
      if (!activeVariants.some((t) => voiceAddOn.includedIn.includes(t))) {
        total += voiceAddOn.price;
      }
    }
    if (addOns.customApi) {
      const customApiAddOn = ADD_ONS.find((a) => a.key === 'customApi')!;
      if (!activeVariants.some((t) => customApiAddOn.includedIn.includes(t))) {
        total += customApiAddOn.price;
      }
    }
    return total;
  }, [addOns, activeVariants]);

  const totalMonthly = baseSubscription + addOnTotal;
  const savings = estimateSavings(totalTicketLimit, totalMonthly);

  // Overage projection (estimates at 80% utilization)
  const projectedTickets = Math.round(totalTicketLimit * 0.8);
  const overageTickets = Math.max(0, projectedTickets - totalTicketLimit);
  const overageCost = overageTickets * OVERAGE_PRICE_PER_TICKET;

  const toggleVariant = (tier: VariantTier) => {
    setActiveVariants((prev) => {
      if (prev.includes(tier)) {
        if (prev.length <= 1) {
          toast.error('You must have at least one active variant');
          return prev;
        }
        return prev.filter((t) => t !== tier);
      }
      return [...prev, tier];
    });
  };

  const toggleAddOn = (key: 'voice' | 'customApi') => {
    setAddOns((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const handleProceed = async () => {
    setIsSubmitting(true);
    setCheckoutError(null);

    try {
      // Update pricing context in localStorage
      const primaryVariant = activeVariants[0] || 'parwa';
      const context: PricingContext = {
        industry: 'other',
        variant: primaryVariant,
        addOns,
        totalMonthly,
        timestamp: new Date().toISOString(),
      };

      // Preserve industry from existing context
      try {
        const stored = localStorage.getItem('parwa_pricing_context');
        if (stored) {
          const existing = JSON.parse(stored) as PricingContext;
          context.industry = existing.industry;
        }
      } catch {
        // ignore
      }

      localStorage.setItem('parwa_pricing_context', JSON.stringify(context));

      // ── Razorpay Checkout Flow ───────────────────────────────────
      // Paddle was removed; checkout is now handled server-side via the
      // /api/onboarding/checkout endpoint, which returns a Razorpay
      // checkout_url. We redirect to it; if no URL is returned, we save
      // the configuration and let the user complete payment later.
      const customData = {
        source: 'parwa_onboarding',
        variant: primaryVariant,
        activeVariants: [...activeVariants],
        addOns,
        industry: context.industry,
        totalMonthly,
      };

      // Try server-side transaction first
      let checkoutUrl: string | null = null;

      try {
        const res = await fetch('/api/onboarding/checkout', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            variant: primaryVariant,
            activeVariants: [...activeVariants],
            addOns,
            totalMonthly,
            industry: context.industry,
            customData,
          }),
        });

        if (res.ok) {
          const checkoutData = await res.json();
          checkoutUrl = checkoutData.checkout_url || null;
        }
      } catch {
        // API unavailable — fall through to save-and-proceed
      }

      // If we got a checkout_url, redirect to it (Razorpay hosted checkout)
      if (checkoutUrl) {
        window.location.href = checkoutUrl;
        return;
      }

      // Fallback: checkout endpoint unavailable — save configuration and proceed
      toast.success('Configuration saved! Complete payment to activate your plan.');
      onComplete();
    } catch (err) {
      console.error('[cost-breakdown] Error:', err);
      setCheckoutError('Something went wrong. Please try again.');
      toast.error('Something went wrong. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="text-center space-y-2">
        <div className="w-14 h-14 mx-auto rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center">
          <Receipt className="w-7 h-7 text-emerald-400" />
        </div>
        <h2 className="text-2xl font-bold text-white">Review Your Plan</h2>
        <p className="text-orange-200/40 text-sm">
          Configure variants, add-ons, and review costs before checkout.
        </p>
      </div>

      {/* ── Payment Provider Notice ───────────────────────────────── */}
      <div className="rounded-xl border border-emerald-500/20 p-3 flex items-center gap-2" style={{ background: 'rgba(16,185,129,0.04)' }}>
        <Shield className="w-4 h-4 text-emerald-400" />
        <p className="text-xs text-emerald-400">Payments handled by Razorpay</p>
        <ExternalLink className="w-3 h-3 text-emerald-400/60 ml-auto" />
      </div>

      {/* ── 1. Variant Mixer ──────────────────────────────────────────── */}
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <Brain className="w-4 h-4 text-orange-400" />
          <label className="text-xs text-orange-200/40 uppercase tracking-wider font-medium">
            Active Variants
          </label>
          <span className="text-[10px] text-orange-200/25">
            Each variant adds its own ticket allocation and AI pipeline
          </span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {(['parwa', 'high'] as VariantTier[]).map((tier) => (
            <VariantMixerCard
              key={tier}
              tier={tier}
              isActive={activeVariants.includes(tier)}
              onToggle={() => toggleVariant(tier)}
            />
          ))}
        </div>
      </div>

      {/* ── 2. Live Usage Bar & Overage Projection ──────────────────── */}
      <div className="rounded-xl border border-white/[0.06] p-4 space-y-4" style={{ background: 'rgba(255,255,255,0.03)' }}>
        <div className="flex items-center gap-2">
          <BarChart3 className="w-4 h-4 text-orange-400" />
          <span className="text-xs text-orange-200/50 uppercase tracking-wider font-medium">
            Live Usage & Overage Projection
          </span>
        </div>
        <UsageBar
          used={projectedTickets}
          total={totalTicketLimit}
          label="Ticket Usage (projected at 80%)"
          unit="tickets"
          overageRate={`$${OVERAGE_PRICE_PER_TICKET}`}
        />
        {overageCost > 0 && (
          <div className="rounded-lg border border-red-500/20 p-3 flex items-start gap-2" style={{ background: 'rgba(239,68,68,0.05)' }}>
            <AlertTriangle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
            <div>
              <p className="text-xs font-medium text-red-400">Overage Projected</p>
              <p className="text-[10px] text-orange-200/30 mt-0.5">
                At 80% utilization, projected overage: ${overageCost.toFixed(2)} ({overageTickets.toLocaleString()} tickets × ${OVERAGE_PRICE_PER_TICKET}/ticket). Overage charged at end of billing cycle.
              </p>
            </div>
          </div>
        )}
        {overageCost === 0 && (
          <div className="rounded-lg border border-emerald-500/20 p-3 flex items-center gap-2" style={{ background: 'rgba(16,185,129,0.04)' }}>
            <Shield className="w-3.5 h-3.5 text-emerald-400" />
            <p className="text-[10px] text-emerald-400">Within limits at projected usage. No overage charges.</p>
          </div>
        )}
      </div>

      {/* ── 3. Add-Ons ───────────────────────────────────────────────── */}
      <div className="space-y-3">
        <label className="text-xs text-orange-200/40 uppercase tracking-wider font-medium">
          Optional Add-Ons
        </label>
        {ADD_ONS.map((addOn) => {
          const Icon = addOn.icon;
          const isSelected = addOns[addOn.key];
          const isIncluded = activeVariants.some((t) => addOn.includedIn.includes(t));
          const showPrice = !isIncluded;

          return (
            <button
              key={addOn.key}
              type="button"
              onClick={() => toggleAddOn(addOn.key)}
              className={cn(
                'w-full text-left p-4 rounded-xl border transition-all duration-200 flex items-start gap-4',
                isSelected
                  ? 'border-orange-500/30 bg-orange-500/5'
                  : 'border-white/[0.06] hover:border-orange-500/15'
              )}
              style={!isSelected ? { background: 'rgba(255,255,255,0.03)' } : undefined}
            >
              <div className={cn(
                'w-10 h-10 rounded-lg flex items-center justify-center shrink-0',
                isSelected ? 'bg-orange-500/10' : 'bg-white/[0.04]'
              )}>
                <Icon className={cn(
                  'w-5 h-5',
                  isSelected ? 'text-orange-400' : 'text-zinc-500'
                )} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <p className={cn(
                    'text-sm font-medium',
                    isSelected ? 'text-orange-400' : 'text-white'
                  )}>
                    {addOn.name}
                  </p>
                  {isIncluded && (
                    <span className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400">
                      Included
                    </span>
                  )}
                </div>
                <p className="text-[10px] text-orange-200/30 mt-0.5">{addOn.description}</p>
              </div>
              <div className="flex flex-col items-end shrink-0 gap-1">
                {showPrice && (
                  <p className="text-sm font-semibold text-white">${addOn.price}/mo</p>
                )}
                <div className={cn(
                  'w-8 h-5 rounded-full flex items-center px-0.5 transition-colors duration-200',
                  isSelected || isIncluded
                    ? 'bg-gradient-to-r from-orange-500 to-amber-400'
                    : 'bg-white/10'
                )}>
                  <div className={cn(
                    'w-4 h-4 rounded-full bg-white shadow-sm transition-transform duration-200',
                    (isSelected || isIncluded) ? 'translate-x-3' : 'translate-x-0'
                  )} />
                </div>
              </div>
            </button>
          );
        })}
      </div>

      {/* ── 4. Cost Summary (pure math — D7) ──────────────────────────── */}
      <div
        className="rounded-xl border border-white/[0.08] p-5 space-y-3"
        style={{ background: 'rgba(255,255,255,0.03)' }}
      >
        {/* Per-variant breakdown */}
        {activeVariants.map((tier) => (
          <div key={tier} className="flex items-center justify-between">
            <span className="text-sm text-orange-200/50 flex items-center gap-1.5">
              <div className={cn(
                'w-2 h-2 rounded-full',
                tier === 'parwa' ? 'bg-orange-400' : 'bg-purple-400'
              )} />
              {VARIANT_DISPLAY[tier].name}
            </span>
            <span className="text-sm text-white">${VARIANT_PRICES[tier].toLocaleString()}/mo</span>
          </div>
        ))}

        {/* Add-ons */}
        {addOns.voice && !activeVariants.some((t) => ADD_ONS.find(a => a.key === 'voice')!.includedIn.includes(t)) && (
          <div className="flex items-center justify-between">
            <span className="text-sm text-orange-200/50">Voice Channel</span>
            <span className="text-sm text-white">$199/mo</span>
          </div>
        )}
        {addOns.customApi && !activeVariants.some((t) => ADD_ONS.find(a => a.key === 'customApi')!.includedIn.includes(t)) && (
          <div className="flex items-center justify-between">
            <span className="text-sm text-orange-200/50">Custom API Connector</span>
            <span className="text-sm text-white">$49/mo</span>
          </div>
        )}

        {/* Integrations = $0 (D13) */}
        <div className="flex items-center justify-between">
          <span className="text-sm text-orange-200/50">Integrations</span>
          <span className="text-sm text-emerald-400">$0 (free)</span>
        </div>

        <div className="border-t border-white/[0.06] pt-3 flex items-center justify-between">
          <span className="text-sm font-semibold text-white">Total Monthly</span>
          <span className="text-lg font-bold text-orange-400">${totalMonthly.toLocaleString()}/mo</span>
        </div>

        {/* Overage rate info */}
        <div className="flex items-center justify-between">
          <span className="text-[10px] text-orange-200/25">Overage rate (beyond limits)</span>
          <span className="text-[10px] text-orange-200/25">${OVERAGE_PRICE_PER_TICKET}/ticket</span>
        </div>
      </div>

      {/* ── 5. Savings Comparison (D10 — reuse ROI Calculator logic) ──── */}
      <div
        className="rounded-xl border border-emerald-500/20 p-4"
        style={{ background: 'rgba(16,185,129,0.04)' }}
      >
        <div className="flex items-start gap-3">
          <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center shrink-0">
            <TrendingDown className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="flex-1">
            <p className="text-sm font-semibold text-emerald-400">
              Save {savings.savingsPercent}% vs human agents
            </p>
            <p className="text-[10px] text-orange-200/30 mt-1">
              PARWA handles {totalTicketLimit.toLocaleString()} tickets/mo — equivalent to{' '}
              {savings.agentsReplaced} full-time support agent{savings.agentsReplaced > 1 ? 's' : ''} at ~${AGENT_COST_MONTHLY.toLocaleString()}/mo each.
              That&apos;s ${savings.humanCost.toLocaleString()}/mo in human costs vs ${totalMonthly.toLocaleString()}/mo with PARWA.
            </p>
          </div>
        </div>
      </div>

      {/* ── No Hidden Fees (D13) ──────────────────────────────────────── */}
      <div className="flex items-center justify-center gap-2 text-[10px] text-orange-200/25">
        <Shield className="w-3 h-3" />
        <span>No hidden fees. Need more? Add another variant.</span>
      </div>

      {/* ── Error Display ────────────────────────────────────────────── */}
      {checkoutError && (
        <div className="rounded-xl border border-red-500/20 p-4 flex items-start gap-3" style={{ background: 'rgba(239,68,68,0.05)' }}>
          <AlertCircle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
          <p className="text-sm text-red-300">{checkoutError}</p>
        </div>
      )}

      {/* ── Proceed Button ────────────────────────────────────────────── */}
      <div className="flex justify-end">
        <button
          onClick={handleProceed}
          disabled={isSubmitting}
          className="px-8 py-3 bg-gradient-to-r from-orange-500 to-amber-400 hover:from-orange-400 hover:to-amber-300 text-[#1A1A1A] font-semibold rounded-xl transition-all duration-300 shadow-lg shadow-orange-500/25 text-sm flex items-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {isSubmitting ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Processing...
            </>
          ) : (
            <>
              Proceed to Checkout
              <ArrowRight className="w-4 h-4" />
            </>
          )}
        </button>
      </div>
    </div>
  );
}

export default CostBreakdownStep;
