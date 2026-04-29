/**
 * JARVIS Performance Monitor - Week 15 (Phase 4)
 *
 * Monitors and optimizes JARVIS performance.
 */

import type {
  PerformanceMetric,
  LatencyMetrics,
  ThroughputMetrics,
  CacheMetrics,
  ErrorMetrics,
  ResourceMetrics,
  ComponentPerformance,
  PerformanceThresholds,
  PerformanceReport,
  ThresholdViolation,
  PerformanceAlert,
  OptimizationSuggestion,
} from './types';

// ── Performance Monitor ──────────────────────────────────────────────

export class PerformanceMonitor {
  private organizationId: string;
  private thresholds: PerformanceThresholds;
  private metrics: PerformanceMetric[] = [];
  private latencies: number[] = [];
  private errors: Array<{ type: string; component: string; timestamp: Date; message: string }> = [];
  private cacheHits = 0;
  private cacheMisses = 0;
  private cacheEvictions = 0;
  private requestCount = 0;
  private commandCount = 0;
  private eventCount = 0;
  private startTime: Date;
  private alerts: PerformanceAlert[] = [];
  
  constructor(organizationId: string, thresholds?: Partial<PerformanceThresholds>) {
    this.organizationId = organizationId;
    this.thresholds = {
      ...DEFAULT_PERFORMANCE_THRESHOLDS,
      ...thresholds,
    };
    this.startTime = new Date();
  }
  
  /**
   * Record a latency measurement
   */
  recordLatency(latencyMs: number): void {
    this.latencies.push(latencyMs);
    this.requestCount++;
    
    // Keep only last 1000 measurements
    if (this.latencies.length > 1000) {
      this.latencies.shift();
    }
    
    // Check threshold
    if (latencyMs > this.thresholds.maxLatency) {
      this.addAlert({
        type: 'latency',
        severity: latencyMs > this.thresholds.maxLatency * 2 ? 'critical' : 'warning',
        message: `High latency detected: ${latencyMs}ms (threshold: ${this.thresholds.maxLatency}ms)`,
        currentValue: latencyMs,
        threshold: this.thresholds.maxLatency,
        component: 'request',
      });
    }
  }
  
  /**
   * Record a cache hit
   */
  recordCacheHit(): void {
    this.cacheHits++;
  }
  
  /**
   * Record a cache miss
   */
  recordCacheMiss(): void {
    this.cacheMisses++;
  }
  
  /**
   * Record a cache eviction
   */
  recordCacheEviction(): void {
    this.cacheEvictions++;
  }
  
  /**
   * Record an error
   */
  recordError(type: string, component: string, message?: string): void {
    this.errors.push({
      type,
      component,
      timestamp: new Date(),
      message: message || '',
    });
    
    // Keep only last 100 errors
    if (this.errors.length > 100) {
      this.errors.shift();
    }
    
    // Check error rate threshold
    const errorRate = this.getErrorMetrics().rate;
    if (errorRate > this.thresholds.maxErrorRate) {
      this.addAlert({
        type: 'error_rate',
        severity: errorRate > this.thresholds.maxErrorRate * 2 ? 'critical' : 'warning',
        message: `High error rate: ${errorRate.toFixed(2)}% (threshold: ${this.thresholds.maxErrorRate}%)`,
        currentValue: errorRate,
        threshold: this.thresholds.maxErrorRate,
        component,
      });
    }
  }
  
  /**
   * Record a command execution
   */
  recordCommand(): void {
    this.commandCount++;
  }
  
  /**
   * Record an event
   */
  recordEvent(): void {
    this.eventCount++;
  }
  
