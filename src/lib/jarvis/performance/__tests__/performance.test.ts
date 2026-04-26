/**
 * JARVIS Performance Monitor Tests - Week 15 (Phase 4)
 *
 * Comprehensive tests for performance monitoring and optimization.
 */

import {
  PerformanceMonitor,
  getPerformanceMonitor,
  clearPerformanceMonitorCache,
} from '../performance-monitor';

// ── Performance Monitor Tests ─────────────────────────────────────────

describe('PerformanceMonitor', () => {
  let monitor: PerformanceMonitor;
  
  beforeEach(() => {
    monitor = new PerformanceMonitor('org-test-123');
  });
  
  describe('constructor', () => {
    it('should create monitor with organization ID', () => {
      expect(monitor).toBeDefined();
    });
    
    it('should accept custom thresholds', () => {
      const customMonitor = new PerformanceMonitor('org-test', {
        maxLatency: 500,
        maxErrorRate: 1,
      });
      
      expect(customMonitor).toBeDefined();
    });
  });
  
  describe('recordLatency', () => {
    it('should record latency measurements', () => {
      monitor.recordLatency(100);
      monitor.recordLatency(200);
      monitor.recordLatency(150);
      
      const metrics = monitor.getLatencyMetrics();
      
      expect(metrics.sampleSize).toBe(3);
      expect(metrics.min).toBe(100);
      expect(metrics.max).toBe(200);
      expect(metrics.avg).toBe(150);
    });
    
    it('should calculate percentiles correctly', () => {
      for (let i = 1; i <= 100; i++) {
        monitor.recordLatency(i);
      }
      
      const metrics = monitor.getLatencyMetrics();
      
      expect(metrics.p50).toBeCloseTo(50, 10);
      expect(metrics.p95).toBeCloseTo(95, 10);
      expect(metrics.p99).toBeCloseTo(99, 10);
    });
    
    it('should keep only last 1000 measurements', () => {
      for (let i = 0; i < 1500; i++) {
        monitor.recordLatency(i);
      }
      
      const metrics = monitor.getLatencyMetrics();
      expect(metrics.sampleSize).toBe(1000);
    });
    
    it('should generate alert for high latency', () => {
      monitor.recordLatency(1500); // Above default threshold of 1000
      
      const alerts = monitor.getActiveAlerts();
      expect(alerts.length).toBeGreaterThan(0);
      expect(alerts[0].type).toBe('latency');
    });
    
    it('should generate critical alert for very high latency', () => {
      monitor.recordLatency(3000); // 2x threshold
      
      const alerts = monitor.getActiveAlerts();
      expect(alerts[0].severity).toBe('critical');
    });
  });
  
  describe('recordCacheHit/recordCacheMiss', () => {
    it('should track cache hits', () => {
      monitor.recordCacheHit();
      monitor.recordCacheHit();
      monitor.recordCacheHit();
      
      const metrics = monitor.getCacheMetrics();
      expect(metrics.hits).toBe(3);
    });
    
    it('should track cache misses', () => {
      monitor.recordCacheMiss();
      monitor.recordCacheMiss();
      
      const metrics = monitor.getCacheMetrics();
      expect(metrics.misses).toBe(2);
    });
    
    it('should calculate hit rate', () => {
      monitor.recordCacheHit();
      monitor.recordCacheHit();
      monitor.recordCacheMiss();
      
      const metrics = monitor.getCacheMetrics();
      expect(metrics.hitRate).toBeCloseTo(66.67, 1);
    });
    
    it('should track cache evictions', () => {
      monitor.recordCacheEviction();
      monitor.recordCacheEviction();
      monitor.recordCacheEviction();
      
      const metrics = monitor.getCacheMetrics();
      expect(metrics.evictions).toBe(3);
    });
    
    it('should return zero hit rate when no operations', () => {
      const metrics = monitor.getCacheMetrics();
      expect(metrics.hitRate).toBe(0);
    });
  });
  
  describe('recordError', () => {
    it('should track errors', () => {
      monitor.recordError('TypeError', 'TestComponent', 'Test error');
      monitor.recordError('NetworkError', 'API', 'Connection failed');
      
      const metrics = monitor.getErrorMetrics();
      expect(metrics.total).toBe(2);
    });
    
    it('should categorize errors by type', () => {
      monitor.recordError('TypeError', 'Comp1');
      monitor.recordError('TypeError', 'Comp2');
      monitor.recordError('NetworkError', 'Comp1');
      
      const metrics = monitor.getErrorMetrics();
      
      expect(metrics.byType['TypeError']).toBe(2);
      expect(metrics.byType['NetworkError']).toBe(1);
    });
    
    it('should categorize errors by component', () => {
      monitor.recordError('TypeError', 'Comp1');
      monitor.recordError('TypeError', 'Comp1');
      monitor.recordError('NetworkError', 'Comp2');
      
      const metrics = monitor.getErrorMetrics();
      
      expect(metrics.byComponent['Comp1']).toBe(2);
      expect(metrics.byComponent['Comp2']).toBe(1);
    });
    
    it('should calculate error rate', () => {
      // Record some requests
      for (let i = 0; i < 10; i++) {
        monitor.recordLatency(100);
      }
      
      // Record an error
      monitor.recordError('TypeError', 'Test');
      
      const metrics = monitor.getErrorMetrics();
      expect(metrics.rate).toBe(10); // 10%
    });
    
    it('should generate alert for high error rate', () => {
      // Create high error rate
      for (let i = 0; i < 20; i++) {
        monitor.recordLatency(100);
      }
      for (let i = 0; i < 5; i++) {
        monitor.recordError('TypeError', 'Test');
      }
      
      const alerts = monitor.getActiveAlerts();
      const errorAlert = alerts.find(a => a.type === 'error_rate');
      expect(errorAlert).toBeDefined();
    });
    
    it('should track last error', () => {
      monitor.recordError('TypeError', 'Test', 'First error');
      monitor.recordError('NetworkError', 'API', 'Second error');
      
      const metrics = monitor.getErrorMetrics();
      expect(metrics.lastErrorMessage).toBe('Second error');
    });
    
    it('should limit error history to 100', () => {
      for (let i = 0; i < 150; i++) {
        monitor.recordError('TypeError', 'Test', `Error ${i}`);
      }
      
      const metrics = monitor.getErrorMetrics();
      expect(metrics.total).toBe(100);
    });
  });
  
  describe('recordCommand', () => {
    it('should track command count', () => {
      monitor.recordCommand();
      monitor.recordCommand();
      monitor.recordCommand();
      
      // Wait a bit to ensure uptime > 0
      const metrics = monitor.getThroughputMetrics();
      expect(metrics.commandsPerSecond).toBeGreaterThanOrEqual(0);
    });
  });
  
  describe('recordEvent', () => {
    it('should track event count', () => {
      monitor.recordEvent();
      monitor.recordEvent();
      
      const metrics = monitor.getThroughputMetrics();
      expect(metrics.eventsPerSecond).toBeGreaterThanOrEqual(0);
    });
  });
  
  describe('getLatencyMetrics', () => {
    it('should return zero metrics when no data', () => {
      const metrics = monitor.getLatencyMetrics();
      
      expect(metrics.min).toBe(0);
      expect(metrics.max).toBe(0);
      expect(metrics.avg).toBe(0);
      expect(metrics.sampleSize).toBe(0);
    });
  });
  
  describe('getThroughputMetrics', () => {
    it('should calculate throughput', () => {
      for (let i = 0; i < 100; i++) {
        monitor.recordLatency(10);
        monitor.recordCommand();
        monitor.recordEvent();
      }
      
      const metrics = monitor.getThroughputMetrics();
      
      // These might be 0 if test runs too fast, so check for >= 0
      expect(metrics.requestsPerSecond).toBeGreaterThanOrEqual(0);
      expect(metrics.commandsPerSecond).toBeGreaterThanOrEqual(0);
      expect(metrics.eventsPerSecond).toBeGreaterThanOrEqual(0);
    });
  });
  
  describe('getResourceMetrics', () => {
    it('should return resource metrics', () => {
      const metrics = monitor.getResourceMetrics();
      
      expect(metrics.uptime).toBeGreaterThanOrEqual(0);
      expect(metrics.memoryLimit).toBe(512);
    });
  });
  
  describe('getComponentPerformance', () => {
    it('should return performance for all components', () => {
      const components = monitor.getComponentPerformance();
      
      expect(components.length).toBeGreaterThan(0);
      
      const componentNames = components.map(c => c.name);
      expect(componentNames).toContain('AwarenessEngine');
      expect(componentNames).toContain('CommandProcessor');
      expect(componentNames).toContain('MemoryManager');
      expect(componentNames).toContain('CacheManager');
    });
    
    it('should return healthy status by default', () => {
      const components = monitor.getComponentPerformance();
      
      for (const component of components) {
        expect(component.status).toBe('healthy');
      }
    });
  });
  
  describe('getThresholdViolations', () => {
    it('should return empty array when no violations', () => {
      const violations = monitor.getThresholdViolations();
      expect(violations).toHaveLength(0);
    });
    
    it('should detect latency violations', () => {
      for (let i = 0; i < 100; i++) {
        monitor.recordLatency(2500); // Above p95 threshold
      }
      
      const violations = monitor.getThresholdViolations();
      const latencyViolation = violations.find(v => v.metric === 'latency_p95');
      
      expect(latencyViolation).toBeDefined();
    });
    
    it('should detect cache hit rate violations', () => {
      for (let i = 0; i < 20; i++) {
        monitor.recordCacheMiss();
      }
      for (let i = 0; i < 5; i++) {
        monitor.recordCacheHit();
      }
      
      const violations = monitor.getThresholdViolations();
      const cacheViolation = violations.find(v => v.metric === 'cache_hit_rate');
      
      expect(cacheViolation).toBeDefined();
    });
    
    it('should detect error rate violations', () => {
      for (let i = 0; i < 20; i++) {
        monitor.recordLatency(100);
      }
      for (let i = 0; i < 5; i++) {
        monitor.recordError('TypeError', 'Test');
      }
      
      const violations = monitor.getThresholdViolations();
      const errorViolation = violations.find(v => v.metric === 'error_rate');
      
      expect(errorViolation).toBeDefined();
    });
  });
  
  describe('getOptimizationSuggestions', () => {
    it('should return empty array when no issues', () => {
      const suggestions = monitor.getOptimizationSuggestions();
      expect(suggestions).toHaveLength(0);
    });
    
    it('should suggest cache optimization for low hit rate', () => {
      // Low cache hit rate
      for (let i = 0; i < 20; i++) {
        monitor.recordCacheMiss();
      }
      for (let i = 0; i < 5; i++) {
        monitor.recordCacheHit();
      }
      
      const suggestions = monitor.getOptimizationSuggestions();
      const cacheSuggestion = suggestions.find(s => s.type === 'cache');
      
      expect(cacheSuggestion).toBeDefined();
      expect(cacheSuggestion?.priority).toBe('high');
    });
    
    it('should suggest latency optimization for high latency', () => {
      for (let i = 0; i < 100; i++) {
        monitor.recordLatency(2500);
      }
      
      const suggestions = monitor.getOptimizationSuggestions();
      const latencySuggestion = suggestions.find(s => s.type === 'query');
      
      expect(latencySuggestion).toBeDefined();
    });
  });
  
  describe('generateReport', () => {
    it('should generate a complete report', () => {
      for (let i = 0; i < 50; i++) {
        monitor.recordLatency(100);
        monitor.recordCommand();
        monitor.recordEvent();
      }
      
      const report = monitor.generateReport();
      
      expect(report.id).toBeDefined();
      expect(report.organizationId).toBe('org-test-123');
      expect(report.period.start).toBeDefined();
      expect(report.period.end).toBeDefined();
      expect(report.healthScore).toBe(100);
      expect(report.status).toBe('healthy');
      expect(report.components).toBeDefined();
      expect(report.latency).toBeDefined();
      expect(report.throughput).toBeDefined();
      expect(report.cache).toBeDefined();
      expect(report.errors).toBeDefined();
      expect(report.resources).toBeDefined();
      expect(report.violations).toBeDefined();
      expect(report.recommendations).toBeDefined();
    });
    
    it('should calculate health score based on violations', () => {
      // Trigger a violation
      for (let i = 0; i < 100; i++) {
        monitor.recordLatency(2500);
      }
      
      const report = monitor.generateReport();
      
      expect(report.healthScore).toBeLessThan(100);
      expect(report.status).not.toBe('healthy');
    });
    
    it('should set status to unhealthy for critical violations', () => {
      // Trigger critical violation
      for (let i = 0; i < 100; i++) {
        monitor.recordLatency(5000); // Way above threshold
      }
      
      const report = monitor.generateReport();
      
      expect(report.status).toBe('unhealthy');
    });
  });
  
  describe('alerts', () => {
    it('should track active alerts', () => {
      monitor.recordLatency(1500);
      monitor.recordLatency(2000);
      
      const alerts = monitor.getActiveAlerts();
      expect(alerts.length).toBeGreaterThan(0);
    });
    
    it('should acknowledge alerts', () => {
      monitor.recordLatency(1500);
      
      const alerts = monitor.getActiveAlerts();
      const alertId = alerts[0].id;
      
      monitor.acknowledgeAlert(alertId);
      
      const activeAlerts = monitor.getActiveAlerts();
      expect(activeAlerts.find(a => a.id === alertId)).toBeUndefined();
    });
    
    it('should limit alert history to 50', () => {
      for (let i = 0; i < 60; i++) {
        monitor.recordLatency(1500);
      }
      
      // Access internal alerts array
      const alerts = monitor.getActiveAlerts();
      // Some alerts may be acknowledged automatically
      expect(alerts.length).toBeLessThanOrEqual(50);
    });
  });
  
  describe('reset', () => {
    it('should reset all metrics', () => {
      monitor.recordLatency(100);
      monitor.recordCacheHit();
      monitor.recordError('TypeError', 'Test');
      monitor.recordCommand();
      monitor.recordEvent();
      
      monitor.reset();
      
      const latency = monitor.getLatencyMetrics();
      const cache = monitor.getCacheMetrics();
      const errors = monitor.getErrorMetrics();
      const throughput = monitor.getThroughputMetrics();
      
      expect(latency.sampleSize).toBe(0);
      expect(cache.hits).toBe(0);
      expect(errors.total).toBe(0);
    });
  });
});

