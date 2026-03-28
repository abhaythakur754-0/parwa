/**
 * PARWA Dashboard Query Hook
 *
 * Enhanced hook for dashboard metrics with background refetching.
 * Features real-time updates, caching, and performance monitoring.
 *
 * @module hooks/queries/useDashboardQuery
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
 * Dashboard metrics schema.
 */
export const DashboardMetricsSchema = z.object({
  // Ticket metrics
  totalTickets: z.number(),
  openTickets: z.number(),
  inProgressTickets: z.number(),
  resolvedToday: z.number(),
  avgResponseTime: z.number(),
  avgResolutionTime: z.number(),

  // Approval metrics
  pendingApprovals: z.number(),
  approvedToday: z.number(),
  deniedToday: z.number(),
  avgApprovalTime: z.number(),

  // Performance metrics
  customerSatisfaction: z.number(),
  automationRate: z.number(),
  escalationRate: z.number(),
  firstContactResolution: z.number(),

  // Agent metrics
  activeAgents: z.number(),
  totalAgents: z.number(),
  avgAgentLoad: z.number(),

  // SLA metrics
  slaBreaches: z.number(),
  slaAtRisk: z.number(),
  slaCompliance: z.number(),

  // Period comparison
  comparison: z.object({
    ticketVolume: z.number(), // percentage change
    responseTime: z.number(),
    resolutionTime: z.number(),
    satisfaction: z.number(),
    automationRate: z.number(),
  }),
});

export type DashboardMetrics = z.infer<typeof DashboardMetricsSchema>;

/**
 * Activity feed item schema.
 */
export const ActivityItemSchema = z.object({
  id: z.string(),
  type: z.enum([
    "ticket_created",
    "ticket_updated",
    "ticket_resolved",
    "approval_requested",
    "approval_processed",
    "escalation",
    "agent_action",
    "system_alert",
  ]),
  title: z.string(),
  description: z.string(),
  timestamp: z.string(),
  actor: z
    .object({
      id: z.string(),
      name: z.string(),
      avatar: z.string().optional(),
    })
    .optional(),
  metadata: z.record(z.unknown()).optional(),
  link: z.string().optional(),
});

export type ActivityItem = z.infer<typeof ActivityItemSchema>;

/**
 * Activity feed response schema.
 */
export const ActivityFeedResponseSchema = z.object({
  activities: z.array(ActivityItemSchema),
  total: z.number(),
  hasMore: z.boolean(),
});

export type ActivityFeedResponse = z.infer<typeof ActivityFeedResponseSchema>;

/**
 * Notification item schema.
 */
export const NotificationItemSchema = z.object({
  id: z.string(),
  type: z.enum(["info", "warning", "error", "success"]),
  title: z.string(),
  message: z.string(),
  timestamp: z.string(),
  read: z.boolean(),
  actionUrl: z.string().optional(),
});

export type NotificationItem = z.infer<typeof NotificationItemSchema>;

/**
 * Notifications response schema.
 */
export const NotificationsResponseSchema = z.object({
  notifications: z.array(NotificationItemSchema),
  unreadCount: z.number(),
  total: z.number(),
});

export type NotificationsResponse = z.infer<typeof NotificationsResponseSchema>;

/**
 * Dashboard stats schema.
 */
export const DashboardStatsSchema = z.object({
  ticketsByStatus: z.record(z.number()),
  ticketsByPriority: z.record(z.number()),
  ticketsBySource: z.record(z.number()),
  approvalsByType: z.record(z.number()),
  performanceByAgent: z.array(
    z.object({
      agentId: z.string(),
      agentName: z.string(),
      ticketsResolved: z.number(),
      avgResponseTime: z.number(),
      satisfaction: z.number(),
    })
  ),
  hourlyVolume: z.array(
    z.object({
      hour: z.number(),
      tickets: z.number(),
      resolved: z.number(),
    })
  ),
  dailyTrends: z.array(
    z.object({
      date: z.string(),
      tickets: z.number(),
      resolved: z.number(),
      satisfaction: z.number(),
    })
  ),
});

export type DashboardStats = z.infer<typeof DashboardStatsSchema>;

/**
 * Quick action schema.
 */
export const QuickActionSchema = z.object({
  id: z.string(),
  label: z.string(),
  description: z.string(),
  icon: z.string(),
  href: z.string().optional(),
  action: z.string().optional(),
  badge: z.number().optional(),
  disabled: z.boolean().optional(),
});

export type QuickAction = z.infer<typeof QuickActionSchema>;

// ============================================================================
// API Functions
// ============================================================================

const API_BASE = "/api";

/**
 * Fetch dashboard metrics.
 */
async function fetchDashboardMetrics(): Promise<DashboardMetrics> {
  const response = await fetch(`${API_BASE}/dashboard/metrics`);
  if (!response.ok) {
    throw new Error(`Failed to fetch dashboard metrics: ${response.statusText}`);
  }

  const data = await response.json();
  return DashboardMetricsSchema.parse(data);
}

