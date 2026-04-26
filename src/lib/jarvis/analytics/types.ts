/**
 * JARVIS Advanced Analytics Types - Week 10 (Phase 3)
 *
 * Type definitions for predictive analytics, forecasting, and resource planning.
 */

import type { Variant } from '@/types/variant';

// ── Analytics Configuration ───────────────────────────────────────────

export interface AnalyticsConfig {
  /** Tenant ID */
  tenant_id: string;
  /** Variant for capability gating */
  variant: Variant;
  /** Enable volume prediction */
  volume_prediction_enabled: boolean;
  /** Enable churn prediction */
  churn_prediction_enabled: boolean;
  /** Enable performance forecasting */
  performance_forecast_enabled: boolean;
  /** Enable resource planning */
  resource_planning_enabled: boolean;
  /** Prediction horizon in days */
  prediction_horizon_days: number;
  /** Minimum data points for prediction */
  min_data_points: number;
  /** Confidence threshold for alerts */
  confidence_threshold: number;
}

export const DEFAULT_ANALYTICS_CONFIG: Record<Variant, Partial<AnalyticsConfig>> = {
  mini_parwa: {
    volume_prediction_enabled: false,
    churn_prediction_enabled: false,
    performance_forecast_enabled: false,
    resource_planning_enabled: false,
    prediction_horizon_days: 7,
    min_data_points: 10,
  },
  parwa: {
    volume_prediction_enabled: true,
    churn_prediction_enabled: true,
    performance_forecast_enabled: true,
    resource_planning_enabled: false,
    prediction_horizon_days: 14,
    min_data_points: 7,
  },
  parwa_high: {
    volume_prediction_enabled: true,
    churn_prediction_enabled: true,
    performance_forecast_enabled: true,
    resource_planning_enabled: true,
    prediction_horizon_days: 30,
    min_data_points: 5,
  },
};

// ── Volume Prediction Types ──────────────────────────────────────────

export interface VolumePredictionRequest {
  /** Start date for historical data */
  start_date: Date;
  /** End date for historical data */
  end_date: Date;
  /** Channel filter (optional) */
  channel?: string;
  /** Category filter (optional) */
  category?: string;
  /** Granularity of prediction */
  granularity: 'hourly' | 'daily' | 'weekly';
  /** Forecast horizon (number of periods) */
  horizon: number;
}

export interface VolumePredictionResult {
  /** Prediction ID */
  id: string;
  /** Prediction timestamp */
  timestamp: Date;
  /** Predicted data points */
  predictions: VolumeDataPoint[];
  /** Model used */
  model: PredictionModel;
  /** Overall confidence (0-1) */
  confidence: number;
  /** Accuracy metrics (if historical data available) */
  accuracy_metrics?: AccuracyMetrics;
  /** Processing time in ms */
  processing_time_ms: number;
}

export interface VolumeDataPoint {
  /** Period start */
  period_start: Date;
  /** Period end */
  period_end: Date;
  /** Predicted volume */
  predicted_volume: number;
  /** Lower bound (confidence interval) */
  lower_bound: number;
  /** Upper bound (confidence interval) */
  upper_bound: number;
  /** Confidence level */
  confidence: number;
  /** Contributing factors */
  factors?: VolumeFactor[];
}

export interface VolumeFactor {
  /** Factor name */
  name: string;
  /** Impact percentage */
  impact_pct: number;
  /** Direction */
  direction: 'increase' | 'decrease' | 'neutral';
}

// ── Churn Prediction Types ───────────────────────────────────────────

export interface ChurnPredictionRequest {
  /** Customer ID (single customer) */
  customer_id?: string;
  /** Batch of customer IDs */
  customer_ids?: string[];
  /** Include risk factors */
  include_risk_factors?: boolean;
  /** Prediction window in days */
  prediction_window_days?: number;
}

export interface ChurnPredictionResult {
  /** Prediction ID */
  id: string;
  /** Timestamp */
  timestamp: Date;
  /** Customer predictions */
  predictions: CustomerChurnPrediction[];
  /** Aggregate statistics */
  aggregate_stats: ChurnAggregateStats;
  /** Processing time in ms */
  processing_time_ms: number;
}

