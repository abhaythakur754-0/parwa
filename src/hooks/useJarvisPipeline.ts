/**
 * PARWA Jarvis Pipeline Hooks
 *
 * React hooks for the 3-node JARVIS pipeline features:
 * Quality, SLA, Approvals, Notifications, Wave 8, Emergency, Audit, ROI
 */

'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import {
  jarvisChatApi,
  jarvisNotificationApi,
  jarvisQualityApi,
  jarvisSlaApi,
  jarvisApprovalApi,
  jarvisWave8Api,
  jarvisEmergencyApi,
  jarvisAuditApi,
  jarvisHealthApi,
  jarvisFlagApi,
  jarvisCommandControlApi,
} from '@/lib/jarvis-pipeline-api';

// ── Types ─────────────────────────────────────────────────────────

export type FetchState<T> = {
  status: 'idle' | 'loading' | 'error' | 'success';
  data: T | null;
  error: string | null;
};

// ── useJarvisPipelineStatus ──────────────────────────────────────

export function useJarvisPipelineStatus(tenantId?: string, pollInterval = 30000) {
  const [status, setStatus] = useState<FetchState<Record<string, unknown>>>({ status: 'idle', data: null, error: null });
  const [metrics, setMetrics] = useState<FetchState<Record<string, unknown>>>({ status: 'idle', data: null, error: null });
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const result = await jarvisChatApi.status(tenantId);
      setStatus({ status: 'success', data: result, error: null });
    } catch (err) {
      setStatus(prev => ({ ...prev, error: err instanceof Error ? err.message : 'Failed to fetch status' }));
    }
  }, [tenantId]);

  const fetchMetrics = useCallback(async () => {
    try {
      const result = await jarvisChatApi.metrics(tenantId, 7);
      setMetrics({ status: 'success', data: result, error: null });
    } catch (err) {
      setMetrics(prev => ({ ...prev, error: err instanceof Error ? err.message : 'Failed to fetch metrics' }));
    }
  }, [tenantId]);

  const startPolling = useCallback(() => {
    if (pollRef.current) return;
    fetchStatus();
    fetchMetrics();
    pollRef.current = setInterval(() => {
      fetchStatus();
      fetchMetrics();
    }, pollInterval);
  }, [fetchStatus, fetchMetrics, pollInterval]);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const chat = useCallback(async (question: string, parwaState?: Record<string, unknown>) => {
    try {
      return await jarvisChatApi.chat({ tenant_id: tenantId, question, parwa_state: parwaState });
    } catch (err) {
      throw err;
    }
  }, [tenantId]);

  useEffect(() => {
    return () => stopPolling();
  }, [stopPolling]);

  return { status, metrics, fetchStatus, fetchMetrics, startPolling, stopPolling, chat };
}

// ── useJarvisQuality ───────────────────────────────────────────────

