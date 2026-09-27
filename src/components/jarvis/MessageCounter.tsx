/**
 * PARWA MessageCounter (Week 6 — Day 4 Phase 6)
 *
 * Shows "16/20 messages remaining today" inline in chat.
 * Visual bar showing usage percentage.
 */

'use client';

import { MessageSquare } from 'lucide-react';

interface MessageCounterProps {
  remaining: number;
  total: number;
  isDemoPack?: boolean;
}

export function MessageCounter({ remaining, total, isDemoPack }: MessageCounterProps) {
  const used = total - remaining;
  const percentage = Math.min((used / total) * 100, 100);
  const isLow = remaining <= 5 && remaining > 0;
  const isEmpty = remaining <= 0;

  const barColor = isEmpty
    ? 'bg-red-500'
    : isLow
      ? 'bg-amber-500'
      : 'bg-orange-500';

  const textColor = isEmpty
    ? 'text-red-300'
    : isLow
      ? 'text-amber-300'
      : 'text-orange-300';

  return (
    <div className="flex items-center gap-2.5 px-3 py-2 rounded-lg bg-white/[0.03] border border-white/5 max-w-xs">
      <MessageSquare className="w-3.5 h-3.5 text-white/30 shrink-0" />

      <div className="flex-1 min-w-0">
        <div className="flex items-baseline justify-between mb-1">
          <span className={`text-[11px] font-medium ${textColor}`}>
            {isEmpty ? 'No messages left' : `${remaining}/${total} remaining today`}
          </span>
          {isDemoPack && (
            <span className="text-[9px] text-amber-400/60 ml-1">DEMO</span>
          )}
        </div>
        <div className="w-full h-1 rounded-full bg-white/5 overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${barColor}`}
            style={{ width: `${percentage}%` }}
          />
        </div>
      </div>
    </div>
  );
}
