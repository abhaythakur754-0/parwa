/**
 * PARWA DemoIndustryPicker — Industry Selection
 *
 * Grid of industry cards for the demo flow.
 * Matches ORANGE design system.
 */

'use client';

import { cn } from '@/lib/utils';
import { DEMO_INDUSTRIES } from '@/lib/demo-store';

interface DemoIndustryPickerProps {
  selectedIndustry: string;
  onSelect: (industry: string) => void;
}

export function DemoIndustryPicker({ selectedIndustry, onSelect }: DemoIndustryPickerProps) {
  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-white/60">Select your industry</h3>
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-2">
        {DEMO_INDUSTRIES.map((ind) => {
          const isSelected = selectedIndustry === ind.id;
          return (
            <button
              key={ind.id}
              onClick={() => onSelect(ind.id)}
              className={cn(
                'flex flex-col items-center gap-1.5 p-3 rounded-xl border transition-all duration-300',
                isSelected
                  ? 'border-orange-500/40 bg-orange-500/10 shadow-sm shadow-orange-500/10'
                  : 'border-white/[0.06] bg-white/[0.02] hover:border-white/15 hover:bg-white/[0.04]',
              )}
            >
              <span className="text-xl">{ind.icon}</span>
              <span className={cn(
                'text-[11px] font-medium',
                isSelected ? 'text-orange-300' : 'text-white/40',
              )}>
                {ind.name}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
