/**
 * PARWA ApprovalWatcher
 *
 * Displays pending AI agent approval requests that require human action.
 * Real-time — new approvals arrive via Socket.io instantly.
 * Shows approve/reject buttons with optimistic updates.
 */

'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useApprovalStore, Approval, ApprovalType, ApprovalStatus } from '@/lib/approval-store';
import {
  APPROVAL_TYPE_LABELS,
  APPROVAL_STATUS_LABELS,
  APPROVAL_STATUS_COLORS,
  RISK_LEVEL_COLORS,
} from '@/lib/approval-store';
import { LockedFeature } from '@/components/LockedFeature';

// ── Approval Type Icons ───────────────────────────────────────────────

function ApprovalTypeIcon({ type }: { type: ApprovalType }) {
  const icons: Record<ApprovalType, React.ReactNode> = {
    refund: (
      <svg className="w-4 h-4 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 15 3 9m0 0 6-6M3 9h12a6 6 0 0 1 0 12h-3" />
      </svg>
    ),
    cancellation: (
      <svg className="w-4 h-4 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
      </svg>
    ),
    escalation: (
      <svg className="w-4 h-4 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5m-13.5-9L12 3m0 0 4.5 4.5M12 3v13.5" />
      </svg>
    ),
    discount: (
      <svg className="w-4 h-4 text-sky-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9.568 3H5.25A2.25 2.25 0 0 0 3 5.25v4.318c0 .597.237 1.17.659 1.591l9.581 9.581c.699.699 1.78.872 2.607.33a18.095 18.095 0 0 0 5.223-5.223c.542-.827.369-1.908-.33-2.607L11.16 3.66A2.25 2.25 0 0 0 9.568 3Z" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M6 6h.008v.008H6V6Z" />
      </svg>
    ),
    account_change: (
      <svg className="w-4 h-4 text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.501 20.118a7.5 7.5 0 0 1 14.998 0A17.933 17.933 0 0 1 12 21.75c-2.676 0-5.216-.584-7.499-1.632Z" />
      </svg>
    ),
    data_deletion: (
      <svg className="w-4 h-4 text-rose-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0" />
      </svg>
    ),
  };

  return <>{icons[type] || icons.refund}</>;
}

// ── Time Until Expiry ─────────────────────────────────────────────────

function timeUntilExpiry(expiresAt: string): string {
  const now = Date.now();
  const expiry = new Date(expiresAt).getTime();
  const diffMs = expiry - now;

  if (diffMs <= 0) return 'Expired';

  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 60) return `${minutes}m left`;

  const hours = Math.floor(minutes / 60);
  return `${hours}h ${minutes % 60}m left`;
}

// ── ApprovalWatcher Component ─────────────────────────────────────────

