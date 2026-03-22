/**
 * PARWA Dashboard Components
 *
 * Export all dashboard-related components.
 */

// Ticket List
export { TicketList } from "./TicketList";
export type {
  Ticket,
  TicketPriority,
  TicketStatus,
  SortConfig,
  TicketListProps,
} from "./TicketList";

// Approval Queue
export { ApprovalQueue } from "./ApprovalQueue";
export type {
  ApprovalRequest,
  ApprovalStatus,
  ApprovalQueueProps,
} from "./ApprovalQueue";

// Jarvis Terminal
export { JarvisTerminal } from "./JarvisTerminal";
export type {
  TerminalLine,
  CommandHandler,
  JarvisTerminalProps,
} from "./JarvisTerminal";

// Agent Status
export { AgentStatus } from "./AgentStatus";
export type {
  Agent,
  AgentStatusType,
  AgentVariant,
  AgentStatusProps,
} from "./AgentStatus";

// Activity Feed
export { ActivityFeed } from "./ActivityFeed";
export type {
  Activity,
  ActivityType,
  ActivityFeedProps,
} from "./ActivityFeed";

// Notification Center
export { NotificationCenter } from "./NotificationCenter";
export type {
  Notification,
  NotificationType,
  NotificationCenterProps,
} from "./NotificationCenter";

// Search Bar
export { SearchBar } from "./SearchBar";
export type {
  SearchResult,
  SearchResultType,
  SearchBarProps,
} from "./SearchBar";
