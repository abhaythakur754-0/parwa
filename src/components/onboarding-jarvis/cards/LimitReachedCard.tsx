/**
 * PARWA Onboarding — Limit Reached Card
 *
 * Shown when the user has exhausted their daily free message limit.
 */

'use client';

import { MessageSquareOff, Zap } from 'lucide-react';

export function LimitReachedCard() {
  return (
    <div className="rounded-xl p-4 bg-white/[0.03] backdrop-blur-xl border border-red-500/15 max-w-sm w-full">
      <div className="flex items-center gap-2 mb-3">
        <div className="w-8 h-8 rounded-lg bg-red-500/10 flex items-center justify-center">
          <MessageSquareOff className="w-4 h-4 text-red-400" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-white">Daily Limit Reached</h3>
          <p className="text-[10px] text-white/40">
            You&apos;ve used all your free messages for today
          </p>
        </div>
      </div>

      <p className="text-[11px] text-white/50 mb-3">
        Upgrade to a Demo Pack for 500 more messages and an AI demo call, or come back
        tomorrow for your free daily allowance.
      </p>

      <div className="flex items-center gap-2 py-2 px-3 rounded-lg bg-amber-500/5 border border-amber-500/15">
        <Zap className="w-3.5 h-3.5 text-amber-400" />
        <span className="text-[11px] text-amber-300">
          Demo Pack — 500 messages + 1 AI call for $1
        </span>
      </div>
    </div>
  );
}
