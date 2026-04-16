'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { dashboardApi, type BlockedResponse, type ApprovalDetail, type ApprovalQueueStats } from '@/lib/dashboard-api';
import { useSocket } from '@/contexts/SocketContext';
import { getErrorMessage } from '@/lib/api';
import {
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell,
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Skeleton } from '@/components/ui/skeleton';
import { Textarea } from '@/components/ui/textarea';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '@/components/ui/dialog';

// ── Constants ───────────────────────────────────────────────────────────

const PAGE_SIZE = 20;

const STATUS_TABS: { value: string; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'pending', label: 'Pending' },
  { value: 'in_review', label: 'In Review' },
  { value: 'approved', label: 'Approved' },
  { value: 'rejected', label: 'Rejected' },
  { value: 'auto_rejected', label: 'Auto Rejected' },
  { value: 'expired', label: 'Expired' },
];

const PRIORITY_OPTIONS: { value: string; label: string }[] = [
  { value: 'all', label: 'All Priority' },
  { value: 'urgent', label: 'Urgent' },
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
];

const BLOCK_REASON_OPTIONS: { value: string; label: string }[] = [
  { value: 'all', label: 'All Reasons' },
  { value: 'low_confidence', label: 'Low Confidence' },
  { value: 'guardrail_blocked', label: 'Guardrail Blocked' },
  { value: 'pii_leak', label: 'PII Leak' },
  { value: 'hallucination', label: 'Hallucination' },
  { value: 'prompt_injection', label: 'Prompt Injection' },
  { value: 'content_safety', label: 'Content Safety' },
  { value: 'policy_violation', label: 'Policy Violation' },
  { value: 'tone_violation', label: 'Tone Violation' },
  { value: 'length_violation', label: 'Length Violation' },
  { value: 'topic_irrelevance', label: 'Topic Irrelevance' },
  { value: 'custom_rule', label: 'Custom Rule' },
  { value: 'timeout', label: 'Timeout' },
];

// ── Color Maps ──────────────────────────────────────────────────────────

const PRIORITY_DOT_COLORS: Record<string, string> = {
  urgent: 'bg-red-500',
  high: 'bg-orange-500',
  medium: 'bg-amber-500',
  low: 'bg-zinc-500',
};

const PRIORITY_STYLES: Record<string, string> = {
  urgent: 'bg-red-500/15 text-red-400 border-red-500/20',
  high: 'bg-orange-500/15 text-orange-400 border-orange-500/20',
  medium: 'bg-amber-500/15 text-amber-400 border-amber-500/20',
  low: 'bg-zinc-600/15 text-zinc-400 border-zinc-600/20',
};

const STATUS_STYLES: Record<string, string> = {
  pending: 'bg-orange-500/15 text-orange-400 border-orange-500/20',
  in_review: 'bg-blue-500/15 text-blue-400 border-blue-500/20',
  approved: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20',
  rejected: 'bg-red-500/15 text-red-400 border-red-500/20',
  auto_rejected: 'bg-zinc-600/15 text-zinc-500 border-zinc-600/20',
  expired: 'bg-zinc-600/15 text-zinc-500 border-zinc-600/20',
};

const BLOCK_REASON_STYLES: Record<string, string> = {
  low_confidence: 'bg-amber-500/15 text-amber-400 border-amber-500/20',
  guardrail_blocked: 'bg-violet-500/15 text-violet-400 border-violet-500/20',
  pii_leak: 'bg-red-500/15 text-red-400 border-red-500/20',
  hallucination: 'bg-pink-500/15 text-pink-400 border-pink-500/20',
  prompt_injection: 'bg-rose-500/15 text-rose-400 border-rose-500/20',
  content_safety: 'bg-orange-500/15 text-orange-400 border-orange-500/20',
  policy_violation: 'bg-red-500/15 text-red-400 border-red-500/20',
  tone_violation: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/20',
  length_violation: 'bg-cyan-500/15 text-cyan-400 border-cyan-500/20',
  topic_irrelevance: 'bg-teal-500/15 text-teal-400 border-teal-500/20',
  custom_rule: 'bg-indigo-500/15 text-indigo-400 border-indigo-500/20',
  timeout: 'bg-zinc-600/15 text-zinc-400 border-zinc-600/20',
};

// ── Helper: Relative Time ───────────────────────────────────────────────

function relativeTime(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffSec = Math.round((now - then) / 1000);
  if (diffSec < 0) return 'just now';
  if (diffSec < 60) return `${diffSec}s ago`;
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
  if (diffSec < 2592000) return `${Math.floor(diffSec / 86400)}d ago`;
  return new Date(dateStr).toLocaleDateString();
}

function formatBlockReason(reason: string): string {
  return reason
    .replace(/_/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase());
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

const RefreshIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182" />
  </svg>
);

const CheckIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
  </svg>
);

const XIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
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

const AlertTriangleIcon = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
  </svg>
);

const CheckCircleIcon = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
  </svg>
);

const ClockIcon = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
  </svg>
);

const ArrowUpIcon = () => (
  <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 19.5v-15m0 0-6.75 6.75M12 4.5l6.75 6.75" />
  </svg>
);

const ShieldCheckIcon = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75m-3-7.036A11.959 11.959 0 0 1 3.598 6 11.99 11.99 0 0 0 3 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285Z" />
  </svg>
);

