'use client';

import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type { VariantData } from './VariantCard';
import { ArrowRight, Sparkles, Info } from 'lucide-react';

export interface SelectedVariant {
  variant: VariantData;
  quantity: number;
}

export interface TotalSummaryProps {
  selectedVariants: SelectedVariant[];
  onContinue: () => void;
}

export default function TotalSummary({
  selectedVariants,
  onContinue,
}: TotalSummaryProps) {
  const totalMonthlyCost = selectedVariants.reduce(
    (sum, sv) => sum + sv.variant.pricePerMonth * sv.quantity,
    0
  );

  const totalTickets = selectedVariants.reduce(
    (sum, sv) => sum + sv.variant.ticketsPerMonth * sv.quantity,
    0
  );

  const hasSelection = selectedVariants.length > 0;

  return (
    <Card
      className={cn(
        'relative rounded-2xl overflow-hidden transition-all duration-300',
        hasSelection
          ? 'bg-[#0A1F18] border-emerald-500/30 shadow-2xl shadow-emerald-500/10'
          : 'bg-[#111111] border-white/[0.06]'
      )}
    >
      {/* Top gradient accent */}
      {hasSelection && (
        <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-emerald-500 via-emerald-400 to-emerald-500" />
      )}

      <CardContent className="p-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-2.5">
            <div
              className={cn(
                'w-8 h-8 rounded-lg flex items-center justify-center',
                hasSelection
                  ? 'bg-emerald-500/15 text-emerald-400'
                  : 'bg-white/5 text-gray-600'
              )}
            >
              <Sparkles className="w-4 h-4" />
            </div>
            <h3 className="text-lg font-bold text-white">Order Summary</h3>
          </div>

          {hasSelection && (
            <Badge className="bg-emerald-500/15 text-emerald-400 border-emerald-500/25 text-xs font-bold px-3 py-1 rounded-full">
              {totalTickets.toLocaleString()} tickets/mo
            </Badge>
          )}
        </div>

        {/* Selected Variants List */}
        {!hasSelection ? (
          <div className="py-8 text-center">
            <p className="text-gray-600 text-sm">
              Select an industry and add variants to see your summary
            </p>
          </div>
        ) : (
          <div className="space-y-3 mb-5">
            {selectedVariants.map(({ variant, quantity }) => {
              const subtotal = variant.pricePerMonth * quantity;

              return (
                <div
                  key={variant.id}
                  className="flex items-center justify-between py-2.5 px-3 rounded-xl bg-white/[0.02] border border-white/[0.04]"
                >
                  <div className="flex-1 min-w-0 mr-3">
                    <p className="text-sm font-medium text-white truncate">
                      {variant.name}
                    </p>
                    <p className="text-xs text-gray-500 tabular-nums">
                      {quantity} &times; ${variant.pricePerMonth}/mo
                    </p>
                  </div>
                  <span className="text-sm font-semibold text-emerald-400 tabular-nums shrink-0">
                    ${subtotal}/mo
                  </span>
                </div>
              );
            })}
          </div>
        )}

        {/* Divider */}
        {hasSelection && (
          <div className="border-t border-emerald-500/10 pt-4 mb-5">
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-400 font-medium">
                Total Monthly Cost
              </span>
              <span className="text-2xl font-extrabold text-white tabular-nums">
                ${totalMonthlyCost}
                <span className="text-sm font-medium text-gray-500">/mo</span>
              </span>
            </div>
          </div>
        )}

        {/* CTA Button */}
        <Button
          onClick={onContinue}
          disabled={!hasSelection}
          className={cn(
            'w-full rounded-xl font-semibold text-sm py-3.5 transition-all duration-300',
            hasSelection
              ? 'bg-gradient-to-r from-emerald-600 to-emerald-500 hover:from-emerald-500 hover:to-emerald-400 text-white shadow-lg shadow-emerald-500/25 hover:shadow-emerald-500/40'
              : 'bg-white/[0.06] text-gray-600 cursor-not-allowed'
          )}
        >
          Continue with Jarvis
          <ArrowRight className="w-4 h-4 ml-2" />
        </Button>

        {/* Disclaimer */}
        <div className="flex items-start gap-2 mt-4">
          <Info className="w-3.5 h-3.5 text-gray-600 mt-0.5 shrink-0" />
          <p className="text-[11px] text-gray-600 leading-relaxed">
            All prices in USD. Monthly billing, cancel anytime.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
