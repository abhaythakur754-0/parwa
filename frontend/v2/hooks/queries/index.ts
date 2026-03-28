/**
 * PARWA Query Hooks Index
 *
 * Export all query hooks for the PARWA v2 frontend.
 */

// Tickets
export {
  useTickets,
  useTicket,
  useInfiniteTickets,
  useTicketSearch,
  useCreateTicket,
  useUpdateTicket,
  useAddTicketReply,
  usePrefetchTickets,
  usePrefetchTicket,
  // Types
  type Ticket,
  type TicketStatus,
  type TicketPriority,
  type TicketSource,
  type TicketCustomer,
  type TicketAssignee,
  type TicketMessage,
  type TicketsListResponse,
  type TicketsFilters,
  type CreateTicketData,
  type UpdateTicketData,
  type UseTicketsOptions,
  type UseTicketOptions,
  type UseInfiniteTicketsOptions,
} from "./useTicketsQuery";

// Approvals
export {
  useApprovals,
  useApproval,
  useApprovalStats,
  useApproveApproval,
  useDenyApproval,
  useApprovalActions,
  usePrefetchApprovals,
  // Types
  type Approval,
  type ApprovalType,
  type ApprovalStatus,
  type ApprovalRecommendation,
  type ApprovalRecommendationData,
  type ApprovalsListResponse,
  type ApprovalsFilters,
  type ApproveRequest,
  type DenyRequest,
  type ApprovalStats,
  type UseApprovalsOptions,
  type UseApprovalOptions,
} from "./useApprovalsQuery";

// Analytics
export {
  useAnalyticsOverview,
  useAnalyticsMetrics,
  useAnalyticsTrends,
  useRealtimeMetrics,
  useAnalyticsDashboard,
  useAgentPerformance,
  useCategoryBreakdown,
  useInvalidateAnalytics,
  usePrefetchAnalytics,
  useDateRangeFromPreset,
  // Types
  type AnalyticsOverview,
  type AnalyticsMetrics,
  type AnalyticsTrends,
  type TrendDataPoint,
  type RealtimeMetrics,
  type AnalyticsDashboard,
  type AgentPerformance,
  type CategoryBreakdown,
  type DateRange,
  type DateRangePreset,
  type UseAnalyticsOverviewOptions,
  type UseAnalyticsMetricsOptions,
  type UseAnalyticsTrendsOptions,
  type UseRealtimeMetricsOptions,
  DATE_RANGE_PRESETS,
} from "./useAnalyticsQuery";

// Clients
export {
  useClients,
  useClient,
  useClientHealth,
  useClientStats,
  useCreateClient,
  useUpdateClient,
  usePrefetchClients,
  usePrefetchClient,
  usePrefetchClientHealth,
  usePrefetchClientDetails,
  // Types
  type Client,
  type ClientIndustry,
  type ClientStatus,
  type SubscriptionTier,
  type ClientHealth,
  type ClientsListResponse,
  type ClientsFilters,
  type CreateClientData,
  type UpdateClientData,
  type ClientStats,
  type UseClientsOptions,
  type UseClientOptions,
  type UseClientHealthOptions,
} from "./useClientsQuery";

// Dashboard
export {
  useDashboardMetrics,
  useActivityFeed,
  useNotifications,
  useDashboardStats,
  useMarkNotificationRead,
  useMarkAllNotificationsRead,
  useInvalidateDashboard,
  usePrefetchDashboard,
  useUnreadNotificationCount,
  // Types
  type DashboardMetrics,
  type ActivityItem,
  type ActivityFeedResponse,
  type NotificationItem,
  type NotificationsResponse,
  type DashboardStats,
  type QuickAction,
  type UseDashboardMetricsOptions,
  type UseActivityFeedOptions,
} from "./useDashboardQuery";
