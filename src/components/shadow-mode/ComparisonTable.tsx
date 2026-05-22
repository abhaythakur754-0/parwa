/**
 * ComparisonTable — Table showing live vs shadow comparison results
 *
 * Displays quality, latency, and token usage for each comparison,
 * with human review action buttons for supervised mode.
 */

'use client';

import React, { useState } from 'react';
import { cn } from '@/lib/utils';
import type { ShadowComparison, HumanVerdict } from '@/types/shadow-mode';

// ── Props ───────────────────────────────────────────────────────────

export interface ComparisonTableProps {
  comparisons: ShadowComparison[];
  onReview?: (resultId: string, verdict: HumanVerdict, notes: string) => void;
  isReviewLoading?: boolean;
  className?: string;
}

// ── Component ───────────────────────────────────────────────────────

export function ComparisonTable({
  comparisons,
  onReview,
  isReviewLoading,
  className,
}: ComparisonTableProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [reviewNotes, setReviewNotes] = useState<Record<string, string>>({});

  if (comparisons.length === 0) {
    return (
      <div className={cn('rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-8 text-center', className)}>
        <svg className="w-10 h-10 text-zinc-700 mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 12h16.5m-16.5 3.75h16.5M3.75 19.5h16.5M5.625 4.5h12.75a1.875 1.875 0 010 3.75H5.625a1.875 1.875 0 010-3.75Z" />
        </svg>
        <h4 className="text-sm font-medium text-zinc-400 mb-1">No Comparisons Yet</h4>
        <p className="text-xs text-zinc-600">Comparison data will appear here once shadow mode starts processing messages.</p>
      </div>
    );
  }

  return (
    <div className={cn('rounded-xl border border-white/[0.06] bg-[#1A1A1A] overflow-hidden', className)}>
      {/* Header */}
      <div className="px-4 py-3 border-b border-white/[0.06] flex items-center justify-between">
        <h3 className="text-sm font-semibold text-white">Comparison History</h3>
        <span className="text-[10px] text-zinc-500">{comparisons.length} results</span>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-white/[0.06]">
              <th className="text-left px-4 py-2.5 text-zinc-500 font-medium">Ticket</th>
              <th className="text-center px-4 py-2.5 text-zinc-500 font-medium">Live Quality</th>
              <th className="text-center px-4 py-2.5 text-zinc-500 font-medium">Shadow Quality</th>
              <th className="text-center px-4 py-2.5 text-zinc-500 font-medium">Delta</th>
              <th className="text-center px-4 py-2.5 text-zinc-500 font-medium">Winner</th>
              <th className="text-center px-4 py-2.5 text-zinc-500 font-medium">Latency</th>
              <th className="text-center px-4 py-2.5 text-zinc-500 font-medium">Review</th>
              <th className="text-center px-4 py-2.5 text-zinc-500 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {comparisons.map((comp) => {
              const isExpanded = expandedId === comp.id;
              const qualityDelta = comp.quality_delta;
              const shadowWon = comp.shadow_winner;

              return (
                <React.Fragment key={comp.id}>
                  <tr
                    className={cn(
                      'border-b border-white/[0.03] hover:bg-white/[0.02] cursor-pointer transition-colors',
                      shadowWon ? 'bg-purple-500/[0.02]' : ''
                    )}
                    onClick={() => setExpandedId(isExpanded ? null : comp.id)}
                  >
                    <td className="px-4 py-2.5 text-zinc-300 font-mono">
                      {comp.ticket_id.slice(0, 8)}...
                    </td>
                    <td className="px-4 py-2.5 text-center">
                      <span className={cn(
                        'font-medium',
                        comp.live_quality >= 0.7 ? 'text-emerald-400' : comp.live_quality >= 0.5 ? 'text-amber-400' : 'text-red-400'
                      )}>
                        {Math.round(comp.live_quality * 100)}%
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-center">
                      <span className={cn(
                        'font-medium',
                        comp.shadow_quality >= 0.7 ? 'text-emerald-400' : comp.shadow_quality >= 0.5 ? 'text-amber-400' : 'text-red-400'
                      )}>
                        {Math.round(comp.shadow_quality * 100)}%
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-center">
                      <span className={cn(
                        'font-medium',
                        qualityDelta > 0 ? 'text-emerald-400' : qualityDelta < 0 ? 'text-red-400' : 'text-zinc-400'
                      )}>
                        {qualityDelta > 0 ? '+' : ''}{(qualityDelta * 100).toFixed(1)}%
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-center">
                      <span className={cn(
                        'inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full',
                        shadowWon
                          ? 'text-purple-400 bg-purple-500/10'
                          : 'text-zinc-400 bg-zinc-500/10'
                      )}>
                        {shadowWon ? 'Shadow' : 'Live'}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-center text-zinc-400">
                      <span className="text-zinc-500">{comp.live_latency_ms}ms</span>
                      <span className="text-zinc-700 mx-1">/</span>
                      <span className={cn(
                        comp.shadow_latency_ms <= comp.live_latency_ms ? 'text-emerald-400' : 'text-amber-400'
                      )}>
                        {comp.shadow_latency_ms}ms
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-center">
                      {comp.human_reviewed ? (
                        <span className={cn(
                          'text-[10px] font-medium px-2 py-0.5 rounded-full',
                          comp.human_verdict === 'shadow_better' ? 'text-purple-400 bg-purple-500/10' :
                          comp.human_verdict === 'live_better' ? 'text-zinc-400 bg-zinc-500/10' :
                          comp.human_verdict === 'equal' ? 'text-amber-400 bg-amber-500/10' :
                          'text-zinc-500 bg-zinc-500/5'
                        )}>
                          {comp.human_verdict === 'shadow_better' ? 'Shadow' :
                           comp.human_verdict === 'live_better' ? 'Live' :
                           comp.human_verdict === 'equal' ? 'Equal' : 'Skip'}
                        </span>
                      ) : (
                        <span className="text-[10px] text-zinc-600">Pending</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-center">
                      <svg
                        className={cn('w-3.5 h-3.5 text-zinc-500 mx-auto transition-transform', isExpanded && 'rotate-180')}
                        fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
                      </svg>
                    </td>
                  </tr>

                  {/* Expanded Row — Details + Review */}
                  {isExpanded && (
                    <tr className="bg-white/[0.01]">
                      <td colSpan={8} className="px-4 py-4">
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                          <div>
                            <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Live Tokens</p>
                            <p className="text-sm text-zinc-300 font-medium">{comp.live_tokens}</p>
                          </div>
                          <div>
                            <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Shadow Tokens</p>
                            <p className="text-sm text-zinc-300 font-medium">{comp.shadow_tokens}</p>
                          </div>
                          <div>
                            <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Created</p>
                            <p className="text-sm text-zinc-300 font-medium">
                              {new Date(comp.created_at).toLocaleString()}
                            </p>
                          </div>
                          <div>
                            <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Result ID</p>
                            <p className="text-sm text-zinc-400 font-mono">{comp.id.slice(0, 16)}...</p>
                          </div>
                        </div>

                        {/* Human Review Section */}
                        {onReview && !comp.human_reviewed && (
                          <div className="pt-3 border-t border-white/[0.06]">
                            <p className="text-xs text-zinc-400 mb-2">Submit Human Review</p>
                            <div className="flex items-center gap-2 mb-2">
                              <button
                                onClick={(e) => { e.stopPropagation(); onReview(comp.id, 'shadow_better', reviewNotes[comp.id] || ''); }}
                                disabled={isReviewLoading}
                                className="text-xs px-3 py-1.5 rounded bg-purple-500/10 text-purple-400 hover:bg-purple-500/20 transition-colors disabled:opacity-50"
                              >
                                Shadow Better
                              </button>
                              <button
                                onClick={(e) => { e.stopPropagation(); onReview(comp.id, 'live_better', reviewNotes[comp.id] || ''); }}
                                disabled={isReviewLoading}
                                className="text-xs px-3 py-1.5 rounded bg-zinc-500/10 text-zinc-400 hover:bg-zinc-500/20 transition-colors disabled:opacity-50"
                              >
                                Live Better
                              </button>
                              <button
                                onClick={(e) => { e.stopPropagation(); onReview(comp.id, 'equal', reviewNotes[comp.id] || ''); }}
                                disabled={isReviewLoading}
                                className="text-xs px-3 py-1.5 rounded bg-amber-500/10 text-amber-400 hover:bg-amber-500/20 transition-colors disabled:opacity-50"
                              >
                                Equal
                              </button>
                              <button
                                onClick={(e) => { e.stopPropagation(); onReview(comp.id, 'skip', reviewNotes[comp.id] || ''); }}
                                disabled={isReviewLoading}
                                className="text-xs px-3 py-1.5 rounded bg-white/5 text-zinc-500 hover:bg-white/10 transition-colors disabled:opacity-50"
                              >
                                Skip
                              </button>
                            </div>
                            <input
                              type="text"
                              placeholder="Optional review notes..."
                              value={reviewNotes[comp.id] || ''}
                              onChange={(e) => setReviewNotes(prev => ({ ...prev, [comp.id]: e.target.value }))}
                              onClick={(e) => e.stopPropagation()}
                              className="w-full text-xs px-3 py-2 rounded-lg bg-white/5 border border-white/[0.06] text-zinc-300 placeholder-zinc-600 outline-none focus:border-purple-500/30 transition-colors"
                            />
                          </div>
                        )}

                        {/* Existing Review */}
                        {comp.human_reviewed && comp.human_verdict && (
                          <div className="pt-3 border-t border-white/[0.06]">
                            <p className="text-xs text-zinc-400 mb-1">
                              Reviewed: <span className="font-medium capitalize">{comp.human_verdict.replace('_', ' ')}</span>
                            </p>
                            {comp.review_notes && (
                              <p className="text-xs text-zinc-500">Notes: {comp.review_notes}</p>
                            )}
                          </div>
                        )}
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
