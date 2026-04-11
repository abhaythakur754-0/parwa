/**
 * PARWA HandoffCard (Week 6 — Day 4 Phase 6)
 *
 * Celebration card shown when onboarding is complete.
 * "Meet Customer Care Jarvis" button triggers handoff.
 * Metadata: { new_session_id?: string }
 */

'use client';

import { PartyPopper, ArrowRight, Headphones } from 'lucide-react';

interface HandoffCardProps {
  metadata: Record<string, unknown>;
  onHandoff?: () => Promise<void>;
  isHandoffComplete?: boolean;
}

export function HandoffCard({
  metadata,
  onHandoff,
  isHandoffComplete,
}: HandoffCardProps) {
  return (
    <div className="glass rounded-xl p-4 border border-purple-500/15 max-w-sm w-full">
      {/* Celebration */}
      <div className="flex items-center justify-center mb-3">
        <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-purple-500/20 to-emerald-500/20 border border-purple-500/15 flex items-center justify-center">
          <PartyPopper className="w-7 h-7 text-purple-300" />
        </div>
      </div>

      <div className="text-center mb-3">
        <h3 className="text-sm font-semibold text-white mb-1">
          Onboarding Complete!
        </h3>
        <p className="text-xs text-white/50 leading-relaxed">
          Great choices! You&apos;re all set up. Let me hand you over to our
          Customer Care Jarvis who can help with billing, support, and more.
        </p>
      </div>

      {/* Handoff button */}
      {isHandoffComplete ? (
        <div className="flex items-center justify-center gap-2 py-3 rounded-xl bg-emerald-500/10 border border-emerald-500/15">
          <Headphones className="w-4 h-4 text-emerald-400" />
          <span className="text-xs font-medium text-emerald-300">
            Connected to Customer Care
          </span>
        </div>
      ) : (
        <button
          onClick={onHandoff}
          className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl bg-gradient-to-r from-purple-500 to-purple-600 text-white text-xs font-medium hover:from-purple-400 hover:to-purple-500 transition-all active:scale-[0.98]"
        >
          Meet Customer Care Jarvis
          <ArrowRight className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  );
}
