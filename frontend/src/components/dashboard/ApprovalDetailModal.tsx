'use client';

import React, { useState, useEffect } from 'react';
import toast from 'react-hot-toast';
import { cn } from '@/lib/utils';
import { getErrorMessage } from '@/lib/api';
import { shadowApi, type ShadowLogEntry, type RiskEvaluation } from '@/lib/shadow-api';
import RiskScoreIndicator, { RiskGauge } from './RiskScoreIndicator';
import ModeBadge from './ModeBadge';

// ── Inline SVG Icons ────────────────────────────────────────────────────────

function XIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
    </svg>
  );
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
    </svg>
  );
}

function ArrowUpIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 19.5v-15m0 0-6.75 6.75M12 4.5l6.75 6.75" />
    </svg>
  );
}

function ExternalLinkIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 0 0 3 8.25v10.5A2.25 2.25 0 0 0 5.25 21h10.5A2.25 2.25 0 0 0 18 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
    </svg>
  );
}

function ShieldIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75m-3-7.036A11.959 11.959 0 0 1 3.598 6 11.99 11.99 0 0 0 3 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285Z" />
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

function SpinnerIcon({ className }: { className?: string }) {
  return (
    <svg className={cn('animate-spin', className)} fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  );
}

// ── Helper Functions ───────────────────────────────────────────────────────

