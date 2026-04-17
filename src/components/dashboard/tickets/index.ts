/**
 * PARWA Dashboard Tickets Components
 *
 * Barrel exports for all ticket management components.
 * Day 3 — Tickets Page
 * Day 7 — Real-time Updates & Dashboard Integration
 */

export { default as TicketList } from './TicketList';
export { default as TicketDetail } from './TicketDetail';
export { default as TicketRow, statusConfig, priorityConfig, channelIcons, timeAgo } from './TicketRow';
export { default as TicketSearch } from './TicketSearch';
export { default as TicketFiltersBar } from './TicketFilters';
export { default as TicketQuickView } from './TicketQuickView';
export { default as BulkActions } from './BulkActions';
export { default as ConversationView } from './ConversationView';
export { default as TicketMetadata } from './TicketMetadata';
export { default as ConfidenceBar } from './ConfidenceBar';
export { default as GSDStateIndicator } from './GSDStateIndicator';
export { default as CustomerInfoCard } from './CustomerInfoCard';
export { default as InternalNotes } from './InternalNotes';
export { default as TimelineView } from './TimelineView';
export { default as ReplyBox } from './ReplyBox';

// Day 7 — Real-time Updates
export { default as RealtimeNotifications } from './RealtimeNotifications';
export { default as TicketActivityStream } from './TicketActivityStream';
export { default as DashboardWidgets } from './DashboardWidgets';
export { default as AgentPresenceIndicator, AgentPresenceList, PresenceDot } from './AgentPresenceIndicator';
export { useTicketRealtime } from './useTicketRealtime';
export type { TicketEvent, TicketRealtimeState, TicketRealtimeActions, TicketRealtimeReturn } from './useTicketRealtime';
export type { AgentPresence, PresenceStatus } from './AgentPresenceIndicator';
