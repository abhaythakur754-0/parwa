/**
 * PARWA Analytics API
 *
 * API helper functions for ticket analytics endpoints.
 * Backend endpoints at /analytics/tickets (registered in main.py).
 * Frontend calls go through Next.js proxy at /api/analytics.
 *
 * Uses the centralized apiClient from @/lib/api.ts which handles
 * JWT auth (httpOnly cookies), CSRF, timeouts, and error handling.
 *
 * All errors propagate to the caller — no silent mock fallbacks.
 */

import apiClient from '@/lib/api';
import {
  DashboardData,
  TicketSummaryResponse,
  TrendPointResponse,
  CategoryDistributionResponse,
  SLAMetricsResponse,
  AgentMetrics,
  ResponseTimeDistribution,
  DateRange,
  IntervalType,
} from '@/types/analytics';

const ANALYTICS_BASE = '/api/analytics';

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

// ── Analytics API ─────────────────────────────────────────────────

export const analyticsApi = {
  /**
   * Get combined dashboard data (summary + SLA + category + trend).
   */
  getDashboard: async (dateRange?: Partial<DateRange>): Promise<DashboardData> => {
    const qs = formatDateParams(dateRange);
    const res = await apiClient.get<DashboardData>(`${ANALYTICS_BASE}/dashboard${qs}`);
    return res.data;
  },

  /**
   * Get ticket summary counts, priority breakdown, resolution rate.
   */
  getSummary: async (dateRange?: Partial<DateRange>): Promise<TicketSummaryResponse> => {
    const qs = formatDateParams(dateRange);
    const res = await apiClient.get<TicketSummaryResponse>(`${ANALYTICS_BASE}/summary${qs}`);
    return res.data;
  },

  /**
   * Get ticket trend data over time.
   */
  getTrends: async (
    interval: IntervalType = 'day',
    dateRange?: Partial<DateRange>
  ): Promise<TrendPointResponse> => {
    const qs = formatDateParams(dateRange);
    const res = await apiClient.get<TrendPointResponse>(
      `${ANALYTICS_BASE}/trends?interval=${interval}${qs ? '&' + qs.slice(1) : ''}`
    );
    return res.data;
  },

  /**
   * Get ticket category distribution.
   */
  getCategories: async (dateRange?: Partial<DateRange>): Promise<CategoryDistributionResponse> => {
    const qs = formatDateParams(dateRange);
    const res = await apiClient.get<CategoryDistributionResponse>(`${ANALYTICS_BASE}/category${qs}`);
    return res.data;
  },

  /**
   * Get SLA compliance metrics.
   */
  getSLA: async (dateRange?: Partial<DateRange>): Promise<SLAMetricsResponse> => {
    const qs = formatDateParams(dateRange);
    const res = await apiClient.get<SLAMetricsResponse>(`${ANALYTICS_BASE}/sla${qs}`);
    return res.data;
  },

  /**
   * Get per-agent performance metrics.
   */
  getAgents: async (
    limit: number = 50,
    dateRange?: Partial<DateRange>
  ): Promise<AgentMetrics[]> => {
    const qs = formatDateParams(dateRange);
    const res = await apiClient.get<AgentMetrics[]>(
      `${ANALYTICS_BASE}/agents?limit=${limit}${qs ? '&' + qs.slice(1) : ''}`
    );
    return res.data;
  },

  /**
   * Get response time distribution.
   */
  getResponseTime: async (dateRange?: Partial<DateRange>): Promise<ResponseTimeDistribution> => {
    const qs = dateRange ? formatDateParams(dateRange) : '';
    const res = await apiClient.get<ResponseTimeDistribution>(
      `${ANALYTICS_BASE}/response-time${qs}`
    );
    return res.data;
  },
};

export default analyticsApi;