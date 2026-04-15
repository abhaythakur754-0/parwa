/**
 * PARWA ActivityFeed — Week 16 Day 1 (F-037)
 *
 * Real-time activity feed panel for the dashboard.
 * Shows ticket events with type-colored icons, actor info,
 * time-ago formatting, and filter tabs.
 */

'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import {
  dashboardApi,
  type ActivityEvent,
  type ActivityFeedResponse,
} from '@/lib/dashboard-api';

// ── Event Type Config ────────────────────────────────────────────────

const EVENT_TYPE_CONFIG: Record<
  string,
  { color: string; bgColor: string; label: string }
> = {
  ticket_created: {
    color: '#3B82F6',
    bgColor: 'bg-blue-500/10',
    label: 'New',
  },
  status_changed: {
    color: '#10B981',
    bgColor: 'bg-emerald-500/10',
    label: 'Status',
  },
  assigned: {
    color: '#F97316',
    bgColor: 'bg-orange-500/10',
    label: 'Assigned',
  },
  message: {
    color: '#0EA5E9',
    bgColor: 'bg-sky-500/10',
    label: 'Messages',
  },
  resolved: {
    color: '#22C55E',
    bgColor: 'bg-green-500/10',
    label: 'Resolved',
  },
};

const DEFAULT_EVENT_CONFIG = {
  color: '#71717A',
  bgColor: 'bg-zinc-500/10',
  label: 'Other',
};

// ── Filter Tabs ──────────────────────────────────────────────────────

type FilterTab = 'all' | 'status' | 'assigned' | 'new' | 'messages';

const FILTER_TABS: { key: FilterTab; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'status', label: 'Status' },
  { key: 'assigned', label: 'Assignments' },
  { key: 'new', label: 'New' },
  { key: 'messages', label: 'Messages' },
];

// Maps filter tabs to backend event_type params
const FILTER_EVENT_TYPE_MAP: Record<FilterTab, string | undefined> = {
  all: undefined,
  status: 'status_changed',
  assigned: 'assigned',
  new: 'ticket_created',
  messages: 'message',
};

// ── Time Formatting ──────────────────────────────────────────────────

