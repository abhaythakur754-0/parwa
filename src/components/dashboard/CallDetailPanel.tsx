/**
 * PARWA CallDetailPanel
 *
 * Slide-out panel showing comprehensive call details including:
 * - Call info (direction, duration, status, variant)
 * - Transcript summary
 * - Topics discussed (tag pills)
 * - Key moments timeline
 * - Satisfaction score
 * - Recording playback
 * - ROI mapping
 */

'use client';

import { useEffect, useState } from 'react';
import { X, Phone, PhoneOutgoing, PhoneIncoming, Clock, FileText, Star, Volume2, TrendingDown, Sparkles } from 'lucide-react';
import { cn } from '@/lib/utils';
import { voiceApi } from '@/lib/voice-api';
import type { VoiceCall, CallStatus } from '@/types/voice';

interface CallDetailPanelProps {
  call: VoiceCall | null;
  open: boolean;
  onClose: () => void;
}

// ── Status Colors ───────────────────────────────────────────────────

const statusColors: Record<string, string> = {
  'queued': 'text-amber-400 bg-amber-500/10',
  'ringing': 'text-blue-400 bg-blue-500/10',
  'in-progress': 'text-emerald-400 bg-emerald-500/10',
  'completed': 'text-zinc-400 bg-zinc-500/10',
  'failed': 'text-red-400 bg-red-500/10',
  'busy': 'text-amber-400 bg-amber-500/10',
  'no-answer': 'text-zinc-400 bg-zinc-500/10',
  'canceled': 'text-zinc-500 bg-zinc-600/10',
};

const variantLabels: Record<string, string> = {
  parwa: 'Mini',
  parwa_pro: 'Pro',
  parwa_high: 'High',
};

// ── Component ───────────────────────────────────────────────────────

