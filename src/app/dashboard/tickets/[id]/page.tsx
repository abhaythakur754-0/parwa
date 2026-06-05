'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import {
  useTicketStore,
  seedTickets,
  CATEGORY_LABELS,
  PRIORITY_LABELS,
  STATUS_LABELS,
  CHANNEL_LABELS,
  VARIANT_LABELS,
  ALL_PRIORITIES,
  type TicketPriority,
  type TicketStatus,
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

// ── Ticket Detail Page ─────────────────────────────────────────────

export default function TicketDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  const tickets = useTicketStore((s) => s.tickets);
  const init = useTicketStore((s) => s.init);
  const getTicket = useTicketStore((s) => s.getTicket);
  const getTicketByNumber = useTicketStore((s) => s.getTicketByNumber);
  const resolveTicket = useTicketStore((s) => s.resolveTicket);
  const escalateToHuman = useTicketStore((s) => s.escalateToHuman);
  const updatePriority = useTicketStore((s) => s.updatePriority);
  const addMessage = useTicketStore((s) => s.addMessage);

  const [replyText, setReplyText] = useState('');
  const [priorityDropdownOpen, setPriorityDropdownOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const priorityRef = useRef<HTMLDivElement>(null);

  // Initialize store on mount
  useEffect(() => {
    init();
    const timer = setTimeout(() => setIsLoading(false), 400);
    return () => clearTimeout(timer);
  }, [init]);

  useEffect(() => {
    if (tickets.length > 0) {
      setIsLoading(false);
    }
  }, [tickets]);

  // Close priority dropdown on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (priorityRef.current && !priorityRef.current.contains(e.target as Node)) {
        setPriorityDropdownOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  // Find the ticket by id or ticket_number
  const ticket = getTicket(id) ?? getTicketByNumber(id) ?? null;

  // Scroll messages to bottom
  useEffect(() => {
    if (ticket) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [ticket?.messages.length, ticket]);

  const handleResolve = () => {
    if (!ticket) return;
    resolveTicket(ticket.id);
  };

  const handleEscalate = () => {
    if (!ticket) return;
    escalateToHuman(ticket.id);
  };

  const handleSendReply = () => {
    if (!ticket || !replyText.trim()) return;
    addMessage(ticket.id, {
      sender: 'ai_agent',
      sender_name: 'PARWA AI',
      content: replyText.trim(),
      variant: ticket.assigned_variant ?? undefined,
    });
    setReplyText('');
  };

  const handlePriorityChange = (priority: TicketPriority) => {
    if (!ticket) return;
    updatePriority(ticket.id, priority);
    setPriorityDropdownOpen(false);
  };

  // ── Loading State ─────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="flex items-center gap-3">
          <div className="w-20 h-4 bg-white/[0.04] rounded" />
          <div className="w-32 h-6 bg-white/[0.04] rounded" />
        </div>
        <div className="h-40 bg-white/[0.04] rounded-xl" />
        <div className="h-60 bg-white/[0.04] rounded-xl" />
      </div>
    );
  }

  // ── Not Found State ───────────────────────────────────────────────
  if (!ticket) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="flex flex-col items-center justify-center py-24 text-center"
      >
        <div className="w-16 h-16 rounded-2xl bg-white/[0.03] border border-white/[0.06] flex items-center justify-center mb-5">
          <svg className="w-8 h-8 text-zinc-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 3.75h.008v.008H12v-.008Z" />
          </svg>
        </div>
        <h3 className="text-lg font-semibold text-zinc-300 mb-2">Ticket not found</h3>
        <p className="text-sm text-zinc-500 max-w-sm mb-6">
          The ticket you are looking for does not exist or may have been removed.
        </p>
        <button
          onClick={() => router.push('/dashboard/tickets')}
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-semibold bg-gradient-to-r from-orange-500 to-amber-400 text-[#1A1A1A] hover:shadow-lg hover:shadow-orange-500/20 hover:-translate-y-0.5 transition-all duration-200"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5 3 12m0 0 7.5-7.5M3 12h18" />
          </svg>
          Back to Tickets
        </button>
      </motion.div>
    );
  }

  // ── Ticket Found: Full Detail View ────────────────────────────────
  const isResolvedOrClosed = ticket.status === 'resolved' || ticket.status === 'closed';

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="space-y-6"
    >
      {/* Back button */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => router.push('/dashboard/tickets')}
          className="inline-flex items-center gap-1.5 text-xs text-zinc-400 hover:text-white transition-colors"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5 3 12m0 0 7.5-7.5M3 12h18" />
          </svg>
          Back to Tickets
        </button>
      </div>

      {/* ── Ticket Header ──────────────────────────────────────────── */}
      <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] overflow-hidden">
        <div className="p-6">
          <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xs font-mono text-orange-400">{ticket.ticket_number}</span>
                <StatusBadge status={ticket.status} />
                <PriorityBadge priority={ticket.priority} />
              </div>
              <h1 className="text-xl font-bold text-white mb-2">{ticket.subject}</h1>
              {ticket.description && (
                <p className="text-sm text-zinc-400 leading-relaxed">{ticket.description}</p>
              )}
              {ticket.tags.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {ticket.tags.map((tag) => (
                    <span key={tag} className="text-[10px] px-2 py-0.5 rounded bg-white/[0.05] text-zinc-500 border border-white/[0.04]">
                      {tag}
                    </span>
                  ))}
                </div>
              )}
            </div>

            {/* Action Buttons */}
            <div className="flex flex-wrap items-center gap-2 shrink-0">
              {!isResolvedOrClosed && (
                <button
                  onClick={handleResolve}
                  className="inline-flex items-center gap-1.5 text-xs font-medium px-4 py-2 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/20 transition-colors"
                >
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
                  </svg>
                  Resolve
                </button>
              )}
              {ticket.status !== 'awaiting_human' && !isResolvedOrClosed && (
                <button
                  onClick={handleEscalate}
                  className="inline-flex items-center gap-1.5 text-xs font-medium px-4 py-2 rounded-lg bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500/20 transition-colors"
                >
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0 0 13.5 3h-6a2.25 2.25 0 0 0-2.25 2.25v13.5A2.25 2.25 0 0 0 7.5 21h6a2.25 2.25 0 0 0 2.25-2.25V15m3 0 3-3m0 0-3-3m3 3H9" />
                  </svg>
                  Escalate
                </button>
              )}

              {/* Change Priority dropdown */}
              <div ref={priorityRef} className="relative">
                <button
                  onClick={() => setPriorityDropdownOpen(!priorityDropdownOpen)}
                  className="inline-flex items-center gap-1.5 text-xs font-medium px-4 py-2 rounded-lg bg-white/[0.04] text-zinc-300 border border-white/[0.06] hover:bg-white/[0.08] transition-colors"
                >
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3 4.5h14.25M3 9h9.75M3 13.5h5.25m5.25-.75L17.25 9m0 0L21 12.75M17.25 9v12" />
                  </svg>
                  Change Priority
                </button>
                {priorityDropdownOpen && (
                  <motion.div
                    initial={{ opacity: 0, y: -4 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -4 }}
                    className="absolute top-full right-0 mt-1 w-44 bg-[#1A1A1A] border border-white/[0.06] rounded-lg shadow-xl z-20 py-1 overflow-hidden"
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
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Content: Info Sidebar + Messages ────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Info Sidebar */}
        <div className="lg:col-span-1 space-y-4">
          {/* Customer Card */}
          <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-5">
            <h3 className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-3">Customer</h3>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-gradient-to-br from-orange-500/20 to-amber-500/20 border border-orange-500/20 flex items-center justify-center text-sm font-semibold text-orange-300">
                {ticket.customer_name.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase()}
              </div>
              <div className="min-w-0">
                <p className="text-sm font-medium text-white truncate">{ticket.customer_name}</p>
                <p className="text-xs text-zinc-500 truncate">{ticket.customer_email}</p>
              </div>
            </div>
          </div>

          {/* Details Card */}
          <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-5">
            <h3 className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-3">Details</h3>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs text-zinc-500">Category</span>
                <span className="text-xs text-zinc-300">{CATEGORY_LABELS[ticket.category]}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-zinc-500">Channel</span>
                <span className="text-xs text-zinc-300">{CHANNEL_LABELS[ticket.channel]}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-zinc-500">Variant</span>
                <span className="text-xs text-zinc-300">
                  {ticket.assigned_variant ? VARIANT_LABELS[ticket.assigned_variant] : '—'}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-zinc-500">Assigned Agent</span>
                <span className="text-xs text-zinc-300">{ticket.assigned_agent ?? '—'}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-zinc-500">AI Confidence</span>
                <span className="text-xs text-zinc-300">
                  {ticket.ai_confidence != null ? `${ticket.ai_confidence}%` : '—'}
                </span>
              </div>
            </div>
          </div>

          {/* Dates Card */}
          <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-5">
            <h3 className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-3">Timeline</h3>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs text-zinc-500">Created</span>
                <span className="text-xs text-zinc-300 tabular-nums">{formatDate(ticket.created_at)}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-zinc-500">Updated</span>
                <span className="text-xs text-zinc-300 tabular-nums">{formatDate(ticket.updated_at)}</span>
              </div>
              {ticket.resolved_at && (
                <div className="flex items-center justify-between">
                  <span className="text-xs text-zinc-500">Resolved</span>
                  <span className="text-xs text-emerald-400 tabular-nums">{formatDate(ticket.resolved_at)}</span>
                </div>
              )}
              {ticket.resolution_time_hours != null && (
                <div className="flex items-center justify-between">
                  <span className="text-xs text-zinc-500">Resolution Time</span>
                  <span className="text-xs text-zinc-300 tabular-nums">{ticket.resolution_time_hours}h</span>
                </div>
              )}
              {ticket.first_response_at && (
                <div className="flex items-center justify-between">
                  <span className="text-xs text-zinc-500">First Response</span>
                  <span className="text-xs text-zinc-300 tabular-nums">{formatRelativeDate(ticket.first_response_at)}</span>
                </div>
              )}
            </div>
          </div>

          {/* Cost Card */}
          <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-5">
            <h3 className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-3">Cost</h3>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs text-zinc-500">Ticket Cost</span>
                <span className="text-xs text-zinc-300">
                  {ticket.cost_per_ticket != null ? `$${ticket.cost_per_ticket.toFixed(3)}` : '—'}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-zinc-500">Savings vs Human</span>
                <span className="text-xs text-emerald-400">
                  {ticket.savings_per_ticket != null ? `$${ticket.savings_per_ticket.toFixed(2)}` : '—'}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Message Thread */}
        <div className="lg:col-span-2">
          <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] overflow-hidden flex flex-col">
            {/* Messages Header */}
            <div className="px-5 py-3 border-b border-white/[0.06] flex items-center justify-between">
              <h3 className="text-xs font-medium text-zinc-500 uppercase tracking-wider">
                Messages ({ticket.messages.length})
              </h3>
              <span className="text-[10px] text-zinc-600">
                {ticket.messages.length > 0 ? `Last message ${formatRelativeDate(ticket.messages[ticket.messages.length - 1].created_at)}` : ''}
              </span>
            </div>

            {/* Messages List */}
            <div className="flex-1 overflow-y-auto max-h-[calc(100vh-420px)] min-h-[300px] px-5 py-4 space-y-4">
              {ticket.messages.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  <div className="w-12 h-12 rounded-xl bg-white/[0.03] border border-white/[0.06] flex items-center justify-center mb-3">
                    <svg className="w-5 h-5 text-zinc-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H8.25m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H12m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 0 1-2.555-.337A5.972 5.972 0 0 1 5.41 20.97a5.969 5.969 0 0 1-.474-.065 4.48 4.48 0 0 0 .978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25Z" />
                    </svg>
                  </div>
                  <p className="text-xs text-zinc-600">No messages yet</p>
                </div>
              ) : (
                ticket.messages.map((msg) => {
                  const isCustomer = msg.sender === 'customer';
                  const isAI = msg.sender === 'ai_agent';
                  const isSystem = msg.sender === 'system';
                  const isHumanAgent = msg.sender === 'human_agent';

                  return (
                    <div key={msg.id} className={`flex ${isCustomer ? 'justify-start' : 'justify-end'}`}>
                      <div
                        className={`max-w-[80%] rounded-xl px-4 py-3 ${
                          isCustomer
                            ? 'bg-white/[0.04] border border-white/[0.06] rounded-bl-sm'
                            : isSystem
                            ? 'bg-amber-500/5 border border-amber-500/10 rounded-br-sm'
                            : isHumanAgent
                            ? 'bg-blue-500/10 border border-blue-500/15 rounded-br-sm'
                            : 'bg-orange-500/10 border border-orange-500/15 rounded-br-sm'
                        }`}
                      >
                        <div className="flex items-center gap-2 mb-1.5">
                          <span
                            className={`text-[11px] font-semibold ${
                              isCustomer
                                ? 'text-zinc-400'
                                : isSystem
                                ? 'text-amber-400'
                                : isHumanAgent
                                ? 'text-blue-400'
                                : 'text-orange-400'
                            }`}
                          >
                            {msg.sender_name}
                          </span>
                          {isAI && msg.variant && (
                            <span className="text-[9px] px-1.5 py-0.5 rounded bg-orange-500/10 text-orange-300 border border-orange-500/10">
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
            {!isResolvedOrClosed && (
              <div className="px-5 py-4 border-t border-white/[0.06]">
                <div className="flex items-end gap-3">
                  <textarea
                    value={replyText}
                    onChange={(e) => setReplyText(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        handleSendReply();
                      }
                    }}
                    placeholder="Type a reply as PARWA AI..."
                    rows={3}
                    className="flex-1 bg-[#0A0A0A] border border-white/[0.06] rounded-lg px-4 py-3 text-xs text-white placeholder:text-zinc-600 focus:outline-none focus:border-orange-500/40 transition-colors resize-none"
                  />
                  <button
                    onClick={handleSendReply}
                    disabled={!replyText.trim()}
                    className="h-10 w-10 flex items-center justify-center rounded-lg bg-orange-500 text-white hover:bg-orange-600 transition-colors disabled:opacity-30 disabled:cursor-not-allowed shrink-0"
                    aria-label="Send reply"
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6 12 3.269 3.125A59.769 59.769 0 0 1 21.485 12 59.768 59.768 0 0 1 3.27 20.875L5.999 12Zm0 0h7.5" />
                    </svg>
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </motion.div>
  );
}
