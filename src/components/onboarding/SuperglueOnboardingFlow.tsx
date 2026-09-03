'use client';

/**
 * SuperglueOnboardingFlow — progressive integration flow.
 *
 * Phase 1: CRM Connect — show ONE CRM card. User connects + verifies.
 *          Verify = Superglue GET check + MCPConnection DB record.
 * Phase 2: CRM Analysis — auto-trigger /api/integrations/analyze.
 *          Show loading spinner (2-3 min, analyser scans 30 days of tickets).
 *          New tenants with no ticket history get a starter-pack fallback
 *          from the backend, so this phase ALWAYS produces recommendations.
 * Phase 3: Recommended Integrations — show analyser results as connectable
 *          cards below the CRM. User connects each via Superglue.
 * Phase 4: Agent build — auto-triggered in background, polled via
 *          /api/onboarding-build/status. "Continue" unlocks when all pass.
 *
 * Replaces the old "show all 12 systems at once" grid. Makes onboarding
 * fast, guided, and simple — customer just follows instructions.
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Loader2, CheckCircle2, Link2, X, Plug, AlertTriangle,
  Sparkles, Search, ChevronRight,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { cn } from '@/lib/utils';

// ── Types ────────────────────────────────────────────────────────────

interface CRMType {
  id: string;
  name: string;
  icon: string;
  url_hint: string;
}

interface VerifyResult {
  verified: boolean;
  superglue_ok: boolean;
  mcp_registered: boolean;
  system_id: string;
  name: string;
  url: string;
  message: string;
}

interface AnalysisRecommendation {
  name: string;
  priority?: string;
  reason?: string;
}

interface AnalysisResult {
  company_id: string;
  analyzed_at: string;
  connected_integrations: any[];
  data_profile: any;
  detected_gaps: any[];
  recommendations: AnalysisRecommendation[];
  analysis_summary: string;
}

type Phase = 'crm-connect' | 'analyzing' | 'recommendations' | 'building-agents' | 'agents-ready' | 'error';

// ── Agent build status (Phase 4 + 5) ─────────────────────────────────

interface AgentBuildStatus {
  agent_name: string;
  agent_role: string;
  status: string; // pending|active|failed|skipped
  superglue_tool_id?: string;
  error?: string;
}

interface BuildStatus {
  total_agents: number;
  ready: number;
  pending: number;
  failed: number;
  all_ready: boolean;
  agents: AgentBuildStatus[];
}

// ── CRM options (only CRM types shown in Phase 1) ────────────────────
// auth_type "oauth" systems (HubSpot/Salesforce/Zoho) currently use the same
// paste-a-token form — honest path until the Superglue OAuth redirect ships.
// auth_schema: extra fields per system (rendered before the API Key field)

interface AuthSchemaField {
  key: string;
  label: string;
  type: 'text' | 'email' | 'password' | 'textarea';
  required?: boolean;
  placeholder?: string;
}

const CRM_OPTIONS: (CRMType & { auth_type?: string; auth_schema?: AuthSchemaField[] })[] = [
  { id: 'hubspot',    name: 'HubSpot',      icon: '🎯', url_hint: 'https://api.hubapi.com',  auth_type: 'oauth' },
  { id: 'salesforce',  name: 'Salesforce',   icon: '☁️', url_hint: 'https://login.salesforce.com', auth_type: 'oauth' },
  { id: 'zendesk',    name: 'Zendesk',      icon: '🎫', url_hint: 'https://{subdomain}.zendesk.com/api/v2', auth_type: 'api_key',
    auth_schema: [
      { key: 'subdomain', label: 'Subdomain', type: 'text', required: true, placeholder: 'mycompany' },
      { key: 'email', label: 'Email', type: 'email', required: true, placeholder: 'admin@company.com' },
    ]},
  { id: 'freshdesk',  name: 'Freshdesk',    icon: '🎫', url_hint: 'https://{domain}.freshdesk.com/api/v2', auth_type: 'api_key',
    auth_schema: [
      { key: 'domain', label: 'Domain', type: 'text', required: true, placeholder: 'mycompany.freshdesk.com' },
    ]},
  { id: 'zoho',       name: 'Zoho CRM',     icon: '🏢', url_hint: 'https://www.zohoapis.com/crm/v2', auth_type: 'oauth' },
  { id: 'pipedrive',  name: 'Pipedrive',    icon: '🔄', url_hint: 'https://api.pipedrive.com', auth_type: 'api_key' },
  { id: 'custom',     name: 'Custom CRM',   icon: '🔌', url_hint: '', auth_type: 'api_key' },
];

// ── Component ────────────────────────────────────────────────────────

export function SuperglueOnboardingFlow({ onComplete }: { onComplete?: () => void } = {}) {
  const [phase, setPhase] = useState<Phase>('crm-connect');
  const [selectedCRM, setSelectedCRM] = useState<CRMType | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [formName, setFormName] = useState('');
  const [formUrl, setFormUrl] = useState('');
  const [formApiKey, setFormApiKey] = useState('');
  // Dynamic auth schema fields (keyed by field key from auth_schema)
  const [formExtraFields, setFormExtraFields] = useState<Record<string, string>>({});
  // Database-specific form fields
  const [formDbType, setFormDbType] = useState('postgresql');
  const [formDbHost, setFormDbHost] = useState('');
  const [formDbPort, setFormDbPort] = useState('5432');
  const [formDbName, setFormDbName] = useState('');
  const [formDbUsername, setFormDbUsername] = useState('');
  const [formDbPassword, setFormDbPassword] = useState('');
  const [isDbForm, setIsDbForm] = useState(false); // true when connecting a database
  const [connecting, setConnecting] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [verified, setVerified] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);
  const [analysisError, setAnalysisError] = useState<string>('');
  const [connectedRecommendations, setConnectedRecommendations] = useState<Set<string>>(new Set());
  const [buildStatus, setBuildStatus] = useState<BuildStatus | null>(null);
  const [testingSystem, setTestingSystem] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, { works: boolean; message: string }>>({});
  const [allTested, setAllTested] = useState(false);

  // ── Phase 1: Open CRM connect form ────────────────────────────────
  // OAuth-type CRMs also use this form: until Superglue exposes an OAuth
  // redirect endpoint, the user pastes an API key / access token — same
  // fast path, but the credentials are REAL (empty-credential connects
  // used to "verify" OK and then fail on first data access).
  const openCRMForm = (crm: any) => {
    setSelectedCRM(crm);
    setFormName(crm.name === 'Custom CRM' ? '' : crm.name);
    setFormUrl(crm.url_hint || '');
    setFormApiKey('');
    setFormExtraFields({});
    setFormOpen(true);
  };

  // ── Phase 1: Verify CRM (Superglue + MCP) ────────────────────────
  const handleVerify = async (systemId: string) => {
    setVerifying(true);
    try {
      const res = await fetch(`/api/superglue/systems/${encodeURIComponent(systemId)}/verify`, {
        method: 'POST',
      });
      const data: VerifyResult = await res.json();
      if (data.verified) {
        setVerified(true);
        toast.success(data.message);
        // Auto-proceed to Phase 2: Analysis
        setTimeout(() => runAnalysis(), 500);
      } else {
        toast.error(data.message || 'Verification failed');
      }
    } catch {
      toast.error('Network error during verification');
    } finally {
      setVerifying(false);
    }
  };

  // ── Phase 2: Run CRM Analysis ─────────────────────────────────────
  const runAnalysis = async () => {
    setPhase('analyzing');
    setAnalysisError('');
    try {
      const res = await fetch('/api/integrations/analyze', {
        method: 'POST',
      });
      const data: AnalysisResult = await res.json();
      if (res.ok) {
        setAnalysisResult(data);
        setPhase('recommendations');
        // AUTO-TRIGGER agent + tool creation in the background (no user click needed).
        // Runs in parallel while the user fills in their integrations.
        triggerAgentBuild();
      } else {
        setAnalysisError((data as any).detail || 'Analysis failed');
        setPhase('error');
      }
    } catch {
      setAnalysisError('Network error — could not reach the CRM Analyser');
      setPhase('error');
    }
  };

  // ── Phase 3: Connect a recommended integration ────────────────────
  // Opens a connect form (same modal as CRM) — detects if it's a database
  // and shows DB-specific fields (host, port, db name, user, password)
  const connectRecommendation = async (rec: AnalysisRecommendation) => {
    const systemId = rec.name.toLowerCase().replace(/\s+/g, '-');
    // Detect if this is a database recommendation
    const dbKeywords = ['database', 'db', 'postgres', 'mysql', 'mongo', 'snowflake', 'bigquery', 'warehouse'];
    const isDb = dbKeywords.some((kw) => rec.name.toLowerCase().includes(kw) || (rec.reason || '').toLowerCase().includes(kw));

    // Open the connect form with the right mode
    setSelectedCRM({ id: systemId, name: rec.name, icon: '🔌', url_hint: '' });
    setFormName(rec.name);
    setFormUrl('');
    setFormApiKey('');
    setFormDbType('postgresql');
    setFormDbHost('');
    setFormDbPort('5432');
    setFormDbName('');
    setFormDbUsername('');
    setFormDbPassword('');
    setIsDbForm(isDb);
    setFormOpen(true);
  };

  // ── Phase 3: Submit the connect form (handles CRM + API + database) ──
  const handleConnect = async () => {
    if (!selectedCRM) return;
    if (!formName.trim()) {
      toast.error('Name is required');
      return;
    }
    if (isDbForm) {
      if (!formDbHost.trim() || !formDbName.trim() || !formDbUsername.trim()) {
        toast.error('Host, database name, and username are required');
        return;
      }
    } else {
      if (!formUrl.trim()) {
        toast.error('URL is required');
        return;
      }
    }

    setConnecting(true);
    try {
      // Detect if this is a CRM connection (Phase 1) vs recommendation (Phase 3)
      const isCrm = CRM_OPTIONS.some((c) => c.id === selectedCRM.id);

      const payload: any = {
        system_id: selectedCRM.id,
        name: formName.trim(),
        icon: selectedCRM.icon,
        metadata: { is_crm: isCrm, recommendation_reason: '' },
      };

      if (isDbForm) {
        // Database connection — send DB-specific fields
        payload.db_type = formDbType;
        payload.db_host = formDbHost.trim();
        payload.db_port = parseInt(formDbPort) || 5432;
        payload.db_name = formDbName.trim();
        payload.db_username = formDbUsername.trim();
        payload.db_password = formDbPassword;
        payload.url = ''; // backend builds it from DB fields
        payload.credentials = {};
      } else {
        // API connection — build credentials from auth_schema fields + API key.
        // auth_schema fields (Zendesk subdomain/email, Freshdesk domain, etc.)
        // used to be dropped here — they must reach Superglue or the
        // connection is broken from birth.
        const credentials: Record<string, string> = {};
        const crmDef = CRM_OPTIONS.find((c) => c.id === selectedCRM.id);
        if (crmDef?.auth_schema) {
          for (const field of crmDef.auth_schema) {
            if (formExtraFields[field.key]?.trim()) {
              credentials[field.key] = formExtraFields[field.key].trim();
            }
          }
        }
        if (formApiKey.trim()) {
          // HubSpot uses access_token, others use api_key
          if (selectedCRM.id === 'hubspot') {
            credentials.access_token = formApiKey.trim();
          } else {
            credentials.api_key = formApiKey.trim();
          }
        }
        payload.url = formUrl.trim();
        payload.credentials = credentials;
      }

      const res = await fetch('/api/superglue/systems', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (res.ok) {
        toast.success(`${formName} connected`);
        setFormOpen(false);

        // If this was a CRM (Phase 1), auto-verify + trigger analysis
        if (isCrm) {
          await handleVerify(selectedCRM.id);
        } else {
          // Phase 3 recommendation — mark as connected
          setConnectedRecommendations((prev) => new Set(prev).add(formName));
        }
      } else {
        toast.error(data.detail || 'Failed to connect');
      }
    } catch {
      toast.error('Network error');
    } finally {
      setConnecting(false);
    }
  };

  // ── Phase 3b: Test that a connected integration actually works ────
  const testIntegration = async (rec: AnalysisRecommendation) => {
    const systemId = rec.name.toLowerCase().replace(/\s+/g, '-');
    setTestingSystem(systemId);
    try {
      const res = await fetch(`/api/superglue/systems/${encodeURIComponent(systemId)}/test`, {
        method: 'POST',
      });
      const data = await res.json();
      setTestResults((prev) => ({
        ...prev,
        [systemId]: { works: data.works, message: data.message || 'Test failed' },
      }));
      if (data.works) {
        toast.success(`${rec.name}: connection verified ✓`);
      } else {
        toast.error(`${rec.name}: ${data.message || 'verification failed'}`);
      }
    } catch {
      toast.error('Network error during test');
    } finally {
      setTestingSystem(null);
    }
  };

  // ── Phase 3c: Check if all connected integrations have been tested ──
  useEffect(() => {
    if (analysisResult && connectedRecommendations.size > 0) {
      const allTestedNow = Array.from(connectedRecommendations).every((name) => {
        const id = name.toLowerCase().replace(/\s+/g, '-');
        return testResults[id] !== undefined;
      });
      setAllTested(allTestedNow);
    }
  }, [connectedRecommendations, testResults, analysisResult]);

  // ── Phase 4 (background): Auto-trigger agent + tool creation ──────
  // Called automatically when analysis results come back. Runs in the
  // background while the user fills in integrations. No UI change — just
  // polls status silently.
  const triggerAgentBuild = async () => {
    try {
      const res = await fetch('/api/onboarding-build/trigger', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      if (res.ok) {
        // Start polling for status in the background
        pollBuildStatus();
      }
      // If it fails, the Verify button will catch it (agents not ready)
    } catch {
      // Silent — Verify button will report the failure
    }
  };

  // ── Background polling for build status ───────────────────────────
  const pollBuildStatus = async () => {
    const poll = async () => {
      try {
        const res = await fetch('/api/onboarding-build/status');
        const data: BuildStatus = await res.json();
        setBuildStatus(data);
        // Keep polling until all agents are ready or all failed
        if (!data.all_ready && !(data.failed > 0 && data.pending === 0)) {
          setTimeout(poll, 3000);
        }
      } catch {
        setTimeout(poll, 5000);
      }
    };
    poll();
  };

  // ── Phase 4: Verify button — checks all 3 things with progressive loading ──
  const [verifyingAll, setVerifyingAll] = useState(false);
  const [verifyStep, setVerifyStep] = useState(0); // 0=idle, 1=checking API keys, 2=checking MCP, 3=checking agents, 4=done
  const [verifyResult, setVerifyResult] = useState<{
    api_keys_ok: boolean;
    mcp_ok: boolean;
    agents_ok: boolean;
    all_passed: boolean;
    message: string;
  } | null>(null);

  const verifyAll = async () => {
    setVerifyingAll(true);
    setVerifyResult(null);
    setVerifyStep(1);

    try {
      // Step 1: Check all connected integrations have been tested + work
      const connected = Array.from(connectedRecommendations);
      const allTestedOk = connected.every((name) => {
        const id = name.toLowerCase().replace(/\s+/g, '-');
        return testResults[id]?.works === true;
      });
      const apiKeysOk = allTestedOk && connected.length > 0;
      // Brief pause so the user sees the loading state for each step
      await new Promise((r) => setTimeout(r, 400));
      setVerifyStep(2);

      // Step 2: Check MCP connection (CRM was verified in Phase 1)
      const mcpOk = verified;
      await new Promise((r) => setTimeout(r, 400));
      setVerifyStep(3);

      // Step 3: Check build status (agents + tools)
      const statusRes = await fetch('/api/onboarding-build/status');
      const status: BuildStatus = await statusRes.json();
      setBuildStatus(status);
      const agentsOk = status.all_ready;
      setVerifyStep(4);

      const allPassed = apiKeysOk && mcpOk && agentsOk;

      let message = '';
      if (allPassed) {
        message = '✓ All checks passed — ready to continue!';
      } else {
        const failures: string[] = [];
        if (!apiKeysOk) failures.push('test all integrations');
        if (!mcpOk) failures.push('MCP not connected');
        if (!agentsOk) failures.push(`agents building (${status.ready}/${status.total_agents} ready)`);
        message = `✗ Pending: ${failures.join(', ')}`;
      }

      setVerifyResult({
        api_keys_ok: apiKeysOk,
        mcp_ok: mcpOk,
        agents_ok: agentsOk,
        all_passed: allPassed,
        message,
      });
    } catch {
      setVerifyStep(4);
      setVerifyResult({
        api_keys_ok: false,
        mcp_ok: false,
        agents_ok: false,
        all_passed: false,
        message: '✗ Network error during verification',
      });
    } finally {
      setVerifyingAll(false);
    }
  };

  // ── Retry analysis ────────────────────────────────────────────────
  const retryAnalysis = () => runAnalysis();

  // ── Render ────────────────────────────────────────────────────────

  return (
    <div className="space-y-4">
      {/* Superglue badge */}
      <div className="flex items-center gap-2 mb-3">
        <div className="px-2 py-1 rounded-md bg-violet-500/10 border border-violet-500/20 text-violet-300 text-[10px] font-bold uppercase tracking-wider">
          ⚡ Powered by Superglue
        </div>
        <span className="text-xs text-zinc-500">Connect your apps — guided setup in minutes</span>
      </div>

      {/* ═══ Phase 1: CRM Connect ═══ */}
      <div className="rounded-xl border border-violet-500/20 bg-violet-500/[0.02] p-5">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-medium text-white flex items-center gap-2">
            <span className="text-violet-400">①</span>
            Connect Your CRM
          </h3>
          {verified && (
            <span className="flex items-center gap-1 text-xs text-emerald-400">
              <CheckCircle2 className="w-3.5 h-3.5" /> Verified
            </span>
          )}
        </div>
        <p className="text-xs text-zinc-500 mb-4">
          First, connect your CRM. PARWA will access it on every ticket to resolve customer issues faster.
        </p>

        {verified && selectedCRM ? (
          // CRM is connected + verified — show connected state
          <div className="flex items-center justify-between rounded-lg border border-emerald-500/20 bg-emerald-500/[0.04] p-3">
            <div className="flex items-center gap-3">
              <span className="text-2xl">{selectedCRM.icon}</span>
              <div>
                <p className="text-sm font-medium text-white">{formName || selectedCRM.name}</p>
                <p className="text-[10px] text-emerald-400">Connected to Superglue + registered with MCP</p>
              </div>
            </div>
            <CheckCircle2 className="w-5 h-5 text-emerald-400" />
          </div>
        ) : (
          // Show CRM options
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            {CRM_OPTIONS.map((crm) => (
              <button
                key={crm.id}
                onClick={() => openCRMForm(crm)}
                disabled={verifying}
                className="flex items-center gap-2 p-3 rounded-lg border border-white/[0.06] bg-white/[0.02] hover:border-violet-500/30 hover:bg-violet-500/[0.04] transition-all text-left disabled:opacity-50"
              >
                <span className="text-xl">{crm.icon}</span>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium text-white">{crm.name}</p>
                  <p className="text-[10px] text-zinc-500 truncate">{crm.url_hint || 'Enter your URL'}</p>
                </div>
                <Link2 className="w-3.5 h-3.5 text-violet-400" />
              </button>
            ))}
          </div>
        )}

        {verifying && (
          <div className="flex items-center gap-2 mt-3 text-xs text-violet-300">
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
            Verifying connection...
          </div>
        )}
      </div>

      {/* ═══ Phase 2: Analyzing ═══ */}
      {phase === 'analyzing' && (
        <div className="rounded-xl border border-blue-500/20 bg-blue-500/[0.02] p-8 text-center">
          <Loader2 className="w-8 h-8 animate-spin text-blue-400 mx-auto mb-3" />
          <h3 className="text-sm font-medium text-white mb-1 flex items-center justify-center gap-2">
            <Sparkles className="w-4 h-4 text-blue-400" />
            Analyzing your tickets...
          </h3>
          <p className="text-xs text-zinc-500 max-w-md mx-auto">
            Our CRM Analyser is scanning your last 30 days of tickets to recommend which integrations you need.
            This usually takes 2-3 minutes.
          </p>
        </div>
      )}

      {/* ═══ Phase 3: Recommendations ═══ */}
      {phase === 'recommendations' && analysisResult && (
        <div className="rounded-xl border border-violet-500/20 bg-white/[0.01] p-5">
          <h3 className="text-sm font-medium text-white mb-1 flex items-center gap-2">
            <span className="text-violet-400">②</span>
            Recommended Integrations
          </h3>
          <p className="text-xs text-zinc-500 mb-4">
            {analysisResult.analysis_summary}
          </p>

          {analysisResult.recommendations.length === 0 ? (
            <p className="text-xs text-zinc-500 italic">No additional integrations needed — your CRM covers everything.</p>
          ) : (
            <div className="space-y-2">
              {analysisResult.recommendations.map((rec, i) => {
                const isConnected = connectedRecommendations.has(rec.name);
                return (
                  <div
                    key={i}
                    className={cn(
                      'flex items-center justify-between rounded-lg border p-3 transition-all',
                      isConnected
                        ? 'border-emerald-500/20 bg-emerald-500/[0.02]'
                        : 'border-white/[0.06] bg-white/[0.02] hover:border-violet-500/20',
                    )}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-medium text-white">{rec.name}</p>
                        {rec.priority && (
                          <span className={cn(
                            'text-[9px] px-1.5 py-0.5 rounded-full border',
                            rec.priority === 'high'
                              ? 'bg-red-500/10 text-red-400 border-red-500/20'
                              : 'bg-zinc-500/10 text-zinc-400 border-zinc-500/20',
                          )}>
                            {rec.priority}
                          </span>
                        )}
                      </div>
                      {rec.reason && (
                        <p className="text-[10px] text-zinc-500 mt-0.5">{rec.reason}</p>
                      )}
                    </div>
                    {isConnected ? (
                      <div className="flex items-center gap-2">
                        {testResults[rec.name.toLowerCase().replace(/\s+/g, '-')] && (
                          <span className={cn(
                            'text-[10px] px-2 py-0.5 rounded-full border',
                            testResults[rec.name.toLowerCase().replace(/\s+/g, '-')].works
                              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                              : 'bg-red-500/10 text-red-400 border-red-500/20',
                          )}>
                            {testResults[rec.name.toLowerCase().replace(/\s+/g, '-')].works ? '✓ Verified' : '✗ Failed'}
                          </span>
                        )}
                        <button
                          onClick={() => testIntegration(rec)}
                          disabled={testingSystem === rec.name.toLowerCase().replace(/\s+/g, '-')}
                          className="flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-medium bg-blue-500/10 text-blue-300 border border-blue-500/20 hover:bg-blue-500/20 transition-all disabled:opacity-50"
                        >
                          {testingSystem === rec.name.toLowerCase().replace(/\s+/g, '-') ? (
                            <Loader2 className="w-3 h-3 animate-spin" />
                          ) : (
                            <Search className="w-3 h-3" />
                          )}
                          Test
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => connectRecommendation(rec)}
                        disabled={connecting}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-violet-500/15 text-violet-300 border border-violet-500/30 hover:bg-violet-500/25 transition-all disabled:opacity-50"
                      >
                        <Plug className="w-3 h-3" />
                        Connect
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {/* Background build status indicator (small, non-blocking) */}
          {buildStatus && buildStatus.total_agents > 0 && (
            <div className="mt-4 pt-3 border-t border-white/5">
              <div className="flex items-center gap-3 text-[11px]">
                <span className="text-zinc-500">AI Agents (building in background):</span>
                <span className="text-emerald-400">✓ {buildStatus.ready} ready</span>
                {buildStatus.pending > 0 && (
                  <span className="text-blue-400 flex items-center gap-1">
                    <Loader2 className="w-3 h-3 animate-spin" />
                    {buildStatus.pending} building
                  </span>
                )}
                {buildStatus.failed > 0 && (
                  <span className="text-red-400">✗ {buildStatus.failed} failed</span>
                )}
                {buildStatus.all_ready && (
                  <span className="text-emerald-400 font-medium">— All ready!</span>
                )}
              </div>
            </div>
          )}

          {/* Verify + Continue buttons */}
          {connectedRecommendations.size > 0 && (
            <div className="mt-4 pt-3 border-t border-white/5 space-y-3">
              {/* Verify button — checks all 3 things */}
              <button
                onClick={verifyAll}
                disabled={verifyingAll || !allTested}
                className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg text-sm font-medium bg-blue-500/15 text-blue-300 border border-blue-500/30 hover:bg-blue-500/25 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {verifyingAll ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Search className="w-4 h-4" />
                )}
                {verifyingAll ? 'Verifying...' : 'Verify All Connections'}
              </button>

              {!allTested && connectedRecommendations.size > 0 && (
                <p className="text-[11px] text-amber-400 flex items-center gap-1.5 justify-center">
                  <AlertTriangle className="w-3 h-3" />
                  Test all integrations first ({Object.keys(testResults).length}/{connectedRecommendations.size} tested)
                </p>
              )}

              {/* Progressive loading state during verification */}
              {verifyingAll && (
                <div className="rounded-lg border border-blue-500/20 bg-blue-500/[0.04] p-4 text-xs">
                  <div className="flex items-center gap-2 mb-3 text-blue-300 font-medium">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Verifying your setup...
                  </div>
                  <div className="space-y-2 text-[11px]">
                    {/* Step 1: API keys */}
                    <div className="flex items-center gap-2">
                      {verifyStep > 1 ? (
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                      ) : verifyStep === 1 ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin text-blue-400" />
                      ) : (
                        <div className="w-3.5 h-3.5 rounded-full border border-zinc-600" />
                      )}
                      <span className={verifyStep > 1 ? 'text-emerald-300' : verifyStep === 1 ? 'text-blue-300' : 'text-zinc-500'}>
                        Checking API keys are genuine + working...
                      </span>
                    </div>
                    {/* Step 2: MCP */}
                    <div className="flex items-center gap-2">
                      {verifyStep > 2 ? (
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                      ) : verifyStep === 2 ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin text-blue-400" />
                      ) : (
                        <div className="w-3.5 h-3.5 rounded-full border border-zinc-600" />
                      )}
                      <span className={verifyStep > 2 ? 'text-emerald-300' : verifyStep === 2 ? 'text-blue-300' : 'text-zinc-500'}>
                        Checking MCP connection (pipeline access)...
                      </span>
                    </div>
                    {/* Step 3: Agents */}
                    <div className="flex items-center gap-2">
                      {verifyStep > 3 ? (
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                      ) : verifyStep === 3 ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin text-blue-400" />
                      ) : (
                        <div className="w-3.5 h-3.5 rounded-full border border-zinc-600" />
                      )}
                      <span className={verifyStep > 3 ? 'text-emerald-300' : verifyStep === 3 ? 'text-blue-300' : 'text-zinc-500'}>
                        Checking AI agents + tools are created...
                      </span>
                    </div>
                  </div>
                </div>
              )}

              {/* Final verify result (after all checks complete) */}
              {verifyResult && !verifyingAll && (
                <div className={cn(
                  'rounded-lg border p-4 text-xs transition-all',
                  verifyResult.all_passed
                    ? 'border-emerald-500/30 bg-emerald-500/[0.06] text-emerald-300'
                    : 'border-amber-500/30 bg-amber-500/[0.06] text-amber-300',
                )}>
                  {verifyResult.all_passed ? (
                    <div className="flex items-center gap-2 mb-2">
                      <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                      <p className="font-medium text-sm">{verifyResult.message}</p>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2 mb-2">
                      <AlertTriangle className="w-4 h-4 text-amber-400" />
                      <p className="font-medium text-sm">{verifyResult.message}</p>
                    </div>
                  )}
                  <div className="space-y-1 text-[11px]">
                    <div className="flex items-center gap-2">
                      <span className={verifyResult.api_keys_ok ? 'text-emerald-400' : 'text-red-400'}>
                        {verifyResult.api_keys_ok ? '✓' : '✗'}
                      </span>
                      <span>API keys verified (genuine + working)</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={verifyResult.mcp_ok ? 'text-emerald-400' : 'text-red-400'}>
                        {verifyResult.mcp_ok ? '✓' : '✗'}
                      </span>
                      <span>Connected to MCP (pipeline access)</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={verifyResult.agents_ok ? 'text-emerald-400' : 'text-red-400'}>
                        {verifyResult.agents_ok ? '✓' : '✗'}
                      </span>
                      <span>AI agents + tools created</span>
                    </div>
                  </div>
                </div>
              )}

              {/* Continue button — only activates when verify passes all 3.
                  Fires onComplete so the parent wizard advances the step. */}
              <button
                onClick={() => {
                  if (verifyResult?.all_passed) onComplete?.();
                }}
                disabled={!verifyResult?.all_passed}
                className={cn(
                  'w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg text-sm font-medium transition-all',
                  verifyResult?.all_passed
                    ? 'bg-gradient-to-r from-emerald-500/20 to-violet-500/20 text-white border border-emerald-500/40 hover:from-emerald-500/30 hover:to-violet-500/30 animate-pulse'
                    : 'bg-white/5 text-zinc-600 border border-white/5 cursor-not-allowed',
                )}
              >
                <CheckCircle2 className="w-4 h-4" />
                Continue to Next Step
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>
      )}

      {/* ═══ Error state ═══ */}
      {phase === 'error' && (
        <div className="rounded-xl border border-red-500/20 bg-red-500/[0.02] p-5">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <h3 className="text-sm font-medium text-white mb-1">Analysis failed</h3>
              <p className="text-xs text-zinc-500 mb-3">{analysisError}</p>
              <button
                onClick={retryAnalysis}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium bg-red-500/10 text-red-300 border border-red-500/20 hover:bg-red-500/20 transition-all"
              >
                <Loader2 className="w-3 h-3" />
                Retry analysis
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ═══ Connect Form Modal (Phase 1 + Phase 3) ═══ */}
      {formOpen && selectedCRM && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-2xl border border-white/10 bg-zinc-900 p-6 shadow-2xl max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-medium text-white flex items-center gap-2">
                <span className="text-xl">{selectedCRM.icon}</span>
                Connect {selectedCRM.name}
              </h3>
              <button
                onClick={() => setFormOpen(false)}
                className="text-zinc-500 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3">
              {/* Name field (always shown) */}
              <div>
                <label className="block text-xs text-zinc-400 mb-1">
                  {isDbForm ? 'Database Name *' : 'Name *'}
                </label>
                <input
                  type="text"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  placeholder={isDbForm ? 'Payment Database' : 'My HubSpot Account'}
                  className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-violet-500/50"
                />
              </div>

              {/* ── DATABASE FORM: show DB-specific fields ── */}
              {isDbForm ? (
                <>
                  <div>
                    <label className="block text-xs text-zinc-400 mb-1">Database Type *</label>
                    <select
                      value={formDbType}
                      onChange={(e) => {
                        setFormDbType(e.target.value);
                        // Set default port based on type
                        const ports: Record<string, string> = {
                          postgresql: '5432', mysql: '3306', mongodb: '27017',
                          snowflake: '443', bigquery: '443',
                        };
                        setFormDbPort(ports[e.target.value] || '5432');
                      }}
                      className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-sm text-white focus:outline-none focus:border-violet-500/50"
                    >
                      <option value="postgresql" className="bg-zinc-900">PostgreSQL</option>
                      <option value="mysql" className="bg-zinc-900">MySQL</option>
                      <option value="mongodb" className="bg-zinc-900">MongoDB</option>
                      <option value="snowflake" className="bg-zinc-900">Snowflake</option>
                      <option value="bigquery" className="bg-zinc-900">BigQuery</option>
                    </select>
                  </div>
                  <div className="grid grid-cols-3 gap-2">
                    <div className="col-span-2">
                      <label className="block text-xs text-zinc-400 mb-1">Host *</label>
                      <input
                        type="text"
                        value={formDbHost}
                        onChange={(e) => setFormDbHost(e.target.value)}
                        placeholder="mydb.company.com"
                        className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-violet-500/50 font-mono"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-zinc-400 mb-1">Port</label>
                      <input
                        type="text"
                        value={formDbPort}
                        onChange={(e) => setFormDbPort(e.target.value)}
                        placeholder="5432"
                        className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-violet-500/50 font-mono"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs text-zinc-400 mb-1">Database Name *</label>
                    <input
                      type="text"
                      value={formDbName}
                      onChange={(e) => setFormDbName(e.target.value)}
                      placeholder="payments"
                      className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-violet-500/50 font-mono"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-zinc-400 mb-1">Username * (use read-only user)</label>
                    <input
                      type="text"
                      value={formDbUsername}
                      onChange={(e) => setFormDbUsername(e.target.value)}
                      placeholder="readonly_user"
                      className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-violet-500/50 font-mono"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-zinc-400 mb-1">Password</label>
                    <input
                      type="password"
                      value={formDbPassword}
                      onChange={(e) => setFormDbPassword(e.target.value)}
                      placeholder="••••••••••••"
                      className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-violet-500/50 font-mono"
                    />
                    <p className="text-[10px] text-zinc-600 mt-1">
                      🔒 Read-only enforced. Superglue auto-reads your schema + generates query tools.
                    </p>
                  </div>
                </>
              ) : (
                /* ── API FORM: show URL + API key ── */
                <>
                  <div>
                    <label className="block text-xs text-zinc-400 mb-1">URL *</label>
                    <input
                      type="text"
                      value={formUrl}
                      onChange={(e) => setFormUrl(e.target.value)}
                      placeholder={selectedCRM.url_hint || 'https://api.yourcrm.com'}
                      className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-violet-500/50 font-mono"
                    />
                  </div>
                  {/* Dynamic auth_schema fields (subdomain, email, domain, account_sid, etc.) */}
                  {(selectedCRM as any)?.auth_schema?.map((field: AuthSchemaField) => (
                    <div key={field.key}>
                      <label className="block text-xs text-zinc-400 mb-1">
                        {field.label}{field.required ? ' *' : ''}
                      </label>
                      <input
                        type={field.type === 'password' ? 'password' : 'text'}
                        value={formExtraFields[field.key] || ''}
                        onChange={(e) => setFormExtraFields(prev => ({...prev, [field.key]: e.target.value}))}
                        placeholder={field.placeholder || ''}
                        className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-violet-500/50 font-mono"
                      />
                    </div>
                  ))}
                  {/* API Key field — shown for ALL systems. OAuth-type CRMs
                      accept an API key / access token until the Superglue
                      OAuth redirect endpoint ships; a real credential here
                      beats an empty "OAuth" connect that fails on first use. */}
                  <div>
                    <label className="block text-xs text-zinc-400 mb-1">
                      API Key / Token *
                    </label>
                    <input
                      type="password"
                      value={formApiKey}
                      onChange={(e) => setFormApiKey(e.target.value)}
                      placeholder="••••••••••••"
                      className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-violet-500/50 font-mono"
                    />
                    <p className="text-[10px] text-zinc-600 mt-1">
                      {((selectedCRM as any)?.auth_type === 'oauth')
                        ? `Paste an access token from your ${selectedCRM.name} account — stored securely in Superglue.`
                        : 'Stored securely in Superglue + encrypted in MCP registry.'}
                    </p>
                  </div>
                </>
              )}
            </div>

            <div className="flex gap-2 mt-5">
              <button
                onClick={() => setFormOpen(false)}
                className="flex-1 px-4 py-2 rounded-lg text-xs font-medium bg-white/5 border border-white/10 text-zinc-400 hover:bg-white/10"
              >
                Cancel
              </button>
              <button
                onClick={handleConnect}
                disabled={connecting || !formName.trim() || (isDbForm ? (!formDbHost.trim() || !formDbName.trim()) : (!formUrl.trim() || !formApiKey.trim()))}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-xs font-medium bg-violet-500/20 text-violet-300 border border-violet-500/40 hover:bg-violet-500/30 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {connecting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plug className="w-3.5 h-3.5" />}
                {connecting ? 'Connecting...' : (isDbForm ? 'Connect & Auto-Setup' : 'Connect & Verify')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
