'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';
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

const TENANT_ID = 'tenant_001';

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

  // Initial fetch
  useEffect(() => {
    fetchStats(TENANT_ID);
    fetchEscalations(TENANT_ID);
  }, []);

  // Debounced search
  const handleSearchChange = useCallback(
    (value: string) => {
      setSearchInput(value);
      if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current);
      searchTimeoutRef.current = setTimeout(() => {
        setFilters({ search: value });
        fetchEscalations(TENANT_ID, { search: value });
      }, 300);
    },
    [fetchEscalations, setFilters],
  );

  const handleFilterChange = useCallback(
    (key: string, value: string) => {
      setFilters({ [key]: value } as never);
      fetchEscalations(TENANT_ID, { [key]: value } as never);
    },
    [fetchEscalations, setFilters],
  );

  const handleAutoResume = useCallback(() => {
    autoResumeAll(TENANT_ID);
  }, [autoResumeAll]);

  const handleBatchGuidanceTickets = useCallback(() => {
    batchGuidanceTickets(TENANT_ID);
  }, [batchGuidanceTickets]);

  // Close modal handler
  const handleCloseModal = useCallback(() => {
    closeModal();
  }, [closeModal]);

  return (
    <main className="min-h-screen bg-zinc-950">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold text-white tracking-tight">Escalation Management</h1>
            <p className="text-xs text-zinc-500 mt-1">
              Tickets where PARWA AI needs human guidance to resolve
            </p>
          </div>
          <div className="flex items-center gap-2 self-start">
            <button
              onClick={() => setAutoResumeDialogOpen(true)}
              disabled={loading || stats.guidance_provided === 0}
              className="inline-flex items-center gap-2 text-[11px] font-medium px-4 py-2 rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20 hover:bg-amber-500/20 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.347a1.125 1.125 0 0 1 0 1.972l-11.54 6.347a1.125 1.125 0 0 1-1.667-.986V5.653Z" />
              </svg>
              Auto-Resume All
              {stats.guidance_provided > 0 && (
                <span className="bg-amber-500/20 text-amber-300 text-[10px] font-bold px-1.5 py-0.5 rounded-full">
                  {stats.guidance_provided}
                </span>
              )}
            </button>
            {stats.failed > 0 && (
              <button
                onClick={handleBatchGuidanceTickets}
                disabled={loading}
                className="inline-flex items-center gap-2 text-[11px] font-medium px-4 py-2 rounded-lg bg-violet-500/10 text-violet-400 border border-violet-500/20 hover:bg-violet-500/20 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09ZM18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 0 0-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 0 0 2.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 0 0 2.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 0 0-2.456 2.456ZM16.894 20.567 16.5 21.75l-.394-1.183a2.25 2.25 0 0 0-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 0 0 1.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 0 0 1.423 1.423l1.183.394-1.183.394a2.25 2.25 0 0 0-1.423 1.423Z" />
                </svg>
                Retry Failed as Direct
                <span className="bg-violet-500/20 text-violet-300 text-[10px] font-bold px-1.5 py-0.5 rounded-full">
                  {stats.failed}
                </span>
              </button>
            )}
          </div>
        </div>

        {/* Auto Resume Result Banner */}
        <AnimatePresence>
          {autoResumeResult && (
            <motion.div
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-4 flex items-center gap-3"
            >
              <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center shrink-0">
                <svg className="w-4 h-4 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
                </svg>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-white">{autoResumeResult.message}</p>
                <p className="text-[10px] text-zinc-500 mt-0.5">
                  {autoResumeResult.success} succeeded, {autoResumeResult.failed} failed
                </p>
              </div>
              <button
                onClick={() => useEscalationStore.setState({ autoResumeResult: null })}
                className="w-6 h-6 flex items-center justify-center rounded text-zinc-500 hover:text-white hover:bg-white/5 transition-colors"
                aria-label="Dismiss"
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
                </svg>
              </button>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Stats Cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {loading ? (
            <>
              <StatCardSkeleton />
              <StatCardSkeleton />
              <StatCardSkeleton />
              <StatCardSkeleton />
            </>
          ) : (
            <>
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0 }}
                className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-4"
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[10px] text-zinc-500 uppercase tracking-wider font-medium">Awaiting Human</span>
                  <span className="w-2 h-2 rounded-full bg-red-400 animate-pulse" />
                </div>
                <p className="text-2xl font-bold text-red-400 tabular-nums">{stats.awaiting_human}</p>
                <p className="text-[10px] text-zinc-600 mt-1">Needs guidance</p>
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.05 }}
                className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-4"
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[10px] text-zinc-500 uppercase tracking-wider font-medium">Guidance Provided</span>
                  <span className="w-2 h-2 rounded-full bg-amber-400" />
                </div>
                <p className="text-2xl font-bold text-amber-400 tabular-nums">{stats.guidance_provided}</p>
                <p className="text-[10px] text-zinc-600 mt-1">Ready to resume</p>
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 }}
                className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-4"
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[10px] text-zinc-500 uppercase tracking-wider font-medium">Resolved</span>
                  <span className="w-2 h-2 rounded-full bg-emerald-400" />
                </div>
                <p className="text-2xl font-bold text-emerald-400 tabular-nums">{stats.resolved}</p>
                <p className="text-[10px] text-zinc-600 mt-1">
                  {stats.total > 0 ? `${Math.round((stats.resolved / stats.total) * 100)}%` : '0%'} resolve rate
                </p>
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.15 }}
                className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-4"
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[10px] text-zinc-500 uppercase tracking-wider font-medium">Failed</span>
                  <span className="w-2 h-2 rounded-full bg-red-400" />
                </div>
                <p className="text-2xl font-bold text-red-400 tabular-nums">{stats.failed}</p>
                <p className="text-[10px] text-zinc-600 mt-1">Reprocess failures</p>
              </motion.div>
            </>
          )}
        </div>

        {/* Filter Bar */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-2 p-3 rounded-xl bg-[#1A1A1A] border border-white/[0.06]">
          <div className="relative flex-1 w-full sm:w-auto">
            <svg
              className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-zinc-600"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z" />
            </svg>
            <input
              type="text"
              value={searchInput}
              onChange={(e) => handleSearchChange(e.target.value)}
              placeholder="Search ticket ID or notification key..."
              className="w-full h-8 bg-[#0A0A0A] border border-white/[0.06] rounded-lg pl-9 pr-3 text-xs text-white placeholder:text-zinc-600 focus:outline-none focus:border-blue-500/40 transition-colors"
            />
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <FilterSelect
              label="Status"
              value={filters.humanStatus}
              options={ALL_HUMAN_STATUSES.map((s) => ({ value: s, label: HUMAN_STATUS_LABELS[s] }))}
              onChange={(v) => handleFilterChange('humanStatus', v)}
            />
            <FilterSelect
              label="Reprocess"
              value={filters.reprocessStatus}
              options={ALL_REPROCESS_STATUSES.map((s) => ({ value: s, label: REPROCESS_STATUS_LABELS[s] }))}
              onChange={(v) => handleFilterChange('reprocessStatus', v)}
            />
          </div>
        </div>

        {/* Escalation List */}
        {loading && escalations.length === 0 ? (
          <div className="space-y-3">
            <EscalationCardSkeleton />
            <EscalationCardSkeleton />
            <EscalationCardSkeleton />
          </div>
        ) : escalations.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 max-h-[calc(100vh-380px)] overflow-y-auto pr-1 [scrollbar-width:thin] [scrollbar-color:rgba(255,255,255,0.08)_transparent]">
            <AnimatePresence mode="popLayout">
              {escalations.map((esc, i) => (
                <EscalationCard key={esc.escalation_id} escalation={esc} index={i} />
              ))}
            </AnimatePresence>
          </div>
        )}
      </div>

      {/* Modals */}
      <AnimatePresence>
        {isModalOpen && selectedEscalation && (
          modalMode === 'guidance' ? (
            <GuidanceModal escalation={selectedEscalation} onClose={handleCloseModal} />
          ) : (
            <ViewResultPanel escalation={selectedEscalation} onClose={handleCloseModal} />
          )
        )}
      </AnimatePresence>

      {/* Auto Resume Dialog */}
      <AutoResumeDialog
        open={autoResumeDialogOpen}
        onClose={() => setAutoResumeDialogOpen(false)}
        onConfirm={handleAutoResume}
      />

      </main>
  );
}

export const dynamic = 'force-dynamic';