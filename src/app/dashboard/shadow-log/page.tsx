'use client';

import React, { useState, useEffect, useCallback } from 'react';
import toast from 'react-hot-toast';
import { getErrorMessage } from '@/lib/api';
import { cn } from '@/lib/utils';
import {
  shadowApi,
  type SystemMode,
  type ManagerDecision,
  type ShadowLogEntry,
  type ShadowStats,
} from '@/lib/shadow-api';
import { useSocket } from '@/contexts/SocketContext';

// ── Skeleton Helper ────────────────────────────────────────────────────────

function Skeleton({ className }: { className?: string }) {
  return <div className={cn('animate-pulse rounded-lg bg-white/[0.06]', className)} />;
}

// ── Inline SVG Icons ───────────────────────────────────────────────────────

function ShieldEyeIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 0 1 0-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178Z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
    </svg>
  );
}

function ChartBarIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 0 1 3 19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V8.625ZM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V4.125Z" />
    </svg>
  );
}

function FilterIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 3c2.755 0 5.455.232 8.083.678.533.09.917.556.917 1.096v1.044a2.25 2.25 0 0 1-.659 1.591l-5.432 5.432a2.25 2.25 0 0 0-.659 1.591v2.927a2.25 2.25 0 0 1-1.244 2.013L9.75 21v-6.568a2.25 2.25 0 0 0-.659-1.591L3.659 7.409A2.25 2.25 0 0 1 3 5.818V4.774c0-.54.384-1.006.917-1.096A48.32 48.32 0 0 1 12 3Z" />
    </svg>
  );
}

function DownloadIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3" />
    </svg>
  );
}

function ChevronDownIcon({ className, open }: { className?: string; open?: boolean }) {
  return (
    <svg className={cn(className, open && 'rotate-180')} fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
    </svg>
  );
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
    </svg>
  );
}

function XMarkIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
    </svg>
  );
}

function SpinnerIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  );
}

function CheckboxSquareIcon({ className, checked }: { className?: string; checked?: boolean }) {
  if (checked) {
    return (
      <svg className={className} viewBox="0 0 24 24" fill="none">
        <rect x="3" y="3" width="18" height="18" rx="4" fill="#FF7F11" stroke="#FF7F11" strokeWidth="2" />
        <path d="M8 12.5l2.5 2.5 5.5-5.5" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      <rect x="3" y="3" width="18" height="18" rx="4" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

// ── Format Helpers ─────────────────────────────────────────────────────────

function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return 'N/A';
  try {
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric', month: 'short', day: 'numeric',
    });
  } catch { return 'N/A'; }
}

function formatDateTime(dateStr: string | null | undefined): string {
  if (!dateStr) return 'N/A';
  try {
    return new Date(dateStr).toLocaleString('en-US', {
      month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
    });
  } catch { return 'N/A'; }
}

function formatRelativeTime(dateStr: string | null | undefined): string {
  if (!dateStr) return '';
  try {
    const now = new Date();
    const date = new Date(dateStr);
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    if (diffDays < 7) return `${diffDays}d ago`;
    return formatDate(dateStr);
  } catch { return ''; }
}

// ── Badge Helpers ──────────────────────────────────────────────────────────

function ModeBadge({ mode }: { mode: SystemMode }) {
  const config: Record<SystemMode, string> = {
    shadow: 'bg-orange-500/15 text-orange-400 border-orange-500/20',
    supervised: 'bg-blue-500/15 text-blue-400 border-blue-500/20',
    graduated: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20',
  };
  return (
    <span className={cn('inline-flex rounded-md border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider', config[mode])}>
      {mode}
    </span>
  );
}

function DecisionBadge({ decision }: { decision: ManagerDecision }) {
  if (!decision) return (
    <span className="inline-flex rounded-md bg-zinc-500/15 border border-zinc-500/20 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-zinc-400">
      Pending
    </span>
  );
  const config: Record<string, string> = {
    approved: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20',
    rejected: 'bg-red-500/15 text-red-400 border-red-500/20',
    modified: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/20',
  };
  return (
    <span className={cn('inline-flex rounded-md border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider', config[decision])}>
      {decision}
    </span>
  );
}

