/**
 * PARWA Dashboard & Analytics API
 *
 * Canonical API client for all dashboard and analytics endpoints.
 * Backend endpoints at /api/dashboard/* and /api/analytics/*
 *
 * Uses the centralized apiClient from @/lib/api.ts
 * with JWT Bearer auth and tenant-scoped queries.
 *
 * D6-10 Fix: Consolidated from analytics-api.ts + dashboard-api.ts.
 * Shared types (ActivityEvent, DashboardHomeData, etc.) imported from @/types/analytics.ts
 */

import { get, post } from '@/lib/api';
import type {
  DashboardHomeData,
  ActivityEvent,
  ActivityFeedResponse,
  DashboardLayoutResponse,
} from '@/types/analytics';

// ── Re-export canonical types for convenience ─────────────────────────

export type {
  DashboardHomeData,
  ActivityEvent,
  ActivityFeedResponse,
  DashboardLayoutResponse,
};

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

// ── Dashboard API ────────────────────────────────────────────────────

export const dashboardApi = {
  /**
   * Get unified dashboard home data (F-036).
   * Returns summary, KPIs, SLA, trends, categories,
   * activity feed, savings, workforce, CSAT, and anomalies.
   */
  getHome: (periodDays: number = 30) =>
    get<DashboardHomeData>(`/api/dashboard/home?period_days=${periodDays}`),

  /**
   * Get dashboard widget layout config (F-036).
   */
  getLayout: () =>
    get<DashboardLayoutResponse>('/api/dashboard/layout'),

  /**
   * Get paginated activity feed (F-037).
   * Supports filtering by event_type and ticket_id.
   */
  getActivityFeed: (params?: {
    page?: number;
    pageSize?: number;
    eventType?: string;
    ticketId?: string;
  }): Promise<ActivityFeedResponse> => {
    const searchParams = new URLSearchParams();
    if (params?.page) searchParams.set('page', String(params.page));
    if (params?.pageSize) searchParams.set('page_size', String(params.pageSize));
    if (params?.eventType) searchParams.set('event_type', params.eventType);
    if (params?.ticketId) searchParams.set('ticket_id', params.ticketId);
    const qs = searchParams.toString();
    return get<ActivityFeedResponse>(`/api/dashboard/activity-feed${qs ? `?${qs}` : ''}`);
  },

  /**
   * Get key KPI metrics with sparkline data (F-038).
   */
  getMetrics: (period: string = 'last_30d') =>
    get<MetricsResponse>(`/api/dashboard/metrics?period=${period}`),

  /**
   * Get AI adaptation tracker — 30-day AI learning progress.
   */
  getAdaptationTracker: (days: number = 30) =>
    get<AdaptationTrackerResponse>(`/api/analytics/adaptation?days=${days}`),

  /**
   * Get growth nudge alerts based on usage pattern analysis.
   */
  getGrowthNudges: () =>
    get<GrowthNudgeResponse>('/api/analytics/growth-nudges'),

  /**
   * Get ticket volume forecast using predictive analytics.
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
   * Get AI confidence trend — daily avg confidence scores (F-115).
   */
  getConfidenceTrend: (days: number = 30) =>
    get<ConfidenceTrendResponse>(`/api/analytics/confidence-trend?days=${days}`),

  /**
   * Get drift detection reports — model performance drift (F-116).
   */
  getDriftReports: (limit: number = 20) =>
    get<DriftReportsResponse>(`/api/analytics/drift-reports?limit=${limit}`),

  /**
   * Get QA scores — response quality scores (F-119).
   */
  getQAScores: (days: number = 30) =>
    get<QAScoresResponse>(`/api/analytics/qa-scores?days=${days}`),

  /**
   * Get ROI dashboard — cost savings, AI vs human comparison (F-113).
   */
  getROIDashboard: (months: number = 12) =>
    get<ROIDashboardResponse>(`/api/analytics/savings?months=${months}`),

  // ── Day 5: Customer CRM API ───────────────────────────────────────
  getCustomers: (params?: { page?: number; pageSize?: number; search?: string; verified?: string; hasOpenTickets?: boolean }) => {
    const sp = new URLSearchParams();
    if (params?.page) sp.set('page', String(params.page));
    if (params?.pageSize) sp.set('page_size', String(params.pageSize));
    if (params?.search) sp.set('search', params.search);
    if (params?.verified) sp.set('is_verified', params.verified);
    if (params?.hasOpenTickets !== undefined) sp.set('has_open_tickets', String(params.hasOpenTickets));
    const qs = sp.toString();
    return get<CustomerListResponse>(`/api/customers${qs ? `?${qs}` : ''}`);
  },

  getCustomer: (id: string) =>
    get<Customer>(`/api/customers/${id}`),

  getCustomerTickets: (id: string, params?: { page?: number; pageSize?: number }) => {
    const sp = new URLSearchParams();
    if (params?.page) sp.set('page', String(params.page));
    if (params?.pageSize) sp.set('page_size', String(params.pageSize));
    const qs = sp.toString();
    return get<TicketListResponse>(`/api/customers/${id}/tickets${qs ? `?${qs}` : ''}`);
  },

  getTicket: (ticketId: string) =>
    get<TicketResponse>(`/api/tickets/${ticketId}`),

  getCustomerChannels: (id: string) =>
    get<CustomerChannel[]>(`/api/customers/${id}/channels`),

  mergeCustomers: (data: CustomerMergeRequest) =>
    post<any>('/api/customers/merge', data),

  // ── Day 5: Conversations API ──────────────────────────────────────
  getConversations: (params?: { page?: number; pageSize?: number; channel?: string; search?: string; assignedTo?: string; status?: string[] }) => {
    const sp = new URLSearchParams();
    if (params?.page) sp.set('page', String(params.page));
    if (params?.pageSize) sp.set('page_size', String(params.pageSize));
    if (params?.channel) sp.set('channel', params.channel);
    if (params?.search) sp.set('search', params.search);
    if (params?.assignedTo) sp.set('assigned_to', params.assignedTo);
    if (params?.status) params.status.forEach(s => sp.append('status', s));
    const qs = sp.toString();
    return get<ConversationListResponse>(`/api/tickets${qs ? `?${qs}` : ''}`);
  },

  getConversationMessages: (ticketId: string, params?: { page?: number; pageSize?: number; includeInternal?: boolean }) => {
    const sp = new URLSearchParams();
    if (params?.page) sp.set('page', String(params.page));
    if (params?.pageSize) sp.set('page_size', String(params.pageSize));
    if (params?.includeInternal) sp.set('include_internal', 'true');
    const qs = sp.toString();
    return get<TicketMessagesResponse>(`/api/tickets/${ticketId}/messages${qs ? `?${qs}` : ''}`);
  },

  // ── Day 6: Approvals API ──────────────────────────────────────
  getApprovals: (params?: { page?: number; pageSize?: number; status?: string; priority?: string; blockReason?: string; search?: string }) => {
    const sp = new URLSearchParams();
    if (params?.page) sp.set('page', String(params.page));
    if (params?.pageSize) sp.set('page_size', String(params.pageSize));
    if (params?.status) sp.set('status', params.status);
    if (params?.priority) sp.set('priority', params.priority);
    if (params?.blockReason) sp.set('block_reason', params.blockReason);
    if (params?.search) sp.set('search', params.search);
    const qs = sp.toString();
    return get<ApprovalListResponse>(`/api/approvals${qs ? `?${qs}` : ''}`);
  },

  getApproval: (id: string) =>
    get<ApprovalDetail>(`/api/approvals/${id}`),

  approveResponse: (id: string, data?: { edited_response?: string; review_notes?: string }) =>
    post<any>(`/api/approvals/${id}/approve`, data || {}),

  rejectResponse: (id: string, data?: { review_notes?: string }) =>
    post<any>(`/api/approvals/${id}/reject`, data || {}),

  escalateResponse: (id: string, data?: { review_notes?: string }) =>
    post<any>(`/api/approvals/${id}/escalate`, data || {}),

  batchReview: (data: { ids: string[]; action: 'approved' | 'rejected'; review_notes?: string }) =>
    post<any>('/api/approvals/batch', data),

  getApprovalStats: () =>
    get<ApprovalQueueStats>(`/api/approvals/stats`),
};

