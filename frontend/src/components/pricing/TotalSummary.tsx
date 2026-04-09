'use client';

import React from 'react';
import {
  Ticket,
  ArrowRight,
  Sparkles,
  CalendarCheck,
  ShoppingCart,
  X,
} from 'lucide-react';
import type { PricingVariant } from './VariantCard';

/**
 * TotalSummary Component
 *
 * Premium card with:
 * - Variant breakdown with qty × price
 * - Total tickets/month
 * - Total monthly cost with teal accent
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
  onContinue: () => void;
  isSubmitting?: boolean;
  disabled?: boolean;
  onRemoveVariant?: (variantId: string) => void;
}

export function TotalSummary({
  selectedVariants,
  onContinue,
  isSubmitting = false,
  disabled = false,
  onRemoveVariant,
}: TotalSummaryProps) {
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
            ? 'border-emerald-300 bg-emerald-50 shadow-lg shadow-emerald-600/10'
            : 'border-gray-200 bg-white'
        }
      `}
    >
      {/* Header */}
      <div className="flex items-center gap-2.5 mb-5">
        <div
          className={`w-9 h-9 rounded-lg flex items-center justify-center ${
            hasSelection ? 'bg-emerald-50' : 'bg-gray-100'
          }`}
        >
          <ShoppingCart
            className={`w-5 h-5 ${
              hasSelection ? 'text-emerald-600' : 'text-gray-300'
            }`}
          />
        </div>
        <div>
          <h3 className="text-base sm:text-lg font-bold text-gray-900">
            Total Summary
          </h3>
          {hasSelection && (
            <p className="text-xs text-gray-500">
              {totalVariants} {totalVariants === 1 ? 'variant' : 'variants'}{' '}
              selected
            </p>
          )}
        </div>
      </div>

      {/* Empty State */}
      {!hasSelection ? (
        <div className="text-center py-8">
          <div className="w-14 h-14 rounded-full bg-gray-100 flex items-center justify-center mx-auto mb-4">
            <Ticket className="w-7 h-7 text-gray-300" />
          </div>
          <p className="text-sm text-gray-400 mb-1 font-medium">
            No variants selected
          </p>
          <p className="text-xs text-gray-300 leading-relaxed">
            Select variants and adjust quantities to see your bill summary
          </p>
        </div>
      ) : (
        <>
          {/* Variant Breakdown */}
          <div className="space-y-2 mb-5">
            {selectedVariants.map(({ variant, quantity }) => (
              <div
                key={variant.id}
                className="group flex items-center gap-2.5 p-2.5 rounded-lg bg-gray-50 border border-gray-200 hover:border-gray-300 transition-colors"
              >
                {/* Remove button */}
                {onRemoveVariant && (
                  <button
                    type="button"
                    onClick={() => onRemoveVariant(variant.id)}
                    disabled={disabled}
                    className="w-5 h-5 rounded flex items-center justify-center text-transparent group-hover:text-gray-400 hover:!text-red-500 hover:!bg-red-50 transition-all opacity-0 group-hover:opacity-100 flex-shrink-0"
                    aria-label={`Remove ${variant.name}`}
                  >
                    <X className="w-3 h-3" />
                  </button>
                )}

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-gray-900 truncate">
                    {variant.name}
                  </p>
                  <p className="text-[11px] text-gray-400">
                    {quantity} x ${variant.pricePerMonth}/mo
                  </p>
                </div>

                {/* Price */}
                <span className="text-sm font-bold text-gray-800 flex-shrink-0">
                  ${variant.pricePerMonth * quantity}
                </span>
              </div>
            ))}
          </div>

          {/* Totals Section */}
          <div className="space-y-3 py-4 border-t border-gray-200">
            {/* Total Tickets */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-gray-500">
                <Ticket className="w-4 h-4" />
                <span className="text-sm">Total Tickets</span>
              </div>
              <span className="text-sm font-bold text-gray-900">
                {totalTickets.toLocaleString()}
                <span className="text-xs font-normal text-gray-400 ml-0.5">
                  /mo
                </span>
              </span>
            </div>

            {/* Total Variants */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-gray-500">
                <Sparkles className="w-4 h-4" />
                <span className="text-sm">Active Variants</span>
              </div>
              <span className="text-sm font-bold text-gray-900">
                {totalVariants}
              </span>
            </div>
          </div>

          {/* Monthly Total */}
          <div className="flex items-center justify-between py-4 border-t border-gray-200">
            <span className="text-sm font-semibold text-gray-700">
              Monthly Total
            </span>
            <div className="flex items-baseline gap-0.5">
              <span className="text-xs text-emerald-600 font-medium">$</span>
              <span className="text-2xl sm:text-3xl font-extrabold text-emerald-600 tabular-nums">
                {totalMonthly}
              </span>
              <span className="text-xs text-emerald-500 font-medium">
                /mo
              </span>
            </div>
          </div>

          {/* Annual Savings Badge */}
          {totalMonthly > 0 && (
            <div className="p-3 rounded-lg bg-amber-50 border border-amber-200 mb-4">
              <div className="flex items-center gap-2">
                <CalendarCheck className="w-4 h-4 text-amber-500 flex-shrink-0" />
                <p className="text-xs sm:text-sm text-amber-700 font-medium">
                  <span className="text-amber-600 font-bold">
                    2 months free
                  </span>{' '}
                  with annual plan — save{' '}
                  <span className="text-amber-600 font-bold">
                    ${annualSavings}
                  </span>
                  /year
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
              bg-gradient-to-r from-emerald-600 to-emerald-700
              text-white shadow-lg shadow-emerald-600/25
              hover:from-emerald-500 hover:to-emerald-600
              hover:shadow-emerald-600/40 hover:-translate-y-0.5
              active:translate-y-0 active:shadow-md
              transition-all duration-300
              disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:translate-y-0
              ${isSubmitting ? 'animate-pulse cursor-wait' : ''}
            `}
          >
            {isSubmitting ? (
              <>
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Processing...
              </>
            ) : (
              <>
                Continue to Checkout
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </>
      )}
    </div>
  );
}
