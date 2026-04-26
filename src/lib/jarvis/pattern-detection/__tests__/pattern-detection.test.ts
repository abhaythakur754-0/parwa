/**
 * JARVIS Pattern Detection Tests - Week 8 (Phase 2)
 *
 * Comprehensive tests for the Pattern Detection system.
 */

import {
  PatternDetectionManager,
  createPatternDetectionManager,
} from '../pattern-detection-manager';
import {
  DEFAULT_PATTERN_DETECTION_CONFIG,
  PATTERN_DETECTION_VARIANT_LIMITS,
} from '../types';
import type {
  PatternCategory,
  PatternType,
  PatternDetectionConfig,
  Variant,
} from '../types';

// ── Test Configuration ─────────────────────────────────────────────

const createTestConfig = (variant: Variant = 'parwa'): PatternDetectionConfig => ({
  ...DEFAULT_PATTERN_DETECTION_CONFIG,
  tenant_id: `test_tenant_${Date.now()}`,
  variant,
});

const TEST_TENANT = 'test_tenant_123';
const TEST_USER = 'test_user_456';
const TEST_VARIANT: Variant = 'parwa';

// ── Pattern Detection Manager Tests ─────────────────────────────────

describe('PatternDetectionManager', () => {
  let manager: PatternDetectionManager;
  let config: PatternDetectionConfig;

  beforeEach(() => {
    config = createTestConfig();
    manager = createPatternDetectionManager(config);
  });

  afterEach(() => {
    manager.shutdown();
  });

  describe('Initialization', () => {
    test('should initialize with default config', () => {
      expect(manager).toBeDefined();
      const stats = manager.getStats();
      expect(stats.total_patterns_detected).toBe(0);
    });

    test('should load variant limits', () => {
      const stats = manager.getStats();
      expect(stats).toBeDefined();
    });
  });

  describe('User Behavior Pattern Detection', () => {
    test('should detect sequential patterns', () => {
      const intentHistory = [
        { intent: 'search_tickets' as const, timestamp: new Date(Date.now() - 1000 * 60 * 60) },
        { intent: 'view_ticket' as const, timestamp: new Date(Date.now() - 1000 * 60 * 55) },
        { intent: 'search_tickets' as const, timestamp: new Date(Date.now() - 1000 * 60 * 50) },
        { intent: 'view_ticket' as const, timestamp: new Date(Date.now() - 1000 * 60 * 45) },
        { intent: 'search_tickets' as const, timestamp: new Date(Date.now() - 1000 * 60 * 40) },
        { intent: 'view_ticket' as const, timestamp: new Date(Date.now() - 1000 * 60 * 35) },
        { intent: 'search_tickets' as const, timestamp: new Date(Date.now() - 1000 * 60 * 30) },
        { intent: 'view_ticket' as const, timestamp: new Date(Date.now() - 1000 * 60 * 25) },
      ];

      const patterns = manager.analyzeUserBehavior(TEST_USER, intentHistory);

      expect(patterns.length).toBeGreaterThan(0);

      const sequentialPatterns = patterns.filter(p => p.type === 'sequential');
      expect(sequentialPatterns.length).toBeGreaterThan(0);
    });

    test('should detect temporal patterns', () => {
      // Create intents at specific hours
      const baseTime = new Date();
      baseTime.setHours(9, 0, 0, 0); // 9 AM

      const intentHistory = [
        { intent: 'view_dashboard' as const, timestamp: new Date(baseTime) },
        { intent: 'view_dashboard' as const, timestamp: new Date(baseTime.getTime() + 24 * 60 * 60 * 1000) },
        { intent: 'view_dashboard' as const, timestamp: new Date(baseTime.getTime() + 48 * 60 * 60 * 1000) },
        { intent: 'view_dashboard' as const, timestamp: new Date(baseTime.getTime() + 72 * 60 * 60 * 1000) },
      ];

      const patterns = manager.analyzeUserBehavior(TEST_USER, intentHistory);

      const temporalPatterns = patterns.filter(p => p.category === 'time_patterns');
      expect(temporalPatterns.length).toBeGreaterThan(0);
    });

    test('should detect frequency patterns', () => {
      const intentHistory = [
        { intent: 'search_tickets' as const, timestamp: new Date() },
        { intent: 'search_tickets' as const, timestamp: new Date() },
        { intent: 'search_tickets' as const, timestamp: new Date() },
        { intent: 'search_tickets' as const, timestamp: new Date() },
        { intent: 'view_ticket' as const, timestamp: new Date() },
      ];

      const patterns = manager.analyzeUserBehavior(TEST_USER, intentHistory);

      const frequencyPatterns = patterns.filter(p => p.type === 'frequency');
      expect(frequencyPatterns.length).toBeGreaterThan(0);
    });

    test('should create pattern with correct properties', () => {
      const intentHistory = [
        { intent: 'action_a' as const, timestamp: new Date() },
        { intent: 'action_b' as const, timestamp: new Date() },
        { intent: 'action_a' as const, timestamp: new Date() },
        { intent: 'action_b' as const, timestamp: new Date() },
        { intent: 'action_a' as const, timestamp: new Date() },
        { intent: 'action_b' as const, timestamp: new Date() },
      ];

      const patterns = manager.analyzeUserBehavior(TEST_USER, intentHistory);

      if (patterns.length > 0) {
        const pattern = patterns[0];
        expect(pattern.id).toBeDefined();
        expect(pattern.category).toBeDefined();
        expect(pattern.type).toBeDefined();
        expect(pattern.name).toBeDefined();
        expect(pattern.confidence_score).toBeGreaterThanOrEqual(0);
        expect(pattern.confidence_score).toBeLessThanOrEqual(1);
        expect(pattern.occurrences).toBeGreaterThan(0);
      }
    });
  });

  describe('Ticket Pattern Detection', () => {
    test('should detect ticket priority patterns', () => {
      const tickets = [
        { id: 'TKT-001', priority: 'high', created_at: new Date() },
        { id: 'TKT-002', priority: 'high', created_at: new Date() },
        { id: 'TKT-003', priority: 'high', created_at: new Date() },
        { id: 'TKT-004', priority: 'high', created_at: new Date() },
        { id: 'TKT-005', priority: 'medium', created_at: new Date() },
      ];

      const patterns = manager.analyzeTicketPatterns(tickets);

      expect(patterns.length).toBeGreaterThan(0);

      const priorityPatterns = patterns.filter(p => p.name.includes('Priority'));
      expect(priorityPatterns.length).toBeGreaterThan(0);
    });

    test('should not detect patterns with insufficient data', () => {
      const tickets = [
        { id: 'TKT-001', priority: 'high', created_at: new Date() },
        { id: 'TKT-002', priority: 'low', created_at: new Date() },
      ];

      const patterns = manager.analyzeTicketPatterns(tickets);

      // Should not detect patterns with only 2 tickets
      expect(patterns.length).toBe(0);
    });
  });

  describe('SLA Pattern Detection', () => {
    test('should detect high breach rate patterns', () => {
      const slaRecords = [
        { ticket_id: 'TKT-001', sla_type: 'resolution', deadline: new Date(), met: false },
        { ticket_id: 'TKT-002', sla_type: 'resolution', deadline: new Date(), met: false },
        { ticket_id: 'TKT-003', sla_type: 'resolution', deadline: new Date(), met: false },
        { ticket_id: 'TKT-004', sla_type: 'resolution', deadline: new Date(), met: true },
        { ticket_id: 'TKT-005', sla_type: 'resolution', deadline: new Date(), met: true },
      ];

      const patterns = manager.analyzeSLAPatterns(slaRecords);

      // 60% breach rate should trigger pattern
      expect(patterns.length).toBeGreaterThan(0);

      const breachPattern = patterns.find(p => p.name.includes('Breach'));
      expect(breachPattern).toBeDefined();
    });

    test('should not detect patterns with good SLA performance', () => {
      const slaRecords = [
        { ticket_id: 'TKT-001', sla_type: 'resolution', deadline: new Date(), met: true },
        { ticket_id: 'TKT-002', sla_type: 'resolution', deadline: new Date(), met: true },
        { ticket_id: 'TKT-003', sla_type: 'resolution', deadline: new Date(), met: true },
        { ticket_id: 'TKT-004', sla_type: 'resolution', deadline: new Date(), met: true },
        { ticket_id: 'TKT-005', sla_type: 'resolution', deadline: new Date(), met: true },
      ];

      const patterns = manager.analyzeSLAPatterns(slaRecords);

      // 0% breach rate should not trigger pattern
      expect(patterns.length).toBe(0);
    });
  });

  describe('Anomaly Detection', () => {
    test('should detect spike anomalies', () => {
      const anomaly = manager.checkForAnomalies(
        'ticket_volume',
        150, // Current value
        { mean: 100, stdDev: 15 } // Baseline
      );

      // Should detect anomaly (50% above mean)
      expect(anomaly).toBeDefined();
      expect(anomaly?.type).toBe('spike');
    });

    test('should detect drop anomalies', () => {
      const anomaly = manager.checkForAnomalies(
        'ticket_volume',
        50, // Current value
        { mean: 100, stdDev: 15 } // Baseline
      );

      // Should detect anomaly (50% below mean)
      expect(anomaly).toBeDefined();
      expect(anomaly?.type).toBe('drop');
    });

    test('should not detect anomaly for normal values', () => {
      const anomaly = manager.checkForAnomalies(
        'ticket_volume',
        105, // Current value (within normal range)
        { mean: 100, stdDev: 15 } // Baseline
      );

      // Should not detect anomaly (5% deviation is below threshold)
      expect(anomaly).toBeNull();
    });

    test('should set correct severity for anomalies', () => {
      const criticalAnomaly = manager.checkForAnomalies(
        'ticket_volume',
        200, // 100% above mean
        { mean: 100, stdDev: 15 }
      );

      expect(criticalAnomaly?.severity).toBe('critical');
    });

    test('should get active anomalies', () => {
      manager.checkForAnomalies('ticket_volume', 150, { mean: 100, stdDev: 15 });
      manager.checkForAnomalies('response_time', 200, { mean: 100, stdDev: 20 });

      const activeAnomalies = manager.getActiveAnomalies();
      expect(activeAnomalies.length).toBe(2);
    });

    test('should resolve anomaly', () => {
      const anomaly = manager.checkForAnomalies(
        'ticket_volume',
        150,
        { mean: 100, stdDev: 15 }
      );

      if (anomaly) {
        const resolved = manager.resolveAnomaly(anomaly.id, 'Fixed by scaling');
        expect(resolved?.resolved).toBe(true);
        expect(resolved?.resolution_note).toBe('Fixed by scaling');
      }
    });
  });

  describe('Trend Analysis', () => {
    test('should detect increasing trend', () => {
      const dataPoints = [
        { timestamp: new Date(Date.now() - 5 * 60 * 60 * 1000), value: 10 },
        { timestamp: new Date(Date.now() - 4 * 60 * 60 * 1000), value: 15 },
        { timestamp: new Date(Date.now() - 3 * 60 * 60 * 1000), value: 20 },
        { timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000), value: 25 },
        { timestamp: new Date(Date.now() - 1 * 60 * 60 * 1000), value: 30 },
      ];

      const trend = manager.analyzeTrend('ticket_volume', dataPoints);

      expect(trend).toBeDefined();
      expect(trend?.direction).toBe('increasing');
    });

    test('should detect decreasing trend', () => {
      const dataPoints = [
        { timestamp: new Date(Date.now() - 5 * 60 * 60 * 1000), value: 50 },
        { timestamp: new Date(Date.now() - 4 * 60 * 60 * 1000), value: 40 },
        { timestamp: new Date(Date.now() - 3 * 60 * 60 * 1000), value: 30 },
        { timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000), value: 20 },
        { timestamp: new Date(Date.now() - 1 * 60 * 60 * 1000), value: 10 },
      ];

      const trend = manager.analyzeTrend('escalation_rate', dataPoints);

      expect(trend).toBeDefined();
      expect(trend?.direction).toBe('decreasing');
    });

    test('should detect stable trend', () => {
      const dataPoints = [
        { timestamp: new Date(Date.now() - 5 * 60 * 60 * 1000), value: 100 },
        { timestamp: new Date(Date.now() - 4 * 60 * 60 * 1000), value: 100 },
        { timestamp: new Date(Date.now() - 3 * 60 * 60 * 1000), value: 100 },
        { timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000), value: 100 },
        { timestamp: new Date(Date.now() - 1 * 60 * 60 * 1000), value: 100 },
      ];

      const trend = manager.analyzeTrend('stable_metric', dataPoints);

      expect(trend?.direction).toBe('stable');
    });

    test('should not analyze with insufficient data', () => {
      const dataPoints = [
        { timestamp: new Date(), value: 100 },
        { timestamp: new Date(), value: 100 },
      ];

      const trend = manager.analyzeTrend('metric', dataPoints);
      expect(trend).toBeNull();
    });

    test('should get active trends', () => {
      const dataPoints = [
        { timestamp: new Date(Date.now() - 5 * 60 * 60 * 1000), value: 10 },
        { timestamp: new Date(Date.now() - 4 * 60 * 60 * 1000), value: 20 },
        { timestamp: new Date(Date.now() - 3 * 60 * 60 * 1000), value: 30 },
      ];

      manager.analyzeTrend('test_metric', dataPoints);

      const activeTrends = manager.getActiveTrends();
      expect(activeTrends.length).toBeGreaterThan(0);
    });
  });

  describe('Pattern Management', () => {
    test('should get patterns', () => {
      // Create some patterns first - need enough data to trigger pattern detection
      const intentHistory = [
        { intent: 'search_tickets' as const, timestamp: new Date() },
        { intent: 'view_ticket' as const, timestamp: new Date() },
        { intent: 'search_tickets' as const, timestamp: new Date() },
        { intent: 'view_ticket' as const, timestamp: new Date() },
        { intent: 'search_tickets' as const, timestamp: new Date() },
        { intent: 'view_ticket' as const, timestamp: new Date() },
        { intent: 'search_tickets' as const, timestamp: new Date() },
        { intent: 'view_ticket' as const, timestamp: new Date() },
      ];

      manager.analyzeUserBehavior(TEST_USER, intentHistory);

      const response = manager.getPatterns({
        tenant_id: config.tenant_id,
      });

      expect(response.patterns.length).toBeGreaterThan(0);
    });

    test('should filter patterns by category', () => {
      const intentHistory = [
        { intent: 'search_tickets' as const, timestamp: new Date() },
        { intent: 'view_ticket' as const, timestamp: new Date() },
        { intent: 'search_tickets' as const, timestamp: new Date() },
        { intent: 'view_ticket' as const, timestamp: new Date() },
      ];

      manager.analyzeUserBehavior(TEST_USER, intentHistory);

      const response = manager.getPatterns({
        tenant_id: config.tenant_id,
        categories: ['user_behavior'],
      });

      expect(response.patterns.every(p => p.category === 'user_behavior')).toBe(true);
    });

    test('should filter patterns by type', () => {
      const intentHistory = [
        { intent: 'search_tickets' as const, timestamp: new Date() },
        { intent: 'view_ticket' as const, timestamp: new Date() },
        { intent: 'search_tickets' as const, timestamp: new Date() },
        { intent: 'view_ticket' as const, timestamp: new Date() },
      ];

      manager.analyzeUserBehavior(TEST_USER, intentHistory);

      const response = manager.getPatterns({
        tenant_id: config.tenant_id,
        types: ['sequential'],
      });

      expect(response.patterns.every(p => p.type === 'sequential')).toBe(true);
    });

    test('should get pattern by ID', () => {
      const intentHistory = [
        { intent: 'search_tickets' as const, timestamp: new Date() },
        { intent: 'view_ticket' as const, timestamp: new Date() },
        { intent: 'search_tickets' as const, timestamp: new Date() },
        { intent: 'view_ticket' as const, timestamp: new Date() },
      ];

      const patterns = manager.analyzeUserBehavior(TEST_USER, intentHistory);

      if (patterns.length > 0) {
        const pattern = manager.getPattern(patterns[0].id);
        expect(pattern).toBeDefined();
        expect(pattern?.id).toBe(patterns[0].id);
      }
    });

    test('should record pattern instance', () => {
      const intentHistory = [
        { intent: 'search_tickets' as const, timestamp: new Date() },
        { intent: 'view_ticket' as const, timestamp: new Date() },
        { intent: 'search_tickets' as const, timestamp: new Date() },
        { intent: 'view_ticket' as const, timestamp: new Date() },
      ];

      const patterns = manager.analyzeUserBehavior(TEST_USER, intentHistory);

      if (patterns.length > 0) {
        const instance = manager.recordPatternInstance(patterns[0].id, { test: true });
        expect(instance).toBeDefined();
        expect(instance?.pattern_id).toBe(patterns[0].id);
      }
    });

    test('should invalidate pattern', () => {
      const intentHistory = [
        { intent: 'search_tickets' as const, timestamp: new Date() },
        { intent: 'view_ticket' as const, timestamp: new Date() },
        { intent: 'search_tickets' as const, timestamp: new Date() },
        { intent: 'view_ticket' as const, timestamp: new Date() },
      ];

      const patterns = manager.analyzeUserBehavior(TEST_USER, intentHistory);

      if (patterns.length > 0) {
        const result = manager.invalidatePattern(patterns[0].id, 'No longer relevant');
        expect(result).toBe(true);

        const pattern = manager.getPattern(patterns[0].id);
        expect(pattern?.status).toBe('invalidated');
      }
    });
  });

  describe('Predictions', () => {
    test('should make prediction', () => {
      const intentHistory = [
        { intent: 'search_tickets' as const, timestamp: new Date() },
        { intent: 'view_ticket' as const, timestamp: new Date() },
        { intent: 'search_tickets' as const, timestamp: new Date() },
        { intent: 'view_ticket' as const, timestamp: new Date() },
      ];

      const patterns = manager.analyzeUserBehavior(TEST_USER, intentHistory);

      if (patterns.length > 0) {
        const prediction = manager.makePrediction(
          patterns[0].id,
          'user_will_view_ticket',
          0.85,
          { type: 'short_term', duration_minutes: 30 }
        );

        expect(prediction).toBeDefined();
        expect(prediction?.predicted_event).toBe('user_will_view_ticket');
        expect(prediction?.probability).toBe(0.85);
      }
    });
  });

  describe('Statistics', () => {
    test('should return statistics', () => {
      const stats = manager.getStats();

      expect(stats.total_patterns_detected).toBeDefined();
      expect(stats.patterns_by_category).toBeDefined();
      expect(stats.patterns_by_type).toBeDefined();
      expect(stats.anomalies_detected).toBeDefined();
    });

    test('should track detected patterns', () => {
      const intentHistory = [
        { intent: 'search_tickets' as const, timestamp: new Date() },
        { intent: 'view_ticket' as const, timestamp: new Date() },
        { intent: 'search_tickets' as const, timestamp: new Date() },
        { intent: 'view_ticket' as const, timestamp: new Date() },
        { intent: 'search_tickets' as const, timestamp: new Date() },
        { intent: 'view_ticket' as const, timestamp: new Date() },
        { intent: 'search_tickets' as const, timestamp: new Date() },
        { intent: 'view_ticket' as const, timestamp: new Date() },
      ];

      manager.analyzeUserBehavior(TEST_USER, intentHistory);

      const stats = manager.getStats();
      expect(stats.total_patterns_detected).toBeGreaterThan(0);
    });
  });

  describe('Events', () => {
    test('should emit pattern_detected event', (done) => {
      const unsubscribe = manager.onEvent('pattern_detected', (event) => {
        expect(event.type).toBe('pattern_detected');
        expect(event.tenant_id).toBe(config.tenant_id);
        unsubscribe();
        done();
      });

      // Need enough data to trigger pattern detection
      const intentHistory = [
        { intent: 'search_tickets' as const, timestamp: new Date() },
        { intent: 'view_ticket' as const, timestamp: new Date() },
        { intent: 'search_tickets' as const, timestamp: new Date() },
        { intent: 'view_ticket' as const, timestamp: new Date() },
        { intent: 'search_tickets' as const, timestamp: new Date() },
        { intent: 'view_ticket' as const, timestamp: new Date() },
        { intent: 'search_tickets' as const, timestamp: new Date() },
        { intent: 'view_ticket' as const, timestamp: new Date() },
      ];

      manager.analyzeUserBehavior(TEST_USER, intentHistory);
    });

    test('should emit anomaly_detected event', (done) => {
      const unsubscribe = manager.onEvent('anomaly_detected', (event) => {
        expect(event.type).toBe('anomaly_detected');
        unsubscribe();
        done();
      });

      manager.checkForAnomalies('ticket_volume', 150, { mean: 100, stdDev: 15 });
    });

    test('should emit anomaly_resolved event', (done) => {
      const anomaly = manager.checkForAnomalies('ticket_volume', 150, { mean: 100, stdDev: 15 });

      const unsubscribe = manager.onEvent('anomaly_resolved', (event) => {
        expect(event.type).toBe('anomaly_resolved');
        unsubscribe();
        done();
      });

      if (anomaly) {
        manager.resolveAnomaly(anomaly.id);
      } else {
        done();
      }
    });

    test('should emit trend_detected event', (done) => {
      const unsubscribe = manager.onEvent('trend_detected', (event) => {
        expect(event.type).toBe('trend_detected');
        unsubscribe();
        done();
      });

      const dataPoints = [
        { timestamp: new Date(Date.now() - 3 * 60 * 60 * 1000), value: 10 },
        { timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000), value: 20 },
        { timestamp: new Date(Date.now() - 1 * 60 * 60 * 1000), value: 30 },
      ];

      manager.analyzeTrend('test_metric', dataPoints);
    });
  });
});

