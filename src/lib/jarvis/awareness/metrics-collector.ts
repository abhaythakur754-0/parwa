/**
 * JARVIS Performance Metrics Collector (Week 2 - Phase 1)
 *
 * Collects and manages performance metrics for monitoring.
 * Handles: response times, resolution rates, agent performance, system metrics
 */

import type {
  PerformanceMetric,
  AggregatedMetric,
  MetricAggregation,
  MetricDefinition,
  AwarenessEvent,
} from '@/types/awareness';

// ── Metrics Collector Configuration ──────────────────────────────────

export interface MetricsCollectorConfig {
  tenant_id: string;
  variant: 'mini_parwa' | 'parwa' | 'parwa_high';
  collection_interval_ms: number;
  retention_hours: number;
  max_metrics_per_type: number;
}

// ── Metric Record ────────────────────────────────────────────────────

export interface MetricRecord {
  name: string;
  value: number;
  unit: string;
  tags: Record<string, string>;
  timestamp: Date;
}

// ── Standard Metrics Definitions ──────────────────────────────────────

export const STANDARD_METRICS: MetricDefinition[] = [
  {
    name: 'ticket.response_time',
    display_name: 'Response Time',
    description: 'Time to first response for tickets',
    type: 'timer',
    unit: 'ms',
    aggregation_methods: ['avg', 'p95', 'p99', 'min', 'max'],
    tags: ['channel', 'priority', 'agent_id'],
    variant_limits: {
      mini_parwa: null,
      parwa: null,
      parwa_high: null,
    },
  },
  {
    name: 'ticket.resolution_time',
    display_name: 'Resolution Time',
    description: 'Time to ticket resolution',
    type: 'timer',
    unit: 'ms',
    aggregation_methods: ['avg', 'p95', 'p99'],
    tags: ['channel', 'priority', 'category'],
    variant_limits: {
      mini_parwa: null,
      parwa: null,
      parwa_high: null,
    },
  },
  {
    name: 'ticket.count',
    display_name: 'Ticket Count',
    description: 'Number of tickets',
    type: 'counter',
    unit: 'tickets',
    aggregation_methods: ['sum', 'count'],
    tags: ['status', 'channel', 'priority'],
    variant_limits: {
      mini_parwa: 2000,
      parwa: 5000,
      parwa_high: null,
    },
  },
  {
    name: 'agent.tickets_resolved',
    display_name: 'Tickets Resolved',
    description: 'Number of tickets resolved by agent',
    type: 'counter',
    unit: 'tickets',
    aggregation_methods: ['sum'],
    tags: ['agent_id', 'channel'],
    variant_limits: {
      mini_parwa: null,
      parwa: null,
      parwa_high: null,
    },
  },
  {
    name: 'agent.satisfaction_score',
    display_name: 'Satisfaction Score',
    description: 'Customer satisfaction rating',
    type: 'gauge',
    unit: 'score',
    aggregation_methods: ['avg'],
    tags: ['agent_id'],
    variant_limits: {
      mini_parwa: null,
      parwa: null,
      parwa_high: null,
    },
  },
  {
    name: 'sla.breach_count',
    display_name: 'SLA Breaches',
    description: 'Number of SLA breaches',
    type: 'counter',
    unit: 'breaches',
    aggregation_methods: ['sum'],
    tags: ['priority', 'channel'],
    variant_limits: {
      mini_parwa: null,
      parwa: null,
      parwa_high: null,
    },
  },
  {
    name: 'system.latency',
    display_name: 'System Latency',
    description: 'API response latency',
    type: 'timer',
    unit: 'ms',
    aggregation_methods: ['avg', 'p95', 'p99'],
    tags: ['endpoint', 'method'],
    variant_limits: {
      mini_parwa: null,
      parwa: null,
      parwa_high: null,
    },
  },
  {
    name: 'system.error_rate',
    display_name: 'Error Rate',
    description: 'API error rate percentage',
    type: 'gauge',
    unit: '%',
    aggregation_methods: ['avg'],
    tags: ['endpoint', 'error_type'],
    variant_limits: {
      mini_parwa: null,
      parwa: null,
      parwa_high: null,
    },
  },
  {
    name: 'queue.size',
    display_name: 'Queue Size',
    description: 'Number of items in queue',
    type: 'gauge',
    unit: 'items',
    aggregation_methods: ['avg', 'max'],
    tags: ['queue_type', 'channel'],
    variant_limits: {
      mini_parwa: null,
      parwa: null,
      parwa_high: null,
    },
  },
  {
    name: 'ai.resolution_rate',
    display_name: 'AI Resolution Rate',
    description: 'Percentage of tickets resolved by AI',
    type: 'gauge',
    unit: '%',
    aggregation_methods: ['avg'],
    tags: ['channel', 'category'],
    variant_limits: {
      mini_parwa: null,
      parwa: null,
      parwa_high: null,
    },
  },
];

// ── Metrics Collector Class ──────────────────────────────────────────

