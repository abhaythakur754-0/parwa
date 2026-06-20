/**
 * PARWA NotificationBell
 *
 * Bell icon in the dashboard header showing unread notification count.
 * Opens a dropdown with recent notifications on click.
 * Real-time — count updates instantly via Socket.io.
 */

'use client';

import React, { useState, useRef, useEffect } from 'react';
import Link from 'next/link';
import { useNotificationStore, Notification, NotificationType, NotificationCategory } from '@/lib/notification-store';
import { NOTIFICATION_TYPE_COLORS } from '@/lib/notification-store';

// ── Icons (inline SVG to avoid extra deps) ────────────────────────────

const BellIcon = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 0 0 5.454-1.31A8.967 8.967 0 0 1 18 9.75V9A6 6 0 0 0 6 9v.75a8.967 8.967 0 0 1-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 0 1-5.714 0m5.714 0a3 3 0 1 1-5.714 0" />
  </svg>
);

const CheckIcon = () => (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
  </svg>
);

const XIcon = () => (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
  </svg>
);

// ── Type Color Dot ────────────────────────────────────────────────────

function TypeDot({ type }: { type: NotificationType }) {
  const colorMap: Record<NotificationType, string> = {
    info: 'bg-sky-400',
    success: 'bg-emerald-400',
    warning: 'bg-amber-400',
    error: 'bg-red-400',
    approval: 'bg-violet-400',
    system: 'bg-zinc-400',
  };

  return <span className={`w-2 h-2 rounded-full shrink-0 ${colorMap[type] || 'bg-zinc-400'}`} />;
}

// ── Time Ago Helper ───────────────────────────────────────────────────

function timeAgo(timestamp: string): string {
  const now = Date.now();
  const then = new Date(timestamp).getTime();
  const diffMs = now - then;

  if (diffMs < 60000) return 'just now';
  if (diffMs < 3600000) return `${Math.floor(diffMs / 60000)}m ago`;
  if (diffMs < 86400000) return `${Math.floor(diffMs / 3600000)}h ago`;
  return `${Math.floor(diffMs / 86400000)}d ago`;
}

// ── NotificationBell Component ────────────────────────────────────────

export function NotificationBell() {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const notifications = useNotificationStore((s) => s.notifications);
  const unreadCount = useNotificationStore((s) => s.unreadCount);
  const markAsRead = useNotificationStore((s) => s.markAsRead);
  const markAllAsRead = useNotificationStore((s) => s.markAllAsRead);
  const dismissNotification = useNotificationStore((s) => s.dismissNotification);
  const fetchNotifications = useNotificationStore((s) => s.fetchNotifications);

  // Fetch notifications on mount
  useEffect(() => {
    fetchNotifications();
  }, [fetchNotifications]);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Show max 10 in dropdown
  const visibleNotifications = notifications.slice(0, 10);

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Bell Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="relative w-9 h-9 rounded-lg flex items-center justify-center text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.05] transition-colors"
        aria-label={`Notifications${unreadCount > 0 ? ` (${unreadCount} unread)` : ''}`}
      >
        <BellIcon />

        {/* Unread Badge */}
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] rounded-full bg-orange-500 text-white text-[10px] font-bold flex items-center justify-center px-1 shadow-lg shadow-orange-500/30">
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {/* Dropdown */}
      {isOpen && (
        <div className="absolute right-0 top-full mt-2 w-[380px] max-h-[500px] bg-[#1A1A1A] border border-white/[0.08] rounded-xl shadow-2xl shadow-black/40 overflow-hidden z-50">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.06]">
            <h3 className="text-sm font-semibold text-white">Notifications</h3>
            <div className="flex items-center gap-2">
              {unreadCount > 0 && (
                <button
                  onClick={markAllAsRead}
                  className="text-[11px] text-orange-400 hover:text-orange-300 transition-colors flex items-center gap-1"
                >
                  <CheckIcon />
                  Mark all read
                </button>
              )}
            </div>
          </div>

          {/* Notification List */}
          <div className="overflow-y-auto max-h-[400px] scrollbar-premium">
            {visibleNotifications.length === 0 ? (
              <div className="py-12 text-center">
                <p className="text-sm text-zinc-500">No notifications yet</p>
                <p className="text-xs text-zinc-600 mt-1">Real-time alerts will appear here</p>
              </div>
            ) : (
              visibleNotifications.map((notif) => (
                <NotificationItem
                  key={notif.id}
                  notification={notif}
                  onMarkRead={markAsRead}
                  onDismiss={dismissNotification}
                  onClose={() => setIsOpen(false)}
                />
              ))
            )}
          </div>

          {/* Footer */}
          {notifications.length > 10 && (
            <Link
              href="/dashboard/monitoring"
              className="block text-center text-xs text-orange-400 hover:text-orange-300 py-2.5 border-t border-white/[0.06] transition-colors"
              onClick={() => setIsOpen(false)}
            >
              View all notifications
            </Link>
          )}
        </div>
      )}
    </div>
  );
}

// ── NotificationItem ──────────────────────────────────────────────────

function NotificationItem({
  notification,
  onMarkRead,
  onDismiss,
  onClose,
}: {
  notification: Notification;
  onMarkRead: (id: string) => void;
  onDismiss: (id: string) => void;
  onClose: () => void;
}) {
  const isUnread = !notification.read;

  const handleClick = () => {
    if (isUnread) {
      onMarkRead(notification.id);
    }
    if (notification.actionUrl) {
      onClose();
    }
  };

  return (
    <div
      className={`px-4 py-3 border-b border-white/[0.04] hover:bg-white/[0.02] transition-colors cursor-pointer ${
        isUnread ? 'bg-orange-500/[0.03]' : ''
      }`}
      onClick={handleClick}
    >
      <div className="flex items-start gap-3">
        {/* Type dot */}
        <div className="pt-1.5">
          <TypeDot type={notification.type} />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <p className={`text-sm truncate ${isUnread ? 'font-medium text-white' : 'text-zinc-300'}`}>
              {notification.title}
            </p>
            {isUnread && (
              <span className="w-1.5 h-1.5 rounded-full bg-orange-400 shrink-0" />
            )}
          </div>
          <p className="text-xs text-zinc-500 mt-0.5 line-clamp-2">{notification.message}</p>
          <div className="flex items-center gap-2 mt-1.5">
            <span className="text-[10px] text-zinc-600">{timeAgo(notification.timestamp)}</span>
            {notification.actionLabel && notification.actionUrl && (
              <Link
                href={notification.actionUrl}
                className="text-[10px] text-orange-400 hover:text-orange-300 transition-colors"
                onClick={onClose}
              >
                {notification.actionLabel}
              </Link>
            )}
          </div>
        </div>

        {/* Dismiss button */}
        <button
          onClick={(e) => {
            e.stopPropagation();
            onDismiss(notification.id);
          }}
          className="p-1 rounded text-zinc-600 hover:text-zinc-300 hover:bg-white/[0.05] transition-colors shrink-0"
          title="Dismiss"
        >
          <XIcon />
        </button>
      </div>
    </div>
  );
}

export default NotificationBell;
