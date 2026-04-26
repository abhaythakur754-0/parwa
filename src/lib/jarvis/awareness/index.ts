/**
 * JARVIS Awareness Engine - Week 2 (Phase 1)
 *
 * Complete implementation of the JARVIS Awareness Engine v1.
 * This module provides real-time monitoring, alerting, and awareness capabilities.
 *
 * Components:
 * - Ticket Event Listeners: Monitor ticket lifecycle events
 * - Customer Activity Trackers: Track customer interactions and patterns
 * - System Health Monitors: Monitor system component health
 * - Alert Dispatcher: Multi-channel alert routing and management
 * - Event Capture: Real-time event buffering and delivery
 * - Data Aggregator: Historical data aggregation for analytics
 * - Sentiment Pipeline: Customer sentiment analysis
 * - Metrics Collector: Performance metrics collection
 */

// Main Engine
export { AwarenessEngine, createAwarenessEngine, getAwarenessEngine, shutdownAwarenessEngine } from './awareness-engine';
export type { AwarenessEngineConfig } from './awareness-engine';

// Components
export { TicketEventListener, createTicketListener, DEFAULT_TICKET_LISTENER_CONFIG } from './ticket-event-listener';
export type { TicketEventData, EventEmitter as TicketEventEmitter } from './ticket-event-listener';

export { CustomerActivityTracker, createActivityTracker, DEFAULT_ACTIVITY_TRACKER_CONFIG } from './activity-tracker';
export type { CustomerActivityData } from './activity-tracker';

export { SystemHealthMonitor, createHealthMonitor, DEFAULT_CHECK_INTERVALS } from './health-monitor';
export type { ComponentDefinition, HealthCheckFunction } from './health-monitor';

export { AlertDispatcher, createAlertDispatcher, DEFAULT_ALERT_DISPATCHER_CONFIG, DEFAULT_ALERT_RULES } from './alert-dispatcher';
export type { AlertChannelHandler, AlertDispatcherConfig } from './alert-dispatcher';

export { EventCapture, createEventCapture, DEFAULT_EVENT_CAPTURE_CONFIG } from './event-capture';
export type { EventCallback, EventFilter } from './event-capture';

export { DataAggregator, createDataAggregator, DEFAULT_AGGREGATOR_CONFIG } from './data-aggregator';
export type { AggregatorConfig, TimeSeriesPoint } from './data-aggregator';

export { SentimentPipeline, createSentimentPipeline, DEFAULT_SENTIMENT_PIPELINE_CONFIG } from './sentiment-pipeline';
export type { SentimentPipelineConfig, SentimentInput } from './sentiment-pipeline';

export { MetricsCollector, createMetricsCollector, DEFAULT_METRICS_COLLECTOR_CONFIG, STANDARD_METRICS } from './metrics-collector';
export type { MetricsCollectorConfig, MetricRecord } from './metrics-collector';

// Re-export types
export type {
  AwarenessEvent,
  AwarenessEventType,
  Alert,
  AlertSeverity,
  AlertChannel,
  AlertRule,
  AlertCondition,
  AlertAction,
  HealthStatus,
  ComponentHealth,
  SystemHealth,
  CustomerActivity,
  CustomerActivitySummary,
  ActivityPattern,
  SentimentAnalysis,
  SentimentLabel,
  SentimentTrend,
  PerformanceMetric,
  AggregatedMetric,
  MetricAggregation,
  EventCaptureConfig,
  AwarenessState,
  AwarenessCapabilities,
  VARIANT_AWARENESS_CAPABILITIES,
} from '@/types/awareness';
