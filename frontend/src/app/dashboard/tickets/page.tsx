'use client';

import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { ticketsApi, type TicketResponse, type TicketStatus, type TicketPriority, type TicketChannel } from '@/lib/tickets-api';
import { useSocket } from '@/contexts/SocketContext';
import { getErrorMessage } from '@/lib/api';
import {
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell,
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger, DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '@/components/ui/dialog';
import {
  Popover, PopoverTrigger, PopoverContent,
} from '@/components/ui/popover';

// ── Constants ───────────────────────────────────────────────────────────

const PAGE_SIZE = 25;

const STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: 'open', label: 'Open' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'awaiting_human', label: 'Awaiting Human' },
  { value: 'awaiting_client', label: 'Awaiting Client' },
  { value: 'resolved', label: 'Resolved' },
  { value: 'closed', label: 'Closed' },
  { value: 'reopened', label: 'Reopened' },
];

const CHANNEL_OPTIONS: { value: string; label: string }[] = [
  { value: 'email', label: 'Email' },
  { value: 'chat', label: 'Chat' },
  { value: 'sms', label: 'SMS' },
  { value: 'voice', label: 'Voice' },
  { value: 'social', label: 'Social' },
];

const PRIORITY_OPTIONS: { value: string; label: string }[] = [
  { value: 'critical', label: 'Critical' },
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
];

const CONFIDENCE_OPTIONS: { value: string; label: string; min: number | null; max: number | null }[] = [
  { value: 'all', label: 'All Confidence', min: null, max: null },
  { value: 'critical', label: 'Critical (0-25%)', min: 0, max: 25 },
  { value: 'low', label: 'Low (25-50%)', min: 25, max: 50 },
  { value: 'medium', label: 'Medium (50-75%)', min: 50, max: 75 },
  { value: 'high', label: 'High (75-100%)', min: 75, max: 100 },
];

const SORT_COLUMNS = [
  { value: 'id', label: 'ID' },
  { value: 'status', label: 'Status' },
  { value: 'priority', label: 'Priority' },
  { value: 'channel', label: 'Channel' },
  { value: 'created_at', label: 'Created At' },
  { value: 'updated_at', label: 'Updated At' },
] as const;

type SortColumn = typeof SORT_COLUMNS[number]['value'];

// ── Helper: Color Maps ──────────────────────────────────────────────────

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

const CHANNEL_ICONS: Record<string, { icon: string; color: string }> = {
  email: { icon: '✉', color: 'text-blue-400' },
  chat: { icon: '💬', color: 'text-emerald-400' },
  sms: { icon: '📱', color: 'text-purple-400' },
  voice: { icon: '📞', color: 'text-amber-400' },
  social: { icon: '🌐', color: 'text-pink-400' },
};

// ── Helper: Relative Time ───────────────────────────────────────────────

function relativeTime(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffSec = Math.round((now - then) / 1000);
  if (diffSec < 60) return `${diffSec}s ago`;
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
  if (diffSec < 2592000) return `${Math.floor(diffSec / 86400)}d ago`;
  return new Date(dateStr).toLocaleDateString();
}

function formatStatus(status: string): string {
  return status.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

// ── Inline SVG Icons ────────────────────────────────────────────────────

const SearchIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z" />
  </svg>
);

const ArrowUpIcon = () => (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 15.75 7.5-7.5 7.5 7.5" />
  </svg>
);

const ArrowDownIcon = () => (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
  </svg>
);

const ChevronLeftIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5 8.25 12l7.5-7.5" />
  </svg>
);

const ChevronRightIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="m8.25 4.5 7.5 7.5-7.5 7.5" />
  </svg>
);

const FilterIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 3c2.755 0 5.455.232 8.083.678.533.09.917.556.917 1.096v1.044a2.25 2.25 0 0 1-.659 1.591l-5.432 5.432a2.25 2.25 0 0 0-.659 1.591v2.927a2.25 2.25 0 0 1-1.244 2.013L9.75 21v-6.568a2.25 2.25 0 0 0-.659-1.591L3.659 7.409A2.25 2.25 0 0 1 3 5.818V4.774c0-.54.384-1.006.917-1.096A48.32 48.32 0 0 1 12 3Z" />
  </svg>
);

const RefreshIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182" />
  </svg>
);

const DownloadIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3" />
  </svg>
);

const CheckIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
  </svg>
);

const EmptyTicketIcon = () => (
  <svg className="w-12 h-12" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 6v.75m0 3v.75m0 3v.75m0 3V18m-9-5.25h5.25M7.5 15h3M3.375 5.25c-.621 0-1.125.504-1.125 1.125v3.026a2.999 2.999 0 0 1 0 5.198v3.026c0 .621.504 1.125 1.125 1.125h17.25c.621 0 1.125-.504 1.125-1.125v-3.026a2.999 2.999 0 0 1 0-5.198V6.375c0-.621-.504-1.125-1.125-1.125H3.375Z" />
  </svg>
);