// ── Variant Limits Tests ────────────────────────────────────────────

describe('Variant Limits', () => {
  test('mini_parwa should have limited features', () => {
    const limits = PATTERN_DETECTION_VARIANT_LIMITS['mini_parwa'];

    expect(limits.max_patterns).toBe(10);
    expect(limits.ml_detection).toBe(false);
    expect(limits.predictive_forecasting).toBe(false);
    expect(limits.trend_analysis).toBe(false);
    expect(limits.custom_thresholds).toBe(false);
  });

  test('parwa should have standard features', () => {
    const limits = PATTERN_DETECTION_VARIANT_LIMITS['parwa'];

    expect(limits.max_patterns).toBe(100);
    expect(limits.predictive_forecasting).toBe(true);
    expect(limits.anomaly_detection).toBe(true);
    expect(limits.trend_analysis).toBe(true);
    expect(limits.custom_thresholds).toBe(true);
  });

  test('parwa_high should have all features', () => {
    const limits = PATTERN_DETECTION_VARIANT_LIMITS['parwa_high'];

    expect(limits.max_patterns).toBe(1000);
    expect(limits.ml_detection).toBe(true);
    expect(limits.predictive_forecasting).toBe(true);
    expect(limits.anomaly_detection).toBe(true);
    expect(limits.trend_analysis).toBe(true);
    expect(limits.max_custom_thresholds).toBe(20);
  });

  test('mini_parwa should not have trend analysis', () => {
    const config = createTestConfig('mini_parwa');
    const manager = createPatternDetectionManager(config);

    const dataPoints = [
      { timestamp: new Date(Date.now() - 3 * 60 * 60 * 1000), value: 10 },
      { timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000), value: 20 },
      { timestamp: new Date(Date.now() - 1 * 60 * 60 * 1000), value: 30 },
    ];

    const trend = manager.analyzeTrend('test_metric', dataPoints);
    expect(trend).toBeNull();

    manager.shutdown();
  });
});

// ── Test Summary Export ────────────────────────────────────────────

export {};
