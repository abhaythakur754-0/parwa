/**
 * SHOBH AI QA API Client — The Report Card
 *
 * Centralized client for the QA Report Card endpoints.
 * All endpoints mirror backend/app/api/qa_metrics.py (prefix: /api/qa).
 *
 * Tenant lock is enforced server-side (BC-001): every query filters on the
 * authenticated caller's company_id — a client can never read another
 * client's report card, by construction.
 *
 * Used by:
 *   - /dashboard/qa page (the Report Card screen)
 */

import { get } from '@/lib/api';

const BASE = '/api/qa';

// ── Types ────────────────────────────────────────────────────────────

export interface QaSummary {
  days: number;
  graded_total: number;
  average_score: number | null;
  flagged_count: number;
  flagged_rate: number;
  double_checks_ran: number;
  daily_cap: number;
  grading_cost_usd: number;
  volume_by_day: Record<string, number>;
  by_channel: Record<string, number>;
  top_flag_reasons: [string, number][];
}

export interface QaFlaggedConversation {
  id: string;
  conversation_id: string | null;
  channel: string | null;
  score: number | null;
  question_excerpt: string | null;
  flag_reasons: string[];
  evidence: unknown[];
  officer_status: string | null;
  officer_verdict: string | null;
  officer_notes: string | null;
  created_at: string | null;
}

export interface QaConversationsResponse {
  flagged: boolean;
  total: number;
  limit: number;
  offset: number;
  conversations: QaFlaggedConversation[];
}

// ── API calls ────────────────────────────────────────────────────────

export const qaApi = {
  /** Report Card KPIs for the caller's company only. */
  getSummary(days: number = 30): Promise<QaSummary> {
    return get<QaSummary>(`${BASE}/summary`, { params: { days } });
  },

  /** Flagged conversations (with reasons) — the Problems panel. */
  getFlaggedConversations(limit: number = 50, offset: number = 0): Promise<QaConversationsResponse> {
    return get<QaConversationsResponse>(`${BASE}/conversations`, {
      params: { flagged: true, limit, offset },
    });
  },
};
