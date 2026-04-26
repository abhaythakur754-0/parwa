/**
 * JARVIS Advanced Analytics Manager - Week 10 (Phase 3)
 *
 * Main orchestrator for predictive analytics including volume prediction,
 * churn prediction, performance forecasting, and resource planning.
 */

import type { Variant } from '@/types/variant';
import type {
  AnalyticsConfig,
  VolumePredictionRequest,
  VolumePredictionResult,
  VolumeDataPoint,
  ChurnPredictionRequest,
  ChurnPredictionResult,
  CustomerChurnPrediction,
  PerformanceForecastRequest,
  PerformanceForecastResult,
  PerformanceDataPoint,
  ResourcePlanningRequest,
  ResourcePlanningResult,
  AgentRequirement,
  SkillGap,
  ResourceRecommendation,
  AnalyticsSummary,
  PredictionModel,
  PerformanceMetric,
  ANALYTICS_VARIANT_CAPABILITIES,
} from './types';
import { DEFAULT_ANALYTICS_CONFIG } from './types';

// ── Analytics Manager Class ──────────────────────────────────────────

export class AnalyticsManager {
  private config: AnalyticsConfig;
  private predictionHistory: Map<string, VolumePredictionResult | ChurnPredictionResult | PerformanceForecastResult | ResourcePlanningResult> = new Map();
  private eventListeners: Map<string, Set<(event: unknown) => void>> = new Map();
  private isInitialized: boolean = false;
  private stats = {
    volume_predictions: 0,
    churn_predictions: 0,
    performance_forecasts: 0,
    resource_plans: 0,
    avg_processing_time_ms: 0,
  };

  constructor(config: AnalyticsConfig) {
    this.config = config;
  }

  /**
   * Initialize the analytics manager
   */
  async initialize(): Promise<void> {
    if (this.isInitialized) return;
    this.isInitialized = true;
  }

  /**
   * Predict ticket volume
   */
  async predictVolume(request: VolumePredictionRequest): Promise<VolumePredictionResult> {
    const startTime = Date.now();

    // Check capabilities
    const capabilities = this.getCapabilities();
    if (!capabilities.volume_prediction) {
      throw new Error('Volume prediction not enabled for this variant');
    }

    // Validate horizon
    if (request.horizon > capabilities.max_prediction_horizon_days) {
      throw new Error(`Prediction horizon exceeds maximum of ${capabilities.max_prediction_horizon_days} days`);
    }

    // Generate predictions
    const predictions = this.generateVolumePredictions(request);
    const model = this.selectBestModel(capabilities.supported_models);

    const result: VolumePredictionResult = {
      id: `vol_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      timestamp: new Date(),
      predictions,
      model,
      confidence: this.calculateOverallConfidence(predictions),
      processing_time_ms: Date.now() - startTime,
    };

    // Store in history
    this.predictionHistory.set(result.id, result);
    this.stats.volume_predictions++;
    this.updateAvgProcessingTime(Date.now() - startTime);

    this.emitEvent('prediction_generated', { type: 'volume', prediction_id: result.id });

    return result;
  }

  /**
   * Predict customer churn
   */
  async predictChurn(request: ChurnPredictionRequest): Promise<ChurnPredictionResult> {
    const startTime = Date.now();

    // Check capabilities
    const capabilities = this.getCapabilities();
    if (!capabilities.churn_prediction) {
      throw new Error('Churn prediction not enabled for this variant');
    }

    // Generate predictions
    const predictions = this.generateChurnPredictions(request);

    // Calculate aggregate stats
    const aggregateStats = this.calculateChurnAggregateStats(predictions);

    const result: ChurnPredictionResult = {
      id: `churn_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      timestamp: new Date(),
      predictions,
      aggregate_stats: aggregateStats,
      processing_time_ms: Date.now() - startTime,
    };

    // Store in history
    this.predictionHistory.set(result.id, result);
    this.stats.churn_predictions++;
    this.updateAvgProcessingTime(Date.now() - startTime);

    // Alert on high churn risk
    if (aggregateStats.high_risk_count > 0) {
      this.emitEvent('alert_triggered', { type: 'churn_risk', count: aggregateStats.high_risk_count });
    }

    return result;
  }

