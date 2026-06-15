/**
 * PARWA Onboarding BillSummaryCard
 *
 * Shows selected variants with quantities, per-unit pricing, and total.
 * Emerald/parrot green theme.
 */

'use client';

import { Receipt, ArrowRight } from 'lucide-react';
import type { BillItem, BillSummaryData } from '@/types/onboarding-jarvis';

interface BillSummaryCardProps {
  metadata: Record<string, unknown>;
  onProceed?: () => void;
}

export function BillSummaryCard({ metadata, onProceed }: BillSummaryCardProps) {
  const items = (metadata.items as BillItem[]) || [];
  const summaryData = (metadata as Partial<BillSummaryData>);
  const total = (metadata.total as number) || summaryData.total || 0;
  const subtotal = (metadata.subtotal as number) || summaryData.subtotal || total;
  const currency = (metadata.currency as string) || 'USD';
  const billingPeriod = (metadata.billing_period as string) || 'monthly';

  return (
    <div className="rounded-xl p-4 bg-white/[0.03] backdrop-blur-xl border border-emerald-500/15 max-w-sm w-full">
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center">
          <Receipt className="w-4 h-4 text-emerald-400" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-white">Bill Summary</h3>
          <p className="text-[10px] text-white/40">
            {items.length || 0} item{(items.length || 0) !== 1 ? 's' : ''} · {billingPeriod}
          </p>
        </div>
      </div>

      {/* Item rows */}
      {items.length > 0 ? (
        <div className="space-y-2 mb-3">
          {items.map((item, idx) => (
            <div
              key={item.variant_id || idx}
              className="py-2 px-3 rounded-lg bg-white/[0.03] border border-white/5"
            >
              <div className="flex items-center justify-between">
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium text-white/80 truncate">
                    {item.variant_name}
                  </p>
                  <p className="text-[10px] text-white/40">
                    Qty: {item.quantity} × {currency} {item.price_per_unit.toLocaleString()}
                  </p>
                </div>
                <div className="text-right ml-3">
                  <p className="text-xs font-semibold text-emerald-300">
                    {currency} {item.total.toLocaleString()}
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="py-3 mb-3 text-center">
          <p className="text-xs text-white/40">No items in bill</p>
        </div>
      )}

      {/* Subtotal + Total */}
      {items.length > 0 && (
        <div className="space-y-1.5 mb-3">
          <div className="flex items-center justify-between px-3">
            <span className="text-[11px] text-white/40">Subtotal</span>
            <span className="text-[11px] text-white/60">{currency} {subtotal.toLocaleString()}</span>
          </div>
          <div className="flex items-center justify-between py-2.5 px-3 rounded-lg bg-emerald-500/5 border border-emerald-500/15">
            <span className="text-xs font-medium text-white/70">Total</span>
            <span className="text-sm font-bold text-emerald-300">
              {currency} {total.toLocaleString()}
            </span>
          </div>
        </div>
      )}

      {/* Proceed CTA */}
      {onProceed && (
        <button
          onClick={onProceed}
          className="mt-3 w-full flex items-center justify-center gap-2 py-2.5 rounded-xl bg-gradient-to-r from-emerald-500 to-emerald-600 text-white text-xs font-medium hover:from-emerald-400 hover:to-emerald-500 transition-all active:scale-[0.98]"
        >
          Proceed to Payment
          <ArrowRight className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  );
}
