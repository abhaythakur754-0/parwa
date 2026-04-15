'use client';

import React from 'react';

/**
 * BillSummary Component
 *
 * Renders inside ChatMessage when message_type=bill_summary.
 * Shows plan, industry, variants, totals, and action buttons.
 */

interface BillSummaryProps {
  metadata?: Record<string, unknown> | null;
  onConfirm?: () => void;
  onChangePlan?: () => void;
}

export function BillSummary({ metadata, onConfirm, onChangePlan }: BillSummaryProps) {
  if (!metadata) return null;

  const plan = metadata.plan as string || 'parwa';
  const industry = metadata.industry as string || '';
  const totalTickets = metadata.totalTickets as number || 0;
  const totalMonthly = metadata.totalMonthly as number || 0;

  const planNames: Record<string, string> = {
    'mini-parwa': 'PARWA Starter',
    'parwa': 'PARWA Growth',
    'high-parwa': 'PARWA High',
    'starter': 'PARWA Starter',
    'growth': 'PARWA Growth',
    'high': 'PARWA High',
  };

  const variants = (metadata.variants as Array<Record<string, unknown>>) || [];

  return (
    <div className="my-2 rounded-xl border border-orange-200/60 bg-gradient-to-br from-orange-50/90 via-white/90 to-orange-50/40 backdrop-blur-sm overflow-hidden shadow-md">
      {/* Header */}
      <div className="bg-gradient-to-r from-orange-600 to-orange-500 px-4 py-2.5">
        <h4 className="text-white text-sm font-bold flex items-center gap-2">
          <span>&#x1f4cb;</span> Your PARWA Plan
        </h4>
      </div>

      {/* Body */}
      <div className="p-4 space-y-3">
        {/* Plan & Industry */}
        <div className="flex flex-wrap gap-3">
          <div className="flex-1 min-w-[120px]">
            <p className="text-[10px] text-gray-500 uppercase tracking-wide font-medium">Plan</p>
            <p className="text-sm font-bold text-gray-900">{planNames[plan] || plan}</p>
          </div>
          <div className="flex-1 min-w-[120px]">
            <p className="text-[10px] text-gray-500 uppercase tracking-wide font-medium">Industry</p>
            <p className="text-sm font-bold text-gray-900 capitalize">{industry.replace(/_/g, ' ')}</p>
          </div>
        </div>

        {/* Variants */}
        {variants.length > 0 && (
          <div>
            <p className="text-[10px] text-gray-500 uppercase tracking-wide font-medium mb-1.5">Selected Variants</p>
            <div className="space-y-1">
              {variants.map((v, i) => (
                <div key={i} className="flex items-center justify-between text-xs bg-white/60 rounded-lg px-3 py-2 border border-gray-100">
                  <span className="text-gray-700 font-medium">{v.name ?? 'Unknown'}</span>
                  <span className="text-gray-500">
                    {(typeof v.quantity === 'number' ? v.quantity : 0)}x &middot; {(typeof v.ticketsPerMonth === 'number' ? v.ticketsPerMonth : 0).toLocaleString()} tickets
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Totals */}
        <div className="border-t border-gray-100 pt-3 flex items-center justify-between">
          <div>
            <p className="text-[10px] text-gray-500 uppercase tracking-wide font-medium">Total Monthly</p>
            <p className="text-2xl font-black text-orange-600">${totalMonthly.toLocaleString()}</p>
          </div>
          <div className="text-right">
            <p className="text-[10px] text-gray-500 uppercase tracking-wide font-medium">Total Tickets</p>
            <p className="text-lg font-bold text-gray-800">{totalTickets.toLocaleString()}</p>
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="border-t border-gray-100 px-4 py-3 bg-gray-50/50 flex gap-2">
        <button
          onClick={onConfirm}
          className="flex-1 py-2 rounded-lg bg-gradient-to-r from-orange-600 to-orange-500 text-white text-xs font-bold shadow-sm hover:from-orange-500 hover:to-orange-400 transition-all active:scale-[0.98]"
        >
          Confirm &#x2713;
        </button>
        <button
          onClick={onChangePlan}
          className="flex-1 py-2 rounded-lg bg-white border border-gray-200 text-gray-700 text-xs font-medium hover:bg-gray-50 transition-all active:scale-[0.98]"
        >
          Change Plan
        </button>
      </div>
    </div>
  );
}

export default BillSummary;
