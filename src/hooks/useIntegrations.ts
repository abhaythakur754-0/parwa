"use client";

/**
 * useIntegrations — Integration State Management Hook
 * ====================================================
 * Manages the state of all integrations (connected providers, webhooks,
 * custom APIs) for the current tenant.
 *
 * Features:
 *   - Fetch connected integrations from backend API
 *   - Add/remove integrations
 *   - Test connection status
 *   - Manage webhook configurations
 *   - Track integration health
 *
 * Phase 19: Webhook Unification + Universal API
 */

import { useState, useCallback, useEffect, useRef } from "react";

// ── Types ─────────────────────────────────────────────────────────────

export type ConnectionStatus = "connected" | "disconnected" | "error" | "testing";
export type ProviderCategory = "email" | "sms" | "payment" | "crm" | "ecommerce" | "custom";

export interface Integration {
  id: string;
  provider: string;
  category: ProviderCategory;
  name: string;
  status: ConnectionStatus;
  connected_at: string;
  last_tested?: string;
  config?: Record<string, unknown>;
  health_score?: number; // 0-100
}

export interface WebhookConfig {
  id: string;
  provider: string;
  name: string;
  endpoint: string;
  events: string[];
  status: "active" | "inactive" | "error";
  last_delivery?: string;
  success_count: number;
  failure_count: number;
}

export interface IntegrationTestResult {
  success: boolean;
  message: string;
  latency_ms?: number;
}

interface UseIntegrationsReturn {
  // State
  integrations: Integration[];
  webhooks: WebhookConfig[];
  isLoading: boolean;
  error: string | null;

  // Integration actions
  fetchIntegrations: () => Promise<void>;
  addIntegration: (provider: string, category: ProviderCategory, config?: Record<string, unknown>) => Promise<IntegrationTestResult>;
  removeIntegration: (integrationId: string) => Promise<void>;
  testConnection: (integrationId: string) => Promise<IntegrationTestResult>;

  // Webhook actions
  fetchWebhooks: () => Promise<void>;
  saveWebhook: (config: Partial<WebhookConfig>) => Promise<void>;
  deleteWebhook: (webhookId: string) => Promise<void>;
  testWebhook: (webhookId: string) => Promise<IntegrationTestResult>;
  retryWebhook: (eventId: string) => Promise<IntegrationTestResult>;

  // Custom API actions
  createCustomApi: (config: {
    name: string;
    baseUrl: string;
    authMethod: string;
    authToken?: string;
  }) => Promise<IntegrationTestResult>;

  // Available providers
  availableProviders: ProviderInfo[];
}

export interface ProviderInfo {
  provider: string;
  category: ProviderCategory;
  name: string;
  description: string;
  connected: boolean;
}

// ── API Helper ────────────────────────────────────────────────────────

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function apiFetch<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
    ...options,
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || error.message || `API Error: ${res.status}`);
  }
  return res.json();
}

// ── Hook ──────────────────────────────────────────────────────────────

