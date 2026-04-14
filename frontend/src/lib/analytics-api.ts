/**
 * PARWA Analytics API
 *
 * API helper functions for ticket analytics endpoints.
 * Backend endpoints at /api/v1/analytics/tickets/*
 *
 * Uses the centralized apiClient from @/lib/api.ts
 * with JWT Bearer auth and tenant-scoped queries.
 */

import { get } from '@/lib/api';
import {
  DashboardData,
  DashboardHomeData,
  ActivityFeedResponse,
  DashboardLayoutResponse,
  TicketSummaryResponse,
  TrendPointResponse,
  CategoryDistributionResponse,
  SLAMetricsResponse,
  AgentMetricsResponse,
  DateRange,
  IntervalType,
} from '@/types/analytics';

const ANALYTICS_BASE = '/analytics/tickets';
const DASHBOARD_BASE = '/api/dashboard';

/**
 * Format DateRange into query params.
 */
function formatDateParams(dateRange?: Partial<DateRange>): string {
  if (!dateRange) return '';
  const params = new URLSearchParams();
  if (dateRange.start_date) params.set('start_date', dateRange.start_date);
  if (dateRange.end_date) params.set('end_date', dateRange.end_date);
  const qs = params.toString();
  return qs ? `?${qs}` : '';
}

// ── Analytics API ─────────────────────────────────────────────────────

export const analyticsApi = {
  /**
   * Get combined dashboard data (summary + SLA + category + trend).
   * This is the primary endpoint for the dashboard page.
   */
  getDashboard: async (dateRange?: Partial<DateRange>): Promise<DashboardData> => {
    const qs = formatDateParams(dateRange);
    const response = await get<{ data: DashboardData }>(`${ANALYTICS_BASE}/dashboard${qs}`);
    return response.data;
  },

  /**
   * Get ticket summary counts, priority breakdown, resolution rate.
   */
  getSummary: async (dateRange?: Partial<DateRange>): Promise<TicketSummaryResponse> => {
    const qs = formatDateParams(dateRange);
    return get<TicketSummaryResponse>(`${ANALYTICS_BASE}/summary${qs}`);
  },

  /**
   * Get ticket trend data over time.
   * @param interval - hour | day | week | month
   */
  getTrends: async (
    interval: IntervalType = 'day',
    dateRange?: Partial<DateRange>
  ): Promise<TrendPointResponse> => {
    const qs = formatDateParams(dateRange);
    return get<TrendPointResponse>(`${ANALYTICS_BASE}/trends?interval=${interval}${qs ? '&' + qs.slice(1) : ''}`);
  },

  /**
   * Get ticket category distribution (top categories by count).
   */
  getCategories: async (dateRange?: Partial<DateRange>): Promise<CategoryDistributionResponse> => {
    const qs = formatDateParams(dateRange);
    return get<CategoryDistributionResponse>(`${ANALYTICS_BASE}/category${qs}`);
  },

  /**
   * Get SLA compliance metrics.
   */
  getSLA: async (dateRange?: Partial<DateRange>): Promise<SLAMetricsResponse> => {
    const qs = formatDateParams(dateRange);
    return get<SLAMetricsResponse>(`${ANALYTICS_BASE}/sla${qs}`);
  },

  /**
   * Get per-agent performance metrics.
   * @param limit - Max agents to return (default 50)
   */
  getAgents: async (
    limit: number = 50,
    dateRange?: Partial<DateRange>
  ): Promise<AgentMetricsResponse> => {
    const qs = formatDateParams(dateRange);
    return get<AgentMetricsResponse>(`${ANALYTICS_BASE}/agents?limit=${limit}${qs ? '&' + qs.slice(1) : ''}`);
  },
};

// ── Dashboard API (F-036, F-037, F-038) ───────────────────────────────

export const dashboardApi = {
  /**
   * Get unified dashboard home data (F-036).
   * Single API call for all widgets: summary, KPIs, SLA, trend,
   * category, activity feed, savings, workforce, CSAT, anomalies.
   */
  getHome: async (periodDays: number = 30): Promise<DashboardHomeData> => {
    return get<DashboardHomeData>(`${DASHBOARD_BASE}/home?period_days=${periodDays}`);
  },

  /**
   * Get dashboard widget layout config (F-036).
   */
  getLayout: async (): Promise<DashboardLayoutResponse> => {
    return get<DashboardLayoutResponse>(`${DASHBOARD_BASE}/layout`);
  },

  /**
   * Get paginated activity feed (F-037).
   * @param page - Page number (default 1)
   * @param pageSize - Events per page (default 25)
   * @param eventType - Optional comma-separated event type filter
   * @param ticketId - Optional ticket ID filter
   */
  getActivityFeed: async (params?: {
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
    return get<ActivityFeedResponse>(`${DASHBOARD_BASE}/activity-feed${qs ? `?${qs}` : ''}`);
  },

  /**
   * Get key KPI metrics with sparkline data (F-038).
   * @param period - last_7d | last_30d | last_90d
   */
  getMetrics: async (period: 'last_7d' | 'last_30d' | 'last_90d' = 'last_30d') => {
    return get(`${DASHBOARD_BASE}/metrics?period=${period}`);
  },
};

export default analyticsApi;
