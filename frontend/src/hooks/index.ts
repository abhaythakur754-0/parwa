/**
 * PARWA Hooks
 *
 * Export all custom hooks for the PARWA application.
 *
 * Hooks included:
 * - useAuth: Authentication operations
 * - useApprovals: Approval queue management
 * - useTickets: Ticket management
 * - useAnalytics: Analytics and reporting
 * - useJarvis: Jarvis command terminal (with streaming)
 * - useAgents: Agent management
 * - useNotifications: Notification management
 * - useSearch: Global search functionality
 *
 * @example
 * ```tsx
 * import {
 *   useAuth,
 *   useApprovals,
 *   useTickets,
 *   useAnalytics,
 *   useJarvis,
 *   useAgents,
 *   useNotifications,
 *   useSearch
 * } from "@/hooks";
 *
 * function Dashboard() {
 *   const { user, isAuthenticated } = useAuth();
 *   const { approvals, approve } = useApprovals();
 *   const { tickets, fetchTickets } = useTickets();
 *   const { metrics } = useAnalytics();
 *   const { sendCommand, response } = useJarvis();
 *   const { agents, pauseAgent } = useAgents();
 *   const { notifications, unreadCount } = useNotifications();
 *   const { search, results } = useSearch();
 *
 *   return (
 *     // Dashboard UI
 *   );
 * }
 * ```
 */

// Auth hook
export { useAuth } from "./useAuth";
export type { UseAuthReturn } from "./useAuth";

// Approvals hook
export { useApprovals } from "./useApprovals";
export type {
  UseApprovalsReturn,
  Approval,
  ApprovalType,
  ApprovalStatus,
  ApprovalRecommendation,
  ApprovalsFilters,
} from "./useApprovals";

// Tickets hook
export { useTickets } from "./useTickets";
export type {
  UseTicketsReturn,
  Ticket,
  TicketStatus,
  TicketPriority,
  TicketSource,
  TicketCustomer,
  TicketAssignee,
  TicketMessage,
  TicketsFilters,
  CreateTicketData,
  UpdateTicketData,
} from "./useTickets";

// Analytics hook
export { useAnalytics } from "./useAnalytics";
export type {
  UseAnalyticsReturn,
  DashboardMetrics,
  ChartDataPoint,
  ChartType,
  ChartDataResponse,
  AgentPerformance,
  DateRange,
  PresetRange,
  ExportFormat,
} from "./useAnalytics";

// Jarvis hook (CRITICAL: supports streaming)
export { useJarvis } from "./useJarvis";
export type {
  UseJarvisReturn,
  CommandHistoryItem,
  JarvisCommand,
  JarvisResponse,
} from "./useJarvis";

// Agents hook
export { useAgents } from "./useAgents";
export type {
  UseAgentsReturn,
  Agent,
  AgentVariant,
  AgentStatus,
  AgentTask,
  AgentMetrics,
  AgentLogEntry,
} from "./useAgents";

// Notifications hook
export { useNotifications } from "./useNotifications";
export type {
  UseNotificationsReturn,
  Notification,
  NotificationType,
  NotificationPriority,
} from "./useNotifications";

// Search hook
export { useSearch } from "./useSearch";
export type {
  UseSearchReturn,
  SearchResult,
  SearchResultType,
  SearchSuggestion,
  SearchHistoryItem,
} from "./useSearch";

// Re-export toast hook from shadcn/ui
export { useToast, toast, ToastProvider } from "./use-toast";
export type { Toast, ToastOptions, ToastVariant, ToastAction } from "./use-toast";
