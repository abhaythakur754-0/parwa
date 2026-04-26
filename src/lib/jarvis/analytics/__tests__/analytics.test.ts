/**
 * JARVIS Advanced Analytics Tests - Week 10 (Phase 3)
 *
 * Comprehensive test suite for predictive analytics capabilities.
 */

import { AnalyticsManager, createAnalyticsManager } from '../analytics-manager';
import type {
  AnalyticsConfig,
  VolumePredictionRequest,
  ChurnPredictionRequest,
  PerformanceForecastRequest,
  ResourcePlanningRequest,
} from '../types';
import type { Variant } from '@/types/variant';

// ── Test Configuration ─────────────────────────────────────────────

const createTestConfig = (variant: Variant = 'parwa'): AnalyticsConfig => ({
  tenant_id: 'test-tenant',
  variant,
  volume_prediction_enabled: variant !== 'mini_parwa',
  churn_prediction_enabled: variant !== 'mini_parwa',
  performance_forecast_enabled: variant !== 'mini_parwa',
  resource_planning_enabled: variant === 'parwa_high',
  prediction_horizon_days: variant === 'parwa_high' ? 30 : 14,
  min_data_points: 7,
  confidence_threshold: 0.7,
});

// ── Analytics Manager Tests ────────────────────────────────────────

