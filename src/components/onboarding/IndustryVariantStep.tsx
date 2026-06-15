'use client';

import React, { useState, useEffect } from 'react';
import {
  Cloud,
  ShoppingCart,
  Truck,
  Layers,
  ArrowRight,
  CheckCircle2,
  Sparkles,
  Zap,
  Crown,
  Loader2,
} from 'lucide-react';
import { toast } from '@/lib/dynamic-toast';
import { cn } from '@/lib/utils';
import type { ParwaIndustry } from '@/lib/integration-catalog';
import { VARIANT_PRICES, VARIANT_LIMITS, VARIANT_AI_INFO } from '@/lib/pricing-config';

// ── Variant Types ──────────────────────────────────────────────────────

export type ParwaVariant = 'mini_parwa' | 'parwa' | 'parwa_high';

export interface PricingContext {
  industry: ParwaIndustry;
  variant: ParwaVariant;
  addOns: {
    voice: boolean;
    customApi: boolean;
  };
  totalMonthly: number;
  timestamp: string;
}

// ── Variant Display Map ────────────────────────────────────────────────

const VARIANT_DISPLAY: Record<ParwaVariant, {
  name: string;
  icon: React.ElementType;
  iconColor: string;
  price: number;
  priceLabel: string;
  tickets: number;
  pipeline: number;
  concurrent: number;
  customApi: boolean;
  openApi: boolean;
}> = {
  mini_parwa: {
    name: 'Mini PARWA',
    icon: Zap,
    iconColor: 'text-amber-400',
    price: VARIANT_PRICES.starter,
    priceLabel: `$${VARIANT_PRICES.starter.toLocaleString()}/mo`,
    tickets: VARIANT_LIMITS.starter.monthlyTickets,
    pipeline: VARIANT_AI_INFO.starter.pipelineSteps,
    concurrent: VARIANT_AI_INFO.starter.concurrentCalls,
    customApi: false,
    openApi: false,
  },
  parwa: {
    name: 'PARWA',
    icon: Sparkles,
    iconColor: 'text-orange-400',
    price: VARIANT_PRICES.growth,
    priceLabel: `$${VARIANT_PRICES.growth.toLocaleString()}/mo`,
    tickets: VARIANT_LIMITS.growth.monthlyTickets,
    pipeline: VARIANT_AI_INFO.growth.pipelineSteps,
    concurrent: VARIANT_AI_INFO.growth.concurrentCalls,
    customApi: true,
    openApi: false,
  },
  parwa_high: {
    name: 'PARWA High',
    icon: Crown,
    iconColor: 'text-yellow-400',
    price: VARIANT_PRICES.high,
    priceLabel: `$${VARIANT_PRICES.high.toLocaleString()}/mo`,
    tickets: VARIANT_LIMITS.high.monthlyTickets,
    pipeline: VARIANT_AI_INFO.high.pipelineSteps,
    concurrent: VARIANT_AI_INFO.high.concurrentCalls,
    customApi: true,
    openApi: true,
  },
};

const INDUSTRY_LABELS: Record<ParwaIndustry, { label: string; icon: React.ElementType; gradient: string }> = {
  saas: { label: 'SaaS', icon: Cloud, gradient: 'from-violet-500 to-violet-400' },
  ecommerce: { label: 'E-commerce', icon: ShoppingCart, gradient: 'from-emerald-500 to-emerald-400' },
  logistics: { label: 'Logistics', icon: Truck, gradient: 'from-amber-500 to-amber-400' },
  other: { label: 'Other', icon: Layers, gradient: 'from-rose-500 to-rose-400' },
};

// ── Props ──────────────────────────────────────────────────────────────

interface IndustryVariantStepProps {
  onComplete: (data: { industry: ParwaIndustry; variant: ParwaVariant }) => void;
}

// ── Component ──────────────────────────────────────────────────────────