export function useJarvisQuality(tenantId?: string) {
  const [scores, setScores] = useState<FetchState<Record<string, unknown>>>({ status: 'idle', data: null, error: null });
  const [healthScore, setHealthScore] = useState<FetchState<Record<string, unknown>>>({ status: 'idle', data: null, error: null });
  const [driftCheck, setDriftCheck] = useState<FetchState<Record<string, unknown>>>({ status: 'idle', data: null, error: null });
  const [alerts, setAlerts] = useState<FetchState<Record<string, unknown>>>({ status: 'idle', data: null, error: null });
  const [report, setReport] = useState<FetchState<Record<string, unknown>>>({ status: 'idle', data: null, error: null });
  const [recommendations, setRecommendations] = useState<FetchState<Record<string, unknown>>>({ status: 'idle', data: null, error: null });

  const fetchScores = useCallback(async () => {
    setScores(prev => ({ ...prev, status: 'loading' }));
    try {
      const result = await jarvisQualityApi.scores(tenantId);
      setScores({ status: 'success', data: result, error: null });
    } catch (err) {
      setScores(prev => ({ ...prev, status: 'error', error: err instanceof Error ? err.message : 'Failed' }));
    }
  }, [tenantId]);

  const fetchHealthScore = useCallback(async () => {
    setHealthScore(prev => ({ ...prev, status: 'loading' }));
    try {
      const result = await jarvisQualityApi.healthScore(tenantId);
      setHealthScore({ status: 'success', data: result, error: null });
    } catch (err) {
      setHealthScore(prev => ({ ...prev, status: 'error', error: err instanceof Error ? err.message : 'Failed' }));
    }
  }, [tenantId]);

  const fetchDriftCheck = useCallback(async () => {
    setDriftCheck(prev => ({ ...prev, status: 'loading' }));
    try {
      const result = await jarvisQualityApi.driftCheck(tenantId);
      setDriftCheck({ status: 'success', data: result, error: null });
    } catch (err) {
      setDriftCheck(prev => ({ ...prev, status: 'error', error: err instanceof Error ? err.message : 'Failed' }));
    }
  }, [tenantId]);

  const fetchAlerts = useCallback(async () => {
    try {
      const result = await jarvisQualityApi.alerts(tenantId);
      setAlerts({ status: 'success', data: result, error: null });
    } catch (err) {
      setAlerts(prev => ({ ...prev, error: err instanceof Error ? err.message : 'Failed' }));
    }
  }, [tenantId]);

  const fetchReport = useCallback(async () => {
    setReport(prev => ({ ...prev, status: 'loading' }));
    try {
      const result = await jarvisQualityApi.weeklyReport(tenantId);
      setReport({ status: 'success', data: result, error: null });
    } catch (err) {
      setReport(prev => ({ ...prev, status: 'error', error: err instanceof Error ? err.message : 'Failed' }));
    }
  }, [tenantId]);

  const fetchRecommendations = useCallback(async () => {
    try {
      const result = await jarvisQualityApi.recommendations(tenantId);
      setRecommendations({ status: 'success', data: result, error: null });
    } catch (err) {
      setRecommendations(prev => ({ ...prev, error: err instanceof Error ? err.message : 'Failed' }));
    }
  }, [tenantId]);

  const submitFeedback = useCallback(async (ticketId: string, score: number, comment?: string) => {
    return await jarvisQualityApi.feedback({ tenant_id: tenantId, ticket_id: ticketId, score, comment });
  }, [tenantId]);

  const resolveAlert = useCallback(async (alertId: string) => {
    return await jarvisQualityApi.resolveAlert(alertId, tenantId);
  }, [tenantId]);

  const refreshAll = useCallback(() => {
    fetchScores();
    fetchHealthScore();
    fetchDriftCheck();
    fetchAlerts();
  }, [fetchScores, fetchHealthScore, fetchDriftCheck, fetchAlerts]);

  return {
    scores, healthScore, driftCheck, alerts, report, recommendations,
    fetchScores, fetchHealthScore, fetchDriftCheck, fetchAlerts, fetchReport, fetchRecommendations,
    submitFeedback, resolveAlert, refreshAll,
  };
}

// ── useJarvisSLA ──────────────────────────────────────────────────

export function useJarvisSLA(tenantId?: string) {
  const [slaStatus, setSlaStatus] = useState<FetchState<Record<string, unknown>>>({ status: 'idle', data: null, error: null });
  const [credits, setCredits] = useState<FetchState<Record<string, unknown>>>({ status: 'idle', data: null, error: null });

  const fetchStatus = useCallback(async () => {
    setSlaStatus(prev => ({ ...prev, status: 'loading' }));
    try {
      const result = await jarvisSlaApi.status(tenantId);
      setSlaStatus({ status: 'success', data: result, error: null });
    } catch (err) {
      setSlaStatus(prev => ({ ...prev, status: 'error', error: err instanceof Error ? err.message : 'Failed' }));
    }
  }, [tenantId]);

  const fetchCredits = useCallback(async () => {
    setCredits(prev => ({ ...prev, status: 'loading' }));
    try {
      const result = await jarvisSlaApi.credits(tenantId);
      setCredits({ status: 'success', data: result, error: null });
    } catch (err) {
      setCredits(prev => ({ ...prev, status: 'error', error: err instanceof Error ? err.message : 'Failed' }));
    }
  }, [tenantId]);

  const refreshAll = useCallback(() => { fetchStatus(); fetchCredits(); }, [fetchStatus, fetchCredits]);

  return { slaStatus, credits, fetchStatus, fetchCredits, refreshAll };
}