function formatTimeAgo(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffMs = now - then;

  if (diffMs < 0) return 'just now';

  const seconds = Math.floor(diffMs / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  if (seconds < 60) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  if (hours < 24) return `${hours}h ago`;
  if (days < 7) return `${days}d ago`;
  if (days < 30) return `${Math.floor(days / 7)}w ago`;
  return `${Math.floor(days / 30)}mo ago`;
}

// ── Event Type Icons (inline SVGs) ───────────────────────────────────

function EventIcon({ eventType }: { eventType: string }) {
  const config = EVENT_TYPE_CONFIG[eventType] ?? DEFAULT_EVENT_CONFIG;

  switch (eventType) {
    case 'ticket_created':
      return (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke={config.color} strokeWidth={1.8}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
        </svg>
      );
    case 'status_changed':
      return (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke={config.color} strokeWidth={1.8}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
        </svg>
      );
    case 'assigned':
      return (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke={config.color} strokeWidth={1.8}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.501 20.118a7.5 7.5 0 0 1 14.998 0A17.933 17.933 0 0 1 12 21.75c-2.676 0-5.216-.584-7.499-1.632Z" />
        </svg>
      );
    case 'message':
      return (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke={config.color} strokeWidth={1.8}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H8.25m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H12m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 0 1-2.555-.337A5.972 5.972 0 0 1 5.41 20.97a5.969 5.969 0 0 1-.474-.065 4.48 4.48 0 0 0 .978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25Z" />
        </svg>
      );
    case 'resolved':
      return (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke={config.color} strokeWidth={1.8}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
        </svg>
      );
    default:
      return (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke={config.color} strokeWidth={1.8}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6A2.25 2.25 0 0 1 6 3.75h2.25A2.25 2.25 0 0 1 10.5 6v2.25a2.25 2.25 0 0 1-2.25 2.25H6a2.25 2.25 0 0 1-2.25-2.25V6ZM3.75 15.75A2.25 2.25 0 0 1 6 13.5h2.25a2.25 2.25 0 0 1 2.25 2.25V18a2.25 2.25 0 0 1-2.25 2.25H6A2.25 2.25 0 0 1 3.75 18v-2.25ZM13.5 6a2.25 2.25 0 0 1 2.25-2.25H18A2.25 2.25 0 0 1 20.25 6v2.25A2.25 2.25 0 0 1 18 10.5h-2.25a2.25 2.25 0 0 1-2.25-2.25V6ZM13.5 15.75a2.25 2.25 0 0 1 2.25-2.25H18a2.25 2.25 0 0 1 2.25 2.25V18A2.25 2.25 0 0 1 18 20.25h-2.25A2.25 2.25 0 0 1 13.5 18v-2.25Z" />
        </svg>
      );
  }
}

// ── Skeleton Item ────────────────────────────────────────────────────

function EventSkeleton() {
  return (
    <div className="flex items-start gap-3 px-4 py-3">
      <Skeleton className="w-8 h-8 rounded-lg shrink-0 bg-white/[0.06]" />
      <div className="flex-1 min-w-0 space-y-2">
        <Skeleton className="h-3.5 w-3/4 bg-white/[0.06]" />
        <Skeleton className="h-3 w-1/2 bg-white/[0.04]" />
      </div>
    </div>
  );
}

// ── Single Event Row ─────────────────────────────────────────────────

function EventRow({ event, isNew }: { event: ActivityEvent; isNew: boolean }) {
  const config = EVENT_TYPE_CONFIG[event.event_type] ?? DEFAULT_EVENT_CONFIG;

  return (
    <div
      className={cn(
        'flex items-start gap-3 px-4 py-3 rounded-lg transition-all duration-500',
        'hover:bg-white/[0.02] group',
        isNew && 'animate-[slideIn_0.4s_ease-out]'
      )}
    >
      {/* Icon */}
      <div
        className={cn(
          'w-8 h-8 rounded-lg flex items-center justify-center shrink-0 mt-0.5',
          config.bgColor
        )}
      >
        <EventIcon eventType={event.event_type} />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <p className="text-sm text-zinc-300 leading-relaxed truncate">
          {event.description}
        </p>

        <div className="flex items-center gap-2 mt-1 flex-wrap">
          {/* Actor name */}
          {event.actor_name && (
            <span className="text-xs text-zinc-500 font-medium">
              {event.actor_name}
            </span>
          )}

          {/* Separator dot */}
          {event.actor_name && <span className="w-1 h-1 rounded-full bg-zinc-700" />}

          {/* Time ago */}
          <span className="text-xs text-zinc-600">
            {formatTimeAgo(event.created_at)}
          </span>
        </div>

        {/* Ticket subject link */}
        {event.ticket_subject && (
          <p className="mt-1.5 text-xs text-zinc-500 group-hover:text-zinc-400 transition-colors truncate">
            <span className="inline-flex items-center gap-1">
              <svg className="w-3 h-3 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 6v.75m0 3v.75m0 3v.75m0 3V18m-9-5.25h5.25M7.5 15h3M3.375 5.25c-.621 0-1.125.504-1.125 1.125v3.026a2.999 2.999 0 0 1 0 5.198v3.026c0 .621.504 1.125 1.125 1.125h17.25c.621 0 1.125-.504 1.125-1.125v-3.026a2.999 2.999 0 0 1 0-5.198V6.375c0-.621-.504-1.125-1.125-1.125H3.375Z" />
              </svg>
              {event.ticket_subject}
            </span>
          </p>
        )}
      </div>
    </div>
  );
}

// ── Empty State ──────────────────────────────────────────────────────

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div className="w-12 h-12 rounded-xl bg-white/[0.03] border border-white/[0.06] flex items-center justify-center mb-3">
        <svg className="w-6 h-6 text-zinc-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
        </svg>
      </div>
      <p className="text-sm text-zinc-500 font-medium">No recent activity</p>
      <p className="text-xs text-zinc-600 mt-1">
        Events will appear here in real time
      </p>
    </div>
  );
}

// ── ActivityFeed Component ───────────────────────────────────────────

interface ActivityFeedProps {
  /** Pre-loaded initial events from the dashboard home API */
  initialEvents?: ActivityEvent[];
  /** Whether the parent is still loading */
  isLoading?: boolean;
  /** Additional CSS classes */
  className?: string;
}

