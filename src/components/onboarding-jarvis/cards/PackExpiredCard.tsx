/**
 * PARWA Onboarding — Pack Expired Card
 *
 * Shown when the user's demo pack has expired.
 */

'use client';

import { Clock, RefreshCw } from 'lucide-react';

export function PackExpiredCard() {
  return (
    <div className="rounded-xl p-4 bg-white/[0.03] backdrop-blur-xl border border-amber-500/15 max-w-sm w-full">
      <div className="flex items-center gap-2 mb-3">
        <div className="w-8 h-8 rounded-lg bg-amber-500/10 flex items-center justify-center">
          <Clock className="w-4 h-4 text-amber-400" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-white">Demo Pack Expired</h3>
          <p className="text-[10px] text-white/40">
            Your demo pack has reached its time limit
          </p>
        </div>
      </div>

      <p className="text-[11px] text-white/50 mb-3">
        Your demo pack was valid for 24 hours. You can purchase a new one or
        upgrade to a full plan to continue using PARWA.
      </p>

      <div className="flex items-center gap-2 py-2 px-3 rounded-lg bg-amber-500/5 border border-amber-500/15">
        <RefreshCw className="w-3.5 h-3.5 text-amber-400" />
        <span className="text-[11px] text-amber-300">
          Purchase a new demo pack or upgrade your plan
        </span>
      </div>
    </div>
  );
}
