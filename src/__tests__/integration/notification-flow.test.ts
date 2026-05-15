/**
 * PARWA Integration Tests — Notification Flow (Day 4)
 *
 * End-to-end integration tests verifying:
 * 1. Socket event → notification store → toast → unread count flow
 * 2. Notification lifecycle: new → read → dismissed
 * 3. Bulk notification handling
 * 4. Cross-store interaction (notification + approval)
 */

import { useNotificationStore } from '@/lib/notification-store';
import { useApprovalStore } from '@/lib/approval-store';

// ── Setup ─────────────────────────────────────────────────────────────

beforeEach(() => {
  useNotificationStore.getState().clearAll();
  useApprovalStore.setState({
    approvals: [],
    pendingCount: 0,
    isLoading: false,
    activeApprovalId: null,
  });
});

// ── Integration: Socket Event → Store → Toast ─────────────────────────

describe('Integration: notification flow from socket events', () => {
  it('should process notification:new event end-to-end', () => {
    const store = useNotificationStore.getState();

    // Simulate incoming socket event
    store.handleNotificationNew({
      type: 'warning',
      category: 'billing',
      title: 'Usage Alert: 90% API calls used',
      message: 'You have used 4,500 out of 5,000 API calls this month',
      priority: 'high',
      action_url: '/dashboard/billing',
      action_label: 'View Usage',
    });

    const state = useNotificationStore.getState();

    // Notification should be added
    expect(state.notifications.length).toBeGreaterThanOrEqual(1);
    const notif = state.notifications.find((n) => n.title === 'Usage Alert: 90% API calls used');
    expect(notif).toBeDefined();
    expect(notif?.read).toBe(false);
    expect(notif?.category).toBe('billing');

    // High-priority should auto-toast
    expect(state.toasts.length).toBeGreaterThanOrEqual(1);

    // Unread count should be incremented
    expect(state.unreadCount).toBeGreaterThanOrEqual(1);
  });

  it('should handle critical notification with toast + notification', () => {
    const store = useNotificationStore.getState();

    store.handleNotificationNew({
      type: 'error',
      category: 'system',
      title: 'Service Down: Email Service',
      message: 'The email service is currently unreachable',
      priority: 'critical',
    });

    const state = useNotificationStore.getState();

    // Both toast and notification should exist
    expect(state.notifications.length).toBeGreaterThanOrEqual(1);
    expect(state.toasts.length).toBeGreaterThanOrEqual(1);

    // Toast should be error type
    const toastNotif = state.toasts.find((t) => t.title === 'Service Down: Email Service');
    expect(toastNotif?.type).toBe('error');
  });

  it('should not auto-toast low/medium priority notifications', () => {
    const store = useNotificationStore.getState();

    store.handleNotificationNew({
      type: 'info',
      category: 'ticket',
      title: 'Ticket assigned to you',
      message: 'TKT-0042 has been assigned to you',
      priority: 'low',
    });

    const state = useNotificationStore.getState();

    // Notification should exist but no toast
    expect(state.notifications.length).toBeGreaterThanOrEqual(1);
    // Only high/critical/approval auto-toast
    expect(state.toasts.length).toBe(0);
  });
});

// ── Integration: Notification Lifecycle ────────────────────────────────

describe('Integration: notification lifecycle', () => {
  it('should handle new → read → dismissed lifecycle', () => {
    const store = useNotificationStore.getState();

    // 1. New notification arrives
    store.handleNotificationNew({
      type: 'success',
      category: 'ticket',
      title: 'Ticket Resolved',
      message: 'TKT-0010 has been resolved',
      priority: 'high',
    });

    const notifId = useNotificationStore.getState().notifications[0].id;
    expect(useNotificationStore.getState().unreadCount).toBeGreaterThanOrEqual(1);

    // 2. Mark as read (simulating user click)
    store.markAsRead(notifId);
    expect(useNotificationStore.getState().unreadCount).toBe(0);
    const notif = useNotificationStore.getState().notifications.find((n) => n.id === notifId);
    expect(notif?.read).toBe(true);

    // 3. Dismiss notification
    store.dismissNotification(notifId);
    expect(useNotificationStore.getState().notifications.find((n) => n.id === notifId)).toBeUndefined();
  });

  it('should handle markAllAsRead for multiple notifications', () => {
    const store = useNotificationStore.getState();

    // Add 5 notifications
    for (let i = 0; i < 5; i++) {
      store.addNotification({
        type: 'info',
        category: 'system',
        title: `Notif ${i}`,
        message: `Message ${i}`,
        priority: 'low',
      });
    }

    expect(useNotificationStore.getState().unreadCount).toBe(5);

    store.markAllAsRead();

    expect(useNotificationStore.getState().unreadCount).toBe(0);
    expect(useNotificationStore.getState().notifications.every((n) => n.read)).toBe(true);
  });
});

