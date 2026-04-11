/**
 * PARWA PostCallSummaryCard (Week 6 — Day 4 Phase 6, Gap Fixed)
 *
 * Full call summary card with: topics, key moments, impressions, satisfaction,
 * transcript summary, and optional ROI mapping section.
 *
 * Metadata shape (per spec §20.2-20.3):
 *   {
 *     duration: number,
 *     topics: string[],
 *     summary: string,
 *     satisfaction?: number,
 *     key_moments?: { time: string; description: string }[],
 *     impressions?: { queries_handled?: number; avg_response_time?: string; interventions_needed?: number },
 *     transcript_summary?: string,
 *     roi_mapping?: { current_cost: number; parwa_cost: number; savings: number; currency: string; queries_in_call: number; time_saved_weekly: string }
 *   }
 */

'use client';

import { Phone, Star, FileText, Clock, TrendingDown, Sparkles, BarChart3 } from 'lucide-react';

interface PostCallSummaryCardProps {
  metadata: Record<string, unknown>;
}

export function PostCallSummaryCard({ metadata }: PostCallSummaryCardProps) {
  const duration = (metadata.duration as number) || 0;
  const topics = (metadata.topics as string[]) || [];
  const summary = (metadata.summary as string) || '';
  const satisfaction = (metadata.satisfaction as number) ?? 0;

  // Gap fix: Key Moments section (spec §20.2)
  const keyMoments = (metadata.key_moments as { time: string; description: string }[]) || [];

  // Gap fix: Impressions section (spec §20.2)
  const impressions = metadata.impressions as {
    queries_handled?: number;
    avg_response_time?: string;
    interventions_needed?: number;
  } | null;

  // Gap fix: Transcript summary
  const transcriptSummary = (metadata.transcript_summary as string) || '';

  // Gap fix: ROI Mapping section (spec §20.3)
  const roiMapping = metadata.roi_mapping as {
    current_cost: number;
    parwa_cost: number;
    savings: number;
    currency: string;
    queries_in_call: number;
    time_saved_weekly: string;
  } | null;

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}m ${s}s`;
  };

  const formatCurrency = (amount: number, currency: string) => {
    return `${currency} ${amount.toLocaleString()}`;
  };

  return (
    <div className="glass rounded-xl p-4 border border-blue-500/15 max-w-sm w-full space-y-3">
      {/* Header */}
      <div className="flex items-center gap-2">
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
        <div className="flex flex-wrap gap-1.5">
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

      {/* Key Moments (Gap Fix — spec §20.2) */}
      {keyMoments.length > 0 && (
        <div className="p-2.5 rounded-lg bg-white/[0.03] border border-white/5">
          <div className="flex items-center gap-1.5 mb-2">
            <Sparkles className="w-3 h-3 text-amber-400/60" />
            <span className="text-[10px] font-medium text-white/40">Key Moments</span>
          </div>
          <div className="space-y-1.5">
            {keyMoments.map((moment, i) => (
              <div key={i} className="flex items-start gap-2">
                <span className="text-[9px] font-mono text-blue-300/50 whitespace-nowrap pt-px min-w-[28px]">
                  {moment.time}
                </span>
                <span className="text-[11px] text-white/55 leading-relaxed">
                  {moment.description}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Impressions (Gap Fix — spec §20.2) */}
      {impressions && (
        <div className="p-2.5 rounded-lg bg-white/[0.03] border border-white/5">
          <div className="flex items-center gap-1.5 mb-2">
            <BarChart3 className="w-3 h-3 text-orange-400/60" />
            <span className="text-[10px] font-medium text-white/40">Your Impressions</span>
          </div>
          <div className="grid grid-cols-3 gap-2">
            {impressions.queries_handled != null && (
              <div className="text-center">
                <p className="text-sm font-bold text-blue-300">{impressions.queries_handled}</p>
                <p className="text-[9px] text-white/35">queries handled</p>
              </div>
            )}
            {impressions.avg_response_time && (
              <div className="text-center">
                <p className="text-sm font-bold text-orange-300">{impressions.avg_response_time}</p>
                <p className="text-[9px] text-white/35">avg response</p>
              </div>
            )}
            {impressions.interventions_needed != null && (
              <div className="text-center">
                <p className="text-sm font-bold text-amber-300">{impressions.interventions_needed}</p>
                <p className="text-[9px] text-white/35">human assists</p>
              </div>
            )}
          </div>
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

      {/* Transcript Summary (Gap Fix) */}
      {transcriptSummary && (
        <details className="group">
          <summary className="flex items-center gap-1.5 text-[10px] text-white/35 cursor-pointer hover:text-white/50 transition-colors select-none">
            <Clock className="w-3 h-3" />
            View Full Transcript Summary
          </summary>
          <p className="mt-2 text-[10px] text-white/45 leading-relaxed pl-4 border-l border-white/5">
            {transcriptSummary}
          </p>
        </details>
      )}

      {/* ROI Mapping (Gap Fix — spec §20.3) */}
      {roiMapping && (
        <div className="p-3 rounded-lg bg-orange-500/5 border border-orange-500/10">
          <div className="flex items-center gap-1.5 mb-2">
            <TrendingDown className="w-3.5 h-3.5 text-orange-400" />
            <span className="text-[10px] font-semibold text-orange-300/70">Your ROI with Jarvis</span>
          </div>
          <div className="space-y-1.5 mb-2">
            <div className="flex justify-between text-[10px]">
              <span className="text-white/40">Current monthly cost</span>
              <span className="text-white/60">{formatCurrency(roiMapping.current_cost, roiMapping.currency)}</span>
            </div>
            <div className="flex justify-between text-[10px]">
              <span className="text-white/40">PARWA cost</span>
              <span className="text-orange-300/70">{formatCurrency(roiMapping.parwa_cost, roiMapping.currency)}/mo</span>
            </div>
            <div className="flex justify-between text-[10px] pt-1 border-t border-white/5">
              <span className="text-white/50 font-medium">Est. savings</span>
              <span className="text-orange-300 font-semibold">{formatCurrency(roiMapping.savings, roiMapping.currency)}/mo</span>
            </div>
          </div>
          {roiMapping.queries_in_call > 0 && (
            <p className="text-[10px] text-white/40 leading-relaxed">
              In the call, Jarvis handled {roiMapping.queries_in_call} queries that would normally take your team significant time. At scale, that&apos;s {roiMapping.time_saved_weekly} saved per week.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