// ── Day 5: Customer CRM Types ──────────────────────────────────────

export interface Customer {
  id: string;
  email: string | null;
  phone: string | null;
  name: string | null;
  external_id: string | null;
  metadata_json: Record<string, unknown>;
  company_id: string;
  is_verified: boolean;
  created_at: string;
  updated_at: string;
}

export interface CustomerChannel {
  id: string;
  customer_id: string;
  channel_type: string;
  external_id: string;
  is_verified: boolean;
  verified_at: string | null;
  created_at: string;
}

export interface CustomerListResponse {
  items: Customer[];
  total: number;
  page: number;
  page_size: number;
}

export interface CustomerMergeRequest {
  primary_customer_id: string;
  merged_customer_ids: string[];
  reason?: string;
}

// ── Day 5: Conversation Types (aligned with backend TicketResponse) ──

export interface Conversation {
  id: string;
  company_id: string;
  customer_id: string | null;
  channel: string;
  status: string;
  subject: string | null;
  priority: string;
  category: string | null;
  tags: string[];
  agent_id: string | null;
  assigned_to: string | null;
  classification_intent: string | null;
  classification_type: string | null;
  awaiting_human: boolean;
  escalation_level: number;
  sla_breached: boolean;
  is_open: boolean;
  is_resolved: boolean;
  is_closed: boolean;
  time_since_created: string | null;
  time_since_updated: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface ConversationListResponse {
  items: Conversation[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface TicketResponse {
  id: string;
  company_id: string;
  customer_id: string | null;
  channel: string;
  status: string;
  subject: string | null;
  priority: string;
  category: string | null;
  tags: string[];
  agent_id: string | null;
  assigned_to: string | null;
  classification_intent: string | null;
  classification_type: string | null;
  awaiting_human: boolean;
  escalation_level: number;
  sla_breached: boolean;
  is_open: boolean;
  is_resolved: boolean;
  is_closed: boolean;
  time_since_created: string | null;
  time_since_updated: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface TicketListResponse {
  items: TicketResponse[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface TicketMessage {
  id: string;
  ticket_id: string;
  role: string;
  content: string;
  channel: string | null;
  is_internal: boolean;
  ai_confidence: number | null;
  created_at: string;
}

export interface TicketMessagesResponse {
  messages: TicketMessage[];
  total: number;
  page: number;
  page_size: number;
}

// ── Day 6: Approval Types ─────────────────────────────────────

export interface BlockedResponse {
  id: string;
  company_id: string;
  ticket_id: string | null;
  query: string;
  original_response: string;
  edited_response: string | null;
  block_reason: string;
  confidence_score: number;
  guardrail_report: Record<string, unknown> | null;
  priority: 'low' | 'medium' | 'high' | 'urgent';
  status: 'pending' | 'in_review' | 'approved' | 'rejected' | 'auto_rejected' | 'expired';
  reviewer_id: string | null;
  reviewer_action: string | null;
  review_notes: string | null;
  auto_reject_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ApprovalListResponse {
  items: BlockedResponse[];
  total: number;
  page: number;
  page_size: number;
}

export interface ApprovalDetail extends BlockedResponse {
  wait_time_minutes: number | null;
  ticket_subject: string | null;
  ticket_channel: string | null;
  ticket_customer_id: string | null;
}

export interface ApprovalQueueStats {
  total_pending: number;
  total_in_review: number;
  total_approved: number;
  total_rejected: number;
  total_auto_rejected: number;
  total_expired: number;
  avg_wait_time_minutes: number;
  urgent_count: number;
  high_count: number;
}

export default dashboardApi;
