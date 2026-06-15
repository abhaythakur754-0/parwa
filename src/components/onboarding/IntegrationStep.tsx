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
  ChevronDown,
  ChevronUp,
  Sparkles,
  Search,
} from 'lucide-react';
import { toast } from '@/lib/dynamic-toast';
import { cn } from '@/lib/utils';
import {
  INTEGRATION_CATALOG,
  CATEGORY_META,
  getIntegrationsForIndustry,
  getIntegrationsGroupedByCategory,
  getIntegrationByKey,
  type ParwaIndustry,
  type IntegrationDefinition,
  type IntegrationCategory,
  type AuthType,
} from '@/lib/integration-catalog';

// ── Types ──────────────────────────────────────────────────────────────

interface ConnectedIntegration {
  id: string;
  name: string;
  platform: string;
  authType: AuthType;
  credentials: Record<string, string>;
  testUrl?: string;
  testMethod?: 'GET' | 'POST';
  status: 'active' | 'error' | 'pending';
  testedAt?: string;
  testResult?: 'success' | 'failed';
  catalogKey?: string; // Link to catalog entry
}

interface IntegrationStepProps {
  onNext: () => void;
  industry?: string;
}

// ── Auth type configurations (for custom integrations) ──────────────────

const AUTH_TYPES: Array<{
  value: AuthType;
  label: string;
  description: string;
}> = [
  { value: 'bearer', label: 'Bearer Token', description: 'Authorization: Bearer {token}' },
  { value: 'api_key_header', label: 'API Key (Header)', description: 'Custom header with your API key' },
  { value: 'api_key_query', label: 'API Key (Query Param)', description: 'API key passed as a URL parameter' },
  { value: 'basic_auth', label: 'Basic Auth', description: 'Username and password authentication' },
  { value: 'oauth2', label: 'OAuth 2.0', description: 'Client credentials or refresh token flow' },
];

// ── Component ──────────────────────────────────────────────────────────

