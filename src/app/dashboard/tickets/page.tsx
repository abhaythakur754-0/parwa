'use client';

import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Loader2 } from 'lucide-react';
import toast from 'react-hot-toast';
import {
  useTicketStore,
  fetchTicketMessages,
  CATEGORY_LABELS,
  PRIORITY_LABELS,
  STATUS_LABELS,
  CHANNEL_LABELS,
  VARIANT_LABELS,
  ALL_STATUSES,
  ALL_PRIORITIES,
  ALL_CATEGORIES,
  ALL_CHANNELS,
  ALL_VARIANTS,
  type Ticket,
  type TicketStatus,
  type TicketPriority,
  type TicketCategory,
  type TicketChannel,
  type TicketVariant,
} from '@/lib/ticket-store';
import { useAuth } from '@/hooks/useAuth';
import { WelcomeCard } from '@/components/dashboard';

// ── Color Maps ──────────────────────────────────────────────────────

const PRIORITY_COLORS: Record<TicketPriority, { dot: string; badge: string }> = {
  low: { dot: 'bg-green-400', badge: 'bg-green-500/10 text-green-400 border-green-500/20' },
  medium: { dot: 'bg-yellow-400', badge: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20' },
  high: { dot: 'bg-orange-400', badge: 'bg-orange-500/10 text-orange-400 border-orange-500/20' },
  critical: { dot: 'bg-red-400', badge: 'bg-red-500/10 text-red-400 border-red-500/20' },
};

const STATUS_COLORS: Record<TicketStatus, { dot: string; badge: string }> = {
  open: { dot: 'bg-blue-400', badge: 'bg-blue-500/10 text-blue-400 border-blue-500/20' },
  in_progress: { dot: 'bg-blue-400', badge: 'bg-blue-500/10 text-blue-400 border-blue-500/20' },
  resolved: { dot: 'bg-green-400', badge: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' },
  closed: { dot: 'bg-green-400', badge: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' },
  awaiting_human: { dot: 'bg-red-400', badge: 'bg-red-500/10 text-red-400 border-red-500/20' },
  awaiting_client: { dot: 'bg-blue-400', badge: 'bg-blue-500/10 text-blue-400 border-blue-500/20' },
};

// Simplified status display — 3 options only (per user request):
//   Solved = resolved + closed
//   Not Solved = open + in_progress + awaiting_client
//   Waiting for Human = awaiting_human
function getDisplayStatus(status: TicketStatus): 'solved' | 'not_solved' | 'waiting' {
  if (status === 'resolved' || status === 'closed') return 'solved';
  if (status === 'awaiting_human') return 'waiting';
  return 'not_solved';
}

const DISPLAY_STATUS_LABELS: Record<'solved' | 'not_solved' | 'waiting', string> = {
  solved: 'Solved',
  not_solved: 'Not Solved',
  waiting: 'Waiting for Human',
};

const DISPLAY_STATUS_COLORS: Record<'solved' | 'not_solved' | 'waiting', { dot: string; badge: string }> = {
  solved: { dot: 'bg-green-400', badge: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' },
  not_solved: { dot: 'bg-blue-400', badge: 'bg-blue-500/10 text-blue-400 border-blue-500/20' },
  waiting: { dot: 'bg-red-400', badge: 'bg-red-500/10 text-red-400 border-red-500/20' },
};

const VARIANT_COLORS: Record<TicketVariant, string> = {
  light: 'bg-zinc-500/10 text-zinc-300 border-zinc-500/20',
  medium: 'bg-sky-500/10 text-sky-300 border-sky-500/20',
  heavy: 'bg-orange-500/10 text-orange-300 border-orange-500/20',
};

// ── Helpers ─────────────────────────────────────────────────────────

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

// ── Badge Components ────────────────────────────────────────────────

function StatusBadge({ status }: { status: TicketStatus }) {
  const displayStatus = getDisplayStatus(status);
  const c = DISPLAY_STATUS_COLORS[displayStatus];
  return (
    <span className={`inline-flex items-center gap-1.5 text-[10px] font-medium px-2 py-0.5 rounded-full border ${c.badge}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${c.dot}`} />
      {DISPLAY_STATUS_LABELS[displayStatus]}
    </span>
  );
}

function PriorityBadge({ priority }: { priority: TicketPriority }) {
  const c = PRIORITY_COLORS[priority];
  return (
    <span className={`inline-flex items-center gap-1.5 text-[10px] font-medium px-2 py-0.5 rounded-full border ${c.badge}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${c.dot}`} />
      {PRIORITY_LABELS[priority]}
    </span>
  );
}

function VariantBadge({ variant }: { variant: TicketVariant }) {
  return (
    <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full border ${VARIANT_COLORS[variant]}`}>
      {VARIANT_LABELS[variant]}
    </span>
  );
}

// ── Filter Dropdown ─────────────────────────────────────────────────

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
        className="h-8 bg-[#1A1A1A] border border-white/[0.06] rounded-lg px-2.5 text-xs text-zinc-300 focus:outline-none focus:border-orange-500/40 appearance-none cursor-pointer pr-7"
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

// ── Stat Pill ───────────────────────────────────────────────────────

function StatPill({
  label,
  count,
  dotColor,
}: {
  label: string;
  count: number;
  dotColor: string;
}) {
  return (
    <div className="flex items-center gap-2 bg-[#1A1A1A] border border-white/[0.06] rounded-lg px-3 py-2">
      <span className={`w-2 h-2 rounded-full ${dotColor}`} />
      <span className="text-xs text-zinc-400">{label}</span>
      <span className="text-sm font-semibold text-white tabular-nums">{count}</span>
    </div>
  );
}

// ── Customer Context Panel (shows integration data) ─────────────────

function CustomerContextPanel({
  ticketId,
  customerEmail,
}: {
  ticketId: string;
  customerEmail: string;
}) {
  const [contextData, setContextData] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    // Fetch the ticket detail from the backend — it includes metadata_json
    // which may contain CRM data, ecommerce orders, and carrier tracking
    // that Node 3 fetched during pipeline processing.
    fetch(`/api/v1/tickets/${ticketId}`, { credentials: 'include' })
      .then((r) => r.json())
      .then((data) => {
        if (cancelled) return;
        // The metadata_json field may contain CRM/ecommerce/carrier data
        const meta = data.metadata_json || {};
        setContextData(meta);
      })
      .catch(() => {
        if (!cancelled) setContextData(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [ticketId]);

  if (loading) {
    return (
      <div className="px-4 py-3 border-b border-white/[0.06]">
        <p className="text-[10px] text-zinc-600">Loading customer context...</p>
      </div>
    );
  }

  if (!contextData || Object.keys(contextData).length === 0) {
    return null; // No integration data — don't show the panel
  }

  return (
    <div className="px-4 py-3 border-b border-white/[0.06] bg-white/[0.01]">
      <p className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wide mb-2">
        Customer Context
      </p>
      <div className="space-y-1.5 text-[11px]">
        {Object.entries(contextData).slice(0, 8).map(([key, value]) => (
          <div key={key} className="flex justify-between gap-2">
            <span className="text-zinc-500 capitalize">{key.replace(/_/g, ' ')}</span>
            <span className="text-zinc-300 text-right truncate max-w-[200px]">
              {typeof value === 'object'
                ? JSON.stringify(value).slice(0, 80) + '...'
                : String(value).slice(0, 80)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Ticket Detail Panel ─────────────────────────────────────────────

function TicketDetailPanel({
  ticket,
  onClose,
}: {
  ticket: Ticket;
  onClose: () => void;
}) {
  const resolveTicket = useTicketStore((s) => s.resolveTicket);
  const escalateToHuman = useTicketStore((s) => s.escalateToHuman);
  const resumeWithGuidance = useTicketStore((s) => s.resumeWithGuidance);
  const updateTicketStatus = useTicketStore((s) => s.updateTicketStatus);
  const updatePriority = useTicketStore((s) => s.updatePriority);
  const addMessage = useTicketStore((s) => s.addMessage);

  const [replyText, setReplyText] = useState('');
  const [statusDropdownOpen, setStatusDropdownOpen] = useState(false);
  const [priorityDropdownOpen, setPriorityDropdownOpen] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const statusRef = useRef<HTMLDivElement>(null);
  const priorityRef = useRef<HTMLDivElement>(null);

  // Scroll messages to bottom on open / new message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [ticket.messages.length]);

  // Close dropdowns on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (statusRef.current && !statusRef.current.contains(e.target as Node)) setStatusDropdownOpen(false);
      if (priorityRef.current && !priorityRef.current.contains(e.target as Node)) setPriorityDropdownOpen(false);
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const handleResolve = () => {
    resolveTicket(ticket.id);
  };

  const handleEscalate = () => {
    escalateToHuman(ticket.id);
  };

  const [guidanceText, setGuidanceText] = useState('');
  const [resuming, setResuming] = useState(false);

  const handleResumeWithGuidance = async () => {
    if (!guidanceText.trim()) {
      toast.error('Please enter guidance for the AI to resume with.');
      return;
    }
    setResuming(true);
    const ok = await resumeWithGuidance(ticket.id, guidanceText.trim());
    if (ok) {
      toast.success('Pipeline resumed with guidance. AI is processing...');
      setGuidanceText('');
    } else {
      toast.error('Failed to resume pipeline. Please try again.');
    }
    setResuming(false);
  };

  const handleSendReply = () => {
    if (!replyText.trim()) return;
    addMessage(ticket.id, {
      sender: 'human_agent',
      sender_name: 'Human Agent',
      content: replyText.trim(),
      variant: ticket.assigned_variant ?? undefined,
    });
    setReplyText('');
  };

  const handleStatusChange = (status: TicketStatus) => {
    updateTicketStatus(ticket.id, status);
    setStatusDropdownOpen(false);
  };

  const handlePriorityChange = (priority: TicketPriority) => {
    updatePriority(ticket.id, priority);
    setPriorityDropdownOpen(false);
  };

  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 20 }}
      transition={{ duration: 0.25 }}
      className="w-full lg:w-[440px] xl:w-[480px] shrink-0 bg-[#1A1A1A] border border-white/[0.06] rounded-xl overflow-hidden flex flex-col max-h-[calc(100vh-180px)]"
    >
      {/* Header */}
      <div className="p-4 border-b border-white/[0.06] flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-mono text-orange-400">{ticket.ticket_number}</span>
            <StatusBadge status={ticket.status} />
            <PriorityBadge priority={ticket.priority} />
          </div>
          <h3 className="text-sm font-semibold text-white truncate">{ticket.subject}</h3>
        </div>
        <button
          onClick={onClose}
          className="w-7 h-7 flex items-center justify-center rounded-lg text-zinc-400 hover:text-white hover:bg-white/5 transition-colors shrink-0"
          aria-label="Close detail panel"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Customer Info */}
      <div className="px-4 py-3 border-b border-white/[0.06] bg-white/[0.01]">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-orange-500/20 to-amber-500/20 border border-orange-500/20 flex items-center justify-center text-xs font-semibold text-orange-300">
            {ticket.customer_name.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase()}
          </div>
          <div className="min-w-0">
            <p className="text-sm font-medium text-white truncate">{ticket.customer_name}</p>
            <p className="text-xs text-zinc-500 truncate">{ticket.customer_email}</p>
          </div>
        </div>
        <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-[11px]">
          <div className="text-zinc-500">Category</div>
          <div className="text-zinc-300">{CATEGORY_LABELS[ticket.category]}</div>
          <div className="text-zinc-500">Channel</div>
          <div className="text-zinc-300 capitalize">{CHANNEL_LABELS[ticket.channel]}</div>
          <div className="text-zinc-500">Variant</div>
          <div className="text-zinc-300">{ticket.assigned_variant ? VARIANT_LABELS[ticket.assigned_variant] : '—'}</div>
          <div className="text-zinc-500">AI Confidence</div>
          <div className="text-zinc-300">{ticket.ai_confidence != null ? `${ticket.ai_confidence}%` : '—'}</div>
          <div className="text-zinc-500">Created</div>
          <div className="text-zinc-300">{formatDate(ticket.created_at)}</div>
          {ticket.resolved_at && (
            <>
              <div className="text-zinc-500">Resolved</div>
              <div className="text-zinc-300">{formatDate(ticket.resolved_at)}</div>
            </>
          )}
          {ticket.resolution_time_hours != null && (
            <>
              <div className="text-zinc-500">Resolution Time</div>
              <div className="text-zinc-300">{ticket.resolution_time_hours}h</div>
            </>
          )}
        </div>
        {ticket.description && (
          <p className="mt-2 text-xs text-zinc-400 leading-relaxed line-clamp-3">{ticket.description}</p>
        )}
        {ticket.tags.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {ticket.tags.map((tag) => (
              <span key={tag} className="text-[10px] px-1.5 py-0.5 rounded bg-white/[0.05] text-zinc-500 border border-white/[0.04]">
                {tag}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Customer Context (from integrations — CRM, e-commerce, carrier) */}
      <CustomerContextPanel ticketId={ticket.id} customerEmail={ticket.customer_email} />

      {/* Action Buttons */}
      <div className="px-4 py-3 border-b border-white/[0.06] flex flex-wrap items-center gap-2">
        {ticket.status !== 'resolved' && ticket.status !== 'closed' && (
          <button
            onClick={handleResolve}
            className="inline-flex items-center gap-1.5 text-[11px] font-medium px-3 py-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/20 transition-colors"
          >
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
            </svg>
            Resolve
          </button>
        )}
        {ticket.status !== 'awaiting_human' && ticket.status !== 'resolved' && ticket.status !== 'closed' && (
          <button
            onClick={handleEscalate}
            className="inline-flex items-center gap-1.5 text-[11px] font-medium px-3 py-1.5 rounded-lg bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500/20 transition-colors"
          >
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0 0 13.5 3h-6a2.25 2.25 0 0 0-2.25 2.25v13.5A2.25 2.25 0 0 0 7.5 21h6a2.25 2.25 0 0 0 2.25-2.25V15m3 0 3-3m0 0-3-3m3 3H9" />
            </svg>
            Escalate to Human
          </button>
        )}

        {/* Resume with Guidance — shown when AI paused (awaiting_human) */}
        {ticket.status === 'awaiting_human' && (
          <div className="w-full mt-2 p-3 rounded-lg bg-amber-500/5 border border-amber-500/20 space-y-2">
            <div className="flex items-center gap-1.5">
              <svg className="w-3.5 h-3.5 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
              </svg>
              <span className="text-[11px] font-medium text-amber-400">AI Paused — Needs Guidance</span>
            </div>
            <p className="text-[10px] text-zinc-500">
              The AI pipeline paused because it needs help. Enter guidance below and
              the pipeline will resume from where it stopped — no restart needed.
            </p>
            <textarea
              value={guidanceText}
              onChange={(e) => setGuidanceText(e.target.value)}
              placeholder="e.g. The refund policy allows full refunds within 30 days. Approve the $50 refund."
              rows={2}
              className="w-full px-2 py-1.5 rounded-md bg-white/[0.03] border border-white/[0.06] text-white text-xs placeholder:text-zinc-600 focus:outline-none focus:ring-1 focus:ring-amber-500/40 focus:border-amber-500/40 resize-none"
            />
            <div className="flex items-center gap-2">
              <button
                onClick={handleResumeWithGuidance}
                disabled={resuming || !guidanceText.trim()}
                className="inline-flex items-center gap-1.5 text-[11px] font-medium px-3 py-1.5 rounded-lg bg-amber-500/20 text-amber-300 border border-amber-500/30 hover:bg-amber-500/30 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {resuming ? (
                  <>
                    <svg className="animate-spin w-3 h-3" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                    </svg>
                    Resuming...
                  </>
                ) : (
                  <>
                    <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.348a1.125 1.125 0 010 1.971l-11.54 6.347a1.125 1.125 0 01-1.667-.985V5.653z" />
                    </svg>
                    Resume with Guidance
                  </>
                )}
              </button>
              <span className="text-[10px] text-zinc-600">
                {guidanceText.trim().length} chars
              </span>
            </div>
          </div>
        )}

        {/* Change Priority dropdown */}
        <div ref={priorityRef} className="relative">
          <button
            onClick={() => { setPriorityDropdownOpen(!priorityDropdownOpen); setStatusDropdownOpen(false); }}
            className="inline-flex items-center gap-1.5 text-[11px] font-medium px-3 py-1.5 rounded-lg bg-white/[0.04] text-zinc-300 border border-white/[0.06] hover:bg-white/[0.08] transition-colors"
          >
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 4.5h14.25M3 9h9.75M3 13.5h5.25m5.25-.75L17.25 9m0 0L21 12.75M17.25 9v12" />
            </svg>
            Priority
          </button>
          <AnimatePresence>
            {priorityDropdownOpen && (
              <motion.div
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                className="absolute top-full left-0 mt-1 w-40 bg-[#1A1A1A] border border-white/[0.06] rounded-lg shadow-xl z-20 py-1 overflow-hidden"
              >
                {ALL_PRIORITIES.map((p) => (
                  <button
                    key={p}
                    onClick={() => handlePriorityChange(p)}
                    className={`w-full text-left text-xs px-3 py-2 hover:bg-white/[0.05] transition-colors flex items-center gap-2 ${
                      ticket.priority === p ? 'text-orange-400' : 'text-zinc-300'
                    }`}
                  >
                    <span className={`w-1.5 h-1.5 rounded-full ${PRIORITY_COLORS[p].dot}`} />
                    {PRIORITY_LABELS[p]}
                    {ticket.priority === p && (
                      <svg className="w-3 h-3 ml-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
                      </svg>
                    )}
                  </button>
                ))}
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Change Status dropdown */}
        <div ref={statusRef} className="relative">
          <button
            onClick={() => { setStatusDropdownOpen(!statusDropdownOpen); setPriorityDropdownOpen(false); }}
            className="inline-flex items-center gap-1.5 text-[11px] font-medium px-3 py-1.5 rounded-lg bg-white/[0.04] text-zinc-300 border border-white/[0.06] hover:bg-white/[0.08] transition-colors"
          >
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182" />
            </svg>
            Status
          </button>
          <AnimatePresence>
            {statusDropdownOpen && (
              <motion.div
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                className="absolute top-full left-0 mt-1 w-48 bg-[#1A1A1A] border border-white/[0.06] rounded-lg shadow-xl z-20 py-1 overflow-hidden"
              >
                {ALL_STATUSES.map((s) => (
                  <button
                    key={s}
                    onClick={() => handleStatusChange(s)}
                    className={`w-full text-left text-xs px-3 py-2 hover:bg-white/[0.05] transition-colors flex items-center gap-2 ${
                      ticket.status === s ? 'text-orange-400' : 'text-zinc-300'
                    }`}
                  >
                    <span className={`w-1.5 h-1.5 rounded-full ${STATUS_COLORS[s].dot}`} />
                    {STATUS_LABELS[s]}
                    {ticket.status === s && (
                      <svg className="w-3 h-3 ml-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
                      </svg>
                    )}
                  </button>
                ))}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* Message Thread */}
      <div className="flex-1 overflow-y-auto min-h-0 px-4 py-3 space-y-3">
        {ticket.messages.length === 0 ? (
          <p className="text-xs text-zinc-600 text-center py-6">No messages yet</p>
        ) : (
          ticket.messages.map((msg) => {
            const isCustomer = msg.sender === 'customer';
            const isAI = msg.sender === 'ai_agent';
            const isSystem = msg.sender === 'system';
            return (
              <div key={msg.id} className={`flex ${isCustomer ? 'justify-start' : 'justify-end'}`}>
                <div
                  className={`max-w-[85%] rounded-xl px-3 py-2 ${
                    isCustomer
                      ? 'bg-white/[0.04] border border-white/[0.06] rounded-bl-sm'
                      : isSystem
                      ? 'bg-amber-500/5 border border-amber-500/10 rounded-br-sm'
                      : 'bg-orange-500/10 border border-orange-500/15 rounded-br-sm'
                  }`}
                >
                  <div className="flex items-center gap-1.5 mb-1">
                    <span className={`text-[10px] font-semibold ${isCustomer ? 'text-zinc-400' : isSystem ? 'text-amber-400' : 'text-orange-400'}`}>
                      {msg.sender_name}
                    </span>
                    {isAI && msg.variant && (
                      <span className="text-[9px] px-1 py-0.5 rounded bg-orange-500/10 text-orange-300 border border-orange-500/10">
                        {msg.variant}
                      </span>
                    )}
                    <span className="text-[9px] text-zinc-600">{formatRelativeDate(msg.created_at)}</span>
                  </div>
                  <p className="text-xs text-zinc-300 leading-relaxed whitespace-pre-wrap">{msg.content}</p>
                </div>
              </div>
            );
          })
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Reply Input */}
      {ticket.status !== 'resolved' && ticket.status !== 'closed' && (
        <div className="px-4 py-3 border-t border-white/[0.06]">
          <div className="flex items-end gap-2">
            <textarea
              value={replyText}
              onChange={(e) => setReplyText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSendReply();
                }
              }}
              placeholder="Type a reply..."
              rows={2}
              className="flex-1 bg-[#0A0A0A] border border-white/[0.06] rounded-lg px-3 py-2 text-xs text-white placeholder:text-zinc-600 focus:outline-none focus:border-orange-500/40 transition-colors resize-none"
            />
            <button
              onClick={handleSendReply}
              disabled={!replyText.trim()}
              className="h-9 w-9 flex items-center justify-center rounded-lg bg-orange-500 text-white hover:bg-orange-600 transition-colors disabled:opacity-30 disabled:cursor-not-allowed shrink-0"
              aria-label="Send reply"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 12 3.269 3.125A59.769 59.769 0 0 1 21.485 12 59.768 59.768 0 0 1 3.27 20.875L5.999 12Zm0 0h7.5" />
              </svg>
            </button>
          </div>
        </div>
      )}
    </motion.div>
  );
}

// ── Ticket Row ──────────────────────────────────────────────────────

function TicketRow({
  ticket,
  isSelected,
  onClick,
}: {
  ticket: Ticket;
  isSelected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`w-full text-left grid grid-cols-[5rem_1fr_8rem_6rem] gap-2 items-center px-4 py-3 border-b border-white/[0.03] transition-colors hover:bg-white/[0.02] ${
        isSelected ? 'bg-orange-500/5 border-l-2 border-l-orange-500' : 'border-l-2 border-l-transparent'
      }`}
    >
      <span className="text-xs font-mono text-orange-400">{ticket.ticket_number}</span>
      <span className="text-xs text-white truncate font-medium">{ticket.subject}</span>
      <StatusBadge status={ticket.status} />
      <span className="text-[10px] text-zinc-500 tabular-nums">{formatRelativeDate(ticket.created_at)}</span>
    </button>
  );
}

// ── Mobile Ticket Card ──────────────────────────────────────────────

function TicketCard({
  ticket,
  isSelected,
  onClick,
}: {
  ticket: Ticket;
  isSelected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`w-full text-left p-4 rounded-xl border transition-colors ${
        isSelected
          ? 'bg-orange-500/5 border-orange-500/30'
          : 'bg-white/[0.02] border-white/[0.06] hover:border-white/[0.12]'
      }`}
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-mono text-orange-400">{ticket.ticket_number}</span>
            <PriorityBadge priority={ticket.priority} />
          </div>
          <p className="text-sm font-medium text-white truncate">{ticket.subject}</p>
        </div>
        <StatusBadge status={ticket.status} />
      </div>
      <div className="flex items-center gap-3 text-xs text-zinc-500">
        <span>{ticket.customer_name}</span>
        <span>&middot;</span>
        <span>{CATEGORY_LABELS[ticket.category]}</span>
        <span>&middot;</span>
        <span>{formatRelativeDate(ticket.created_at)}</span>
      </div>
    </button>
  );
}

// ── Skeleton Loader ─────────────────────────────────────────────────

function SkeletonLoader() {
  return (
    <div className="space-y-6 animate-pulse">
      {/* Stats skeleton */}
      <div className="flex flex-wrap gap-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-9 w-28 bg-white/[0.04] rounded-lg" />
        ))}
      </div>
      {/* Filter skeleton */}
      <div className="flex flex-wrap gap-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-8 w-32 bg-white/[0.04] rounded-lg" />
        ))}
      </div>
      {/* Table skeleton */}
      <div className="bg-[#1A1A1A] border border-white/[0.06] rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-white/[0.06]">
          <div className="h-3 w-40 bg-white/[0.04] rounded" />
        </div>
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="px-4 py-3 border-b border-white/[0.03] flex gap-4">
            <div className="h-3 w-16 bg-white/[0.04] rounded" />
            <div className="h-3 flex-1 bg-white/[0.04] rounded" />
            <div className="h-3 w-20 bg-white/[0.04] rounded" />
            <div className="h-3 w-14 bg-white/[0.04] rounded" />
            <div className="h-3 w-16 bg-white/[0.04] rounded" />
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Empty State ─────────────────────────────────────────────────────

function EmptyState({ onCreate }: { onCreate?: () => void }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="flex flex-col items-center justify-center py-20 text-center"
    >
      <div className="w-16 h-16 rounded-2xl bg-white/[0.03] border border-white/[0.06] flex items-center justify-center mb-5">
        <svg className="w-8 h-8 text-zinc-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 6v.75m0 3v.75m0 3v.75m0 3V18m-9-5.25h5.25M7.5 15h3M3.375 5.25c-.621 0-1.125.504-1.125 1.125v3.026a2.999 2.999 0 0 1 0 5.198v3.026c0 .621.504 1.125 1.125 1.125h17.25c.621 0 1.125-.504 1.125-1.125v-3.026a2.999 2.999 0 0 1 0-5.198V6.375c0-.621-.504-1.125-1.125-1.125H3.375Z" />
        </svg>
      </div>
      <h3 className="text-base font-semibold text-zinc-300 mb-1.5">No tickets yet</h3>
      <p className="text-sm text-zinc-500 max-w-sm mb-5">
        Your ticket inbox is empty. Create a ticket manually or wait for
        customers to email / chat / call — inbound tickets will appear here
        automatically.
      </p>
      {onCreate && (
        <button
          onClick={onCreate}
          className="px-4 py-2 rounded-lg bg-orange-500 hover:bg-orange-600 text-white text-sm font-medium transition-colors flex items-center gap-2"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
          </svg>
          Create First Ticket
        </button>
      )}
    </motion.div>
  );
}

// ── Create Ticket Modal (Simplified) ─────────────────────────────────
//
// Per user request 2026-07-13: remove all unnecessary fields.
// Only show: body (the ticket content) + tool selector dropdown
// (which connected integration the AI should fetch data from).
// Customer info is auto-filled with defaults — the user testing the
// AI doesn't need to enter customer name/email.

interface CreateTicketFormData {
  subject: string;
  description: string;
  customer_name: string;
  customer_email: string;
  category: TicketCategory;
  priority: TicketPriority;
  channel: TicketChannel;
  tags: string[];
  metadata_json: Record<string, unknown>;
}

interface ConnectedIntegration {
  id: string;
  integration_type: string;
  name: string | null;
  status: string;
}

const INTEGRATION_ICONS: Record<string, string> = {
  hubspot: '🎯', shopify: '🛒', salesforce: '☁️', zendesk: '🎫',
  slack: '💬', gmail: '📧', intercom: '💭', pipedrive: '📊',
  supabase: '🗄️', razorpay: '💳', custom: '🔌',
};

const INTEGRATION_NAMES: Record<string, string> = {
  hubspot: 'HubSpot', shopify: 'Shopify', salesforce: 'Salesforce',
  zendesk: 'Zendesk', slack: 'Slack', gmail: 'Gmail', intercom: 'Intercom',
  pipedrive: 'Pipedrive', supabase: 'Supabase CRM', razorpay: 'Razorpay',
  custom: 'Custom Connector',
};

function CreateTicketModal({
  open,
  onClose,
  onSubmit,
}: {
  open: boolean;
  onClose: () => void;
  onSubmit: (data: CreateTicketFormData) => void;
}) {
  const [description, setDescription] = useState('');
  const [selectedTool, setSelectedTool] = useState<string>('');
  const [integrations, setIntegrations] = useState<ConnectedIntegration[]>([]);
  const [submitting, setSubmitting] = useState(false);

  // Fetch connected integrations (tools) when modal opens
  useEffect(() => {
    if (!open) return;
    setDescription('');
    setSelectedTool('');
    fetch('/api/integrations', { credentials: 'include' })
      .then((res) => res.ok ? res.json() : null)
      .then((data) => {
        const list = Array.isArray(data) ? data : (data?.items || []);
        setIntegrations(list.filter((i: ConnectedIntegration) =>
          i.status === 'active' || i.status === 'connected'
        ));
      })
      .catch(() => {});
  }, [open]);

  const canSubmit = description.trim().length > 0;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    setSubmitting(true);
    try {
      const subject = description.trim().slice(0, 60) + (description.length > 60 ? '…' : '');
      const formData: CreateTicketFormData = {
        subject,
        description,
        customer_name: 'Customer',
        customer_email: `customer-${Date.now()}@ticket.parwa.buzz`,
        category: 'technical_support' as TicketCategory,
        priority: 'medium' as TicketPriority,
        channel: 'email' as TicketChannel,
        tags: [],
        metadata_json: selectedTool ? { source_tool: selectedTool } : {},
      };
      onSubmit(formData);
      onClose();
    } finally {
      setSubmitting(false);
    }
  };

  if (!open) return null;

  const inputClasses = "w-full px-3 py-2 rounded-lg bg-white/[0.03] border border-white/[0.06] text-white text-sm placeholder:text-zinc-600 focus:outline-none focus:ring-1 focus:ring-orange-500/40 focus:border-orange-500/40";

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      >
        <motion.div
          initial={{ scale: 0.96, opacity: 0, y: 8 }}
          animate={{ scale: 1, opacity: 1, y: 0 }}
          exit={{ scale: 0.96, opacity: 0, y: 8 }}
          transition={{ duration: 0.18 }}
          className="w-full max-w-xl rounded-2xl bg-[#161616] border border-white/[0.08] shadow-2xl"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.06]">
            <div>
              <h2 className="text-lg font-semibold text-white">Create Ticket</h2>
              <p className="text-xs text-zinc-500 mt-0.5">
                The AI pipeline will resolve it automatically
              </p>
            </div>
            <button
              onClick={onClose}
              className="text-zinc-500 hover:text-zinc-300 transition-colors"
              aria-label="Close"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
            {/* Tool selector — which connected integration to fetch data from */}
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1.5">
                Fetch data from (optional)
              </label>
              <select
                value={selectedTool}
                onChange={(e) => setSelectedTool(e.target.value)}
                className={inputClasses}
              >
                <option value="" className="bg-[#161616]">— None (AI only) —</option>
                {integrations.map((i) => {
                  const icon = INTEGRATION_ICONS[i.integration_type] || '🔌';
                  const name = INTEGRATION_NAMES[i.integration_type] || i.name || i.integration_type;
                  return (
                    <option key={i.id} value={i.integration_type} className="bg-[#161616]">
                      {icon} {name}
                    </option>
                  );
                })}
              </select>
              {integrations.length === 0 && (
                <p className="text-[11px] text-zinc-600 mt-1">
                  No integrations connected. The AI will respond using its knowledge base only.
                </p>
              )}
            </div>

            {/* Body — the ticket content */}
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1.5">
                What does the customer need? *
              </label>
              <textarea
                required
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="e.g. Where is my refund for order ORD-1001? I placed it 5 days ago."
                rows={6}
                className={inputClasses + ' resize-none'}
                autoFocus
              />
              <p className="text-[11px] text-zinc-600 mt-1">
                The AI reads this, fetches data from your connected tool (if selected),
                generates a response, and quality-checks it before replying.
              </p>
            </div>
          </form>

          {/* Footer */}
          <div className="flex items-center justify-end gap-2 px-6 py-4 border-t border-white/[0.06]">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg text-zinc-400 hover:text-white hover:bg-white/[0.04] text-sm font-medium transition-colors"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleSubmit}
              disabled={submitting || !canSubmit}
              className="px-4 py-2 rounded-lg bg-orange-500 hover:bg-orange-600 disabled:bg-zinc-700 disabled:text-zinc-500 text-white text-sm font-medium transition-colors flex items-center gap-2"
            >
              {submitting ? (
                <>
                  <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                  </svg>
                  Creating…
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                  </svg>
                  Create Ticket
                </>
              )}
            </button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

// ── No Results State ────────────────────────────────────────────────

function NoResultsState({ onClearFilters }: { onClearFilters: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="w-12 h-12 rounded-xl bg-white/[0.03] border border-white/[0.06] flex items-center justify-center mb-4">
        <svg className="w-6 h-6 text-zinc-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z" />
        </svg>
      </div>
      <h3 className="text-sm font-semibold text-zinc-300 mb-1">No matching tickets</h3>
      <p className="text-xs text-zinc-500 mb-4">Try adjusting your filters or search term</p>
      <button
        onClick={onClearFilters}
        className="text-xs font-medium text-orange-400 hover:text-orange-300 transition-colors"
      >
        Clear all filters
      </button>
    </div>
  );
}

// ── Main Page ───────────────────────────────────────────────────────

export default function TicketsPage() {
  const tickets = useTicketStore((s) => s.tickets);
  const initialized = useTicketStore((s) => s.initialized);
  const init = useTicketStore((s) => s.init);
  const ticketStats = useTicketStore((s) => s.ticketStats);
  const addTicket = useTicketStore((s) => s.addTicket);

  const [isLoading, setIsLoading] = useState(true);
  const [selectedTicketId, setSelectedTicketId] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<TicketStatus | 'all'>('all');
  const [priorityFilter, setPriorityFilter] = useState<TicketPriority | 'all'>('all');
  const [categoryFilter, setCategoryFilter] = useState<TicketCategory | 'all'>('all');
  const [channelFilter, setChannelFilter] = useState<TicketChannel | 'all'>('all');
  const [searchText, setSearchText] = useState('');
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);

  // Initialize store on mount
  useEffect(() => {
    init();
    // If init didn't set initialized (no localStorage data), mark it ourselves
    // so the loading state resolves
    const timer = setTimeout(() => setIsLoading(false), 400);
    return () => clearTimeout(timer);
  }, [init]);

  // Also stop loading when store initializes from localStorage
  useEffect(() => {
    if (initialized) {
      setIsLoading(false);
    }
  }, [initialized]);

  // Compute stats
  const stats = useMemo(() => ticketStats(), [tickets, ticketStats]);

  // Filter tickets with AND logic
  const filteredTickets = useMemo(() => {
    return tickets.filter((t) => {
      if (statusFilter !== 'all' && t.status !== statusFilter) return false;
      if (priorityFilter !== 'all' && t.priority !== priorityFilter) return false;
      if (categoryFilter !== 'all' && t.category !== categoryFilter) return false;
      if (channelFilter !== 'all' && t.channel !== channelFilter) return false;
      if (searchText.trim()) {
        const q = searchText.toLowerCase();
        const searchable = `${t.ticket_number} ${t.subject} ${t.customer_name} ${t.customer_email} ${t.description} ${t.tags.join(' ')}`.toLowerCase();
        if (!searchable.includes(q)) return false;
      }
      return true;
    });
  }, [tickets, statusFilter, priorityFilter, categoryFilter, channelFilter, searchText]);

  // Get selected ticket object
  const selectedTicket = useMemo(
    () => tickets.find((t) => t.id === selectedTicketId) ?? null,
    [tickets, selectedTicketId]
  );

  // Fetch messages when a ticket is opened in the detail panel
  useEffect(() => {
    if (selectedTicketId) {
      void fetchTicketMessages(selectedTicketId);
    }
  }, [selectedTicketId]);

  const clearFilters = useCallback(() => {
    setStatusFilter('all');
    setPriorityFilter('all');
    setCategoryFilter('all');
    setChannelFilter('all');
    setSearchText('');
  }, []);

  const hasActiveFilters = statusFilter !== 'all' || priorityFilter !== 'all' || categoryFilter !== 'all' || channelFilter !== 'all' || searchText.trim() !== '';

  // ── Loading ──────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Tickets</h1>
          <p className="text-zinc-400 mt-1">Manage and track customer support tickets</p>
        </div>
        <SkeletonLoader />
      </div>
    );
  }

  // ── Empty state ──────────────────────────────────────────────────
  if (tickets.length === 0) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">Tickets</h1>
            <p className="text-zinc-400 mt-1">Manage and track customer support tickets</p>
          </div>
          <button
            onClick={() => setIsCreateModalOpen(true)}
            className="px-4 py-2 rounded-lg bg-orange-500 hover:bg-orange-600 text-white text-sm font-medium transition-colors flex items-center gap-2"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
            </svg>
            Create Ticket
          </button>
        </div>
        <EmptyState onCreate={() => setIsCreateModalOpen(true)} />
        <CreateTicketModal
          open={isCreateModalOpen}
          onClose={() => setIsCreateModalOpen(false)}
          onSubmit={(data) => addTicket(data)}
        />
      </div>
    );
  }

  // ── Main Render ──────────────────────────────────────────────────
  return (
    <div className="space-y-6">
      {/* ── Welcome Card (real variant subscription data) ── */}
      <WelcomeCardSection />

      {/* ── Connected Integrations ── */}
      <ConnectedIntegrationsSection />

      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35 }}
      >
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-white">Tickets</h1>
            <p className="text-sm text-zinc-500 mt-1">
              Manage and track customer support tickets
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setIsCreateModalOpen(true)}
              className="px-4 py-2 rounded-lg bg-orange-500 hover:bg-orange-600 text-white text-sm font-medium transition-colors flex items-center gap-2"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
              </svg>
              Create Ticket
            </button>
          </div>
        </div>
      </motion.div>

      {/* Stats Bar */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, delay: 0.05 }}
        className="flex flex-wrap gap-2"
      >
        <StatPill label="Total" count={stats.total} dotColor="bg-zinc-400" />
        <StatPill label="Not Solved" count={stats.byStatus.open + stats.byStatus.in_progress} dotColor="bg-blue-400" />
        <StatPill label="Solved" count={stats.byStatus.resolved + stats.byStatus.closed} dotColor="bg-green-400" />
        <StatPill label="Waiting for Human" count={stats.byStatus.awaiting_human} dotColor="bg-red-400" />
      </motion.div>

      {/* Filter Row */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, delay: 0.1 }}
        className="flex flex-wrap items-center gap-2"
      >
        <FilterSelect
          label="Status"
          value={statusFilter}
          options={ALL_STATUSES.map((s) => ({ value: s, label: STATUS_LABELS[s] }))}
          onChange={setStatusFilter}
        />
        <div className="flex items-center gap-2 flex-1 min-w-[180px]">
          <div className="relative flex-1">
            <svg
              className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-zinc-500 pointer-events-none"
              fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z" />
            </svg>
            <input
              type="text"
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              placeholder="Search tickets..."
              className="w-full h-8 bg-[#1A1A1A] border border-white/[0.06] rounded-lg pl-8 pr-3 text-xs text-zinc-300 placeholder:text-zinc-600 focus:outline-none focus:border-orange-500/40 transition-colors"
            />
          </div>
        </div>
        {hasActiveFilters && (
          <button
            onClick={clearFilters}
            className="text-[11px] font-medium text-orange-400 hover:text-orange-300 transition-colors whitespace-nowrap"
          >
            Clear filters
          </button>
        )}
      </motion.div>

      {/* Ticket List + Detail */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, delay: 0.15 }}
        className="flex flex-col lg:flex-row gap-4"
      >
        {/* Ticket List */}
        <div className="flex-1 min-w-0">
          {filteredTickets.length === 0 ? (
            <div className="bg-[#1A1A1A] border border-white/[0.06] rounded-xl">
              <NoResultsState onClearFilters={clearFilters} />
            </div>
          ) : (
            <>
              {/* Desktop Table */}
              <div className="hidden xl:block bg-[#1A1A1A] border border-white/[0.06] rounded-xl overflow-hidden">
                {/* Table Header — simplified: Ticket #, Subject, Status, Created only */}
                <div className="grid grid-cols-[5rem_1fr_8rem_6rem] gap-2 items-center px-4 py-2.5 border-b border-white/[0.06] bg-white/[0.02]">
                  <span className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider">Ticket #</span>
                  <span className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider">Subject</span>
                  <span className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider">Status</span>
                  <span className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider">Created</span>
                </div>
                {/* Rows */}
                <div className="max-h-[calc(100vh-380px)] overflow-y-auto">
                  {filteredTickets.map((ticket) => (
                    <TicketRow
                      key={ticket.id}
                      ticket={ticket}
                      isSelected={selectedTicketId === ticket.id}
                      onClick={() => setSelectedTicketId(selectedTicketId === ticket.id ? null : ticket.id)}
                    />
                  ))}
                </div>
              </div>

              {/* Tablet / Mobile Cards */}
              <div className="xl:hidden space-y-2 max-h-[calc(100vh-380px)] overflow-y-auto pr-1">
                {filteredTickets.map((ticket) => (
                  <TicketCard
                    key={ticket.id}
                    ticket={ticket}
                    isSelected={selectedTicketId === ticket.id}
                    onClick={() => setSelectedTicketId(selectedTicketId === ticket.id ? null : ticket.id)}
                  />
                ))}
              </div>
            </>
          )}

          {/* Results count */}
          {filteredTickets.length > 0 && (
            <p className="text-[11px] text-zinc-600 mt-2">
              Showing {filteredTickets.length} of {tickets.length} tickets
            </p>
          )}
        </div>

        {/* Detail Panel */}
        <AnimatePresence mode="wait">
          {selectedTicket && (
            <TicketDetailPanel
              ticket={selectedTicket}
              onClose={() => setSelectedTicketId(null)}
            />
          )}
        </AnimatePresence>
      </motion.div>

      {/* Click-away hint when no ticket selected */}
      {!selectedTicket && filteredTickets.length > 0 && (
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
          className="text-[11px] text-zinc-600 text-center"
        >
          Click a ticket to view details and take actions
        </motion.p>
      )}

      {/* Create Ticket Modal */}
      <CreateTicketModal
        open={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onSubmit={(data) => addTicket(data)}
      />
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────────
// WELCOME CARD SECTION
// Renders the WelcomeCard which shows the user's real subscribed variants
// + monthly ticket usage. NO mock data, NO ROI/AI-cost widgets.
// (Per user request 2026-07-12: remove AI Cost Savings, ROI, Active Agents
//  and Customer Satisfaction KPICards — they were misleading and showed
//  zero-data states before any tickets had been resolved.)
// ────────────────────────────────────────────────────────────────────────

function WelcomeCardSection() {
  const { user } = useAuth();
  return (
    <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }}>
      <WelcomeCard
        userName={user?.full_name}
        companyName={user?.company_name}
        uniqueId={user?.unique_id}
        industry="Support"
      />
    </motion.div>
  );
}

// ────────────────────────────────────────────────────────────────────────
// CONNECTED INTEGRATIONS SECTION
// Shows which integrations the user has connected during onboarding.
// Fetches from /api/integrations (same endpoint used by Settings page).
// ────────────────────────────────────────────────────────────────────────

// NOTE: ConnectedIntegration interface, INTEGRATION_ICONS, and INTEGRATION_NAMES
// are now defined above (near CreateTicketModal) to avoid duplication.

function ConnectedIntegrationsSection() {
  const [integrations, setIntegrations] = useState<ConnectedIntegration[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    fetch('/api/integrations', { credentials: 'include', signal: controller.signal })
      .then((res) => res.ok ? res.json() : null)
      .then((data) => {
        if (Array.isArray(data)) {
          setIntegrations(data.filter((i: ConnectedIntegration) => i.status === 'active' || i.status === 'connected'));
        } else if (data?.items && Array.isArray(data.items)) {
          setIntegrations(data.items.filter((i: ConnectedIntegration) => i.status === 'active' || i.status === 'connected'));
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, []);

  if (loading || integrations.length === 0) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: 0.1 }}
      className="space-y-4"
    >
      <h2 className="text-sm font-medium text-zinc-500 uppercase tracking-wider">Connected Integrations</h2>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
        {integrations.map((integration) => {
          const icon = INTEGRATION_ICONS[integration.integration_type] || '🔌';
          const name = INTEGRATION_NAMES[integration.integration_type] || integration.name || integration.integration_type;
          return (
            <div key={integration.id} className="flex items-center gap-3 px-4 py-3 rounded-xl bg-[#1A1A1A] border border-white/[0.06]">
              <span className="text-2xl">{icon}</span>
              <div className="min-w-0">
                <p className="text-sm font-medium text-white truncate">{name}</p>
                <p className="text-[10px] text-emerald-400 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                  {integration.status}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </motion.div>
  );
}