export function CallDetailPanel({ call, open, onClose }: CallDetailPanelProps) {
  const [detailedCall, setDetailedCall] = useState<VoiceCall | null>(null);
  const [loading, setLoading] = useState(false);

  // Fetch full call details when panel opens
  useEffect(() => {
    if (open && call) {
      setLoading(true);
      voiceApi.getCall(call.id)
        .then(setDetailedCall)
        .catch(() => setDetailedCall(call))
        .finally(() => setLoading(false));
    } else {
      setDetailedCall(null);
    }
  }, [open, call]);

  const data = detailedCall || call;
  if (!data) return null;

  const formatDuration = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}m ${s}s`;
  };

  const formatTime = (isoString?: string) => {
    if (!isoString) return '—';
    const date = new Date(isoString);
    return date.toLocaleString(undefined, {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  };

  const phoneNumber = data.direction === 'outbound' ? data.to_number : data.from_number;

  return (
    <>
      {/* Backdrop */}
      {open && (
        <div
          className="fixed inset-0 bg-black/40 backdrop-blur-sm z-40 lg:hidden"
          onClick={onClose}
        />
      )}

      {/* Panel */}
      <div className={cn(
        'fixed right-0 top-0 h-full w-full sm:w-[420px] bg-[#1A1A1A] border-l border-white/[0.06] z-50 transition-transform duration-300 ease-out overflow-y-auto',
        open ? 'translate-x-0' : 'translate-x-full'
      )}>
        {/* Header */}
        <div className="sticky top-0 bg-[#1A1A1A] border-b border-white/[0.06] p-4 flex items-center justify-between z-10">
          <div className="flex items-center gap-3">
            <div className={cn(
              'w-9 h-9 rounded-lg flex items-center justify-center',
              data.direction === 'outbound' ? 'bg-orange-500/10' : 'bg-blue-500/10'
            )}>
              {data.direction === 'outbound' ? (
                <PhoneOutgoing className="w-4 h-4 text-orange-400" />
              ) : (
                <PhoneIncoming className="w-4 h-4 text-blue-400" />
              )}
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white">Call Details</h3>
              <p className="text-[11px] text-zinc-500">{phoneNumber}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg flex items-center justify-center text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.05] transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="w-6 h-6 border-2 border-orange-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          <div className="p-4 space-y-4">
            {/* Call Info Grid */}
            <div className="grid grid-cols-2 gap-3">
              <InfoItem icon={<Phone className="w-3.5 h-3.5" />} label="Direction" value={data.direction === 'outbound' ? 'Outgoing' : 'Incoming'} />
              <InfoItem icon={<Clock className="w-3.5 h-3.5" />} label="Duration" value={formatDuration(data.duration_seconds)} />
              <InfoItem label="Status">
                <span className={cn('text-xs px-2 py-0.5 rounded-full', statusColors[data.status] || 'text-zinc-400 bg-zinc-500/10')}>
                  {data.status}
                </span>
              </InfoItem>
              <InfoItem label="Variant" value={variantLabels[data.variant_tier] || data.variant_tier} />
              {data.intent_detected && <InfoItem label="Intent" value={data.intent_detected} />}
              {data.resolution && <InfoItem label="Resolution" value={data.resolution} />}
              <InfoItem icon={<Clock className="w-3.5 h-3.5" />} label="Started" value={formatTime(data.started_at)} />
              <InfoItem label="Ended" value={formatTime(data.ended_at)} />
            </div>

            {/* Satisfaction Score */}
            {data.satisfaction_score != null && data.satisfaction_score > 0 && (
              <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.05]">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-zinc-500">Satisfaction</span>
                  <div className="flex items-center gap-1">
                    {Array.from({ length: 5 }).map((_, i) => (
                      <Star
                        key={i}
                        className={cn(
                          'w-4 h-4',
                          i < (data.satisfaction_score || 0)
                            ? 'text-amber-400 fill-amber-400'
                            : 'text-zinc-700'
                        )}
                      />
                    ))}
                    <span className="text-xs font-medium text-amber-300 ml-1">{data.satisfaction_score}/5</span>
                  </div>
                </div>
              </div>
            )}

            {/* Topics Discussed */}
            {data.topics_discussed && data.topics_discussed.length > 0 && (
              <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.05]">
                <div className="flex items-center gap-1.5 mb-2">
                  <Sparkles className="w-3 h-3 text-amber-400/60" />
                  <span className="text-[10px] font-medium text-white/40">Topics Discussed</span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {data.topics_discussed.map((topic, i) => (
                    <span
                      key={i}
                      className="text-[10px] px-2 py-0.5 rounded-full bg-blue-500/10 border border-blue-500/10 text-blue-300/70"
                    >
                      {topic}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Transcript Summary */}
            {data.transcript_summary && (
              <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.05]">
                <div className="flex items-center gap-1.5 mb-2">
                  <FileText className="w-3 h-3 text-white/30" />
                  <span className="text-[10px] font-medium text-white/40">Transcript Summary</span>
                </div>
                <p className="text-xs text-white/60 leading-relaxed">{data.transcript_summary}</p>
              </div>
            )}

            {/* Recording Playback */}
            {data.recording_url && (
              <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.05]">
                <div className="flex items-center gap-1.5 mb-2">
                  <Volume2 className="w-3 h-3 text-white/30" />
                  <span className="text-[10px] font-medium text-white/40">Recording</span>
                </div>
                <audio
                  controls
                  src={data.recording_url}
                  className="w-full h-8 opacity-75"
                  preload="none"
                >
                  Your browser does not support audio playback.
                </audio>
              </div>
            )}

            {/* ROI Mapping */}
            {data.duration_seconds > 0 && (
              <div className="p-3 rounded-xl bg-orange-500/5 border border-orange-500/10">
                <div className="flex items-center gap-1.5 mb-2">
                  <TrendingDown className="w-3.5 h-3.5 text-orange-400" />
                  <span className="text-[10px] font-semibold text-orange-300/70">ROI with PARWA</span>
                </div>
                <div className="space-y-1.5">
                  <div className="flex justify-between text-[10px]">
                    <span className="text-white/40">Call handled by AI</span>
                    <span className="text-emerald-300/70">Yes</span>
                  </div>
                  <div className="flex justify-between text-[10px]">
                    <span className="text-white/40">Duration saved</span>
                    <span className="text-white/60">{formatDuration(data.duration_seconds)}</span>
                  </div>
                  <div className="flex justify-between text-[10px]">
                    <span className="text-white/40">Est. cost savings</span>
                    <span className="text-orange-300 font-medium">
                      ${(data.duration_seconds * 0.15).toFixed(2)} vs human agent
                    </span>
                  </div>
                </div>
              </div>
            )}

            {/* Call SID */}
            <div className="p-3 rounded-xl bg-white/[0.02] border border-white/[0.04]">
              <span className="text-[10px] text-zinc-600 font-mono">SID: {data.twilio_call_sid}</span>
            </div>
          </div>
        )}
      </div>
    </>
  );
}

// ── Helper Component ────────────────────────────────────────────────

function InfoItem({
  icon,
  label,
  value,
  children,
}: {
  icon?: React.ReactNode;
  label: string;
  value?: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="p-2.5 rounded-lg bg-white/[0.02] border border-white/[0.04]">
      <div className="flex items-center gap-1 mb-1">
        {icon && <span className="text-white/20">{icon}</span>}
        <span className="text-[10px] text-zinc-600">{label}</span>
      </div>
      {children || <span className="text-xs text-white/70 font-medium">{value || '—'}</span>}
    </div>
  );
}
