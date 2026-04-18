'use client';

import React, { useRef, useState, useCallback } from 'react';
import { cn } from '@/lib/utils';
import type { Ticket } from '@/types/ticket';
import ConfidenceBar from './ConfidenceBar';
import { statusConfig, priorityConfig, timeAgo } from './TicketRow';

interface TicketQuickViewProps {
  ticket: Ticket;
  onClose: () => void;
}

export default function TicketQuickView({ ticket, onClose }: TicketQuickViewProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  return (
    <div
      ref={panelRef}
      className="absolute z-50 top-full left-0 mt-1 w-[360px] rounded-xl bg-[#1F1F1F] border border-white/[0.08] shadow-2xl shadow-black/50 overflow-hidden"
      onMouseLeave={onClose}
    >
      {/* Header */}
      <div className="px-4 py-3 border-b border-white/[0.06] flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-mono text-orange-400">{ticket.ticket_number}</span>
            <span className={cn(
              'inline-flex px-1.5 py-0.5 rounded text-[9px] font-bold border',
              statusConfig[ticket.status].className
            )}>
              {statusConfig[ticket.status].label}
            </span>
            <span className="flex items-center gap-1">
              <span className={cn('w-1.5 h-1.5 rounded-full', priorityConfig[ticket.priority].dotClass)} />
              <span className="text-[10px] text-zinc-500">{priorityConfig[ticket.priority].label}</span>
            </span>
          </div>
          <p className="text-sm font-medium text-zinc-200 truncate">{ticket.subject}</p>
        </div>
      </div>

      {/* Body */}
      <div className="px-4 py-3 space-y-3">
        {/* Customer */}
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-full bg-gradient-to-br from-violet-500/60 to-purple-400/60 flex items-center justify-center text-[10px] font-bold text-white shrink-0">
            {ticket.customer.name.charAt(0)}
          </div>
          <div className="min-w-0">
            <p className="text-xs font-medium text-zinc-300 truncate">{ticket.customer.name}</p>
            <p className="text-[10px] text-zinc-600 truncate">{ticket.customer.email}</p>
          </div>
        </div>

        {/* Description */}
        <p className="text-xs text-zinc-500 line-clamp-2">{ticket.description}</p>

        {/* Meta grid */}
        <div className="grid grid-cols-2 gap-2">
          <div className="rounded-lg bg-white/[0.03] border border-white/[0.04] p-2">
            <p className="text-[10px] text-zinc-600">AI Confidence</p>
            <ConfidenceBar value={ticket.ai_confidence} size="sm" />
          </div>
          <div className="rounded-lg bg-white/[0.03] border border-white/[0.04] p-2">
            <p className="text-[10px] text-zinc-600">Messages</p>
            <p className="text-sm font-semibold text-zinc-300">{ticket.message_count}</p>
          </div>
          <div className="rounded-lg bg-white/[0.03] border border-white/[0.04] p-2">
            <p className="text-[10px] text-zinc-600">Channel</p>
            <p className="text-xs font-medium text-zinc-300 capitalize">{ticket.channel}</p>
          </div>
          <div className="rounded-lg bg-white/[0.03] border border-white/[0.04] p-2">
            <p className="text-[10px] text-zinc-600">Agent</p>
            <p className="text-xs font-medium text-zinc-300">
              {ticket.assigned_agent?.name || 'Unassigned'}
            </p>
          </div>
        </div>

        {/* Tags */}
        {ticket.tags.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {ticket.tags.map((tag) => (
              <span key={tag} className="px-1.5 py-0.5 rounded bg-white/[0.04] text-[10px] text-zinc-500 border border-white/[0.04]">
                {tag}
              </span>
            ))}
          </div>
        )}

        {/* Footer */}
        <div className="flex items-center justify-between pt-2 border-t border-white/[0.04]">
          <span className="text-[10px] text-zinc-600">{timeAgo(ticket.created_at)}</span>
          {ticket.is_ai_resolved && (
            <span className="px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 text-[10px] font-medium border border-emerald-500/20">
              AI Resolved
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
