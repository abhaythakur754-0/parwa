/**
 * PARWA Ticket Activity Stream Component
 *
 * Real-time activity stream for ticket updates.
 * Shows live events with filtering, status indicators, and click-to-navigate.
 *
 * Day 7 — Real-time Updates & Dashboard Integration
 */

'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { cn } from '@/lib/utils';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Button } from '@/components/ui/button';
import { useTicketRealtime, type TicketEvent } from './useTicketRealtime';

// ── Types ─────────────────────────────────────────────────────────────────

type FilterType = 'all' | 'new' | 'status' | 'messages' | 'escalations' | 'assignments';

interface TicketActivityStreamProps {
  /** Title for the stream panel */
  title?: string;
  /** Show connection status indicator */
  showConnectionStatus?: boolean;
  /** Enable filter tabs */
  enableFilters?: boolean;
  /** Maximum height of the stream */
  maxHeight?: string;
  /** Auto-scroll to new events */
  autoScroll?: boolean;
  /** Callback when event is clicked */
  onEventClick?: (event: TicketEvent) => void;
  /** Additional CSS classes */
  className?: string;
}

// ── Event Type Configuration ─────────────────────────────────────────────

const EVENT_TYPE_CONFIG: Record<
  string,
  { color: string; bgColor: string; borderColor: string; label: string; icon: React.ReactNode }
> = {
  'ticket:new': {
    color: 'text-blue-400',
    bgColor: 'bg-blue-500/10',
    borderColor: 'border-l-blue-500',
    label: 'New Ticket',
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
      </svg>
    ),
  },
  'ticket:status_changed': {
    color: 'text-emerald-400',
    bgColor: 'bg-emerald-500/10',
    borderColor: 'border-l-emerald-500',
    label: 'Status Changed',
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99" />
      </svg>
    ),
  },
  'ticket:assigned': {
    color: 'text-orange-400',
    bgColor: 'bg-orange-500/10',
    borderColor: 'border-l-orange-500',
    label: 'Assigned',
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.501 20.118a7.5 7.5 0 0 1 14.998 0A17.933 17.933 0 0 1 12 21.75c-2.676 0-5.216-.584-7.499-1.632Z" />
      </svg>
    ),
  },
  'ticket:resolved': {
    color: 'text-green-400',
    bgColor: 'bg-green-500/10',
    borderColor: 'border-l-green-500',
    label: 'Resolved',
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
      </svg>
    ),
  },
  'ticket:escalated': {
    color: 'text-red-400',
    bgColor: 'bg-red-500/10',
    borderColor: 'border-l-red-500',
    label: 'Escalated',
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 0 1 3 19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V8.625ZM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V4.125Z" />
      </svg>
    ),
  },
  'ticket:reopened': {
    color: 'text-amber-400',
    bgColor: 'bg-amber-500/10',
    borderColor: 'border-l-amber-500',
    label: 'Reopened',
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99" />
      </svg>
    ),
  },
  'message:new': {
    color: 'text-sky-400',
    bgColor: 'bg-sky-500/10',
    borderColor: 'border-l-sky-500',
    label: 'New Message',
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H8.25m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H12m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 0 1-2.555-.337A5.972 5.972 0 0 1 5.41 20.97a5.969 5.969 0 0 1-.474-.065 4.48 4.48 0 0 0 .978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25Z" />
      </svg>
    ),
  },
  'note:added': {
    color: 'text-violet-400',
    bgColor: 'bg-violet-500/10',
    borderColor: 'border-l-violet-500',
    label: 'Note Added',
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0 1 15.75 21H5.25A2.25 2.25 0 0 1 3 18.75V8.25A2.25 2.25 0 0 1 5.25 6H10" />
      </svg>
    ),
  },
};

const DEFAULT_CONFIG = {
  color: 'text-zinc-400',
  bgColor: 'bg-zinc-500/10',
  borderColor: 'border-l-zinc-500',
  label: 'Event',
  icon: (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6A2.25 2.25 0 0 1 6 3.75h2.25A2.25 2.25 0 0 1 10.5 6v2.25a2.25 2.25 0 0 1-2.25 2.25H6a2.25 2.25 0 0 1-2.25-2.25V6Z" />
    </svg>
  ),
};

// ── Filter Configuration ─────────────────────────────────────────────────

const FILTERS: { key: FilterType; label: string; eventTypes: string[] }[] = [
  { key: 'all', label: 'All', eventTypes: [] },
  { key: 'new', label: 'New', eventTypes: ['ticket:new'] },
  { key: 'status', label: 'Status', eventTypes: ['ticket:status_changed', 'ticket:resolved', 'ticket:reopened'] },
  { key: 'messages', label: 'Messages', eventTypes: ['message:new', 'note:added'] },
  { key: 'escalations', label: 'Escalations', eventTypes: ['ticket:escalated'] },
  { key: 'assignments', label: 'Assignments', eventTypes: ['ticket:assigned'] },
];