const AllCaughtUpIcon = () => (
  <svg className="w-16 h-16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12c0 1.268-.63 2.39-1.593 3.068a3.745 3.745 0 0 1-1.043 3.296 3.745 3.745 0 0 1-3.296 1.043A3.745 3.745 0 0 1 12 21c-1.268 0-2.39-.63-3.068-1.593a3.746 3.746 0 0 1-3.296-1.043 3.745 3.745 0 0 1-1.043-3.296A3.745 3.745 0 0 1 3 12c0-1.268.63-2.39 1.593-3.068a3.745 3.745 0 0 1 1.043-3.296 3.746 3.746 0 0 1 3.296-1.043A3.746 3.746 0 0 1 12 3c1.268 0 2.39.63 3.068 1.593a3.746 3.746 0 0 1 3.296 1.043 3.746 3.746 0 0 1 1.043 3.296A3.745 3.745 0 0 1 21 12Z" />
  </svg>
);

const SpinnerIcon = ({ className = 'w-4 h-4' }: { className?: string }) => (
  <svg className={`animate-spin ${className}`} fill="none" viewBox="0 0 24 24">
    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
  </svg>
);

// ── Confidence Bar ──────────────────────────────────────────────────────

function ConfidenceBar({ confidence }: { confidence: number }) {
  const color = confidence >= 75 ? 'bg-emerald-500' : confidence >= 50 ? 'bg-amber-500' : 'bg-red-500';
  const textColor = confidence >= 75 ? 'text-emerald-400' : confidence >= 50 ? 'text-amber-400' : 'text-red-400';
  return (
    <div className="flex items-center gap-2 min-w-[80px]">
      <div className="flex-1 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color} transition-all`} style={{ width: `${Math.min(confidence, 100)}%` }} />
      </div>
      <span className={`text-xs font-medium ${textColor} w-8 text-right`}>{confidence}%</span>
    </div>
  );
}

// ── Skeleton Helpers ────────────────────────────────────────────────────

function StatCardSkeleton() {
  return (
    <div className="bg-zinc-900/50 border border-white/[0.06] rounded-xl p-4">
      <div className="flex items-center justify-between mb-3">
        <Skeleton className="h-8 w-8 rounded-lg" />
        <Skeleton className="h-3 w-12" />
      </div>
      <Skeleton className="h-7 w-16 mb-1" />
      <Skeleton className="h-3 w-24" />
    </div>
  );
}

function SkeletonRows() {
  return (
    <>
      {Array.from({ length: 6 }).map((_, i) => (
        <TableRow key={i} className="hover:bg-transparent">
          <TableCell className="p-3"><Skeleton className="h-4 w-4" /></TableCell>
          <TableCell className="p-3"><Skeleton className="h-3 w-3 rounded-full" /></TableCell>
          <TableCell className="p-3"><Skeleton className="h-4 w-48" /></TableCell>
          <TableCell className="p-3"><Skeleton className="h-5 w-20 rounded-full" /></TableCell>
          <TableCell className="p-3"><Skeleton className="h-4 w-16" /></TableCell>
          <TableCell className="p-3"><Skeleton className="h-5 w-16 rounded-full" /></TableCell>
          <TableCell className="p-3"><Skeleton className="h-4 w-28" /></TableCell>
          <TableCell className="p-3"><Skeleton className="h-4 w-16" /></TableCell>
          <TableCell className="p-3"><Skeleton className="h-6 w-16 rounded" /></TableCell>
        </TableRow>
      ))}
    </>
  );
}

// ── Main Component ──────────────────────────────────────────────────────

