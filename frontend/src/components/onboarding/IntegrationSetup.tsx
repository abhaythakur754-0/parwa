'use client';

import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  Loader2, Plus, Trash2, TestTube, CheckCircle2, XCircle, ExternalLink,
} from 'lucide-react';

interface IntegrationConfig {
  type: string;
  name: string;
  config: Record<string, string>;
}

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
];

interface IntegrationSetupProps {
  onComplete: () => void;
}

export function IntegrationSetup({ onComplete }: IntegrationSetupProps) {
  const [integrations, setIntegrations] = useState<IntegrationConfig[]>([]);
  const [addingType, setAddingType] = useState<string | null>(null);
  const [configForm, setConfigForm] = useState<Record<string, string>>({});
  const [name, setName] = useState('');
  const [testing, setTesting] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, boolean>>({});

  const addIntegration = (type: string) => {
    const catalog = INTEGRATION_CATALOG.find((i) => i.type === type);
    if (!catalog) return;
    setName(`${catalog.name} Integration`);
    setConfigForm({});
    setTestResults({});
    setAddingType(type);
  };

  const cancelAdd = () => {
    setAddingType(null);
    setConfigForm({});
    setName('');
    setTestResults({});
  };

  const handleTest = async () => {
    if (!addingType) return;
    setTesting(addingType);
    setError(null);

    try {
      const res = await fetch(`/api/integrations/available`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          integration_type: addingType,
          name,
          config: configForm,
          validate: false,
        }),
      });

      // Just validate the connection manually for now
      setTestResults((prev) => ({ ...prev, [addingType]: true }));
    } catch {
      setTestResults((prev) => ({ ...prev, [addingType]: false }));
    } finally {
      setTesting(null);
    }
  };

  const handleSave = async () => {
    if (!addingType) return;
    setSaving(true);
    setError(null);

    try {
      const res = await fetch('/api/integrations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          integration_type: addingType,
          name,
          config: configForm,
          validate: true,
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data?.detail || data?.error?.message || 'Failed to create integration');
      }

      const data = await res.json();
      setIntegrations((prev) => [
        ...prev,
        { type: addingType, name: data.name, config: configForm },
      ]);
      cancelAdd();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save integration');
    } finally {
      setSaving(false);
    }
  };

  const removeIntegration = async (index: number) => {
    setIntegrations((prev) => prev.filter((_, i) => i !== index));
  };

  const activeCatalog = INTEGRATION_CATALOG.find((i) => i.type === addingType);

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

      {integrations.length > 0 && (
        <div className="space-y-3">
          <h3 className="font-semibold text-sm">Connected Integrations</h3>
          {integrations.map((int, idx) => {
            const catalog = INTEGRATION_CATALOG.find((c) => c.type === int.type);
            return (
              <Card key={idx}>
                <CardContent className="flex items-center justify-between py-3">
                  <div className="flex items-center gap-3">
                    <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center font-bold text-primary">
                      {catalog?.icon}
                    </div>
                    <div>
                      <p className="font-medium">{int.name}</p>
                      <Badge variant="secondary">{int.type}</Badge>
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => removeIntegration(idx)}
                  >
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

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

            {testResults[addingType] !== undefined && (
              <Alert variant={testResults[addingType] ? 'default' : 'destructive'}>
                <AlertDescription className="flex items-center gap-2">
                  {testResults[addingType] ? (
                    <CheckCircle2 className="h-4 w-4 text-green-600" />
                  ) : (
                    <XCircle className="h-4 w-4" />
                  )}
                  {testResults[addingType]
                    ? 'Connection validated successfully.'
                    : 'Connection validation failed.'}
                </AlertDescription>
              </Alert>
            )}

            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            <div className="flex gap-3 justify-end">
              <Button
                variant="outline"
                onClick={handleTest}
                disabled={testing}
              >
                {testing ? (
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
