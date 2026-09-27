/**
 * CRM DLQ Page (/dashboard/crm-dlq) — BC-018
 *
 * Ops dashboard for filtering CRM-specific Dead Letter Queue entries.
 *
 * Surfaces the 3 BC-017 CRM error_types as separate KPI tiles so ops can
 * immediately see what's broken:
 *
 *   - crm_escalation_push_failed        (Node 8 — recoverable)
 *   - crm_resume_push_failed            (guidance flow — recoverable)
 *   - crm_permanent_failure_push_failed (worst case — MANUAL ACTION REQUIRED)
 *
 * Includes a filterable table of DLQ entries with retry + resolve actions.
 * The "Permanent Failure" entries also show a link to the runbook
 * (documents/ops_runbooks/crm_permanent_failure_push_failed_runbook.md).
 */

'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { cn } from '@/lib/utils';
import KPICard from '@/components/dashboard/KPICard';
import {
  dlqApi,
  BC017_CRM_ERROR_TYPES,
  CRM_ERROR_TYPE_LABELS,
  type DLQEntry,
  type DLQStats,
} from '@/lib/dlq-api';
import { toast } from 'react-hot-toast';
import {
  AlertTriangle,
  RefreshCw,
  CheckCircle2,
  AlertOctagon,
  ExternalLink,
  Filter,
  Loader2,
} from 'lucide-react';

// ── Inline SVG Icons (mirror DashboardSidebar pattern) ───────────────

const Icons = {
  escalation: (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
    </svg>
  ),
  resume: (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99" />
    </svg>
  ),
  permanentFailure: (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
    </svg>
  ),
};

// ── Types ─────────────────────────────────────────────────────────────

type ErrorTypeFilter = 'all' | 'crm_only' | (typeof BC017_CRM_ERROR_TYPES)[number];

// ── Page Component ────────────────────────────────────────────────────

