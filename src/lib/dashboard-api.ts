/**
 * PARWA Dashboard API — Week 16 Day 1
 *
 * API client for the new unified dashboard endpoints.
 * Backend endpoints at /api/dashboard/*
 *
 * Uses the centralized apiClient from @/lib/api.ts
 * with JWT Bearer auth and tenant-scoped queries.
 */

import { get } from '@/lib/api';

// ── Activity Event Types ─────────────────────────────────────────────

export interface ActivityEvent {
  event_id: string;
  event_type: string;
  actor_id?: string;
  actor_type?: string;
  actor_name?: string;
  description: string;
  ticket_id?: string;
  ticket_subject?: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface ActivityFeedResponse {
  events: ActivityEvent[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

// ── KPI Metrics Types ────────────────────────────────────────────────

export interface KPIData {
  key: string;
  label: string;
  value: unknown;
  previous_value?: unknown;
  change_pct?: number;
  change_direction?: 'up' | 'down' | 'neutral';
  unit?: string;
  is_anomaly: boolean;
  sparkline: number[];
}

export interface MetricsResponse {
  kpis: KPIData[];
  period: string;
  generated_at: string;
}

// ── Dashboard Home Types ─────────────────────────────────────────────

export interface AnomalyItem {
  type: string;
  severity: string;
  message: string;
  detected_at: string;
}

export interface DashboardHomeResponse {
  summary: Record<string, unknown>;
  kpis: Record<string, unknown>;
  sla: Record<string, unknown>;
  trend: Array<{ timestamp: string; count: number; label: string }>;
  by_category: Array<{ category: string; count: number; percentage: number }>;
  activity_feed: ActivityEvent[];
  savings: Record<string, unknown>;
  workforce: Record<string, unknown>;
  csat: Record<string, unknown>;
  anomalies: AnomalyItem[];
  layout: { layout_id: string; widgets: unknown[]; is_default: boolean };
  generated_at: string;
}

// ── F-039: Adaptation Tracker Types ────────────────────────────────────

export interface AdaptationDayData {
  date: string;
  ai_accuracy: number;
  human_accuracy: number;
  gap: number;
  tickets_processed: number;
  mistakes_count: number;
  mistake_rate: number;
}

export interface AdaptationTrackerResponse {
  daily_data: AdaptationDayData[];
  overall_improvement_pct: number;
  current_accuracy: number;
  starting_accuracy: number;
  best_day: AdaptationDayData | null;
  worst_day: AdaptationDayData | null;
  training_runs_count: number;
  drift_reports_count: number;
}

// ── Dashboard API ────────────────────────────────────────────────────

export const dashboardApi = {
  /**
   * Get unified dashboard home data.
   * Returns summary, KPIs, SLA, trends, categories,
   * activity feed, savings, workforce, CSAT, and anomalies.
   */
  getHome: (periodDays: number = 30) =>
    get<DashboardHomeResponse>(`/api/dashboard/home?period_days=${periodDays}`),

  /**
   * Get paginated activity feed.
   * Supports filtering by event_type and ticket_id.
   */
  getActivityFeed: (
    page: number = 1,
    pageSize: number = 25,
    eventType?: string,
    ticketId?: string
  ) => {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });
    if (eventType) params.set('event_type', eventType);
    if (ticketId) params.set('ticket_id', ticketId);
    return get<ActivityFeedResponse>(
      `/api/dashboard/activity-feed?${params.toString()}`
    );
  },

  /**
   * Get KPI metrics with sparklines for a given period.
   */
  getMetrics: (period: string = 'last_30d') =>
    get<MetricsResponse>(`/api/dashboard/metrics?period=${period}`),

  /**
   * Get AI adaptation tracker — 30-day AI learning progress.
   * Returns daily AI vs human accuracy, mistake rates,
   * training runs, and drift reports.
   */
  getAdaptationTracker: (days: number = 30) =>
    get<AdaptationTrackerResponse>(`/api/analytics/adaptation?days=${days}`),

  /**
   * Get growth nudge alerts based on usage pattern analysis.
   * Returns actionable recommendations for scaling, channels, CSAT, etc.
   */
  getGrowthNudges: () =>
    get<GrowthNudgeResponse>('/api/analytics/growth-nudges'),

  /**
   * Get ticket volume forecast using predictive analytics.
   * Returns historical + forecast data with confidence bounds.
   */
  getTicketForecast: (forecastDays: number = 14, historicalDays: number = 30) =>
    get<TicketForecastResponse>(`/api/analytics/forecast?forecast_days=${forecastDays}&historical_days=${historicalDays}`),

  /**
   * Get CSAT trend analytics with daily trend, distribution,
   * and breakdowns by agent, category, and channel.
   */
  getCSATTrends: (days: number = 30) =>
    get<CSATTrendsResponse>(`/api/analytics/csat-trends?days=${days}`),

  /**
   * Get AI confidence trend — daily avg confidence scores
   * over time with distribution buckets and thresholds.
   * F-115
   */
  getConfidenceTrend: (days: number = 30) =>
    get<ConfidenceTrendResponse>(`/api/analytics/confidence-trend?days=${days}`),

  /**
   * Get drift detection reports — model performance drift
   * alerts with severity, metrics, and recovery status.
   * F-116
   */
  getDriftReports: (limit: number = 20) =>
    get<DriftReportsResponse>(`/api/analytics/drift-reports?limit=${limit}`),

  /**
   * Get QA scores — response quality scores with dimension
   * breakdowns, pass rates, and trend data.
   * F-119
   */
  getQAScores: (days: number = 30) =>
    get<QAScoresResponse>(`/api/analytics/qa-scores?days=${days}`),

  /**
   * Get ROI dashboard — cost savings, AI vs human ticket comparison,
   * monthly trend, and return on investment metrics.
   * F-113
   */
  getROIDashboard: (months: number = 12) =>
    get<ROIDashboardResponse>(`/api/analytics/savings?months=${months}`),
};

// ── F-042: Growth Nudge Types ─────────────────────────────────────────

export interface GrowthNudge {
  nudge_id: string;
  nudge_type: string;
  severity: 'urgent' | 'recommendation' | 'suggestion' | 'info';
  title: string;
  message: string;
  action_label?: string;
  action_url?: string;
  dismissed: boolean;
  detected_at: string;
}

export interface GrowthNudgeResponse {
  nudges: GrowthNudge[];
  total: number;
  dismissed_count: number;
}

// ── F-043: Ticket Forecast Types ────────────────────────────────────────

export interface ForecastPoint {
  date: string;
  predicted: number;
  lower_bound?: number;
  upper_bound?: number;
  actual?: number | null;
}

export interface TicketForecastResponse {
  historical: ForecastPoint[];
  forecast: ForecastPoint[];
  model_type: string;
  confidence_level: number;
  seasonality_detected: boolean;
  trend_direction: 'increasing' | 'decreasing' | 'stable';
  avg_daily_volume: number;
}

// ── F-044: CSAT Trends Types ────────────────────────────────────────────

export interface CSATDayData {
  date: string;
  avg_rating: number;
  total_ratings: number;
  distribution: Record<string, number>;
}

export interface CSATDimension {
  dimension_name: string;
  avg_rating: number;
  total_ratings: number;
}

export interface CSATTrendsResponse {
  daily_trend: CSATDayData[];
  overall_avg: number;
  overall_total: number;
  by_agent: CSATDimension[];
  by_category: CSATDimension[];
  by_channel: CSATDimension[];
  trend_direction: 'improving' | 'declining' | 'stable';
  change_vs_previous_period: number | null;
}

// ── F-115: Confidence Trend Types ──────────────────────────────────────

export interface ConfidenceDayData {
  date: string;
  avg_confidence: number;
  min_confidence: number;
  max_confidence: number;
  total_predictions: number;
  low_confidence_count: number;
}

export interface ConfidenceBucket {
  range: string;
  count: number;
  percentage: number;
}

export interface ConfidenceTrendResponse {
  daily_trend: ConfidenceDayData[];
  current_avg: number;
  overall_avg: number;
  trend_direction: 'improving' | 'declining' | 'stable';
  change_vs_previous_period: number;
  distribution: ConfidenceBucket[];
  low_confidence_threshold: number;
  critical_threshold: number;
  total_predictions: number;
}

// ── F-116: Drift Detection Types ───────────────────────────────────────

export interface DriftReport {
  report_id: string;
  detected_at: string;
  severity: 'critical' | 'warning' | 'info';
  metric_name: string;
  metric_value: number;
  baseline_value: number;
  drift_pct: number;
  description: string;
  status: 'active' | 'resolved' | 'investigating';
  resolved_at?: string;
  recovery_action?: string;
}

export interface DriftReportsResponse {
  reports: DriftReport[];
  total: number;
  active_count: number;
  last_detected_at: string | null;
  most_severe: 'critical' | 'warning' | 'info' | null;
}

// ── F-119: QA Scores Types ─────────────────────────────────────────────

export interface QADayData {
  date: string;
  overall_score: number;
  accuracy_score: number;
  completeness_score: number;
  tone_score: number;
  relevance_score: number;
  total_evaluated: number;
  pass_count: number;
}

export interface QADimension {
  dimension_name: string;
  avg_score: number;
  pass_rate: number;
  trend: 'improving' | 'declining' | 'stable';
}

export interface QAScoresResponse {
  daily_trend: QADayData[];
  current_overall: number;
  overall_avg: number;
  pass_rate: number;
  total_evaluated: number;
  dimensions: QADimension[];
  trend_direction: 'improving' | 'declining' | 'stable';
  change_vs_previous_period: number | null;
  threshold_pass: number;
}

// ── F-113: ROI Dashboard Types ──────────────────────────────────────

export interface ROIMonthSnapshot {
  period: string;
  date: string;
  tickets_ai: number;
  tickets_human: number;
  ai_cost: number;
  human_cost: number;
  savings: number;
  cumulative_savings: number;
}

export interface ROIMonthDetail {
  tickets_ai: number;
  tickets_human: number;
  ai_cost: number;
  human_cost: number;
  savings: number;
  cumulative_savings: number;
  period: string;
  date: string;
}

export interface ROIDashboardResponse {
  current_month: ROIMonthDetail;
  previous_month: ROIMonthDetail;
  all_time_savings: number;
  all_time_tickets_ai: number;
  all_time_tickets_human: number;
  monthly_trend: ROIMonthSnapshot[];
  avg_cost_per_ticket_ai: number;
  avg_cost_per_ticket_human: number;
  savings_pct: number;
}

export default dashboardApi;
