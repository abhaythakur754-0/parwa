'use client';

import React from 'react';
import { cn } from '@/lib/utils';
import type { GSDState } from '@/types/ticket';

interface GSDStateIndicatorProps {
  currentState: GSDState;
  className?: string;
}

const steps: { state: GSDState; label: string; shortLabel: string }[] = [
  { state: 'greeting', label: 'Greeting', shortLabel: 'Greet' },
  { state: 'understanding', label: 'Understanding', shortLabel: 'Understand' },
  { state: 'resolution', label: 'Resolution', shortLabel: 'Resolve' },
  { state: 'confirmation', label: 'Confirmation', shortLabel: 'Confirm' },
  { state: 'closing', label: 'Closing', shortLabel: 'Close' },
];

const stateOrder: Record<GSDState, number> = {
  greeting: 0,
  understanding: 1,
  resolution: 2,
  confirmation: 3,
  closing: 4,
};

export default function GSDStateIndicator({ currentState, className }: GSDStateIndicatorProps) {
  const currentIdx = stateOrder[currentState];

  return (
    <div className={cn('flex items-center gap-0', className)}>
      {steps.map((step, idx) => {
        const isCompleted = idx < currentIdx;
        const isCurrent = idx === currentIdx;
        const isPending = idx > currentIdx;

        return (
          <React.Fragment key={step.state}>
            {/* Step circle */}
            <div className="flex flex-col items-center gap-1">
              <div
                className={cn(
                  'w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold transition-all duration-300 border',
                  isCompleted
                    ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-400'
                    : isCurrent
                      ? 'bg-orange-500/20 border-orange-500/40 text-orange-400 ring-2 ring-orange-500/20'
                      : 'bg-white/[0.04] border-white/[0.08] text-zinc-600'
                )}
              >
                {isCompleted ? (
                  <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                  </svg>
                ) : (
                  idx + 1
                )}
              </div>
              <span
                className={cn(
                  'text-[9px] font-medium hidden lg:block max-w-[52px] text-center leading-tight',
                  isCompleted ? 'text-emerald-400/70' : isCurrent ? 'text-orange-400' : 'text-zinc-600'
                )}
              >
                {step.shortLabel}
              </span>
            </div>

            {/* Connector line */}
            {idx < steps.length - 1 && (
              <div
                className={cn(
                  'h-0.5 w-4 sm:w-6 lg:w-8 transition-all duration-300',
                  isCompleted ? 'bg-emerald-500/40' : 'bg-white/[0.06]'
                )}
              />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}
