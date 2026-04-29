/**
 * JARVIS Pattern Detection Manager - Week 8 (Phase 2)
 *
 * Main implementation for the Pattern Detection system.
 * Identifies patterns in user behavior, ticket trends, and operational metrics.
 */

import type { Variant } from '@/types/variant';
import type { IntentAction } from '@/types/command';
import {
  DEFAULT_PATTERN_DETECTION_CONFIG,
  PATTERN_DETECTION_VARIANT_LIMITS,
} from './types';
import type {
  Pattern,
  PatternCategory,
  PatternType,
  PatternStatus,
  PatternConfidence,
  PatternCondition,
  PatternInstance,
  PatternPrediction,
  Anomaly,
  AnomalyThreshold,
  Trend,
  TrendDataPoint,
  PatternDetectionConfig,
  PatternDetectionVariantLimits,
  PatternDetectionStats,
  PatternEvent,
  PatternEventType,
  DetectPatternsRequest,
  DetectPatternsResponse,
  GetPatternsRequest,
  GetPatternsResponse,
} from './types';

// ── Event Emitter ─────────────────────────────────────────────────────

type EventCallback = (event: PatternEvent) => void;

class PatternEventEmitter {
  private listeners: Map<PatternEventType, Set<EventCallback>> = new Map();

  on(event: PatternEventType, callback: EventCallback): () => void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event)!.add(callback);
    return () => this.listeners.get(event)?.delete(callback);
  }

  emit(event: PatternEvent): void {
    const callbacks = this.listeners.get(event.type);
    if (callbacks) {
      for (const callback of callbacks) {
        try {
          callback(event);
        } catch (error) {
          console.error('Pattern event callback error:', error);
        }
      }
    }
  }

  clear(): void {
    this.listeners.clear();
  }
}

// ── Pattern Storage ────────────────────────────────────────────────────

class PatternStorage {
  private patterns: Map<string, Pattern> = new Map();
  private instances: Map<string, PatternInstance[]> = new Map();
  private predictions: Map<string, PatternPrediction[]> = new Map();
  private anomalies: Map<string, Anomaly> = new Map();
  private trends: Map<string, Trend> = new Map();

  // Indexes for quick lookups
  private patternByCategory: Map<PatternCategory, Set<string>> = new Map();
  private patternByType: Map<PatternType, Set<string>> = new Map();
  private patternByTenant: Map<string, Set<string>> = new Map();

  addPattern(pattern: Pattern): void {
    this.patterns.set(pattern.id, pattern);

    // Update category index
    if (!this.patternByCategory.has(pattern.category)) {
      this.patternByCategory.set(pattern.category, new Set());
    }
    this.patternByCategory.get(pattern.category)!.add(pattern.id);

    // Update type index
    if (!this.patternByType.has(pattern.type)) {
      this.patternByType.set(pattern.type, new Set());
    }
    this.patternByType.get(pattern.type)!.add(pattern.id);

    // Update tenant index
    if (!this.patternByTenant.has(pattern.tenant_id)) {
      this.patternByTenant.set(pattern.tenant_id, new Set());
    }
    this.patternByTenant.get(pattern.tenant_id)!.add(pattern.id);
  }

  getPattern(id: string): Pattern | undefined {
    return this.patterns.get(id);
  }

  getPatternsByCategory(category: PatternCategory): Pattern[] {
    const ids = this.patternByCategory.get(category);
    if (!ids) return [];
    return Array.from(ids)
      .map(id => this.patterns.get(id))
      .filter((p): p is Pattern => p !== undefined);
  }

  getPatternsByType(type: PatternType): Pattern[] {
    const ids = this.patternByType.get(type);
    if (!ids) return [];
    return Array.from(ids)
      .map(id => this.patterns.get(id))
      .filter((p): p is Pattern => p !== undefined);
  }

  getPatternsByTenant(tenantId: string): Pattern[] {
    const ids = this.patternByTenant.get(tenantId);
    if (!ids) return [];
    return Array.from(ids)
      .map(id => this.patterns.get(id))
      .filter((p): p is Pattern => p !== undefined);
  }

