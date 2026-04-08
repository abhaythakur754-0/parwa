'use client';

import React from 'react';
import { Ticket, DollarSign, TrendingUp, ArrowRight } from 'lucide-react';
import type { PricingVariant } from './VariantCard';

/**
 * TotalSummary Component
 *
 * Day 6: Pricing Page - Total Summary
 * Displays the bill summary with:
 * - Selected variants breakdown
 * - Total tickets per month
 * - Total monthly cost
 * - Continue to checkout button
 */

interface SelectedVariant {
  variant: PricingVariant;
  quantity: number;
}

interface TotalSummaryProps {
  selectedVariants: SelectedVariant[];
  onContinue: () => void;
  isSubmitting?: boolean;
  disabled?: boolean;
}

export function TotalSummary({
  selectedVariants,
  onContinue,
  isSubmitting = false,
  disabled = false,
}: TotalSummaryProps) {
  // Calculate totals
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

  const hasSelection = selectedVariants.length > 0 && totalVariants > 0;

  return (
    <div className="card card-padding">
      <h3 className="text-lg font-semibold text-white mb-4">
        Bill Summary
      </h3>

      {!hasSelection ? (
        <div className="text-center py-6">
          <div className="w-12 h-12 rounded-full bg-white/5 flex items-center justify-center mx-auto mb-3">
            <Ticket className="w-6 h-6 text-white/30" />
          </div>
          <p className="text-white/40">
            Select variants to see your bill summary
          </p>
        </div>
      ) : (
        <>
          {/* Selected Variants Breakdown */}
          <div className="space-y-3 mb-6">
            {selectedVariants.map(({ variant, quantity }) => (
              <div
                key={variant.id}
                className="flex items-center justify-between py-2 border-b border-white/5 last:border-0"
              >
                <div className="flex-1">
                  <p className="text-sm font-medium text-white">
                    {variant.name}
                    {quantity > 1 && (
                      <span className="text-white/50 ml-1">× {quantity}</span>
                    )}
                  </p>
                  <p className="text-xs text-white/40">
                    {(variant.ticketsPerMonth * quantity).toLocaleString()} tickets/month
                  </p>
                </div>
                <p className="text-sm font-semibold text-white">
                  ${variant.pricePerMonth * quantity}/mo
                </p>
              </div>
            ))}
          </div>

          {/* Totals */}
          <div className="space-y-3 py-4 border-t border-white/10">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-white/60">
                <Ticket className="w-4 h-4" />
                <span className="text-sm">Total Tickets</span>
              </div>
              <span className="text-sm font-medium text-white">
                {totalTickets.toLocaleString()}/month
              </span>
            </div>

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-white/60">
                <TrendingUp className="w-4 h-4" />
                <span className="text-sm">Active Variants</span>
              </div>
              <span className="text-sm font-medium text-white">
                {totalVariants}
              </span>
            </div>
          </div>

          {/* Monthly Total */}
          <div className="flex items-center justify-between py-4 border-t border-white/10">
            <div className="flex items-center gap-2">
              <DollarSign className="w-5 h-5 text-teal-400" />
              <span className="text-base font-semibold text-white">Monthly Total</span>
            </div>
            <span className="text-2xl font-bold text-teal-400">
              ${totalMonthly}
            </span>
          </div>

          {/* Annual Savings */}
          {totalMonthly > 0 && (
            <div className="p-3 rounded-lg bg-teal-500/10 border border-teal-500/20 mb-4">
              <p className="text-sm text-teal-300">
                💡 Save ${(totalMonthly * 2).toFixed(0)}/year with annual billing
              </p>
            </div>
          )}

          {/* Continue Button */}
          <button
            type="button"
            onClick={onContinue}
            disabled={disabled || isSubmitting || !hasSelection}
            className={`
              w-full btn btn-primary btn-lg
              flex items-center justify-center gap-2
              ${isSubmitting ? 'opacity-70 cursor-wait' : ''}
            `}
          >
            {isSubmitting ? (
              <>
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Processing...
              </>
            ) : (
              <>
                Continue to Checkout
                <ArrowRight className="w-5 h-5" />
              </>
            )}
          </button>
        </>
      )}
    </div>
  );
}
