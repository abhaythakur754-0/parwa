/**
 * JARVIS Pattern Detection Types - Week 8 (Phase 2)
 *
 * Type definitions for the Pattern Detection system.
 * Identifies patterns in user behavior, ticket trends, and operational metrics.
 */

import type { Variant } from '@/types/variant';
import type { IntentAction } from '@/types/command';

// ── Pattern Types ─────────────────────────────────────────────────────

export type PatternCategory =
  | 'user_behavior'      // Individual user behavior patterns
  | 'team_behavior'      // Team-level behavior patterns
  | 'ticket_trends'      // Ticket volume, type, and status trends
  | 'sla_patterns'       // SLA performance patterns
  | 'escalation_patterns' // Escalation frequency and reasons
  | 'customer_sentiment'  // Customer sentiment patterns
  | 'time_patterns'      // Time-based patterns (hourly, daily, weekly)
  | 'entity_correlation'; // Entity relationship patterns

export type PatternType =
  | 'sequential'         // A then B patterns
  | 'temporal'           // Time-based patterns
  | 'frequency'          // Frequency/count patterns
  | 'correlation'        // Correlation between entities/events
  | 'anomaly'            // Deviation from normal patterns
  | 'seasonal'           // Recurring seasonal patterns
  | 'trend';             // Upward/downward trends

export type PatternStatus = 'active' | 'inactive' | 'archived' | 'invalidated';

export type PatternConfidence = 'high' | 'medium' | 'low';

// ── Base Pattern ───────────────────────────────────────────────────────

export interface Pattern {
  id: string;
  tenant_id: string;
  category: PatternCategory;
  type: PatternType;
  name: string;
  description: string;
  status: PatternStatus;
  confidence: PatternConfidence;
  confidence_score: number;        // 0-1 numeric confidence
  support: number;                 // Number of supporting instances
  first_detected: Date;
  last_observed: Date;
  occurrences: number;
  pattern_data: PatternData;
  metadata: PatternMetadata;
  predictions: PatternPrediction[];
  related_patterns: string[];      // IDs of related patterns
  tags: string[];
}

export interface PatternData {
  trigger_conditions: PatternCondition[];
  pattern_expression: PatternExpression;
  statistical_significance: number;
  sample_size: number;
  false_positive_rate: number;
}

export interface PatternCondition {
  dimension: string;               // e.g., 'time_of_day', 'ticket_type'
  operator: 'equals' | 'not_equals' | 'greater_than' | 'less_than' | 'contains' | 'matches' | 'in';
  value: unknown;
  weight: number;                  // Importance of this condition
}

export interface PatternExpression {
  type: 'rule' | 'statistical' | 'ml_model';
  rule_definition?: RuleDefinition;
  statistical_model?: StatisticalModel;
  model_reference?: string;        // Reference to trained ML model
}

export interface RuleDefinition {
  if: PatternCondition[];
  then: PatternConsequence;
  probability: number;
}

export interface PatternConsequence {
  action: string;
  params?: Record<string, unknown>;
  expected_outcome: string;
}

export interface StatisticalModel {
  mean: number;
  std_dev: number;
  percentile_95?: number;
  trend_direction?: 'increasing' | 'decreasing' | 'stable';
}

export interface PatternMetadata {
  detection_method: 'automatic' | 'manual' | 'ml';
  verified_by?: string;
  verified_at?: Date;
  annotations?: string[];
  source_data_reference?: string;
  [key: string]: unknown;
}

// ── Pattern Predictions ────────────────────────────────────────────────

export interface PatternPrediction {
  id: string;
  pattern_id: string;
  predicted_event: string;
  predicted_value?: number;
  probability: number;
  time_horizon: TimeHorizon;
  conditions: PatternCondition[];
  created_at: Date;
  expires_at?: Date;
  actualized?: boolean;
  actualized_at?: Date;
}

export interface TimeHorizon {
  type: 'immediate' | 'short_term' | 'medium_term' | 'long_term';
  duration_minutes?: number;
  target_time?: Date;
}

// ── Pattern Instance ───────────────────────────────────────────────────

export interface PatternInstance {
  id: string;
  pattern_id: string;
  observed_at: Date;
  context: Record<string, unknown>;
  entities_involved: PatternEntity[];
  outcome?: string;
  matched_conditions: PatternCondition[];
  confidence_at_detection: number;
}

export interface PatternEntity {
  type: 'ticket' | 'customer' | 'agent' | 'team' | 'product' | 'order';
  id: string;
  name?: string;
  role: 'primary' | 'secondary' | 'affected';
}

// ── Anomaly Detection ──────────────────────────────────────────────────

export interface Anomaly {
  id: string;
  tenant_id: string;
  type: 'spike' | 'drop' | 'outlier' | 'drift' | 'change_point';
  severity: 'critical' | 'warning' | 'info';
  metric: string;
  expected_value: number;
  actual_value: number;
  deviation_percent: number;
  detected_at: Date;
  context: Record<string, unknown>;
  pattern_id?: string;             // If linked to a pattern
  resolved: boolean;
  resolved_at?: Date;
  resolution_note?: string;
}

export interface AnomalyThreshold {
  metric: string;
  warning_threshold: number;       // Percent deviation for warning
  critical_threshold: number;      // Percent deviation for critical
  min_sample_size: number;
  baseline_window_hours: number;
}

// ── Trend Analysis ─────────────────────────────────────────────────────

