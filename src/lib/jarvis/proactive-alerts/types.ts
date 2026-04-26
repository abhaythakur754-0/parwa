/**
 * JARVIS Proactive Alerts Types - Week 6 (Phase 2)
 *
 * Type definitions for the Proactive Alerts system.
 * Provides predictive alerting, escalation detection, and proactive monitoring.
 */

import type { Variant } from '@/types/variant';
import type { AlertSeverity } from '@/types/awareness';

// ── Proactive Alert Types ─────────────────────────────────────────────

export type ProactiveAlertType =
  | 'sla_breach_prediction'
  | 'sla_breach_imminent'
  | 'escalation_needed'
  | 'escalation_overdue'
  | 'sentiment_declining'
  | 'sentiment_critical'
  | 'response_time_slow'
  | 'queue_overload'
  | 'agent_overload'
  | 'customer_at_risk'
  | 'ticket_stale'
  | 'followup_overdue';

export type AlertUrgency = 'immediate' | 'urgent' | 'high' | 'medium' | 'low';

export type AlertState = 
  | 'pending'
  | 'notified'
  | 'acknowledged'
  | 'action_taken'
  | 'resolved'
  | 'escalated'
  | 'expired';

// ── Proactive Alert ───────────────────────────────────────────────────

export interface ProactiveAlert {
  id: string;
  tenant_id: string;
  type: ProactiveAlertType;
  severity: AlertSeverity;
  urgency: AlertUrgency;
  state: AlertState;
  
  // Target information
  target_type: 'ticket' | 'customer' | 'agent' | 'queue' | 'system';
  target_id: string;
  target_name?: string;
  
  // Alert details
  title: string;
  message: string;
  prediction_confidence?: number;
  predicted_time?: Date;
  time_remaining_ms?: number;
  
  // Metrics that triggered the alert
  trigger_metrics: AlertMetric[];
  threshold_values: Record<string, { current: number; threshold: number }>;
  
  // Recommended actions
  recommended_actions: RecommendedAction[];
  
  // Tracking
  created_at: Date;
  updated_at: Date;
  expires_at?: Date;
  acknowledged_at?: Date;
  acknowledged_by?: string;
  resolved_at?: Date;
  resolved_by?: string;
  resolution_note?: string;
  
  // Escalation
  escalation_level: number;
  escalation_chain?: EscalationLevel[];
  
  // Metadata
  metadata: Record<string, unknown>;
}

export interface AlertMetric {
  name: string;
  value: number;
  unit: string;
  trend?: 'increasing' | 'decreasing' | 'stable';
  change_pct?: number;
}

export interface RecommendedAction {
  id: string;
  priority: number;
  type: 'command' | 'navigation' | 'notification' | 'assignment';
  label: string;
  description: string;
  command?: string;
  endpoint?: string;
  auto_executable: boolean;
  estimated_impact: 'high' | 'medium' | 'low';
}

// ── SLA Monitoring Types ──────────────────────────────────────────────

export interface SLAMonitorConfig {
  tenant_id: string;
  variant: Variant;
  warning_threshold_pct: number;  // Alert when this % of SLA time remains
  critical_threshold_pct: number;
  prediction_enabled: boolean;
  prediction_horizon_hours: number;
  check_interval_seconds: number;
}

export interface SLATicketStatus {
  ticket_id: string;
  sla_type: 'first_response' | 'resolution' | 'next_response';
  sla_deadline: Date;
  created_at: Date;
  status: 'on_track' | 'warning' | 'critical' | 'breached';
  time_remaining_ms: number;
  pct_remaining: number;
  predicted_breach?: boolean;
  predicted_breach_time?: Date;
  at_risk_reasons?: string[];
}

export interface SLABreachPrediction {
  ticket_id: string;
  sla_type: 'first_response' | 'resolution' | 'next_response';
  predicted_breach_time: Date;
  confidence: number;
  contributing_factors: string[];
  recommended_interventions: string[];
}

// ── Escalation Types ──────────────────────────────────────────────────

export interface EscalationRule {
  id: string;
  tenant_id: string;
  name: string;
  description: string;
  
  // Trigger conditions
  conditions: EscalationCondition[];
  
  // Escalation chain
  levels: EscalationLevel[];
  
  // Timing
  auto_escalate_after_minutes: number;
  max_escalation_level: number;
  
  // Settings
  enabled: boolean;
  priority: number;
  created_at: Date;
  updated_at: Date;
}

export interface EscalationCondition {
  type: 'time_in_status' | 'sentiment_score' | 'priority_level' | 'customer_tier' | 'ticket_count';
  operator: 'gt' | 'gte' | 'lt' | 'lte' | 'eq' | 'neq';
  value: unknown;
}

export interface EscalationLevel {
  level: number;
  notify_roles: string[];
  notify_user_ids?: string[];
  notify_channels: ('dashboard' | 'email' | 'sms' | 'slack')[];
  time_limit_minutes?: number;
  auto_actions?: AutoEscalationAction[];
}

export interface AutoEscalationAction {
  type: 'reassign' | 'add_watcher' | 'change_priority' | 'add_tag';
  params: Record<string, unknown>;
}

export interface EscalationStatus {
  ticket_id: string;
  current_level: number;
  escalated_at?: Date;
  escalated_to?: string[];
  next_escalation_at?: Date;
  escalation_history: EscalationEvent[];
}