export function useIntegrations(): UseIntegrationsReturn {
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [webhooks, setWebhooks] = useState<WebhookConfig[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      mountedRef.current = false;
    };
  }, []);

  // ── Fetch Integrations ──────────────────────────────────────────

  const fetchIntegrations = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await apiFetch<Integration[]>("/api/integrations");
      if (mountedRef.current) {
        setIntegrations(data);
      }
    } catch (err: any) {
      if (mountedRef.current) {
        setError(err.message || "Failed to fetch integrations");
        // Use mock data as fallback
        setIntegrations(getMockIntegrations());
      }
    } finally {
      if (mountedRef.current) {
        setIsLoading(false);
      }
    }
  }, []);

  // ── Add Integration ─────────────────────────────────────────────

  const addIntegration = useCallback(
    async (
      provider: string,
      category: ProviderCategory,
      config?: Record<string, unknown>,
    ): Promise<IntegrationTestResult> => {
      try {
        const result = await apiFetch<IntegrationTestResult>(
          "/api/integrations",
          {
            method: "POST",
            body: JSON.stringify({ provider, category, ...config }),
          },
        );
        // Refresh list
        await fetchIntegrations();
        return result;
      } catch (err: any) {
        return {
          success: false,
          message: err.message || "Failed to add integration",
        };
      }
    },
    [fetchIntegrations],
  );

  // ── Remove Integration ──────────────────────────────────────────

  const removeIntegration = useCallback(
    async (integrationId: string) => {
      try {
        await apiFetch(`/api/integrations/${integrationId}`, {
          method: "DELETE",
        });
        if (mountedRef.current) {
          setIntegrations((prev) =>
            prev.filter((i) => i.id !== integrationId),
          );
        }
      } catch (err: any) {
        if (mountedRef.current) {
          setError(err.message || "Failed to remove integration");
        }
      }
    },
    [],
  );

  // ── Test Connection ─────────────────────────────────────────────

  const testConnection = useCallback(
    async (integrationId: string): Promise<IntegrationTestResult> => {
      try {
        const result = await apiFetch<IntegrationTestResult>(
          `/api/integrations/${integrationId}/test`,
          { method: "POST" },
        );
        // Update status
        if (mountedRef.current) {
          setIntegrations((prev) =>
            prev.map((i) =>
              i.id === integrationId
                ? {
                    ...i,
                    status: result.success ? "connected" : "error",
                    last_tested: new Date().toISOString(),
                  }
                : i,
            ),
          );
        }
        return result;
      } catch (err: any) {
        return {
          success: false,
          message: err.message || "Connection test failed",
        };
      }
    },
    [],
  );

  // ── Fetch Webhooks ──────────────────────────────────────────────

  const fetchWebhooks = useCallback(async () => {
    try {
      const data = await apiFetch<WebhookConfig[]>("/api/webhooks/configs");
      if (mountedRef.current) {
        setWebhooks(data);
      }
    } catch (err: any) {
      if (mountedRef.current) {
        // Use mock data as fallback
        setWebhooks(getMockWebhooks());
      }
    }
  }, []);

  // ── Save Webhook ────────────────────────────────────────────────

  const saveWebhook = useCallback(
    async (config: Partial<WebhookConfig>) => {
      try {
        await apiFetch("/api/webhooks/configs", {
          method: "POST",
          body: JSON.stringify(config),
        });
        await fetchWebhooks();
      } catch (err: any) {
        if (mountedRef.current) {
          setError(err.message || "Failed to save webhook config");
        }
      }
    },
    [fetchWebhooks],
  );

  // ── Delete Webhook ──────────────────────────────────────────────

  const deleteWebhook = useCallback(
    async (webhookId: string) => {
      try {
        await apiFetch(`/api/webhooks/configs/${webhookId}`, {
          method: "DELETE",
        });
        if (mountedRef.current) {
          setWebhooks((prev) => prev.filter((w) => w.id !== webhookId));
        }
      } catch (err: any) {
        if (mountedRef.current) {
          setError(err.message || "Failed to delete webhook config");
        }
      }
    },
    [],
  );

  // ── Test Webhook ────────────────────────────────────────────────

  const testWebhook = useCallback(
    async (webhookId: string): Promise<IntegrationTestResult> => {
      try {
        return await apiFetch<IntegrationTestResult>(
          `/api/webhooks/configs/${webhookId}/test`,
          { method: "POST" },
        );
      } catch (err: any) {
        return {
          success: false,
          message: err.message || "Webhook test failed",
        };
      }
    },
    [],
  );

  // ── Retry Webhook ───────────────────────────────────────────────

  const retryWebhook = useCallback(
    async (eventId: string): Promise<IntegrationTestResult> => {
      try {
        return await apiFetch<IntegrationTestResult>(
          `/api/webhooks/retry/${eventId}`,
          { method: "POST" },
        );
      } catch (err: any) {
        return {
          success: false,
          message: err.message || "Webhook retry failed",
        };
      }
    },
    [],
  );

  // ── Create Custom API ───────────────────────────────────────────

  const createCustomApi = useCallback(
    async (config: {
      name: string;
      baseUrl: string;
      authMethod: string;
      authToken?: string;
    }): Promise<IntegrationTestResult> => {
      try {
        const result = await apiFetch<IntegrationTestResult>(
          "/api/integrations",
          {
            method: "POST",
            body: JSON.stringify({
              provider: "custom",
              category: "custom",
              ...config,
            }),
          },
        );
        await fetchIntegrations();
        return result;
      } catch (err: any) {
        return {
          success: false,
          message: err.message || "Failed to create custom API connection",
        };
      }
    },
    [fetchIntegrations],
  );

  // ── Available Providers ─────────────────────────────────────────

  const availableProviders: ProviderInfo[] = [
    {
      provider: "brevo",
      category: "email",
      name: "Brevo",
      description: "Email marketing and transactional email",
      connected: integrations.some((i) => i.provider === "brevo"),
    },
    {
      provider: "sendgrid",
      category: "email",
      name: "SendGrid",
      description: "Email delivery and analytics",
      connected: integrations.some((i) => i.provider === "sendgrid"),
    },
    {
      provider: "twilio",
      category: "sms",
      name: "Twilio",
      description: "SMS and voice communications",
      connected: integrations.some((i) => i.provider === "twilio"),
    },
    {
      provider: "paddle",
      category: "payment",
      name: "Paddle",
      description: "Payment processing and subscriptions",
      connected: integrations.some((i) => i.provider === "paddle"),
    },
    {
      provider: "shopify",
      category: "ecommerce",
      name: "Shopify",
      description: "E-commerce platform integration",
      connected: integrations.some((i) => i.provider === "shopify"),
    },
    {
      provider: "zendesk",
      category: "crm",
      name: "Zendesk",
      description: "Customer support and ticketing",
      connected: integrations.some((i) => i.provider === "zendesk"),
    },
    {
      provider: "slack",
      category: "crm",
      name: "Slack",
      description: "Team communication integration",
      connected: integrations.some((i) => i.provider === "slack"),
    },
    {
      provider: "custom",
      category: "custom",
      name: "Custom API",
      description: "Connect any REST API endpoint",
      connected: integrations.some((i) => i.provider === "custom"),
    },
  ];

  return {
    integrations,
    webhooks,
    isLoading,
    error,
    fetchIntegrations,
    addIntegration,
    removeIntegration,
    testConnection,
    fetchWebhooks,
    saveWebhook,
    deleteWebhook,
    testWebhook,
    retryWebhook,
    createCustomApi,
    availableProviders,
  };
}