// ── Time Formatting ───────────────────────────────────────────────────────

function formatTimeAgo(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffMs = now - then;

  if (diffMs < 0) return 'just now';
  const seconds = Math.floor(diffMs / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);

  if (seconds < 60) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  if (hours < 24) return `${hours}h ago`;
  return new Date(dateStr).toLocaleDateString();
}

// ── Event Row Component ──────────────────────────────────────────────────

interface EventRowProps {
  event: TicketEvent;
  isNew: boolean;
  onClick?: (event: TicketEvent) => void;
}

function EventRow({ event, isNew, onClick }: EventRowProps) {
  const config = EVENT_TYPE_CONFIG[event.event_type] ?? DEFAULT_CONFIG;

  return (
    <button
      onClick={() => onClick?.(event)}
      className={cn(
        'w-full text-left px-4 py-3 border-l-2 transition-all duration-300',
        config.borderColor,
        'hover:bg-white/[0.02]',
        isNew && 'animate-[fadeIn_0.4s_ease-out]'
      )}
    >
      <div className="flex items-start gap-3">
        {/* Icon */}
        <div
          className={cn(
            'w-8 h-8 rounded-lg flex items-center justify-center shrink-0 mt-0.5',
            config.bgColor
          )}
        >
          <span className={config.color}>{config.icon}</span>
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className={cn('text-xs font-medium', config.color)}>
              {config.label}
            </span>
            {isNew && (
              <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-blue-500/20 text-blue-400">
                NEW
              </span>
            )}
          </div>

          <p className="text-sm text-zinc-300 mt-1 truncate">
            {event.ticket_subject || `Ticket #${event.ticket_id.slice(0, 8)}`}
          </p>

          <div className="flex items-center gap-2 mt-1.5 flex-wrap">
            {/* Status change details */}
            {event.old_value && event.new_value && (
              <span className="text-xs text-zinc-500">
                <span className="text-zinc-600">{event.old_value}</span>
                <span className="mx-1">→</span>
                <span className="text-zinc-400">{event.new_value}</span>
              </span>
            )}

            {/* Actor */}
            {event.actor_name && (
              <span className="text-xs text-zinc-500">
                {event.actor_type === 'ai' ? '🤖' : event.actor_type === 'system' ? '⚙️' : '👤'}{' '}
                {event.actor_name}
              </span>
            )}

            {/* Time */}
            <span className="text-xs text-zinc-600">{formatTimeAgo(event.timestamp)}</span>
          </div>
        </div>
      </div>
    </button>
  );
}

// ── Connection Status ─────────────────────────────────────────────────────

interface ConnectionStatusProps {
  isConnected: boolean;
  lastEventAt: string | null;
}

function ConnectionStatus({ isConnected, lastEventAt }: ConnectionStatusProps) {
  return (
    <div className="flex items-center gap-2 px-4 py-2 bg-white/[0.02] border-b border-white/[0.04]">
      <div className="flex items-center gap-1.5">
        <span
          className={cn(
            'w-2 h-2 rounded-full',
            isConnected ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500'
          )}
        />
        <span className="text-xs font-medium text-zinc-400">
          {isConnected ? 'Connected' : 'Reconnecting...'}
        </span>
      </div>

      {lastEventAt && (
        <span className="text-xs text-zinc-600 ml-auto">
          Last event: {formatTimeAgo(lastEventAt)}
        </span>
      )}
    </div>
  );
}

// ── Empty State ───────────────────────────────────────────────────────────

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-12 px-4">
      <div className="w-14 h-14 rounded-xl bg-white/[0.03] border border-white/[0.06] flex items-center justify-center mb-4">
        <svg className="w-7 h-7 text-zinc-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M3.75 12h16.5m-16.5 3.75h16.5M3.75 19.5h16.5M5.625 4.5h12.75a1.875 1.875 0 0 1 0 3.75H5.625a1.875 1.875 0 0 1 0-3.75Z"
          />
        </svg>
      </div>
      <p className="text-sm text-zinc-500 font-medium">No activity yet</p>
      <p className="text-xs text-zinc-600 mt-1 text-center max-w-[200px]">
        Real-time ticket events will stream here as they happen
      </p>
    </div>
  );
}

// ── Main Component ───────────────────────────────────────────────────────

