/**
 * PARWA Shadow Mode API Client
 * 
 * Typed client for all shadow mode endpoints.
 * Uses the shared apiClient (axios instance with httpOnly cookie auth + CSRF).
 * 
 * Day 4 Implementation - Shadow Mode Frontend API Client
 */

import { get, post, put, patch, del } from '@/lib/api';

// ── Types ──────────────────────────────────────────────────────────────────

/** System mode type alias */
export type SystemMode = 'shadow' | 'supervised' | 'graduated';

/** Manager decision type alias */
export type ManagerDecision = 'approved' | 'rejected' | 'modified' | null;

export interface ShadowLogEntry {
  id: string;
  company_id: string;
  action_type: string;
  action_payload: Record<string, any>;
  jarvis_risk_score: number | null;
  mode: 'shadow' | 'supervised' | 'graduated';
  manager_decision: 'approved' | 'rejected' | 'modified' | null;
  manager_note: string | null;
  resolved_at: string | null;
  created_at: string;
}

export interface ShadowPreference {
  id: string;
  company_id: string;
  action_category: string;
  preferred_mode: 'shadow' | 'supervised' | 'graduated';
  set_via: 'ui' | 'jarvis';
  updated_at: string;
}

export interface ShadowStats {
  company_id: string;
  total_actions: number;
  pending_count: number;
  approved_count: number;
  rejected_count: number;
  approval_rate: number;
  avg_risk_score: number;
  mode_distribution: Record<string, number>;
  action_type_distribution: Record<string, number>;
}

export interface RiskEvaluation {
  mode: string;
  risk_score: number;
  reason: string;
  requires_approval: boolean;
  auto_execute: boolean;
  layers: {
    layer1_heuristic: { score: number; reason: string };
    layer2_preference: { mode: string | null; reason: string };
    layer3_historical: { avg_risk: number | null; reason: string };
    layer4_safety_floor: { hard_safety: boolean; reason: string };
  };
  company_mode: string;
  stage_0?: boolean;
  shadow_actions_remaining?: number;
}