function RiskBar({ score }: { score: number | null }) {
  if (score === null) return <span className="text-zinc-600 text-xs">—</span>;
  const pct = Math.min(100, Math.max(0, score * 100));
  const color = pct >= 70 ? 'bg-red-500' : pct >= 40 ? 'bg-yellow-500' : 'bg-emerald-500';
  const textColor = pct >= 70 ? 'text-red-400' : pct >= 40 ? 'text-yellow-400' : 'text-emerald-400';
  return (
    <div className="flex items-center gap-2 min-w-[120px]">
      <div className="flex-1 h-1.5 bg-white/[0.06] rounded-full overflow-hidden">
        <div className={cn('h-full rounded-full transition-all duration-300', color)} style={{ width: `${pct}%` }} />
      </div>
      <span className={cn('text-[11px] font-mono font-medium w-10 text-right', textColor)}>
        {(score * 100).toFixed(0)}%
      </span>
    </div>
  );
}

// ── Error Fallback ─────────────────────────────────────────────────────────

function SectionError({ message, onRetry }: { message?: string; onRetry?: () => void }) {
  return (
    <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-5">
      <p className="text-sm text-zinc-500">{message || 'Unable to load data'}</p>
      {onRetry && (
        <button onClick={onRetry} className="mt-2 text-xs text-[#FF7F11] hover:underline">Try again</button>
      )}
    </div>
  );
}

// ── Stats Card ─────────────────────────────────────────────────────────────

function StatCard({ label, value, icon, color }: {
  label: string;
  value: string | number;
  icon: React.ReactNode;
  color: string;
}) {
  return (
    <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-4">
      <div className="flex items-center gap-3">
        <div className={cn('flex h-9 w-9 items-center justify-center rounded-lg', color)}>
          {icon}
        </div>
        <div>
          <p className="text-lg font-bold text-white">{value}</p>
          <p className="text-[11px] text-zinc-500">{label}</p>
        </div>
      </div>
    </div>
  );
}

// ── Action Type Labels ─────────────────────────────────────────────────────

const ACTION_LABELS: Record<string, string> = {
  refund: 'Refund',
  email_reply: 'Email Reply',
  sms_reply: 'SMS Reply',
  voice_reply: 'Voice Reply',
  ticket_close: 'Close Ticket',
  account_change: 'Account Change',
  integration_action: 'Integration',
};

