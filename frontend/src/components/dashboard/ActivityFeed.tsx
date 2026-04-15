'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { cn } from '@/lib/utils';
import { dashboardApi, type ActivityEvent } from '@/lib/dashboard-api';
import type { ActivityEventType } from '@/types/analytics';

// ── Props ─────────────────────────────────────────────────────────────

interface ActivityFeedProps {
  /** Pre-loaded events from dashboard home (F-036 embed) */
  initialEvents?: ActivityEvent[];
  /** Height class for the feed container */
  className?: string;
  /** Whether to show the filter tabs */
  showFilters?: boolean;
}

// ── Event Type Config ─────────────────────────────────────────────────

const EVENT_TYPE_CONFIG: Record<ActivityEventType, {
  label: string;
  icon: React.ReactNode;
  color: string;
  bgColor: string;
}> = {
  ticket_created: {
    label: 'Created',
    color: 'text-sky-400',
    bgColor: 'bg-sky-500/10',
    icon: (
      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
      </svg>
    ),
  },
  status_changed: {
    label: 'Status',
    color: 'text-amber-400',
    bgColor: 'bg-amber-500/10',
    icon: (
      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 21 3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" />
      </svg>
    ),
  },
  assigned: {
    label: 'Assigned',
    color: 'text-purple-400',
    bgColor: 'bg-purple-500/10',
    icon: (
      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.501 20.118a7.5 7.5 0 0 1 14.998 0A17.933 17.933 0 0 1 12 21.75c-2.676 0-5.216-.584-7.499-1.632Z" />
      </svg>
    ),
  },
  resolved: {
    label: 'Resolved',
    color: 'text-emerald-400',
    bgColor: 'bg-emerald-500/10',
    icon: (
      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
      </svg>
    ),
  },
  message_added: {
    label: 'Message',
    color: 'text-blue-400',
    bgColor: 'bg-blue-500/10',
    icon: (
      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H8.25m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H12m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 0 1-2.555-.337A5.972 5.972 0 0 1 5.41 20.97a5.969 5.969 0 0 1-.474-.065 4.48 4.48 0 0 0 .978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25Z" />
      </svg>
    ),
  },
  note_added: {
    label: 'Note',
    color: 'text-zinc-400',
    bgColor: 'bg-zinc-500/10',
    icon: (
      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931Zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10" />
      </svg>
    ),
  },
  tag_added: {
    label: 'Tag',
    color: 'text-orange-400',
    bgColor: 'bg-orange-500/10',
    icon: (
      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9.568 3H5.25A2.25 2.25 0 003 5.25v4.318c0 .597.237 1.17.659 1.591l9.581 9.581c.699.699 1.78.872 2.607.33a18.095 18.095 0 005.223-5.223c.542-.827.369-1.908-.33-2.607L11.16 3.66A2.25 2.25 0 009.568 3Z" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M6 6h.008v.008H6V6Z" />
      </svg>
    ),
  },
  sla_warning: {
    label: 'SLA',
    color: 'text-red-400',
    bgColor: 'bg-red-500/10',
    icon: (
      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
      </svg>
    ),
  },
  attachment_added: {
    label: 'Attachment',
    color: 'text-indigo-400',
    bgColor: 'bg-indigo-500/10',
    icon: (
      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="m18.375 12.739-7.693 7.693a4.5 4.5 0 0 1-6.364-6.364l10.94-10.94A3 3 0 1 1 19.5 7.372L8.552 18.32m.009-.01-.01.01m5.699-9.941-7.81 7.81a1.5 1.5 0 0 0 2.112 2.13" />
      </svg>
    ),
  },
  merged: {
    label: 'Merged',
    color: 'text-teal-400',
    bgColor: 'bg-teal-500/10',
    icon: (
      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 21 3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" />
      </svg>
    ),
  },
};

// Filter tabs config
const FILTER_TABS: { key: string; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'ticket_created', label: 'Created' },
  { key: 'status_changed', label: 'Status' },
  { key: 'assigned', label: 'Assigned' },
  { key: 'resolved', label: 'Resolved' },
];

// ── Time Formatting ───────────────────────────────────────────────────

