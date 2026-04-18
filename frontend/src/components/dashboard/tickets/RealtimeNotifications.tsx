/**
 * PARWA Real-time Notifications Component
 *
 * Live notification dropdown with toast notifications for ticket events.
 * Integrates with useTicketRealtime hook for WebSocket events.
 *
 * Day 7 — Real-time Updates & Dashboard Integration
 */

'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { createPortal } from 'react-dom';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useTicketRealtime, type TicketEvent } from './useTicketRealtime';

// ── Types ────────────────────────────────────────────────────────────────

interface ToastNotification {
  id: string;
  event: TicketEvent;
  dismissed: boolean;
  createdAt: number;
}

interface RealtimeNotificationsProps {
  /** Show toast notifications for new events */
  enableToasts?: boolean;
  /** Duration for toast notifications in ms (default: 5000) */
  toastDuration?: number;
  /** Maximum number of toasts to show at once */
  maxToasts?: number;
  /** Custom class for the notification bell */
  className?: string;
  /** Callback when a notification is clicked */
  onNotificationClick?: (event: TicketEvent) => void;
}

// ── Event Type Config ────────────────────────────────────────────────────

const EVENT_CONFIG: Record<
  string,
  { icon: React.ReactNode; color: string; bgColor: string; label: string }
> = {
  'ticket:new': {
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
      </svg>
    ),
    color: 'text-blue-400',
    bgColor: 'bg-blue-500/15',
    label: 'New Ticket',
  },
  'ticket:status_changed': {
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99" />
      </svg>
    ),
    color: 'text-emerald-400',
    bgColor: 'bg-emerald-500/15',
    label: 'Status Changed',
  },
  'ticket:assigned': {
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.501 20.118a7.5 7.5 0 0 1 14.998 0A17.933 17.933 0 0 1 12 21.75c-2.676 0-5.216-.584-7.499-1.632Z" />
      </svg>
    ),
    color: 'text-orange-400',
    bgColor: 'bg-orange-500/15',
    label: 'Assigned',
  },
  'ticket:resolved': {
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
      </svg>
    ),
    color: 'text-green-400',
    bgColor: 'bg-green-500/15',
    label: 'Resolved',
  },
  'ticket:escalated': {
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 0 1 3 19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V8.625ZM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V4.125Z" />
      </svg>
    ),
    color: 'text-red-400',
    bgColor: 'bg-red-500/15',
    label: 'Escalated',
  },
  'message:new': {
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H8.25m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H12m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 0 1-2.555-.337A5.972 5.972 0 0 1 5.41 20.97a5.969 5.969 0 0 1-.474-.065 4.48 4.48 0 0 0 .978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25Z" />
      </svg>
    ),
    color: 'text-sky-400',
    bgColor: 'bg-sky-500/15',
    label: 'New Message',
  },
  'ticket:reopened': {
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99" />
      </svg>
    ),
    color: 'text-amber-400',
    bgColor: 'bg-amber-500/15',
    label: 'Reopened',
  },
};

const DEFAULT_CONFIG = {
  icon: (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 0 0 5.454-1.31A8.967 8.967 0 0 1 18 9.75V9A6 6 0 0 0 6 9v.75a8.967 8.967 0 0 1-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 0 1-5.714 0m5.714 0a3 3 0 1 1-5.714 0" />
    </svg>
  ),
  color: 'text-zinc-400',
  bgColor: 'bg-zinc-500/15',
  label: 'Notification',
};

// ── Time Formatting ──────────────────────────────────────────────────────

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

// ── Toast Component ──────────────────────────────────────────────────────

interface ToastProps {
  notification: ToastNotification;
  onDismiss: (id: string) => void;
  onClick?: (event: TicketEvent) => void;
}

