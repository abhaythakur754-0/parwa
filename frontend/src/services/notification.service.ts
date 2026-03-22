/**
 * PARWA Notification Service
 * Handles notifications API operations.
 */

import { apiClient } from "./api/client";

export interface Notification {
  id: string;
  type: "ticket_created" | "ticket_updated" | "approval_pending" | "escalation" | "system" | "alert";
  title: string;
  message: string;
  priority: "low" | "medium" | "high" | "critical";
  read: boolean;
  actionUrl?: string;
  metadata?: Record<string, unknown>;
  createdAt: string;
  readAt?: string;
}

export const notificationService = {
  async getNotifications(page = 1, pageSize = 20) {
    const res = await apiClient.get<{ notifications: Notification[]; total: number; unreadCount: number }>(
      "/notifications",
      { page: String(page), pageSize: String(pageSize) }
    );
    return res.data;
  },

  async markAsRead(id: string) {
    await apiClient.post(`/notifications/${id}/read`);
  },

  async markAllAsRead() {
    await apiClient.post("/notifications/read-all");
  },

  async getUnreadCount() {
    const res = await apiClient.get<{ count: number }>("/notifications/unread-count");
    return res.data.count;
  },

  async deleteNotification(id: string) {
    await apiClient.delete(`/notifications/${id}`);
  },

  async updatePreferences(preferences: Record<string, boolean>) {
    const res = await apiClient.patch<Record<string, boolean>>("/notifications/preferences", preferences);
    return res.data;
  },
};

export default notificationService;