// ── Integration: Bulk Notifications ───────────────────────────────────

describe('Integration: bulk notification handling', () => {
  it('should handle notification:bulk socket event', () => {
    const store = useNotificationStore.getState();

    store.handleNotificationBulk({
      notifications: [
        { id: 'bulk-1', type: 'info', category: 'ticket', title: 'New Ticket', message: 'm1', priority: 'low', read: false },
        { id: 'bulk-2', type: 'warning', category: 'billing', title: 'Usage Alert', message: 'm2', priority: 'medium', read: false },
        { id: 'bulk-3', type: 'error', category: 'system', title: 'System Error', message: 'm3', priority: 'critical', read: true },
      ],
    });

    const state = useNotificationStore.getState();
    expect(state.notifications.length).toBe(3);
    // Only unread ones count
    expect(state.unreadCount).toBe(2);
  });

  it('should merge bulk notifications with existing by id', () => {
    const store = useNotificationStore.getState();

    // Add initial notification
    store.addNotification({
      type: 'info',
      category: 'system',
      title: 'Original Title',
      message: 'Original message',
      priority: 'low',
    });

    const existingId = useNotificationStore.getState().notifications[0].id;

    // Bulk update should merge by id
    store.handleNotificationBulk({
      notifications: [
        { id: existingId, type: 'warning', category: 'system', title: 'Updated Title', message: 'Updated', priority: 'medium', read: false },
      ],
    });

    const notif = useNotificationStore.getState().notifications.find((n) => n.id === existingId);
    expect(notif?.title).toBe('Updated Title');
  });
});

// ── Integration: Cross-Store (Notification + Approval) ────────────────

describe('Integration: notification + approval cross-store flow', () => {
  it('should create notification when approval arrives', () => {
    // Simulate what useRealtimeEvents does for approval:pending
    const approvalStore = useApprovalStore.getState();
    const notifStore = useNotificationStore.getState();

    // Add pending approval
    approvalStore.handleApprovalPending({
      id: 'apr-1',
      type: 'refund',
      title: 'Refund Request: $149.99',
      description: 'Customer requests refund',
      reason: 'Duplicate charge',
      risk_level: 'medium',
      ai_confidence: 88,
      expires_at: new Date(Date.now() + 3600000).toISOString(),
      requested_by: 'Refund Agent',
    });

    // Also push notification (as useRealtimeEvents does)
    notifStore.addToast({
      type: 'approval',
      category: 'approval',
      title: 'New Approval Request',
      message: 'Refund Request: $149.99',
      priority: 'high',
      actionUrl: '/dashboard/monitoring',
      actionLabel: 'Review',
    });

    // Both stores should reflect the approval
    expect(useApprovalStore.getState().pendingCount).toBe(1);
    expect(useNotificationStore.getState().unreadCount).toBeGreaterThanOrEqual(1);
    expect(useNotificationStore.getState().toasts.length).toBeGreaterThanOrEqual(1);

    // When approval is approved, notification should still exist
    useApprovalStore.getState().handleApprovalApproved({ id: 'apr-1', respondedBy: 'Admin' });
    expect(useApprovalStore.getState().pendingCount).toBe(0);

    // Approval notification should still be in notification list
    const approvalNotif = useNotificationStore.getState().notifications.find((n) => n.category === 'approval');
    expect(approvalNotif).toBeDefined();
  });
});

// ── Integration: Category Filtering ───────────────────────────────────

describe('Integration: category-based filtering', () => {
  it('should filter notifications by category correctly', () => {
    const store = useNotificationStore.getState();

    store.handleNotificationNew({ type: 'info', category: 'ticket', title: 'T1', message: 'm', priority: 'low' });
    store.handleNotificationNew({ type: 'info', category: 'billing', title: 'B1', message: 'm', priority: 'medium' });
    store.handleNotificationNew({ type: 'info', category: 'ticket', title: 'T2', message: 'm', priority: 'low' });
    store.handleNotificationNew({ type: 'warning', category: 'system', title: 'S1', message: 'm', priority: 'high' });

    expect(store.getUnreadByCategory('ticket')).toBe(2);
    expect(store.getUnreadByCategory('billing')).toBe(1);
    expect(store.getUnreadByCategory('system')).toBe(1);
    expect(store.getUnreadByCategory('approval')).toBe(0);

    const ticketNotifs = store.getByCategory('ticket');
    expect(ticketNotifs.length).toBe(2);
  });
});
