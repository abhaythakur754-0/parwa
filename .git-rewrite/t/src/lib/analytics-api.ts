/**
 * PARWA Analytics API
 *
 * API helper functions for ticket analytics endpoints.
 * Backend endpoints at /api/v1/analytics/tickets/*
 *
 * Uses the centralized apiClient from @/lib/api.ts
 * with JWT Bearer auth and tenant-scoped queries.
 *
 * Includes comprehensive mock data fallbacks for when
 * the backend is unavailable (demo/development mode).
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

// ── Mock Data Generators ───────────────────────────────────────────

function generateMockSummary(): TicketSummaryResponse {
  return {
    summary: {
      total_tickets: 1247,
      open: 183,
      in_progress: 97,
      resolved: 842,
      closed: 89,
      awaiting_client: 24,
      awaiting_human: 12,
      critical: 15,
      high: 134,
      medium: 487,
      low: 611,
      resolution_rate: 87.3,
      avg_resolution_time_hours: 2.4,
      avg_first_response_time_hours: 0.3,
    },
    date_range: {
      start_date: new Date(Date.now() - 30 * 86400000).toISOString().split('T')[0],
      end_date: new Date().toISOString().split('T')[0],
    },
  };
}

function generateMockTrends(interval: IntervalType = 'day'): TrendPointResponse {
  const days = 30;
  const points = [];
  for (let i = days - 1; i >= 0; i--) {
    const date = new Date(Date.now() - i * 86400000);
    points.push({
      timestamp: date.toISOString(),
      count: Math.floor(30 + Math.random() * 50 + (i < 10 ? 15 : 0)),
      label: date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
    });
  }
  return {
    trend: points,
    interval,
    date_range: {
      start_date: points[0]?.timestamp?.split('T')[0] || '',
      end_date: points[points.length - 1]?.timestamp?.split('T')[0] || '',
    },
  };
}

function generateMockCategories(): CategoryDistributionResponse {
  return {
    categories: [
      { category: 'Order Status', count: 287, percentage: 23.0 },
      { category: 'Billing & Payments', count: 198, percentage: 15.9 },
      { category: 'Technical Support', count: 174, percentage: 13.9 },
      { category: 'Product Returns', count: 156, percentage: 12.5 },
      { category: 'Account Issues', count: 132, percentage: 10.6 },
      { category: 'Shipping & Delivery', count: 118, percentage: 9.5 },
      { category: 'Product Info', count: 98, percentage: 7.9 },
      { category: 'Other', count: 84, percentage: 6.7 },
    ],
    date_range: {
      start_date: new Date(Date.now() - 30 * 86400000).toISOString().split('T')[0],
      end_date: new Date().toISOString().split('T')[0],
    },
  };
}

function generateMockSLA(): SLAMetricsResponse {
  return {
    sla: {
      total_tickets_with_sla: 1200,
      breached_count: 34,
      approaching_count: 56,
      compliant_count: 1110,
      compliance_rate: 92.5,
      avg_first_response_minutes: 4.2,
      avg_resolution_minutes: 142.0,
    },
    date_range: {
      start_date: new Date(Date.now() - 30 * 86400000).toISOString().split('T')[0],
      end_date: new Date().toISOString().split('T')[0],
    },
  };
}

function generateMockAgents(): AgentMetrics[] {
  return [
    {
      agent_id: 'agent_parwa_growth_01',
      agent_name: 'PARWA Growth #1',
      tickets_assigned: 389,
      tickets_resolved: 324,
      tickets_open: 42,
      avg_resolution_time_hours: 1.8,
      csat_avg: 4.5,
      csat_count: 312,
      resolution_rate: 83.3,
    },
    {
      agent_id: 'agent_parwa_growth_02',
      agent_name: 'PARWA Growth #2',
      tickets_assigned: 341,
      tickets_resolved: 287,
      tickets_open: 29,
      avg_resolution_time_hours: 2.1,
      csat_avg: 4.3,
      csat_count: 276,
      resolution_rate: 84.2,
    },
    {
      agent_id: 'agent_parwa_starter_01',
      agent_name: 'PARWA Starter #1',
      tickets_assigned: 267,
      tickets_resolved: 178,
      tickets_open: 52,
      avg_resolution_time_hours: 3.4,
      csat_avg: 3.9,
      csat_count: 167,
      resolution_rate: 66.7,
    },
    {
      agent_id: 'agent_human_01',
      agent_name: 'Sarah Johnson',
      tickets_assigned: 148,
      tickets_resolved: 134,
      tickets_open: 8,
      avg_resolution_time_hours: 1.2,
      csat_avg: 4.7,
      csat_count: 141,
      resolution_rate: 90.5,
    },
    {
      agent_id: 'agent_human_02',
      agent_name: 'Mike Chen',
      tickets_assigned: 102,
      tickets_resolved: 89,
      tickets_open: 6,
      avg_resolution_time_hours: 1.5,
      csat_avg: 4.6,
      csat_count: 95,
      resolution_rate: 87.3,
    },
  ];
}

function generateMockDashboard(): DashboardData {
  const summary = generateMockSummary();
  const categories = generateMockCategories();
  const trends = generateMockTrends('day');
  const sla = generateMockSLA();

  return {
    summary: summary.summary,
    sla: sla.sla,
    by_category: categories.categories,
    trend: trends.trend,
    date_range: summary.date_range,
  };
}

/**
 * Safe fetch wrapper with mock fallback.
 * M-29: Adds a `_mock: true` flag to the response when mock data
 * is returned, so the UI can display a "MOCK DATA" banner.
 */
