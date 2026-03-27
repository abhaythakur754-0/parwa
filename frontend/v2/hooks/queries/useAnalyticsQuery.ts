/**
 * PARWA Analytics Query Hook
 *
 * Enhanced hook for analytics data with caching strategies.
 * Features date range filtering, trend analysis, and real-time metrics.
 *
 * @module hooks/queries/useAnalyticsQuery
 */

"use client";

import {
  useQuery,
  useQueryClient,
  type UseQueryOptions,
} from "@tanstack/react-query";
import { useCallback, useEffect, useRef } from "react";
import { z } from "zod";
import { queryKeys } from "../../lib/react-query/query-client";

// ============================================================================
// Types & Schemas
// ============================================================================

/**
 * Date range schema.
 */
export const DateRangeSchema = z.object({
  start: z.string(),
  end: z.string(),
});

export type DateRange = z.infer<typeof DateRangeSchema>;

/**
 * Analytics overview schema.
 */
export const AnalyticsOverviewSchema = z.object({
  totalTickets: z.number(),
  openTickets: z.number(),
  resolvedTickets: z.number(),
  avgResponseTime: z.number(),
  avgResolutionTime: z.number(),
  customerSatisfaction: z.number(),
  automationRate: z.number(),
  approvalRate: z.number(),
  escalationRate: z.number(),
  periodComparison: z.object({
    totalTickets: z.number(),
    response: z.number(),
    resolution: z.number(),
    satisfaction: z.number(),
  }),
});

export type AnalyticsOverview = z.infer<typeof AnalyticsOverviewSchema>;

/**
 * Metrics schema for specific date range.
 */
export const AnalyticsMetricsSchema = z.object({
  date: z.string(),
  ticketsCreated: z.number(),
  ticketsResolved: z.number(),
  avgResponseTime: z.number(),
  avgResolutionTime: z.number(),
  customerSatisfaction: z.number(),
  automationRate: z.number(),
  approvalsProcessed: z.number(),
  escalations: z.number(),
  topCategories: z.array(
    z.object({
      category: z.string(),
      count: z.number(),
      percentage: z.number(),
    })
  ),
});

export type AnalyticsMetrics = z.infer<typeof AnalyticsMetricsSchema>;

/**
 * Trend data point schema.
 */
export const TrendDataPointSchema = z.object({
  date: z.string(),
  value: z.number(),
  label: z.string().optional(),
});

export type TrendDataPoint = z.infer<typeof TrendDataPointSchema>;

/**
 * Analytics trends schema.
 */
export const AnalyticsTrendsSchema = z.object({
  ticketVolume: z.array(TrendDataPointSchema),
  responseTime: z.array(TrendDataPointSchema),
  resolutionTime: z.array(TrendDataPointSchema),
  satisfaction: z.array(TrendDataPointSchema),
  automationRate: z.array(TrendDataPointSchema),
});

export type AnalyticsTrends = z.infer<typeof AnalyticsTrendsSchema>;

/**
 * Real-time metrics schema.
 */
export const RealtimeMetricsSchema = z.object({
  activeTickets: z.number(),
  activeConversations: z.number(),
  pendingApprovals: z.number(),
  agentsOnline: z.number(),
  avgWaitTime: z.number(),
  timestamp: z.string(),
});

export type RealtimeMetrics = z.infer<typeof RealtimeMetricsSchema>;

/**
 * Agent performance schema.
 */
export const AgentPerformanceSchema = z.object({
  agentId: z.string(),
  agentName: z.string(),
  ticketsResolved: z.number(),
  avgResponseTime: z.number(),
  customerSatisfaction: z.number(),
  automationRate: z.number(),
  escalations: z.number(),
});

export type AgentPerformance = z.infer<typeof AgentPerformanceSchema>;

/**
 * Category breakdown schema.
 */
export const CategoryBreakdownSchema = z.object({
  category: z.string(),
  count: z.number(),
  percentage: z.number(),
  avgResolutionTime: z.number(),
  satisfaction: z.number(),
  trend: z.enum(["up", "down", "stable"]),
});

export type CategoryBreakdown = z.infer<typeof CategoryBreakdownSchema>;

