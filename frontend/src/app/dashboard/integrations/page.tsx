'use client';

import React, { useState, useEffect, useCallback } from 'react';
import toast from 'react-hot-toast';
import { cn } from '@/lib/utils';
import { getErrorMessage } from '@/lib/api';
import { integrationsApi } from '@/lib/integrations-api';
import type {
  Integration,
  AvailableIntegration,
  TestResult,
  CustomIntegration,
  DeliveryLog,
} from '@/lib/integrations-api';
import { getChannelConfig } from '@/lib/channels-api';
import type { ChannelConfig } from '@/lib/channels-api';

// ── Constants ─────────────────────────────────────────────────────────

const INTEGRATION_ICONS: Record<string, string> = {
  shopify: '🛒',
  slack: '💬',
  zendesk: '🎫',
  gmail: '📧',
  freshdesk: '🎧',
  intercom: '🟢',
  hubspot: '🟠',
  salesforce: '☁️',
  stripe: '💳',
  jira: '📋',
  github: '🐙',
  notion: '📓',
  custom: '🔗',
};

const CATEGORY_LABELS: Record<string, string> = {
  ecommerce: 'E-Commerce',
  communication: 'Communication',
  helpdesk: 'Help Desk',
  crm: 'CRM',
  productivity: 'Productivity',
  payments: 'Payments',
  developer: 'Developer Tools',
  custom: 'Custom',
};

type TabId = 'integrations' | 'custom' | 'health';

// ── Skeleton Loader ───────────────────────────────────────────────────

function Skeleton({ className }: { className?: string }) {
  return (
    <div className={cn('animate-pulse rounded-lg bg-white/[0.04]', className)} />
  );
}

function IntegrationCardSkeleton() {
  return (
    <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-5 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Skeleton className="w-10 h-10 rounded-lg" />
          <div className="space-y-2">
            <Skeleton className="w-24 h-4" />
            <Skeleton className="w-36 h-3" />
          </div>
        </div>
        <Skeleton className="w-14 h-5 rounded-full" />
      </div>
      <Skeleton className="w-full h-3" />
      <div className="flex items-center justify-between pt-3 border-t border-white/[0.04]">
        <Skeleton className="w-16 h-3" />
        <Skeleton className="w-20 h-3" />
      </div>
    </div>
  );
}

// ── Status Dot ─────────────────────────────────────────────────────────

function StatusDot({ status, errorCount }: { status: string; errorCount: number }) {
  if (errorCount > 0) {
    return (
      <span className="flex items-center gap-1.5">
        <span className="w-2 h-2 rounded-full bg-red-400 pulse-live" />
        <span className="text-xs font-medium text-red-400">Errors</span>
      </span>
    );
  }
  if (status === 'connected' || status === 'active') {
    return (
      <span className="flex items-center gap-1.5">
        <span className="w-2 h-2 rounded-full bg-emerald-400" />
        <span className="text-xs font-medium text-emerald-400">Connected</span>
      </span>
    );
  }
  return (
    <span className="flex items-center gap-1.5">
      <span className="w-2 h-2 rounded-full bg-zinc-600" />
      <span className="text-xs font-medium text-zinc-500">Disconnected</span>
    </span>
  );
}

// ── Integration Card (I1) ─────────────────────────────────────────────

function IntegrationCard({
  integration,
  onClick,
}: {
  integration: Integration;
  onClick: () => void;
}) {
  const icon = INTEGRATION_ICONS[integration.integration_type] || '🔌';
  const lastSync = integration.last_sync_at
    ? new Date(integration.last_sync_at).toLocaleDateString()
    : 'Never';

  return (
    <button
      onClick={onClick}
      className="w-full text-left rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-5 transition-all duration-200 hover:border-white/[0.12] hover:bg-[#1E1E1E] group"
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <span className="text-2xl">{icon}</span>
          <div>
            <h3 className="text-sm font-semibold text-white group-hover:text-[#FF7F11] transition-colors">
              {integration.name}
            </h3>
            <p className="text-xs text-zinc-500 mt-0.5 capitalize">{integration.integration_type}</p>
          </div>
        </div>
        <StatusDot status={integration.status} errorCount={integration.error_count} />
      </div>
      <p className="text-xs text-zinc-400 mb-1">Last sync: {lastSync}</p>
      {integration.error_count > 0 && (
        <p className="text-xs text-red-400">{integration.error_count} errors</p>
      )}
    </button>
  );
}

// ── Connect New Modal (I2) ────────────────────────────────────────────