// ── Confidence Bar Component ────────────────────────────────────────────

function ConfidenceBar({ confidence }: { confidence: number | null }) {
  if (confidence === null) return <span className="text-zinc-600 text-xs">&mdash;</span>;
  const color = confidence >= 75 ? 'bg-emerald-500' : confidence >= 50 ? 'bg-amber-500' : 'bg-red-500';
  const textColor = confidence >= 75 ? 'text-emerald-400' : confidence >= 50 ? 'text-amber-400' : 'text-red-400';
  return (
    <div className="flex items-center gap-2 min-w-[80px]">
      <div className="flex-1 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color} transition-all`} style={{ width: `${confidence}%` }} />
      </div>
      <span className={`text-xs font-medium ${textColor} w-8 text-right`}>{confidence}%</span>
    </div>
  );
}

// ── Skeleton Rows ───────────────────────────────────────────────────────

function SkeletonRows() {
  return (
    <>
      {Array.from({ length: 10 }).map((_, i) => (
        <TableRow key={i} className="hover:bg-transparent">
          <TableCell className="p-3"><Skeleton className="h-4 w-4" /></TableCell>
          <TableCell className="p-3"><Skeleton className="h-4 w-16" /></TableCell>
          <TableCell className="p-3"><Skeleton className="h-5 w-16 rounded-full" /></TableCell>
          <TableCell className="p-3"><Skeleton className="h-5 w-16 rounded-full" /></TableCell>
          <TableCell className="p-3"><Skeleton className="h-4 w-48" /></TableCell>
          <TableCell className="p-3"><Skeleton className="h-4 w-16" /></TableCell>
          <TableCell className="p-3"><Skeleton className="h-4 w-20" /></TableCell>
          <TableCell className="p-3"><Skeleton className="h-4 w-24" /></TableCell>
          <TableCell className="p-3"><Skeleton className="h-4 w-16" /></TableCell>
        </TableRow>
      ))}
    </>
  );
}

// ── Main Component ──────────────────────────────────────────────────────

