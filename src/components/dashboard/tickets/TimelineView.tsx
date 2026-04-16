'use client';

import React from 'react';
import { cn } from '@/lib/utils';
import type { TimelineEntry } from '@/types/ticket';

interface TimelineViewProps {
  entries: TimelineEntry[];
  className?: string;
}

const eventIcons: Record<string, { icon: string; color: string }> = {
  'ticket.created': { icon: '📝', color: 'text-blue-400' },
  'ticket.auto_assigned': { icon: '🤖', color: 'text-orange-400' },
  'ticket.ai_responded': { icon: '💬', color: 'text-orange-400' },
  'ticket.agent_assigned': { icon: '👤', color: 'text-emerald-400' },
  'ticket.escalated': { icon: '⚡', color: 'text-red-400' },
  'ticket.note_added': { icon: '📌', color: 'text-amber-400' },
  'ticket.status_changed': { icon: '🔄', color: 'text-purple-400' },
  'ticket.priority_changed': { icon: '🔥', color: 'text-orange-400' },
  'ticket.resolved': { icon: '✅', color: 'text-emerald-400' },
  'ticket.closed': { icon: '🔒', color: 'text-zinc-400' },
  'ticket.reopened': { icon: '🔓', color: 'text-blue-400' },
  'ticket.reply_sent': { icon: '↩️', color: 'text-cyan-400' },
};

function formatTime(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

export default function TimelineView({ entries, className }: TimelineViewProps) {
  return (
    <div className={cn('rounded-xl bg-[#1A1A1A] border border-white/[0.06] overflow-hidden', className)}>
      {/* Header */}
      <div className="px-4 py-3 border-b border-white/[0.06]">
        <h3 className="text-xs font-semibold text-zinc-300">Timeline</h3>
      </div>

      {/* Timeline */}
      <div className="max-h-72 overflow-y-auto p-4">
        {entries.length === 0 ? (
          <div className="text-center text-xs text-zinc-600 py-6">No events yet</div>
        ) : (
          <div className="relative">
            {/* Vertical line */}
            <div className="absolute left-[14px] top-2 bottom-2 w-px bg-white/[0.06]" />

            <div className="space-y-4">
              {entries.map((entry, idx) => {
                const icon = eventIcons[entry.event_type] || { icon: '•', color: 'text-zinc-500' };

                return (
                  <div key={entry.id} className="flex gap-3 relative">
                    {/* Dot */}
                    <div className={cn(
                      'w-7 h-7 rounded-full bg-[#1A1A1A] border border-white/[0.06] flex items-center justify-center text-sm shrink-0 z-10',
                    )}>
                      {icon.icon}
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0 pt-0.5">
                      <p className="text-xs text-zinc-300">{entry.description}</p>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-[10px] text-zinc-600">{formatTime(entry.created_at)}</span>
                        {entry.actor_name && (
                          <>
                            <span className="text-[10px] text-zinc-700">by</span>
                            <span className="text-[10px] text-zinc-500">{entry.actor_name}</span>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
