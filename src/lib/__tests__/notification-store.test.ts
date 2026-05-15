/**
 * PARWA Notification Store — Unit Tests (Day 4)
 *
 * Tests all actions, computed values, Socket.io event handlers,
 * and API integration for the notification Zustand store.
 */

import { useNotificationStore } from '@/lib/notification-store';

// ── Setup ─────────────────────────────────────────────────────────────

beforeEach(() => {
  useNotificationStore.getState().clearAll();
});

// ── addNotification ───────────────────────────────────────────────────

describe('notification-store: addNotification', () => {
  it('should add a notification with generated id, timestamp, and read=false', () => {
    const store = useNotificationStore.getState();
    store.addNotification({
      type: 'info',
      category: 'system',
      title: 'Test Notification',
      message: 'This is a test',
      priority: 'medium',
    });

    const notifications = useNotificationStore.getState().notifications;
    expect(notifications.length).toBe(1);
    expect(notifications[0].title).toBe('Test Notification');
    expect(notifications[0].read).toBe(false);
    expect(notifications[0].id).toBeDefined();
    expect(notifications[0].timestamp).toBeDefined();
  });

  it('should increment unreadCount when adding unread notification', () => {
    const store = useNotificationStore.getState();
    expect(store.unreadCount).toBe(0);

    store.addNotification({
      type: 'info',
      category: 'system',
      title: 'Test',
      message: 'msg',
      priority: 'low',
    });

    expect(useNotificationStore.getState().unreadCount).toBe(1);
  });

  it('should cap notifications at 100 (FIFO)', () => {
    const store = useNotificationStore.getState();

    for (let i = 0; i < 110; i++) {
      store.addNotification({
        type: 'info',
        category: 'system',
        title: `Notif ${i}`,
        message: `Message ${i}`,
        priority: 'low',
      });
    }

    const notifications = useNotificationStore.getState().notifications;
    expect(notifications.length).toBe(100);
    // Most recent should be first
    expect(notifications[0].title).toBe('Notif 109');
  });

  it('should preserve metadata, actionUrl, and actionLabel', () => {
    const store = useNotificationStore.getState();
    store.addNotification({
      type: 'approval',
      category: 'approval',
      title: 'Approval needed',
      message: 'Refund request',
      priority: 'high',
      actionUrl: '/dashboard/monitoring',
      actionLabel: 'Review',
      metadata: { ticketId: 'tkt-123' },
      persistent: true,
    });

    const notif = useNotificationStore.getState().notifications[0];
    expect(notif.actionUrl).toBe('/dashboard/monitoring');
    expect(notif.actionLabel).toBe('Review');
    expect(notif.metadata?.ticketId).toBe('tkt-123');
    expect(notif.persistent).toBe(true);
  });
});

// ── markAsRead ────────────────────────────────────────────────────────

describe('notification-store: markAsRead', () => {
  it('should mark a notification as read', () => {
    const store = useNotificationStore.getState();
    store.addNotification({
      type: 'info',
      category: 'system',
      title: 'Test',
      message: 'msg',
      priority: 'medium',
    });

    const notifId = useNotificationStore.getState().notifications[0].id;
    expect(useNotificationStore.getState().unreadCount).toBe(1);

    store.markAsRead(notifId);

    const notif = useNotificationStore.getState().notifications.find((n) => n.id === notifId);
    expect(notif?.read).toBe(true);
    expect(useNotificationStore.getState().unreadCount).toBe(0);
  });

  it('should not affect other notifications', () => {
    const store = useNotificationStore.getState();
    store.addNotification({ type: 'info', category: 'system', title: 'A', message: 'a', priority: 'low' });
    store.addNotification({ type: 'info', category: 'system', title: 'B', message: 'b', priority: 'low' });

    const idA = useNotificationStore.getState().notifications.find((n) => n.title === 'A')!.id;
    store.markAsRead(idA);

    expect(useNotificationStore.getState().unreadCount).toBe(1);
  });
});

// ── markAllAsRead ─────────────────────────────────────────────────────

