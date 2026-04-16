'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  ticketsApi,
  type TicketResponse,
  type MessageResponse,
  type NoteResponse,
  type TimelineEvent,
  type AttachmentResponse,
  type TicketStatus,
} from '@/lib/tickets-api';
import { getErrorMessage } from '@/lib/api';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Separator } from '@/components/ui/separator';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Textarea } from '@/components/ui/textarea';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import {
  Tabs, TabsContent, TabsList, TabsTrigger,
} from '@/components/ui/tabs';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '@/components/ui/dialog';
import {
  Tooltip, TooltipContent, TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  Popover, PopoverTrigger, PopoverContent,
} from '@/components/ui/popover';

// ── Constants ───────────────────────────────────────────────────────────

const STATUS_OPTIONS = [
  { value: 'open', label: 'Open' },
  { value: 'assigned', label: 'Assigned' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'awaiting_client', label: 'Awaiting Client' },
  { value: 'awaiting_human', label: 'Awaiting Human' },
  { value: 'resolved', label: 'Resolved' },
  { value: 'closed', label: 'Closed' },
  { value: 'frozen', label: 'Frozen' },
];

const PRIORITY_OPTIONS = [
  { value: 'critical', label: 'Critical' },
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
];

const GSD_STAGES = ['NEW', 'GREETING', 'DIAGNOSIS', 'RESOLUTION', 'CLOSED'];

const STATUS_STYLES: Record<string, string> = {
  open: 'bg-zinc-500/15 text-zinc-300 border-zinc-500/20',
  assigned: 'bg-blue-500/15 text-blue-400 border-blue-500/20',
  in_progress: 'bg-blue-500/15 text-blue-400 border-blue-500/20',
  awaiting_client: 'bg-amber-500/15 text-amber-400 border-amber-500/20',
  awaiting_human: 'bg-orange-500/15 text-orange-400 border-orange-500/20',
  resolved: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20',
  reopened: 'bg-violet-500/15 text-violet-400 border-violet-500/20',
  closed: 'bg-zinc-600/15 text-zinc-500 border-zinc-600/20',
  frozen: 'bg-cyan-500/15 text-cyan-400 border-cyan-500/20',
  queued: 'bg-zinc-500/10 text-zinc-400 border-zinc-500/15',
  stale: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/20',
};

const PRIORITY_STYLES: Record<string, string> = {
  critical: 'bg-red-500/15 text-red-400 border-red-500/20',
  high: 'bg-orange-500/15 text-orange-400 border-orange-500/20',
  medium: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/20',
  low: 'bg-zinc-600/15 text-zinc-400 border-zinc-600/20',
};

// ── Helpers ─────────────────────────────────────────────────────────────

function formatStatus(status: string): string {
  return status.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function formatTime(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' });
}

function formatDateTime(dateStr: string): string {
  return `${formatDate(dateStr)} ${formatTime(dateStr)}`;
}

function confidenceColor(c: number | null): string {
  if (c === null) return 'text-zinc-600';
  if (c >= 75) return 'text-emerald-400';
  if (c >= 50) return 'text-amber-400';
  return 'text-red-400';
}

function confidenceBarColor(c: number | null): string {
  if (c === null) return 'bg-zinc-700';
  if (c >= 75) return 'bg-emerald-500';
  if (c >= 50) return 'bg-amber-500';
  return 'bg-red-500';
}

function getGSDStage(status: string): number {
  const map: Record<string, number> = {
    open: 0, queued: 0, stale: 0,
    assigned: 1, in_progress: 1,
    awaiting_client: 2, awaiting_human: 2,
    resolved: 3, reopened: 2,
    closed: 4, frozen: 3,
  };
  return map[status] ?? 0;
}

function getFileIcon(fileType: string): string {
  if (fileType.startsWith('image/')) return '🖼';
  if (fileType.includes('pdf')) return '📄';
  if (fileType.includes('csv') || fileType.includes('excel') || fileType.includes('spreadsheet')) return '📊';
  if (fileType.includes('json')) return '📋';
  return '📎';
}

// ── Inline SVG Icons ────────────────────────────────────────────────────

const ArrowLeftIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5 3 12m0 0 7.5-7.5M3 12h18" />
  </svg>
);

const SendIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M6 12 3.269 3.125A59.769 59.769 0 0 1 21.485 12 59.768 59.768 0 0 1 3.27 20.875L5.999 12Zm0 0h7.5" />
  </svg>
);

const PinIcon = ({ filled }: { filled?: boolean }) => (
  <svg className={`w-3.5 h-3.5 ${filled ? 'text-[#FF7F11]' : 'text-zinc-500'}`} fill={filled ? 'currentColor' : 'none'} viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M15 10.5a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
    <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1 1 15 0Z" />
  </svg>
);

const TrashIcon = () => (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0" />
  </svg>
);

const DownloadIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3" />
  </svg>
);

const PlusIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
  </svg>
);

// ── GSD State Indicator (T13) ───────────────────────────────────────────

