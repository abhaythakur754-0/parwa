/**
 * PARWA Shadow Mode Types
 *
 * TypeScript type definitions for the Shadow Mode system.
 * Mirrors backend Pydantic schemas from backend/app/api/shadow_mode.py
 * and backend/app/services/shadow_mode_service.py
 */

// ── Core Enums ──────────────────────────────────────────────────────

export type ShadowModeStatusType = 'shadow' | 'supervised' | 'graduated' | 'disabled';

export type HumanVerdict = 'shadow_better' | 'live_better' | 'equal' | 'skip';

// ── Shadow Mode Config ─────────────────────────────────────────────

export interface ShadowModeConfig {
  company_id: string;
  live_variant: string;
  shadow_variant: string;
  status: ShadowModeStatusType;
  sample_rate: number;
  auto_graduation_threshold: number;
  auto_graduation_window: number;
  supervised_timeout_seconds: number;
  quality_streak: number;
  total_comparisons: number;
  shadow_wins: number;
  auto_promote_to_supervised: boolean;
  auto_promote_to_graduated: boolean;
  live_instance_id: string | null;
  shadow_instance_id: string | null;
  enabled_at: string | null;
  last_comparison_at: string | null;
  created_at: string;
  updated_at: string;
}

// ── Shadow Mode Status (from get_status) ────────────────────────────

export interface ShadowModeStatus {
  active: boolean;
  company_id: string;
  live_variant: string;
  shadow_variant: string;
  status: ShadowModeStatusType;
  sample_rate: number;
  total_comparisons: number;
  shadow_wins: number;
  shadow_win_rate: number;
  quality_streak: number;
  auto_graduation_threshold: number;
  auto_graduation_window: number;
  auto_graduation_progress: number;
  supervised_timeout_seconds: number;
  live_instance_id: string | null;
  shadow_instance_id: string | null;
  enabled_at: string | null;
  last_comparison_at: string | null;
}

// ── Shadow Comparison ───────────────────────────────────────────────

export interface ShadowComparison {
  id: string;
  company_id: string;
  config_id: string;
  ticket_id: string;
  live_quality: number;
  shadow_quality: number;
  live_latency_ms: number;
  shadow_latency_ms: number;
  live_tokens: number;
  shadow_tokens: number;
  quality_delta: number;
  shadow_winner: boolean;
  human_reviewed: boolean;
  human_verdict: HumanVerdict | null;
  reviewer_id: string | null;
  review_notes: string | null;
  created_at: string;
}

// ── Shadow Mode Statistics ──────────────────────────────────────────

export interface ShadowModeStatistics {
  company_id: string;
  total_comparisons: number;
  shadow_wins: number;
  shadow_win_rate: number;
  avg_live_quality: number;
  avg_shadow_quality: number;
  avg_quality_delta: number;
  avg_live_latency_ms: number;
  avg_shadow_latency_ms: number;
  avg_latency_delta_ms: number;
  avg_live_tokens: number;
  avg_shadow_tokens: number;
  avg_token_delta: number;
  quality_streak: number;
  auto_graduation_threshold: number;
  auto_graduation_window: number;
  auto_graduation_progress: number;
  human_reviews_total: number;
  human_reviews_shadow_better: number;
  human_reviews_live_better: number;
  human_reviews_equal: number;
  human_agreement_rate: number;
  comparisons_last_24h: number;
  comparisons_last_7d: number;
}

// ── Request Types ───────────────────────────────────────────────────

export interface EnableShadowModeRequest {
  live_variant: string;
  shadow_variant: string;
  sample_rate?: number;
  auto_graduation_threshold?: number;
  auto_graduation_window?: number;
  supervised_timeout_seconds?: number;
  auto_promote_to_supervised?: boolean;
  auto_promote_to_graduated?: boolean;
  live_instance_id?: string;
  shadow_instance_id?: string;
}

export interface DisableShadowModeRequest {
  reason?: string;
}

export interface PromoteShadowModeRequest {
  target_status?: 'supervised' | 'graduated';
}

export interface HumanReviewRequest {
  result_id: string;
  verdict: HumanVerdict;
  notes?: string;
}

// ── Response Types ──────────────────────────────────────────────────

export interface ShadowModeApiResponse<T> {
  status: 'ok' | 'error';
  data: T;
}

export interface ComparisonHistoryResponse {
  comparisons: ShadowComparison[];
  limit: number;
  offset: number;
}
