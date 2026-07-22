/**
 * PARWA DLQ API Client (BC-018)
 *
 * Centralized client for the Dead Letter Queue ops endpoints.
 * All endpoints mirror backend/app/api/dlq.py (prefix: /api/dlq).
 *
 * Used by:
 *   - /dashboard/crm-dlq page (CRM-specific DLQ tile + table)
 *   - /dashboard main page (CRM DLQ count badge)
 */

import { get, post } from '@/lib/api';

const BASE = '/api/dlq';

// ── Types ────────────────────────────────────────────────────────────

export interface DLQEntry {
  id: string;
  company_id: string;
  conversation_id: string | null;
  session_id: string | null;
  error: string;
  error_type: string | null;
  state_snapshot: Record<string, unknown>;
  variant_tier: string | null;
  channel: string | null;
  intent: string | null;
  retried: boolean;
  retry_count: number;
  retry_succeeded: boolean | null;
  last_retry_at: string | null;
  created_at: string | null;
  resolved_at: string | null;
}

export interface DLQListResponse {
  success: boolean;
  count: number;
  total_unresolved?: number | null;
  entries: DLQEntry[];
}

export interface DLQStats {
  success: boolean;
  by_error_type: Record<string, number>;
  total_unresolved: number;
  total_retried: number;
  total_resolved: number;
  /** Unresolved count across the 3 BC-017 CRM error_types. Powers the dashboard tile. */
  crm_unresolved: number;
  /** Per-error-type unresolved count for the 3 CRM types. */
  crm_unresolved_by_type: Record<string, number>;
}

export interface DLQRetryResponse {
  success: boolean;
  entry_id: string;
  retried: boolean;
  retry_count: number;
  last_retry_at: string | null;
}

export interface DLQResolveResponse {
  success: boolean;
  entry_id: string;
  resolved_at: string;
  retry_succeeded: boolean;
}

export interface CRMErrorTypesResponse {
  success: boolean;
  bc_017_crm_error_types: string[]; // 3 BC-017 types
  bc_016_crm_error_types: string[]; // ['crm_push_failed']
  all_crm_error_types: string[]; // BC-016 + BC-017
}

// ── Helper ───────────────────────────────────────────────────────────

function qs(params: Record<string, unknown>): string {
  const parts = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null && v !== '')
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
    .join('&');
  return parts ? `?${parts}` : '';
}

// ── DLQ API ──────────────────────────────────────────────────────────

export const dlqApi = {
  /**
   * List DLQ entries with optional filtering.
   * Pass error_type='crm_only' to filter to the 3 BC-017 CRM error_types.
   */
  list: (params: {
    error_type?: string;
    limit?: number;
    offset?: number;
    resolved?: boolean;
    company_id?: string; // '__all__' for cross-tenant (platform admin only)
  } = {}) => get<DLQListResponse>(`${BASE}/entries${qs(params)}`),

  /**
   * Get aggregate DLQ stats including the CRM-specific breakdown
   * (crm_unresolved + crm_unresolved_by_type).
   */
  stats: (params: { company_id?: string } = {}) =>
    get<DLQStats>(`${BASE}/stats${qs(params)}`),

  /**
   * Get the list of CRM-specific error_types (BC-016 + BC-017).
   * Used to populate filter dropdowns without hardcoding strings.
   */
  crmErrorTypes: () => get<CRMErrorTypesResponse>(`${BASE}/crm_error_types`),

  /**
   * Mark a DLQ entry as manually retried.
   * NOTE: does NOT re-execute the graph — only increments retry_count.
   */
  retry: (entryId: string) =>
    post<DLQRetryResponse>(`${BASE}/entries/${entryId}/retry`),

  /**
   * Mark a DLQ entry as resolved (soft-close).
   * For crm_permanent_failure_push_failed entries, follow the runbook FIRST:
   * documents/ops_runbooks/crm_permanent_failure_push_failed_runbook.md
   */
  resolve: (entryId: string, retrySucceeded = true) =>
    post<DLQResolveResponse>(
      `${BASE}/entries/${entryId}/resolve${qs({ retry_succeeded: retrySucceeded })}`,
    ),
};

// ── Constants ────────────────────────────────────────────────────────

/**
 * The 3 BC-017 CRM error_types. Hardcoded here for type-safety/UX
 * (so the dashboard can render tiles before the /crm_error_types call returns).
 * Keep in sync with backend/app/api/dlq.py::CRM_ERROR_TYPES.
 */
export const BC017_CRM_ERROR_TYPES = [
  'crm_escalation_push_failed',
  'crm_resume_push_failed',
  'crm_permanent_failure_push_failed',
] as const;

export type BC017CrmErrorType = (typeof BC017_CRM_ERROR_TYPES)[number];

/**
 * Human-readable labels for each CRM error_type. Used by the dashboard tile.
 */
export const CRM_ERROR_TYPE_LABELS: Record<string, { label: string; severity: 'warning' | 'danger'; description: string }> = {
  crm_escalation_push_failed: {
    label: 'Escalation Push Failed',
    severity: 'warning',
    description:
      "Node 8 tried to tell the CRM 'this ticket was escalated' but the CRM API rejected / timed out after all retries. CRM is still showing 'open' while PARWA thinks it's pending_human.",
  },
  crm_resume_push_failed: {
    label: 'Resume Push Failed',
    severity: 'warning',
    description:
      "Guidance flow tried to tell the CRM 'this ticket was resumed with human guidance' but the push failed after all retries. CRM still shows 'pending' even though the customer received the answer.",
  },
  crm_permanent_failure_push_failed: {
    label: 'Permanent Failure — MANUAL ACTION REQUIRED',
    severity: 'danger',
    description:
      'WORST CASE: AI exhausted all guidance retries AND we could not tell the CRM to reset the ticket to open/new. The vault is in REPROCESS_EXHAUSTED state. Ops MUST manually reset the CRM ticket per the runbook.',
  },
};
