'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from '@/components/ui/dialog';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';
import {
  Ticket, Search, Filter, Clock, MessageSquare, Bot, User,
  CheckCircle2, XCircle, AlertTriangle, ChevronRight,
  Loader2, ArrowUpDown, Eye, ThumbsUp, ThumbsDown, RotateCcw,
  StickyNote,
} from 'lucide-react';
import {
  getTickets, getTicketDetail, getTicketMessages, getTicketStats,
  approveAction, denyAction, undoAction, addNoteToAction,
  type TicketListItem, type TicketDetail as TicketDetailType,
  type TicketMessage as TicketMessageType, type TicketStats,
  type AIAction, type VariantType,
} from '@/lib/api';
import { toast } from 'sonner';

interface TicketsPageProps {
  activeVariants: VariantType[];
}

// Badge color helpers
function priorityColor(priority: string): string {
  switch (priority) {
    case 'urgent': return 'bg-red-100 text-red-800 border-red-200';
    case 'high': return 'bg-orange-100 text-orange-800 border-orange-200';
    case 'normal': return 'bg-blue-100 text-blue-800 border-blue-200';
    case 'low': return 'bg-slate-100 text-slate-700 border-slate-200';
    default: return 'bg-slate-100 text-slate-700 border-slate-200';
  }
}

function statusColor(status: string): string {
  switch (status) {
    case 'open': return 'bg-amber-100 text-amber-800 border-amber-200';
    case 'in_progress': return 'bg-sky-100 text-sky-800 border-sky-200';
    case 'resolved': return 'bg-emerald-100 text-emerald-800 border-emerald-200';
    case 'closed': return 'bg-slate-100 text-slate-600 border-slate-200';
    default: return 'bg-slate-100 text-slate-600 border-slate-200';
  }
}

function sentimentColor(sentiment: string): string {
  switch (sentiment) {
    case 'angry': return 'text-red-600';
    case 'frustrated': return 'text-orange-600';
    case 'negative': return 'text-orange-500';
    case 'neutral': return 'text-slate-500';
    case 'positive': return 'text-emerald-600';
    default: return 'text-slate-500';
  }
}

function sentimentEmoji(sentiment: string): string {
  switch (sentiment) {
    case 'angry': return '😡';
    case 'frustrated': return '😤';
    case 'negative': return '😕';
    case 'neutral': return '😐';
    case 'positive': return '😊';
    default: return '😐';
  }
}

function actionStatusColor(status: string): string {
  switch (status) {
    case 'executed': return 'bg-[#0A3D2E]/10 text-[#0A3D2E]';
    case 'pending': return 'bg-amber-100 text-amber-800';
    case 'undone': return 'bg-slate-100 text-slate-600';
    case 'denied': return 'bg-red-100 text-red-800';
    default: return 'bg-slate-100 text-slate-600';
  }
}

// Quality score helpers
function qualityScoreColor(score: number): string {
  if (score >= 80) return 'bg-emerald-100 text-emerald-800 border-emerald-200';
  if (score >= 60) return 'bg-amber-100 text-amber-800 border-amber-200';
  if (score >= 40) return 'bg-orange-100 text-orange-800 border-orange-200';
  return 'bg-red-100 text-red-800 border-red-200';
}

function qualityScoreLabel(score: number): string {
  if (score >= 80) return 'Excellent';
  if (score >= 60) return 'Good';
  if (score >= 40) return 'Needs Review';
  return 'Poor';
}

function qualityScoreBgGradient(score: number): string {
  if (score >= 80) return 'from-emerald-500 to-emerald-600';
  if (score >= 60) return 'from-amber-500 to-amber-600';
  if (score >= 40) return 'from-orange-500 to-orange-600';
  return 'from-red-500 to-red-600';
}

