'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
  Mail,
  HeadphonesIcon,
  MessageSquare,
  ShoppingBag,
  Code,
  ArrowRight,
  ArrowLeft,
  Loader2,
  CheckCircle,
  XCircle,
  Eye,
  EyeOff,
  Unplug,
  AlertTriangle,
  Zap,
  FileJson,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { integrationsApi, onboardingApi, getErrorMessage } from '@/lib/api';
import { cn } from '@/lib/utils';
import { Integration, IntegrationStatus } from '@/types/onboarding';
import {
  INTEGRATION_CATALOG,
  CATEGORY_META,
  getIntegrationsForIndustry,
  mapIndustryToParwaIndustry,
  type IntegrationDefinition,
  type IntegrationCategory,
} from '@/lib/integration-catalog';
import { CustomConnectorForm } from './CustomConnectorForm';

// Category icon mapping
const CATEGORY_ICONS: Record<IntegrationCategory, React.ElementType> = {
  crm: HeadphonesIcon,
  ecommerce: ShoppingBag,
  helpdesk: HeadphonesIcon,
  communication: MessageSquare,
  analytics: Code,
  marketing: Mail,
  payments: Code,
  shipping: ShoppingBag,
  dev_tools: Code,
  productivity: Code,
  custom: Code,
};

interface IntegrationStepProps {
  onNext: () => void;
  /** Current industry from onboarding — used to filter suggested integrations */
  industry?: string;
}

/**
 * IntegrationStep Component (Step 3)
 *
 * Displays a grid of integration provider cards organized by category.
 * Users can connect to external services by clicking "Connect" on a
 * provider card, which reveals an inline form with credential inputs.
 * Each connection can be tested, and status indicators show whether
 * the connection is pending, active, or in an error state. The step
 * allows skipping with a warning about limited AI functionality.
 */
