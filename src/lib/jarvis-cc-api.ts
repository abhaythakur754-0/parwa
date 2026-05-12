/**
 * PARWA Jarvis CC API Client (Phase 5)
 *
 * Centralized API client for Jarvis Customer Care endpoints.
 * All endpoints mirror backend/app/api/jarvis_cc.py
 */

import { get, post, patch, del } from '@/lib/api';
import type {
  JarvisCCSession,
  JarvisCCMessage,
  JarvisCCContext,
  JarvisCCSessionHealth,
  CCMessageSendRequest,
  CCSessionCreateRequest,
  CCContextUpdateRequest,
  CCHistoryResponse,
  AwarenessTickRequest,
  AwarenessTickResult,
  AwarenessSnapshot,
  SnapshotListResponse,
  AwarenessDelta,
  ProactiveAlert,
  AlertListResponse,
  AlertActionRequest,
  CommandSendRequest,
  CommandResponse,
  QuickCommandRequest,
  CommandUndoRequest,
  CommandHistoryResponse,
  QuickCommandListResponse,
  CoPilotSuggestion,
  CustomQuickCommandAddRequest,
  CustomQuickCommandRemoveRequest,
} from '@/types/jarvis-cc';

const BASE = '/api/jarvis/cc';

// ── Helper ──────────────────────────────────────────────────────────

function qs(params: Record<string, unknown>): string {
  const parts = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null && v !== '')
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
    .join('&');
  return parts ? `?${parts}` : '';
}

// ── Session API ─────────────────────────────────────────────────────

export const ccSessionApi = {
  create: (data: CCSessionCreateRequest = {}) =>
    post<JarvisCCSession>(`${BASE}/session`, data),

  get: (sessionId: string) =>
    get<JarvisCCSession>(`${BASE}/session${qs({ session_id: sessionId })}`),

  health: (sessionId: string) =>
    get<JarvisCCSessionHealth>(`${BASE}/session/health${qs({ session_id: sessionId })}`),
};

// ── Message API ─────────────────────────────────────────────────────

export const ccMessageApi = {
  send: (data: CCMessageSendRequest) =>
    post<JarvisCCMessage>(`${BASE}/message`, data),

  history: (sessionId: string, limit = 50, offset = 0) =>
    get<CCHistoryResponse>(`${BASE}/history${qs({ session_id: sessionId, limit, offset })}`),
};

// ── Context API ─────────────────────────────────────────────────────

export const ccContextApi = {
  get: (sessionId: string) =>
    get<JarvisCCContext>(`${BASE}/context${qs({ session_id: sessionId })}`),

  update: (sessionId: string, data: CCContextUpdateRequest) =>
    patch<JarvisCCSession>(`${BASE}/context${qs({ session_id: sessionId })}`, data),
};

// ── Awareness API ───────────────────────────────────────────────────

export const ccAwarenessApi = {
  tick: (data: AwarenessTickRequest) =>
    post<AwarenessTickResult>(`${BASE}/awareness/tick`, data),

  snapshot: (sessionId: string) =>
    get<AwarenessSnapshot>(`${BASE}/awareness/snapshot${qs({ session_id: sessionId })}`),

  snapshots: (sessionId: string, limit = 20, offset = 0) =>
    get<SnapshotListResponse>(`${BASE}/awareness/snapshots${qs({ session_id: sessionId, limit, offset })}`),

  delta: (sessionId: string) =>
    get<AwarenessDelta>(`${BASE}/awareness/delta${qs({ session_id: sessionId })}`),
};

// ── Alerts API ──────────────────────────────────────────────────────

export const ccAlertApi = {
  list: (sessionId: string, filters?: { severity?: string; category?: string; limit?: number; offset?: number }) =>
    get<AlertListResponse>(`${BASE}/awareness/alerts${qs({ session_id: sessionId, ...filters })}`),

  acknowledge: (sessionId: string, data: AlertActionRequest) =>
    post<ProactiveAlert>(`${BASE}/awareness/alerts/acknowledge${qs({ session_id: sessionId })}`, data),

  dismiss: (sessionId: string, data: AlertActionRequest) =>
    post<ProactiveAlert>(`${BASE}/awareness/alerts/dismiss${qs({ session_id: sessionId })}`, data),

  resolve: (sessionId: string, data: AlertActionRequest) =>
    post<ProactiveAlert>(`${BASE}/awareness/alerts/resolve${qs({ session_id: sessionId })}`, data),
};

// ── Command API ─────────────────────────────────────────────────────

export const ccCommandApi = {
  send: (data: CommandSendRequest) =>
    post<CommandResponse>(`${BASE}/command`, data),

  quick: (data: QuickCommandRequest) =>
    post<CommandResponse>(`${BASE}/command/quick`, data),

  undo: (data: CommandUndoRequest) =>
    post<CommandResponse>(`${BASE}/command/undo`, data),

  history: (sessionId: string, filters?: { status?: string; intent?: string; source?: string; limit?: number; offset?: number }) =>
    get<CommandHistoryResponse>(`${BASE}/command/history${qs({ session_id: sessionId, ...filters })}`),

  quickCommands: (sessionId: string) =>
    get<QuickCommandListResponse>(`${BASE}/command/quick-commands${qs({ session_id: sessionId })}`),

  getById: (sessionId: string, commandId: string) =>
    get<Record<string, unknown>>(`${BASE}/command/${commandId}${qs({ session_id: sessionId })}`),

  coPilot: (sessionId: string, userContext?: string) =>
    post<CoPilotSuggestion>(`${BASE}/command/co-pilot${qs({ session_id: sessionId, user_context: userContext })}`),

  addCustomQuickCommand: (data: CustomQuickCommandAddRequest) =>
    post<Record<string, unknown>>(`${BASE}/command/custom-quick-command`, data),

  removeCustomQuickCommand: (data: CustomQuickCommandRemoveRequest) =>
    del<Record<string, unknown>>(`${BASE}/command/custom-quick-command`),
};

// ── Debug API ───────────────────────────────────────────────────────

export const ccDebugApi = {
  prompt: (sessionId: string) =>
    get<{ session_id: string; prompt: string }>(`${BASE}/prompt${qs({ session_id: sessionId })}`),
};
