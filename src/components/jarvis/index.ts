/**
 * PARWA Jarvis Component Barrel Export (Week 6 — Day 3 Phase 5, Updated Day 4 Phase 6)
 *
 * Single entry point for all Jarvis chat UI components.
 */

// Core (Phase 5)
export { JarvisChat } from './JarvisChat';
export { ChatHeader } from './ChatHeader';
export { ChatWindow } from './ChatWindow';
export { ChatMessage } from './ChatMessage';
export { ChatInput } from './ChatInput';
export { TypingIndicator } from './TypingIndicator';
export { ErrorBanner } from './ErrorBanner';
export { ChatErrorBoundary } from './ChatErrorBoundary';

// Rich Cards (Phase 6)
export { BillSummaryCard } from './BillSummaryCard';
export { PaymentCard } from './PaymentCard';
export { OtpVerificationCard } from './OtpVerificationCard';
export { HandoffCard } from './HandoffCard';
export { DemoCallCard } from './DemoCallCard';
export { MessageCounter } from './MessageCounter';
export { DemoPackCTA } from './DemoPackCTA';
export { LimitReachedCard } from './LimitReachedCard';
export { PackExpiredCard } from './PackExpiredCard';
export { ActionTicketCard } from './ActionTicketCard';
export { PostCallSummaryCard } from './PostCallSummaryCard';
export { RechargeCTACard } from './RechargeCTACard';

// Integration Setup Cards
export { ProviderSelectorCard } from './ProviderSelectorCard';
export type { ProviderInfo, ProviderSelectorCardProps } from './ProviderSelectorCard';
export { ApiKeyInputCard } from './ApiKeyInputCard';
export type { DetectionResult, TestResult, ApiKeyInputCardProps } from './ApiKeyInputCard';
export { ConnectionStatusCard } from './ConnectionStatusCard';
export type { ConnectionStatusCardProps } from './ConnectionStatusCard';
export { ConnectionErrorCard } from './ConnectionErrorCard';
export type { ConnectionErrorCardProps } from './ConnectionErrorCard';
export { IntegrationSummaryCard } from './IntegrationSummaryCard';
export type { ConnectedIntegration, SkippedIntegration, IntegrationSummaryCardProps } from './IntegrationSummaryCard';
export { IndustrySuggestionCard } from './IndustrySuggestionCard';
export type { IndustrySuggestion, IndustrySuggestionCardProps } from './IndustrySuggestionCard';