export function IntegrationStep({ onNext, industry }: IntegrationStepProps) {
  const [existingIntegrations, setExistingIntegrations] = useState<Integration[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Get industry-filtered integrations from the unified catalog
  const parwaIndustry = industry ? mapIndustryToParwaIndustry(industry) : 'other';
  const filteredCatalog = getIntegrationsForIndustry(parwaIndustry);

  // Group by category in display order
  const orderedCategories = Object.entries(CATEGORY_META)
    .filter(([key]) => filteredCatalog.some((i) => i.category === key))
    .sort(([, a], [, b]) => a.order - b.order);
  const [expandedProvider, setExpandedProvider] = useState<string | null>(null);
  const [formValues, setFormValues] = useState<Record<string, Record<string, string>>>({});
  const [showPasswords, setShowPasswords] = useState<Record<string, boolean>>({});
  const [connectingProvider, setConnectingProvider] = useState<string | null>(null);
  const [testingProvider, setTestingProvider] = useState<string | null>(null);
  const [showSkipWarning, setShowSkipWarning] = useState(false);
  const [showCustomForm, setShowCustomForm] = useState<'custom' | 'openapi' | null>(null);

  useEffect(() => {
    async function loadIntegrations() {
      try {
        const integrations = await integrationsApi.list();
        setExistingIntegrations(Array.isArray(integrations) ? integrations : []);
      } catch {
        setExistingIntegrations([]);
      } finally {
        setIsLoading(false);
      }
    }
    loadIntegrations();
  }, []);

  const getIntegrationStatus = useCallback(
    (providerKey: string): IntegrationStatus | null => {
      const integration = existingIntegrations.find((i) => i.type === providerKey);
      return integration?.status || null;
    },
    [existingIntegrations]
  );

  const handleConnect = async (provider: IntegrationDefinition) => {
    const values = formValues[provider.key] || {};
    const requiredFields = provider.authSchema.fields.filter((f) => f.required);
    const hasAllRequired = requiredFields.every((f) => values[f.name]?.trim());
    if (!hasAllRequired) {
      toast.error('Please fill in all required credentials');
      return;
    }

    setConnectingProvider(provider.key);
    try {
      const config: Record<string, unknown> = {};
      provider.authSchema.fields.forEach((f) => {
        config[f.name] = values[f.name] || '';
      });

      await integrationsApi.create({
        type: provider.key,
        name: provider.name,
        config,
      });

      const updated = await integrationsApi.list();
      setExistingIntegrations(Array.isArray(updated) ? updated : []);
      toast.success(`${provider.name} connected successfully`);
      setExpandedProvider(null);
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setConnectingProvider(null);
    }
  };

  const handleTest = async (providerKey: string) => {
    const integration = existingIntegrations.find((i) => i.type === providerKey);
    if (!integration) return;

    setTestingProvider(providerKey);
    try {
      await integrationsApi.test(integration.id);
      const updated = await integrationsApi.list();
      setExistingIntegrations(Array.isArray(updated) ? updated : []);
      toast.success(`${providerKey} connection test passed`);
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setTestingProvider(null);
    }
  };

  const handleContinue = async () => {
    try {
      await onboardingApi.completeStep(3);
    } catch (error) {
      console.warn('Step 3 complete API failed, continuing locally:', error);
    }
    // Always advance — never block on API failure
    onNext();
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
      <div className="text-center mb-10">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-orange-500/10 border border-orange-500/20 mb-6">
          <Unplug className="w-8 h-8 text-orange-400" />
        </div>
        <h2 className="text-2xl sm:text-3xl font-bold text-white mb-3">
          Connect Your Tools
        </h2>
        <p className="text-orange-200/50 text-sm max-w-lg mx-auto">
          Integrate your existing support channels and tools so PARWA can start handling tickets automatically.
          You can always add more integrations later from your dashboard settings.
        </p>
      </div>

      {/* Integration categories — filtered by industry */}
      <div className="space-y-8">
        {orderedCategories.map(([catKey, catMeta]) => {
          const providers = filteredCatalog.filter((p) => p.category === catKey);
          const CatIcon = CATEGORY_ICONS[catKey as IntegrationCategory] || Code;

          return (
            <div key={catKey}>
              <div className="flex items-center gap-2 mb-3">
                <CatIcon className="w-4 h-4 text-orange-400" />
                <h3 className="text-sm font-semibold text-orange-200/60 uppercase tracking-wider">
                  {catMeta.label}
                </h3>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {providers.map((provider) => {
                  const status = getIntegrationStatus(provider.key);
                  const isExpanded = expandedProvider === provider.key;
                  const isConnecting = connectingProvider === provider.key;
                  const isTesting = testingProvider === provider.key;

                  return (
                    <div
                      key={provider.key}
                      className={cn(
                        'card-parwa transition-all duration-300',
                        isExpanded ? 'col-span-2 sm:col-span-3' : ''
                      )}
                    >
                      {/* Provider card (collapsed) */}
                      <div className="p-4 flex items-center justify-between gap-3">
                        <div className="flex items-center gap-3 min-w-0">
                          <div className={cn('w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 bg-gradient-to-br', provider.colorGradient)}>
                            <span className="text-white text-xs font-bold">{provider.name.charAt(0)}</span>
                          </div>
                          <span className="text-sm font-medium text-white truncate">
                            {provider.name}
                          </span>
                          {status && (
                            <span
                              className={cn(
                                'inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full',
                                status === 'active' && 'bg-green-500/10 text-green-400',
                                status === 'pending' && 'bg-yellow-500/10 text-yellow-400',
                                status === 'error' && 'bg-red-500/10 text-red-400'
                              )}
                            >
                              {status === 'active' && <CheckCircle className="w-3 h-3" />}
                              {status === 'pending' && <Loader2 className="w-3 h-3 animate-spin" />}
                              {status === 'error' && <XCircle className="w-3 h-3" />}
                              {status}
                            </span>
                          )}
                        </div>

                        <button
                          type="button"
                          onClick={() => setExpandedProvider(isExpanded ? null : provider.key)}
                          className={cn(
                            'rounded-lg px-3 py-1.5 text-xs font-semibold transition-all flex-shrink-0',
                            status === 'active'
                              ? 'bg-white/5 text-orange-200/60 hover:bg-white/10'
                              : 'bg-gradient-to-r from-orange-600 to-orange-500 text-white hover:from-orange-500 hover:to-orange-400 shadow-sm'
                          )}
                        >
                          {status === 'active' ? 'Connected' : isExpanded ? 'Cancel' : 'Connect'}
                        </button>
                      </div>

                      {/* Expanded inline form — uses catalog authSchema fields */}
                      {isExpanded && (
                        <div className="px-4 pb-4 border-t border-white/5 pt-4">
                          <p className="text-xs text-orange-200/40 mb-3">{provider.description}</p>
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                            {provider.authSchema.fields.map((field) => (
                              <div key={field.name}>
                                <label className="label-parwa text-xs">
                                  {field.label}
                                  {field.required && <span className="text-red-400 ml-1">*</span>}
                                </label>
                                <div className="relative">
                                  <input
                                    type={field.type === 'password' && !showPasswords[`${provider.key}-${field.name}`] ? 'password' : 'text'}
                                    value={formValues[provider.key]?.[field.name] || ''}
                                    onChange={(e) =>
                                      setFormValues((prev) => ({
                                        ...prev,
                                        [provider.key]: {
                                          ...prev[provider.key],
                                          [field.name]: e.target.value,
                                        },
                                      }))
                                    }
                                    placeholder={field.placeholder || field.label}
                                    className="input-parwa text-sm"
                                  />
                                  {field.type === 'password' && (
                                    <button
                                      type="button"
                                      onClick={() =>
                                        setShowPasswords((prev) => ({
                                          ...prev,
                                          [`${provider.key}-${field.name}`]: !prev[`${provider.key}-${field.name}`],
                                        }))
                                      }
                                      className="absolute right-3 top-1/2 -translate-y-1/2 text-white/30 hover:text-white/60 transition-colors"
                                    >
                                      {showPasswords[`${provider.key}-${field.name}`] ? (
                                        <EyeOff className="w-4 h-4" />
                                      ) : (
                                        <Eye className="w-4 h-4" />
                                      )}
                                    </button>
                                  )}
                                </div>
                              </div>
                            ))}
                          </div>

                          <div className="flex items-center gap-3 mt-4">
                            <button
                              type="button"
                              onClick={() => handleConnect(provider)}
                              disabled={isConnecting}
                              className="btn-primary-parwa py-2 px-4 text-sm"
                            >
                              {isConnecting ? (
                                <>
                                  <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                                  Connecting...
                                </>
                              ) : (
                                'Connect'
                              )}
                            </button>

                            {status && (
                              <button
                                type="button"
                                onClick={() => handleTest(provider.key)}
                                disabled={isTesting}
                                className="btn-secondary-parwa py-2 px-4 text-sm"
                              >
                                {isTesting ? (
                                  <>
                                    <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                                    Testing...
                                  </>
                                ) : (
                                  'Test Connection'
                                )}
                              </button>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>

      {/* Custom Connector & OpenAPI Import */}
      {!showCustomForm ? (
        <div className="mt-8 flex items-center gap-3">
          <button
            type="button"
            onClick={() => setShowCustomForm('custom')}
            className="flex items-center gap-2 py-2.5 px-4 rounded-xl border border-dashed border-white/10 text-sm text-white/40 hover:text-white/60 hover:border-white/20 transition-colors"
          >
            <Zap className="w-4 h-4" />
            Add Custom REST Connector
          </button>
          <button
            type="button"
            onClick={() => setShowCustomForm('openapi')}
            className="flex items-center gap-2 py-2.5 px-4 rounded-xl border border-dashed border-white/10 text-sm text-white/40 hover:text-white/60 hover:border-white/20 transition-colors"
          >
            <FileJson className="w-4 h-4" />
            Import OpenAPI Spec
          </button>
        </div>
      ) : (
        <div className="mt-8">
          <CustomConnectorForm
            mode={showCustomForm}
            onSaved={async () => {
              setShowCustomForm(null);
              const updated = await integrationsApi.list();
              setExistingIntegrations(Array.isArray(updated) ? updated : []);
            }}
            onClose={() => setShowCustomForm(null)}
          />
        </div>
      )}

      {/* Action buttons */}
      <div className="mt-10 flex items-center justify-center gap-3">
        <button
          type="button"
          onClick={() => setShowSkipWarning(true)}
          className="btn-ghost-parwa text-sm"
        >
          Skip for now
        </button>

        <button type="button" onClick={handleContinue} className="btn-primary-parwa py-2.5 px-5">
          Continue
          <ArrowRight className="w-4 h-4 ml-2" />
        </button>
      </div>

      {/* Skip warning modal */}
      {showSkipWarning && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
          onClick={() => setShowSkipWarning(false)}
        >
          <div
            className="card-elevated-parwa p-6 max-w-md w-full"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-yellow-500/10 flex items-center justify-center">
                <AlertTriangle className="w-5 h-5 text-yellow-400" />
              </div>
              <h3 className="text-lg font-bold text-white">Skip Integrations?</h3>
            </div>
            <p className="text-sm text-orange-200/50 mb-6">
              Without connecting at least one integration, your AI assistant will have limited functionality.
              It won&apos;t be able to receive or respond to customer tickets until you connect a support channel.
              You can always add integrations later from your dashboard settings.
            </p>
            <div className="flex items-center justify-end gap-3">
              <button
                type="button"
                onClick={() => setShowSkipWarning(false)}
                className="btn-secondary-parwa py-2 px-4 text-sm"
              >
                Go Back
              </button>
              <button
                type="button"
                onClick={async () => {
                  setShowSkipWarning(false);
                  await handleContinue();
                }}
                className="btn-primary-parwa py-2 px-4 text-sm"
              >
                Skip Anyway
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default IntegrationStep;
