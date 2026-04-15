'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  Loader2, Plus, Trash2, TestTube, CheckCircle2, XCircle, ExternalLink,
} from 'lucide-react';

// ── Types ─────────────────────────────────────────────────────────────────

interface SavedIntegration {
  id: string;
  type: string;
  name: string;
  status: string;
  config: Record<string, string>;
  last_test_at: string | null;
  last_test_result: string | null;
  created_at: string;
}

interface TestResponse {
  integration_id: string;
  success: boolean;
  message: string;
  status: string;
  tested_at: string;
}

// ── Integration Catalog (synced with backend INTEGRATION_TYPES) ──────────

const INTEGRATION_CATALOG: Array<{
  type: string;
  name: string;
  description: string;
  icon: string;
  fields: Array<{ key: string; label: string; placeholder: string; type?: string }>;
}> = [
  {
    type: 'zendesk',
    name: 'Zendesk',
    description: 'Connect your Zendesk support center for unified ticket management.',
    icon: 'Z',
    fields: [
      { key: 'subdomain', label: 'Subdomain', placeholder: 'your-company' },
      { key: 'email', label: 'Email', placeholder: 'admin@company.com' },
      { key: 'api_token', label: 'API Token', placeholder: 'zendesk_api_token', type: 'password' },
    ],
  },
  {
    type: 'shopify',
    name: 'Shopify',
    description: 'Import product and order data for context-aware support.',
    icon: 'S',
    fields: [
      { key: 'shop_domain', label: 'Shop Domain', placeholder: 'your-store.myshopify.com' },
      { key: 'access_token', label: 'Access Token', placeholder: 'shpat_xxx', type: 'password' },
    ],
  },
  {
    type: 'slack',
    name: 'Slack',
    description: 'Receive real-time alerts and manage tickets from Slack.',
    icon: 'Sl',
    fields: [
      { key: 'bot_token', label: 'Bot Token', placeholder: 'xoxb-xxx', type: 'password' },
      { key: 'channel_id', label: 'Channel ID', placeholder: 'C01ABCDEF' },
    ],
  },
  {
    type: 'gmail',
    name: 'Gmail',
    description: 'Sync email conversations and auto-respond via AI.',
    icon: 'G',
    fields: [
      { key: 'client_id', label: 'Client ID', placeholder: 'xxx.apps.googleusercontent.com' },
      { key: 'client_secret', label: 'Client Secret', placeholder: 'GOCSPX-xxx', type: 'password' },
      { key: 'refresh_token', label: 'Refresh Token', placeholder: '1//xxx', type: 'password' },
    ],
  },
  {
    type: 'freshdesk',
    name: 'Freshdesk',
    description: 'Pull tickets and customer data from Freshdesk.',
    icon: 'F',
    fields: [
      { key: 'domain', label: 'Domain', placeholder: 'your-company' },
      { key: 'api_key', label: 'API Key', placeholder: 'freshdesk_api_key', type: 'password' },
    ],
  },
  {
    type: 'intercom',
    name: 'Intercom',
    description: 'Connect Intercom for live chat and inbox integration.',
    icon: 'I',
    fields: [
      { key: 'access_token', label: 'Access Token', placeholder: 'dGcmRxxx', type: 'password' },
    ],
  },
];

// ── Component ─────────────────────────────────────────────────────────────

interface IntegrationSetupProps {
  onComplete: () => void;
}