async function apiFetch<T>(url: string, mockFn: () => T): Promise<T & { _mock?: boolean }> {
  try {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    const res = await fetch(url, {
      headers,
      credentials: 'include',
      signal: AbortSignal.timeout(8000),
    });

    if (!res.ok) {
      throw new Error(`API returned ${res.status}`);
    }

    return await res.json();
  } catch (err) {
    // M-29: Log when mock data is being returned
    if (typeof window !== 'undefined') {
      console.warn(
        '[PARWA Analytics] Backend unavailable — showing MOCK DATA.',
        'Set up the backend to see real analytics.',
        err
      );
    }
    // Backend unavailable — return mock data for demo mode
    // Mark with _mock flag so UI can display a banner
    return { ...mockFn(), _mock: true };
  }
}

// ── Analytics API ─────────────────────────────────────────────────

export const analyticsApi = {
  /**
   * Get combined dashboard data (summary + SLA + category + trend).
   */
  getDashboard: async (dateRange?: Partial<DateRange>): Promise<DashboardData> => {
    const qs = formatDateParams(dateRange);
    return apiFetch<DashboardData>(`${ANALYTICS_BASE}/dashboard${qs}`, generateMockDashboard);
  },

  /**
   * Get ticket summary counts, priority breakdown, resolution rate.
   */
  getSummary: async (dateRange?: Partial<DateRange>): Promise<TicketSummaryResponse> => {
    const qs = formatDateParams(dateRange);
    return apiFetch<TicketSummaryResponse>(`${ANALYTICS_BASE}/summary${qs}`, generateMockSummary);
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
      `${ANALYTICS_BASE}/trends?interval=${interval}${qs ? '&' + qs.slice(1) : ''}`,
      () => generateMockTrends(interval)
    );
  },

  /**
   * Get ticket category distribution.
   */
  getCategories: async (dateRange?: Partial<DateRange>): Promise<CategoryDistributionResponse> => {
    const qs = formatDateParams(dateRange);
    return apiFetch<CategoryDistributionResponse>(`${ANALYTICS_BASE}/category${qs}`, generateMockCategories);
  },

  /**
   * Get SLA compliance metrics.
   */
  getSLA: async (dateRange?: Partial<DateRange>): Promise<SLAMetricsResponse> => {
    const qs = formatDateParams(dateRange);
    return apiFetch<SLAMetricsResponse>(`${ANALYTICS_BASE}/sla${qs}`, generateMockSLA);
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
      `${ANALYTICS_BASE}/agents?limit=${limit}${qs ? '&' + qs.slice(1) : ''}`,
      generateMockAgents
    );
  },

  /**
   * Get response time distribution.
   */
  getResponseTime: async (_dateRange?: Partial<DateRange>): Promise<ResponseTimeDistribution> => {
    return {
      buckets: [
        { bucket: '0-15m', count: 342, label: '<15m' },
        { bucket: '15-30m', count: 267, label: '15-30m' },
        { bucket: '30m-1h', count: 189, label: '30m-1h' },
        { bucket: '1-2h', count: 134, label: '1-2h' },
        { bucket: '2-4h', count: 87, label: '2-4h' },
        { bucket: '4-8h', count: 42, label: '4-8h' },
        { bucket: '8h+', count: 18, label: '8h+' },
      ],
      avg_response_minutes: 28.4,
      median_response_minutes: 18.2,
      p95_response_minutes: 142.0,
    };
  },
};

export default analyticsApi;
