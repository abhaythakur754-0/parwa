/**
 * JARVIS Awareness Engine Types (Week 2 - Phase 1)
 *
 * Type definitions for the Awareness Engine v1
 * Covers: Event listeners, Activity trackers, Health monitors, Alert dispatcher
 */

// ── Event Types ─────────────────────────────────────────────────────

export type AwarenessEventType =
  // Ticket events
  | 'ticket_created'
  | 'ticket_updated'
  | 'ticket_assigned'
  | 'ticket_closed'
  | 'ticket_escalated'
  | 'ticket_reopened'
  | 'ticket_priority_changed'
  | 'ticket_sla_breach'
  | 'ticket_sla_warning'
  // Customer events
  | 'customer_message_received'
  | 'customer_sentiment_changed'
  | 'customer_churn_risk'
  | 'customer_resolved'
  // System events
  | 'system_health_degraded'
  | 'system_health_recovered'
  | 'agent_performance_drop'
  | 'queue_buildup_detected'
  | 'high_volume_spike'
  // Alert events
  | 'alert_triggered'
  | 'alert_acknowledged'
  | 'alert_resolved'
  | 'alert_escalated';

export type AlertSeverity = 'critical' | 'warning' | 'info' | 'opportunity';

export type AlertChannel = 'dashboard' | 'email' | 'slack' | 'sms' | 'webhook';

export type HealthStatus = 'healthy' | 'degraded' | 'critical' | 'unknown';

export type SentimentLabel = 'positive' | 'neutral' | 'negative' | 'mixed';

export type MetricAggregation = 'sum' | 'avg' | 'min' | 'max' | 'count' | 'p95' | 'p99';

// ── Event Interfaces ────────────────────────────────────────────────

export interface AwarenessEvent {
  id: string;
  type: AwarenessEventType;
  timestamp: Date;
  tenant_id: string;
  variant: 'mini_parwa' | 'parwa' | 'parwa_high';
  source: string;
  payload: Record<string, unknown>;
  metadata?: EventMetadata;
}

export interface EventMetadata {
  correlation_id?: string;
  causation_id?: string;
  user_id?: string;
  session_id?: string;
  agent_id?: string;
  channel?: string;
  [key: string]: unknown;
}

// ── Alert Interfaces ────────────────────────────────────────────────

export interface Alert {
  id: string;
  tenant_id: string;
  type: AwarenessEventType;
  severity: AlertSeverity;
  title: string;
  message: string;
  source: string;
  status: 'active' | 'acknowledged' | 'resolved';
  created_at: Date;
  acknowledged_at?: Date;
  resolved_at?: Date;
  acknowledged_by?: string;
  channels: AlertChannel[];
  metadata: Record<string, unknown>;
  actions?: AlertAction[];
}

export interface AlertAction {
  id: string;
  label: string;
  type: 'execute' | 'draft';
  command?: string;
  endpoint?: string;
}

export interface AlertRule {
  id: string;
  tenant_id: string;
  name: string;
  description: string;
  event_types: AwarenessEventType[];
  conditions: AlertCondition[];
  severity: AlertSeverity;
  channels: AlertChannel[];
  enabled: boolean;
  cooldown_minutes: number;
  created_at: Date;
  updated_at: Date;
}

export interface AlertCondition {
  field: string;
  operator: 'eq' | 'neq' | 'gt' | 'gte' | 'lt' | 'lte' | 'contains' | 'matches';
  value: unknown;
}

// ── Health Monitor Interfaces ────────────────────────────────────────

export interface SystemHealth {
  tenant_id: string;
  overall_status: HealthStatus;
  components: ComponentHealth[];
  checked_at: Date;
  uptime_percentage: number;
  incident_count_24h: number;
}

export interface ComponentHealth {
  name: string;
  status: HealthStatus;
  latency_ms?: number;
  error_rate?: number;
  last_check: Date;
  message?: string;
  details?: Record<string, unknown>;
}