function formatDateTime(dateStr: string | null | undefined): string {
  if (!dateStr) return 'N/A';
  try {
    return new Date(dateStr).toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
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

const ACTION_LABELS: Record<string, string> = {
  refund: 'Refund',
  sms_reply: 'SMS Reply',
  email_reply: 'Email Reply',
  ticket_close: 'Close Ticket',
  ticket_reply: 'Ticket Reply',
  account_update: 'Account Update',
  escalation: 'Escalation',
  knowledge_update: 'Knowledge Update',
  integration_action: 'Integration Action',
  customer_outreach: 'Customer Outreach',
  schedule_followup: 'Schedule Follow-up',
  tag_ticket: 'Tag Ticket',
  categorize_ticket: 'Categorize Ticket',
  priority_change: 'Priority Change',
};

function actionLabel(type: string): string {
  return ACTION_LABELS[type] || type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

// ── Action Type Icon ───────────────────────────────────────────────────────

function ActionTypeIcon({ type, className }: { type: string; className?: string }) {
  switch (type) {
    case 'refund':
      return (
        <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 8.25h19.5M2.25 9h19.5m-16.5 5.25h6m-6 2.25h3m-3.75 3h15a2.25 2.25 0 0 0 2.25-2.25V6.75A2.25 2.25 0 0 0 19.5 4.5h-15a2.25 2.25 0 0 0-2.25 2.25v10.5A2.25 2.25 0 0 0 4.5 19.5Z" />
        </svg>
      );
    case 'sms_reply':
      return (
        <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H8.25m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H12m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 0 1-2.555-.337A5.972 5.972 0 0 1 5.41 20.97a5.969 5.969 0 0 1-.474-.065 4.48 4.48 0 0 0 .978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25Z" />
        </svg>
      );
    case 'email_reply':
      return (
        <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 0 1-2.25 2.25h-15a2.25 2.25 0 0 1-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0 0 19.5 4.5h-15a2.25 2.25 0 0 0-2.25 2.25m19.5 0v.243a2.25 2.25 0 0 1-1.07 1.916l-7.5 4.615a2.25 2.25 0 0 1-2.36 0L3.32 8.91a2.25 2.25 0 0 1-1.07-1.916V6.75" />
        </svg>
      );
    case 'ticket_close':
    case 'ticket_reply':
      return (
        <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 6v.75m0 3v.75m0 3v.75m0 3V18m-9-5.25h5.25M7.5 15h3M3.375 5.25c-.621 0-1.125.504-1.125 1.125v3.026a2.999 2.999 0 0 1 0 5.198v3.026c0 .621.504 1.125 1.125 1.125h17.25c.621 0 1.125-.504 1.125-1.125v-3.026a2.999 2.999 0 0 1 0-5.198V6.375c0-.621-.504-1.125-1.125-1.125H3.375Z" />
        </svg>
      );
    default:
      return (
        <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 0 1 1.37.49l1.296 2.247a1.125 1.125 0 0 1-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 0 1 0 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 0 1-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 0 1-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.94-1.11.94h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 0 1-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 0 1-1.369-.49l-1.297-2.247a1.125 1.125 0 0 1 .26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 0 1 0-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 0 1-.26-1.43l1.297-2.247a1.125 1.125 0 0 1 1.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28Z" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
        </svg>
      );
  }
}

// ── Types ──────────────────────────────────────────────────────────────────

interface ApprovalDetailModalProps {
  /** The shadow log entry to display */
  item: ShadowLogEntry | null;
  /** Whether the modal is open */
  isOpen: boolean;
  /** Callback when modal is closed */
  onClose: () => void;
  /** Callback when action is approved */
  onApprove?: (id: string) => void;
  /** Callback when action is rejected */
  onReject?: (id: string) => void;
  /** Callback when action is escalated */
  onEscalate?: (id: string) => void;
}

// ── ApprovalDetailModal Component ──────────────────────────────────────────

export default function ApprovalDetailModal({
  item,
  isOpen,
  onClose,
  onApprove,
  onReject,
  onEscalate,
}: ApprovalDetailModalProps) {
  const [note, setNote] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [riskEvaluation, setRiskEvaluation] = useState<RiskEvaluation | null>(null);

  // Reset state when modal opens/closes
  useEffect(() => {
    if (isOpen) {
      setNote('');
      setError(null);
      setRiskEvaluation(null);
    }
  }, [isOpen]);

  // Fetch risk evaluation when item changes
  useEffect(() => {
    if (!item || !isOpen) return;

    const fetchRiskEvaluation = async () => {
      try {
        const evaluation = await shadowApi.evaluate(item.action_type, item.action_payload);
        setRiskEvaluation(evaluation);
      } catch (err) {
        console.warn('Failed to fetch risk evaluation:', err);
      }
    };

    fetchRiskEvaluation();
  }, [item, isOpen]);

  if (!isOpen || !item) return null;

  const isPending = !item.manager_decision;

  const handleApprove = async () => {
    setLoading(true);
    setError(null);
    try {
      await shadowApi.approve(item.id, note || undefined);
      toast.success('Action approved successfully');
      onApprove?.(item.id);
      onClose();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const handleReject = async () => {
    setLoading(true);
    setError(null);
    try {
      await shadowApi.reject(item.id, note || undefined);
      toast.success('Action rejected');
      onReject?.(item.id);
      onClose();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const handleEscalate = async () => {
    setLoading(true);
    setError(null);
    try {
      // Escalate by setting mode to shadow if needed
      await shadowApi.setMode('shadow', 'ui');
      toast.success('Escalated to Shadow Mode');
      onEscalate?.(item.id);
      onClose();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  // Generate smart summary from action_payload
  const generateSummary = (): string => {
    const payload = item.action_payload;
    if (!payload) return `Pending ${actionLabel(item.action_type)} action`;

    switch (item.action_type) {
      case 'refund':
        return `Process refund of ${payload.amount || 'amount'} for order ${payload.order_id || 'unknown'}`;
      case 'sms_reply':
      case 'email_reply':
        return `Send ${item.action_type === 'sms_reply' ? 'SMS' : 'email'} response to ${payload.recipient || 'customer'}`;
      case 'ticket_close':
        return `Close ticket ${payload.ticket_id || item.id.slice(0, 8)}`;
      case 'account_update':
        return `Update account ${payload.account_id || 'details'}: ${payload.update_type || 'changes'}`;
      default:
        return `${actionLabel(item.action_type)} action pending approval`;
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative w-full max-w-3xl max-h-[90vh] overflow-y-auto bg-[#111111] border border-white/[0.08] rounded-2xl shadow-2xl">
        {/* Header */}
        <div className="sticky top-0 z-10 bg-[#111111]/95 backdrop-blur-sm border-b border-white/[0.06] px-6 py-4">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-[#FF7F11]/10 flex items-center justify-center">
                <ActionTypeIcon type={item.action_type} className="w-5 h-5 text-[#FF7F11]" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-white">
                  {actionLabel(item.action_type)} Action
                </h2>
                <p className="text-sm text-zinc-500">
                  {formatRelativeTime(item.created_at)}
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-2 rounded-lg text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.05] transition-colors"
            >
              <XIcon className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Error Alert */}
          {error && (
            <div className="rounded-lg bg-red-500/10 border border-red-500/20 p-4">
              <p className="text-sm text-red-400">{error}</p>
            </div>
          )}

          {/* Summary Card */}
          <div className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-4">
            <h3 className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-2">
              Action Summary
            </h3>
            <p className="text-sm text-zinc-200">{generateSummary()}</p>
          </div>

          {/* Risk Score & Mode Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Risk Score */}
            <div className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-4">
              <div className="flex items-center gap-2 mb-4">
                <ShieldIcon className="w-4 h-4 text-zinc-500" />
                <h3 className="text-xs font-medium text-zinc-500 uppercase tracking-wider">
                  Risk Assessment
                </h3>
              </div>
              <div className="flex items-center justify-center py-2">
                <RiskGauge score={item.jarvis_risk_score} size={100} showLabel />
              </div>
              {riskEvaluation?.reason && (
                <p className="text-xs text-zinc-500 text-center mt-3">
                  {riskEvaluation.reason}
                </p>
              )}
            </div>

            {/* Mode */}
            <div className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-4">
              <div className="flex items-center gap-2 mb-4">
                <ClockIcon className="w-4 h-4 text-zinc-500" />
                <h3 className="text-xs font-medium text-zinc-500 uppercase tracking-wider">
                  Mode & Status
                </h3>
              </div>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-zinc-400">Mode</span>
                  <ModeBadge modeOverride={item.mode} compact={false} interactive={false} />
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-zinc-400">Decision</span>
                  {item.manager_decision ? (
                    <span className={cn(
                      'text-xs font-medium uppercase',
                      item.manager_decision === 'approved' && 'text-emerald-400',
                      item.manager_decision === 'rejected' && 'text-red-400',
                      item.manager_decision === 'modified' && 'text-yellow-400'
                    )}>
                      {item.manager_decision}
                    </span>
                  ) : (
                    <span className="text-xs text-orange-400 font-medium">Pending</span>
                  )}
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-zinc-400">Created</span>
                  <span className="text-xs text-zinc-300">{formatDateTime(item.created_at)}</span>
                </div>
                {item.resolved_at && (
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-zinc-400">Resolved</span>
                    <span className="text-xs text-zinc-300">{formatDateTime(item.resolved_at)}</span>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* 4-Layer Decision Breakdown */}
          {riskEvaluation?.layers && (
            <div className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-4">
              <h3 className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-4">
                4-Layer Decision Breakdown
              </h3>
              <div className="space-y-3">
                {/* Layer 1: Heuristic */}
                <div className="rounded-lg bg-[#0A0A0A] border border-white/[0.04] p-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-medium text-zinc-400">Layer 1: Heuristic Risk</span>
                    <RiskScoreIndicator score={riskEvaluation.layers.layer1_heuristic.score} size="sm" />
                  </div>
                  <p className="text-[11px] text-zinc-500">{riskEvaluation.layers.layer1_heuristic.reason}</p>
                </div>

                {/* Layer 2: Preference */}
                <div className="rounded-lg bg-[#0A0A0A] border border-white/[0.04] p-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-medium text-zinc-400">Layer 2: Company Preference</span>
                    <span className="text-xs text-zinc-300">
                      {riskEvaluation.layers.layer2_preference.mode || 'Default'}
                    </span>
                  </div>
                  <p className="text-[11px] text-zinc-500">{riskEvaluation.layers.layer2_preference.reason}</p>
                </div>

                {/* Layer 3: Historical */}
                <div className="rounded-lg bg-[#0A0A0A] border border-white/[0.04] p-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-medium text-zinc-400">Layer 3: Historical Patterns</span>
                    {riskEvaluation.layers.layer3_historical.avg_risk !== null ? (
                      <RiskScoreIndicator score={riskEvaluation.layers.layer3_historical.avg_risk} size="sm" />
                    ) : (
                      <span className="text-xs text-zinc-600">No data</span>
                    )}
                  </div>
                  <p className="text-[11px] text-zinc-500">{riskEvaluation.layers.layer3_historical.reason}</p>
                </div>

                {/* Layer 4: Safety Floor */}
                <div className="rounded-lg bg-[#0A0A0A] border border-white/[0.04] p-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-medium text-zinc-400">Layer 4: Safety Floor</span>
                    <span className={cn(
                      'text-xs font-medium',
                      riskEvaluation.layers.layer4_safety_floor.hard_safety ? 'text-red-400' : 'text-emerald-400'
                    )}>
                      {riskEvaluation.layers.layer4_safety_floor.hard_safety ? 'BLOCKED' : 'PASSED'}
                    </span>
                  </div>
                  <p className="text-[11px] text-zinc-500">{riskEvaluation.layers.layer4_safety_floor.reason}</p>
                </div>
              </div>
            </div>
          )}

          {/* Action Payload (JSON pretty-print) */}
          <div className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-4">
            <h3 className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-3">
              Action Payload
            </h3>
            <pre className="bg-[#0A0A0A] rounded-lg border border-white/[0.04] p-4 text-xs text-zinc-400 overflow-x-auto max-h-64 font-mono">
              {JSON.stringify(item.action_payload, null, 2)}
            </pre>
          </div>

          {/* Customer Context (if available) */}
          {item.action_payload?.ticket_id && (
            <div className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-4">
              <h3 className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-3">
                Related Ticket
              </h3>
              <a
                href={`/dashboard/tickets/${item.action_payload.ticket_id}`}
                className="inline-flex items-center gap-2 text-sm text-[#FF7F11] hover:text-orange-300 transition-colors"
              >
                <span>View Ticket #{item.action_payload.ticket_id.toString().slice(0, 8)}</span>
                <ExternalLinkIcon className="w-4 h-4" />
              </a>
            </div>
          )}

          {/* Manager Note (if resolved) */}
          {item.manager_note && (
            <div className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-4">
              <h3 className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-3">
                Manager Note
              </h3>
              <p className="text-sm text-zinc-300">{item.manager_note}</p>
            </div>
          )}

          {/* Note Input (for pending actions) */}
          {isPending && (
            <div className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-4">
              <h3 className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-3">
                Add Note (Optional)
              </h3>
              <textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="Add a note explaining your decision..."
                className="w-full h-24 bg-[#0A0A0A] border border-white/[0.06] rounded-lg px-4 py-3 text-sm text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-[#FF7F11]/50 resize-none"
              />
            </div>
          )}
        </div>

        {/* Footer Actions */}
        {isPending && (
          <div className="sticky bottom-0 bg-[#111111]/95 backdrop-blur-sm border-t border-white/[0.06] px-6 py-4">
            <div className="flex items-center justify-between gap-3">
              {/* Escalate Button */}
              <button
                onClick={handleEscalate}
                disabled={loading}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-white/[0.08] bg-white/[0.04] text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.08] disabled:opacity-50 transition-colors text-sm"
              >
                <ArrowUpIcon className="w-4 h-4" />
                Escalate to Shadow
              </button>

              {/* Approve/Reject Buttons */}
              <div className="flex items-center gap-3">
                <button
                  onClick={handleReject}
                  disabled={loading}
                  className="inline-flex items-center gap-2 px-5 py-2 rounded-lg bg-red-500/15 border border-red-500/25 text-red-400 hover:bg-red-500/25 disabled:opacity-50 transition-colors text-sm font-medium"
                >
                  {loading ? <SpinnerIcon className="w-4 h-4" /> : <XIcon className="w-4 h-4" />}
                  Reject
                </button>
                <button
                  onClick={handleApprove}
                  disabled={loading}
                  className="inline-flex items-center gap-2 px-5 py-2 rounded-lg bg-emerald-500/15 border border-emerald-500/25 text-emerald-400 hover:bg-emerald-500/25 disabled:opacity-50 transition-colors text-sm font-medium"
                >
                  {loading ? <SpinnerIcon className="w-4 h-4" /> : <CheckIcon className="w-4 h-4" />}
                  Approve
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