export function IndustryVariantStep({ onComplete }: IndustryVariantStepProps) {
  const [pricingContext, setPricingContext] = useState<PricingContext | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Restore from localStorage — this was set on the models page
  useEffect(() => {
    try {
      const stored = localStorage.getItem('parwa_pricing_context');
      if (stored) {
        const ctx = JSON.parse(stored) as PricingContext;
        setPricingContext(ctx);
      }
    } catch {
      // ignore
    }
  }, []);

  const variant = pricingContext?.variant || 'parwa';
  const industry = pricingContext?.industry || 'other';
  const display = VARIANT_DISPLAY[variant];
  const industryInfo = INDUSTRY_LABELS[industry];
  const Icon = display.icon;
  const IndustryIcon = industryInfo.icon;

  const handleConfirm = async () => {
    setIsSubmitting(true);

    try {
      // POST to backend to save industry + variant selection
      const res = await fetch('/api/onboarding/industry-variant', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ industry, variant }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        if (errData.error === 'backend_unreachable') {
          console.warn('[industry-variant] Backend unreachable, continuing locally');
        } else {
          console.warn('[industry-variant] Backend returned', res.status, errData);
        }
        // Continue anyway — backend may not have this endpoint yet
      }

      toast.success(`${display.name} confirmed — let's set it up!`);
      onComplete({ industry, variant });
    } catch {
      toast.error('Something went wrong. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="text-center space-y-2">
        <div className="w-16 h-16 mx-auto rounded-2xl bg-gradient-to-br from-orange-500 to-amber-400 flex items-center justify-center shadow-xl shadow-orange-500/20 mb-4">
          <svg className="w-8 h-8" viewBox="0 0 40 40" fill="none">
            <path d="M6 7h24a4 4 0 014 4v13a4 4 0 01-4 4h-8l-3 6-2-6H6a4 4 0 01-4-4V11a4 4 0 014-4z" stroke="white" strokeWidth="2.8" strokeLinejoin="round" />
            <path d="M22 11l-6 8h4.5L17 28l8-10h-4.5l3.5-7z" fill="white" />
          </svg>
        </div>
        <h2 className="text-2xl sm:text-3xl font-bold text-white">Confirm Your Selection</h2>
        <p className="text-orange-200/50 text-sm max-w-md mx-auto">
          You selected this plan on the pricing page. Review and confirm to proceed with setup.
        </p>
      </div>

      {/* ── Read-Only Selection Summary ─────────────────────────────────── */}
      <div className="space-y-4">
        {/* Industry Card */}
        <div
          className="rounded-xl border border-orange-500/30 p-5"
          style={{ background: 'rgba(255,127,17,0.05)' }}
        >
          <p className="text-xs text-orange-200/40 uppercase tracking-wider font-medium mb-3">Your Industry</p>
          <div className="flex items-center gap-3">
            <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center bg-gradient-to-br', industryInfo.gradient)}>
              <IndustryIcon className="w-5 h-5 text-white" />
            </div>
            <span className="text-lg font-semibold text-orange-400">{industryInfo.label}</span>
          </div>
        </div>

        {/* Variant Card */}
        <div
          className="rounded-xl border border-orange-500/30 p-5"
          style={{ background: 'rgba(255,127,17,0.05)' }}
        >
          <p className="text-xs text-orange-200/40 uppercase tracking-wider font-medium mb-3">Your Plan</p>
          <div className="flex items-center gap-3 mb-4">
            <Icon className={cn('w-5 h-5', display.iconColor)} />
            <span className="text-lg font-semibold text-orange-400">{display.name}</span>
          </div>

          {/* Price */}
          <p className="text-3xl font-bold text-white mb-4">{display.priceLabel}</p>

          {/* Features */}
          <div className="grid grid-cols-2 gap-2">
            <FeatureRow label={`${display.pipeline}-step AI pipeline`} />
            <FeatureRow label={`${display.tickets.toLocaleString()} tickets/mo`} />
            <FeatureRow label={`${display.concurrent} concurrent AI calls`} />
            <FeatureRow label="Custom API" enabled={display.customApi} />
            <FeatureRow label="OpenAPI Import" enabled={display.openApi} />
          </div>
        </div>

        {/* Monthly total */}
        <div className="flex items-center justify-between p-4 rounded-xl border border-white/[0.06]" style={{ background: 'rgba(255,255,255,0.03)' }}>
          <span className="text-sm text-orange-200/50">Monthly Total</span>
          <span className="text-xl font-bold text-orange-400">${display.price.toLocaleString()}/mo</span>
        </div>
      </div>

      {/* ── Confirm Button ──────────────────────────────────────────── */}
      <div className="flex justify-end">
        <button
          onClick={handleConfirm}
          disabled={isSubmitting}
          className="px-8 py-3 font-semibold rounded-xl transition-all duration-300 text-sm flex items-center gap-2 bg-gradient-to-r from-orange-500 to-amber-400 hover:from-orange-400 hover:to-amber-300 text-[#1A1A1A] shadow-lg shadow-orange-500/25"
        >
          {isSubmitting ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Confirming...
            </>
          ) : (
            <>
              Confirm & Continue
              <ArrowRight className="w-4 h-4" />
            </>
          )}
        </button>
      </div>
    </div>
  );
}

// ── Helper: Feature Row ────────────────────────────────────────────────

function FeatureRow({ label, enabled = true }: { label: string; enabled?: boolean }) {
  return (
    <div className="flex items-center gap-1.5">
      {enabled ? (
        <CheckCircle2 className="w-3 h-3 text-emerald-400 shrink-0" />
      ) : (
        <div className="w-3 h-3 rounded-full border border-zinc-600 shrink-0" />
      )}
      <span className={cn(
        'text-xs',
        enabled ? 'text-orange-200/50' : 'text-zinc-600'
      )}>
        {label}
      </span>
    </div>
  );
}

export default IndustryVariantStep;
