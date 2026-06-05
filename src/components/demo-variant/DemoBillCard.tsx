/**
 * PARWA DemoBillCard — Bill Summary & ROI Display
 *
 * Shows per-ticket cost breakdown, ROI, and monthly estimates.
 * Matches ORANGE design system.
 */

'use client';

import { DollarSign, TrendingDown, TrendingUp, Calculator } from 'lucide-react';
import type { DemoBillSummary } from '@/types/demo-variant';

interface DemoBillCardProps {
  billSummary: DemoBillSummary | null;
  compact?: boolean;
}

export function DemoBillCard({ billSummary, compact }: DemoBillCardProps) {
  if (!billSummary) return null;

  if (compact) {
    return (
      <div className="flex items-center gap-3 text-xs">
        <div className="flex items-center gap-1">
          <DollarSign className="w-3.5 h-3.5 text-amber-400/60" />
          <span className="text-white/50">${billSummary.total.toLocaleString()}/mo</span>
        </div>
        <div className="flex items-center gap-1">
          <TrendingUp className="w-3.5 h-3.5 text-emerald-400/60" />
          <span className="text-emerald-400/70">Save {billSummary.savings_percentage}%</span>
        </div>
      </div>
    );
  }

  return (
    <div className="glass rounded-xl p-4 border border-amber-500/15 max-w-sm w-full space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-white flex items-center gap-2">
          <Calculator className="w-4 h-4 text-amber-400" />
          Bill Summary
        </h3>
        <span className="text-lg font-bold text-gradient-gold">
          ${billSummary.total.toLocaleString()}
          <span className="text-[10px] text-white/30 font-normal">/mo</span>
        </span>
      </div>

      {/* Line items */}
      <div className="space-y-1.5">
        {billSummary.items.map((item, idx) => (
          <div key={idx} className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-1 h-1 rounded-full bg-amber-400/60" />
              <span className="text-[11px] text-white/50">{item.name}</span>
            </div>
            <span className="text-[11px] font-medium text-white/60">
              ${item.total.toLocaleString()}
            </span>
          </div>
        ))}

        {/* Tax */}
        <div className="flex items-center justify-between pt-1 border-t border-white/[0.04]">
          <span className="text-[11px] text-white/30">Tax (8%)</span>
          <span className="text-[11px] text-white/40">${billSummary.tax.toFixed(2)}</span>
        </div>
      </div>

      {/* Total */}
      <div className="flex items-center justify-between py-2 border-t border-orange-500/10">
        <span className="text-xs font-semibold text-white/70">Total Monthly</span>
        <span className="text-base font-bold text-gradient">${billSummary.total.toLocaleString()}</span>
      </div>

      {/* ROI Section */}
      <div className="grid grid-cols-2 gap-2 pt-2 border-t border-white/[0.04]">
        <div className="text-center py-2 rounded-lg bg-white/[0.03] border border-white/5">
          <div className="flex items-center justify-center gap-1 mb-0.5">
            <TrendingDown className="w-3 h-3 text-emerald-400/60" />
            <span className="text-sm font-bold text-emerald-400">{billSummary.savings_percentage}%</span>
          </div>
          <span className="text-[9px] text-white/25">vs hiring</span>
        </div>
        <div className="text-center py-2 rounded-lg bg-white/[0.03] border border-white/5">
          <div className="flex items-center justify-center gap-1 mb-0.5">
            <DollarSign className="w-3 h-3 text-amber-400/60" />
            <span className="text-sm font-bold text-amber-400">${billSummary.savings_vs_human.toLocaleString()}</span>
          </div>
          <span className="text-[9px] text-white/25">saved/mo</span>
        </div>
      </div>

      {/* Annual estimate */}
      <p className="text-[10px] text-white/20 text-center">
        Annual: ${billSummary.annual_estimate.toLocaleString()} (15% off) · ROI in {billSummary.roi_months} months
      </p>
    </div>
  );
}