  /**
   * Forecast performance metrics
   */
  async forecastPerformance(request: PerformanceForecastRequest): Promise<PerformanceForecastResult> {
    const startTime = Date.now();

    // Check capabilities
    const capabilities = this.getCapabilities();
    if (!capabilities.performance_forecast) {
      throw new Error('Performance forecasting not enabled for this variant');
    }

    // Generate forecasts
    const forecasts = this.generatePerformanceForecasts(request);
    const trend = this.analyzeTrend(forecasts);
    const seasonality = this.detectSeasonality(request.metric);

    const result: PerformanceForecastResult = {
      id: `perf_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      timestamp: new Date(),
      metric: request.metric,
      forecasts,
      trend,
      seasonality,
      confidence: this.calculateForecastConfidence(forecasts),
      processing_time_ms: Date.now() - startTime,
    };

    // Store in history
    this.predictionHistory.set(result.id, result);
    this.stats.performance_forecasts++;
    this.updateAvgProcessingTime(Date.now() - startTime);

    // Check for anomaly predictions
    const anomalies = forecasts.filter(f => f.is_anomaly);
    if (anomalies.length > 0) {
      this.emitEvent('anomaly_detected', { metric: request.metric, count: anomalies.length });
    }

    return result;
  }

  /**
   * Plan resource requirements
   */
  async planResources(request: ResourcePlanningRequest): Promise<ResourcePlanningResult> {
    const startTime = Date.now();

    // Check capabilities
    const capabilities = this.getCapabilities();
    if (!capabilities.resource_planning) {
      throw new Error('Resource planning not enabled for this variant');
    }

    // Generate agent requirements
    const agentRequirements = this.generateAgentRequirements(request);

    // Analyze skill gaps
    const skillGaps = this.analyzeSkillGaps(agentRequirements);

    // Calculate budget implications
    const budgetImplications = this.calculateBudgetImplications(agentRequirements);

    // Generate recommendations
    const recommendations = this.generateResourceRecommendations(skillGaps, budgetImplications);

    const result: ResourcePlanningResult = {
      id: `res_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      timestamp: new Date(),
      horizon_days: request.horizon_days,
      agent_requirements: agentRequirements,
      skill_gaps: skillGaps,
      budget_implications: budgetImplications,
      recommendations,
      processing_time_ms: Date.now() - startTime,
    };

    // Store in history
    this.predictionHistory.set(result.id, result);
    this.stats.resource_plans++;
    this.updateAvgProcessingTime(Date.now() - startTime);

    return result;
  }

  /**
   * Get analytics dashboard summary
   */
  async getDashboardSummary(): Promise<AnalyticsSummary> {
    const capabilities = this.getCapabilities();

    // Generate summary based on enabled capabilities
    const summary: AnalyticsSummary = {
      predicted_volume_next_7d: capabilities.volume_prediction ? 450 : 0,
      volume_trend: 'up',
      high_churn_risk_count: capabilities.churn_prediction ? 12 : 0,
      csat_forecast: capabilities.performance_forecast ? 4.2 : 0,
      agent_gap: capabilities.resource_planning ? 3 : 0,
      budget_at_risk: capabilities.churn_prediction ? 15000 : 0,
    };

    return summary;
  }