export interface Trend {
  id: string;
  metric: string;
  direction: 'increasing' | 'decreasing' | 'stable';
  magnitude: number;               // Rate of change
  start_time: Date;
  end_time?: Date;
  data_points: TrendDataPoint[];
  pattern_id?: string;
  forecast?: TrendForecast;
}

export interface TrendDataPoint {
  timestamp: Date;
  value: number;
  expected?: number;
  anomaly?: boolean;
}

export interface TrendForecast {
  horizon_hours: number;
  predicted_values: Array<{
    timestamp: Date;
    value: number;
    confidence_interval: [number, number];
  }>;
  confidence: number;
}

// ── Configuration ───────────────────────────────────────────────────────

export interface PatternDetectionConfig {
  tenant_id: string;
  variant: Variant;
  enabled: boolean;
  detection_interval_minutes: number;
  min_occurrences_for_pattern: number;
  min_confidence_threshold: number;
  anomaly_detection_enabled: boolean;
  trend_analysis_enabled: boolean;
  pattern_retention_days: number;
  categories_enabled: PatternCategory[];
  thresholds: AnomalyThreshold[];
  alert_on_anomaly: boolean;
  alert_on_pattern: boolean;
}

export const DEFAULT_PATTERN_DETECTION_CONFIG: Omit<PatternDetectionConfig, 'tenant_id' | 'variant'> = {
  enabled: true,
  detection_interval_minutes: 5,
  min_occurrences_for_pattern: 3,
  min_confidence_threshold: 0.6,
  anomaly_detection_enabled: true,
  trend_analysis_enabled: true,
  pattern_retention_days: 30,
  categories_enabled: [
    'user_behavior',
    'team_behavior',
    'ticket_trends',
    'sla_patterns',
    'escalation_patterns',
    'time_patterns',
  ],
  thresholds: [
    { metric: 'ticket_volume', warning_threshold: 30, critical_threshold: 50, min_sample_size: 10, baseline_window_hours: 24 },
    { metric: 'sla_breach_rate', warning_threshold: 20, critical_threshold: 40, min_sample_size: 5, baseline_window_hours: 24 },
    { metric: 'escalation_rate', warning_threshold: 25, critical_threshold: 50, min_sample_size: 5, baseline_window_hours: 24 },
    { metric: 'response_time', warning_threshold: 40, critical_threshold: 60, min_sample_size: 10, baseline_window_hours: 24 },
  ],
  alert_on_anomaly: true,
  alert_on_pattern: false,
};

// ── Variant Limits ──────────────────────────────────────────────────────

export interface PatternDetectionVariantLimits {
  enabled: boolean;
  max_patterns: number;
  ml_detection: boolean;
  predictive_forecasting: boolean;
  anomaly_detection: boolean;
  trend_analysis: boolean;
  custom_thresholds: boolean;
  max_custom_thresholds: number;
}

export const PATTERN_DETECTION_VARIANT_LIMITS: Record<Variant, PatternDetectionVariantLimits> = {
  mini_parwa: {
    enabled: true,
    max_patterns: 10,
    ml_detection: false,
    predictive_forecasting: false,
    anomaly_detection: true,
    trend_analysis: false,
    custom_thresholds: false,
    max_custom_thresholds: 0,
  },
  parwa: {
    enabled: true,
    max_patterns: 100,
    ml_detection: false,
    predictive_forecasting: true,
    anomaly_detection: true,
    trend_analysis: true,
    custom_thresholds: true,
    max_custom_thresholds: 5,
  },
  parwa_high: {
    enabled: true,
    max_patterns: 1000,
    ml_detection: true,
    predictive_forecasting: true,
    anomaly_detection: true,
    trend_analysis: true,
    custom_thresholds: true,
    max_custom_thresholds: 20,
  },
};

// ── Statistics ──────────────────────────────────────────────────────────

export interface PatternDetectionStats {
  total_patterns_detected: number;
  patterns_by_category: Record<PatternCategory, number>;
  patterns_by_type: Record<PatternType, number>;
  active_patterns: number;
  pattern_predictions_made: number;
  predictions_accuracy: number;
  anomalies_detected: number;
  anomalies_by_severity: Record<'critical' | 'warning' | 'info', number>;
  trends_tracked: number;
  detection_runs: number;
  last_detection_time?: Date;
}

// ── Events ──────────────────────────────────────────────────────────────

export type PatternEventType =
  | 'pattern_detected'
  | 'pattern_updated'
  | 'pattern_invalidated'
  | 'prediction_made'
  | 'prediction_actualized'
  | 'anomaly_detected'
  | 'anomaly_resolved'
  | 'trend_detected'
  | 'trend_changed';

export interface PatternEvent {
  type: PatternEventType;
  pattern_id?: string;
  anomaly_id?: string;
  trend_id?: string;
  user_id?: string;
  tenant_id: string;
  timestamp: Date;
  metadata?: Record<string, unknown>;
}

// ── Request/Response Types ──────────────────────────────────────────────

export interface DetectPatternsRequest {
  tenant_id: string;
  user_id?: string;
  category?: PatternCategory;
  time_range?: {
    start: Date;
    end: Date;
  };
  min_occurrences?: number;
}

export interface DetectPatternsResponse {
  patterns: Pattern[];
  detection_time_ms: number;
  data_points_analyzed: number;
}

export interface GetPatternsRequest {
  tenant_id: string;
  user_id?: string;
  categories?: PatternCategory[];
  types?: PatternType[];
  status?: PatternStatus;
  min_confidence?: number;
  limit?: number;
  offset?: number;
}

export interface GetPatternsResponse {
  patterns: Pattern[];
  total: number;
  has_more: boolean;
}
