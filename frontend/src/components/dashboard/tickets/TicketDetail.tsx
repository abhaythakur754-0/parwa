'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import { ticketsApi } from '@/lib/tickets-api';
import type { Ticket, TicketMessage, InternalNote, TimelineEntry, BulkActionType } from '@/types/ticket';
import { statusConfig, priorityConfig, timeAgo } from './TicketRow';
import ConversationView from './ConversationView';
import TicketMetadata from './TicketMetadata';
import CustomerInfoCard from './CustomerInfoCard';
import InternalNotes from './InternalNotes';
import TimelineView from './TimelineView';
import ReplyBox from './ReplyBox';
import AssignmentSuggestions from './AssignmentSuggestions';
import toast from 'react-hot-toast';

interface TicketDetailProps {
  ticketId: string;
}

// ── Tabs ────────────────────────────────────────────────────────────────

type DetailTab = 'conversation' | 'notes' | 'timeline';

const tabs: { id: DetailTab; label: string }[] = [
  { id: 'conversation', label: '💬 Conversation' },
  { id: 'notes', label: '📌 Notes' },
  { id: 'timeline', label: '🕐 Timeline' },
];

export default function TicketDetail({ ticketId }: TicketDetailProps) {
  const router = useRouter();

  // State
  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [messages, setMessages] = useState<TicketMessage[]>([]);
  const [notes, setNotes] = useState<InternalNote[]>([]);
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<DetailTab>('conversation');

  // Fetch detail
  useEffect(() => {
    async function load() {
      try {
        setIsLoading(true);
        const data = await ticketsApi.fetchTicketDetail(ticketId);
        if (data) {
          setTicket(data.ticket);
          setMessages(data.messages);
          setNotes(data.notes);
          setTimeline(data.timeline);
        }
      } catch {
        toast.error('Failed to load ticket');
      } finally {
        setIsLoading(false);
      }
    }
    load();
  }, [ticketId]);

  // Action handlers
  const handleEscalate = useCallback(async () => {
    if (!ticket) return;
    try {
      const updated = await ticketsApi.escalateTicket(ticket.id);
      setTicket(updated);
      toast.success('Ticket escalated');
    } catch {
      toast.error('Failed to escalate');
    }
  }, [ticket]);

  const handleReply = useCallback(async (content: string) => {
    const msg = await ticketsApi.sendReply(ticketId, content);
    setMessages((prev) => [...prev, msg]);
  }, [ticketId]);

  const handleAddNote = useCallback(async (content: string, isPinned: boolean) => {
    const note = await ticketsApi.addInternalNote(ticketId, content, isPinned);
    setNotes((prev) => [note, ...prev]);
  }, [ticketId]);

  const handleAssignAgent = useCallback(async (agentId: string) => {
    if (!ticket) return;
    try {
      const updated = await ticketsApi.assignTicket(ticket.id, agentId);
      setTicket(updated);
      toast.success('Agent assigned successfully');
    } catch {
      toast.error('Failed to assign agent');
    }
  }, [ticket]);

  // Loading state
  if (isLoading) {
    return (
      <div className="space-y-4">
        {/* Skeleton header */}
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-white/[0.04] animate-pulse" />
          <div className="w-32 h-5 rounded bg-white/[0.04] animate-pulse" />
          <div className="w-20 h-5 rounded bg-white/[0.04] animate-pulse" />
        </div>
        <div className="h-4 w-96 rounded bg-white/[0.04] animate-pulse" />
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 h-96 rounded-xl bg-[#1A1A1A] border border-white/[0.06] animate-pulse" />
          <div className="h-96 rounded-xl bg-[#1A1A1A] border border-white/[0.06] animate-pulse" />
        </div>
      </div>
    );
  }

  if (!ticket) {
    return (
      <div className="text-center py-16">
        <p className="text-zinc-500 text-sm">Ticket not found</p>
        <button onClick={() => router.push('/dashboard/tickets')} className="mt-2 text-orange-400 text-sm hover:text-orange-300">
          ← Back to tickets
        </button>
      </div>
    );
  }

  const status = statusConfig[ticket.status];
  const priority = priorityConfig[ticket.priority];

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          {/* Breadcrumb */}
          <button
            onClick={() => router.push('/dashboard/tickets')}
            className="flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-300 transition-colors mb-2"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5 8.25 12l7.5-7.5" />
            </svg>
            Back to Tickets
          </button>

          {/* Title row */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-mono text-orange-400">{ticket.ticket_number}</span>
            <span className={cn('inline-flex px-2 py-0.5 rounded-md text-[10px] font-bold border', status.className)}>
              {status.label}
            </span>
            <div className="flex items-center gap-1">
              <span className={cn('w-2 h-2 rounded-full', priority.dotClass)} />
              <span className="text-[10px] text-zinc-500">{priority.label}</span>
            </div>
            {ticket.is_ai_resolved && (
              <span className="px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-400 text-[10px] font-bold border border-emerald-500/20">
                AI Resolved
              </span>
            )}
            {ticket.has_attachments && (
              <span className="text-xs text-zinc-500" title="Has attachments">📎</span>
            )}
          </div>

          <h1 className="text-lg font-bold text-white mt-1">{ticket.subject}</h1>
          <p className="text-xs text-zinc-500 mt-0.5">
            Created {timeAgo(ticket.created_at)} · {ticket.message_count} messages · via {ticket.channel}
          </p>
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={handleEscalate}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-red-500/10 text-red-400 text-xs font-medium border border-red-500/20 hover:bg-red-500/20 transition-all"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
            </svg>
            Escalate
          </button>
          <button
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-blue-500/10 text-blue-400 text-xs font-medium border border-blue-500/20 hover:bg-blue-500/20 transition-all"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 21 3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" />
            </svg>
            Reassign
          </button>
          <button
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-white/[0.04] text-zinc-400 text-xs font-medium border border-white/[0.08] hover:bg-white/[0.08] transition-all"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5m-13.5-9L12 3m0 0 4.5 4.5M12 3v13.5" />
            </svg>
            Export
          </button>
        </div>
      </div>

      {/* Main content grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Left: Conversation + Reply */}
        <div className="lg:col-span-2 space-y-4">
          {/* Tab bar */}
          <div className="flex items-center gap-1 px-1">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  'px-3 py-2 rounded-lg text-xs font-medium transition-all',
                  activeTab === tab.id
                    ? 'bg-white/[0.06] text-zinc-200 border border-white/[0.08]'
                    : 'text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.03]'
                )}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Tab content */}
          <div className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] min-h-[400px] max-h-[600px] flex flex-col">
            {activeTab === 'conversation' && (
              <ConversationView messages={messages} className="p-4 flex-1" />
            )}
            {activeTab === 'notes' && (
              <div className="p-4 flex-1">
                <InternalNotes notes={notes} onAddNote={handleAddNote} />
              </div>
            )}
            {activeTab === 'timeline' && (
              <div className="p-4 flex-1">
                <TimelineView entries={timeline} />
              </div>
            )}
          </div>

          {/* Reply Box */}
          <ReplyBox ticketId={ticket.id} onSend={handleReply} />
        </div>

        {/* Right: Metadata sidebar */}
        <div className="space-y-4">
          {/* AI Assignment Suggestions */}
          {!ticket.assigned_to && ticket.status !== 'closed' && ticket.status !== 'resolved' && (
            <AssignmentSuggestions
              ticketId={ticketId}
              onSelectAgent={handleAssignAgent}
            />
          )}
          <CustomerInfoCard customer={ticket.customer} />
          <TicketMetadata ticket={ticket} />
        </div>
      </div>
    </div>
  );
}
