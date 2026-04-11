'use client';

import React from 'react';
import { useRouter } from 'next/navigation';
import {
  Ticket,
  ArrowRight,
  Sparkles,
  CalendarCheck,
  ShoppingCart,
  X,
  MessageSquare,
} from 'lucide-react';
import type { PricingVariant } from './VariantCard';

/**
 * TotalSummary Component
 *
 * Premium card with:
 * - Variant breakdown with qty × price
 * - Total tickets/month
 * - Total monthly cost with orange accent
 * - "2 months free with annual plan" badge
 * - "Continue to Checkout" button
 * - Empty state message
 */

interface SelectedVariant {
  variant: PricingVariant;
  quantity: number;
}

interface TotalSummaryProps {
  selectedVariants: SelectedVariant[];
  selectedIndustry?: string | null;
  onContinue: () => void;
  isSubmitting?: boolean;
  disabled?: boolean;
  onRemoveVariant?: (variantId: string) => void;
}

export function TotalSummary({
  selectedVariants,
  selectedIndustry,
  onContinue,
  isSubmitting = false,
  disabled = false,
  onRemoveVariant,
}: TotalSummaryProps) {
  const router = useRouter();
  const totalTickets = selectedVariants.reduce(
    (sum, item) => sum + item.variant.ticketsPerMonth * item.quantity,
    0
  );
  const totalMonthly = selectedVariants.reduce(
    (sum, item) => sum + item.variant.pricePerMonth * item.quantity,
    0
  );
  const totalVariants = selectedVariants.reduce(
    (sum, item) => sum + item.quantity,
    0
  );
  const annualSavings = totalMonthly > 0 ? totalMonthly * 2 : 0;

  const hasSelection = selectedVariants.length > 0 && totalVariants > 0;

  return (
    <div
      className={`
        rounded-xl border-2 p-5 sm:p-6
        backdrop-blur-xl transition-all duration-300
        ${
          hasSelection
            ? 'border-orange-500/30 bg-orange-500/5 shadow-lg shadow-orange-600/10'
            : 'border-white/10 bg-white/[0.05]'
        }
      `}
    >
      {/* Header */}
      <div className="flex items-center gap-2.5 mb-5">
        <div
          className={`w-9 h-9 rounded-lg flex items-center justify-center ${
            hasSelection ? 'bg-orange-500/10' : 'bg-white/10'
          }`}
        >
          <ShoppingCart
            className={`w-5 h-5 ${
              hasSelection ? 'text-orange-400' : 'text-orange-200/30'
            }`}
          />
        </div>
        <div>
          <h3 className="text-base sm:text-lg font-bold text-white">
            Total Summary
          </h3>
          {hasSelection && (
            <p className="text-xs text-orange-200/50">
              {totalVariants} {totalVariants === 1 ? 'variant' : 'variants'}{' '}
              selected
            </p>
          )}
        </div>
      </div>

      {/* Empty State */}
      {!hasSelection ? (
        <div className="text-center py-8">
          <div className="w-14 h-14 rounded-full bg-white/10 flex items-center justify-center mx-auto mb-4">
            <Ticket className="w-7 h-7 text-orange-200/30" />
          </div>
          <p className="text-sm text-orange-200/30 mb-1 font-medium">
            Select variants to see your bill summary
          </p>
        </div>
      ) : (
        <>
          {/* Variant Breakdown */}
          <div className="space-y-2 mb-5">
            {selectedVariants.map(({ variant, quantity }) => (
              <div
                key={variant.id}
                className="group flex items-center gap-2.5 p-2.5 rounded-lg bg-white/5 border border-white/10 hover:border-white/20 transition-colors"
              >
                {/* Remove button */}
                {onRemoveVariant && (
                  <button
                    type="button"
                    onClick={() => onRemoveVariant(variant.id)}
                    disabled={disabled}
                    className="w-5 h-5 rounded flex items-center justify-center text-transparent group-hover:text-orange-200/40 hover:!text-red-400 hover:!bg-red-500/10 transition-all opacity-0 group-hover:opacity-100 flex-shrink-0"
                    aria-label={`Remove ${variant.name}`}
                  >
                    <X className="w-3 h-3" />
                  </button>
                )}

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-white truncate">
                    {variant.name}
                  </p>
                  <p className="text-[11px] text-orange-200/30">
                    {(variant.ticketsPerMonth * quantity).toLocaleString()} tickets/month
                  </p>
                </div>

                {/* Price */}
                <span className="text-sm font-bold text-gray-100 flex-shrink-0">
                  ${variant.pricePerMonth * quantity}/mo
                </span>
              </div>
            ))}
          </div>

          {/* Totals Section */}
          <div className="space-y-3 py-4 border-t border-white/10">
            {/* Total Tickets */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-orange-200/50">
                <Ticket className="w-4 h-4" />
                <span className="text-sm">Total Tickets</span>
              </div>
              <span className="text-sm font-bold text-white">
                {totalTickets.toLocaleString()}/month
              </span>
            </div>

            {/* Total Variants */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-orange-200/50">
                <Sparkles className="w-4 h-4" />
                <span className="text-sm">Active Variants</span>
              </div>
              <span className="text-sm font-bold text-white">
                {totalVariants}
              </span>
            </div>
          </div>

          {/* Monthly Total */}
          <div className="flex items-center justify-between py-4 border-t border-white/10">
            <span className="text-sm font-semibold text-orange-200/70">
              Monthly Total
            </span>
            <span className="text-2xl sm:text-3xl font-extrabold text-orange-400 tabular-nums">
              ${totalMonthly}
            </span>
          </div>

          {/* Annual Savings Badge */}
          {totalMonthly > 0 && (
            <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 mb-4">
              <div className="flex items-center gap-2">
                <CalendarCheck className="w-4 h-4 text-amber-400 flex-shrink-0" />
                <p className="text-xs sm:text-sm text-amber-400 font-bold">
                  Save ${annualSavings}/year with annual billing
                </p>
              </div>
            </div>
          )}

          {/* Continue Button */}
          <button
            type="button"
            onClick={onContinue}
            disabled={disabled || isSubmitting || !hasSelection}
            className={`
              w-full flex items-center justify-center gap-2
              px-5 py-3 rounded-lg text-sm font-bold
              bg-gradient-to-r from-orange-500 to-orange-400
              text-[#1A1A1A] shadow-lg shadow-orange-500/25
              hover:from-orange-400 hover:to-orange-300
              hover:shadow-orange-500/40 hover:-translate-y-0.5
              active:translate-y-0 active:shadow-md
              transition-all duration-300
              disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:translate-y-0
              ${isSubmitting ? 'animate-pulse cursor-wait' : ''}
            `}
          >
            {isSubmitting ? (
              <>
                <div className="w-4 h-4 border-2 border-[#1A1A1A]/30 border-t-[#1A1A1A] rounded-full animate-spin" />
                Processing...
              </>
            ) : (
              <>
                Continue to Checkout
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>

          {/* Phase 9: Proceed with Jarvis → Onboarding */}
          <button
            type="button"
            onClick={() => {
              // Store context for Jarvis to pick up on /onboarding
              const jarvisContext = {
                industry: selectedIndustry || null,
                selected_variants: selectedVariants.map((sv) => ({
                  id: sv.variant.id,
                  name: sv.variant.name,
                  quantity: sv.quantity,
                  price_per_month: sv.variant.pricePerMonth,
                  tickets_per_month: sv.variant.ticketsPerMonth,
                })),
                total_price: totalMonthly,
                source: 'pricing_page',
              };
              localStorage.setItem('parwa_jarvis_context', JSON.stringify(jarvisContext));
              router.push('/onboarding');
            }}
            disabled={disabled || !hasSelection}
            className={
              'w-full flex items-center justify-center gap-2 mt-3 px-5 py-3 rounded-lg text-sm font-semibold border-2 border-orange-400/30 bg-orange-500/10 text-orange-300 hover:bg-orange-500/20 hover:border-orange-400/50 hover:text-orange-200 transition-all duration-300 disabled:opacity-30 disabled:cursor-not-allowed'
            }
          >
            <MessageSquare className="w-4 h-4" />
            Proceed with Jarvis
            <ArrowRight className="w-4 h-4" />
          </button>
        </>
      )}
    </div>
  );
}
