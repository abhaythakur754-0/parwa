'use client';

import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { cn } from '@/lib/utils';
import { useSocket } from '@/lib/socket';
import { ticketsApi } from '@/lib/tickets-api';
import type { Ticket, TicketFilters, TicketSort, TicketSortField, BulkActionType } from '@/types/ticket';
import TicketSearch from './TicketSearch';
import TicketFiltersBar from './TicketFilters';
import TicketRow, { statusConfig, priorityConfig, channelIcons } from './TicketRow';
import TicketQuickView from './TicketQuickView';
import BulkActions from './BulkActions';
import ConfidenceBar from './ConfidenceBar';
import toast from 'react-hot-toast';

const PAGE_SIZE = 25;

const sortFields: { value: TicketSortField; label: string }[] = [
  { value: 'created_at', label: 'Created' },
  { value: 'ticket_number', label: 'ID' },
  { value: 'status', label: 'Status' },
  { value: 'priority', label: 'Priority' },
  { value: 'channel', label: 'Channel' },
  { value: 'assigned_agent', label: 'Agent' },
  { value: 'ai_confidence', label: 'Confidence' },
  { value: 'updated_at', label: 'Updated' },
];

// ── Sort Header Cell ────────────────────────────────────────────────────

function SortHeaderCell({
  label,
  field,
  currentSort,
  onSort,
  className,
  showMobile,
}: {
  label: string;
  field: TicketSortField;
  currentSort: TicketSort;
  onSort: (field: TicketSortField) => void;
  className?: string;
  showMobile?: boolean;
}) {
  const isActive = currentSort.field === field;

  return (
    <th
      className={cn(
        'px-3 py-2.5 text-left text-[10px] font-semibold text-zinc-600 uppercase tracking-wider cursor-pointer hover:text-zinc-400 transition-colors select-none',
        isActive && 'text-orange-400/80',
        showMobile === false && 'hidden xl:table-cell',
        className
      )}
      onClick={() => onSort(field)}
    >
      <div className="flex items-center gap-1">
        {label}
        {isActive && (
          <svg className={cn('w-3 h-3', currentSort.direction === 'desc' && 'rotate-180')} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 15.75 7.5-7.5 7.5 7.5" />
          </svg>
        )}
      </div>
    </th>
  );
}

// ── TicketList Component ────────────────────────────────────────────────