function GSDStateIndicator({ status }: { status: string }) {
  const currentStage = getGSDStage(status);

  return (
    <div className="w-full">
      <div className="flex items-center justify-between mb-1.5">
        {GSD_STAGES.map((stage, i) => (
          <div key={stage} className="flex items-center flex-1">
            <div className="flex flex-col items-center flex-1">
              <div className={`
                w-6 h-6 rounded-full flex items-center justify-center text-[9px] font-bold transition-all
                ${i < currentStage
                  ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                  : i === currentStage
                    ? 'bg-[#FF7F11]/20 text-[#FF7F11] border border-[#FF7F11]/30 ring-2 ring-[#FF7F11]/10'
                    : 'bg-zinc-800 text-zinc-600 border border-zinc-700'
                }
              `}>
                {i < currentStage ? (
                  <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
                  </svg>
                ) : (
                  i + 1
                )}
              </div>
              <span className={`text-[9px] mt-1 text-center ${i <= currentStage ? 'text-zinc-400' : 'text-zinc-600'}`}>
                {stage}
              </span>
            </div>
            {i < GSD_STAGES.length - 1 && (
              <div className={`h-[2px] flex-1 mx-1 rounded -mt-3 ${
                i < currentStage ? 'bg-emerald-500/30' : 'bg-zinc-800'
              }`} />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Sentiment Indicator (T12) ───────────────────────────────────────────

function SentimentBadge({ sentiment }: { sentiment: string | null }) {
  if (!sentiment) return <span className="text-xs text-zinc-600">&mdash;</span>;
  const s = sentiment.toLowerCase();
  const styles: Record<string, string> = {
    positive: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20',
    negative: 'bg-red-500/15 text-red-400 border-red-500/20',
    neutral: 'bg-zinc-600/15 text-zinc-400 border-zinc-600/20',
    mixed: 'bg-amber-500/15 text-amber-400 border-amber-500/20',
  };
  const icons: Record<string, string> = { positive: '😊', negative: '😟', neutral: '😐', mixed: '🤔' };
  return (
    <Badge variant="outline" className={`text-xs ${styles[s] || styles.neutral}`}>
      {icons[s] || '😐'} {s}
    </Badge>
  );
}

// ── Main Component ──────────────────────────────────────────────────────

export default function TicketDetailPage() {
  const params = useParams();
  const router = useRouter();
  const ticketId = params.id as string;

  // Data state
  const [ticket, setTicket] = useState<TicketResponse | null>(null);
  const [messages, setMessages] = useState<MessageResponse[]>([]);
  const [notes, setNotes] = useState<NoteResponse[]>([]);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [attachments, setAttachments] = useState<AttachmentResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // UI state
  const [replyText, setReplyText] = useState('');
  const [sendingReply, setSendingReply] = useState(false);
  const [noteText, setNoteText] = useState('');
  const [addingNote, setAddingNote] = useState(false);
  const [showNoteForm, setShowNoteForm] = useState(false);
  const [escalateOpen, setEscalateOpen] = useState(false);
  const [escalateReason, setEscalateReason] = useState('');
  const [escalating, setEscalating] = useState(false);

  // Reassign state (Fix 8)
  const [reassignOpen, setReassignOpen] = useState(false);
  const [reassignAgentId, setReassignAgentId] = useState('');
  const [reassigning, setReassigning] = useState(false);

  // Edit note state (Fix 10)
  const [editingNoteId, setEditingNoteId] = useState<string | null>(null);
  const [editNoteText, setEditNoteText] = useState('');
  const [savingNote, setSavingNote] = useState(false);

  // Messages ref for auto-scroll
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // ── Fetch Data ─────────────────────────────────────────────────────

  const fetchTicket = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [ticketData, msgsData, notesData, timelineData, attachData] = await Promise.all([
        ticketsApi.get(ticketId),
        ticketsApi.getMessages(ticketId, { page_size: 100, include_internal: true }),
        ticketsApi.getNotes(ticketId, { page_size: 50 }),
        ticketsApi.getTimeline(ticketId, { page_size: 100 }),
        ticketsApi.getAttachments(ticketId).catch(() => ({ attachments: [], total: 0 })),
      ]);
      setTicket(ticketData);
      setMessages(msgsData.messages || []);
      setNotes(notesData.notes || []);
      setTimeline(timelineData.events || []);
      setAttachments(attachData.attachments || []);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [ticketId]);

  useEffect(() => {
    fetchTicket();
  }, [fetchTicket]);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // ── Send Reply (T20) ───────────────────────────────────────────────

  const handleSendReply = async () => {
    if (!replyText.trim()) return;
    setSendingReply(true);
    try {
      const newMsg = await ticketsApi.createMessage(ticketId, {
        role: 'agent',
        content: replyText.trim(),
        channel: ticket?.channel || 'chat',
      });
      setMessages(prev => [...prev, newMsg]);
      setReplyText('');
    } catch (err) {
      console.error('Failed to send reply:', err);
    } finally {
      setSendingReply(false);
    }
  };

  // ── Add Note (T17) ─────────────────────────────────────────────────

  const handleAddNote = async () => {
    if (!noteText.trim()) return;
    setAddingNote(true);
    try {
      const newNote = await ticketsApi.createNote(ticketId, {
        content: noteText.trim(),
      });
      setNotes(prev => [newNote, ...prev]);
      setNoteText('');
      setShowNoteForm(false);
    } catch (err) {
      console.error('Failed to add note:', err);
    } finally {
      setAddingNote(false);
    }
  };

  // ── Toggle Pin Note ───────────────────────────────────────────────

  const handleTogglePin = async (noteId: string) => {
    try {
      const updated = await ticketsApi.togglePinNote(ticketId, noteId);
      setNotes(prev => prev.map(n => n.id === noteId ? updated : n));
    } catch (err) {
      console.error('Failed to toggle pin:', err);
    }
  };

  // ── Delete Note ───────────────────────────────────────────────────

  const handleDeleteNote = async (noteId: string) => {
    try {
      await ticketsApi.deleteNote(ticketId, noteId);
      setNotes(prev => prev.filter(n => n.id !== noteId));
    } catch (err) {
      console.error('Failed to delete note:', err);
    }
  };

  // ── Reassign (Fix 8) ─────────────────────────────────────────

  const handleReassign = async () => {
    if (!reassignAgentId.trim()) return;
    setReassigning(true);
    try {
      const updated = await ticketsApi.assign(ticketId, {
        assignee_id: reassignAgentId.trim(),
        assignee_type: 'human',
      });
      setTicket(updated);
      setReassignOpen(false);
      setReassignAgentId('');
    } catch (err) {
      console.error('Failed to reassign:', err);
    } finally {
      setReassigning(false);
    }
  };

  // ── Edit Note (Fix 10) ────────────────────────────────────────────

  const handleStartEditNote = (note: NoteResponse) => {
    setEditingNoteId(note.id);
    setEditNoteText(note.content);
  };

  const handleCancelEditNote = () => {
    setEditingNoteId(null);
    setEditNoteText('');
  };

  const handleSaveEditNote = async (noteId: string) => {
    if (!editNoteText.trim()) return;
    setSavingNote(true);
    try {
      const updated = await ticketsApi.updateNote(ticketId, noteId, { content: editNoteText.trim() });
      setNotes(prev => prev.map(n => n.id === noteId ? updated : n));
      setEditingNoteId(null);
      setEditNoteText('');
    } catch (err) {
      console.error('Failed to update note:', err);
    } finally {
      setSavingNote(false);
    }
  };

  // ── Export Conversation CSV (Fix 9) ────────────────────────────────

  const handleExportConversation = () => {
    const csvContent = [
      'Role,Content,Confidence,Created At',
      ...messages.map(m =>
        `"${m.role}","${(m.content || '').replace(/"/g, '"")}","${m.ai_confidence ?? ''}","${m.created_at}"`
      ),
    ].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `ticket-${ticketId.slice(0, 8)}-conversation.csv`;
    link.click();
    URL.revokeObjectURL(link.href);
  };

  // ── Escalate (T16) ────────────────────────────────────────────────

  const handleEscalate = async () => {
    setEscalating(true);
    try {
      await ticketsApi.updateStatus(ticketId, {
        status: 'awaiting_human',
        reason: escalateReason || 'Escalated by agent',
      });
      setEscalateOpen(false);
      setEscalateReason('');
      fetchTicket();
    } catch (err) {
      console.error('Failed to escalate:', err);
    } finally {
      setEscalating(false);
    }
  };

  // ── Change Status (T16) ───────────────────────────────────────────

  const handleChangeStatus = async (newStatus: string) => {
    try {
      const updated = await ticketsApi.updateStatus(ticketId, {
        status: newStatus as TicketStatus,
      });
      setTicket(updated);
    } catch (err) {
      console.error('Failed to change status:', err);
    }
  };

  // ── Timeline event icon ───────────────────────────────────────────

  const timelineEventIcon = (type: string): { icon: React.ReactNode; color: string } => {
    const icons: Record<string, { icon: React.ReactNode; color: string }> = {
      status_change: {
        icon: <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M7.5 21 3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" /></svg>,
        color: 'text-blue-400 bg-blue-500/15',
      },
      assigned: {
        icon: <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M15 19.128a9.38 9.38 0 0 0 2.625.372 9.337 9.337 0 0 0 4.121-.952 4.125 4.125 0 0 0-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 0 1 8.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0 1 11.964-3.07M12 6.375a3.375 3.375 0 1 1-6.75 0 3.375 3.375 0 0 1 6.75 0Z" /></svg>,
        color: 'text-purple-400 bg-purple-500/15',
      },
      message: {
        icon: <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H8.25m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H12m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 0 1-2.555-.337A5.972 5.972 0 0 1 5.41 20.97a5.969 5.969 0 0 1-.474-.065 4.48 4.48 0 0 0 .978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25Z" /></svg>,
        color: 'text-emerald-400 bg-emerald-500/15',
      },
      note: {
        icon: <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" /></svg>,
        color: 'text-amber-400 bg-amber-500/15',
      },
      attachment: {
        icon: <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="m18.375 12.739-7.693 7.693a4.5 4.5 0 0 1-6.364-6.364l10.94-10.94A3 3 0 1 1 19.5 7.372L8.552 18.32m.009-.01-.01.01m5.699-9.941-7.81 7.81a1.5 1.5 0 0 0 2.112 2.13" /></svg>,
        color: 'text-cyan-400 bg-cyan-500/15',
      },
      sla_warning: {
        icon: <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" /></svg>,
        color: 'text-amber-400 bg-amber-500/15',
      },
      sla_breached: {
        icon: <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" /></svg>,
        color: 'text-red-400 bg-red-500/15',
      },
    };
    return icons[type] || { icon: <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" /></svg>, color: 'text-zinc-400 bg-zinc-500/15' };
  };

  const timelineEventDescription = (event: TimelineEvent): string => {
    switch (event.type) {
      case 'status_change':
        return `Status changed from ${formatStatus(event.old_value || 'unknown')} to ${formatStatus(event.new_value || 'unknown')}`;
      case 'assigned':
        return `Assigned to ${event.new_value || 'unknown agent'}`;
      case 'message':
        return `New ${event.metadata?.role || ''} message`;
      case 'note':
        return 'Internal note added';
      case 'attachment':
        return `Attachment ${event.new_value || ''} added`;
      case 'sla_warning':
        return 'SLA warning: approaching deadline';
      case 'sla_breached':
        return 'SLA breached!';
      default:
        return event.type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    }
  };

  // ── Loading State ──────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0D0D0D] p-4 md:p-6">
        <div className="flex items-center gap-3 mb-6">
          <Skeleton className="h-8 w-8 rounded" />
          <Skeleton className="h-6 w-32" />
        </div>
        <div className="flex flex-col lg:flex-row gap-4">
          <div className="flex-1">
            <Skeleton className="h-20 w-full rounded-xl mb-4" />
            <Skeleton className="h-96 w-full rounded-xl" />
          </div>
          <div className="w-full lg:w-80 space-y-4">
            <Skeleton className="h-64 rounded-xl" />
            <Skeleton className="h-48 rounded-xl" />
          </div>
        </div>
      </div>
    );
  }

  if (error || !ticket) {
    return (
      <div className="min-h-screen bg-[#0D0D0D] p-4 md:p-6">
        <Link href="/dashboard/tickets" className="inline-flex items-center gap-1.5 text-sm text-zinc-500 hover:text-zinc-300 mb-6 transition-colors">
          <ArrowLeftIcon /> Back to Tickets
        </Link>
        <div className="flex flex-col items-center justify-center py-20 gap-4">
          <div className="w-16 h-16 rounded-2xl bg-red-500/10 flex items-center justify-center">
            <svg className="w-8 h-8 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 3.75h.008v.008H12v-.008Z" />
            </svg>
          </div>
          <p className="text-sm text-red-400">{error || 'Ticket not found'}</p>
          <Link href="/dashboard/tickets" className="text-sm text-[#FF7F11] hover:underline">
            Return to tickets list
          </Link>
        </div>
      </div>
    );
  }

  // ── Computed values ────────────────────────────────────────────────

  const metadata = ticket.metadata_json || {};
  const sentiment = metadata.sentiment as string | null;
  const language = metadata.language as string | null;
  const aiTechnique = metadata.ai_technique as string | null;
  const avgConfidence = (() => {
    const aiMsgs = messages.filter(m => m.role === 'ai' && m.ai_confidence != null);
    if (aiMsgs.length === 0) return null;
    return aiMsgs.reduce((s, m) => s + (m.ai_confidence || 0), 0) / aiMsgs.length;
  })();

  const sortedNotes = [...notes].sort((a, b) => {
    if (a.is_pinned !== b.is_pinned) return a.is_pinned ? -1 : 1;
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
  });

  // ── Render ─────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-[#0D0D0D]">
      {/* Back Link */}
      <div className="sticky top-0 z-20 bg-[#0D0D0D]/80 backdrop-blur-sm border-b border-white/[0.04]">
        <div className="max-w-screen-2xl mx-auto px-4 md:px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link href="/dashboard/tickets" className="inline-flex items-center gap-1.5 text-sm text-zinc-500 hover:text-zinc-300 transition-colors">
              <ArrowLeftIcon /> Tickets
            </Link>
            <Separator orientation="vertical" className="h-4 bg-white/[0.06]" />
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-[#FF7F11]">#{ticket.id.slice(0, 8)}</span>
              <Badge variant="outline" className={`text-[10px] font-medium ${STATUS_STYLES[ticket.status] || ''}`}>
                {formatStatus(ticket.status)}
              </Badge>
              <Badge variant="outline" className={`text-[10px] font-semibold uppercase ${PRIORITY_STYLES[ticket.priority] || ''}`}>
                {ticket.priority}
              </Badge>
            </div>
          </div>

          {/* Action Buttons (T16) */}
          <div className="flex items-center gap-2">
            <Select value={ticket.status} onValueChange={handleChangeStatus}>
              <SelectTrigger size="sm" className="w-[130px] bg-[#1A1A1A] border-white/[0.06] text-zinc-300 text-xs h-7">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-[#1A1A1A] border-white/[0.06]">
                {STATUS_OPTIONS.map(opt => (
                  <SelectItem key={opt.value} value={opt.value} className="text-zinc-300">{opt.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button
              size="sm"
              variant="ghost"
              className="text-zinc-400 hover:text-orange-400 hover:bg-orange-500/10 text-xs h-7"
              onClick={() => setEscalateOpen(true)}
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v6m3-3H9m12 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
              </svg>
              Escalate
            </Button>
            {/* Reassign (Fix 8) */}
            <Popover open={reassignOpen} onOpenChange={setReassignOpen}>
              <PopoverTrigger asChild>
                <Button
                  size="sm"
                  variant="ghost"
                  className="text-zinc-400 hover:text-purple-400 hover:bg-purple-500/10 text-xs h-7"
                >
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15 19.128a9.38 9.38 0 0 0 2.625.372 9.337 9.337 0 0 0 4.121-.952 4.125 4.125 0 0 0-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 0 1 8.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0 1 11.964-3.07M12 6.375a3.375 3.375 0 1 1-6.75 0 3.375 3.375 0 0 1 6.75 0Z" />
                  </svg>
                  Reassign
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-[260px] bg-[#1A1A1A] border-white/[0.06] p-3" side="bottom" align="end">
                <div className="space-y-2">
                  <label className="text-xs font-medium text-zinc-400">Agent ID</label>
                  <input
                    type="text"
                    placeholder="Enter Agent ID..."
                    value={reassignAgentId}
                    onChange={(e) => setReassignAgentId(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') handleReassign(); }}
                    className="w-full px-2.5 py-1.5 bg-[#111111] border border-white/[0.06] rounded-md text-xs text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-[#FF7F11]/50"
                    autoFocus
                  />
                  <Button
                    size="sm"
                    className="w-full bg-[#FF7F11] text-white hover:bg-[#FF7F11]/90 text-xs h-7"
                    disabled={!reassignAgentId.trim() || reassigning}
                    onClick={handleReassign}
                  >
                    {reassigning ? 'Reassigning...' : 'Reassign'}
                  </Button>
                </div>
              </PopoverContent>
            </Popover>
            {/* Export Conversation (Fix 9) */}
            <Button
              size="sm"
              variant="ghost"
              className="text-zinc-400 hover:text-emerald-400 hover:bg-emerald-500/10 text-xs h-7"
              onClick={handleExportConversation}
            >
              <DownloadIcon />
              Export
            </Button>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-screen-2xl mx-auto p-4 md:p-6 flex flex-col lg:flex-row gap-4">
        {/* Left: Conversation (T9, T17, T19, T20) */}
        <div className="flex-1 min-w-0 space-y-4">
          {/* Ticket Header */}
          <div className="bg-[#111111] border border-white/[0.06] rounded-xl p-4">
            <h1 className="text-lg font-semibold text-zinc-100 mb-1">
              {ticket.subject || '(No Subject)'}
            </h1>
            <div className="flex flex-wrap items-center gap-2 text-xs text-zinc-500">
              <span>Created {formatDateTime(ticket.created_at)}</span>
              {ticket.updated_at !== ticket.created_at && (
                <>
                  <span>&middot;</span>
                  <span>Updated {formatDateTime(ticket.updated_at)}</span>
                </>
              )}
              {ticket.reopen_count > 0 && (
                <>
                  <span>&middot;</span>
                  <span className="text-amber-400">Reopened {ticket.reopen_count}x</span>
                </>
              )}
              {ticket.sla_breached && (
                <Badge variant="outline" className="text-[10px] bg-red-500/10 text-red-400 border-red-500/20">
                  SLA Breached
                </Badge>
              )}
            </div>
            {ticket.tags && ticket.tags.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-2">
                {ticket.tags.map(tag => (
                  <span key={tag} className="text-[10px] px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-500 border border-white/[0.04]">
                    {tag}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Conversation Messages (T9) */}
          <div className="bg-[#111111] border border-white/[0.06] rounded-xl p-4">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold text-zinc-200">Conversation</h2>
              <span className="text-xs text-zinc-500">{messages.length} messages</span>
            </div>

            <div className="space-y-3 max-h-[50vh] overflow-y-auto pr-1">
              {messages.length === 0 ? (
                <div className="text-center py-12">
                  <p className="text-sm text-zinc-500">No messages in this conversation yet.</p>
                </div>
              ) : (
                messages.map((msg) => {
                  const isCustomer = msg.role === 'customer';
                  const isAi = msg.role === 'ai';
                  const isAgent = msg.role === 'agent';
                  const isSystem = msg.role === 'system';
                  const isInternal = msg.is_internal;

                  // System messages centered
                  if (isSystem) {
                    return (
                      <div key={msg.id} className="flex justify-center">
                        <div className="px-4 py-1.5 bg-zinc-800/50 rounded-full">
                          <p className="text-xs text-zinc-500 italic">{msg.content}</p>
                        </div>
                      </div>
                    );
                  }

                  // Internal notes (shown inline but styled differently)
                  if (isInternal) {
                    return (
                      <div key={msg.id} className="flex justify-center">
                        <div className="max-w-[80%] bg-amber-500/5 border border-amber-500/10 rounded-xl px-4 py-2.5">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-[10px] font-semibold text-amber-400 uppercase">Internal Note</span>
                            <span className="text-[10px] text-zinc-600">{formatTime(msg.created_at)}</span>
                          </div>
                          <p className="text-xs text-zinc-400 whitespace-pre-wrap">{msg.is_redacted ? '[REDACTED]' : msg.content}</p>
                        </div>
                      </div>
                    );
                  }

                  // Customer messages left-aligned, AI/Agent messages right-aligned
                  return (
                    <div key={msg.id} className={`flex ${isCustomer ? 'justify-start' : 'justify-end'}`}>
                      <div className="max-w-[75%]">
                        {/* Sender info */}
                        <div className="flex items-center gap-2 mb-1">
                          <span className={`text-xs font-medium ${isCustomer ? 'text-zinc-400' : 'text-[#FF7F11]'}`}>
                            {isCustomer ? 'Customer' : isAi ? 'PARWA AI' : 'Agent'}
                          </span>
                          {/* AI Confidence (T11) */}
                          {isAi && msg.ai_confidence != null && (
                            <Tooltip>
                              <TooltipTrigger>
                                <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                                  msg.ai_confidence >= 75
                                    ? 'bg-emerald-500/10 text-emerald-400'
                                    : msg.ai_confidence >= 50
                                      ? 'bg-amber-500/10 text-amber-400'
                                      : 'bg-red-500/10 text-red-400'
                                }`}>
                                  {msg.ai_confidence}%
                                </span>
                              </TooltipTrigger>
                              <TooltipContent side="top" className="bg-[#1A1A1A] text-zinc-300 border-white/[0.06] text-xs">
                                AI Confidence: {msg.ai_confidence}%
                              </TooltipContent>
                            </Tooltip>
                          )}
                          <span className="text-[10px] text-zinc-600">{formatTime(msg.created_at)}</span>
                        </div>
                        {/* Message bubble */}
                        <div className={`rounded-2xl px-4 py-2.5 ${
                          isCustomer
                            ? 'bg-zinc-800 text-zinc-200 rounded-tl-sm'
                            : 'bg-gradient-to-br from-[#FF7F11]/15 to-[#FF7F11]/5 text-zinc-100 border border-[#FF7F11]/10 rounded-tr-sm'
                        }`}>
                          <p className="text-sm whitespace-pre-wrap">
                            {msg.is_redacted ? (
                              <span className="italic text-zinc-500">[REDACTED]</span>
                            ) : (
                              msg.content
                            )}
                          </p>
                        </div>
                      </div>
                    </div>
                  );
                })
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Reply Box (T20) */}
            <div className="mt-4 pt-4 border-t border-white/[0.06]">
              <div className="flex gap-2">
                <Textarea
                  placeholder="Type your reply as an agent..."
                  value={replyText}
                  onChange={(e) => setReplyText(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                      e.preventDefault();
                      handleSendReply();
                    }
                  }}
                  className="bg-[#1A1A1A] border-white/[0.06] text-zinc-200 placeholder:text-zinc-600 text-sm min-h-[80px] resize-none focus-visible:border-[#FF7F11]/50 focus-visible:ring-[#FF7F11]/20"
                  rows={3}
                />
              </div>
              <div className="flex items-center justify-between mt-2">
                <span className="text-[10px] text-zinc-600">Press Cmd+Enter to send</span>
                <Button
                  size="sm"
                  className="bg-[#FF7F11] text-white hover:bg-[#FF7F11]/90 text-xs"
                  disabled={!replyText.trim() || sendingReply}
              onClick={handleSendReply}
                >
                  <SendIcon />
                  {sendingReply ? 'Sending...' : 'Send Reply'}
                </Button>
              </div>
            </div>
          </div>

          {/* Attachments (T19) */}
          {attachments.length > 0 && (
            <div className="bg-[#111111] border border-white/[0.06] rounded-xl p-4">
              <h2 className="text-sm font-semibold text-zinc-200 mb-3">
                Attachments ({attachments.length})
              </h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {attachments.map(att => (
                  <div key={att.id} className="flex items-center gap-3 p-2.5 bg-[#1A1A1A] rounded-lg border border-white/[0.04] hover:border-white/[0.08] transition-colors">
                    <span className="text-lg">{getFileIcon(att.file_type)}</span>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-zinc-300 truncate">{att.filename}</p>
                      <p className="text-[10px] text-zinc-600">
                        {(att.file_size / 1024).toFixed(1)} KB &middot; {formatDate(att.created_at)}
                      </p>
                    </div>
                    {att.url && (
                      <a
                        href={att.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-zinc-500 hover:text-[#FF7F11] transition-colors"
                      >
                        <DownloadIcon />
                      </a>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right: Sidebar (T10, T12, T13, T14, T15, T17, T18) */}
        <div className="w-full lg:w-80 shrink-0 space-y-4">
          <div className="lg:sticky lg:top-16">
            <Tabs defaultValue="details" className="w-full">
              <TabsList className="w-full bg-[#111111] border border-white/[0.06] p-1 h-9">
                <TabsTrigger value="details" className="text-xs flex-1 data-[state=active]:bg-[#1A1A1A] data-[state=active]:text-zinc-200 text-zinc-500">
                  Details
                </TabsTrigger>
                <TabsTrigger value="timeline" className="text-xs flex-1 data-[state=active]:bg-[#1A1A1A] data-[state=active]:text-zinc-200 text-zinc-500">
                  Timeline
                </TabsTrigger>
                <TabsTrigger value="notes" className="text-xs flex-1 data-[state=active]:bg-[#1A1A1A] data-[state=active]:text-zinc-200 text-zinc-500">
                  Notes
                </TabsTrigger>
              </TabsList>

              {/* ── Details Tab (T10, T12, T13, T14, T15) ──────────── */}
              <TabsContent value="details" className="space-y-4 mt-4">
                {/* Customer Info Card (T15) */}
                <div className="bg-[#111111] border border-white/[0.06] rounded-xl p-4">
                  <h3 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider mb-3">Customer</h3>
                  {ticket.customer_id ? (
                    <Link
                      href={`/dashboard/customers/${ticket.customer_id}`}
                      className="flex items-center gap-3 p-2.5 bg-[#1A1A1A] rounded-lg border border-white/[0.04] hover:border-[#FF7F11]/20 transition-colors group"
                    >
                      <div className="w-8 h-8 rounded-full bg-gradient-to-br from-emerald-500 to-teal-400 flex items-center justify-center text-white text-xs font-semibold shrink-0">
                        C
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-zinc-200 group-hover:text-[#FF7F11] transition-colors truncate">
                          Customer
                        </p>
                        <p className="text-[10px] text-zinc-500">ID: {ticket.customer_id.slice(0, 12)}</p>
                      </div>
                      <svg className="w-4 h-4 text-zinc-600 group-hover:text-[#FF7F11] transition-colors shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="m8.25 4.5 7.5 7.5-7.5 7.5" />
                      </svg>
                    </Link>
                  ) : (
                    <p className="text-xs text-zinc-500">No customer associated</p>
                  )}
                </div>

                {/* Metadata Grid (T10) */}
                <div className="bg-[#111111] border border-white/[0.06] rounded-xl p-4">
                  <h3 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider mb-3">Ticket Info</h3>
                  <dl className="space-y-3">
                    <div className="flex items-center justify-between">
                      <dt className="text-xs text-zinc-500">Channel</dt>
                      <dd className="text-xs text-zinc-300 capitalize flex items-center gap-1.5">
                        <span className="text-sm">{ticket.channel === 'email' ? '✉' : ticket.channel === 'chat' ? '💬' : ticket.channel === 'sms' ? '📱' : ticket.channel === 'voice' ? '📞' : '🌐'}</span>
                        {ticket.channel}
                      </dd>
                    </div>
                    <Separator className="bg-white/[0.04]" />
                    <div className="flex items-center justify-between">
                      <dt className="text-xs text-zinc-500">Category</dt>
                      <dd className="text-xs text-zinc-300 capitalize">{ticket.category?.replace(/_/g, ' ') || '\u2014'}</dd>
                    </div>
                    <Separator className="bg-white/[0.04]" />
                    <div className="flex items-center justify-between">
                      <dt className="text-xs text-zinc-500">Agent</dt>
                      <dd className="text-xs text-zinc-300">{ticket.assigned_to?.slice(0, 12) || ticket.agent_id?.slice(0, 12) || '\u2014'}</dd>
                    </div>
                    <Separator className="bg-white/[0.04]" />
                    <div className="flex items-center justify-between">
                      <dt className="text-xs text-zinc-500">Variant</dt>
                      <dd className="text-xs text-zinc-300">{ticket.variant_version || '\u2014'}</dd>
                    </div>
                    <Separator className="bg-white/[0.04]" />
                    <div className="flex items-center justify-between">
                      <dt className="text-xs text-zinc-500">Escalation</dt>
                      <dd className={`text-xs font-medium ${ticket.escalation_level > 0 ? 'text-red-400' : 'text-zinc-500'}`}>
                        {ticket.escalation_level > 0 ? `Level ${ticket.escalation_level}` : 'None'}
                      </dd>
                    </div>
                    <Separator className="bg-white/[0.04]" />
                    <div className="flex items-center justify-between">
                      <dt className="text-xs text-zinc-500">Language</dt>
                      <dd className="text-xs text-zinc-300">{language || '\u2014'}</dd>
                    </div>
                  </dl>
                </div>

                {/* AI Confidence (T10) */}
                <div className="bg-[#111111] border border-white/[0.06] rounded-xl p-4">
                  <h3 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider mb-3">AI Confidence</h3>
                  {avgConfidence !== null ? (
                    <div>
                      <div className="flex items-center gap-2 mb-2">
                        <span className={`text-2xl font-bold ${confidenceColor(avgConfidence)}`}>
                          {avgConfidence.toFixed(1)}%
                        </span>
                        <span className="text-xs text-zinc-500">avg</span>
                      </div>
                      <div className="w-full h-2 bg-zinc-800 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all ${confidenceBarColor(avgConfidence)}`}
                          style={{ width: `${avgConfidence}%` }}
                        />
                      </div>
                      <p className="text-[10px] text-zinc-600 mt-1.5">
                        Across {messages.filter(m => m.role === 'ai' && m.ai_confidence != null).length} AI responses
                      </p>
                    </div>
                  ) : (
                    <p className="text-xs text-zinc-500">No AI responses with confidence data</p>
                  )}
                </div>

                {/* GSD State (T13) */}
                <div className="bg-[#111111] border border-white/[0.06] rounded-xl p-4">
                  <h3 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider mb-3">Resolution Progress</h3>
                  <GSDStateIndicator status={ticket.status} />
                </div>

                {/* Sentiment (T12) */}
                <div className="bg-[#111111] border border-white/[0.06] rounded-xl p-4">
                  <h3 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider mb-3">Sentiment</h3>
                  <SentimentBadge sentiment={sentiment} />
                </div>

                {/* AI Technique (T14) */}
                {aiTechnique && (
                  <div className="bg-[#111111] border border-white/[0.06] rounded-xl p-4">
                    <h3 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider mb-2">AI Technique</h3>
                    <Tooltip>
                      <TooltipTrigger>
                        <Badge variant="outline" className="text-xs bg-[#FF7F11]/10 text-[#FF7F11] border-[#FF7F11]/20 cursor-help">
                          {aiTechnique}
                        </Badge>
                      </TooltipTrigger>
                      <TooltipContent side="top" className="bg-[#1A1A1A] text-zinc-300 border-white/[0.06] text-xs max-w-[200px]">
                        The AI technique used to generate responses for this conversation.
                      </TooltipContent>
                    </Tooltip>
                  </div>
                )}

                {/* Resolution Time (T10) */}
                {ticket.first_response_at && (
                  <div className="bg-[#111111] border border-white/[0.06] rounded-xl p-4">
                    <h3 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider mb-3">Timing</h3>
                    <dl className="space-y-2">
                      <div className="flex items-center justify-between">
                        <dt className="text-xs text-zinc-500">First Response</dt>
                        <dd className="text-xs text-zinc-300">{formatDateTime(ticket.first_response_at)}</dd>
                      </div>
                      {ticket.resolution_target_at && (
                        <>
                          <Separator className="bg-white/[0.04]" />
                          <div className="flex items-center justify-between">
                            <dt className="text-xs text-zinc-500">Resolution Target</dt>
                            <dd className="text-xs text-zinc-300">{formatDateTime(ticket.resolution_target_at)}</dd>
                          </div>
                        </>
                      )}
                      {ticket.closed_at && (
                        <>
                          <Separator className="bg-white/[0.04]" />
                          <div className="flex items-center justify-between">
                            <dt className="text-xs text-zinc-500">Closed At</dt>
                            <dd className="text-xs text-zinc-300">{formatDateTime(ticket.closed_at)}</dd>
                          </div>
                        </>
                      )}
                    </dl>
                  </div>
                )}
              </TabsContent>

              {/* ── Timeline Tab (T18) ─────────────────────────────── */}
              <TabsContent value="timeline" className="mt-4">
                <div className="bg-[#111111] border border-white/[0.06] rounded-xl p-4">
                  <h3 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider mb-3">
                    Activity ({timeline.length})
                  </h3>
                  <ScrollArea className="max-h-[60vh]">
                    <div className="relative pl-6">
                      {/* Vertical line */}
                      <div className="absolute left-[9px] top-1 bottom-1 w-px bg-white/[0.06]" />
                      <div className="space-y-4">
                        {timeline.length === 0 ? (
                          <p className="text-xs text-zinc-500 text-center py-8">No activity recorded</p>
                        ) : (
                          timeline.map(event => {
                            const { icon, color } = timelineEventIcon(event.type);
                            return (
                              <div key={event.id} className="relative flex gap-3">
                                {/* Dot */}
                                <div className={`absolute -left-6 top-0.5 w-[18px] h-[18px] rounded-full flex items-center justify-center shrink-0 ${color}`}>
                                  {icon}
                                </div>
                                {/* Content */}
                                <div className="flex-1 min-w-0">
                                  <p className="text-xs text-zinc-300">{timelineEventDescription(event)}</p>
                                  {event.reason && (
                                    <p className="text-[10px] text-zinc-500 mt-0.5 italic">Reason: {event.reason}</p>
                                  )}
                                  <div className="flex items-center gap-2 mt-1">
                                    <span className="text-[10px] text-zinc-600">{formatDateTime(event.timestamp)}</span>
                                    <span className={`text-[10px] px-1.5 py-0 rounded ${
                                      event.actor_type === 'ai' ? 'bg-[#FF7F11]/10 text-[#FF7F11]' :
                                      event.actor_type === 'human' ? 'bg-blue-500/10 text-blue-400' :
                                      'bg-zinc-800 text-zinc-500'
                                    }`}>
                                      {event.actor_type}
                                    </span>
                                  </div>
                                </div>
                              </div>
                            );
                          })
                        )}
                      </div>
                    </div>
                  </ScrollArea>
                </div>
              </TabsContent>

              {/* ── Notes Tab (T17) ───────────────────────────────── */}
              <TabsContent value="notes" className="mt-4">
                <div className="bg-[#111111] border border-white/[0.06] rounded-xl p-4">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider">
                      Notes ({notes.length})
                    </h3>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="text-zinc-500 hover:text-[#FF7F11] hover:bg-[#FF7F11]/10 text-xs h-7"
                      onClick={() => setShowNoteForm(true)}
                    >
                      <PlusIcon /> Add Note
                    </Button>
                  </div>

                  {/* Add Note Form */}
                  {showNoteForm && (
                    <div className="mb-4 p-3 bg-[#1A1A1A] rounded-lg border border-white/[0.06] animate-in fade-in-0 slide-in-from-top-1 duration-200">
                      <Textarea
                        placeholder="Write an internal note..."
                        value={noteText}
                        onChange={(e) => setNoteText(e.target.value)}
                        className="bg-[#0D0D0D] border-white/[0.06] text-zinc-200 placeholder:text-zinc-600 text-xs min-h-[60px] resize-none focus-visible:border-[#FF7F11]/50 focus-visible:ring-[#FF7F11]/20"
                        rows={3}
                      />
                      <div className="flex items-center justify-end gap-2 mt-2">
                        <Button
                          size="sm"
                          variant="ghost"
                          className="text-zinc-500 hover:text-zinc-300 text-xs h-7"
                          onClick={() => { setShowNoteForm(false); setNoteText(''); }}
                        >
                          Cancel
                        </Button>
                        <Button
                          size="sm"
                          className="bg-[#FF7F11] text-white hover:bg-[#FF7F11]/90 text-xs h-7"
                          disabled={!noteText.trim() || addingNote}
                          onClick={handleAddNote}
                        >
                          {addingNote ? 'Saving...' : 'Save Note'}
                        </Button>
                      </div>
                    </div>
                  )}

                  {/* Notes List */}
                  <ScrollArea className="max-h-[60vh]">
                    <div className="space-y-3">
                      {sortedNotes.length === 0 && !showNoteForm ? (
                        <div className="text-center py-8">
                          <p className="text-xs text-zinc-500">No notes yet</p>
                        </div>
                      ) : (
                        sortedNotes.map(note => (
                          <div key={note.id} className={`p-3 rounded-lg border transition-colors ${
                            note.is_pinned
                              ? 'bg-amber-500/[0.03] border-amber-500/10'
                              : 'bg-[#1A1A1A] border-white/[0.04]'
                          }`}>
                            <div className="flex items-start justify-between gap-2 mb-1.5">
                              <div className="flex items-center gap-2">
                                {note.is_pinned && <PinIcon filled />}
                                <span className="text-[10px] text-zinc-500">
                                  {formatDateTime(note.created_at)}
                                </span>
                              </div>
                              <div className="flex items-center gap-1">
                                {/* Edit note button (Fix 10) */}
                                <button
                                  onClick={() => handleStartEditNote(note)}
                                  className="p-1 text-zinc-600 hover:text-[#FF7F11] transition-colors rounded"
                                  title="Edit note"
                                >
                                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                    <path strokeLinecap="round" strokeLinejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0 1 15.75 21H5.25A2.25 2.25 0 0 1 3 18.75V8.25A2.25 2.25 0 0 1 5.25 6H10" />
                                  </svg>
                                </button>
                                <button
                                  onClick={() => handleTogglePin(note.id)}
                                  className="p-1 text-zinc-600 hover:text-[#FF7F11] transition-colors rounded"
                                  title={note.is_pinned ? 'Unpin note' : 'Pin note'}
                                >
                                  <PinIcon filled={note.is_pinned} />
                                </button>
                                <button
                                  onClick={() => handleDeleteNote(note.id)}
                                  className="p-1 text-zinc-600 hover:text-red-400 transition-colors rounded"
                                  title="Delete note"
                                >
                                  <TrashIcon />
                                </button>
                              </div>
                            </div>
                            {editingNoteId === note.id ? (
                              <div className="space-y-2">
                                <Textarea
                                  value={editNoteText}
                                  onChange={(e) => setEditNoteText(e.target.value)}
                                  className="bg-[#0D0D0D] border-white/[0.06] text-zinc-200 placeholder:text-zinc-600 text-xs min-h-[60px] resize-none focus-visible:border-[#FF7F11]/50 focus-visible:ring-[#FF7F11]/20"
                                  rows={3}
                                  autoFocus
                                />
                                <div className="flex items-center justify-end gap-2">
                                  <Button
                                    size="sm"
                                    variant="ghost"
                                    className="text-zinc-500 hover:text-zinc-300 text-xs h-6 px-2"
                                    onClick={handleCancelEditNote}
                                    disabled={savingNote}
                                  >
                                    Cancel
                                  </Button>
                                  <Button
                                    size="sm"
                                    className="bg-[#FF7F11] text-white hover:bg-[#FF7F11]/90 text-xs h-6 px-2"
                                    disabled={!editNoteText.trim() || savingNote}
                                    onClick={() => handleSaveEditNote(note.id)}
                                  >
                                    {savingNote ? 'Saving...' : 'Save'}
                                  </Button>
                                </div>
                              </div>
                            ) : (
                              <p className="text-xs text-zinc-400 whitespace-pre-wrap">{note.content}</p>
                            )}
                          </div>
                        ))
                      )}
                    </div>
                  </ScrollArea>
                </div>
              </TabsContent>
            </Tabs>
          </div>
        </div>
      </div>

      {/* Escalate Dialog (T16) */}
      <Dialog open={escalateOpen} onOpenChange={setEscalateOpen}>
        <DialogContent className="bg-[#1A1A1A] border-white/[0.06] text-zinc-200 sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-zinc-100">Escalate Ticket</DialogTitle>
            <DialogDescription className="text-zinc-500">
              This will change the ticket status to &quot;Awaiting Human&quot; and notify a human agent.
            </DialogDescription>
          </DialogHeader>
          <div className="py-2">
            <label className="text-xs font-medium text-zinc-400 block mb-1.5">Reason for escalation</label>
            <Textarea
              placeholder="Describe why this ticket needs human intervention..."
              value={escalateReason}
              onChange={(e) => setEscalateReason(e.target.value)}
              className="bg-[#111111] border-white/[0.06] text-zinc-200 placeholder:text-zinc-600 text-sm min-h-[80px] resize-none focus-visible:border-[#FF7F11]/50 focus-visible:ring-[#FF7F11]/20"
              rows={3}
            />
          </div>
          <DialogFooter>
            <Button
              variant="ghost"
              size="sm"
              className="text-zinc-400 hover:text-zinc-200"
              onClick={() => setEscalateOpen(false)}
              disabled={escalating}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              className="bg-orange-500 text-white hover:bg-orange-600"
              onClick={handleEscalate}
              disabled={escalating}
            >
              {escalating ? 'Escalating...' : 'Escalate Ticket'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
