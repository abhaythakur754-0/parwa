'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';
import { useAuth } from '@/hooks/useAuth';
import {
  useEscalationStore,
  TICKET_TYPE_LABELS,
  COMPLEXITY_LABELS,
  HUMAN_STATUS_LABELS,
  REPROCESS_STATUS_LABELS,
  CRM_PROVIDER_LABELS,
  ALL_HUMAN_STATUSES,
  ALL_REPROCESS_STATUSES,
  type Escalation,
  type HumanStatus,
  type ReprocessStatus,
  type TicketType,
  type Complexity,
} from '@/lib/escalation-store';

// ── Constants ────────────────────────────────────────────────────────

// BC-001: tenant_id is taken from the authenticated user's company_id at
// runtime (see EscalationsPage below). No hardcoded tenant.

const TICKET_TYPE_COLORS: Record<TicketType, string> = {
  billing: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
  technical: 'bg-sky-500/10 text-sky-400 border-sky-500/20',
  account: 'bg-violet-500/10 text-violet-400 border-violet-500/20',
  general: 'bg-zinc-500/10 text-zinc-300 border-zinc-500/20',
  refund: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  feature_request: 'bg-pink-500/10 text-pink-400 border-pink-500/20',
  complaint: 'bg-red-500/10 text-red-400 border-red-500/20',
};

const COMPLEXITY_COLORS: Record<Complexity, string> = {
  simple: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  moderate: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
  complex: 'bg-orange-500/10 text-orange-400 border-orange-500/20',
  critical: 'bg-red-500/10 text-red-400 border-red-500/20',
};

const HUMAN_STATUS_COLORS: Record<HumanStatus, { dot: string; badge: string }> = {
  pending: { dot: 'bg-red-400', badge: 'bg-red-500/10 text-red-400 border-red-500/20' },
  guidance_provided: { dot: 'bg-amber-400', badge: 'bg-amber-500/10 text-amber-400 border-amber-500/20' },
  resolved: { dot: 'bg-emerald-400', badge: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' },
};

const REPROCESS_COLORS: Record<ReprocessStatus, { dot: string; badge: string }> = {
  pending: { dot: 'bg-zinc-500', badge: 'bg-zinc-500/10 text-zinc-400 border-zinc-500/20' },
  processing: { dot: 'bg-blue-400 animate-pulse', badge: 'bg-blue-500/10 text-blue-400 border-blue-500/20' },
  done: { dot: 'bg-emerald-400', badge: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' },
  failed: { dot: 'bg-red-400', badge: 'bg-red-500/10 text-red-400 border-red-500/20' },
};

const CRM_COLORS: Record<string, string> = {
  zendesk: 'bg-red-500/10 text-red-400 border-red-500/20',
  hubspot: 'bg-orange-500/10 text-orange-400 border-orange-500/20',
  generic: 'bg-zinc-500/10 text-zinc-400 border-zinc-500/20',
  pending: 'bg-zinc-500/10 text-zinc-400 border-zinc-500/20',
  updated: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  failed: 'bg-red-500/10 text-red-400 border-red-500/20',
};

// ── Helpers ──────────────────────────────────────────────────────────

function formatRelativeDate(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit',
  });
}

function truncate(str: string, max: number): string {
  if (str.length <= max) return str;
  return str.slice(0, max).trim() + '…';
}

function qualityColor(score: number): string {
  if (score >= 0.7) return 'text-emerald-400';
  if (score >= 0.4) return 'text-amber-400';
  return 'text-red-400';
}

function qualityBg(score: number): string {
  if (score >= 0.7) return 'bg-emerald-500';
  if (score >= 0.4) return 'bg-amber-500';
  return 'bg-red-500';
}

// ── Badge Components ─────────────────────────────────────────────────

function StatusDot({ status, size = 'sm' }: { status: HumanStatus; size?: 'sm' | 'lg' }) {
  const c = HUMAN_STATUS_COLORS[status];
  const dotSize = size === 'lg' ? 'w-2.5 h-2.5' : 'w-1.5 h-1.5';
  return (
    <span className={cn('inline-flex items-center gap-1.5 text-xs font-medium px-2 py-0.5 rounded-full border', c.badge)}>
      <span className={cn('rounded-full', c.dot, dotSize, status === 'pending' && 'animate-pulse')} />
      {HUMAN_STATUS_LABELS[status]}
    </span>
  );
}

function TicketTypeBadge({ type }: { type: TicketType }) {
  return (
    <span className={cn('text-[10px] font-medium px-2 py-0.5 rounded-full border', TICKET_TYPE_COLORS[type])}>
      {TICKET_TYPE_LABELS[type]}
    </span>
  );
}

function ComplexityBadge({ complexity }: { complexity: Complexity }) {
  return (
    <span className={cn('text-[10px] font-medium px-2 py-0.5 rounded-full border', COMPLEXITY_COLORS[complexity])}>
      {COMPLEXITY_LABELS[complexity]}
    </span>
  );
}

function ReprocessBadge({ status }: { status: ReprocessStatus }) {
  const c = REPROCESS_COLORS[status];
  return (
    <span className={cn('inline-flex items-center gap-1.5 text-[10px] font-medium px-2 py-0.5 rounded-full border', c.badge)}>
      <span className={cn('w-1.5 h-1.5 rounded-full', c.dot)} />
      {REPROCESS_STATUS_LABELS[status]}
    </span>
  );
}

// ── Quality Score Bar ────────────────────────────────────────────────

