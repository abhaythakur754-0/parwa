/**
 * JARVIS Historical Data Aggregation (Week 2 - Phase 1)
 *
 * Aggregates historical data for analytics and pattern detection.
 * Handles: metrics aggregation, time-series data, trend analysis
 */

import type {
  AwarenessEvent,
  AggregatedMetric,
  MetricAggregation,
  PerformanceMetric,
} from '@/types/awareness';

// ── Aggregation Configuration ────────────────────────────────────────

export interface AggregatorConfig {
  tenant_id: string;
  retention_days: number;
  aggregation_periods: ('minute' | 'hour' | 'day' | 'week')[];
  max_data_points: number;
}

// ── Time Series Point ────────────────────────────────────────────────

export interface TimeSeriesPoint {
  timestamp: Date;
  value: number;
  count?: number;
}

// ── Data Aggregator Class ────────────────────────────────────────────

export class DataAggregator {
  private config: AggregatorConfig;
  private metricsStore: Map<string, PerformanceMetric[]> = new Map();
  private aggregatedStore: Map<string, AggregatedMetric[]> = new Map();
  private eventStore: Map<string, AwarenessEvent[]> = new Map();

  constructor(config: AggregatorConfig) {
    this.config = config;
  }

  /**
   * Store a metric
   */
  storeMetric(metric: PerformanceMetric): void {
    const key = this.getMetricKey(metric.metric_name, metric.tags);

    if (!this.metricsStore.has(key)) {
      this.metricsStore.set(key, []);
    }

    const metrics = this.metricsStore.get(key)!;
    metrics.push(metric);

    // Trim old data
    this.trimOldData(metrics);
  }

  /**
   * Store an event
   */
  storeEvent(event: AwarenessEvent): void {
    const key = `${event.tenant_id}_${event.type}`;

    if (!this.eventStore.has(key)) {
      this.eventStore.set(key, []);
    }

    const events = this.eventStore.get(key)!;
    events.push(event);

    // Trim old data
    this.trimEvents(events);
  }

  /**
   * Aggregate metrics for a period
   */
  aggregate(
    metricName: string,
    aggregation: MetricAggregation,
    period: 'minute' | 'hour' | 'day' | 'week',
    tags: Record<string, string> = {}
  ): AggregatedMetric | null {
    const key = this.getMetricKey(metricName, tags);
    const metrics = this.metricsStore.get(key);

    if (!metrics || metrics.length === 0) {
      return null;
    }

    const now = new Date();
    const periodStart = this.getPeriodStart(now, period);
    const periodEnd = this.getPeriodEnd(periodStart, period);

    // Filter metrics within period
    const periodMetrics = metrics.filter((m) => {
      const ts = new Date(m.timestamp);
      return ts >= periodStart && ts < periodEnd;
    });

    if (periodMetrics.length === 0) {
      return null;
    }

    // Calculate aggregation
    const values = periodMetrics.map((m) => m.value);
    const aggregatedValue = this.calculateAggregation(values, aggregation);

    const result: AggregatedMetric = {
      tenant_id: this.config.tenant_id,
      metric_name: metricName,
      aggregation,
      value: aggregatedValue,
      period,
      period_start: periodStart,
      period_end: periodEnd,
      sample_count: values.length,
      tags,
    };

    // Cache result
    this.cacheAggregation(result);

    return result;
  }

  /**
   * Get time series data
   */
  getTimeSeries(
    metricName: string,
    period: 'minute' | 'hour' | 'day' | 'week',
    points: number,
    tags: Record<string, string> = {}
  ): TimeSeriesPoint[] {
    const key = this.getMetricKey(metricName, tags);
    const metrics = this.metricsStore.get(key);

    if (!metrics || metrics.length === 0) {
      return [];
    }

    const result: TimeSeriesPoint[] = [];
    const now = new Date();

    for (let i = points - 1; i >= 0; i--) {
      const periodStart = this.getPeriodStart(
        new Date(now.getTime() - this.getPeriodDuration(period) * i),
        period
      );
      const periodEnd = this.getPeriodEnd(periodStart, period);

      const periodMetrics = metrics.filter((m) => {
        const ts = new Date(m.timestamp);
        return ts >= periodStart && ts < periodEnd;
      });

      const values = periodMetrics.map((m) => m.value);
      const avgValue = values.length > 0
        ? values.reduce((a, b) => a + b, 0) / values.length
        : 0;

      result.push({
        timestamp: periodStart,
        value: avgValue,
        count: values.length,
      });
    }

    return result;
  }

  /**
   * Get event counts by type
   */
  getEventCounts(
    eventTypes?: string[],
    period: 'hour' | 'day' | 'week' = 'day'
  ): Record<string, number> {
    const counts: Record<string, number> = {};
    const now = new Date();
    const periodStart = new Date(now.getTime() - this.getPeriodDuration(period));

    for (const [key, events] of this.eventStore) {
      const eventType = key.split('_').slice(1).join('_');

      if (eventTypes && !eventTypes.includes(eventType)) {
        continue;
      }

      const periodEvents = events.filter(
        (e) => new Date(e.timestamp) >= periodStart
      );

      counts[eventType] = periodEvents.length;
    }

    return counts;
  }

  /**
   * Calculate trend (percentage change)
   */
  calculateTrend(
    metricName: string,
    tags: Record<string, string> = {}
  ): { direction: 'up' | 'down' | 'stable'; percentage: number } | null {
    const hourlyData = this.getTimeSeries(metricName, 'hour', 2, tags);

    if (hourlyData.length < 2) {
      return null;
    }

    const current = hourlyData[1].value;
    const previous = hourlyData[0].value;

    if (previous === 0) {
      return { direction: current > 0 ? 'up' : 'stable', percentage: 0 };
    }

    const change = ((current - previous) / previous) * 100;

    return {
      direction: change > 5 ? 'up' : change < -5 ? 'down' : 'stable',
      percentage: Math.round(change * 100) / 100,
    };
  }

