/**
 * PARWA BillSummaryCard (Week 6 — Day 4 Phase 6)
 *
 * Displays variant selections with quantity, price, and total.
 * Rendered inline in chat when message_type === 'bill_summary'.
 * Metadata shape: { variants: VariantSelection[], total: number, currency: string }
 */

'use client';

import { Receipt, ArrowRight } from 'lucide-react';
import type { VariantSelection } from '@/types/jarvis';

interface BillSummaryCardProps {
  metadata: Record<string, unknown>;
  onProceed?: () => void;
}

export function BillSummaryCard({ metadata, onProceed }: BillSummaryCardProps) {
  const variants = (metadata.variants as VariantSelection[]) || [];
  const total = (metadata.total as number) || 0;
  const currency = (metadata.currency as string) || 'USD';

  return (
    <div className="glass rounded-xl p-4 border border-orange-500/15 max-w-sm w-full">
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        <div className="w-8 h-8 rounded-lg bg-orange-500/10 flex items-center justify-center">
          <Receipt className="w-4 h-4 text-orange-400" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-white">Bill Summary</h3>
          <p className="text-[10px] text-white/40">{variants.length} variant{variants.length !== 1 ? 's' : ''} selected</p>
        </div>
      </div>

      {/* Variant rows */}
      <div className="space-y-2 mb-3">
        {variants.map((v, idx) => (
          <div
            key={v.id || idx}
            className="py-2 px-3 rounded-lg bg-white/[0.03] border border-white/5"
          >
            <div className="flex items-center justify-between">
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-white/80 truncate">
                  {v.name || v.id}
                </p>
                <p className="text-[10px] text-white/40">
                  Qty: {v.quantity}
                </p>
              </div>
              <div className="text-right ml-3">
                <p className="text-xs font-semibold text-orange-300">
                  {v.price != null ? `${currency} ${v.price.toLocaleString()}` : 'Custom'}
                </p>
              </div>
            </div>
            {/* Gap fix: Show variant features */}
            {v.features && v.features.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-1.5">
                {v.features.map((f, fi) => (
                  <span
                    key={fi}
                    className="text-[9px] px-1.5 py-0.5 rounded bg-orange-500/5 border border-orange-500/8 text-orange-300/40"
                  >
                    {f}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Total */}
      <div className="flex items-center justify-between py-2.5 px-3 rounded-lg bg-orange-500/5 border border-orange-500/15">
        <span className="text-xs font-medium text-white/70">Total</span>
        <span className="text-sm font-bold text-orange-300">
          {currency} {total.toLocaleString()}
        </span>
      </div>

      {/* Proceed CTA */}
      {onProceed && (
        <button
          onClick={onProceed}
          className="mt-3 w-full flex items-center justify-center gap-2 py-2.5 rounded-xl bg-gradient-to-r from-orange-500 to-orange-600 text-white text-xs font-medium hover:from-orange-400 hover:to-orange-500 transition-all active:scale-[0.98]"
        >
          Proceed to Payment
          <ArrowRight className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  );
}