/**
 * Analytics dashboard data schema.
 */
export const AnalyticsDashboardSchema = z.object({
  overview: AnalyticsOverviewSchema,
  trends: AnalyticsTrendsSchema,
  categories: z.array(CategoryBreakdownSchema),
  topAgents: z.array(AgentPerformanceSchema),
});

export type AnalyticsDashboard = z.infer<typeof AnalyticsDashboardSchema>;

// ============================================================================
// API Functions
// ============================================================================

const API_BASE = "/api";

/**
 * Fetch analytics overview.
 */
async function fetchAnalyticsOverview(): Promise<AnalyticsOverview> {
  const response = await fetch(`${API_BASE}/analytics/overview`);
  if (!response.ok) {
    throw new Error(`Failed to fetch analytics overview: ${response.statusText}`);
  }

  const data = await response.json();
  return AnalyticsOverviewSchema.parse(data);
}

/**
 * Fetch metrics for specific date range.
 */
async function fetchAnalyticsMetrics(dateRange: DateRange): Promise<AnalyticsMetrics> {
  const searchParams = new URLSearchParams({
    start: dateRange.start,
    end: dateRange.end,
  });

  const response = await fetch(`${API_BASE}/analytics/metrics?${searchParams}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch analytics metrics: ${response.statusText}`);
  }

  const data = await response.json();
  return AnalyticsMetricsSchema.parse(data);
}

/**
 * Fetch analytics trends.
 */
async function fetchAnalyticsTrends(period: string): Promise<AnalyticsTrends> {
  const response = await fetch(`${API_BASE}/analytics/trends?period=${period}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch analytics trends: ${response.statusText}`);
  }

  const data = await response.json();
  return AnalyticsTrendsSchema.parse(data);
}

/**
 * Fetch real-time metrics.
 */
async function fetchRealtimeMetrics(): Promise<RealtimeMetrics> {
  const response = await fetch(`${API_BASE}/analytics/realtime`);
  if (!response.ok) {
    throw new Error(`Failed to fetch realtime metrics: ${response.statusText}`);
  }

  const data = await response.json();
  return RealtimeMetricsSchema.parse(data);
}

/**
 * Fetch analytics dashboard data.
 */
async function fetchAnalyticsDashboard(): Promise<AnalyticsDashboard> {
  const response = await fetch(`${API_BASE}/analytics/dashboard`);
  if (!response.ok) {
    throw new Error(`Failed to fetch analytics dashboard: ${response.statusText}`);
  }

  const data = await response.json();
  return AnalyticsDashboardSchema.parse(data);
}

/**
 * Fetch agent performance data.
 */
async function fetchAgentPerformance(dateRange?: DateRange): Promise<AgentPerformance[]> {
  const searchParams = new URLSearchParams();
  if (dateRange) {
    searchParams.set("start", dateRange.start);
    searchParams.set("end", dateRange.end);
  }

  const response = await fetch(`${API_BASE}/analytics/agents?${searchParams}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch agent performance: ${response.statusText}`);
  }

  const data = await response.json();
  return z.array(AgentPerformanceSchema).parse(data);
}

/**
 * Fetch category breakdown.
 */
async function fetchCategoryBreakdown(): Promise<CategoryBreakdown[]> {
  const response = await fetch(`${API_BASE}/analytics/categories`);
  if (!response.ok) {
    throw new Error(`Failed to fetch category breakdown: ${response.statusText}`);
  }

  const data = await response.json();
  return z.array(CategoryBreakdownSchema).parse(data);
}

// ============================================================================
// Query Hooks
// ============================================================================

/**
 * Options for useAnalyticsOverview hook.
 */
export interface UseAnalyticsOverviewOptions
  extends Omit<UseQueryOptions<AnalyticsOverview, Error>, "queryKey" | "queryFn"> {
  /** Auto-refresh interval in milliseconds */
  refetchInterval?: number;
}

