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
  Brain,
  BarChart3,
  Check,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { cn } from '@/lib/utils';
import { openCheckoutWithItems, getPaddleInstance, VARIANT_PRICE_IDS } from '@/lib/paddle';
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
  normalizeTier,
  type VariantTier,
} from '@/lib/pricing-config';

// ── Onboarding variant → VariantTier mapping ────────────────────────

const ONBOARDING_TO_TIER: Record<ParwaVariant, VariantTier> = {
  mini_parwa: 'starter',
  parwa: 'growth',
  parwa_high: 'high',
};

const TIER_TO_ONBOARDING: Record<VariantTier, ParwaVariant> = {
  starter: 'mini_parwa',
  growth: 'parwa',
  high: 'parwa_high',
};

// ── Variant Display Data (sourced from pricing-config.ts) ──────────────

const VARIANT_DISPLAY: Record<VariantTier, {
  name: string;
  price: number;
  priceLabel: string;
  aiPipeline: number;
  ticketVolume: number;
  tagline: string;
}> = {
  starter: {
    name: VARIANT_DISPLAY_NAMES.starter,
    price: VARIANT_PRICES.starter,
    priceLabel: `$${VARIANT_PRICES.starter.toLocaleString()}/mo`,
    aiPipeline: VARIANT_AI_INFO.starter.pipelineSteps,
    ticketVolume: VARIANT_LIMITS.starter.monthlyTickets,
    tagline: VARIANT_AI_INFO.starter.techniques,
  },
  growth: {
    name: VARIANT_DISPLAY_NAMES.growth,
    price: VARIANT_PRICES.growth,
    priceLabel: `$${VARIANT_PRICES.growth.toLocaleString()}/mo`,
    aiPipeline: VARIANT_AI_INFO.growth.pipelineSteps,
    ticketVolume: VARIANT_LIMITS.growth.monthlyTickets,
    tagline: VARIANT_AI_INFO.growth.techniques,
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
    includedIn: ['growth', 'high'],
  },
  {
    key: 'customApi',
    name: 'Custom API Connector',
    description: 'Connect any REST API with custom auth and schema mapping.',
    price: 49,
    icon: Plug,
    includedIn: ['growth', 'high'],
  },
];

// ── Savings Calculation ──────────────────────────────────────────────────

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

// ── Variant Mixer Card ─────────────────────────────────────────────────

