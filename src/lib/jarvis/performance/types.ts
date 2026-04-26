/**
 * JARVIS Performance Types - Week 15 (Phase 4)
 *
 * Types for performance monitoring and optimization.
 */

// ── Performance Metrics ─────────────────────────────────────────────

export interface PerformanceMetric {
  /** Metric ID */
  id: string;
  
  /** Organization ID */
  organizationId: string;
  
  /** Metric name */
  name: string;
  
  /** Metric type */
  type: MetricType;
  
  /** Metric value */
  value: number;
  
  /** Unit (ms, percent, count, etc.) */
  unit: string;
  
  /** Timestamp */
  timestamp: Date;
  
  /** Additional tags */
  tags?: Record<string, string>;
}

export type MetricType =
  | 'latency'
  | 'throughput'
  | 'error_rate'
  | 'cache_hit_rate'
  | 'memory_usage'
  | 'cpu_usage'
  | 'queue_depth'
  | 'connection_count';

// ── Latency Metrics ──────────────────────────────────────────────────

export interface LatencyMetrics {
  /** Minimum latency */
  min: number;
  
  /** Maximum latency */
  max: number;
  
  /** Average latency */
  avg: number;
  
  /** Median latency (p50) */
  p50: number;
  
  /** 95th percentile */
  p95: number;
  
  /** 99th percentile */
  p99: number;
  
  /** Sample size */
  sampleSize: number;
}

// ── Throughput Metrics ───────────────────────────────────────────────

export interface ThroughputMetrics {
  /** Requests per second */
  requestsPerSecond: number;
  
  /** Commands per second */
  commandsPerSecond: number;
  
  /** Events per second */
  eventsPerSecond: number;
  
  /** Peak throughput */
  peakThroughput: number;
  
  /** Average throughput */
  avgThroughput: number;
}

// ── Cache Metrics ────────────────────────────────────────────────────

export interface CacheMetrics {
  /** Total hits */
  hits: number;
  
  /** Total misses */
  misses: number;
  
  /** Hit rate percentage */
  hitRate: number;
  
  /** Evictions */
  evictions: number;
  
  /** Cache size (entries) */
  size: number;
  
  /** Max size */
  maxSize: number;
  
  /** Memory usage (MB) */
  memoryUsage: number;
}

// ── Error Metrics ────────────────────────────────────────────────────

export interface ErrorMetrics {
  /** Total errors */
  total: number;
  
  /** Error rate percentage */
  rate: number;
  
  /** Errors by type */
  byType: Record<string, number>;
  
  /** Errors by component */
  byComponent: Record<string, number>;
  
  /** Last error timestamp */
  lastError?: Date;
  
  /** Last error message */
  lastErrorMessage?: string;
}

// ── Resource Metrics ──────────────────────────────────────────────────

export interface ResourceMetrics {
  /** Memory usage (MB) */
  memoryUsage: number;
  
  /** Memory limit (MB) */
  memoryLimit: number;
  
  /** CPU usage percentage */
  cpuUsage: number;
  
  /** Active connections */
  activeConnections: number;
  
  /** Queue depth */
  queueDepth: number;
  
  /** Uptime (seconds) */
  uptime: number;
}

// ── Component Health ──────────────────────────────────────────────────

export interface ComponentPerformance {
  /** Component name */
  name: string;
  
  /** Health status */
  status: 'healthy' | 'degraded' | 'unhealthy';
  
  /** Latency metrics */
  latency: LatencyMetrics;
  
  /** Error metrics */
  errors: ErrorMetrics;
  
  /** Throughput metrics */
  throughput: ThroughputMetrics;
  
  /** Last check timestamp */
  lastCheck: Date;
}

// ── Performance Thresholds ────────────────────────────────────────────

export interface PerformanceThresholds {
  /** Max acceptable latency (ms) */
  maxLatency: number;
  
  /** Max acceptable p95 latency (ms) */
  maxLatencyP95: number;
  
  /** Min acceptable cache hit rate (%) */
  minCacheHitRate: number;
  
  /** Max acceptable error rate (%) */
  maxErrorRate: number;
  
  /** Max acceptable memory usage (MB) */
  maxMemoryUsage: number;
  
  /** Min acceptable throughput */
  minThroughput: number;
}

// ── Performance Report ────────────────────────────────────────────────

export interface PerformanceReport {
  /** Report ID */
  id: string;
  
  /** Organization ID */
  organizationId: string;
  
  /** Report period */
  period: {
    start: Date;
    end: Date;
  };
  
  /** Overall health score (0-100) */
  healthScore: number;
  
  /** Overall status */
  status: 'healthy' | 'degraded' | 'unhealthy';
  
  /** Component performance */
  components: ComponentPerformance[];
  
  /** Latency summary */
  latency: LatencyMetrics;
  
  /** Throughput summary */
  throughput: ThroughputMetrics;
  
  /** Cache performance */
  cache: CacheMetrics;
  
  /** Error summary */
  errors: ErrorMetrics;
  
  /** Resource usage */
  resources: ResourceMetrics;
  
  /** Threshold violations */
  violations: ThresholdViolation[];
  
  /** Recommendations */
  recommendations: string[];
  
  /** Generated timestamp */
  generatedAt: Date;
}

export interface ThresholdViolation {
  /** Metric name */
  metric: string;
  
  /** Current value */
  currentValue: number;
  
  /** Threshold */
  threshold: number;
  
  /** Severity */
  severity: 'warning' | 'critical';
  
  /** Timestamp */
  timestamp: Date;
}

// ── Performance Alerts ────────────────────────────────────────────────

export interface PerformanceAlert {
  /** Alert ID */
  id: string;
  
  /** Alert type */
  type: 'latency' | 'error_rate' | 'cache' | 'memory' | 'throughput';
  
  /** Severity */
  severity: 'info' | 'warning' | 'critical';
  
  /** Message */
  message: string;
  
  /** Current value */
  currentValue: number;
  
  /** Threshold */
  threshold: number;
  
  /** Component */
  component: string;
  
  /** Timestamp */
  timestamp: Date;
  
  /** Acknowledged */
  acknowledged: boolean;
}

// ── Performance Optimization ──────────────────────────────────────────

export interface OptimizationSuggestion {
  /** Suggestion ID */
  id: string;
  
  /** Type */
  type: 'cache' | 'query' | 'connection' | 'memory' | 'throughput';
  
  /** Priority */
  priority: 'low' | 'medium' | 'high';
  
  /** Description */
  description: string;
  
  /** Expected improvement */
  expectedImprovement: string;
  
  /** Implementation effort */
  effort: 'low' | 'medium' | 'high';
  
  /** Affected components */
  affectedComponents: string[];
}

// ── Default Thresholds ────────────────────────────────────────────────

export const DEFAULT_PERFORMANCE_THRESHOLDS: PerformanceThresholds = {
  maxLatency: 1000,        // 1 second
  maxLatencyP95: 2000,     // 2 seconds
  minCacheHitRate: 80,     // 80%
  maxErrorRate: 5,         // 5%
  maxMemoryUsage: 512,     // 512 MB
  minThroughput: 100,      // 100 requests/second
};