export function IntegrationSetup({ onComplete }: IntegrationSetupProps) {
  const [integrations, setIntegrations] = useState<SavedIntegration[]>([]);
  const [addingType, setAddingType] = useState<string | null>(null);
  const [configForm, setConfigForm] = useState<Record<string, string>>({});
  const [name, setName] = useState('');
  const [testingId, setTestingId] = useState<string | null>(null);    // integration ID being tested
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);  // integration ID being deleted
  const [error, setError] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, { success: boolean; message: string }>>({});
  const [loading, setLoading] = useState(true);

  // ── Load existing integrations on mount ───────────────────────────
  const loadIntegrations = useCallback(async () => {
    try {
      const res = await fetch('/api/integrations');
      if (res.ok) {
        const data = await res.json();
        setIntegrations(data);
      }
    } catch {
      // Non-blocking — user can still add integrations
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadIntegrations();
  }, [loadIntegrations]);

  // ── Validate form fields before submission ────────────────────────
  const validateForm = (): string | null => {
    if (!name.trim()) return 'Integration name is required.';
    const catalog = INTEGRATION_CATALOG.find((i) => i.type === addingType);
    if (!catalog) return null;
    for (const field of catalog.fields) {
      const val = (configForm[field.key] || '').trim();
      if (!val) return `${field.label} is required.`;
    }
    return null;
  };

  // ── Test a saved integration via backend ──────────────────────────
  const handleTestSaved = async (id: string) => {
    setTestingId(id);
    setError(null);
    try {
      const res = await fetch(`/api/integrations/${id}/test`, { method: 'POST' });
      const data: TestResponse = await res.json();
      setTestResults((prev) => ({
        ...prev,
        [id]: { success: data.success, message: data.message },
      }));
    } catch {
      setTestResults((prev) => ({
        ...prev,
        [id]: { success: false, message: 'Connection test failed.' },
      }));
    } finally {
      setTestingId(null);
    }
  };

  // ── Test before save (dry run — doesn't persist) ──────────────────
  const handleTestNew = async () => {
    if (!addingType) return;
    const validationError = validateForm();
    if (validationError) {
      setError(validationError);
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const res = await fetch('/api/integrations/test-credentials', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          integration_type: addingType,
          config: configForm,
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data?.detail || data?.error?.message || 'Connection test failed');
      }
      const data: TestResponse = await res.json();
      setTestResults((prev) => ({
        ...prev,
        [`new-${addingType}`]: { success: data.success, message: data.message },
      }));
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Connection test failed';
      setError(msg);
      setTestResults((prev) => ({
        ...prev,
        [`new-${addingType}`]: { success: false, message: msg },
      }));
    } finally {
      setSaving(false);
    }
  };

  // ── Save integration ──────────────────────────────────────────────
  const handleSave = async () => {
    if (!addingType) return;
    const validationError = validateForm();
    if (validationError) {
      setError(validationError);
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const res = await fetch('/api/integrations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          integration_type: addingType,
          name: name.trim(),
          config: configForm,
          validate: true,
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data?.detail || data?.error?.message || 'Failed to save integration');
      }
      const data = await res.json();
      setIntegrations((prev) => [...prev, data]);
      cancelAdd();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save integration');
    } finally {
      setSaving(false);
    }
  };

  // ── Delete integration via backend ────────────────────────────────
  const removeIntegration = async (id: string) => {
    setDeletingId(id);
    try {
      const res = await fetch(`/api/integrations/${id}`, { method: 'DELETE' });
      if (res.ok) {
        setIntegrations((prev) => prev.filter((i) => i.id !== id));
        setTestResults((prev) => {
          const next = { ...prev };
          delete next[id];
          return next;
        });
      }
    } catch {
      // Silently fail — integration stays in UI
    } finally {
      setDeletingId(null);
    }
  };

  const addIntegration = (type: string) => {
    const catalog = INTEGRATION_CATALOG.find((i) => i.type === type);
    if (!catalog) return;
    setName(`${catalog.name} Integration`);
    setConfigForm({});
    setTestResults({});
    setError(null);
    setAddingType(type);
  };

  const cancelAdd = () => {
    setAddingType(null);
    setConfigForm({});
    setName('');
    setTestResults({});
    setError(null);
  };

  const activeCatalog = INTEGRATION_CATALOG.find((i) => i.type === addingType);

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'active': return <Badge className="bg-green-100 text-green-700">Active</Badge>;
      case 'error': return <Badge className="bg-red-100 text-red-700">Error</Badge>;
      case 'pending': return <Badge className="bg-yellow-100 text-yellow-700">Pending</Badge>;
      default: return <Badge variant="secondary">{status}</Badge>;
    }
  };

  return (
    <div className="space-y-6">
      <div className="text-center space-y-2">
        <ExternalLink className="h-12 w-12 mx-auto text-purple-600" />
        <h2 className="text-2xl font-bold">Connect Integrations</h2>
        <p className="text-muted-foreground">
          Connect your support tools so PARWA can provide context-aware responses.
          At least one integration is recommended before activation.
        </p>
      </div>

      {/* Connected Integrations */}
      {loading ? (
        <div className="flex justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : integrations.length > 0 && (
        <div className="space-y-3">
          <h3 className="font-semibold text-sm">Connected Integrations</h3>
          {integrations.map((int) => {
            const catalog = INTEGRATION_CATALOG.find((c) => c.type === int.type);
            const testResult = testResults[int.id];
            return (
              <Card key={int.id}>
                <CardContent className="flex items-center justify-between py-3">
                  <div className="flex items-center gap-3">
                    <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center font-bold text-primary">
                      {catalog?.icon || '?'}
                    </div>
                    <div>
                      <p className="font-medium">{int.name}</p>
                      <div className="flex items-center gap-2">
                        <Badge variant="secondary">{int.type}</Badge>
                        {getStatusBadge(int.status)}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleTestSaved(int.id)}
                      disabled={testingId === int.id}
                      title="Test Connection"
                    >
                      {testingId === int.id ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <TestTube className="h-4 w-4" />
                      )}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => removeIntegration(int.id)}
                      disabled={deletingId === int.id}
                      title="Delete Integration"
                    >
                      {deletingId === int.id ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Trash2 className="h-4 w-4 text-destructive" />
                      )}
                    </Button>
                  </div>
                </CardContent>
                {testResult && (
                  <div className="px-4 pb-3">
                    <Alert variant={testResult.success ? 'default' : 'destructive'}>
                      <AlertDescription className="flex items-center gap-2 text-sm">
                        {testResult.success ? (
                          <CheckCircle2 className="h-4 w-4 text-green-600 shrink-0" />
                        ) : (
                          <XCircle className="h-4 w-4 shrink-0" />
                        )}
                        {testResult.message}
                      </AlertDescription>
                    </Alert>
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      )}

      {/* Add New Integration */}
      {!addingType ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {INTEGRATION_CATALOG.filter(
            (c) => !integrations.some((i) => i.type === c.type)
          ).map((catalog) => (
            <Card
              key={catalog.type}
              className="cursor-pointer hover:border-primary/50 transition-colors"
              onClick={() => addIntegration(catalog.type)}
            >
              <CardHeader className="pb-2">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center font-bold text-primary">
                    {catalog.icon}
                  </div>
                  <CardTitle className="text-base">{catalog.name}</CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <CardDescription>{catalog.description}</CardDescription>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center font-bold text-primary">
                  {activeCatalog?.icon}
                </div>
                <CardTitle>{activeCatalog?.name} Setup</CardTitle>
              </div>
              <Button variant="ghost" size="sm" onClick={cancelAdd}>
                Cancel
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label htmlFor="int-name">Integration Name</Label>
              <Input
                id="int-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={`${activeCatalog?.name} Integration`}
              />
            </div>
            {activeCatalog?.fields.map((field) => (
              <div key={field.key}>
                <Label htmlFor={field.key}>{field.label}</Label>
                <Input
                  id={field.key}
                  type={field.type || 'text'}
                  value={configForm[field.key] || ''}
                  onChange={(e) =>
                    setConfigForm((prev) => ({ ...prev, [field.key]: e.target.value }))
                  }
                  placeholder={field.placeholder}
                />
              </div>
            ))}

            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            {(() => {
              const result = testResults[`new-${addingType}`];
              if (!result) return null;
              return (
                <Alert variant={result.success ? 'default' : 'destructive'}>
                  <AlertDescription className="flex items-center gap-2">
                    {result.success ? (
                      <CheckCircle2 className="h-4 w-4 text-green-600" />
                    ) : (
                      <XCircle className="h-4 w-4" />
                    )}
                    {result.message}
                  </AlertDescription>
                </Alert>
              );
            })()}

            <div className="flex gap-3 justify-end">
              <Button
                variant="outline"
                onClick={handleTestNew}
                disabled={saving}
              >
                {saving ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <TestTube className="mr-2 h-4 w-4" />
                )}
                Test Connection
              </Button>
              <Button onClick={handleSave} disabled={saving}>
                {saving ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Plus className="mr-2 h-4 w-4" />
                )}
                Save Integration
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="flex justify-between">
        <p className="text-sm text-muted-foreground">
          {integrations.length} integration(s) connected
        </p>
        <Button onClick={onComplete} size="lg">
          Continue
          {integrations.length === 0 && (
            <span className="ml-2 text-xs text-muted-foreground">(optional)</span>
          )}
        </Button>
      </div>
    </div>
  );
}