export default function TicketsPage({ activeVariants }: TicketsPageProps) {
  // State
  const [tickets, setTickets] = useState<TicketListItem[]>([]);
  const [stats, setStats] = useState<TicketStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [totalTickets, setTotalTickets] = useState(0);

  // Filters
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [channelFilter, setChannelFilter] = useState<string>('all');
  const [priorityFilter, setPriorityFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');

  // Detail dialog
  const [selectedTicket, setSelectedTicket] = useState<TicketDetailType | null>(null);
  const [ticketMessages, setTicketMessages] = useState<TicketMessageType[]>([]);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);

  // Note dialog
  const [noteActionId, setNoteActionId] = useState<string | null>(null);
  const [noteText, setNoteText] = useState('');
  const [noteLoading, setNoteLoading] = useState(false);

  // Load tickets
  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      try {
        const params: Record<string, string | number> = {};
        if (statusFilter !== 'all') params.status = statusFilter;
        if (channelFilter !== 'all') params.channel = channelFilter;
        if (priorityFilter !== 'all') params.priority = priorityFilter;
        if (searchQuery.trim()) params.search = searchQuery.trim();

        const [ticketRes, statsRes] = await Promise.all([
          getTickets(params),
          getTicketStats(),
        ]);
        if (!cancelled) {
          setTickets(ticketRes.tickets);
          setTotalTickets(ticketRes.total);
          setStats(statsRes);
        }
      } catch {
        // Fallback data already handled in api.ts
      }
      if (!cancelled) setLoading(false);
    }
    load();
    return () => { cancelled = true; };
  }, [statusFilter, channelFilter, priorityFilter, searchQuery]);

  const loadTickets = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string | number> = {};
      if (statusFilter !== 'all') params.status = statusFilter;
      if (channelFilter !== 'all') params.channel = channelFilter;
      if (priorityFilter !== 'all') params.priority = priorityFilter;
      if (searchQuery.trim()) params.search = searchQuery.trim();

      const [ticketRes, statsRes] = await Promise.all([
        getTickets(params),
        getTicketStats(),
      ]);
      setTickets(ticketRes.tickets);
      setTotalTickets(ticketRes.total);
      setStats(statsRes);
    } catch {
      // Fallback data already handled in api.ts
    }
    setLoading(false);
  }, [statusFilter, channelFilter, priorityFilter, searchQuery]);

  // Open ticket detail
  const openTicketDetail = useCallback(async (ticketId: string) => {
    setDetailLoading(true);
    setDetailOpen(true);
    try {
      const [detail, msgs] = await Promise.all([
        getTicketDetail(ticketId),
        getTicketMessages(ticketId),
      ]);
      setSelectedTicket(detail);
      setTicketMessages(msgs);
    } catch {
      toast.error('Failed to load ticket details');
    }
    setDetailLoading(false);
  }, []);

  // Action handlers
  const handleApprove = useCallback(async (actionId: string) => {
    try {
      await approveAction(actionId);
      toast.success('Action approved and executed');
      if (selectedTicket) openTicketDetail(selectedTicket.id);
      loadTickets();
    } catch {
      toast.error('Failed to approve action');
    }
  }, [selectedTicket, openTicketDetail, loadTickets]);

  const handleDeny = useCallback(async (actionId: string) => {
    try {
      await denyAction(actionId);
      toast.success('Action denied');
      if (selectedTicket) openTicketDetail(selectedTicket.id);
      loadTickets();
    } catch {
      toast.error('Failed to deny action');
    }
  }, [selectedTicket, openTicketDetail, loadTickets]);

  const handleUndo = useCallback(async (actionId: string) => {
    try {
      await undoAction(actionId);
      toast.success('Action undone');
      if (selectedTicket) openTicketDetail(selectedTicket.id);
      loadTickets();
    } catch {
      toast.error('Failed to undo action');
    }
  }, [selectedTicket, openTicketDetail, loadTickets]);

  const handleAddNote = async () => {
    if (!noteActionId || !noteText.trim()) return;
    setNoteLoading(true);
    try {
      await addNoteToAction(noteActionId, noteText.trim());
      toast.success('Note added');
      setNoteActionId(null);
      setNoteText('');
      if (selectedTicket) openTicketDetail(selectedTicket.id);
    } catch {
      toast.error('Failed to add note');
    }
    setNoteLoading(false);
  };

  const statsCards = [
    { label: 'Total', value: stats?.total_tickets ?? 0, color: 'bg-[#0A3D2E]/5 text-[#0A3D2E]' },
    { label: 'Open', value: stats?.open_tickets ?? 0, color: 'bg-amber-50 text-amber-700' },
    { label: 'In Progress', value: stats?.in_progress ?? 0, color: 'bg-sky-50 text-sky-700' },
    { label: 'Resolved', value: stats?.resolved ?? 0, color: 'bg-emerald-50 text-emerald-700' },
    { label: 'Pending AI', value: stats?.pending_approvals ?? 0, color: 'bg-red-50 text-red-700' },
    { label: 'Avg Quality', value: tickets.length > 0 ? Math.round(tickets.reduce((sum, t) => sum + (t.quality_score ?? 0), 0) / tickets.length) : 0, color: 'bg-violet-50 text-violet-700' },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Tickets</h2>
        <p className="text-muted-foreground">Manage and monitor all customer support tickets with AI action tracking.</p>
      </div>

      {/* Stats Bar */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {statsCards.map((s) => (
          <Card key={s.label} className="border-0 shadow-sm">
            <CardContent className={`p-4 rounded-lg ${s.color}`}>
              <p className="text-xs font-medium opacity-70">{s.label}</p>
              <p className="text-2xl font-bold">{loading ? <Skeleton className="h-7 w-10 bg-white/50" /> : s.value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Filter Bar */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="flex-1">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search tickets by subject or customer..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-9"
                />
              </div>
            </div>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-full sm:w-[150px]">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Status</SelectItem>
                <SelectItem value="open">Open</SelectItem>
                <SelectItem value="in_progress">In Progress</SelectItem>
                <SelectItem value="resolved">Resolved</SelectItem>
                <SelectItem value="closed">Closed</SelectItem>
              </SelectContent>
            </Select>
            <Select value={channelFilter} onValueChange={setChannelFilter}>
              <SelectTrigger className="w-full sm:w-[150px]">
                <SelectValue placeholder="Channel" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Channels</SelectItem>
                <SelectItem value="email">Email</SelectItem>
                <SelectItem value="chat">Chat</SelectItem>
                <SelectItem value="voice">Voice</SelectItem>
                <SelectItem value="sms">SMS</SelectItem>
                <SelectItem value="webhook">Webhook</SelectItem>
              </SelectContent>
            </Select>
            <Select value={priorityFilter} onValueChange={setPriorityFilter}>
              <SelectTrigger className="w-full sm:w-[150px]">
                <SelectValue placeholder="Priority" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Priority</SelectItem>
                <SelectItem value="urgent">Urgent</SelectItem>
                <SelectItem value="high">High</SelectItem>
                <SelectItem value="normal">Normal</SelectItem>
                <SelectItem value="low">Low</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Tickets Table */}
      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="p-6 space-y-3">
              {[1, 2, 3, 4, 5].map(i => (
                <Skeleton key={i} className="h-14 w-full" />
              ))}
            </div>
          ) : tickets.length === 0 ? (
            <div className="text-center py-16">
              <Ticket className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <p className="text-lg font-medium text-muted-foreground">No tickets found</p>
              <p className="text-sm text-muted-foreground mt-1">Try adjusting your filters</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="bg-[#0A3D2E]/5 hover:bg-[#0A3D2E]/5">
                    <TableHead className="font-semibold text-[#0A3D2E]">ID</TableHead>
                    <TableHead className="font-semibold text-[#0A3D2E]">Subject</TableHead>
                    <TableHead className="font-semibold text-[#0A3D2E]">Customer</TableHead>
                    <TableHead className="font-semibold text-[#0A3D2E]">Channel</TableHead>
                    <TableHead className="font-semibold text-[#0A3D2E]">Priority</TableHead>
                    <TableHead className="font-semibold text-[#0A3D2E]">Status</TableHead>
                    <TableHead className="font-semibold text-[#0A3D2E]">AI Actions</TableHead>
                    <TableHead className="font-semibold text-[#0A3D2E]">Quality Score</TableHead>
                    <TableHead className="font-semibold text-[#0A3D2E]">Sentiment</TableHead>
                    <TableHead className="font-semibold text-[#0A3D2E]">Created</TableHead>
                    <TableHead className="w-10"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  <AnimatePresence>
                    {tickets.map((t) => (
                      <motion.tr
                        key={t.id}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="cursor-pointer hover:bg-[#0A3D2E]/5 transition-colors group"
                        onClick={() => openTicketDetail(t.id)}
                      >
                        <TableCell className="font-mono text-xs text-muted-foreground">{t.id}</TableCell>
                        <TableCell className="font-medium max-w-[250px] truncate">{t.subject}</TableCell>
                        <TableCell className="text-sm">{t.customer_name}</TableCell>
                        <TableCell>
                          <Badge variant="outline" className="text-xs capitalize">{t.channel}</Badge>
                        </TableCell>
                        <TableCell>
                          <Badge className={`text-xs border ${priorityColor(t.priority)}`}>
                            {t.priority}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Badge className={`text-xs border ${statusColor(t.status)}`}>
                            {t.status.replace('_', ' ')}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-sm">
                          {t.ai_action_count > 0 ? (
                            <Badge className="bg-[#0A3D2E]/10 text-[#0A3D2E] text-xs">
                              <Bot className="h-3 w-3 mr-1" />
                              {t.ai_action_count}
                            </Badge>
                          ) : (
                            <span className="text-muted-foreground text-xs">—</span>
                          )}
                        </TableCell>
                        <TableCell className="text-sm">
                          <div className="flex items-center gap-1.5">
                            <div className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold border ${qualityScoreColor(t.quality_score ?? 0)}`}>
                              <span className="font-mono">{Math.round(t.quality_score ?? 0)}</span>
                              <span className="opacity-70">/100</span>
                            </div>
                          </div>
                        </TableCell>
                        <TableCell className="text-sm">
                          <span className={sentimentColor(t.sentiment)}>
                            {sentimentEmoji(t.sentiment)} {t.sentiment}
                          </span>
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          {new Date(t.created_at).toLocaleDateString()}
                        </TableCell>
                        <TableCell>
                          <ChevronRight className="h-4 w-4 text-muted-foreground group-hover:text-[#0A3D2E] transition-colors" />
                        </TableCell>
                      </motion.tr>
                    ))}
                  </AnimatePresence>
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Ticket Detail Dialog */}
      <Dialog open={detailOpen} onOpenChange={setDetailOpen}>
        <DialogContent className="max-w-3xl max-h-[85vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Ticket className="h-5 w-5 text-[#0A3D2E]" />
              {detailLoading ? 'Loading...' : selectedTicket?.subject ?? 'Ticket Details'}
            </DialogTitle>
            <DialogDescription>
              {selectedTicket && (
                <span className="flex items-center gap-2 flex-wrap">
                  <Badge className={`border ${statusColor(selectedTicket.status)}`}>
                    {selectedTicket.status.replace('_', ' ')}
                  </Badge>
                  <Badge className={`border ${priorityColor(selectedTicket.priority)}`}>
                    {selectedTicket.priority}
                  </Badge>
                  <Badge variant="outline" className="capitalize">{selectedTicket.channel}</Badge>
                  <Badge className={`text-xs border ${qualityScoreColor(selectedTicket.quality_score)}`}>
                    Score: {Math.round(selectedTicket.quality_score)}
                  </Badge>
                  <span className="text-xs text-muted-foreground">
                    by {selectedTicket.customer_name} • {selectedTicket.customer_email}
                  </span>
                  <span className={sentimentColor(selectedTicket.sentiment)}>
                    {sentimentEmoji(selectedTicket.sentiment)} {selectedTicket.sentiment}
                  </span>
                </span>
              )}
            </DialogDescription>
          </DialogHeader>

          {detailLoading ? (
            <div className="flex-1 space-y-3 p-4">
              {[1, 2, 3, 4].map(i => <Skeleton key={i} className="h-16 w-full" />)}
            </div>
          ) : selectedTicket ? (
            <div className="flex-1 overflow-y-auto space-y-6 px-1 pb-4">
              {/* Quality Score Card */}
              <div className="flex items-center gap-4 p-4 rounded-xl bg-gradient-to-r from-slate-50 to-white border">
                <div className="relative flex-shrink-0">
                  <svg className="w-20 h-20 -rotate-90" viewBox="0 0 80 80">
                    <circle cx="40" cy="40" r="34" fill="none" stroke="#e5e7eb" strokeWidth="6" />
                    <circle
                      cx="40" cy="40" r="34" fill="none"
                      stroke={selectedTicket.quality_score >= 80 ? '#10b981' : selectedTicket.quality_score >= 60 ? '#f59e0b' : selectedTicket.quality_score >= 40 ? '#f97316' : '#ef4444'}
                      strokeWidth="6"
                      strokeDasharray={`${(selectedTicket.quality_score / 100) * 213.6} 213.6`}
                      strokeLinecap="round"
                    />
                  </svg>
                  <div className="absolute inset-0 flex items-center justify-center">
                    <span className="text-lg font-bold font-mono">{Math.round(selectedTicket.quality_score)}</span>
                  </div>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <h4 className="text-sm font-semibold text-[#0A3D2E]">AI Quality Score</h4>
                    <Badge className={`text-xs border ${qualityScoreColor(selectedTicket.quality_score)}`}>
                      {qualityScoreLabel(selectedTicket.quality_score)}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground mb-2">
                    Scored by the PARWA quality_scorer node on accuracy, completeness, compliance, and empathy.
                  </p>
                  {selectedTicket.quality_issues && selectedTicket.quality_issues.length > 0 && (
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className="text-xs font-medium text-muted-foreground">Issues:</span>
                      {selectedTicket.quality_issues.map((issue, idx) => (
                        <Badge key={idx} variant="outline" className="text-xs text-orange-700 border-orange-200 bg-orange-50">
                          {issue.replace(/_/g, ' ')}
                        </Badge>
                      ))}
                    </div>
                  )}
                  {(!selectedTicket.quality_issues || selectedTicket.quality_issues.length === 0) && (
                    <div className="flex items-center gap-1.5">
                      <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                      <span className="text-xs text-emerald-600 font-medium">No quality issues detected</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Conversation */}
              <div>
                <h4 className="text-sm font-semibold text-[#0A3D2E] flex items-center gap-1.5 mb-3">
                  <MessageSquare className="h-4 w-4" />
                  Conversation ({ticketMessages.length} messages)
                </h4>
                <div className="space-y-3 max-h-64 overflow-y-auto pr-1">
                  {ticketMessages.map((msg) => (
                    <div
                      key={msg.id}
                      className={`flex gap-3 ${msg.sender === 'customer' ? '' : msg.sender === 'ai' ? 'flex-row-reverse' : ''}`}
                    >
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${
                        msg.sender === 'customer' ? 'bg-amber-100' :
                        msg.sender === 'ai' ? 'bg-[#0A3D2E]' :
                        msg.sender === 'agent' ? 'bg-sky-100' :
                        'bg-slate-100'
                      }`}>
                        {msg.sender === 'customer' ? <User className="h-4 w-4 text-amber-700" /> :
                         msg.sender === 'ai' ? <Bot className="h-4 w-4 text-white" /> :
                         msg.sender === 'agent' ? <User className="h-4 w-4 text-sky-700" /> :
                         <AlertTriangle className="h-4 w-4 text-slate-600" />}
                      </div>
                      <div className={`flex-1 p-3 rounded-lg text-sm ${
                        msg.sender === 'customer' ? 'bg-amber-50 border border-amber-100' :
                        msg.sender === 'ai' ? 'bg-[#0A3D2E]/5 border border-[#0A3D2E]/10' :
                        'bg-slate-50 border border-slate-100'
                      }`}>
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-medium text-xs capitalize">{msg.sender}</span>
                          <span className="text-xs text-muted-foreground">
                            {new Date(msg.timestamp).toLocaleTimeString()}
                          </span>
                        </div>
                        <p>{msg.content}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <Separator />

              {/* AI Actions Trail */}
              <div>
                <h4 className="text-sm font-semibold text-[#0A3D2E] flex items-center gap-1.5 mb-3">
                  <Bot className="h-4 w-4" />
                  AI Action Trail ({selectedTicket.ai_actions.length} actions)
                </h4>
                {selectedTicket.ai_actions.length === 0 ? (
                  <div className="text-center py-6 text-sm text-muted-foreground">
                    No AI actions taken for this ticket
                  </div>
                ) : (
                  <div className="space-y-3 max-h-64 overflow-y-auto pr-1">
                    {selectedTicket.ai_actions.map((action: AIAction) => (
                      <div key={action.id} className="p-3 rounded-lg border bg-white">
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-1">
                              <Badge className={`text-xs ${actionStatusColor(action.status)}`}>
                                {action.status}
                              </Badge>
                              <Badge variant="outline" className="text-xs capitalize">
                                {action.action_type.replace(/_/g, ' ')}
                              </Badge>
                              <span className="text-xs text-muted-foreground capitalize">{action.variant}</span>
                            </div>
                            <p className="text-sm">{action.description}</p>
                            <p className="text-xs text-muted-foreground mt-1">
                              {new Date(action.timestamp).toLocaleString()}
                            </p>
                            {action.result && (
                              <div className="mt-2 p-2 rounded bg-slate-50 text-xs font-mono">
                                {JSON.stringify(action.result)}
                              </div>
                            )}
                          </div>
                          <div className="flex items-center gap-1 shrink-0">
                            {action.can_approve && action.status === 'pending' && (
                              <>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="h-7 text-xs border-emerald-300 text-emerald-700 hover:bg-emerald-50"
                                  onClick={(e) => { e.stopPropagation(); handleApprove(action.id); }}
                                >
                                  <ThumbsUp className="h-3 w-3 mr-1" /> Approve
                                </Button>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="h-7 text-xs border-red-300 text-red-700 hover:bg-red-50"
                                  onClick={(e) => { e.stopPropagation(); handleDeny(action.id); }}
                                >
                                  <ThumbsDown className="h-3 w-3 mr-1" /> Deny
                                </Button>
                              </>
                            )}
                            {action.can_undo && action.status === 'executed' && (
                              <Button
                                size="sm"
                                variant="outline"
                                className="h-7 text-xs border-amber-300 text-amber-700 hover:bg-amber-50"
                                onClick={(e) => { e.stopPropagation(); handleUndo(action.id); }}
                              >
                                <RotateCcw className="h-3 w-3 mr-1" /> Undo
                              </Button>
                            )}
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-7 text-xs"
                              onClick={(e) => { e.stopPropagation(); setNoteActionId(action.id); setNoteText(''); }}
                            >
                              <StickyNote className="h-3 w-3 mr-1" /> Note
                            </Button>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Tags */}
              {selectedTicket.tags.length > 0 && (
                <>
                  <Separator />
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs font-medium text-muted-foreground">Tags:</span>
                    {selectedTicket.tags.map((tag) => (
                      <Badge key={tag} variant="outline" className="text-xs">{tag}</Badge>
                    ))}
                  </div>
                </>
              )}
            </div>
          ) : null}
        </DialogContent>
      </Dialog>

      {/* Note Dialog */}
      <Dialog open={noteActionId !== null} onOpenChange={() => { setNoteActionId(null); setNoteText(''); }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Add Note to Action</DialogTitle>
            <DialogDescription>Provide a correction or instruction for this AI action.</DialogDescription>
          </DialogHeader>
          <textarea
            className="w-full h-32 rounded-lg border p-3 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-[#0A3D2E]/30"
            placeholder="Enter your note..."
            value={noteText}
            onChange={(e) => setNoteText(e.target.value)}
          />
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => { setNoteActionId(null); setNoteText(''); }}>
              Cancel
            </Button>
            <Button
              onClick={handleAddNote}
              disabled={noteLoading || !noteText.trim()}
              className="bg-[#D4AF37] hover:bg-[#E5C860] text-[#1A1A1A]"
            >
              {noteLoading ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : null}
              Add Note
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
