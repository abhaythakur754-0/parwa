/**
 * PARWA RecentApprovals — Day 2 (O1.8)
 *
 * Last 3 pending/approved items with quick action buttons.
 * Shows ticket ID, AI recommendation, action, and financial impact.
 * Inline Approve/Reject buttons. Click navigates to full approvals page.
 */

'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { get, post } from '@/lib/api';
import toast from 'react-hot-toast';

// ── Types ──────────────────────────────────────────────────────────────

interface ApprovalItem {
  approval_id: string;
  ticket_id: string;
  ticket_subject?: string;
  action_type: string;
  action_description: string;
  confidence: number;
  financial_impact?: number;
  status: 'pending' | 'approved' | 'rejected' | 'timed_out';
  reason?: string;
  created_at: string;
}

interface ApprovalsResponse {
  items: ApprovalItem[];
  total: number;
  pending_count: number;
}

// ── Component ──────────────────────────────────────────────────────────

export default function RecentApprovals() {
  const [data, setData] = useState<ApprovalsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const fetchApprovals = useCallback(() => {
    get<ApprovalsResponse>('/api/approvals?limit=3')
      .then(setData)
      .catch(() => {
        setData({ items: [], total: 0, pending_count: 0 });
      })
      .finally(() => setIsLoading(false));
  }, []);

  useEffect(() => {
    fetchApprovals();
  }, [fetchApprovals]);

  const handleAction = async (approvalId: string, action: 'approved' | 'rejected') => {
    setActionLoading(approvalId);
    try {
      await post(`/api/approvals/${approvalId}/${action}`, {});
      toast.success(`Approval ${action}`);
      fetchApprovals();
    } catch {
      toast.error(`Failed to ${action}`);
    } finally {
      setActionLoading(null);
    }
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount);
  };

  const timeAgo = (dateStr: string) => {
    const diff = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    return `${Math.floor(hours / 24)}d ago`;
  };

  const statusBadge = (status: string) => {
    const config = {
      pending: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
      approved: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
      rejected: 'bg-red-500/10 text-red-400 border-red-500/20',
      timed_out: 'bg-zinc-500/10 text-zinc-400 border-zinc-500/20',
    };
    return (
      <span className={`inline-block px-2 py-0.5 rounded-full text-[11px] font-medium border ${
        config[status as keyof typeof config] || config.pending
      }`}>
        {status.charAt(0).toUpperCase() + status.slice(1).replace('_', ' ')}
      </span>
    );
  };

  if (isLoading) {
    return (
      <div className="rounded-xl bg-[#141414] border border-white/[0.06] p-4">
        <div className="h-4 w-36 rounded bg-white/[0.04] animate-pulse mb-4" />
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-16 rounded-lg bg-white/[0.03] animate-pulse mb-2" />
        ))}
      </div>
    );
  }

  return (
    <div className="rounded-xl bg-[#141414] border border-white/[0.06] p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-zinc-300">Recent Approvals</h3>
        <div className="flex items-center gap-2">
          {data && data.pending_count > 0 && (
            <span className="px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 text-[11px] font-medium">
              {data.pending_count} pending
            </span>
          )}
          <Link
            href="/dashboard/approvals"
            className="text-[11px] text-zinc-500 hover:text-zinc-300 transition-colors"
          >
            View All →
          </Link>
        </div>
      </div>

      {/* Approval Items */}
      <div className="space-y-2">
        {!data || data.items.length === 0 ? (
          <div className="text-center py-6 text-sm text-zinc-500">
            No recent approvals
          </div>
        ) : (
          data.items.map((item) => (
            <div
              key={item.approval_id}
              className="px-3 py-2.5 rounded-lg bg-white/[0.03] border border-white/[0.04] hover:bg-white/[0.05] transition-colors"
            >
              <div className="flex items-start justify-between gap-2 mb-1.5">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-zinc-500 font-mono">#{item.ticket_id}</span>
                    {statusBadge(item.status)}
                  </div>
                  <p className="text-sm text-zinc-300 truncate mt-0.5">
                    {item.action_description}
                  </p>
                </div>
                <span className="text-[11px] text-zinc-600 shrink-0">
                  {timeAgo(item.created_at)}
                </span>
              </div>

              {/* Meta row */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  {/* Confidence */}
                  <div className="flex items-center gap-1">
                    <span className="text-[11px] text-zinc-500">Conf:</span>
                    <span className={`text-[11px] font-medium ${
                      item.confidence >= 75 ? 'text-emerald-400' :
                      item.confidence >= 50 ? 'text-amber-400' : 'text-red-400'
                    }`}>
                      {item.confidence}%
                    </span>
                  </div>

                  {/* Financial impact */}
                  {item.financial_impact !== undefined && (
                    <span className="text-[11px] text-zinc-500">
                      {formatCurrency(item.financial_impact)}
                    </span>
                  )}
                </div>

                {/* Action buttons (only for pending) */}
                {item.status === 'pending' && (
                  <div className="flex items-center gap-1.5">
                    <button
                      onClick={() => handleAction(item.approval_id, 'approved')}
                      disabled={actionLoading === item.approval_id}
                      className="px-2.5 py-1 rounded-md text-[11px] font-medium bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 transition-colors disabled:opacity-50"
                    >
                      Approve
                    </button>
                    <button
                      onClick={() => handleAction(item.approval_id, 'rejected')}
                      disabled={actionLoading === item.approval_id}
                      className="px-2.5 py-1 rounded-md text-[11px] font-medium bg-red-500/10 text-red-400 hover:bg-red-500/20 transition-colors disabled:opacity-50"
                    >
                      Reject
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