export interface HealthCheckResult {
  component: string;
  status: HealthStatus;
  latency_ms: number;
  message?: string;
  details?: Record<string, unknown>;
}

export interface HealthThreshold {
  component: string;
  latency_warning_ms: number;
  latency_critical_ms: number;
  error_rate_warning_pct: number;
  error_rate_critical_pct: number;
}

// ── Activity Tracking Interfaces ─────────────────────────────────────

export interface CustomerActivity {
  id: string;
  tenant_id: string;
  customer_id: string;
  activity_type: string;
  channel: string;
  timestamp: Date;
  sentiment?: SentimentAnalysis;
  ticket_id?: string;
  agent_id?: string;
  metadata: Record<string, unknown>;
}

export interface ActivityPattern {
  customer_id: string;
  pattern_type: 'peak_hours' | 'frequent_issues' | 'sentiment_trend' | 'channel_preference';
  pattern_data: Record<string, unknown>;
  confidence: number;
  detected_at: Date;
}

export interface CustomerActivitySummary {
  customer_id: string;
  total_interactions: number;
  last_24h: number;
  last_7d: number;
  last_30d: number;
  primary_channel: string;
  avg_sentiment: number;
  sentiment_trend: 'improving' | 'stable' | 'declining';
  top_issues: string[];
  churn_risk_score: number;
}

// ── Sentiment Analysis Interfaces ─────────────────────────────────────

export interface SentimentAnalysis {
  label: SentimentLabel;
  score: number; // -1 to 1
  confidence: number; // 0 to 1
  aspects?: SentimentAspect[];
  detected_at: Date;
}

export interface SentimentAspect {
  name: string;
  sentiment: SentimentLabel;
  score: number;
  keywords: string[];
}

export interface SentimentTrend {
  tenant_id: string;
  period: 'hour' | 'day' | 'week' | 'month';
  start_date: Date;
  end_date: Date;
  avg_score: number;
  trend_direction: 'up' | 'down' | 'stable';
  sample_size: number;
  breakdown: SentimentBreakdown[];
}

export interface SentimentBreakdown {
  label: SentimentLabel;
  count: number;
  percentage: number;
}

// ── Metrics & Aggregation Interfaces ─────────────────────────────────

export interface PerformanceMetric {
  id: string;
  tenant_id: string;
  metric_name: string;
  metric_type: 'counter' | 'gauge' | 'histogram' | 'timer';
  value: number;
  unit: string;
  tags: Record<string, string>;
  timestamp: Date;
  variant: 'mini_parwa' | 'parwa' | 'parwa_high';
}

export interface AggregatedMetric {
  tenant_id: string;
  metric_name: string;
  aggregation: MetricAggregation;
  value: number;
  period: 'minute' | 'hour' | 'day' | 'week';
  period_start: Date;
  period_end: Date;
  sample_count: number;
  tags: Record<string, string>;
}

export interface MetricDefinition {
  name: string;
  display_name: string;
  description: string;
  type: 'counter' | 'gauge' | 'histogram' | 'timer';
  unit: string;
  aggregation_methods: MetricAggregation[];
  tags: string[];
  variant_limits: Record<string, number | null>;
}

// ── Event Capture Interfaces ─────────────────────────────────────────

export interface EventCaptureConfig {
  tenant_id: string;
  enabled_sources: string[];
  buffer_size: number;
  flush_interval_ms: number;
  retry_attempts: number;
  dead_letter_enabled: boolean;
}

export interface EventBuffer {
  events: AwarenessEvent[];
  size: number;
  oldest_timestamp?: Date;
  newest_timestamp?: Date;
}

export interface EventSubscription {
  id: string;
  tenant_id: string;
  event_types: AwarenessEventType[];
  callback_url: string;
  secret?: string;
  enabled: boolean;
  created_at: Date;
}

// ── Listener Configurations ──────────────────────────────────────────

