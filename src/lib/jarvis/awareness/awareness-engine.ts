/**
 * JARVIS Awareness Engine (Week 2 - Phase 1)
 *
 * Main orchestrator for the JARVIS awareness system.
 * Integrates all Week 2 components: event listeners, activity trackers,
 * health monitors, alert dispatcher, event capture, data aggregation,
 * sentiment pipeline, and metrics collector.
 */

import type {
  AwarenessEvent,
  AwarenessState,
  Alert,
  SystemHealth,
  CustomerActivitySummary,
  SentimentTrend,
  AggregatedMetric,
  AlertSeverity,
  AwarenessEventType,
} from '@/types/awareness';

import type { Industry } from '../integration/types';

import { TicketEventListener, DEFAULT_TICKET_LISTENER_CONFIG } from './ticket-event-listener';
import { CustomerActivityTracker, DEFAULT_ACTIVITY_TRACKER_CONFIG } from './activity-tracker';
import { SystemHealthMonitor, DEFAULT_CHECK_INTERVALS } from './health-monitor';
import { AlertDispatcher, DEFAULT_ALERT_DISPATCHER_CONFIG, DEFAULT_ALERT_RULES } from './alert-dispatcher';
import { EventCapture, DEFAULT_EVENT_CAPTURE_CONFIG } from './event-capture';
import { DataAggregator, DEFAULT_AGGREGATOR_CONFIG } from './data-aggregator';
import { SentimentPipeline, DEFAULT_SENTIMENT_PIPELINE_CONFIG } from './sentiment-pipeline';
import { MetricsCollector, DEFAULT_METRICS_COLLECTOR_CONFIG } from './metrics-collector';

// ── Awareness Engine Configuration ───────────────────────────────────

export interface AwarenessEngineConfig {
  tenant_id: string;
  variant: 'mini_parwa' | 'parwa' | 'parwa_high';
  industry?: Industry;
}

// ── Event Emitter Implementation ─────────────────────────────────────

class EventEmitHandler {
  private eventCapture: EventCapture;
  private alertDispatcher: AlertDispatcher;
  private dataAggregator: DataAggregator;

  constructor(
    eventCapture: EventCapture,
    alertDispatcher: AlertDispatcher,
    dataAggregator: DataAggregator
  ) {
    this.eventCapture = eventCapture;
    this.alertDispatcher = alertDispatcher;
    this.dataAggregator = dataAggregator;
  }

  async emit(event: AwarenessEvent): Promise<void> {
    // Capture event
    await this.eventCapture.capture(event);

    // Store for aggregation
    this.dataAggregator.storeEvent(event);

    // Process for alerts
    await this.alertDispatcher.processEvent(event);
  }
}

// ── Awareness Engine Class ───────────────────────────────────────────

export class AwarenessEngine {
  private config: AwarenessEngineConfig;
  private initialized = false;

  // Components
  private ticketListener!: TicketEventListener;
  private activityTracker!: CustomerActivityTracker;
  private healthMonitor!: SystemHealthMonitor;
  private alertDispatcher!: AlertDispatcher;
  private eventCapture!: EventCapture;
  private dataAggregator!: DataAggregator;
  private sentimentPipeline!: SentimentPipeline;
  private metricsCollector!: MetricsCollector;
  private eventEmitter!: EventEmitHandler;

  // State
  private state: AwarenessState;
  private stateListeners: Array<(state: AwarenessState) => void> = [];

  constructor(config: AwarenessEngineConfig) {
    this.config = config;
    this.state = {
      tenant_id: config.tenant_id,
      variant: config.variant,
      active_alerts: [],
      health_status: {
        tenant_id: config.tenant_id,
        overall_status: 'unknown',
        components: [],
        checked_at: new Date(),
        uptime_percentage: 100,
        incident_count_24h: 0,
      },
      recent_events: [],
      metrics_cache: new Map(),
      last_updated: new Date(),
    };
  }