  /**
   * Get latency metrics
   */
  getLatencyMetrics(): LatencyMetrics {
    if (this.latencies.length === 0) {
      return {
        min: 0,
        max: 0,
        avg: 0,
        p50: 0,
        p95: 0,
        p99: 0,
        sampleSize: 0,
      };
    }
    
    const sorted = [...this.latencies].sort((a, b) => a - b);
    const sum = sorted.reduce((a, b) => a + b, 0);
    
    return {
      min: sorted[0],
      max: sorted[sorted.length - 1],
      avg: sum / sorted.length,
      p50: this.percentile(sorted, 50),
      p95: this.percentile(sorted, 95),
      p99: this.percentile(sorted, 99),
      sampleSize: sorted.length,
    };
  }
  
  /**
   * Get throughput metrics
   */
  getThroughputMetrics(): ThroughputMetrics {
    const uptimeSeconds = (Date.now() - this.startTime.getTime()) / 1000;
    
    return {
      requestsPerSecond: uptimeSeconds > 0 ? this.requestCount / uptimeSeconds : 0,
      commandsPerSecond: uptimeSeconds > 0 ? this.commandCount / uptimeSeconds : 0,
      eventsPerSecond: uptimeSeconds > 0 ? this.eventCount / uptimeSeconds : 0,
      peakThroughput: this.requestCount, // Simplified
      avgThroughput: uptimeSeconds > 0 ? this.requestCount / uptimeSeconds : 0,
    };
  }
  
  /**
   * Get cache metrics
   */
  getCacheMetrics(): CacheMetrics {
    const total = this.cacheHits + this.cacheMisses;
    
    return {
      hits: this.cacheHits,
      misses: this.cacheMisses,
      hitRate: total > 0 ? (this.cacheHits / total) * 100 : 0,
      evictions: this.cacheEvictions,
      size: 0, // Would need cache implementation
      maxSize: 1000, // Default
      memoryUsage: 0, // Would need memory measurement
    };
  }
  
  /**
   * Get error metrics
   */
  getErrorMetrics(): ErrorMetrics {
    const byType: Record<string, number> = {};
    const byComponent: Record<string, number> = {};
    
    for (const error of this.errors) {
      byType[error.type] = (byType[error.type] || 0) + 1;
      byComponent[error.component] = (byComponent[error.component] || 0) + 1;
    }
    
    const errorRate = this.requestCount > 0 
      ? (this.errors.length / this.requestCount) * 100 
      : 0;
    
    const lastError = this.errors[this.errors.length - 1];
    
    return {
      total: this.errors.length,
      rate: errorRate,
      byType,
      byComponent,
      lastError: lastError?.timestamp,
      lastErrorMessage: lastError?.message,
    };
  }
  
  /**
   * Get resource metrics
   */
  getResourceMetrics(): ResourceMetrics {
    // In a real implementation, these would come from actual monitoring
    const memoryUsage = process.memoryUsage?.()?.heapUsed 
      ? process.memoryUsage().heapUsed / 1024 / 1024 
      : 0;
    
    const uptime = (Date.now() - this.startTime.getTime()) / 1000;
    
    return {
      memoryUsage,
      memoryLimit: 512, // Default
      cpuUsage: 0, // Would need actual CPU measurement
      activeConnections: 0, // Would need connection tracking
      queueDepth: 0, // Would need queue monitoring
      uptime,
    };
  }
  
  /**
   * Get component performance
   */
  getComponentPerformance(): ComponentPerformance[] {
    const components: ComponentPerformance[] = [];
    
    // Awareness Engine
    components.push({
      name: 'AwarenessEngine',
      status: 'healthy',
      latency: this.getLatencyMetrics(),
      errors: this.getErrorMetrics(),
      throughput: this.getThroughputMetrics(),
      lastCheck: new Date(),
    });
    
    // Command Processor
    components.push({
      name: 'CommandProcessor',
      status: 'healthy',
      latency: this.getLatencyMetrics(),
      errors: this.getErrorMetrics(),
      throughput: this.getThroughputMetrics(),
      lastCheck: new Date(),
    });
    
    // Memory Manager
    components.push({
      name: 'MemoryManager',
      status: 'healthy',
      latency: this.getLatencyMetrics(),
      errors: this.getErrorMetrics(),
      throughput: this.getThroughputMetrics(),
      lastCheck: new Date(),
    });
    
    // Cache
    components.push({
      name: 'CacheManager',
      status: this.cacheHits + this.cacheMisses > 0 
        ? (this.cacheHits / (this.cacheHits + this.cacheMisses)) * 100 >= this.thresholds.minCacheHitRate 
          ? 'healthy' 
          : 'degraded'
        : 'healthy',
      latency: this.getLatencyMetrics(),
      errors: this.getErrorMetrics(),
      throughput: this.getThroughputMetrics(),
      lastCheck: new Date(),
    });
    
    return components;
  }
  
