'use client';

/**
 * IntegrationStep — manual integration catalog.
 *
 * Used by /dashboard/integrations as the power-user path: browse the full
 * catalog, search, paste credentials, Save & Verify.
 *
 * NOTE: the guided / automatic path is SuperglueOnboardingFlow (onboarding
 * Step 2 + SuperglueIntegrationsSection on the dashboard). This component
 * intentionally contains NO analysis or recommendation UI — that lives in
 * StoredAnalysisCard / CRMAnalyzerCard so each surface has exactly one job.
 *
 * `focusKey` (optional): when the recommendation cards send a user here,
 * the search box is pre-filled with that integration's key.
 */

import React, { useState, useEffect, useMemo } from 'react';
import {
  Loader2, CheckCircle2, ChevronDown, ChevronUp,
  Plug, Search, AlertTriangle, ShieldCheck, Plus,
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
import { CustomIntegrationForm } from './CustomIntegrationForm';

// ── Props ────────────────────────────────────────────────────────────

interface IntegrationStepProps {
  focusKey?: string; // pre-fill search with this integration key
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

export function IntegrationStep({ focusKey }: IntegrationStepProps) {
  const [existingIntegrations, setExistingIntegrations] = useState<ConnectedIntegration[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedCategory, setSelectedCategory] = useState<IntegrationCategory | 'all'>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedIntegration, setExpandedIntegration] = useState<string | null>(null);
  const [credentialValues, setCredentialValues] = useState<Record<string, Record<string, string>>>({});
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const [verifyResults, setVerifyResults] = useState<Record<string, { verified: boolean; message: string }>>({});
  const [showCustomForm, setShowCustomForm] = useState(false);

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

  // Pre-fill search when a recommendation card points the user here
  useEffect(() => {
    if (focusKey) {
      setSearchQuery(focusKey);
      setSelectedCategory('all');
      setExpandedIntegration(null);
    }
  }, [focusKey]);

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

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-6 h-6 animate-spin text-orange-400" />
      </div>
    );
  }

  return (
    <div>
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
        {searchQuery && (
          <button
            onClick={() => setSearchQuery('')}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-[11px] text-zinc-500 hover:text-zinc-300"
          >
            Clear
          </button>
        )}
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
        {grouped.length === 0 && (
          <p className="text-sm text-zinc-500 text-center py-8">
            No integrations match &ldquo;{searchQuery}&rdquo;.
          </p>
        )}
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
    </div>
  );
}
