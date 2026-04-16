'use client';

import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Loader2, Save, X, Plus, Trash2, ShieldAlert, Info, Globe,
  Database, Webhook, Code2, Plug,
} from 'lucide-react';
import { AuthConfig, type AuthType } from './AuthConfig';
import { TestConnection, type TestResult } from './TestConnection';

// ── Types ─────────────────────────────────────────────────────────────

/** The 5 custom integration types supported by the backend */
type CustomIntegrationType = 'rest' | 'graphql' | 'webhook_in' | 'webhook_out' | 'database';

/** HTTP methods for REST and Webhook Out */
type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE' | 'HEAD' | 'OPTIONS';

/** Database engines supported by the backend */
type DatabaseType = 'postgresql' | 'mysql' | 'sqlite' | 'mongodb';

/** SSL mode options for database connections */
type SslMode = 'disable' | 'require' | 'verify-ca' | 'verify-full';

/** A single key-value header pair */
interface HeaderEntry {
  key: string;
  value: string;
}

interface CustomIntegrationBuilderProps {
  /** Called after the integration is successfully created and saved */
  onComplete: () => void;
  /** Called when the user cancels without saving */
  onCancel: () => void;
}

// ── Constants ─────────────────────────────────────────────────────────

/** Integration type definitions with metadata and icons */
const INTEGRATION_TYPES: Array<{
  value: CustomIntegrationType;
  label: string;
  description: string;
  icon: React.ReactNode;
}> = [
  {
    value: 'rest',
    label: 'REST API',
    description: 'Connect to any REST/HTTP endpoint with custom methods and headers.',
    icon: <Globe className="h-5 w-5" />,
  },
  {
    value: 'graphql',
    label: 'GraphQL',
    description: 'Query GraphQL endpoints with custom queries and headers.',
    icon: <Code2 className="h-5 w-5" />,
  },
  {
    value: 'webhook_in',
    label: 'Incoming Webhook',
    description: 'Receive data via a unique webhook URL with HMAC verification.',
    icon: <Webhook className="h-5 w-5" />,
  },
  {
    value: 'webhook_out',
    label: 'Outgoing Webhook',
    description: 'Send data to external services when events occur in PARWA.',
    icon: <Webhook className="h-5 w-5" />,
  },
  {
    value: 'database',
    label: 'Database',
    description: 'Connect directly to PostgreSQL, MySQL, SQLite, or MongoDB.',
    icon: <Database className="h-5 w-5" />,
  },
];

const HTTP_METHODS: HttpMethod[] = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'];
const DATABASE_TYPES: DatabaseType[] = ['postgresql', 'mysql', 'sqlite', 'mongodb'];
const SSL_MODES: SslMode[] = ['disable', 'require', 'verify-ca', 'verify-full'];

// ── Component ─────────────────────────────────────────────────────────