export class MetricsCollector {
  private config: MetricsCollectorConfig;
  private metricsBuffer: Map<string, PerformanceMetric[]> = new Map();
  private counters: Map<string, number> = new Map();
  private gauges: Map<string, number> = new Map();
  private collectionInterval: NodeJS.Timeout | null = null;
  private onCollectCallback?: (metrics: PerformanceMetric[]) => void;

  constructor(config: MetricsCollectorConfig) {
    this.config = config;
  }

  /**
   * Start periodic collection
   */
  startCollection(): void {
    if (this.collectionInterval) return;

    this.collectionInterval = setInterval(() => {
      this.collectPeriodicMetrics();
    }, this.config.collection_interval_ms);
  }

  /**
   * Stop periodic collection
   */
  stopCollection(): void {
    if (this.collectionInterval) {
      clearInterval(this.collectionInterval);
      this.collectionInterval = null;
    }
  }

  /**
   * Set callback for collected metrics
   */
  onCollect(callback: (metrics: PerformanceMetric[]) => void): void {
    this.onCollectCallback = callback;
  }

  /**
   * Record a metric
   */
  record(
    name: string,
    value: number,
    unit: string,
    tags: Record<string, string> = {}
  ): void {
    const metric: PerformanceMetric = {
      id: this.generateMetricId(),
      tenant_id: this.config.tenant_id,
      metric_name: name,
      metric_type: this.getMetricType(name),
      value,
      unit,
      tags,
      timestamp: new Date(),
      variant: this.config.variant,
    };

    this.bufferMetric(metric);
  }

  /**
   * Record a timing metric
   */
  recordTiming(
    name: string,
    durationMs: number,
    tags: Record<string, string> = {}
  ): void {
    this.record(name, durationMs, 'ms', tags);
  }

  /**
   * Increment a counter
   */
  incrementCounter(
    name: string,
    increment: number = 1,
    tags: Record<string, string> = {}
  ): void {
    const key = this.getTagsKey(name, tags);
    const current = this.counters.get(key) || 0;
    this.counters.set(key, current + increment);

    this.record(name, current + increment, 'count', tags);
  }

  /**
   * Set a gauge value
   */
  setGauge(
    name: string,
    value: number,
    tags: Record<string, string> = {}
  ): void {
    const key = this.getTagsKey(name, tags);
    this.gauges.set(key, value);

    this.record(name, value, 'value', tags);
  }

  /**
   * Time an operation
   */
  async timeOperation<T>(
    name: string,
    operation: () => Promise<T>,
    tags: Record<string, string> = {}
  ): Promise<T> {
    const start = Date.now();
    try {
      const result = await operation();
      return result;
    } finally {
      const duration = Date.now() - start;
      this.recordTiming(name, duration, tags);
    }
  }

  /**
   * Get metrics by name
   */
  getMetrics(name: string, limit?: number): PerformanceMetric[] {
    const metrics = this.metricsBuffer.get(name) || [];
    return limit ? metrics.slice(-limit) : [...metrics];
  }

  /**
   * Get aggregated metric
   */
  getAggregated(
    name: string,
    aggregation: MetricAggregation,
    periodMs: number,
    tags: Record<string, string> = {}
  ): AggregatedMetric | null {
    const metrics = this.metricsBuffer.get(name) || [];
    const cutoff = new Date(Date.now() - periodMs);

    const periodMetrics = metrics.filter(
      (m) => m.timestamp >= cutoff && this.tagsMatch(m.tags, tags)
    );

    if (periodMetrics.length === 0) return null;

    const values = periodMetrics.map((m) => m.value);
    const aggregatedValue = this.calculateAggregation(values, aggregation);

    return {
      tenant_id: this.config.tenant_id,
      metric_name: name,
      aggregation,
      value: aggregatedValue,
      period: 'minute',
      period_start: cutoff,
      period_end: new Date(),
      sample_count: values.length,
      tags,
    };
  }

  /**
   * Get all current counters
   */
  getCounters(): Map<string, number> {
    return new Map(this.counters);
  }

  /**
   * Get all current gauges
   */
  getGauges(): Map<string, number> {
    return new Map(this.gauges);
  }

  /**
   * Get metrics summary
   */
  getSummary(): {
    totalMetrics: number;
    metricTypes: Record<string, number>;
    oldestTimestamp: Date | null;
    newestTimestamp: Date | null;
  } {
    let totalMetrics = 0;
    const metricTypes: Record<string, number> = {};
    let oldestTimestamp: Date | null = null;
    let newestTimestamp: Date | null = null;

    for (const [name, metrics] of this.metricsBuffer) {
      totalMetrics += metrics.length;
      metricTypes[name] = metrics.length;

      for (const m of metrics) {
        if (!oldestTimestamp || m.timestamp < oldestTimestamp) {
          oldestTimestamp = m.timestamp;
        }
        if (!newestTimestamp || m.timestamp > newestTimestamp) {
          newestTimestamp = m.timestamp;
        }
      }
    }

    return {
      totalMetrics,
      metricTypes,
      oldestTimestamp,
      newestTimestamp,
    };
  }