describe('notification-store: markAllAsRead', () => {
  it('should mark all notifications as read and set unreadCount to 0', () => {
    const store = useNotificationStore.getState();
    store.addNotification({ type: 'info', category: 'system', title: 'A', message: 'a', priority: 'low' });
    store.addNotification({ type: 'info', category: 'system', title: 'B', message: 'b', priority: 'low' });
    store.addNotification({ type: 'info', category: 'system', title: 'C', message: 'c', priority: 'low' });

    expect(useNotificationStore.getState().unreadCount).toBe(3);

    store.markAllAsRead();

    expect(useNotificationStore.getState().unreadCount).toBe(0);
    expect(useNotificationStore.getState().notifications.every((n) => n.read)).toBe(true);
  });
});

// ── dismissNotification ───────────────────────────────────────────────

describe('notification-store: dismissNotification', () => {
  it('should remove a notification by id', () => {
    const store = useNotificationStore.getState();
    store.addNotification({ type: 'info', category: 'system', title: 'A', message: 'a', priority: 'low' });
    store.addNotification({ type: 'info', category: 'system', title: 'B', message: 'b', priority: 'low' });

    const idA = useNotificationStore.getState().notifications.find((n) => n.title === 'A')!.id;
    store.dismissNotification(idA);

    expect(useNotificationStore.getState().notifications.length).toBe(1);
    expect(useNotificationStore.getState().notifications[0].title).toBe('B');
  });

  it('should update unreadCount after dismissal', () => {
    const store = useNotificationStore.getState();
    store.addNotification({ type: 'info', category: 'system', title: 'A', message: 'a', priority: 'low' });

    const idA = useNotificationStore.getState().notifications[0].id;
    store.dismissNotification(idA);

    expect(useNotificationStore.getState().unreadCount).toBe(0);
  });
});

// ── clearAll ──────────────────────────────────────────────────────────

describe('notification-store: clearAll', () => {
  it('should clear all notifications, toasts, and reset unreadCount', () => {
    const store = useNotificationStore.getState();
    store.addNotification({ type: 'info', category: 'system', title: 'A', message: 'a', priority: 'low' });
    store.addToast({ type: 'warning', category: 'system', title: 'Toast', message: 't', priority: 'high' });

    store.clearAll();

    expect(useNotificationStore.getState().notifications.length).toBe(0);
    expect(useNotificationStore.getState().toasts.length).toBe(0);
    expect(useNotificationStore.getState().unreadCount).toBe(0);
  });
});

// ── handleNotificationNew (Socket.io handler) ─────────────────────────

describe('notification-store: handleNotificationNew', () => {
  it('should add notification from socket event data', () => {
    const store = useNotificationStore.getState();
    store.handleNotificationNew({
      type: 'warning',
      category: 'billing',
      title: 'Usage Alert',
      message: 'You are at 90% of your limit',
      priority: 'high',
    });

    const notifs = useNotificationStore.getState().notifications;
    expect(notifs.length).toBeGreaterThanOrEqual(1);
    const found = notifs.find((n) => n.title === 'Usage Alert');
    expect(found).toBeDefined();
    expect(found?.type).toBe('warning');
    expect(found?.category).toBe('billing');
    expect(found?.priority).toBe('high');
  });

  it('should auto-toast critical, high, and approval notifications', () => {
    const store = useNotificationStore.getState();

    store.handleNotificationNew({
      type: 'error',
      category: 'system',
      title: 'Critical Alert',
      message: 'System down',
      priority: 'critical',
    });

    const toasts = useNotificationStore.getState().toasts;
    expect(toasts.length).toBeGreaterThanOrEqual(1);
  });
});

// ── handleNotificationRead (Socket.io handler) ────────────────────────

describe('notification-store: handleNotificationRead', () => {
  it('should mark notification as read via socket event', () => {
    const store = useNotificationStore.getState();
    store.addNotification({ type: 'info', category: 'system', title: 'Test', message: 'msg', priority: 'low' });

    const notifId = useNotificationStore.getState().notifications[0].id;
    store.handleNotificationRead({ id: notifId });

    const notif = useNotificationStore.getState().notifications.find((n) => n.id === notifId);
    expect(notif?.read).toBe(true);
  });
});

// ── handleNotificationBulk (Socket.io handler) ────────────────────────