function formatRelativeTime(isoString: string): string {
  if (!isoString) return '';
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSecs = Math.floor(diffMs / 1000);
  const diffMins = Math.floor(diffSecs / 60);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSecs < 60) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

// ── Actor Badge ───────────────────────────────────────────────────────

function ActorBadge({ actorType, actorName }: { actorType?: string; actorName?: string }) {
  if (!actorName && !actorType) return null;

  const typeStyles: Record<string, string> = {
    ai: 'bg-gradient-to-r from-orange-500/20 to-orange-400/10 text-orange-400 border-orange-500/20',
    human: 'bg-sky-500/10 text-sky-400 border-sky-500/20',
    system: 'bg-zinc-500/10 text-zinc-400 border-zinc-500/20',
    customer: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  };

  return (
    <span className={cn(
      'inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium border',
      typeStyles[actorType || 'system']
    )}>
      {actorType === 'ai' && (
        <svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09ZM18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 0 0-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 0 0 2.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 0 0 2.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 0 0-2.456 2.456ZM16.894 20.567 16.5 21.75l-.394-1.183a2.25 2.25 0 0 0-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 0 0 1.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 0 0 1.423 1.423l1.183.394-1.183.394a2.25 2.25 0 0 0-1.423 1.423Z" />
        </svg>
      )}
      {actorName || actorType}
    </span>
  );
}

// ── Single Event Row ──────────────────────────────────────────────────