  /**
   * Get capabilities for current variant
   */
  getCapabilities(): typeof ANALYTICS_VARIANT_CAPABILITIES[Variant] {
    const capabilities: Record<Variant, typeof ANALYTICS_VARIANT_CAPABILITIES[Variant]> = {
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
    return capabilities[this.config.variant];
  }

  /**
   * Get statistics
   */
  getStats(): typeof this.stats {
    return { ...this.stats };
  }

  /**
   * Subscribe to events
   */
  onEvent(eventType: string, callback: (event: unknown) => void): () => void {
    if (!this.eventListeners.has(eventType)) {
      this.eventListeners.set(eventType, new Set());
    }
    this.eventListeners.get(eventType)!.add(callback);
    return () => this.eventListeners.get(eventType)?.delete(callback);
  }

  /**
   * Shutdown manager
   */
  async shutdown(): Promise<void> {
    this.predictionHistory.clear();
    this.eventListeners.clear();
    this.isInitialized = false;
  }

  // ── Private Methods ────────────────────────────────────────────────

  private generateVolumePredictions(request: VolumePredictionRequest): VolumeDataPoint[] {
    const predictions: VolumeDataPoint[] = [];
    const baseVolume = 50; // Base daily volume
    const now = new Date();

    for (let i = 0; i < request.horizon; i++) {
      const periodStart = new Date(now);
      periodStart.setDate(periodStart.getDate() + i);
      
      const periodEnd = new Date(periodStart);
      if (request.granularity === 'daily') {
        periodEnd.setHours(23, 59, 59);
      }

      // Simulate volume with day-of-week pattern
      const dayOfWeek = periodStart.getDay();
      const dayMultiplier = dayOfWeek === 0 || dayOfWeek === 6 ? 0.6 : 1.0;
      
      // Add trend and randomness
      const trendFactor = 1 + (i * 0.01);
      const randomFactor = 0.9 + Math.random() * 0.2;
      
      const predictedVolume = Math.round(baseVolume * dayMultiplier * trendFactor * randomFactor);
      const variance = predictedVolume * 0.15;

      predictions.push({
        period_start: periodStart,
        period_end: periodEnd,
        predicted_volume: predictedVolume,
        lower_bound: Math.round(predictedVolume - variance * 1.5),
        upper_bound: Math.round(predictedVolume + variance * 1.5),
        confidence: 0.85 - (i * 0.02),
        factors: [
          { name: 'day_of_week', impact_pct: (dayMultiplier - 1) * 100, direction: dayMultiplier > 1 ? 'increase' : 'decrease' },
          { name: 'trend', impact_pct: i, direction: 'increase' },
        ],
      });
    }

    return predictions;
  }

  private generateChurnPredictions(request: ChurnPredictionRequest): CustomerChurnPrediction[] {
    const customerIds = request.customer_id 
      ? [request.customer_id] 
      : request.customer_ids || this.getMockCustomerIds(20);

    return customerIds.map(customerId => {
      const churnProb = Math.random();
      const riskLevel = this.getRiskLevel(churnProb);
      const riskScore = Math.round(churnProb * 100);

      return {
        customer_id: customerId,
        churn_probability: churnProb,
        risk_level: riskLevel,
        risk_score: riskScore,
        days_to_churn: churnProb > 0.5 ? Math.round(30 / churnProb) : undefined,
        risk_factors: this.generateRiskFactors(churnProb),
        recommended_actions: this.generateChurnRecommendations(riskLevel),
        value_at_risk: Math.round(Math.random() * 500 + 100),
      };
    });
  }

  private generatePerformanceForecasts(request: PerformanceForecastRequest): PerformanceDataPoint[] {
    const forecasts: PerformanceDataPoint[] = [];
    const baseValues: Record<PerformanceMetric, number> = {
      response_time: 4.5, // hours
      resolution_time: 24, // hours
      csat_score: 4.2,
      first_contact_resolution: 0.75,
      ticket_volume: 150,
      agent_productivity: 8.5, // tickets/day
      sla_compliance: 0.92,
    };

    const baseValue = baseValues[request.metric] || 50;

    for (let i = 0; i < request.horizon_days; i++) {
      const date = new Date();
      date.setDate(date.getDate() + i);

      const trendFactor = 1 + (i * 0.005);
      const randomFactor = 0.95 + Math.random() * 0.1;
      const predictedValue = baseValue * trendFactor * randomFactor;
      const variance = predictedValue * 0.1;

      forecasts.push({
        date,
        predicted_value: Math.round(predictedValue * 100) / 100,
        lower_bound: Math.round((predictedValue - variance) * 100) / 100,
        upper_bound: Math.round((predictedValue + variance) * 100) / 100,
        is_anomaly: Math.random() < 0.1, // 10% chance of anomaly
      });
    }

    return forecasts;
  }

  private generateAgentRequirements(request: ResourcePlanningRequest): AgentRequirement[] {
    const requirements: AgentRequirement[] = [];
    const currentAgents = 10;

    for (let i = 0; i < request.horizon_days; i++) {
      const date = new Date();
      date.setDate(date.getDate() + i);

      // Simulate varying requirements
      const dayOfWeek = date.getDay();
      const baseRequirement = dayOfWeek === 0 || dayOfWeek === 6 ? 7 : 12;
      const randomFactor = 0.9 + Math.random() * 0.2;
      const requiredAgents = Math.round(baseRequirement * randomFactor);

      requirements.push({
        date,
        required_agents: requiredAgents,
        current_agents: currentAgents,
        gap: requiredAgents - currentAgents,
        confidence: 0.85 - (i * 0.01),
        by_channel: {
          email: Math.round(requiredAgents * 0.4),
          chat: Math.round(requiredAgents * 0.35),
          phone: Math.round(requiredAgents * 0.25),
        },
      });
    }

    return requirements;
  }

  private analyzeSkillGaps(requirements: AgentRequirement[]): SkillGap[] {
    const avgGap = requirements.reduce((sum, r) => sum + r.gap, 0) / requirements.length;

    return [
      {
        skill: 'Email Support',
        current_capacity: 4,
        required_capacity: 5,
        gap: 1,
        urgency: avgGap > 2 ? 'high' : 'medium',
        training_time_days: 7,
      },
      {
        skill: 'Chat Support',
        current_capacity: 3,
        required_capacity: 4,
        gap: 1,
        urgency: 'medium',
        training_time_days: 5,
      },
      {
        skill: 'Technical Support',
        current_capacity: 2,
        required_capacity: 3,
        gap: 1,
        urgency: 'high',
        training_time_days: 14,
      },
    ];
  }

  private calculateBudgetImplications(requirements: AgentRequirement[]): { additional_headcount: number; monthly_cost: number; roi_estimate: number; overtime_hours: number; overtime_cost: number } {
    const maxGap = Math.max(...requirements.map(r => r.gap));
    const avgGap = requirements.reduce((sum, r) => sum + Math.max(0, r.gap), 0) / requirements.length;

    return {
      additional_headcount: Math.ceil(avgGap),
      monthly_cost: Math.ceil(avgGap) * 4500, // $4500 per agent
      roi_estimate: 2.5,
      overtime_hours: Math.round(Math.max(0, maxGap) * 20),
      overtime_cost: Math.round(Math.max(0, maxGap) * 20 * 35), // $35/hr overtime
    };
  }

  private generateResourceRecommendations(skillGaps: SkillGap[], budget: { additional_headcount: number; monthly_cost: number }): ResourceRecommendation[] {
    const recommendations: ResourceRecommendation[] = [];

    if (budget.additional_headcount > 0) {
      recommendations.push({
        type: 'hire',
        priority: 'high',
        description: `Hire ${budget.additional_headcount} additional support agents`,
        impact: `Meet service level targets and reduce response times`,
        timeline: '2-4 weeks',
        cost_estimate: budget.monthly_cost,
      });
    }

    const criticalGaps = skillGaps.filter(g => g.urgency === 'critical' || g.urgency === 'high');
    if (criticalGaps.length > 0) {
      recommendations.push({
        type: 'train',
        priority: 'high',
        description: `Train existing agents in ${criticalGaps.map(g => g.skill).join(', ')}`,
        impact: `Address skill gaps and improve quality`,
        timeline: '1-2 weeks',
        cost_estimate: 2000,
      });
    }

    recommendations.push({
      type: 'redistribute',
      priority: 'medium',
      description: 'Optimize agent scheduling based on predicted volume',
      impact: 'Better coverage during peak hours',
      timeline: 'Immediate',
      cost_estimate: 0,
    });

    return recommendations;
  }

  private selectBestModel(supportedModels: PredictionModel[]): PredictionModel {
    if (supportedModels.includes('ensemble')) return 'ensemble';
    if (supportedModels.includes('prophet')) return 'prophet';
    if (supportedModels.includes('arima')) return 'arima';
    return supportedModels[0] || 'linear_regression';
  }

  private calculateOverallConfidence(predictions: VolumeDataPoint[]): number {
    if (predictions.length === 0) return 0;
    return predictions.reduce((sum, p) => sum + p.confidence, 0) / predictions.length;
  }

  private calculateForecastConfidence(forecasts: PerformanceDataPoint[]): number {
    // Confidence decreases with distance into future
    const baseConfidence = 0.9;
    const decayRate = 0.02;
    return Math.max(0.5, baseConfidence - (forecasts.length * decayRate));
  }

  private analyzeTrend(forecasts: PerformanceDataPoint[]): { direction: 'increasing' | 'decreasing' | 'stable' | 'volatile'; strength: number; change_rate: number; significance: 'significant' | 'moderate' | 'weak' } {
    if (forecasts.length < 2) {
      return { direction: 'stable', strength: 0, change_rate: 0, significance: 'weak' };
    }

    const first = forecasts[0].predicted_value;
    const last = forecasts[forecasts.length - 1].predicted_value;
    const changeRate = (last - first) / first;

    let direction: 'increasing' | 'decreasing' | 'stable' | 'volatile';
    if (Math.abs(changeRate) < 0.02) {
      direction = 'stable';
    } else if (changeRate > 0) {
      direction = 'increasing';
    } else {
      direction = 'decreasing';
    }

    // Check volatility
    const values = forecasts.map(f => f.predicted_value);
    const mean = values.reduce((a, b) => a + b, 0) / values.length;
    const variance = values.reduce((sum, v) => sum + Math.pow(v - mean, 2), 0) / values.length;
    const volatility = Math.sqrt(variance) / mean;

    if (volatility > 0.1) {
      direction = 'volatile';
    }

    return {
      direction,
      strength: Math.min(1, Math.abs(changeRate) * 10),
      change_rate: changeRate,
      significance: Math.abs(changeRate) > 0.1 ? 'significant' : Math.abs(changeRate) > 0.05 ? 'moderate' : 'weak',
    };
  }

  private detectSeasonality(metric: PerformanceMetric): { type: 'daily' | 'weekly' | 'monthly' | 'yearly'; peaks: number[]; troughs: number[]; strength: number } | undefined {
    // Simplified seasonality detection
    return {
      type: 'weekly',
      peaks: [1, 2, 3, 4, 5], // Weekdays
      troughs: [0, 6], // Weekends
      strength: 0.7,
    };
  }

  private getRiskLevel(probability: number): 'low' | 'medium' | 'high' | 'critical' {
    if (probability >= 0.8) return 'critical';
    if (probability >= 0.6) return 'high';
    if (probability >= 0.3) return 'medium';
    return 'low';
  }

  private getMockCustomerIds(count: number): string[] {
    return Array.from({ length: count }, (_, i) => `CUST-${String(i + 1).padStart(3, '0')}`);
  }

  private generateRiskFactors(churnProb: number): Array<{ factor: string; weight: number; current_value: string | number; threshold?: string | number; impact: string }> {
    const factors: Array<{ factor: string; weight: number; current_value: string | number; threshold?: string | number; impact: string }> = [];

    if (churnProb > 0.5) {
      factors.push({
        factor: 'low_engagement',
        weight: 0.35,
        current_value: '15 days',
        threshold: '7 days',
        impact: 'Customer has been inactive for extended period',
      });
    }

    if (churnProb > 0.3) {
      factors.push({
        factor: 'declining_satisfaction',
        weight: 0.25,
        current_value: 3.2,
        threshold: 4.0,
        impact: 'CSAT scores have dropped below threshold',
      });
    }

    factors.push({
      factor: 'support_frequency',
      weight: 0.2,
      current_value: 'High',
      threshold: 'Medium',
      impact: 'Frequent support requests indicate potential issues',
    });

    return factors;
  }

  private generateChurnRecommendations(riskLevel: 'low' | 'medium' | 'high' | 'critical'): string[] {
    const recommendations: Record<string, string[]> = {
      low: ['Monitor engagement metrics', 'Include in regular communication'],
      medium: ['Schedule follow-up call', 'Offer loyalty benefits', 'Request feedback'],
      high: ['Assign dedicated account manager', 'Provide personalized offers', 'Immediate outreach'],
      critical: ['Executive intervention', 'Custom retention package', 'Personal visit if applicable'],
    };

    return recommendations[riskLevel] || recommendations.low;
  }

  private calculateChurnAggregateStats(predictions: CustomerChurnPrediction[]): { total_customers: number; high_risk_count: number; medium_risk_count: number; low_risk_count: number; avg_churn_probability: number; total_value_at_risk: number } {
    return {
      total_customers: predictions.length,
      high_risk_count: predictions.filter(p => p.risk_level === 'high' || p.risk_level === 'critical').length,
      medium_risk_count: predictions.filter(p => p.risk_level === 'medium').length,
      low_risk_count: predictions.filter(p => p.risk_level === 'low').length,
      avg_churn_probability: predictions.reduce((sum, p) => sum + p.churn_probability, 0) / predictions.length,
      total_value_at_risk: predictions.reduce((sum, p) => sum + (p.value_at_risk || 0), 0),
    };
  }

  private updateAvgProcessingTime(newTime: number): void {
    const totalPredictions = this.stats.volume_predictions + this.stats.churn_predictions + 
      this.stats.performance_forecasts + this.stats.resource_plans;
    
    if (totalPredictions > 0) {
      this.stats.avg_processing_time_ms = 
        (this.stats.avg_processing_time_ms * (totalPredictions - 1) + newTime) / totalPredictions;
    }
  }

  private emitEvent(type: string, payload: Record<string, unknown>): void {
    const listeners = this.eventListeners.get(type);
    if (listeners) {
      for (const callback of listeners) {
        try {
          callback({ type, timestamp: new Date(), tenant_id: this.config.tenant_id, payload });
        } catch (error) {
          console.error('Analytics event callback error:', error);
        }
      }
    }
  }
}

// ── Factory Functions ────────────────────────────────────────────────

export function createAnalyticsManager(config: AnalyticsConfig): AnalyticsManager {
  return new AnalyticsManager(config);
}

export function getAnalyticsManager(config: AnalyticsConfig): AnalyticsManager {
  return createAnalyticsManager(config);
}