// ── useJarvisApprovals ────────────────────────────────────────────

export function useJarvisApprovals(tenantId?: string) {
  const [pending, setPending] = useState<FetchState<Record<string, unknown>>>({ status: 'idle', data: null, error: null });

  const fetchPending = useCallback(async () => {
    setPending(prev => ({ ...prev, status: 'loading' }));
    try {
      const result = await jarvisApprovalApi.pending(tenantId);
      setPending({ status: 'success', data: result, error: null });
    } catch (err) {
      setPending(prev => ({ ...prev, status: 'error', error: err instanceof Error ? err.message : 'Failed' }));
    }
  }, [tenantId]);

  const batchApprove = useCallback(async (commandIds?: string[]) => {
    return await jarvisApprovalApi.batch({ tenant_id: tenantId, command_ids: commandIds });
  }, [tenantId]);

  return { pending, fetchPending, batchApprove };
}

// ── useJarvisNotifications ────────────────────────────────────────

export function useJarvisNotifications(tenantId?: string) {
  const [notifications, setNotifications] = useState<FetchState<Record<string, unknown>>>({ status: 'idle', data: null, error: null });

  const fetchNotifications = useCallback(async (includeResolved = false) => {
    setNotifications(prev => ({ ...prev, status: 'loading' }));
    try {
      const result = await jarvisNotificationApi.list(tenantId, includeResolved);
      setNotifications({ status: 'success', data: result, error: null });
    } catch (err) {
      setNotifications(prev => ({ ...prev, status: 'error', error: err instanceof Error ? err.message : 'Failed' }));
    }
  }, [tenantId]);

  const resolveNotification = useCallback(async (key: string) => {
    return await jarvisNotificationApi.resolve(key);
  }, []);

  const batchApprove = useCallback(async () => {
    return await jarvisNotificationApi.batchApprove({ tenant_id: tenantId });
  }, [tenantId]);

  const batchReject = useCallback(async () => {
    return await jarvisNotificationApi.batchReject({ tenant_id: tenantId });
  }, [tenantId]);

  return { notifications, fetchNotifications, resolveNotification, batchApprove, batchReject };
}

// ── useJarvisWave8 ────────────────────────────────────────────────