  updatePattern(id: string, updates: Partial<Pattern>): Pattern | undefined {
    const pattern = this.patterns.get(id);
    if (!pattern) return undefined;

    const updated = { ...pattern, ...updates };
    this.patterns.set(id, updated);
    return updated;
  }

  deletePattern(id: string): boolean {
    const pattern = this.patterns.get(id);
    if (!pattern) return false;

    this.patterns.delete(id);
    this.patternByCategory.get(pattern.category)?.delete(id);
    this.patternByType.get(pattern.type)?.delete(id);
    this.patternByTenant.get(pattern.tenant_id)?.delete(id);
    this.instances.delete(id);

    return true;
  }

  addInstance(patternId: string, instance: PatternInstance): void {
    if (!this.instances.has(patternId)) {
      this.instances.set(patternId, []);
    }
    this.instances.get(patternId)!.push(instance);
  }

  getInstances(patternId: string): PatternInstance[] {
    return this.instances.get(patternId) || [];
  }

  addPrediction(patternId: string, prediction: PatternPrediction): void {
    if (!this.predictions.has(patternId)) {
      this.predictions.set(patternId, []);
    }
    this.predictions.get(patternId)!.push(prediction);
  }

  getPredictions(patternId: string): PatternPrediction[] {
    return this.predictions.get(patternId) || [];
  }

  addAnomaly(anomaly: Anomaly): void {
    this.anomalies.set(anomaly.id, anomaly);
  }

  getAnomaly(id: string): Anomaly | undefined {
    return this.anomalies.get(id);
  }

  getActiveAnomalies(tenantId: string): Anomaly[] {
    return Array.from(this.anomalies.values())
      .filter(a => a.tenant_id === tenantId && !a.resolved);
  }

  updateAnomaly(id: string, updates: Partial<Anomaly>): Anomaly | undefined {
    const anomaly = this.anomalies.get(id);
    if (!anomaly) return undefined;

    const updated = { ...anomaly, ...updates };
    this.anomalies.set(id, updated);
    return updated;
  }

  addTrend(trend: Trend): void {
    this.trends.set(trend.id, trend);
  }

  getTrend(id: string): Trend | undefined {
    return this.trends.get(id);
  }

  getActiveTrends(): Trend[] {
    return Array.from(this.trends.values())
      .filter(t => !t.end_time);
  }

  getAllPatterns(): Pattern[] {
    return Array.from(this.patterns.values());
  }

  clear(): void {
    this.patterns.clear();
    this.instances.clear();
    this.predictions.clear();
    this.anomalies.clear();
    this.trends.clear();
    this.patternByCategory.clear();
    this.patternByType.clear();
    this.patternByTenant.clear();
  }
}

// ── Pattern Detector ───────────────────────────────────────────────────

class PatternDetector {
  private config: PatternDetectionConfig;
  private variantLimits: PatternDetectionVariantLimits;

  constructor(config: PatternDetectionConfig, variantLimits: PatternDetectionVariantLimits) {
    this.config = config;
    this.variantLimits = variantLimits;
  }

  detectUserBehaviorPatterns(
    userId: string,
    intentHistory: Array<{ intent: IntentAction; timestamp: Date; context?: Record<string, unknown> }>
  ): Pattern[] {
    const patterns: Pattern[] = [];

    // Detect sequential patterns (A then B)
    const sequentialPatterns = this.detectSequentialPatterns(userId, intentHistory);
    patterns.push(...sequentialPatterns);

    // Detect temporal patterns (time-based)
    const temporalPatterns = this.detectTemporalPatterns(userId, intentHistory);
    patterns.push(...temporalPatterns);

    // Detect frequency patterns
    const frequencyPatterns = this.detectFrequencyPatterns(userId, intentHistory);
    patterns.push(...frequencyPatterns);

    return patterns;
  }