export function CustomIntegrationBuilder({ onComplete, onCancel }: CustomIntegrationBuilderProps) {
  // ── Integration Type Selection ───────────────────────────────────
  const [selectedType, setSelectedType] = useState<CustomIntegrationType | null>(null);
  const [name, setName] = useState('');

  // ── Connection Configuration ────────────────────────────────────
  const [url, setUrl] = useState('');
  const [httpMethod, setHttpMethod] = useState<HttpMethod>('GET');
  const [authType, setAuthType] = useState<AuthType>('none');
  const [authValue, setAuthValue] = useState<Record<string, string>>({});
  const [timeout, setTimeout] = useState('10');

  // ── Headers (key-value pairs for REST/GraphQL/Webhook Out) ─────
  const [headers, setHeaders] = useState<HeaderEntry[]>([]);

  // ── Request/Response Mapping (REST/GraphQL) ────────────────────
  const [requestTemplate, setRequestTemplate] = useState('');
  const [responseMapping, setResponseMapping] = useState('');

  // ── Webhook-specific Fields ────────────────────────────────────
  const [webhookSecret, setWebhookSecret] = useState('');
  const [allowedEvents, setAllowedEvents] = useState('');
  const [payloadTemplate, setPayloadTemplate] = useState('');
  // D12-P6: Expected payload schema for webhook_in test validation
  const [payloadSchema, setPayloadSchema] = useState('');

  // ── Database-specific Fields ───────────────────────────────────
  const [dbType, setDbType] = useState<DatabaseType>('postgresql');
  const [connectionString, setConnectionString] = useState('');
  const [sslMode, setSslMode] = useState<SslMode>('require');

  // ── UI State ───────────────────────────────────────────────────
  const [error, setError] = useState<string | null>(null);
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  // D12-P14: Preserve previous test result so a new failure doesn't erase a prior success
  const [previousTestResult, setPreviousTestResult] = useState<TestResult | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  // D12-P7: Double-submit guard — useRef doesn't trigger re-render race
  const isSavingRef = useRef(false);
  // D12-P7: AbortController for cleanup on unmount
  const abortControllerRef = useRef<AbortController | null>(null);

  // D12-P7: Abort in-flight save on unmount
  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
    };
  }, []);

  // ── Helpers ────────────────────────────────────────────────────

  /** Check if the current type uses URL + auth fields */
  const needsUrl = selectedType === 'rest' || selectedType === 'graphql' || selectedType === 'webhook_out';
  const needsAuth = selectedType === 'rest' || selectedType === 'graphql' || selectedType === 'webhook_out';
  const needsHeaders = selectedType === 'rest' || selectedType === 'graphql' || selectedType === 'webhook_out';
  const needsMethod = selectedType === 'rest' || selectedType === 'webhook_out';
  const needsMapping = selectedType === 'rest' || selectedType === 'graphql';

  // ── Header Management ───────────────────────────────────────────

  const addHeader = () => setHeaders([...headers, { key: '', value: '' }]);
  const removeHeader = (index: number) => setHeaders(headers.filter((_, i) => i !== index));
  const updateHeader = (index: number, field: 'key' | 'value', val: string) => {
    const updated = [...headers];
    updated[index] = { ...updated[index], [field]: val };
    setHeaders(updated);
  };

  // ── Validation ─────────────────────────────────────────────────

  const validate = (): string | null => {
    if (!selectedType) return 'Please select an integration type.';
    if (!name.trim()) return 'Integration name is required.';

    if (needsUrl && !url.trim()) return 'URL is required.';
    if (selectedType === 'webhook_in' && !webhookSecret.trim()) return 'HMAC secret is required for incoming webhooks.';
    if (selectedType === 'database' && !connectionString.trim()) return 'Connection string is required.';
    if (selectedType === 'database' && !dbType) return 'Database type is required.';

    return null;
  };

  // ── Build Config Object ─────────────────────────────────────────

  const buildConfig = (): Record<string, unknown> => {
    const config: Record<string, unknown> = {};

    switch (selectedType) {
      case 'rest':
        config.url = url.trim();
        config.method = httpMethod;
        config.auth_type = authType;
        if (authType !== 'none') Object.assign(config, authValue);
        if (headers.length > 0) {
          config.headers = headers
            .filter((h) => h.key.trim())
            .reduce<Record<string, string>>((acc, h) => {
              acc[h.key.trim()] = h.value;
              return acc;
            }, {});
        }
        if (timeout) config.timeout = Math.max(1, Math.min(30, parseInt(timeout, 10) || 10));
        if (requestTemplate.trim()) config.request_template = requestTemplate.trim();
        if (responseMapping.trim()) config.response_mapping = responseMapping.trim();
        break;

      case 'graphql':
        config.url = url.trim();
        config.auth_type = authType;
        if (authType !== 'none') Object.assign(config, authValue);
        if (headers.length > 0) {
          config.headers = headers
            .filter((h) => h.key.trim())
            .reduce<Record<string, string>>((acc, h) => {
              acc[h.key.trim()] = h.value;
              return acc;
            }, {});
        }
        if (timeout) config.timeout = Math.max(1, Math.min(30, parseInt(timeout, 10) || 10));
        if (requestTemplate.trim()) config.query_template = requestTemplate.trim();
        if (responseMapping.trim()) config.response_mapping = responseMapping.trim();
        break;

      case 'webhook_in':
        config.secret = webhookSecret.trim();
        if (allowedEvents.trim()) config.allowed_events = allowedEvents.split(',').map((e) => e.trim()).filter(Boolean);
        // D12-P6: Include expected payload schema if provided
        if (payloadSchema.trim()) {
          try {
            config.expected_payload_schema = JSON.parse(payloadSchema.trim());
          } catch {
            // If it's not valid JSON, pass as-is (backend will validate)
            config.expected_payload_schema = payloadSchema.trim();
          }
        }
        break;

      case 'webhook_out':
        config.url = url.trim();
        config.method = httpMethod;
        config.auth_type = authType;
        if (authType !== 'none') Object.assign(config, authValue);
        if (headers.length > 0) {
          config.headers = headers
            .filter((h) => h.key.trim())
            .reduce<Record<string, string>>((acc, h) => {
              acc[h.key.trim()] = h.value;
              return acc;
            }, {});
        }
        if (allowedEvents.trim()) config.trigger_events = allowedEvents.split(',').map((e) => e.trim()).filter(Boolean);
        if (payloadTemplate.trim()) config.payload_template = payloadTemplate.trim();
        break;

      case 'database':
        config.db_type = dbType;
        config.connection_string = connectionString.trim();
        config.ssl_mode = sslMode;
        if (requestTemplate.trim()) config.query_template = requestTemplate.trim();
        if (responseMapping.trim()) config.field_mapping = responseMapping.trim();
        break;
    }

    return config;
  };

  // ── Test Connection ────────────────────────────────────────────

  const handleTest = useCallback(async (): Promise<TestResult> => {
    const validationError = validate();
    if (validationError) throw new Error(validationError);

    // Create a temporary integration first (draft), then test it
    const config = buildConfig();

    // For testing without persisting, use test-credentials endpoint
    const res = await fetch('/api/integrations/test-credentials', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        integration_type: 'custom',
        config: { ...config, custom_integration_type: selectedType },
      }),
    });

    const data = await res.json().catch(() => ({ success: false, message: 'Connection test failed.' }));

    if (!res.ok) {
      return {
        success: false,
        message: data?.detail || data?.error?.message || `Test failed with status ${res.status}`,
      };
    }

    return {
      success: data.success ?? false,
      latency_ms: data.latency_ms,
      message: data.message || (data.success ? 'Connection successful' : 'Connection failed'),
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedType, name, url, httpMethod, authType, authValue, headers, timeout,
      webhookSecret, allowedEvents, payloadTemplate, payloadSchema, dbType, connectionString, sslMode,
      requestTemplate, responseMapping]);

  const runTest = async (): Promise<TestResult> => {
    // D12-P14: Archive current result before starting a new test
    setPreviousTestResult(testResult);
    setError(null);
    setTestResult(null);
    setIsTesting(true);
    try {
      const result = await handleTest();
      setTestResult(result);
      return result;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Connection test failed.';
      setError(message);
      const failResult: TestResult = { success: false, message };
      setTestResult(failResult);
      return failResult;
    } finally {
      setIsTesting(false);
    }
  };

  // ── Dependency array helper for useCallback ───────────────────
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const allFieldDeps = [selectedType, name, url, httpMethod, authType, authValue, headers, timeout,
    webhookSecret, allowedEvents, payloadTemplate, payloadSchema, dbType, connectionString, sslMode,
    requestTemplate, responseMapping] as const;

  // ── Save Integration ───────────────────────────────────────────

  const handleSave = async () => {
    // D12-P7: Guard against double-submit using ref (not state)
    if (isSavingRef.current) return;
    isSavingRef.current = true;

    const validationError = validate();
    if (validationError) {
      setError(validationError);
      isSavingRef.current = false;
      return;
    }

    setIsSaving(true);
    setError(null);

    // D12-P7: Create AbortController for this request
    const controller = new AbortController();
    abortControllerRef.current = controller;

    // D12-P7: Generate idempotency key for deduplication
    const idempotencyKey = crypto.randomUUID();

    try {
      const config = buildConfig();

      // POST to custom integrations endpoint
      const res = await fetch('/api/integrations/custom', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Idempotency-Key': idempotencyKey, // D12-P7: Prevent duplicates on retry
        },
        body: JSON.stringify({
          type: selectedType,
          name: name.trim(),
          config,
        }),
        signal: controller.signal, // D12-P7: Abort on unmount
      });

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        throw new Error(
          data?.detail || data?.message || `Failed to create integration (${res.status})`
        );
      }

      onComplete();
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        setError(err instanceof Error ? err.message : 'Failed to save integration.');
      }
    } finally {
      setIsSaving(false);
      isSavingRef.current = false;
      abortControllerRef.current = null;
    }
  };

  // ── Reset form when type changes ───────────────────────────────

  const handleTypeChange = (type: CustomIntegrationType) => {
    setSelectedType(type);
    setError(null);
    setTestResult(null);
    setPreviousTestResult(null); // D12-P14: Clear archived result on type change
    // D12-P17: Intentionally preserve `name` across type changes
    // Reset type-specific fields
    setUrl('');
    setHttpMethod('GET');
    setAuthType('none');
    setAuthValue({});
    setHeaders([]);
    setRequestTemplate('');
    setResponseMapping('');
    setWebhookSecret('');
    setAllowedEvents('');
    setPayloadTemplate('');
    setPayloadSchema('');
    setDbType('postgresql');
    setConnectionString('');
    setSslMode('require');
  };

  // ── Type Selection View ────────────────────────────────────────

  if (!selectedType) {
    return (
      <div className="space-y-6">
        {/* Header */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center">
                <Plug className="h-5 w-5 text-primary" />
              </div>
              <div>
                <h2 className="text-lg font-semibold">Custom Integration</h2>
                <p className="text-sm text-muted-foreground">
                  Create a custom integration for REST APIs, GraphQL, webhooks, or databases.
                </p>
              </div>
            </div>
            <Button variant="ghost" size="sm" onClick={onCancel}>
              <X className="h-4 w-4 mr-1" />
              Cancel
            </Button>
          </div>
        </div>

        {/* SSRF Security Notice */}
        <Alert>
          <ShieldAlert className="h-4 w-4" />
          <AlertDescription className="text-xs">
            For security, URLs pointing to private/internal IP addresses, localhost, or
            cloud metadata endpoints are blocked (SSRF prevention). Only public URLs are allowed.
          </AlertDescription>
        </Alert>

        {/* Type Selector Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {INTEGRATION_TYPES.map((type) => (
            <Card
              key={type.value}
              className="cursor-pointer hover:border-primary/50 transition-colors"
              onClick={() => handleTypeChange(type.value)}
            >
              <CardHeader className="pb-2">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center text-primary">
                    {type.icon}
                  </div>
                  <CardTitle className="text-sm">{type.label}</CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <CardDescription className="text-xs">{type.description}</CardDescription>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  // ── Configuration View ─────────────────────────────────────────

  const currentTypeMeta = INTEGRATION_TYPES.find((t) => t.value === selectedType);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center text-primary">
            {currentTypeMeta?.icon}
          </div>
          <div>
            <h2 className="text-lg font-semibold">
              {currentTypeMeta?.label} Integration
            </h2>
            <p className="text-sm text-muted-foreground">{currentTypeMeta?.description}</p>
          </div>
        </div>
        <Button variant="ghost" size="sm" onClick={onCancel}>
          <X className="h-4 w-4 mr-1" />
          Cancel
        </Button>
      </div>

      {/* Name Field */}
      <div className="space-y-1.5">
        <Label htmlFor="custom-int-name">Integration Name</Label>
        <Input
          id="custom-int-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder={`My ${currentTypeMeta?.label} Integration`}
          maxLength={100}
          disabled={isSaving}
        />
      </div>

      {/* ── Connection Details ────────────────────────────────────── */}

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm">Connection Details</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* URL for REST / GraphQL / Webhook Out */}
          {needsUrl && (
            <div className="space-y-1.5">
              <Label htmlFor="custom-int-url">
                {selectedType === 'graphql' ? 'GraphQL Endpoint URL' : 'Endpoint URL'}
              </Label>
              <Input
                id="custom-int-url"
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder={
                  selectedType === 'graphql'
                    ? 'https://api.example.com/graphql'
                    : 'https://api.example.com/v1/resource'
                }
                maxLength={2048}
                disabled={isSaving}
              />
              <p className="text-xs text-muted-foreground flex items-center gap-1">
                <Info className="h-3 w-3" />
                Private IPs, localhost, and cloud metadata endpoints are blocked.
              </p>
            </div>
          )}

          {/* HTTP Method for REST / Webhook Out */}
          {needsMethod && (
            <div className="space-y-1.5">
              <Label htmlFor="custom-int-method">HTTP Method</Label>
              <Select
                value={httpMethod}
                onValueChange={(v) => setHttpMethod(v as HttpMethod)}
                disabled={isSaving}
              >
                <SelectTrigger id="custom-int-method" className="w-full sm:w-[200px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {HTTP_METHODS.map((method) => (
                    <SelectItem key={method} value={method}>
                      {method}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {/* Timeout for REST / GraphQL */}
          {(selectedType === 'rest' || selectedType === 'graphql') && (
            <div className="space-y-1.5">
              <Label htmlFor="custom-int-timeout">Timeout (seconds)</Label>
              <Input
                id="custom-int-timeout"
                type="number"
                min={1}
                max={30}
                value={timeout}
                onChange={(e) => setTimeout(e.target.value)}
                placeholder="10"
                disabled={isSaving}
              />
            </div>
          )}

          {/* Database-specific fields */}
          {selectedType === 'database' && (
            <div className="space-y-4">
              {/* Database Type */}
              <div className="space-y-1.5">
                <Label htmlFor="custom-int-dbtype">Database Type</Label>
                <Select
                  value={dbType}
                  onValueChange={(v) => setDbType(v as DatabaseType)}
                  disabled={isSaving}
                >
                  <SelectTrigger id="custom-int-dbtype" className="w-full sm:w-[200px]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {DATABASE_TYPES.map((db) => (
                      <SelectItem key={db} value={db}>
                        {db.charAt(0).toUpperCase() + db.slice(1)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Connection String */}
              <div className="space-y-1.5">
                <Label htmlFor="custom-int-connstr">Connection String</Label>
                <Textarea
                  id="custom-int-connstr"
                  value={connectionString}
                  onChange={(e) => setConnectionString(e.target.value)}
                  placeholder={
                    dbType === 'sqlite'
                      ? '/path/to/database.db'
                      : dbType === 'mongodb'
                        ? 'mongodb+srv://user:pass@cluster.example.mongodb.net/dbname'
                        : 'postgresql://user:password@host:5432/database'
                  }
                  rows={3}
                  maxLength={1024}
                  disabled={isSaving}
                  className="font-mono text-xs"
                />
              </div>

              {/* SSL Mode (not for SQLite) */}
              {dbType !== 'sqlite' && (
                <div className="space-y-1.5">
                  <Label htmlFor="custom-int-ssl">SSL Mode</Label>
                  <Select
                    value={sslMode}
                    onValueChange={(v) => setSslMode(v as SslMode)}
                    disabled={isSaving}
                  >
                    <SelectTrigger id="custom-int-ssl" className="w-full sm:w-[200px]">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {SSL_MODES.map((mode) => (
                        <SelectItem key={mode} value={mode}>
                          {mode}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}
            </div>
          )}

          {/* Webhook In-specific fields */}
          {selectedType === 'webhook_in' && (
            <div className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="custom-int-whsecret">HMAC Secret</Label>
                <Input
                  id="custom-int-whsecret"
                  type="password"
                  value={webhookSecret}
                  onChange={(e) => setWebhookSecret(e.target.value)}
                  placeholder="Enter a secret for HMAC signature verification"
                  maxLength={256}
                  disabled={isSaving}
                />
                <p className="text-xs text-muted-foreground flex items-center gap-1">
                  <Info className="h-3 w-3" />
                  This secret is used to verify that incoming webhook payloads are authentic.
                </p>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="custom-int-events">Allowed Events</Label>
                <Input
                  id="custom-int-events"
                  value={allowedEvents}
                  onChange={(e) => setAllowedEvents(e.target.value)}
                  placeholder="ticket.created, ticket.resolved (comma-separated)"
                  maxLength={1024}
                  disabled={isSaving}
                />
              </div>
              {/* D12-P6: Expected Payload Schema for webhook_in test */}
              <div className="space-y-1.5">
                <Label htmlFor="custom-int-payload-schema">Expected Payload Schema (optional)</Label>
                <Textarea
                  id="custom-int-payload-schema"
                  value={payloadSchema}
                  onChange={(e) => setPayloadSchema(e.target.value)}
                  placeholder={'{\n  "type": "object",\n  "properties": {\n    "event": { "type": "string" }\n  }\n}'}
                  rows={4}
                  disabled={isSaving}
                  className="font-mono text-xs"
                />
                <p className="text-xs text-muted-foreground flex items-center gap-1">
                  <Info className="h-3 w-3" />
                  JSON schema for validating incoming webhook payloads.
                </p>
              </div>
            </div>
          )}

          {/* Webhook Out-specific: payload template */}
          {selectedType === 'webhook_out' && (
            <div className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="custom-int-wh-events">Trigger Events</Label>
                <Input
                  id="custom-int-wh-events"
                  value={allowedEvents}
                  onChange={(e) => setAllowedEvents(e.target.value)}
                  placeholder="ticket.created, ticket.resolved (comma-separated)"
                  maxLength={1024}
                  disabled={isSaving}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="custom-int-payload">Payload Template (JSON)</Label>
                <Textarea
                  id="custom-int-payload"
                  value={payloadTemplate}
                  onChange={(e) => setPayloadTemplate(e.target.value)}
                  placeholder={'{\n  "event": "{{event_type}}",\n  "ticket_id": "{{ticket_id}}"\n}'}
                  rows={5}
                  maxLength={10000}
                  disabled={isSaving}
                  className="font-mono text-xs"
                />
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* ── Auth Configuration ────────────────────────────────────── */}

      {needsAuth && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Authentication</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Auth Type Selector */}
            <div className="space-y-1.5">
              <Label htmlFor="custom-int-authtype">Auth Type</Label>
              <Select
                value={authType}
                onValueChange={(v) => {
                  setAuthType(v as AuthType);
                  setAuthValue({});
                  setTestResult(null);
                }}
                disabled={isSaving}
              >
                <SelectTrigger id="custom-int-authtype" className="w-full sm:w-[200px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">None</SelectItem>
                  <SelectItem value="bearer">Bearer Token</SelectItem>
                  <SelectItem value="basic">Basic Auth</SelectItem>
                  <SelectItem value="api_key">API Key</SelectItem>
                  <SelectItem value="oauth2">OAuth 2.0</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Auth credential fields */}
            <AuthConfig
              authType={authType}
              value={authValue}
              onChange={setAuthValue}
              disabled={isSaving}
            />
          </CardContent>
        </Card>
      )}

      {/* ── Custom Headers ────────────────────────────────────────── */}

      {needsHeaders && (
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm">Custom Headers</CardTitle>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={addHeader}
                disabled={isSaving}
              >
                <Plus className="h-3 w-3 mr-1" />
                Add Header
              </Button>
            </div>
            <CardDescription className="text-xs">
              Add custom headers to include with each request.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {headers.length === 0 ? (
              <p className="text-xs text-muted-foreground text-center py-3">
                No custom headers configured. Click &quot;Add Header&quot; to add one.
              </p>
            ) : (
              <div className="space-y-2">
                {headers.map((header, index) => (
                  <div key={index} className="flex items-center gap-2">
                    <Input
                      value={header.key}
                      onChange={(e) => updateHeader(index, 'key', e.target.value)}
                      placeholder="Header name"
                      className="flex-1"
                      maxLength={128}
                      disabled={isSaving}
                    />
                    <Input
                      value={header.value}
                      onChange={(e) => updateHeader(index, 'value', e.target.value)}
                      placeholder="Value"
                      className="flex-1"
                      maxLength={4096}
                      disabled={isSaving}
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => removeHeader(index)}
                      disabled={isSaving}
                      aria-label={`Remove header ${header.key || index + 1}`}
                    >
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* ── Request/Response Mapping ──────────────────────────────── */}

      {needsMapping && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Request &amp; Response Mapping</CardTitle>
            <CardDescription className="text-xs">
              Define how PARWA maps data to and from the external service.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="custom-int-request">
                {selectedType === 'graphql' ? 'Default Query' : 'Request Template'}
              </Label>
              <Textarea
                id="custom-int-request"
                value={requestTemplate}
                onChange={(e) => setRequestTemplate(e.target.value)}
                placeholder={
                  selectedType === 'graphql'
                    ? '{ __typename }'
                    : '{\n  "query": "{{user_query}}"\n}'
                }
                rows={4}
                maxLength={10000}
                disabled={isSaving}
                className="font-mono text-xs"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="custom-int-response">
                Response Mapping (JSON)
              </Label>
              <Textarea
                id="custom-int-response"
                value={responseMapping}
                onChange={(e) => setResponseMapping(e.target.value)}
                placeholder={'{\n  "ticket_id": "data.id",\n  "subject": "data.title"\n}'}
                rows={4}
                maxLength={10000}
                disabled={isSaving}
                className="font-mono text-xs"
              />
            </div>
          </CardContent>
        </Card>
      )}

      {/* ── Database: Query Template & Field Mapping ───────────────*/}

      {selectedType === 'database' && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Query &amp; Field Mapping</CardTitle>
            <CardDescription className="text-xs">
              Define the SQL query template and how results map to PARWA fields.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="custom-int-query">Query Template</Label>
              <Textarea
                id="custom-int-query"
                value={requestTemplate}
                onChange={(e) => setRequestTemplate(e.target.value)}
                placeholder="SELECT * FROM tickets WHERE status = :status LIMIT 10"
                rows={4}
                maxLength={10000}
                disabled={isSaving}
                className="font-mono text-xs"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="custom-int-fieldmapping">Field Mapping (JSON)</Label>
              <Textarea
                id="custom-int-fieldmapping"
                value={responseMapping}
                onChange={(e) => setResponseMapping(e.target.value)}
                placeholder={'{\n  "ticket_id": "id",\n  "subject": "title",\n  "status": "status"\n}'}
                rows={4}
                maxLength={10000}
                disabled={isSaving}
                className="font-mono text-xs"
              />
            </div>
          </CardContent>
        </Card>
      )}

      {/* ── Error Display ─────────────────────────────────────────── */}

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* ── Test Connection ───────────────────────────────────────── */}

      <div>
        <TestConnection
          onTest={runTest}
          isTesting={isTesting}
          testResult={testResult}
          previousTestResult={previousTestResult}
        />
      </div>

      {/* ── Action Buttons ────────────────────────────────────────── */}

      <div className="flex items-center gap-3 pt-2">
        <Button
          type="button"
          variant="outline"
          onClick={onCancel}
          disabled={isSaving}
        >
          Cancel
        </Button>
        <Button
          type="button"
          onClick={handleSave}
          disabled={isSaving || isTesting}
          className="ml-auto"
        >
          {isSaving ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Saving...
            </>
          ) : (
            <>
              <Save className="mr-2 h-4 w-4" />
              Save Integration
            </>
          )}
        </Button>
      </div>
    </div>
  );
}