  /**
   * Initialize the awareness engine
   */
  async initialize(): Promise<void> {
    if (this.initialized) return;

    const { tenant_id, variant } = this.config;

    // Initialize Event Capture
    this.eventCapture = new EventCapture({
      tenant_id,
      ...DEFAULT_EVENT_CAPTURE_CONFIG[variant],
    });

    // Initialize Alert Dispatcher
    this.alertDispatcher = new AlertDispatcher({
      tenant_id,
      ...DEFAULT_ALERT_DISPATCHER_CONFIG[variant],
    });

    // Add default alert rules
    for (const rule of DEFAULT_ALERT_RULES) {
      this.alertDispatcher.addAlertRule({
        ...rule,
        id: this.generateId(),
        tenant_id,
        created_at: new Date(),
        updated_at: new Date(),
      });
    }

    // Initialize Data Aggregator
    this.dataAggregator = new DataAggregator({
      tenant_id,
      ...DEFAULT_AGGREGATOR_CONFIG[variant],
    });

    // Create event emitter handler
    this.eventEmitter = new EventEmitHandler(
      this.eventCapture,
      this.alertDispatcher,
      this.dataAggregator
    );

    // Initialize Ticket Event Listener
    this.ticketListener = new TicketEventListener(
      { tenant_id, ...DEFAULT_TICKET_LISTENER_CONFIG[variant] },
      this.eventEmitter
    );

    // Initialize Activity Tracker
    this.activityTracker = new CustomerActivityTracker(
      { tenant_id, ...DEFAULT_ACTIVITY_TRACKER_CONFIG[variant] },
      this.eventEmitter
    );

    // Initialize Health Monitor
    this.healthMonitor = new SystemHealthMonitor(tenant_id, variant, this.eventEmitter);

    // Initialize Sentiment Pipeline
    this.sentimentPipeline = new SentimentPipeline({
      tenant_id,
      ...DEFAULT_SENTIMENT_PIPELINE_CONFIG[variant],
    });

    // Initialize Metrics Collector
    this.metricsCollector = new MetricsCollector({
      tenant_id,
      ...DEFAULT_METRICS_COLLECTOR_CONFIG[variant],
    });

    // Set up metrics collection callback
    this.metricsCollector.onCollect((metrics) => {
      for (const metric of metrics) {
        this.dataAggregator.storeMetric(metric);
      }
    });

    // Subscribe to events for state updates
    this.eventCapture.subscribe('state-updater', async (event) => {
      this.updateState(event);
    });

    // Start health monitoring
    this.healthMonitor.startMonitoring();

    // Start metrics collection
    this.metricsCollector.startCollection();

    this.initialized = true;
  }

  /**
   * Shutdown the awareness engine
   */
  async shutdown(): Promise<void> {
    this.healthMonitor.stopMonitoring();
    this.metricsCollector.stopCollection();
    await this.eventCapture.shutdown();
    this.ticketListener.shutdown();
    this.initialized = false;
  }

  // ── Public API: Ticket Events ──────────────────────────────────────

  get ticketEvents(): TicketEventListener {
    return this.ticketListener;
  }

  // ── Public API: Activity Tracking ───────────────────────────────────

  async trackCustomerActivity(data: {
    customer_id: string;
    activity_type: 'message' | 'email' | 'ticket' | 'call' | 'chat';
    channel: string;
    ticket_id?: string;
    agent_id?: string;
    content?: string;
  }): Promise<void> {
    await this.activityTracker.trackActivity({
      tenant_id: this.config.tenant_id,
      ...data,
    });
  }

  async getCustomerSummary(customerId: string): Promise<CustomerActivitySummary> {
    return this.activityTracker.getActivitySummary(customerId);
  }

  // ── Public API: Health Monitoring ───────────────────────────────────

  async getSystemHealth(): Promise<SystemHealth> {
    return this.healthMonitor.getSystemHealth();
  }

  registerHealthComponent(definition: {
    name: string;
    check: () => Promise<{ status: string; latency_ms: number; message?: string }>;
    thresholds?: Record<string, number>;
    intervalMs?: number;
  }): void {
    this.healthMonitor.registerComponent({
      name: definition.name,
      check: async () => {
        const result = await definition.check();
        return {
          component: definition.name,
          status: result.status as 'healthy' | 'degraded' | 'critical' | 'unknown',
          latency_ms: result.latency_ms,
          message: result.message,
        };
      },
      thresholds: {
        component: definition.name,
        latency_warning_ms: definition.thresholds?.latency_warning_ms || 1000,
        latency_critical_ms: definition.thresholds?.latency_critical_ms || 5000,
        error_rate_warning_pct: definition.thresholds?.error_rate_warning_pct || 5,
        error_rate_critical_pct: definition.thresholds?.error_rate_critical_pct || 20,
      },
      enabled: true,
      check_interval_ms: definition.intervalMs || DEFAULT_CHECK_INTERVALS[this.config.variant],
    });
  }