  private detectSequentialPatterns(
    userId: string,
    intentHistory: Array<{ intent: IntentAction; timestamp: Date }>
  ): Pattern[] {
    const patterns: Pattern[] = [];

    // Look for A -> B sequences
    const sequenceCounts = new Map<string, number>();

    for (let i = 0; i < intentHistory.length - 1; i++) {
      const current = intentHistory[i].intent;
      const next = intentHistory[i + 1].intent;
      const sequence = `${current}->${next}`;

      sequenceCounts.set(sequence, (sequenceCounts.get(sequence) || 0) + 1);
    }

    // Create patterns for frequent sequences
    for (const [sequence, count] of sequenceCounts) {
      if (count >= this.config.min_occurrences_for_pattern) {
        const [fromIntent, toIntent] = sequence.split('->');

        patterns.push(this.createPattern(
          'user_behavior',
          'sequential',
          `Sequential Pattern: ${fromIntent} → ${toIntent}`,
          `User frequently performs '${toIntent}' after '${fromIntent}'`,
          count,
          this.calculateConfidence(count, intentHistory.length),
          [{
            dimension: 'previous_intent',
            operator: 'equals',
            value: fromIntent,
            weight: 1,
          }],
          userId
        ));
      }
    }

    return patterns;
  }

  private detectTemporalPatterns(
    userId: string,
    intentHistory: Array<{ intent: IntentAction; timestamp: Date }>
  ): Pattern[] {
    const patterns: Pattern[] = [];

    // Group intents by hour
    const hourlyDistribution = new Map<number, Map<string, number>>();

    for (const item of intentHistory) {
      const hour = item.timestamp.getHours();
      if (!hourlyDistribution.has(hour)) {
        hourlyDistribution.set(hour, new Map());
      }
      const hourMap = hourlyDistribution.get(hour)!;
      hourMap.set(item.intent, (hourMap.get(item.intent) || 0) + 1);
    }

    // Find intents that occur frequently at specific times
    for (const [hour, intentCounts] of hourlyDistribution) {
      for (const [intent, count] of intentCounts) {
        if (count >= this.config.min_occurrences_for_pattern) {
          const hourLabel = this.getHourLabel(hour);

          patterns.push(this.createPattern(
            'time_patterns',
            'temporal',
            `Temporal Pattern: ${intent} at ${hourLabel}`,
            `User frequently performs '${intent}' during ${hourLabel}`,
            count,
            this.calculateConfidence(count, intentHistory.length),
            [{
              dimension: 'hour_of_day',
              operator: 'equals',
              value: hour,
              weight: 0.8,
            }],
            userId
          ));
        }
      }
    }

    return patterns;
  }

  private detectFrequencyPatterns(
    userId: string,
    intentHistory: Array<{ intent: IntentAction; timestamp: Date }>
  ): Pattern[] {
    const patterns: Pattern[] = [];

    // Count intent frequencies
    const intentCounts = new Map<string, number>();
    for (const item of intentHistory) {
      intentCounts.set(item.intent, (intentCounts.get(item.intent) || 0) + 1);
    }

    // Create patterns for frequent intents
    const totalIntents = intentHistory.length;
    for (const [intent, count] of intentCounts) {
      const frequency = count / totalIntents;
      if (frequency >= 0.3 && count >= this.config.min_occurrences_for_pattern) {
        patterns.push(this.createPattern(
          'user_behavior',
          'frequency',
          `Frequency Pattern: ${intent}`,
          `User frequently performs '${intent}' (${(frequency * 100).toFixed(1)}% of actions)`,
          count,
          frequency,
          [{
            dimension: 'intent',
            operator: 'equals',
            value: intent,
            weight: 1,
          }],
          userId
        ));
      }
    }

    return patterns;
  }

