"use client";

/**
 * CustomApiBuilder — Custom REST API Connection Builder UI
 * ========================================================
 * Allows users to create custom REST API connections for any provider
 * that isn't natively supported. Users can configure:
 *   - Base URL
 *   - Authentication method (Bearer, API Key, Basic, None)
 *   - Headers
 *   - Request method (GET, POST, PUT, DELETE)
 *   - Request body template
 *   - Response mapping
 *
 * Phase 19: Webhook Unification + Universal API
 */

import React, { useState, useCallback } from "react";
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

type AuthMethod = "bearer" | "api_key" | "basic" | "none";
type HttpMethod = "GET" | "POST" | "PUT" | "DELETE" | "PATCH";

interface CustomApiConfig {
  name: string;
  baseUrl: string;
  authMethod: AuthMethod;
  authToken: string;
  authHeaderName: string;
  username: string;
  password: string;
  method: HttpMethod;
  headers: Record<string, string>;
  bodyTemplate: string;
  responsePath: string;
  timeout: number;
  retryCount: number;
}

interface CustomApiBuilderProps {
  onSave?: (config: CustomApiConfig) => void;
  onTest?: (config: CustomApiConfig) => Promise<{ success: boolean; message: string }>;
  initialConfig?: Partial<CustomApiConfig>;
}

const AUTH_METHODS: { value: AuthMethod; label: string; description: string }[] = [
  { value: "bearer", label: "Bearer Token", description: "Authorization: Bearer <token>" },
  { value: "api_key", label: "API Key Header", description: "Custom header with API key" },
  { value: "basic", label: "Basic Auth", description: "Username & password" },
  { value: "none", label: "No Auth", description: "No authentication required" },
];

const HTTP_METHODS: HttpMethod[] = ["GET", "POST", "PUT", "DELETE", "PATCH"];

// ── Component ─────────────────────────────────────────────────────────

