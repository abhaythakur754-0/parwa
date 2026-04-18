'use client';

import React, { useCallback, useRef, useState } from 'react';
import Link from 'next/link';
import { cn } from '@/lib/utils';
import type { Ticket, TicketStatus, TicketPriority, TicketChannel } from '@/types/ticket';
import ConfidenceBar from './ConfidenceBar';
import { SLABadge } from './SLATimer';

// ── Config Maps ─────────────────────────────────────────────────────────

const statusConfig: Record<TicketStatus, { label: string; className: string }> = {
  open: { label: 'Open', className: 'bg-blue-500/15 text-blue-400 border-blue-500/25' },
  in_progress: { label: 'In Progress', className: 'bg-amber-500/15 text-amber-400 border-amber-500/25' },
  awaiting_customer: { label: 'Awaiting', className: 'bg-purple-500/15 text-purple-400 border-purple-500/25' },
  awaiting_agent: { label: 'Pending Agent', className: 'bg-cyan-500/15 text-cyan-400 border-cyan-500/25' },
  escalated: { label: 'Escalated', className: 'bg-red-500/15 text-red-400 border-red-500/25' },
  resolved: { label: 'Resolved', className: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/25' },
  closed: { label: 'Closed', className: 'bg-zinc-500/15 text-zinc-400 border-zinc-500/25' },
  spam: { label: 'Spam', className: 'bg-zinc-500/15 text-zinc-500 border-zinc-500/25' },
};

const priorityConfig: Record<TicketPriority, { label: string; dotClass: string }> = {
  critical: { label: 'Critical', dotClass: 'bg-red-500 shadow-sm shadow-red-500/50' },
  high: { label: 'High', dotClass: 'bg-orange-500 shadow-sm shadow-orange-500/50' },
  medium: { label: 'Medium', dotClass: 'bg-amber-500 shadow-sm shadow-amber-500/50' },
  low: { label: 'Low', dotClass: 'bg-zinc-500' },
};

const channelIcons: Record<TicketChannel, string> = {
  email: '✉️',
  chat: '💬',
  sms: '📱',
  voice: '🎙️',
  whatsapp: '🟢',
  messenger: '🙋',
  twitter: '🐦',
  instagram: '📷',
  telegram: '✈️',
  slack: '💡',
};

function timeAgo(dateStr: string): string {
  const seconds = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
  if (seconds < 60) return 'just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  if (seconds < 604800) return `${Math.floor(seconds / 86400)}d ago`;
  return new Date(dateStr).toLocaleDateString();
}

// ── TicketRow Props ─────────────────────────────────────────────────────

interface TicketRowProps {
  ticket: Ticket;
  isSelected: boolean;
  onSelect: (id: string) => void;
  onHover?: (ticket: Ticket | null) => void;
  sortField?: string;
  onSort?: (field: string) => void;
}

export default function TicketRow({ ticket, isSelected, onSelect, onHover }: TicketRowProps) {
  const status = statusConfig[ticket.status];
  const priority = priorityConfig[ticket.priority];
  const rowRef = useRef<HTMLTableRowElement>(null);

  const handleMouseEnter = useCallback(() => {
    if (onHover) onHover(ticket);
  }, [onHover, ticket]);

  const handleMouseLeave = useCallback(() => {
    if (onHover) onHover(null);
  }, [onHover]);

  return (
    <tr
      ref={rowRef}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      className={cn(
        'group border-b border-white/[0.04] transition-all duration-150',
        isSelected
          ? 'bg-orange-500/[0.06]'
          : 'hover:bg-white/[0.02]'
      )}
    >
      {/* Checkbox */}
      <td className="w-10 px-3 py-3">
        <input
          type="checkbox"
          checked={isSelected}
          onChange={() => onSelect(ticket.id)}
          className="w-4 h-4 rounded border-white/[0.15] bg-white/[0.04] text-orange-500 focus:ring-orange-500/30 focus:ring-offset-0 cursor-pointer accent-orange-500"
        />
      </td>

      {/* Ticket ID */}
      <td className="px-3 py-3">
        <Link
          href={`/dashboard/tickets/${ticket.id}`}
          className="text-xs font-mono font-medium text-orange-400 hover:text-orange-300 transition-colors"
        >
          {ticket.ticket_number}
        </Link>
      </td>

      {/* Priority */}
      <td className="px-3 py-3">
        <div className="flex items-center gap-1.5">
          <span className={cn('w-2 h-2 rounded-full', priority.dotClass)} />
          <span className="text-xs text-zinc-400 hidden xl:inline">{priority.label}</span>
        </div>
      </td>

      {/* Status */}
      <td className="px-3 py-3">
        <div className="flex items-center gap-2">
          <span className={cn('inline-flex px-2 py-0.5 rounded-md text-[10px] font-semibold border', status.className)}>
            {status.label}
          </span>
          {/* SLA Badge */}
          {ticket.sla_deadline && (
            <SLABadge
              isBreached={ticket.sla_breached}
              isApproaching={ticket.sla_approaching}
              hasSLA={true}
            />
          )}
        </div>
      </td>

      {/* Subject */}
      <td className="px-3 py-3 max-w-[220px] lg:max-w-[300px]">
        <Link
          href={`/dashboard/tickets/${ticket.id}`}
          className="text-sm text-zinc-200 hover:text-white transition-colors truncate block font-medium"
          title={ticket.subject}
        >
          {ticket.subject}
        </Link>
        {ticket.has_attachments && (
          <span className="text-[10px] text-zinc-600">📎</span>
        )}
      </td>

      {/* Customer */}
      <td className="px-3 py-3 hidden md:table-cell">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-full bg-gradient-to-br from-violet-500/60 to-purple-400/60 flex items-center justify-center text-[10px] font-bold text-white shrink-0">
            {ticket.customer.name.charAt(0)}
          </div>
          <span className="text-xs text-zinc-400 truncate max-w-[100px]">{ticket.customer.name}</span>
        </div>
      </td>

      {/* Channel */}
      <td className="px-3 py-3 hidden lg:table-cell">
        <span className="text-sm" title={ticket.channel}>
          {channelIcons[ticket.channel] || '💬'}
        </span>
      </td>

      {/* Agent */}
      <td className="px-3 py-3 hidden xl:table-cell">
        {ticket.assigned_agent ? (
          <div className="flex items-center gap-1.5">
            <div className={cn(
              'w-1.5 h-1.5 rounded-full',
              ticket.assigned_agent.is_online ? 'bg-emerald-400' : 'bg-zinc-600'
            )} />
            <span className="text-xs text-zinc-400">{ticket.assigned_agent.name.split(' ')[0]}</span>
          </div>
        ) : (
          <span className="text-xs text-zinc-600">Unassigned</span>
        )}
      </td>

      {/* Confidence */}
      <td className="px-3 py-3 hidden lg:table-cell w-[120px]">
        <ConfidenceBar value={ticket.ai_confidence} size="sm" showLabel={false} />
      </td>

      {/* Time */}
      <td className="px-3 py-3 hidden sm:table-cell">
        <span className="text-[11px] text-zinc-500 tabular-nums">
          {timeAgo(ticket.created_at)}
        </span>
      </td>
    </tr>
  );
}

export { statusConfig, priorityConfig, channelIcons, timeAgo };
