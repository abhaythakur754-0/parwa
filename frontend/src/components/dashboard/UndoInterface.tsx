'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import toast from 'react-hot-toast';
import { getErrorMessage } from '@/lib/api';
import { cn } from '@/lib/utils';
import { shadowApi, type ShadowLogEntry } from '@/lib/shadow-api';
import { useSocket } from '@/contexts/SocketContext';

// ── Skeleton Helper ────────────────────────────────────────────────────────

function Skeleton({ className }: { className?: string }) {
  return <div className={cn('animate-pulse rounded-lg bg-white/[0.06]', className)} />;
}

// ── Inline SVG Icons ───────────────────────────────────────────────────────

function ArrowUturnLeftIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 15 3 9m0 0 6-6M3 9h12a6 6 0 0 1 0 12h-3" />
    </svg>
  );
}

function ClockIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
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

function ExclamationCircleIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 3.75h.008v.008H12v-.008Z" />
    </svg>
  );
}

function HistoryIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
    </svg>
  );
}

// ── Format Helpers ─────────────────────────────────────────────────────────

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
    return `${diffDays}d ago`;
  } catch { return ''; }
}

// ── Action Type Labels ─────────────────────────────────────────────────────

const ACTION_LABELS: Record<string, string> = {
  refund: 'Refund Issued',
  email_reply: 'Email Sent',
  sms_reply: 'SMS Sent',
  voice_reply: 'Voice Reply Sent',
  ticket_close: 'Ticket Closed',
  account_change: 'Account Modified',
  integration_action: 'Integration Triggered',
};

function actionLabel(type: string): string {
  return ACTION_LABELS[type] || type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function actionDescription(entry: ShadowLogEntry): string {
  const label = actionLabel(entry.action_type);
  const payload = entry.action_payload;
  if (entry.action_type === 'refund' && payload?.amount) {
    return `${label} — $${payload.amount}`;
  }
  if (entry.action_type === 'ticket_close' && payload?.ticket_id) {
    return `${label} — Ticket #${payload.ticket_id}`;
  }
  if (entry.action_type === 'email_reply' && payload?.recipient) {
    return `${label} — to ${payload.recipient}`;
  }
  if (entry.action_type === 'sms_reply' && payload?.phone) {
    return `${label} — to ${payload.phone}`;
  }
  return label;
}

// ── Countdown Timer ────────────────────────────────────────────────────────

function CountdownTimer({ expiresAt }: { expiresAt: string }) {
  const [remaining, setRemaining] = useState<number>(0);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    const calc = () => {
      const diff = new Date(expiresAt).getTime() - Date.now();
      setRemaining(Math.max(0, diff));
    };
    calc();
    intervalRef.current = setInterval(calc, 1000);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [expiresAt]);

  if (remaining <= 0) return null;

  const mins = Math.floor(remaining / 60000);
  const secs = Math.floor((remaining % 60000) / 1000);

  return (
    <span className={cn(
      'inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[10px] font-mono font-medium',
      mins < 5 ? 'bg-red-500/15 text-red-400' : 'bg-zinc-500/15 text-zinc-400',
    )}>
      <ClockIcon className="w-3 h-3" />
      {mins > 0 ? `${mins}m ${secs}s` : `${secs}s`}
    </span>
  );
}

// ════════════════════════════════════════════════════════════════════════════
// UndoInterface Component
// ════════════════════════════════════════════════════════════════════════════

const UNDO_WINDOW_MS = 30 * 60 * 1000; // 30 minutes

