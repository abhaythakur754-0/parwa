/**
 * PARWA RechargeCTACard (Week 6 — Day 4 Phase 6)
 *
 * Post-call option to recharge Demo Pack or subscribe.
 * Metadata: { pack_type, message }
 */

'use client';

import { Zap, ArrowRight } from 'lucide-react';

interface RechargeCTACardProps {
  metadata: Record<string, unknown>;
  onRecharge?: () => Promise<void>;
  isProcessing?: boolean;
}

export function RechargeCTACard({
  metadata,
  onRecharge,
  isProcessing,
}: RechargeCTACardProps) {
  const message =
    (metadata.message as string) ||
    'Enjoyed the demo? Get 500 more messages + another AI call for just $1.';

  return (
    <div className="glass rounded-xl p-4 border border-orange-500/15 max-w-sm w-full">
      <div className="flex items-center gap-2 mb-2">
        <div className="w-8 h-8 rounded-lg bg-orange-500/10 flex items-center justify-center">
          <Zap className="w-4 h-4 text-orange-400" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-white">Continue Exploring</h3>
          <p className="text-[10px] text-white/40">Recharge your demo pack</p>
        </div>
      </div>

      <p className="text-xs text-white/50 leading-relaxed mb-3">{message}</p>

      {onRecharge && (
        <button
          onClick={onRecharge}
          disabled={isProcessing}
          className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl bg-gradient-to-r from-orange-500 to-orange-600 text-white text-xs font-medium hover:from-orange-400 hover:to-orange-500 disabled:opacity-40 transition-all active:scale-[0.98]"
        >
          {isProcessing ? (
            <span className="inline-block w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
          ) : (
            <>
              Recharge for $1
              <ArrowRight className="w-3.5 h-3.5" />
            </>
          )}
        </button>
      )}
    </div>
  );
}
