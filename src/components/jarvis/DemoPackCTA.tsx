/**
 * PARWA DemoPackCTA (Week 6 — Day 4 Phase 6)
 *
 * "Upgrade — 500 msgs + AI call for $1" call-to-action card.
 * Shown when user is approaching the free limit.
 */

'use client';

import { Zap, ArrowRight } from 'lucide-react';

interface DemoPackCTAProps {
  onPurchase?: () => Promise<void>;
  isProcessing?: boolean;
  isAlreadyActive?: boolean;
}

export function DemoPackCTA({
  onPurchase,
  isProcessing,
  isAlreadyActive,
}: DemoPackCTAProps) {
  return (
    <div className="glass rounded-xl p-4 border border-amber-500/15 max-w-sm w-full">
      <div className="flex items-center gap-2 mb-2">
        <div className="w-8 h-8 rounded-lg bg-amber-500/10 flex items-center justify-center">
          <Zap className="w-4 h-4 text-amber-400" />
        </div>
        <div className="flex-1">
          <h3 className="text-sm font-semibold text-white">Upgrade to Demo Pack</h3>
          <p className="text-[10px] text-white/40">Just $1 for unlimited access</p>
        </div>
      </div>

      <div className="flex gap-3 mb-3">
        <div className="flex-1 text-center py-2 rounded-lg bg-white/[0.03] border border-white/5">
          <p className="text-sm font-bold text-amber-300">500</p>
          <p className="text-[10px] text-white/40">messages/day</p>
        </div>
        <div className="flex-1 text-center py-2 rounded-lg bg-white/[0.03] border border-white/5">
          <p className="text-sm font-bold text-orange-300">1</p>
          <p className="text-[10px] text-white/40">AI demo call</p>
        </div>
        <div className="flex-1 text-center py-2 rounded-lg bg-white/[0.03] border border-white/5">
          <p className="text-sm font-bold text-blue-300">$1</p>
          <p className="text-[10px] text-white/40">one-time</p>
        </div>
      </div>

      {isAlreadyActive ? (
        <div className="flex items-center justify-center py-2 rounded-lg bg-orange-500/10 border border-orange-500/10">
          <span className="text-xs text-orange-300 font-medium">Demo Pack Active</span>
        </div>
      ) : (
        <button
          onClick={onPurchase}
          disabled={isProcessing}
          className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl bg-gradient-to-r from-amber-500 to-amber-600 text-white text-xs font-medium hover:from-amber-400 hover:to-amber-500 disabled:opacity-40 transition-all active:scale-[0.98]"
        >
          {isProcessing ? (
            <span className="inline-block w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
          ) : (
            <>
              Get Demo Pack for $1
              <ArrowRight className="w-3.5 h-3.5" />
            </>
          )}
        </button>
      )}
    </div>
  );
}
