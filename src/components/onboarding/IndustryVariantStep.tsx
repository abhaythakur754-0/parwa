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
  Crown,
  Loader2,
  X,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { cn } from '@/lib/utils';
import type { ParwaIndustry } from '@/lib/integration-catalog';

// ── Variant Types ──────────────────────────────────────────────────────

export type ParwaVariant = 'parwa' | 'high';

export interface VariantDefinition {
  key: ParwaVariant;
  name: string;
  price: number;
  priceLabel: string;
  aiPipeline: number;
  ticketVolume: number;
  customApi: boolean;
  openApiImport: boolean;
  concurrentAiCalls: number;
  description: string;
  badge?: string;
}

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

// ── Variant Definitions (D5) — prices from /src/lib/pricing-config.ts ─────

import { VARIANT_PRICES, VARIANT_AI_INFO, VARIANT_LIMITS } from '@/lib/pricing-config';

const VARIANTS: VariantDefinition[] = [
  {
    key: 'parwa',
    name: 'PARWA',
    price: VARIANT_PRICES.parwa,
    priceLabel: `$${VARIANT_PRICES.parwa.toLocaleString()}/mo`,
    aiPipeline: VARIANT_AI_INFO.parwa.pipelineSteps,
    ticketVolume: VARIANT_LIMITS.parwa.monthlyTickets,
    customApi: true,
    openApiImport: false,
    concurrentAiCalls: VARIANT_AI_INFO.parwa.concurrentCalls,
    description: 'For growing businesses that need more power and flexibility.',
    badge: 'Popular',
  },
  {
    key: 'high',
    name: 'PARWA High',
    price: VARIANT_PRICES.high,
    priceLabel: `$${VARIANT_PRICES.high.toLocaleString()}/mo`,
    aiPipeline: VARIANT_AI_INFO.high.pipelineSteps,
    ticketVolume: VARIANT_LIMITS.high.monthlyTickets,
    customApi: true,
    openApiImport: true,
    concurrentAiCalls: VARIANT_AI_INFO.high.concurrentCalls,
    description: 'Enterprise-grade AI support with unlimited potential.',
    badge: 'Enterprise',
  },
];

// ── Industry Options (D1 — 4 industries) ───────────────────────────────

const INDUSTRY_OPTIONS: Array<{
  value: ParwaIndustry;
  label: string;
  description: string;
  icon: React.ElementType;
  colorGradient: string;
}> = [
  {
    value: 'saas',
    label: 'SaaS',
    description: 'Software & technology companies',
    icon: Cloud,
    colorGradient: 'from-violet-500 to-violet-400',
  },
  {
    value: 'ecommerce',
    label: 'E-commerce',
    description: 'Online stores & retail',
    icon: ShoppingCart,
    colorGradient: 'from-emerald-500 to-emerald-400',
  },
  {
    value: 'logistics',
    label: 'Logistics',
    description: 'Shipping, freight & supply chain',
    icon: Truck,
    colorGradient: 'from-amber-500 to-amber-400',
  },
  {
    value: 'other',
    label: 'Other',
    description: 'All integrations available',
    icon: Layers,
    colorGradient: 'from-rose-500 to-rose-400',
  },
];

// ── Props ──────────────────────────────────────────────────────────────

interface IndustryVariantStepProps {
  onComplete: (data: { industry: ParwaIndustry; variant: ParwaVariant }) => void;
}

// ── Component ──────────────────────────────────────────────────────────

