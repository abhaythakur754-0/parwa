/**
 * PARWA Onboarding — Demo Call Card
 *
 * Shows a card to book an AI demo call during onboarding.
 */

'use client';

import { Phone, Clock } from 'lucide-react';

interface DemoCallCardProps {
  data: Record<string, any>;
}

export function DemoCallCard({ data }: DemoCallCardProps) {
  const phone = data.phone_number || '';
  const duration = data.duration_minutes || 3;
  const price = data.price || '$1';

  return (
    <div className="rounded-xl p-4 bg-white/[0.03] backdrop-blur-xl border border-emerald-500/15 max-w-sm w-full">
      <div className="flex items-center gap-2 mb-3">
        <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center">
          <Phone className="w-4 h-4 text-emerald-400" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-white">AI Demo Call</h3>
          <p className="text-[10px] text-white/40">Experience PARWA&apos;s AI agent on a live call</p>
        </div>
      </div>

      <div className="space-y-2 mb-3">
        <div className="flex items-center gap-2 px-1">
          <Clock className="w-3.5 h-3.5 text-emerald-400/60" />
          <span className="text-[11px] text-white/50">{duration} min demo call</span>
        </div>
        <div className="flex items-center gap-2 px-1">
          <Phone className="w-3.5 h-3.5 text-emerald-400/60" />
          <span className="text-[11px] text-white/50">
            {phone ? `To: ${phone}` : 'Phone number required'}
          </span>
        </div>
      </div>

      <div className="flex items-center justify-between py-2 px-3 rounded-lg bg-emerald-500/5 border border-emerald-500/15">
        <span className="text-xs text-white/60">Price</span>
        <span className="text-sm font-bold text-emerald-300">{price}</span>
      </div>
    </div>
  );
}
