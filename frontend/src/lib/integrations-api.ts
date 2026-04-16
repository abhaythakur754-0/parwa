/**
 * PARWA Integrations API Client
 *
 * API client for third-party app integrations and custom webhooks.
 * Handles pre-built integrations (Shopify, Slack, Zendesk, etc.),
 * custom webhook integrations, and webhook delivery management.
 */

import { get, post, put, del } from '@/lib/api';

// ── Integration Types ──────────────────────────────────────────────────

export interface Integration {
  id: string;
  company_id: string;
  integration_type: string;
  name: string;
  status: string;
  config: Record<string, any>;
  last_sync_at: string | null;
  error_count: number;
  created_at: string;
  updated_at: string;
}

export interface AvailableIntegration {
  type: string;
  name: string;
  description: string;
  icon: string;
  auth_type: 'oauth' | 'api_key' | 'webhook';
  category: string;
}

export interface CreateIntegrationRequest {
  integration_type: string;
  name?: string;
  credentials?: Record<string, any>;
  config?: Record<string, any>;
}

export interface TestCredentialsRequest {
  integration_type: string;
  credentials: Record<string, any>;
}

export interface TestResult {
  success: boolean;
  message: string;
  latency_ms?: number;
}

export interface CustomIntegration {
  id: string;
  company_id: string;
  name: string;
  integration_type: string;
  status: 'draft' | 'active' | 'disabled';
  config: Record<string, any>;
  endpoint_url?: string;
  secret?: string;
  last_test_at: string | null;
  last_delivery_at: string | null;
  error_count: number;
  created_at: string;
  updated_at: string;
}

export interface DeliveryLog {
  id: string;
  custom_integration_id: string;
  url: string;
  method: string;
  status_code: number | null;
  response_body: string | null;
  error_message: string | null;
  latency_ms: number | null;
  created_at: string;
}

export interface WebhookDelivery {
  event_db_id: string;
  provider: string;
  event_type: string;
  status: string;
  created_at: string;
  processed_at: string | null;
  retry_count: number;
}

// ── Integrations API ───────────────────────────────────────────────────

export const integrationsApi = {
  // ── Available Integrations ─────────────────────────────────────────
  getAvailable: () =>
    get<AvailableIntegration[]>('/api/integrations/available'),

  // ── Credentials ───────────────────────────────────────────────────
  testCredentials: (data: TestCredentialsRequest) =>
    post<TestResult>('/api/integrations/test-credentials', data),

  // ── Integration CRUD ──────────────────────────────────────────────
  create: (data: CreateIntegrationRequest) =>
    post<Integration>('/api/integrations', data),

  list: () =>
    get<Integration[]>('/api/integrations'),

  test: (id: string) =>
    post<TestResult>(`/api/integrations/${id}/test`),

  remove: (id: string) =>
    del(`/api/integrations/${id}`),

  // ── Custom Integrations ───────────────────────────────────────────
  listCustom: () =>
    get<CustomIntegration[]>('/api/integrations/custom'),

  getCustom: (id: string) =>
    get<CustomIntegration>(`/api/integrations/custom/${id}`),

  createCustom: (data: Record<string, any>) =>
    post<CustomIntegration>('/api/integrations/custom', data),

  updateCustom: (id: string, data: Record<string, any>) =>
    put<CustomIntegration>(`/api/integrations/custom/${id}`, data),

  removeCustom: (id: string) =>
    del(`/api/integrations/custom/${id}`),

  testCustom: (id: string) =>
    post<TestResult>(`/api/integrations/custom/${id}/test`),

  activateCustom: (id: string) =>
    post(`/api/integrations/custom/${id}/activate`),

  getDeliveryLogs: (id: string) =>
    get<DeliveryLog[]>(`/api/integrations/custom/${id}/deliveries`),

  // ── Webhooks ──────────────────────────────────────────────────────
  getWebhookStatus: (id: string) =>
    get(`/api/webhooks/status/${id}`),

  retryWebhook: (id: string) =>
    post(`/api/webhooks/retry/${id}`),
};

export default integrationsApi;
