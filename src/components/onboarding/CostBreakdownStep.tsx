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
} from 'lucide-react';
import toast from 'react-hot-toast';
import { cn } from '@/lib/utils';
import type { ParwaVariant } from './IndustryVariantStep';
import type { PricingContext } from './IndustryVariantStep';

// ── Variant Display Data ───────────────────────────────────────────────

const VARIANT_DISPLAY: Record<ParwaVariant, {
  name: string;
  price: number;
  priceLabel: string;
  aiPipeline: number;
  ticketVolume: number;
}> = {
  mini_parwa: { name: 'Mini PARWA', price: 999, priceLabel: '$999/mo', aiPipeline: 3, ticketVolume: 500 },
  parwa: { name: 'PARWA', price: 2499, priceLabel: '$2,499/mo', aiPipeline: 6, ticketVolume: 2000 },
  parwa_high: { name: 'PARWA High', price: 4999, priceLabel: '$4,999/mo', aiPipeline: 9, ticketVolume: 10000 },
};

// ── Add-Ons ────────────────────────────────────────────────────────────

interface AddOn {
  key: 'voice' | 'customApi';
  name: string;
  description: string;
  price: number;
  icon: React.ElementType;
  /** Which variants already include this feature (no extra charge) */
  includedIn: ParwaVariant[];
}

const ADD_ONS: AddOn[] = [
  {
    key: 'voice',
    name: 'Voice Channel',
    description: 'AI-powered inbound & outbound voice calls with real-time transcription.',
    price: 199,
    icon: Mic,
    includedIn: [],
  },
  {
    key: 'customApi',
    name: 'Custom API Connector',
    description: 'Connect any REST API with custom auth and schema mapping.',
    price: 49,
    icon: Plug,
    includedIn: ['parwa', 'parwa_high'],
  },
];

// ── Savings Calculation ────────────────────────────────────────────────
// Average US support agent: ~$3,500/mo salary + overhead ≈ $4,500/mo total cost
// PARWA handles tickets equivalent to N agents depending on volume

const AGENT_COST_MONTHLY = 4500;

function estimateSavings(ticketVolume: number, monthlyCost: number): {
  agentsReplaced: number;
  humanCost: number;
  savings: number;
  savingsPercent: number;
} {
  // Conservative: 1 agent handles ~400 tickets/mo
  const ticketsPerAgent = 400;
  const agentsReplaced = Math.max(1, Math.round(ticketVolume / ticketsPerAgent));
  const humanCost = agentsReplaced * AGENT_COST_MONTHLY;
  const savings = Math.max(0, humanCost - monthlyCost);
  const savingsPercent = humanCost > 0 ? Math.round((savings / humanCost) * 100) : 0;
  return { agentsReplaced, humanCost, savings, savingsPercent };
}

// ── Props ──────────────────────────────────────────────────────────────

interface CostBreakdownStepProps {
  variant: ParwaVariant;
  onComplete: () => void;
}

// ── Component ──────────────────────────────────────────────────────────