export default function TicketActivityStream({
  title = 'Live Activity',
  showConnectionStatus = true,
  enableFilters = true,
  maxHeight = '500px',
  autoScroll = true,
  onEventClick,
  className,
}: TicketActivityStreamProps) {
  const { recentEvents, isConnected, lastEventAt, clearEvents, acknowledge } = useTicketRealtime();
  const [activeFilter, setActiveFilter] = useState<FilterType>('all');
  const scrollRef = React.useRef<HTMLDivElement>(null);

  // Filter events based on active filter
  const filteredEvents = useMemo(() => {
    if (activeFilter === 'all') return recentEvents;

    const filterConfig = FILTERS.find((f) => f.key === activeFilter);
    if (!filterConfig) return recentEvents;

    return recentEvents.filter((event) =>
      filterConfig.eventTypes.includes(event.event_type)
    );
  }, [recentEvents, activeFilter]);

  // Auto-scroll to bottom on new events
  useEffect(() => {
    if (autoScroll && scrollRef.current && filteredEvents.length > 0) {
      scrollRef.current.scrollTop = 0;
    }
  }, [filteredEvents, autoScroll]);

  // Acknowledge events when component mounts
  useEffect(() => {
    acknowledge('all');
  }, [acknowledge]);

  // Determine which events are "new" (last 60 seconds)
  const nowMs = Date.now();
  const newEventIds = useMemo(
    () =>
      new Set(
        recentEvents
          .filter((e) => nowMs - new Date(e.timestamp).getTime() < 60_000)
          .map((e) => e.event_id)
      ),
    [recentEvents, nowMs]
  );

  return (
    <div
      className={cn(
        'bg-[#1A1A1A] border border-white/[0.06] rounded-xl overflow-hidden',
        className
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.06]">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-zinc-200">{title}</h3>
          {isConnected && (
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20">
              <span className="relative flex h-1.5 w-1.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-emerald-500" />
              </span>
              <span className="text-[10px] font-medium text-emerald-400">LIVE</span>
            </span>
          )}
        </div>

        {recentEvents.length > 0 && (
          <button
            onClick={clearEvents}
            className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
          >
            Clear
          </button>
        )}
      </div>

      {/* Connection Status */}
      {showConnectionStatus && (
        <ConnectionStatus isConnected={isConnected} lastEventAt={lastEventAt} />
      )}

      {/* Filter Tabs */}
      {enableFilters && (
        <div className="flex items-center gap-0.5 px-4 py-2 border-b border-white/[0.04] overflow-x-auto">
          {FILTERS.map((filter) => (
            <button
              key={filter.key}
              onClick={() => setActiveFilter(filter.key)}
              className={cn(
                'px-2.5 py-1 rounded-md text-xs font-medium whitespace-nowrap transition-all duration-200',
                activeFilter === filter.key
                  ? 'bg-white/[0.08] text-zinc-200 shadow-sm'
                  : 'text-zinc-500 hover:text-zinc-400 hover:bg-white/[0.03]'
              )}
            >
              {filter.label}
              {filter.key !== 'all' && (
                <span className="ml-1 text-zinc-600">
                  (
                  {filter.key === 'new'
                    ? recentEvents.filter((e) => e.event_type === 'ticket:new').length
                    : filter.key === 'status'
                    ? recentEvents.filter((e) =>
                        ['ticket:status_changed', 'ticket:resolved', 'ticket:reopened'].includes(e.event_type)
                      ).length
                    : filter.key === 'messages'
                    ? recentEvents.filter((e) => ['message:new', 'note:added'].includes(e.event_type)).length
                    : filter.key === 'escalations'
                    ? recentEvents.filter((e) => e.event_type === 'ticket:escalated').length
                    : recentEvents.filter((e) => e.event_type === 'ticket:assigned').length}
                  )
                </span>
              )}
            </button>
          ))}
        </div>
      )}

      {/* Event List */}
      {filteredEvents.length === 0 ? (
        <EmptyState />
      ) : (
        <ScrollArea style={{ maxHeight }} ref={scrollRef}>
          <div className="divide-y divide-white/[0.04]">
            {filteredEvents.map((event) => (
              <EventRow
                key={event.event_id}
                event={event}
                isNew={newEventIds.has(event.event_id)}
                onClick={onEventClick}
              />
            ))}
          </div>
        </ScrollArea>
      )}

      {/* Footer Stats */}
      {recentEvents.length > 0 && (
        <div className="flex items-center justify-between px-4 py-2 border-t border-white/[0.04] bg-white/[0.01]">
          <span className="text-xs text-zinc-600">
            {recentEvents.length} event{recentEvents.length !== 1 ? 's' : ''} in stream
          </span>
          <span className="text-xs text-zinc-600">
            {filteredEvents.length} shown
          </span>
        </div>
      )}
    </div>
  );
}