export default function TicketList({ className }: { className?: string }) {
  const { latestTicketEvent } = useSocket();

  // State
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [filters, setFilters] = useState<Partial<TicketFilters>>({});
  const [sort, setSort] = useState<TicketSort>({ field: 'created_at', direction: 'desc' });
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [hoveredTicket, setHoveredTicket] = useState<Ticket | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  const quickViewRef = useRef<HTMLDivElement>(null);

  // Fetch tickets
  const fetchTickets = useCallback(async () => {
    try {
      setIsLoading(true);
      const response = await ticketsApi.fetchTickets(page, PAGE_SIZE, filters, sort);
      setTickets(response.tickets);
      setTotal(response.pagination.total);
      setTotalPages(response.pagination.total_pages);
    } catch (err) {
      toast.error('Failed to load tickets');
    } finally {
      setIsLoading(false);
    }
  }, [page, filters, sort]);

  useEffect(() => {
    fetchTickets();
  }, [fetchTickets]);

  // Real-time new ticket event
  useEffect(() => {
    if (!latestTicketEvent) return;
    if (latestTicketEvent.event_type === 'ticket.created') {
      fetchTickets();
    }
  }, [latestTicketEvent, fetchTickets]);

  // Sort handler
  const handleSort = useCallback((field: TicketSortField) => {
    setSort((prev) => ({
      field,
      direction: prev.field === field && prev.direction === 'desc' ? 'asc' : 'desc',
    }));
    setPage(1);
  }, []);

  // Select handlers
  const toggleSelect = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const toggleSelectAll = useCallback(() => {
    if (selectedIds.size === tickets.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(tickets.map((t) => t.id)));
    }
  }, [selectedIds, tickets]);

  const clearSelection = useCallback(() => setSelectedIds(new Set()), []);

  // Bulk action handler
  const handleBulkAction = useCallback(async (action: BulkActionType, data?: Record<string, unknown>) => {
    try {
      const ids = Array.from(selectedIds);
      await ticketsApi.executeBulkAction({
        action,
        ticket_ids: ids,
        data: data as any,
      });
      toast.success(`Bulk action completed on ${ids.length} tickets`);
      clearSelection();
      fetchTickets();
    } catch {
      toast.error('Bulk action failed');
    }
  }, [selectedIds, clearSelection, fetchTickets]);

  // Page change
  const goToPage = useCallback((p: number) => {
    if (p < 1 || p > totalPages) return;
    setPage(p);
    clearSelection();
  }, [totalPages, clearSelection]);

  // Render pagination
  const renderPagination = () => {
    if (totalPages <= 1) return null;

    const pages: (number | '...')[] = [];
    if (totalPages <= 7) {
      for (let i = 1; i <= totalPages; i++) pages.push(i);
    } else {
      pages.push(1);
      if (page > 3) pages.push('...');
      for (let i = Math.max(2, page - 1); i <= Math.min(totalPages - 1, page + 1); i++) {
        pages.push(i);
      }
      if (page < totalPages - 2) pages.push('...');
      pages.push(totalPages);
    }

    return (
      <div className="flex items-center justify-between px-2">
        <span className="text-xs text-zinc-600">
          Showing {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, total)} of {total}
        </span>
        <div className="flex items-center gap-1">
          <button
            onClick={() => goToPage(page - 1)}
            disabled={page === 1}
            className="w-8 h-8 rounded-lg flex items-center justify-center text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.05] disabled:opacity-30 disabled:cursor-not-allowed transition-all"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5 8.25 12l7.5-7.5" />
            </svg>
          </button>
          {pages.map((p, idx) =>
            p === '...' ? (
              <span key={`ellipsis-${idx}`} className="w-8 h-8 flex items-center justify-center text-zinc-600 text-xs">
                ...
              </span>
            ) : (
              <button
                key={p}
                onClick={() => goToPage(p)}
                className={cn(
                  'w-8 h-8 rounded-lg flex items-center justify-center text-xs font-medium transition-all',
                  page === p
                    ? 'bg-orange-500/15 text-orange-400 border border-orange-500/25'
                    : 'text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.05]'
                )}
              >
                {p}
              </button>
            )
          )}
          <button
            onClick={() => goToPage(page + 1)}
            disabled={page === totalPages}
            className="w-8 h-8 rounded-lg flex items-center justify-center text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.05] disabled:opacity-30 disabled:cursor-not-allowed transition-all"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="m8.25 4.5 7.5 7.5-7.5 7.5" />
            </svg>
          </button>
        </div>
      </div>
    );
  };

  const allOnPageSelected = tickets.length > 0 && selectedIds.size === tickets.length;

  return (
    <div className={cn('space-y-4', className)}>
      {/* Search + Actions bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
        <TicketSearch
          value={filters.search || ''}
          onChange={(v) => {
            setFilters((prev) => ({ ...prev, search: v || undefined }));
            setPage(1);
          }}
          className="flex-1 max-w-md"
        />
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={cn(
              'flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium transition-all border',
              showFilters
                ? 'bg-orange-500/10 text-orange-400 border-orange-500/25'
                : 'bg-white/[0.04] text-zinc-400 border-white/[0.08] hover:bg-white/[0.08]'
            )}
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 6h9.75M10.5 6a1.5 1.5 0 1 1-3 0m3 0a1.5 1.5 0 1 0-3 0M3.75 6H7.5m3 12h9.75m-9.75 0a1.5 1.5 0 0 1-3 0m3 0a1.5 1.5 0 0 0-3 0m-3.75 0H7.5m9-6h3.75m-3.75 0a1.5 1.5 0 0 1-3 0m3 0a1.5 1.5 0 0 0-3 0m-9.75 0h9.75" />
            </svg>
            Filters
          </button>
          <button
            onClick={fetchTickets}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-white/[0.04] text-zinc-400 border border-white/[0.08] hover:bg-white/[0.08] text-xs font-medium transition-all"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182" />
            </svg>
            Refresh
          </button>
        </div>
      </div>

      {/* Filters panel */}
      {showFilters && (
        <div className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-4">
          <TicketFiltersBar filters={filters} onChange={(f) => { setFilters(f); setPage(1); }} />
        </div>
      )}

      {/* Bulk Actions */}
      <BulkActions
        selectedCount={selectedIds.size}
        onAction={handleBulkAction}
        onClearSelection={clearSelection}
      />

      {/* Table */}
      <div className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-white/[0.06]">
                <th className="w-10 px-3 py-2.5">
                  <input
                    type="checkbox"
                    checked={allOnPageSelected}
                    onChange={toggleSelectAll}
                    className="w-4 h-4 rounded border-white/[0.15] bg-white/[0.04] text-orange-500 focus:ring-orange-500/30 focus:ring-offset-0 cursor-pointer accent-orange-500"
                  />
                </th>
                <SortHeaderCell label="ID" field="ticket_number" currentSort={sort} onSort={handleSort} />
                <SortHeaderCell label="Pri" field="priority" currentSort={sort} onSort={handleSort} />
                <SortHeaderCell label="Status" field="status" currentSort={sort} onSort={handleSort} />
                <SortHeaderCell label="Subject" field="ticket_number" currentSort={sort} onSort={handleSort} />
                <th className="px-3 py-2.5 text-left text-[10px] font-semibold text-zinc-600 uppercase tracking-wider hidden md:table-cell">Customer</th>
                <SortHeaderCell label="Ch" field="channel" currentSort={sort} onSort={handleSort} showMobile={false} />
                <SortHeaderCell label="Agent" field="assigned_agent" currentSort={sort} onSort={handleSort} showMobile={false} />
                <SortHeaderCell label="AI" field="ai_confidence" currentSort={sort} onSort={handleSort} showMobile={false} />
                <SortHeaderCell label="Time" field="created_at" currentSort={sort} onSort={handleSort} showMobile />
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                Array.from({ length: 10 }).map((_, i) => (
                  <tr key={i} className="border-b border-white/[0.04]">
                    <td className="px-3 py-3"><div className="w-4 h-4 rounded bg-white/[0.04] animate-pulse" /></td>
                    <td className="px-3 py-3"><div className="w-16 h-3 rounded bg-white/[0.04] animate-pulse" /></td>
                    <td className="px-3 py-3"><div className="w-3 h-3 rounded-full bg-white/[0.04] animate-pulse" /></td>
                    <td className="px-3 py-3"><div className="w-16 h-5 rounded bg-white/[0.04] animate-pulse" /></td>
                    <td className="px-3 py-3"><div className="w-full max-w-[200px] h-3 rounded bg-white/[0.04] animate-pulse" /></td>
                    <td className="px-3 py-3 hidden md:table-cell"><div className="w-20 h-3 rounded bg-white/[0.04] animate-pulse" /></td>
                    <td className="px-3 py-3 hidden lg:table-cell"><div className="w-6 h-6 rounded bg-white/[0.04] animate-pulse" /></td>
                    <td className="px-3 py-3 hidden xl:table-cell"><div className="w-12 h-3 rounded bg-white/[0.04] animate-pulse" /></td>
                    <td className="px-3 py-3 hidden lg:table-cell"><div className="w-16 h-2 rounded bg-white/[0.04] animate-pulse" /></td>
                    <td className="px-3 py-3 hidden sm:table-cell"><div className="w-10 h-3 rounded bg-white/[0.04] animate-pulse" /></td>
                  </tr>
                ))
              ) : tickets.length === 0 ? (
                <tr>
                  <td colSpan={10} className="px-4 py-16 text-center">
                    <div className="text-zinc-600">
                      <svg className="w-12 h-12 mx-auto mb-3 text-zinc-700" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 6v.75m0 3v.75m0 3v.75m0 3V18m-9-5.25h5.25M7.5 15h3M3.375 5.25c-.621 0-1.125.504-1.125 1.125v3.026a2.999 2.999 0 0 1 0 5.198v3.026c0 .621.504 1.125 1.125 1.125h17.25c.621 0 1.125-.504 1.125-1.125v-3.026a2.999 2.999 0 0 1 0-5.198V6.375c0-.621-.504-1.125-1.125-1.125H3.375Z" />
                      </svg>
                      <p className="text-sm font-medium">No tickets found</p>
                      <p className="text-xs mt-1">Try adjusting your filters or search query</p>
                    </div>
                  </td>
                </tr>
              ) : (
                tickets.map((ticket) => (
                  <TicketRow
                    key={ticket.id}
                    ticket={ticket}
                    isSelected={selectedIds.has(ticket.id)}
                    onSelect={toggleSelect}
                    onHover={setHoveredTicket}
                  />
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {renderPagination()}
      </div>

      {/* Quick View (anchored to hovered row) */}
      {hoveredTicket && (
        <div className="fixed inset-0 z-40 pointer-events-none">
          <TicketQuickView
            ticket={hoveredTicket}
            onClose={() => setHoveredTicket(null)}
          />
        </div>
      )}
    </div>
  );
}
