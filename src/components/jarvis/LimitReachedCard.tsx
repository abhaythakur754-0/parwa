/**
 * PARWA LimitReachedCard (Week 6 — Day 4 Phase 6)
 *
 * "Daily limit reached. Come back tomorrow or upgrade."
 * Replaces the old inline limit_reached banner with a richer card.
 */

'use client';

import { Clock, ArrowRight } from 'lucide-react';

interface LimitReachedCardProps {
  onUpgrade?: () => void;
}

export function LimitReachedCard({ onUpgrade }: LimitReachedCardProps) {
  return (
    <div className="glass rounded-xl p-4 border border-amber-500/20 max-w-sm w-full">
      <div className="flex items-center gap-2 mb-2">
        <div className="w-8 h-8 rounded-lg bg-amber-500/10 flex items-center justify-center">
          <Clock className="w-4 h-4 text-amber-400" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-amber-200">Daily Limit Reached</h3>
          <p className="text-[10px] text-white/40">Free messages exhausted for today</p>
        </div>
      </div>

      <p className="text-xs text-white/50 leading-relaxed mb-3">
        You&apos;ve used all 20 free messages for today. Come back tomorrow for a fresh
        batch, or upgrade to the Demo Pack for 500 messages and an AI demo call.
      </p>

      {onUpgrade && (
        <button
          onClick={onUpgrade}
          className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl bg-gradient-to-r from-amber-500 to-amber-600 text-white text-xs font-medium hover:from-amber-400 hover:to-amber-500 transition-all active:scale-[0.98]"
        >
          Upgrade for $1
          <ArrowRight className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  );
}
