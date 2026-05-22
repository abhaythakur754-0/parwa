/**
 * PARWA DemoUsageTracker — Usage Progress Display
 *
 * Shows message and call usage with progress bars.
 * Matches ORANGE design system.
 */

'use client';

import { MessageSquare, Phone, Clock } from 'lucide-react';
import type { DemoUsage } from '@/types/demo-variant';

interface DemoUsageTrackerProps {
  usage: DemoUsage | null;
  compact?: boolean;
}

export function DemoUsageTracker({ usage, compact }: DemoUsageTrackerProps) {
  if (!usage) return null;

  const msgPercent = Math.min((usage.user_messages_sent / usage.user_messages_limit) * 100, 100);
  const callPercent = Math.min((usage.call_seconds_used / usage.call_seconds_limit) * 100, 100);
  const isMsgLow = usage.user_messages_limit - usage.user_messages_sent <= 10;
  const isMsgEmpty = usage.user_messages_sent >= usage.user_messages_limit;

  if (compact) {
    return (
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5">
          <MessageSquare className="w-3.5 h-3.5 text-orange-400/50" />
          <span className={`text-[11px] font-medium ${isMsgEmpty ? 'text-red-300' : isMsgLow ? 'text-amber-300' : 'text-orange-300'}`}>
            {usage.user_messages_limit - usage.user_messages_sent}/{usage.user_messages_limit}
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <Phone className="w-3.5 h-3.5 text-orange-400/50" />
          <span className="text-[11px] font-medium text-orange-300">
            {usage.is_call_available ? 'Available' : 'Used'}
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="glass rounded-xl p-4 border border-orange-500/15 max-w-sm w-full space-y-3">
      <h3 className="text-sm font-semibold text-white flex items-center gap-2">
        <Clock className="w-4 h-4 text-orange-400" />
        Demo Pack Usage
      </h3>

      {/* Messages */}
      <div>
        <div className="flex items-center justify-between mb-1">
          <div className="flex items-center gap-1.5">
            <MessageSquare className="w-3.5 h-3.5 text-white/30" />
            <span className="text-[11px] text-white/50">Messages</span>
          </div>
          <span className={`text-[11px] font-medium ${isMsgEmpty ? 'text-red-300' : isMsgLow ? 'text-amber-300' : 'text-orange-300'}`}>
            {usage.user_messages_limit - usage.user_messages_sent} remaining
          </span>
        </div>
        <div className="w-full h-1.5 rounded-full bg-white/5 overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${isMsgEmpty ? 'bg-red-500' : isMsgLow ? 'bg-amber-500' : 'bg-orange-500'}`}
            style={{ width: `${msgPercent}%` }}
          />
        </div>
      </div>

      {/* Call */}
      <div>
        <div className="flex items-center justify-between mb-1">
          <div className="flex items-center gap-1.5">
            <Phone className="w-3.5 h-3.5 text-white/30" />
            <span className="text-[11px] text-white/50">Demo Call</span>
          </div>
          <span className={`text-[11px] font-medium ${usage.is_call_available ? 'text-orange-300' : 'text-red-300'}`}>
            {usage.is_call_available ? '3 min available' : 'Used'}
          </span>
        </div>
        <div className="w-full h-1.5 rounded-full bg-white/5 overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${usage.is_call_available ? 'bg-orange-500' : 'bg-red-500'}`}
            style={{ width: `${callPercent}%` }}
          />
        </div>
      </div>
    </div>
  );
}
