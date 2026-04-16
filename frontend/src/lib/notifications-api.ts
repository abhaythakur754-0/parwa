/**
 * PARWA Notifications API Client
 *
 * Dedicated API client for all notification-related endpoints.
 * Full TypeScript types matching the backend schema.
 *
 * NOTE: Notification endpoints use /notifications prefix (NOT /api/notifications).
 */

import { get, post, put, del } from '@/lib/api';

// ── Notification Types ─────────────────────────────────────────────────

export type NotificationType =
  | 'ticket'
  | 'approval'
  | 'system'
  | 'billing'
  | 'training'
  | 'agent'
  | 'escalation';

export type NotificationPriority = 'low' | 'medium' | 'high' | 'urgent';

export interface Notification {
  id: string;
  user_id: string;
  type: NotificationType;
  priority: NotificationPriority;
  title: string;
  message: string;
  link: string | null;
  is_read: boolean;
  action_data: Record<string, any> | null;
  created_at: string;
  read_at: string | null;
}

export interface NotificationListResponse {
  notifications: Notification[];
  total: number;
  unread_count: number;
  page: number;
  page_size: number;
}

export interface NotificationPreferences {
  email_enabled: boolean;
  push_enabled: boolean;
  in_app_enabled: boolean;
  digest_frequency: 'never' | 'daily' | 'weekly';
  quiet_hours_enabled: boolean;
  quiet_hours_start: string | null;
  quiet_hours_end: string | null;
  type_preferences: Record<string, { email: boolean; push: boolean; in_app: boolean }>;
}

export interface NotificationTemplate {
  id: string;
  name: string;
  event_type: string;
  subject_template: string;
  body_template: string;
  channel: string;
  is_active: boolean;
  created_at: string;
}

// ── Request Parameter Types ────────────────────────────────────────────

export interface NotificationListParams {
  page?: number;
  pageSize?: number;
  type?: string;
  unreadOnly?: boolean;
}

export interface MarkReadRequest {
  notification_ids?: string[];
  mark_all?: boolean;
}

export interface DigestSettings {
  frequency: string;
  time?: string;
}

// ── Notifications API ──────────────────────────────────────────────────

export const notificationsApi = {
  /** List notifications with optional filters */
  list: (params?: NotificationListParams) => {
    const sp = new URLSearchParams();
    if (params) {
      if (params.page) sp.set('page', String(params.page));
      if (params.pageSize) sp.set('page_size', String(params.pageSize));
      if (params.type && params.type !== 'all') sp.set('type', params.type);
      if (params.unreadOnly) sp.set('unread_only', 'true');
    }
    const qs = sp.toString();
    return get<NotificationListResponse>(`/notifications${qs ? `?${qs}` : ''}`);
  },

  /** Get unread notification count */
  getUnreadCount: () =>
    get<{ count: number }>('/notifications/unread-count'),

  /** Mark notifications as read (single, multiple, or all) */
  markRead: (data: MarkReadRequest) =>
    post<{ marked_count: number }>('/notifications/mark-read', data),

  /** Get user notification preferences */
  getPreferences: () =>
    get<NotificationPreferences>('/notifications/preferences'),

  /** Bulk update notification preferences */
  updatePreferences: (data: Partial<NotificationPreferences>) =>
    put<NotificationPreferences>('/notifications/preferences', data),

  /** Set digest frequency settings */
  setDigest: (data: DigestSettings) =>
    put<NotificationPreferences>('/notifications/preferences/digest', data),

  /** Disable all notification preferences */
  disableAll: () =>
    post<NotificationPreferences>('/notifications/preferences/disable-all'),

  /** Enable all notification preferences */
  enableAll: () =>
    post<NotificationPreferences>('/notifications/preferences/enable-all'),

  // ── Templates ──────────────────────────────────────────────────────

  /** List all notification templates */
  listTemplates: () =>
    get<NotificationTemplate[]>('/notifications/templates'),

  /** Get a single notification template */
  getTemplate: (id: string) =>
    get<NotificationTemplate>(`/notifications/templates/${id}`),

  /** Create a new notification template */
  createTemplate: (data: Partial<NotificationTemplate>) =>
    post<NotificationTemplate>('/notifications/templates', data),

  /** Update an existing notification template */
  updateTemplate: (id: string, data: Partial<NotificationTemplate>) =>
    put<NotificationTemplate>(`/notifications/templates/${id}`, data),

  /** Delete a notification template */
  deleteTemplate: (id: string) =>
    del<void>(`/notifications/templates/${id}`),

  // ── Send (admin/utility) ──────────────────────────────────────────

  /** Send a notification (admin action) */
  send: (data: {
    user_id: string;
    title: string;
    message: string;
    type: NotificationType;
    link?: string;
  }) =>
    post<Notification>('/notifications/send', data),
};

export default notificationsApi;