/**
 * Hook to fetch analytics overview.
 *
 * @param options - Query options
 * @returns Query result with analytics overview
 *
 * @example
 * ```tsx
 * function AnalyticsCard() {
 *   const { data, isLoading } = useAnalyticsOverview();
 *
 *   return (
 *     <div>
 *       <h3>Total Tickets: {data?.totalTickets}</h3>
 *       <p>Satisfaction: {(data?.customerSatisfaction * 100).toFixed(0)}%</p>
 *     </div>
 *   );
 * }
 * ```
 */
export function useAnalyticsOverview(options: UseAnalyticsOverviewOptions = {}) {
  const { refetchInterval = 60000, ...queryOptions } = options;

  return useQuery({
    queryKey: queryKeys.analytics.overview(),
    queryFn: fetchAnalyticsOverview,
    staleTime: 5 * 60 * 1000, // 5 minutes
    refetchInterval,
    ...queryOptions,
  });
}

/**
 * Options for useAnalyticsMetrics hook.
 */
export interface UseAnalyticsMetricsOptions
  extends Omit<UseQueryOptions<AnalyticsMetrics, Error>, "queryKey" | "queryFn"> {
  /** Date range for metrics */
  dateRange: DateRange;
}

/**
 * Hook to fetch analytics metrics for specific date range.
 *
 * @param options - Query options including date range
 * @returns Query result with metrics data
 */
export function useAnalyticsMetrics(options: UseAnalyticsMetricsOptions) {
  const { dateRange, ...queryOptions } = options;

  return useQuery({
    queryKey: queryKeys.analytics.metrics(dateRange),
    queryFn: () => fetchAnalyticsMetrics(dateRange),
    staleTime: 10 * 60 * 1000, // 10 minutes
    ...queryOptions,
  });
}

/**
 * Options for useAnalyticsTrends hook.
 */
export interface UseAnalyticsTrendsOptions
  extends Omit<UseQueryOptions<AnalyticsTrends, Error>, "queryKey" | "queryFn"> {
  /** Time period (e.g., '7d', '30d', '90d') */
  period?: string;
}

/**
 * Hook to fetch analytics trends.
 *
 * @param options - Query options including period
 * @returns Query result with trends data
 */
export function useAnalyticsTrends(options: UseAnalyticsTrendsOptions = {}) {
  const { period = "30d", ...queryOptions } = options;

  return useQuery({
    queryKey: queryKeys.analytics.trends(period),
    queryFn: () => fetchAnalyticsTrends(period),
    staleTime: 15 * 60 * 1000, // 15 minutes
    ...queryOptions,
  });
}

/**
 * Options for useRealtimeMetrics hook.
 */
export interface UseRealtimeMetricsOptions
  extends Omit<UseQueryOptions<RealtimeMetrics, Error>, "queryKey" | "queryFn"> {
  /** Enable real-time WebSocket updates */
  websocket?: boolean;
  /** Auto-refresh interval in milliseconds */
  refetchInterval?: number;
}

/**
 * Hook to fetch real-time metrics.
 *
 * @param options - Query options
 * @returns Query result with real-time metrics
 */
export function useRealtimeMetrics(options: UseRealtimeMetricsOptions = {}) {
  const { websocket = false, refetchInterval = 5000, ...queryOptions } = options;

  const queryClient = useQueryClient();
  const wsRef = useRef<WebSocket | null>(null);

  const query = useQuery({
    queryKey: queryKeys.analytics.realtime(),
    queryFn: fetchRealtimeMetrics,
    staleTime: 10 * 1000, // 10 seconds
    refetchInterval: websocket ? false : refetchInterval,
    ...queryOptions,
  });

  // WebSocket for real-time updates
  useEffect(() => {
    if (!websocket) return;

    const wsUrl = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:3001";
    wsRef.current = new WebSocket(`${wsUrl}/analytics/realtime`);

    wsRef.current.onmessage = (event) => {
      const update = JSON.parse(event.data);
      if (update.type === "realtime_metrics") {
        queryClient.setQueryData(queryKeys.analytics.realtime(), update.data);
      }
    };

    return () => {
      wsRef.current?.close();
    };
  }, [websocket, queryClient]);

  return query;
}

/**
 * Hook to fetch complete analytics dashboard data.
 *
 * @param options - Query options
 * @returns Query result with dashboard data
 */
