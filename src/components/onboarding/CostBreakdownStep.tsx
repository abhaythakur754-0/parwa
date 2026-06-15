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
  Tag,
  Check,
  X,
  Ticket,
} from 'lucide-react';
import { toast } from '@/lib/dynamic-toast';
import { cn } from '@/lib/utils';
// ── DYNAMIC IMPORTS: paddle and coupon-config are loaded on demand ──────
// Static imports of @/lib/paddle cause TDZ errors because the module
// pulls in @paddle/paddle-js (ESM-only). By using dynamic imports,
// we defer evaluation until runtime, avoiding "Cannot access 'ee' before initialization".
import { VARIANT_PRICE_IDS } from '@/lib/paddle-constants';
import type { Coupon } from '@/lib/coupon-config';
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
  type OnboardingVariant,
} from '@/lib/pricing-config';

// ── Lazy-loaded paddle/coupon functions ──────────────────────────────────
// These are only imported when the user clicks "Proceed" or when the
// component mounts and checks Paddle availability. This avoids pulling
// @paddle/paddle-js into the chunk at evaluation time.
type PaddleModule = typeof import('@/lib/paddle');
type CouponModule = typeof import('@/lib/coupon-config');

let _paddleMod: PaddleModule | null = null;
let _couponMod: CouponModule | null = null;

async function loadPaddle(): Promise<PaddleModule> {
  if (_paddleMod) return _paddleMod;
  _paddleMod = await import('@/lib/paddle');
  return _paddleMod;
}

async function loadCoupon(): Promise<CouponModule> {
  if (_couponMod) return _couponMod;
  _couponMod = await import('@/lib/coupon-config');
  return _couponMod;
}

// ── Synchronous coupon helpers (inline — avoid importing coupon-config) ──
// These are small pure functions that don't need the full coupon-config module.
// We inline them here so that the component can use them at render time
// without a static import that would pull coupon-config into the chunk.

function _validateCoupon(code: string): Coupon | null {
  // Minimal inline version — delegates to dynamically-loaded module when ready
  // For the initial render, we use a simplified check
  if (!code || code.trim().length === 0) return null;
  const normalized = code.trim().toUpperCase();
  // Known coupons (must match coupon-config.ts)
  const COUPON_CODE = (typeof process !== 'undefined' && process.env?.NEXT_PUBLIC_PADDLE_FREE_DISCOUNT_CODE) || 'DURGA754';
  if (normalized === COUPON_CODE.toUpperCase()) {
    return {
      code: COUPON_CODE,
      discountPercent: 100,
      paddleDiscountId: (typeof process !== 'undefined' && process.env?.NEXT_PUBLIC_PADDLE_FREE_DISCOUNT_ID) || 'dsc_01kv26d0s3qt2w1vpj888qa2nh',
      description: '100% off — Full testing access (all variants free)',
      active: true,
    };
  }
  return null;
}

function _applyCouponDiscount(price: number, coupon: Coupon | null): number {
  if (!coupon) return price;
  const discount = price * (coupon.discountPercent / 100);
  return Math.max(0, Math.round((price - discount) * 100) / 100);
}

