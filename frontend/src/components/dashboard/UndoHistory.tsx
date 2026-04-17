'use client';

import React, { useState, useEffect, useCallback } from 'react';
import toast from 'react-hot-toast';
import { getErrorMessage } from '@/lib/api';
import { cn } from '@/lib/utils';
import apiClient from '@/lib/api';

// ── Skeleton Helper ────────────────────────────────────────────────────────

function Skeleton({ className }: { className?: string }) {
  return <div className={cn('animate-pulse rounded-lg bg-white/[0.06]', className)} />;
}

// ── Inline SVG Icons ───────────────────────────────────────────────────────

function ClockIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
    </svg>
  );
}

function ArrowUturnLeftIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 15 3 9m0 0 6-6M3 9h12a6 6 0 0 1 0 12h-3" />
    </svg>
  );
}

function UserIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.501 20.118a7.5 7.5 0 0 1 14.998 0A17.933 17.933 0 0 1 12 21.75c-2.676 0-5.216-.584-7.499-1.632Z" />
    </svg>
  );
}

function DocumentTextIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
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

function ExclamationCircleIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 3.75h.008v.008H12v-.008Z" />
    </svg>
  );
}

// ── Types ──────────────────────────────────────────────────────────────────

interface UndoLogEntry {
  id: string;
  company_id: string;
  executed_action_id: string;
  undo_type: string;
  original_data: string | null;
  undo_data: string | null;
  undo_reason: string | null;
  undone_by: string | null;
  created_at: string;
  // Joined fields
  action_type?: string;
  undone_by_name?: string;
}

interface UndoHistoryProps {
  /** Show compact version */
  compact?: boolean;
  /** Max items to show */
  limit?: number;
  /** Additional CSS classes */
  className?: string;
}

// ── Constants ──────────────────────────────────────────────────────────────

const ACTION_LABELS: Record<string, string> = {
  refund: 'Refund',
  email_reply: 'Email Reply',
  sms_reply: 'SMS Reply',
  voice_reply: 'Voice Reply',
  ticket_close: 'Close Ticket',
  ticket_resolve: 'Resolve Ticket',
  account_change: 'Account Change',
  integration_action: 'Integration',
};

const UNDO_TYPE_LABELS: Record<string, string> = {
  reversal: 'Reversal',
  email_recall: 'Email Recall',
  sms_recall: 'SMS Recall',
  ticket_reopen: 'Ticket Reopen',
};

// ── Helper Functions ───────────────────────────────────────────────────────

function formatDateTime(dateStr: string | null | undefined): string {
  if (!dateStr) return 'N/A';
  try {
    return new Date(dateStr).toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return 'N/A';
  }
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
    return formatDateTime(dateStr);
  } catch {
    return '';
  }
}

// ════════════════════════════════════════════════════════════════════════════
// UndoHistory Component
// ════════════════════════════════════════════════════════════════════════════