export function useJarvisWave8(tenantId?: string) {
  const [agents, setAgents] = useState<FetchState<Record<string, unknown>>>({ status: 'idle', data: null, error: null });
  const [skills, setSkills] = useState<FetchState<Record<string, unknown>>>({ status: 'idle', data: null, error: null });
  const [logs, setLogs] = useState<FetchState<Record<string, unknown>>>({ status: 'idle', data: null, error: null });
  const [copilotResult, setCopilotResult] = useState<Record<string, unknown> | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const fetchAgents = useCallback(async () => {
    setAgents(prev => ({ ...prev, status: 'loading' }));
    try {
      const result = await jarvisWave8Api.agents(tenantId);
      setAgents({ status: 'success', data: result, error: null });
    } catch (err) {
      setAgents(prev => ({ ...prev, status: 'error', error: err instanceof Error ? err.message : 'Failed' }));
    }
  }, [tenantId]);

  const fetchSkills = useCallback(async () => {
    setSkills(prev => ({ ...prev, status: 'loading' }));
    try {
      const result = await jarvisWave8Api.skills(tenantId);
      setSkills({ status: 'success', data: result, error: null });
    } catch (err) {
      setSkills(prev => ({ ...prev, status: 'error', error: err instanceof Error ? err.message : 'Failed' }));
    }
  }, [tenantId]);

  const fetchLogs = useCallback(async () => {
    setLogs(prev => ({ ...prev, status: 'loading' }));
    try {
      const result = await jarvisWave8Api.provisioningLogs(tenantId);
      setLogs({ status: 'success', data: result, error: null });
    } catch (err) {
      setLogs(prev => ({ ...prev, status: 'error', error: err instanceof Error ? err.message : 'Failed' }));
    }
  }, [tenantId]);

  const provision = useCallback(async (agentName: string, agentType: string, capabilities?: string[]) => {
    setIsLoading(true);
    try {
      return await jarvisWave8Api.provision({ tenant_id: tenantId, agent_name: agentName, agent_type: agentType, capabilities });
    } finally { setIsLoading(false); }
  }, [tenantId]);

  const teach = useCallback(async (agentName: string, skillName: string, skillContent: string) => {
    setIsLoading(true);
    try {
      return await jarvisWave8Api.teach({ tenant_id: tenantId, agent_name: agentName, skill_name: skillName, skill_content: skillContent });
    } finally { setIsLoading(false); }
  }, [tenantId]);

  const copilotDraft = useCallback(async (ticketId: string, customerQuery: string, channel?: string) => {
    setIsLoading(true);
    try {
      const result = await jarvisWave8Api.copilotDraft({ tenant_id: tenantId, ticket_id: ticketId, customer_query: customerQuery, channel });
      setCopilotResult(result);
      return result;
    } finally { setIsLoading(false); }
  }, [tenantId]);

  const copilotEdit = useCallback(async (ticketId: string, draftText: string, editedText: string) => {
    setIsLoading(true);
    try {
      return await jarvisWave8Api.copilotEdit({ tenant_id: tenantId, ticket_id: ticketId, draft_text: draftText, edited_text: editedText });
    } finally { setIsLoading(false); }
  }, [tenantId]);

  const proactive = useCallback(async (targetCustomer: string, message: string) => {
    setIsLoading(true);
    try {
      return await jarvisWave8Api.proactive({ tenant_id: tenantId, target_customer: targetCustomer, message });
    } finally { setIsLoading(false); }
  }, [tenantId]);

  const correction = useCallback(async (originalResponse: string, correctedResponse: string, ticketId?: string) => {
    setIsLoading(true);
    try {
      return await jarvisWave8Api.correction({ tenant_id: tenantId, original_response: originalResponse, corrected_response: correctedResponse, ticket_id: ticketId });
    } finally { setIsLoading(false); }
  }, [tenantId]);

  return {
    agents, skills, logs, copilotResult, isLoading,
    fetchAgents, fetchSkills, fetchLogs,
    provision, teach, copilotDraft, copilotEdit, proactive, correction,
  };
}

// ── useJarvisEmergency ─────────────────────────────────────────────

export function useJarvisEmergency(tenantId?: string) {
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);

  const emergencyShutdown = useCallback(async (reason?: string) => {
    setIsLoading(true);
    try {
      const res = await jarvisEmergencyApi.shutdown({ tenant_id: tenantId, reason });
      setResult(res);
      return res;
    } finally { setIsLoading(false); }
  }, [tenantId]);

  const pauseAllRefunds = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await jarvisEmergencyApi.pauseAllRefunds({ tenant_id: tenantId });
      setResult(res);
      return res;
    } finally { setIsLoading(false); }
  }, [tenantId]);

  return { isLoading, result, emergencyShutdown, pauseAllRefunds };
}

// ── useJarvisAudit ──────────────────────────────────────────────

export function useJarvisAudit(tenantId?: string) {
  const [audit, setAudit] = useState<FetchState<Record<string, unknown>>>({ status: 'idle', data: null, error: null });

  const fetchAudit = useCallback(async (limit = 50) => {
    setAudit(prev => ({ ...prev, status: 'loading' }));
    try {
      const result = await jarvisAuditApi.list(tenantId, limit);
      setAudit({ status: 'success', data: result, error: null });
    } catch (err) {
      setAudit(prev => ({ ...prev, status: 'error', error: err instanceof Error ? err.message : 'Failed' }));
    }
  }, [tenantId]);

  return { audit, fetchAudit };
}