export interface EscalationEvent {
  level: number;
  from_user?: string;
  to_users: string[];
  reason: string;
  timestamp: Date;
}

// ── Sentiment Monitoring Types ────────────────────────────────────────

export interface SentimentMonitorConfig {
  tenant_id: string;
  variant: Variant;
  negative_threshold: number;      // Alert when sentiment < this
  declining_threshold: number;     // Alert when trend declining this much
  track_trends: boolean;
  trend_window_messages: number;
  check_interval_seconds: number;
}

export interface SentimentStatus {
  customer_id: string;
  ticket_id?: string;
  current_sentiment: SentimentScore;
  sentiment_trend: 'improving' | 'stable' | 'declining' | 'critical';
  trend_strength: number;
  messages_analyzed: number;
  last_analyzed_at: Date;
  alert_triggered: boolean;
}

export interface SentimentScore {
  label: 'positive' | 'neutral' | 'negative' | 'mixed';
  score: number;  // -1 to 1
  confidence: number;
  aspects?: SentimentAspect[];
}

export interface SentimentAspect {
  name: string;
  sentiment: 'positive' | 'neutral' | 'negative';
  score: number;
  keywords: string[];
}

export interface SentimentAlert {
  customer_id: string;
  ticket_id?: string;
  previous_sentiment?: SentimentScore;
  current_sentiment: SentimentScore;
  change_type: 'rapid_decline' | 'gradual_decline' | 'critical_level' | 'negative_persist';
  messages_in_window: number;
  recommended_actions: string[];
}

// ── Proactive Alerts Configuration ────────────────────────────────────

export interface ProactiveAlertsConfig {
  enabled: boolean;
  tenant_id: string;
  variant: Variant;
  
  sla_monitoring: SLAMonitorConfig;
  escalation: {
    enabled: boolean;
    auto_escalate: boolean;
    max_levels: number;
  };
  sentiment_monitoring: SentimentMonitorConfig;
  
  notification_channels: ('dashboard' | 'email' | 'slack' | 'sms')[];
  alert_cooldown_minutes: number;
  max_active_alerts: number;
}

export const DEFAULT_PROACTIVE_ALERTS_CONFIG: Omit<ProactiveAlertsConfig, 'tenant_id'> & { tenant_id: string } = {
  enabled: true,
  tenant_id: 'default',
  variant: 'parwa' as Variant,
  
  sla_monitoring: {
    tenant_id: 'default',
    variant: 'parwa' as Variant,
    warning_threshold_pct: 25,
    critical_threshold_pct: 10,
    prediction_enabled: true,
    prediction_horizon_hours: 2,
    check_interval_seconds: 60,
  },
  
  escalation: {
    enabled: true,
    auto_escalate: true,
    max_levels: 3,
  },
  
  sentiment_monitoring: {
    tenant_id: 'default',
    variant: 'parwa' as Variant,
    negative_threshold: -0.3,
    declining_threshold: -0.2,
    track_trends: true,
    trend_window_messages: 5,
    check_interval_seconds: 120,
  },
  
  notification_channels: ['dashboard', 'email'],
  alert_cooldown_minutes: 15,
  max_active_alerts: 100,
};

// ── Variant Limits ────────────────────────────────────────────────────

export const PROACTIVE_ALERTS_VARIANT_LIMITS: Record<Variant, {
  sla_prediction: boolean;
  auto_escalation: boolean;
  sentiment_tracking: boolean;
  max_alerts_per_hour: number;
  max_escalation_levels: number;
}> = {
  mini_parwa: {
    sla_prediction: false,
    auto_escalation: false,
    sentiment_tracking: false,
    max_alerts_per_hour: 10,
    max_escalation_levels: 1,
  },
  parwa: {
    sla_prediction: true,
    auto_escalation: true,
    sentiment_tracking: true,
    max_alerts_per_hour: 50,
    max_escalation_levels: 3,
  },
  parwa_high: {
    sla_prediction: true,
    auto_escalation: true,
    sentiment_tracking: true,
    max_alerts_per_hour: -1, // unlimited
    max_escalation_levels: 5,
  },
};

// ── Statistics ────────────────────────────────────────────────────────

export interface ProactiveAlertsStats {
  total_alerts_generated: number;
  alerts_by_type: Record<ProactiveAlertType, number>;
  alerts_by_severity: Record<AlertSeverity, number>;
  avg_resolution_time_ms: number;
  avg_acknowledgement_time_ms: number;
  
  sla_stats: {
    breaches_prevented: number;
    predictions_made: number;
    prediction_accuracy: number;
  };
  
  escalation_stats: {
    total_escalations: number;
    auto_escalations: number;
    avg_time_to_escalate_ms: number;
  };
  
  sentiment_stats: {
    alerts_triggered: number;
    avg_sentiment_score: number;
    declining_customers_detected: number;
  };
}

// ── Event Types ───────────────────────────────────────────────────────

export type ProactiveAlertEventType =
  | 'proactive_alert_created'
  | 'proactive_alert_acknowledged'
  | 'proactive_alert_resolved'
  | 'proactive_alert_escalated'
  | 'proactive_alert_expired'
  | 'sla_prediction_made'
  | 'escalation_triggered'
  | 'sentiment_alert_triggered';

export interface ProactiveAlertEvent {
  type: ProactiveAlertEventType;
  alert_id?: string;
  tenant_id: string;
  timestamp: Date;
  payload: Record<string, unknown>;
}