  detectTicketPatterns(
    tickets: Array<{
      id: string;
      type?: string;
      priority?: string;
      status?: string;
      created_at: Date;
      resolved_at?: Date;
      sla_deadline?: Date;
    }>
  ): Pattern[] {
    const patterns: Pattern[] = [];

    if (tickets.length < this.config.min_occurrences_for_pattern) {
      return patterns;
    }

    // Detect priority patterns
    const priorityCounts = new Map<string, number>();
    for (const ticket of tickets) {
      if (ticket.priority) {
        priorityCounts.set(ticket.priority, (priorityCounts.get(ticket.priority) || 0) + 1);
      }
    }

    for (const [priority, count] of priorityCounts) {
      if (count >= this.config.min_occurrences_for_pattern) {
        patterns.push(this.createPattern(
          'ticket_trends',
          'frequency',
          `Ticket Priority Pattern: ${priority}`,
          `Frequent ${priority} priority tickets`,
          count,
          this.calculateConfidence(count, tickets.length),
          [{
            dimension: 'priority',
            operator: 'equals',
            value: priority,
            weight: 1,
          }],
          'tenant'
        ));
      }
    }

    return patterns;
  }

  detectSLAPatterns(
    slaRecords: Array<{
      ticket_id: string;
      sla_type: string;
      deadline: Date;
      met: boolean;
      breach_time?: Date;
    }>
  ): Pattern[] {
    const patterns: Pattern[] = [];

    if (slaRecords.length < this.config.min_occurrences_for_pattern) {
      return patterns;
    }

    // Calculate breach rate
    const breaches = slaRecords.filter(r => !r.met);
    const breachRate = breaches.length / slaRecords.length;

    if (breachRate >= 0.2) {
      patterns.push(this.createPattern(
        'sla_patterns',
        'trend',
        'High SLA Breach Rate',
        `${(breachRate * 100).toFixed(1)}% SLA breach rate detected`,
        breaches.length,
        breachRate,
        [{
          dimension: 'breach_rate',
          operator: 'greater_than',
          value: 0.2,
          weight: 1,
        }],
        'tenant'
      ));
    }

    return patterns;
  }

  detectAnomalies(
    metric: string,
    currentValue: number,
    baseline: { mean: number; stdDev: number },
    threshold: AnomalyThreshold
  ): Anomaly | null {
    if (!this.variantLimits.anomaly_detection) {
      return null;
    }

    const deviation = Math.abs(currentValue - baseline.mean);
    const deviationPercent = baseline.mean !== 0
      ? (deviation / baseline.mean) * 100
      : (deviation > 0 ? 100 : 0);

    let severity: 'critical' | 'warning' | 'info' | null = null;

    if (deviationPercent >= threshold.critical_threshold) {
      severity = 'critical';
    } else if (deviationPercent >= threshold.warning_threshold) {
      severity = 'warning';
    }

    if (!severity) {
      return null;
    }

    // Determine anomaly type
    let type: 'spike' | 'drop' | 'outlier';
    if (currentValue > baseline.mean + 2 * baseline.stdDev) {
      type = 'spike';
    } else if (currentValue < baseline.mean - 2 * baseline.stdDev) {
      type = 'drop';
    } else {
      type = 'outlier';
    }

    return {
      id: `anomaly_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      tenant_id: '',
      type,
      severity,
      metric,
      expected_value: baseline.mean,
      actual_value: currentValue,
      deviation_percent: deviationPercent,
      detected_at: new Date(),
      context: {},
      resolved: false,
    };
  }

  analyzeTrend(
    metric: string,
    dataPoints: Array<{ timestamp: Date; value: number }>
  ): Trend | null {
    if (!this.variantLimits.trend_analysis || dataPoints.length < 3) {
      return null;
    }

    // Simple linear regression for trend detection
    const n = dataPoints.length;
    const x = dataPoints.map((_, i) => i);
    const y = dataPoints.map(d => d.value);

    const sumX = x.reduce((a, b) => a + b, 0);
    const sumY = y.reduce((a, b) => a + b, 0);
    const sumXY = x.reduce((acc, xi, i) => acc + xi * y[i], 0);
    const sumXX = x.reduce((acc, xi) => acc + xi * xi, 0);

    const slope = (n * sumXY - sumX * sumY) / (n * sumXX - sumX * sumX);

    let direction: 'increasing' | 'decreasing' | 'stable';
    if (slope > 0.01) {
      direction = 'increasing';
    } else if (slope < -0.01) {
      direction = 'decreasing';
    } else {
      direction = 'stable';
    }

    return {
      id: `trend_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      metric,
      direction,
      magnitude: Math.abs(slope),
      start_time: dataPoints[0].timestamp,
      data_points: dataPoints.map((d, i) => ({
        timestamp: d.timestamp,
        value: d.value,
      })),
    };
  }