function ConnectModal({
  available,
  onClose,
  onConnected,
}: {
  available: AvailableIntegration[];
  onClose: () => void;
  onConnected: () => void;
}) {
  const [step, setStep] = useState<'pick' | 'configure'>('pick');
  const [selected, setSelected] = useState<AvailableIntegration | null>(null);
  const [credentials, setCredentials] = useState<Record<string, string>>({});
  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [search, setSearch] = useState('');

  const filtered = available.filter(
    (a) =>
      a.name.toLowerCase().includes(search.toLowerCase()) ||
      a.category.toLowerCase().includes(search.toLowerCase()),
  );

  const handleSelect = (item: AvailableIntegration) => {
    setSelected(item);
    setStep('configure');
    setCredentials({});
    setTestResult(null);
  };

  const handleTest = async () => {
    if (!selected) return;
    try {
      setTesting(true);
      const result = await integrationsApi.testCredentials({
        integration_type: selected.type,
        credentials,
      });
      setTestResult(result);
      if (result.success) {
        toast.success('Connection test passed!');
      } else {
        toast.error(result.message);
      }
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setTesting(false);
    }
  };

  const handleSave = async () => {
    if (!selected) return;
    try {
      setSaving(true);
      await integrationsApi.create({
        integration_type: selected.type,
        name: selected.name,
        credentials,
      });
      toast.success(`${selected.name} connected successfully`);
      onConnected();
      onClose();
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  // ── Credential fields for common types ──────────────────────────────

  const getCredentialFields = (): { key: string; label: string; placeholder: string }[] => {
    if (!selected) return [];
    switch (selected.type) {
      case 'slack':
        return [
          { key: 'bot_token', label: 'Bot Token', placeholder: 'xoxb-...' },
          { key: 'signing_secret', label: 'Signing Secret', placeholder: 'Enter signing secret' },
        ];
      case 'shopify':
        return [
          { key: 'shop_domain', label: 'Shop Domain', placeholder: 'your-store.myshopify.com' },
          { key: 'access_token', label: 'Access Token', placeholder: 'shpat_...' },
        ];
      case 'zendesk':
        return [
          { key: 'subdomain', label: 'Subdomain', placeholder: 'yourcompany' },
          { key: 'email', label: 'API Email', placeholder: 'admin@yourcompany.com' },
          { key: 'token', label: 'API Token', placeholder: 'Enter token' },
        ];
      case 'gmail':
        return [
          { key: 'client_id', label: 'Client ID', placeholder: 'Enter OAuth client ID' },
          { key: 'client_secret', label: 'Client Secret', placeholder: 'Enter client secret' },
          { key: 'refresh_token', label: 'Refresh Token', placeholder: 'Enter refresh token' },
        ];
      case 'freshdesk':
        return [
          { key: 'domain', label: 'Domain', placeholder: 'yourcompany.freshdesk.com' },
          { key: 'api_key', label: 'API Key', placeholder: 'Enter API key' },
        ];
      case 'intercom':
        return [
          { key: 'access_token', label: 'Access Token', placeholder: 'Enter access token' },
        ];
      case 'hubspot':
        return [
          { key: 'access_token', label: 'Access Token', placeholder: 'Enter access token' },
        ];
      case 'salesforce':
        return [
          { key: 'client_id', label: 'Client ID', placeholder: 'Enter client ID' },
          { key: 'client_secret', label: 'Client Secret', placeholder: 'Enter client secret' },
          { key: 'instance_url', label: 'Instance URL', placeholder: 'https://yourinstance.salesforce.com' },
        ];
      default:
        return [
          { key: 'api_key', label: 'API Key', placeholder: 'Enter API key' },
          { key: 'api_secret', label: 'API Secret', placeholder: 'Enter API secret (optional)' },
        ];
    }
  };

  const credentialFields = getCredentialFields();

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-xl rounded-2xl bg-[#1A1A1A] border border-white/[0.06] shadow-2xl max-h-[85vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-white/[0.06]">
          <h2 className="text-base font-semibold text-white">
            {step === 'pick' ? 'Add Integration' : `Connect ${selected?.name}`}
          </h2>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-zinc-500 hover:text-white hover:bg-white/[0.06] transition-colors"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-5">
          {step === 'pick' && (
            <>
              {/* Search */}
              <div className="relative mb-4">
                <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z" />
                </svg>
                <input
                  type="text"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search integrations..."
                  className="w-full pl-10 pr-4 py-2.5 rounded-lg bg-white/[0.04] border border-white/[0.06] text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-[#FF7F11]/40"
                />
              </div>
              {/* Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {filtered.map((item) => {
                  const icon = INTEGRATION_ICONS[item.type] || '🔌';
                  return (
                    <button
                      key={item.type}
                      onClick={() => handleSelect(item)}
                      className="flex items-center gap-3 p-4 rounded-xl border border-white/[0.06] bg-[#141414] hover:border-[#FF7F11]/30 hover:bg-[#1A1A1A] transition-all text-left group"
                    >
                      <span className="text-2xl">{item.icon || icon}</span>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <h3 className="text-sm font-semibold text-white group-hover:text-[#FF7F11] transition-colors truncate">
                            {item.name}
                          </h3>
                          <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-white/[0.06] text-zinc-500 uppercase tracking-wide shrink-0">
                            {item.auth_type}
                          </span>
                        </div>
                        <p className="text-xs text-zinc-500 mt-0.5 truncate">{item.description}</p>
                      </div>
                      <svg className="w-4 h-4 text-zinc-600 group-hover:text-zinc-400 shrink-0 transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="m8.25 4.5 7.5 7.5-7.5 7.5" />
                      </svg>
                    </button>
                  );
                })}
                {filtered.length === 0 && (
                  <div className="col-span-2 py-8 text-center text-sm text-zinc-500">
                    No integrations match your search.
                  </div>
                )}
              </div>
            </>
          )}

          {step === 'configure' && selected && (
            <div className="space-y-5">
              {/* Back */}
              <button
                onClick={() => { setStep('pick'); setTestResult(null); }}
                className="flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5 8.25 12l7.5-7.5" />
                </svg>
                Back to list
              </button>

              {/* Provider info */}
              <div className="flex items-center gap-3 p-4 rounded-xl bg-[#141414] border border-white/[0.06]">
                <span className="text-3xl">{INTEGRATION_ICONS[selected.type] || '🔌'}</span>
                <div>
                  <h3 className="text-sm font-semibold text-white">{selected.name}</h3>
                  <p className="text-xs text-zinc-500">{selected.description}</p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-[#FF7F11]/10 text-[#FF7F11] uppercase tracking-wide">
                      {selected.auth_type}
                    </span>
                    <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-white/[0.06] text-zinc-500 uppercase tracking-wide">
                      {selected.category}
                    </span>
                  </div>
                </div>
              </div>

              {selected.auth_type === 'oauth' ? (
                /* OAuth flow */
                <div className="text-center py-6">
                  <p className="text-sm text-zinc-400 mb-4">
                    You&apos;ll be redirected to {selected.name} to authorize PARWA.
                  </p>
                  <a
                    href={`/api/integrations/oauth/${selected.type}`}
                    className="inline-flex items-center gap-2 px-6 py-2.5 rounded-lg bg-[#FF7F11] text-sm font-semibold text-white hover:bg-[#FF7F11]/90 transition-colors"
                  >
                    <span>{INTEGRATION_ICONS[selected.type]}</span>
                    Connect with {selected.name}
                  </a>
                </div>
              ) : (
                /* API Key / Webhook credentials form */
                <div className="space-y-3">
                  <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Credentials</h4>
                  {credentialFields.map((field) => (
                    <div key={field.key}>
                      <label className="block text-xs text-zinc-500 mb-1">{field.label}</label>
                      <input
                        type={field.key.toLowerCase().includes('secret') || field.key.toLowerCase().includes('token') ? 'password' : 'text'}
                        value={credentials[field.key] || ''}
                        onChange={(e) =>
                          setCredentials((prev) => ({ ...prev, [field.key]: e.target.value }))
                        }
                        placeholder={field.placeholder}
                        className="w-full px-3 py-2.5 rounded-lg bg-white/[0.04] border border-white/[0.06] text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-[#FF7F11]/40 font-mono"
                      />
                    </div>
                  ))}
                </div>
              )}

              {/* Test result */}
              {testResult && (
                <div
                  className={cn(
                    'p-3 rounded-lg border text-xs',
                    testResult.success
                      ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
                      : 'bg-red-500/10 border-red-500/20 text-red-400',
                  )}
                >
                  <div className="flex items-center gap-2 font-semibold">
                    {testResult.success ? '✅ Connection Successful' : '❌ Connection Failed'}
                    {testResult.latency_ms && (
                      <span className="text-zinc-500 ml-auto">{testResult.latency_ms}ms</span>
                    )}
                  </div>
                  <p className="mt-1 text-zinc-400">{testResult.message}</p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        {step === 'configure' && selected && selected.auth_type !== 'oauth' && (
          <div className="flex items-center justify-end gap-3 p-5 border-t border-white/[0.06]">
            <button
              onClick={onClose}
              className="px-4 py-2 rounded-lg text-sm text-zinc-400 hover:text-white transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleTest}
              disabled={testing || Object.keys(credentials).length === 0}
              className="px-4 py-2 rounded-lg text-sm font-medium text-zinc-300 border border-white/[0.1] hover:border-white/[0.2] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {testing ? 'Testing...' : 'Test Connection'}
            </button>
            <button
              onClick={handleSave}
              disabled={saving || !testResult?.success}
              className="px-4 py-2 rounded-lg text-sm font-semibold text-white bg-[#FF7F11] hover:bg-[#FF7F11]/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {saving ? 'Saving...' : 'Save'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Integration Detail Modal (I3) ─────────────────────────────────────

function DetailModal({
  integration,
  onClose,
  onDisconnect,
}: {
  integration: Integration;
  onClose: () => void;
  onDisconnect: () => void;
}) {
  const [testing, setTesting] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const icon = INTEGRATION_ICONS[integration.integration_type] || '🔌';

  const handleTest = async () => {
    try {
      setTesting(true);
      const result = await integrationsApi.test(integration.id);
      setTestResult(result);
      toast[result.success ? 'success' : 'error'](result.message);
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setTesting(false);
    }
  };

  const handleDisconnect = async () => {
    try {
      await integrationsApi.remove(integration.id);
      toast.success(`${integration.name} disconnected`);
      onDisconnect();
      onClose();
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-lg rounded-2xl bg-[#1A1A1A] border border-white/[0.06] shadow-2xl max-h-[85vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-white/[0.06]">
          <div className="flex items-center gap-3">
            <span className="text-2xl">{icon}</span>
            <div>
              <h2 className="text-base font-semibold text-white">{integration.name}</h2>
              <p className="text-xs text-zinc-500 capitalize">{integration.integration_type}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-zinc-500 hover:text-white hover:bg-white/[0.06] transition-colors"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {/* Status */}
          <div className="flex items-center justify-between p-4 rounded-xl bg-[#141414] border border-white/[0.06]">
            <div>
              <p className="text-xs text-zinc-500 mb-1">Status</p>
              <StatusDot status={integration.status} errorCount={integration.error_count} />
            </div>
            <div className="text-right">
              <p className="text-xs text-zinc-500 mb-1">Last Sync</p>
              <p className="text-sm text-zinc-300">
                {integration.last_sync_at
                  ? new Date(integration.last_sync_at).toLocaleString()
                  : 'Never'}
              </p>
            </div>
          </div>

          {/* Config (masked) */}
          <div>
            <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2">Configuration</h4>
            <div className="rounded-xl bg-[#141414] border border-white/[0.06] p-4 space-y-2">
              {Object.entries(integration.config || {}).map(([key, value]) => (
                <div key={key} className="flex items-center justify-between">
                  <span className="text-xs text-zinc-500 font-mono">{key}</span>
                  <span className="text-xs text-zinc-300 font-mono max-w-[200px] truncate">
                    {typeof value === 'string' && value.length > 8 ? '••••••••' : String(value)}
                  </span>
                </div>
              ))}
              {Object.keys(integration.config || {}).length === 0 && (
                <p className="text-xs text-zinc-600">No configuration stored</p>
              )}
            </div>
          </div>

          {/* Errors */}
          {integration.error_count > 0 && (
            <div className="p-4 rounded-xl bg-red-500/5 border border-red-500/20">
              <div className="flex items-center gap-2 mb-2">
                <svg className="w-4 h-4 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
                </svg>
                <span className="text-xs font-semibold text-red-400">{integration.error_count} errors recorded</span>
              </div>
              <p className="text-xs text-zinc-500">
                This integration has recorded sync errors. Test the connection or check your credentials.
              </p>
            </div>
          )}

          {/* Test result */}
          {testResult && (
            <div
              className={cn(
                'p-3 rounded-lg border text-xs',
                testResult.success
                  ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
                  : 'bg-red-500/10 border-red-500/20 text-red-400',
              )}
            >
              <div className="flex items-center gap-2 font-semibold">
                {testResult.success ? '✅ Test Passed' : '❌ Test Failed'}
                {testResult.latency_ms && (
                  <span className="text-zinc-500 ml-auto">{testResult.latency_ms}ms</span>
                )}
              </div>
              <p className="mt-1 text-zinc-400">{testResult.message}</p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-5 border-t border-white/[0.06]">
          <button
            onClick={() => setShowConfirm(true)}
            className="px-4 py-2 rounded-lg text-sm font-medium text-red-400 hover:text-red-300 hover:bg-red-500/10 transition-colors"
          >
            Disconnect
          </button>
          <div className="flex items-center gap-3">
            <button
              onClick={onClose}
              className="px-4 py-2 rounded-lg text-sm text-zinc-400 hover:text-white transition-colors"
            >
              Close
            </button>
            <button
              onClick={handleTest}
              disabled={testing}
              className="px-4 py-2 rounded-lg text-sm font-semibold text-white bg-[#FF7F11] hover:bg-[#FF7F11]/90 transition-colors disabled:opacity-50"
            >
              {testing ? 'Testing...' : 'Test Connection'}
            </button>
          </div>
        </div>
      </div>

      {/* Confirm disconnect */}
      {showConfirm && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/60">
          <div className="w-full max-w-sm rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-5 space-y-4">
            <h3 className="text-base font-semibold text-white">Disconnect {integration.name}?</h3>
            <p className="text-sm text-zinc-400">
              This will remove the integration and stop all sync operations. You can reconnect it later.
            </p>
            <div className="flex items-center justify-end gap-3">
              <button
                onClick={() => setShowConfirm(false)}
                className="px-4 py-2 rounded-lg text-sm text-zinc-400 hover:text-white transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleDisconnect}
                className="px-4 py-2 rounded-lg text-sm font-semibold text-white bg-red-500 hover:bg-red-600 transition-colors"
              >
                Disconnect
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Custom Webhook Form (I5) ──────────────────────────────────────────

function CustomWebhookForm({
  onSave,
  onCancel,
}: {
  onSave: () => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState('');
  const [url, setUrl] = useState('');
  const [secret, setSecret] = useState('');
  const [method, setMethod] = useState('POST');
  const [events, setEvents] = useState('ticket.created, ticket.resolved');
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    if (!name || !url) {
      toast.error('Name and URL are required');
      return;
    }
    try {
      setSaving(true);
      await integrationsApi.createCustom({
        name,
        integration_type: 'custom_webhook',
        endpoint_url: url,
        secret: secret || undefined,
        config: {
          method,
          events: events.split(',').map((e) => e.trim()).filter(Boolean),
        },
      });
      toast.success('Custom webhook created');
      onSave();
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-5 space-y-4">
      <div className="flex items-center gap-2">
        <span className="text-xl">🔗</span>
        <h3 className="text-sm font-semibold text-white">New Custom Webhook</h3>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label className="block text-xs text-zinc-500 mb-1">Name</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="My Webhook"
            className="w-full px-3 py-2.5 rounded-lg bg-white/[0.04] border border-white/[0.06] text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-[#FF7F11]/40"
          />
        </div>
        <div>
          <label className="block text-xs text-zinc-500 mb-1">HTTP Method</label>
          <select
            value={method}
            onChange={(e) => setMethod(e.target.value)}
            className="w-full px-3 py-2.5 rounded-lg bg-white/[0.04] border border-white/[0.06] text-sm text-white focus:outline-none focus:border-[#FF7F11]/40"
          >
            <option value="POST">POST</option>
            <option value="PUT">PUT</option>
            <option value="PATCH">PATCH</option>
          </select>
        </div>
      </div>

      <div>
        <label className="block text-xs text-zinc-500 mb-1">Endpoint URL</label>
        <input
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://your-server.com/webhook"
          className="w-full px-3 py-2.5 rounded-lg bg-white/[0.04] border border-white/[0.06] text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-[#FF7F11]/40 font-mono"
        />
      </div>

      <div>
        <label className="block text-xs text-zinc-500 mb-1">Secret (optional)</label>
        <input
          type="password"
          value={secret}
          onChange={(e) => setSecret(e.target.value)}
          placeholder="Shared secret for signature verification"
          className="w-full px-3 py-2.5 rounded-lg bg-white/[0.04] border border-white/[0.06] text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-[#FF7F11]/40 font-mono"
        />
      </div>

      <div>
        <label className="block text-xs text-zinc-500 mb-1">Events (comma-separated)</label>
        <input
          type="text"
          value={events}
          onChange={(e) => setEvents(e.target.value)}
          placeholder="ticket.created, ticket.resolved"
          className="w-full px-3 py-2.5 rounded-lg bg-white/[0.04] border border-white/[0.06] text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-[#FF7F11]/40 font-mono"
        />
      </div>

      <div className="flex items-center justify-end gap-3 pt-2">
        <button
          onClick={onCancel}
          className="px-4 py-2 rounded-lg text-sm text-zinc-400 hover:text-white transition-colors"
        >
          Cancel
        </button>
        <button
          onClick={handleSave}
          disabled={saving || !name || !url}
          className="px-4 py-2 rounded-lg text-sm font-semibold text-white bg-[#FF7F11] hover:bg-[#FF7F11]/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {saving ? 'Creating...' : 'Create Webhook'}
        </button>
      </div>
    </div>
  );
}

// ── Custom Integration Card (I5) ──────────────────────────────────────

function CustomIntegrationCard({
  webhook,
  onRefresh,
}: {
  webhook: CustomIntegration;
  onRefresh: () => void;
}) {
  const [logs, setLogs] = useState<DeliveryLog[]>([]);
  const [showLogs, setShowLogs] = useState(false);
  const [loadingLogs, setLoadingLogs] = useState(false);
  const [testing, setTesting] = useState(false);
  const [activating, setActivating] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [showDetail, setShowDetail] = useState(false);

  const statusColor =
    webhook.status === 'active'
      ? 'text-emerald-400 bg-emerald-500/10'
      : webhook.status === 'draft'
        ? 'text-yellow-400 bg-yellow-500/10'
        : 'text-zinc-500 bg-white/[0.04]';

  const loadLogs = async () => {
    try {
      setLoadingLogs(true);
      const data = await integrationsApi.getDeliveryLogs(webhook.id);
      setLogs(data);
    } catch (err) {
      console.error('Failed to load logs:', err);
    } finally {
      setLoadingLogs(false);
    }
  };

  const handleTest = async () => {
    try {
      setTesting(true);
      const result = await integrationsApi.testCustom(webhook.id);
      toast[result.success ? 'success' : 'error'](result.message);
      onRefresh();
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setTesting(false);
    }
  };

  const handleActivate = async () => {
    try {
      setActivating(true);
      await integrationsApi.activateCustom(webhook.id);
      toast.success('Webhook activated');
      onRefresh();
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setActivating(false);
    }
  };

  const handleDelete = async () => {
    try {
      setDeleting(true);
      await integrationsApi.removeCustom(webhook.id);
      toast.success('Webhook deleted');
      onRefresh();
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setDeleting(false);
    }
  };

  const toggleLogs = () => {
    if (!showLogs) loadLogs();
    setShowLogs(!showLogs);
  };

  return (
    <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] overflow-hidden">
      {/* Card header */}
      <div
        className="p-5 cursor-pointer hover:bg-[#1E1E1E] transition-colors"
        onClick={() => setShowDetail(!showDetail)}
      >
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <span className="text-xl">🔗</span>
            <div>
              <h3 className="text-sm font-semibold text-white">{webhook.name}</h3>
              <p className="text-xs text-zinc-500 font-mono mt-0.5 truncate max-w-[240px]">
                {webhook.endpoint_url || 'No URL'}
              </p>
            </div>
          </div>
          <span className={cn('text-[10px] font-semibold px-2 py-0.5 rounded-full uppercase tracking-wider', statusColor)}>
            {webhook.status}
          </span>
        </div>

        <div className="flex items-center gap-4 mt-3 text-xs text-zinc-500">
          <span>{webhook.config?.method || 'POST'}</span>
          <span>{webhook.error_count} errors</span>
          {webhook.last_test_at && (
            <span>Tested: {new Date(webhook.last_test_at).toLocaleDateString()}</span>
          )}
          {webhook.last_delivery_at && (
            <span>Last delivery: {new Date(webhook.last_delivery_at).toLocaleDateString()}</span>
          )}
        </div>
      </div>

      {/* Expanded actions */}
      {showDetail && (
        <div className="px-5 pb-4 space-y-3 border-t border-white/[0.04] pt-3">
          {/* 3-step workflow indicators */}
          <div className="flex items-center gap-2 mb-2">
            {['Create', 'Test', 'Activate'].map((step, i) => {
              const stepNum = i + 1;
              const done =
                (stepNum === 1) ||
                (stepNum === 2 && webhook.last_test_at) ||
                (stepNum === 3 && webhook.status === 'active');
              return (
                <div key={step} className="flex items-center gap-1.5">
                  <span
                    className={cn(
                      'w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold',
                      done
                        ? 'bg-[#FF7F11] text-white'
                        : 'bg-white/[0.06] text-zinc-600',
                    )}
                  >
                    {done ? '✓' : stepNum}
                  </span>
                  <span className={cn('text-[10px] font-medium', done ? 'text-zinc-300' : 'text-zinc-600')}>
                    {step}
                  </span>
                  {i < 2 && <span className="w-6 h-px bg-white/[0.06] mx-1" />}
                </div>
              );
            })}
          </div>

          <div className="flex flex-wrap gap-2">
            <button
              onClick={handleTest}
              disabled={testing}
              className="px-3 py-1.5 rounded-lg text-xs font-medium text-zinc-300 border border-white/[0.1] hover:border-[#FF7F11]/30 transition-colors disabled:opacity-50"
            >
              {testing ? 'Testing...' : 'Test'}
            </button>
            {webhook.status !== 'active' && (
              <button
                onClick={handleActivate}
                disabled={activating}
                className="px-3 py-1.5 rounded-lg text-xs font-semibold text-white bg-emerald-500 hover:bg-emerald-600 transition-colors disabled:opacity-50"
              >
                {activating ? 'Activating...' : 'Activate'}
              </button>
            )}
            <button
              onClick={toggleLogs}
              className="px-3 py-1.5 rounded-lg text-xs font-medium text-zinc-300 border border-white/[0.1] hover:border-white/[0.2] transition-colors"
            >
              {showLogs ? 'Hide Logs' : 'Delivery Logs'}
            </button>
            <button
              onClick={() => setShowDeleteConfirm(true)}
              className="px-3 py-1.5 rounded-lg text-xs font-medium text-red-400 hover:bg-red-500/10 transition-colors ml-auto"
            >
              Delete
            </button>
          </div>

          {/* Delivery logs */}
          {showLogs && (
            <div className="max-h-48 overflow-y-auto rounded-lg border border-white/[0.04]">
              {loadingLogs ? (
                <div className="p-3 space-y-2">
                  {[1, 2, 3].map((i) => (
                    <Skeleton key={i} className="w-full h-8" />
                  ))}
                </div>
              ) : logs.length === 0 ? (
                <div className="p-4 text-center text-xs text-zinc-500">No delivery logs yet</div>
              ) : (
                <table className="w-full text-xs">
                  <thead className="bg-white/[0.02]">
                    <tr>
                      <th className="text-left p-2 text-zinc-500 font-medium">Status</th>
                      <th className="text-left p-2 text-zinc-500 font-medium">Code</th>
                      <th className="text-left p-2 text-zinc-500 font-medium">Latency</th>
                      <th className="text-left p-2 text-zinc-500 font-medium">Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {logs.map((log) => (
                      <tr key={log.id} className="border-t border-white/[0.03]">
                        <td className="p-2">
                          <span
                            className={cn(
                              'inline-block w-2 h-2 rounded-full',
                              log.status_code && log.status_code >= 200 && log.status_code < 300
                                ? 'bg-emerald-400'
                                : 'bg-red-400',
                            )}
                          />
                        </td>
                        <td className="p-2 font-mono text-zinc-400">
                          {log.status_code ?? '—'}
                        </td>
                        <td className="p-2 font-mono text-zinc-400">
                          {log.latency_ms ? `${log.latency_ms}ms` : '—'}
                        </td>
                        <td className="p-2 text-zinc-500">
                          {new Date(log.created_at).toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}
        </div>
      )}

      {/* Delete confirm */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/60">
          <div className="w-full max-w-sm rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-5 space-y-4">
            <h3 className="text-base font-semibold text-white">Delete Webhook?</h3>
            <p className="text-sm text-zinc-400">
              This will permanently delete &ldquo;{webhook.name}&rdquo; and all its delivery logs.
            </p>
            <div className="flex items-center justify-end gap-3">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                className="px-4 py-2 rounded-lg text-sm text-zinc-400 hover:text-white transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="px-4 py-2 rounded-lg text-sm font-semibold text-white bg-red-500 hover:bg-red-600 transition-colors disabled:opacity-50"
              >
                {deleting ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Health Dashboard (I7) ─────────────────────────────────────────────

function HealthDashboard({
  integrations,
  customIntegrations,
}: {
  integrations: Integration[];
  customIntegrations: CustomIntegration[];
}) {
  const allIntegrations = [...integrations, ...customIntegrations];
  const connected = allIntegrations.filter(
    (i) => i.status === 'connected' || i.status === 'active',
  ).length;
  const withErrors = allIntegrations.filter((i) => i.error_count > 0).length;
  const total = allIntegrations.length;

  const healthStatus =
    withErrors > 0 ? 'warning' : connected > 0 ? 'healthy' : 'inactive';

  const healthColor =
    healthStatus === 'healthy'
      ? 'text-emerald-400'
      : healthStatus === 'warning'
        ? 'text-yellow-400'
        : 'text-zinc-500';

  const healthBg =
    healthStatus === 'healthy'
      ? 'bg-emerald-500/10 border-emerald-500/20'
      : healthStatus === 'warning'
        ? 'bg-yellow-500/10 border-yellow-500/20'
        : 'bg-white/[0.02] border-white/[0.06]';

  const healthLabel =
    healthStatus === 'healthy'
      ? 'All Systems Operational'
      : healthStatus === 'warning'
        ? 'Some Integrations Have Errors'
        : 'No Integrations Connected';

  const stats = [
    {
      label: 'Connected',
      value: connected,
      color: 'text-emerald-400',
      bgColor: 'bg-emerald-500/10',
    },
    {
      label: 'With Errors',
      value: withErrors,
      color: 'text-red-400',
      bgColor: 'bg-red-500/10',
    },
    {
      label: 'Total',
      value: total,
      color: 'text-zinc-300',
      bgColor: 'bg-white/[0.04]',
    },
  ];

  return (
    <div className="space-y-6">
      {/* Health indicator */}
      <div className={cn('rounded-xl border p-5', healthBg)}>
        <div className="flex items-center gap-3 mb-4">
          <span
            className={cn(
              'w-3 h-3 rounded-full',
              healthStatus === 'healthy'
                ? 'bg-emerald-400'
                : healthStatus === 'warning'
                  ? 'bg-yellow-400 pulse-live'
                  : 'bg-zinc-600',
            )}
          />
          <h3 className={cn('text-sm font-semibold', healthColor)}>{healthLabel}</h3>
        </div>
        <div className="grid grid-cols-3 gap-4">
          {stats.map((stat) => (
            <div key={stat.label} className={cn('rounded-lg p-3 text-center', stat.bgColor)}>
              <p className={cn('text-2xl font-bold', stat.color)}>{stat.value}</p>
              <p className="text-xs text-zinc-500 mt-0.5">{stat.label}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Integration health list */}
      {allIntegrations.length > 0 && (
        <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] overflow-hidden">
          <div className="p-4 border-b border-white/[0.06]">
            <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
              Integration Health Details
            </h4>
          </div>
          <div className="max-h-96 overflow-y-auto">
            {allIntegrations.map((integration) => {
              const icon = INTEGRATION_ICONS[integration.integration_type] || '🔌';
              const hasError = integration.error_count > 0;
              return (
                <div
                  key={integration.id}
                  className="flex items-center justify-between px-4 py-3 border-b border-white/[0.03] last:border-b-0 hover:bg-white/[0.02] transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-lg">{icon}</span>
                    <div>
                      <p className="text-sm font-medium text-white">{integration.name}</p>
                      <p className="text-xs text-zinc-500 capitalize">{integration.integration_type}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    {hasError && (
                      <span className="text-xs text-red-400 font-mono">{integration.error_count} errors</span>
                    )}
                    <StatusDot status={integration.status} errorCount={integration.error_count} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {allIntegrations.length === 0 && (
        <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-12 text-center">
          <span className="text-4xl mb-3 block">🔌</span>
          <h3 className="text-sm font-semibold text-zinc-300 mb-1">No integrations yet</h3>
          <p className="text-xs text-zinc-500">
            Connect your first integration to start seeing health metrics.
          </p>
        </div>
      )}
    </div>
  );
}

// ── Channel Quick Status (I6) ─────────────────────────────────────────

function ChannelQuickStatus({ configs }: { configs: ChannelConfig[] }) {
  const typeEmoji: Record<string, string> = {
    email: '📧',
    chat: '💬',
    sms: '📱',
    voice: '📞',
    whatsapp: '💬',
    messenger: '💬',
    twitter: '🐦',
    instagram: '📷',
    telegram: '✈️',
    slack: '💡',
    webchat: '🌐',
  };

  return (
    <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className="text-sm">📡</span>
          <h3 className="text-sm font-semibold text-white">Channel Quick Status</h3>
        </div>
        <a
          href="/dashboard/channels"
          className="text-xs font-medium text-[#FF7F11] hover:text-[#FF7F11]/80 transition-colors"
        >
          Manage Channels →
        </a>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {configs.slice(0, 8).map((ch) => (
          <div
            key={ch.channel_type}
            className="flex items-center gap-2 p-2 rounded-lg bg-[#141414]"
          >
            <span className="text-base">{typeEmoji[ch.channel_type] || '📡'}</span>
            <div>
              <p className="text-xs font-medium text-zinc-300 capitalize">{ch.channel_type}</p>
              <p className={cn('text-[10px]', ch.is_enabled ? 'text-emerald-400' : 'text-zinc-600')}>
                {ch.is_enabled ? 'Active' : 'Off'}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Webhook Deliveries Section (I4) ───────────────────────────────────

function WebhookDeliversSection() {
  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-white">Webhook Deliveries</h3>
      <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-8 text-center">
        <span className="text-2xl block mb-2">📬</span>
        <p className="text-sm text-zinc-300 mb-1">Delivery logs are tracked per integration</p>
        <p className="text-xs text-zinc-500">
          Webhook events are tracked per integration. See the <strong className="text-zinc-400">Custom Webhooks</strong> tab for individual delivery logs.
        </p>
      </div>
    </div>
  );
}

// ── Main Integrations Page ────────────────────────────────────────────

export default function IntegrationsPage() {
  const [activeTab, setActiveTab] = useState<TabId>('integrations');
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [available, setAvailable] = useState<AvailableIntegration[]>([]);
  const [customIntegrations, setCustomIntegrations] = useState<CustomIntegration[]>([]);
  const [channelConfigs, setChannelConfigs] = useState<ChannelConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [showConnectModal, setShowConnectModal] = useState(false);
  const [selectedIntegration, setSelectedIntegration] = useState<Integration | null>(null);
  const [showCustomForm, setShowCustomForm] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  // ── Load Data ───────────────────────────────────────────────────────

  const loadAll = useCallback(async () => {
    try {
      setLoading(true);
      const [ints, avails, customs, channels] = await Promise.allSettled([
        integrationsApi.list(),
        integrationsApi.getAvailable(),
        integrationsApi.listCustom(),
        getChannelConfig(),
      ]);
      if (ints.status === 'fulfilled') setIntegrations(ints.value);
      if (avails.status === 'fulfilled') setAvailable(avails.value);
      if (customs.status === 'fulfilled') setCustomIntegrations(customs.value);
      if (channels.status === 'fulfilled') setChannelConfigs(channels.value);
    } catch (err) {
      console.error('Failed to load integrations:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  // ── Filtered Integrations ───────────────────────────────────────────

  const filteredIntegrations = integrations.filter(
    (i) =>
      i.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      i.integration_type.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  // ── Tab Config ──────────────────────────────────────────────────────

  const tabs: { id: TabId; label: string; count?: number }[] = [
    { id: 'integrations', label: 'Integrations', count: integrations.length },
    { id: 'custom', label: 'Custom Webhooks', count: customIntegrations.length },
    { id: 'health', label: 'Health' },
  ];

  // ── Render ──────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen jarvis-page-body">
      <div className="p-6 lg:p-8 space-y-6">
        {/* ── Page Header ─────────────────────────────────────────────── */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-6 border-b border-white/[0.06]">
          <div>
            <h1 className="text-xl font-bold text-white">Integrations</h1>
            <p className="text-sm text-zinc-500 mt-0.5">
              Connect third-party apps and manage webhooks for your support workflow.
            </p>
          </div>
          <div className="flex items-center gap-2">
            {activeTab === 'integrations' && (
              <button
                onClick={() => setShowConnectModal(true)}
                className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-[#FF7F11] text-sm font-semibold text-white hover:bg-[#FF7F11]/90 transition-colors"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                </svg>
                Add Integration
              </button>
            )}
            {activeTab === 'custom' && (
              <button
                onClick={() => setShowCustomForm(!showCustomForm)}
                className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-[#FF7F11] text-sm font-semibold text-white hover:bg-[#FF7F11]/90 transition-colors"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                </svg>
                {showCustomForm ? 'Cancel' : 'New Webhook'}
              </button>
            )}
          </div>
        </div>

        {/* ── Tabs ───────────────────────────────────────────────────── */}
        <div className="flex items-center gap-1 p-1 rounded-lg bg-white/[0.03] w-fit">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                'px-4 py-2 rounded-md text-xs font-medium transition-all',
                activeTab === tab.id
                  ? 'bg-[#FF7F11] text-white shadow-sm'
                  : 'text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.04]',
              )}
            >
              {tab.label}
              {tab.count !== undefined && (
                <span
                  className={cn(
                    'ml-1.5 text-[10px] px-1.5 py-0.5 rounded-full',
                    activeTab === tab.id ? 'bg-white/20' : 'bg-white/[0.06]',
                  )}
                >
                  {tab.count}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* ── Tab: Integrations (I1, I2, I3) ─────────────────────────── */}
        {activeTab === 'integrations' && (
          <div className="space-y-6">
            {/* Search */}
            <div className="relative max-w-md">
              <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z" />
              </svg>
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search integrations..."
                className="w-full pl-10 pr-4 py-2.5 rounded-lg bg-white/[0.04] border border-white/[0.06] text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-[#FF7F11]/40"
              />
            </div>

            {/* Integration Grid */}
            {loading ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
                {[1, 2, 3, 4, 5, 6].map((i) => (
                  <IntegrationCardSkeleton key={i} />
                ))}
              </div>
            ) : filteredIntegrations.length === 0 ? (
              <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-12 text-center">
                <span className="text-4xl block mb-3">🔌</span>
                <h3 className="text-sm font-semibold text-zinc-300 mb-1">
                  {searchQuery ? 'No integrations found' : 'No integrations connected'}
                </h3>
                <p className="text-xs text-zinc-500 mb-4">
                  {searchQuery
                    ? 'Try a different search term.'
                    : 'Connect your first integration to extend PARWA\'s capabilities.'}
                </p>
                {!searchQuery && (
                  <button
                    onClick={() => setShowConnectModal(true)}
                    className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[#FF7F11] text-sm font-semibold text-white hover:bg-[#FF7F11]/90 transition-colors"
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                    </svg>
                    Add Your First Integration
                  </button>
                )}
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
                {filteredIntegrations.map((integration) => (
                  <IntegrationCard
                    key={integration.id}
                    integration={integration}
                    onClick={() => setSelectedIntegration(integration)}
                  />
                ))}
              </div>
            )}

            {/* Webhook Deliveries (I4) */}
            {integrations.length > 0 && (
              <WebhookDeliversSection />
            )}

            {/* Channel Quick Status (I6) */}
            {channelConfigs.length > 0 && (
              <ChannelQuickStatus configs={channelConfigs} />
            )}
          </div>
        )}

        {/* ── Tab: Custom Webhooks (I5) ──────────────────────────────── */}
        {activeTab === 'custom' && (
          <div className="space-y-4">
            {showCustomForm && (
              <CustomWebhookForm
                onSave={() => {
                  setShowCustomForm(false);
                  loadAll();
                }}
                onCancel={() => setShowCustomForm(false)}
              />
            )}

            {loading ? (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <Skeleton key={i} className="w-full h-32 rounded-xl" />
                ))}
              </div>
            ) : customIntegrations.length === 0 && !showCustomForm ? (
              <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-12 text-center">
                <span className="text-4xl block mb-3">🔗</span>
                <h3 className="text-sm font-semibold text-zinc-300 mb-1">No custom webhooks</h3>
                <p className="text-xs text-zinc-500 mb-4">
                  Create custom webhooks to send PARWA events to any HTTP endpoint.
                </p>
                <button
                  onClick={() => setShowCustomForm(true)}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[#FF7F11] text-sm font-semibold text-white hover:bg-[#FF7F11]/90 transition-colors"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                  </svg>
                  Create Your First Webhook
                </button>
              </div>
            ) : (
              <div className="space-y-3">
                {customIntegrations.map((webhook) => (
                  <CustomIntegrationCard
                    key={webhook.id}
                    webhook={webhook}
                    onRefresh={loadAll}
                  />
                ))}
              </div>
            )}
          </div>
        )}

        {/* ── Tab: Health (I7) ───────────────────────────────────────── */}
        {activeTab === 'health' && (
          <HealthDashboard
            integrations={integrations}
            customIntegrations={customIntegrations}
          />
        )}
      </div>

      {/* ── Modals ───────────────────────────────────────────────────── */}
      {showConnectModal && (
        <ConnectModal
          available={available}
          onClose={() => setShowConnectModal(false)}
          onConnected={loadAll}
        />
      )}

      {selectedIntegration && (
        <DetailModal
          integration={selectedIntegration}
          onClose={() => setSelectedIntegration(null)}
          onDisconnect={loadAll}
        />
      )}
    </div>
  );
}