export default function UndoHistory({
  compact = false,
  limit = 10,
  className,
}: UndoHistoryProps) {
  // ── State ───────────────────────────────────────────────────────────────
  const [entries, setEntries] = useState<UndoLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // ── Load Undo History ───────────────────────────────────────────────────
  const loadHistory = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      const { data } = await apiClient.get(`/api/shadow/undo-history?limit=${limit}`);
      if (data && Array.isArray(data.entries || data)) {
        setEntries(data.entries || data);
      } else {
        // Mock data for development
        setEntries([]);
      }
    } catch {
      // For now, show empty state if endpoint doesn't exist
      setEntries([]);
    } finally {
      setLoading(false);
    }
  }, [limit]);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  // ── Export to CSV ───────────────────────────────────────────────────────
  const handleExportCSV = () => {
    if (entries.length === 0) {
      toast.error('No data to export');
      return;
    }

    const headers = ['Timestamp', 'Action Type', 'Undo Type', 'Reason', 'Undone By'];
    const rows = entries.map((e) => [
      e.created_at,
      e.action_type || 'Unknown',
      e.undo_type,
      e.undo_reason || '',
      e.undone_by_name || e.undone_by || '',
    ]);

    const csv = [
      headers.join(','),
      ...rows.map((r) => r.map((v) => `"${v}"`).join(',')),
    ].join('\n');

    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `undo-history-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success('CSV exported');
  };

  // ════════════════════════════════════════════════════════════════════════
  // Render
  // ════════════════════════════════════════════════════════════════════════

  return (
    <div className={cn('relative', className)}>
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <ClockIcon className="h-5 w-5 text-[#FF7F11]" />
          <h3 className="text-base font-semibold text-white">
            {compact ? 'History' : 'Undo History'}
          </h3>
          {!loading && entries.length > 0 && (
            <span className="ml-1 text-xs text-zinc-500 bg-white/[0.04] px-2 py-0.5 rounded-md">
              {entries.length}
            </span>
          )}
        </div>
        {!loading && entries.length > 0 && !compact && (
          <button
            onClick={handleExportCSV}
            className="inline-flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
          >
            <DownloadIcon className="h-3.5 w-3.5" />
            Export CSV
          </button>
        )}
      </div>

      {/* ── Content ──────────────────────────────────────────────────────── */}
      {loading ? (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-16" />
          ))}
        </div>
      ) : error ? (
        <div className="rounded-lg border border-white/[0.06] bg-[#1A1A1A] p-4">
          <div className="flex items-center gap-2 text-zinc-500">
            <ExclamationCircleIcon className="h-4 w-4" />
            <p className="text-sm">Unable to load undo history</p>
          </div>
          <button
            onClick={loadHistory}
            className="mt-2 text-xs text-[#FF7F11] hover:underline"
          >
            Try again
          </button>
        </div>
      ) : entries.length === 0 ? (
        <div className="rounded-lg border border-white/[0.06] bg-[#1A1A1A] p-6 text-center">
          <DocumentTextIcon className="h-10 w-10 text-zinc-700 mx-auto mb-3" />
          <p className="text-sm text-zinc-500">No undo history</p>
          {!compact && (
            <p className="text-xs text-zinc-600 mt-1">
              Actions that have been undone will appear here
            </p>
          )}
        </div>
      ) : (
        <div className="space-y-2">
          {entries.map((entry) => {
            const isExpanded = expandedId === entry.id;

            return (
              <div
                key={entry.id}
                className={cn(
                  'rounded-lg border border-white/[0.06] bg-[#1A1A1A] overflow-hidden transition-all',
                  isExpanded && 'ring-1 ring-[#FF7F11]/20'
                )}
              >
                {/* ── Row ────────────────────────────────────────────────── */}
                <div
                  className="p-3 cursor-pointer hover:bg-white/[0.02]"
                  onClick={() => setExpandedId(isExpanded ? null : entry.id)}
                >
                  <div className="flex items-start justify-between gap-3">
                    {/* Left: Action Info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <ArrowUturnLeftIcon className="h-4 w-4 text-orange-400 shrink-0" />
                        <span className="text-sm font-medium text-white truncate">
                          {ACTION_LABELS[entry.action_type || ''] || entry.action_type || 'Action'}
                        </span>
                        <span className="text-[10px] text-zinc-600 bg-white/[0.04] px-1.5 py-0.5 rounded">
                          {UNDO_TYPE_LABELS[entry.undo_type] || entry.undo_type}
                        </span>
                      </div>
                      <div className="flex items-center gap-3 text-xs text-zinc-500">
                        <span className="flex items-center gap-1">
                          <ClockIcon className="h-3 w-3" />
                          {formatRelativeTime(entry.created_at)}
                        </span>
                        {entry.undone_by_name && (
                          <span className="flex items-center gap-1">
                            <UserIcon className="h-3 w-3" />
                            {entry.undone_by_name}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Right: Expand indicator */}
                    <svg
                      className={cn('w-4 h-4 text-zinc-600 transition-transform', isExpanded && 'rotate-180')}
                      fill="none"
                      viewBox="0 0 24 24"
                      strokeWidth={2}
                      stroke="currentColor"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
                    </svg>
                  </div>
                </div>

                {/* ── Expanded Content ────────────────────────────────────── */}
                {isExpanded && (
                  <div className="border-t border-white/[0.06] p-4 bg-white/[0.01]">
                    <div className="space-y-3">
                      {/* Reason */}
                      {entry.undo_reason && (
                        <div>
                          <p className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider mb-1">
                            Undo Reason
                          </p>
                          <p className="text-sm text-zinc-300">{entry.undo_reason}</p>
                        </div>
                      )}

                      {/* Original Data */}
                      {entry.original_data && (
                        <div>
                          <p className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider mb-1">
                            Original Action Data
                          </p>
                          <pre className="rounded-lg bg-[#0A0A0A] border border-white/[0.04] p-3 text-xs text-zinc-400 overflow-x-auto max-h-32 font-mono">
                            {(() => {
                              try {
                                return JSON.stringify(JSON.parse(entry.original_data), null, 2);
                              } catch {
                                return entry.original_data;
                              }
                            })()}
                          </pre>
                        </div>
                      )}

                      {/* Meta */}
                      <div className="flex items-center gap-4 text-xs text-zinc-500 pt-2 border-t border-white/[0.04]">
                        <span>Undone at: {formatDateTime(entry.created_at)}</span>
                        <span>ID: {entry.id.slice(0, 8)}...</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