export function IntegrationStep({ onNext, industry }: IntegrationStepProps) {
  const [integrations, setIntegrations] = useState<ConnectedIntegration[]>([]);
  const [showAddForm, setShowAddForm] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [expandedCategory, setExpandedCategory] = useState<IntegrationCategory | 'custom' | null>(null);
  const [activeCatalogIntegration, setActiveCatalogIntegration] = useState<IntegrationDefinition | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  // Form state for catalog-based integration
  const [catalogCredentials, setCatalogCredentials] = useState<Record<string, string>>({});
  const [showPasswords, setShowPasswords] = useState<Record<string, boolean>>({});
  const [testingId, setTestingId] = useState<string | null>(null);

  // Form state for custom integration
  const [customName, setCustomName] = useState('');
  const [customPlatform, setCustomPlatform] = useState('');
  const [customAuthType, setCustomAuthType] = useState<AuthType>('bearer');
  const [customCredentials, setCustomCredentials] = useState<Record<string, string>>({});
  const [customTestUrl, setCustomTestUrl] = useState('');
  const [customTestMethod, setCustomTestMethod] = useState<'GET' | 'POST'>('GET');

  // Resolve industry for recommendations
  const parwaIndustry: ParwaIndustry = (industry as ParwaIndustry) || 'other';

  // Get recommended integrations grouped by category
  const recommendedGroups = getIntegrationsGroupedByCategory(parwaIndustry);
  const allCatalogKeys = new Set(integrations.filter((i) => i.catalogKey).map((i) => i.catalogKey));

  // Load existing integrations from backend
  useEffect(() => {
    async function load() {
      try {
        const res = await fetch('/api/integrations');
        if (res.ok) {
          const data = await res.json();
          if (Array.isArray(data)) {
            const loaded = data.map((i: Record<string, unknown>) => ({
              id: String(i.id || i.integration_id || ''),
              name: String(i.name || i.integration_type || ''),
              platform: String(i.integration_type || i.platform || ''),
              authType: (i.auth_type as AuthType) || 'bearer',
              credentials: (i.credentials as Record<string, string>) || {},
              testUrl: i.test_url ? String(i.test_url) : undefined,
              testMethod: (i.test_method as 'GET' | 'POST') || undefined,
              status: (i.status as ConnectedIntegration['status']) || 'active',
              testedAt: i.tested_at ? String(i.tested_at) : undefined,
              testResult: i.test_result as 'success' | 'failed' | undefined,
              catalogKey: i.catalog_key ? String(i.catalog_key) : undefined,
            }));
            setIntegrations(loaded);
          }
        }
      } catch {
        // Backend unavailable — start with empty list
      }
    }
    load();
  }, []);

  // Save integration count to localStorage whenever it changes
  useEffect(() => {
    try {
      const summary = {
        total: integrations.length,
        verified: integrations.filter((i) => i.testResult === 'success').length,
        pending: integrations.filter((i) => !i.testResult).length,
        failed: integrations.filter((i) => i.testResult === 'failed').length,
        names: integrations.map((i) => i.name),
        catalogKeys: integrations.filter((i) => i.catalogKey).map((i) => i.catalogKey),
        updatedAt: new Date().toISOString(),
      };
      localStorage.setItem('parwa_integrations_summary', JSON.stringify(summary));
    } catch {
      // ignore
    }
  }, [integrations]);

  // ── Catalog-based integration add ────────────────────────────────────

  const handleAddCatalogIntegration = async (def: IntegrationDefinition) => {
    // Validate required fields
    const missing = def.authSchema.fields.filter(
      (f) => f.required && !catalogCredentials[f.name]?.trim()
    );
    if (missing.length > 0) {
      toast.error(`Please fill in: ${missing.map((f) => f.label).join(', ')}`);
      return;
    }

    setIsSaving(true);

    const integration: ConnectedIntegration = {
      id: `int-${Date.now()}`,
      name: def.name,
      platform: def.key,
      authType: def.authSchema.type,
      credentials: { ...catalogCredentials },
      testUrl: undefined,
      testMethod: undefined,
      status: 'pending',
      catalogKey: def.key,
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
          catalog_key: integration.catalogKey,
          test_url: def.testConnection.urlTemplate,
          test_method: def.testConnection.method,
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
    setActiveCatalogIntegration(null);
    setCatalogCredentials({});
    setIsSaving(false);
    toast.success(`${def.name} added! Test the connection to verify it works.`);
  };

  // ── Custom integration add ───────────────────────────────────────────

  const handleAddCustomIntegration = async () => {
    if (!customName.trim()) {
      toast.error('Please enter a name for this integration');
      return;
    }

    // Get the auth config fields for custom
    const authConfig = getAuthFieldsForType(customAuthType);
    const missing = authConfig.filter(
      (f) => f.required && !customCredentials[f.name]?.trim()
    );
    if (missing.length > 0) {
      toast.error(`Please fill in: ${missing.map((f) => f.label).join(', ')}`);
      return;
    }

    setIsSaving(true);

    const integration: ConnectedIntegration = {
      id: `int-${Date.now()}`,
      name: customName.trim(),
      platform: customPlatform.trim() || customName.trim().toLowerCase().replace(/\s+/g, '_'),
      authType: customAuthType,
      credentials: { ...customCredentials },
      testUrl: customTestUrl.trim() || undefined,
      testMethod: customTestUrl.trim() ? customTestMethod : undefined,
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
    resetCustomForm();
    setIsSaving(false);
    toast.success(`${integration.name} added! Test the connection to verify.`);
  };

  // ── Test Connection ──────────────────────────────────────────────────

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
        setIntegrations((prev) =>
          prev.map((i) =>
            i.id === integration.id
              ? { ...i, testResult: success ? 'success' : 'failed', testedAt: new Date().toISOString(), status: success ? 'active' : 'error' }
              : i
          )
        );
        toast[success ? 'success' : 'error'](
          success
            ? `${integration.name} connected! API key verified.`
            : `Connection failed — ${data.message || 'check your credentials'}`
        );
      } else {
        setIntegrations((prev) =>
          prev.map((i) =>
            i.id === integration.id
              ? { ...i, testResult: 'failed', testedAt: new Date().toISOString(), status: 'error' }
              : i
          )
        );
        toast.error('Connection test failed — server error');
      }
    } catch {
      setIntegrations((prev) =>
        prev.map((i) =>
          i.id === integration.id
            ? { ...i, testResult: 'failed', testedAt: new Date().toISOString(), status: 'error' }
            : i
        )
      );
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

  const resetCustomForm = () => {
    setCustomName('');
    setCustomPlatform('');
    setCustomAuthType('bearer');
    setCustomCredentials({});
    setCustomTestUrl('');
    setCustomTestMethod('GET');
    setShowAddForm(false);
  };

  // ── Helper: get auth fields for a custom auth type ───────────────────

  function getAuthFieldsForType(authType: AuthType) {
    const map: Record<AuthType, Array<{ name: string; label: string; type: 'text' | 'password'; placeholder: string; required: boolean }>> = {
      bearer: [{ name: 'api_key', label: 'Token / API Key', type: 'password', placeholder: 'sk_live_xxx', required: true }],
      api_key_header: [
        { name: 'header_name', label: 'Header Name', type: 'text', placeholder: 'X-API-Key', required: true },
        { name: 'api_key', label: 'API Key', type: 'password', placeholder: 'your-api-key', required: true },
      ],
      api_key_query: [
        { name: 'param_name', label: 'Parameter Name', type: 'text', placeholder: 'api_key', required: true },
        { name: 'api_key', label: 'API Key', type: 'password', placeholder: 'your-api-key', required: true },
      ],
      basic_auth: [
        { name: 'username', label: 'Username / Key', type: 'text', placeholder: 'user@example.com', required: true },
        { name: 'password', label: 'Password / Secret', type: 'password', placeholder: 'your-password', required: true },
      ],
      oauth2: [
        { name: 'client_id', label: 'Client ID', type: 'text', placeholder: 'xxx.apps.googleusercontent.com', required: true },
        { name: 'client_secret', label: 'Client Secret', type: 'password', placeholder: 'GOCSPX-xxx', required: true },
        { name: 'refresh_token', label: 'Refresh Token', type: 'password', placeholder: '1//xxx', required: false },
      ],
    };
    return map[authType] || [];
  }

  // ── Compute stats ────────────────────────────────────────────────────

  const verifiedCount = integrations.filter((i) => i.testResult === 'success').length;
  const failedCount = integrations.filter((i) => i.testResult === 'failed').length;
  const untestedCount = integrations.filter((i) => !i.testResult).length;

  // ── Filter catalog by search ─────────────────────────────────────────

  const filteredCatalog = searchQuery.trim()
    ? INTEGRATION_CATALOG.filter(
        (i) =>
          i.available &&
          (i.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            i.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
            i.category.toLowerCase().includes(searchQuery.toLowerCase()))
      )
    : null;

  // ── Render ───────────────────────────────────────────────────────────

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="text-center space-y-2">
        <div className="w-14 h-14 mx-auto rounded-2xl bg-orange-500/10 border border-orange-500/20 flex items-center justify-center">
          <Plug className="w-7 h-7 text-orange-400" />
        </div>
        <h2 className="text-2xl font-bold text-white">Connect Your Platforms</h2>
        <p className="text-orange-200/40 text-sm max-w-lg mx-auto">
          Connect the tools you already use. PARWA verifies each connection so your AI assistant
          has real-time access to your data. <strong className="text-orange-200/60">Test each integration</strong> before proceeding.
        </p>
      </div>

      {/* Stats Row */}
      {integrations.length > 0 && (
        <div className="grid grid-cols-3 gap-3">
          <div className="rounded-xl border border-emerald-500/20 p-3 text-center" style={{ background: 'rgba(16,185,129,0.04)' }}>
            <p className="text-[10px] text-orange-200/30 uppercase tracking-wider">Verified</p>
            <p className="text-xl font-bold text-emerald-400">{verifiedCount}</p>
          </div>
          <div className="rounded-xl border border-red-500/20 p-3 text-center" style={{ background: 'rgba(239,68,68,0.04)' }}>
            <p className="text-[10px] text-orange-200/30 uppercase tracking-wider">Failed</p>
            <p className="text-xl font-bold text-red-400">{failedCount}</p>
          </div>
          <div className="rounded-xl border border-amber-500/20 p-3 text-center" style={{ background: 'rgba(245,158,11,0.04)' }}>
            <p className="text-[10px] text-orange-200/30 uppercase tracking-wider">Not Tested</p>
            <p className="text-xl font-bold text-amber-400">{untestedCount}</p>
          </div>
        </div>
      )}

      {/* Connected Integrations List */}
      {integrations.length > 0 && (
        <div className="space-y-3">
          <p className="text-xs text-orange-200/40 uppercase tracking-wider font-medium">
            Connected ({integrations.length})
          </p>
          {integrations.map((intg) => (
            <div
              key={intg.id}
              className="flex items-center justify-between p-4 rounded-xl border transition-all"
              style={{
                background: 'rgba(255,255,255,0.03)',
                borderColor: intg.testResult === 'success'
                  ? 'rgba(16,185,129,0.2)'
                  : intg.testResult === 'failed'
                  ? 'rgba(239,68,68,0.2)'
                  : 'rgba(255,255,255,0.06)',
              }}
            >
              <div className="flex items-center gap-3 min-w-0">
                <div className={cn(
                  'w-9 h-9 rounded-lg flex items-center justify-center shrink-0',
                  intg.testResult === 'success'
                    ? 'bg-emerald-500/10'
                    : intg.testResult === 'failed'
                    ? 'bg-red-500/10'
                    : 'bg-orange-500/10'
                )}>
                  {intg.testResult === 'success' ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  ) : intg.testResult === 'failed' ? (
                    <XCircle className="w-4 h-4 text-red-400" />
                  ) : (
                    <Globe className="w-4 h-4 text-orange-400" />
                  )}
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-white truncate">{intg.name}</p>
                  <p className="text-[10px] text-orange-200/30">
                    {intg.authType.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                    {intg.testResult === 'success' && ' · Verified'}
                    {intg.testResult === 'failed' && ' · Failed — check credentials'}
                    {!intg.testResult && ' · Not tested yet'}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {intg.testResult !== 'success' && (
                  <button
                    onClick={() => handleTestConnection(intg)}
                    disabled={testingId === intg.id}
                    className="px-3 py-1.5 text-xs font-medium rounded-lg border border-orange-500/20 text-orange-400 hover:bg-orange-500/10 transition-all flex items-center gap-1.5"
                  >
                    {testingId === intg.id ? (
                      <Loader2 className="w-3 h-3 animate-spin" />
                    ) : (
                      <TestTube className="w-3 h-3" />
                    )}
                    Test
                  </button>
                )}
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

      {/* ── Integration Catalog ──────────────────────────────────────── */}

      {/* If a specific catalog integration form is open */}
      {activeCatalogIntegration ? (
        <CatalogIntegrationForm
          definition={activeCatalogIntegration}
          credentials={catalogCredentials}
          setCredentials={setCatalogCredentials}
          showPasswords={showPasswords}
          setShowPasswords={setShowPasswords}
          onAdd={handleAddCatalogIntegration}
          onCancel={() => {
            setActiveCatalogIntegration(null);
            setCatalogCredentials({});
          }}
          isSaving={isSaving}
        />
      ) : showAddForm ? (
        /* Custom integration form */
        <CustomIntegrationForm
          name={customName}
          setName={setCustomName}
          platform={customPlatform}
          setPlatform={setCustomPlatform}
          authType={customAuthType}
          setAuthType={setCustomAuthType}
          credentials={customCredentials}
          setCredentials={setCustomCredentials}
          testUrl={customTestUrl}
          setTestUrl={setCustomTestUrl}
          testMethod={customTestMethod}
          setTestMethod={setCustomTestMethod}
          showPasswords={showPasswords}
          setShowPasswords={setShowPasswords}
          onAdd={handleAddCustomIntegration}
          onCancel={resetCustomForm}
          isSaving={isSaving}
          getAuthFieldsForType={getAuthFieldsForType}
        />
      ) : (
        /* ── Browse Catalog ─────────────────────────────────────────── */
        <div className="space-y-4">
          {/* Search Bar */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-orange-200/30" />
            <input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search integrations... (e.g. Stripe, Zendesk, Shopify)"
              className="w-full pl-10 pr-4 py-2.5 rounded-xl text-sm bg-white/[0.04] border border-white/[0.08] text-white placeholder:text-zinc-600 focus:border-orange-500/50 focus:outline-none transition-colors"
            />
          </div>

          {/* Recommended for your industry */}
          {!searchQuery.trim() && (
            <div className="p-3 rounded-xl border border-orange-500/20" style={{ background: 'rgba(255,127,17,0.04)' }}>
              <div className="flex items-center gap-2 mb-1">
                <Sparkles className="w-4 h-4 text-orange-400" />
                <p className="text-xs font-semibold text-orange-400">
                  Recommended for {parwaIndustry === 'other' ? 'your business' : parwaIndustry}
                </p>
              </div>
              <p className="text-[10px] text-orange-200/30">
                These integrations work best with your industry. You can connect any tool below.
              </p>
            </div>
          )}

          {/* Search Results */}
          {filteredCatalog ? (
            <div className="space-y-2">
              <p className="text-xs text-orange-200/40 uppercase tracking-wider font-medium">
                Search Results ({filteredCatalog.length})
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {filteredCatalog.map((def) => (
                  <CatalogCard
                    key={def.key}
                    definition={def}
                    isConnected={allCatalogKeys.has(def.key)}
                    onConnect={() => {
                      setActiveCatalogIntegration(def);
                      setCatalogCredentials({});
                    }}
                  />
                ))}
              </div>
              {filteredCatalog.length === 0 && (
                <div className="text-center py-6">
                  <p className="text-zinc-500 text-sm">No integrations found for &ldquo;{searchQuery}&rdquo;</p>
                  <button
                    onClick={() => setShowAddForm(true)}
                    className="mt-2 text-xs text-orange-400 hover:text-orange-300 transition-colors"
                  >
                    Add a custom integration instead
                  </button>
                </div>
              )}
            </div>
          ) : (
            /* Grouped by Category */
            <div className="space-y-2">
              {(Object.entries(CATEGORY_META) as [IntegrationCategory, { label: string; order: number }][])
                .sort((a, b) => a[1].order - b[1].order)
                .filter(([cat]) => {
                  const group = recommendedGroups[cat];
                  return group && group.length > 0;
                })
                .map(([cat, meta]) => {
                  const group = recommendedGroups[cat] || [];
                  const isExpanded = expandedCategory === cat;
                  // Show first 4 inline, rest in expanded
                  const visibleItems = isExpanded ? group : group.slice(0, 4);

                  return (
                    <div key={cat} className="rounded-xl border border-white/[0.06]" style={{ background: 'rgba(255,255,255,0.02)' }}>
                      <button
                        onClick={() => setExpandedCategory(isExpanded ? null : cat)}
                        className="w-full flex items-center justify-between p-3 hover:bg-white/[0.02] transition-colors"
                      >
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-semibold text-orange-200/60 uppercase tracking-wider">{meta.label}</span>
                          <span className="text-[10px] text-orange-200/20">({group.length})</span>
                        </div>
                        {isExpanded ? (
                          <ChevronUp className="w-4 h-4 text-orange-200/30" />
                        ) : (
                          <ChevronDown className="w-4 h-4 text-orange-200/30" />
                        )}
                      </button>
                      <div className="px-3 pb-3 grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {visibleItems.map((def) => (
                          <CatalogCard
                            key={def.key}
                            definition={def}
                            isConnected={allCatalogKeys.has(def.key)}
                            onConnect={() => {
                              setActiveCatalogIntegration(def);
                              setCatalogCredentials({});
                            }}
                          />
                        ))}
                      </div>
                      {!isExpanded && group.length > 4 && (
                        <div className="px-3 pb-3">
                          <button
                            onClick={() => setExpandedCategory(cat)}
                            className="text-[10px] text-orange-400/60 hover:text-orange-400 transition-colors"
                          >
                            +{group.length - 4} more in {meta.label}
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })}
            </div>
          )}

          {/* Custom Integration Button */}
          <button
            onClick={() => setShowAddForm(true)}
            className="w-full p-3 rounded-xl border-2 border-dashed border-white/[0.08] hover:border-orange-500/30 transition-all flex items-center justify-center gap-2 text-sm text-orange-200/40 hover:text-orange-400"
            style={{ background: 'rgba(255,255,255,0.02)' }}
          >
            <Plus className="w-4 h-4" />
            Add Custom Integration (Any API)
          </button>
        </div>
      )}

      {/* Skip warning */}
      {integrations.length === 0 && (
        <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400 text-xs flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
          <div>
            <p className="font-medium">No integrations connected</p>
            <p className="mt-1 text-amber-400/60">
              You can skip this step, but PARWA&apos;s AI will have limited context without connected platforms.
              You can always add integrations later from the Dashboard.
            </p>
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

// ── Sub-component: Catalog Card ────────────────────────────────────────

function CatalogCard({
  definition,
  isConnected,
  onConnect,
}: {
  definition: IntegrationDefinition;
  isConnected: boolean;
  onConnect: () => void;
}) {
  return (
    <div
      className={cn(
        'flex items-center justify-between p-3 rounded-lg border transition-all',
        isConnected
          ? 'border-emerald-500/20 bg-emerald-500/5'
          : 'border-white/[0.06] hover:border-orange-500/20 hover:bg-white/[0.03]'
      )}
    >
      <div className="flex items-center gap-2.5 min-w-0">
        <div className={cn('w-8 h-8 rounded-lg bg-gradient-to-br flex items-center justify-center text-white text-[10px] font-bold shrink-0', definition.colorGradient)}>
          {definition.name.charAt(0)}
        </div>
        <div className="min-w-0">
          <p className="text-xs font-medium text-white truncate">{definition.name}</p>
          <p className="text-[9px] text-orange-200/25 truncate">{definition.description}</p>
        </div>
      </div>
      {isConnected ? (
        <div className="flex items-center gap-1 shrink-0">
          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
          <span className="text-[9px] text-emerald-400 font-medium">Added</span>
        </div>
      ) : (
        <button
          onClick={onConnect}
          className="px-2.5 py-1 text-[10px] font-medium rounded-lg border border-orange-500/20 text-orange-400 hover:bg-orange-500/10 transition-all shrink-0 flex items-center gap-1"
        >
          <Plus className="w-3 h-3" />
          Connect
        </button>
      )}
    </div>
  );
}

// ── Sub-component: Catalog Integration Form ─────────────────────────────

function CatalogIntegrationForm({
  definition,
  credentials,
  setCredentials,
  showPasswords,
  setShowPasswords,
  onAdd,
  onCancel,
  isSaving,
}: {
  definition: IntegrationDefinition;
  credentials: Record<string, string>;
  setCredentials: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  showPasswords: Record<string, boolean>;
  setShowPasswords: React.Dispatch<React.SetStateAction<Record<string, boolean>>>;
  onAdd: (def: IntegrationDefinition) => void;
  onCancel: () => void;
  isSaving: boolean;
}) {
  return (
    <div className="rounded-xl border border-orange-500/20 p-5 space-y-5" style={{ background: 'rgba(255,127,17,0.03)' }}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={cn('w-10 h-10 rounded-lg bg-gradient-to-br flex items-center justify-center text-white text-sm font-bold', definition.colorGradient)}>
            {definition.name.charAt(0)}
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white">{definition.name}</h3>
            <p className="text-[10px] text-orange-200/30">{definition.description}</p>
          </div>
        </div>
        <button
          onClick={onCancel}
          className="text-xs text-zinc-500 hover:text-white transition-colors"
        >
          Cancel
        </button>
      </div>

      {/* Auth type badge */}
      <div className="flex items-center gap-2">
        <KeyRound className="w-3.5 h-3.5 text-orange-400" />
        <span className="text-[10px] text-orange-200/40 uppercase tracking-wider font-medium">
          {definition.authSchema.type.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())} Authentication
        </span>
      </div>

      {/* Credential Fields */}
      <div className="space-y-3">
        {definition.authSchema.fields.map((field) => (
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
              value={credentials[field.name] || ''}
              onChange={(e) => setCredentials((prev) => ({ ...prev, [field.name]: e.target.value }))}
              type={field.type === 'password' && !showPasswords[field.name] ? 'password' : 'text'}
              placeholder={field.placeholder || `Enter ${field.label}`}
              className="w-full px-3 py-2.5 rounded-lg text-sm bg-white/[0.04] border border-white/[0.08] text-white placeholder:text-zinc-600 focus:border-orange-500/50 focus:outline-none transition-colors"
            />
          </div>
        ))}
      </div>

      {/* Test info */}
      <div className="p-2.5 rounded-lg border border-white/[0.06]" style={{ background: 'rgba(255,255,255,0.02)' }}>
        <p className="text-[10px] text-orange-200/30 flex items-start gap-1.5">
          <TestTube className="w-3 h-3 shrink-0 mt-0.5 text-orange-400" />
          After adding, PARWA will test your credentials against {definition.name}&apos;s API to verify the connection works.
        </p>
      </div>

      {/* Buttons */}
      <div className="flex justify-end gap-3">
        <button
          onClick={onCancel}
          className="px-4 py-2.5 rounded-xl text-sm font-medium border border-white/10 text-zinc-400 hover:text-white hover:border-white/20 transition-all"
        >
          Cancel
        </button>
        <button
          onClick={() => onAdd(definition)}
          disabled={isSaving}
          className="px-5 py-2.5 rounded-xl text-sm font-bold bg-gradient-to-r from-orange-500 to-amber-400 text-[#1A1A1A] hover:from-orange-400 hover:to-amber-300 shadow-lg shadow-orange-500/25 transition-all flex items-center gap-2"
        >
          {isSaving ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Plus className="w-4 h-4" />
          )}
          Add {definition.name}
        </button>
      </div>
    </div>
  );
}

// ── Sub-component: Custom Integration Form ──────────────────────────────

function CustomIntegrationForm({
  name,
  setName,
  platform,
  setPlatform,
  authType,
  setAuthType,
  credentials,
  setCredentials,
  testUrl,
  setTestUrl,
  testMethod,
  setTestMethod,
  showPasswords,
  setShowPasswords,
  onAdd,
  onCancel,
  isSaving,
  getAuthFieldsForType,
}: {
  name: string;
  setName: (v: string) => void;
  platform: string;
  setPlatform: (v: string) => void;
  authType: AuthType;
  setAuthType: (v: AuthType) => void;
  credentials: Record<string, string>;
  setCredentials: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  testUrl: string;
  setTestUrl: (v: string) => void;
  testMethod: 'GET' | 'POST';
  setTestMethod: (v: 'GET' | 'POST') => void;
  showPasswords: Record<string, boolean>;
  setShowPasswords: React.Dispatch<React.SetStateAction<Record<string, boolean>>>;
  onAdd: () => void;
  onCancel: () => void;
  isSaving: boolean;
  getAuthFieldsForType: (authType: AuthType) => Array<{ name: string; label: string; type: 'text' | 'password'; placeholder: string; required: boolean }>;
}) {
  const authFields = getAuthFieldsForType(authType);

  return (
    <div className="rounded-xl border border-orange-500/20 p-5 space-y-5" style={{ background: 'rgba(255,127,17,0.03)' }}>
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-white flex items-center gap-2">
          <Globe className="w-4 h-4 text-orange-400" />
          Custom Integration
        </h3>
        <button
          onClick={onCancel}
          className="text-xs text-zinc-500 hover:text-white transition-colors"
        >
          Cancel
        </button>
      </div>

      {/* Platform Name */}
      <div className="space-y-2">
        <label className="text-xs text-orange-200/40 uppercase tracking-wider font-medium">Platform Name</label>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. Stripe, PayPal, Custom API..."
          className="w-full px-3 py-2.5 rounded-lg text-sm bg-white/[0.04] border border-white/[0.08] text-white placeholder:text-zinc-600 focus:border-orange-500/50 focus:outline-none transition-colors"
        />
      </div>

      {/* Platform Key */}
      <div className="space-y-2">
        <label className="text-xs text-orange-200/40 uppercase tracking-wider font-medium">
          Platform ID <span className="text-zinc-600">(optional)</span>
        </label>
        <input
          value={platform}
          onChange={(e) => setPlatform(e.target.value)}
          placeholder="Auto-generated from name if empty"
          className="w-full px-3 py-2.5 rounded-lg text-sm bg-white/[0.04] border border-white/[0.08] text-white placeholder:text-zinc-600 focus:border-orange-500/50 focus:outline-none transition-colors"
        />
      </div>

      {/* Auth Type */}
      <div className="space-y-2">
        <label className="text-xs text-orange-200/40 uppercase tracking-wider font-medium">Authentication Type</label>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {AUTH_TYPES.map((auth) => (
            <button
              key={auth.value}
              onClick={() => {
                setAuthType(auth.value);
                setCredentials({});
              }}
              className={cn(
                'text-left p-3 rounded-xl border transition-all duration-200',
                authType === auth.value
                  ? 'border-orange-500/40 bg-orange-500/5'
                  : 'border-white/[0.06] hover:border-orange-500/20'
              )}
              style={authType !== auth.value ? { background: 'rgba(255,255,255,0.03)' } : undefined}
            >
              <p className={cn('text-sm font-medium', authType === auth.value ? 'text-orange-400' : 'text-white')}>
                {auth.label}
              </p>
              <p className="text-[10px] text-orange-200/30 mt-0.5">{auth.description}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Credential Fields */}
      <div className="space-y-3">
        <label className="text-xs text-orange-200/40 uppercase tracking-wider font-medium">Credentials</label>
        {authFields.map((field) => (
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
              value={credentials[field.name] || ''}
              onChange={(e) => setCredentials((prev) => ({ ...prev, [field.name]: e.target.value }))}
              type={field.type === 'password' && !showPasswords[field.name] ? 'password' : 'text'}
              placeholder={field.placeholder}
              className="w-full px-3 py-2.5 rounded-lg text-sm bg-white/[0.04] border border-white/[0.08] text-white placeholder:text-zinc-600 focus:border-orange-500/50 focus:outline-none transition-colors"
            />
          </div>
        ))}
      </div>

      {/* Test URL */}
      <div className="space-y-2">
        <label className="text-xs text-orange-200/40 uppercase tracking-wider font-medium flex items-center gap-1.5">
          <TestTube className="w-3 h-3" />
          Test Connection URL <span className="text-zinc-600">(optional)</span>
        </label>
        <input
          value={testUrl}
          onChange={(e) => setTestUrl(e.target.value)}
          placeholder="https://api.example.com/v1/health — PARWA will test your credentials against this URL"
          type="url"
          className="w-full px-3 py-2.5 rounded-lg text-sm bg-white/[0.04] border border-white/[0.08] text-white placeholder:text-zinc-600 focus:border-orange-500/50 focus:outline-none transition-colors"
        />
        {testUrl.trim() && (
          <div className="flex items-center gap-3 mt-1">
            <span className="text-[10px] text-orange-200/20">HTTP Method:</span>
            <div className="flex gap-1.5">
              {(['GET', 'POST'] as const).map((method) => (
                <button
                  key={method}
                  onClick={() => setTestMethod(method)}
                  className={cn(
                    'px-2.5 py-1 text-[10px] font-medium rounded transition-all',
                    testMethod === method
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
      </div>

      {/* Buttons */}
      <div className="flex justify-end gap-3">
        <button
          onClick={onCancel}
          className="px-4 py-2.5 rounded-xl text-sm font-medium border border-white/10 text-zinc-400 hover:text-white hover:border-white/20 transition-all"
        >
          Cancel
        </button>
        <button
          onClick={onAdd}
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
  );
}

export default IntegrationStep;
