'use client';

import React from 'react';
import { cn } from '@/lib/utils';

interface ConfidenceBarProps {
  value: number; // 0-1
  showLabel?: boolean;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export default function ConfidenceBar({ value, showLabel = true, size = 'md', className }: ConfidenceBarProps) {
  const pct = Math.round(value * 100);

  const colorMap = (() => {
    if (pct >= 80) return { bar: 'bg-emerald-500', text: 'text-emerald-400', bg: 'bg-emerald-500/20' };
    if (pct >= 60) return { bar: 'bg-amber-500', text: 'text-amber-400', bg: 'bg-amber-500/20' };
    if (pct >= 40) return { bar: 'bg-orange-500', text: 'text-orange-400', bg: 'bg-orange-500/20' };
    return { bar: 'bg-red-500', text: 'text-red-400', bg: 'bg-red-500/20' };
  })();

  const heightMap = { sm: 'h-1.5', md: 'h-2', lg: 'h-3' };

  return (
    <div className={cn('flex items-center gap-2', className)}>
      <div className={cn('flex-1 rounded-full overflow-hidden', heightMap[size], colorMap.bg)}>
        <div
          className={cn('h-full rounded-full transition-all duration-500', heightMap[size], colorMap.bar)}
          style={{ width: `${pct}%` }}
        />
      </div>
      {showLabel && (
        <span className={cn('text-xs font-medium tabular-nums min-w-[32px] text-right', colorMap.text)}>
          {pct}%
        </span>
      )}
    </div>
  );
}
