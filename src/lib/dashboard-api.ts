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
};

export default dashboardApi;