  /**
   * Get threshold violations
   */
  getThresholdViolations(): ThresholdViolation[] {
    const violations: ThresholdViolation[] = [];
    
    const latency = this.getLatencyMetrics();
    const cache = this.getCacheMetrics();
    const errors = this.getErrorMetrics();
    
    // Check latency
    if (latency.p95 > this.thresholds.maxLatencyP95) {
      violations.push({
        metric: 'latency_p95',
        currentValue: latency.p95,
        threshold: this.thresholds.maxLatencyP95,
        severity: latency.p95 > this.thresholds.maxLatencyP95 * 2 ? 'critical' : 'warning',
        timestamp: new Date(),
      });
    }
    
    // Check cache hit rate
    if (cache.hitRate < this.thresholds.minCacheHitRate && this.cacheHits + this.cacheMisses > 10) {
      violations.push({
        metric: 'cache_hit_rate',
        currentValue: cache.hitRate,
        threshold: this.thresholds.minCacheHitRate,
        severity: cache.hitRate < this.thresholds.minCacheHitRate / 2 ? 'critical' : 'warning',
        timestamp: new Date(),
      });
    }
    
    // Check error rate
    if (errors.rate > this.thresholds.maxErrorRate && this.requestCount > 10) {
      violations.push({
        metric: 'error_rate',
        currentValue: errors.rate,
        threshold: this.thresholds.maxErrorRate,
        severity: errors.rate > this.thresholds.maxErrorRate * 2 ? 'critical' : 'warning',
        timestamp: new Date(),
      });
    }
    
    return violations;
  }
  
  /**
   * Get optimization suggestions
   */
  getOptimizationSuggestions(): OptimizationSuggestion[] {
    const suggestions: OptimizationSuggestion[] = [];
    
    const cache = this.getCacheMetrics();
    const latency = this.getLatencyMetrics();
    const throughput = this.getThroughputMetrics();
    
    // Cache optimization
    if (cache.hitRate < this.thresholds.minCacheHitRate && this.cacheHits + this.cacheMisses > 10) {
      suggestions.push({
        id: 'opt-cache-1',
        type: 'cache',
        priority: 'high',
        description: 'Cache hit rate is below threshold. Consider increasing cache size or TTL.',
        expectedImprovement: '10-30% reduction in latency',
        effort: 'low',
        affectedComponents: ['CacheManager'],
      });
    }
    
    // Latency optimization
    if (latency.p95 > this.thresholds.maxLatencyP95) {
      suggestions.push({
        id: 'opt-latency-1',
        type: 'query',
        priority: 'high',
        description: 'High latency detected. Consider optimizing slow queries or adding indexes.',
        expectedImprovement: '20-50% reduction in latency',
        effort: 'medium',
        affectedComponents: ['CommandProcessor', 'MemoryManager'],
      });
    }
    
    // Throughput optimization
    if (throughput.requestsPerSecond < this.thresholds.minThroughput && this.requestCount > 10) {
      suggestions.push({
        id: 'opt-throughput-1',
        type: 'throughput',
        priority: 'medium',
        description: 'Low throughput detected. Consider scaling resources or optimizing bottlenecks.',
        expectedImprovement: '50-100% increase in throughput',
        effort: 'high',
        affectedComponents: ['AwarenessEngine', 'CommandProcessor'],
      });
    }
    
    return suggestions;
  }
  