  /**
   * Clear metrics older than retention period
   */
  cleanup(): void {
    const cutoff = new Date(
      Date.now() - this.config.retention_hours * 60 * 60 * 1000
    );

    for (const [name, metrics] of this.metricsBuffer) {
      const filtered = metrics.filter((m) => m.timestamp >= cutoff);
      this.metricsBuffer.set(name, filtered);
    }
  }

  /**
   * Flush all buffered metrics
   */
  flush(): PerformanceMetric[] {
    const allMetrics: PerformanceMetric[] = [];

    for (const metrics of this.metricsBuffer.values()) {
      allMetrics.push(...metrics);
    }

    return allMetrics;
  }

  // ── Private Methods ────────────────────────────────────────────────

  /**
   * Buffer a metric
   */
  private bufferMetric(metric: PerformanceMetric): void {
    if (!this.metricsBuffer.has(metric.metric_name)) {
      this.metricsBuffer.set(metric.metric_name, []);
    }

    const buffer = this.metricsBuffer.get(metric.metric_name)!;
    buffer.push(metric);

    // Trim buffer if needed
    while (buffer.length > this.config.max_metrics_per_type) {
      buffer.shift();
    }
  }

  /**
   * Collect periodic metrics
   */
  private collectPeriodicMetrics(): void {
    const metrics: PerformanceMetric[] = [];

    // Collect all current gauges
    for (const [key, value] of this.gauges) {
      const [name, tags] = this.parseTagsKey(key);
      metrics.push({
        id: this.generateMetricId(),
        tenant_id: this.config.tenant_id,
        metric_name: name,
        metric_type: 'gauge',
        value,
        unit: 'value',
        tags,
        timestamp: new Date(),
        variant: this.config.variant,
      });
    }

    // Call callback if set
    if (this.onCollectCallback && metrics.length > 0) {
      this.onCollectCallback(metrics);
    }
  }

  /**
   * Get metric type from name
   */
  private getMetricType(name: string): 'counter' | 'gauge' | 'histogram' | 'timer' {
    const definition = STANDARD_METRICS.find((m) => m.name === name);
    return definition?.type || 'gauge';
  }

  /**
   * Generate tags key
   */
  private getTagsKey(name: string, tags: Record<string, string>): string {
    const tagStr = Object.entries(tags)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([k, v]) => `${k}=${v}`)
      .join(',');
    return `${name}:${tagStr}`;
  }

  /**
   * Parse tags key
   */
  private parseTagsKey(key: string): [string, Record<string, string>] {
    const [name, tagStr] = key.split(':');
    const tags: Record<string, string> = {};

    if (tagStr) {
      for (const pair of tagStr.split(',')) {
        const [k, v] = pair.split('=');
        if (k && v) tags[k] = v;
      }
    }

    return [name, tags];
  }

  /**
   * Check if tags match
   */
  private tagsMatch(
    actual: Record<string, string>,
    expected: Record<string, string>
  ): boolean {
    for (const [key, value] of Object.entries(expected)) {
      if (actual[key] !== value) return false;
    }
    return true;
  }

  /**
   * Calculate aggregation
   */
  private calculateAggregation(values: number[], aggregation: MetricAggregation): number {
    if (values.length === 0) return 0;

    switch (aggregation) {
      case 'sum':
        return values.reduce((a, b) => a + b, 0);
      case 'avg':
        return values.reduce((a, b) => a + b, 0) / values.length;
      case 'min':
        return Math.min(...values);
      case 'max':
        return Math.max(...values);
      case 'count':
        return values.length;
      case 'p95':
        return this.percentile(values, 95);
      case 'p99':
        return this.percentile(values, 99);
      default:
        return values[values.length - 1];
    }
  }

  /**
   * Calculate percentile
   */
  private percentile(values: number[], p: number): number {
    const sorted = [...values].sort((a, b) => a - b);
    const index = Math.ceil((p / 100) * sorted.length) - 1;
    return sorted[Math.max(0, index)];
  }

  /**
   * Generate unique metric ID
   */
  private generateMetricId(): string {
    return `metric_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }
}

// ── Factory Function ─────────────────────────────────────────────────

export function createMetricsCollector(config: MetricsCollectorConfig): MetricsCollector {
  return new MetricsCollector(config);
}

// ── Default Configuration by Variant ─────────────────────────────────

export const DEFAULT_METRICS_COLLECTOR_CONFIG: Record<
  string,
  Omit<MetricsCollectorConfig, 'tenant_id'>
> = {
  mini_parwa: {
    variant: 'mini_parwa',
    collection_interval_ms: 60000,
    retention_hours: 24,
    max_metrics_per_type: 100,
  },
  parwa: {
    variant: 'parwa',
    collection_interval_ms: 30000,
    retention_hours: 168, // 7 days
    max_metrics_per_type: 500,
  },
  parwa_high: {
    variant: 'parwa_high',
    collection_interval_ms: 15000,
    retention_hours: 720, // 30 days
    max_metrics_per_type: 1000,
  },
};