function actionLabel(type: string): string {
  return ACTION_LABELS[type] || type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

// ════════════════════════════════════════════════════════════════════════════
// Main Shadow Log Page
// ════════════════════════════════════════════════════════════════════════════

export default function ShadowLogPage() {
  const { isConnected } = useSocket();

  // ── State ───────────────────────────────────────────────────────────────
  const [stats, setStats] = useState<ShadowStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);
  const [statsError, setStatsError] = useState(false);

  const [entries, setEntries] = useState<ShadowLogEntry[]>([]);
  const [pagination, setPagination] = useState({ page: 1, pages: 1, total: 0 });
  const [logLoading, setLogLoading] = useState(true);
  const [logError, setLogError] = useState(false);

  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [approvingId, setApprovingId] = useState<string | null>(null);
  const [rejectingId, setRejectingId] = useState<string | null>(null);

  // ── Batch Selection ────────────────────────────────────────────────────
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [batchLoading, setBatchLoading] = useState(false);

  // ── Filters ─────────────────────────────────────────────────────────────
  const [filterAction, setFilterAction] = useState('');
  const [filterMode, setFilterMode] = useState<SystemMode | ''>('');
  const [filterDecision, setFilterDecision] = useState<string>('');
  const [sortBy, setSortBy] = useState('created_at');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [showFilters, setShowFilters] = useState(false);

  // ── Load Stats ──────────────────────────────────────────────────────────
  const loadStats = useCallback(async () => {
    setStatsLoading(true);
    setStatsError(false);
    try {
      const data = await shadowApi.getStats();
      setStats(data);
    } catch {
      setStatsError(true);
    } finally {
      setStatsLoading(false);
    }
  }, []);

  // ── Load Log ────────────────────────────────────────────────────────────
  const loadLog = useCallback(async (page: number = 1) => {
    setLogLoading(true);
    setLogError(false);
    try {
      const params: Record<string, any> = { page, page_size: 20 };
      if (filterAction) params.action_type = filterAction;
      if (filterMode) params.mode = filterMode;
      if (filterDecision) params.decision = filterDecision;
      params.sort_by = sortBy;
      params.sort_dir = sortDir;
      const data = await shadowApi.getLog(params);
      setEntries(data.items);
      setPagination({ page: data.page, pages: data.pages, total: data.total });
    } catch {
      setLogError(true);
    } finally {
      setLogLoading(false);
    }
  }, [filterAction, filterMode, filterDecision, sortBy, sortDir]);

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  useEffect(() => {
    loadLog(1);
  }, [loadLog]);

  // ── Real-time via Socket.io ─────────────────────────────────────────────
  useEffect(() => {
    if (!isConnected) return;
    const socket = (window as any).__parwa_socket;
    if (!socket) return;

    const handler = () => {
      loadLog(pagination.page);
      loadStats();
    };
    socket.on('shadow:new', handler);
    socket.on('shadow:decision', handler);
    return () => {
      socket.off('shadow:new', handler);
      socket.off('shadow:decision', handler);
    };
  }, [isConnected, pagination.page, loadLog, loadStats]);

  // ── Handlers ────────────────────────────────────────────────────────────
  const handleApprove = async (id: string) => {
    const note = prompt('Approval note (optional):');
    if (note === null) return;
    setApprovingId(id);
    try {
      await shadowApi.approve(id, note || undefined);
      toast.success('Action approved');
      loadLog(pagination.page);
      loadStats();
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setApprovingId(null);
    }
  };

  const handleReject = async (id: string) => {
    const note = prompt('Rejection reason:');
    if (note === null) return;
    setRejectingId(id);
    try {
      await shadowApi.reject(id, note || undefined);
      toast.success('Action rejected');
      loadLog(pagination.page);
      loadStats();
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setRejectingId(null);
    }
  };

  const handleExportCSV = () => {
    if (entries.length === 0) {
      toast.error('No data to export');
      return;
    }
    const headers = ['Timestamp', 'Action Type', 'Risk Score', 'Mode', 'Decision', 'Manager Note'];
    const rows = entries.map(e => [
      e.created_at,
      e.action_type,
      e.jarvis_risk_score !== null ? (e.jarvis_risk_score * 100).toFixed(1) + '%' : 'N/A',
      e.mode,
      e.manager_decision || 'Pending',
      e.manager_note || '',
    ]);
    const csv = [headers.join(','), ...rows.map(r => r.map(v => `"${v}"`).join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `shadow-log-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success('CSV exported');
  };

  // ── Batch Handlers ─────────────────────────────────────────────────────
  const pendingEntries = entries.filter(e => !e.manager_decision);
  const allPendingSelected = pendingEntries.length > 0 && pendingEntries.every(e => selectedIds.has(e.id));

  const toggleSelect = (id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAllPending = () => {
    if (allPendingSelected) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(pendingEntries.map(e => e.id)));
    }
  };

  const handleBatchApprove = async () => {
    if (selectedIds.size === 0) return;
    setBatchLoading(true);
    try {
      const ids = Array.from(selectedIds);
      await shadowApi.batchResolve(ids, 'approved');
      toast.success(`${ids.length} action(s) approved`);
      setSelectedIds(new Set());
      // Optimistic: remove resolved items from displayed list
      setEntries(prev => prev.filter(e => !ids.includes(e.id)));
      loadStats();
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setBatchLoading(false);
    }
  };

  const handleBatchReject = async () => {
    if (selectedIds.size === 0) return;
    setBatchLoading(true);
    try {
      const ids = Array.from(selectedIds);
      await shadowApi.batchResolve(ids, 'rejected');
      toast.success(`${ids.length} action(s) rejected`);
      setSelectedIds(new Set());
      // Optimistic: remove resolved items from displayed list
      setEntries(prev => prev.filter(e => !ids.includes(e.id)));
      loadStats();
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setBatchLoading(false);
    }
  };

  const handleSort = (field: string) => {
    if (sortBy === field) {
      setSortDir(prev => prev === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortDir('desc');
    }
  };

  const clearFilters = () => {
    setFilterAction('');
    setFilterMode('');
    setFilterDecision('');
  };

  const hasActiveFilters = filterAction || filterMode || filterDecision;

  // ── Mode Distribution Data ──────────────────────────────────────────────
  const modeDistribution = stats?.mode_distribution || { shadow: 0, supervised: 0, graduated: 0 };
  const totalModeDist = (modeDistribution.shadow || 0) + (modeDistribution.supervised || 0) + (modeDistribution.graduated || 0);

  // ════════════════════════════════════════════════════════════════════════
  // Render
  // ════════════════════════════════════════════════════════════════════════

  return (
    <div className="jarvis-page-body min-h-screen bg-[#0A0A0A]">
      <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
        {/* ── Page Header ──────────────────────────────────────────────── */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#FF7F11]/10">
              <ShieldEyeIcon className="h-5 w-5 text-[#FF7F11]" />
            </div>
            <h1 className="text-2xl font-bold text-white">Shadow Log</h1>
          </div>
          <p className="text-sm text-zinc-500 ml-[52px]">
            Complete audit trail of all Jarvis actions with risk scores, decisions, and outcomes.
          </p>
        </div>

        {/* ── Stats Strip ───────────────────────────────────────────────── */}
        {statsLoading ? (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            {[1, 2, 3, 4].map(i => <Skeleton key={i} className="h-20" />)}
          </div>
        ) : statsError ? (
          <SectionError message="Unable to load statistics" onRetry={loadStats} />
        ) : stats ? (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <StatCard
              label="Total Actions"
              value={stats.total_actions.toLocaleString()}
              icon={<ShieldEyeIcon className="h-4 w-4 text-[#FF7F11]" />}
              color="bg-[#FF7F11]/10"
            />
            <StatCard
              label="Approval Rate"
              value={`${(stats.approval_rate * 100).toFixed(1)}%`}
              icon={<CheckIcon className="h-4 w-4 text-emerald-400" />}
              color="bg-emerald-500/10"
            />
            <StatCard
              label="Avg Risk Score"
              value={`${(stats.avg_risk_score * 100).toFixed(1)}%`}
              icon={<ChartBarIcon className="h-4 w-4 text-yellow-400" />}
              color="bg-yellow-500/10"
            />
            <StatCard
              label="Pending Review"
              value={stats.pending_count}
              icon={<XMarkIcon className="h-4 w-4 text-red-400" />}
              color="bg-red-500/10"
            />
          </div>
        ) : null}

        {/* ── Mode Distribution Bar ─────────────────────────────────────── */}
        {stats && totalModeDist > 0 && (
          <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-4 mb-6">
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm font-medium text-zinc-300">Mode Distribution</span>
              <span className="text-xs text-zinc-500">{totalModeDist} actions</span>
            </div>
            <div className="flex h-3 rounded-full overflow-hidden bg-white/[0.06]">
              {(modeDistribution.shadow || 0) > 0 && (
                <div
                  className="bg-orange-500 h-full transition-all duration-500"
                  style={{ width: `${((modeDistribution.shadow || 0) / totalModeDist) * 100}%` }}
                  title={`Shadow: ${modeDistribution.shadow}`}
                />
              )}
              {(modeDistribution.supervised || 0) > 0 && (
                <div
                  className="bg-blue-500 h-full transition-all duration-500"
                  style={{ width: `${((modeDistribution.supervised || 0) / totalModeDist) * 100}%` }}
                  title={`Supervised: ${modeDistribution.supervised}`}
                />
              )}
              {(modeDistribution.graduated || 0) > 0 && (
                <div
                  className="bg-emerald-500 h-full transition-all duration-500"
                  style={{ width: `${((modeDistribution.graduated || 0) / totalModeDist) * 100}%` }}
                  title={`Graduated: ${modeDistribution.graduated}`}
                />
              )}
            </div>
            <div className="flex items-center gap-4 mt-2">
              <span className="flex items-center gap-1.5 text-[11px] text-zinc-500">
                <span className="w-2 h-2 rounded-full bg-orange-500" /> Shadow ({modeDistribution.shadow || 0})
              </span>
              <span className="flex items-center gap-1.5 text-[11px] text-zinc-500">
                <span className="w-2 h-2 rounded-full bg-blue-500" /> Supervised ({modeDistribution.supervised || 0})
              </span>
              <span className="flex items-center gap-1.5 text-[11px] text-zinc-500">
                <span className="w-2 h-2 rounded-full bg-emerald-500" /> Graduated ({modeDistribution.graduated || 0})
              </span>
            </div>
          </div>
        )}

        {/* ── Action Type Distribution ─────────────────────────────────── */}
        {stats && stats.action_type_distribution && Object.keys(stats.action_type_distribution).length > 0 && (
          <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-4 mb-6">
            <div className="flex items-center gap-2 mb-3">
              <ChartBarIcon className="h-4 w-4 text-[#FF7F11]" />
              <span className="text-sm font-medium text-zinc-300">Action Types</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {Object.entries(stats.action_type_distribution)
                .sort(([, a], [, b]) => b - a)
                .map(([type, count]) => (
                  <span
                    key={type}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-white/[0.04] border border-white/[0.06] px-3 py-1.5 text-xs text-zinc-400"
                  >
                    <span className="font-medium text-zinc-300">{actionLabel(type)}</span>
                    <span className="text-zinc-600">({count})</span>
                  </span>
                ))}
            </div>
          </div>
        )}

        {/* ── Filter Bar + Export ───────────────────────────────────────── */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-4">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowFilters(!showFilters)}
              className={cn(
                'inline-flex items-center gap-1.5 rounded-lg border px-3 py-2 text-xs font-medium transition-colors',
                showFilters || hasActiveFilters
                  ? 'border-[#FF7F11]/30 bg-[#FF7F11]/10 text-[#FF7F11]'
                  : 'border-white/[0.08] bg-white/[0.04] text-zinc-400 hover:text-zinc-300'
              )}
            >
              <FilterIcon className="h-3.5 w-3.5" />
              Filters
              {hasActiveFilters && (
                <span className="ml-1 w-4 h-4 rounded-full bg-[#FF7F11] text-white text-[9px] flex items-center justify-center font-bold">!</span>
              )}
            </button>
            {hasActiveFilters && (
              <button onClick={clearFilters} className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors">
                Clear
              </button>
            )}
          </div>
          <button
            onClick={handleExportCSV}
            className="inline-flex items-center gap-1.5 rounded-lg border border-white/[0.08] bg-white/[0.04] px-3 py-2 text-xs font-medium text-zinc-400 hover:text-zinc-300 transition-colors"
          >
            <DownloadIcon className="h-3.5 w-3.5" />
            Export CSV
          </button>
        </div>

        {/* ── Expandable Filters ───────────────────────────────────────── */}
        {showFilters && (
          <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-4 mb-4">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="block text-[11px] font-medium text-zinc-500 mb-1 uppercase tracking-wider">Action Type</label>
                <select
                  value={filterAction}
                  onChange={e => setFilterAction(e.target.value)}
                  className="w-full rounded-lg border border-white/[0.08] bg-[#141414] px-3 py-2 text-sm text-white focus:border-[#FF7F11]/50 focus:outline-none focus:ring-1 focus:ring-[#FF7F11]/30 appearance-none cursor-pointer"
                >
                  <option value="">All Types</option>
                  {Object.keys(ACTION_LABELS).map(t => (
                    <option key={t} value={t}>{ACTION_LABELS[t]}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-[11px] font-medium text-zinc-500 mb-1 uppercase tracking-wider">Mode</label>
                <select
                  value={filterMode}
                  onChange={e => setFilterMode(e.target.value as SystemMode | '')}
                  className="w-full rounded-lg border border-white/[0.08] bg-[#141414] px-3 py-2 text-sm text-white focus:border-[#FF7F11]/50 focus:outline-none focus:ring-1 focus:ring-[#FF7F11]/30 appearance-none cursor-pointer"
                >
                  <option value="">All Modes</option>
                  <option value="shadow">Shadow</option>
                  <option value="supervised">Supervised</option>
                  <option value="graduated">Graduated</option>
                </select>
              </div>
              <div>
                <label className="block text-[11px] font-medium text-zinc-500 mb-1 uppercase tracking-wider">Decision</label>
                <select
                  value={filterDecision}
                  onChange={e => setFilterDecision(e.target.value)}
                  className="w-full rounded-lg border border-white/[0.08] bg-[#141414] px-3 py-2 text-sm text-white focus:border-[#FF7F11]/50 focus:outline-none focus:ring-1 focus:ring-[#FF7F11]/30 appearance-none cursor-pointer"
                >
                  <option value="">All Decisions</option>
                  <option value="">Pending</option>
                  <option value="approved">Approved</option>
                  <option value="rejected">Rejected</option>
                  <option value="modified">Modified</option>
                </select>
              </div>
            </div>
          </div>
        )}

        {/* ── Log Table ─────────────────────────────────────────────────── */}
        {logLoading ? (
          <Skeleton className="h-96 mb-6" />
        ) : logError ? (
          <SectionError message="Unable to load shadow log" onRetry={() => loadLog(pagination.page)} />
        ) : entries.length === 0 ? (
          <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-12 mb-6 text-center">
            <ShieldEyeIcon className="h-12 w-12 text-zinc-700 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-zinc-400 mb-2">No Actions Found</h3>
            <p className="text-sm text-zinc-600 max-w-md mx-auto">
              {hasActiveFilters
                ? 'No actions match the current filters. Try adjusting or clearing your filters.'
                : 'Shadow mode actions will appear here once Jarvis starts processing requests.'}
            </p>
          </div>
        ) : (
          <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] overflow-hidden mb-6">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/[0.06]">
                    <th className="px-3 py-3 w-10">
                      <button
                        onClick={toggleSelectAllPending}
                        className="flex items-center justify-center"
                        title={allPendingSelected ? 'Deselect all pending' : 'Select all pending'}
                      >
                        <CheckboxSquareIcon
                          className={cn('w-4 h-4 text-zinc-600 hover:text-zinc-400 transition-colors', allPendingSelected && 'text-[#FF7F11]')}
                          checked={allPendingSelected || undefined}
                        />
                      </button>
                    </th>
                    <th
                      onClick={() => handleSort('created_at')}
                      className="px-4 py-3 text-left text-[10px] font-medium text-zinc-500 uppercase tracking-wider cursor-pointer hover:text-zinc-300 transition-colors"
                    >
                      <span className="flex items-center gap-1">
                        Timestamp
                        {sortBy === 'created_at' && <ChevronDownIcon className={cn('w-3 h-3', sortDir === 'asc' ? 'rotate-180' : '')} />}
                      </span>
                    </th>
                    <th className="px-4 py-3 text-left text-[10px] font-medium text-zinc-500 uppercase tracking-wider">Action</th>
                    <th
                      onClick={() => handleSort('jarvis_risk_score')}
                      className="px-4 py-3 text-left text-[10px] font-medium text-zinc-500 uppercase tracking-wider cursor-pointer hover:text-zinc-300 transition-colors"
                    >
                      <span className="flex items-center gap-1">
                        Risk
                        {sortBy === 'jarvis_risk_score' && <ChevronDownIcon className={cn('w-3 h-3', sortDir === 'asc' ? 'rotate-180' : '')} />}
                      </span>
                    </th>
                    <th className="px-4 py-3 text-left text-[10px] font-medium text-zinc-500 uppercase tracking-wider">Mode</th>
                    <th className="px-4 py-3 text-left text-[10px] font-medium text-zinc-500 uppercase tracking-wider">Decision</th>
                    <th className="px-4 py-3 text-left text-[10px] font-medium text-zinc-500 uppercase tracking-wider hidden lg:table-cell">Note</th>
                    <th className="px-4 py-3 text-right text-[10px] font-medium text-zinc-500 uppercase tracking-wider">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/[0.04]">
                  {entries.map(entry => {
                    const isExpanded = expandedId === entry.id;
                    return (
                      <React.Fragment key={entry.id}>
                        <tr
                          className={cn(
                            'hover:bg-white/[0.02] transition-colors cursor-pointer',
                            isExpanded && 'bg-white/[0.03]',
                            selectedIds.has(entry.id) && 'bg-[#FF7F11]/[0.04]',
                          )}
                          onClick={() => setExpandedId(isExpanded ? null : entry.id)}
                        >
                          <td className="px-3 py-3" onClick={e => e.stopPropagation()}>
                            {!entry.manager_decision ? (
                              <button
                                onClick={() => toggleSelect(entry.id)}
                                className="flex items-center justify-center"
                              >
                                <CheckboxSquareIcon
                                  className={cn(
                                    'w-4 h-4 transition-colors',
                                    selectedIds.has(entry.id) ? 'text-[#FF7F11]' : 'text-zinc-600 hover:text-zinc-400',
                                  )}
                                  checked={selectedIds.has(entry.id) || undefined}
                                />
                              </button>
                            ) : (
                              <span className="w-4 h-4 block" />
                            )}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap">
                            <div className="text-zinc-300 text-xs">{formatDateTime(entry.created_at)}</div>
                            <div className="text-[10px] text-zinc-600">{formatRelativeTime(entry.created_at)}</div>
                          </td>
                          <td className="px-4 py-3">
                            <span className="text-zinc-200 text-xs font-medium">{actionLabel(entry.action_type)}</span>
                          </td>
                          <td className="px-4 py-3">
                            <RiskBar score={entry.jarvis_risk_score} />
                          </td>
                          <td className="px-4 py-3">
                            <ModeBadge mode={entry.mode} />
                          </td>
                          <td className="px-4 py-3">
                            <DecisionBadge decision={entry.manager_decision} />
                          </td>
                          <td className="px-4 py-3 hidden lg:table-cell">
                            <span className="text-xs text-zinc-500 truncate block max-w-[200px]">
                              {entry.manager_note || '—'}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-right" onClick={e => e.stopPropagation()}>
                            <div className="flex items-center justify-end gap-1">
                              {!entry.manager_decision && (
                                <>
                                  <button
                                    onClick={() => handleApprove(entry.id)}
                                    disabled={approvingId === entry.id}
                                    className="inline-flex items-center gap-1 rounded-md bg-emerald-500/15 border border-emerald-500/20 px-2 py-1 text-[10px] font-medium text-emerald-400 hover:bg-emerald-500/25 disabled:opacity-50 transition-colors"
                                  >
                                    {approvingId === entry.id ? <SpinnerIcon className="w-3 h-3 animate-spin" /> : <CheckIcon className="w-3 h-3" />}
                                    <span className="hidden sm:inline">Approve</span>
                                  </button>
                                  <button
                                    onClick={() => handleReject(entry.id)}
                                    disabled={rejectingId === entry.id}
                                    className="inline-flex items-center gap-1 rounded-md bg-red-500/15 border border-red-500/20 px-2 py-1 text-[10px] font-medium text-red-400 hover:bg-red-500/25 disabled:opacity-50 transition-colors"
                                  >
                                    {rejectingId === entry.id ? <SpinnerIcon className="w-3 h-3 animate-spin" /> : <XMarkIcon className="w-3 h-3" />}
                                    <span className="hidden sm:inline">Reject</span>
                                  </button>
                                </>
                              )}
                              {entry.manager_decision && (
                                <ChevronDownIcon className={cn('w-4 h-4 text-zinc-600', isExpanded && 'rotate-180')} />
                              )}
                            </div>
                          </td>
                        </tr>
                        {/* ── Expanded Row ────────────────────────────────── */}
                        {isExpanded && (
                          <tr>
                            <td colSpan={8} className="px-4 py-4 bg-white/[0.02]">
                              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                                {/* Action Payload */}
                                <div>
                                  <p className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider mb-2">Action Payload</p>
                                  <pre className="rounded-lg bg-[#0A0A0A] border border-white/[0.06] p-3 text-xs text-zinc-400 overflow-x-auto max-h-48 font-mono">
                                    {JSON.stringify(entry.action_payload, null, 2)}
                                  </pre>
                                </div>
                                {/* Details */}
                                <div className="space-y-3">
                                  <div>
                                    <p className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider mb-2">Risk Breakdown</p>
                                    <div className="rounded-lg bg-[#0A0A0A] border border-white/[0.06] p-3 space-y-2">
                                      <div className="flex items-center justify-between text-xs">
                                        <span className="text-zinc-500">Risk Score</span>
                                        <span className="font-mono font-medium text-zinc-300">
                                          {entry.jarvis_risk_score !== null ? `${(entry.jarvis_risk_score * 100).toFixed(1)}%` : 'N/A'}
                                        </span>
                                      </div>
                                      <div className="flex items-center justify-between text-xs">
                                        <span className="text-zinc-500">Mode</span>
                                        <ModeBadge mode={entry.mode} />
                                      </div>
                                    </div>
                                  </div>
                                  <div>
                                    <p className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider mb-2">Decision Timeline</p>
                                    <div className="rounded-lg bg-[#0A0A0A] border border-white/[0.06] p-3 space-y-2">
                                      <div className="flex items-center justify-between text-xs">
                                        <span className="text-zinc-500">Created</span>
                                        <span className="text-zinc-300">{formatDateTime(entry.created_at)}</span>
                                      </div>
                                      <div className="flex items-center justify-between text-xs">
                                        <span className="text-zinc-500">Resolved</span>
                                        <span className="text-zinc-300">{entry.resolved_at ? formatDateTime(entry.resolved_at) : 'Pending'}</span>
                                      </div>
                                      {entry.manager_decision && (
                                        <div className="flex items-center justify-between text-xs">
                                          <span className="text-zinc-500">Decision</span>
                                          <DecisionBadge decision={entry.manager_decision} />
                                        </div>
                                      )}
                                      {entry.manager_note && (
                                        <div className="pt-2 border-t border-white/[0.06]">
                                          <span className="text-[10px] text-zinc-500">Manager Note</span>
                                          <p className="text-xs text-zinc-400 mt-1">{entry.manager_note}</p>
                                        </div>
                                      )}
                                    </div>
                                  </div>
                                </div>
                              </div>
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* ── Pagination ──────────────────────────────────────────── */}
            {pagination.pages > 1 && (
              <div className="flex items-center justify-between border-t border-white/[0.06] px-4 py-3">
                <p className="text-xs text-zinc-500">
                  Page {pagination.page} of {pagination.pages} ({pagination.total} entries)
                </p>
                <div className="flex items-center gap-2">
                  <button
                    disabled={pagination.page <= 1}
                    onClick={() => loadLog(pagination.page - 1)}
                    className="rounded-lg border border-white/[0.06] bg-white/[0.03] px-3 py-1.5 text-xs text-zinc-400 hover:bg-white/[0.06] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                  >
                    Previous
                  </button>
                  <span className="text-xs text-zinc-600 px-2">{pagination.page}</span>
                  <button
                    disabled={pagination.page >= pagination.pages}
                    onClick={() => loadLog(pagination.page + 1)}
                    className="rounded-lg border border-white/[0.06] bg-white/[0.03] px-3 py-1.5 text-xs text-zinc-400 hover:bg-white/[0.06] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Batch Action Bar (fixed bottom) ────────────────────────────── */}
      {selectedIds.size > 0 && (
        <div className="fixed bottom-0 left-0 right-0 z-50 border-t border-[#FF7F11]/20 bg-[#141414]/95 backdrop-blur-sm shadow-lg shadow-black/30">
          <div className="mx-auto max-w-6xl px-4 py-3 flex items-center gap-3">
            <span className="text-sm font-medium text-[#FF7F11]">
              {selectedIds.size} selected
            </span>
            <div className="h-4 w-px bg-white/[0.08]" />
            <button
              onClick={handleBatchApprove}
              disabled={batchLoading}
              className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-500/15 border border-emerald-500/25 px-3 py-1.5 text-xs font-medium text-emerald-400 hover:bg-emerald-500/25 disabled:opacity-50 transition-colors"
            >
              {batchLoading ? <SpinnerIcon className="w-3.5 h-3.5 animate-spin" /> : <CheckIcon className="w-3.5 h-3.5" />}
              Approve Selected
            </button>
            <button
              onClick={handleBatchReject}
              disabled={batchLoading}
              className="inline-flex items-center gap-1.5 rounded-lg bg-red-500/15 border border-red-500/25 px-3 py-1.5 text-xs font-medium text-red-400 hover:bg-red-500/25 disabled:opacity-50 transition-colors"
            >
              {batchLoading ? <SpinnerIcon className="w-3.5 h-3.5 animate-spin" /> : <XMarkIcon className="w-3.5 h-3.5" />}
              Reject Selected
            </button>
            <div className="ml-auto">
              <button
                onClick={() => setSelectedIds(new Set())}
                className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
              >
                Clear selection
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