describe('notification-store: handleNotificationBulk', () => {
  it('should merge bulk notifications by id', () => {
    const store = useNotificationStore.getState();
    store.handleNotificationBulk({
      notifications: [
        { id: 'n1', type: 'info', category: 'system', title: 'Notif 1', message: 'm1', priority: 'low', read: false },
        { id: 'n2', type: 'success', category: 'ticket', title: 'Notif 2', message: 'm2', priority: 'medium', read: true },
      ],
    });

    const notifs = useNotificationStore.getState().notifications;
    expect(notifs.length).toBe(2);
    expect(notifs.find((n) => n.title === 'Notif 1')).toBeDefined();
    expect(notifs.find((n) => n.title === 'Notif 2')).toBeDefined();
  });
});

// ── Computed: getUnreadByCategory ─────────────────────────────────────

describe('notification-store: getUnreadByCategory', () => {
  it('should count unread notifications by category', () => {
    const store = useNotificationStore.getState();
    store.addNotification({ type: 'info', category: 'system', title: 'A', message: 'a', priority: 'low' });
    store.addNotification({ type: 'info', category: 'system', title: 'B', message: 'b', priority: 'low' });
    store.addNotification({ type: 'info', category: 'billing', title: 'C', message: 'c', priority: 'low' });

    expect(store.getUnreadByCategory('system')).toBe(2);
    expect(store.getUnreadByCategory('billing')).toBe(1);
    expect(store.getUnreadByCategory('ticket')).toBe(0);
  });
});

// ── Computed: getByCategory ───────────────────────────────────────────

describe('notification-store: getByCategory', () => {
  it('should filter notifications by category', () => {
    const store = useNotificationStore.getState();
    store.addNotification({ type: 'info', category: 'system', title: 'A', message: 'a', priority: 'low' });
    store.addNotification({ type: 'info', category: 'billing', title: 'B', message: 'b', priority: 'low' });

    const systemNotifs = store.getByCategory('system');
    expect(systemNotifs.length).toBe(1);
    expect(systemNotifs[0].title).toBe('A');
  });
});

// ── addToast ──────────────────────────────────────────────────────────

describe('notification-store: addToast', () => {
  it('should add to both toasts array and notifications list', () => {
    const store = useNotificationStore.getState();
    store.addToast({
      type: 'warning',
      category: 'system',
      title: 'Toast Test',
      message: 'Toast message',
      priority: 'high',
    });

    expect(useNotificationStore.getState().toasts.length).toBe(1);
    expect(useNotificationStore.getState().notifications.length).toBe(1);
  });

  it('should cap toasts at maxToasts', () => {
    const store = useNotificationStore.getState();

    for (let i = 0; i < 8; i++) {
      store.addToast({
        type: 'info',
        category: 'system',
        title: `Toast ${i}`,
        message: `msg ${i}`,
        priority: 'medium',
      });
    }

    expect(useNotificationStore.getState().toasts.length).toBeLessThanOrEqual(store.maxToasts);
  });
});

// ── removeToast ───────────────────────────────────────────────────────

describe('notification-store: removeToast', () => {
  it('should remove a toast by id without removing the notification', () => {
    const store = useNotificationStore.getState();
    store.addToast({
      type: 'info',
      category: 'system',
      title: 'Toast',
      message: 'msg',
      priority: 'medium',
    });

    const toastId = useNotificationStore.getState().toasts[0].id;
    store.removeToast(toastId);

    expect(useNotificationStore.getState().toasts.length).toBe(0);
    // Notification should still exist
    expect(useNotificationStore.getState().notifications.length).toBe(1);
  });
});

// ── fetchNotifications (API) ──────────────────────────────────────────

describe('notification-store: fetchNotifications', () => {
  it('should handle 404 gracefully without clearing notifications', async () => {
    const store = useNotificationStore.getState();
    store.addNotification({ type: 'info', category: 'system', title: 'Existing', message: 'msg', priority: 'low' });

    (global.fetch as jest.Mock).mockResolvedValueOnce({ ok: false, status: 404 });

    await store.fetchNotifications();

    // Should keep existing notifications
    expect(useNotificationStore.getState().notifications.length).toBe(1);
    expect(useNotificationStore.getState().isLoading).toBe(false);
  });

  it('should parse API response and set notifications', async () => {
    const mockData = {
      notifications: [
        { id: 'api-1', type: 'info', category: 'system', title: 'API Notif', message: 'from api', priority: 'low', read: false },
      ],
    };

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockData),
    });

    await useNotificationStore.getState().fetchNotifications();

    const notifs = useNotificationStore.getState().notifications;
    expect(notifs.find((n) => n.id === 'api-1')).toBeDefined();
  });
});
