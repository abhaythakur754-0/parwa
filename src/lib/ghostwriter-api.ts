/**
 * SHOBH Ghostwriter API Client
 *
 * Centralized API client for Ghostwriter draft endpoints.
 * All endpoints mirror backend/app/api/ghostwriter.py
 *
 * Honesty rule: nothing auto-publishes. Approve is a recorded human
 * decision AND the step that feeds the approved article into the agent's
 * knowledge store — the approve response carries a `published` flag that
 * the UI must surface truthfully.
 */

import { get, post } from '@/lib/api';

// ── Types ─────────────────────────────────────────────────────────────

export type DraftStatus = 'draft' | 'approved' | 'rejected';

export interface GhostwriterDraft {
  id: string;
  gap_topic: string;
  status: DraftStatus;
  title: string | null;
  content: string | null;
  sources: Array<{ document?: string } & Record<string, unknown>>;
  based_on: { flagged_count?: number; sample_questions?: string[] } & Record<string, unknown>;
  model_used: string | null;
  created_at: string | null;
  reviewed_at: string | null;
}

export interface DraftsListResponse {
  total: number;
  limit: number;
  offset: number;
  drafts: GhostwriterDraft[];
}

export interface CreateDraftResponse {
  id: string;
  gap_topic: string;
  status: DraftStatus;
  title: string | null;
  content: string | null;
  sources: string;
  model_used: string | null;
}

export interface ApproveDraftResponse {
  id: string;
  status: DraftStatus;
  /** True when the approved article is in the agent's knowledge store. */
  published: boolean;
  /** Non-null when approval succeeded but publishing failed — honest, retryable. */
  publish_error: string | null;
}

export interface RejectDraftResponse {
  id: string;
  status: DraftStatus;
}

// ── API ───────────────────────────────────────────────────────────────

const BASE = '/api/ghostwriter';

function qs(params: Record<string, unknown>): string {
  const parts = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null && v !== '')
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
    .join('&');
  return parts ? `?${parts}` : '';
}

export const ghostwriterApi = {
  /**
   * List drafts for the caller's company, newest first.
   */
  listDrafts: (limit = 50, offset = 0) =>
    get<DraftsListResponse>(`${BASE}/drafts${qs({ limit, offset })}`),

  /**
   * Draft an article for a knowledge gap — uses this company's own
   * evidence only. ONE cheap LLM call; can take tens of seconds.
   */
  createDraft: (topic: string) =>
    post<CreateDraftResponse>(`${BASE}/drafts`, { topic }),

  /**
   * Approve a draft (human decision) — also publishes the article into
   * the agent's knowledge store. Check `published` in the response and
   * surface `publish_error` honestly; a failed publish is retryable by
   * approving again (idempotent on the backend).
   */
  approveDraft: (draftId: string) =>
    post<ApproveDraftResponse>(`${BASE}/drafts/${encodeURIComponent(draftId)}/approve`),

  /**
   * Reject a draft. Never publishes anything.
   */
  rejectDraft: (draftId: string) =>
    post<RejectDraftResponse>(`${BASE}/drafts/${encodeURIComponent(draftId)}/reject`),
};
