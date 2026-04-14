'use client';

import React from 'react';
import { cn } from '@/lib/utils';

// ── Preset Ranges ─────────────────────────────────────────────────────

interface PresetRange {
  label: string;
  value: 'today' | '7d' | '30d' | '90d' | 'custom';
}

const presetRanges: PresetRange[] = [
  { label: 'Today', value: 'today' },
  { label: 'Last 7 Days', value: '7d' },
  { label: 'Last 30 Days', value: '30d' },
  { label: 'Last 90 Days', value: '90d' },
];

// ── Helper: get date range from preset ────────────────────────────────

function getDateRange(preset: string): { start_date: string; end_date: string } {
  const end = new Date();
  const start = new Date();

  switch (preset) {
    case 'today':
      start.setHours(0, 0, 0, 0);
      break;
    case '7d':
      start.setDate(start.getDate() - 7);
      break;
    case '30d':
      start.setDate(start.getDate() - 30);
      break;
    case '90d':
      start.setDate(start.getDate() - 90);
      break;
    default:
      start.setDate(start.getDate() - 30);
  }

  return {
    start_date: start.toISOString().split('T')[0],
    end_date: end.toISOString().split('T')[0],
  };
}

// ── Props ─────────────────────────────────────────────────────────────

interface DateRangeSelectorProps {
  value: string; // preset value or 'custom'
  onChange: (range: { start_date: string; end_date: string }) => void;
  className?: string;
}

// ── DateRangeSelector Component ───────────────────────────────────────

export default function DateRangeSelector({
  value,
  onChange,
  className,
}: DateRangeSelectorProps) {
  return (
    <div className={cn('flex items-center gap-1 bg-white/[0.04] rounded-lg p-1', className)} role="tablist" aria-label="Date range">
      {presetRanges.map((preset) => (
        <button
          key={preset.value}
          role="tab"
          aria-selected={value === preset.value}
          onClick={() => onChange(getDateRange(preset.value))}
          className={cn(
            'px-3 py-1.5 rounded-md text-xs font-medium transition-all duration-200',
            value === preset.value
              ? 'bg-orange-500/15 text-orange-400 shadow-sm'
              : 'text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.05]'
          )}
        >
          {preset.label}
        </button>
      ))}
    </div>
  );
}

// ── Export helper ─────────────────────────────────────────────────────

export { getDateRange };
