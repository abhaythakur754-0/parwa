'use client';

import React, { useState } from 'react';
import { cn } from '@/lib/utils';

// ── Props ────────────────────────────────────────────────────────────────

interface BillingFrequencyToggleProps {
  value: 'monthly' | 'yearly';
  onChange: (value: 'monthly' | 'yearly') => void;
  className?: string;
  showSavings?: boolean;
}

// ── Component ────────────────────────────────────────────────────────────

export function BillingFrequencyToggle({ 
  value, 
  onChange,
  className,
  showSavings = true,
}: BillingFrequencyToggleProps) {
  return (
    <div className={cn('flex flex-col items-center gap-2', className)}>
      <div className="relative flex items-center bg-[#1A1A1A] rounded-full p-1 border border-white/[0.06]">
        {/* Background slider */}
        <div 
          className={cn(
            'absolute h-[calc(100%-8px)] rounded-full bg-orange-500/20 transition-all duration-300',
            value === 'monthly' 
              ? 'left-1 w-[calc(50%-4px)]' 
              : 'left-[calc(50%+2px)] w-[calc(50%-4px)]'
          )}
        />
        
        {/* Monthly Button */}
        <button
          onClick={() => onChange('monthly')}
          className={cn(
            'relative z-10 px-4 py-2 text-sm font-medium rounded-full transition-colors',
            value === 'monthly' 
              ? 'text-orange-400' 
              : 'text-zinc-400 hover:text-zinc-300'
          )}
        >
          Monthly
        </button>
        
        {/* Yearly Button */}
        <button
          onClick={() => onChange('yearly')}
          className={cn(
            'relative z-10 px-4 py-2 text-sm font-medium rounded-full transition-colors flex items-center gap-1.5',
            value === 'yearly' 
              ? 'text-orange-400' 
              : 'text-zinc-400 hover:text-zinc-300'
          )}
        >
          Yearly
          {showSavings && (
            <span className={cn(
              'text-[10px] font-semibold px-1.5 py-0.5 rounded-full',
              value === 'yearly' 
                ? 'bg-orange-500/20 text-orange-300' 
                : 'bg-green-500/20 text-green-400'
            )}>
              -20%
            </span>
          )}
        </button>
      </div>
      
      {/* Helper text */}
      <p className="text-xs text-zinc-500">
        {value === 'yearly' 
          ? 'Save 20% with annual billing' 
          : 'Switch to yearly to save 20%'}
      </p>
    </div>
  );
}

// ── Compact Version for Modals ────────────────────────────────────────────

export function BillingFrequencyToggleCompact({ 
  value, 
  onChange,
  className,
}: Omit<BillingFrequencyToggleProps, 'showSavings'>) {
  return (
    <div className={cn('flex items-center bg-[#141414] rounded-lg p-1 border border-white/[0.04]', className)}>
      <button
        onClick={() => onChange('monthly')}
        className={cn(
          'px-3 py-1.5 text-xs font-medium rounded-md transition-colors',
          value === 'monthly' 
            ? 'bg-orange-500/20 text-orange-400' 
            : 'text-zinc-400 hover:text-zinc-300'
        )}
      >
        Monthly
      </button>
      <button
        onClick={() => onChange('yearly')}
        className={cn(
          'px-3 py-1.5 text-xs font-medium rounded-md transition-colors',
          value === 'yearly' 
            ? 'bg-orange-500/20 text-orange-400' 
            : 'text-zinc-400 hover:text-zinc-300'
        )}
      >
        Yearly (-20%)
      </button>
    </div>
  );
}

export default BillingFrequencyToggle;
