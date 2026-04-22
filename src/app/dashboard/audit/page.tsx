'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { getErrorMessage } from '@/lib/api';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import {
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell,
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import apiClient from '@/lib/api';

// ── Types ───────────────────────────────────────────────────────────────

interface AuditEntry {
  id: string;
  actor_id: string | null;
  actor_type: string;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  ip_address: string | null;
  old_value: string | null;
  new_value: string | null;
  created_at: string | null;
}

interface AuditStats {
  action_counts: Record<string, number>;
  actor_type_counts: Record<string, number>;
  most_active_actors: Array<{ actor_id: string; actor_type: string; count: number }>;
  recent_24h_count: number;
  total_count: number;
  period_days: number;
}

interface AuditTrailResponse {
  items: AuditEntry[];
  total: number;
  offset: number;
  limit: number;
}

// ── Constants ───────────────────────────────────────────────────────────

const PAGE_SIZE = 25;

const ACTOR_TYPE_OPTIONS = [
  { value: 'all', label: 'All Actors' },
  { value: 'user', label: 'User' },
  { value: 'system', label: 'System' },
  { value: 'api_key', label: 'API Key' },
];

// ── Action color styles ─────────────────────────────────────────────────

const ACTION_STYLES: Record<string, string> = {
  create: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20',
  read: 'bg-blue-500/15 text-blue-400 border-blue-500/20',
  update: 'bg-amber-500/15 text-amber-400 border-amber-500/20',
  delete: 'bg-red-500/15 text-red-400 border-red-500/20',
  login: 'bg-cyan-500/15 text-cyan-400 border-cyan-500/20',
  logout: 'bg-zinc-500/15 text-zinc-400 border-zinc-500/20',
  login_failed: 'bg-red-500/15 text-red-400 border-red-500/20',
  approve: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20',
  reject: 'bg-red-500/15 text-red-400 border-red-500/20',
  export: 'bg-violet-500/15 text-violet-400 border-violet-500/20',
  settings_change: 'bg-amber-500/15 text-amber-400 border-amber-500/20',
  permission_change: 'bg-orange-500/15 text-orange-400 border-orange-500/20',
  api_key_create: 'bg-blue-500/15 text-blue-400 border-blue-500/20',
  api_key_rotate: 'bg-amber-500/15 text-amber-400 border-amber-500/20',
  api_key_revoke: 'bg-red-500/15 text-red-400 border-red-500/20',
  webhook_delivered: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20',
  webhook_failed: 'bg-red-500/15 text-red-400 border-red-500/20',
};

function formatAction(action: string): string {
  return action.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

// ── Helpers ─────────────────────────────────────────────────────────────

function formatTimestamp(dateStr: string | null): string {
  if (!dateStr) return '\u2014';
  const d = new Date(dateStr);
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function relativeTime(dateStr: string | null): string {
  if (!dateStr) return '';
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffSec = Math.round((now - then) / 1000);
  if (diffSec < 60) return `${diffSec}s ago`;
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
  if (diffSec < 2592000) return `${Math.floor(diffSec / 86400)}d ago`;
  return new Date(dateStr).toLocaleDateString();
}

function truncateId(id: string | null): string {
  if (!id) return '\u2014';
  return id.length > 10 ? `${id.slice(0, 8)}\u2026` : id;
}

// ── Inline SVG Icons ────────────────────────────────────────────────────

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

const SearchIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z" />
  </svg>
);

const FilterIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 3c2.755 0 5.455.232 8.083.678.533.09.917.556.917 1.096v1.044a2.25 2.25 0 0 1-.659 1.591l-5.432 5.432a2.25 2.25 0 0 0-.659 1.591v2.927a2.25 2.25 0 0 1-1.244 2.013L9.75 21v-6.568a2.25 2.25 0 0 0-.659-1.591L3.659 7.409A2.25 2.25 0 0 1 3 5.818V4.774c0-.54.384-1.006.917-1.096A48.32 48.32 0 0 1 12 3Z" />
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

const ShieldCheckIcon = () => (
  <svg className="w-12 h-12" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75m-3-7.036A11.959 11.959 0 0 1 3.598 6 11.99 11.99 0 0 0 3 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285Z" />
  </svg>
);

const ActivityIcon = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 12h16.5m-16.5 3.75h16.5M3.75 19.5h16.5M5.625 4.5h12.75a1.875 1.875 0 0 1 0 3.75H5.625a1.875 1.875 0 0 1 0-3.75Z" />
  </svg>
);

