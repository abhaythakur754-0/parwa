'use client';

import React from 'react';
import { cn } from '@/lib/utils';
import type { BulkActionType, TicketPriority } from '@/types/ticket';
import { mockAgents } from '@/lib/mock/ticket-mock-data';

interface BulkActionsProps {
  selectedCount: number;
  onAction: (action: BulkActionType, data?: Record<string, unknown>) => void;
  onClearSelection: () => void;
  className?: string;
}

export default function BulkActions({ selectedCount, onAction, onClearSelection, className }: BulkActionsProps) {
  if (selectedCount === 0) return null;

  return (
    <div
      className={cn(
        'flex items-center gap-3 px-4 py-2.5 rounded-xl bg-orange-500/[0.06] border border-orange-500/15 shadow-sm',
        className
      )}
    >
      <span className="text-xs font-semibold text-orange-400 whitespace-nowrap">
        {selectedCount} selected
      </span>

      <div className="w-px h-4 bg-orange-500/20" />

      <div className="flex items-center gap-1.5 flex-wrap">
        <button
          onClick={() => onAction('mark_resolved')}
          className="px-2.5 py-1 rounded-lg bg-emerald-500/10 text-emerald-400 text-xs font-medium border border-emerald-500/20 hover:bg-emerald-500/20 transition-all"
        >
          ✓ Mark Resolved
        </button>

        {/* Assign Agent Dropdown */}
        <div className="relative group">
          <button className="px-2.5 py-1 rounded-lg bg-blue-500/10 text-blue-400 text-xs font-medium border border-blue-500/20 hover:bg-blue-500/20 transition-all">
            👤 Assign Agent ▾
          </button>
          <div className="absolute top-full left-0 mt-1 min-w-[160px] bg-[#1F1F1F] border border-white/[0.08] rounded-xl shadow-2xl shadow-black/50 py-1 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50">
            {mockAgents.map((agent) => (
              <button
                key={agent.id}
                onClick={() => onAction('assign_agent', { agent_id: agent.id })}
                className="w-full text-left px-3 py-1.5 text-xs text-zinc-300 hover:bg-white/[0.05] transition-colors flex items-center gap-2"
              >
                <div className={cn('w-1.5 h-1.5 rounded-full', agent.is_online ? 'bg-emerald-400' : 'bg-zinc-600')} />
                {agent.name}
              </button>
            ))}
          </div>
        </div>

        {/* Change Priority Dropdown */}
        <div className="relative group">
          <button className="px-2.5 py-1 rounded-lg bg-amber-500/10 text-amber-400 text-xs font-medium border border-amber-500/20 hover:bg-amber-500/20 transition-all">
            ⚡ Priority ▾
          </button>
          <div className="absolute top-full left-0 mt-1 min-w-[140px] bg-[#1F1F1F] border border-white/[0.08] rounded-xl shadow-2xl shadow-black/50 py-1 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50">
            {(['low', 'medium', 'high', 'critical'] as TicketPriority[]).map((p) => (
              <button
                key={p}
                onClick={() => onAction('change_priority', { priority: p })}
                className="w-full text-left px-3 py-1.5 text-xs text-zinc-300 hover:bg-white/[0.05] transition-colors capitalize"
              >
                {p}
              </button>
            ))}
          </div>
        </div>

        <button
          onClick={() => onAction('export')}
          className="px-2.5 py-1 rounded-lg bg-white/[0.04] text-zinc-400 text-xs font-medium border border-white/[0.08] hover:bg-white/[0.08] transition-all"
        >
          📥 Export
        </button>
      </div>

      <div className="w-px h-4 bg-orange-500/20" />

      <button
        onClick={onClearSelection}
        className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors whitespace-nowrap"
      >
        Clear
      </button>
    </div>
  );
}
