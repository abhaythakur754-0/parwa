/**
 * PARWA DemoVariantSelector — Variant Selection Card Grid
 *
 * Shows the 3 PARWA variants (Starter, Growth, High) with feature comparison.
 * Matches the existing ORANGE (#FF7F11) design system with dark background (#1A1A1A).
 */

'use client';

import { cn } from '@/lib/utils';
import type { DemoVariant, VariantTier } from '@/types/demo-variant';
import { Check, Zap, Crown, Shield } from 'lucide-react';

interface DemoVariantSelectorProps {
  variants: DemoVariant[];
  selectedVariant: DemoVariant | null;
  onSelect: (variant: DemoVariant) => void;
  isLoading?: boolean;
}

const TIER_STYLES: Record<string, { gradient: string; border: string; badge: string; icon: React.ReactNode }> = {
  starter: {
    gradient: 'from-orange-600/10 to-orange-500/5',
    border: 'border-orange-500/20 hover:border-orange-500/40',
    badge: 'bg-orange-500/10 text-orange-400',
    icon: <Zap className="w-5 h-5" />,
  },
  growth: {
    gradient: 'from-amber-600/10 to-amber-500/5',
    border: 'border-amber-500/20 hover:border-amber-500/40',
    badge: 'bg-amber-500/10 text-amber-400',
    icon: <Shield className="w-5 h-5" />,
  },
  high: {
    gradient: 'from-gold-500/10 to-gold-400/5',
    border: 'border-gold-500/20 hover:border-gold-500/40',
    badge: 'bg-gold-500/10 text-gold-400',
    icon: <Crown className="w-5 h-5" />,
  },
};

export function DemoVariantSelector({
  variants,
  selectedVariant,
  onSelect,
  isLoading,
}: DemoVariantSelectorProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {variants.map((variant) => {
        const style = TIER_STYLES[variant.tier] || TIER_STYLES.starter;
        const isSelected = selectedVariant?.id === variant.id;

        return (
          <button
            key={variant.id}
            onClick={() => onSelect(variant)}
            disabled={isLoading}
            className={cn(
              'relative text-left rounded-xl p-5 border transition-all duration-300',
              'bg-gradient-to-br',
              style.gradient,
              isSelected
                ? `${style.border} ring-2 ring-orange-500/30 shadow-lg shadow-orange-500/10`
                : `border-white/[0.06] hover:border-white/15 hover:bg-white/[0.03]`,
              isLoading && 'opacity-50 cursor-not-allowed',
            )}
          >
            {/* Selected check */}
            {isSelected && (
              <div className="absolute top-3 right-3 w-6 h-6 rounded-full bg-orange-500 flex items-center justify-center">
                <Check className="w-3.5 h-3.5 text-white" />
              </div>
            )}

            {/* Tier badge */}
            <div className={cn('inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[10px] font-semibold uppercase tracking-wider mb-3', style.badge)}>
              {style.icon}
              {variant.tagline}
            </div>

            {/* Name & Price */}
            <h3 className="text-lg font-bold text-white mb-1">{variant.name}</h3>
            <div className="flex items-baseline gap-1 mb-3">
              <span className="text-2xl font-bold text-gradient">${variant.price_per_month.toLocaleString()}</span>
              <span className="text-xs text-white/30">/mo</span>
            </div>

            {/* Description */}
            <p className="text-xs text-white/40 mb-4 leading-relaxed">{variant.description}</p>

            {/* Key features */}
            <div className="space-y-1.5">
              {variant.features.slice(0, 5).map((feature, idx) => (
                <div key={idx} className="flex items-center gap-2">
                  <div className="w-1 h-1 rounded-full bg-orange-400/60 shrink-0" />
                  <span className="text-[11px] text-white/50">{feature}</span>
                </div>
              ))}
              {variant.features.length > 5 && (
                <span className="text-[10px] text-orange-400/40 ml-3">
                  +{variant.features.length - 5} more features
                </span>
              )}
            </div>

            {/* Ticket limit */}
            <div className="mt-4 pt-3 border-t border-white/[0.06] flex items-center justify-between">
              <span className="text-[10px] text-white/30">Tickets/month</span>
              <span className="text-xs font-semibold text-white/60">
                {variant.tickets_per_month.toLocaleString()}
              </span>
            </div>
          </button>
        );
      })}
    </div>
  );
}