export function ApprovalWatcher() {
  const pendingApprovals = useApprovalStore((s) => s.getPendingApprovals());
  const pendingCount = useApprovalStore((s) => s.pendingCount);
  const approve = useApprovalStore((s) => s.approve);
  const reject = useApprovalStore((s) => s.reject);
  const fetchApprovals = useApprovalStore((s) => s.fetchApprovals);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState<string | null>(null);

  // Fetch approvals on mount
  useEffect(() => {
    fetchApprovals();
  }, [fetchApprovals]);

  // Don't render if no pending approvals
  if (pendingCount === 0) return null;

  const handleApprove = async (id: string) => {
    setIsProcessing(id);
    try {
      await approve(id);
    } catch {
      // Error handled by store (optimistic revert)
    }
    setIsProcessing(null);
    setExpandedId(null);
  };

  const handleReject = async (id: string) => {
    setIsProcessing(id);
    try {
      await reject(id, 'Rejected by human agent');
    } catch {
      // Error handled by store (optimistic revert)
    }
    setIsProcessing(null);
    setExpandedId(null);
  };

  return (
    <div className="space-y-2">
      {/* Header */}
      <div className="flex items-center gap-2 px-1">
        <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
        <h3 className="text-sm font-medium text-white">Pending Approvals</h3>
        <span className="ml-auto text-[10px] font-semibold uppercase tracking-wider text-amber-400 bg-amber-400/10 px-2 py-0.5 rounded-md">
          {pendingCount} pending
        </span>
      </div>

      {/* Approval Cards */}
      {pendingApprovals.slice(0, 5).map((approval) => (
        <div
          key={approval.id}
          className="rounded-lg border border-white/[0.06] bg-[#1A1A1A] overflow-hidden"
        >
          {/* Summary Row */}
          <button
            onClick={() => setExpandedId(expandedId === approval.id ? null : approval.id)}
            className="w-full flex items-center gap-3 p-3 text-left hover:bg-white/[0.02] transition-colors"
          >
            <ApprovalTypeIcon type={approval.type} />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-white truncate">{approval.title}</p>
              <div className="flex items-center gap-2 mt-0.5">
                <span className="text-[10px] text-zinc-500">
                  by {approval.requestedBy}
                </span>
                <span className={`w-1.5 h-1.5 rounded-full ${RISK_LEVEL_COLORS[approval.riskLevel]}`} title={`${approval.riskLevel} risk`} />
                <span className="text-[10px] text-zinc-600">
                  {timeUntilExpiry(approval.expiresAt)}
                </span>
              </div>
            </div>

            {/* Amount (if refund/discount) */}
            {approval.amount != null && (
              <span className="text-sm font-semibold text-white">
                ${approval.amount.toLocaleString()}
                {approval.currency && <span className="text-xs text-zinc-500 ml-0.5">{approval.currency}</span>}
              </span>
            )}

            {/* Expand/Collapse chevron */}
            <svg
              className={`w-4 h-4 text-zinc-500 transition-transform duration-200 ${expandedId === approval.id ? 'rotate-180' : ''}`}
              fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
            </svg>
          </button>

          {/* Expanded Detail */}
          {expandedId === approval.id && (
            <div className="px-3 pb-3 border-t border-white/[0.04] pt-3 space-y-3">
              {/* Description */}
              <p className="text-xs text-zinc-400">{approval.description || approval.reason}</p>

              {/* Meta Info */}
              <div className="grid grid-cols-2 gap-2 text-xs">
                {approval.customerName && (
                  <div>
                    <span className="text-zinc-600">Customer</span>
                    <p className="text-zinc-300">{approval.customerName}</p>
                  </div>
                )}
                {approval.ticketNumber && (
                  <div>
                    <span className="text-zinc-600">Ticket</span>
                    <Link href={`/dashboard/tickets`} className="text-orange-400 hover:text-orange-300">
                      {approval.ticketNumber}
                    </Link>
                  </div>
                )}
                <div>
                  <span className="text-zinc-600">AI Confidence</span>
                  <p className={`${approval.aiConfidence < 70 ? 'text-amber-400' : 'text-zinc-300'}`}>
                    {approval.aiConfidence}%
                  </p>
                </div>
                <div>
                  <span className="text-zinc-600">Risk Level</span>
                  <p className="text-zinc-300 capitalize">{approval.riskLevel}</p>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center gap-2 pt-1">
                <button
                  onClick={() => handleApprove(approval.id)}
                  disabled={isProcessing === approval.id}
                  className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-xs font-semibold bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 transition-colors disabled:opacity-50"
                >
                  {isProcessing === approval.id ? (
                    <div className="w-3.5 h-3.5 border-2 border-emerald-400 border-t-transparent rounded-full animate-spin" />
                  ) : (
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
                    </svg>
                  )}
                  Approve
                </button>
                <button
                  onClick={() => handleReject(approval.id)}
                  disabled={isProcessing === approval.id}
                  className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-xs font-semibold bg-red-500/10 text-red-400 hover:bg-red-500/20 transition-colors disabled:opacity-50"
                >
                  {isProcessing === approval.id ? (
                    <div className="w-3.5 h-3.5 border-2 border-red-400 border-t-transparent rounded-full animate-spin" />
                  ) : (
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
                    </svg>
                  )}
                  Reject
                </button>
              </div>
            </div>
          )}
        </div>
      ))}

      {/* View All Link */}
      {pendingCount > 5 && (
        <Link
          href="/dashboard/monitoring"
          className="block text-center text-xs text-orange-400 hover:text-orange-300 py-2 transition-colors"
        >
          View all {pendingCount} pending approvals
        </Link>
      )}
    </div>
  );
}

export default ApprovalWatcher;