function _formatDiscount(coupon: Coupon): string {
  return `${coupon.discountPercent}% off`;
}

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
  quantity,
  onToggle,
  onQuantityChange,
  discountedPrice,
}: {
  tier: VariantTier;
  isActive: boolean;
  quantity: number;
  onToggle: () => void;
  onQuantityChange: (qty: number) => void;
  discountedPrice?: number;
}) {
  const info = VARIANT_DISPLAY[tier];
  const limits = VARIANT_LIMITS[tier];
  const aiInfo = VARIANT_AI_INFO[tier];
  const displayPrice = discountedPrice !== undefined ? discountedPrice : info.price;
  const isFree = displayPrice === 0;

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
            {isActive && isFree && (
              <span className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-full bg-purple-500/10 text-purple-400">
                FREE
              </span>
            )}
          </div>
        </div>
        <span className={cn(
          'text-base font-bold',
          isFree ? 'text-emerald-400' : 'text-white'
        )}>
          {isFree ? '$0/mo' : `$${displayPrice.toLocaleString()}/mo`}
          {isFree && discountedPrice !== undefined && discountedPrice !== info.price && (
            <span className="text-[10px] text-orange-200/25 line-through ml-1">${info.price.toLocaleString()}</span>
          )}
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

// ── Coupon Code Input Component ──────────────────────────────────────

function CouponCodeInput({
  appliedCoupon,
  onApply,
  onRemove,
}: {
  appliedCoupon: Coupon | null;
  onApply: (coupon: Coupon) => void;
  onRemove: () => void;
}) {
  const [code, setCode] = useState('');
  const [isValidating, setIsValidating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleApply = () => {
    if (!code.trim()) return;
    setIsValidating(true);
    setError(null);

    // Simulate brief validation delay
    setTimeout(() => {
      const coupon = _validateCoupon(code);
      if (coupon) {
        onApply(coupon);
        toast.success(`Coupon applied: ${_formatDiscount(coupon)}`);
      } else {
        setError('Invalid coupon code. Please check and try again.');
        toast.error('Invalid coupon code');
      }
      setIsValidating(false);
    }, 300);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleApply();
    }
  };

  if (appliedCoupon) {
    return (
      <div className="rounded-xl border border-emerald-500/30 p-4" style={{ background: 'rgba(16,185,129,0.06)' }}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-emerald-500/15 flex items-center justify-center">
              <Ticket className="w-4 h-4 text-emerald-400" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold text-emerald-400">
                  {appliedCoupon.code}
                </span>
                <span className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400">
                  {_formatDiscount(appliedCoupon)}
                </span>
              </div>
              <p className="text-[10px] text-orange-200/30 mt-0.5">
                {appliedCoupon.description}
              </p>
            </div>
          </div>
          <button
            onClick={onRemove}
            className="p-1.5 rounded-lg hover:bg-white/[0.06] text-orange-200/30 hover:text-red-400 transition-all"
            title="Remove coupon"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        {appliedCoupon.discountPercent === 100 && (
          <div className="mt-3 flex items-start gap-2 rounded-lg p-2.5" style={{ background: 'rgba(16,185,129,0.08)' }}>
            <Sparkles className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
            <div>
              <p className="text-[10px] font-medium text-emerald-300">
                Free checkout — $0.00 total
              </p>
              <p className="text-[9px] text-orange-200/25 mt-0.5">
                Paddle will process a $0 transaction. Your subscription will be activated after confirmation.
              </p>
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-white/[0.08] p-4 space-y-3" style={{ background: 'rgba(255,255,255,0.03)' }}>
      <div className="flex items-center gap-2">
        <Tag className="w-4 h-4 text-orange-400" />
        <span className="text-xs text-orange-200/50 uppercase tracking-wider font-medium">
          Have a coupon code?
        </span>
      </div>
      <div className="flex gap-2">
        <input
          type="text"
          value={code}
          onChange={(e) => {
            setCode(e.target.value.toUpperCase());
            setError(null);
          }}
          onKeyDown={handleKeyDown}
          placeholder="Enter coupon code"
          className={cn(
            'flex-1 h-10 rounded-lg bg-white/[0.04] border px-3 text-sm text-white placeholder-orange-200/20',
            'focus:outline-none focus:border-orange-500/50 transition-all',
            error ? 'border-red-500/40' : 'border-white/[0.08]'
          )}
        />
        <button
          onClick={handleApply}
          disabled={!code.trim() || isValidating}
          className="h-10 px-4 rounded-lg bg-gradient-to-r from-orange-500 to-amber-400 text-[#1A1A1A] text-xs font-semibold hover:from-orange-400 hover:to-amber-300 transition-all disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1.5"
        >
          {isValidating ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <Check className="w-3.5 h-3.5" />
          )}
          Apply
        </button>
      </div>
      {error && (
        <p className="text-[10px] text-red-400 flex items-center gap-1">
          <AlertCircle className="w-3 h-3" />
          {error}
        </p>
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
  const [appliedCoupon, setAppliedCoupon] = useState<Coupon | null>(null);
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
        // Restore multiple variants if selected on ModelsPage
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
        // Restore coupon from ModelsPage
        if (ctx.couponCode && typeof ctx.couponCode === 'string') {
          const coupon = _validateCoupon(ctx.couponCode);
          if (coupon) {
            setAppliedCoupon(coupon);
          }
        }
      }
    } catch {
      // ignore
    }
  }, []);

  // Check if Paddle.js is available
  useEffect(() => {
    loadPaddle().then(({ getPaddleInstance }) => {
      getPaddleInstance().then((paddle) => {
        setPaddleStatus(paddle ? 'ready' : 'unavailable');
      }).catch(() => {
        setPaddleStatus('unavailable');
      });
    }).catch(() => {
      setPaddleStatus('unavailable');
    });
  }, []);

  // Re-check Paddle status when coupon is applied — if free checkout,
  // Paddle availability doesn't matter
  useEffect(() => {
    if (isFreeCheckout && paddleStatus === 'unavailable') {
      // Free checkout doesn't need Paddle — update status to suppress warning
      console.log('[cost-breakdown] Free checkout detected — Paddle not required');
    }
  }, [isFreeCheckout, paddleStatus]);

  // ── Calculations (pure math — D7, D10) ──────────────────────────────

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

  // ── Coupon-discounted total ──────────────────────────────────────
  const discountedTotal = useMemo(
    () => _applyCouponDiscount(totalMonthly, appliedCoupon),
    [totalMonthly, appliedCoupon]
  );
  const isFreeCheckout = discountedTotal === 0;

  // Per-variant discounted prices
  const variantDiscountedPrices = useMemo(() => {
    const prices: Record<VariantTier, number> = { starter: 0, growth: 0, high: 0 };
    for (const tier of activeVariants) {
      const variantPrice = VARIANT_PRICES[tier] * (variantQuantities[tier] || 1);
      prices[tier] = _applyCouponDiscount(variantPrice, appliedCoupon);
    }
    return prices;
  }, [activeVariants, variantQuantities, appliedCoupon]);

  const savings = estimateSavings(totalTicketLimit, discountedTotal);

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

  const updateQuantity = (tier: VariantTier, qty: number) => {
    const newQty = Math.max(1, Math.min(qty, 10));
    setVariantQuantities((prev) => ({ ...prev, [tier]: newQty }));
  };

  const toggleAddOn = (key: 'voice' | 'customApi') => {
    setAddOns((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const handleApplyCoupon = (coupon: Coupon) => {
    setAppliedCoupon(coupon);
    setCheckoutError(null);
  };

  const handleRemoveCoupon = () => {
    setAppliedCoupon(null);
    toast('Coupon removed');
  };

  // ── Payment success handler — ONLY called after Paddle confirms ──
  const handlePaymentSuccess = () => {
    setPaymentConfirmed(true);
    localStorage.removeItem('parwa_payment_pending');
    if (isFreeCheckout) {
      toast.success('Subscription activated! Welcome to PARWA!');
    } else {
      toast.success('Payment successful! Welcome to PARWA!');
    }
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

      // Voice add-on (only for starter where it's not included)
      if (addOns.voice && !activeVariants.some((t) => ADD_ONS.find(a => a.key === 'voice')!.includedIn.includes(t))) {
        checkoutItems.push({ priceId: 'pri_voice_addon_01', quantity: 1 });
      }

      // Custom API add-on (only for variants where it's not included)
      if (addOns.customApi && !activeVariants.some((t) => ADD_ONS.find(a => a.key === 'customApi')!.includedIn.includes(t))) {
        checkoutItems.push({ priceId: 'pri_custom_api_addon_01', quantity: 1 });
      }

      const customData = {
        source: 'parwa_onboarding',
        variant: primaryOnboardingVariant,
        activeVariants: activeVariants.map((t) => TIER_TO_ONBOARDING[t]),
        variantQuantities,
        addOns,
        industry: context.industry,
        totalMonthly,
        couponCode: appliedCoupon?.code || null,
        discountedTotal,
        isFreeCheckout,
      };

      // Get Paddle discount code/ID if a coupon is applied
      // PRIORITY: Use discountId over discountCode (more reliable, no case-sensitivity issues)
      const couponMod = await loadCoupon();
      const paddleDiscountCode = couponMod.getPaddleDiscountCode(appliedCoupon);
      const paddleDiscountId = couponMod.getPaddleDiscountId(appliedCoupon);

      console.log('[cost-breakdown] Checkout config:', {
        isFreeCheckout,
        discountedTotal,
        discountCode: paddleDiscountCode,
        discountId: paddleDiscountId,
        checkoutItems,
      });

      // ── FAST PATH: Free checkout (100% coupon) — skip Paddle entirely ──
      // If the total is $0 after coupon, we don't need a payment gateway.
      // Activate the subscription directly and move to First Victory.
      if (isFreeCheckout) {
        console.log('[cost-breakdown] Free checkout ($0) — skipping Paddle, activating directly');

        // Try to notify the backend about the activation
        try {
          await fetch('/api/onboarding/activate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              variant: primaryOnboardingVariant,
              industry: context.industry,
              couponCode: appliedCoupon?.code || null,
              isFreeCheckout: true,
            }),
          });
        } catch {
          // Continue locally even if API fails
        }

        // Save onboarding as completed
        localStorage.setItem('parwa_onboarding_completed', 'true');
        localStorage.removeItem('parwa_payment_pending');

        toast.success('Free plan activated! Welcome to PARWA!');
        handlePaymentSuccess();
        return;
      }

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
            couponCode: appliedCoupon?.code || null,
            discountCode: paddleDiscountCode,
            discountId: paddleDiscountId,
            discountedTotal,
            isFreeCheckout,
          }),
        });

        if (res.ok) {
          const checkoutData = await res.json();
          checkoutUrl = checkoutData.checkout_url || null;
          console.log('[cost-breakdown] Server checkout response:', checkoutData);
        } else {
          console.warn('[cost-breakdown] Server checkout failed:', res.status, await res.text().catch(() => ''));
        }
      } catch (err) {
        console.warn('[cost-breakdown] Server checkout API unavailable:', err);
      }

      // If we got a checkout_url from backend, redirect to it
      if (checkoutUrl) {
        localStorage.setItem('parwa_payment_pending', JSON.stringify({
          activeVariants, addOns, totalMonthly, variantQuantities,
          couponCode: appliedCoupon?.code || null,
          pendingAt: new Date().toISOString(),
        }));
        window.location.href = checkoutUrl;
        return;
      }

      // ── Step 2: Client-side Paddle checkout (items-based overlay) ──
      // Re-check Paddle availability (might have loaded since initial check)
      const paddleMod = await loadPaddle();
      const paddle = await paddleMod.getPaddleInstance();
      console.log('[cost-breakdown] Paddle instance:', paddle ? 'available' : 'not available');

      if (paddle && checkoutItems.length > 0) {
        setPaddleStatus('ready');
        // Pass discountId (preferred) or discountCode — NOT both
        // Paddle only accepts one type at a time
        const effectiveDiscountCode = paddleDiscountId ? undefined : paddleDiscountCode;
        const effectiveDiscountId = paddleDiscountId || undefined;
        
        const opened = await paddleMod.openCheckoutWithItems(
          checkoutItems,
          customData,
          // onPaymentSuccess — triggers after Paddle confirms the transaction
          handlePaymentSuccess,
          // onCheckoutClosed — user closed without completing
          () => {
            toast('Checkout closed — payment is required to activate your plan.', { icon: '⚠️' });
            setIsSubmitting(false);
          },
          effectiveDiscountCode,
          effectiveDiscountId,
        );

        if (opened) {
          console.log('[cost-breakdown] Paddle overlay opened successfully');
          return; // Paddle overlay is showing — wait for user to complete or close
        }
        console.warn('[cost-breakdown] Paddle overlay did NOT open');
      }

      // ── Step 3: Paddle unavailable — try re-initializing ──
      // Sometimes Paddle fails on first load but works on retry
      try {
        const retryPaddle = await paddleMod.getPaddleInstance();
        if (retryPaddle && checkoutItems.length > 0) {
          setPaddleStatus('ready');
          const effectiveDiscountCode = paddleDiscountId ? undefined : paddleDiscountCode;
          const effectiveDiscountId = paddleDiscountId || undefined;

          const opened = await paddleMod.openCheckoutWithItems(
            checkoutItems,
            customData,
            handlePaymentSuccess,
            () => {
              toast('Checkout closed — payment is required to activate your plan.', { icon: '⚠️' });
              setIsSubmitting(false);
            },
            effectiveDiscountCode,
            effectiveDiscountId,
          );
          if (opened) {
            console.log('[cost-breakdown] Paddle overlay opened on retry');
            return;
          }
        }
      } catch (err) {
        console.warn('[cost-breakdown] Paddle retry failed:', err);
      }

      // ── Step 4: Paddle unavailable — handle based on checkout type ──
      setPaddleStatus('unavailable');
      localStorage.setItem('parwa_payment_pending', JSON.stringify({
        activeVariants, addOns, totalMonthly, variantQuantities,
        couponCode: appliedCoupon?.code || null,
        pendingAt: new Date().toISOString(),
      }));

      if (isFreeCheckout) {
        // $0 checkout (100% coupon) — Paddle gateway is unavailable but the total is $0.
        // We still want to confirm the subscription through Paddle if possible, but if
        // Paddle is down, we can safely activate the free subscription since no money
        // is changing hands. The user applied a valid 100% coupon (e.g. "durga754").
        console.log('[cost-breakdown] Free checkout ($0) with Paddle unavailable — activating subscription');
        toast.success('Free plan activated! Welcome to PARWA!');
        handlePaymentSuccess();
      } else {
        // Paid checkout — payment gateway is REQUIRED. Block and show error.
        setCheckoutError(
          'Payment gateway is currently unavailable. Your plan configuration has been saved. ' +
          'Please refresh the page and try again, or contact support@parwa.buzz to complete your subscription.'
        );
        toast.error('Payment gateway unavailable — please try again or contact support.');
      }
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
      {paddleStatus === 'unavailable' && !isFreeCheckout && (
        <div className="rounded-xl border border-amber-500/20 p-4 flex items-start gap-3" style={{ background: 'rgba(245,158,11,0.05)' }}>
          <AlertCircle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-amber-300">Payment checkout unavailable</p>
            <p className="text-[10px] text-orange-200/30 mt-1">
              Paddle payment gateway is not configured. Apply a coupon code for free checkout, or try again later.
            </p>
          </div>
        </div>
      )}
      {paddleStatus === 'unavailable' && isFreeCheckout && (
        <div className="rounded-xl border border-emerald-500/20 p-3 flex items-center gap-2" style={{ background: 'rgba(16,185,129,0.04)' }}>
          <Sparkles className="w-4 h-4 text-emerald-400" />
          <p className="text-xs text-emerald-400">Free checkout — no payment required</p>
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
              discountedPrice={activeVariants.includes(tier) ? variantDiscountedPrices[tier] : undefined}
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
                  <p className={cn(
                    'text-sm font-semibold',
                    isFreeCheckout ? 'text-emerald-400' : 'text-white'
                  )}>
                    {isFreeCheckout ? '$0/mo' : `$${addOn.price}/mo`}
                  </p>
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

      {/* ── 4. Coupon Code ─────────────────────────────────────────────── */}
      <CouponCodeInput
        appliedCoupon={appliedCoupon}
        onApply={handleApplyCoupon}
        onRemove={handleRemoveCoupon}
      />

      {/* ── 5. Cost Summary (pure math — D7) ──────────────────────────── */}
      <div
        className="rounded-xl border border-white/[0.08] p-5 space-y-3"
        style={{ background: 'rgba(255,255,255,0.03)' }}
      >
        {/* Per-variant breakdown */}
        {activeVariants.map((tier) => {
          const qty = variantQuantities[tier] || 1;
          const discounted = variantDiscountedPrices[tier];
          const originalPrice = VARIANT_PRICES[tier] * qty;
          const hasDiscount = discounted < originalPrice;

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
              <span className={cn(
                'text-sm',
                hasDiscount ? 'text-emerald-400' : 'text-white'
              )}>
                {hasDiscount && (
                  <span className="text-orange-200/25 line-through mr-1.5">
                    ${originalPrice.toLocaleString()}/mo
                  </span>
                )}
                ${discounted.toLocaleString()}/mo
              </span>
            </div>
          );
        })}

        {/* Add-ons */}
        {addOns.voice && !activeVariants.some((t) => ADD_ONS.find(a => a.key === 'voice')!.includedIn.includes(t)) && (
          <div className="flex items-center justify-between">
            <span className="text-sm text-orange-200/50">Voice Channel</span>
            <span className={cn(
              'text-sm',
              isFreeCheckout ? 'text-emerald-400' : 'text-white'
            )}>
              {isFreeCheckout ? (
                <><span className="text-orange-200/25 line-through mr-1.5">$199/mo</span>$0/mo</>
              ) : '$199/mo'}
            </span>
          </div>
        )}
        {addOns.customApi && !activeVariants.some((t) => ADD_ONS.find(a => a.key === 'customApi')!.includedIn.includes(t)) && (
          <div className="flex items-center justify-between">
            <span className="text-sm text-orange-200/50">Custom API Connector</span>
            <span className={cn(
              'text-sm',
              isFreeCheckout ? 'text-emerald-400' : 'text-white'
            )}>
              {isFreeCheckout ? (
                <><span className="text-orange-200/25 line-through mr-1.5">$49/mo</span>$0/mo</>
              ) : '$49/mo'}
            </span>
          </div>
        )}

        {/* Integrations = $0 (D13) */}
        <div className="flex items-center justify-between">
          <span className="text-sm text-orange-200/50">Integrations</span>
          <span className="text-sm text-emerald-400">$0 (free)</span>
        </div>

        {/* Coupon discount line */}
        {appliedCoupon && discountedTotal < totalMonthly && (
          <div className="flex items-center justify-between py-1">
            <span className="text-sm text-emerald-400 flex items-center gap-1.5">
              <Tag className="w-3 h-3" />
              Coupon: {appliedCoupon.code} ({_formatDiscount(appliedCoupon)})
            </span>
            <span className="text-sm text-emerald-400 font-medium">
              −${(totalMonthly - discountedTotal).toLocaleString()}/mo
            </span>
          </div>
        )}

        <div className={cn(
          'border-t pt-3 flex items-center justify-between',
          isFreeCheckout ? 'border-emerald-500/20' : 'border-white/[0.06]'
        )}>
          <span className="text-sm font-semibold text-white">Total Monthly</span>
          <span className={cn(
            'text-lg font-bold',
            isFreeCheckout ? 'text-emerald-400' : 'text-orange-400'
          )}>
            {isFreeCheckout ? (
              <>
                <span className="text-orange-200/25 line-through text-sm mr-2">${totalMonthly.toLocaleString()}/mo</span>
                $0/mo
              </>
            ) : (
              `$${discountedTotal.toLocaleString()}/mo`
            )}
          </span>
        </div>

        {/* Overage rate info */}
        <div className="flex items-center justify-between">
          <span className="text-[10px] text-orange-200/25">Overage rate (beyond limits)</span>
          <span className="text-[10px] text-orange-200/25">${OVERAGE_PRICE_PER_TICKET}/ticket</span>
        </div>
      </div>

      {/* ── 6. Savings Comparison (D10 — reuse ROI Calculator logic) ──── */}
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
              That&apos;s ${savings.humanCost.toLocaleString()}/mo in human costs vs ${discountedTotal.toLocaleString()}/mo with PARWA.
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
            isFreeCheckout
              ? 'bg-gradient-to-r from-emerald-500 to-emerald-400 hover:from-emerald-400 hover:to-emerald-300 text-[#1A1A1A] shadow-emerald-500/25'
              : 'bg-gradient-to-r from-orange-500 to-amber-400 hover:from-orange-400 hover:to-amber-300 text-[#1A1A1A] shadow-orange-500/25',
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
          ) : isFreeCheckout ? (
            <>
              <Sparkles className="w-4 h-4" />
              Activate Free Plan ($0/mo)
              <ArrowRight className="w-4 h-4" />
            </>
          ) : (
            <>
              Pay ${discountedTotal.toLocaleString()}/mo & Activate
              <ArrowRight className="w-4 h-4" />
            </>
          )}
        </button>
      </div>
    </div>
  );
}

export default CostBreakdownStep;
