/**
 * PARWA PostCallSummaryCard (Week 6 — Day 4 Phase 6)
 *
 * Call summary: topics discussed, key moments, impressions.
 * Metadata: { duration, topics: string[], summary: string, satisfaction?: number }
 */

'use client';

import { Phone, Star, FileText } from 'lucide-react';

interface PostCallSummaryCardProps {
  metadata: Record<string, unknown>;
}

export function PostCallSummaryCard({ metadata }: PostCallSummaryCardProps) {
  const duration = (metadata.duration as number) || 0;
  const topics = (metadata.topics as string[]) || [];
  const summary = (metadata.summary as string) || '';
  const satisfaction = (metadata.satisfaction as number) | 0;

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}m ${s}s`;
  };

  return (
    <div className="glass rounded-xl p-4 border border-blue-500/15 max-w-sm w-full">
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        <div className="w-8 h-8 rounded-lg bg-blue-500/10 flex items-center justify-center">
          <Phone className="w-4 h-4 text-blue-400" />
        </div>
        <div className="flex-1">
          <h3 className="text-sm font-semibold text-white">Call Summary</h3>
          <p className="text-[10px] text-white/40">Duration: {formatTime(duration)}</p>
        </div>
        {satisfaction > 0 && (
          <div className="flex items-center gap-0.5">
            <Star className="w-3.5 h-3.5 text-amber-400 fill-amber-400" />
            <span className="text-xs font-medium text-amber-300">{satisfaction}/5</span>
          </div>
        )}
      </div>

      {/* Topics */}
      {topics.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-3">
          {topics.map((topic, i) => (
            <span
              key={i}
              className="text-[10px] px-2 py-0.5 rounded-full bg-blue-500/10 border border-blue-500/10 text-blue-300/70"
            >
              {topic}
            </span>
          ))}
        </div>
      )}

      {/* Summary */}
      {summary && (
        <div className="p-2.5 rounded-lg bg-white/[0.03] border border-white/5">
          <div className="flex items-center gap-1.5 mb-1.5">
            <FileText className="w-3 h-3 text-white/30" />
            <span className="text-[10px] font-medium text-white/40">Summary</span>
          </div>
          <p className="text-[11px] text-white/60 leading-relaxed">{summary}</p>
        </div>
      )}
    </div>
  );
}