export interface CustomerChurnPrediction {
  /** Customer ID */
  customer_id: string;
  /** Churn probability (0-1) */
  churn_probability: number;
  /** Risk level */
  risk_level: 'low' | 'medium' | 'high' | 'critical';
  /** Risk score (0-100) */
  risk_score: number;
  /** Days until predicted churn */
  days_to_churn?: number;
  /** Risk factors */
  risk_factors: ChurnRiskFactor[];
  /** Recommended actions */
  recommended_actions: string[];
  /** Value at risk */
  value_at_risk?: number;
}

export interface ChurnRiskFactor {
  /** Factor name */
  factor: string;
  /** Weight in prediction */
  weight: number;
  /** Current value */
  current_value: string | number;
  /** Threshold for concern */
  threshold?: string | number;
  /** Impact description */
  impact: string;
}

export interface ChurnAggregateStats {
  /** Total customers analyzed */
  total_customers: number;
  /** High risk count */
  high_risk_count: number;
  /** Medium risk count */
  medium_risk_count: number;
  /** Low risk count */
  low_risk_count: number;
  /** Average churn probability */
  avg_churn_probability: number;
  /** Total value at risk */
  total_value_at_risk: number;
}

// ── Performance Forecasting Types ─────────────────────────────────────

export interface PerformanceForecastRequest {
  /** Metric to forecast */
  metric: PerformanceMetric;
  /** Start date */
  start_date: Date;
  /** End date */
  end_date: Date;
  /** Forecast horizon in days */
  horizon_days: number;
  /** Agent filter (optional) */
  agent_id?: string;
  /** Team filter (optional) */
  team_id?: string;
}

export type PerformanceMetric =
  | 'response_time'
  | 'resolution_time'
  | 'csat_score'
  | 'first_contact_resolution'
  | 'ticket_volume'
  | 'agent_productivity'
  | 'sla_compliance';

export interface PerformanceForecastResult {
  /** Forecast ID */
  id: string;
  /** Timestamp */
  timestamp: Date;
  /** Metric forecasted */
  metric: PerformanceMetric;
  /** Forecast data points */
  forecasts: PerformanceDataPoint[];
  /** Trend analysis */
  trend: TrendAnalysis;
  /** Seasonal patterns detected */
  seasonality?: SeasonalityPattern;
  /** Confidence level */
  confidence: number;
  /** Processing time in ms */
  processing_time_ms: number;
}

export interface PerformanceDataPoint {
  /** Date */
  date: Date;
  /** Predicted value */
  predicted_value: number;
  /** Lower bound */
  lower_bound: number;
  /** Upper bound */
  upper_bound: number;
  /** Is anomaly predicted */
  is_anomaly: boolean;
  /** Actual value (if available) */
  actual_value?: number;
}

export interface TrendAnalysis {
  /** Trend direction */
  direction: 'increasing' | 'decreasing' | 'stable' | 'volatile';
  /** Trend strength (0-1) */
  strength: number;
  /** Average change rate */
  change_rate: number;
  /** Trend significance */
  significance: 'significant' | 'moderate' | 'weak';
}

export interface SeasonalityPattern {
  /** Pattern type */
  type: 'daily' | 'weekly' | 'monthly' | 'yearly';
  /** Peak times */
  peaks: number[];
  /** Trough times */
  troughs: number[];
  /** Pattern strength */
  strength: number;
}

// ── Resource Planning Types ───────────────────────────────────────────

export interface ResourcePlanningRequest {
  /** Planning horizon in days */
  horizon_days: number;
  /** Target service level (0-1) */
  target_service_level: number;
  /** Include skill requirements */
  include_skills?: boolean;
  /** Channels to consider */
  channels?: string[];
}

export interface ResourcePlanningResult {
  /** Plan ID */
  id: string;
  /** Timestamp */
  timestamp: Date;
  /** Planning horizon */
  horizon_days: number;
  /** Agent requirements by period */
  agent_requirements: AgentRequirement[];
  /** Skill gap analysis */
  skill_gaps: SkillGap[];
  /** Budget implications */
  budget_implications: BudgetImplication;
  /** Recommendations */
  recommendations: ResourceRecommendation[];
  /** Processing time in ms */
  processing_time_ms: number;
}

export interface AgentRequirement {
  /** Period */
  date: Date;
  /** Required agents */
  required_agents: number;
  /** Current agents */
  current_agents: number;
  /** Gap (positive = need more) */
  gap: number;
  /** Confidence */
  confidence: number;
  /** By channel */
  by_channel?: Record<string, number>;
  /** By skill */
  by_skill?: Record<string, number>;
}

