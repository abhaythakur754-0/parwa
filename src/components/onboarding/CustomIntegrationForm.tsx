'use client';

import React, { useState } from 'react';
import { Loader2, ShieldCheck, Sparkles } from 'lucide-react';
import toast from 'react-hot-toast';

interface CustomIntegrationFormProps {
  onSaved: (integration: { id: string; integration_type: string; name: string | null; status: string }) => void;
}

// Unified credential-field shape: manual auth types identify fields by
// `name`, Superglue-discovered schemas use `key`. Both may set `required`.
interface CredentialField {
  name?: string;
  key?: string;
  label: string;
  type: string;
  required?: boolean;
  placeholder?: string;
}

const fieldId = (f: CredentialField): string => f.name || f.key || '';

const AUTH_TYPES: { value: string; label: string; fields: CredentialField[] }[] = [
  { value: 'bearer', label: 'Bearer Token', fields: [{ name: 'api_key', label: 'API Key / Token', type: 'password' }] },
  { value: 'api_key_header', label: 'API Key (Header)', fields: [{ name: 'header_name', label: 'Header Name', type: 'text' }, { name: 'api_key', label: 'API Key', type: 'password' }] },
  { value: 'api_key_query', label: 'API Key (Query Param)', fields: [{ name: 'param_name', label: 'Param Name', type: 'text' }, { name: 'api_key', label: 'API Key', type: 'password' }] },
  { value: 'basic_auth', label: 'Basic Auth', fields: [{ name: 'username', label: 'Username', type: 'text' }, { name: 'password', label: 'Password', type: 'password' }] },
];