/**
 * Fetch activity feed.
 */
async function fetchActivityFeed(limit = 20): Promise<ActivityFeedResponse> {
  const response = await fetch(`${API_BASE}/dashboard/activity?limit=${limit}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch activity feed: ${response.statusText}`);
  }

  const data = await response.json();
  return ActivityFeedResponseSchema.parse(data);
}

/**
 * Fetch notifications.
 */
async function fetchNotifications(): Promise<NotificationsResponse> {
  const response = await fetch(`${API_BASE}/dashboard/notifications`);
  if (!response.ok) {
    throw new Error(`Failed to fetch notifications: ${response.statusText}`);
  }

  const data = await response.json();
  return NotificationsResponseSchema.parse(data);
}

/**
 * Fetch dashboard stats.
 */
async function fetchDashboardStats(): Promise<DashboardStats> {
  const response = await fetch(`${API_BASE}/dashboard/stats`);
  if (!response.ok) {
    throw new Error(`Failed to fetch dashboard stats: ${response.statusText}`);
  }

  const data = await response.json();
  return DashboardStatsSchema.parse(data);
}

/**
 * Mark notification as read.
 */
async function markNotificationRead(id: string): Promise<void> {
  const response = await fetch(`${API_BASE}/dashboard/notifications/${id}/read`, {
    method: "POST",
  });

  if (!response.ok) {
    throw new Error(`Failed to mark notification as read: ${response.statusText}`);
  }
}

/**
 * Mark all notifications as read.
 */
async function markAllNotificationsRead(): Promise<void> {
  const response = await fetch(`${API_BASE}/dashboard/notifications/read-all`, {
    method: "POST",
  });

  if (!response.ok) {
    throw new Error(`Failed to mark all notifications as read: ${response.statusText}`);
  }
}

// ============================================================================
// Query Hooks
// ============================================================================

/**
 * Options for useDashboardMetrics hook.
 */
export interface UseDashboardMetricsOptions
  extends Omit<UseQueryOptions<DashboardMetrics, Error>, "queryKey" | "queryFn"> {
  /** Enable real-time WebSocket updates */
  realtime?: boolean;
  /** Auto-refresh interval in milliseconds */
  refetchInterval?: number;
  /** Background refetch on window focus */
  refetchOnWindowFocus?: boolean;
}

/**
 * Hook to fetch dashboard metrics.
 *
 * @param options - Query options
 * @returns Query result with dashboard metrics
 *
 * @example
 * ```tsx
 * function Dashboard() {
 *   const { data, isLoading, error } = useDashboardMetrics({
 *     realtime: true,
 *     refetchInterval: 30000,
 *   });
 *
 *   return (
 *     <div>
 *       <MetricCard title="Open Tickets" value={data?.openTickets} />
 *       <MetricCard title="Satisfaction" value={data?.customerSatisfaction} />
 *     </div>
 *   );
 * }
 * ```
 */
export function useDashboardMetrics(options: UseDashboardMetricsOptions = {}) {
  const {
    realtime = false,
    refetchInterval = 30000, // 30 seconds
    refetchOnWindowFocus = true,
    ...queryOptions
  } = options;

  const queryClient = useQueryClient();
  const wsRef = useRef<WebSocket | null>(null);

  const query = useQuery({
    queryKey: queryKeys.dashboard.metrics(),
    queryFn: fetchDashboardMetrics,
    staleTime: 15 * 1000, // 15 seconds
    refetchInterval,
    refetchOnWindowFocus,
    ...queryOptions,
  });

  // WebSocket for real-time updates
  useEffect(() => {
    if (!realtime) return;

    const wsUrl = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:3001";
    wsRef.current = new WebSocket(`${wsUrl}/dashboard`);

    wsRef.current.onmessage = (event) => {
      const update = JSON.parse(event.data);

      switch (update.type) {
        case "metrics_update":
          queryClient.setQueryData(queryKeys.dashboard.metrics(), update.data);
          break;

        case "ticket_update":
          // Incrementally update ticket counts
          queryClient.setQueryData<DashboardMetrics>(
            queryKeys.dashboard.metrics(),
            (old) => {
              if (!old) return old;
              return {
                ...old,
                totalTickets: old.totalTickets + (update.data.created ? 1 : 0),
                openTickets: old.openTickets + (update.data.status === "open" ? 1 : 0),
                resolvedToday: old.resolvedToday + (update.data.resolved ? 1 : 0),
              };
            }
          );
          break;

        case "approval_update":
          queryClient.setQueryData<DashboardMetrics>(
            queryKeys.dashboard.metrics(),
            (old) => {
              if (!old) return old;
              return {
                ...old,
                pendingApprovals: old.pendingApprovals + update.data.change,
              };
            }
          );
          break;
      }
    };

    return () => {
      wsRef.current?.close();
    };
  }, [realtime, queryClient]);

  return query;
}

