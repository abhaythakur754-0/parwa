/**
 * PARWA Analytics API
 *
 * API helper functions for ticket analytics endpoints.
 * Backend endpoints at /api/v1/analytics/tickets/*
 *
 * Uses the centralized apiClient from @/lib/api.ts
 * with JWT Bearer auth and tenant-scoped queries.
 *
 * NO mock data — if the backend is unavailable, calls fail
 * and the UI shows empty/error states instead of fake numbers.
 */

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

// Backend analytics router is at /analytics/tickets (registered in main.py)
// Frontend calls go through Next.js proxy at /api/analytics which forwards to backend
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

/**
 * Safe fetch wrapper — returns real data or throws.
 * The UI is responsible for showing empty/error states.
 */
async function apiFetch<T>(url: string): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  const res = await fetch(url, {
    headers,
    credentials: 'include',
    signal: AbortSignal.timeout(8000),
  });

  if (!res.ok) {
    throw new Error(`Analytics API returned ${res.status}`);
  }

  return await res.json();
}

// ── Analytics API ─────────────────────────────────────────────────

export const analyticsApi = {
  /**
   * Get combined dashboard data (summary + SLA + category + trend).
   */
  getDashboard: async (dateRange?: Partial<DateRange>): Promise<DashboardData> => {
    const qs = formatDateParams(dateRange);
    return apiFetch<DashboardData>(`${ANALYTICS_BASE}/dashboard${qs}`);
  },

  /**
   * Get ticket summary counts, priority breakdown, resolution rate.
   */
  getSummary: async (dateRange?: Partial<DateRange>): Promise<TicketSummaryResponse> => {
    const qs = formatDateParams(dateRange);
    return apiFetch<TicketSummaryResponse>(`${ANALYTICS_BASE}/summary${qs}`);
  },

  /**
   * Get summary directly from backend (no Next.js proxy).
   */
  getSummaryDirect: async (dateRange?: Partial<DateRange>): Promise<TicketSummaryResponse> => {
    const API_BASE = typeof window !== 'undefined' ? '' : (process.env.NEXT_PUBLIC_API_URL || '');
    const qs = formatDateParams(dateRange);
    return apiFetch<TicketSummaryResponse>(`${API_BASE}/analytics/tickets/summary${qs}`);
  },

  /**
   * Get ticket trend data over time.
   */
  getTrends: async (
    interval: IntervalType = 'day',
    dateRange?: Partial<DateRange>
  ): Promise<TrendPointResponse> => {
    const qs = formatDateParams(dateRange);
    return apiFetch<TrendPointResponse>(
      `${ANALYTICS_BASE}/trends?interval=${interval}${qs ? '&' + qs.slice(1) : ''}`
    );
  },

  /**
   * Get trends directly from backend.
   */
  getTrendsDirect: async (
    interval: IntervalType = 'day',
    dateRange?: Partial<DateRange>
  ): Promise<TrendPointResponse> => {
    const API_BASE = typeof window !== 'undefined' ? '' : (process.env.NEXT_PUBLIC_API_URL || '');
    const qs = formatDateParams(dateRange);
    return apiFetch<TrendPointResponse>(
      `${API_BASE}/analytics/tickets/trends?interval=${interval}${qs ? '&' + qs.slice(1) : ''}`
    );
  },

  /**
   * Get ticket category distribution.
   */
  getCategories: async (dateRange?: Partial<DateRange>): Promise<CategoryDistributionResponse> => {
    const qs = formatDateParams(dateRange);
    return apiFetch<CategoryDistributionResponse>(`${ANALYTICS_BASE}/category${qs}`);
  },

  /**
   * Get categories directly from backend.
   */
  getCategoriesDirect: async (dateRange?: Partial<DateRange>): Promise<CategoryDistributionResponse> => {
    const API_BASE = typeof window !== 'undefined' ? '' : (process.env.NEXT_PUBLIC_API_URL || '');
    const qs = formatDateParams(dateRange);
    return apiFetch<CategoryDistributionResponse>(`${API_BASE}/analytics/tickets/category${qs}`);
  },

  /**
   * Get SLA compliance metrics.
   */
  getSLA: async (dateRange?: Partial<DateRange>): Promise<SLAMetricsResponse> => {
    const qs = formatDateParams(dateRange);
    return apiFetch<SLAMetricsResponse>(`${ANALYTICS_BASE}/sla${qs}`);
  },

  /**
   * Get SLA directly from backend.
   */
  getSLADirect: async (dateRange?: Partial<DateRange>): Promise<SLAMetricsResponse> => {
    const API_BASE = typeof window !== 'undefined' ? '' : (process.env.NEXT_PUBLIC_API_URL || '');
    const qs = formatDateParams(dateRange);
    return apiFetch<SLAMetricsResponse>(`${API_BASE}/analytics/tickets/sla${qs}`);
  },

  /**
   * Get per-agent performance metrics.
   */
  getAgents: async (
    limit: number = 50,
    dateRange?: Partial<DateRange>
  ): Promise<AgentMetrics[]> => {
    const qs = formatDateParams(dateRange);
    return apiFetch<AgentMetrics[]>(
      `${ANALYTICS_BASE}/agents?limit=${limit}${qs ? '&' + qs.slice(1) : ''}`
    );
  },

  /**
   * Get agent metrics directly from backend.
   */
  getAgentsDirect: async (
    limit: number = 50,
    dateRange?: Partial<DateRange>
  ): Promise<AgentMetrics[]> => {
    const API_BASE = typeof window !== 'undefined' ? '' : (process.env.NEXT_PUBLIC_API_URL || '');
    const qs = formatDateParams(dateRange);
    return apiFetch<AgentMetrics[]>(
      `${API_BASE}/analytics/tickets/agents?limit=${limit}${qs ? '&' + qs.slice(1) : ''}`
    );
  },

  /**
   * Get response time distribution.
   */
  getResponseTime: async (_dateRange?: Partial<DateRange>): Promise<ResponseTimeDistribution> => {
    const API_BASE = typeof window !== 'undefined' ? '' : (process.env.NEXT_PUBLIC_API_URL || '');
    const qs = _dateRange ? formatDateParams(_dateRange) : '';
    return apiFetch<ResponseTimeDistribution>(`${API_BASE}/analytics/tickets/response-time${qs}`);
  },
};

export default analyticsApi;