export default function TicketsPage() {
  const router = useRouter();
  const { latestTicketEvent } = useSocket();
  const prevEventRef = useRef<string | null>(null);

  // Data state
  const [tickets, setTickets] = useState<TicketResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters state
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [channelFilter, setChannelFilter] = useState<string>('all');
  const [priorityFilter, setPriorityFilter] = useState<string>('all');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [agentFilter, setAgentFilter] = useState('');
  const [confidenceFilter, setConfidenceFilter] = useState('all');

  // Sort state
  const [sortBy, setSortBy] = useState<SortColumn>('created_at');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');

  // Bulk action state
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkDialogOpen, setBulkDialogOpen] = useState(false);
  const [bulkAction, setBulkAction] = useState<'resolve' | 'priority' | 'assign'>('resolve');
  const [bulkPriority, setBulkPriority] = useState<string>('medium');
  const [bulkAgentId, setBulkAgentId] = useState<string>('');
  const [bulkLoading, setBulkLoading] = useState(false);
  const [bulkError, setBulkError] = useState<string | null>(null);

  // New ticket highlight
  const [highlightedId, setHighlightedId] = useState<string | null>(null);

  // Hover state for quick view
  const [hoveredTicketId, setHoveredTicketId] = useState<string | null>(null);
  const hoverTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // ── Fetch Tickets ───────────────────────────────────────────────────

  const fetchTickets = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, unknown> = {
        page,
        page_size: PAGE_SIZE,
        sort_by: sortBy,
        sort_order: sortOrder,
      };
      if (search) params.search = search;
      if (statusFilter !== 'all') params.status = [statusFilter];
      if (channelFilter !== 'all') params.channel = channelFilter;
      if (priorityFilter !== 'all') params.priority = [priorityFilter];
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo) params.date_to = dateTo;
      if (agentFilter) params.assigned_to = agentFilter;

      const data = await ticketsApi.list(params as Parameters<typeof ticketsApi.list>[0]);
      let ticketItems = data.items || [];

      // Client-side confidence filter
      if (confidenceFilter !== 'all') {
        const range = CONFIDENCE_OPTIONS.find(o => o.value === confidenceFilter);
        if (range && range.min !== null && range.max !== null) {
          ticketItems = ticketItems.filter(t => {
            const conf = (t.metadata_json?.confidence as number) ?? null;
            if (conf === null) return false;
            if (confidenceFilter === 'critical') return conf >= 0 && conf < 25;
            return conf >= range.min! && conf < range.max!;
          });
        }
      }

      setTickets(ticketItems);
      setTotal(data.total || 0);
      setPages(data.pages || 0);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [page, search, statusFilter, channelFilter, priorityFilter, sortBy, sortOrder, dateFrom, dateTo, agentFilter, confidenceFilter]);

  useEffect(() => {
    fetchTickets();
  }, [fetchTickets]);

  // ── Debounced Search ────────────────────────────────────────────────

  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(searchInput);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchInput]);

  // ── Real-time Socket Updates (T7) ──────────────────────────────────

  useEffect(() => {
    if (latestTicketEvent && latestTicketEvent !== prevEventRef.current) {
      prevEventRef.current = latestTicketEvent;
      if (latestTicketEvent === 'ticket:new') {
        fetchTickets().then(() => {
          // Highlight the new ticket (will be first in list since sorted by created_at desc)
          setTickets(prev => {
            if (prev.length > 0) {
              setHighlightedId(prev[0].id);
              setTimeout(() => setHighlightedId(null), 3000);
            }
            return prev;
          });
        });
      } else if (
        latestTicketEvent === 'ticket:status_changed' ||
        latestTicketEvent === 'ticket:resolved' ||
        latestTicketEvent === 'ticket:escalated'
      ) {
        fetchTickets();
      }
    }
  }, [latestTicketEvent, fetchTickets]);

  // ── Reset page on filter change ────────────────────────────────────

  const handleStatusChange = (value: string) => { setStatusFilter(value); setPage(1); };
  const handleChannelChange = (value: string) => { setChannelFilter(value); setPage(1); };
  const handlePriorityChange = (value: string) => { setPriorityFilter(value); setPage(1); };
  const handleConfidenceChange = (value: string) => { setConfidenceFilter(value); setPage(1); };

  // ── Sort Handler ───────────────────────────────────────────────────

  const handleSort = (column: SortColumn) => {
    if (sortBy === column) {
      setSortOrder(prev => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortBy(column);
      setSortOrder('asc');
    }
  };

  // ── Selection Handlers (T6) ────────────────────────────────────────

  const toggleSelect = (id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === tickets.length && tickets.length > 0) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(tickets.map(t => t.id)));
    }
  };

  // ── Bulk Actions (T6) ──────────────────────────────────────────────

  const handleBulkAction = async () => {
    if (selectedIds.size === 0) return;
    setBulkLoading(true);
    setBulkError(null);
    try {
      const ids = Array.from(selectedIds);
      if (bulkAction === 'resolve') {
        await ticketsApi.bulkUpdateStatus({ ticket_ids: ids, status: 'resolved' });
      } else if (bulkAction === 'priority') {
        // Iterate through each ticket and update priority individually
        await Promise.all(
          ids.map(id =>
            ticketsApi.update(id, { priority: bulkPriority as 'critical' | 'high' | 'medium' | 'low' })
          )
        );
      } else if (bulkAction === 'assign') {
        if (!bulkAgentId.trim()) {
          setBulkError('Agent ID is required');
          setBulkLoading(false);
          return;
        }
        await ticketsApi.bulkAssign({
          ticket_ids: ids,
          assignee_id: bulkAgentId.trim(),
          assignee_type: 'human',
        });
      }
      setBulkDialogOpen(false);
      setSelectedIds(new Set());
      setBulkAgentId('');
      fetchTickets();
    } catch (err) {
      setBulkError(getErrorMessage(err));
    } finally {
      setBulkLoading(false);
    }
  };

  const clearFilters = () => {
    setSearchInput('');
    setSearch('');
    setStatusFilter('all');
    setChannelFilter('all');
    setPriorityFilter('all');
    setDateFrom('');
    setDateTo('');
    setAgentFilter('');
    setConfidenceFilter('all');
    setPage(1);
  };

  const hasActiveFilters = search || statusFilter !== 'all' || channelFilter !== 'all' || priorityFilter !== 'all' || dateFrom || dateTo || agentFilter || confidenceFilter !== 'all';

  // ── Pagination ─────────────────────────────────────────────────────

  const getVisiblePages = () => {
    if (pages <= 7) return Array.from({ length: pages }, (_, i) => i + 1);
    const start = Math.max(1, page - 2);
    const end = Math.min(pages, page + 2);
    const visible: number[] = [];
    if (start > 1) { visible.push(1); if (start > 2) visible.push(-1); }
    for (let i = start; i <= end; i++) visible.push(i);
    if (end < pages) { if (end < pages - 1) visible.push(-1); visible.push(pages); }
    return visible;
  };

  // ── Render ─────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-[#0D0D0D] p-4 md:p-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-zinc-100">Tickets</h1>
          <p className="text-sm text-zinc-500 mt-0.5">
            {loading ? 'Loading...' : `${total} ticket${total !== 1 ? 's' : ''} found`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            className="text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.04]"
            onClick={() => fetchTickets()}
          >
            <RefreshIcon />
            Refresh
          </Button>
        </div>
      </div>

      {/* Filter Bar (T3) */}
      <div className="bg-[#111111] border border-white/[0.06] rounded-xl p-4 mb-4">
        <div className="flex flex-col lg:flex-row lg:items-center gap-3">
          {/* Search (T2) */}
          <div className="relative flex-1 min-w-0">
            <div className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500">
              <SearchIcon />
            </div>
            <input
              type="text"
              placeholder="Search tickets by subject, ID, or content..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-[#1A1A1A] border border-white/[0.06] rounded-lg text-sm text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-[#FF7F11]/50 transition-colors"
            />
          </div>

          {/* Filter Dropdowns */}
          <div className="flex flex-wrap items-center gap-2">
            <Select value={statusFilter} onValueChange={handleStatusChange}>
              <SelectTrigger size="sm" className="w-[130px] bg-[#1A1A1A] border-white/[0.06] text-zinc-300 text-xs">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent className="bg-[#1A1A1A] border-white/[0.06]">
                <SelectItem value="all" className="text-zinc-300">All Status</SelectItem>
                {STATUS_OPTIONS.map(opt => (
                  <SelectItem key={opt.value} value={opt.value} className="text-zinc-300">
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select value={channelFilter} onValueChange={handleChannelChange}>
              <SelectTrigger size="sm" className="w-[120px] bg-[#1A1A1A] border-white/[0.06] text-zinc-300 text-xs">
                <SelectValue placeholder="Channel" />
              </SelectTrigger>
              <SelectContent className="bg-[#1A1A1A] border-white/[0.06]">
                <SelectItem value="all" className="text-zinc-300">All Channels</SelectItem>
                {CHANNEL_OPTIONS.map(opt => (
                  <SelectItem key={opt.value} value={opt.value} className="text-zinc-300">
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select value={priorityFilter} onValueChange={handlePriorityChange}>
              <SelectTrigger size="sm" className="w-[120px] bg-[#1A1A1A] border-white/[0.06] text-zinc-300 text-xs">
                <SelectValue placeholder="Priority" />
              </SelectTrigger>
              <SelectContent className="bg-[#1A1A1A] border-white/[0.06]">
                <SelectItem value="all" className="text-zinc-300">All Priority</SelectItem>
                {PRIORITY_OPTIONS.map(opt => (
                  <SelectItem key={opt.value} value={opt.value} className="text-zinc-300">
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            {/* Agent Filter */}
            <input
              type="text"
              placeholder="Agent ID..."
              value={agentFilter}
              onChange={(e) => { setAgentFilter(e.target.value); setPage(1); }}
              className="h-8 w-[100px] px-2 bg-[#1A1A1A] border border-white/[0.06] rounded-lg text-xs text-zinc-300 placeholder:text-zinc-600 focus:outline-none focus:border-[#FF7F11]/50"
              title="Filter by Agent ID"
            />

            {/* Confidence Filter */}
            <Select value={confidenceFilter} onValueChange={handleConfidenceChange}>
              <SelectTrigger size="sm" className="w-[130px] bg-[#1A1A1A] border-white/[0.06] text-zinc-300 text-xs">
                <SelectValue placeholder="Confidence" />
              </SelectTrigger>
              <SelectContent className="bg-[#1A1A1A] border-white/[0.06]">
                {CONFIDENCE_OPTIONS.map(opt => (
                  <SelectItem key={opt.value} value={opt.value} className="text-zinc-300">
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            {/* Date Range */}
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => { setDateFrom(e.target.value); setPage(1); }}
              className="h-8 px-2 bg-[#1A1A1A] border border-white/[0.06] rounded-lg text-xs text-zinc-300 focus:outline-none focus:border-[#FF7F11]/50 [color-scheme:dark]"
              title="From date"
            />
            <input
              type="date"
              value={dateTo}
              onChange={(e) => { setDateTo(e.target.value); setPage(1); }}
              className="h-8 px-2 bg-[#1A1A1A] border border-white/[0.06] rounded-lg text-xs text-zinc-300 focus:outline-none focus:border-[#FF7F11]/50 [color-scheme:dark]"
              title="To date"
            />

            {hasActiveFilters && (
              <button
                onClick={clearFilters}
                className="h-8 px-3 text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
              >
                Clear all
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Bulk Action Toolbar (T6) */}
      {selectedIds.size > 0 && (
        <div className="bg-[#FF7F11]/5 border border-[#FF7F11]/20 rounded-xl p-3 mb-4 flex items-center gap-3 animate-in fade-in-0 slide-in-from-top-1 duration-200">
          <span className="text-sm text-zinc-300 font-medium">
            {selectedIds.size} selected
          </span>
          <div className="h-4 w-px bg-white/[0.06]" />
          <Button
            size="sm"
            variant="ghost"
            className="text-zinc-300 hover:text-emerald-400 hover:bg-emerald-500/10 text-xs h-7"
            onClick={() => { setBulkAction('resolve'); setBulkDialogOpen(true); }}
          >
            <CheckIcon /> Mark Resolved
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="text-zinc-300 hover:text-[#FF7F11] hover:bg-[#FF7F11]/10 text-xs h-7"
            onClick={() => { setBulkAction('priority'); setBulkDialogOpen(true); }}
          >
            Change Priority
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="text-zinc-300 hover:text-purple-400 hover:bg-purple-500/10 text-xs h-7"
            onClick={() => { setBulkAction('assign'); setBulkAgentId(''); setBulkDialogOpen(true); }}
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19.128a9.38 9.38 0 0 0 2.625.372 9.337 9.337 0 0 0 4.121-.952 4.125 4.125 0 0 0-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 0 1 8.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0 1 11.964-3.07M12 6.375a3.375 3.375 0 1 1-6.75 0 3.375 3.375 0 0 1 6.75 0Z" />
            </svg>
            Assign Agent
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="text-zinc-300 hover:text-blue-400 hover:bg-blue-500/10 text-xs h-7"
            onClick={() => {
              // Export CSV of selected ticket IDs (simple CSV download)
              const csvContent = 'Ticket ID,Status,Priority,Subject,Created At\n' +
                tickets.filter(t => selectedIds.has(t.id)).map(t =>
                  `"#${t.id.slice(0, 8)}","${t.status}","${t.priority}","${(t.subject || '').replace(/"/g, '""')}","${t.created_at}"`
                ).join('\n');
              const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
              const link = document.createElement('a');
              link.href = URL.createObjectURL(blob);
              link.download = `tickets-export-${Date.now()}.csv`;
              link.click();
              URL.revokeObjectURL(link.href);
            }}
          >
            <DownloadIcon /> Export
          </Button>
          <div className="ml-auto">
            <Button
              size="sm"
              variant="ghost"
              className="text-zinc-500 hover:text-zinc-300 text-xs h-7"
              onClick={() => setSelectedIds(new Set())}
            >
              Clear selection
            </Button>
          </div>
        </div>
      )}

      {/* Table (T4, T5) */}
      <div className="bg-[#111111] border border-white/[0.06] rounded-xl overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="border-b border-white/[0.06] hover:bg-transparent">
              {/* Select all checkbox */}
              <TableHead className="p-3 w-10">
                <Checkbox
                  checked={tickets.length > 0 && selectedIds.size === tickets.length}
                  onCheckedChange={toggleSelectAll}
                  className="border-white/[0.1] data-[state=checked]:bg-[#FF7F11] data-[state=checked]:border-[#FF7F11]"
                />
              </TableHead>

              {/* Sortable headers */}
              <TableHead className="p-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">
                <button onClick={() => handleSort('id')} className="flex items-center gap-1 hover:text-zinc-300 transition-colors">
                  ID
                  {sortBy === 'id' && (sortOrder === 'asc' ? <ArrowUpIcon /> : <ArrowDownIcon />)}
                </button>
              </TableHead>
              <TableHead className="p-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">
                <button onClick={() => handleSort('priority')} className="flex items-center gap-1 hover:text-zinc-300 transition-colors">
                  Priority
                  {sortBy === 'priority' && (sortOrder === 'asc' ? <ArrowUpIcon /> : <ArrowDownIcon />)}
                </button>
              </TableHead>
              <TableHead className="p-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">
                <button onClick={() => handleSort('status')} className="flex items-center gap-1 hover:text-zinc-300 transition-colors">
                  Status
                  {sortBy === 'status' && (sortOrder === 'asc' ? <ArrowUpIcon /> : <ArrowDownIcon />)}
                </button>
              </TableHead>
              <TableHead className="p-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">
                Subject
              </TableHead>
              <TableHead className="p-3 text-xs font-medium text-zinc-500 uppercase tracking-wider hidden md:table-cell">
                <button onClick={() => handleSort('channel')} className="flex items-center gap-1 hover:text-zinc-300 transition-colors">
                  Channel
                  {sortBy === 'channel' && (sortOrder === 'asc' ? <ArrowUpIcon /> : <ArrowDownIcon />)}
                </button>
              </TableHead>
              <TableHead className="p-3 text-xs font-medium text-zinc-500 uppercase tracking-wider hidden lg:table-cell">
                Agent
              </TableHead>
              <TableHead className="p-3 text-xs font-medium text-zinc-500 uppercase tracking-wider hidden lg:table-cell">
                Confidence
              </TableHead>
              <TableHead className="p-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">
                <button onClick={() => handleSort('created_at')} className="flex items-center gap-1 hover:text-zinc-300 transition-colors">
                  Created
                  {sortBy === 'created_at' && (sortOrder === 'asc' ? <ArrowUpIcon /> : <ArrowDownIcon />)}
                </button>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody className="divide-y divide-white/[0.04]">
            {/* Loading state */}
            {loading && <SkeletonRows />}

            {/* Error state */}
            {!loading && error && (
              <TableRow className="hover:bg-transparent">
                <TableCell colSpan={9} className="py-16 text-center">
                  <div className="flex flex-col items-center gap-3">
                    <div className="w-12 h-12 rounded-full bg-red-500/10 flex items-center justify-center">
                      <svg className="w-6 h-6 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
                      </svg>
                    </div>
                    <p className="text-sm text-red-400">{error}</p>
                    <Button size="sm" variant="ghost" onClick={fetchTickets} className="text-zinc-400 hover:text-zinc-200">
                      <RefreshIcon /> Retry
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            )}

            {/* Empty state */}
            {!loading && !error && tickets.length === 0 && (
              <TableRow className="hover:bg-transparent">
                <TableCell colSpan={9} className="py-16 text-center">
                  <div className="flex flex-col items-center gap-3">
                    <div className="w-16 h-16 rounded-2xl bg-zinc-800/50 flex items-center justify-center text-zinc-600">
                      <EmptyTicketIcon />
                    </div>
                    <p className="text-sm text-zinc-400 font-medium">No tickets found</p>
                    <p className="text-xs text-zinc-600 max-w-xs">
                      {hasActiveFilters
                        ? 'Try adjusting your filters to find what you\'re looking for.'
                        : 'Tickets will appear here when new support requests come in.'}
                    </p>
                    {hasActiveFilters && (
                      <Button size="sm" variant="ghost" onClick={clearFilters} className="text-zinc-400 hover:text-zinc-200">
                        <FilterIcon /> Clear Filters
                      </Button>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            )}

            {/* Ticket Rows (T5) */}
            {!loading && !error && tickets.map((ticket) => {
              const isSelected = selectedIds.has(ticket.id);
              const isHighlighted = highlightedId === ticket.id;
              const chInfo = CHANNEL_ICONS[ticket.channel] || { icon: '?', color: 'text-zinc-400' };
              const confidence = ticket.metadata_json?.confidence as number | null;

              return (
                <TableRow
                  key={ticket.id}
                  className={`
                    cursor-pointer group transition-all
                    ${isHighlighted ? 'bg-[#FF7F11]/5' : 'hover:bg-white/[0.02]'}
                    ${isSelected ? 'bg-[#FF7F11]/8' : ''}
                  `}
                  onClick={() => router.push(`/dashboard/tickets/${ticket.id}`)}
                  data-ticket-id={ticket.id}
                >
                  {/* Checkbox */}
                  <TableCell className="p-3" onClick={(e) => e.stopPropagation()}>
                    <Checkbox
                      checked={isSelected}
                      onCheckedChange={() => toggleSelect(ticket.id)}
                      className="border-white/[0.1] data-[state=checked]:bg-[#FF7F11] data-[state=checked]:border-[#FF7F11]"
                    />
                  </TableCell>

                  {/* ID */}
                  <TableCell className="p-3">
                    <span className="text-sm font-medium text-[#FF7F11] group-hover:text-[#FF9F40] transition-colors">
                      #{ticket.id.slice(0, 8)}
                    </span>
                  </TableCell>

                  {/* Priority Badge */}
                  <TableCell className="p-3">
                    <Badge
                      variant="outline"
                      className={`text-[10px] font-semibold uppercase tracking-wide ${PRIORITY_STYLES[ticket.priority] || 'bg-zinc-700 text-zinc-400 border-zinc-700'}`}
                    >
                      {ticket.priority}
                    </Badge>
                  </TableCell>

                  {/* Status Badge */}
                  <TableCell className="p-3">
                    <Badge
                      variant="outline"
                      className={`text-[10px] font-medium ${STATUS_STYLES[ticket.status] || 'bg-zinc-700 text-zinc-400 border-zinc-700'}`}
                    >
                      {ticket.frozen && (
                        <span className="mr-1" title="Frozen">❄</span>
                      )}
                      {formatStatus(ticket.status)}
                    </Badge>
                  </TableCell>

                  {/* Subject + Quick View Popover (T8) */}
                  <TableCell className="p-3 max-w-[300px]">
                    <Popover open={hoveredTicketId === ticket.id} onOpenChange={(open) => {
                      if (!open) setHoveredTicketId(null);
                    }}>
                      <PopoverTrigger asChild>
                        <div
                          className="cursor-default"
                          onMouseEnter={() => {
                            if (hoverTimeoutRef.current) clearTimeout(hoverTimeoutRef.current);
                            hoverTimeoutRef.current = setTimeout(() => {
                              setHoveredTicketId(ticket.id);
                            }, 500);
                          }}
                          onMouseLeave={() => {
                            if (hoverTimeoutRef.current) clearTimeout(hoverTimeoutRef.current);
                            hoverTimeoutRef.current = setTimeout(() => {
                              setHoveredTicketId(null);
                            }, 200);
                          }}
                        >
                          <p className="text-sm text-zinc-200 truncate">{ticket.subject || '(No subject)'}</p>
                          {ticket.tags && ticket.tags.length > 0 && (
                            <div className="flex gap-1 mt-0.5 flex-wrap">
                              {ticket.tags.slice(0, 3).map(tag => (
                                <span key={tag} className="text-[10px] px-1.5 py-0 rounded bg-zinc-800 text-zinc-500">
                                  {tag}
                                </span>
                              ))}
                              {ticket.tags.length > 3 && (
                                <span className="text-[10px] text-zinc-600">+{ticket.tags.length - 3}</span>
                              )}
                            </div>
                          )}
                        </div>
                      </PopoverTrigger>
                      <PopoverContent
                        className="w-[300px] bg-[#1A1A1A] border-white/[0.06] p-4 text-zinc-200 shadow-xl"
                        side="bottom"
                        align="start"
                        sideOffset={4}
                        onMouseEnter={() => {
                          if (hoverTimeoutRef.current) clearTimeout(hoverTimeoutRef.current);
                        }}
                        onMouseLeave={() => {
                          if (hoverTimeoutRef.current) clearTimeout(hoverTimeoutRef.current);
                          setHoveredTicketId(null);
                        }}
                      >
                        <div className="space-y-3">
                          <div>
                            <p className="text-sm font-medium text-zinc-100 truncate">{ticket.subject || '(No subject)'}</p>
                          </div>
                          <div className="grid grid-cols-2 gap-2 text-xs">
                            <div>
                              <span className="text-zinc-500">Customer</span>
                              <p className="text-zinc-300 truncate mt-0.5">{ticket.customer_id?.slice(0, 12) || '\u2014'}</p>
                            </div>
                            <div>
                              <span className="text-zinc-500">Channel</span>
                              <p className="text-zinc-300 flex items-center gap-1 mt-0.5 capitalize">
                                <span>{CHANNEL_ICONS[ticket.channel]?.icon || '?'}</span>
                                {ticket.channel}
                              </p>
                            </div>
                            <div>
                              <span className="text-zinc-500">Priority</span>
                              <div className="mt-0.5">
                                <Badge variant="outline" className={`text-[10px] font-semibold uppercase ${PRIORITY_STYLES[ticket.priority] || ''}`}>
                                  {ticket.priority}
                                </Badge>
                              </div>
                            </div>
                            <div>
                              <span className="text-zinc-500">Status</span>
                              <div className="mt-0.5">
                                <Badge variant="outline" className={`text-[10px] font-medium ${STATUS_STYLES[ticket.status] || ''}`}>
                                  {formatStatus(ticket.status)}
                                </Badge>
                              </div>
                            </div>
                            <div>
                              <span className="text-zinc-500">AI Confidence</span>
                              <div className="mt-0.5">
                                <ConfidenceBar confidence={ticket.metadata_json?.confidence as number | null} />
                              </div>
                            </div>
                            <div>
                              <span className="text-zinc-500">Created</span>
                              <p className="text-zinc-300 mt-0.5">{relativeTime(ticket.created_at)}</p>
                            </div>
                          </div>
                        </div>
                      </PopoverContent>
                    </Popover>
                  </TableCell>

                  {/* Channel (hidden on mobile) */}
                  <TableCell className="p-3 hidden md:table-cell">
                    <span className={`inline-flex items-center gap-1.5 text-xs capitalize ${chInfo.color}`}>
                      <span>{chInfo.icon}</span>
                      {ticket.channel}
                    </span>
                  </TableCell>

                  {/* Agent (hidden on small screens) */}
                  <TableCell className="p-3 hidden lg:table-cell">
                    <span className="text-xs text-zinc-400">
                      {ticket.assigned_to || ticket.agent_id ? (ticket.assigned_to || ticket.agent_id)?.slice(0, 8) : '\u2014'}
                    </span>
                  </TableCell>

                  {/* Confidence (hidden on small screens) */}
                  <TableCell className="p-3 hidden lg:table-cell">
                    <ConfidenceBar confidence={confidence} />
                  </TableCell>

                  {/* Time Ago */}
                  <TableCell className="p-3">
                    <span className="text-xs text-zinc-500 whitespace-nowrap">
                      {ticket.time_since_updated || relativeTime(ticket.updated_at || ticket.created_at)}
                    </span>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>

      {/* Pagination (T1) */}
      {pages > 1 && (
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between mt-4 gap-3">
          <p className="text-xs text-zinc-500">
            Showing {(page - 1) * PAGE_SIZE + 1}&ndash;{Math.min(page * PAGE_SIZE, total)} of {total} results
          </p>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="sm"
              className="text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.04] h-8 px-2"
              disabled={page === 1}
              onClick={() => setPage(1)}
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="m18.75 19.5-7.5-7.5 7.5-7.5m-6 15L5.25 12l7.5-7.5" />
              </svg>
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.04] h-8 px-2"
              disabled={page === 1}
              onClick={() => setPage(p => Math.max(1, p - 1))}
            >
              <ChevronLeftIcon />
            </Button>
            {getVisiblePages().map((p, i) =>
              p === -1 ? (
                <span key={`ellipsis-${i}`} className="px-2 text-xs text-zinc-600">...</span>
              ) : (
                <Button
                  key={p}
                  variant={p === page ? 'default' : 'ghost'}
                  size="sm"
                  className={
                    p === page
                      ? 'bg-[#FF7F11] text-white hover:bg-[#FF7F11]/90 h-8 w-8 p-0'
                      : 'text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.04] h-8 w-8 p-0'
                  }
                  onClick={() => setPage(p)}
                >
                  {p}
                </Button>
              )
            )}
            <Button
              variant="ghost"
              size="sm"
              className="text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.04] h-8 px-2"
              disabled={page === pages}
              onClick={() => setPage(p => Math.min(pages, p + 1))}
            >
              <ChevronRightIcon />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.04] h-8 px-2"
              disabled={page === pages}
              onClick={() => setPage(pages)}
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="m11.25 4.5 7.5 7.5-7.5 7.5m6-15L13.5 12l6 6" />
              </svg>
            </Button>
          </div>
        </div>
      )}

      {/* Bulk Action Dialog */}
      <Dialog open={bulkDialogOpen} onOpenChange={setBulkDialogOpen}>
        <DialogContent className="bg-[#1A1A1A] border-white/[0.06] text-zinc-200">
          <DialogHeader>
            <DialogTitle className="text-zinc-100">
              {bulkAction === 'resolve' ? 'Mark as Resolved' : bulkAction === 'priority' ? 'Change Priority' : 'Assign Agent'}
            </DialogTitle>
            <DialogDescription className="text-zinc-500">
              This action will be applied to {selectedIds.size} selected ticket{selectedIds.size !== 1 ? 's' : ''}.
            </DialogDescription>
          </DialogHeader>

          {bulkAction === 'priority' && (
            <div className="py-2">
              <label className="text-xs font-medium text-zinc-400 block mb-1.5">New Priority</label>
              <Select value={bulkPriority} onValueChange={setBulkPriority}>
                <SelectTrigger className="bg-[#111111] border-white/[0.06] text-zinc-300">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-[#1A1A1A] border-white/[0.06]">
                  {PRIORITY_OPTIONS.map(opt => (
                    <SelectItem key={opt.value} value={opt.value} className="text-zinc-300">
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {bulkAction === 'assign' && (
            <div className="py-2">
              <label className="text-xs font-medium text-zinc-400 block mb-1.5">Agent ID</label>
              <input
                type="text"
                placeholder="Enter Agent ID..."
                value={bulkAgentId}
                onChange={(e) => setBulkAgentId(e.target.value)}
                className="w-full px-3 py-2 bg-[#111111] border border-white/[0.06] rounded-lg text-sm text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-[#FF7F11]/50"
              />
            </div>
          )}

          {bulkError && (
            <p className="text-xs text-red-400">{bulkError}</p>
          )}

          <DialogFooter>
            <Button
              variant="ghost"
              size="sm"
              className="text-zinc-400 hover:text-zinc-200"
              onClick={() => setBulkDialogOpen(false)}
              disabled={bulkLoading}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              className="bg-[#FF7F11] text-white hover:bg-[#FF7F11]/90"
              onClick={handleBulkAction}
              disabled={bulkLoading}
            >
              {bulkLoading ? 'Applying...' : `Apply to ${selectedIds.size} ticket${selectedIds.size !== 1 ? 's' : ''}`}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
