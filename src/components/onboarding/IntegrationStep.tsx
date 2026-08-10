'use client';

import React, { useState, useEffect, useMemo } from 'react';
import {
  Loader2, CheckCircle2, XCircle, ChevronDown, ChevronUp,
  Plug, Search, AlertTriangle, ShieldCheck, Plus,
  Sparkles, TrendingUp, CreditCard, Truck, Mail, MessageSquare,
  BarChart3, Users, ShoppingCart, RefreshCw,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { cn } from '@/lib/utils';
import {
  INTEGRATION_CATALOG,
  CATEGORY_META,
  type IntegrationDefinition,
  type IntegrationCategory,
  type AuthField,
} from '@/lib/integration-catalog';
import { getRecommendations, type IntegrationRecommendation } from '@/lib/integration-recommendations';
import { CustomIntegrationForm } from './CustomIntegrationForm';
import { NangoIntegrationsSection } from '@/components/integrations/NangoConnectButton';
import { useAuth } from '@/hooks/useAuth';

// ── Props ────────────────────────────────────────────────────────────

interface IntegrationStepProps {
  onNext: () => void;
  industry?: string;
}

interface ConnectedIntegration {
  id: string;
  integration_type: string;
  name: string | null;
  status: string;
  last_test_result?: string | null;
}

// ── Category icons ───────────────────────────────────────────────────

const CATEGORY_ICONS: Record<IntegrationCategory, string> = {
  crm: '🎯',
  ecommerce: '🛒',
  helpdesk: '🎫',
  communication: '💬',
  analytics: '📊',
  marketing: '📧',
  payments: '💳',
  shipping: '📦',
  dev_tools: '🔧',
  productivity: '📝',
  custom: '🔌',
};

// ── Component ────────────────────────────────────────────────────────

export function IntegrationStep({ onNext, industry }: IntegrationStepProps) {
  const { user } = useAuth();
  const userId = user?.id;
  const [existingIntegrations, setExistingIntegrations] = useState<ConnectedIntegration[]>([]);
  const [showRecommendations, setShowRecommendations] = useState(true); // default: show recommendations
  const [isLoading, setIsLoading] = useState(true);
  const [selectedCategory, setSelectedCategory] = useState<IntegrationCategory | 'all'>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedIntegration, setExpandedIntegration] = useState<string | null>(null);
  const [credentialValues, setCredentialValues] = useState<Record<string, Record<string, string>>>({});
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const [verifyResults, setVerifyResults] = useState<Record<string, { verified: boolean; message: string }>>({});
  const [showCustomForm, setShowCustomForm] = useState(false);
  
  // CRM Analyzer state
  const [crmAnalysis, setCrmAnalysis] = useState<any>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [hasAnalyzed, setHasAnalyzed] = useState(false);

  // Fetch existing integrations
  useEffect(() => {
    fetch('/api/integrations', { credentials: 'include' })
      .then((res) => res.ok ? res.json() : null)
      .then((data) => {
        const items = Array.isArray(data) ? data : (data?.items || []);
        setExistingIntegrations(items);
      })
      .catch(() => {})
      .finally(() => setIsLoading(false));
  }, []);

  // Filter integrations by category + search
  const filteredIntegrations = useMemo(() => {
    let list = INTEGRATION_CATALOG.filter(i => i.available !== false);
    if (selectedCategory !== 'all') {
      list = list.filter(i => i.category === selectedCategory);
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      list = list.filter(i => i.name.toLowerCase().includes(q) || i.description.toLowerCase().includes(q));
    }
    return list;
  }, [selectedCategory, searchQuery]);

  // Group by category
  const grouped = useMemo(() => {
    const groups: Record<string, IntegrationDefinition[]> = {};
    for (const integration of filteredIntegrations) {
      if (!groups[integration.category]) groups[integration.category] = [];
      groups[integration.category].push(integration);
    }
    // Sort categories by order
    return Object.entries(groups).sort((a, b) => {
      const orderA = CATEGORY_META[a[0] as IntegrationCategory]?.order ?? 99;
      const orderB = CATEGORY_META[b[0] as IntegrationCategory]?.order ?? 99;
      return orderA - orderB;
    });
  }, [filteredIntegrations]);

  // Check if an integration is already connected
  const getExistingStatus = (key: string): ConnectedIntegration | null => {
    return existingIntegrations.find((i) => i.integration_type === key) || null;
  };

  // Handle credential field change
  const handleFieldChange = (integrationKey: string, fieldName: string, value: string) => {
    setCredentialValues((prev) => ({
      ...prev,
      [integrationKey]: {
        ...(prev[integrationKey] || {}),
        [fieldName]: value,
      },
    }));
  };

  // Save & Verify integration
  const handleSaveAndVerify = async (integration: IntegrationDefinition) => {
    const values = credentialValues[integration.key] || {};
    const requiredFields = integration.authSchema.fields.filter(f => f.required);
    const missing = requiredFields.filter(f => !values[f.name]?.trim());

    if (missing.length > 0) {
      toast.error(`Please fill in: ${missing.map(f => f.label).join(', ')}`);
      return;
    }

    setSavingKey(integration.key);
    try {
      // Check if integration already exists
      const existing = getExistingStatus(integration.key);

      let integrationId = existing?.id;

      if (!integrationId) {
        // Create new integration
        const createRes = await fetch('/api/integrations', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({
            integration_type: integration.key,
            name: integration.name,
            config: values,
            validate_credentials: true,
          }),
        });

        if (!createRes.ok) {
          const err = await createRes.json().catch(() => ({}));
          throw new Error(err.detail || err.message || 'Failed to save integration');
        }

        const created = await createRes.json();
        integrationId = created.id;
      } else {
        // Update existing integration credentials
        const updateRes = await fetch(`/api/integrations/${integrationId}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({
            config: values,
          }),
        });

        if (!updateRes.ok) {
          throw new Error('Failed to update integration');
        }
      }

      // Test/verify the integration
      const testRes = await fetch(`/api/integrations/${integrationId}/test`, {
        method: 'POST',
        credentials: 'include',
      });

      const testData = await testRes.json().catch(() => ({}));

      if (testRes.ok && testData.success) {
        setVerifyResults((prev) => ({
          ...prev,
          [integration.key]: { verified: true, message: testData.message || 'Verified' },
        }));
        toast.success(`${integration.name} verified successfully!`);
      } else {
        setVerifyResults((prev) => ({
          ...prev,
          [integration.key]: { verified: false, message: testData.message || testData.error || 'Verification failed' },
        }));
        toast.error(`${integration.name} verification failed: ${testData.message || testData.error || 'Invalid credentials'}`);
      }

      // Refresh integrations list
      const refreshed = await fetch('/api/integrations', { credentials: 'include' });
      if (refreshed.ok) {
        const data = await refreshed.json();
        const items = Array.isArray(data) ? data : (data?.items || []);
        setExistingIntegrations(items);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to save integration');
    } finally {
      setSavingKey(null);
    }
  };

  // Continue button
  const handleContinue = async () => {
    const verifiedCount = Object.values(verifyResults).filter(r => r.verified).length;
    const connectedCount = existingIntegrations.length;

    if (connectedCount === 0) {
      toast.error('Please connect at least one integration to continue.');
      return;
    }

    if (verifiedCount === 0 && connectedCount > 0) {
      // Some integrations connected but none verified — warn but allow
      toast('Note: Some integrations are not verified. You can verify them later in Settings.', { icon: '⚠️' });
    }

    onNext();
  };

  // Run CRM Analysis - Fixed v2: Works without connected integrations
  const runCRMAnalysis = async () => {
    // Allow analysis even without connected integrations - 
    // AI will recommend what tools they need based on their profile
    console.log('[CRM Analyzer] Starting analysis...');
    setIsAnalyzing(true);
    
    try {
      const response = await fetch('/api/integrations/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          industry: industry || 'unknown',
          connected_count: existingIntegrations.length,
          integrations: existingIntegrations.map(i => i.integration_type),
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.message || `Analysis failed (${response.status})`);
      }

      const data = await response.json();
      setCrmAnalysis(data);
      setHasAnalyzed(true);
      
      if (data.recommendations?.length > 0) {
        toast.success(`Found ${data.recommendations.length} recommendations for you!`);
      } else {
        toast.success('Analysis complete! Your integration health looks good.');
      }
    } catch (error) {
      console.error('CRM Analysis error:', error);
      const message = error instanceof Error ? error.message : 'Failed to analyze';
      toast.error(`${message}. You can continue anyway.`);
    } finally {
      setIsAnalyzing(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-6 h-6 animate-spin text-orange-400" />
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto">
      {/* Header */}
      <div className="text-center mb-6">
        <div className="w-12 h-12 mx-auto rounded-xl bg-gradient-to-br from-orange-500/20 to-orange-600/10 border border-orange-500/20 flex items-center justify-center mb-3">
          <Plug className="w-6 h-6 text-orange-400" />
        </div>
        <h2 className="text-xl font-bold text-white">Connect Your Tools</h2>
        <p className="text-sm text-zinc-500 mt-1">
          Choose the tools your team uses. Enter credentials and verify to connect.
        </p>
      </div>

      {/* ── Smart Recommendations (from static mapping — no LLM needed) ── */}
      {(() => {
        const connectedTypes = existingIntegrations.map(i => i.integration_type);
        const recs = getRecommendations(connectedTypes, industry);
        if (recs.length === 0 || !showRecommendations) return null;
        return (
          <div className="mb-6 rounded-xl border border-orange-500/20 bg-orange-500/[0.04] p-4">
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-start gap-2.5">
                <Sparkles className="w-4 h-4 text-orange-400 mt-0.5 flex-shrink-0" />
                <div>
                  <div className="text-sm font-medium text-orange-300">Recommended for you</div>
                  <div className="text-[11px] text-zinc-500 mt-0.5">
                    Based on {connectedTypes.length > 0 ? `what you've connected (${connectedTypes.join(', ')})` : `your industry (${industry || 'general'})`}
                  </div>
                </div>
              </div>
              <button
                onClick={() => setShowRecommendations(false)}
                className="text-[11px] text-zinc-500 hover:text-zinc-300 transition-colors"
              >
                Dismiss
              </button>
            </div>
            <div className="space-y-2">
              {recs.slice(0, 4).map((rec: IntegrationRecommendation) => {
                const integ = INTEGRATION_CATALOG.find(i => i.key === rec.type);
                if (!integ) return null;
                const alreadyConnected = connectedTypes.includes(rec.type);
                return (
                  <div
                    key={rec.type}
                    className="flex items-center gap-3 p-2.5 rounded-lg bg-white/[0.02] border border-white/[0.05]"
                  >
                    <div
                      className="w-8 h-8 rounded-md flex items-center justify-center flex-shrink-0"
                      style={{ background: integ.gradient || 'linear-gradient(135deg, #f97316, #f59e0b)' }}
                    >
                      <Plug className="w-4 h-4 text-white" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-white">{integ.name}</span>
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-orange-500/15 text-orange-300">
                          {rec.popularity}% match
                        </span>
                      </div>
                      <div className="text-[11px] text-zinc-500 truncate">{rec.reason}</div>
                    </div>
                    {alreadyConnected ? (
                      <span className="text-[11px] text-emerald-400 flex items-center gap-1">
                        <CheckCircle2 className="w-3 h-3" /> Connected
                      </span>
                    ) : (
                      <span className="text-[11px] text-zinc-500">↓ Find below</span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        );
      })()}

      {/* OAuth Integrations (Nango) */}
      <div className="mb-6 rounded-xl border border-violet-500/10 bg-white/[0.01] p-4">
        <h3 className="text-xs font-medium text-violet-300 mb-3 flex items-center gap-2">
          <span className="text-violet-400">⚡</span>
          Secure OAuth Integrations
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-violet-500/10 text-violet-300 border border-violet-500/20">
            One-click connect
          </span>
        </h3>
        <NangoIntegrationsSection userId={userId} />
      </div>

      {/* API Key Integrations Header */}
      <div className="mb-3">
        <h3 className="text-xs font-medium text-orange-300 flex items-center gap-2">
          <span className="text-orange-400">🔑</span>
          API Key Integrations
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-orange-500/10 text-orange-300 border border-orange-500/20">
            Manual setup
          </span>
        </h3>
      </div>

      {/* Search */}
      <div className="relative mb-4">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search integrations..."
          className="w-full pl-9 pr-4 py-2.5 rounded-lg bg-white/[0.03] border border-white/[0.08] text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-orange-500/40 transition-colors"
        />
      </div>

      {/* Category tabs */}
      <div className="flex flex-wrap gap-2 mb-6">
        <button
          onClick={() => setSelectedCategory('all')}
          className={cn(
            'px-3 py-1.5 rounded-lg text-xs font-medium transition-colors',
            selectedCategory === 'all'
              ? 'bg-orange-500/20 text-orange-400 border border-orange-500/30'
              : 'bg-white/[0.03] text-zinc-400 border border-white/[0.06] hover:bg-white/[0.06]'
          )}
        >
          All
        </button>
        {Object.entries(CATEGORY_META).map(([cat, meta]) => (
          <button
            key={cat}
            onClick={() => setSelectedCategory(cat as IntegrationCategory)}
            className={cn(
              'px-3 py-1.5 rounded-lg text-xs font-medium transition-colors flex items-center gap-1.5',
              selectedCategory === cat
                ? 'bg-orange-500/20 text-orange-400 border border-orange-500/30'
                : 'bg-white/[0.03] text-zinc-400 border border-white/[0.06] hover:bg-white/[0.06]'
            )}
          >
            <span>{CATEGORY_ICONS[cat as IntegrationCategory]}</span>
            {meta.label}
          </button>
        ))}
      </div>

      {/* Integration list grouped by category */}
      <div className="space-y-6 mb-6">
        {grouped.map(([category, integrations]) => (
          <div key={category}>
            <h3 className="text-xs text-zinc-600 uppercase tracking-wider font-medium mb-3">
              {CATEGORY_ICONS[category as IntegrationCategory]} {CATEGORY_META[category as IntegrationCategory]?.label || category}
            </h3>
            <div className="space-y-2">
              {integrations.map((integration) => {
                const existing = getExistingStatus(integration.key);
                const isExpanded = expandedIntegration === integration.key;
                const verifyResult = verifyResults[integration.key];
                const isSaving = savingKey === integration.key;
                const values = credentialValues[integration.key] || {};

                return (
                  <div
                    key={integration.key}
                    className={cn(
                      'rounded-xl border overflow-hidden transition-all duration-200',
                      existing?.status === 'active' && verifyResult?.verified
                        ? 'border-emerald-500/20 bg-emerald-500/[0.02] hover:border-emerald-500/30'
                        : existing?.status === 'active'
                        ? 'border-amber-500/20 bg-amber-500/[0.02] hover:border-amber-500/30'
                        : 'border-white/[0.06] bg-white/[0.02] hover:border-white/[0.12] hover:bg-white/[0.03]'
                    )}
                  >
                    {/* Header row */}
                    <button
                      onClick={() => setExpandedIntegration(isExpanded ? null : integration.key)}
                      className="w-full flex items-center justify-between px-4 py-3.5 hover:bg-white/[0.02] transition-colors group"
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <span className="text-xl transition-transform group-hover:scale-110">{CATEGORY_ICONS[integration.category]}</span>
                        <div className="min-w-0 text-left">
                          <p className="text-sm font-medium text-white truncate">{integration.name}</p>
                          <p className="text-[10px] text-zinc-600 truncate">{integration.description}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        {/* Status badge */}
                        {existing?.status === 'active' && verifyResult?.verified && (
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1">
                            <CheckCircle2 className="w-3 h-3" /> Verified
                          </span>
                        )}
                        {existing?.status === 'active' && !verifyResult?.verified && (
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20 flex items-center gap-1">
                            <AlertTriangle className="w-3 h-3" /> Not Verified
                          </span>
                        )}
                        {isExpanded ? <ChevronUp className="w-4 h-4 text-zinc-500 transition-transform" /> : <ChevronDown className="w-4 h-4 text-zinc-500 transition-transform group-hover:text-zinc-400" />}
                      </div>
                    </button>

                    {/* Expanded credential form */}
                    {isExpanded && (
                      <div className="px-4 pb-4 pt-2 border-t border-white/[0.04] space-y-3">
                        {integration.authSchema.fields.map((field: AuthField) => (
                          <div key={field.name}>
                            <label className="text-[10px] text-zinc-500 uppercase tracking-wider font-medium block mb-1">
                              {field.label} {field.required && <span className="text-red-400">*</span>}
                            </label>
                            <input
                              type={field.type === 'password' ? 'password' : 'text'}
                              value={values[field.name] || ''}
                              onChange={(e) => handleFieldChange(integration.key, field.name, e.target.value)}
                              placeholder={field.placeholder || ''}
                              className="w-full px-3 py-2 rounded-lg bg-white/[0.03] border border-white/[0.08] text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-orange-500/40 transition-colors"
                            />
                          </div>
                        ))}

                        {/* Verify result message */}
                        {verifyResult && (
                          <div className={cn(
                            'rounded-lg px-3 py-2 text-xs',
                            verifyResult.verified
                              ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                              : 'bg-red-500/10 text-red-400 border border-red-500/20'
                          )}>
                            {verifyResult.verified ? '✓ ' : '✗ '}{verifyResult.message}
                          </div>
                        )}

                        {/* Save & Verify button */}
                        <button
                          onClick={() => handleSaveAndVerify(integration)}
                          disabled={isSaving}
                          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-orange-500/20 text-orange-400 text-xs font-medium border border-orange-500/30 hover:bg-orange-500/30 transition-colors disabled:opacity-50"
                        >
                          {isSaving ? (
                            <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Saving...</>
                          ) : (
                            <><ShieldCheck className="w-3.5 h-3.5" /> Save & Verify</>
                          )}
                        </button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      {/* Add Custom Integration button */}
      <div className="mb-6">
        <button
          onClick={() => setShowCustomForm(!showCustomForm)}
          className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-white/[0.03] border border-dashed border-white/[0.12] text-sm text-zinc-400 hover:text-white hover:bg-white/[0.06] transition-colors w-full justify-center"
        >
          <Plus className="w-4 h-4" />
          {showCustomForm ? 'Cancel Custom Integration' : 'Add Custom Integration + Category'}
        </button>
      </div>

      {/* Custom Integration Form */}
      {showCustomForm && (
        <div className="mb-6 rounded-xl bg-white/[0.02] border border-orange-500/15 p-5">
          <h3 className="text-sm font-semibold text-white mb-4">Create Custom Integration</h3>
          <CustomIntegrationForm
            onSaved={(newIntegration) => {
              setExistingIntegrations((prev) => [...prev, newIntegration]);
              setShowCustomForm(false);
              toast.success('Custom integration saved!');
            }}
          />
        </div>
      )}

      {/* CRM Analyzer - Smart Recommendations */}
      {existingIntegrations.length > 0 && (
        <div className="mb-6 rounded-xl bg-gradient-to-br from-orange-500/10 to-amber-500/5 border border-orange-500/20 p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-orange-400" />
              <h3 className="text-sm font-semibold text-white">Smart Recommendations</h3>
            </div>
            {!hasAnalyzed ? (
              <button
                onClick={runCRMAnalysis}
                disabled={isAnalyzing}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-orange-500/20 text-orange-400 text-xs font-medium border border-orange-500/30 hover:bg-orange-500/30 transition-colors disabled:opacity-50"
              >
                {isAnalyzing ? (
                  <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Analyzing...</>
                ) : (
                  <><TrendingUp className="w-3.5 h-3.5" /> Analyze My Setup</>
                )}
              </button>
            ) : (
              <button
                onClick={runCRMAnalysis}
                disabled={isAnalyzing}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/[0.05] text-zinc-400 text-xs font-medium border border-white/[0.08] hover:bg-white/[0.08] transition-colors disabled:opacity-50"
              >
                <RefreshCw className="w-3.5 h-3.5" /> Refresh
              </button>
            )}
          </div>

          {/* Loading State */}
          {isAnalyzing && (
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-xs text-zinc-400">
                <Loader2 className="w-4 h-4 animate-spin text-orange-400" />
                Analyzing your integrations with AI...
              </div>
              <div className="grid grid-cols-3 gap-2">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-16 rounded-lg bg-white/[0.03] animate-pulse" />
                ))}
              </div>
            </div>
          )}

          {/* Results */}
          {hasAnalyzed && crmAnalysis && !isAnalyzing && (
            <div className="space-y-4">
              {/* Data Profile Summary */}
              {crmAnalysis.data_profile && (
                <div className="grid grid-cols-4 gap-2 text-center">
                  <div className="rounded-lg bg-white/[0.03] p-2">
                    <Users className="w-4 h-4 text-blue-400 mx-auto mb-1" />
                    <p className="text-[10px] text-zinc-500">Contacts</p>
                    <p className="text-sm font-bold text-white">{crmAnalysis.data_profile.total_contacts?.toLocaleString() || 0}</p>
                  </div>
                  <div className="rounded-lg bg-white/[0.03] p-2">
                    <ShoppingCart className="w-4 h-4 text-green-400 mx-auto mb-1" />
                    <p className="text-[10px] text-zinc-500">Orders</p>
                    <p className="text-sm font-bold text-white">{crmAnalysis.data_profile.total_orders?.toLocaleString() || 0}</p>
                  </div>
                  <div className="rounded-lg bg-white/[0.03] p-2">
                    <BarChart3 className="w-4 h-4 text-purple-400 mx-auto mb-1" />
                    <p className="text-[10px] text-zinc-500">Deals</p>
                    <p className="text-sm font-bold text-white">{crmAnalysis.data_profile.total_deals?.toLocaleString() || 0}</p>
                  </div>
                  <div className="rounded-lg bg-white/[0.03] p-2">
                    <Plug className="w-4 h-4 text-orange-400 mx-auto mb-1" />
                    <p className="text-[10px] text-zinc-500">Connected</p>
                    <p className="text-sm font-bold text-white">{crmAnalysis.connected_integrations?.length || 0}</p>
                  </div>
                </div>
              )}

              {/* Recommendations */}
              {crmAnalysis.recommendations && crmAnalysis.recommendations.length > 0 && (
                <div>
                  <p className="text-xs text-zinc-400 mb-2">
                    💡 Based on your data, we recommend adding:
                  </p>
                  <div className="space-y-2">
                    {crmAnalysis.recommendations.slice(0, 4).map((rec: any, idx: number) => {
                      const priorityColors = {
                        high: 'border-red-500/30 bg-red-500/[0.05]',
                        medium: 'border-amber-500/30 bg-amber-500/[0.05]',
                        low: 'border-blue-500/30 bg-blue-500/[0.05]',
                      };
                      const priorityBadges = {
                        high: 'bg-red-500/10 text-red-400 border-red-500/20',
                        medium: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
                        low: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
                      };
                      
                      return (
                        <div
                          key={idx}
                          className={`rounded-lg border p-3 ${priorityColors[rec.priority as keyof typeof priorityColors] || priorityColors.medium}`}
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 mb-1">
                                <span className="text-sm font-medium text-white truncate">
                                  {rec.name || rec.integration_key}
                                </span>
                                <span className={`text-[9px] px-1.5 py-0.5 rounded-full border font-medium ${priorityBadges[rec.priority as keyof typeof priorityBadges] || priorityBadges.medium}`}>
                                  {rec.priority?.toUpperCase()}
                                </span>
                              </div>
                              <p className="text-[11px] text-zinc-400 line-clamp-2">
                                {rec.reason || rec.business_impact}
                              </p>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Analysis Summary */}
              {crmAnalysis.analysis_summary && (
                <div className="rounded-lg bg-white/[0.02] p-3 border border-white/[0.04]">
                  <p className="text-[11px] text-zinc-300 leading-relaxed">
                    {crmAnalysis.analysis_summary}
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Empty state (not yet analyzed) */}
          {!hasAnalyzed && !isAnalyzing && (
            <div className="text-center py-4">
              <p className="text-xs text-zinc-500 mb-2">
                Curious which integrations would work best together?
              </p>
              <p className="text-[10px] text-zinc-600">
                Our AI will analyze your setup and suggest improvements.
              </p>
            </div>
          )}
        </div>
      )}

      {/* Continue button */}
      <div className="flex justify-end">
        <button
          onClick={handleContinue}
          className="flex items-center gap-2 px-6 py-3 rounded-xl bg-gradient-to-r from-orange-500 to-amber-400 text-[#1A1A1A] text-sm font-bold shadow-lg shadow-orange-500/20 hover:shadow-orange-500/30 hover:-translate-y-0.5 transition-all"
        >
          Continue
        </button>
      </div>
    </div>
  );
}
