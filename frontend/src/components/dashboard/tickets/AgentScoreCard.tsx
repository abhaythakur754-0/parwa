'use client';

import React from 'react';
import { cn } from '@/lib/utils';

interface ScoreBreakdown {
  raw: number;
  max: number;
  percentage: number;
}

interface AgentScoreCardProps {
  agentId: string;
  agentName: string;
  score: number;
  rawScore: number;
  scoreBreakdown: {
    expertise: ScoreBreakdown & { current_tickets?: number };
    workload: ScoreBreakdown & { current_tickets: number };
    performance: ScoreBreakdown;
    response_time: ScoreBreakdown;
    availability: ScoreBreakdown;
  };
  explanations?: {
    expertise: string;
    workload: string;
    performance: string;
    response_time: string;
    availability: string;
  };
  isRecommended?: boolean;
  rank?: number;
  onAssign?: (agentId: string) => void;
  compact?: boolean;
  className?: string;
}

const factorColors: Record<string, string> = {
  expertise: 'bg-blue-500',
  workload: 'bg-purple-500',
  performance: 'bg-emerald-500',
  response_time: 'bg-yellow-500',
  availability: 'bg-cyan-500',
};

const factorLabels: Record<string, string> = {
  expertise: 'Expertise',
  workload: 'Workload',
  performance: 'Performance',
  response_time: 'Response Time',
  availability: 'Availability',
};