const ClockIcon = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
  </svg>
);

const TrendingIcon = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18 9 11.25l4.306 4.306a11.95 11.95 0 0 1 5.814-5.518l2.74-1.22m0 0-5.94-2.281m5.94 2.28-2.28 5.941" />
  </svg>
);

// ── Skeleton Rows ───────────────────────────────────────────────────────

function SkeletonRows() {
  return (
    <>
      {Array.from({ length: 10 }).map((_, i) => (
        <TableRow key={i} className="hover:bg-transparent">
          <TableCell className="p-3"><Skeleton className="h-4 w-36" /></TableCell>
          <TableCell className="p-3"><Skeleton className="h-4 w-24" /></TableCell>
          <TableCell className="p-3"><Skeleton className="h-5 w-20 rounded-full" /></TableCell>
          <TableCell className="p-3"><Skeleton className="h-4 w-24" /></TableCell>
          <TableCell className="p-3"><Skeleton className="h-4 w-20" /></TableCell>
          <TableCell className="p-3 hidden md:table-cell"><Skeleton className="h-4 w-32" /></TableCell>
        </TableRow>
      ))}
    </>
  );
}

// ── Main Component ──────────────────────────────────────────────────────

export default function AuditLogPage() {
  const { user } = useAuth();
  const isAdminOrOwner = user?.role === 'owner' || user?.role === 'admin';

  // Data state
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [statsLoading, setStatsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Stats state
  const [stats, setStats] = useState<AuditStats | null>(null);

  // Filter options state
  const [actionTypes, setActionTypes] = useState<string[]>([]);
  const [resourceTypes, setResourceTypes] = useState<string[]>([]);

  // Filter state
  const [actionFilter, setActionFilter] = useState<string>('all');
  const [resourceTypeFilter, setResourceTypeFilter] = useState<string>('all');
  const [actorTypeFilter, setActorTypeFilter] = useState<string>('all');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  // Export state
  const [exporting, setExporting] = useState(false);

  // ── Compute total pages ───────────────────────────────────────────

  const totalPages = Math.ceil(total / PAGE_SIZE);
  const offset = (page - 1) * PAGE_SIZE;

  // ── Fetch audit trail ─────────────────────────────────────────────

  const fetchTrail = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string | number> = {
        offset,
        limit: PAGE_SIZE,
      };
      if (actionFilter !== 'all') params.action = actionFilter;
      if (resourceTypeFilter !== 'all') params.resource_type = resourceTypeFilter;
      if (actorTypeFilter !== 'all') params.actor_type = actorTypeFilter;
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo) params.date_to = dateTo;

      const { data } = await apiClient.get<AuditTrailResponse>('/api/audit/trail', { params });
      setEntries(data.items || []);
      setTotal(data.total || 0);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [offset, actionFilter, resourceTypeFilter, actorTypeFilter, dateFrom, dateTo]);

  // ── Fetch stats ───────────────────────────────────────────────────

  const fetchStats = useCallback(async () => {
    setStatsLoading(true);
    try {
      const { data } = await apiClient.get<AuditStats>('/api/audit/stats');
      setStats(data);
    } catch {
      // Stats are non-critical
    } finally {
      setStatsLoading(false);
    }
  }, []);

  // ── Fetch filter options ──────────────────────────────────────────

  const fetchFilterOptions = useCallback(async () => {
    try {
      const [actionsRes, resourceTypesRes] = await Promise.all([
        apiClient.get<{ actions: string[] }>('/api/audit/actions'),
        apiClient.get<{ resource_types: string[] }>('/api/audit/resource-types'),
      ]);
      setActionTypes(actionsRes.data.actions || []);
      setResourceTypes(resourceTypesRes.data.resource_types || []);
    } catch {
      // Non-critical
    }
  }, []);

  // ── Load on mount ─────────────────────────────────────────────────

  useEffect(() => {
    fetchTrail();
    fetchStats();
    fetchFilterOptions();
  }, [fetchTrail, fetchStats, fetchFilterOptions]);

  // ── Filter handlers (reset to page 1) ─────────────────────────────

  const handleActionChange = (value: string) => { setActionFilter(value); setPage(1); };
  const handleResourceTypeChange = (value: string) => { setResourceTypeFilter(value); setPage(1); };
  const handleActorTypeChange = (value: string) => { setActorTypeFilter(value); setPage(1); };

  // ── Clear filters ─────────────────────────────────────────────────

  const clearFilters = () => {
    setActionFilter('all');
    setResourceTypeFilter('all');
    setActorTypeFilter('all');
    setDateFrom('');
    setDateTo('');
    setPage(1);
  };

  const hasActiveFilters = actionFilter !== 'all' || resourceTypeFilter !== 'all' || actorTypeFilter !== 'all' || dateFrom || dateTo;

  // ── Export handler ────────────────────────────────────────────────

  const handleExport = async () => {
    setExporting(true);
    try {
      const params: Record<string, string> = { format: 'json' };
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo) params.date_to = dateTo;

      const response = await apiClient.get('/api/audit/export', {
        params,
        responseType: 'blob',
      });

      // Extract filename from Content-Disposition header
      const contentDisposition = response.headers['content-disposition'] || '';
      const filenameMatch = contentDisposition.match(/filename="(.+?)"/);
      const filename = filenameMatch ? filenameMatch[1] : `audit-export-${Date.now()}.json`;

      const blob = new Blob([JSON.stringify(response.data, null, 2)], { type: 'application/json' });
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = filename;
      link.click();
      URL.revokeObjectURL(link.href);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setExporting(false);
    }
  };

  // ── Most common action (for stats card) ───────────────────────────

  const mostCommonAction = stats?.action_counts
    ? Object.entries(stats.action_counts).sort((a, b) => b[1] - a[1])[0]
    : null;

  // ── Pagination helpers ────────────────────────────────────────────

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

  // ── Render ────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-[#0D0D0D] p-4 md:p-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-zinc-100">Audit Log</h1>
          <p className="text-sm text-zinc-500 mt-0.5">
            {loading ? 'Loading...' : `${total} entr${total !== 1 ? 'ies' : 'y'} found`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {isAdminOrOwner && (
            <Button
              variant="ghost"
              size="sm"
              className="text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.04]"
              onClick={handleExport}
              disabled={exporting}
            >
              <DownloadIcon />
              {exporting ? 'Exporting...' : 'Export JSON'}
            </Button>
          )}
          <Button
            variant="ghost"
            size="sm"
            className="text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.04]"
            onClick={() => { fetchTrail(); fetchStats(); }}
          >
            <RefreshIcon />
            Refresh
          </Button>
        </div>
      </div>

      {/* Stats Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        {/* Total Entries Card */}
        <div className="bg-[#111111] border border-white/[0.06] rounded-xl p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center text-blue-400">
              <ActivityIcon />
            </div>
            <div className="min-w-0">
              <p className="text-xs text-zinc-500 font-medium uppercase tracking-wider">Total Entries</p>
              <p className="text-xl font-semibold text-zinc-100">
                {statsLoading ? <Skeleton className="h-7 w-16 inline-block" /> : (stats?.total_count ?? 0).toLocaleString()}
              </p>
              <p className="text-[11px] text-zinc-600">Last {stats?.period_days ?? 30} days</p>
            </div>
          </div>
        </div>

        {/* Last 24h Card */}
        <div className="bg-[#111111] border border-white/[0.06] rounded-xl p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-emerald-500/10 flex items-center justify-center text-emerald-400">
              <ClockIcon />
            </div>
            <div className="min-w-0">
              <p className="text-xs text-zinc-500 font-medium uppercase tracking-wider">Last 24 Hours</p>
              <p className="text-xl font-semibold text-zinc-100">
                {statsLoading ? <Skeleton className="h-7 w-10 inline-block" /> : (stats?.recent_24h_count ?? 0).toLocaleString()}
              </p>
              <p className="text-[11px] text-zinc-600">Recent activity</p>
            </div>
          </div>
        </div>

        {/* Most Common Action Card */}
        <div className="bg-[#111111] border border-white/[0.06] rounded-xl p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-orange-500/10 flex items-center justify-center text-orange-400">
              <TrendingIcon />
            </div>
            <div className="min-w-0">
              <p className="text-xs text-zinc-500 font-medium uppercase tracking-wider">Top Action</p>
              <p className="text-xl font-semibold text-zinc-100">
                {statsLoading ? <Skeleton className="h-7 w-24 inline-block" /> : mostCommonAction ? formatAction(mostCommonAction[0]) : '\u2014'}
              </p>
              {mostCommonAction && (
                <p className="text-[11px] text-zinc-600">{mostCommonAction[1].toLocaleString()} occurrences</p>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="bg-[#111111] border border-white/[0.06] rounded-xl p-4 mb-4">
        <div className="flex flex-col lg:flex-row lg:items-center gap-3">
          <div className="flex flex-wrap items-center gap-2 flex-1">
            {/* Action Type Filter */}
            <Select value={actionFilter} onValueChange={handleActionChange}>
              <SelectTrigger size="sm" className="w-[150px] bg-[#1A1A1A] border-white/[0.06] text-zinc-300 text-xs">
                <SelectValue placeholder="All Actions" />
              </SelectTrigger>
              <SelectContent className="bg-[#1A1A1A] border-white/[0.06]">
                <SelectItem value="all" className="text-zinc-300">All Actions</SelectItem>
                {actionTypes.map(action => (
                  <SelectItem key={action} value={action} className="text-zinc-300">
                    {formatAction(action)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            {/* Resource Type Filter */}
            <Select value={resourceTypeFilter} onValueChange={handleResourceTypeChange}>
              <SelectTrigger size="sm" className="w-[140px] bg-[#1A1A1A] border-white/[0.06] text-zinc-300 text-xs">
                <SelectValue placeholder="All Resources" />
              </SelectTrigger>
              <SelectContent className="bg-[#1A1A1A] border-white/[0.06]">
                <SelectItem value="all" className="text-zinc-300">All Resources</SelectItem>
                {resourceTypes.map(rt => (
                  <SelectItem key={rt} value={rt} className="text-zinc-300 capitalize">
                    {rt}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            {/* Actor Type Filter */}
            <Select value={actorTypeFilter} onValueChange={handleActorTypeChange}>
              <SelectTrigger size="sm" className="w-[120px] bg-[#1A1A1A] border-white/[0.06] text-zinc-300 text-xs">
                <SelectValue placeholder="All Actors" />
              </SelectTrigger>
              <SelectContent className="bg-[#1A1A1A] border-white/[0.06]">
                {ACTOR_TYPE_OPTIONS.map(opt => (
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

      {/* Table */}
      <div className="bg-[#111111] border border-white/[0.06] rounded-xl overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="border-b border-white/[0.06] hover:bg-transparent">
              <TableHead className="p-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">
                Timestamp
              </TableHead>
              <TableHead className="p-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">
                Actor
              </TableHead>
              <TableHead className="p-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">
                Action
              </TableHead>
              <TableHead className="p-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">
                Resource
              </TableHead>
              <TableHead className="p-3 text-xs font-medium text-zinc-500 uppercase tracking-wider hidden md:table-cell">
                Resource ID
              </TableHead>
              <TableHead className="p-3 text-xs font-medium text-zinc-500 uppercase tracking-wider hidden lg:table-cell">
                IP Address
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody className="divide-y divide-white/[0.04]">
            {/* Loading state */}
            {loading && <SkeletonRows />}

            {/* Error state */}
            {!loading && error && (
              <TableRow className="hover:bg-transparent">
                <TableCell colSpan={6} className="py-16 text-center">
                  <div className="flex flex-col items-center gap-3">
                    <div className="w-12 h-12 rounded-full bg-red-500/10 flex items-center justify-center">
                      <svg className="w-6 h-6 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
                      </svg>
                    </div>
                    <p className="text-sm text-red-400">{error}</p>
                    <Button size="sm" variant="ghost" onClick={fetchTrail} className="text-zinc-400 hover:text-zinc-200">
                      <RefreshIcon /> Retry
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            )}

            {/* Empty state */}
            {!loading && !error && entries.length === 0 && (
              <TableRow className="hover:bg-transparent">
                <TableCell colSpan={6} className="py-16 text-center">
                  <div className="flex flex-col items-center gap-3">
                    <div className="w-16 h-16 rounded-2xl bg-zinc-800/50 flex items-center justify-center text-zinc-600">
                      <ShieldCheckIcon />
                    </div>
                    <p className="text-sm text-zinc-400 font-medium">No audit entries found</p>
                    <p className="text-xs text-zinc-600 max-w-xs">
                      {hasActiveFilters
                        ? 'Try adjusting your filters to find what you\'re looking for.'
                        : 'Audit entries will appear here when actions are performed in the system.'}
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

            {/* Data Rows */}
            {!loading && !error && entries.map((entry) => (
              <TableRow key={entry.id} className="hover:bg-white/[0.02] transition-colors">
                {/* Timestamp */}
                <TableCell className="p-3">
                  <div className="flex flex-col">
                    <span className="text-sm text-zinc-200">{formatTimestamp(entry.created_at)}</span>
                    <span className="text-[11px] text-zinc-600">{relativeTime(entry.created_at)}</span>
                  </div>
                </TableCell>

                {/* Actor */}
                <TableCell className="p-3">
                  <div className="flex flex-col">
                    <span className="text-sm text-zinc-300">{truncateId(entry.actor_id)}</span>
                    <Badge
                      variant="outline"
                      className={`text-[9px] font-medium w-fit ${
                        entry.actor_type === 'user'
                          ? 'bg-blue-500/10 text-blue-400 border-blue-500/15'
                          : entry.actor_type === 'system'
                          ? 'bg-zinc-500/10 text-zinc-400 border-zinc-500/15'
                          : 'bg-purple-500/10 text-purple-400 border-purple-500/15'
                      }`}
                    >
                      {entry.actor_type}
                    </Badge>
                  </div>
                </TableCell>

                {/* Action */}
                <TableCell className="p-3">
                  <Badge
                    variant="outline"
                    className={`text-[10px] font-medium ${ACTION_STYLES[entry.action] || 'bg-zinc-500/10 text-zinc-400 border-zinc-500/15'}`}
                  >
                    {formatAction(entry.action)}
                  </Badge>
                </TableCell>

                {/* Resource Type */}
                <TableCell className="p-3">
                  <span className="text-sm text-zinc-300 capitalize">
                    {entry.resource_type || '\u2014'}
                  </span>
                </TableCell>

                {/* Resource ID (hidden on mobile) */}
                <TableCell className="p-3 hidden md:table-cell">
                  <span className="text-sm text-zinc-500 font-mono">
                    {truncateId(entry.resource_id)}
                  </span>
                </TableCell>

                {/* IP Address (hidden on smaller screens) */}
                <TableCell className="p-3 hidden lg:table-cell">
                  <span className="text-sm text-zinc-500 font-mono">
                    {entry.ip_address || '\u2014'}
                  </span>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-white/[0.06]">
            <p className="text-xs text-zinc-500">
              Showing {offset + 1}-{Math.min(offset + PAGE_SIZE, total)} of {total}
            </p>
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="sm"
                className="h-7 px-2 text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.04]"
                disabled={page <= 1}
                onClick={() => setPage(p => p - 1)}
              >
                <ChevronLeftIcon />
              </Button>
              {getVisiblePages().map((p, i) =>
                p === -1 ? (
                  <span key={`ellipsis-${i}`} className="text-zinc-600 text-xs px-1">&hellip;</span>
                ) : (
                  <Button
                    key={p}
                    variant="ghost"
                    size="sm"
                    className={`h-7 w-7 p-0 text-xs ${
                      p === page
                        ? 'bg-[#FF7F11]/10 text-[#FF7F11] font-semibold'
                        : 'text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.04]'
                    }`}
                    onClick={() => setPage(p)}
                  >
                    {p}
                  </Button>
                ),
              )}
              <Button
                variant="ghost"
                size="sm"
                className="h-7 px-2 text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.04]"
                disabled={page >= totalPages}
                onClick={() => setPage(p => p + 1)}
              >
                <ChevronRightIcon />
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