  /**
   * Get aggregated metrics from cache
   */
  getCachedAggregations(
    metricName: string,
    period: 'minute' | 'hour' | 'day' | 'week'
  ): AggregatedMetric[] {
    const results: AggregatedMetric[] = [];

    for (const [key, aggregations] of this.aggregatedStore) {
      if (key.startsWith(`${metricName}_${period}`)) {
        results.push(...aggregations);
      }
    }

    return results.sort(
      (a, b) => b.period_start.getTime() - a.period_start.getTime()
    );
  }

  /**
   * Clear old data
   */
  cleanup(): void {
    const cutoff = new Date(
      Date.now() - this.config.retention_days * 24 * 60 * 60 * 1000
    );

    for (const metrics of this.metricsStore.values()) {
      this.trimOldData(metrics, cutoff);
    }

    for (const events of this.eventStore.values()) {
      this.trimEvents(events, cutoff);
    }
  }

  /**
   * Get storage statistics
   */
  getStats(): {
    metricCount: number;
    eventCount: number;
    aggregationCount: number;
    uniqueMetrics: number;
  } {
    let metricCount = 0;
    let eventCount = 0;
    let aggregationCount = 0;

    for (const metrics of this.metricsStore.values()) {
      metricCount += metrics.length;
    }

    for (const events of this.eventStore.values()) {
      eventCount += events.length;
    }

    for (const aggs of this.aggregatedStore.values()) {
      aggregationCount += aggs.length;
    }

    return {
      metricCount,
      eventCount,
      aggregationCount,
      uniqueMetrics: this.metricsStore.size,
    };
  }

  // ── Private Methods ────────────────────────────────────────────────

  /**
   * Get metric storage key
   */
  private getMetricKey(name: string, tags: Record<string, string>): string {
    const tagStr = Object.entries(tags)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([k, v]) => `${k}=${v}`)
      .join(',');
    return `${name}_${tagStr}`;
  }

  /**
   * Trim old data based on retention
   */
  private trimOldData(
    metrics: PerformanceMetric[],
    cutoff?: Date
  ): void {
    const cutoffDate = cutoff || new Date(
      Date.now() - this.config.retention_days * 24 * 60 * 60 * 1000
    );

    while (
      metrics.length > this.config.max_data_points ||
      (metrics[0] && new Date(metrics[0].timestamp) < cutoffDate)
    ) {
      metrics.shift();
    }
  }

  /**
   * Trim old events
   */
  private trimEvents(events: AwarenessEvent[], cutoff?: Date): void {
    const cutoffDate = cutoff || new Date(
      Date.now() - this.config.retention_days * 24 * 60 * 60 * 1000
    );

    while (
      events.length > this.config.max_data_points ||
      (events[0] && new Date(events[0].timestamp) < cutoffDate)
    ) {
      events.shift();
    }
  }

  /**
   * Get period start time
   */
  private getPeriodStart(date: Date, period: 'minute' | 'hour' | 'day' | 'week'): Date {
    const d = new Date(date);

    switch (period) {
      case 'minute':
        d.setSeconds(0, 0);
        break;
      case 'hour':
        d.setMinutes(0, 0, 0);
        break;
      case 'day':
        d.setHours(0, 0, 0, 0);
        break;
      case 'week':
        const day = d.getDay();
        d.setHours(0, 0, 0, 0);
        d.setDate(d.getDate() - day);
        break;
    }

    return d;
  }

  /**
   * Get period end time
   */
  private getPeriodEnd(start: Date, period: 'minute' | 'hour' | 'day' | 'week'): Date {
    const duration = this.getPeriodDuration(period);
    return new Date(start.getTime() + duration);
  }

  /**
   * Get period duration in milliseconds
   */
  private getPeriodDuration(period: 'minute' | 'hour' | 'day' | 'week'): number {
    const durations: Record<string, number> = {
      minute: 60 * 1000,
      hour: 60 * 60 * 1000,
      day: 24 * 60 * 60 * 1000,
      week: 7 * 24 * 60 * 60 * 1000,
    };
    return durations[period];
  }

  /**
   * Calculate aggregation value
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
   * Cache aggregation result
   */
  private cacheAggregation(metric: AggregatedMetric): void {
    const key = `${metric.metric_name}_${metric.period}_${metric.aggregation}`;

    if (!this.aggregatedStore.has(key)) {
      this.aggregatedStore.set(key, []);
    }

    const aggregations = this.aggregatedStore.get(key)!;
    aggregations.push(metric);

    // Keep only recent aggregations
    if (aggregations.length > 100) {
      aggregations.shift();
    }
  }
}

// ── Factory Function ─────────────────────────────────────────────────

export function createDataAggregator(config: AggregatorConfig): DataAggregator {
  return new DataAggregator(config);
}

// ── Default Configuration by Variant ─────────────────────────────────

export const DEFAULT_AGGREGATOR_CONFIG: Record<
  string,
  Omit<AggregatorConfig, 'tenant_id'>
> = {
  mini_parwa: {
    retention_days: 1,
    aggregation_periods: ['hour', 'day'],
    max_data_points: 500,
  },
  parwa: {
    retention_days: 7,
    aggregation_periods: ['minute', 'hour', 'day'],
    max_data_points: 2000,
  },
  parwa_high: {
    retention_days: 30,
    aggregation_periods: ['minute', 'hour', 'day', 'week'],
    max_data_points: 10000,
  },
};