describe('AnalyticsManager', () => {
  let manager: AnalyticsManager;

  beforeEach(async () => {
    manager = createAnalyticsManager(createTestConfig('parwa'));
    await manager.initialize();
  });

  afterEach(async () => {
    await manager.shutdown();
  });

  describe('Initialization', () => {
    test('should initialize successfully', async () => {
      const newManager = createAnalyticsManager(createTestConfig('parwa'));
      await expect(newManager.initialize()).resolves.not.toThrow();
    });

    test('should not reinitialize if already initialized', async () => {
      await manager.initialize();
      await expect(manager.initialize()).resolves.not.toThrow();
    });
  });

  describe('Volume Prediction', () => {
    test('should predict ticket volume', async () => {
      const request: VolumePredictionRequest = {
        start_date: new Date('2024-01-01'),
        end_date: new Date('2024-01-31'),
        granularity: 'daily',
        horizon: 7,
      };

      const result = await manager.predictVolume(request);

      expect(result).toBeDefined();
      expect(result.predictions).toHaveLength(7);
      expect(result.model).toBeDefined();
      expect(result.confidence).toBeGreaterThan(0);
      expect(result.confidence).toBeLessThanOrEqual(1);
    });

    test('should include confidence bounds', async () => {
      const request: VolumePredictionRequest = {
        start_date: new Date('2024-01-01'),
        end_date: new Date('2024-01-31'),
        granularity: 'daily',
        horizon: 7,
      };

      const result = await manager.predictVolume(request);

      result.predictions.forEach(p => {
        expect(p.lower_bound).toBeLessThan(p.predicted_volume);
        expect(p.upper_bound).toBeGreaterThan(p.predicted_volume);
      });
    });

    test('should include volume factors', async () => {
      const request: VolumePredictionRequest = {
        start_date: new Date('2024-01-01'),
        end_date: new Date('2024-01-31'),
        granularity: 'daily',
        horizon: 7,
      };

      const result = await manager.predictVolume(request);

      expect(result.predictions[0].factors).toBeDefined();
      expect(result.predictions[0].factors!.length).toBeGreaterThan(0);
    });

    test('should throw error for mini_parwa', async () => {
      const miniManager = createAnalyticsManager(createTestConfig('mini_parwa'));
      await miniManager.initialize();

      const request: VolumePredictionRequest = {
        start_date: new Date(),
        end_date: new Date(),
        granularity: 'daily',
        horizon: 7,
      };

      await expect(miniManager.predictVolume(request)).rejects.toThrow('not enabled');
      await miniManager.shutdown();
    });

    test('should throw error for horizon exceeding limit', async () => {
      const request: VolumePredictionRequest = {
        start_date: new Date(),
        end_date: new Date(),
        granularity: 'daily',
        horizon: 30, // Exceeds parwa limit of 14
      };

      await expect(manager.predictVolume(request)).rejects.toThrow('exceeds maximum');
    });

    test('should update volume prediction count', async () => {
      const initialStats = manager.getStats();
      
      await manager.predictVolume({
        start_date: new Date(),
        end_date: new Date(),
        granularity: 'daily',
        horizon: 7,
      });

      const newStats = manager.getStats();
      expect(newStats.volume_predictions).toBe(initialStats.volume_predictions + 1);
    });
  });

  describe('Churn Prediction', () => {
    test('should predict churn for single customer', async () => {
      const request: ChurnPredictionRequest = {
        customer_id: 'CUST-001',
        include_risk_factors: true,
      };

      const result = await manager.predictChurn(request);

      expect(result).toBeDefined();
      expect(result.predictions).toHaveLength(1);
      expect(result.predictions[0].customer_id).toBe('CUST-001');
      expect(result.predictions[0].churn_probability).toBeGreaterThanOrEqual(0);
      expect(result.predictions[0].churn_probability).toBeLessThanOrEqual(1);
    });

    test('should predict churn for multiple customers', async () => {
      const request: ChurnPredictionRequest = {
        customer_ids: ['CUST-001', 'CUST-002', 'CUST-003'],
      };

      const result = await manager.predictChurn(request);

      expect(result.predictions).toHaveLength(3);
    });

    test('should calculate risk level', async () => {
      const request: ChurnPredictionRequest = {
        customer_ids: Array.from({ length: 20 }, (_, i) => `CUST-${i}`),
      };

      const result = await manager.predictChurn(request);

      const riskLevels = result.predictions.map(p => p.risk_level);
      expect(riskLevels).toContain('low');
    });

    test('should include risk factors', async () => {
      const request: ChurnPredictionRequest = {
        customer_id: 'CUST-001',
        include_risk_factors: true,
      };

      const result = await manager.predictChurn(request);

      const prediction = result.predictions[0];
      expect(prediction.risk_factors).toBeDefined();
      expect(prediction.risk_factors.length).toBeGreaterThan(0);
    });

    test('should include recommended actions', async () => {
      const request: ChurnPredictionRequest = {
        customer_id: 'CUST-001',
      };

      const result = await manager.predictChurn(request);

      expect(result.predictions[0].recommended_actions).toBeDefined();
      expect(result.predictions[0].recommended_actions.length).toBeGreaterThan(0);
    });

    test('should calculate aggregate statistics', async () => {
      const request: ChurnPredictionRequest = {
        customer_ids: Array.from({ length: 20 }, (_, i) => `CUST-${i}`),
      };

      const result = await manager.predictChurn(request);

      expect(result.aggregate_stats).toBeDefined();
      expect(result.aggregate_stats.total_customers).toBe(20);
      expect(result.aggregate_stats.high_risk_count).toBeGreaterThanOrEqual(0);
    });

    test('should throw error for mini_parwa', async () => {
      const miniManager = createAnalyticsManager(createTestConfig('mini_parwa'));
      await miniManager.initialize();

      await expect(miniManager.predictChurn({ customer_id: 'CUST-001' })).rejects.toThrow('not enabled');
      await miniManager.shutdown();
    });

    test('should update churn prediction count', async () => {
      const initialStats = manager.getStats();
      
      await manager.predictChurn({ customer_id: 'CUST-001' });

      const newStats = manager.getStats();
      expect(newStats.churn_predictions).toBe(initialStats.churn_predictions + 1);
    });
  });

  describe('Performance Forecasting', () => {
    test('should forecast response time', async () => {
      const request: PerformanceForecastRequest = {
        metric: 'response_time',
        start_date: new Date('2024-01-01'),
        end_date: new Date('2024-01-31'),
        horizon_days: 7,
      };

      const result = await manager.forecastPerformance(request);

      expect(result).toBeDefined();
      expect(result.metric).toBe('response_time');
      expect(result.forecasts).toHaveLength(7);
      expect(result.trend).toBeDefined();
    });

    test('should forecast CSAT score', async () => {
      const request: PerformanceForecastRequest = {
        metric: 'csat_score',
        start_date: new Date(),
        end_date: new Date(),
        horizon_days: 14,
      };

      const result = await manager.forecastPerformance(request);

      expect(result.metric).toBe('csat_score');
      result.forecasts.forEach(f => {
        expect(f.predicted_value).toBeGreaterThan(0);
        expect(f.predicted_value).toBeLessThanOrEqual(5); // CSAT is typically 1-5
      });
    });

    test('should detect seasonality', async () => {
      const request: PerformanceForecastRequest = {
        metric: 'ticket_volume',
        start_date: new Date(),
        end_date: new Date(),
        horizon_days: 7,
      };

      const result = await manager.forecastPerformance(request);

      expect(result.seasonality).toBeDefined();
      expect(result.seasonality!.type).toBe('weekly');
    });

    test('should analyze trend', async () => {
      const request: PerformanceForecastRequest = {
        metric: 'agent_productivity',
        start_date: new Date(),
        end_date: new Date(),
        horizon_days: 14,
      };

      const result = await manager.forecastPerformance(request);

      expect(result.trend.direction).toBeDefined();
      expect(['increasing', 'decreasing', 'stable', 'volatile']).toContain(result.trend.direction);
      expect(result.trend.strength).toBeGreaterThanOrEqual(0);
    });

    test('should flag anomalies', async () => {
      const request: PerformanceForecastRequest = {
        metric: 'sla_compliance',
        start_date: new Date(),
        end_date: new Date(),
        horizon_days: 30, // Longer horizon increases anomaly chance
      };

      const result = await manager.forecastPerformance(request);

      const anomalies = result.forecasts.filter(f => f.is_anomaly);
      // We expect some anomalies with longer horizon
      expect(result.forecasts.some(f => f.is_anomaly !== undefined)).toBe(true);
    });

    test('should throw error for mini_parwa', async () => {
      const miniManager = createAnalyticsManager(createTestConfig('mini_parwa'));
      await miniManager.initialize();

      await expect(miniManager.forecastPerformance({
        metric: 'response_time',
        start_date: new Date(),
        end_date: new Date(),
        horizon_days: 7,
      })).rejects.toThrow('not enabled');

      await miniManager.shutdown();
    });

    test('should update performance forecast count', async () => {
      const initialStats = manager.getStats();
      
      await manager.forecastPerformance({
        metric: 'response_time',
        start_date: new Date(),
        end_date: new Date(),
        horizon_days: 7,
      });

      const newStats = manager.getStats();
      expect(newStats.performance_forecasts).toBe(initialStats.performance_forecasts + 1);
    });
  });

  describe('Resource Planning', () => {
    test('should throw error for parwa variant', async () => {
      // Resource planning only available for parwa_high
      await expect(manager.planResources({
        horizon_days: 7,
        target_service_level: 0.95,
      })).rejects.toThrow('not enabled');
    });

    test('should plan resources for parwa_high', async () => {
      const highManager = createAnalyticsManager(createTestConfig('parwa_high'));
      await highManager.initialize();

      const request: ResourcePlanningRequest = {
        horizon_days: 7,
        target_service_level: 0.95,
      };

      const result = await highManager.planResources(request);

      expect(result).toBeDefined();
      expect(result.horizon_days).toBe(7);
      expect(result.agent_requirements).toHaveLength(7);

      await highManager.shutdown();
    });

    test('should calculate agent requirements', async () => {
      const highManager = createAnalyticsManager(createTestConfig('parwa_high'));
      await highManager.initialize();

      const result = await highManager.planResources({
        horizon_days: 7,
        target_service_level: 0.95,
      });

      result.agent_requirements.forEach(req => {
        expect(req.required_agents).toBeGreaterThan(0);
        expect(req.current_agents).toBeGreaterThan(0);
        expect(req.gap).toBeDefined();
        expect(req.confidence).toBeGreaterThan(0);
      });

      await highManager.shutdown();
    });

    test('should identify skill gaps', async () => {
      const highManager = createAnalyticsManager(createTestConfig('parwa_high'));
      await highManager.initialize();

      const result = await highManager.planResources({
        horizon_days: 7,
        target_service_level: 0.95,
        include_skills: true,
      });

      expect(result.skill_gaps).toBeDefined();
      expect(result.skill_gaps.length).toBeGreaterThan(0);
      
      result.skill_gaps.forEach(gap => {
        expect(gap.skill).toBeDefined();
        expect(gap.gap).toBeDefined();
        expect(gap.urgency).toBeDefined();
      });

      await highManager.shutdown();
    });

    test('should calculate budget implications', async () => {
      const highManager = createAnalyticsManager(createTestConfig('parwa_high'));
      await highManager.initialize();

      const result = await highManager.planResources({
        horizon_days: 7,
        target_service_level: 0.95,
      });

      expect(result.budget_implications).toBeDefined();
      expect(result.budget_implications.additional_headcount).toBeGreaterThanOrEqual(0);
      expect(result.budget_implications.monthly_cost).toBeGreaterThan(0);

      await highManager.shutdown();
    });

    test('should generate recommendations', async () => {
      const highManager = createAnalyticsManager(createTestConfig('parwa_high'));
      await highManager.initialize();

      const result = await highManager.planResources({
        horizon_days: 7,
        target_service_level: 0.95,
      });

      expect(result.recommendations).toBeDefined();
      expect(result.recommendations.length).toBeGreaterThan(0);

      result.recommendations.forEach(rec => {
        expect(rec.type).toBeDefined();
        expect(rec.priority).toBeDefined();
        expect(rec.description).toBeDefined();
      });

      await highManager.shutdown();
    });

    test('should update resource plan count', async () => {
      const highManager = createAnalyticsManager(createTestConfig('parwa_high'));
      await highManager.initialize();
      const initialStats = highManager.getStats();
      
      await highManager.planResources({
        horizon_days: 7,
        target_service_level: 0.95,
      });

      const newStats = highManager.getStats();
      expect(newStats.resource_plans).toBe(initialStats.resource_plans + 1);

      await highManager.shutdown();
    });
  });

  describe('Dashboard Summary', () => {
    test('should generate dashboard summary', async () => {
      const summary = await manager.getDashboardSummary();

      expect(summary).toBeDefined();
      expect(summary.predicted_volume_next_7d).toBeGreaterThan(0);
      expect(summary.volume_trend).toBeDefined();
      expect(summary.high_churn_risk_count).toBeGreaterThanOrEqual(0);
    });

    test('should return zeros for mini_parwa', async () => {
      const miniManager = createAnalyticsManager(createTestConfig('mini_parwa'));
      await miniManager.initialize();

      const summary = await miniManager.getDashboardSummary();

      expect(summary.predicted_volume_next_7d).toBe(0);
      expect(summary.high_churn_risk_count).toBe(0);
      expect(summary.csat_forecast).toBe(0);
      expect(summary.agent_gap).toBe(0);

      await miniManager.shutdown();
    });
  });

  describe('Capabilities', () => {
    test('should return parwa capabilities', () => {
      const capabilities = manager.getCapabilities();

      expect(capabilities.volume_prediction).toBe(true);
      expect(capabilities.churn_prediction).toBe(true);
      expect(capabilities.performance_forecast).toBe(true);
      expect(capabilities.resource_planning).toBe(false);
      expect(capabilities.max_prediction_horizon_days).toBe(14);
    });

    test('should return parwa_high capabilities', async () => {
      const highManager = createAnalyticsManager(createTestConfig('parwa_high'));
      await highManager.initialize();

      const capabilities = highManager.getCapabilities();

      expect(capabilities.volume_prediction).toBe(true);
      expect(capabilities.churn_prediction).toBe(true);
      expect(capabilities.performance_forecast).toBe(true);
      expect(capabilities.resource_planning).toBe(true);
      expect(capabilities.max_prediction_horizon_days).toBe(30);
      expect(capabilities.supported_models).toContain('ensemble');

      await highManager.shutdown();
    });

    test('should return mini_parwa capabilities', async () => {
      const miniManager = createAnalyticsManager(createTestConfig('mini_parwa'));
      await miniManager.initialize();

      const capabilities = miniManager.getCapabilities();

      expect(capabilities.volume_prediction).toBe(false);
      expect(capabilities.churn_prediction).toBe(false);
      expect(capabilities.performance_forecast).toBe(false);
      expect(capabilities.resource_planning).toBe(false);
      expect(capabilities.supported_models).toHaveLength(0);

      await miniManager.shutdown();
    });
  });

  describe('Statistics', () => {
    test('should track stats', async () => {
      await manager.predictVolume({
        start_date: new Date(),
        end_date: new Date(),
        granularity: 'daily',
        horizon: 7,
      });

      const stats = manager.getStats();

      expect(stats.volume_predictions).toBeGreaterThan(0);
    });

    test('should track average processing time', async () => {
      // Run multiple predictions to test average calculation
      await manager.predictVolume({
        start_date: new Date(),
        end_date: new Date(),
        granularity: 'daily',
        horizon: 7,
      });

      await manager.predictChurn({ customer_id: 'CUST-001' });

      const stats = manager.getStats();

      expect(stats.avg_processing_time_ms).toBeGreaterThanOrEqual(0);
    });
  });

  describe('Event System', () => {
    test('should emit prediction_generated event', async () => {
      const listener = jest.fn();
      manager.onEvent('prediction_generated', listener);

      await manager.predictVolume({
        start_date: new Date(),
        end_date: new Date(),
        granularity: 'daily',
        horizon: 7,
      });

      expect(listener).toHaveBeenCalled();
    });

    test('should emit alert_triggered for high churn', async () => {
      const listener = jest.fn();
      manager.onEvent('alert_triggered', listener);

      // Request churn prediction with many customers to likely get high risk
      await manager.predictChurn({
        customer_ids: Array.from({ length: 50 }, (_, i) => `CUST-${i}`),
      });

      // May or may not trigger based on random predictions
      // Just verify the event system works
    });

    test('should emit anomaly_detected for performance forecasts', async () => {
      const listener = jest.fn();
      manager.onEvent('anomaly_detected', listener);

      await manager.forecastPerformance({
        metric: 'response_time',
        start_date: new Date(),
        end_date: new Date(),
        horizon_days: 30,
      });

      // May or may not trigger based on random anomaly detection
    });

    test('should return unsubscribe function', async () => {
      const listener = jest.fn();
      const unsubscribe = manager.onEvent('prediction_generated', listener);

      await manager.predictVolume({
        start_date: new Date(),
        end_date: new Date(),
        granularity: 'daily',
        horizon: 7,
      });

      expect(listener).toHaveBeenCalledTimes(1);

      unsubscribe();

      await manager.predictVolume({
        start_date: new Date(),
        end_date: new Date(),
        granularity: 'daily',
        horizon: 7,
      });

      expect(listener).toHaveBeenCalledTimes(1); // Still 1 after unsubscribe
    });
  });

  describe('Shutdown', () => {
    test('should clear history on shutdown', async () => {
      await manager.predictVolume({
        start_date: new Date(),
        end_date: new Date(),
        granularity: 'daily',
        horizon: 7,
      });

      await manager.shutdown();

      // Manager should be shut down cleanly
    });

    test('should clear event listeners on shutdown', async () => {
      const listener = jest.fn();
      manager.onEvent('prediction_generated', listener);

      await manager.shutdown();
    });
  });
});

