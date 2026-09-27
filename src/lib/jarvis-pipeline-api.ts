/**
 * PARWA Jarvis Pipeline API Client
 *
 * Typed API client for the 3-node JARVIS pipeline endpoints.
 * All endpoints mirror backend/app/api/jarvis_routes.py
 *
 * Pipeline: SENSE → EVALUATE → NOTIFY
 * Routes: /api/pipeline/jarvis/*, /api/pipeline/quality/*, /api/pipeline/sla/*,
 *         /api/pipeline/approvals/*, /api/pipeline/wave8/*, /api/pipeline/emergency/*
 *
 * NOTE: All paths use /api/pipeline/<service>/<endpoint> prefix. The Next.js BFF
 * catch-all at /api/pipeline/[...path]/route.ts strips /api/pipeline and forwards
 * to the backend root path (e.g. /jarvis/status, /quality/scores, /sla/status).
 * This avoids conflicts with existing BFF routes at /api/jarvis/*, /api/approvals/*,
 * /api/tickets/* which serve different backend routers.
 */

import { get, post, patch, del } from '@/lib/api';

// ── Helper ──────────────────────────────────────────────────────────

function qs(params: Record<string, unknown>): string {
  const parts = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null && v !== '')
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
    .join('&');
  return parts ? `?${parts}` : '';
}

// ── Types ─────────────────────────────────────────────────────────

export interface ChatRequest {
  tenant_id?: string;
  question: string;
  parwa_state?: Record<string, unknown>;
}

export interface MetricsQuery {
  tenant_id?: string;
  days?: number;
}

export interface NotificationsQuery {
  tenant_id?: string;
  include_resolved?: boolean;
}

export interface BatchActionRequest {
  tenant_id?: string;
}

export interface SetFlagRequest {
  tenant_id?: string;
  flag_key: string;
  flag_value: string;
  reason?: string;
}

export interface PauseRequest {
  tenant_id?: string;
  reason?: string;
}

export interface ResumeRequest {
  tenant_id?: string;
  reason?: string;
}

export interface RedirectRequest {
  tenant_id?: string;
  target_variant?: string;
  reason?: string;
}

export interface ModeRequest {
  tenant_id?: string;
  mode: string;
}

export interface QualityFeedbackRequest {
  tenant_id?: string;
  ticket_id?: string;
  score: number;
  comment?: string;
}

export interface ApprovalBatchRequest {
  tenant_id?: string;
  command_ids?: string[];
}

export interface EmergencyShutdownRequest {
  tenant_id?: string;
  reason?: string;
}

export interface Wave8ProvisionRequest {
  tenant_id?: string;
  agent_name?: string;
  agent_type?: string;
  capabilities?: string[];
}

export interface Wave8TeachRequest {
  tenant_id?: string;
  agent_name?: string;
  skill_name?: string;
  skill_content?: string;
}

export interface Wave8CopilotDraftRequest {
  tenant_id?: string;
  ticket_id?: string;
  customer_query?: string;
  channel?: string;
}

export interface Wave8CopilotEditRequest {
  tenant_id?: string;
  ticket_id?: string;
  draft_text?: string;
  edited_text?: string;
}

export interface Wave8ProactiveRequest {
  tenant_id?: string;
  target_customer?: string;
  message?: string;
}

export interface Wave8CorrectionRequest {
  tenant_id?: string;
  original_response?: string;
  corrected_response?: string;
  ticket_id?: string;
}

// ── Chat & Status API ──────────────────────────────────────────────

export const jarvisChatApi = {
  chat: (data: ChatRequest) =>
    post<Record<string, unknown>>('/api/pipeline/jarvis/chat', data),

  status: (tenantId?: string) =>
    get<Record<string, unknown>>(`/api/pipeline/jarvis/status${qs({ tenant_id: tenantId })}`),

  metrics: (tenantId?: string, days = 7) =>
    get<Record<string, unknown>>(`/api/pipeline/jarvis/metrics${qs({ tenant_id: tenantId, days })}`),
};

// ── Notifications API ─────────────────────────────────────────────

export const jarvisNotificationApi = {
  list: (tenantId?: string, includeResolved = false) =>
    get<Record<string, unknown>>(`/api/pipeline/jarvis/notifications${qs({ tenant_id: tenantId, include_resolved: includeResolved })}`),

  resolve: (key: string) =>
    post<Record<string, unknown>>(`/api/pipeline/jarvis/notifications/${encodeURIComponent(key)}/resolve`, {}),

  batchApprove: (data: BatchActionRequest) =>
    post<Record<string, unknown>>('/api/pipeline/jarvis/notifications/batch/approve', data),

  batchReject: (data: BatchActionRequest) =>
    post<Record<string, unknown>>('/api/pipeline/jarvis/notifications/batch/reject', data),
};

// ── Flags API ─────────────────────────────────────────────────────

export const jarvisFlagApi = {
  list: (tenantId?: string) =>
    get<Record<string, unknown>>(`/api/pipeline/jarvis/flags${qs({ tenant_id: tenantId })}`),

  set: (data: SetFlagRequest) =>
    post<Record<string, unknown>>('/api/pipeline/jarvis/flags', data),

  revoke: (id: string, tenantId?: string) =>
    post<Record<string, unknown>>(`/api/pipeline/jarvis/flags/${encodeURIComponent(id)}/revoke`, { tenant_id: tenantId }),
};

// ── Command Control API ──────────────────────────────────────────