function QualityBar({ score, label }: { score: number; label: string }) {
  const pct = Math.round(score * 100);
  return (
    <div className="flex items-center gap-2 min-w-[120px]">
      <span className="text-[10px] text-zinc-500 w-14 shrink-0">{label}</span>
      <div className="flex-1 h-1.5 bg-white/[0.06] rounded-full overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.8, ease: 'easeOut' }}
          className={cn('h-full rounded-full', qualityBg(score))}
        />
      </div>
      <span className={cn('text-[11px] font-semibold tabular-nums w-8 text-right', qualityColor(score))}>
        {pct}%
      </span>
    </div>
  );
}

// ── Skeleton Components ──────────────────────────────────────────────

function StatCardSkeleton() {
  return (
    <div className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-4 animate-pulse">
      <div className="h-3 w-24 bg-white/[0.06] rounded mb-3" />
      <div className="h-7 w-12 bg-white/[0.06] rounded" />
    </div>
  );
}

function EscalationCardSkeleton() {
  return (
    <div className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-4 animate-pulse">
      <div className="flex items-center justify-between mb-3">
        <div className="h-4 w-32 bg-white/[0.06] rounded" />
        <div className="h-5 w-20 bg-white/[0.06] rounded" />
      </div>
      <div className="h-3 w-full bg-white/[0.06] rounded mb-2" />
      <div className="h-3 w-3/4 bg-white/[0.06] rounded mb-4" />
      <div className="flex gap-2">
        <div className="h-5 w-14 bg-white/[0.06] rounded-full" />
        <div className="h-5 w-16 bg-white/[0.06] rounded-full" />
        <div className="h-5 w-14 bg-white/[0.06] rounded-full" />
      </div>
    </div>
  );
}

// ── Filter Select ────────────────────────────────────────────────────

function FilterSelect<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: { value: T; label: string }[];
  onChange: (value: T | 'all') => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <label className="text-[11px] text-zinc-500 whitespace-nowrap hidden sm:block">{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value as T | 'all')}
        className="h-8 bg-[#1A1A1A] border border-white/[0.06] rounded-lg px-2.5 text-xs text-zinc-300 focus:outline-none focus:border-blue-500/40 appearance-none cursor-pointer pr-7"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%2371717a' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E")`,
          backgroundRepeat: 'no-repeat',
          backgroundPosition: 'right 8px center',
        }}
      >
        <option value="all">All {label}</option>
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>{opt.label}</option>
        ))}
      </select>
    </div>
  );
}

// ── Guidance Modal ───────────────────────────────────────────────────