export default function AgentScoreCard({
  agentId,
  agentName,
  score,
  rawScore,
  scoreBreakdown,
  explanations,
  isRecommended = false,
  rank,
  onAssign,
  compact = false,
  className,
}: AgentScoreCardProps) {
  const scorePercent = Math.round(score * 100);

  const getScoreColor = (s: number) => {
    if (s >= 0.8) return 'text-emerald-400';
    if (s >= 0.6) return 'text-yellow-400';
    if (s >= 0.4) return 'text-orange-400';
    return 'text-red-400';
  };

  const getScoreBg = (s: number) => {
    if (s >= 0.8) return 'bg-emerald-500/15 border-emerald-500/25';
    if (s >= 0.6) return 'bg-yellow-500/15 border-yellow-500/25';
    if (s >= 0.4) return 'bg-orange-500/15 border-orange-500/25';
    return 'bg-red-500/15 border-red-500/25';
  };

  const renderScoreBar = (
    key: string,
    breakdown: ScoreBreakdown,
    showLabel = true
  ) => (
    <div className="flex items-center gap-2">
      {showLabel && (
        <span className="text-[10px] text-zinc-500 w-20 truncate">
          {factorLabels[key] || key}
        </span>
      )}
      <div className="flex-1 h-1.5 bg-white/[0.04] rounded-full overflow-hidden">
        <div
          className={cn('h-full rounded-full transition-all', factorColors[key] || 'bg-zinc-500')}
          style={{ width: `${Math.min(100, breakdown.percentage)}%` }}
        />
      </div>
      <span className="text-[10px] text-zinc-400 w-7 text-right">
        {Math.round(breakdown.percentage)}%
      </span>
    </div>
  );

  // Compact mode for list views
  if (compact) {
    return (
      <div
        className={cn(
          'flex items-center gap-3 p-2 rounded-lg border transition-colors',
          isRecommended
            ? 'bg-emerald-500/5 border-emerald-500/20'
            : 'bg-[#1A1A1A] border-white/[0.06] hover:bg-white/[0.02]',
          className
        )}
      >
        {rank !== undefined && (
          <div
            className={cn(
              'w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold',
              rank === 1
                ? 'bg-orange-500/20 text-orange-400'
                : 'bg-white/[0.04] text-zinc-500'
            )}
          >
            {rank}
          </div>
        )}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-zinc-200 truncate">
              {agentName}
            </span>
            {isRecommended && (
              <span className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-400">
                Best
              </span>
            )}
          </div>
          <div className="text-[10px] text-zinc-500">
            {scoreBreakdown.workload.current_tickets} open tickets
          </div>
        </div>
        <div
          className={cn(
            'px-2 py-1 rounded-md border text-xs font-semibold',
            getScoreBg(score),
            getScoreColor(score)
          )}
        >
          {scorePercent}%
        </div>
        {onAssign && (
          <button
            onClick={() => onAssign(agentId)}
            className="px-2 py-1 rounded-md bg-orange-500/15 text-orange-400 text-[10px] font-medium border border-orange-500/25 hover:bg-orange-500/25 transition-colors"
          >
            Assign
          </button>
        )}
      </div>
    );
  }

  // Full card mode
  return (
    <div
      className={cn(
        'rounded-xl overflow-hidden transition-all',
        isRecommended
          ? 'bg-gradient-to-br from-emerald-500/10 to-[#1A1A1A] border-2 border-emerald-500/30'
          : 'bg-[#1A1A1A] border border-white/[0.06]',
        className
      )}
    >
      {/* Header */}
      <div className="px-4 py-3 border-b border-white/[0.06] flex items-center justify-between">
        <div className="flex items-center gap-3">
          {rank !== undefined && (
            <div
              className={cn(
                'w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold',
                rank === 1
                  ? 'bg-orange-500/20 text-orange-400'
                  : 'bg-white/[0.04] text-zinc-500'
              )}
            >
              {rank}
            </div>
          )}
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-zinc-100">
                {agentName}
              </span>
              {isRecommended && (
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/25">
                  Recommended
                </span>
              )}
            </div>
            <div className="text-xs text-zinc-500 mt-0.5">
              {scoreBreakdown.workload.current_tickets} open tickets
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right">
            <div className={cn('text-2xl font-bold', getScoreColor(score))}>
              {scorePercent}%
            </div>
            <div className="text-[10px] text-zinc-500">
              {rawScore.toFixed(1)} / 115 pts
            </div>
          </div>
        </div>
      </div>

      {/* Score breakdown */}
      <div className="p-4 space-y-2">
        <div className="text-xs font-medium text-zinc-400 mb-3">
          5-Factor Score Breakdown
        </div>
        {renderScoreBar('expertise', scoreBreakdown.expertise)}
        {renderScoreBar('workload', scoreBreakdown.workload)}
        {renderScoreBar('performance', scoreBreakdown.performance)}
        {renderScoreBar('response_time', scoreBreakdown.response_time)}
        {renderScoreBar('availability', scoreBreakdown.availability)}
      </div>

      {/* Explanations (if provided) */}
      {explanations && (
        <div className="px-4 pb-4">
          <div className="p-3 rounded-lg bg-white/[0.02] border border-white/[0.04] space-y-1.5">
            <div className="text-[10px] text-zinc-500">
              <span className="text-blue-400">Expertise:</span> {explanations.expertise}
            </div>
            <div className="text-[10px] text-zinc-500">
              <span className="text-purple-400">Workload:</span> {explanations.workload}
            </div>
            <div className="text-[10px] text-zinc-500">
              <span className="text-emerald-400">Performance:</span> {explanations.performance}
            </div>
            <div className="text-[10px] text-zinc-500">
              <span className="text-yellow-400">Response:</span> {explanations.response_time}
            </div>
            <div className="text-[10px] text-zinc-500">
              <span className="text-cyan-400">Availability:</span> {explanations.availability}
            </div>
          </div>
        </div>
      )}

      {/* Action */}
      {onAssign && (
        <div className="px-4 pb-4">
          <button
            onClick={() => onAssign(agentId)}
            className={cn(
              'w-full py-2.5 rounded-lg text-sm font-semibold transition-all',
              isRecommended
                ? 'bg-emerald-500 text-white hover:bg-emerald-600'
                : 'bg-orange-500/15 text-orange-400 border border-orange-500/25 hover:bg-orange-500/25'
            )}
          >
            {isRecommended ? 'Assign Best Match' : 'Assign to Agent'}
          </button>
        </div>
      )}
    </div>
  );
}

// Export a mini version for inline use
export function AgentScoreMini({
  score,
  agentName,
  className,
}: {
  score: number;
  agentName: string;
  className?: string;
}) {
  const scorePercent = Math.round(score * 100);

  const getColor = (s: number) => {
    if (s >= 0.8) return 'bg-emerald-500';
    if (s >= 0.6) return 'bg-yellow-500';
    if (s >= 0.4) return 'bg-orange-500';
    return 'bg-red-500';
  };

  return (
    <div className={cn('flex items-center gap-2', className)}>
      <div className={cn('w-2 h-2 rounded-full', getColor(score))} />
      <span className="text-xs text-zinc-300">{agentName}</span>
      <span className="text-[10px] text-zinc-500">{scorePercent}%</span>
    </div>
  );
}