// ── useJarvisROI ─────────────────────────────────────────────────

export function useJarvisROI(tenantId?: string) {
  const [roi, setRoi] = useState<FetchState<Record<string, unknown>>>({ status: 'idle', data: null, error: null });

  const fetchROI = useCallback(async (days = 30) => {
    setRoi(prev => ({ ...prev, status: 'loading' }));
    try {
      const result = await jarvisHealthApi.roi(tenantId, days);
      setRoi({ status: 'success', data: result, error: null });
    } catch (err) {
      setRoi(prev => ({ ...prev, status: 'error', error: err instanceof Error ? err.message : 'Failed' }));
    }
  }, [tenantId]);

  return { roi, fetchROI };
}

// ── useJarvisCustomerHealth ──────────────────────────────────────

export function useJarvisCustomerHealth(tenantId?: string) {
  const [health, setHealth] = useState<FetchState<Record<string, unknown>>>({ status: 'idle', data: null, error: null });

  const fetchHealth = useCallback(async () => {
    setHealth(prev => ({ ...prev, status: 'loading' }));
    try {
      const result = await jarvisHealthApi.customerHealth(tenantId);
      setHealth({ status: 'success', data: result, error: null });
    } catch (err) {
      setHealth(prev => ({ ...prev, status: 'error', error: err instanceof Error ? err.message : 'Failed' }));
    }
  }, [tenantId]);

  return { health, fetchHealth };
}

// ── useJarvisFlags ───────────────────────────────────────────────

export function useJarvisFlags(tenantId?: string) {
  const [flags, setFlags] = useState<FetchState<Record<string, unknown>>>({ status: 'idle', data: null, error: null });

  const fetchFlags = useCallback(async () => {
    try {
      const result = await jarvisFlagApi.list(tenantId);
      setFlags({ status: 'success', data: result, error: null });
    } catch (err) {
      setFlags(prev => ({ ...prev, error: err instanceof Error ? err.message : 'Failed' }));
    }
  }, [tenantId]);

  const setFlag = useCallback(async (flagKey: string, flagValue: string, reason?: string) => {
    return await jarvisFlagApi.set({ tenant_id: tenantId, flag_key: flagKey, flag_value: flagValue, reason });
  }, [tenantId]);

  const revokeFlag = useCallback(async (id: string) => {
    return await jarvisFlagApi.revoke(id, tenantId);
  }, [tenantId]);

  return { flags, fetchFlags, setFlag, revokeFlag };
}

// ── useJarvisCommandControl ──────────────────────────────────────

export function useJarvisCommandControl(tenantId?: string) {
  const [isLoading, setIsLoading] = useState(false);
  const [lastResult, setLastResult] = useState<Record<string, unknown> | null>(null);

  const pause = useCallback(async (reason?: string) => {
    setIsLoading(true);
    try {
      const res = await jarvisCommandControlApi.pause({ tenant_id: tenantId, reason });
      setLastResult(res);
      return res;
    } finally { setIsLoading(false); }
  }, [tenantId]);

  const resume = useCallback(async (reason?: string) => {
    setIsLoading(true);
    try {
      const res = await jarvisCommandControlApi.resume({ tenant_id: tenantId, reason });
      setLastResult(res);
      return res;
    } finally { setIsLoading(false); }
  }, [tenantId]);

  const redirect = useCallback(async (targetVariant: string, reason?: string) => {
    setIsLoading(true);
    try {
      const res = await jarvisCommandControlApi.redirect({ tenant_id: tenantId, target_variant: targetVariant, reason });
      setLastResult(res);
      return res;
    } finally { setIsLoading(false); }
  }, [tenantId]);

  const setMode = useCallback(async (mode: string) => {
    setIsLoading(true);
    try {
      const res = await jarvisCommandControlApi.setMode({ tenant_id: tenantId, mode });
      setLastResult(res);
      return res;
    } finally { setIsLoading(false); }
  }, [tenantId]);

  return { isLoading, lastResult, pause, resume, redirect, setMode };
}
