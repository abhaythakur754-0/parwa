/**
 * NotificationList — Displays a filtered list of notifications.
 *
 * Used by the Notifications page to show notifications grouped by tab.
 * Follows the PARWA dark dashboard style.
 */

'use client';

import React from 'react';
import { cn } from '@/lib/utils';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';

// ── Types ────────────────────────────────────────────────────────────

export type NotificationTabType =
  | 'all'
  | 'escalation'
  | 'self_improvement'
  | 'subgraph_performance'
  | 'technique_alert';

export interface NotificationItem {
  id: string;
  type: NotificationTabType;
  title: string;
  message: string;
  timestamp: string;
  read: boolean;
  priority: 'low' | 'medium' | 'high' | 'critical';
  subgraph?: string;
  technique?: string;
  metadata?: Record<string, unknown>;
}

// ── Helpers ──────────────────────────────────────────────────────────

function timeAgo(timestamp: string): string {
  const now = Date.now();
  const then = new Date(timestamp).getTime();
  const diffMs = now - then;

  if (diffMs < 60000) return 'just now';
  if (diffMs < 3600000) return `${Math.floor(diffMs / 60000)}m ago`;
  if (diffMs < 86400000) return `${Math.floor(diffMs / 3600000)}h ago`;
  return `${Math.floor(diffMs / 86400000)}d ago`;
}

const PRIORITY_STYLES: Record<NotificationItem['priority'], string> = {
  low: 'bg-zinc-500/20 text-zinc-400 border-zinc-500/20',
  medium: 'bg-amber-500/15 text-amber-400 border-amber-500/20',
  high: 'bg-orange-500/15 text-orange-400 border-orange-500/20',
  critical: 'bg-red-500/15 text-red-400 border-red-500/20',
};

const TYPE_DOT_COLORS: Record<NotificationTabType, string> = {
  all: 'bg-zinc-400',
  escalation: 'bg-amber-400',
  self_improvement: 'bg-emerald-400',
  subgraph_performance: 'bg-sky-400',
  technique_alert: 'bg-purple-400',
};

const TYPE_LABELS: Record<NotificationTabType, string> = {
  all: 'All',
  escalation: 'Escalation',
  self_improvement: 'Self-Improvement',
  subgraph_performance: 'Subgraph',
  technique_alert: 'Technique',
};

// ── NotificationRow ──────────────────────────────────────────────────

function NotificationRow({
  item,
  onMarkRead,
}: {
  item: NotificationItem;
  onMarkRead: (id: string) => void;
}) {
  return (
    <div
      className={cn(
        'px-4 py-3 border-b border-white/[0.04] hover:bg-white/[0.02] transition-colors cursor-pointer',
        !item.read && 'bg-orange-500/[0.03]'
      )}
      onClick={() => {
        if (!item.read) onMarkRead(item.id);
      }}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' && !item.read) onMarkRead(item.id);
      }}
    >
      <div className="flex items-start gap-3">
        {/* Type dot */}
        <div className="pt-1.5">
          <span
            className={cn(
              'w-2 h-2 rounded-full shrink-0 block',
              TYPE_DOT_COLORS[item.type] || 'bg-zinc-400'
            )}
          />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <p
              className={cn(
                'text-sm truncate',
                !item.read ? 'font-medium text-white' : 'text-zinc-300'
              )}
            >
              {item.title}
            </p>
            {!item.read && (
              <span className="w-1.5 h-1.5 rounded-full bg-orange-400 shrink-0" />
            )}
            <Badge
              variant="outline"
              className={cn(
                'text-[9px] px-1.5 py-0 border font-medium',
                PRIORITY_STYLES[item.priority]
              )}
            >
              {item.priority}
            </Badge>
          </div>
          <p className="text-xs text-zinc-500 mt-0.5 line-clamp-2">
            {item.message}
          </p>
          <div className="flex items-center gap-2 mt-1.5 flex-wrap">
            <span className="text-[10px] text-zinc-600">
              {timeAgo(item.timestamp)}
            </span>
            {item.subgraph && (
              <Badge
                variant="outline"
                className="text-[9px] px-1.5 py-0 border border-white/[0.08] text-zinc-500"
              >
                {item.subgraph}
              </Badge>
            )}
            {item.technique && (
              <Badge
                variant="outline"
                className="text-[9px] px-1.5 py-0 border border-white/[0.08] text-zinc-500"
              >
                {item.technique}
              </Badge>
            )}
          </div>
        </div>

        {/* Type badge */}
        <Badge
          variant="outline"
          className="text-[9px] px-1.5 py-0 border border-white/[0.08] text-zinc-500 shrink-0 hidden sm:inline-flex"
        >
          {TYPE_LABELS[item.type]}
        </Badge>
      </div>
    </div>
  );
}

// ── NotificationList Component ───────────────────────────────────────

interface NotificationListProps {
  notifications: NotificationItem[];
  activeTab: NotificationTabType;
  onMarkRead: (id: string) => void;
  onMarkAllRead: () => void;
}

export function NotificationList({
  notifications,
  activeTab,
  onMarkRead,
  onMarkAllRead,
}: NotificationListProps) {
  const filtered =
    activeTab === 'all'
      ? notifications
      : notifications.filter((n) => n.type === activeTab);

  const unreadCount = filtered.filter((n) => !n.read).length;

  return (
    <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.06]">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-white">
            Notifications
          </h3>
          {unreadCount > 0 && (
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-orange-500/15 text-orange-400 font-medium">
              {unreadCount} unread
            </span>
          )}
        </div>
        {unreadCount > 0 && (
          <button
            onClick={onMarkAllRead}
            className="text-[11px] text-orange-400 hover:text-orange-300 transition-colors flex items-center gap-1"
          >
            <svg
              className="w-3 h-3"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="m4.5 12.75 6 6 9-13.5"
              />
            </svg>
            Mark all read
          </button>
        )}
      </div>

      {/* List */}
      <ScrollArea className="max-h-[500px]">
        {filtered.length === 0 ? (
          <div className="py-16 text-center">
            <div className="w-12 h-12 rounded-xl bg-zinc-800 flex items-center justify-center mx-auto mb-3">
              <svg
                className="w-6 h-6 text-zinc-600"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={1.5}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M14.857 17.082a23.848 23.848 0 0 0 5.454-1.31A8.967 8.967 0 0 1 18 9.75V9A6 6 0 0 0 6 9v.75a8.967 8.967 0 0 1-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 0 1-5.714 0m5.714 0a3 3 0 1 1-5.714 0"
                />
              </svg>
            </div>
            <p className="text-sm text-zinc-500">
              No{' '}
              {activeTab === 'all'
                ? ''
                : TYPE_LABELS[activeTab].toLowerCase() + ' '}
              notifications
            </p>
            <p className="text-xs text-zinc-600 mt-1">
              New alerts will appear here as they arrive
            </p>
          </div>
        ) : (
          <div>
            {filtered.map((item) => (
              <NotificationRow
                key={item.id}
                item={item}
                onMarkRead={onMarkRead}
              />
            ))}
          </div>
        )}
      </ScrollArea>
    </div>
  );
}

export default NotificationList;