export default function UndoInterface() {
  const { isConnected } = useSocket();

  // ── State ───────────────────────────────────────────────────────────────
  const [undoableActions, setUndoableActions] = useState<ShadowLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const [undoingId, setUndoingId] = useState<string | null>(null);
  const [confirmUndoId, setConfirmUndoId] = useState<string | null>(null);
  const [undoReason, setUndoReason] = useState('');
  const [showHistory, setShowHistory] = useState(false);

  // ── Load Undoable Actions ───────────────────────────────────────────────
  const loadUndoable = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      const data = await shadowApi.getLog({
        page: 1,
        page_size: 10,
        decision: 'approved',
        sort_by: 'created_at',
        sort_dir: 'desc',
      });
      const now = Date.now();
      const withinWindow = data.items.filter(entry => {
        if (!entry.created_at) return false;
        const created = new Date(entry.created_at).getTime();
        return (now - created) < UNDO_WINDOW_MS;
      });
      setUndoableActions(withinWindow);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadUndoable();
  }, [loadUndoable]);

  // ── Real-time updates ──────────────────────────────────────────────────
  useEffect(() => {
    if (!isConnected) return;
    const socket = (window as any).__parwa_socket;
    if (!socket) return;
    const handler = () => loadUndoable();
    socket.on('shadow:new', handler);
    return () => { socket.off('shadow:new', handler); };
  }, [isConnected, loadUndoable]);

  // ── Handlers ───────────────────────────────────────────────────────────
  const handleConfirmUndo = async () => {
    if (!confirmUndoId || !undoReason.trim()) {
      toast.error('Please provide a reason for the undo');
      return;
    }
    setUndoingId(confirmUndoId);
    try {
      await shadowApi.undo(confirmUndoId, undoReason);
      toast.success('Action successfully undone');
      setConfirmUndoId(null);
      setUndoReason('');
      loadUndoable();
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setUndoingId(null);
    }
  };

  const handleCancelUndo = () => {
    setConfirmUndoId(null);
    setUndoReason('');
  };

  // ════════════════════════════════════════════════════════════════════════
  // Render
  // ════════════════════════════════════════════════════════════════════════

  return (
    <div className="space-y-4">
      {/* ── Header ────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-[#FF7F11]">
            <ArrowUturnLeftIcon className="h-5 w-5" />
          </span>
          <h3 className="text-base font-semibold text-white">Undo Interface</h3>
          {undoableActions.length > 0 && (
            <span className="min-w-[18px] h-[18px] flex items-center justify-center text-[10px] font-bold bg-red-500/20 text-red-400 rounded-full px-1">
              {undoableActions.length}
            </span>
          )}
        </div>
        <button
          onClick={() => setShowHistory(!showHistory)}
          className={cn(
            'inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-colors',
            showHistory
              ? 'bg-[#FF7F11]/10 text-[#FF7F11]'
              : 'bg-white/[0.04] text-zinc-500 hover:text-zinc-300',
          )}
        >
          <HistoryIcon className="h-3.5 w-3.5" />
          Past Undos
        </button>
      </div>

      {/* ── Loading ───────────────────────────────────────────────────── */}
      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map(i => <Skeleton key={i} className="h-16" />)}
        </div>
      ) : error ? (
        <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-4">
          <p className="text-sm text-zinc-500">Unable to load undoable actions</p>
          <button onClick={loadUndoable} className="mt-2 text-xs text-[#FF7F11] hover:underline">Try again</button>
        </div>
      ) : undoableActions.length === 0 ? (
        /* ── Empty State ─────────────────────────────────────────────── */
        !showHistory ? (
          <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-8 text-center">
            <ArrowUturnLeftIcon className="h-10 w-10 text-zinc-700 mx-auto mb-3" />
            <h4 className="text-sm font-semibold text-zinc-400 mb-1">No Undoable Actions</h4>
            <p className="text-xs text-zinc-600 max-w-sm mx-auto">
              Auto-approved actions within the undo window will appear here. Actions are undoable for 30 minutes after execution.
            </p>
          </div>
        ) : null
      ) : (
        /* ── Undoable List ────────────────────────────────────────────── */
        <div className="space-y-2">
          {undoableActions.map(entry => {
            const isConfirming = confirmUndoId === entry.id;
            const isUndoing = undoingId === entry.id;
            const expiresAt = new Date(new Date(entry.created_at).getTime() + UNDO_WINDOW_MS).toISOString();

            return (
              <div
                key={entry.id}
                className={cn(
                  'rounded-xl border bg-[#1A1A1A] p-4 transition-all',
                  isConfirming ? 'border-red-500/30 bg-red-500/5' : 'border-white/[0.06]',
                )}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs font-medium text-zinc-300">
                        {actionDescription(entry)}
                      </span>
                      <CountdownTimer expiresAt={expiresAt} />
                    </div>
                    <div className="flex items-center gap-3 text-[11px] text-zinc-500">
                      <span>{formatDateTime(entry.created_at)}</span>
                      <span>{formatRelativeTime(entry.created_at)}</span>
                    </div>
                  </div>

                  {!isConfirming ? (
                    <button
                      onClick={() => setConfirmUndoId(entry.id)}
                      disabled={isUndoing}
                      className="shrink-0 inline-flex items-center gap-1.5 rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-1.5 text-xs font-medium text-red-400 hover:bg-red-500/20 disabled:opacity-50 transition-colors"
                    >
                      {isUndoing ? <SpinnerIcon className="w-3 h-3 animate-spin" /> : <ArrowUturnLeftIcon className="w-3.5 h-3.5" />}
                      Undo
                    </button>
                  ) : null}
                </div>

                {/* ── Confirm Dialog ──────────────────────────────────── */}
                {isConfirming && (
                  <div className="mt-3 pt-3 border-t border-white/[0.06] space-y-3">
                    <div className="flex items-start gap-2">
                      <ExclamationCircleIcon className="h-4 w-4 text-red-400 mt-0.5 shrink-0" />
                      <p className="text-xs text-zinc-400">
                        This will reverse the auto-approved action. The original action will be marked as undone in the audit trail.
                      </p>
                    </div>
                    <div>
                      <label className="block text-[10px] font-medium text-zinc-500 uppercase tracking-wider mb-1">
                        Reason for Undo
                      </label>
                      <textarea
                        value={undoReason}
                        onChange={e => setUndoReason(e.target.value)}
                        placeholder="Describe why this action needs to be undone..."
                        className="w-full rounded-lg border border-white/[0.08] bg-[#141414] px-3 py-2 text-xs text-white placeholder-zinc-600 focus:border-[#FF7F11]/50 focus:outline-none focus:ring-1 focus:ring-[#FF7F11]/30 resize-none transition-colors"
                        rows={2}
                      />
                    </div>
                    <div className="flex items-center gap-2 justify-end">
                      <button
                        onClick={handleCancelUndo}
                        disabled={isUndoing}
                        className="inline-flex items-center gap-1 rounded-lg border border-white/[0.08] bg-white/[0.04] px-3 py-1.5 text-xs font-medium text-zinc-400 hover:bg-white/[0.08] disabled:opacity-50 transition-colors"
                      >
                        <XMarkIcon className="w-3 h-3" />
                        Cancel
                      </button>
                      <button
                        onClick={handleConfirmUndo}
                        disabled={isUndoing || !undoReason.trim()}
                        className="inline-flex items-center gap-1 rounded-lg bg-red-500 px-3 py-1.5 text-xs font-medium text-white hover:bg-red-600 disabled:opacity-50 transition-colors"
                      >
                        {isUndoing ? <SpinnerIcon className="w-3 h-3 animate-spin" /> : <ArrowUturnLeftIcon className="w-3 h-3" />}
                        Confirm Undo
                      </button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* ── Past Undos (placeholder) ───────────────────────────────────── */}
      {showHistory && (
        <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-8 text-center mt-4">
          <HistoryIcon className="h-10 w-10 text-zinc-700 mx-auto mb-3" />
          <h4 className="text-sm font-semibold text-zinc-400 mb-1">No Past Undos</h4>
          <p className="text-xs text-zinc-600">
            Completed undo operations will be recorded here with their reasons.
          </p>
        </div>
      )}
    </div>
  );
}