function Toast({ notification, onDismiss, onClick }: ToastProps) {
  const { event } = notification;
  const config = EVENT_CONFIG[event.event_type] ?? DEFAULT_CONFIG;

  useEffect(() => {
    const timer = setTimeout(() => {
      onDismiss(notification.id);
    }, 5000);

    return () => clearTimeout(timer);
  }, [notification.id, onDismiss]);

  return (
    <div
      onClick={() => onClick?.(event)}
      className={cn(
        'flex items-start gap-3 p-3 rounded-lg',
        'bg-[#1E1E1E] border border-white/[0.08]',
        'shadow-lg shadow-black/30',
        'cursor-pointer transition-all duration-200',
        'hover:border-white/[0.15] hover:bg-[#222]',
        'animate-[slideInRight_0.3s_ease-out]'
      )}
    >
      {/* Icon */}
      <div className={cn('w-8 h-8 rounded-lg flex items-center justify-center shrink-0', config.bgColor)}>
        <span className={config.color}>{config.icon}</span>
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <p className={cn('text-xs font-medium', config.color)}>{config.label}</p>
        <p className="text-sm text-zinc-300 mt-0.5 truncate">
          {event.ticket_subject || `Ticket #${event.ticket_id.slice(0, 8)}`}
        </p>
        {event.actor_name && (
          <p className="text-xs text-zinc-500 mt-0.5">by {event.actor_name}</p>
        )}
      </div>

      {/* Close button */}
      <button
        onClick={(e) => {
          e.stopPropagation();
          onDismiss(notification.id);
        }}
        className="text-zinc-500 hover:text-zinc-300 transition-colors p-1"
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
}

// ── Toast Container ──────────────────────────────────────────────────────

interface ToastContainerProps {
  notifications: ToastNotification[];
  onDismiss: (id: string) => void;
  onClick?: (event: TicketEvent) => void;
}

function ToastContainer({ notifications, onDismiss, onClick }: ToastContainerProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted || notifications.length === 0) return null;

  return createPortal(
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm">
      {notifications.slice(0, 3).map((n) => (
        <Toast key={n.id} notification={n} onDismiss={onDismiss} onClick={onClick} />
      ))}
    </div>,
    document.body
  );
}

// ── Main Component ───────────────────────────────────────────────────────