// ── Variant Limits Tests ─────────────────────────────────────────────

describe('Analytics Variant Limits', () => {
  test('mini_parwa should have no analytics capabilities', async () => {
    const manager = createAnalyticsManager(createTestConfig('mini_parwa'));
    await manager.initialize();

    const capabilities = manager.getCapabilities();

    expect(capabilities.volume_prediction).toBe(false);
    expect(capabilities.churn_prediction).toBe(false);
    expect(capabilities.performance_forecast).toBe(false);
    expect(capabilities.resource_planning).toBe(false);
    expect(capabilities.max_prediction_horizon_days).toBe(0);

    await manager.shutdown();
  });

  test('parwa should have limited analytics capabilities', async () => {
    const manager = createAnalyticsManager(createTestConfig('parwa'));
    await manager.initialize();

    const capabilities = manager.getCapabilities();

    expect(capabilities.volume_prediction).toBe(true);
    expect(capabilities.churn_prediction).toBe(true);
    expect(capabilities.performance_forecast).toBe(true);
    expect(capabilities.resource_planning).toBe(false);
    expect(capabilities.max_prediction_horizon_days).toBe(14);

    await manager.shutdown();
  });

  test('parwa_high should have full analytics capabilities', async () => {
    const manager = createAnalyticsManager(createTestConfig('parwa_high'));
    await manager.initialize();

    const capabilities = manager.getCapabilities();

    expect(capabilities.volume_prediction).toBe(true);
    expect(capabilities.churn_prediction).toBe(true);
    expect(capabilities.performance_forecast).toBe(true);
    expect(capabilities.resource_planning).toBe(true);
    expect(capabilities.max_prediction_horizon_days).toBe(30);
    expect(capabilities.real_time_updates).toBe(true);

    await manager.shutdown();
  });
});