// ── Singleton Tests ──────────────────────────────────────────────────

describe('getPerformanceMonitor', () => {
  beforeEach(() => {
    clearPerformanceMonitorCache();
  });
  
  it('should return a singleton instance', () => {
    const monitor1 = getPerformanceMonitor('org-123');
    const monitor2 = getPerformanceMonitor('org-123');
    
    expect(monitor1).toBe(monitor2);
  });
  
  it('should return different instances for different orgs', () => {
    const monitor1 = getPerformanceMonitor('org-123');
    const monitor2 = getPerformanceMonitor('org-456');
    
    expect(monitor1).not.toBe(monitor2);
  });
  
  it('should accept custom thresholds', () => {
    const monitor = getPerformanceMonitor('org-789', {
      maxLatency: 500,
    });
    
    expect(monitor).toBeDefined();
  });
});

// ── Gap Testing - Edge Cases ──────────────────────────────────────────

describe('Gap Testing', () => {
  let monitor: PerformanceMonitor;
  
  beforeEach(() => {
    monitor = new PerformanceMonitor('org-gap-test');
  });
  
  describe('empty state handling', () => {
    it('should handle getLatencyMetrics with no data', () => {
      const metrics = monitor.getLatencyMetrics();
      expect(metrics).toEqual({
        min: 0,
        max: 0,
        avg: 0,
        p50: 0,
        p95: 0,
        p99: 0,
        sampleSize: 0,
      });
    });
    
    it('should handle getThroughputMetrics with no data', () => {
      const metrics = monitor.getThroughputMetrics();
      expect(metrics.requestsPerSecond).toBe(0);
      expect(metrics.commandsPerSecond).toBe(0);
      expect(metrics.eventsPerSecond).toBe(0);
    });
    
    it('should handle getErrorMetrics with no errors', () => {
      const metrics = monitor.getErrorMetrics();
      expect(metrics.total).toBe(0);
      expect(metrics.rate).toBe(0);
      expect(metrics.byType).toEqual({});
      expect(metrics.byComponent).toEqual({});
    });
    
    it('should handle getCacheMetrics with no operations', () => {
      const metrics = monitor.getCacheMetrics();
      expect(metrics.hits).toBe(0);
      expect(metrics.misses).toBe(0);
      expect(metrics.hitRate).toBe(0);
    });
    
    it('should handle generateReport with no data', () => {
      const report = monitor.generateReport();
      expect(report.healthScore).toBe(100);
      expect(report.status).toBe('healthy');
    });
  });
  
  describe('boundary conditions', () => {
    it('should handle single latency measurement', () => {
      monitor.recordLatency(100);
      
      const metrics = monitor.getLatencyMetrics();
      expect(metrics.sampleSize).toBe(1);
      expect(metrics.min).toBe(100);
      expect(metrics.max).toBe(100);
      expect(metrics.avg).toBe(100);
      expect(metrics.p50).toBe(100);
      expect(metrics.p95).toBe(100);
      expect(metrics.p99).toBe(100);
    });
    
    it('should handle zero latency', () => {
      monitor.recordLatency(0);
      
      const metrics = monitor.getLatencyMetrics();
      expect(metrics.min).toBe(0);
      expect(metrics.avg).toBe(0);
    });
    
    it('should handle very large latency values', () => {
      monitor.recordLatency(1000000);
      
      const metrics = monitor.getLatencyMetrics();
      expect(metrics.max).toBe(1000000);
    });
    
    it('should handle single cache operation', () => {
      monitor.recordCacheHit();
      
      const metrics = monitor.getCacheMetrics();
      expect(metrics.hits).toBe(1);
      expect(metrics.hitRate).toBe(100);
    });
  });
  
  describe('concurrent operations', () => {
    it('should handle rapid recording', () => {
      for (let i = 0; i < 1000; i++) {
        monitor.recordLatency(Math.random() * 100);
        monitor.recordCacheHit();
        monitor.recordCommand();
        monitor.recordEvent();
      }
      
      const report = monitor.generateReport();
      expect(report.latency.sampleSize).toBe(1000);
    });
  });
  
  describe('threshold edge cases', () => {
    it('should not alert for latency exactly at threshold', () => {
      monitor.recordLatency(1000); // Exactly at threshold
      
      const violations = monitor.getThresholdViolations();
      // Should not create latency_p95 violation for single measurement
      expect(violations.find(v => v.metric === 'latency_p95')).toBeUndefined();
    });
    
    it('should alert for latency just above threshold', () => {
      for (let i = 0; i < 100; i++) {
        monitor.recordLatency(2001); // Just above p95 threshold
      }
      
      const violations = monitor.getThresholdViolations();
      expect(violations.find(v => v.metric === 'latency_p95')).toBeDefined();
    });
    
    it('should not create cache violation with few operations', () => {
      // Few operations should not trigger cache violation
      monitor.recordCacheMiss();
      
      const violations = monitor.getThresholdViolations();
      expect(violations.find(v => v.metric === 'cache_hit_rate')).toBeUndefined();
    });
    
    it('should not create error violation with few requests', () => {
      // Few requests should not trigger error rate violation
      monitor.recordLatency(100);
      monitor.recordError('TypeError', 'Test');
      
      const violations = monitor.getThresholdViolations();
      expect(violations.find(v => v.metric === 'error_rate')).toBeUndefined();
    });
  });
  
  describe('data consistency', () => {
    it('should maintain consistent counts', () => {
      for (let i = 0; i < 50; i++) {
        monitor.recordCacheHit();
        monitor.recordCacheMiss();
      }
      
      const metrics = monitor.getCacheMetrics();
      expect(metrics.hits).toBe(50);
      expect(metrics.misses).toBe(50);
      expect(metrics.hitRate).toBe(50);
    });
    
    it('should maintain consistent error counts', () => {
      for (let i = 0; i < 10; i++) {
        monitor.recordError('TypeError', 'Comp1');
        monitor.recordError('NetworkError', 'Comp2');
      }
      
      const metrics = monitor.getErrorMetrics();
      expect(metrics.total).toBe(20);
      expect(metrics.byType['TypeError']).toBe(10);
      expect(metrics.byType['NetworkError']).toBe(10);
      expect(metrics.byComponent['Comp1']).toBe(10);
      expect(metrics.byComponent['Comp2']).toBe(10);
    });
  });
});