export interface TicketEventListenerConfig {
  tenant_id: string;
  enabled_events: AwarenessEventType[];
  sla_warning_threshold_pct: number;
  sla_breach_threshold_pct: number;
  high_volume_threshold: number;
  queue_buildup_threshold: number;
  variant: 'mini_parwa' | 'parwa' | 'parwa_high';
}

export interface CustomerTrackerConfig {
  tenant_id: string;
  track_sentiment: boolean;
  track_patterns: boolean;
  sentiment_threshold_negative: number;
  churn_risk_threshold: number;
  history_limit: number;
  variant: 'mini_parwa' | 'parwa' | 'parwa_high';
}

// ── Awareness Engine State ───────────────────────────────────────────

export interface AwarenessState {
  tenant_id: string;
  variant: 'mini_parwa' | 'parwa' | 'parwa_high';
  active_alerts: Alert[];
  health_status: SystemHealth;
  recent_events: AwarenessEvent[];
  metrics_cache: Map<string, AggregatedMetric>;
  last_updated: Date;
}

export interface AwarenessCapabilities {
  ticket_monitoring_level: 'basic' | 'standard' | 'advanced';
  sentiment_tracking_level: 'limited' | 'full' | 'full_with_trends';
  team_activity_monitoring: 'basic' | 'standard' | 'advanced';
  system_alerts: 'critical_only' | 'all' | 'all_with_predictive';
  pattern_detection: 'none' | 'basic' | 'advanced';
  real_time_refresh_ms: number;
  history_retention_days: number;
}

// ── API Request/Response Types ───────────────────────────────────────

export interface GetAlertsRequest {
  tenant_id: string;
  status?: 'active' | 'acknowledged' | 'resolved';
  severity?: AlertSeverity;
  type?: AwarenessEventType;
  limit?: number;
  offset?: number;
}

export interface GetAlertsResponse {
  alerts: Alert[];
  total: number;
  limit: number;
  offset: number;
}

export interface AcknowledgeAlertRequest {
  alert_id: string;
  acknowledged_by: string;
  notes?: string;
}

export interface GetHealthResponse {
  health: SystemHealth;
  recommendations?: string[];
}

export interface GetActivitySummaryRequest {
  tenant_id: string;
  customer_id?: string;
  start_date?: Date;
  end_date?: Date;
  limit?: number;
}

export interface GetActivitySummaryResponse {
  activities: CustomerActivitySummary[];
  total: number;
}

export interface GetSentimentTrendRequest {
  tenant_id: string;
  period: 'hour' | 'day' | 'week' | 'month';
  start_date?: Date;
  end_date?: Date;
}

export interface GetMetricsRequest {
  tenant_id: string;
  metric_names?: string[];
  aggregation?: MetricAggregation;
  period?: 'minute' | 'hour' | 'day';
  start_date?: Date;
  end_date?: Date;
  tags?: Record<string, string>;
}

export interface GetMetricsResponse {
  metrics: AggregatedMetric[];
  period: string;
}

// ── Variant-specific capabilities mapping ────────────────────────────

export const VARIANT_AWARENESS_CAPABILITIES: Record<string, AwarenessCapabilities> = {
  mini_parwa: {
    ticket_monitoring_level: 'basic',
    sentiment_tracking_level: 'limited',
    team_activity_monitoring: 'basic',
    system_alerts: 'critical_only',
    pattern_detection: 'none',
    real_time_refresh_ms: 5000,
    history_retention_days: 1,
  },
  parwa: {
    ticket_monitoring_level: 'standard',
    sentiment_tracking_level: 'full',
    team_activity_monitoring: 'standard',
    system_alerts: 'all',
    pattern_detection: 'basic',
    real_time_refresh_ms: 2000,
    history_retention_days: 7,
  },
  parwa_high: {
    ticket_monitoring_level: 'advanced',
    sentiment_tracking_level: 'full_with_trends',
    team_activity_monitoring: 'advanced',
    system_alerts: 'all_with_predictive',
    pattern_detection: 'advanced',
    real_time_refresh_ms: 1000,
    history_retention_days: 30,
  },
};
