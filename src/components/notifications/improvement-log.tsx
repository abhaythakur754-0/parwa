/**
 * ImprovementLog — Displays self-improvement engine activity.
 *
 * Shows recent prompt adjustments and technique tuning changes
 * made by the self-improvement engine. Follows PARWA dark dashboard style.
 */

'use client';

import React from 'react';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';

// ── Types ────────────────────────────────────────────────────────────

export type ImprovementType = 'prompt_adjustment' | 'technique_tuning';

export interface ImprovementEntry {
  id: string;
  type: ImprovementType;
  subgraph: string;
  title: string;
  description: string;
  timestamp: string;
  status: 'pending' | 'applied' | 'verified' | 'rejected';
  confidence: number; // 0–1
  adjustmentType?: string; // e.g. "add_rule", "promote", "demote"
  technique?: string; // For technique_tuning entries
}

// ── Status Styles ────────────────────────────────────────────────────

const STATUS_STYLES: Record<ImprovementEntry['status'], { badge: string; dot: string }> = {
  pending: {
    badge: 'bg-amber-500/15 text-amber-400 border-amber-500/20',
    dot: 'bg-amber-400',
  },
  applied: {
    badge: 'bg-sky-500/15 text-sky-400 border-sky-500/20',
    dot: 'bg-sky-400',
  },
  verified: {
    badge: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20',
    dot: 'bg-emerald-400',
  },
  rejected: {
    badge: 'bg-red-500/15 text-red-400 border-red-500/20',
    dot: 'bg-red-400',
  },
};

// ── Confidence Bar ───────────────────────────────────────────────────

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color =
    value >= 0.8
      ? 'bg-emerald-400'
      : value >= 0.6
        ? 'bg-amber-400'
        : 'bg-red-400';

  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1 bg-zinc-800 rounded-full overflow-hidden">
        <div
          className={cn('h-full rounded-full transition-all', color)}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-[9px] text-zinc-500">{pct}%</span>
    </div>
  );
}

// ── Time Ago ─────────────────────────────────────────────────────────

function timeAgo(timestamp: string): string {
  const now = Date.now();
  const then = new Date(timestamp).getTime();
  const diffMs = now - then;

  if (diffMs < 60000) return 'just now';
  if (diffMs < 3600000) return `${Math.floor(diffMs / 60000)}m ago`;
  if (diffMs < 86400000) return `${Math.floor(diffMs / 3600000)}h ago`;
  return `${Math.floor(diffMs / 86400000)}d ago`;
}

// ── Prompt Adjustment Section ────────────────────────────────────────

interface PromptAdjustmentsProps {
  entries: ImprovementEntry[];
}

