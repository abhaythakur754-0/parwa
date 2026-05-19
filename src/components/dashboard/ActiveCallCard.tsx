/**
 * PARWA ActiveCallCard
 *
 * Shows a single active call with live status, duration timer,
 * variant tier badge, and action buttons (End, Transfer).
 */

'use client';

import { useState, useEffect, useRef } from 'react';
import { Phone, PhoneOff, PhoneForwarded, Clock, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { VoiceCall, CallStatus } from '@/types/voice';

interface ActiveCallCardProps {
  call: VoiceCall;
  onEnd: (id: string) => void;
  onTransfer: (id: string) => void;
  onClick: (call: VoiceCall) => void;
}

// ── Status Config ───────────────────────────────────────────────────

const statusConfig: Record<string, { color: string; dot: string; label: string; animate: boolean }> = {
  'queued':     { color: 'text-amber-400', dot: 'bg-amber-400', label: 'Queued', animate: false },
  'ringing':    { color: 'text-blue-400', dot: 'bg-blue-400', label: 'Ringing', animate: true },
  'in-progress': { color: 'text-emerald-400', dot: 'bg-emerald-400', label: 'In Progress', animate: true },
  'completed':  { color: 'text-zinc-400', dot: 'bg-zinc-400', label: 'Completed', animate: false },
  'failed':     { color: 'text-red-400', dot: 'bg-red-400', label: 'Failed', animate: false },
  'busy':       { color: 'text-amber-400', dot: 'bg-amber-400', label: 'Busy', animate: false },
  'no-answer':  { color: 'text-zinc-400', dot: 'bg-zinc-500', label: 'No Answer', animate: false },
  'canceled':   { color: 'text-zinc-500', dot: 'bg-zinc-600', label: 'Canceled', animate: false },
};

const variantColors: Record<string, string> = {
  parwa: 'bg-zinc-500/10 text-zinc-400 border-zinc-500/20',
  parwa_pro: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
  parwa_high: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
};

// ── Component ───────────────────────────────────────────────────────

export function ActiveCallCard({ call, onEnd, onTransfer, onClick }: ActiveCallCardProps) {
  const [elapsed, setElapsed] = useState(0);
  const [ending, setEnding] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const config = statusConfig[call.status] || statusConfig['queued'];
  const phoneNumber = call.direction === 'outbound' ? call.to_number : call.from_number;

  // ── Duration Timer ──────────────────────────────────────────────

  useEffect(() => {
    if (call.status === 'in-progress' || call.status === 'ringing') {
      const startTime = call.started_at ? new Date(call.started_at).getTime() : Date.now();
      const tick = () => setElapsed(Math.floor((Date.now() - startTime) / 1000));
      tick();
      timerRef.current = setInterval(tick, 1000);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [call.status, call.started_at]);

  const formatDuration = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  const handleEnd = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setEnding(true);
    onEnd(call.id);
  };

  const handleTransfer = (e: React.MouseEvent) => {
    e.stopPropagation();
    onTransfer(call.id);
  };

  return (
    <div
      onClick={() => onClick(call)}
      className={cn(
        'rounded-xl border p-4 cursor-pointer transition-all duration-300 hover:border-white/[0.12]',
        'bg-[#1A1A1A] border-white/[0.06]',
        config.animate && 'border-emerald-500/10'
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className={cn(
            'w-8 h-8 rounded-lg flex items-center justify-center',
            call.status === 'in-progress' ? 'bg-emerald-500/10' :
            call.status === 'ringing' ? 'bg-blue-500/10' : 'bg-amber-500/10'
          )}>
            <Phone className={cn('w-4 h-4', config.animate && 'animate-pulse', config.color)} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className={cn('w-2 h-2 rounded-full', config.dot, config.animate && 'animate-pulse')} />
              <span className={cn('text-xs font-medium', config.color)}>{config.label}</span>
            </div>
            <p className="text-sm font-semibold text-white mt-0.5">{phoneNumber}</p>
          </div>
        </div>

        {/* Duration */}
        {(call.status === 'in-progress' || call.status === 'ringing') && (
          <div className="flex items-center gap-1 text-xs font-mono text-white/60">
            <Clock className="w-3 h-3" />
            {formatDuration(elapsed)}
          </div>
        )}
      </div>

      {/* Variant Badge */}
      <div className="flex items-center gap-2 mb-3">
        <span className={cn(
          'text-[10px] px-2 py-0.5 rounded-full border',
          variantColors[call.variant_tier] || variantColors.parwa
        )}>
          {call.variant_tier.replace('parwa', 'Mini').replace('_', ' ').trim() || 'Mini'}
        </span>
        {call.intent_detected && (
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-orange-500/10 text-orange-400 border border-orange-500/20">
            {call.intent_detected}
          </span>
        )}
      </div>

      {/* Actions */}
      <div className="flex gap-2 pt-3 border-t border-white/[0.04]">
        <button
          onClick={handleEnd}
          disabled={ending}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-500/10 text-red-400 text-xs font-medium hover:bg-red-500/20 transition-colors disabled:opacity-50"
        >
          {ending ? (
            <Loader2 className="w-3 h-3 animate-spin" />
          ) : (
            <PhoneOff className="w-3 h-3" />
          )}
          End
        </button>
        {call.status === 'in-progress' && (
          <button
            onClick={handleTransfer}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/[0.05] text-white/60 text-xs font-medium hover:bg-white/[0.08] hover:text-white/80 transition-colors"
          >
            <PhoneForwarded className="w-3 h-3" />
            Transfer
          </button>
        )}
      </div>
    </div>
  );
}