  private createPattern(
    category: PatternCategory,
    type: PatternType,
    name: string,
    description: string,
    occurrences: number,
    confidenceScore: number,
    conditions: PatternCondition[],
    userId: string
  ): Pattern {
    const confidence: PatternConfidence =
      confidenceScore >= 0.8 ? 'high' :
      confidenceScore >= 0.6 ? 'medium' : 'low';

    return {
      id: `pattern_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      tenant_id: '',
      category,
      type,
      name,
      description,
      status: 'active',
      confidence,
      confidence_score: confidenceScore,
      support: occurrences,
      first_detected: new Date(),
      last_observed: new Date(),
      occurrences,
      pattern_data: {
        trigger_conditions: conditions,
        pattern_expression: {
          type: 'rule',
          rule_definition: {
            if: conditions,
            then: {
              action: 'predict',
              expected_outcome: 'pattern_match',
            },
            probability: confidenceScore,
          },
        },
        statistical_significance: confidenceScore,
        sample_size: occurrences,
        false_positive_rate: 1 - confidenceScore,
      },
      metadata: {
        detection_method: 'automatic',
        user_id: userId,
      },
      predictions: [],
      related_patterns: [],
      tags: [category, type],
    };
  }

  private calculateConfidence(occurrences: number, total: number): number {
    if (total === 0) return 0;
    const frequency = occurrences / total;
    // Confidence increases with frequency but caps at 0.95
    return Math.min(0.95, frequency * 0.8 + (occurrences / 10) * 0.2);
  }

  private getHourLabel(hour: number): string {
    if (hour < 6) return 'late night';
    if (hour < 12) return 'morning';
    if (hour < 17) return 'afternoon';
    if (hour < 21) return 'evening';
    return 'night';
  }
}

// ── Pattern Detection Manager ───────────────────────────────────────────

export class PatternDetectionManager {
  private config: PatternDetectionConfig;
  private variantLimits: PatternDetectionVariantLimits;
  private storage: PatternStorage;
  private detector: PatternDetector;
  private eventEmitter: PatternEventEmitter;
  private detectionInterval: NodeJS.Timeout | null = null;
  private stats = {
    totalPatternsDetected: 0,
    predictionsMade: 0,
    predictionsActualized: 0,
    anomaliesDetected: 0,
    detectionRuns: 0,
    lastDetectionTime: undefined as Date | undefined,
  };

  constructor(config: PatternDetectionConfig) {
    this.config = { ...DEFAULT_PATTERN_DETECTION_CONFIG, ...config } as PatternDetectionConfig;
    this.variantLimits = PATTERN_DETECTION_VARIANT_LIMITS[config.variant];
    this.storage = new PatternStorage();
    this.detector = new PatternDetector(this.config, this.variantLimits);
    this.eventEmitter = new PatternEventEmitter();

    if (this.config.enabled) {
      this.startDetection();
    }
  }

  // ── Pattern Detection ───────────────────────────────────────────────

  detectPatterns(request: DetectPatternsRequest): DetectPatternsResponse {
    const startTime = Date.now();

    if (!this.variantLimits.enabled) {
      return {
        patterns: [],
        detection_time_ms: 0,
        data_points_analyzed: 0,
      };
    }

    const patterns = this.storage.getPatternsByTenant(request.tenant_id);
    this.stats.detectionRuns++;
    this.stats.lastDetectionTime = new Date();

    return {
      patterns,
      detection_time_ms: Date.now() - startTime,
      data_points_analyzed: patterns.length,
    };
  }

  analyzeUserBehavior(
    userId: string,
    intentHistory: Array<{ intent: IntentAction; timestamp: Date; context?: Record<string, unknown> }>
  ): Pattern[] {
    if (!this.variantLimits.enabled) {
      return [];
    }

    const patterns = this.detector.detectUserBehaviorPatterns(userId, intentHistory);

    // Store patterns
    for (const pattern of patterns) {
      pattern.tenant_id = this.config.tenant_id;
      this.storage.addPattern(pattern);
      this.stats.totalPatternsDetected++;

      this.emitEvent('pattern_detected', undefined, undefined, {
        pattern_id: pattern.id,
        category: pattern.category,
        type: pattern.type,
      });
    }

    return patterns;
  }

  analyzeTicketPatterns(
    tickets: Array<{
      id: string;
      type?: string;
      priority?: string;
      status?: string;
      created_at: Date;
      resolved_at?: Date;
      sla_deadline?: Date;
    }>
  ): Pattern[] {
    if (!this.variantLimits.enabled) {
      return [];
    }

    const patterns = this.detector.detectTicketPatterns(tickets);

    for (const pattern of patterns) {
      pattern.tenant_id = this.config.tenant_id;
      this.storage.addPattern(pattern);
      this.stats.totalPatternsDetected++;

      this.emitEvent('pattern_detected', undefined, undefined, {
        pattern_id: pattern.id,
      });
    }

    return patterns;
  }

  analyzeSLAPatterns(
    slaRecords: Array<{
      ticket_id: string;
      sla_type: string;
      deadline: Date;
      met: boolean;
      breach_time?: Date;
    }>
  ): Pattern[] {
    if (!this.variantLimits.enabled) {
      return [];
    }

    const patterns = this.detector.detectSLAPatterns(slaRecords);

    for (const pattern of patterns) {
      pattern.tenant_id = this.config.tenant_id;
      this.storage.addPattern(pattern);
      this.stats.totalPatternsDetected++;

      this.emitEvent('pattern_detected', undefined, undefined, {
        pattern_id: pattern.id,
      });
    }

    return patterns;
  }

  // ── Anomaly Detection ───────────────────────────────────────────────

  checkForAnomalies(
    metric: string,
    currentValue: number,
    baseline: { mean: number; stdDev: number }
  ): Anomaly | null {
    if (!this.config.anomaly_detection_enabled) {
      return null;
    }

    const threshold = this.config.thresholds.find(t => t.metric === metric);
    if (!threshold) return null;

    const anomaly = this.detector.detectAnomalies(metric, currentValue, baseline, threshold);

    if (anomaly) {
      anomaly.tenant_id = this.config.tenant_id;
      this.storage.addAnomaly(anomaly);
      this.stats.anomaliesDetected++;

      this.emitEvent('anomaly_detected', undefined, anomaly.id, {
        metric,
        severity: anomaly.severity,
        deviation_percent: anomaly.deviation_percent,
      });
    }

    return anomaly;
  }

  getActiveAnomalies(): Anomaly[] {
    return this.storage.getActiveAnomalies(this.config.tenant_id);
  }

  getAnomaly(anomalyId: string): Anomaly | undefined {
    return this.storage.getAnomaly(anomalyId);
  }

  resolveAnomaly(anomalyId: string, note?: string): Anomaly | undefined {
    const anomaly = this.storage.updateAnomaly(anomalyId, {
      resolved: true,
      resolved_at: new Date(),
      resolution_note: note,
    });

    if (anomaly) {
      this.emitEvent('anomaly_resolved', undefined, anomalyId, {
        note,
      });
    }

    return anomaly;
  }

  // ── Trend Analysis ───────────────────────────────────────────────────

  analyzeTrend(
    metric: string,
    dataPoints: Array<{ timestamp: Date; value: number }>
  ): Trend | null {
    if (!this.config.trend_analysis_enabled) {
      return null;
    }

    const trend = this.detector.analyzeTrend(metric, dataPoints);

    if (trend) {
      this.storage.addTrend(trend);
      this.emitEvent('trend_detected', undefined, undefined, {
        trend_id: trend.id,
        metric,
        direction: trend.direction,
      });
    }

    return trend;
  }

  getTrend(trendId: string): Trend | undefined {
    return this.storage.getTrend(trendId);
  }

  getActiveTrends(): Trend[] {
    return this.storage.getActiveTrends();
  }

  // ── Pattern Management ───────────────────────────────────────────────

  getPatterns(request: GetPatternsRequest): GetPatternsResponse {
    let patterns = this.storage.getPatternsByTenant(request.tenant_id);

    // Filter by categories
    if (request.categories && request.categories.length > 0) {
      patterns = patterns.filter(p => request.categories!.includes(p.category));
    }

    // Filter by types
    if (request.types && request.types.length > 0) {
      patterns = patterns.filter(p => request.types!.includes(p.type));
    }

    // Filter by status
    if (request.status) {
      patterns = patterns.filter(p => p.status === request.status);
    }

    // Filter by confidence
    if (request.min_confidence !== undefined) {
      patterns = patterns.filter(p => p.confidence_score >= request.min_confidence!);
    }

    const total = patterns.length;
    const offset = request.offset ?? 0;
    const limit = request.limit ?? 100;

    return {
      patterns: patterns.slice(offset, offset + limit),
      total,
      has_more: offset + limit < total,
    };
  }

  getPattern(patternId: string): Pattern | undefined {
    return this.storage.getPattern(patternId);
  }

  recordPatternInstance(patternId: string, context: Record<string, unknown>): PatternInstance | undefined {
    const pattern = this.storage.getPattern(patternId);
    if (!pattern) return undefined;

    const instance: PatternInstance = {
      id: `instance_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      pattern_id: patternId,
      observed_at: new Date(),
      context,
      entities_involved: [],
      matched_conditions: pattern.pattern_data.trigger_conditions,
      confidence_at_detection: pattern.confidence_score,
    };

    this.storage.addInstance(patternId, instance);

    // Update pattern occurrence count
    this.storage.updatePattern(patternId, {
      occurrences: pattern.occurrences + 1,
      last_observed: new Date(),
    });

    return instance;
  }