  /**
   * Generate performance report
   */
  generateReport(): PerformanceReport {
    const violations = this.getThresholdViolations();
    const hasCritical = violations.some(v => v.severity === 'critical');
    const hasWarning = violations.some(v => v.severity === 'warning');
    
    // Calculate health score (0-100)
    let healthScore = 100;
    for (const violation of violations) {
      if (violation.severity === 'critical') {
        healthScore -= 20;
      } else {
        healthScore -= 10;
      }
    }
    healthScore = Math.max(0, healthScore);
    
    return {
      id: `report-${Date.now()}`,
      organizationId: this.organizationId,
      period: {
        start: this.startTime,
        end: new Date(),
      },
      healthScore,
      status: hasCritical ? 'unhealthy' : hasWarning ? 'degraded' : 'healthy',
      components: this.getComponentPerformance(),
      latency: this.getLatencyMetrics(),
      throughput: this.getThroughputMetrics(),
      cache: this.getCacheMetrics(),
      errors: this.getErrorMetrics(),
      resources: this.getResourceMetrics(),
      violations,
      recommendations: this.getOptimizationSuggestions().map(s => s.description),
      generatedAt: new Date(),
    };
  }
  
  /**
   * Get active alerts
   */
  getActiveAlerts(): PerformanceAlert[] {
    return this.alerts.filter(a => !a.acknowledged);
  }
  
  /**
   * Acknowledge an alert
   */
  acknowledgeAlert(alertId: string): void {
    const alert = this.alerts.find(a => a.id === alertId);
    if (alert) {
      alert.acknowledged = true;
    }
  }
  
  /**
   * Reset metrics
   */
  reset(): void {
    this.latencies = [];
    this.errors = [];
    this.cacheHits = 0;
    this.cacheMisses = 0;
    this.cacheEvictions = 0;
    this.requestCount = 0;
    this.commandCount = 0;
    this.eventCount = 0;
    this.alerts = [];
    this.startTime = new Date();
  }
  
  // ── Private Methods ────────────────────────────────────────────────
  
  private percentile(sorted: number[], p: number): number {
    if (sorted.length === 0) return 0;
    
    const index = Math.ceil((p / 100) * sorted.length) - 1;
    return sorted[Math.max(0, index)];
  }
  
  private addAlert(alert: Omit<PerformanceAlert, 'id' | 'timestamp' | 'acknowledged'>): void {
    this.alerts.push({
      ...alert,
      id: `alert-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`,
      timestamp: new Date(),
      acknowledged: false,
    });
    
    // Keep only last 50 alerts
    if (this.alerts.length > 50) {
      this.alerts.shift();
    }
  }
}

// ── Default Thresholds ────────────────────────────────────────────────

const DEFAULT_PERFORMANCE_THRESHOLDS: PerformanceThresholds = {
  maxLatency: 1000,
  maxLatencyP95: 2000,
  minCacheHitRate: 80,
  maxErrorRate: 5,
  maxMemoryUsage: 512,
  minThroughput: 100,
};

// ── Singleton Cache ───────────────────────────────────────────────────

const monitorCache = new Map<string, PerformanceMonitor>();

/**
 * Get or create a performance monitor for an organization
 */
export function getPerformanceMonitor(
  organizationId: string,
  thresholds?: Partial<PerformanceThresholds>
): PerformanceMonitor {
  let monitor = monitorCache.get(organizationId);
  
  if (!monitor) {
    monitor = new PerformanceMonitor(organizationId, thresholds);
    monitorCache.set(organizationId, monitor);
  }
  
  return monitor;
}

/**
 * Clear performance monitor cache
 */
export function clearPerformanceMonitorCache(): void {
  monitorCache.clear();
}
