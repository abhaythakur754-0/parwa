/**
 * PARWA Onboarding — Handoff Card
 *
 * Shown when the onboarding chat is handed off to a live agent
 * or transitions to the customer care system.
 */

'use client';

import { UserCheck, ArrowRight } from 'lucide-react';
import type { HandoffCardData } from '@/types/onboarding-jarvis';

interface HandoffCardProps {
  data: Record<string, any>;
}

export function HandoffCard({ data }: HandoffCardProps) {
  const handoffData = data as Partial<HandoffCardData>;
  const completed = handoffData.handoff_completed ?? false;
  const agentsActive = handoffData.agents_active || [];

  return (
    <div className="rounded-xl p-4 bg-white/[0.03] backdrop-blur-xl border border-emerald-500/15 max-w-sm w-full">
      <div className="flex items-center gap-2 mb-3">
        <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center">
          <UserCheck className="w-4 h-4 text-emerald-400" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-white">
            {completed ? 'Handoff Complete' : 'Connecting You…'}
          </h3>
          <p className="text-[10px] text-white/40">
            {completed
              ? 'You\'re now connected to a live agent'
              : 'Transferring to a human agent'}
          </p>
        </div>
      </div>

      {agentsActive.length > 0 && (
        <div className="py-2 px-3 rounded-lg bg-emerald-500/5 border border-emerald-500/15">
          <p className="text-[11px] text-white/50 mb-1">Active agents:</p>
          <div className="flex flex-wrap gap-1">
            {agentsActive.map((agent, idx) => (
              <span
                key={idx}
                className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-300"
              >
                {agent}
              </span>
            ))}
          </div>
        </div>
      )}

      {completed && (
        <div className="mt-3 flex items-center gap-2 text-emerald-400 text-xs">
          <ArrowRight className="w-3.5 h-3.5" />
          <span>Session transitioned successfully</span>
        </div>
      )}
    </div>
  );
}
