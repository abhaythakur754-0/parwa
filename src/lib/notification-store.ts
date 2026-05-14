/**
 * PARWA Notification Store
 *
 * Zustand store for real-time notification management.
 * Handles in-app notifications, toast messages, and unread tracking.
 * Backed by server API and Socket.io events — no localStorage.
 */

import { create } from 'zustand';
import { v4 as uuid } from 'uuid';

// ── Types ────────────────────────────────────────────────────────────

export type NotificationType = 'info' | 'success' | 'warning' | 'error' | 'approval' | 'system';
export type NotificationCategory = 'ticket' | 'billing' | 'system' | 'approval' | 'ai' | 'chat';

export interface Notification {
  id: string;
  type: NotificationType;
  category: NotificationCategory;
  title: string;
  message: string;
  timestamp: string;
  read: boolean;
  actionUrl?: string;
  actionLabel?: string;
  metadata?: Record<string, unknown>;
  persistent?: boolean;
  priority: 'low' | 'medium' | 'high' | 'critical';
}

export interface NotificationState {
  notifications: Notification[];
  unreadCount: number;
  isLoading: boolean;
  toasts: Notification[];
  maxToasts: number;

  // Actions
  addNotification: (notif: Omit<Notification, 'id' | 'timestamp' | 'read'>) => void;
  addToast: (notif: Omit<Notification, 'id' | 'timestamp' | 'read'>) => void;
  removeToast: (id: string) => void;
  markAsRead: (id: string) => void;
  markAllAsRead: () => void;
  dismissNotification: (id: string) => void;
  clearAll: () => void;

  // Socket.io event handlers (called by useRealtimeEvents)
  handleNotificationNew: (data: any) => void;
  handleNotificationRead: (data: { id: string }) => void;
  handleNotificationBulk: (data: { notifications: any[] }) => void;

  // Fetch from API (for initial load / reconnection recovery)
  fetchNotifications: () => Promise<void>;

  // Computed
  getUnreadByCategory: (category: NotificationCategory) => number;
  getByCategory: (category: NotificationCategory) => Notification[];
}

// ── Display Helpers ──────────────────────────────────────────────────

export const NOTIFICATION_TYPE_LABELS: Record<NotificationType, string> = {
  info: 'Info',
  success: 'Success',
  warning: 'Warning',
  error: 'Error',
  approval: 'Approval',
  system: 'System',
};

export const NOTIFICATION_CATEGORY_LABELS: Record<NotificationCategory, string> = {
  ticket: 'Tickets',
  billing: 'Billing',
  system: 'System',
  approval: 'Approvals',
  ai: 'AI Agents',
  chat: 'Chat',
};

export const NOTIFICATION_TYPE_COLORS: Record<NotificationType, string> = {
  info: 'from-sky-500 to-sky-400',
  success: 'from-emerald-500 to-emerald-400',
  warning: 'from-amber-500 to-amber-400',
  error: 'from-red-500 to-red-400',
  approval: 'from-violet-500 to-violet-400',
  system: 'from-zinc-500 to-zinc-400',
};

export const PRIORITY_LABELS: Record<Notification['priority'], string> = {
  low: 'Low',
  medium: 'Medium',
  high: 'High',
  critical: 'Critical',
};

// ── Constants ────────────────────────────────────────────────────────

const MAX_NOTIFICATIONS = 100;
const TOAST_DURATION_MS = 5000;
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// ── Store ────────────────────────────────────────────────────────────

