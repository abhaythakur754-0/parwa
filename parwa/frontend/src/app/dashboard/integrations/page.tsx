'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
  Plug,
  Plus,
  Trash2,
  Eye,
  EyeOff,
  CheckCircle2,
  XCircle,
  Loader2,
  AlertTriangle,
  KeyRound,
  TestTube,
  Globe,
  RefreshCw,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { cn } from '@/lib/utils';

// ── Types ──────────────────────────────────────────────────────────────

interface ConnectedIntegration {
  id: string;
  name: string;
  platform: string;
  authType: 'bearer' | 'api_key_header' | 'api_key_query' | 'basic_auth' | 'oauth2';
  credentials: Record<string, string>;
  testUrl?: string;
  testMethod?: 'GET' | 'POST';
  status: 'active' | 'error' | 'pending';
  testedAt?: string;
  testResult?: 'success' | 'failed';
}

interface CredentialField {
  name: string;
  label: string;
  type: 'text' | 'password' | 'url';
  placeholder: string;
  required: boolean;
}

// ── Auth type configurations ───────────────────────────────────────────

const AUTH_TYPES: Array<{
  value: ConnectedIntegration['authType'];
  label: string;
  description: string;
  fields: CredentialField[];
}> = [
  {
    value: 'bearer',
    label: 'Bearer Token',
    description: 'Authorization: Bearer {token}',
    fields: [
      { name: 'api_key', label: 'Token / API Key', type: 'password', placeholder: 'sk_live_xxx or pat-xxx', required: true },
    ],
  },
  {
    value: 'api_key_header',
    label: 'API Key (Header)',
    description: 'Custom header with your API key',
    fields: [
      { name: 'header_name', label: 'Header Name', type: 'text', placeholder: 'X-API-Key', required: true },
      { name: 'api_key', label: 'API Key', type: 'password', placeholder: 'your-api-key', required: true },
    ],
  },
  {
    value: 'api_key_query',
    label: 'API Key (Query Param)',
    description: 'API key passed as a URL parameter',
    fields: [
      { name: 'param_name', label: 'Parameter Name', type: 'text', placeholder: 'api_key', required: true },
      { name: 'api_key', label: 'API Key', type: 'password', placeholder: 'your-api-key', required: true },
    ],
  },
  {
    value: 'basic_auth',
    label: 'Basic Auth',
    description: 'Username and password authentication',
    fields: [
      { name: 'username', label: 'Username / Key', type: 'text', placeholder: 'user@example.com', required: true },
      { name: 'password', label: 'Password / Secret', type: 'password', placeholder: 'your-password', required: true },
    ],
  },
  {
    value: 'oauth2',
    label: 'OAuth 2.0',
    description: 'Client credentials or refresh token flow',
    fields: [
      { name: 'client_id', label: 'Client ID', type: 'text', placeholder: 'xxx.apps.googleusercontent.com', required: true },
      { name: 'client_secret', label: 'Client Secret', type: 'password', placeholder: 'GOCSPX-xxx', required: true },
      { name: 'refresh_token', label: 'Refresh Token', type: 'password', placeholder: '1//xxx', required: false },
    ],
  },
];

// ── Dashboard Integrations Page ────────────────────────────────────────

