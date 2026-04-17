'use client';

import React, { useState, useEffect, useCallback } from 'react';
import toast from 'react-hot-toast';
import { getErrorMessage } from '@/lib/api';
import { cn } from '@/lib/utils';
import {
  shadowApi,
  type ShadowLogEntry,
  type SystemMode,
} from '@/lib/shadow-api';
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

function CheckCircleIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
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

// ── Types ──────────────────────────────────────────────────────────────────

interface UndoableAction extends ShadowLogEntry {
  /** Time remaining in seconds until undo window expires */
  undo_remaining_seconds?: number;
  /** When the action was executed */
  executed_at?: string;
}

interface UndoQueueProps {
  /** Optional max height for scrollable container */
  maxHeight?: string;
  /** Show compact version for sidebar/embed */
  compact?: boolean;
  /** Called when an action is undone */
  onUndo?: (action: UndoableAction) => void;
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

const DEFAULT_UNDO_WINDOW_MINUTES = 30;

// ── Helper Functions ───────────────────────────────────────────────────────

function formatTimeRemaining(seconds: number): string {
  if (seconds <= 0) return 'Expired';
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  if (mins > 0) {
    return `${mins}m ${secs}s left`;
  }
  return `${secs}s left`;
}

function getRiskColor(score: number): { bg: string; text: string; bar: string } {
  if (score >= 0.7) return { bg: 'bg-red-500/15', text: 'text-red-400', bar: 'bg-red-500' };
  if (score >= 0.4) return { bg: 'bg-yellow-500/15', text: 'text-yellow-400', bar: 'bg-yellow-500' };
  return { bg: 'bg-emerald-500/15', text: 'text-emerald-400', bar: 'bg-emerald-500' };
}

// ════════════════════════════════════════════════════════════════════════════
// UndoQueue Component
// ════════════════════════════════════════════════════════════════════════════

export default function UndoQueue({
  maxHeight,
  compact = false,
  onUndo,
  className,
}: UndoQueueProps) {
  const { isConnected } = useSocket();

  // ── State ───────────────────────────────────────────────────────────────
  const [actions, setActions] = useState<UndoableAction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [undoingId, setUndoingId] = useState<string | null>(null);
  const [undoModalOpen, setUndoModalOpen] = useState(false);
  const [selectedAction, setSelectedAction] = useState<UndoableAction | null>(null);
  const [undoReason, setUndoReason] = useState('');
  const [timers, setTimers] = useState<Record<string, number>>({});

  // ── Load Auto-Approved Actions ──────────────────────────────────────────
  const loadActions = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      // Get actions that are auto-approved (manager_decision is null and mode is graduated/supervised)
      // These are candidates for undo
      const data = await shadowApi.getLog({
        page: 1,
        page_size: 50,
        decision: '',  // Pending/Auto-approved
        // In a real implementation, we'd filter by auto_execute or similar
      });

      // Filter for actions that could be undone (approved or auto-approved within window)
      const undoable = data.items.filter((item) => {
        // Check if within undo window (30 min default)
        const createdAt = new Date(item.created_at);
        const now = new Date();
        const diffMs = now.getTime() - createdAt.getTime();
        const diffMins = diffMs / 60000;
        return diffMins <= DEFAULT_UNDO_WINDOW_MINUTES && item.manager_decision !== 'rejected';
      });

      setActions(undoable);

      // Initialize timers
      const newTimers: Record<string, number> = {};
      undoable.forEach((action) => {
        const createdAt = new Date(action.created_at);
        const expiresAt = new Date(createdAt.getTime() + DEFAULT_UNDO_WINDOW_MINUTES * 60000);
        const remaining = Math.max(0, Math.floor((expiresAt.getTime() - Date.now()) / 1000));
        newTimers[action.id] = remaining;
      });
      setTimers(newTimers);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadActions();
  }, [loadActions]);

  // ── Countdown Timer ─────────────────────────────────────────────────────
  useEffect(() => {
    const interval = setInterval(() => {
      setTimers((prev) => {
        const updated: Record<string, number> = {};
        let hasChanges = false;
        Object.entries(prev).forEach(([id, seconds]) => {
          if (seconds > 0) {
            updated[id] = seconds - 1;
            hasChanges = true;
          } else {
            updated[id] = 0;
          }
        });
        return hasChanges ? updated : prev;
      });
    }, 1000);

    return () => clearInterval(interval);
  }, []);

  // ── Remove Expired Actions ───────────────────────────────────────────────
  useEffect(() => {
    const expiredIds = Object.entries(timers)
      .filter(([, seconds]) => seconds <= 0)
      .map(([id]) => id);

    if (expiredIds.length > 0) {
      setActions((prev) => prev.filter((a) => !expiredIds.includes(a.id)));
    }
  }, [timers]);

  // ── Real-time via Socket.io ─────────────────────────────────────────────
  useEffect(() => {
    if (!isConnected) return;
    const socket = (window as any).__parwa_socket;
    if (!socket) return;

    const handler = () => {
      loadActions();
    };

    socket.on('shadow:new', handler);
    socket.on('shadow:action_undone', handler);
    return () => {
      socket.off('shadow:new', handler);
      socket.off('shadow:action_undone', handler);
    };
  }, [isConnected, loadActions]);

  // ── Handlers ────────────────────────────────────────────────────────────
  const handleUndoClick = (action: UndoableAction) => {
    setSelectedAction(action);
    setUndoReason('');
    setUndoModalOpen(true);
  };

  const handleUndoConfirm = async () => {
    if (!selectedAction) return;
    if (!undoReason.trim()) {
      toast.error('Please provide a reason for undoing this action');
      return;
    }

    setUndoingId(selectedAction.id);
    try {
      await shadowApi.undo(selectedAction.id, undoReason);
      toast.success('Action undone successfully');
      setActions((prev) => prev.filter((a) => a.id !== selectedAction.id));
      setUndoModalOpen(false);
      setSelectedAction(null);
      onUndo?.(selectedAction);
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setUndoingId(null);
    }
  };

  // ════════════════════════════════════════════════════════════════════════
  // Render
  // ════════════════════════════════════════════════════════════════════════

  return (
    <div className={cn('relative', className)}>
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <ArrowUturnLeftIcon className="h-5 w-5 text-[#FF7F11]" />
          <h3 className="text-base font-semibold text-white">
            {compact ? 'Undo' : 'Undo Queue'}
          </h3>
          {!loading && actions.length > 0 && (
            <span className="ml-1 text-xs text-zinc-500 bg-white/[0.04] px-2 py-0.5 rounded-md">
              {actions.length}
            </span>
          )}
        </div>
        {!loading && actions.length > 0 && (
          <button
            onClick={loadActions}
            className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
          >
            Refresh
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
            <p className="text-sm">Unable to load undo queue</p>
          </div>
          <button
            onClick={loadActions}
            className="mt-2 text-xs text-[#FF7F11] hover:underline"
          >
            Try again
          </button>
        </div>
      ) : actions.length === 0 ? (
        <div className="rounded-lg border border-white/[0.06] bg-[#1A1A1A] p-6 text-center">
          <CheckCircleIcon className="h-10 w-10 text-zinc-700 mx-auto mb-3" />
          <p className="text-sm text-zinc-500">
            {compact ? 'No actions to undo' : 'No actions available for undo'}
          </p>
          {!compact && (
            <p className="text-xs text-zinc-600 mt-1">
              Auto-approved actions will appear here for {DEFAULT_UNDO_WINDOW_MINUTES} minutes
            </p>
          )}
        </div>
      ) : (
        <div
          className={cn('space-y-2', maxHeight && 'overflow-y-auto')}
          style={maxHeight ? { maxHeight } : undefined}
        >
          {actions.map((action) => {
            const remaining = timers[action.id] ?? 0;
            const isExpiring = remaining < 300; // Less than 5 min
            const riskScore = action.jarvis_risk_score ?? 0;
            const riskColors = getRiskColor(riskScore);

            return (
              <div
                key={action.id}
                className={cn(
                  'rounded-lg border bg-[#1A1A1A] p-3 transition-all',
                  isExpiring ? 'border-yellow-500/30' : 'border-white/[0.06]',
                  remaining <= 0 && 'opacity-50'
                )}
              >
                <div className="flex items-start justify-between gap-3">
                  {/* Left: Action Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-sm font-medium text-white truncate">
                        {ACTION_LABELS[action.action_type] || action.action_type}
                      </span>
                      {riskScore > 0 && (
                        <span className={cn('text-[10px] font-mono px-1.5 py-0.5 rounded', riskColors.bg, riskColors.text)}>
                          {(riskScore * 100).toFixed(0)}%
                        </span>
                      )}
                    </div>
                    {/* Countdown Timer */}
                    <div className={cn('flex items-center gap-1.5 text-xs', isExpiring ? 'text-yellow-400' : 'text-zinc-500')}>
                      <ClockIcon className="h-3.5 w-3.5" />
                      <span className="font-mono">{formatTimeRemaining(remaining)}</span>
                    </div>
                  </div>

                  {/* Right: Undo Button */}
                  <button
                    onClick={() => handleUndoClick(action)}
                    disabled={remaining <= 0}
                    className={cn(
                      'inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors',
                      remaining > 0
                        ? 'border-orange-500/30 bg-orange-500/10 text-orange-400 hover:bg-orange-500/20'
                        : 'border-zinc-700 bg-zinc-800 text-zinc-500 cursor-not-allowed'
                    )}
                  >
                    <ArrowUturnLeftIcon className="h-3.5 w-3.5" />
                    Undo
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ── Undo Confirmation Modal ─────────────────────────────────────── */}
      {undoModalOpen && selectedAction && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="w-full max-w-md mx-4 rounded-xl border border-white/[0.08] bg-[#1A1A1A] p-6 shadow-2xl">
            <div className="flex items-center gap-3 mb-4">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-orange-500/10">
                <ArrowUturnLeftIcon className="h-5 w-5 text-orange-400" />
              </div>
              <div>
                <h4 className="text-base font-semibold text-white">Undo Action</h4>
                <p className="text-xs text-zinc-500">
                  {ACTION_LABELS[selectedAction.action_type] || selectedAction.action_type}
                </p>
              </div>
            </div>

            <p className="text-sm text-zinc-400 mb-4">
              This will reverse the action that was auto-approved. Please provide a reason for the undo.
            </p>

            <div className="mb-4">
              <label className="block text-xs font-medium text-zinc-400 mb-1.5">
                Reason for Undo <span className="text-red-400">*</span>
              </label>
              <textarea
                value={undoReason}
                onChange={(e) => setUndoReason(e.target.value)}
                placeholder="Why are you undoing this action?"
                className="w-full rounded-lg border border-white/[0.08] bg-[#141414] px-3 py-2.5 text-sm text-white placeholder-zinc-600 focus:border-[#FF7F11]/50 focus:outline-none focus:ring-1 focus:ring-[#FF7F11]/30 resize-none"
                rows={3}
                autoFocus
              />
            </div>

            <div className="flex items-center justify-end gap-3">
              <button
                onClick={() => setUndoModalOpen(false)}
                disabled={undoingId !== null}
                className="rounded-lg border border-white/[0.08] bg-white/[0.04] px-4 py-2 text-sm font-medium text-zinc-400 hover:text-zinc-300 transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={handleUndoConfirm}
                disabled={undoingId !== null || !undoReason.trim()}
                className="inline-flex items-center gap-2 rounded-lg bg-orange-500 px-4 py-2 text-sm font-semibold text-white hover:bg-orange-500/90 disabled:opacity-50 transition-colors"
              >
                {undoingId !== null && <SpinnerIcon className="h-4 w-4 animate-spin" />}
                {undoingId !== null ? 'Undoing...' : 'Confirm Undo'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
