'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { cn } from '@/lib/utils';
import toast from 'react-hot-toast';

interface AgentScore {
  agent_id: string;
  agent_name: string;
  normalized_score: number;
  raw_score: number;
  score_breakdown: {
    expertise: { raw: number; max: number; percentage: number };
    workload: { raw: number; max: number; percentage: number; current_tickets: number };
    performance: { raw: number; max: number; percentage: number };
    response_time: { raw: number; max: number; percentage: number };
    availability: { raw: number; max: number; percentage: number };
  };
  explanations?: {
    expertise: string;
    workload: string;
    performance: string;
    response_time: string;
    availability: string;
  };
}

interface AssignmentSuggestionsProps {
  ticketId: string;
  onSelectAgent?: (agentId: string) => void;
  className?: string;
}

export default function AssignmentSuggestions({
  ticketId,
  onSelectAgent,
  className,
}: AssignmentSuggestionsProps) {
  const [loading, setLoading] = useState(true);
  const [candidates, setCandidates] = useState<AgentScore[]>([]);
  const [recommended, setRecommended] = useState<AgentScore | null>(null);
  const [expandedAgent, setExpandedAgent] = useState<string | null>(null);
  const [scoringMethod, setScoringMethod] = useState<string>('');

  const fetchScores = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/tickets/${ticketId}/suggest-assignee`);
      if (!res.ok) throw new Error('Failed to fetch suggestions');
      
      const data = await res.json();
      setCandidates(data.candidates || []);
      setRecommended(data.recommended_assignee);
      setScoringMethod(data.scoring_method || 'unknown');
    } catch (err) {
      toast.error('Failed to load assignment suggestions');
    } finally {
      setLoading(false);
    }
  }, [ticketId]);

  useEffect(() => {
    fetchScores();
  }, [fetchScores]);

  const handleAssign = async (agentId: string) => {
    if (!onSelectAgent) return;
    
    try {
      onSelectAgent(agentId);
      toast.success('Agent assigned successfully');
    } catch {
      toast.error('Failed to assign agent');
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 0.8) return 'text-emerald-400';
    if (score >= 0.6) return 'text-yellow-400';
    if (score >= 0.4) return 'text-orange-400';
    return 'text-red-400';
  };

  const getScoreBg = (score: number) => {
    if (score >= 0.8) return 'bg-emerald-500/15 border-emerald-500/25';
    if (score >= 0.6) return 'bg-yellow-500/15 border-yellow-500/25';
    if (score >= 0.4) return 'bg-orange-500/15 border-orange-500/25';
    return 'bg-red-500/15 border-red-500/25';
  };

  const renderScoreBar = (percentage: number, label: string, color?: string) => (
    <div className="flex items-center gap-2">
      <span className="text-[10px] text-zinc-500 w-24 truncate">{label}</span>
      <div className="flex-1 h-1.5 bg-white/[0.04] rounded-full overflow-hidden">
        <div
          className={cn('h-full rounded-full transition-all', color || 'bg-orange-500')}
          style={{ width: `${Math.min(100, percentage)}%` }}
        />
      </div>
      <span className="text-[10px] text-zinc-400 w-8 text-right">{Math.round(percentage)}%</span>
    </div>
  );

  if (loading) {
    return (
      <div className={cn('rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-4', className)}>
        <div className="animate-pulse space-y-3">
          <div className="h-4 w-32 bg-white/[0.04] rounded" />
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-16 bg-white/[0.04] rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  if (candidates.length === 0) {
    return (
      <div className={cn('rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-4', className)}>
        <p className="text-sm text-zinc-500">No agents available for assignment</p>
      </div>
    );
  }

  return (
    <div className={cn('rounded-xl bg-[#1A1A1A] border border-white/[0.06] overflow-hidden', className)}>
      {/* Header */}
      <div className="px-4 py-3 border-b border-white/[0.06] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-orange-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09ZM18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 0 0-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 0 0 2.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 0 0 2.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 0 0-2.456 2.456ZM16.894 20.567 16.5 21.75l-.394-1.183a2.25 2.25 0 0 0-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 0 0 1.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 0 0 1.423 1.423l1.183.394-1.183.394a2.25 2.25 0 0 0-1.423 1.423Z" />
          </svg>
          <h3 className="text-sm font-medium text-zinc-200">AI Assignment Suggestions</h3>
        </div>
        <span className="text-[10px] px-2 py-0.5 rounded-full bg-orange-500/15 text-orange-400 border border-orange-500/25">
          {scoringMethod === '5-factor-ai' ? 'AI Scored' : 'Rule-Based'}
        </span>
      </div>

      {/* Candidates List */}
      <div className="divide-y divide-white/[0.04]">
        {candidates.slice(0, 5).map((candidate, index) => {
          const isRecommended = recommended?.agent_id === candidate.agent_id;
          const isExpanded = expandedAgent === candidate.agent_id;
          const scorePercent = Math.round(candidate.normalized_score * 100);

          return (
            <div
              key={candidate.agent_id}
              className={cn(
                'p-3 transition-colors cursor-pointer hover:bg-white/[0.02]',
                isRecommended && 'bg-emerald-500/5'
              )}
              onClick={() => setExpandedAgent(isExpanded ? null : candidate.agent_id)}
            >
              <div className="flex items-center gap-3">
                {/* Rank */}
                <div className={cn(
                  'w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold',
                  index === 0 ? 'bg-orange-500/20 text-orange-400' : 'bg-white/[0.04] text-zinc-500'
                )}>
                  {index + 1}
                </div>

                {/* Agent Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-zinc-200 truncate">
                      {candidate.agent_name}
                    </span>
                    {isRecommended && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-400">
                        Best Match
                      </span>
                    )}
                    {candidate.score_breakdown.workload.current_tickets <= 5 && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-500/15 text-blue-400">
                        Available
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-zinc-500 mt-0.5">
                    {candidate.score_breakdown.workload.current_tickets} open tickets
                  </div>
                </div>

                {/* Score */}
                <div className={cn(
                  'px-3 py-1.5 rounded-lg border text-sm font-semibold',
                  getScoreBg(candidate.normalized_score),
                  getScoreColor(candidate.normalized_score)
                )}>
                  {scorePercent}%
                </div>

                {/* Actions */}
                {onSelectAgent && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleAssign(candidate.agent_id);
                    }}
                    className="px-3 py-1.5 rounded-lg bg-orange-500/15 text-orange-400 text-xs font-medium border border-orange-500/25 hover:bg-orange-500/25 transition-colors"
                  >
                    Assign
                  </button>
                )}
              </div>

              {/* Expanded Details */}
              {isExpanded && candidate.explanations && (
                <div className="mt-3 pt-3 border-t border-white/[0.06] space-y-2">
                  <div className="text-xs font-medium text-zinc-400 mb-2">Score Breakdown</div>
                  {renderScoreBar(candidate.score_breakdown.expertise.percentage, 'Expertise', 'bg-blue-500')}
                  {renderScoreBar(candidate.score_breakdown.workload.percentage, 'Workload', 'bg-purple-500')}
                  {renderScoreBar(candidate.score_breakdown.performance.percentage, 'Performance', 'bg-emerald-500')}
                  {renderScoreBar(candidate.score_breakdown.response_time.percentage, 'Response Time', 'bg-yellow-500')}
                  {renderScoreBar(candidate.score_breakdown.availability.percentage, 'Availability', 'bg-cyan-500')}
                  
                  <div className="mt-3 text-xs text-zinc-500 space-y-1">
                    <p><span className="text-zinc-400">Expertise:</span> {candidate.explanations.expertise}</p>
                    <p><span className="text-zinc-400">Workload:</span> {candidate.explanations.workload}</p>
                    <p><span className="text-zinc-400">Performance:</span> {candidate.explanations.performance}</p>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Footer */}
      {candidates.length > 5 && (
        <div className="px-4 py-2 border-t border-white/[0.06] text-center">
          <button className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors">
            View {candidates.length - 5} more candidates
          </button>
        </div>
      )}
    </div>
  );
}