/**
 * Options for useActivityFeed hook.
 */
export interface UseActivityFeedOptions
  extends Omit<UseQueryOptions<ActivityFeedResponse, Error>, "queryKey" | "queryFn"> {
  /** Number of items to fetch */
  limit?: number;
  /** Enable real-time updates */
  realtime?: boolean;
}

/**
 * Hook to fetch activity feed.
 *
 * @param options - Query options
 * @returns Query result with activity feed data
 */
export function useActivityFeed(options: UseActivityFeedOptions = {}) {
  const { limit = 20, realtime = false, ...queryOptions } = options;

  const queryClient = useQueryClient();
  const wsRef = useRef<WebSocket | null>(null);

  const query = useQuery({
    queryKey: queryKeys.dashboard.activity(),
    queryFn: () => fetchActivityFeed(limit),
    staleTime: 10 * 1000,
    ...queryOptions,
  });

  // WebSocket for real-time updates
  useEffect(() => {
    if (!realtime) return;

    const wsUrl = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:3001";
    wsRef.current = new WebSocket(`${wsUrl}/activity`);

    wsRef.current.onmessage = (event) => {
      const update = JSON.parse(event.data);

      if (update.type === "new_activity") {
        queryClient.setQueryData<ActivityFeedResponse>(
          queryKeys.dashboard.activity(),
          (old) => {
            if (!old) return old;
            return {
              ...old,
              activities: [update.data, ...old.activities.slice(0, limit - 1)],
              total: old.total + 1,
            };
          }
        );
      }
    };

    return () => {
      wsRef.current?.close();
    };
  }, [realtime, limit, queryClient]);

  return query;
}

/**
 * Hook to fetch notifications.
 *
 * @param options - Query options
 * @returns Query result with notifications data
 */
export function useNotifications(
  options: Omit<UseQueryOptions<NotificationsResponse, Error>, "queryKey" | "queryFn"> = {}
) {
  return useQuery({
    queryKey: queryKeys.dashboard.notifications(),
    queryFn: fetchNotifications,
    staleTime: 30 * 1000,
    ...options,
  });
}

/**
 * Hook to fetch dashboard stats.
 *
 * @param options - Query options
 * @returns Query result with dashboard stats
 */
export function useDashboardStats(
  options: Omit<UseQueryOptions<DashboardStats, Error>, "queryKey" | "queryFn"> = {}
) {
  return useQuery({
    queryKey: queryKeys.dashboard.stats(),
    queryFn: fetchDashboardStats,
    staleTime: 60 * 1000, // 1 minute
    ...options,
  });
}

// ============================================================================
// Utility Hooks
// ============================================================================

/**
 * Hook to mark notification as read.
 */
export function useMarkNotificationRead() {
  const queryClient = useQueryClient();

  return useCallback(
    async (id: string) => {
      await markNotificationRead(id);

      // Update cache
      queryClient.setQueryData<NotificationsResponse>(
        queryKeys.dashboard.notifications(),
        (old) => {
          if (!old) return old;
          return {
            ...old,
            notifications: old.notifications.map((n) =>
              n.id === id ? { ...n, read: true } : n
            ),
            unreadCount: Math.max(0, old.unreadCount - 1),
          };
        }
      );
    },
    [queryClient]
  );
}

/**
 * Hook to mark all notifications as read.
 */
export function useMarkAllNotificationsRead() {
  const queryClient = useQueryClient();

  return useCallback(async () => {
    await markAllNotificationsRead();

    // Update cache
    queryClient.setQueryData<NotificationsResponse>(
      queryKeys.dashboard.notifications(),
      (old) => {
        if (!old) return old;
        return {
          ...old,
          notifications: old.notifications.map((n) => ({ ...n, read: true })),
          unreadCount: 0,
        };
      }
    );
  }, [queryClient]);
}

/**
 * Hook to invalidate all dashboard caches.
 */
export function useInvalidateDashboard() {
  const queryClient = useQueryClient();

  return useCallback(() => {
    queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.all });
  }, [queryClient]);
}

/**
 * Hook to prefetch dashboard data.
 */
export function usePrefetchDashboard() {
  const queryClient = useQueryClient();

  return useCallback(() => {
    queryClient.prefetchQuery({
      queryKey: queryKeys.dashboard.metrics(),
      queryFn: fetchDashboardMetrics,
    });

    queryClient.prefetchQuery({
      queryKey: queryKeys.dashboard.activity(),
      queryFn: () => fetchActivityFeed(20),
    });

    queryClient.prefetchQuery({
      queryKey: queryKeys.dashboard.stats(),
      queryFn: fetchDashboardStats,
    });
  }, [queryClient]);
}

/**
 * Hook to get unread notification count.
 */
export function useUnreadNotificationCount(): number {
  const { data } = useNotifications();
  return data?.unreadCount ?? 0;
}

export default useDashboardMetrics;