export interface PaginatedShadowLog {
  items: ShadowLogEntry[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// ── API Functions ───────────────────────────────────────────────────────────

/**
 * Get the current shadow mode for the company.
 */
export async function getShadowMode(): Promise<string> {
  const response = await get<{ mode: string }>('/api/shadow/mode');
  return response.mode;
}

/**
 * Set the shadow mode for the company.
 */
export async function setShadowMode(
  mode: string,
  setVia: string
): Promise<{ mode: string; previous_mode: string }> {
  return put<{ mode: string; previous_mode: string }>('/api/shadow/mode', {
    mode,
    set_via: setVia,
  });
}

/**
 * Get all shadow preferences for the company.
 */
export async function getShadowPreferences(): Promise<ShadowPreference[]> {
  const response = await get<{ preferences: ShadowPreference[] }>('/api/shadow/preferences');
  return response.preferences;
}

/**
 * Set a shadow preference for an action category.
 */
export async function setShadowPreference(
  category: string,
  mode: string,
  setVia: string
): Promise<ShadowPreference> {
  return patch<ShadowPreference>('/api/shadow/preferences', {
    action_category: category,
    preferred_mode: mode,
    set_via: setVia,
  });
}

/**
 * Delete a shadow preference for an action category.
 */
export async function deleteShadowPreference(
  category: string
): Promise<{ deleted: boolean }> {
  return del<{ deleted: boolean }>(`/api/shadow/preferences?category=${encodeURIComponent(category)}`);
}

/**
 * Get shadow log entries with filtering and pagination.
 */
export async function getShadowLog(
  filters: Record<string, any>,
  page: number,
  pageSize: number
): Promise<PaginatedShadowLog> {
  const sp = new URLSearchParams();
  sp.set('page', String(page));
  sp.set('page_size', String(pageSize));
  
  // Apply filters
  if (filters.action_type) sp.set('action_type', filters.action_type);
  if (filters.mode) sp.set('mode', filters.mode);
  if (filters.decision) sp.set('decision', filters.decision);
  if (filters.date_from) sp.set('date_from', filters.date_from);
  if (filters.date_to) sp.set('date_to', filters.date_to);
  if (filters.sort_by) sp.set('sort_by', filters.sort_by);
  if (filters.sort_dir) sp.set('sort_dir', filters.sort_dir);
  if (filters.risk_min !== undefined) sp.set('risk_min', String(filters.risk_min));
  if (filters.risk_max !== undefined) sp.set('risk_max', String(filters.risk_max));
  
  return get<PaginatedShadowLog>(`/api/shadow/log?${sp.toString()}`);
}

/**
 * Get shadow mode statistics for the company.
 */
export async function getShadowStats(): Promise<ShadowStats> {
  return get<ShadowStats>('/api/shadow/stats');
}

/**
 * Evaluate the risk for a potential action.
 */
export async function evaluateActionRisk(
  actionType: string,
  payload: Record<string, any>
): Promise<RiskEvaluation> {
  return post<RiskEvaluation>('/api/shadow/evaluate', {
    action_type: actionType,
    action_payload: payload,
  });
}

/**
 * Approve a pending shadow action.
 */
export async function approveShadowAction(
  id: string,
  note?: string
): Promise<ShadowLogEntry> {
  return post<ShadowLogEntry>(`/api/shadow/approve/${id}`, { note });
}

/**
 * Reject a pending shadow action.
 */
export async function rejectShadowAction(
  id: string,
  note?: string
): Promise<ShadowLogEntry> {
  return post<ShadowLogEntry>(`/api/shadow/reject/${id}`, { note });
}

/**
 * Undo a previously approved shadow action.
 */
export async function undoShadowAction(
  id: string,
  reason: string
): Promise<{ undo_id: string }> {
  return post<{ undo_id: string }>(`/api/shadow/undo/${id}`, { reason });
}

/**
 * Batch resolve multiple shadow actions at once.
 */
export async function batchResolve(
  ids: string[],
  decision: string,
  note?: string
): Promise<{ resolved: number; skipped: number }> {
  return post<{ resolved: number; skipped: number }>('/api/shadow/batch-resolve', {
    ids,
    decision,
    note,
  });
}

// ── Convenience Export Object ──────────────────────────────────────────────

export const shadowApi = {
  /** Get current shadow mode (returns object with mode for hook compatibility) */
  getMode: async (): Promise<{ mode: SystemMode }> => {
    const mode = await getShadowMode();
    return { mode: mode as SystemMode };
  },
  
  /** Set shadow mode */
  setMode: (mode: SystemMode, setVia: string = 'ui'): Promise<{ mode: string; previous_mode: string }> => 
    setShadowMode(mode, setVia),
  
  /** Get all action-category preferences (returns object for hook compatibility) */
  getPreferences: async (): Promise<{ preferences: ShadowPreference[] }> => {
    const preferences = await getShadowPreferences();
    return { preferences };
  },
  
  /** Set preference for an action category */
  setPreference: (category: string, mode: SystemMode, setVia: string = 'ui'): Promise<ShadowPreference> =>
    setShadowPreference(category, mode, setVia),
  
  /** Delete a preference (reset to default) */
  deletePreference: (category: string): Promise<{ deleted: boolean }> => 
    deleteShadowPreference(category),
  
  /** Get shadow log with pagination and filters */
  getLog: getShadowLog,
  
  /** Get shadow mode statistics */
  getStats: getShadowStats,
  
  /** Evaluate a what-if scenario */
  evaluate: evaluateActionRisk,
  
  /** Approve a shadow action */
  approve: approveShadowAction,
  
  /** Reject a shadow action */
  reject: rejectShadowAction,
  
  /** Undo a previously approved action */
  undo: undoShadowAction,
  
  /** Batch resolve multiple actions */
  batchResolve,
  
  /** Process a Jarvis conversational shadow mode command */
  jarvisCommand: (message: string) =>
    post<{ command_matched: boolean; success: boolean; message: string | null; data: Record<string, any> }>(
      '/api/shadow/jarvis-command',
      { message }
    ),
};

export default shadowApi;