export interface SkillGap {
  /** Skill name */
  skill: string;
  /** Current capacity */
  current_capacity: number;
  /** Required capacity */
  required_capacity: number;
  /** Gap */
  gap: number;
  /** Urgency */
  urgency: 'critical' | 'high' | 'medium' | 'low';
  /** Training time needed (days) */
  training_time_days?: number;
}

export interface BudgetImplication {
  /** Additional headcount needed */
  additional_headcount: number;
  /** Estimated monthly cost */
  monthly_cost: number;
  /** ROI estimate */
  roi_estimate?: number;
  /** Overtime hours needed */
  overtime_hours?: number;
  /** Overtime cost */
  overtime_cost?: number;
}

export interface ResourceRecommendation {
  /** Recommendation type */
  type: 'hire' | 'train' | 'redistribute' | 'outsource' | 'automate';
  /** Priority */
  priority: 'high' | 'medium' | 'low';
  /** Description */
  description: string;
  /** Expected impact */
  impact: string;
  /** Implementation timeline */
  timeline: string;
  /** Cost estimate */
  cost_estimate?: number;
}

// ── Accuracy Metrics ──────────────────────────────────────────────────

export interface AccuracyMetrics {
  /** Mean Absolute Error */
  mae: number;
  /** Mean Absolute Percentage Error */
  mape: number;
  /** Root Mean Square Error */
  rmse: number;
  /** R-squared */
  r_squared: number;
  /** Number of test periods */
  test_periods: number;
}

// ── Prediction Model Types ────────────────────────────────────────────

export type PredictionModel =
  | 'arima'
  | 'exponential_smoothing'
  | 'prophet'
  | 'linear_regression'
  | 'ensemble';

// ── Analytics Event Types ─────────────────────────────────────────────

export interface AnalyticsEvent {
  /** Event type */
  type: AnalyticsEventType;
  /** Timestamp */
  timestamp: Date;
  /** Tenant ID */
  tenant_id: string;
  /** Event payload */
  payload: Record<string, unknown>;
}

export type AnalyticsEventType =
  | 'prediction_generated'
  | 'anomaly_detected'
  | 'threshold_exceeded'
  | 'trend_changed'
  | 'forecast_updated'
  | 'alert_triggered';

// ── Analytics Dashboard Types ─────────────────────────────────────────

export interface AnalyticsDashboard {
  /** Volume predictions */
  volume_prediction?: VolumePredictionResult;
  /** Churn predictions */
  churn_prediction?: ChurnPredictionResult;
  /** Performance forecast */
  performance_forecast?: PerformanceForecastResult;
  /** Resource plan */
  resource_plan?: ResourcePlanningResult;
  /** Last updated */
  last_updated: Date;
  /** Summary metrics */
  summary: AnalyticsSummary;
}

export interface AnalyticsSummary {
  /** Predicted volume next 7 days */
  predicted_volume_next_7d: number;
  /** Volume trend */
  volume_trend: 'up' | 'down' | 'stable';
  /** High churn risk customers */
  high_churn_risk_count: number;
  /** Average CSAT forecast */
  csat_forecast: number;
  /** Agent gap */
  agent_gap: number;
  /** Budget at risk */
  budget_at_risk: number;
}

// ── Variant Capabilities ──────────────────────────────────────────────

export const ANALYTICS_VARIANT_CAPABILITIES: Record<Variant, {
  volume_prediction: boolean;
  churn_prediction: boolean;
  performance_forecast: boolean;
  resource_planning: boolean;
  max_prediction_horizon_days: number;
  supported_models: PredictionModel[];
  real_time_updates: boolean;
}> = {
  mini_parwa: {
    volume_prediction: false,
    churn_prediction: false,
    performance_forecast: false,
    resource_planning: false,
    max_prediction_horizon_days: 0,
    supported_models: [],
    real_time_updates: false,
  },
  parwa: {
    volume_prediction: true,
    churn_prediction: true,
    performance_forecast: true,
    resource_planning: false,
    max_prediction_horizon_days: 14,
    supported_models: ['exponential_smoothing', 'linear_regression'],
    real_time_updates: false,
  },
  parwa_high: {
    volume_prediction: true,
    churn_prediction: true,
    performance_forecast: true,
    resource_planning: true,
    max_prediction_horizon_days: 30,
    supported_models: ['arima', 'exponential_smoothing', 'prophet', 'linear_regression', 'ensemble'],
    real_time_updates: true,
  },
};
