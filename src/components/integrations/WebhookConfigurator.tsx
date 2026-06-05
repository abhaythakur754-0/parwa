"use client";

/**
 * WebhookConfigurator — Webhook Setup & Management UI
 * ====================================================
 * Allows users to configure webhook endpoints for any provider:
 *   - Set up webhook receiver URLs
 *   - Configure signature verification secrets
 *   - Map incoming webhook events to actions
 *   - View recent webhook activity/logs
 *   - Test webhook delivery
 *   - Retry failed webhooks
 *
 * Phase 19: Webhook Unification + Universal API
 */

import React, { useState, useCallback, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";

// ── Types ─────────────────────────────────────────────────────────────

type WebhookStatus = "active" | "inactive" | "error";

interface WebhookConfig {
  id?: string;
  name: string;
  provider: string;
  endpoint: string;
  secret: string;
  events: string[];
  status: WebhookStatus;
  retryEnabled: boolean;
  maxRetries: number;
  lastDelivery?: string;
  successCount: number;
  failureCount: number;
}

interface WebhookLog {
  id: string;
  event_type: string;
  provider: string;
  status: "success" | "failed" | "pending" | "retrying";
  timestamp: string;
  payload_preview: string;
  error_message?: string;
}

interface WebhookConfiguratorProps {
  configs?: WebhookConfig[];
  logs?: WebhookLog[];
  onSave?: (config: WebhookConfig) => void;
  onTest?: (configId: string) => Promise<{ success: boolean; message: string }>;
  onRetry?: (eventId: string) => Promise<{ success: boolean; message: string }>;
  onDelete?: (configId: string) => void;
}

const SUPPORTED_PROVIDERS = [
  { value: "paddle", label: "Paddle", category: "Payment" },
  { value: "stripe", label: "Stripe", category: "Payment" },
  { value: "shopify", label: "Shopify", category: "E-Commerce" },
  { value: "twilio", label: "Twilio", category: "SMS/Voice" },
  { value: "brevo", label: "Brevo", category: "Email" },
  { value: "custom", label: "Custom Provider", category: "Custom" },
];

const PROVIDER_EVENTS: Record<string, string[]> = {
  paddle: [
    "subscription.created",
    "subscription.updated",
    "subscription.canceled",
    "transaction.completed",
    "transaction.payment_failed",
  ],
  shopify: [
    "orders/create",
    "orders/updated",
    "orders/cancelled",
    "products/create",
    "products/update",
  ],
  twilio: [
    "sms.incoming",
    "sms.delivered",
    "sms.undelivered",
    "call.incoming",
    "call.completed",
  ],
  brevo: [
    "delivered",
    "opened",
    "clicked",
    "bounce",
    "complaint",
  ],
  stripe: [
    "payment_intent.succeeded",
    "payment_intent.failed",
    "invoice.paid",
    "invoice.payment_failed",
    "customer.subscription.updated",
  ],
  custom: ["custom.event"],
};

// ── Component ─────────────────────────────────────────────────────────

export default function WebhookConfigurator({
  configs = [],
  logs = [],
  onSave,
  onTest,
  onRetry,
  onDelete,
}: WebhookConfiguratorProps) {
  const [activeTab, setActiveTab] = useState<"configure" | "logs">("configure");
  const [showNewForm, setShowNewForm] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState("");
  const [testing, setTesting] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<{ configId: string; success: boolean; message: string } | null>(null);

  const [newConfig, setNewConfig] = useState<Partial<WebhookConfig>>({
    name: "",
    provider: "",
    secret: "",
    events: [],
    retryEnabled: true,
    maxRetries: 5,
  });

  const handleSave = useCallback(() => {
    if (!onSave || !newConfig.name || !newConfig.provider) return;
    onSave({
      name: newConfig.name || "",
      provider: newConfig.provider || "custom",
      endpoint: `/api/webhooks/${newConfig.provider || "custom"}`,
      secret: newConfig.secret || "",
      events: newConfig.events || [],
      status: "active",
      retryEnabled: newConfig.retryEnabled ?? true,
      maxRetries: newConfig.maxRetries ?? 5,
      successCount: 0,
      failureCount: 0,
    });
    setShowNewForm(false);
    setNewConfig({
      name: "",
      provider: "",
      secret: "",
      events: [],
      retryEnabled: true,
      maxRetries: 5,
    });
  }, [newConfig, onSave]);

  const handleTest = useCallback(
    async (configId: string) => {
      if (!onTest) return;
      setTesting(configId);
      setTestResult(null);
      try {
        const result = await onTest(configId);
        setTestResult({ configId, ...result });
      } catch (err: any) {
        setTestResult({ configId, success: false, message: err.message });
      } finally {
        setTesting(null);
      }
    },
    [onTest]
  );

  const handleEventToggle = useCallback((event: string) => {
    setNewConfig((prev) => {
      const events = prev.events || [];
      return {
        ...prev,
        events: events.includes(event)
          ? events.filter((e) => e !== event)
          : [...events, event],
      };
    });
  }, []);

  const getStatusColor = (status: WebhookStatus) => {
    switch (status) {
      case "active":
        return "bg-green-500";
      case "inactive":
        return "bg-gray-400";
      case "error":
        return "bg-red-500";
    }
  };

  const getLogStatusBadge = (status: WebhookLog["status"]) => {
    const variants: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
      success: "default",
      failed: "destructive",
      pending: "secondary",
      retrying: "outline",
    };
    return <Badge variant={variants[status] || "outline"}>{status}</Badge>;
  };

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <svg className="w-5 h-5 text-purple-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.111 16.404a5.5 5.5 0 017.778 0M12 20h.01m-7.08-7.071c3.904-3.905 10.236-3.905 14.141 0M1.394 9.393c5.857-5.858 15.355-5.858 21.213 0" />
          </svg>
          Webhook Configurator
        </CardTitle>
        <CardDescription>
          Configure webhook receivers for any provider. Set up signature
          verification, event subscriptions, and retry policies.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {/* ── Tab Navigation ─────────────────────────────────────── */}
        <div className="flex gap-2 mb-6" role="tablist">
          <Button
            variant={activeTab === "configure" ? "default" : "outline"}
            size="sm"
            onClick={() => setActiveTab("configure")}
            role="tab"
            aria-selected={activeTab === "configure"}
          >
            Configure ({configs.length})
          </Button>
          <Button
            variant={activeTab === "logs" ? "default" : "outline"}
            size="sm"
            onClick={() => setActiveTab("logs")}
            role="tab"
            aria-selected={activeTab === "logs"}
          >
            Activity Logs ({logs.length})
          </Button>
        </div>

        {/* ── Configure Tab ──────────────────────────────────────── */}
        {activeTab === "configure" && (
          <div className="space-y-4">
            {/* Existing webhook configs */}
            {configs.map((cfg) => (
              <div
                key={cfg.id || cfg.name}
                className="border rounded-lg p-4 space-y-3 dark:border-gray-700"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div
                      className={`w-3 h-3 rounded-full ${getStatusColor(cfg.status)}`}
                      role="status"
                      aria-label={`Status: ${cfg.status}`}
                    />
                    <span className="font-semibold">{cfg.name}</span>
                    <Badge variant="outline">{cfg.provider}</Badge>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => cfg.id && handleTest(cfg.id)}
                      disabled={testing === cfg.id}
                    >
                      {testing === cfg.id ? "Testing..." : "Test"}
                    </Button>
                    {cfg.id && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onDelete?.(cfg.id!)}
                        aria-label={`Delete ${cfg.name}`}
                      >
                        Delete
                      </Button>
                    )}
                  </div>
                </div>
                <div className="text-sm text-gray-600 dark:text-gray-400">
                  <p>
                    <span className="font-medium">Endpoint:</span> {cfg.endpoint}
                  </p>
                  <p>
                    <span className="font-medium">Events:</span>{" "}
                    {cfg.events.join(", ") || "All events"}
                  </p>
                  <p>
                    <span className="font-medium">Stats:</span>{" "}
                    <span className="text-green-600">{cfg.successCount} success</span> /{" "}
                    <span className="text-red-600">{cfg.failureCount} failed</span>
                  </p>
                  {cfg.retryEnabled && (
                    <p>
                      <span className="font-medium">Retries:</span> Up to {cfg.maxRetries}
                    </p>
                  )}
                </div>
                {testResult && testResult.configId === cfg.id && (
                  <div
                    className={`p-2 rounded text-sm ${
                      testResult.success
                        ? "bg-green-50 text-green-800 dark:bg-green-900/20 dark:text-green-400"
                        : "bg-red-50 text-red-800 dark:bg-red-900/20 dark:text-red-400"
                    }`}
                    role="alert"
                  >
                    {testResult.message}
                  </div>
                )}
              </div>
            ))}

            {/* New webhook form */}
            {showNewForm ? (
              <div className="border rounded-lg p-4 space-y-4 dark:border-gray-700">
                <h3 className="font-semibold">New Webhook Configuration</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="wh-name">Configuration Name</Label>
                    <Input
                      id="wh-name"
                      placeholder="e.g. Paddle Billing Webhooks"
                      value={newConfig.name || ""}
                      onChange={(e) =>
                        setNewConfig((prev) => ({ ...prev, name: e.target.value }))
                      }
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="wh-provider">Provider</Label>
                    <Select
                      value={newConfig.provider || ""}
                      onValueChange={(v) => {
                        setSelectedProvider(v);
                        setNewConfig((prev) => ({
                          ...prev,
                          provider: v,
                          events: [],
                        }));
                      }}
                    >
                      <SelectTrigger id="wh-provider">
                        <SelectValue placeholder="Select provider" />
                      </SelectTrigger>
                      <SelectContent>
                        {SUPPORTED_PROVIDERS.map((p) => (
                          <SelectItem key={p.value} value={p.value}>
                            {p.label} ({p.category})
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                {newConfig.provider && (
                  <div className="p-3 bg-blue-50 dark:bg-blue-900/20 rounded-md">
                    <p className="text-sm font-medium text-blue-800 dark:text-blue-300">
                      Webhook Endpoint:
                    </p>
                    <code className="text-sm text-blue-600 dark:text-blue-400">
                      {typeof window !== "undefined"
                        ? `${window.location.origin}/api/webhooks/${newConfig.provider}`
                        : `/api/webhooks/${newConfig.provider}`}
                    </code>
                  </div>
                )}
                <div className="space-y-2">
                  <Label htmlFor="wh-secret">Webhook Secret</Label>
                  <Input
                    id="wh-secret"
                    type="password"
                    placeholder="Enter webhook verification secret"
                    value={newConfig.secret || ""}
                    onChange={(e) =>
                      setNewConfig((prev) => ({ ...prev, secret: e.target.value }))
                    }
                  />
                  <p className="text-xs text-gray-500">
                    Used for HMAC signature verification. Keep this secret.
                  </p>
                </div>
                {/* Event subscription */}
                {newConfig.provider && PROVIDER_EVENTS[newConfig.provider] && (
                  <div className="space-y-2">
                    <Label>Subscribe to Events</Label>
                    <div className="flex flex-wrap gap-2">
                      {PROVIDER_EVENTS[newConfig.provider].map((event) => (
                        <Badge
                          key={event}
                          variant={
                            (newConfig.events || []).includes(event)
                              ? "default"
                              : "outline"
                          }
                          className="cursor-pointer"
                          onClick={() => handleEventToggle(event)}
                          role="checkbox"
                          aria-checked={(newConfig.events || []).includes(event)}
                        >
                          {event}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="flex items-center gap-2">
                    <input
                      id="wh-retry"
                      type="checkbox"
                      checked={newConfig.retryEnabled ?? true}
                      onChange={(e) =>
                        setNewConfig((prev) => ({
                          ...prev,
                          retryEnabled: e.target.checked,
                        }))
                      }
                      className="rounded"
                    />
                    <Label htmlFor="wh-retry">Enable Auto-Retry</Label>
                  </div>
                  {newConfig.retryEnabled && (
                    <div className="space-y-2">
                      <Label htmlFor="wh-max-retries">Max Retries</Label>
                      <Input
                        id="wh-max-retries"
                        type="number"
                        min={1}
                        max={10}
                        value={newConfig.maxRetries ?? 5}
                        onChange={(e) =>
                          setNewConfig((prev) => ({
                            ...prev,
                            maxRetries: parseInt(e.target.value) || 5,
                          }))
                        }
                      />
                    </div>
                  )}
                </div>
                <div className="flex gap-3">
                  <Button
                    onClick={handleSave}
                    disabled={!newConfig.name || !newConfig.provider}
                  >
                    Save Configuration
                  </Button>
                  <Button variant="outline" onClick={() => setShowNewForm(false)}>
                    Cancel
                  </Button>
                </div>
              </div>
            ) : (
              <Button variant="outline" onClick={() => setShowNewForm(true)}>
                + Add Webhook Configuration
              </Button>
            )}
          </div>
        )}

        {/* ── Logs Tab ───────────────────────────────────────────── */}
        {activeTab === "logs" && (
          <div className="space-y-3">
            {logs.length === 0 ? (
              <p className="text-sm text-gray-500 text-center py-8">
                No webhook activity yet. Configure a webhook to start receiving events.
              </p>
            ) : (
              logs.map((log) => (
                <div
                  key={log.id}
                  className="border rounded-lg p-3 space-y-1 dark:border-gray-700"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {getLogStatusBadge(log.status)}
                      <span className="font-medium text-sm">{log.event_type}</span>
                      <Badge variant="outline" className="text-xs">
                        {log.provider}
                      </Badge>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-gray-500">{log.timestamp}</span>
                      {log.status === "failed" && onRetry && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => onRetry(log.id)}
                        >
                          Retry
                        </Button>
                      )}
                    </div>
                  </div>
                  <p className="text-xs text-gray-600 dark:text-gray-400 truncate">
                    {log.payload_preview}
                  </p>
                  {log.error_message && (
                    <p className="text-xs text-red-600 dark:text-red-400">
                      Error: {log.error_message}
                    </p>
                  )}
                </div>
              ))
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