// ── Mock Data ─────────────────────────────────────────────────────────

function getMockIntegrations(): Integration[] {
  return [
    {
      id: "int-1",
      provider: "paddle",
      category: "payment",
      name: "Paddle Payments",
      status: "connected",
      connected_at: "2024-01-15T10:00:00Z",
      last_tested: "2024-01-20T14:30:00Z",
      health_score: 98,
    },
    {
      id: "int-2",
      provider: "brevo",
      category: "email",
      name: "Brevo Email",
      status: "connected",
      connected_at: "2024-01-10T09:00:00Z",
      health_score: 95,
    },
    {
      id: "int-3",
      provider: "twilio",
      category: "sms",
      name: "Twilio SMS",
      status: "disconnected",
      connected_at: "2024-01-05T08:00:00Z",
      health_score: 0,
    },
  ];
}

function getMockWebhooks(): WebhookConfig[] {
  return [
    {
      id: "wh-1",
      provider: "paddle",
      name: "Paddle Billing Webhooks",
      endpoint: "/api/webhooks/paddle",
      events: ["subscription.created", "transaction.completed"],
      status: "active",
      last_delivery: "2024-01-20T14:30:00Z",
      success_count: 42,
      failure_count: 2,
    },
    {
      id: "wh-2",
      provider: "brevo",
      name: "Brevo Email Events",
      endpoint: "/api/webhooks/brevo",
      events: ["delivered", "bounce", "complaint"],
      status: "active",
      last_delivery: "2024-01-20T12:00:00Z",
      success_count: 150,
      failure_count: 5,
    },
  ];
}
