/**
 * PARWA RecentApprovals — Day 2 (O1.8)
 *
 * Shows last 3 pending/approved approval items.
 * Inline Approve/Reject buttons.
 * Link to full approvals page.
 */

'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { cn } from '@/lib/utils';
import { get, post } from '@/lib/api';
import toast from 'react-hot-toast';

// ── Types ──────────────────────────────────────────────────────────────

interface ApprovalItem {
  id: string;
  type: string;
  title: string;
  description?: string;
  status: 'pending' | 'approved' | 'rejected';
  requested_at: string;
  requested_by?: string;
  ticket_id?: string;
  agent_name?: string;
}

// ── Component ──────────────────────────────────────────────────────────

export default function RecentApprovals() {
  const [approvals, setApprovals] = useState<ApprovalItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const fetchApprovals = useCallback(async () => {
    try {
      setIsLoading(true);
      const data = await get<{ items: ApprovalItem[] } | ApprovalItem[]>('/api/approvals?page=1&page_size=3&status=pending');

      // Handle both array and object response shapes
      if (Array.isArray(data)) {
        setApprovals(data);
      } else if (data && 'items' in data) {
        setApprovals(data.items);
      }
    } catch {
      // Approvals endpoint not available yet
      setApprovals([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchApprovals();
  }, [fetchApprovals]);

  const handleAction = useCallback(async (id: string, action: 'approved' | 'rejected') => {
    try {
      setActionLoading(id);
      await post(`/api/approvals/${id}/${action}`);
      setApprovals(prev => prev.filter(a => a.id !== id));
      toast.success(`Approval ${action}`);
    } catch {
      toast.error(`Failed to ${action} approval`);
    } finally {
      setActionLoading(null);
    }
  }, []);

  function formatTime(isoString: string): string {
    if (!isoString) return '';
    const diff = Date.now() - new Date(isoString).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    return `${Math.floor(hours / 24)}d ago`;
  }

  if (isLoading) {
    return (
      <div className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-5">
        <div className="flex items-center gap-2 mb-4">
          <div className="w-6 h-6 rounded-md bg-white/[0.06] animate-pulse" />
          <div className="h-4 w-36 bg-white/[0.06] rounded animate-pulse" />
        </div>
        <div className="space-y-2">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-14 bg-white/[0.04] rounded-lg animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.06]">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-md bg-purple-500/10 flex items-center justify-center">
            <svg className="w-3.5 h-3.5 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12c0 1.268-.63 2.39-1.593 3.068a3.745 3.745 0 0 1-1.043 3.296 3.745 3.745 0 0 1-3.296 1.043A3.745 3.745 0 0 1 12 21c-1.268 0-2.39-.63-3.068-1.593a3.746 3.746 0 0 1-3.296-1.043 3.745 3.745 0 0 1-1.043-3.296A3.745 3.745 0 0 1 3 12c0-1.268.63-2.39 1.593-3.068a3.745 3.745 0 0 1 1.043-3.296 3.746 3.746 0 0 1 3.296-1.043A3.746 3.746 0 0 1 12 3c1.268 0 2.39.63 3.068 1.593a3.746 3.746 0 0 1 3.296 1.043 3.746 3.746 0 0 1 1.043 3.296A3.745 3.745 0 0 1 21 12Z" />
            </svg>
          </div>
          <h3 className="text-sm font-semibold text-zinc-300">Recent Approvals</h3>
          {approvals.length > 0 && (
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-purple-500/10 text-purple-400 font-medium">
              {approvals.length} pending
            </span>
          )}
        </div>
        <a
          href="/dashboard/approvals"
          className="text-[11px] text-purple-400 hover:text-purple-300 transition-colors"
        >
          View all
        </a>
      </div>

      {/* Approval list */}
      <div className="divide-y divide-white/[0.03]">
        {approvals.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <p className="text-sm text-zinc-600">No pending approvals</p>
            <p className="text-xs text-zinc-700 mt-0.5">Items will appear when AI needs human review</p>
          </div>
        ) : (
          approvals.map(item => (
            <div key={item.id} className="flex items-center gap-3 px-4 py-3 hover:bg-white/[0.02] transition-colors">
              {/* Icon */}
              <div className="w-8 h-8 rounded-lg bg-amber-500/10 flex items-center justify-center shrink-0">
                <svg className="w-4 h-4 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 3.75h.008v.008H12v-.008Z" />
                </svg>
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0">
                <p className="text-sm text-zinc-300 truncate">{item.title}</p>
                <p className="text-[10px] text-zinc-600">
                  {item.agent_name && <span className="text-zinc-500">{item.agent_name}</span>}
                  {item.requested_at && <span> · {formatTime(item.requested_at)}</span>}
                </p>
              </div>

              {/* Actions */}
              <div className="flex items-center gap-1.5 shrink-0">
                <button
                  onClick={() => handleAction(item.id, 'approved')}
                  disabled={actionLoading === item.id}
                  className="px-2.5 py-1 rounded-md text-[10px] font-medium bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 transition-colors disabled:opacity-50"
                >
                  Approve
                </button>
                <button
                  onClick={() => handleAction(item.id, 'rejected')}
                  disabled={actionLoading === item.id}
                  className="px-2.5 py-1 rounded-md text-[10px] font-medium bg-red-500/10 text-red-400 hover:bg-red-500/20 transition-colors disabled:opacity-50"
                >
                  Reject
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