export function CostBreakdownStep({ variant, onComplete }: CostBreakdownStepProps) {
  const [addOns, setAddOns] = useState<{ voice: boolean; customApi: boolean }>({ voice: false, customApi: false });
  const [isSubmitting, setIsSubmitting] = useState(false);

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

  const variantInfo = VARIANT_DISPLAY[variant];

  // Calculate total monthly cost
  const addOnTotal = useMemo(() => {
    let total = 0;
    if (addOns.voice) {
      const voiceAddOn = ADD_ONS.find((a) => a.key === 'voice')!;
      if (!voiceAddOn.includedIn.includes(variant)) {
        total += voiceAddOn.price;
      }
    }
    if (addOns.customApi) {
      const customApiAddOn = ADD_ONS.find((a) => a.key === 'customApi')!;
      if (!customApiAddOn.includedIn.includes(variant)) {
        total += customApiAddOn.price;
      }
    }
    return total;
  }, [addOns, variant]);

  const totalMonthly = variantInfo.price + addOnTotal;
  const savings = estimateSavings(variantInfo.ticketVolume, totalMonthly);

  const toggleAddOn = (key: 'voice' | 'customApi') => {
    setAddOns((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const handleProceed = async () => {
    setIsSubmitting(true);

    try {
      // Update pricing context in localStorage
      const context: PricingContext = {
        industry: 'other', // will be overwritten from existing context
        variant,
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

      // POST to backend (fire-and-forget)
      try {
        await fetch('/api/onboarding/checkout', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            variant,
            addOns,
            totalMonthly,
          }),
        });
      } catch {
        // API unavailable — continue with local state
      }

      toast.success('Configuration saved — proceeding to checkout!');
      onComplete();
    } catch {
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
          Confirm your configuration and add any optional channels before going live.
        </p>
      </div>

      {/* ── Selected Variant Summary ──────────────────────────────────── */}
      <div
        className="rounded-xl border border-orange-500/20 p-5"
        style={{ background: 'rgba(255,127,17,0.04)' }}
      >
        <div className="flex items-center justify-between mb-4">
          <div>
            <p className="text-xs text-orange-200/40 uppercase tracking-wider">Selected Plan</p>
            <p className="text-lg font-bold text-white mt-0.5">{variantInfo.name}</p>
          </div>
          <p className="text-xl font-bold text-orange-400">{variantInfo.priceLabel}</p>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-lg p-3" style={{ background: 'rgba(255,255,255,0.03)' }}>
            <p className="text-[10px] text-orange-200/30 uppercase tracking-wider">AI Pipeline</p>
            <p className="text-sm font-semibold text-white mt-0.5">{variantInfo.aiPipeline}-step</p>
          </div>
          <div className="rounded-lg p-3" style={{ background: 'rgba(255,255,255,0.03)' }}>
            <p className="text-[10px] text-orange-200/30 uppercase tracking-wider">Ticket Volume</p>
            <p className="text-sm font-semibold text-white mt-0.5">{variantInfo.ticketVolume.toLocaleString()}/mo</p>
          </div>
        </div>
      </div>

      {/* ── Add-Ons ───────────────────────────────────────────────────── */}
      <div className="space-y-3">
        <label className="text-xs text-orange-200/40 uppercase tracking-wider font-medium">
          Optional Add-Ons
        </label>
        {ADD_ONS.map((addOn) => {
          const Icon = addOn.icon;
          const isSelected = addOns[addOn.key];
          const isIncluded = addOn.includedIn.includes(variant);
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
              {/* Icon */}
              <div className={cn(
                'w-10 h-10 rounded-lg flex items-center justify-center shrink-0',
                isSelected ? 'bg-orange-500/10' : 'bg-white/[0.04]'
              )}>
                <Icon className={cn(
                  'w-5 h-5',
                  isSelected ? 'text-orange-400' : 'text-zinc-500'
                )} />
              </div>

              {/* Text */}
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

              {/* Price & Toggle */}
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

      {/* ── Cost Summary ──────────────────────────────────────────────── */}
      <div
        className="rounded-xl border border-white/[0.08] p-5 space-y-3"
        style={{ background: 'rgba(255,255,255,0.03)' }}
      >
        <div className="flex items-center justify-between">
          <span className="text-sm text-orange-200/50">{variantInfo.name}</span>
          <span className="text-sm text-white">${variantInfo.price.toLocaleString()}/mo</span>
        </div>
        {addOns.voice && !ADD_ONS.find((a) => a.key === 'voice')!.includedIn.includes(variant) && (
          <div className="flex items-center justify-between">
            <span className="text-sm text-orange-200/50">Voice Channel</span>
            <span className="text-sm text-white">$199/mo</span>
          </div>
        )}
        {addOns.customApi && !ADD_ONS.find((a) => a.key === 'customApi')!.includedIn.includes(variant) && (
          <div className="flex items-center justify-between">
            <span className="text-sm text-orange-200/50">Custom API Connector</span>
            <span className="text-sm text-white">$49/mo</span>
          </div>
        )}
        <div className="border-t border-white/[0.06] pt-3 flex items-center justify-between">
          <span className="text-sm font-semibold text-white">Total Monthly</span>
          <span className="text-lg font-bold text-orange-400">${totalMonthly.toLocaleString()}/mo</span>
        </div>
      </div>

      {/* ── Savings Comparison ────────────────────────────────────────── */}
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
              PARWA handles {variantInfo.ticketVolume.toLocaleString()} tickets/mo — equivalent to{' '}
              {savings.agentsReplaced} full-time support agent{savings.agentsReplaced > 1 ? 's' : ''} at ~$4,500/mo each.
              That&apos;s ${savings.humanCost.toLocaleString()}/mo in human costs vs ${totalMonthly.toLocaleString()}/mo with PARWA.
            </p>
          </div>
        </div>
      </div>

      {/* ── No Hidden Fees ────────────────────────────────────────────── */}
      <div className="flex items-center justify-center gap-2 text-[10px] text-orange-200/25">
        <Shield className="w-3 h-3" />
        <span>No hidden fees. Need more? Add another variant.</span>
      </div>

      {/* ── Proceed Button ────────────────────────────────────────────── */}
      <div className="flex justify-end">
        <button
          onClick={handleProceed}
          disabled={isSubmitting}
          className="px-8 py-3 bg-gradient-to-r from-orange-500 to-amber-400 hover:from-orange-400 hover:to-amber-300 text-[#1A1A1A] font-semibold rounded-xl transition-all duration-300 shadow-lg shadow-orange-500/25 text-sm flex items-center gap-2"
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
