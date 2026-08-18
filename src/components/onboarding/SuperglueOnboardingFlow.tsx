'use client';

/**
 * SuperglueOnboardingFlow — 3-phase progressive integration flow.
 *
 * Phase 1: CRM Connect — show ONE CRM card. User connects + verifies.
 *          Verify = Superglue GET check + MCPConnection DB record.
 * Phase 2: CRM Analysis — auto-trigger /api/integrations/analyze.
 *          Show loading spinner (2-3 min, analyser scans 30 days of tickets).
 * Phase 3: Recommended Integrations — show analyser results as connectable
 *          cards below the CRM. User connects each via Superglue.
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

const CRM_OPTIONS: CRMType[] = [
  { id: 'hubspot',   name: 'HubSpot',      icon: '🎯', url_hint: 'https://api.hubapi.com' },
  { id: 'zendesk',   name: 'Zendesk',      icon: '🎫', url_hint: 'https://{subdomain}.zendesk.com/api/v2' },
  { id: 'custom',    name: 'Custom CRM',   icon: '🔌', url_hint: '' },
];

// ── Component ────────────────────────────────────────────────────────

export function SuperglueOnboardingFlow() {
  const [phase, setPhase] = useState<Phase>('crm-connect');
  const [selectedCRM, setSelectedCRM] = useState<CRMType | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [formName, setFormName] = useState('');
  const [formUrl, setFormUrl] = useState('');
  const [formApiKey, setFormApiKey] = useState('');
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
  const openCRMForm = (crm: CRMType) => {
    setSelectedCRM(crm);
    setFormName(crm.name === 'Custom CRM' ? '' : crm.name);
    setFormUrl(crm.url_hint || '');
    setFormApiKey('');
    setFormOpen(true);
  };

  // ── Phase 1: Connect CRM to Superglue ─────────────────────────────
  const handleConnectCRM = async () => {
    if (!selectedCRM || !formName.trim() || !formUrl.trim()) {
      toast.error('Name and URL are required');
      return;
    }
    setConnecting(true);
    try {
      const res = await fetch('/api/superglue/systems', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          system_id: selectedCRM.id,
          name: formName.trim(),
          url: formUrl.trim(),
          credentials: formApiKey.trim() ? { api_key: formApiKey.trim() } : {},
          icon: selectedCRM.icon,
          metadata: { is_crm: true },
        }),
      });
      const data = await res.json();
      if (res.ok) {
        toast.success(`${formName} connected to Superglue`);
        setFormOpen(false);
        // Auto-verify after connect
        await handleVerify(selectedCRM.id);
      } else {
        toast.error(data.detail || 'Failed to connect');
      }
    } catch {
      toast.error('Network error — could not reach Superglue');
    } finally {
      setConnecting(false);
    }
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
        setAnalysisError(data.detail || 'Analysis failed');
        setPhase('error');
      }
    } catch {
      setAnalysisError('Network error — could not reach the CRM Analyser');
      setPhase('error');
    }
  };

  // ── Phase 3: Connect a recommended integration ────────────────────
  const connectRecommendation = async (rec: AnalysisRecommendation) => {
    const systemId = rec.name.toLowerCase().replace(/\s+/g, '-');
    setConnecting(true);
    try {
      const res = await fetch('/api/superglue/systems', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          system_id: systemId,
          name: rec.name,
          url: '', // user will need to fill this in a real flow
          credentials: {},
          icon: '🔌',
          metadata: { recommendation_reason: rec.reason || '' },
        }),
      });
      if (res.ok) {
        toast.success(`${rec.name} connected`);
        setConnectedRecommendations((prev) => new Set(prev).add(rec.name));
      } else {
        const data = await res.json();
        toast.error(data.detail || `Failed to connect ${rec.name}`);
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

          {/* Data profile summary */}
          {analysisResult.data_profile && Object.keys(analysisResult.data_profile).length > 0 && (
            <div className="mt-4 pt-3 border-t border-white/5">
              <p className="text-[10px] text-zinc-600 mb-1">Analysis details:</p>
              <pre className="text-[10px] text-zinc-500 font-mono overflow-x-auto">
                {JSON.stringify(analysisResult.data_profile, null, 2)}
              </pre>
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

              {/* Continue button — only activates when verify passes all 3 */}
              <button
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

      {/* ═══ Connect Form Modal (Phase 1) ═══ */}
      {formOpen && selectedCRM && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-2xl border border-white/10 bg-zinc-900 p-6 shadow-2xl">
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
              <div>
                <label className="block text-xs text-zinc-400 mb-1">CRM Name *</label>
                <input
                  type="text"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  placeholder="My HubSpot Account"
                  className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-violet-500/50"
                />
              </div>
              <div>
                <label className="block text-xs text-zinc-400 mb-1">CRM URL *</label>
                <input
                  type="text"
                  value={formUrl}
                  onChange={(e) => setFormUrl(e.target.value)}
                  placeholder={selectedCRM.url_hint || 'https://api.yourcrm.com'}
                  className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-violet-500/50 font-mono"
                />
              </div>
              <div>
                <label className="block text-xs text-zinc-400 mb-1">API Key / Token</label>
                <input
                  type="password"
                  value={formApiKey}
                  onChange={(e) => setFormApiKey(e.target.value)}
                  placeholder="••••••••••••"
                  className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-violet-500/50 font-mono"
                />
                <p className="text-[10px] text-zinc-600 mt-1">Stored securely in Superglue + encrypted in MCP registry.</p>
              </div>
            </div>

            <div className="flex gap-2 mt-5">
              <button
                onClick={() => setFormOpen(false)}
                className="flex-1 px-4 py-2 rounded-lg text-xs font-medium bg-white/5 border border-white/10 text-zinc-400 hover:bg-white/10"
              >
                Cancel
              </button>
              <button
                onClick={handleConnectCRM}
                disabled={connecting || !formName.trim() || !formUrl.trim()}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-xs font-medium bg-violet-500/20 text-violet-300 border border-violet-500/40 hover:bg-violet-500/30 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {connecting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plug className="w-3.5 h-3.5" />}
                {connecting ? 'Connecting...' : 'Connect & Verify'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