function GuidanceModal({
  escalation,
  onClose,
}: {
  escalation: Escalation;
  onClose: () => void;
}) {
  const [guidance, setGuidance] = useState(escalation.human_guidance || '');
  const [autoResume, setAutoResume] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const provideGuidance = useEscalationStore((s) => s.provideGuidance);
  const resumeEscalation = useEscalationStore((s) => s.resumeEscalation);
  const closeModal = useEscalationStore((s) => s.closeModal);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  const handleSubmit = async () => {
    if (guidance.trim().length < 5) {
      toast.error('Guidance must be at least 5 characters.');
      return;
    }
    setSubmitting(true);
    const ok = await provideGuidance(escalation.escalation_id, guidance.trim());
    if (ok) {
      toast.success('Guidance saved. Ticket is now eligible for resume.');
      if (autoResume) {
        await resumeEscalation(escalation.escalation_id);
      }
      closeModal();
    } else {
      toast.error('Failed to save guidance. Please try again.');
      setSubmitting(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 10 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 10 }}
        transition={{ duration: 0.2 }}
        className="w-full max-w-2xl max-h-[85vh] bg-[#1A1A1A] border border-white/[0.06] rounded-xl overflow-hidden flex flex-col shadow-2xl"
      >
        {/* Header */}
        <div className="px-5 py-4 border-b border-white/[0.06] flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="text-base font-semibold text-white">Provide Guidance</h2>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-xs font-mono text-blue-400">{escalation.original_ticket_id}</span>
              <span className="text-[10px] text-zinc-600">•</span>
              <span className="text-[10px] text-zinc-500">{escalation.notification_key}</span>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-7 h-7 flex items-center justify-center rounded-lg text-zinc-400 hover:text-white hover:bg-white/5 transition-colors shrink-0"
            aria-label="Close modal"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto min-h-0 px-5 py-4 space-y-5">
          {/* Original Query */}
          <section>
            <h3 className="text-[11px] text-zinc-500 uppercase tracking-wider font-medium mb-2">Original Query</h3>
            <div className="bg-[#0A0A0A] border border-white/[0.06] rounded-lg p-3">
              <p className="text-xs text-zinc-300 leading-relaxed whitespace-pre-wrap">{escalation.original_query}</p>
            </div>
          </section>

          {/* Metadata */}
          <section>
            <h3 className="text-[11px] text-zinc-500 uppercase tracking-wider font-medium mb-2">Ticket Details</h3>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              <div>
                <span className="text-[10px] text-zinc-600">Type</span>
                <div className="mt-0.5"><TicketTypeBadge type={escalation.ticket_type} /></div>
              </div>
              <div>
                <span className="text-[10px] text-zinc-600">Complexity</span>
                <div className="mt-0.5"><ComplexityBadge complexity={escalation.complexity} /></div>
              </div>
              <div>
                <span className="text-[10px] text-zinc-600">Quality Score</span>
                <div className="mt-0.5">
                  <span className={cn('text-sm font-bold', qualityColor(escalation.quality_score))}>
                    {Math.round(escalation.quality_score * 100)}%
                  </span>
                </div>
              </div>
            </div>
            <div className="mt-3">
              <span className="text-[10px] text-zinc-600">Required Action</span>
              <p className="text-xs text-zinc-300 mt-0.5 leading-relaxed">{escalation.required_action}</p>
            </div>
          </section>

          {/* Failure Analysis */}
          <section>
            <h3 className="text-[11px] text-zinc-500 uppercase tracking-wider font-medium mb-2 flex items-center gap-1.5">
              <svg className="w-3 h-3 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
              </svg>
              Why It Failed
            </h3>
            <div className="bg-red-500/5 border border-red-500/10 rounded-lg p-3">
              <p className="text-xs text-zinc-300 leading-relaxed">{escalation.failure_analysis}</p>
            </div>
          </section>

          {/* Knowledge Context */}
          {escalation.knowledge_context && escalation.knowledge_context.length > 0 && (
            <section>
              <h3 className="text-[11px] text-zinc-500 uppercase tracking-wider font-medium mb-2">Knowledge Context Found</h3>
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {escalation.knowledge_context.map((ctx, i) => (
                  <div key={i} className="bg-[#0A0A0A] border border-white/[0.06] rounded-lg p-3">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[11px] font-medium text-zinc-300">{ctx.title}</span>
                      <span className="text-[10px] text-zinc-500">{Math.round(ctx.score * 100)}% match</span>
                    </div>
                    <p className="text-[11px] text-zinc-500 leading-relaxed line-clamp-2">{ctx.snippet}</p>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Previous Attempts */}
          {escalation.previous_attempts && escalation.previous_attempts.length > 0 && (
            <section>
              <h3 className="text-[11px] text-zinc-500 uppercase tracking-wider font-medium mb-2">Previous AI Attempts</h3>
              <div className="space-y-1.5">
                {escalation.previous_attempts.map((attempt, i) => (
                  <div key={i} className="flex items-start gap-2 text-xs text-zinc-400">
                    <span className="text-[10px] text-zinc-600 mt-0.5 shrink-0">#{i + 1}</span>
                    <span className="leading-relaxed">{attempt}</span>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Guidance Input */}
          <section>
            <h3 className="text-[11px] text-zinc-500 uppercase tracking-wider font-medium mb-2">Your Guidance</h3>
            <textarea
              ref={textareaRef}
              value={guidance}
              onChange={(e) => setGuidance(e.target.value)}
              placeholder="Provide context, instructions, or specific steps the AI should follow to resolve this ticket..."
              rows={5}
              className="w-full bg-[#0A0A0A] border border-white/[0.06] rounded-lg px-3 py-2.5 text-xs text-white placeholder:text-zinc-600 focus:outline-none focus:border-blue-500/40 transition-colors resize-none leading-relaxed"
            />
            <div className="flex items-center justify-between mt-1.5">
              <span className="text-[10px] text-zinc-600">Min 5 characters</span>
              <span className={cn('text-[10px]', guidance.trim().length >= 5 ? 'text-emerald-400' : 'text-zinc-600')}>
                {guidance.trim().length} chars
              </span>
            </div>
          </section>
        </div>

        {/* Footer */}
        <div className="px-5 py-4 border-t border-white/[0.06] flex items-center justify-between gap-3 bg-[#141414]">
          <label className="flex items-center gap-2 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={autoResume}
              onChange={(e) => setAutoResume(e.target.checked)}
              className="w-3.5 h-3.5 rounded border-white/[0.15] bg-[#0A0A0A] text-blue-500 focus:ring-blue-500/30 focus:ring-offset-0 cursor-pointer"
            />
            <span className="text-[11px] text-zinc-400">Auto-resume after submit</span>
          </label>
          <div className="flex items-center gap-2">
            <button
              onClick={onClose}
              className="text-[11px] font-medium px-3 py-1.5 rounded-lg bg-white/[0.04] text-zinc-400 hover:text-white hover:bg-white/[0.08] transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSubmit}
              disabled={guidance.trim().length < 5 || submitting}
              className="text-[11px] font-medium px-4 py-1.5 rounded-lg bg-blue-500 text-white hover:bg-blue-600 transition-colors disabled:opacity-30 disabled:cursor-not-allowed flex items-center gap-1.5"
            >
              {submitting && (
                <svg className="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              )}
              Submit Guidance
            </button>
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
}

// ── View Result Panel ────────────────────────────────────────────────

function ViewResultPanel({
  escalation,
  onClose,
}: {
  escalation: Escalation;
  onClose: () => void;
}) {
  const closeModal = useEscalationStore((s) => s.closeModal);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 10 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 10 }}
        transition={{ duration: 0.2 }}
        className="w-full max-w-2xl max-h-[85vh] bg-[#1A1A1A] border border-white/[0.06] rounded-xl overflow-hidden flex flex-col shadow-2xl"
      >
        {/* Header */}
        <div className="px-5 py-4 border-b border-white/[0.06] flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="text-base font-semibold text-white">Reprocessing Result</h2>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-xs font-mono text-blue-400">{escalation.original_ticket_id}</span>
              <ReprocessBadge status={escalation.reprocess_status} />
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-7 h-7 flex items-center justify-center rounded-lg text-zinc-400 hover:text-white hover:bg-white/5 transition-colors shrink-0"
            aria-label="Close panel"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto min-h-0 px-5 py-4 space-y-5">
          {/* Quality Comparison */}
          <section>
            <h3 className="text-[11px] text-zinc-500 uppercase tracking-wider font-medium mb-3">Quality Score Comparison</h3>
            <div className="space-y-2.5">
              <QualityBar score={escalation.quality_score} label="Original" />
              {escalation.reprocess_quality_score !== null && (
                <QualityBar score={escalation.reprocess_quality_score} label="Improved" />
              )}
            </div>
            {escalation.reprocess_quality_score !== null && (
              <div className="mt-2 flex items-center gap-1.5">
                {escalation.reprocess_quality_score >= 0.6 ? (
                  <>
                    <svg className="w-3.5 h-3.5 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
                    </svg>
                    <span className="text-[11px] text-emerald-400 font-medium">
                      Quality threshold passed ({Math.round(escalation.reprocess_quality_score * 100)}% ≥ 60%)
                    </span>
                  </>
                ) : (
                  <>
                    <svg className="w-3.5 h-3.5 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 3.75h.008v.008H12v-.008Z" />
                    </svg>
                    <span className="text-[11px] text-red-400 font-medium">Resume Failed — Quality below threshold</span>
                  </>
                )}
              </div>
            )}
          </section>

          {/* Improved Response */}
          {escalation.reprocess_result && (
            <section>
              <h3 className="text-[11px] text-zinc-500 uppercase tracking-wider font-medium mb-2">Improved Response</h3>
              <div className="bg-emerald-500/5 border border-emerald-500/10 rounded-lg p-3">
                <p className="text-xs text-zinc-300 leading-relaxed whitespace-pre-wrap">{escalation.reprocess_result}</p>
              </div>
            </section>
          )}

          {/* Agent Guidance */}
          {escalation.human_guidance && (
            <section>
              <h3 className="text-[11px] text-zinc-500 uppercase tracking-wider font-medium mb-2">Agent Guidance Provided</h3>
              <div className="bg-blue-500/5 border border-blue-500/10 rounded-lg p-3">
                <p className="text-xs text-zinc-300 leading-relaxed whitespace-pre-wrap">{escalation.human_guidance}</p>
                {escalation.guidance_timestamp && (
                  <span className="text-[10px] text-zinc-600 mt-2 block">
                    Provided {formatRelativeDate(escalation.guidance_timestamp)} via {escalation.guidance_source || 'agent'}
                  </span>
                )}
              </div>
            </section>
          )}

          {/* Technique Log */}
          {escalation.reprocess_technique_log && escalation.reprocess_technique_log.length > 0 && (
            <section>
              <h3 className="text-[11px] text-zinc-500 uppercase tracking-wider font-medium mb-2">Reprocessing Steps</h3>
              <div className="space-y-1.5">
                {escalation.reprocess_technique_log.map((step, i) => (
                  <div key={i} className="flex items-center gap-3 bg-[#0A0A0A] border border-white/[0.06] rounded-lg px-3 py-2">
                    <span className="w-5 h-5 flex items-center justify-center text-[10px] font-bold text-blue-400 bg-blue-500/10 rounded-full shrink-0">
                      {i + 1}
                    </span>
                    <div className="min-w-0 flex-1">
                      <span className="text-[11px] font-medium text-zinc-300 font-mono">{step.step}</span>
                      <p className="text-[10px] text-zinc-500 truncate">{step.detail}</p>
                    </div>
                    <span className="text-[10px] text-zinc-600 tabular-nums shrink-0">{step.duration_ms}ms</span>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* CRM Push Result */}
          {escalation.crm_provider && (
            <section>
              <h3 className="text-[11px] text-zinc-500 uppercase tracking-wider font-medium mb-2">CRM Push Status</h3>
              <div className="flex items-center gap-3">
                {escalation.crm_provider && (
                  <span className={cn('text-[10px] font-medium px-2 py-0.5 rounded-full border', CRM_COLORS[escalation.crm_provider])}>
                    {CRM_PROVIDER_LABELS[escalation.crm_provider] || escalation.crm_provider}
                  </span>
                )}
                {escalation.crm_ticket_id && (
                  <span className="text-[10px] font-mono text-zinc-400">{escalation.crm_ticket_id}</span>
                )}
                {escalation.crm_status && (
                  <span className={cn('text-[10px] font-medium px-2 py-0.5 rounded-full border', CRM_COLORS[escalation.crm_status])}>
                    {escalation.crm_status}
                  </span>
                )}
              </div>
            </section>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-4 border-t border-white/[0.06] flex items-center justify-end gap-2 bg-[#141414]">
          <button
            onClick={onClose}
            className="text-[11px] font-medium px-4 py-1.5 rounded-lg bg-white/[0.04] text-zinc-400 hover:text-white hover:bg-white/[0.08] transition-colors"
          >
            Close
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
}

// ── Escalation Card ──────────────────────────────────────────────────

function EscalationCard({
  escalation,
  index,
}: {
  escalation: Escalation;
  index: number;
}) {
  const openModal = useEscalationStore((s) => s.openModal);
  const resumeEscalation = useEscalationStore((s) => s.resumeEscalation);
  const createGuidanceTicket = useEscalationStore((s) => s.createGuidanceTicket);
  const [resuming, setResuming] = useState(false);
  const [guidanceTicketting, setGuidanceTicketting] = useState(false);

  const canProvideGuidance = escalation.human_status === 'pending';
  const canViewResult = escalation.reprocess_status === 'done' || escalation.reprocess_status === 'failed';
  const canResume = escalation.human_status === 'guidance_provided' && escalation.reprocess_status === 'pending';
  const canGuidanceTicket =
    (escalation.reprocess_status === 'failed' && escalation.human_status === 'guidance_provided') ||
    (escalation.human_status === 'guidance_provided' && escalation.reprocess_status !== 'done');

  const handleResume = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setResuming(true);
    await resumeEscalation(escalation.escalation_id);
    setResuming(false);
  };

  const handleGuidanceTicket = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setGuidanceTicketting(true);
    await createGuidanceTicket(escalation.escalation_id);
    setGuidanceTicketting(false);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: index * 0.04 }}
      className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-4 hover:border-white/[0.12] transition-colors group"
    >
      {/* Top Row */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className="text-xs font-mono text-blue-400">{escalation.original_ticket_id}</span>
            <span className="text-[10px] text-zinc-600">•</span>
            <span className="text-[10px] text-zinc-500 font-mono">{escalation.notification_key}</span>
          </div>
          <p className="text-xs text-white/80 leading-relaxed line-clamp-2">{truncate(escalation.original_query, 160)}</p>
        </div>
        <StatusDot status={escalation.human_status} />
      </div>

      {/* Badges Row */}
      <div className="flex items-center gap-1.5 flex-wrap mb-3">
        <TicketTypeBadge type={escalation.ticket_type} />
        <ComplexityBadge complexity={escalation.complexity} />
        <ReprocessBadge status={escalation.reprocess_status} />
        {escalation.crm_provider && (
          <span className={cn('text-[10px] font-medium px-2 py-0.5 rounded-full border', CRM_COLORS[escalation.crm_provider])}>
            {CRM_PROVIDER_LABELS[escalation.crm_provider]}
          </span>
        )}
        {escalation.crm_status && escalation.crm_status !== 'pending' && (
          <span className={cn('text-[10px] font-medium px-2 py-0.5 rounded-full border', CRM_COLORS[escalation.crm_status])}>
            CRM: {escalation.crm_status}
          </span>
        )}
      </div>

      {/* Quality Scores */}
      <div className="space-y-1.5 mb-3">
        <QualityBar score={escalation.quality_score} label="Original" />
        {escalation.reprocess_quality_score !== null && (
          <QualityBar score={escalation.reprocess_quality_score} label="Improved" />
        )}
      </div>

      {/* Failed Resume Badge */}
      {escalation.reprocess_status === 'failed' && (
        <div className="flex items-center gap-1.5 mb-3 px-2.5 py-1.5 rounded-lg bg-red-500/5 border border-red-500/10">
          <svg className="w-3 h-3 text-red-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
          </svg>
          <span className="text-[11px] text-red-400">Resume Failed</span>
          {escalation.reprocess_quality_score !== null && escalation.reprocess_quality_score < 0.6 && (
            <span className="text-[10px] text-red-400/60">• Quality too low</span>
          )}
          {escalation.crm_status === 'failed' && (
            <span className="text-[10px] text-red-400/60">• CRM push failed</span>
          )}
        </div>
      )}

      {/* Footer Row */}
      <div className="flex items-center justify-between gap-2 pt-3 border-t border-white/[0.04]">
        <span className="text-[10px] text-zinc-600">{formatRelativeDate(escalation.created_at)}</span>
        <div className="flex items-center gap-2">
          {canProvideGuidance && (
            <button
              onClick={() => openModal(escalation, 'guidance')}
              className="inline-flex items-center gap-1.5 text-[11px] font-medium px-3 py-1.5 rounded-lg bg-blue-500/10 text-blue-400 border border-blue-500/20 hover:bg-blue-500/20 transition-colors"
            >
              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931Zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10" />
              </svg>
              Provide Guidance
            </button>
          )}
          {canResume && (
            <button
              onClick={handleResume}
              disabled={resuming}
              className="inline-flex items-center gap-1.5 text-[11px] font-medium px-3 py-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/20 transition-colors disabled:opacity-50"
            >
              {resuming ? (
                <svg className="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              ) : (
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.347a1.125 1.125 0 0 1 0 1.972l-11.54 6.347a1.125 1.125 0 0 1-1.667-.986V5.653Z" />
                </svg>
              )}
              Resume
            </button>
          )}
          {canGuidanceTicket && (
            <button
              onClick={handleGuidanceTicket}
              disabled={guidanceTicketting}
              className="inline-flex items-center gap-1.5 text-[11px] font-medium px-3 py-1.5 rounded-lg bg-violet-500/10 text-violet-400 border border-violet-500/20 hover:bg-violet-500/20 transition-colors disabled:opacity-50"
            >
              {guidanceTicketting ? (
                <svg className="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              ) : (
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09ZM18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 0 0-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 0 0 2.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 0 0 2.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 0 0-2.456 2.456ZM16.894 20.567 16.5 21.75l-.394-1.183a2.25 2.25 0 0 0-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 0 0 1.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 0 0 1.423 1.423l1.183.394-1.183.394a2.25 2.25 0 0 0-1.423 1.423Z" />
                </svg>
              )}
              Use as Direct Answer
            </button>
          )}
          {canViewResult && (
            <button
              onClick={() => openModal(escalation, 'result')}
              className="inline-flex items-center gap-1.5 text-[11px] font-medium px-3 py-1.5 rounded-lg bg-white/[0.04] text-zinc-300 border border-white/[0.06] hover:bg-white/[0.08] transition-colors"
            >
              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 0 1 0-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178Z" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
              </svg>
              View Result
            </button>
          )}
        </div>
      </div>
    </motion.div>
  );
}

// ── Empty State ──────────────────────────────────────────────────────

function EmptyState() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex flex-col items-center justify-center py-16 px-4"
    >
      <div className="w-16 h-16 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center mb-4">
        <svg className="w-8 h-8 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75m-3-7.036A11.959 11.959 0 0 1 3.598 6 11.99 11.99 0 0 0 3 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285Z" />
        </svg>
      </div>
      <h3 className="text-sm font-semibold text-white mb-1">No Escalations</h3>
      <p className="text-xs text-zinc-500 text-center max-w-sm">
        PARWA AI is successfully resolving all tickets. Escalations will appear here when the AI needs human guidance.
      </p>
    </motion.div>
  );
}

// ── Auto Resume Dialog ───────────────────────────────────────────────

function AutoResumeDialog({
  open,
  onClose,
  onConfirm,
}: {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
}) {
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
          onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            className="w-full max-w-md bg-[#1A1A1A] border border-white/[0.06] rounded-xl p-5 shadow-2xl"
          >
            <div className="flex items-start gap-3 mb-4">
              <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center shrink-0">
                <svg className="w-5 h-5 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.347a1.125 1.125 0 0 1 0 1.972l-11.54 6.347a1.125 1.125 0 0 1-1.667-.986V5.653Z" />
                </svg>
              </div>
              <div>
                <h3 className="text-sm font-semibold text-white">Auto-Resume All</h3>
                <p className="text-xs text-zinc-400 mt-1 leading-relaxed">
                  This will reprocess all escalations that have guidance provided but haven&apos;t been reprocessed yet. Are you sure?
                </p>
              </div>
            </div>
            <div className="flex items-center justify-end gap-2 mt-5">
              <button
                onClick={onClose}
                className="text-[11px] font-medium px-3 py-1.5 rounded-lg bg-white/[0.04] text-zinc-400 hover:text-white hover:bg-white/[0.08] transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => { onClose(); onConfirm(); }}
                className="text-[11px] font-medium px-4 py-1.5 rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20 hover:bg-amber-500/20 transition-colors"
              >
                Confirm Auto-Resume
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

// ── Main Page ────────────────────────────────────────────────────────

export default function EscalationsPage() {
  // BC-001: tenant_id comes from the authenticated user's company_id.
  const { user } = useAuth();
  const tenantId = (user?.company_id as string) || '';

  const {
    escalations,
    stats,
    loading,
    isModalOpen,
    modalMode,
    selectedEscalation,
    filters,
    autoResumeResult,
    fetchEscalations,
    fetchStats,
    setFilters,
    closeModal,
    autoResumeAll,
    batchGuidanceTickets,
  } = useEscalationStore();

  const [autoResumeDialogOpen, setAutoResumeDialogOpen] = useState(false);
  const [searchInput, setSearchInput] = useState(filters.search);
  const searchTimeoutRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  // ── Fetch awaiting_human tickets directly from tickets API ──
  // The escalation vault (InMemoryVaultDB) only stores pipeline-escalated
  // tickets and loses everything on backend restart. This fetches ALL
  // tickets with status='awaiting_human' so they always show up here
  // regardless of how they were escalated (pipeline or manual).
  interface AwaitingTicket {
    id: string;
    ticket_number: string;
    subject: string | null;
    description: string | null;
    status: string;
    priority: string;
    created_at: string;
    customer_name: string | null;
    customer_email: string | null;
  }
  const [awaitingTickets, setAwaitingTickets] = useState<AwaitingTicket[]>([]);
  const [awaitingLoading, setAwaitingLoading] = useState(true);
  const [selectedTicketId, setSelectedTicketId] = useState<string | null>(null);
  const [guidanceText, setGuidanceText] = useState('');
  const [guidanceSubmitting, setGuidanceSubmitting] = useState(false);

  useEffect(() => {
    if (!tenantId) return;
    let cancelled = false;
    setAwaitingLoading(true);
    fetch('/api/v1/tickets?status=awaiting_human&page=1&page_size=50', { credentials: 'include' })
      .then((r) => r.ok ? r.json() : null)
      .then((data) => {
        if (cancelled) return;
        const items = data?.items || data?.tickets || (Array.isArray(data) ? data : []);
        setAwaitingTickets(items);
      })
      .catch(() => {})
      .finally(() => { if (!cancelled) setAwaitingLoading(false); });
    return () => { cancelled = true; };
  }, [tenantId]);

  // Refresh awaiting tickets when guidance is submitted
  const refreshAwaiting = useCallback(() => {
    fetch('/api/v1/tickets?status=awaiting_human&page=1&page_size=50', { credentials: 'include' })
      .then((r) => r.ok ? r.json() : null)
      .then((data) => {
        const items = data?.items || data?.tickets || (Array.isArray(data) ? data : []);
        setAwaitingTickets(items);
      })
      .catch(() => {});
  }, []);

  const handleGuidanceSubmit = useCallback(async () => {
    if (!selectedTicketId || !guidanceText.trim()) return;
    setGuidanceSubmitting(true);
    try {
      const res = await fetch(`/api/v1/tickets/${selectedTicketId}/resume`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ guidance: guidanceText.trim() }),
      });
      if (res.ok) {
        setSelectedTicketId(null);
        setGuidanceText('');
        refreshAwaiting();
      }
    } catch {
      // ignore
    } finally {
      setGuidanceSubmitting(false);
    }
  }, [selectedTicketId, guidanceText, refreshAwaiting]);

  // Initial fetch — wait until tenantId is available (user loaded).
  useEffect(() => {
    if (!tenantId) return;
    fetchStats(tenantId);
    fetchEscalations(tenantId);
  }, [tenantId]);

  // Debounced search
  const handleSearchChange = useCallback(
    (value: string) => {
      setSearchInput(value);
      if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current);
      searchTimeoutRef.current = setTimeout(() => {
        setFilters({ search: value });
        fetchEscalations(tenantId, { search: value });
      }, 300);
    },
    [fetchEscalations, setFilters],
  );

  const handleFilterChange = useCallback(
    (key: string, value: string) => {
      setFilters({ [key]: value } as never);
      fetchEscalations(tenantId, { [key]: value } as never);
    },
    [fetchEscalations, setFilters],
  );

  const handleAutoResume = useCallback(() => {
    autoResumeAll(tenantId);
  }, [autoResumeAll]);

  const handleBatchGuidanceTickets = useCallback(() => {
    batchGuidanceTickets(tenantId);
  }, [batchGuidanceTickets]);

  // Close modal handler
  const handleCloseModal = useCallback(() => {
    closeModal();
  }, [closeModal]);

  return (
    <main className="min-h-screen bg-[#0A0A0A] relative">
      {/* Decorative background glow */}
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute -top-40 -right-40 w-96 h-96 bg-orange-500/5 rounded-full blur-[120px]" />
        <div className="absolute -bottom-40 -left-40 w-96 h-96 bg-amber-500/5 rounded-full blur-[120px]" />
      </div>

      <div className="relative px-4 sm:px-6 lg:px-8 py-6 max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-orange-500/20 to-orange-600/10 border border-orange-500/20 flex items-center justify-center shadow-lg shadow-orange-500/10">
              <svg className="w-5 h-5 text-orange-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
              </svg>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-2xl font-bold text-white tracking-tight">Escalations</h1>
                {!awaitingLoading && awaitingTickets.length > 0 && (
                  <span className="px-2 py-0.5 rounded-full bg-red-500/10 border border-red-500/20 text-red-400 text-[10px] font-bold tabular-nums">
                    {awaitingTickets.length}
                  </span>
                )}
              </div>
              <p className="text-xs text-zinc-500">
                Tickets where the AI needs your guidance to respond
              </p>
            </div>
          </div>
        </div>

        {/* Summary bar */}
        <div className="mb-6 flex items-center gap-4 px-5 py-4 rounded-2xl bg-gradient-to-r from-white/[0.03] to-transparent border border-white/[0.06] backdrop-blur-sm">
          <div className="flex items-center gap-3 flex-1">
            <div className="relative">
              <span className="w-3 h-3 rounded-full bg-red-400 block" />
              <span className="absolute inset-0 w-3 h-3 rounded-full bg-red-400 animate-ping opacity-75" />
            </div>
            <div>
              <p className="text-[10px] text-zinc-500 uppercase tracking-wider font-medium">
                Waiting for Human
              </p>
              <p className="text-xl font-bold text-white tabular-nums">
                {awaitingLoading ? '…' : awaitingTickets.length}
              </p>
            </div>
          </div>
          <div className="h-8 w-px bg-white/[0.06]" />
          <p className="text-xs text-zinc-400">
            {awaitingTickets.length === 0
              ? 'AI is resolving all tickets automatically'
              : 'Click a ticket to open the guidance chat'}
          </p>
        </div>

        {/* Ticket grid — full width cards */}
        {awaitingLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="rounded-2xl bg-white/[0.02] border border-white/[0.06] p-5 animate-pulse h-32" />
            ))}
          </div>
        ) : awaitingTickets.length === 0 ? (
          <div className="rounded-2xl bg-gradient-to-br from-emerald-500/5 to-transparent border border-emerald-500/10 p-16 flex flex-col items-center justify-center gap-4 text-center">
            <div className="w-16 h-16 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center shadow-lg shadow-emerald-500/10">
              <svg className="w-8 h-8 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
              </svg>
            </div>
            <div>
              <p className="text-base font-semibold text-white">All clear</p>
              <p className="text-sm text-zinc-500 mt-1">
                The AI is resolving all tickets automatically.
              </p>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {awaitingTickets.map((ticket) => (
              <div
                key={ticket.id}
                className="group rounded-2xl bg-gradient-to-br from-white/[0.04] to-white/[0.01] border border-white/[0.06] hover:border-orange-500/30 transition-all duration-200 p-5 shadow-lg shadow-black/20 hover:shadow-orange-500/5 flex flex-col"
              >
                <div className="flex items-center justify-between gap-2 mb-3">
                  <span className="text-[10px] font-mono text-orange-400 px-2 py-0.5 rounded-md bg-orange-500/10 border border-orange-500/15">
                    {ticket.ticket_number || ticket.id.slice(0, 8).toUpperCase()}
                  </span>
                  <span className="text-[10px] text-zinc-500 whitespace-nowrap">
                    {formatRelativeDate(ticket.created_at)}
                  </span>
                </div>
                <h3 className="text-sm font-semibold text-white mb-2 line-clamp-1">
                  {ticket.subject || 'No subject'}
                </h3>
                {ticket.description && (
                  <p className="text-xs text-zinc-400 line-clamp-2 leading-relaxed mb-4 flex-1">
                    {ticket.description}
                  </p>
                )}
                <div className="pt-3 border-t border-white/[0.04] flex items-center gap-2">
                  {/* Primary: Discuss with Jarvis */}
                  <a
                    href={`/dashboard/jarvis?ticket_id=${encodeURIComponent(ticket.id)}&ticket_number=${encodeURIComponent(ticket.ticket_number || '')}&subject=${encodeURIComponent(ticket.subject || '')}&description=${encodeURIComponent(ticket.description || '')}`}
                    className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-orange-500/10 border border-orange-500/20 text-orange-400 text-xs font-medium hover:bg-orange-500/20 transition-colors"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H8.25m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H12m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 0 1-2.555-.337A5.972 5.972 0 0 1 5.41 20.97a5.969 5.969 0 0 1-.474-.065 4.48 4.48 0 0 0 .978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25Z" />
                    </svg>
                    Discuss with Jarvis
                  </a>
                  {/* Secondary: Type guidance directly */}
                  <button
                    onClick={() => {
                      setSelectedTicketId(ticket.id);
                      setGuidanceText('');
                    }}
                    className="px-3 py-2 rounded-lg bg-white/[0.03] border border-white/[0.06] text-zinc-400 text-xs font-medium hover:bg-white/[0.06] hover:text-white transition-colors"
                    title="Type guidance directly"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125" />
                    </svg>
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── Floating Chat Popup (centered, like a chat app) ── */}
      {selectedTicketId && (() => {
        const ticket = awaitingTickets.find((t) => t.id === selectedTicketId);
        if (!ticket) return null;
        return (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
            onClick={() => setSelectedTicketId(null)}
          >
            <div
              className="w-full max-w-lg rounded-3xl bg-[#131313] border border-white/[0.08] shadow-2xl overflow-hidden"
              onClick={(e) => e.stopPropagation()}
              style={{ animation: 'popup-in 0.2s ease-out' }}
            >
              {/* Popup Header */}
              <div className="px-6 py-4 border-b border-white/[0.06] bg-gradient-to-r from-orange-500/10 to-transparent flex items-center justify-between">
                <div className="flex items-center gap-3 min-w-0">
                  <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-orange-500/20 to-orange-600/10 border border-orange-500/20 flex items-center justify-center shrink-0">
                    <svg className="w-4 h-4 text-orange-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H8.25m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H12m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 0 1-2.555-.337A5.972 5.972 0 0 1 5.41 20.97a5.969 5.969 0 0 1-.474-.065 4.48 4.48 0 0 0 .978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25Z" />
                    </svg>
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-mono text-orange-400">
                        {ticket.ticket_number || ticket.id.slice(0, 8).toUpperCase()}
                      </span>
                      <span className="text-[10px] text-zinc-500">·</span>
                      <span className="text-[10px] text-zinc-500">{formatRelativeDate(ticket.created_at)}</span>
                    </div>
                    <h2 className="text-sm font-semibold text-white truncate">
                      {ticket.subject || 'No subject'}
                    </h2>
                  </div>
                </div>
                <button
                  onClick={() => setSelectedTicketId(null)}
                  className="w-8 h-8 rounded-lg text-zinc-500 hover:text-white hover:bg-white/[0.06] transition-all flex items-center justify-center shrink-0"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              {/* Chat body — customer message bubble */}
              <div className="px-6 py-5 max-h-[50vh] overflow-y-auto [scrollbar-width:thin] [scrollbar-color:rgba(255,255,255,0.08)_transparent]">
                <div className="flex items-start gap-2.5 mb-4">
                  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-zinc-600 to-zinc-700 flex items-center justify-center text-[11px] font-semibold text-white shrink-0">
                    {(ticket.customer_name || 'C').charAt(0).toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-baseline gap-2 mb-1">
                      <p className="text-xs font-medium text-white">{ticket.customer_name || 'Customer'}</p>
                      <p className="text-[10px] text-zinc-600">{ticket.customer_email || ''}</p>
                    </div>
                    <div className="rounded-2xl rounded-tl-md bg-white/[0.05] border border-white/[0.06] px-4 py-3">
                      <p className="text-sm text-zinc-200 whitespace-pre-wrap leading-relaxed">
                        {ticket.description || '(no description provided)'}
                      </p>
                    </div>
                  </div>
                </div>

                {/* AI status note */}
                <div className="flex items-start gap-2.5">
                  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-orange-500/20 to-orange-600/10 border border-orange-500/20 flex items-center justify-center shrink-0">
                    <svg className="w-4 h-4 text-orange-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09ZM18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 0 0-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 0 0 2.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 0 0 2.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 0 0-2.456 2.456Z" />
                    </svg>
                  </div>
                  <div className="flex-1">
                    <div className="flex items-baseline gap-2 mb-1">
                      <p className="text-xs font-medium text-orange-300">PARWA AI</p>
                      <p className="text-[10px] text-zinc-600">paused · needs guidance</p>
                    </div>
                    <div className="rounded-2xl rounded-tl-md bg-orange-500/5 border border-orange-500/15 px-4 py-3">
                      <p className="text-xs text-zinc-400 leading-relaxed">
                        I paused because I need your guidance to respond to this customer.
                        Tell me what to do and I'll resume automatically.
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Chat input — at the bottom */}
              <div className="px-6 py-4 border-t border-white/[0.06] bg-[#0F0F0F]">
                <div className="relative">
                  <textarea
                    value={guidanceText}
                    onChange={(e) => setGuidanceText(e.target.value)}
                    placeholder="Type your guidance to the AI…"
                    rows={3}
                    className="w-full px-4 py-3 pr-14 rounded-2xl bg-white/[0.03] border border-white/[0.06] text-white text-sm placeholder:text-zinc-600 focus:outline-none focus:ring-2 focus:ring-orange-500/30 focus:border-orange-500/30 resize-none transition-all"
                    autoFocus
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                        e.preventDefault();
                        if (guidanceText.trim() && !guidanceSubmitting) {
                          handleGuidanceSubmit();
                        }
                      }
                    }}
                  />
                  <button
                    onClick={handleGuidanceSubmit}
                    disabled={guidanceSubmitting || !guidanceText.trim()}
                    className="absolute bottom-3 right-3 w-9 h-9 rounded-xl bg-orange-500 hover:bg-orange-600 disabled:bg-zinc-700 disabled:text-zinc-500 text-white transition-all flex items-center justify-center shadow-lg shadow-orange-500/20 disabled:shadow-none"
                    title="Send guidance (Cmd+Enter)"
                  >
                    {guidanceSubmitting ? (
                      <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                      </svg>
                    ) : (
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M6 12 3.269 3.125A59.769 59.769 0 0 1 21.485 12 59.768 59.768 0 0 1 3.27 20.875L5.999 12Zm0 0h7.5" />
                      </svg>
                    )}
                  </button>
                </div>
                <div className="flex items-center justify-between mt-2 px-1">
                  <p className="text-[10px] text-zinc-600">
                    {guidanceText.length} chars · <kbd className="px-1 py-0.5 rounded bg-white/[0.06] text-zinc-400">⌘+Enter</kbd> to send
                  </p>
                  <p className="text-[10px] text-zinc-600">
                    AI resumes automatically after sending
                  </p>
                </div>
              </div>
            </div>
          </div>
        );
      })()}

      {/* Popup animation */}
      <style>{`
        @keyframes popup-in {
          from { opacity: 0; transform: scale(0.95) translateY(10px); }
          to { opacity: 1; transform: scale(1) translateY(0); }
        }
      `}</style>
    </main>
  );
}

export const dynamic = 'force-dynamic';