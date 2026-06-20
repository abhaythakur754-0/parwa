/**
 * PARWA Onboarding — Demo Pack CTA Card
 *
 * Encourages users to purchase a demo pack when running low on messages.
 */

'use client';

import { Zap, ArrowRight } from 'lucide-react';

interface DemoPackCTAProps {
  remaining: number;
  onPurchase: () => void;
}

export function DemoPackCTA({ remaining, onPurchase }: DemoPackCTAProps) {
  return (
    <div className="rounded-xl p-4 bg-white/[0.03] backdrop-blur-xl border border-amber-500/15 max-w-sm w-full">
      <div className="flex items-center gap-2 mb-3">
        <div className="w-8 h-8 rounded-lg bg-amber-500/10 flex items-center justify-center">
          <Zap className="w-4 h-4 text-amber-400" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-white">Running Low</h3>
          <p className="text-[10px] text-white/40">
            Only {remaining} message{remaining !== 1 ? 's' : ''} left today
          </p>
        </div>
      </div>

      <p className="text-[11px] text-white/50 mb-3">
        Get 500 messages + 1 AI demo call for just $1 with the Demo Pack.
      </p>

      <button
        onClick={onPurchase}
        className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl bg-gradient-to-r from-amber-500 to-amber-600 text-white text-xs font-medium hover:from-amber-400 hover:to-amber-500 transition-all active:scale-[0.98]"
      >
        Get Demo Pack — $1
        <ArrowRight className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}