export default function CustomApiBuilder({
  onSave,
  onTest,
  initialConfig,
}: CustomApiBuilderProps) {
  const [config, setConfig] = useState<CustomApiConfig>({
    name: initialConfig?.name || "",
    baseUrl: initialConfig?.baseUrl || "",
    authMethod: initialConfig?.authMethod || "bearer",
    authToken: initialConfig?.authToken || "",
    authHeaderName: initialConfig?.authHeaderName || "X-API-Key",
    username: initialConfig?.username || "",
    password: initialConfig?.password || "",
    method: initialConfig?.method || "POST",
    headers: initialConfig?.headers || {},
    bodyTemplate: initialConfig?.bodyTemplate || '{\n  "data": ""\n}',
    responsePath: initialConfig?.responsePath || "",
    timeout: initialConfig?.timeout || 30000,
    retryCount: initialConfig?.retryCount || 3,
  });

  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [headerKey, setHeaderKey] = useState("");
  const [headerValue, setHeaderValue] = useState("");

  const updateConfig = useCallback(
    (updates: Partial<CustomApiConfig>) => {
      setConfig((prev) => ({ ...prev, ...updates }));
    },
    []
  );

  const handleAddHeader = useCallback(() => {
    if (headerKey.trim()) {
      updateConfig({
        headers: { ...config.headers, [headerKey.trim()]: headerValue },
      });
      setHeaderKey("");
      setHeaderValue("");
    }
  }, [headerKey, headerValue, config.headers, updateConfig]);

  const handleRemoveHeader = useCallback(
    (key: string) => {
      const { [key]: _, ...rest } = config.headers;
      updateConfig({ headers: rest });
    },
    [config.headers, updateConfig]
  );

  const handleTest = useCallback(async () => {
    if (!onTest) return;
    setTesting(true);
    setTestResult(null);
    try {
      const result = await onTest(config);
      setTestResult(result);
    } catch (err: any) {
      setTestResult({ success: false, message: err.message || "Test failed" });
    } finally {
      setTesting(false);
    }
  }, [config, onTest]);

  const handleSave = useCallback(() => {
    onSave?.(config);
  }, [config, onSave]);

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <svg className="w-5 h-5 text-blue-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
          Custom API Connection
        </CardTitle>
        <CardDescription>
          Connect to any REST API endpoint. Configure authentication, headers,
          and request format for custom integrations.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* ── Basic Info ─────────────────────────────────────────── */}
        <div className="space-y-4">
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
            Connection Details
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="api-name">Connection Name</Label>
              <Input
                id="api-name"
                placeholder="e.g. Internal CRM API"
                value={config.name}
                onChange={(e) => updateConfig({ name: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="api-method">HTTP Method</Label>
              <Select
                value={config.method}
                onValueChange={(v) => updateConfig({ method: v as HttpMethod })}
              >
                <SelectTrigger id="api-method">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {HTTP_METHODS.map((m) => (
                    <SelectItem key={m} value={m}>
                      <Badge variant={m === "GET" ? "secondary" : m === "POST" ? "default" : "outline"}>
                        {m}
                      </Badge>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="api-url">Base URL</Label>
            <Input
              id="api-url"
              placeholder="https://api.example.com/v1/endpoint"
              value={config.baseUrl}
              onChange={(e) => updateConfig({ baseUrl: e.target.value })}
            />
          </div>
        </div>

        <Separator />

        {/* ── Authentication ─────────────────────────────────────── */}
        <div className="space-y-4">
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
            Authentication
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="auth-method">Auth Method</Label>
              <Select
                value={config.authMethod}
                onValueChange={(v) => updateConfig({ authMethod: v as AuthMethod })}
              >
                <SelectTrigger id="auth-method">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {AUTH_METHODS.map((am) => (
                    <SelectItem key={am.value} value={am.value}>
                      {am.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-gray-500">
                {AUTH_METHODS.find((a) => a.value === config.authMethod)?.description}
              </p>
            </div>
            {config.authMethod === "bearer" && (
              <div className="space-y-2">
                <Label htmlFor="bearer-token">Bearer Token</Label>
                <Input
                  id="bearer-token"
                  type="password"
                  placeholder="Enter bearer token"
                  value={config.authToken}
                  onChange={(e) => updateConfig({ authToken: e.target.value })}
                />
              </div>
            )}
            {config.authMethod === "api_key" && (
              <>
                <div className="space-y-2">
                  <Label htmlFor="header-name">Header Name</Label>
                  <Input
                    id="header-name"
                    placeholder="X-API-Key"
                    value={config.authHeaderName}
                    onChange={(e) => updateConfig({ authHeaderName: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="api-key">API Key</Label>
                  <Input
                    id="api-key"
                    type="password"
                    placeholder="Enter API key"
                    value={config.authToken}
                    onChange={(e) => updateConfig({ authToken: e.target.value })}
                  />
                </div>
              </>
            )}
            {config.authMethod === "basic" && (
              <>
                <div className="space-y-2">
                  <Label htmlFor="basic-user">Username</Label>
                  <Input
                    id="basic-user"
                    placeholder="Username"
                    value={config.username}
                    onChange={(e) => updateConfig({ username: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="basic-pass">Password</Label>
                  <Input
                    id="basic-pass"
                    type="password"
                    placeholder="Password"
                    value={config.password}
                    onChange={(e) => updateConfig({ password: e.target.value })}
                  />
                </div>
              </>
            )}
          </div>
        </div>

        <Separator />

        {/* ── Custom Headers ─────────────────────────────────────── */}
        <div className="space-y-4">
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
            Custom Headers
          </h3>
          <div className="flex gap-2">
            <Input
              placeholder="Header name"
              value={headerKey}
              onChange={(e) => setHeaderKey(e.target.value)}
              className="flex-1"
            />
            <Input
              placeholder="Header value"
              value={headerValue}
              onChange={(e) => setHeaderValue(e.target.value)}
              className="flex-1"
            />
            <Button variant="outline" onClick={handleAddHeader}>
              Add
            </Button>
          </div>
          {Object.keys(config.headers).length > 0 && (
            <div className="space-y-2">
              {Object.entries(config.headers).map(([key, value]) => (
                <div key={key} className="flex items-center gap-2 text-sm">
                  <Badge variant="secondary">{key}</Badge>
                  <span className="text-gray-600 dark:text-gray-400 truncate">
                    {value}
                  </span>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleRemoveHeader(key)}
                    aria-label={`Remove header ${key}`}
                  >
                    ×
                  </Button>
                </div>
              ))}
            </div>
          )}
        </div>

        <Separator />

        {/* ── Request Body ───────────────────────────────────────── */}
        {config.method !== "GET" && (
          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
              Request Body Template
            </h3>
            <textarea
              className="w-full h-32 p-3 text-sm font-mono border rounded-md bg-gray-50 dark:bg-gray-900 dark:border-gray-700"
              value={config.bodyTemplate}
              onChange={(e) => updateConfig({ bodyTemplate: e.target.value })}
              placeholder='{"key": "value"}'
              aria-label="Request body template"
            />
            <div className="space-y-2">
              <Label htmlFor="response-path">Response Data Path</Label>
              <Input
                id="response-path"
                placeholder="e.g. data.results (JSON path to extract)"
                value={config.responsePath}
                onChange={(e) => updateConfig({ responsePath: e.target.value })}
              />
            </div>
          </div>
        )}

        <Separator />

        {/* ── Advanced Settings ──────────────────────────────────── */}
        <div className="space-y-4">
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
            Advanced Settings
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="timeout">Timeout (ms)</Label>
              <Input
                id="timeout"
                type="number"
                min={1000}
                max={120000}
                value={config.timeout}
                onChange={(e) => updateConfig({ timeout: parseInt(e.target.value) || 30000 })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="retry-count">Max Retries</Label>
              <Input
                id="retry-count"
                type="number"
                min={0}
                max={10}
                value={config.retryCount}
                onChange={(e) => updateConfig({ retryCount: parseInt(e.target.value) || 3 })}
              />
            </div>
          </div>
        </div>

        {/* ── Test Result ────────────────────────────────────────── */}
        {testResult && (
          <div
            className={`p-3 rounded-md text-sm ${
              testResult.success
                ? "bg-green-50 text-green-800 dark:bg-green-900/20 dark:text-green-400"
                : "bg-red-50 text-red-800 dark:bg-red-900/20 dark:text-red-400"
            }`}
            role="alert"
          >
            <span className="font-semibold">
              {testResult.success ? "Connection Successful" : "Connection Failed"}:
            </span>{" "}
            {testResult.message}
          </div>
        )}

        {/* ── Actions ────────────────────────────────────────────── */}
        <div className="flex gap-3 pt-2">
          <Button
            onClick={handleTest}
            disabled={testing || !config.baseUrl}
            variant="outline"
          >
            {testing ? "Testing..." : "Test Connection"}
          </Button>
          <Button
            onClick={handleSave}
            disabled={!config.name || !config.baseUrl}
          >
            Save Connection
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