export default function IntegrationsDashboardPage() {
  const [integrations, setIntegrations] = useState<ConnectedIntegration[]>([]);
  const [showAddForm, setShowAddForm] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  // New integration form state
  const [newName, setNewName] = useState('');
  const [newPlatform, setNewPlatform] = useState('');
  const [newAuthType, setNewAuthType] = useState<ConnectedIntegration['authType']>('bearer');
  const [newCredentials, setNewCredentials] = useState<Record<string, string>>({});
  const [newTestUrl, setNewTestUrl] = useState('');
  const [newTestMethod, setNewTestMethod] = useState<'GET' | 'POST'>('GET');
  const [showPasswords, setShowPasswords] = useState<Record<string, boolean>>({});
  const [testingId, setTestingId] = useState<string | null>(null);

  // Load existing integrations from backend
  useEffect(() => {
    async function load() {
      try {
        const res = await fetch('/api/integrations');
        if (res.ok) {
          const data = await res.json();
          if (Array.isArray(data)) {
            setIntegrations(data.map((i: Record<string, unknown>) => ({
              id: String(i.id || i.integration_id || ''),
              name: String(i.name || i.integration_type || ''),
              platform: String(i.integration_type || i.platform || ''),
              authType: (i.auth_type as ConnectedIntegration['authType']) || 'bearer',
              credentials: (i.credentials as Record<string, string>) || {},
              testUrl: i.test_url ? String(i.test_url) : undefined,
              testMethod: (i.test_method as 'GET' | 'POST') || undefined,
              status: (i.status as ConnectedIntegration['status']) || 'active',
              testedAt: i.tested_at ? String(i.tested_at) : undefined,
              testResult: i.test_result as 'success' | 'failed' | undefined,
            })));
          }
        }
      } catch {
        // Backend unavailable — start with empty list
      } finally {
        setIsLoading(false);
      }
    }
    load();
  }, []);

  const selectedAuthConfig = AUTH_TYPES.find((a) => a.value === newAuthType)!;

  const handleAddIntegration = async () => {
    if (!newName.trim()) {
      toast.error('Please enter a name for this integration');
      return;
    }

    const missing = selectedAuthConfig.fields
      .filter((f) => f.required && !newCredentials[f.name]?.trim());
    if (missing.length > 0) {
      toast.error(`Please fill in: ${missing.map((f) => f.label).join(', ')}`);
      return;
    }

    setIsSaving(true);

    const integration: ConnectedIntegration = {
      id: `int-${Date.now()}`,
      name: newName.trim(),
      platform: newPlatform.trim() || newName.trim().toLowerCase().replace(/\s+/g, '_'),
      authType: newAuthType,
      credentials: { ...newCredentials },
      testUrl: newTestUrl.trim() || undefined,
      testMethod: newTestUrl.trim() ? newTestMethod : undefined,
      status: 'pending',
    };

    try {
      const res = await fetch('/api/integrations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: integration.name,
          integration_type: integration.platform,
          auth_type: integration.authType,
          credentials: integration.credentials,
          test_url: integration.testUrl,
          test_method: integration.testMethod,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        integration.id = data.id || integration.id;
        integration.status = 'active';
      } else {
        integration.status = 'active';
      }
    } catch {
      integration.status = 'active';
    }

    setIntegrations((prev) => [...prev, integration]);
    resetForm();
    setIsSaving(false);
    toast.success(`${integration.name} added!`);
  };

  const resetForm = () => {
    setNewName('');
    setNewPlatform('');
    setNewAuthType('bearer');
    setNewCredentials({});
    setNewTestUrl('');
    setNewTestMethod('GET');
    setShowAddForm(false);
  };

  const handleTestConnection = useCallback(async (integration: ConnectedIntegration) => {
    setTestingId(integration.id);

    try {
      const res = await fetch('/api/integrations/test-local', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          integration_type: integration.platform,
          auth_type: integration.authType,
          credentials: integration.credentials,
          test_url: integration.testUrl,
          test_method: integration.testMethod,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        const success = data.success !== false;
        setIntegrations((prev) => prev.map((i) =>
          i.id === integration.id
            ? { ...i, testResult: success ? 'success' : 'failed', testedAt: new Date().toISOString(), status: success ? 'active' : 'error' }
            : i
        ));
        toast[success ? 'success' : 'error'](
          success
            ? `${integration.name} connected!`
            : `Connection failed — ${data.message || 'check your credentials'}`
        );
      } else {
        setIntegrations((prev) => prev.map((i) =>
          i.id === integration.id
            ? { ...i, testResult: 'failed', testedAt: new Date().toISOString(), status: 'error' }
            : i
        ));
        toast.error('Connection test failed — server error');
      }
    } catch {
      setIntegrations((prev) => prev.map((i) =>
        i.id === integration.id
          ? { ...i, testResult: 'failed', testedAt: new Date().toISOString(), status: 'error' }
          : i
      ));
      toast.error('Connection test failed — could not reach server');
    } finally {
      setTestingId(null);
    }
  }, []);

  const handleRemove = async (id: string) => {
    try {
      await fetch(`/api/integrations/${id}`, { method: 'DELETE' });
    } catch {
      // silent
    }
    setIntegrations((prev) => prev.filter((i) => i.id !== id));
    toast.success('Integration removed');
  };

  const handleTestAll = async () => {
    for (const integration of integrations) {
      await handleTestConnection(integration);
    }
  };

  const activeCount = integrations.filter((i) => i.status === 'active').length;
  const errorCount = integrations.filter((i) => i.status === 'error').length;
  const pendingCount = integrations.filter((i) => i.status === 'pending').length;

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-orange-500/10 border border-orange-500/20 flex items-center justify-center">
              <Plug className="w-5 h-5 text-orange-400" />
            </div>
            Integrations
          </h1>
          <p className="text-orange-200/40 text-sm mt-1">
            Connect any platform with API keys. PARWA verifies each connector works properly.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {integrations.length > 0 && (
            <button
              onClick={handleTestAll}
              className="px-4 py-2 rounded-lg text-xs font-medium border border-orange-500/20 text-orange-400 hover:bg-orange-500/10 transition-all flex items-center gap-1.5"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Test All
            </button>
          )}
          <button
            onClick={() => setShowAddForm(!showAddForm)}
            className="px-4 py-2 rounded-lg text-xs font-semibold bg-gradient-to-r from-orange-500 to-amber-400 text-[#1A1A1A] hover:from-orange-400 hover:to-amber-300 transition-all flex items-center gap-1.5 shadow-lg shadow-orange-500/20"
          >
            <Plus className="w-3.5 h-3.5" />
            Add Integration
          </button>
        </div>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-3 gap-3">
        <div className="rounded-xl border border-emerald-500/20 p-4" style={{ background: 'rgba(16,185,129,0.04)' }}>
          <p className="text-[10px] text-orange-200/30 uppercase tracking-wider">Active</p>
          <p className="text-xl font-bold text-emerald-400">{activeCount}</p>
        </div>
        <div className="rounded-xl border border-red-500/20 p-4" style={{ background: 'rgba(239,68,68,0.04)' }}>
          <p className="text-[10px] text-orange-200/30 uppercase tracking-wider">Errors</p>
          <p className="text-xl font-bold text-red-400">{errorCount}</p>
        </div>
        <div className="rounded-xl border border-amber-500/20 p-4" style={{ background: 'rgba(245,158,11,0.04)' }}>
          <p className="text-[10px] text-orange-200/30 uppercase tracking-wider">Pending</p>
          <p className="text-xl font-bold text-amber-400">{pendingCount}</p>
        </div>
      </div>

      {/* Add Integration Form */}
      {showAddForm && (
        <div className="rounded-xl border border-orange-500/20 p-5 space-y-4" style={{ background: 'rgba(255,127,17,0.04)' }}>
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-orange-400 flex items-center gap-2">
              <Plus className="w-4 h-4" /> New Integration
            </h3>
            <button onClick={resetForm} className="text-zinc-500 hover:text-zinc-300 text-xs">Cancel</button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {/* Name */}
            <div>
              <label className="text-[10px] text-orange-200/40 uppercase tracking-wider">Integration Name</label>
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="e.g. Stripe Payments"
                className="w-full h-10 mt-1 rounded-lg bg-white/[0.04] border border-white/[0.08] px-3 text-sm text-white placeholder-orange-200/20 focus:outline-none focus:border-orange-500/50"
              />
            </div>
            {/* Platform */}
            <div>
              <label className="text-[10px] text-orange-200/40 uppercase tracking-wider">Platform ID</label>
              <input
                type="text"
                value={newPlatform}
                onChange={(e) => setNewPlatform(e.target.value)}
                placeholder="e.g. stripe (auto-generated from name)"
                className="w-full h-10 mt-1 rounded-lg bg-white/[0.04] border border-white/[0.08] px-3 text-sm text-white placeholder-orange-200/20 focus:outline-none focus:border-orange-500/50"
              />
            </div>
          </div>

          {/* Auth Type Selector */}
          <div>
            <label className="text-[10px] text-orange-200/40 uppercase tracking-wider">Authentication Type</label>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 mt-1">
              {AUTH_TYPES.map((authType) => (
                <button
                  key={authType.value}
                  type="button"
                  onClick={() => {
                    setNewAuthType(authType.value);
                    setNewCredentials({});
                  }}
                  className={cn(
                    'p-2.5 rounded-lg border text-left transition-all',
                    newAuthType === authType.value
                      ? 'border-orange-500/30 bg-orange-500/10'
                      : 'border-white/[0.06] hover:border-orange-500/15'
                  )}
                  style={newAuthType !== authType.value ? { background: 'rgba(255,255,255,0.03)' } : undefined}
                >
                  <p className="text-xs font-medium text-white">{authType.label}</p>
                  <p className="text-[9px] text-orange-200/30 mt-0.5">{authType.description}</p>
                </button>
              ))}
            </div>
          </div>

          {/* Dynamic Credential Fields */}
          <div className="space-y-2">
            {selectedAuthConfig.fields.map((field) => (
              <div key={field.name}>
                <label className="text-[10px] text-orange-200/40 uppercase tracking-wider">{field.label}</label>
                <div className="relative mt-1">
                  <input
                    type={showPasswords[field.name] ? 'text' : field.type}
                    value={newCredentials[field.name] || ''}
                    onChange={(e) => setNewCredentials((prev) => ({ ...prev, [field.name]: e.target.value }))}
                    placeholder={field.placeholder}
                    className="w-full h-10 rounded-lg bg-white/[0.04] border border-white/[0.08] px-3 pr-10 text-sm text-white placeholder-orange-200/20 focus:outline-none focus:border-orange-500/50"
                  />
                  {field.type === 'password' && (
                    <button
                      type="button"
                      onClick={() => setShowPasswords((prev) => ({ ...prev, [field.name]: !prev[field.name] }))}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-orange-200/30 hover:text-orange-200/60"
                    >
                      {showPasswords[field.name] ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Test URL */}
          <div>
            <label className="text-[10px] text-orange-200/40 uppercase tracking-wider">Test URL (optional — for verification)</label>
            <div className="flex gap-2 mt-1">
              <input
                type="url"
                value={newTestUrl}
                onChange={(e) => setNewTestUrl(e.target.value)}
                placeholder="https://api.example.com/v1/health"
                className="flex-1 h-10 rounded-lg bg-white/[0.04] border border-white/[0.08] px-3 text-sm text-white placeholder-orange-200/20 focus:outline-none focus:border-orange-500/50"
              />
              <select
                value={newTestMethod}
                onChange={(e) => setNewTestMethod(e.target.value as 'GET' | 'POST')}
                className="h-10 rounded-lg bg-white/[0.04] border border-white/[0.08] px-3 text-sm text-white focus:outline-none focus:border-orange-500/50"
              >
                <option value="GET">GET</option>
                <option value="POST">POST</option>
              </select>
            </div>
          </div>

          {/* Save Button */}
          <button
            onClick={handleAddIntegration}
            disabled={isSaving}
            className="w-full h-10 rounded-lg bg-gradient-to-r from-orange-500 to-amber-400 text-[#1A1A1A] font-semibold text-sm hover:from-orange-400 hover:to-amber-300 transition-all disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {isSaving ? (
              <><Loader2 className="w-4 h-4 animate-spin" /> Saving...</>
            ) : (
              <><KeyRound className="w-4 h-4" /> Save Integration</>
            )}
          </button>
        </div>
      )}

      {/* Integration List */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-orange-400" />
        </div>
      ) : integrations.length === 0 ? (
        <div className="text-center py-12 rounded-xl border border-white/[0.06]" style={{ background: 'rgba(255,255,255,0.02)' }}>
          <Plug className="w-12 h-12 mx-auto text-zinc-600 mb-3" />
          <p className="text-zinc-400 font-medium">No integrations yet</p>
          <p className="text-xs text-zinc-600 mt-1">Click &quot;Add Integration&quot; to connect your first platform</p>
        </div>
      ) : (
        <div className="space-y-3">
          {integrations.map((integration) => (
            <div
              key={integration.id}
              className="rounded-xl border p-4 transition-all"
              style={{
                background: 'rgba(255,255,255,0.03)',
                borderColor: integration.status === 'error' ? 'rgba(239,68,68,0.2)' : integration.testResult === 'success' ? 'rgba(16,185,129,0.2)' : 'rgba(255,255,255,0.06)',
              }}
            >
              <div className="flex items-start justify-between">
                <div className="flex items-start gap-3">
                  {/* Status icon */}
                  <div className={cn(
                    'w-8 h-8 rounded-lg flex items-center justify-center shrink-0 mt-0.5',
                    integration.status === 'active' ? 'bg-emerald-500/10' : integration.status === 'error' ? 'bg-red-500/10' : 'bg-amber-500/10'
                  )}>
                    {integration.status === 'active' ? (
                      integration.testResult === 'success' ? <CheckCircle2 className="w-4 h-4 text-emerald-400" /> : <Plug className="w-4 h-4 text-emerald-400" />
                    ) : integration.status === 'error' ? (
                      <XCircle className="w-4 h-4 text-red-400" />
                    ) : (
                      <AlertTriangle className="w-4 h-4 text-amber-400" />
                    )}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-semibold text-white">{integration.name}</p>
                      <span className={cn(
                        'text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-full',
                        integration.status === 'active' ? 'bg-emerald-500/10 text-emerald-400' : integration.status === 'error' ? 'bg-red-500/10 text-red-400' : 'bg-amber-500/10 text-amber-400'
                      )}>
                        {integration.status}
                      </span>
                      {integration.testResult && (
                        <span className={cn(
                          'text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-full',
                          integration.testResult === 'success' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'
                        )}>
                          {integration.testResult === 'success' ? 'Verified' : 'Failed'}
                        </span>
                      )}
                    </div>
                    <p className="text-[10px] text-orange-200/30 mt-0.5">
                      Platform: {integration.platform} · Auth: {AUTH_TYPES.find(a => a.value === integration.authType)?.label || integration.authType}
                      {integration.testedAt && <span> · Last tested: {new Date(integration.testedAt).toLocaleDateString()}</span>}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <button
                    onClick={() => handleTestConnection(integration)}
                    disabled={testingId === integration.id}
                    className="px-3 py-1.5 rounded-lg text-[10px] font-medium border border-orange-500/20 text-orange-400 hover:bg-orange-500/10 transition-all flex items-center gap-1 disabled:opacity-50"
                  >
                    {testingId === integration.id ? (
                      <><Loader2 className="w-3 h-3 animate-spin" /> Testing...</>
                    ) : (
                      <><TestTube className="w-3 h-3" /> Test</>
                    )}
                  </button>
                  <button
                    onClick={() => handleRemove(integration.id)}
                    className="p-1.5 rounded-lg text-zinc-500 hover:text-red-400 hover:bg-red-500/10 transition-all"
                    title="Remove integration"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