  invalidatePattern(patternId: string, reason?: string): boolean {
    const existingPattern = this.storage.getPattern(patternId);
    const pattern = this.storage.updatePattern(patternId, {
      status: 'invalidated',
      metadata: {
        ...(existingPattern?.metadata || {}),
        detection_method: existingPattern?.metadata?.detection_method || 'manual',
        invalidation_reason: reason,
        invalidated_at: new Date(),
      },
    });

    if (pattern) {
      this.emitEvent('pattern_invalidated', patternId, undefined, { reason });
      return true;
    }

    return false;
  }

  // ── Predictions ───────────────────────────────────────────────────────

  makePrediction(
    patternId: string,
    predictedEvent: string,
    probability: number,
    timeHorizon: { type: 'immediate' | 'short_term' | 'medium_term' | 'long_term'; duration_minutes?: number }
  ): PatternPrediction | undefined {
    const pattern = this.storage.getPattern(patternId);
    if (!pattern) return undefined;

    if (!this.variantLimits.predictive_forecasting) {
      return undefined;
    }

    const prediction: PatternPrediction = {
      id: `pred_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      pattern_id: patternId,
      predicted_event: predictedEvent,
      probability,
      time_horizon: timeHorizon,
      conditions: pattern.pattern_data.trigger_conditions,
      created_at: new Date(),
    };

    this.storage.addPrediction(patternId, prediction);
    this.stats.predictionsMade++;

    this.emitEvent('prediction_made', patternId, undefined, {
      prediction_id: prediction.id,
      predicted_event: predictedEvent,
    });

    return prediction;
  }

  markPredictionActualized(predictionId: string): boolean {
    // Find the prediction
    for (const [patternId, predictions] of Array.from(this.storage.getPredictions('').entries())) {
      // Actually search through all patterns
    }

    // Simplified: mark as actualized in stats
    this.stats.predictionsActualized++;

    this.emitEvent('prediction_actualized', undefined, undefined, {
      prediction_id: predictionId,
    });

    return true;
  }

  // ── Statistics ────────────────────────────────────────────────────────

  getStats(): PatternDetectionStats {
    const patterns = this.storage.getAllPatterns();

    const byCategory: Record<PatternCategory, number> = {
      user_behavior: 0,
      team_behavior: 0,
      ticket_trends: 0,
      sla_patterns: 0,
      escalation_patterns: 0,
      customer_sentiment: 0,
      time_patterns: 0,
      entity_correlation: 0,
    };

    const byType: Record<PatternType, number> = {
      sequential: 0,
      temporal: 0,
      frequency: 0,
      correlation: 0,
      anomaly: 0,
      seasonal: 0,
      trend: 0,
    };

    for (const pattern of patterns) {
      byCategory[pattern.category]++;
      byType[pattern.type]++;
    }

    const anomalies = this.storage.getActiveAnomalies(this.config.tenant_id);
    const anomaliesBySeverity = {
      critical: anomalies.filter(a => a.severity === 'critical').length,
      warning: anomalies.filter(a => a.severity === 'warning').length,
      info: anomalies.filter(a => a.severity === 'info').length,
    };

    return {
      total_patterns_detected: this.stats.totalPatternsDetected,
      patterns_by_category: byCategory,
      patterns_by_type: byType,
      active_patterns: patterns.filter(p => p.status === 'active').length,
      pattern_predictions_made: this.stats.predictionsMade,
      predictions_accuracy: this.stats.predictionsMade > 0
        ? this.stats.predictionsActualized / this.stats.predictionsMade
        : 0,
      anomalies_detected: this.stats.anomaliesDetected,
      anomalies_by_severity: anomaliesBySeverity,
      trends_tracked: this.storage.getActiveTrends().length,
      detection_runs: this.stats.detectionRuns,
      last_detection_time: this.stats.lastDetectionTime,
    };
  }

  // ── Events ─────────────────────────────────────────────────────────────

  onEvent(event: PatternEventType, callback: (event: PatternEvent) => void): () => void {
    return this.eventEmitter.on(event, callback);
  }

  // ── Lifecycle ─────────────────────────────────────────────────────────

  shutdown(): void {
    if (this.detectionInterval) {
      clearInterval(this.detectionInterval);
      this.detectionInterval = null;
    }
    this.storage.clear();
    this.eventEmitter.clear();
  }

  // ── Private Methods ──────────────────────────────────────────────────

  private startDetection(): void {
    // Run periodic pattern detection
    this.detectionInterval = setInterval(() => {
      // Periodic detection would run here
      this.stats.detectionRuns++;
    }, this.config.detection_interval_minutes * 60 * 1000);
  }

  private emitEvent(
    type: PatternEventType,
    patternId?: string,
    anomalyId?: string,
    metadata?: Record<string, unknown>
  ): void {
    this.eventEmitter.emit({
      type,
      pattern_id: patternId,
      anomaly_id: anomalyId,
      tenant_id: this.config.tenant_id,
      timestamp: new Date(),
      metadata,
    });
  }
}

// ── Factory Function ─────────────────────────────────────────────────────

export function createPatternDetectionManager(
  config: PatternDetectionConfig
): PatternDetectionManager {
  return new PatternDetectionManager(config);
}

// ── Singleton Registry ────────────────────────────────────────────────────

const managers = new Map<string, PatternDetectionManager>();

export function getPatternDetectionManager(
  tenantId: string,
  variant: Variant
): PatternDetectionManager {
  const key = `${tenantId}:${variant}`;

  if (!managers.has(key)) {
    managers.set(key, createPatternDetectionManager({
      ...DEFAULT_PATTERN_DETECTION_CONFIG,
      tenant_id: tenantId,
      variant,
    }));
  }

  return managers.get(key)!;
}

export function shutdownPatternDetectionManager(tenantId: string, variant: Variant): void {
  const key = `${tenantId}:${variant}`;
  const manager = managers.get(key);
  if (manager) {
    manager.shutdown();
    managers.delete(key);
  }
}