export function CustomIntegrationForm({ onSaved }: CustomIntegrationFormProps) {
  const [categoryName, setCategoryName] = useState('');
  const [integrationName, setIntegrationName] = useState('');
  const [baseUrl, setBaseUrl] = useState('');
  const [authType, setAuthType] = useState('bearer');
  const [credentials, setCredentials] = useState<Record<string, string>>({});
  const [testUrl, setTestUrl] = useState('');
  const [saving, setSaving] = useState(false);
  const [askingSuperglue, setAskingSuperglue] = useState(false);
  const [superglueFields, setSuperglueFields] = useState<CredentialField[]>([]);

  // If Superglue returned fields, use those. Otherwise use the selected auth type's fields.
  const selectedAuthType = AUTH_TYPES.find(a => a.value === authType) || AUTH_TYPES[0];
  const activeFields = superglueFields.length > 0 ? superglueFields : selectedAuthType.fields;

  const handleFieldChange = (name: string, value: string) => {
    setCredentials((prev) => ({ ...prev, [name]: value }));
  };

  // ── Ask Superglue for auth schema ────────────────────────────────────
  // When user types a platform name, we ask Superglue "What auth does this
  // need?" instead of making the user manually pick auth type + fields.
  const handleAskSuperglue = async () => {
    if (!integrationName.trim()) {
      toast.error('Please enter the integration name first');
      return;
    }
    setAskingSuperglue(true);
    try {
      const res = await fetch('/api/superglue/discover-auth', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          platform_name: integrationName,
          platform_type: 'integration',
        }),
      });
      const data = await res.json();

      if (data.success && data.fields && data.fields.length > 0) {
        // Superglue returned auth schema → use it
        setSuperglueFields(data.fields);
        if (data.auth_type) setAuthType(data.auth_type);
        if (data.url_hint && !baseUrl) setBaseUrl(data.url_hint);
        toast.success(`Superglue found auth schema for "${integrationName}"`);
      } else {
        // Superglue doesn't know this platform → fallback to manual
        setSuperglueFields([]);
        toast(`Superglue doesn't know "${integrationName}" — select auth type manually`, { icon: 'ℹ️' });
      }
    } catch {
      setSuperglueFields([]);
      toast.error('Failed to ask Superglue. Select auth type manually.');
    } finally {
      setAskingSuperglue(false);
    }
  };

  const handleSave = async () => {
    if (!categoryName.trim()) { toast.error('Please enter a category name'); return; }
    if (!integrationName.trim()) { toast.error('Please enter an integration name'); return; }
    if (!baseUrl.trim()) { toast.error('Please enter a base URL'); return; }

    const requiredFields = activeFields.filter(f => f.required && !fieldId(f).startsWith('header') && !fieldId(f).startsWith('param'));
    const missing = requiredFields.filter(f => !credentials[fieldId(f)]?.trim());
    if (missing.length > 0) { toast.error(`Please fill in: ${missing.map(f => f.label).join(', ')}`); return; }

    setSaving(true);
    try {
      // Create integration with custom category in settings
      const res = await fetch('/api/integrations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          integration_type: `custom_${categoryName.toLowerCase().replace(/\s+/g, '_')}_${integrationName.toLowerCase().replace(/\s+/g, '_')}`,
          name: integrationName,
          credentials: {
            ...credentials,
            base_url: baseUrl,
            auth_type: authType,
            category: categoryName,
            test_url: testUrl || baseUrl,
          },
          settings: { custom: true, category: categoryName, discovered_by_superglue: superglueFields.length > 0 },
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || err.message || 'Failed to save');
      }

      const created = await res.json();

      // Try to verify if test URL provided
      if (testUrl || baseUrl) {
        try {
          const testRes = await fetch(`/api/integrations/${created.id}/test`, {
            method: 'POST',
            credentials: 'include',
          });
          const testData = await testRes.json().catch(() => ({}));
          if (testRes.ok && testData.success) {
            toast.success(`${integrationName} verified!`);
          } else {
            toast(`${integrationName} saved but not verified: ${testData.message || 'Test failed'}`, { icon: '⚠️' });
          }
        } catch {
          toast(`${integrationName} saved but verification failed`, { icon: '⚠️' });
        }
      }

      onSaved({
        id: created.id,
        integration_type: created.integration_type,
        name: created.name,
        status: created.status || 'active',
      });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to save integration');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Category name */}
      <div>
        <label className="text-[10px] text-zinc-500 uppercase tracking-wider font-medium block mb-1">
          Category Name (e.g., HR Tools, Accounting, Legal)
        </label>
        <input
          type="text"
          value={categoryName}
          onChange={(e) => setCategoryName(e.target.value)}
          placeholder="e.g., HR Tools"
          maxLength={50}
          className="w-full px-3 py-2 rounded-lg bg-white/[0.03] border border-white/[0.08] text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-orange-500/40 transition-colors"
        />
      </div>

      {/* Integration name */}
      <div>
        <label className="text-[10px] text-zinc-500 uppercase tracking-wider font-medium block mb-1">
          Integration Name
        </label>
        <input
          type="text"
          value={integrationName}
          onChange={(e) => { setIntegrationName(e.target.value); setSuperglueFields([]); }}
          placeholder="e.g., Zoho Inventory, Paddle, Chargebee"
          maxLength={100}
          className="w-full px-3 py-2 rounded-lg bg-white/[0.03] border border-white/[0.08] text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-orange-500/40 transition-colors"
        />
      </div>

      {/* Ask Superglue button — the key new feature */}
      <button
        type="button"
        onClick={handleAskSuperglue}
        disabled={askingSuperglue || !integrationName.trim()}
        className="flex items-center gap-2 w-full px-4 py-2.5 rounded-lg bg-purple-500/20 text-purple-400 text-sm font-medium border border-purple-500/30 hover:bg-purple-500/30 transition-colors disabled:opacity-50"
      >
        {askingSuperglue ? (
          <><Loader2 className="w-4 h-4 animate-spin" /> Asking Superglue...</>
        ) : (
          <><Sparkles className="w-4 h-4" /> Ask Superglue for Auth Schema</>
        )}
      </button>
      <p className="text-[10px] text-zinc-500 -mt-2">
        Superglue will find the right auth type &amp; fields for this platform
      </p>

      {/* Show Superglue-discovered fields if available */}
      {superglueFields.length > 0 && (
        <div className="rounded-lg border border-purple-500/20 bg-purple-500/5 p-3 space-y-2">
          <p className="text-xs text-purple-300 font-medium">Superglue discovered these fields:</p>
          {superglueFields.map((field) => (
            <div key={fieldId(field)}>
              <label className="text-[10px] text-zinc-500 uppercase tracking-wider font-medium block mb-1">
                {field.label} {field.required && <span className="text-red-400">*</span>}
              </label>
              <input
                type={field.type === 'password' ? 'password' : 'text'}
                value={credentials[fieldId(field)] || ''}
                onChange={(e) => handleFieldChange(fieldId(field), e.target.value)}
                placeholder={field.placeholder || field.label}
                maxLength={255}
                className="w-full px-3 py-2 rounded-lg bg-white/[0.03] border border-white/[0.08] text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-orange-500/40 transition-colors"
              />
            </div>
          ))}
        </div>
      )}

      {/* Base URL */}
      <div>
        <label className="text-[10px] text-zinc-500 uppercase tracking-wider font-medium block mb-1">
          API Base URL
        </label>
        <input
          type="text"
          value={baseUrl}
          onChange={(e) => setBaseUrl(e.target.value)}
          placeholder="https://api.example.com/v1"
          maxLength={500}
          className="w-full px-3 py-2 rounded-lg bg-white/[0.03] border border-white/[0.08] text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-orange-500/40 transition-colors"
        />
      </div>

      {/* Auth type selector — only show if Superglue didn't find fields */}
      {superglueFields.length === 0 && (
        <div>
          <label className="text-[10px] text-zinc-500 uppercase tracking-wider font-medium block mb-1">
            Authentication Type
          </label>
          <select
            value={authType}
            onChange={(e) => { setAuthType(e.target.value); setCredentials({}); }}
            className="w-full px-3 py-2 rounded-lg bg-white/[0.03] border border-white/[0.08] text-sm text-white focus:outline-none focus:border-orange-500/40 transition-colors"
          >
            {AUTH_TYPES.map(a => <option key={a.value} value={a.value} className="bg-[#1A1A1A]">{a.label}</option>)}
          </select>

          {/* Dynamic credential fields based on auth type */}
          {activeFields.map((field) => (
            <div key={fieldId(field)} className="mt-3">
              <label className="text-[10px] text-zinc-500 uppercase tracking-wider font-medium block mb-1">
                {field.label}
              </label>
              <input
                type={field.type === 'password' ? 'password' : 'text'}
                value={credentials[fieldId(field)] || ''}
                onChange={(e) => handleFieldChange(fieldId(field), e.target.value)}
                placeholder={field.name === 'header_name' ? 'X-API-Key' : field.name === 'param_name' ? 'api_key' : 'Enter value...'}
                maxLength={255}
                className="w-full px-3 py-2 rounded-lg bg-white/[0.03] border border-white/[0.08] text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-orange-500/40 transition-colors"
              />
            </div>
          ))}
        </div>
      )}

      {/* Test URL (optional) */}
      <div>
        <label className="text-[10px] text-zinc-500 uppercase tracking-wider font-medium block mb-1">
          Test URL (optional — used to verify credentials)
        </label>
        <input
          type="text"
          value={testUrl}
          onChange={(e) => setTestUrl(e.target.value)}
          placeholder="https://api.example.com/v1/health"
          maxLength={500}
          className="w-full px-3 py-2 rounded-lg bg-white/[0.03] border border-white/[0.08] text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-orange-500/40 transition-colors"
        />
      </div>

      {/* Save & Verify button */}
      <button
        onClick={handleSave}
        disabled={saving}
        className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-orange-500/20 text-orange-400 text-sm font-medium border border-orange-500/30 hover:bg-orange-500/30 transition-colors disabled:opacity-50"
      >
        {saving ? <><Loader2 className="w-4 h-4 animate-spin" /> Saving...</> : <><ShieldCheck className="w-4 h-4" /> Save & Verify</>}
      </button>
    </div>
  );
}
