/**
 * PARWA CallHistoryRow
 *
 * Table row for call history with:
 * - Direction icon (outbound/inbound)
 * - Phone number (clickable to view detail)
 * - Status badge (color-coded)
 * - Duration
 * - Intent detected
 * - Time ago
 * - Click to expand detail
 */

'use client';

import { PhoneOutgoing, PhoneIncoming, Clock } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { VoiceCall, CallStatus } from '@/types/voice';

interface CallHistoryRowProps {
  call: VoiceCall;
  onClick: (call: VoiceCall) => void;
}

// ── Status Badge Config ─────────────────────────────────────────────

const statusBadgeConfig: Record<string, { classes: string; label: string }> = {
  'completed':   { classes: 'bg-zinc-500/10 text-zinc-400 border-zinc-500/20', label: 'Completed' },
  'failed':      { classes: 'bg-red-500/10 text-red-400 border-red-500/20', label: 'Failed' },
  'busy':        { classes: 'bg-amber-500/10 text-amber-400 border-amber-500/20', label: 'Busy' },
  'no-answer':   { classes: 'bg-zinc-500/10 text-zinc-500 border-zinc-500/20', label: 'No Answer' },
  'canceled':    { classes: 'bg-zinc-600/10 text-zinc-500 border-zinc-600/20', label: 'Canceled' },
  'queued':      { classes: 'bg-amber-500/10 text-amber-400 border-amber-500/20', label: 'Queued' },
  'ringing':     { classes: 'bg-blue-500/10 text-blue-400 border-blue-500/20', label: 'Ringing' },
  'in-progress': { classes: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20', label: 'Active' },
};

const variantColors: Record<string, string> = {
  parwa: 'text-zinc-500',
  parwa_pro: 'text-blue-400',
  parwa_high: 'text-purple-400',
};

const variantLabels: Record<string, string> = {
  parwa: 'Mini',
  parwa_pro: 'Pro',
  parwa_high: 'High',
};

// ── Component ───────────────────────────────────────────────────────

export function CallHistoryRow({ call, onClick }: CallHistoryRowProps) {
  const badge = statusBadgeConfig[call.status] || statusBadgeConfig['completed'];
  const phoneNumber = call.direction === 'outbound' ? call.to_number : call.from_number;
  const isOutbound = call.direction === 'outbound';

  const formatDuration = (seconds: number) => {
    if (seconds === 0) return '—';
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  const formatTimeAgo = (isoString: string) => {
    const now = Date.now();
    const then = new Date(isoString).getTime();
    const diff = Math.floor((now - then) / 1000);

    if (diff < 60) return `${diff}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
  };

  return (
    <tr
      onClick={() => onClick(call)}
      className="cursor-pointer hover:bg-white/[0.02] transition-colors border-b border-white/[0.04] last:border-0"
    >
      {/* Direction */}
      <td className="py-3 px-3">
        <div className={cn(
          'w-7 h-7 rounded-lg flex items-center justify-center',
          isOutbound ? 'bg-orange-500/10' : 'bg-blue-500/10'
        )}>
          {isOutbound ? (
            <PhoneOutgoing className="w-3.5 h-3.5 text-orange-400" />
          ) : (
            <PhoneIncoming className="w-3.5 h-3.5 text-blue-400" />
          )}
        </div>
      </td>

      {/* Phone Number */}
      <td className="py-3 px-3">
        <span className="text-sm font-medium text-white/80">{phoneNumber}</span>
        <span className={cn(
          'ml-2 text-[10px]',
          variantColors[call.variant_tier] || 'text-zinc-600'
        )}>
          {variantLabels[call.variant_tier] || call.variant_tier}
        </span>
      </td>

      {/* Status */}
      <td className="py-3 px-3">
        <span className={cn(
          'text-[10px] px-2 py-0.5 rounded-full border',
          badge.classes
        )}>
          {badge.label}
        </span>
      </td>

      {/* Duration */}
      <td className="py-3 px-3">
        <span className="text-xs text-white/60 font-mono">{formatDuration(call.duration_seconds)}</span>
      </td>

      {/* Intent */}
      <td className="py-3 px-3 hidden sm:table-cell">
        <span className="text-xs text-white/50">
          {call.intent_detected || '—'}
        </span>
      </td>

      {/* Time */}
      <td className="py-3 px-3 hidden md:table-cell">
        <div className="flex items-center gap-1">
          <Clock className="w-3 h-3 text-white/20" />
          <span className="text-xs text-white/40">{formatTimeAgo(call.created_at)}</span>
        </div>
      </td>
    </tr>
  );
}
