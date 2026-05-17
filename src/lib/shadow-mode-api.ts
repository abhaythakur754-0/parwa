/**
 * PARWA Shadow Mode API Client
 *
 * Centralized API client for Shadow Mode endpoints.
 * All endpoints mirror backend/app/api/shadow_mode.py
 */

import { get, post } from '@/lib/api';
import type {
  ShadowModeStatus,
  ShadowComparison,
  ShadowModeStatistics,
  EnableShadowModeRequest,
  DisableShadowModeRequest,
  PromoteShadowModeRequest,
  HumanReviewRequest,
  ShadowModeApiResponse,
  ComparisonHistoryResponse,
} from '@/types/shadow-mode';

const BASE = '/api/shadow-mode';

// ── Helper ──────────────────────────────────────────────────────────

function qs(params: Record<string, unknown>): string {
  const parts = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null && v !== '')
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
    .join('&');
  return parts ? `?${parts}` : '';
}

// ── Shadow Mode API ─────────────────────────────────────────────────

export const shadowModeApi = {
  /**
   * Enable shadow mode for the current company.
   * Requires owner/admin role.
   */
  enable: (data: EnableShadowModeRequest) =>
    post<ShadowModeApiResponse<{ success: boolean; message?: string }>>(`${BASE}/enable`, data),

  /**
   * Disable shadow mode for the current company.
   * Requires owner/admin role.
   */
  disable: (data: DisableShadowModeRequest = {}) =>
    post<ShadowModeApiResponse<{ success: boolean; message?: string }>>(`${BASE}/disable`, data),

  /**
   * Get current shadow mode status.
   */
  status: () =>
    get<ShadowModeApiResponse<ShadowModeStatus>>(`${BASE}/status`),

  /**
   * Manually promote shadow mode to the next phase.
   * Requires owner/admin role.
   */
  promote: (data: PromoteShadowModeRequest = {}) =>
    post<ShadowModeApiResponse<{ success: boolean; message?: string; new_status?: string }>>(`${BASE}/promote`, data),

  /**
   * Complete graduation: make shadow variant the new live variant.
   * Requires owner/admin role.
   */
  graduate: () =>
    post<ShadowModeApiResponse<{ success: boolean; message?: string }>>(`${BASE}/graduate`),

  /**
   * Get comparison history between live and shadow variants.
   */
  comparisons: (limit = 50, offset = 0) =>
    get<ShadowModeApiResponse<ComparisonHistoryResponse>>(`${BASE}/comparisons${qs({ limit, offset })}`),

  /**
   * Get aggregate shadow mode statistics.
   */
  statistics: () =>
    get<ShadowModeApiResponse<ShadowModeStatistics>>(`${BASE}/statistics`),

  /**
   * Submit a human review for a shadow mode comparison result.
   * Available to owner, admin, and agent roles.
   */
  review: (data: HumanReviewRequest) =>
    post<ShadowModeApiResponse<{ success: boolean; message?: string }>>(`${BASE}/review`, data),
};
