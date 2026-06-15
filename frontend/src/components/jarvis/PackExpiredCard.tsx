/**
 * PARWA PackExpiredCard (Week 6 — Day 4 Phase 6)
 *
 * "Demo pack expired. Options: free tier / repurchase."
 */

'use client';

import { AlertTriangle, RotateCcw, ArrowRight } from 'lucide-react';

interface PackExpiredCardProps {
  onRepurchase?: () => void;
}

export function PackExpiredCard({ onRepurchase }: PackExpiredCardProps) {
  return (
    <div className="glass rounded-xl p-4 border border-red-500/20 max-w-sm w-full">
      <div className="flex items-center gap-2 mb-2">
        <div className="w-8 h-8 rounded-lg bg-red-500/10 flex items-center justify-center">
          <AlertTriangle className="w-4 h-4 text-red-400" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-red-200">Demo Pack Expired</h3>
          <p className="text-[10px] text-white/40">Your trial period has ended</p>
        </div>
      </div>

      <p className="text-xs text-white/50 leading-relaxed mb-3">
        Your demo pack has expired. You can continue with 20 free messages per day,
        or purchase a new demo pack to get 500 messages and an AI demo call.
      </p>

      <div className="flex gap-2">
        <div className="flex-1 text-center py-2 rounded-lg bg-white/[0.03] border border-white/5">
          <RotateCcw className="w-3.5 h-3.5 text-white/40 mx-auto mb-0.5" />
          <p className="text-[10px] text-white/40">Free tier</p>
          <p className="text-[11px] font-medium text-white/60">20 msgs/day</p>
        </div>

        {onRepurchase && (
          <button
            onClick={onRepurchase}
            className="flex-1 flex flex-col items-center py-2 rounded-lg bg-gradient-to-r from-amber-500/20 to-amber-600/20 border border-amber-500/20 hover:from-amber-500/30 hover:to-amber-600/30 transition-all"
          >
            <ArrowRight className="w-3.5 h-3.5 text-amber-300 mx-auto mb-0.5" />
            <p className="text-[10px] text-amber-300/60">Repurchase</p>
            <p className="text-[11px] font-medium text-amber-300">$1 demo</p>
          </button>
        )}
      </div>
    </div>
  );
}
