'use client';

import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  useTicketStore,
  seedTickets,
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

// ── Color Maps ──────────────────────────────────────────────────────

const PRIORITY_COLORS: Record<TicketPriority, { dot: string; badge: string }> = {
  low: { dot: 'bg-green-400', badge: 'bg-green-500/10 text-green-400 border-green-500/20' },
  medium: { dot: 'bg-yellow-400', badge: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20' },
  high: { dot: 'bg-orange-400', badge: 'bg-orange-500/10 text-orange-400 border-orange-500/20' },
  critical: { dot: 'bg-red-400', badge: 'bg-red-500/10 text-red-400 border-red-500/20' },
};

const STATUS_COLORS: Record<TicketStatus, { dot: string; badge: string }> = {
  open: { dot: 'bg-blue-400', badge: 'bg-blue-500/10 text-blue-400 border-blue-500/20' },
  in_progress: { dot: 'bg-yellow-400', badge: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20' },
  resolved: { dot: 'bg-green-400', badge: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' },
  closed: { dot: 'bg-zinc-400', badge: 'bg-zinc-500/10 text-zinc-400 border-zinc-500/20' },
  awaiting_human: { dot: 'bg-red-400', badge: 'bg-red-500/10 text-red-400 border-red-500/20' },
  awaiting_client: { dot: 'bg-purple-400', badge: 'bg-purple-500/10 text-purple-400 border-purple-500/20' },
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
  const c = STATUS_COLORS[status];
  return (
    <span className={`inline-flex items-center gap-1.5 text-[10px] font-medium px-2 py-0.5 rounded-full border ${c.badge}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${c.dot}`} />
      {STATUS_LABELS[status]}
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

  const handleSendReply = () => {
    if (!replyText.trim()) return;
    addMessage(ticket.id, {
      sender: 'ai_agent',
      sender_name: 'PARWA AI',
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
      className={`w-full text-left grid grid-cols-[5rem_1fr_8rem_5.5rem_6.5rem_7.5rem_4rem_6rem_5rem_5.5rem] gap-2 items-center px-4 py-3 border-b border-white/[0.03] transition-colors hover:bg-white/[0.02] ${
        isSelected ? 'bg-orange-500/5 border-l-2 border-l-orange-500' : 'border-l-2 border-l-transparent'
      }`}
    >
      <span className="text-xs font-mono text-orange-400">{ticket.ticket_number}</span>
      <span className="text-xs text-white truncate font-medium">{ticket.subject}</span>
      <span className="text-xs text-zinc-400 truncate">{ticket.customer_name}</span>
      <PriorityBadge priority={ticket.priority} />
      <StatusBadge status={ticket.status} />
      <span className="text-[10px] text-zinc-500 truncate">{CATEGORY_LABELS[ticket.category]}</span>
      <span className="text-[10px] text-zinc-500 capitalize">{CHANNEL_LABELS[ticket.channel]}</span>
      {ticket.assigned_variant ? (
        <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded border inline-block text-center ${VARIANT_COLORS[ticket.assigned_variant]}`}>
          {ticket.assigned_variant.charAt(0).toUpperCase()}
        </span>
      ) : (
        <span className="text-zinc-600 text-[10px]">—</span>
      )}
      <span className="text-[10px] text-zinc-500 tabular-nums">
        {ticket.ai_confidence != null ? `${ticket.ai_confidence}%` : '—'}
      </span>
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

function EmptyState({ onSeed }: { onSeed: () => void }) {
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
      <p className="text-sm text-zinc-500 max-w-sm mb-6">
        Your ticket inbox is empty. Seed demo data to explore the full ticket management experience.
      </p>
      <button
        onClick={onSeed}
        className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-semibold bg-gradient-to-r from-orange-500 to-amber-400 text-[#1A1A1A] hover:shadow-lg hover:shadow-orange-500/20 hover:-translate-y-0.5 transition-all duration-200"
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
        </svg>
        Seed Demo Data
      </button>
    </motion.div>
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

  const [isLoading, setIsLoading] = useState(true);
  const [selectedTicketId, setSelectedTicketId] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<TicketStatus | 'all'>('all');
  const [priorityFilter, setPriorityFilter] = useState<TicketPriority | 'all'>('all');
  const [categoryFilter, setCategoryFilter] = useState<TicketCategory | 'all'>('all');
  const [channelFilter, setChannelFilter] = useState<TicketChannel | 'all'>('all');
  const [searchText, setSearchText] = useState('');

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

  const handleSeed = useCallback(() => {
    const seeded = seedTickets();
    // Persist to localStorage and update the store directly
    if (typeof window !== 'undefined') {
      localStorage.setItem('parwa_tickets', JSON.stringify(seeded));
      localStorage.setItem('parwa_tickets_initialized', 'true');
    }
    useTicketStore.setState({ tickets: seeded, initialized: true });
  }, []);

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
        <div>
          <h1 className="text-2xl font-bold text-white">Tickets</h1>
          <p className="text-zinc-400 mt-1">Manage and track customer support tickets</p>
        </div>
        <EmptyState onSeed={handleSeed} />
      </div>
    );
  }

  // ── Main Render ──────────────────────────────────────────────────
  return (
    <div className="space-y-6">
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
              {stats.total > 0 && (
                <span className="text-zinc-600"> &middot; {stats.resolutionRate}% resolution rate</span>
              )}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleSeed}
              className="text-xs px-3 py-1.5 rounded-lg bg-white/[0.04] text-zinc-400 hover:text-white hover:bg-white/[0.08] transition-colors border border-white/[0.06]"
            >
              Re-seed Data
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
        <StatPill label="Open" count={stats.byStatus.open} dotColor="bg-blue-400" />
        <StatPill label="In Progress" count={stats.byStatus.in_progress} dotColor="bg-yellow-400" />
        <StatPill label="Resolved" count={stats.byStatus.resolved} dotColor="bg-green-400" />
        <StatPill label="Awaiting Human" count={stats.byStatus.awaiting_human} dotColor="bg-red-400" />
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
        <FilterSelect
          label="Priority"
          value={priorityFilter}
          options={ALL_PRIORITIES.map((p) => ({ value: p, label: PRIORITY_LABELS[p] }))}
          onChange={setPriorityFilter}
        />
        <FilterSelect
          label="Category"
          value={categoryFilter}
          options={ALL_CATEGORIES.map((c) => ({ value: c, label: CATEGORY_LABELS[c] }))}
          onChange={setCategoryFilter}
        />
        <FilterSelect
          label="Channel"
          value={channelFilter}
          options={ALL_CHANNELS.map((ch) => ({ value: ch, label: CHANNEL_LABELS[ch] }))}
          onChange={setChannelFilter}
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
                {/* Table Header */}
                <div className="grid grid-cols-[5rem_1fr_8rem_5.5rem_6.5rem_7.5rem_4rem_6rem_5rem_5.5rem] gap-2 items-center px-4 py-2.5 border-b border-white/[0.06] bg-white/[0.02]">
                  <span className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider">Ticket #</span>
                  <span className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider">Subject</span>
                  <span className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider">Customer</span>
                  <span className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider">Priority</span>
                  <span className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider">Status</span>
                  <span className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider">Category</span>
                  <span className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider">Channel</span>
                  <span className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider">Variant</span>
                  <span className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider">AI Conf</span>
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
    </div>
  );
}
