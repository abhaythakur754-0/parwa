'use client';

import React, { useState, useCallback } from 'react';
import {
  Plus,
  Trash2,
  GripVertical,
  Loader2,
  CheckCircle,
  XCircle,
  Upload,
  Link,
  FileJson,
  ChevronDown,
  ChevronUp,
  Eye,
  EyeOff,
  Zap,
  AlertTriangle,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { integrationsApi, getErrorMessage } from '@/lib/api';
import { cn } from '@/lib/utils';

// ── Auth Type Options ──────────────────────────────────────────────────

const AUTH_TYPES = [
  { value: 'bearer', label: 'Bearer Token', fields: [{ name: 'api_key', label: 'API Key / Token', type: 'password' }] },
  { value: 'api_key_header', label: 'API Key (Header)', fields: [{ name: 'header_name', label: 'Header Name', type: 'text' }, { name: 'api_key', label: 'API Key', type: 'password' }] },
  { value: 'api_key_query', label: 'API Key (Query Param)', fields: [{ name: 'param_name', label: 'Param Name', type: 'text' }, { name: 'api_key', label: 'API Key', type: 'password' }] },
  { value: 'basic_auth', label: 'Basic Auth', fields: [{ name: 'username', label: 'Username', type: 'text' }, { name: 'password', label: 'Password', type: 'password' }] },
  { value: 'oauth2', label: 'OAuth 2.0', fields: [{ name: 'client_id', label: 'Client ID', type: 'text' }, { name: 'client_secret', label: 'Client Secret', type: 'password' }, { name: 'refresh_token', label: 'Refresh Token', type: 'password' }] },
] as const;

const METHOD_COLORS: Record<string, string> = {
  GET: 'bg-green-500/20 text-green-400',
  POST: 'bg-blue-500/20 text-blue-400',
  PUT: 'bg-amber-500/20 text-amber-400',
  PATCH: 'bg-orange-500/20 text-orange-400',
  DELETE: 'bg-red-500/20 text-red-400',
};

// ── Props ──────────────────────────────────────────────────────────────

interface CustomConnectorFormProps {
  /** 'custom' for Tier 3, 'openapi' for Tier 2 */
  mode: 'custom' | 'openapi';
  /** Current variant to check permissions */
  variant?: 'mini' | 'parwa' | 'high';
  /** Callback when connector is saved */
  onSaved?: () => void;
  /** Callback to close the form */
  onClose?: () => void;
}

// ── Action Editor ──────────────────────────────────────────────────────

interface ActionDef {
  name: string;
  method: string;
  path: string;
  description: string;
  required_params: string[];
  optional_params: string[];
  enabled: boolean;
}

function ActionEditor({
  action,
  index,
  onChange,
  onRemove,
}: {
  action: ActionDef;
  index: number;
  onChange: (index: number, updated: ActionDef) => void;
  onRemove: (index: number) => void;
}) {
  const [expanded, setExpanded] = useState(index === 0);

  return (
    <div className="border border-white/10 rounded-lg overflow-hidden">
      <div
        className="flex items-center gap-2 p-3 cursor-pointer hover:bg-white/[0.02] transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <GripVertical className="w-4 h-4 text-white/20" />
        <span className={cn('text-xs px-2 py-0.5 rounded font-mono', METHOD_COLORS[action.method] || 'bg-gray-500/20 text-gray-400')}>
          {action.method}
        </span>
        <span className="text-sm text-white/80 font-mono flex-1 truncate">{action.path}</span>
        <span className="text-xs text-white/40 truncate max-w-[120px]">{action.name}</span>
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onRemove(index); }}
          className="text-red-400/50 hover:text-red-400 transition-colors p-1"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
        {expanded ? <ChevronUp className="w-4 h-4 text-white/30" /> : <ChevronDown className="w-4 h-4 text-white/30" />}
      </div>

      {expanded && (
        <div className="px-3 pb-3 border-t border-white/5 pt-3 space-y-3">
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="text-xs text-orange-200/40 mb-1 block">Action Name</label>
              <input
                type="text"
                value={action.name}
                onChange={(e) => onChange(index, { ...action, name: e.target.value })}
                className="input-parwa text-sm"
                placeholder="Get Customer"
              />
            </div>
            <div>
              <label className="text-xs text-orange-200/40 mb-1 block">Method</label>
              <select
                value={action.method}
                onChange={(e) => onChange(index, { ...action, method: e.target.value })}
                className="input-parwa text-sm"
              >
                {['GET', 'POST', 'PUT', 'PATCH', 'DELETE'].map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs text-orange-200/40 mb-1 block">Path</label>
              <input
                type="text"
                value={action.path}
                onChange={(e) => onChange(index, { ...action, path: e.target.value })}
                className="input-parwa text-sm font-mono"
                placeholder="/customers/{id}"
              />
            </div>
          </div>

          <div>
            <label className="text-xs text-orange-200/40 mb-1 block">
              Description <span className="text-orange-400/60">(AI uses this to decide when to call this action)</span>
            </label>
            <textarea
              value={action.description}
              onChange={(e) => onChange(index, { ...action, description: e.target.value })}
              className="input-parwa text-sm min-h-[60px]"
              placeholder="Retrieves customer account balance. Use when customer asks about billing or outstanding amount."
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-orange-200/40 mb-1 block">Required Params (comma-separated)</label>
              <input
                type="text"
                value={action.required_params.join(', ')}
                onChange={(e) => onChange(index, { ...action, required_params: e.target.value.split(',').map((s: string) => s.trim()).filter(Boolean) })}
                className="input-parwa text-sm"
                placeholder="customer_id, amount"
              />
            </div>
            <div>
              <label className="text-xs text-orange-200/40 mb-1 block">Optional Params (comma-separated)</label>
              <input
                type="text"
                value={action.optional_params.join(', ')}
                onChange={(e) => onChange(index, { ...action, optional_params: e.target.value.split(',').map((s: string) => s.trim()).filter(Boolean) })}
                className="input-parwa text-sm"
                placeholder="due_date, notes"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main Component ─────────────────────────────────────────────────────

export function CustomConnectorForm({ mode, variant, onSaved, onClose }: CustomConnectorFormProps) {
  const isCustom = mode === 'custom';
  const isParwaHigh = variant === 'high';

  // Tier 3: Custom REST Connector form (Custom connector description mentions PARWA // Tier 3: Custom REST Connector form PARWA High — these are product names, not variant identifiers)
  const [name, setName] = useState('');
  const [baseUrl, setBaseUrl] = useState('');
  const [authType, setAuthType] = useState('bearer');
  const [authFields, setAuthFields] = useState<Record<string, string>>({});
  const [showPasswords, setShowPasswords] = useState<Record<string, boolean>>({});
  const [actions, setActions] = useState<ActionDef[]>([
    { name: '', method: 'GET', path: '', description: '', required_params: [], optional_params: [], enabled: true },
  ]);
  const [description, setDescription] = useState('');
  const [testEndpoint, setTestEndpoint] = useState('');

  // Tier 2: OpenAPI Import form
  const [importMode, setImportMode] = useState<'url' | 'file'>('url');
  const [specUrl, setSpecUrl] = useState('');
  const [specFile, setSpecFile] = useState<File | null>(null);
  const [parsedSpec, setParsedSpec] = useState<Record<string, unknown> | null>(null);

  // State
  const [saving, setSaving] = useState(false);
  const [importing, setImporting] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);

  // Get auth field definitions for current auth type
  const currentAuthDef = AUTH_TYPES.find((a) => a.value === authType);

  const handleAuthFieldChange = useCallback((fieldName: string, value: string) => {
    setAuthFields((prev) => ({ ...prev, [fieldName]: value }));
  }, []);

  const handleActionChange = useCallback((index: number, updated: ActionDef) => {
    setActions((prev) => prev.map((a, i) => (i === index ? updated : a)));
  }, []);

  const handleAddAction = useCallback(() => {
    setActions((prev) => [
      ...prev,
      { name: '', method: 'GET', path: '', description: '', required_params: [], optional_params: [], enabled: true },
    ]);
  }, []);

  const handleRemoveAction = useCallback((index: number) => {
    setActions((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const handleImportSpec = async () => {
    setImporting(true);
    try {
      let result;
      if (importMode === 'url') {
        if (!specUrl) {
          toast.error('Please enter a URL');
          return;
        }
        result = await integrationsApi.importOpenAPI({ url: specUrl });
      } else {
        if (!specFile) {
          toast.error('Please select a file');
          return;
        }
        const content = await specFile.text();
        result = await integrationsApi.importOpenAPI({
          file_content: content,
          filename: specFile.name,
        });
      }

      setParsedSpec(result as Record<string, unknown>);

      // Pre-fill form from parsed spec
      if (result.name) setName(result.name as string);
      if (result.base_url) setBaseUrl(result.base_url as string);
      if (result.auth_type) setAuthType(result.auth_type as string);
      if (result.auth_fields) {
        const fields: Record<string, string> = {};
        for (const f of (result.auth_fields as Record<string, string>[])) {
          fields[f.name as string] = '';
        }
        setAuthFields(fields);
      }
      if (result.description) setDescription(result.description as string);
      if (result.actions) {
        setActions(
          (result.actions as Record<string, unknown>[]).map((a) => ({
            name: (a.name as string) || '',
            method: (a.method as string) || 'GET',
            path: (a.path as string) || '',
            description: (a.description as string) || '',
            required_params: (a.params as Record<string, string[]>)?.required || [],
            optional_params: (a.params as Record<string, string[]>)?.optional || [],
            enabled: a.enabled !== false,
          }))
        );
      }

      toast.success(`Imported ${Array.isArray(result.actions) ? result.actions.length : 0} endpoints`);
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setImporting(false);
    }
  };

  const handleSave = async () => {
    // Validate
    if (!name.trim()) {
      toast.error('Please enter a connector name');
      return;
    }
    if (!baseUrl.trim()) {
      toast.error('Please enter a base URL');
      return;
    }
    const validActions = actions.filter((a) => a.name.trim() && a.path.trim());
    if (validActions.length === 0) {
      toast.error('Please add at least one action with a name and path');
      return;
    }

    setSaving(true);
    try {
      const payload = {
        name: name.trim(),
        base_url: baseUrl.trim(),
        auth_type: authType,
        auth_config: authFields,
        actions: validActions.map((a) => ({
          name: a.name.trim(),
          method: a.method,
          path: a.path.trim(),
          description: a.description.trim(),
          params: { required: a.required_params, optional: a.optional_params },
          enabled: a.enabled,
        })),
        description: description.trim(),
        test_endpoint: testEndpoint.trim(),
      };

      if (mode === 'openapi' && parsedSpec) {
        await integrationsApi.saveOpenAPIImport(payload);
      } else {
        await integrationsApi.createCustomConnector(payload);
      }

      toast.success(`${name} connector saved successfully`);
      onSaved?.();
      onClose?.();
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    if (!baseUrl.trim()) {
      toast.error('Please enter a base URL first');
      return;
    }
    setTesting(true);
    setTestResult(null);
    try {
      // Quick test via the test endpoint
      const testUrl = testEndpoint || `${baseUrl.replace(/\/$/, '')}/health`;
      const response = await fetch(testUrl, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
        signal: AbortSignal.timeout(10000),
      });
      if (response.ok) {
        setTestResult({ success: true, message: `Connected to ${baseUrl}` });
      } else {
        setTestResult({ success: false, message: `API returned HTTP ${response.status}` });
      }
    } catch (error) {
      setTestResult({ success: false, message: `Connection failed: ${error instanceof Error ? error.message : 'Unknown error'}` });
    } finally {
      setTesting(false);
    }
  };

  // Permission check for OpenAPI import
  if (mode === 'openapi' && !isParwaHigh) {
    return (
      <div className="card-parwa p-6 text-center">
        <AlertTriangle className="w-8 h-8 text-yellow-400 mx-auto mb-3" />
        <h3 className="text-lg font-bold text-white mb-2">PARWA High Required</h3>
        <p className="text-sm text-orange-200/50">
          OpenAPI Import is available for PARWA High only. Upgrade your plan to access this feature.
        </p>
        {onClose && (
          <button type="button" onClick={onClose} className="btn-secondary-parwa mt-4 py-2 px-4 text-sm">
            Close
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3 mb-2">
        <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-purple-500 to-indigo-400 flex items-center justify-center">
          {isCustom ? <Zap className="w-5 h-5 text-white" /> : <FileJson className="w-5 h-5 text-white" />}
        </div>
        <div>
          <h3 className="text-lg font-bold text-white">
            {isCustom ? 'Custom REST Connector' : 'OpenAPI Import'}
          </h3>
          <p className="text-xs text-orange-200/40">
            {isCustom ? 'Tier 3 — PARWA & PARWA High ($49/mo add-on)' : 'Tier 2 — PARWA High only'}
          </p>
        </div>
      </div>

      {/* OpenAPI Import: URL or File upload */}
      {mode === 'openapi' && !parsedSpec && (
        <div className="card-parwa p-4 space-y-4">
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setImportMode('url')}
              className={cn(
                'flex-1 py-2 px-3 rounded-lg text-sm font-medium transition-colors flex items-center justify-center gap-2',
                importMode === 'url' ? 'bg-orange-500/20 text-orange-400 border border-orange-500/30' : 'bg-white/5 text-white/40'
              )}
            >
              <Link className="w-4 h-4" /> URL
            </button>
            <button
              type="button"
              onClick={() => setImportMode('file')}
              className={cn(
                'flex-1 py-2 px-3 rounded-lg text-sm font-medium transition-colors flex items-center justify-center gap-2',
                importMode === 'file' ? 'bg-orange-500/20 text-orange-400 border border-orange-500/30' : 'bg-white/5 text-white/40'
              )}
            >
              <Upload className="w-4 h-4" /> Upload File
            </button>
          </div>

          {importMode === 'url' ? (
            <div>
              <label className="text-xs text-orange-200/40 mb-1 block">OpenAPI Spec URL</label>
              <input
                type="url"
                value={specUrl}
                onChange={(e) => setSpecUrl(e.target.value)}
                className="input-parwa text-sm"
                placeholder="https://api.example.com/docs/openapi.json"
              />
            </div>
          ) : (
            <div>
              <label className="text-xs text-orange-200/40 mb-1 block">Upload OpenAPI Spec (.json, .yaml, .yml)</label>
              <input
                type="file"
                accept=".json,.yaml,.yml"
                onChange={(e) => setSpecFile(e.target.files?.[0] || null)}
                className="input-parwa text-sm file:mr-2 file:py-1 file:px-3 file:rounded-md file:border-0 file:text-xs file:bg-orange-500/20 file:text-orange-400"
              />
            </div>
          )}

          <button
            type="button"
            onClick={handleImportSpec}
            disabled={importing}
            className="btn-primary-parwa py-2 px-4 text-sm w-full"
          >
            {importing ? (
              <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Importing...</>
            ) : (
              <><FileJson className="w-4 h-4 mr-2" />Import & Parse</>
            )}
          </button>
        </div>
      )}

      {/* Parsed spec summary (OpenAPI mode) */}
      {mode === 'openapi' && parsedSpec && (
        <div className="card-parwa p-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle className="w-4 h-4 text-green-400" />
            <span className="text-sm text-white/80">
              Imported <strong>{parsedSpec.name as string}</strong> — {parsedSpec.endpoint_count as number} endpoints
            </span>
          </div>
          <button
            type="button"
            onClick={() => setParsedSpec(null)}
            className="text-xs text-orange-400/60 hover:text-orange-400"
          >
            Re-import
          </button>
        </div>
      )}

      {/* Connector form (shared for both modes) */}
      <div className="space-y-4">
        {/* Name & Base URL */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="text-xs text-orange-200/40 mb-1 block">Connector Name *</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="input-parwa text-sm"
              placeholder="Internal Billing API"
            />
          </div>
          <div>
            <label className="text-xs text-orange-200/40 mb-1 block">Base URL *</label>
            <input
              type="url"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              className="input-parwa text-sm font-mono"
              placeholder="https://billing.internal.company.com/api/v1"
            />
          </div>
        </div>

        {/* Description */}
        <div>
          <label className="text-xs text-orange-200/40 mb-1 block">Description</label>
          <input
            type="text"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="input-parwa text-sm"
            placeholder="Internal billing system for customer invoicing"
          />
        </div>

        {/* Auth Type */}
        <div>
          <label className="text-xs text-orange-200/40 mb-2 block">Authentication Type *</label>
          <div className="flex flex-wrap gap-2">
            {AUTH_TYPES.map((at) => (
              <button
                key={at.value}
                type="button"
                onClick={() => {
                  setAuthType(at.value);
                  setAuthFields({});
                  setTestResult(null);
                }}
                className={cn(
                  'py-1.5 px-3 rounded-lg text-xs font-medium transition-colors',
                  authType === at.value
                    ? 'bg-orange-500/20 text-orange-400 border border-orange-500/30'
                    : 'bg-white/5 text-white/40 border border-transparent hover:bg-white/10'
                )}
              >
                {at.label}
              </button>
            ))}
          </div>
        </div>

        {/* Auth Fields */}
        {currentAuthDef && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {currentAuthDef.fields.map((field) => (
              <div key={field.name}>
                <label className="text-xs text-orange-200/40 mb-1 block">{field.label} *</label>
                <div className="relative">
                  <input
                    type={field.type === 'password' && !showPasswords[field.name] ? 'password' : 'text'}
                    value={authFields[field.name] || ''}
                    onChange={(e) => handleAuthFieldChange(field.name, e.target.value)}
                    className="input-parwa text-sm"
                    placeholder={field.label}
                  />
                  {field.type === 'password' && (
                    <button
                      type="button"
                      onClick={() => setShowPasswords((prev) => ({ ...prev, [field.name]: !prev[field.name] }))}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-white/30 hover:text-white/60"
                    >
                      {showPasswords[field.name] ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Test Connection */}
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={handleTest}
            disabled={testing}
            className="btn-secondary-parwa py-2 px-4 text-sm"
          >
            {testing ? (
              <><Loader2 className="w-4 h-4 mr-1 animate-spin" />Testing...</>
            ) : (
              'Test Connection'
            )}
          </button>
          {testResult && (
            <span className={cn('text-sm flex items-center gap-1', testResult.success ? 'text-green-400' : 'text-red-400')}>
              {testResult.success ? <CheckCircle className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
              {testResult.message}
            </span>
          )}
        </div>

        {/* Test Endpoint Override */}
        <div>
          <label className="text-xs text-orange-200/40 mb-1 block">Test Endpoint Override (optional)</label>
          <input
            type="text"
            value={testEndpoint}
            onChange={(e) => setTestEndpoint(e.target.value)}
            className="input-parwa text-sm font-mono"
            placeholder="Default: GET {base_url}/health"
          />
        </div>

        {/* Actions */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="text-xs text-orange-200/40">Actions ({actions.filter((a) => a.name.trim()).length} defined)</label>
            <button
              type="button"
              onClick={handleAddAction}
              className="flex items-center gap-1 text-xs text-orange-400/70 hover:text-orange-400 transition-colors"
            >
              <Plus className="w-3.5 h-3.5" /> Add Action
            </button>
          </div>
          <div className="space-y-2">
            {actions.map((action, index) => (
              <ActionEditor
                key={index}
                action={action}
                index={index}
                onChange={handleActionChange}
                onRemove={handleRemoveAction}
              />
            ))}
          </div>
          {actions.length === 0 && (
            <p className="text-xs text-orange-200/30 text-center py-4">No actions defined. Click &quot;Add Action&quot; to define an API call.</p>
          )}
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex items-center gap-3 pt-4 border-t border-white/5">
        {onClose && (
          <button type="button" onClick={onClose} className="btn-ghost-parwa text-sm">
            Cancel
          </button>
        )}
        <button
          type="button"
          onClick={handleSave}
          disabled={saving}
          className="btn-primary-parwa py-2 px-5 text-sm"
        >
          {saving ? (
            <><Loader2 className="w-4 h-4 mr-1 animate-spin" />Saving...</>
          ) : (
            'Save Connector'
          )}
        </button>
      </div>
    </div>
  );
}

export default CustomConnectorForm;