export default function RealtimeNotifications({
  enableToasts = true,
  toastDuration = 5000,
  maxToasts = 10,
  className,
  onNotificationClick,
}: RealtimeNotificationsProps) {
  const {
    recentEvents,
    newTicketCount,
    newMessageCount,
    escalationCount,
    isConnected,
    acknowledge,
    clearEvents,
  } = useTicketRealtime();

  const [isOpen, setIsOpen] = useState(false);
  const [toasts, setToasts] = useState<ToastNotification[]>([]);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const lastEventIdRef = useRef<string | null>(null);

  // Total unread count
  const totalUnread = newTicketCount + newMessageCount + escalationCount;

  // Create toast for new events
  useEffect(() => {
    if (!enableToasts || recentEvents.length === 0) return;

    const latestEvent = recentEvents[0];
    if (latestEvent.event_id === lastEventIdRef.current) return;

    lastEventIdRef.current = latestEvent.event_id;

    // Only show toasts for certain event types
    const toastableEvents = ['ticket:new', 'ticket:escalated', 'message:new', 'ticket:resolved'];
    if (!toastableEvents.includes(latestEvent.event_type)) return;

    const newToast: ToastNotification = {
      id: `${latestEvent.event_id}-${Date.now()}`,
      event: latestEvent,
      dismissed: false,
      createdAt: Date.now(),
    };

    setToasts((prev) => [newToast, ...prev].slice(0, maxToasts));
  }, [recentEvents, enableToasts, maxToasts]);

  // Dismiss toast handler
  const handleDismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  // Click outside to close
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  // Handle notification click
  const handleNotificationClick = useCallback(
    (event: TicketEvent) => {
      onNotificationClick?.(event);
      setIsOpen(false);
    },
    [onNotificationClick]
  );

  // Handle dropdown open
  const handleOpen = useCallback(() => {
    setIsOpen(!isOpen);
    if (!isOpen) {
      // Mark as read when opening
      acknowledge('all');
    }
  }, [isOpen, acknowledge]);

  return (
    <>
      {/* Notification Bell */}
      <div ref={dropdownRef} className={cn('relative', className)}>
        <Button
          variant="ghost"
          size="icon"
          onClick={handleOpen}
          className="relative text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.05]"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M14.857 17.082a23.848 23.848 0 0 0 5.454-1.31A8.967 8.967 0 0 1 18 9.75V9A6 6 0 0 0 6 9v.75a8.967 8.967 0 0 1-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 0 1-5.714 0m5.714 0a3 3 0 1 1-5.714 0"
            />
          </svg>

          {/* Connection indicator */}
          {!isConnected && (
            <span className="absolute -bottom-0.5 -right-0.5 w-2 h-2 rounded-full bg-amber-500 border border-[#0A0A0A]" />
          )}

          {/* Unread badge */}
          {totalUnread > 0 && (
            <span className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] px-1 rounded-full bg-blue-500 border border-[#0A0A0A] flex items-center justify-center">
              <span className="text-[10px] font-semibold text-white">
                {totalUnread > 99 ? '99+' : totalUnread}
              </span>
            </span>
          )}
        </Button>

        {/* Dropdown Panel */}
        {isOpen && (
          <div className="absolute right-0 top-full mt-2 w-80 bg-[#1A1A1A] border border-white/[0.08] rounded-xl shadow-xl shadow-black/30 z-50">
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.06]">
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-semibold text-zinc-200">Notifications</h3>
                {isConnected && (
                  <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-emerald-500/10">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                    <span className="text-[10px] font-medium text-emerald-400">Live</span>
                  </span>
                )}
              </div>
              {recentEvents.length > 0 && (
                <button
                  onClick={() => {
                    clearEvents();
                  }}
                  className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
                >
                  Clear all
                </button>
              )}
            </div>

            {/* Event List */}
            {recentEvents.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-8 px-4">
                <div className="w-12 h-12 rounded-xl bg-white/[0.03] border border-white/[0.06] flex items-center justify-center mb-3">
                  <svg className="w-6 h-6 text-zinc-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M14.857 17.082a23.848 23.848 0 0 0 5.454-1.31A8.967 8.967 0 0 1 18 9.75V9A6 6 0 0 0 6 9v.75a8.967 8.967 0 0 1-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 0 1-5.714 0m5.714 0a3 3 0 1 1-5.714 0"
                    />
                  </svg>
                </div>
                <p className="text-sm text-zinc-500 font-medium">No notifications yet</p>
                <p className="text-xs text-zinc-600 mt-1 text-center">
                  Real-time ticket events will appear here
                </p>
              </div>
            ) : (
              <ScrollArea className="max-h-[400px]">
                <div className="divide-y divide-white/[0.04]">
                  {recentEvents.map((event) => {
                    const config = EVENT_CONFIG[event.event_type] ?? DEFAULT_CONFIG;
                    return (
                      <button
                        key={event.event_id}
                        onClick={() => handleNotificationClick(event)}
                        className="w-full flex items-start gap-3 p-3 text-left hover:bg-white/[0.02] transition-colors"
                      >
                        <div className={cn('w-8 h-8 rounded-lg flex items-center justify-center shrink-0', config.bgColor)}>
                          <span className={config.color}>{config.icon}</span>
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className={cn('text-xs font-medium', config.color)}>{config.label}</p>
                          <p className="text-sm text-zinc-300 mt-0.5 truncate">
                            {event.ticket_subject || `Ticket #${event.ticket_id.slice(0, 8)}`}
                          </p>
                          <div className="flex items-center gap-2 mt-1">
                            {event.actor_name && (
                              <span className="text-xs text-zinc-500">{event.actor_name}</span>
                            )}
                            <span className="text-xs text-zinc-600">{formatTimeAgo(event.timestamp)}</span>
                          </div>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </ScrollArea>
            )}
          </div>
        )}
      </div>

      {/* Toast Notifications */}
      {enableToasts && (
        <ToastContainer
          notifications={toasts}
          onDismiss={handleDismissToast}
          onClick={onNotificationClick}
        />
      )}

      {/* CSS Animation */}
      <style jsx global>{`
        @keyframes slideInRight {
          from {
            opacity: 0;
            transform: translateX(100%);
          }
          to {
            opacity: 1;
            transform: translateX(0);
          }
        }
      `}</style>
    </>
  );
}
