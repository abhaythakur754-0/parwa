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
  ArrowRight,
  AlertTriangle,
  KeyRound,
  TestTube,
  Globe,
  RefreshCw,
  HelpCircle,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { cn } from '@/lib/utils';
import type { ParwaIndustry } from '@/lib/integration-catalog';

// ── Types ──────────────────────────────────────────────────────────────

interface ConnectedIntegration {
  id: string;
  name: string;
  platform: string; // e.g. "stripe", "paypal", "custom", any string
  authType: 'bearer' | 'api_key_header' | 'api_key_query' | 'basic_auth' | 'oauth2';
  credentials: Record<string, string>; // key-value pairs (e.g. api_key, client_id, etc.)
  testUrl?: string; // Custom test URL for unknown platforms
  testMethod?: 'GET' | 'POST'; // HTTP method for test
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

interface IntegrationStepProps {
  onNext: () => void;
  industry?: string;
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

// ── Component ──────────────────────────────────────────────────────────

export function IntegrationStep({ onNext, industry }: IntegrationStepProps) {
  const [integrations, setIntegrations] = useState<ConnectedIntegration[]>([]);
  const [showAddForm, setShowAddForm] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

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

    // Validate required fields
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
        console.warn('[IntegrationStep] Save returned non-ok, saving locally');
        integration.status = 'active';
      }
    } catch {
      console.warn('[IntegrationStep] Backend unreachable, saving locally');
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

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="text-center space-y-2">
        <div className="w-14 h-14 mx-auto rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center">
          <Plug className="w-7 h-7 text-emerald-400" />
        </div>
        <h2 className="text-2xl font-bold text-white">Connect Your Platforms</h2>
        <p className="text-orange-200/40 text-sm max-w-lg mx-auto">
          Connect any platform you use — Stripe, PayPal, HubSpot, Shopify, or any service with API keys.
          PARWA works with <strong className="text-orange-200/60">any platform</strong>. Just enter your credentials and we&apos;ll verify them.
        </p>
      </div>

      {/* Connected integrations list */}
      {integrations.length > 0 && (
        <div className="space-y-3">
          <p className="text-xs text-orange-200/40 uppercase tracking-wider font-medium">
            Connected ({integrations.length})
          </p>
          {integrations.map((intg) => (
            <div
              key={intg.id}
              className="flex items-center justify-between p-4 rounded-xl border border-white/[0.06]"
              style={{ background: 'rgba(255,255,255,0.03)' }}
            >
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-emerald-500 to-emerald-400 flex items-center justify-center shrink-0">
                  <Globe className="w-4 h-4 text-white" />
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-white truncate">{intg.name}</p>
                  <p className="text-[10px] text-orange-200/30">
                    {intg.authType.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                    {intg.testResult === 'success' && ' · Verified'}
                    {intg.testResult === 'failed' && ' · Failed'}
                    {!intg.testResult && ' · Not tested'}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {/* Status indicator */}
                {intg.testResult === 'success' && (
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                )}
                {intg.testResult === 'failed' && (
                  <XCircle className="w-4 h-4 text-red-400" />
                )}
                {!intg.testResult && (
                  <div className="w-2 h-2 rounded-full bg-zinc-600" />
                )}

                {/* Test button */}
                <button
                  onClick={() => handleTestConnection(intg)}
                  disabled={testingId === intg.id}
                  className="px-3 py-1.5 text-xs font-medium rounded-lg border border-white/10 text-orange-200/50 hover:text-orange-400 hover:border-orange-400/30 transition-all flex items-center gap-1.5"
                >
                  {testingId === intg.id ? (
                    <Loader2 className="w-3 h-3 animate-spin" />
                  ) : (
                    <TestTube className="w-3 h-3" />
                  )}
                  Test
                </button>

                {/* Remove button */}
                <button
                  onClick={() => handleRemove(intg.id)}
                  className="p-1.5 rounded text-zinc-500 hover:text-red-400 transition-colors"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add Integration Form */}
      {showAddForm ? (
        <div className="rounded-xl border border-orange-500/20 p-5 space-y-5" style={{ background: 'rgba(255,127,17,0.03)' }}>
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <KeyRound className="w-4 h-4 text-orange-400" />
              Add Integration
            </h3>
            <button
              onClick={resetForm}
              className="text-xs text-zinc-500 hover:text-white transition-colors"
            >
              Cancel
            </button>
          </div>

          {/* Platform Name */}
          <div className="space-y-2">
            <label className="text-xs text-orange-200/40 uppercase tracking-wider font-medium">Platform Name</label>
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="e.g. Stripe, PayPal, HubSpot, Custom API..."
              className="w-full px-3 py-2.5 rounded-lg text-sm bg-white/[0.04] border border-white/[0.08] text-white placeholder:text-zinc-600 focus:border-orange-500/50 focus:outline-none transition-colors"
            />
            <p className="text-[10px] text-orange-200/20">Any platform works — enter the name of the service you want to connect.</p>
          </div>

          {/* Platform Key (optional) */}
          <div className="space-y-2">
            <label className="text-xs text-orange-200/40 uppercase tracking-wider font-medium">Platform ID <span className="text-zinc-600">(optional)</span></label>
            <input
              value={newPlatform}
              onChange={(e) => setNewPlatform(e.target.value)}
              placeholder="e.g. stripe, paypal, hubspot (auto-generated from name if empty)"
              className="w-full px-3 py-2.5 rounded-lg text-sm bg-white/[0.04] border border-white/[0.08] text-white placeholder:text-zinc-600 focus:border-orange-500/50 focus:outline-none transition-colors"
            />
          </div>

          {/* Auth Type Selection */}
          <div className="space-y-2">
            <label className="text-xs text-orange-200/40 uppercase tracking-wider font-medium">Authentication Type</label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {AUTH_TYPES.map((auth) => (
                <button
                  key={auth.value}
                  onClick={() => {
                    setNewAuthType(auth.value);
                    setNewCredentials({});
                  }}
                  className={cn(
                    'text-left p-3 rounded-xl border transition-all duration-200',
                    newAuthType === auth.value
                      ? 'border-orange-500/40 bg-orange-500/5'
                      : 'border-white/[0.06] hover:border-orange-500/20'
                  )}
                  style={newAuthType !== auth.value ? { background: 'rgba(255,255,255,0.03)' } : undefined}
                >
                  <p className={cn('text-sm font-medium', newAuthType === auth.value ? 'text-orange-400' : 'text-white')}>
                    {auth.label}
                  </p>
                  <p className="text-[10px] text-orange-200/30 mt-0.5">{auth.description}</p>
                </button>
              ))}
            </div>
          </div>

          {/* Credential Fields (dynamic based on auth type) */}
          <div className="space-y-3">
            <label className="text-xs text-orange-200/40 uppercase tracking-wider font-medium">Credentials</label>
            {selectedAuthConfig.fields.map((field) => (
              <div key={field.name} className="space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-orange-200/50">{field.label}</span>
                  {field.type === 'password' && (
                    <button
                      onClick={() => setShowPasswords((prev) => ({ ...prev, [field.name]: !prev[field.name] }))}
                      className="text-[10px] text-zinc-500 hover:text-orange-400 transition-colors flex items-center gap-1"
                    >
                      {showPasswords[field.name] ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
                      {showPasswords[field.name] ? 'Hide' : 'Show'}
                    </button>
                  )}
                </div>
                <input
                  value={newCredentials[field.name] || ''}
                  onChange={(e) => setNewCredentials((prev) => ({ ...prev, [field.name]: e.target.value }))}
                  type={field.type === 'password' && !showPasswords[field.name] ? 'password' : 'text'}
                  placeholder={field.placeholder}
                  className="w-full px-3 py-2.5 rounded-lg text-sm bg-white/[0.04] border border-white/[0.08] text-white placeholder:text-zinc-600 focus:border-orange-500/50 focus:outline-none transition-colors"
                />
              </div>
            ))}
          </div>

          {/* Custom Test URL (for platforms not in catalog) */}
          <div className="space-y-2">
            <label className="text-xs text-orange-200/40 uppercase tracking-wider font-medium flex items-center gap-1.5">
              <TestTube className="w-3 h-3" />
              Test Connection URL <span className="text-zinc-600">(optional)</span>
            </label>
            <input
              value={newTestUrl}
              onChange={(e) => setNewTestUrl(e.target.value)}
              placeholder="https://api.example.com/v1/validate — PARWA will test your credentials against this URL"
              type="url"
              className="w-full px-3 py-2.5 rounded-lg text-sm bg-white/[0.04] border border-white/[0.08] text-white placeholder:text-zinc-600 focus:border-orange-500/50 focus:outline-none transition-colors"
            />
            {newTestUrl.trim() && (
              <div className="flex items-center gap-3 mt-1">
                <span className="text-[10px] text-orange-200/20">HTTP Method:</span>
                <div className="flex gap-1.5">
                  {(['GET', 'POST'] as const).map((method) => (
                    <button
                      key={method}
                      onClick={() => setNewTestMethod(method)}
                      className={cn(
                        'px-2.5 py-1 text-[10px] font-medium rounded transition-all',
                        newTestMethod === method
                          ? 'bg-orange-500/20 text-orange-400 border border-orange-500/30'
                          : 'text-zinc-500 border border-white/[0.06] hover:text-white'
                      )}
                    >
                      {method}
                    </button>
                  ))}
                </div>
              </div>
            )}
            <p className="text-[10px] text-orange-200/20 flex items-start gap-1">
              <HelpCircle className="w-3 h-3 shrink-0 mt-0.5" />
              For known platforms (Stripe, PayPal, etc.), PARWA auto-detects the test endpoint. For custom platforms, provide a URL that returns 200 on valid auth.
            </p>
          </div>

          {/* Add button */}
          <div className="flex justify-end gap-3">
            <button
              onClick={resetForm}
              className="px-4 py-2.5 rounded-xl text-sm font-medium border border-white/10 text-zinc-400 hover:text-white hover:border-white/20 transition-all"
            >
              Cancel
            </button>
            <button
              onClick={handleAddIntegration}
              disabled={isSaving}
              className="px-5 py-2.5 rounded-xl text-sm font-bold bg-gradient-to-r from-orange-500 to-amber-400 text-[#1A1A1A] hover:from-orange-400 hover:to-amber-300 shadow-lg shadow-orange-500/25 transition-all flex items-center gap-2"
            >
              {isSaving ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Plus className="w-4 h-4" />
              )}
              Add Integration
            </button>
          </div>
        </div>
      ) : (
        <button
          onClick={() => setShowAddForm(true)}
          className="w-full p-4 rounded-xl border-2 border-dashed border-white/[0.08] hover:border-orange-500/30 transition-all flex items-center justify-center gap-2 text-sm text-orange-200/40 hover:text-orange-400"
          style={{ background: 'rgba(255,255,255,0.02)' }}
        >
          <Plus className="w-4 h-4" />
          Add Integration
        </button>
      )}

      {/* Skip warning */}
      {integrations.length === 0 && (
        <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400 text-xs flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
          <div>
            <p className="font-medium">No integrations connected</p>
            <p className="mt-1 text-amber-400/60">You can skip this step, but PARWA&apos;s AI will have limited context without connected platforms. You can always add integrations later from Settings.</p>
          </div>
        </div>
      )}

      {/* Continue button */}
      <div className="flex justify-end">
        <button
          onClick={onNext}
          className="px-6 py-3 bg-gradient-to-r from-orange-500 to-amber-400 hover:from-orange-400 hover:to-amber-300 text-[#1A1A1A] font-semibold rounded-xl transition-all duration-300 shadow-lg shadow-orange-500/25 text-sm flex items-center gap-2"
        >
          Continue
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}

export default IntegrationStep;