export const jarvisCommandControlApi = {
  pause: (data: PauseRequest) =>
    post<Record<string, unknown>>('/api/pipeline/jarvis/command/pause', data),

  resume: (data: ResumeRequest) =>
    post<Record<string, unknown>>('/api/pipeline/jarvis/command/resume', data),

  redirect: (data: RedirectRequest) =>
    post<Record<string, unknown>>('/api/pipeline/jarvis/command/redirect', data),

  setMode: (data: ModeRequest) =>
    post<Record<string, unknown>>('/api/pipeline/jarvis/command/mode', data),
};

// ── Quality API ──────────────────────────────────────────────────

export const jarvisQualityApi = {
  scores: (tenantId?: string) =>
    get<Record<string, unknown>>(`/api/pipeline/quality/scores${qs({ tenant_id: tenantId })}`),

  alerts: (tenantId?: string) =>
    get<Record<string, unknown>>(`/api/pipeline/quality/alerts${qs({ tenant_id: tenantId })}`),

  resolveAlert: (alertId: string, tenantId?: string) =>
    post<Record<string, unknown>>(`/api/pipeline/quality/alerts/${encodeURIComponent(alertId)}/resolve`, { tenant_id: tenantId }),

  recommendations: (tenantId?: string) =>
    get<Record<string, unknown>>(`/api/pipeline/quality/recommendations${qs({ tenant_id: tenantId })}`),

  feedback: (data: QualityFeedbackRequest) =>
    post<Record<string, unknown>>('/api/pipeline/quality/feedback', data),

  weeklyReport: (tenantId?: string) =>
    get<Record<string, unknown>>(`/api/pipeline/quality/weekly-report${qs({ tenant_id: tenantId })}`),

  healthScore: (tenantId?: string) =>
    get<Record<string, unknown>>(`/api/pipeline/quality/health-score${qs({ tenant_id: tenantId })}`),

  driftCheck: (tenantId?: string) =>
    get<Record<string, unknown>>(`/api/pipeline/quality/drift-check${qs({ tenant_id: tenantId })}`),
};

// ── SLA API ──────────────────────────────────────────────────────

export const jarvisSlaApi = {
  status: (tenantId?: string) =>
    get<Record<string, unknown>>(`/api/pipeline/sla/status${qs({ tenant_id: tenantId })}`),

  credits: (tenantId?: string) =>
    get<Record<string, unknown>>(`/api/pipeline/sla/credits${qs({ tenant_id: tenantId })}`),
};

// ── Approvals API ────────────────────────────────────────────────

export const jarvisApprovalApi = {
  pending: (tenantId?: string) =>
    get<Record<string, unknown>>(`/api/pipeline/approvals/pending${qs({ tenant_id: tenantId })}`),

  batch: (data: ApprovalBatchRequest) =>
    post<Record<string, unknown>>('/api/pipeline/approvals/batch', data),
};

// ── Emergency API ─────────────────────────────────────────────────

export const jarvisEmergencyApi = {
  shutdown: (data: EmergencyShutdownRequest) =>
    post<Record<string, unknown>>('/api/pipeline/emergency/shutdown', data),

  pauseAllRefunds: (data: BatchActionRequest) =>
    post<Record<string, unknown>>('/api/pipeline/pause_all_refunds', data),
};

// ── Audit API ─────────────────────────────────────────────────────

export const jarvisAuditApi = {
  list: (tenantId?: string, limit = 50) =>
    get<Record<string, unknown>>(`/api/pipeline/jarvis/audit${qs({ tenant_id: tenantId, limit })}`),
};

// ── Customer Health & ROI API ──────────────────────────────────────

export const jarvisHealthApi = {
  customerHealth: (tenantId?: string) =>
    get<Record<string, unknown>>(`/api/pipeline/jarvis/customer-health${qs({ tenant_id: tenantId })}`),

  roi: (tenantId?: string, days = 30) =>
    get<Record<string, unknown>>(`/api/pipeline/jarvis/roi${qs({ tenant_id: tenantId, days })}`),
};

// ── Ticket Submission API ─────────────────────────────────────────

export const jarvisTicketApi = {
  submit: (data: Record<string, unknown>) =>
    post<Record<string, unknown>>('/api/pipeline/tickets/submit', data),
};

// ── Wave 8 API ───────────────────────────────────────────────────

export const jarvisWave8Api = {
  agents: (tenantId?: string) =>
    get<Record<string, unknown>>(`/api/pipeline/wave8/agents${qs({ tenant_id: tenantId })}`),

  provision: (data: Wave8ProvisionRequest) =>
    post<Record<string, unknown>>('/api/pipeline/wave8/provision', data),

  skills: (tenantId?: string) =>
    get<Record<string, unknown>>(`/api/pipeline/wave8/skills${qs({ tenant_id: tenantId })}`),

  teach: (data: Wave8TeachRequest) =>
    post<Record<string, unknown>>('/api/pipeline/wave8/teach', data),

  copilotDraft: (data: Wave8CopilotDraftRequest) =>
    post<Record<string, unknown>>('/api/pipeline/wave8/copilot/draft', data),

  copilotEdit: (data: Wave8CopilotEditRequest) =>
    post<Record<string, unknown>>('/api/pipeline/wave8/copilot/edit', data),

  proactive: (data: Wave8ProactiveRequest) =>
    post<Record<string, unknown>>('/api/pipeline/wave8/proactive', data),

  correction: (data: Wave8CorrectionRequest) =>
    post<Record<string, unknown>>('/api/pipeline/wave8/correction', data),

  provisioningLogs: (tenantId?: string) =>
    get<Record<string, unknown>>(`/api/pipeline/wave8/provisioning-logs${qs({ tenant_id: tenantId })}`),
};