function PromptAdjustments({ entries }: PromptAdjustmentsProps) {
  if (entries.length === 0) {
    return (
      <div className="py-8 text-center">
        <p className="text-xs text-zinc-600">No prompt adjustments yet</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {entries.map((entry) => (
        <div
          key={entry.id}
          className="rounded-lg border border-white/[0.04] bg-white/[0.01] p-3 hover:bg-white/[0.02] transition-colors"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span
                  className={cn(
                    'w-1.5 h-1.5 rounded-full shrink-0',
                    STATUS_STYLES[entry.status].dot
                  )}
                />
                <p className="text-xs font-medium text-white truncate">
                  {entry.title}
                </p>
                {entry.adjustmentType && (
                  <Badge
                    variant="outline"
                    className="text-[8px] px-1 py-0 border border-white/[0.08] text-zinc-500"
                  >
                    {entry.adjustmentType.replace(/_/g, ' ')}
                  </Badge>
                )}
              </div>
              <p className="text-[11px] text-zinc-500 mt-1 line-clamp-2">
                {entry.description}
              </p>
              <div className="flex items-center gap-3 mt-2">
                <Badge
                  variant="outline"
                  className="text-[8px] px-1 py-0 border border-white/[0.08] text-zinc-500 capitalize"
                >
                  {entry.subgraph}
                </Badge>
                <span className="text-[9px] text-zinc-600">
                  {timeAgo(entry.timestamp)}
                </span>
                <Badge
                  variant="outline"
                  className={cn(
                    'text-[8px] px-1.5 py-0 border font-medium',
                    STATUS_STYLES[entry.status].badge
                  )}
                >
                  {entry.status}
                </Badge>
              </div>
            </div>
            <div className="shrink-0 pt-0.5">
              <ConfidenceBar value={entry.confidence} />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Technique Tuning Section ─────────────────────────────────────────

interface TechniqueTuningProps {
  entries: ImprovementEntry[];
}

function TechniqueTuning({ entries }: TechniqueTuningProps) {
  if (entries.length === 0) {
    return (
      <div className="py-8 text-center">
        <p className="text-xs text-zinc-600">No technique tuning changes yet</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {entries.map((entry) => (
        <div
          key={entry.id}
          className="rounded-lg border border-white/[0.04] bg-white/[0.01] p-3 hover:bg-white/[0.02] transition-colors"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span
                  className={cn(
                    'w-1.5 h-1.5 rounded-full shrink-0',
                    STATUS_STYLES[entry.status].dot
                  )}
                />
                <p className="text-xs font-medium text-white truncate">
                  {entry.title}
                </p>
                {entry.adjustmentType && (
                  <Badge
                    variant="outline"
                    className={cn(
                      'text-[8px] px-1.5 py-0 border font-medium',
                      entry.adjustmentType === 'promote'
                        ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20'
                        : entry.adjustmentType === 'demote'
                          ? 'bg-red-500/15 text-red-400 border-red-500/20'
                          : 'bg-zinc-500/15 text-zinc-400 border-zinc-500/20'
                    )}
                  >
                    {entry.adjustmentType}
                  </Badge>
                )}
              </div>
              <p className="text-[11px] text-zinc-500 mt-1 line-clamp-2">
                {entry.description}
              </p>
              <div className="flex items-center gap-3 mt-2">
                <Badge
                  variant="outline"
                  className="text-[8px] px-1 py-0 border border-white/[0.08] text-zinc-500 capitalize"
                >
                  {entry.subgraph}
                </Badge>
                {entry.technique && (
                  <Badge
                    variant="outline"
                    className="text-[8px] px-1 py-0 border border-white/[0.08] text-purple-400"
                  >
                    {entry.technique}
                  </Badge>
                )}
                <span className="text-[9px] text-zinc-600">
                  {timeAgo(entry.timestamp)}
                </span>
                <Badge
                  variant="outline"
                  className={cn(
                    'text-[8px] px-1.5 py-0 border font-medium',
                    STATUS_STYLES[entry.status].badge
                  )}
                >
                  {entry.status}
                </Badge>
              </div>
            </div>
            <div className="shrink-0 pt-0.5">
              <ConfidenceBar value={entry.confidence} />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── ImprovementLog Component ─────────────────────────────────────────

interface ImprovementLogProps {
  entries: ImprovementEntry[];
}

export function ImprovementLog({ entries }: ImprovementLogProps) {
  const promptEntries = entries.filter((e) => e.type === 'prompt_adjustment');
  const techniqueEntries = entries.filter((e) => e.type === 'technique_tuning');

  return (
    <div className="space-y-4">
      {/* Prompt Adjustments */}
      <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] overflow-hidden">
        <div className="px-4 py-3 border-b border-white/[0.06]">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-md bg-emerald-500/10 flex items-center justify-center">
              <svg
                className="w-3.5 h-3.5 text-emerald-400"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={1.5}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10"
                />
              </svg>
            </div>
            <h3 className="text-sm font-semibold text-white">
              Prompt Adjustments
            </h3>
            <span className="text-[10px] text-zinc-500">
              {promptEntries.length} changes
            </span>
          </div>
        </div>
        <ScrollArea className="max-h-[320px]">
          <div className="p-3">
            <PromptAdjustments entries={promptEntries} />
          </div>
        </ScrollArea>
      </div>

      {/* Technique Tuning */}
      <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] overflow-hidden">
        <div className="px-4 py-3 border-b border-white/[0.06]">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-md bg-purple-500/10 flex items-center justify-center">
              <svg
                className="w-3.5 h-3.5 text-purple-400"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={1.5}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M10.5 6h9.75M10.5 6a1.5 1.5 0 11-3 0m3 0a1.5 1.5 0 10-3 0M3.75 6H7.5m3 12h9.75m-9.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-3.75 0H7.5m9-6h3.75m-3.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-9.75 0h9.75"
                />
              </svg>
            </div>
            <h3 className="text-sm font-semibold text-white">
              Technique Tuning
            </h3>
            <span className="text-[10px] text-zinc-500">
              {techniqueEntries.length} changes
            </span>
          </div>
        </div>
        <ScrollArea className="max-h-[320px]">
          <div className="p-3">
            <TechniqueTuning entries={techniqueEntries} />
          </div>
        </ScrollArea>
      </div>
    </div>
  );
}

export default ImprovementLog;