export default function ActivityFeed({
  initialEvents,
  isLoading = false,
  className,
}: ActivityFeedProps) {
  const [events, setEvents] = useState<ActivityEvent[]>(initialEvents ?? []);
  const [activeFilter, setActiveFilter] = useState<FilterTab>('all');
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [isFetching, setIsFetching] = useState(false);
  const [lastRefreshed, setLastRefreshed] = useState<number>(Date.now());

  // Sync initial events when prop changes
  useEffect(() => {
    if (initialEvents) {
      setEvents(initialEvents);
      setHasMore(true);
      setPage(1);
    }
  }, [initialEvents]);

  // Fetch paginated activity feed
  const fetchEvents = useCallback(
    async (pageNum: number, append: boolean = false) => {
      if (isFetching) return;
      setIsFetching(true);

      try {
        const eventType = FILTER_EVENT_TYPE_MAP[activeFilter];
        const result: ActivityFeedResponse = await dashboardApi.getActivityFeed(
          pageNum,
          25,
          eventType
        );

        if (append) {
          setEvents((prev) => [...prev, ...result.events]);
        } else {
          setEvents(result.events);
        }

        setHasMore(result.has_more);
        setPage(result.page);
      } catch {
        // Silent fail — activity feed is supplementary
      } finally {
        setIsFetching(false);
        setLastRefreshed(Date.now());
      }
    },
    [activeFilter, isFetching]
  );

  // Auto-refresh every 30 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      fetchEvents(1, false);
    }, 30000);
    return () => clearInterval(interval);
  }, [fetchEvents]);

  // Re-fetch when filter changes
  const handleFilterChange = useCallback(
    (tab: FilterTab) => {
      setActiveFilter(tab);
      setPage(1);
      setEvents([]);
      setHasMore(true);
    },
    []
  );

  useEffect(() => {
    fetchEvents(1, false);
  }, [activeFilter]);

  // Load more handler
  const handleLoadMore = useCallback(() => {
    if (!hasMore || isFetching) return;
    fetchEvents(page + 1, true);
  }, [hasMore, isFetching, page, fetchEvents]);

  // Determine which events are "new" (appeared in last 60s)
  const nowMs = Date.now();
  const newEventIds = new Set(
    events
      .filter((e) => nowMs - new Date(e.created_at).getTime() < 60_000)
      .map((e) => e.event_id)
  );

  return (
    <div
      className={cn(
        'bg-[#1A1A1A] border border-white/[0.06] rounded-xl overflow-hidden',
        className
      )}
    >
      {/* ── Header ──────────────────────────────────────────────── */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.06]">
        <div className="flex items-center gap-2.5">
          <h3 className="text-sm font-semibold text-zinc-200">Activity Feed</h3>
          {/* Live indicator */}
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20">
            <span className="relative flex h-1.5 w-1.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-emerald-500" />
            </span>
            <span className="text-[10px] font-medium text-emerald-400">Live</span>
          </span>
        </div>

        {/* Auto-refresh timestamp */}
        <span className="text-[10px] text-zinc-600">
          Updated {formatTimeAgo(new Date(lastRefreshed).toISOString())}
        </span>
      </div>

      {/* ── Filter Tabs ─────────────────────────────────────────── */}
      <div className="flex items-center gap-0.5 px-4 py-2 border-b border-white/[0.04] overflow-x-auto">
        {FILTER_TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => handleFilterChange(tab.key)}
            className={cn(
              'px-2.5 py-1 rounded-md text-xs font-medium whitespace-nowrap transition-all duration-200',
              activeFilter === tab.key
                ? 'bg-white/[0.08] text-zinc-200 shadow-sm'
                : 'text-zinc-500 hover:text-zinc-400 hover:bg-white/[0.03]'
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ── Event List ──────────────────────────────────────────── */}
      {isLoading ? (
        <div className="space-y-1 p-2">
          <EventSkeleton />
          <EventSkeleton />
          <EventSkeleton />
          <EventSkeleton />
          <EventSkeleton />
        </div>
      ) : events.length === 0 ? (
        <EmptyState />
      ) : (
        <ScrollArea className="max-h-[480px]">
          <div className="space-y-0.5 py-1">
            {events.map((event) => (
              <EventRow
                key={event.event_id}
                event={event}
                isNew={newEventIds.has(event.event_id)}
              />
            ))}
          </div>
        </ScrollArea>
      )}

      {/* ── Load More ───────────────────────────────────────────── */}
      {hasMore && !isLoading && (
        <div className="px-4 py-3 border-t border-white/[0.04]">
          <button
            onClick={handleLoadMore}
            disabled={isFetching}
            className={cn(
              'w-full py-2 rounded-lg text-xs font-medium transition-all duration-200',
              'border border-white/[0.08] text-zinc-400',
              'hover:bg-white/[0.04] hover:text-zinc-300 hover:border-white/[0.12]',
              'disabled:opacity-40 disabled:cursor-not-allowed'
            )}
          >
            {isFetching ? (
              <span className="inline-flex items-center gap-2">
                <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Loading…
              </span>
            ) : (
              `Load more (${events.length} shown)`
            )}
          </button>
        </div>
      )}
    </div>
  );
}

// ── CSS Keyframes (injected via style tag) ───────────────────────────
// The slideIn animation is referenced above via Tailwind's arbitrary value syntax.
// We need to add it to globals.css or use a <style> tag.
// For now, we'll use the existing animate- classes available.