function EventRow({ event }: { event: ActivityEvent }) {
  const config = EVENT_TYPE_CONFIG[event.event_type] || EVENT_TYPE_CONFIG.ticket_created;

  return (
    <div className="group flex items-start gap-3 px-3 py-2.5 rounded-lg hover:bg-white/[0.03] transition-colors duration-150">
      {/* Event type icon */}
      <div className={cn(
        'w-7 h-7 rounded-md flex items-center justify-center shrink-0 mt-0.5',
        config.bgColor,
        config.color
      )}>
        {config.icon}
      </div>

      {/* Event content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2">
          <p className="text-sm text-zinc-300 leading-snug truncate">
            {event.description}
          </p>
          <time className="text-[11px] text-zinc-600 shrink-0 whitespace-nowrap mt-0.5">
            {formatRelativeTime(event.created_at)}
          </time>
        </div>

        {/* Bottom row: actor + ticket link */}
        <div className="flex items-center gap-2 mt-1">
          <ActorBadge actorType={event.actor_type} actorName={event.actor_name} />
          {event.ticket_id && (
            <a
              href={`/dashboard/tickets/${event.ticket_id}`}
              className="text-[11px] text-zinc-600 hover:text-zinc-400 transition-colors truncate"
              title={`Ticket: ${event.ticket_subject || event.ticket_id}`}
            >
              {event.ticket_subject
                ? (event.ticket_subject.length > 40
                  ? event.ticket_subject.slice(0, 40) + '...'
                  : event.ticket_subject)
                : `#${event.ticket_id.slice(0, 8)}`}
            </a>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Skeleton Loader ───────────────────────────────────────────────────

function FeedSkeleton() {
  return (
    <div className="space-y-1 px-1">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="flex items-start gap-3 px-3 py-2.5 animate-pulse">
          <div className="w-7 h-7 rounded-md bg-white/[0.06]" />
          <div className="flex-1 space-y-2">
            <div className="h-3.5 w-3/4 bg-white/[0.06] rounded" />
            <div className="h-2.5 w-1/3 bg-white/[0.06] rounded" />
          </div>
        </div>
      ))}
    </div>
  );
}

// ── ActivityFeed Component ────────────────────────────────────────────

export default function ActivityFeed({
  initialEvents = [],
  className,
  showFilters = true,
}: ActivityFeedProps) {
  const [events, setEvents] = useState<ActivityEvent[]>(initialEvents);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [activeFilter, setActiveFilter] = useState('all');
  const [total, setTotal] = useState(initialEvents.length);

  // Fetch initial page if no initialEvents provided
  const fetchFeed = useCallback(async (pageNum: number, eventType?: string) => {
    try {
      if (pageNum === 1) setIsLoading(true);
      else setIsLoadingMore(true);

      const result = await dashboardApi.getActivityFeed({
        page: pageNum,
        pageSize: 25,
        eventType: eventType && eventType !== 'all' ? eventType : undefined,
      });

      if (pageNum === 1) {
        setEvents(result.events);
      } else {
        setEvents(prev => [...prev, ...result.events]);
      }
      setHasMore(result.has_more);
      setTotal(result.total);
    } catch (error) {
      console.error('Failed to fetch activity feed:', error);
    } finally {
      setIsLoading(false);
      setIsLoadingMore(false);
    }
  }, []);

  // Initial load — only if no initialEvents
  useEffect(() => {
    if (initialEvents.length === 0) {
      fetchFeed(1);
    } else {
      setHasMore(true); // Assume more events exist
    }
  }, [fetchFeed, initialEvents.length]);

  // Filter change
  const handleFilterChange = useCallback((filterKey: string) => {
    setActiveFilter(filterKey);
    setPage(1);
    fetchFeed(1, filterKey);
  }, [fetchFeed]);

  // Load more
  const handleLoadMore = useCallback(() => {
    const nextPage = page + 1;
    setPage(nextPage);
    fetchFeed(nextPage, activeFilter);
  }, [page, activeFilter, fetchFeed]);

  return (
    <div className={cn(
      'rounded-xl bg-[#1A1A1A] border border-white/[0.06] overflow-hidden',
      className
    )}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.06]">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-md bg-[#FF7F11]/10 flex items-center justify-center">
            <svg className="w-3.5 h-3.5 text-[#FF7F11]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 12h16.5m-16.5 3.75h16.5M3.75 19.5h16.5M5.625 4.5h12.75a1.875 1.875 0 0 1 0 3.75H5.625a1.875 1.875 0 0 1 0-3.75Z" />
            </svg>
          </div>
          <h3 className="text-sm font-semibold text-zinc-300">Activity Feed</h3>
          {total > 0 && (
            <span className="text-[11px] text-zinc-600 bg-white/[0.05] px-1.5 py-0.5 rounded">
              {total}
            </span>
          )}
        </div>

        {showFilters && (
          <div className="flex items-center gap-0.5 bg-white/[0.03] rounded-lg p-0.5" role="tablist" aria-label="Activity filter">
            {FILTER_TABS.map(tab => (
              <button
                key={tab.key}
                role="tab"
                aria-selected={activeFilter === tab.key}
                onClick={() => handleFilterChange(tab.key)}
                className={cn(
                  'px-2 py-1 text-[11px] font-medium rounded-md transition-all duration-150',
                  activeFilter === tab.key
                    ? 'bg-[#FF7F11]/15 text-[#FF7F11]'
                    : 'text-zinc-500 hover:text-zinc-400'
                )}
              >
                {tab.label}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Event List */}
      <div className="divide-y divide-white/[0.03] max-h-[420px] overflow-y-auto scrollbar-thin">
        {isLoading ? (
          <FeedSkeleton />
        ) : events.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <div className="w-10 h-10 rounded-full bg-white/[0.04] flex items-center justify-center mb-3">
              <svg className="w-5 h-5 text-zinc-700" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
              </svg>
            </div>
            <p className="text-sm text-zinc-600">No activity yet</p>
            <p className="text-xs text-zinc-700 mt-0.5">Events will appear here as tickets are created</p>
          </div>
        ) : (
          <>
            {events.map(event => (
              <EventRow key={event.event_id} event={event} />
            ))}

            {/* Load More */}
            {hasMore && (
              <div className="py-2 px-3">
                <button
                  onClick={handleLoadMore}
                  disabled={isLoadingMore}
                  className={cn(
                    'w-full py-2 text-xs font-medium rounded-lg transition-all duration-150',
                    'text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.05]',
                    'disabled:opacity-50 disabled:cursor-not-allowed'
                  )}
                >
                  {isLoadingMore ? (
                    <span className="flex items-center justify-center gap-2">
                      <svg className="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                      </svg>
                      Loading...
                    </span>
                  ) : (
                    `Load more (${total - events.length} remaining)`
                  )}
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
