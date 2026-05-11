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
} from 'lucide-react';
import toast from 'react-hot-toast';
import { integrationsApi, onboardingApi, getErrorMessage } from '@/lib/api';
import { cn } from '@/lib/utils';
import { Integration, IntegrationStatus } from '@/types/onboarding';

/**
 * Integration provider definition. Each provider has a unique key,
 * display name, category, icon component, and a list of credential
 * fields required for connection.
 */
interface IntegrationProvider {
  key: string;
  name: string;
  category: 'email' | 'helpdesk' | 'chat' | 'ecommerce' | 'custom';
  icon: React.ElementType;
  fields: { key: string; label: string; type: 'text' | 'password' }[];
}

const INTEGRATION_PROVIDERS: IntegrationProvider[] = [
  { key: 'gmail', name: 'Gmail', category: 'email', icon: Mail, fields: [{ key: 'api_key', label: 'OAuth Client Secret', type: 'password' }] },
  { key: 'outlook', name: 'Outlook', category: 'email', icon: Mail, fields: [{ key: 'api_key', label: 'Application Secret', type: 'password' }] },
  { key: 'brevo', name: 'Brevo', category: 'email', icon: Mail, fields: [{ key: 'api_key', label: 'API Key', type: 'password' }] },
  { key: 'sendgrid', name: 'SendGrid', category: 'email', icon: Mail, fields: [{ key: 'api_key', label: 'API Key', type: 'password' }] },
  { key: 'zendesk', name: 'Zendesk', category: 'helpdesk', icon: HeadphonesIcon, fields: [{ key: 'api_key', label: 'API Token', type: 'password' }, { key: 'subdomain', label: 'Subdomain', type: 'text' }] },
  { key: 'intercom', name: 'Intercom', category: 'helpdesk', icon: HeadphonesIcon, fields: [{ key: 'api_key', label: 'Access Token', type: 'password' }] },
  { key: 'freshdesk', name: 'Freshdesk', category: 'helpdesk', icon: HeadphonesIcon, fields: [{ key: 'api_key', label: 'API Key', type: 'password' }, { key: 'subdomain', label: 'Subdomain', type: 'text' }] },
  { key: 'helpscout', name: 'HelpScout', category: 'helpdesk', icon: HeadphonesIcon, fields: [{ key: 'api_key', label: 'App ID', type: 'password' }] },
  { key: 'slack', name: 'Slack', category: 'chat', icon: MessageSquare, fields: [{ key: 'api_key', label: 'Bot Token', type: 'password' }] },
  { key: 'whatsapp', name: 'WhatsApp', category: 'chat', icon: MessageSquare, fields: [{ key: 'api_key', label: 'API Key', type: 'password' }, { key: 'phone_number', label: 'Phone Number ID', type: 'text' }] },
  { key: 'discord', name: 'Discord', category: 'chat', icon: MessageSquare, fields: [{ key: 'api_key', label: 'Bot Token', type: 'password' }] },
  { key: 'shopify', name: 'Shopify', category: 'ecommerce', icon: ShoppingBag, fields: [{ key: 'api_key', label: 'Access Token', type: 'password' }, { key: 'subdomain', label: 'Store URL', type: 'text' }] },
  { key: 'woocommerce', name: 'WooCommerce', category: 'ecommerce', icon: ShoppingBag, fields: [{ key: 'api_key', label: 'Consumer Key', type: 'password' }, { key: 'subdomain', label: 'Store URL', type: 'text' }] },
  { key: 'custom_api', name: 'Custom API', category: 'custom', icon: Code, fields: [{ key: 'api_key', label: 'API Key', type: 'password' }, { key: 'subdomain', label: 'Endpoint URL', type: 'text' }] },
];

const CATEGORIES = [
  { key: 'email', label: 'Email', icon: Mail },
  { key: 'helpdesk', label: 'Helpdesk', icon: HeadphonesIcon },
  { key: 'chat', label: 'Chat', icon: MessageSquare },
  { key: 'ecommerce', label: 'E-commerce', icon: ShoppingBag },
  { key: 'custom', label: 'Custom', icon: Code },
] as const;

interface IntegrationStepProps {
  onNext: () => void;
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
export function IntegrationStep({ onNext }: IntegrationStepProps) {
  const [existingIntegrations, setExistingIntegrations] = useState<Integration[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [expandedProvider, setExpandedProvider] = useState<string | null>(null);
  const [formValues, setFormValues] = useState<Record<string, Record<string, string>>>({});
  const [showPasswords, setShowPasswords] = useState<Record<string, boolean>>({});
  const [connectingProvider, setConnectingProvider] = useState<string | null>(null);
  const [testingProvider, setTestingProvider] = useState<string | null>(null);
  const [showSkipWarning, setShowSkipWarning] = useState(false);

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

  const handleConnect = async (provider: IntegrationProvider) => {
    const values = formValues[provider.key] || {};
    const hasValues = provider.fields.some((f) => values[f.key]?.trim());
    if (!hasValues) {
      toast.error('Please fill in the required credentials');
      return;
    }

    setConnectingProvider(provider.key);
    try {
      const config: Record<string, unknown> = {};
      provider.fields.forEach((f) => {
        config[f.key] = values[f.key] || '';
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
      onNext();
    } catch (error) {
      toast.error(getErrorMessage(error));
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

      {/* Integration categories */}
      <div className="space-y-8">
        {CATEGORIES.map((category) => {
          const providers = INTEGRATION_PROVIDERS.filter((p) => p.category === category.key);
          const CatIcon = category.icon;

          return (
            <div key={category.key}>
              <div className="flex items-center gap-2 mb-3">
                <CatIcon className="w-4 h-4 text-orange-400" />
                <h3 className="text-sm font-semibold text-orange-200/60 uppercase tracking-wider">
                  {category.label}
                </h3>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {providers.map((provider) => {
                  const ProviderIcon = provider.icon;
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
                          <div className="w-9 h-9 rounded-lg bg-white/5 flex items-center justify-center flex-shrink-0">
                            <ProviderIcon className="w-4 h-4 text-orange-300/70" />
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

                      {/* Expanded inline form */}
                      {isExpanded && (
                        <div className="px-4 pb-4 border-t border-white/5 pt-4">
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                            {provider.fields.map((field) => (
                              <div key={field.key}>
                                <label className="label-parwa text-xs">
                                  {field.label}
                                </label>
                                <div className="relative">
                                  <input
                                    type={field.type === 'password' && !showPasswords[`${provider.key}-${field.key}`] ? 'password' : 'text'}
                                    value={formValues[provider.key]?.[field.key] || ''}
                                    onChange={(e) =>
                                      setFormValues((prev) => ({
                                        ...prev,
                                        [provider.key]: {
                                          ...prev[provider.key],
                                          [field.key]: e.target.value,
                                        },
                                      }))
                                    }
                                    placeholder={field.label}
                                    className="input-parwa text-sm"
                                  />
                                  {field.type === 'password' && (
                                    <button
                                      type="button"
                                      onClick={() =>
                                        setShowPasswords((prev) => ({
                                          ...prev,
                                          [`${provider.key}-${field.key}`]: !prev[`${provider.key}-${field.key}`],
                                        }))
                                      }
                                      className="absolute right-3 top-1/2 -translate-y-1/2 text-white/30 hover:text-white/60 transition-colors"
                                    >
                                      {showPasswords[`${provider.key}-${field.key}`] ? (
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