function VariantMixerCard({
  tier,
  isActive,
  quantity,
  onToggle,
  onQuantityChange,
}: {
  tier: VariantTier;
  isActive: boolean;
  quantity: number;
  onToggle: () => void;
  onQuantityChange: (qty: number) => void;
}) {
  const info = VARIANT_DISPLAY[tier];
  const limits = VARIANT_LIMITS[tier];
  const aiInfo = VARIANT_AI_INFO[tier];

  return (
    <div
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
            <button onClick={onToggle} className="focus:outline-none">
              <span className={cn(
                'text-sm font-semibold',
                isActive ? 'text-orange-400' : 'text-white'
              )}>
                {info.name}
              </span>
            </button>
            {isActive && (
              <span className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400">
                Active
              </span>
            )}
          </div>
        </div>
        <span className="text-base font-bold text-white">
          ${info.price.toLocaleString()}/mo
        </span>
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

      {/* Quantity selector when active, or add button when inactive */}
      {isActive ? (
        <div className="flex items-center gap-3">
          <span className="text-[10px] text-orange-200/30">Qty:</span>
          <button
            onClick={(e) => { e.stopPropagation(); onQuantityChange(quantity - 1); }}
            className="w-7 h-7 rounded-lg bg-white/5 border border-white/10 text-gray-400 hover:text-white hover:border-white/20 transition-all flex items-center justify-center text-sm"
          >−</button>
          <span className="text-sm font-bold text-white w-6 text-center">{quantity}</span>
          <button
            onClick={(e) => { e.stopPropagation(); onQuantityChange(quantity + 1); }}
            className="w-7 h-7 rounded-lg bg-white/5 border border-white/10 text-gray-400 hover:text-white hover:border-white/20 transition-all flex items-center justify-center text-sm"
          >+</button>
          <button
            onClick={onToggle}
            className="ml-auto px-3 py-1.5 rounded-lg text-[10px] font-medium bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500/20 transition-all flex items-center gap-1"
          >
            <Minus className="w-3 h-3" /> Remove
          </button>
        </div>
      ) : (
        <button
          onClick={onToggle}
          className="w-full h-8 rounded-lg flex items-center justify-center gap-1.5 text-xs font-medium transition-all bg-gradient-to-r from-orange-500 to-amber-400 text-[#1A1A1A] shadow-lg shadow-orange-500/20"
        >
          <Plus className="w-3.5 h-3.5" /> Add Variant
        </button>
      )}
    </div>
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
  const initialTier = ONBOARDING_TO_TIER[variant] || 'growth';
  const [activeVariants, setActiveVariants] = useState<VariantTier[]>([initialTier]);
  const [variantQuantities, setVariantQuantities] = useState<Record<VariantTier, number>>({ starter: 1, growth: 1, high: 1 });
  const [addOns, setAddOns] = useState<{ voice: boolean; customApi: boolean }>({ voice: false, customApi: false });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [paddleStatus, setPaddleStatus] = useState<'unknown' | 'ready' | 'unavailable'>('unknown');
  const [checkoutError, setCheckoutError] = useState<string | null>(null);
  const [paymentConfirmed, setPaymentConfirmed] = useState(false);

  // Restore add-ons and multi-variant selections from localStorage
  useEffect(() => {
    try {
      const stored = localStorage.getItem('parwa_pricing_context');
      if (stored) {
        const ctx = JSON.parse(stored) as PricingContext & {
          selectedVariants?: string[];
          variantQuantities?: Record<string, number>;
        };
        if (ctx.addOns) {
          setAddOns(ctx.addOns);
        }
        // Restore multiple variants if selected on Pricing page
        if (ctx.selectedVariants && Array.isArray(ctx.selectedVariants) && ctx.selectedVariants.length > 0) {
          const tiers: VariantTier[] = ctx.selectedVariants
            .map((v: string) => {
              const normalized = normalizeTier(v);
              return ['starter', 'growth', 'high'].includes(normalized) ? normalized as VariantTier : null;
            })
            .filter(Boolean) as VariantTier[];
          if (tiers.length > 0) {
            setActiveVariants(tiers);
          }
        }
        // Restore variant quantities
        if (ctx.variantQuantities && typeof ctx.variantQuantities === 'object') {
          const qtyMap: Record<string, number> = ctx.variantQuantities;
          const newQuantities = { ...variantQuantities };
          for (const [variantKey, qty] of Object.entries(qtyMap)) {
            const tier = normalizeTier(variantKey);
            if (['starter', 'growth', 'high'].includes(tier)) {
              newQuantities[tier as VariantTier] = Math.max(1, Math.min(qty as number, 10));
            }
          }
          setVariantQuantities(newQuantities);
        }
      }
    } catch {
      // ignore
    }
  }, []);

  // Check if Paddle.js is available
  useEffect(() => {
    getPaddleInstance().then((paddle) => {
      setPaddleStatus(paddle ? 'ready' : 'unavailable');
    }).catch(() => {
      setPaddleStatus('unavailable');
    });
  }, []);

  // ── Calculations ──────────────────────────────────────────────────

  const totalTicketLimit = useMemo(
    () => activeVariants.reduce((sum, tier) => sum + (VARIANT_LIMITS[tier].monthlyTickets * (variantQuantities[tier] || 1)), 0),
    [activeVariants, variantQuantities]
  );

  const baseSubscription = useMemo(
    () => activeVariants.reduce((sum, tier) => sum + (VARIANT_PRICES[tier] * (variantQuantities[tier] || 1)), 0),
    [activeVariants, variantQuantities]
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

  const updateQuantity = (tier: VariantTier, qty: number) => {
    const newQty = Math.max(1, Math.min(qty, 10));
    setVariantQuantities((prev) => ({ ...prev, [tier]: newQty }));
  };

  const toggleAddOn = (key: 'voice' | 'customApi') => {
    setAddOns((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  // ── Payment success handler — ONLY called after Paddle confirms ──
  const handlePaymentSuccess = () => {
    setPaymentConfirmed(true);
    localStorage.removeItem('parwa_payment_pending');
    toast.success('Payment successful! Welcome to PARWA!');
    // Only trigger onboarding completion AFTER Paddle confirms
    onComplete();
  };

  const handleProceed = async () => {
    setIsSubmitting(true);
    setCheckoutError(null);

    try {
      // Update pricing context in localStorage
      const primaryOnboardingVariant = TIER_TO_ONBOARDING[activeVariants[0]] || 'parwa';
      const context: PricingContext = {
        industry: 'other',
        variant: primaryOnboardingVariant,
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

      // ── Paddle Checkout Flow ──────────────────────────────────────
      const checkoutItems: Array<{ priceId: string; quantity: number }> = [];

      // Add each active variant as a Paddle line item (with quantity)
      for (const tier of activeVariants) {
        const onboardingVariant = TIER_TO_ONBOARDING[tier];
        const variantPriceId = VARIANT_PRICE_IDS[onboardingVariant];
        const qty = variantQuantities[tier] || 1;
        if (variantPriceId) {
          checkoutItems.push({ priceId: variantPriceId, quantity: qty });
        }
      }

      // Voice add-on is included in growth/high — NOT purchasable separately
      // (no Paddle price ID exists for standalone add-on purchases)

      // Custom API add-on is included in growth/high — NOT purchasable separately
      // (no Paddle price ID exists for standalone add-on purchases)

      const customData = {
        source: 'parwa_onboarding',
        variant: primaryOnboardingVariant,
        activeVariants: activeVariants.map((t) => TIER_TO_ONBOARDING[t]),
        variantQuantities,
        addOns,
        industry: context.industry,
        totalMonthly,
      };

      // ── Step 1: Try server-side checkout (backend creates Paddle transaction) ──
      let checkoutUrl: string | null = null;

      try {
        const res = await fetch('/api/onboarding/checkout', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            variant: primaryOnboardingVariant,
            activeVariants: activeVariants.map((t) => TIER_TO_ONBOARDING[t]),
            variantQuantities,
            addOns,
            totalMonthly,
            industry: context.industry,
          }),
        });

        if (res.ok) {
          const checkoutData = await res.json();
          checkoutUrl = checkoutData.checkout_url || null;
        }
      } catch {
        // API unavailable — continue with client-side Paddle checkout
      }

      // If we got a checkout_url from backend, redirect to it
      if (checkoutUrl) {
        localStorage.setItem('parwa_payment_pending', JSON.stringify({
          activeVariants, addOns, totalMonthly, variantQuantities,
          pendingAt: new Date().toISOString(),
        }));
        window.location.href = checkoutUrl;
        return;
      }

      // ── Step 2: Client-side Paddle checkout (items-based overlay) ──
      const paddle = await getPaddleInstance();

      if (paddle && checkoutItems.length > 0) {
        setPaddleStatus('ready');
        const opened = await openCheckoutWithItems(
          checkoutItems,
          customData,
          // onPaymentSuccess — ONLY triggers after Paddle confirms the transaction
          handlePaymentSuccess,
          // onCheckoutClosed — user closed without paying
          () => {
            toast('Checkout closed — payment is required to activate your plan.', { icon: '⚠️' });
            setIsSubmitting(false);
          },
        );

        if (opened) {
          return; // Paddle overlay is showing — wait for user to complete or close
        }
      }

      // ── Step 3: Paddle unavailable — try re-initializing ──
      try {
        const retryPaddle = await getPaddleInstance();
        if (retryPaddle && checkoutItems.length > 0) {
          setPaddleStatus('ready');
          const opened = await openCheckoutWithItems(
            checkoutItems,
            customData,
            handlePaymentSuccess,
            () => {
              toast('Checkout closed — payment is required to activate your plan.', { icon: '⚠️' });
              setIsSubmitting(false);
            },
          );
          if (opened) return;
        }
      } catch {
        // Paddle truly unavailable
      }

      // ── Step 4: Paddle unavailable — block with error ──
      setPaddleStatus('unavailable');
      localStorage.setItem('parwa_payment_pending', JSON.stringify({
        activeVariants, addOns, totalMonthly, variantQuantities,
        pendingAt: new Date().toISOString(),
      }));
      setCheckoutError(
        'Payment gateway is currently unavailable. Your plan configuration has been saved. ' +
        'Please refresh the page and try again, or contact support@parwa.buzz to complete your subscription.'
      );
      toast.error('Payment gateway unavailable — please try again or contact support.');
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
        <h2 className="text-2xl font-bold text-white">Review & Pay</h2>
        <p className="text-orange-200/40 text-sm">
          Configure your plan and complete payment to activate your AI agents.
        </p>
      </div>

      {/* ── Paddle Status Indicator ─────────────────────────────────── */}
      {paddleStatus === 'unavailable' && (
        <div className="rounded-xl border border-amber-500/20 p-4 flex items-start gap-3" style={{ background: 'rgba(245,158,11,0.05)' }}>
          <AlertCircle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-amber-300">Payment checkout unavailable</p>
            <p className="text-[10px] text-orange-200/30 mt-1">
              Paddle payment gateway is not configured. Your configuration will be saved and you can complete payment later.
            </p>
          </div>
        </div>
      )}
      {paddleStatus === 'ready' && (
        <div className="rounded-xl border border-emerald-500/20 p-3 flex items-center gap-2" style={{ background: 'rgba(16,185,129,0.04)' }}>
          <Shield className="w-4 h-4 text-emerald-400" />
          <p className="text-xs text-emerald-400">Secure checkout powered by Paddle</p>
          <ExternalLink className="w-3 h-3 text-emerald-400/60 ml-auto" />
        </div>
      )}

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
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {(['starter', 'growth', 'high'] as VariantTier[]).map((tier) => (
            <VariantMixerCard
              key={tier}
              tier={tier}
              isActive={activeVariants.includes(tier)}
              quantity={variantQuantities[tier] || 1}
              onToggle={() => toggleVariant(tier)}
              onQuantityChange={(qty) => updateQuantity(tier, qty)}
            />
          ))}
        </div>
      </div>

      {/* ── 2. Add-Ons ───────────────────────────────────────────────── */}
      <div className="space-y-3">
        <label className="text-xs text-orange-200/40 uppercase tracking-wider font-medium">
          Add-On Features
        </label>
        {ADD_ONS.map((addOn) => {
          const Icon = addOn.icon;
          const isIncluded = activeVariants.some((t) => addOn.includedIn.includes(t));
          // Add-ons are NOT purchasable separately — only included with growth/high plans
          const isLocked = !isIncluded;

          return (
            <div
              key={addOn.key}
              className={cn(
                'w-full text-left p-4 rounded-xl border transition-all duration-200 flex items-start gap-4',
                isIncluded
                  ? 'border-emerald-500/20 bg-emerald-500/[0.03]'
                  : 'border-white/[0.06]'
              )}
              style={!isIncluded ? { background: 'rgba(255,255,255,0.03)' } : undefined}
            >
              <div className={cn(
                'w-10 h-10 rounded-lg flex items-center justify-center shrink-0',
                isIncluded ? 'bg-emerald-500/10' : 'bg-white/[0.04]'
              )}>
                <Icon className={cn(
                  'w-5 h-5',
                  isIncluded ? 'text-emerald-400' : 'text-zinc-500'
                )} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <p className={cn(
                    'text-sm font-medium',
                    isIncluded ? 'text-emerald-400' : 'text-white'
                  )}>
                    {addOn.name}
                  </p>
                  {isIncluded && (
                    <span className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400">
                      Included
                    </span>
                  )}
                </div>
                <p className="text-[10px] text-orange-200/30 mt-0.5">
                  {isIncluded ? addOn.description : `Included with PARWA and PARWA High plans`}
                </p>
              </div>
              <div className="flex flex-col items-end shrink-0 gap-1">
                {isIncluded ? (
                  <div className="w-8 h-5 rounded-full flex items-center px-0.5 bg-gradient-to-r from-orange-500 to-amber-400">
                    <div className="w-4 h-4 rounded-full bg-white shadow-sm translate-x-3" />
                  </div>
                ) : (
                  <span className="text-[10px] text-orange-200/25 italic">Upgrade required</span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* ── 3. Cost Summary ────────────────────────────────────────────── */}
      <div
        className="rounded-xl border border-white/[0.08] p-5 space-y-3"
        style={{ background: 'rgba(255,255,255,0.03)' }}
      >
        {/* Per-variant breakdown */}
        {activeVariants.map((tier) => {
          const qty = variantQuantities[tier] || 1;
          const price = VARIANT_PRICES[tier] * qty;

          return (
            <div key={tier} className="flex items-center justify-between">
              <span className="text-sm text-orange-200/50 flex items-center gap-1.5">
                <div className={cn(
                  'w-2 h-2 rounded-full',
                  tier === 'starter' ? 'bg-emerald-400' : tier === 'growth' ? 'bg-orange-400' : 'bg-purple-400'
                )} />
                {VARIANT_DISPLAY[tier].name}
                {qty > 1 && <span className="text-orange-200/30"> × {qty}</span>}
              </span>
              <span className="text-sm text-white">
                ${price.toLocaleString()}/mo
              </span>
            </div>
          );
        })}

        {/* Add-ons — shown as included, not separately priced */}

        {/* Integrations = $0 */}
        <div className="flex items-center justify-between">
          <span className="text-sm text-orange-200/50">Integrations</span>
          <span className="text-sm text-emerald-400">$0 (free)</span>
        </div>

        <div className="border-t border-white/[0.06] pt-3 flex items-center justify-between">
          <span className="text-sm font-semibold text-white">Total Monthly</span>
          <span className="text-lg font-bold text-orange-400">
            ${totalMonthly.toLocaleString()}/mo
          </span>
        </div>

        {/* Overage rate info */}
        <div className="flex items-center justify-between">
          <span className="text-[10px] text-orange-200/25">Overage rate (beyond limits)</span>
          <span className="text-[10px] text-orange-200/25">${OVERAGE_PRICE_PER_TICKET}/ticket</span>
        </div>
      </div>

      {/* ── 4. Savings Comparison ──────────────────────────────────────── */}
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

      {/* ── No Hidden Fees ─────────────────────────────────────────────── */}
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

      {/* ── Payment Confirmation Guard ──────────────────────────────── */}
      {paymentConfirmed && (
        <div className="rounded-xl border border-emerald-500/30 p-4 flex items-start gap-3" style={{ background: 'rgba(16,185,129,0.08)' }}>
          <Shield className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-emerald-300">Payment confirmed by Paddle</p>
            <p className="text-[10px] text-orange-200/30 mt-1">
              Your subscription is now active. Redirecting to your dashboard...
            </p>
          </div>
        </div>
      )}

      {/* ── Proceed Button ────────────────────────────────────────────── */}
      <div className="flex justify-end">
        <button
          onClick={handleProceed}
          disabled={isSubmitting || paymentConfirmed}
          className={cn(
            'px-8 py-3 font-semibold rounded-xl transition-all duration-300 shadow-lg text-sm flex items-center gap-2 disabled:cursor-not-allowed',
            'bg-gradient-to-r from-orange-500 to-amber-400 hover:from-orange-400 hover:to-amber-300 text-[#1A1A1A] shadow-orange-500/25',
            (isSubmitting || paymentConfirmed) && 'opacity-60'
          )}
        >
          {isSubmitting ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Opening Checkout...
            </>
          ) : paymentConfirmed ? (
            <>
              <Shield className="w-4 h-4" />
              Activated — Redirecting...
            </>
          ) : (
            <>
              Pay ${totalMonthly.toLocaleString()}/mo & Activate
              <ArrowRight className="w-4 h-4" />
            </>
          )}
        </button>
      </div>
    </div>
  );
}

export default CostBreakdownStep;