export default function CrmDlqPage() {
  const [stats, setStats] = useState<DLQStats | null>(null);
  const [entries, setEntries] = useState<DLQEntry[]>([]);
  const [isLoadingStats, setIsLoadingStats] = useState(true);
  const [isLoadingEntries, setIsLoadingEntries] = useState(true);
  const [errorTypeFilter, setErrorTypeFilter] = useState<ErrorTypeFilter>('crm_only');
  const [showResolved, setShowResolved] = useState(false);
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null);
  const [refreshCounter, setRefreshCounter] = useState(0);

  // ── Data fetching ──────────────────────────────────────────────────

  const fetchStats = useCallback(async () => {
    setIsLoadingStats(true);
    try {
      const response = await dlqApi.stats();
      if (response) {
        setStats(response);
      }
    } catch (err) {
      console.error('Failed to fetch DLQ stats:', err);
      toast.error('Failed to load DLQ stats');
    } finally {
      setIsLoadingStats(false);
    }
  }, []);

  const fetchEntries = useCallback(async () => {
    setIsLoadingEntries(true);
    try {
      const params: Parameters<typeof dlqApi.list>[0] = {
        resolved: showResolved,
        limit: 100,
      };
      if (errorTypeFilter === 'all') {
        // no error_type filter — return everything
      } else if (errorTypeFilter === 'crm_only') {
        params.error_type = 'crm_only';
      } else {
        params.error_type = errorTypeFilter;
      }
      const response = await dlqApi.list(params);
      if (response) {
        setEntries(response.entries || []);
      }
    } catch (err) {
      console.error('Failed to fetch DLQ entries:', err);
      toast.error('Failed to load DLQ entries');
    } finally {
      setIsLoadingEntries(false);
    }
  }, [errorTypeFilter, showResolved]);

  useEffect(() => {
    fetchStats();
  }, [fetchStats, refreshCounter]);

  useEffect(() => {
    fetchEntries();
  }, [fetchEntries, refreshCounter]);

  // Auto-refresh every 30s
  useEffect(() => {
    const interval = setInterval(() => {
      setRefreshCounter((c) => c + 1);
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  // ── Actions ────────────────────────────────────────────────────────

  const handleRetry = async (entryId: string) => {
    setActionLoadingId(entryId);
    try {
      await dlqApi.retry(entryId);
      toast.success('DLQ entry marked as retried');
      setRefreshCounter((c) => c + 1);
    } catch (err) {
      console.error('Retry failed:', err);
      toast.error('Failed to retry DLQ entry');
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleResolve = async (entryId: string, errorType: string | null) => {
    // For permanent-failure entries, require explicit confirmation that the
    // runbook was followed (we use a simple window.confirm for now).
    if (errorType === 'crm_permanent_failure_push_failed') {
      const confirmed = window.confirm(
        'Have you completed the runbook?\n\n' +
        'This entry is a worst-case permanent failure. Before resolving:\n' +
        '1. Reset the CRM ticket to open/new (Zendesk/HubSpot/Generic)\n' +
        '2. Add the internal note per the runbook\n' +
        '3. Notify the human support team\n\n' +
        'See: documents/ops_runbooks/crm_permanent_failure_push_failed_runbook.md\n\n' +
        'Click OK to mark as resolved (retry_succeeded=false).'
      );
      if (!confirmed) return;
    }

    setActionLoadingId(entryId);
    try {
      const retrySucceeded = errorType !== 'crm_permanent_failure_push_failed';
      await dlqApi.resolve(entryId, retrySucceeded);
      toast.success('DLQ entry resolved');
      setRefreshCounter((c) => c + 1);
    } catch (err) {
      console.error('Resolve failed:', err);
      toast.error('Failed to resolve DLQ entry');
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleManualRefresh = () => {
    setRefreshCounter((c) => c + 1);
  };

  // ── Render ─────────────────────────────────────────────────────────

  const permanentFailureCount = stats?.crm_unresolved_by_type?.crm_permanent_failure_push_failed ?? 0;
  const escalationCount = stats?.crm_unresolved_by_type?.crm_escalation_push_failed ?? 0;
  const resumeCount = stats?.crm_unresolved_by_type?.crm_resume_push_failed ?? 0;

  return (
    <div className="space-y-6">
      {/* ── Page Header ─────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <AlertTriangle className="w-6 h-6 text-amber-400" />
            CRM Dead Letter Queue
          </h1>
          <p className="text-sm text-zinc-500 mt-1">
            CRM-specific failures from Node 8 escalation, guidance flow resume, and AI permanent failure paths (BC-017).
          </p>
        </div>
        <button
          onClick={handleManualRefresh}
          disabled={isLoadingStats || isLoadingEntries}
          className="flex items-center gap-2 px-3 py-2 rounded-lg bg-white/[0.05] hover:bg-white/[0.08] text-zinc-300 hover:text-white transition-colors text-sm font-medium disabled:opacity-50"
        >
          <RefreshCw className={cn('w-4 h-4', (isLoadingStats || isLoadingEntries) && 'animate-spin')} />
          Refresh
        </button>
      </div>

      {/* ── Permanent Failure Alert Banner ──────────────────────────── */}
      {permanentFailureCount > 0 && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/5 p-4 flex items-start gap-3">
          <AlertOctagon className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="text-sm font-semibold text-red-300">
              {permanentFailureCount} ticket{permanentFailureCount === 1 ? '' : 's'} require MANUAL CRM RESET
            </p>
            <p className="text-xs text-zinc-400 mt-1">
              AI gave up AND we could not tell the CRM. The CRM ticket is still showing as escalated/pending — human agents can not see it. Follow the runbook to manually reset each ticket.
            </p>
            <a
              href="https://github.com/abhaythakur754-0/parwa/blob/dashboard/documents/ops_runbooks/crm_permanent_failure_push_failed_runbook.md"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 mt-2 text-xs font-medium text-red-300 hover:text-red-200"
            >
              Open runbook
              <ExternalLink className="w-3 h-3" />
            </a>
          </div>
        </div>
      )}

      {/* ── KPI Tiles: 3 BC-017 CRM error_types ─────────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
        <KPICard
          title="Escalation Push Failed"
          value={isLoadingStats ? '—' : escalationCount}
          subtitle="Node 8 → CRM"
          icon={Icons.escalation}
          variant={escalationCount > 0 ? 'warning' : 'success'}
          isLoading={isLoadingStats}
        />
        <KPICard
          title="Resume Push Failed"
          value={isLoadingStats ? '—' : resumeCount}
          subtitle="Guidance flow → CRM"
          icon={Icons.resume}
          variant={resumeCount > 0 ? 'warning' : 'success'}
          isLoading={isLoadingStats}
        />
        <KPICard
          title="Permanent Failure — MANUAL ACTION"
          value={isLoadingStats ? '—' : permanentFailureCount}
          subtitle="AI gave up + CRM not told"
          icon={Icons.permanentFailure}
          variant={permanentFailureCount > 0 ? 'danger' : 'success'}
          isLoading={isLoadingStats}
        />
      </div>

      {/* ── Filter Bar ──────────────────────────────────────────────── */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2 flex-wrap">
          <Filter className="w-4 h-4 text-zinc-500" />
          <FilterButton
            label="All CRM (BC-017)"
            active={errorTypeFilter === 'crm_only'}
            onClick={() => setErrorTypeFilter('crm_only')}
          />
          <FilterButton
            label="Escalation"
            active={errorTypeFilter === 'crm_escalation_push_failed'}
            onClick={() => setErrorTypeFilter('crm_escalation_push_failed')}
          />
          <FilterButton
            label="Resume"
            active={errorTypeFilter === 'crm_resume_push_failed'}
            onClick={() => setErrorTypeFilter('crm_resume_push_failed')}
          />
          <FilterButton
            label="Permanent Failure"
            active={errorTypeFilter === 'crm_permanent_failure_push_failed'}
            danger
            onClick={() => setErrorTypeFilter('crm_permanent_failure_push_failed')}
          />
          <FilterButton
            label="All Error Types"
            active={errorTypeFilter === 'all'}
            onClick={() => setErrorTypeFilter('all')}
          />
        </div>

        <label className="flex items-center gap-2 text-sm text-zinc-400 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={showResolved}
            onChange={(e) => setShowResolved(e.target.checked)}
            className="w-4 h-4 rounded border-white/[0.1] bg-white/[0.05] text-orange-500 focus:ring-orange-500/20"
          />
          Show resolved
        </label>
      </div>

      {/* ── Entries Table ───────────────────────────────────────────── */}
      <div className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] overflow-hidden">
        {isLoadingEntries ? (
          <div className="p-12 flex items-center justify-center">
            <Loader2 className="w-6 h-6 text-zinc-500 animate-spin" />
          </div>
        ) : entries.length === 0 ? (
          <div className="p-12 text-center">
            <CheckCircle2 className="w-12 h-12 text-emerald-500/30 mx-auto mb-3" />
            <p className="text-sm text-zinc-400">No DLQ entries match the current filter</p>
            <p className="text-xs text-zinc-600 mt-1">
              {showResolved ? 'No resolved entries either — system is healthy.' : 'All CRM pushes are succeeding.'}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/[0.06] text-xs uppercase tracking-wider text-zinc-500">
                  <th className="text-left font-medium px-4 py-3">Error Type</th>
                  <th className="text-left font-medium px-4 py-3">CRM Ticket</th>
                  <th className="text-left font-medium px-4 py-3">Provider</th>
                  <th className="text-left font-medium px-4 py-3">Attempts</th>
                  <th className="text-left font-medium px-4 py-3">Created</th>
                  <th className="text-left font-medium px-4 py-3">Last Retry</th>
                  <th className="text-right font-medium px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((entry) => {
                  const errorInfo = entry.error_type
                    ? CRM_ERROR_TYPE_LABELS[entry.error_type]
                    : null;
                  const isPermanent =
                    entry.error_type === 'crm_permanent_failure_push_failed';
                  const snapshot: Record<string, unknown> = entry.state_snapshot || {};
                  return (
                    <tr
                      key={entry.id}
                      className={cn(
                        'border-b border-white/[0.04] hover:bg-white/[0.02] transition-colors',
                        isPermanent && 'bg-red-500/[0.02]',
                      )}
                    >
                      <td className="px-4 py-3 max-w-xs">
                        <div className="flex items-center gap-2">
                          {isPermanent && (
                            <AlertOctagon className="w-4 h-4 text-red-400 shrink-0" />
                          )}
                          <div className="min-w-0">
                            <p
                              className={cn(
                                'font-medium truncate',
                                isPermanent ? 'text-red-300' : 'text-zinc-200',
                              )}
                              title={entry.error_type || 'unknown'}
                            >
                              {errorInfo?.label || entry.error_type || 'unknown'}
                            </p>
                            <p
                              className="text-xs text-zinc-500 truncate mt-0.5"
                              title={entry.error}
                            >
                              {entry.error?.slice(0, 80)}
                              {entry.error && entry.error.length > 80 ? '…' : ''}
                            </p>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <code className="text-xs text-zinc-300 bg-white/[0.05] px-1.5 py-0.5 rounded">
                          {(snapshot.crm_ticket_id as string | undefined) || entry.conversation_id || entry.id.slice(0, 8)}
                        </code>
                      </td>
                      <td className="px-4 py-3 text-zinc-300">
                        {(snapshot.crm_provider as string | undefined) || '—'}
                      </td>
                      <td className="px-4 py-3 text-zinc-300">
                        {(snapshot.reprocess_attempts as number | undefined) ?? entry.retry_count}
                      </td>
                      <td className="px-4 py-3 text-zinc-400 text-xs">
                        {formatDate(entry.created_at)}
                      </td>
                      <td className="px-4 py-3 text-zinc-400 text-xs">
                        {entry.last_retry_at ? formatDate(entry.last_retry_at) : '—'}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end gap-1">
                          {isPermanent && (
                            <a
                              href="https://github.com/abhaythakur754-0/parwa/blob/dashboard/documents/ops_runbooks/crm_permanent_failure_push_failed_runbook.md"
                              target="_blank"
                              rel="noopener noreferrer"
                              className="p-1.5 rounded text-zinc-500 hover:text-orange-400 hover:bg-white/[0.05] transition-colors"
                              title="Open runbook"
                            >
                              <ExternalLink className="w-4 h-4" />
                            </a>
                          )}
                          <button
                            onClick={() => handleRetry(entry.id)}
                            disabled={actionLoadingId === entry.id || showResolved}
                            className="p-1.5 rounded text-zinc-500 hover:text-amber-400 hover:bg-white/[0.05] transition-colors disabled:opacity-30"
                            title="Mark as retried"
                          >
                            <RefreshCw className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => handleResolve(entry.id, entry.error_type)}
                            disabled={actionLoadingId === entry.id || showResolved}
                            className={cn(
                              'p-1.5 rounded transition-colors disabled:opacity-30',
                              isPermanent
                                ? 'text-zinc-500 hover:text-red-400 hover:bg-white/[0.05]'
                                : 'text-zinc-500 hover:text-emerald-400 hover:bg-white/[0.05]',
                            )}
                            title={
                              isPermanent
                                ? 'Resolve (after runbook complete)'
                                : 'Resolve'
                            }
                          >
                            {actionLoadingId === entry.id ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <CheckCircle2 className="w-4 h-4" />
                            )}
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── Footer Info ─────────────────────────────────────────────── */}
      <div className="text-xs text-zinc-600 space-y-1">
        <p>
          <strong className="text-zinc-400">Retry</strong>: marks the entry as retried (increments retry_count). Does NOT re-execute the graph.
        </p>
        <p>
          <strong className="text-zinc-400">Resolve</strong>: soft-closes the entry. For permanent failures, confirm the runbook is complete first.
        </p>
        <p>
          Auto-refreshes every 30 seconds. Last refreshed: {new Date().toLocaleTimeString()}.
        </p>
      </div>
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────

function FilterButton({
  label,
  active,
  onClick,
  danger,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
  danger?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'px-3 py-1.5 rounded-lg text-xs font-medium transition-all',
        active
          ? danger
            ? 'bg-red-500/15 text-red-300 border border-red-500/30'
            : 'bg-orange-500/10 text-orange-400 border border-orange-500/30'
          : 'text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.04] border border-transparent',
      )}
    >
      {label}
    </button>
  );
}

function formatDate(isoString: string | null): string {
  if (!isoString) return '—';
  try {
    const d = new Date(isoString);
    return d.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return isoString;
  }
}