export const useNotificationStore = create<NotificationState>((set, get) => ({
  notifications: [],
  unreadCount: 0,
  isLoading: false,
  toasts: [],
  maxToasts: 5,

  addNotification: (notif) => {
    const notification: Notification = {
      ...notif,
      id: uuid(),
      timestamp: new Date().toISOString(),
      read: false,
    };

    set((state) => {
      const notifications = [notification, ...state.notifications].slice(0, MAX_NOTIFICATIONS);
      const unreadCount = notifications.filter((n) => !n.read).length;
      return { notifications, unreadCount };
    });
  },

  addToast: (notif) => {
    const notification: Notification = {
      ...notif,
      id: uuid(),
      timestamp: new Date().toISOString(),
      read: false,
    };

    // Also add to the notifications list
    get().addNotification(notif);

    set((state) => {
      const toasts = [notification, ...state.toasts].slice(0, state.maxToasts);
      return { toasts };
    });

    // Auto-remove toast after duration
    if (typeof window !== 'undefined') {
      const toastId = notification.id;
      setTimeout(() => {
        get().removeToast(toastId);
      }, TOAST_DURATION_MS);
    }
  },

  removeToast: (id) => {
    set((state) => ({
      toasts: state.toasts.filter((t) => t.id !== id),
    }));
  },

  markAsRead: (id) => {
    set((state) => {
      const notifications = state.notifications.map((n) =>
        n.id === id ? { ...n, read: true } : n
      );
      const unreadCount = notifications.filter((n) => !n.read).length;
      return { notifications, unreadCount };
    });
  },

  markAllAsRead: () => {
    set((state) => {
      const notifications = state.notifications.map((n) => ({ ...n, read: true }));
      return { notifications, unreadCount: 0 };
    });
  },

  dismissNotification: (id) => {
    set((state) => {
      const notifications = state.notifications.filter((n) => n.id !== id);
      const unreadCount = notifications.filter((n) => !n.read).length;
      return { notifications, unreadCount };
    });
  },

  clearAll: () => {
    set({ notifications: [], unreadCount: 0, toasts: [] });
  },

  // ── Socket.io Event Handlers ─────────────────────────────────────

  handleNotificationNew: (data: any) => {
    const notif: Omit<Notification, 'id' | 'timestamp' | 'read'> = {
      type: (data.type || 'info') as NotificationType,
      category: (data.category || 'system') as NotificationCategory,
      title: String(data.title || 'New Notification'),
      message: String(data.message || ''),
      actionUrl: data.action_url || data.actionUrl || undefined,
      actionLabel: data.action_label || data.actionLabel || undefined,
      metadata: data.metadata || undefined,
      persistent: Boolean(data.persistent ?? false),
      priority: (data.priority || 'medium') as Notification['priority'],
    };

    // Critical and high priority notifications also show as toasts
    if (notif.priority === 'critical' || notif.priority === 'high' || notif.type === 'approval') {
      get().addToast(notif);
    } else {
      get().addNotification(notif);
    }
  },

  handleNotificationRead: (data: { id: string }) => {
    get().markAsRead(data.id);
  },

  handleNotificationBulk: (data: { notifications: any[] }) => {
    if (!Array.isArray(data.notifications)) return;

    const incoming: Notification[] = data.notifications.map((n: Record<string, unknown>) => ({
      id: String(n.id || uuid()),
      type: (n.type || 'info') as NotificationType,
      category: (n.category || 'system') as NotificationCategory,
      title: String(n.title || 'Notification'),
      message: String(n.message || ''),
      timestamp: String(n.timestamp || n.created_at || new Date().toISOString()),
      read: Boolean(n.read ?? false),
      actionUrl: n.action_url ? String(n.action_url) : n.actionUrl ? String(n.actionUrl) : undefined,
      actionLabel: n.action_label ? String(n.action_label) : n.actionLabel ? String(n.actionLabel) : undefined,
      metadata: (n.metadata || undefined) as Record<string, unknown> | undefined,
      persistent: Boolean(n.persistent ?? false),
      priority: (n.priority || 'medium') as Notification['priority'],
    }));

    set((state) => {
      // Merge: incoming replaces existing by id, then prepend new ones
      const existingMap = new Map(state.notifications.map((n) => [n.id, n]));
      for (const n of incoming) {
        existingMap.set(n.id, n);
      }
      const notifications = Array.from(existingMap.values())
        .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
        .slice(0, MAX_NOTIFICATIONS);
      const unreadCount = notifications.filter((n) => !n.read).length;
      return { notifications, unreadCount };
    });
  },

  // ── API ──────────────────────────────────────────────────────────

  fetchNotifications: async () => {
    set({ isLoading: true });
    try {
      const res = await fetch(`${API_BASE}/api/v1/notifications`, {
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
      });

      if (!res.ok) {
        // If endpoint not available, keep existing state
        if (res.status === 404 || res.status === 502 || res.status === 503) {
          set({ isLoading: false });
          return;
        }
        throw new Error(`Failed to fetch notifications: ${res.status}`);
      }

      const data = await res.json();
      const list = Array.isArray(data) ? data : (data.notifications || []);

      const notifications: Notification[] = list.map((n: Record<string, unknown>) => ({
        id: String(n.id || uuid()),
        type: (n.type || 'info') as NotificationType,
        category: (n.category || 'system') as NotificationCategory,
        title: String(n.title || 'Notification'),
        message: String(n.message || ''),
        timestamp: String(n.timestamp || n.created_at || new Date().toISOString()),
        read: Boolean(n.read ?? false),
        actionUrl: n.action_url ? String(n.action_url) : n.actionUrl ? String(n.actionUrl) : undefined,
        actionLabel: n.action_label ? String(n.action_label) : n.actionLabel ? String(n.actionLabel) : undefined,
        metadata: (n.metadata || undefined) as Record<string, unknown> | undefined,
        persistent: Boolean(n.persistent ?? false),
        priority: (n.priority || 'medium') as Notification['priority'],
      }));

      const unreadCount = notifications.filter((n) => !n.read).length;
      set({ notifications, unreadCount, isLoading: false });
    } catch {
      // On error, keep existing notifications — don't clear
      set({ isLoading: false });
    }
  },

  // ── Computed ─────────────────────────────────────────────────────

  getUnreadByCategory: (category: NotificationCategory) => {
    return get().notifications.filter((n) => !n.read && n.category === category).length;
  },

  getByCategory: (category: NotificationCategory) => {
    return get().notifications.filter((n) => n.category === category);
  },
}));