  // ── Public API: Alerts ──────────────────────────────────────────────

  getActiveAlerts(options?: { severity?: AlertSeverity; type?: AwarenessEventType }): Alert[] {
    return this.alertDispatcher.getActiveAlerts(options);
  }

  async acknowledgeAlert(alertId: string, acknowledgedBy: string, notes?: string): Promise<Alert | null> {
    return this.alertDispatcher.acknowledgeAlert(alertId, acknowledgedBy, notes);
  }

  async resolveAlert(alertId: string, resolvedBy?: string): Promise<Alert | null> {
    return this.alertDispatcher.resolveAlert(alertId, resolvedBy);
  }

  // ── Public API: Sentiment ───────────────────────────────────────────

  async analyzeSentiment(text: string, customerId?: string): Promise<{
    label: string;
    score: number;
    confidence: number;
  }> {
    const result = await this.sentimentPipeline.analyze({
      text,
      customer_id: customerId,
    });

    return {
      label: result.label,
      score: result.score,
      confidence: result.confidence,
    };
  }

  getSentimentTrend(period: 'hour' | 'day' | 'week' = 'day'): SentimentTrend | null {
    return this.sentimentPipeline.calculateAggregateTrend(period);
  }

  // ── Public API: Metrics ─────────────────────────────────────────────

  recordMetric(name: string, value: number, tags?: Record<string, string>): void {
    this.metricsCollector.record(name, value, 'value', tags);
  }

  recordTiming(name: string, durationMs: number, tags?: Record<string, string>): void {
    this.metricsCollector.recordTiming(name, durationMs, tags);
  }

  getAggregatedMetric(
    name: string,
    aggregation: 'sum' | 'avg' | 'min' | 'max' | 'count' | 'p95' | 'p99',
    periodMs: number,
    tags?: Record<string, string>
  ): AggregatedMetric | null {
    return this.metricsCollector.getAggregated(name, aggregation, periodMs, tags);
  }

  // ── Public API: State ───────────────────────────────────────────────

  getState(): AwarenessState {
    return { ...this.state };
  }

  onStateChange(listener: (state: AwarenessState) => void): () => void {
    this.stateListeners.push(listener);
    return () => {
      const index = this.stateListeners.indexOf(listener);
      if (index >= 0) this.stateListeners.splice(index, 1);
    };
  }

  // ── Public API: Event Subscriptions ─────────────────────────────────

  subscribeToEvents(
    callback: (event: AwarenessEvent) => void,
    eventTypes?: AwarenessEventType[]
  ): () => void {
    return this.eventCapture.subscribe(
      this.generateId(),
      async (event) => callback(event),
      eventTypes ? (e) => eventTypes.includes(e.type) : undefined
    );
  }

  // ── Private Methods ────────────────────────────────────────────────

  private updateState(event: AwarenessEvent): void {
    // Update recent events
    this.state.recent_events.push(event);
    if (this.state.recent_events.length > 100) {
      this.state.recent_events.shift();
    }

    // Update active alerts
    this.state.active_alerts = this.alertDispatcher.getActiveAlerts();

    // Update timestamp
    this.state.last_updated = new Date();

    // Notify listeners
    for (const listener of this.stateListeners) {
      try {
        listener(this.state);
      } catch (error) {
        console.error('[AwarenessEngine] State listener error:', error);
      }
    }
  }

  private generateId(): string {
    return `${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }
}

// ── Singleton Registry ───────────────────────────────────────────────

const engines = new Map<string, AwarenessEngine>();

export async function getAwarenessEngine(config: AwarenessEngineConfig): Promise<AwarenessEngine> {
  const key = `${config.tenant_id}_${config.variant}`;

  if (!engines.has(key)) {
    const engine = new AwarenessEngine(config);
    await engine.initialize();
    engines.set(key, engine);
  }

  return engines.get(key)!;
}

export async function shutdownAwarenessEngine(config: AwarenessEngineConfig): Promise<void> {
  const key = `${config.tenant_id}_${config.variant}`;
  const engine = engines.get(key);

  if (engine) {
    await engine.shutdown();
    engines.delete(key);
  }
}

// ── Factory Function ─────────────────────────────────────────────────

export function createAwarenessEngine(config: AwarenessEngineConfig): AwarenessEngine {
  return new AwarenessEngine(config);
}
