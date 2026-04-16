/**
 * PARWA Shadow Mode API Client
 *
 * Typed client for all shadow mode endpoints.
 * Uses the shared apiClient (axios instance with httpOnly cookie auth + CSRF).
 */

import { get, post, put, patch, del } from '@/lib/api';

// ── Types ──────────────────────────────────────────────────────────────────

export type SystemMode = 'shadow' | 'supervised' | 'graduated';
export type ManagerDecision = 'approved' | 'rejected' | 'modified' | null;

export interface ShadowPreference {
  id: string;
  action_category: string;
  preferred_mode: SystemMode;
  set_via: 'ui' | 'jarvis';
  updated_at: string;
}

export interface ShadowLogEntry {
  id: string;
  action_type: string;
  action_payload: Record<string, any>;
  jarvis_risk_score: number | null;
  mode: SystemMode;
  manager_decision: ManagerDecision;
  manager_note: string | null;
  resolved_at: string | null;
  created_at: string;
}

export interface ShadowStats {
  total_actions: number;
  approval_rate: number;
  rejection_rate: number;
  auto_approved_rate: number;
  avg_risk_score: number;
  mode_distribution: Record<SystemMode, number>;
  pending_count: number;
  action_type_distribution: Record<string, number>;
}

export interface RiskEvaluation {
  mode: SystemMode;
  risk_score: number;
  reason: string;
  requires_approval: boolean;
  auto_execute: boolean;
}

export interface ShadowLogListResponse {
  items: ShadowLogEntry[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface ModeResponse {
  mode: SystemMode;
  previous_mode: SystemMode | null;
  changed_at: string | null;
}

export interface PreferenceListResponse {
  preferences: ShadowPreference[];
  total: number;
}

// ── Shadow API Client ────────────────────────────────────────────────────

export const shadowApi = {
  /** Get current shadow mode */
  getMode: () => get<ModeResponse>('/api/shadow/mode'),

  /** Set shadow mode */
  setMode: (mode: SystemMode) => put<ModeResponse>('/api/shadow/mode', { mode }),

  /** Get all action-category preferences */
  getPreferences: () => get<PreferenceListResponse>('/api/shadow/preferences'),

  /** Set preference for an action category */
  setPreference: (category: string, mode: SystemMode) =>
    patch<ShadowPreference>('/api/shadow/preferences', {
      action_category: category,
      preferred_mode: mode,
    }),

  /** Delete a preference (reset to default) */
  deletePreference: (category: string) =>
    del(`/api/shadow/preferences/${category}`),

  /** Get shadow log with pagination and filters */
  getLog: (params?: {
    page?: number;
    page_size?: number;
    action_type?: string;
    mode?: SystemMode;
    decision?: ManagerDecision;
    date_from?: string;
    date_to?: string;
    sort_by?: string;
    sort_dir?: 'asc' | 'desc';
  }) => {
    const sp = new URLSearchParams();
    if (params?.page) sp.set('page', String(params.page));
    if (params?.page_size) sp.set('page_size', String(params.page_size));
    if (params?.action_type) sp.set('action_type', params.action_type);
    if (params?.mode) sp.set('mode', params.mode);
    if (params?.decision) sp.set('decision', params.decision);
    if (params?.date_from) sp.set('date_from', params.date_from);
    if (params?.date_to) sp.set('date_to', params.date_to);
    if (params?.sort_by) sp.set('sort_by', params.sort_by);
    if (params?.sort_dir) sp.set('sort_dir', params.sort_dir);
    const qs = sp.toString();
    return get<ShadowLogListResponse>(`/api/shadow/log${qs ? `?${qs}` : ''}`);
  },

  /** Get shadow mode statistics */
  getStats: () => get<ShadowStats>('/api/shadow/stats'),

  /** Evaluate a what-if scenario */
  evaluate: (actionType: string, payload: Record<string, any>) =>
    post<RiskEvaluation>('/api/shadow/evaluate', {
      action_type: actionType,
      action_payload: payload,
    }),

  /** Approve a shadow action */
  approve: (id: string, note?: string) =>
    post<ShadowLogEntry>(`/api/shadow/${id}/approve`, { note }),

  /** Reject a shadow action */
  reject: (id: string, note?: string) =>
    post<ShadowLogEntry>(`/api/shadow/${id}/reject`, { note }),

  /** Undo a previously approved action */
  undo: (id: string, reason: string) =>
    post<ShadowLogEntry>(`/api/shadow/${id}/undo`, { reason }),
};
