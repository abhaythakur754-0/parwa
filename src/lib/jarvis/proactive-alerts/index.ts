/**
 * JARVIS Proactive Alerts - Week 6 (Phase 2)
 *
 * Provides proactive alerting capabilities for JARVIS.
 * Includes SLA monitoring, escalation management, and sentiment tracking.
 */

// Types
export type {
  ProactiveAlertType,
  AlertUrgency,
  AlertState,
  ProactiveAlert,
  AlertMetric,
  RecommendedAction,
  SLAMonitorConfig,
  SLATicketStatus,
  SLABreachPrediction,
  EscalationRule,
  EscalationCondition,
  EscalationLevel,
  AutoEscalationAction,
  EscalationStatus,
  EscalationEvent,
  SentimentMonitorConfig,
  SentimentStatus,
  SentimentScore,
  SentimentAspect,
  SentimentAlert,
  ProactiveAlertsConfig,
  ProactiveAlertsStats,
  ProactiveAlertEventType,
  ProactiveAlertEvent,
} from './types';

export {
  DEFAULT_PROACTIVE_ALERTS_CONFIG,
  PROACTIVE_ALERTS_VARIANT_LIMITS,
} from './types';

// Manager
export {
  ProactiveAlertManager,
  createProactiveAlertManager,
  getProactiveAlertManager,
  shutdownProactiveAlertManager,
  shutdownAllProactiveAlertManagers,
} from './proactive-alert-manager';