export function IndustryVariantStep({ onComplete }: IndustryVariantStepProps) {
  const [industry, setIndustry] = useState<ParwaIndustry | null>(null);
  const [variant, setVariant] = useState<ParwaVariant | null>(null);
  const [uniqueId, setUniqueId] = useState('');
  const [uniqueIdChecked, setUniqueIdChecked] = useState<boolean | null>(null);
  const [uniqueIdChecking, setUniqueIdChecking] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Restore from localStorage if available
  useEffect(() => {
    try {
      const stored = localStorage.getItem('parwa_pricing_context');
      if (stored) {
        const ctx = JSON.parse(stored) as PricingContext;
        if (ctx.industry) setIndustry(ctx.industry);
        if (ctx.variant) setVariant(ctx.variant);
      }
    } catch {
      // ignore
    }
  }, []);

  // Check unique_id availability (debounced)
  useEffect(() => {
    if (!uniqueId || uniqueId.length < 3) {
      setUniqueIdChecked(null);
      return;
    }
    const cleaned = uniqueId.trim().toLowerCase().replace(/\s+/g, '-');
    setUniqueIdChecking(true);
    const timer = setTimeout(async () => {
      try {
        const res = await fetch(`/api/onboarding/check-unique-id?unique_id=${encodeURIComponent(cleaned)}`, {
          credentials: 'include',
        });
        if (res.ok) {
          const data = await res.json();
          setUniqueIdChecked(data.available === true);
        } else {
          setUniqueIdChecked(null);
        }
      } catch {
        setUniqueIdChecked(null);
      } finally {
        setUniqueIdChecking(false);
      }
    }, 500);
    return () => clearTimeout(timer);
  }, [uniqueId]);

  const handleContinue = async () => {
    if (!industry || !variant) {
      toast.error('Please select an industry and variant');
      return;
    }

    const cleanedUniqueId = uniqueId.trim().toLowerCase().replace(/\s+/g, '-');
    if (!cleanedUniqueId || cleanedUniqueId.length < 3) {
      toast.error('Please enter a unique ID (at least 3 characters)');
      return;
    }
    if (uniqueIdChecked === false) {
      toast.error('This unique ID is already taken. Please choose another.');
      return;
    }

    setIsSubmitting(true);

    try {
      // Save pricing context to localStorage
      const selectedVariant = VARIANTS.find((v) => v.key === variant)!;
      const context: PricingContext = {
        industry,
        variant,
        addOns: { voice: false, customApi: false },
        totalMonthly: selectedVariant.price,
        timestamp: new Date().toISOString(),
      };
      localStorage.setItem('parwa_pricing_context', JSON.stringify(context));

      // POST to backend — send unique_id with industry + variant
      const res = await fetch('/api/onboarding/industry-variant', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ industry, variant, unique_id: cleanedUniqueId }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        if (errData.error === 'backend_unreachable') {
          toast.error('Backend is not available. Please try again later.');
          setIsSubmitting(false);
          return;
        }
        // Non-503 error (e.g. 400, 409) — backend is reachable but rejected
        console.warn('[industry-variant] Backend returned', res.status, errData);
        // Continue anyway — backend may not have this endpoint yet
      }

      toast.success(`${selectedVariant.name} selected — let's set it up!`);
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
        <h2 className="text-2xl sm:text-3xl font-bold text-white">Welcome to PARWA</h2>
        <p className="text-orange-200/50 text-sm max-w-md mx-auto">
          Configure your AI-powered customer support. Choose your industry and plan to get started.
        </p>
      </div>

      {/* ── Unique ID Input ──────────────────────────────────────────── */}
      <div className="space-y-2">
        <label className="text-xs text-orange-200/40 uppercase tracking-wider font-medium">
          Choose your Unique ID
        </label>
        <div className="relative">
          <input
            type="text"
            value={uniqueId}
            onChange={(e) => { setUniqueId(e.target.value); setUniqueIdChecked(null); }}
            placeholder="e.g. acme-support"
            maxLength={50}
            className="w-full px-4 py-3 rounded-xl bg-white/[0.03] border border-white/[0.08] text-white placeholder:text-zinc-600 focus:outline-none focus:border-orange-500/40 focus:ring-1 focus:ring-orange-500/20 transition-colors"
          />
          {uniqueIdChecking && (
            <div className="absolute inset-y-0 right-3 flex items-center">
              <Loader2 className="w-4 h-4 text-zinc-500 animate-spin" />
            </div>
          )}
          {!uniqueIdChecking && uniqueIdChecked === true && (
            <div className="absolute inset-y-0 right-3 flex items-center">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            </div>
          )}
          {!uniqueIdChecking && uniqueIdChecked === false && (
            <div className="absolute inset-y-0 right-3 flex items-center">
              <X className="w-4 h-4 text-red-400" />
            </div>
          )}
        </div>
        {uniqueIdChecked === true && (
          <p className="text-xs text-emerald-400">✓ Available</p>
        )}
        {uniqueIdChecked === false && (
          <p className="text-xs text-red-400">✗ Already taken. Try another.</p>
        )}
        {uniqueId && uniqueId.length < 3 && (
          <p className="text-xs text-zinc-600">At least 3 characters required</p>
        )}
        <p className="text-[10px] text-zinc-600">
          This ID will be shown on your dashboard. Letters, numbers, and hyphens only.
        </p>
      </div>

      {/* ── Industry Selection ───────────────────────────────────────── */}
      <div className="space-y-3">
        <label className="text-xs text-orange-200/40 uppercase tracking-wider font-medium">
          1. What&apos;s your industry?
        </label>
        <div className="grid grid-cols-2 gap-3">
          {INDUSTRY_OPTIONS.map((opt) => {
            const Icon = opt.icon;
            const isSelected = industry === opt.value;

            return (
              <button
                key={opt.value}
                type="button"
                onClick={() => setIndustry(opt.value)}
                className={cn(
                  'relative text-left p-4 rounded-xl border transition-all duration-200 group',
                  isSelected
                    ? 'border-orange-500/40 bg-orange-500/5'
                    : 'border-white/[0.06] hover:border-orange-500/20'
                )}
                style={!isSelected ? { background: 'rgba(255,255,255,0.03)' } : undefined}
              >
                {/* Check indicator */}
                {isSelected && (
                  <div className="absolute top-2 right-2">
                    <CheckCircle2 className="w-4 h-4 text-orange-400" />
                  </div>
                )}
                <div className={cn(
                  'w-9 h-9 rounded-lg flex items-center justify-center mb-2.5 bg-gradient-to-br',
                  opt.colorGradient,
                  !isSelected && 'opacity-60 group-hover:opacity-80 transition-opacity'
                )}>
                  <Icon className="w-4.5 h-4.5 text-white" />
                </div>
                <p className={cn(
                  'text-sm font-medium',
                  isSelected ? 'text-orange-400' : 'text-white'
                )}>
                  {opt.label}
                </p>
                <p className="text-[10px] text-orange-200/30 mt-0.5">
                  {opt.description}
                </p>
              </button>
            );
          })}
        </div>
      </div>

      {/* ── Variant Selection ────────────────────────────────────────── */}
      <div className="space-y-3">
        <label className="text-xs text-orange-200/40 uppercase tracking-wider font-medium">
          2. Choose your plan
        </label>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {VARIANTS.map((v) => {
            const isSelected = variant === v.key;

            return (
              <button
                key={v.key}
                type="button"
                onClick={() => setVariant(v.key)}
                className={cn(
                  'relative text-left p-4 rounded-xl border transition-all duration-200 group',
                  isSelected
                    ? 'border-orange-500/40 bg-orange-500/5'
                    : 'border-white/[0.06] hover:border-orange-500/20'
                )}
                style={!isSelected ? { background: 'rgba(255,255,255,0.03)' } : undefined}
              >
                {/* Badge */}
                {v.badge && (
                  <span className={cn(
                    'absolute -top-2 right-3 text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full',
                    v.key === 'parwa'
                      ? 'bg-gradient-to-r from-orange-500 to-amber-400 text-[#1A1A1A]'
                      : 'bg-white/10 text-orange-200/60'
                  )}>
                    {v.badge}
                  </span>
                )}

                {/* Check indicator */}
                {isSelected && (
                  <div className="absolute top-2 right-2">
                    <CheckCircle2 className="w-4 h-4 text-orange-400" />
                  </div>
                )}

                {/* Icon */}
                <div className="flex items-center gap-2 mb-3">
                  {v.key === 'parwa' && <Sparkles className="w-4 h-4 text-orange-400" />}
                  {v.key === 'high' && <Crown className="w-4 h-4 text-yellow-400" />}
                  <span className={cn(
                    'text-sm font-semibold',
                    isSelected ? 'text-orange-400' : 'text-white'
                  )}>
                    {v.name}
                  </span>
                </div>

                {/* Price */}
                <p className="text-lg font-bold text-white mb-1">{v.priceLabel}</p>
                <p className="text-[10px] text-orange-200/30 mb-3">{v.description}</p>

                {/* Feature list */}
                <div className="space-y-1.5">
                  <FeatureRow label="9-step AI pipeline" />
                  <FeatureRow label={`${v.ticketVolume.toLocaleString()} tickets/mo`} />
                  <FeatureRow label={`${v.concurrentAiCalls} concurrent AI calls`} />
                  <FeatureRow label="Custom API" enabled={v.customApi} />
                  <FeatureRow label="OpenAPI Import" enabled={v.openApiImport} />
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* ── Continue Button ──────────────────────────────────────────── */}
      <div className="flex justify-end">
        <button
          onClick={handleContinue}
          disabled={!industry || !variant || isSubmitting}
          className={cn(
            'px-8 py-3 font-semibold rounded-xl transition-all duration-300 text-sm flex items-center gap-2',
            industry && variant
              ? 'bg-gradient-to-r from-orange-500 to-amber-400 hover:from-orange-400 hover:to-amber-300 text-[#1A1A1A] shadow-lg shadow-orange-500/25'
              : 'bg-zinc-700 text-zinc-500 cursor-not-allowed'
          )}
        >
          {isSubmitting ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Saving...
            </>
          ) : (
            <>
              Continue
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
        'text-[10px]',
        enabled ? 'text-orange-200/50' : 'text-zinc-600'
      )}>
        {label}
      </span>
    </div>
  );
}

export default IndustryVariantStep;