export function useAnalyticsDashboard(
  options: Omit<UseQueryOptions<AnalyticsDashboard, Error>, "queryKey" | "queryFn"> = {}
) {
  return useQuery({
    queryKey: queryKeys.analytics.all,
    queryFn: fetchAnalyticsDashboard,
    staleTime: 5 * 60 * 1000,
    ...options,
  });
}

/**
 * Hook to fetch agent performance data.
 *
 * @param options - Query options including optional date range
 * @returns Query result with agent performance data
 */
export function useAgentPerformance(
  options: Omit<UseQueryOptions<AgentPerformance[], Error>, "queryKey" | "queryFn"> & {
    dateRange?: DateRange;
  } = {}
) {
  const { dateRange, ...queryOptions } = options;

  return useQuery({
    queryKey: ["analytics", "agents", dateRange],
    queryFn: () => fetchAgentPerformance(dateRange),
    staleTime: 10 * 60 * 1000,
    ...queryOptions,
  });
}

/**
 * Hook to fetch category breakdown.
 *
 * @param options - Query options
 * @returns Query result with category breakdown
 */
export function useCategoryBreakdown(
  options: Omit<UseQueryOptions<CategoryBreakdown[], Error>, "queryKey" | "queryFn"> = {}
) {
  return useQuery({
    queryKey: ["analytics", "categories"],
    queryFn: fetchCategoryBreakdown,
    staleTime: 15 * 60 * 1000,
    ...options,
  });
}

// ============================================================================
// Utility Hooks
// ============================================================================

/**
 * Hook to invalidate analytics caches.
 * Useful after data changes that affect analytics.
 */
export function useInvalidateAnalytics() {
  const queryClient = useQueryClient();

  return useCallback(() => {
    queryClient.invalidateQueries({ queryKey: queryKeys.analytics.all });
  }, [queryClient]);
}

/**
 * Hook to prefetch analytics data.
 */
export function usePrefetchAnalytics() {
  const queryClient = useQueryClient();

  return useCallback(() => {
    queryClient.prefetchQuery({
      queryKey: queryKeys.analytics.overview(),
      queryFn: fetchAnalyticsOverview,
    });

    queryClient.prefetchQuery({
      queryKey: queryKeys.analytics.realtime(),
      queryFn: fetchRealtimeMetrics,
    });
  }, [queryClient]);
}

/**
 * Date range presets.
 */
export const DATE_RANGE_PRESETS = {
  today: { start: "today", end: "today" },
  yesterday: { start: "yesterday", end: "yesterday" },
  last7Days: { start: "-7d", end: "today" },
  last30Days: { start: "-30d", end: "today" },
  last90Days: { start: "-90d", end: "today" },
  thisMonth: { start: "monthStart", end: "today" },
  lastMonth: { start: "lastMonthStart", end: "lastMonthEnd" },
  thisYear: { start: "yearStart", end: "today" },
} as const;

export type DateRangePreset = keyof typeof DATE_RANGE_PRESETS;

/**
 * Hook to get date range from preset.
 */
export function useDateRangeFromPreset(preset: DateRangePreset): DateRange {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());

  const getDate = (offset: string): string => {
    const d = new Date(today);

    switch (offset) {
      case "today":
        break;
      case "yesterday":
        d.setDate(d.getDate() - 1);
        break;
      case "monthStart":
        d.setDate(1);
        break;
      case "lastMonthStart":
        d.setMonth(d.getMonth() - 1);
        d.setDate(1);
        break;
      case "lastMonthEnd":
        d.setDate(0); // Last day of previous month
        break;
      case "yearStart":
        d.setMonth(0, 1);
        break;
      default:
        const daysMatch = offset.match(/^-?(\d+)d$/);
        if (daysMatch) {
          d.setDate(d.getDate() - parseInt(daysMatch[1], 10));
        }
    }

    return d.toISOString().split("T")[0];
  };

  const presetValue = DATE_RANGE_PRESETS[preset];
  return {
    start: getDate(presetValue.start),
    end: getDate(presetValue.end),
  };
}

export default useAnalyticsOverview;
