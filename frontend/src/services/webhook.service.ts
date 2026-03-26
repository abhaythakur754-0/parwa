/**
 * PARWA Webhook Service
 * Handles webhook management API operations.
 */

import { apiClient } from "./api/client";

export interface Webhook {
  id: string;
  name: string;
  url: string;
  events: string[];
  secret: string;
  active: boolean;
  lastTriggered?: string;
  failureCount: number;
  createdAt: string;
}

export interface WebhookDelivery {
  id: string;
  webhookId: string;
  event: string;
  payload: Record<string, unknown>;
  responseStatus: number;
  duration: number;
  success: boolean;
  timestamp: string;
}

export const webhookService = {
  async getWebhooks() {
    const res = await apiClient.get<Webhook[]>("/webhooks");
    return res.data;
  },

  async createWebhook(data: { name: string; url: string; events: string[]; active?: boolean }) {
    const res = await apiClient.post<Webhook>("/webhooks", data);
    return res.data;
  },

  async updateWebhook(id: string, data: Partial<Webhook>) {
    const res = await apiClient.patch<Webhook>(`/webhooks/${id}`, data);
    return res.data;
  },

  async deleteWebhook(id: string) {
    await apiClient.delete(`/webhooks/${id}`);
  },

  async testWebhook(id: string) {
    const res = await apiClient.post<{ success: boolean; responseStatus: number; duration: number }>(`/webhooks/${id}/test`);
    return res.data;
  },

  async getDeliveries(webhookId: string, limit = 20) {
    const res = await apiClient.get<WebhookDelivery[]>(`/webhooks/${webhookId}/deliveries`, { limit: String(limit) });
    return res.data;
  },

  async regenerateSecret(id: string) {
    const res = await apiClient.post<{ secret: string }>(`/webhooks/${id}/regenerate-secret`);
    return res.data;
  },
};

export default webhookService;