export default function ApprovalsPage() {
  const { socket, badgeCounts } = useSocket();

  // Data state
  const [approvals, setApprovals] = useState<BlockedResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isConnecting, setIsConnecting] = useState(false);

  // Stats state
  const [stats, setStats] = useState<ApprovalQueueStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);

  // Filter state
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [priorityFilter, setPriorityFilter] = useState<string>('all');
  const [blockReasonFilter, setBlockReasonFilter] = useState<string>('all');

  // Selection state
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [batchAction, setBatchAction] = useState<'approved' | 'rejected' | null>(null);
  const [batchNotes, setBatchNotes] = useState('');
  const [batchLoading, setBatchLoading] = useState(false);
  const [batchError, setBatchError] = useState<string | null>(null);

  // Detail modal state
  const [detailItem, setDetailItem] = useState<BlockedResponse | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [detailNotes, setDetailNotes] = useState('');
  const [detailEditedResponse, setDetailEditedResponse] = useState('');
  const [showEditResponse, setShowEditResponse] = useState(false);
  const [detailActionLoading, setDetailActionLoading] = useState(false);

  // ── Fetch Approvals ──────────────────────────────────────────────────

  const fetchApprovals = useCallback(async () => {
    setLoading(true);
    setError(null);
    setIsConnecting(false);
    try {
      const params: Record<string, unknown> = {
        page,
        page_size: PAGE_SIZE,
      };
      if (statusFilter !== 'all') params.status = statusFilter;
      if (priorityFilter !== 'all') params.priority = priorityFilter;
      if (blockReasonFilter !== 'all') params.blockReason = blockReasonFilter;
      if (search) params.search = search;

      const data = await dashboardApi.getApprovals(params as Parameters<typeof dashboardApi.getApprovals>[0]);
      setApprovals(data.items || []);
      setTotal(data.total || 0);
    } catch (err: any) {
      const msg = getErrorMessage(err);
      // If 404, backend doesn't exist yet
      if (msg.includes('404') || err?.response?.status === 404) {
        setIsConnecting(true);
        setApprovals([]);
        setTotal(0);
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  }, [page, statusFilter, priorityFilter, blockReasonFilter, search]);

  // ── Fetch Stats ──────────────────────────────────────────────────────

  const fetchStats = useCallback(async () => {
    setStatsLoading(true);
    try {
      const data = await dashboardApi.getApprovalStats();
      setStats(data);
    } catch {
      // Stats are optional — don't show error
    } finally {
      setStatsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchApprovals();
  }, [fetchApprovals]);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  // ── Debounced Search ─────────────────────────────────────────────────

  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(searchInput);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchInput]);

  // ── Real-time Socket Updates ─────────────────────────────────────────

  useEffect(() => {
    if (!socket) return;

    const handleApprovalPending = () => {
      fetchApprovals();
      fetchStats();
    };

    const handleApprovalApproved = () => {
      fetchApprovals();
      fetchStats();
    };

    const handleApprovalRejected = () => {
      fetchApprovals();
      fetchStats();
    };

    socket.on('approval:pending', handleApprovalPending);
    socket.on('approval:approved', handleApprovalApproved);
    socket.on('approval:rejected', handleApprovalRejected);

    return () => {
      socket.off('approval:pending', handleApprovalPending);
      socket.off('approval:approved', handleApprovalApproved);
      socket.off('approval:rejected', handleApprovalRejected);
    };
  }, [socket, fetchApprovals, fetchStats]);

  // ── Filter Handlers ──────────────────────────────────────────────────

  const handleStatusChange = (value: string) => { setStatusFilter(value); setPage(1); };
  const handlePriorityChange = (value: string) => { setPriorityFilter(value); setPage(1); };
  const handleBlockReasonChange = (value: string) => { setBlockReasonFilter(value); setPage(1); };

  const clearFilters = () => {
    setSearchInput('');
    setSearch('');
    setStatusFilter('all');
    setPriorityFilter('all');
    setBlockReasonFilter('all');
    setPage(1);
  };

  const hasActiveFilters = search || statusFilter !== 'all' || priorityFilter !== 'all' || blockReasonFilter !== 'all';

  // ── Selection Handlers ───────────────────────────────────────────────

  const toggleSelect = (id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === approvals.length && approvals.length > 0) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(approvals.map(a => a.id)));
    }
  };

  // ── Batch Actions ────────────────────────────────────────────────────

  const handleBatchAction = async () => {
    if (!batchAction || selectedIds.size === 0) return;
    setBatchLoading(true);
    setBatchError(null);
    try {
      await dashboardApi.batchReview({
        ids: Array.from(selectedIds),
        action: batchAction,
        review_notes: batchNotes || undefined,
      });
      setBatchAction(null);
      setBatchNotes('');
      setSelectedIds(new Set());
      fetchApprovals();
      fetchStats();
    } catch (err) {
      setBatchError(getErrorMessage(err));
    } finally {
      setBatchLoading(false);
    }
  };

  // ── Detail Modal ─────────────────────────────────────────────────────

  const openDetail = async (item: BlockedResponse) => {
    setDetailItem(item);
    setDetailLoading(true);
    setDetailError(null);
    setDetailNotes('');
    setDetailEditedResponse(item.original_response);
    setShowEditResponse(false);
    try {
      const detail = await dashboardApi.getApproval(item.id);
      setDetailItem(detail);
    } catch {
      // Use the list item as fallback
    } finally {
      setDetailLoading(false);
    }
  };

  const closeDetail = () => {
    setDetailItem(null);
    setDetailError(null);
    setDetailNotes('');
    setDetailEditedResponse('');
    setShowEditResponse(false);
  };

  const handleApprove = async () => {
    if (!detailItem) return;
    setDetailActionLoading(true);
    try {
      const payload: { review_notes?: string; edited_response?: string } = { review_notes: detailNotes || undefined };
      if (showEditResponse && detailEditedResponse.trim()) {
        payload.edited_response = detailEditedResponse.trim();
      }
      await dashboardApi.approveResponse(detailItem.id, payload);
      closeDetail();
      fetchApprovals();
      fetchStats();
    } catch (err) {
      setDetailError(getErrorMessage(err));
    } finally {
      setDetailActionLoading(false);
    }
  };

  const handleReject = async () => {
    if (!detailItem) return;
    setDetailActionLoading(true);
    try {
      await dashboardApi.rejectResponse(detailItem.id, { review_notes: detailNotes || undefined });
      closeDetail();
      fetchApprovals();
      fetchStats();
    } catch (err) {
      setDetailError(getErrorMessage(err));
    } finally {
      setDetailActionLoading(false);
    }
  };

  const handleEscalate = async () => {
    if (!detailItem) return;
    setDetailActionLoading(true);
    try {
      await dashboardApi.escalateResponse(detailItem.id, { review_notes: detailNotes || undefined });
      closeDetail();
      fetchApprovals();
      fetchStats();
    } catch (err) {
      setDetailError(getErrorMessage(err));
    } finally {
      setDetailActionLoading(false);
    }
  };

  // ── Pagination ───────────────────────────────────────────────────────

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const getVisiblePages = () => {
    if (totalPages <= 7) return Array.from({ length: totalPages }, (_, i) => i + 1);
    const start = Math.max(1, page - 2);
    const end = Math.min(totalPages, page + 2);
    const visible: number[] = [];
    if (start > 1) { visible.push(1); if (start > 2) visible.push(-1); }
    for (let i = start; i <= end; i++) visible.push(i);
    if (end < totalPages) { if (end < totalPages - 1) visible.push(-1); visible.push(totalPages); }
    return visible;
  };

  // ── Is Pending Filter ────────────────────────────────────────────────

  const isShowingPendingOnly = statusFilter === 'pending' || statusFilter === 'in_review';

  // ── Render ───────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-[#0D0D0D] p-4 md:p-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-zinc-100">Approvals</h1>
          <p className="text-sm text-zinc-500 mt-0.5">
            {loading ? 'Loading...' : `${total} item${total !== 1 ? 's' : ''} in queue`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            className="text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.04]"
            onClick={() => { fetchApprovals(); fetchStats(); }}
          >
            <RefreshIcon />
            Refresh
          </Button>
        </div>
      </div>

      {/* ── Stats Strip ──────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {statsLoading ? (
          <>
            <StatCardSkeleton />
            <StatCardSkeleton />
            <StatCardSkeleton />
            <StatCardSkeleton />
          </>
        ) : (
          <>
            {/* Pending */}
            <div className="bg-zinc-900/50 border border-white/[0.06] rounded-xl p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="w-8 h-8 rounded-lg bg-orange-500/15 flex items-center justify-center">
                  <AlertTriangleIcon />
                </div>
                {(stats?.urgent_count || 0) > 0 && (
                  <span className="text-[10px] font-medium text-red-400 bg-red-500/10 px-1.5 py-0.5 rounded">
                    {(stats?.urgent_count || 0)} urgent
                  </span>
                )}
              </div>
              <p className="text-2xl font-semibold text-orange-400">
                {stats?.total_pending ?? badgeCounts.approvals ?? 0}
              </p>
              <p className="text-xs text-zinc-500 mt-1">Pending Review</p>
            </div>

            {/* In Review */}
            <div className="bg-zinc-900/50 border border-white/[0.06] rounded-xl p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="w-8 h-8 rounded-lg bg-blue-500/15 flex items-center justify-center">
                  <ClockIcon />
                </div>
                <span className="text-[10px] font-medium text-zinc-500 bg-zinc-800 px-1.5 py-0.5 rounded">
                  {(stats?.avg_wait_time_minutes ?? 0).toFixed(0)}m avg
                </span>
              </div>
              <p className="text-2xl font-semibold text-blue-400">
                {stats?.total_in_review ?? 0}
              </p>
              <p className="text-xs text-zinc-500 mt-1">In Review</p>
            </div>

            {/* Approved */}
            <div className="bg-zinc-900/50 border border-white/[0.06] rounded-xl p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="w-8 h-8 rounded-lg bg-emerald-500/15 flex items-center justify-center">
                  <CheckCircleIcon />
                </div>
                <span className="flex items-center gap-0.5 text-[10px] font-medium text-emerald-400">
                  <ArrowUpIcon />
                  approved
                </span>
              </div>
              <p className="text-2xl font-semibold text-emerald-400">
                {stats?.total_approved ?? 0}
              </p>
              <p className="text-xs text-zinc-500 mt-1">Approved</p>
            </div>

            {/* Rejected */}
            <div className="bg-zinc-900/50 border border-white/[0.06] rounded-xl p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="w-8 h-8 rounded-lg bg-red-500/15 flex items-center justify-center">
                  <XIcon />
                </div>
                {stats?.total_auto_rejected !== undefined && (stats.total_auto_rejected ?? 0) > 0 && (
                  <span className="text-[10px] font-medium text-zinc-500 bg-zinc-800 px-1.5 py-0.5 rounded">
                    {stats.total_auto_rejected} auto
                  </span>
                )}
              </div>
              <p className="text-2xl font-semibold text-red-400">
                {stats?.total_rejected ?? 0}
              </p>
              <p className="text-xs text-zinc-500 mt-1">Rejected</p>
            </div>
          </>
        )}
      </div>

      {/* ── Filter Bar ───────────────────────────────────────────────── */}
      <div className="bg-[#111111] border border-white/[0.06] rounded-xl p-4 mb-4">
        <div className="flex flex-col lg:flex-row lg:items-center gap-3">
          {/* Status Tabs */}
          <div className="flex items-center gap-1 overflow-x-auto pb-1 lg:pb-0">
            {STATUS_TABS.map(tab => (
              <button
                key={tab.value}
                onClick={() => handleStatusChange(tab.value)}
                className={`whitespace-nowrap px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
                  statusFilter === tab.value
                    ? 'bg-orange-500/15 text-orange-400'
                    : 'text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.04]'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <div className="h-4 w-px bg-white/[0.06] hidden lg:block" />

          {/* Filter Dropdowns */}
          <div className="flex flex-wrap items-center gap-2">
            <Select value={priorityFilter} onValueChange={handlePriorityChange}>
              <SelectTrigger size="sm" className="w-[130px] bg-[#1A1A1A] border-white/[0.06] text-zinc-300 text-xs">
                <SelectValue placeholder="Priority" />
              </SelectTrigger>
              <SelectContent className="bg-[#1A1A1A] border-white/[0.06]">
                {PRIORITY_OPTIONS.map(opt => (
                  <SelectItem key={opt.value} value={opt.value} className="text-zinc-300">
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select value={blockReasonFilter} onValueChange={handleBlockReasonChange}>
              <SelectTrigger size="sm" className="w-[150px] bg-[#1A1A1A] border-white/[0.06] text-zinc-300 text-xs">
                <SelectValue placeholder="Block Reason" />
              </SelectTrigger>
              <SelectContent className="bg-[#1A1A1A] border-white/[0.06]">
                {BLOCK_REASON_OPTIONS.map(opt => (
                  <SelectItem key={opt.value} value={opt.value} className="text-zinc-300">
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            {/* Search */}
            <div className="relative">
              <div className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500">
                <SearchIcon />
              </div>
              <input
                type="text"
                placeholder="Search queries..."
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                className="w-[180px] lg:w-[200px] pl-9 pr-4 py-2 bg-[#1A1A1A] border border-white/[0.06] rounded-lg text-sm text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-orange-500/50 transition-colors"
              />
            </div>

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

      {/* ── Batch Action Bar ─────────────────────────────────────────── */}
      {selectedIds.size > 0 && (
        <div className="bg-orange-500/5 border border-orange-500/20 rounded-xl p-3 mb-4 flex items-center gap-3 animate-in fade-in-0 slide-in-from-top-1 duration-200">
          <span className="text-sm text-zinc-300 font-medium">
            {selectedIds.size} selected
          </span>
          <div className="h-4 w-px bg-white/[0.06]" />
          <Button
            size="sm"
            variant="ghost"
            className="text-zinc-300 hover:text-emerald-400 hover:bg-emerald-500/10 text-xs h-7"
            onClick={() => { setBatchAction('approved'); setBatchError(null); }}
          >
            <CheckIcon /> Approve Selected
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="text-zinc-300 hover:text-red-400 hover:bg-red-500/10 text-xs h-7"
            onClick={() => { setBatchAction('rejected'); setBatchError(null); }}
          >
            <XIcon /> Reject Selected
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

      {/* ── Table ────────────────────────────────────────────────────── */}
      <div className="bg-[#111111] border border-white/[0.06] rounded-xl overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="border-b border-white/[0.06] hover:bg-transparent">
              <TableHead className="p-3 w-10">
                <Checkbox
                  checked={approvals.length > 0 && selectedIds.size === approvals.length}
                  onCheckedChange={toggleSelectAll}
                  className="border-white/[0.1] data-[state=checked]:bg-orange-500 data-[state=checked]:border-orange-500"
                />
              </TableHead>
              <TableHead className="p-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">
                Priority
              </TableHead>
              <TableHead className="p-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">
                Query
              </TableHead>
              <TableHead className="p-3 text-xs font-medium text-zinc-500 uppercase tracking-wider hidden md:table-cell">
                Block Reason
              </TableHead>
              <TableHead className="p-3 text-xs font-medium text-zinc-500 uppercase tracking-wider hidden md:table-cell">
                Confidence
              </TableHead>
              <TableHead className="p-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">
                Status
              </TableHead>
              <TableHead className="p-3 text-xs font-medium text-zinc-500 uppercase tracking-wider hidden lg:table-cell">
                Agent Response
              </TableHead>
              <TableHead className="p-3 text-xs font-medium text-zinc-500 uppercase tracking-wider hidden lg:table-cell">
                Created
              </TableHead>
              <TableHead className="p-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">
                Actions
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody className="divide-y divide-white/[0.04]">
            {/* Loading state */}
            {loading && <SkeletonRows />}

            {/* Connecting state (404) */}
            {!loading && isConnecting && (
              <TableRow className="hover:bg-transparent">
                <TableCell colSpan={9} className="py-16 text-center">
                  <div className="flex flex-col items-center gap-3">
                    <div className="w-12 h-12 rounded-full bg-orange-500/10 flex items-center justify-center">
                      <SpinnerIcon className="w-6 h-6 text-orange-400" />
                    </div>
                    <p className="text-sm text-orange-400 font-medium">Approval system connecting...</p>
                    <p className="text-xs text-zinc-600 max-w-xs">
                      The approval review queue is being initialized. This page will update automatically once ready.
                    </p>
                  </div>
                </TableCell>
              </TableRow>
            )}

            {/* Error state */}
            {!loading && !isConnecting && error && (
              <TableRow className="hover:bg-transparent">
                <TableCell colSpan={9} className="py-16 text-center">
                  <div className="flex flex-col items-center gap-3">
                    <div className="w-12 h-12 rounded-full bg-red-500/10 flex items-center justify-center">
                      <AlertTriangleIcon />
                    </div>
                    <p className="text-sm text-red-400">{error}</p>
                    <Button size="sm" variant="ghost" onClick={fetchApprovals} className="text-zinc-400 hover:text-zinc-200">
                      <RefreshIcon /> Retry
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            )}

            {/* Empty state */}
            {!loading && !isConnecting && !error && approvals.length === 0 && (
              <TableRow className="hover:bg-transparent">
                <TableCell colSpan={9} className="py-16 text-center">
                  <div className="flex flex-col items-center gap-3">
                    <div className="w-20 h-20 rounded-2xl bg-emerald-500/10 flex items-center justify-center text-emerald-500/40">
                      <AllCaughtUpIcon />
                    </div>
                    <p className="text-sm text-zinc-300 font-medium">
                      {isShowingPendingOnly ? 'All caught up!' : 'No approvals found'}
                    </p>
                    <p className="text-xs text-zinc-600 max-w-xs">
                      {isShowingPendingOnly
                        ? 'All pending responses have been reviewed. Great work!'
                        : hasActiveFilters
                          ? 'Try adjusting your filters to find what you\'re looking for.'
                          : 'Blocked AI responses will appear here for review.'}
                    </p>
                    {hasActiveFilters && (
                      <Button size="sm" variant="ghost" onClick={clearFilters} className="text-zinc-400 hover:text-zinc-200">
                        Clear Filters
                      </Button>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            )}

            {/* Approval Rows */}
            {!loading && !isConnecting && !error && approvals.map((item) => {
              const isSelected = selectedIds.has(item.id);
              const isUrgent = item.priority === 'urgent';
              const isPending = item.status === 'pending' || item.status === 'in_review';

              return (
                <TableRow
                  key={item.id}
                  className={`
                    cursor-pointer group transition-all
                    ${isUrgent ? 'border-l-2 border-l-red-500/60' : ''}
                    ${isSelected ? 'bg-orange-500/8' : 'hover:bg-white/[0.02]'}
                  `}
                  onClick={() => openDetail(item)}
                >
                  {/* Checkbox */}
                  <TableCell className="p-3" onClick={(e) => e.stopPropagation()}>
                    <Checkbox
                      checked={isSelected}
                      onCheckedChange={() => toggleSelect(item.id)}
                      className="border-white/[0.1] data-[state=checked]:bg-orange-500 data-[state=checked]:border-orange-500"
                    />
                  </TableCell>

                  {/* Priority */}
                  <TableCell className="p-3">
                    <div className="flex items-center gap-2">
                      <span className={`w-2 h-2 rounded-full shrink-0 ${PRIORITY_DOT_COLORS[item.priority] || 'bg-zinc-500'}`} />
                      <span className="text-xs text-zinc-400 capitalize hidden sm:inline">{item.priority}</span>
                    </div>
                  </TableCell>

                  {/* Query */}
                  <TableCell className="p-3 max-w-[250px]">
                    <p className="text-sm text-zinc-200 truncate">{item.query || '(No query)'}</p>
                    {item.ticket_id && (
                      <p className="text-[10px] text-zinc-600 mt-0.5">Ticket #{item.ticket_id.slice(0, 8)}</p>
                    )}
                  </TableCell>

                  {/* Block Reason */}
                  <TableCell className="p-3 hidden md:table-cell">
                    <Badge
                      variant="outline"
                      className={`text-[10px] font-medium ${BLOCK_REASON_STYLES[item.block_reason] || 'bg-zinc-700 text-zinc-400 border-zinc-700'}`}
                    >
                      {formatBlockReason(item.block_reason)}
                    </Badge>
                  </TableCell>

                  {/* Confidence */}
                  <TableCell className="p-3 hidden md:table-cell">
                    <ConfidenceBar confidence={item.confidence_score} />
                  </TableCell>

                  {/* Status */}
                  <TableCell className="p-3">
                    <Badge
                      variant="outline"
                      className={`text-[10px] font-medium ${STATUS_STYLES[item.status] || 'bg-zinc-700 text-zinc-400 border-zinc-700'}`}
                    >
                      {formatStatus(item.status)}
                    </Badge>
                  </TableCell>

                  {/* Agent Response */}
                  <TableCell className="p-3 max-w-[200px] hidden lg:table-cell">
                    <p className="text-xs text-zinc-500 truncate">
                      {item.original_response || '(No response)'}
                    </p>
                  </TableCell>

                  {/* Created */}
                  <TableCell className="p-3 hidden lg:table-cell">
                    <span className="text-xs text-zinc-500">
                      {relativeTime(item.created_at)}
                    </span>
                  </TableCell>

                  {/* Actions */}
                  <TableCell className="p-3" onClick={(e) => e.stopPropagation()}>
                    {isPending && (
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => openDetail(item)}
                          className="w-7 h-7 rounded-md flex items-center justify-center text-zinc-500 hover:text-emerald-400 hover:bg-emerald-500/10 transition-colors"
                          title="Review & Approve"
                        >
                          <CheckIcon />
                        </button>
                        <button
                          onClick={async () => {
                            setDetailItem(item);
                            setDetailError(null);
                            setDetailNotes('');
                            setDetailEditedResponse(item.original_response);
                            setShowEditResponse(false);
                            setDetailActionLoading(true);
                            try {
                              await dashboardApi.rejectResponse(item.id);
                              fetchApprovals();
                              fetchStats();
                            } catch {
                              openDetail(item);
                            } finally {
                              setDetailActionLoading(false);
                            }
                          }}
                          className="w-7 h-7 rounded-md flex items-center justify-center text-zinc-500 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                          title="Quick Reject"
                        >
                          <XIcon />
                        </button>
                      </div>
                    )}
                    {!isPending && (
                      <button
                        onClick={() => openDetail(item)}
                        className="w-7 h-7 rounded-md flex items-center justify-center text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.04] transition-colors"
                        title="View Details"
                      >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 0 1 0-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178Z" />
                          <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
                        </svg>
                      </button>
                    )}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>

      {/* ── Pagination ───────────────────────────────────────────────── */}
      {!loading && !isConnecting && total > PAGE_SIZE && (
        <div className="flex items-center justify-between mt-4 px-1">
          <p className="text-xs text-zinc-500">
            Showing {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, total)} of {total}
          </p>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="sm"
              className="text-zinc-400 hover:text-zinc-200 h-7 w-7 p-0"
              disabled={page <= 1}
              onClick={() => setPage(p => Math.max(1, p - 1))}
            >
              <ChevronLeftIcon />
            </Button>
            {getVisiblePages().map((p, idx) =>
              p === -1 ? (
                <span key={`ellipsis-${idx}`} className="text-zinc-600 text-xs px-1">...</span>
              ) : (
                <button
                  key={p}
                  onClick={() => setPage(p)}
                  className={`w-7 h-7 rounded-md text-xs font-medium transition-colors ${
                    page === p
                      ? 'bg-orange-500/15 text-orange-400'
                      : 'text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.04]'
                  }`}
                >
                  {p}
                </button>
              )
            )}
            <Button
              variant="ghost"
              size="sm"
              className="text-zinc-400 hover:text-zinc-200 h-7 w-7 p-0"
              disabled={page >= totalPages}
              onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            >
              <ChevronRightIcon />
            </Button>
          </div>
        </div>
      )}

      {/* ── Detail Modal ─────────────────────────────────────────────── */}
      <Dialog open={!!detailItem} onOpenChange={(open) => { if (!open) closeDetail(); }}>
        <DialogContent className="bg-[#141414] border-white/[0.06] max-w-2xl max-h-[85vh] overflow-y-auto">
          {detailLoading ? (
            <div className="py-12 flex items-center justify-center">
              <SpinnerIcon className="w-6 h-6 text-orange-400" />
            </div>
          ) : detailItem ? (
            <>
              <DialogHeader>
                <DialogTitle className="text-zinc-100 text-lg">Review Blocked Response</DialogTitle>
                <DialogDescription className="text-zinc-500 text-xs">
                  {detailItem.ticket_id ? `Ticket #${detailItem.ticket_id.slice(0, 8)}` : 'No ticket associated'}
                  {' · '}
                  {relativeTime(detailItem.created_at)}
                </DialogDescription>
              </DialogHeader>

              <div className="space-y-4 mt-2">
                {/* Status & Priority */}
                <div className="flex items-center gap-2 flex-wrap">
                  <Badge
                    variant="outline"
                    className={`text-[10px] font-medium ${STATUS_STYLES[detailItem.status] || 'bg-zinc-700 text-zinc-400 border-zinc-700'}`}
                  >
                    {formatStatus(detailItem.status)}
                  </Badge>
                  <Badge
                    variant="outline"
                    className={`text-[10px] font-semibold uppercase tracking-wide ${PRIORITY_STYLES[detailItem.priority] || 'bg-zinc-700 text-zinc-400 border-zinc-700'}`}
                  >
                    {detailItem.priority}
                  </Badge>
                  <Badge
                    variant="outline"
                    className={`text-[10px] font-medium ${BLOCK_REASON_STYLES[detailItem.block_reason] || 'bg-zinc-700 text-zinc-400 border-zinc-700'}`}
                  >
                    {formatBlockReason(detailItem.block_reason)}
                  </Badge>
                </div>

                {/* Customer Query */}
                <div className="bg-zinc-900/50 border border-white/[0.06] rounded-lg p-4">
                  <p className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider mb-2">Customer Query</p>
                  <p className="text-sm text-zinc-200 leading-relaxed whitespace-pre-wrap">{detailItem.query}</p>
                </div>

                {/* Original AI Response */}
                <div className="bg-zinc-900/50 border border-red-500/20 rounded-lg p-4">
                  <p className="text-[10px] font-medium text-red-400/80 uppercase tracking-wider mb-2">Blocked AI Response</p>
                  <p className="text-sm text-zinc-300 leading-relaxed whitespace-pre-wrap">{detailItem.original_response}</p>
                </div>

                {/* Edit Response (Approve with Edit) */}
                {showEditResponse && (
                  <div className="bg-zinc-900/50 border border-emerald-500/20 rounded-lg p-4">
                    <p className="text-[10px] font-medium text-emerald-400/80 uppercase tracking-wider mb-2">Edited Response (will replace original)</p>
                    <Textarea
                      value={detailEditedResponse}
                      onChange={(e) => setDetailEditedResponse(e.target.value)}
                      className="bg-[#1A1A1A] border-white/[0.06] text-sm text-zinc-200 placeholder:text-zinc-600 min-h-[120px] resize-y"
                      placeholder="Edit the response before approving..."
                    />
                  </div>
                )}

                {/* Confidence Score */}
                <div className="flex items-center gap-3">
                  <span className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider">Confidence</span>
                  <ConfidenceBar confidence={detailItem.confidence_score} />
                </div>

                {/* Guardrail Report Summary */}
                {detailItem.guardrail_report && Object.keys(detailItem.guardrail_report).length > 0 && (
                  <div className="bg-zinc-900/50 border border-white/[0.06] rounded-lg p-4">
                    <p className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider mb-2">Guardrail Report</p>
                    <div className="space-y-1">
                      {Object.entries(detailItem.guardrail_report).map(([key, value]) => (
                        <div key={key} className="flex items-start gap-2 text-xs">
                          <span className="text-zinc-500 capitalize">{key.replace(/_/g, ' ')}:</span>
                          <span className="text-zinc-300">
                            {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Ticket Link */}
                {detailItem.ticket_id && (
                  <div className="flex items-center gap-2 text-xs">
                    <span className="text-zinc-500">Ticket:</span>
                    <Link
                      href={`/dashboard/tickets/${detailItem.ticket_id}`}
                      className="text-orange-400 hover:text-orange-300 underline underline-offset-2 transition-colors"
                    >
                      View Ticket #{detailItem.ticket_id.slice(0, 8)}
                    </Link>
                  </div>
                )}

                {/* Wait Time */}
                {'wait_time_minutes' in detailItem && detailItem.wait_time_minutes !== null && detailItem.wait_time_minutes !== undefined && (
                  <div className="flex items-center gap-2 text-xs">
                    <span className="text-zinc-500">Waiting:</span>
                    <span className={`${(detailItem as ApprovalDetail).wait_time_minutes! > 30 ? 'text-orange-400' : 'text-zinc-300'}`}>
                      {(detailItem as ApprovalDetail).wait_time_minutes!.toFixed(0)} minutes
                    </span>
                  </div>
                )}

                {/* Review Notes */}
                <div>
                  <label className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider block mb-2">
                    Review Notes (optional)
                  </label>
                  <Textarea
                    value={detailNotes}
                    onChange={(e) => setDetailNotes(e.target.value)}
                    className="bg-[#1A1A1A] border-white/[0.06] text-sm text-zinc-200 placeholder:text-zinc-600 min-h-[80px] resize-y"
                    placeholder="Add notes about your review decision..."
                  />
                </div>

                {/* Error */}
                {detailError && (
                  <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3 text-sm text-red-400">
                    {detailError}
                  </div>
                )}

                {/* Previous Review Notes */}
                {detailItem.review_notes && (
                  <div className="bg-zinc-900/30 border border-white/[0.04] rounded-lg p-3">
                    <p className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider mb-1">Previous Review Notes</p>
                    <p className="text-xs text-zinc-400">{detailItem.review_notes}</p>
                  </div>
                )}
              </div>

              {/* Action Buttons */}
              {(detailItem.status === 'pending' || detailItem.status === 'in_review') && (
                <DialogFooter className="flex-col gap-2 sm:flex-row mt-4">
                  <Button
                    onClick={handleApprove}
                    disabled={detailActionLoading}
                    className="bg-emerald-600 hover:bg-emerald-700 text-white text-sm"
                  >
                    {detailActionLoading ? <SpinnerIcon /> : <CheckIcon />}
                    Approve
                  </Button>
                  <Button
                    onClick={() => setShowEditResponse(!showEditResponse)}
                    variant="outline"
                    disabled={detailActionLoading}
                    className="border-white/[0.1] text-zinc-300 hover:text-orange-400 hover:border-orange-500/30 text-sm"
                  >
                    {showEditResponse ? 'Hide Edit' : 'Approve with Edit'}
                  </Button>
                  {showEditResponse && (
                    <Button
                      onClick={handleApprove}
                      disabled={detailActionLoading || !detailEditedResponse.trim()}
                      className="bg-orange-600 hover:bg-orange-700 text-white text-sm"
                    >
                      {detailActionLoading ? <SpinnerIcon /> : <ShieldCheckIcon />}
                      Approve Edited
                    </Button>
                  )}
                  <Button
                    onClick={handleReject}
                    disabled={detailActionLoading}
                    variant="outline"
                    className="border-white/[0.1] text-zinc-300 hover:text-red-400 hover:border-red-500/30 text-sm"
                  >
                    {detailActionLoading ? <SpinnerIcon /> : <XIcon />}
                    Reject
                  </Button>
                  <Button
                    onClick={handleEscalate}
                    disabled={detailActionLoading}
                    variant="outline"
                    className="border-white/[0.1] text-zinc-300 hover:text-amber-400 hover:border-amber-500/30 text-sm"
                  >
                    {detailActionLoading ? <SpinnerIcon /> : <AlertTriangleIcon />}
                    Escalate
                  </Button>
                </DialogFooter>
              )}
            </>
          ) : null}
        </DialogContent>
      </Dialog>

      {/* ── Batch Action Dialog ──────────────────────────────────────── */}
      <Dialog open={!!batchAction} onOpenChange={(open) => { if (!open) { setBatchAction(null); setBatchNotes(''); setBatchError(null); } }}>
        <DialogContent className="bg-[#141414] border-white/[0.06] max-w-md">
          <DialogHeader>
            <DialogTitle className="text-zinc-100">
              {batchAction === 'approved' ? 'Approve' : 'Reject'} {selectedIds.size} Items
            </DialogTitle>
            <DialogDescription className="text-zinc-500 text-xs">
              This action will be applied to all {selectedIds.size} selected items.
            </DialogDescription>
          </DialogHeader>
          <div className="mt-2">
            <label className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider block mb-2">
              Review Notes (optional)
            </label>
            <Textarea
              value={batchNotes}
              onChange={(e) => setBatchNotes(e.target.value)}
              className="bg-[#1A1A1A] border-white/[0.06] text-sm text-zinc-200 placeholder:text-zinc-600 min-h-[80px] resize-y"
              placeholder="Add notes for this batch action..."
            />
            {batchError && (
              <p className="text-xs text-red-400 mt-2">{batchError}</p>
            )}
          </div>
          <DialogFooter className="flex-col gap-2 sm:flex-row mt-4">
            <Button
              onClick={handleBatchAction}
              disabled={batchLoading}
              className={
                batchAction === 'approved'
                  ? 'bg-emerald-600 hover:bg-emerald-700 text-white text-sm'
                  : 'bg-red-600 hover:bg-red-700 text-white text-sm'
              }
            >
              {batchLoading ? <SpinnerIcon /> : batchAction === 'approved' ? <CheckIcon /> : <XIcon />}
              {batchAction === 'approved' ? 'Approve' : 'Reject'} All
            </Button>
            <Button
              variant="ghost"
              onClick={() => { setBatchAction(null); setBatchNotes(''); setBatchError(null); }}
              className="text-zinc-400 hover:text-zinc-200 text-sm"
            >
              Cancel
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
