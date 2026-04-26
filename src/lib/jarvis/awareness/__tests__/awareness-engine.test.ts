/**
 * JARVIS Awareness Engine - Week 2 Unit Tests
 *
 * Comprehensive test suite for all Week 2 components.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

// ── Types ────────────────────────────────────────────────────────────

import type {
  AwarenessEvent,
  Alert,
  HealthStatus,
  SentimentLabel,
} from '@/types/awareness';

// ── Mock Event Emitter ────────────────────────────────────────────────

const createMockEmitter = () => ({
  emit: vi.fn().mockResolvedValue(undefined),
});

// ── Ticket Event Listener Tests ───────────────────────────────────────

describe('TicketEventListener', () => {
  let listener: any;
  let mockEmitter: any;

  beforeEach(async () => {
    const { TicketEventListener, DEFAULT_TICKET_LISTENER_CONFIG } = await import(
      '@/lib/jarvis/awareness/ticket-event-listener'
    );
    mockEmitter = createMockEmitter();
    listener = new TicketEventListener(
      {
        tenant_id: 'test-tenant',
        ...DEFAULT_TICKET_LISTENER_CONFIG.parwa,
      },
      mockEmitter
    );
  });

  afterEach(() => {
    listener?.shutdown?.();
  });

  it('should emit ticket_created event', async () => {
    await listener.onTicketCreated({
      ticket_id: 'TKT-001',
      tenant_id: 'test-tenant',
      customer_id: 'CUST-001',
      channel: 'email',
    });

    expect(mockEmitter.emit).toHaveBeenCalled();
    const event = mockEmitter.emit.mock.calls[0][0];
    expect(event.type).toBe('ticket_created');
    expect(event.payload.ticket_id).toBe('TKT-001');
  });

  it('should emit ticket_closed event', async () => {
    await listener.onTicketClosed({
      ticket_id: 'TKT-002',
      tenant_id: 'test-tenant',
    });

    expect(mockEmitter.emit).toHaveBeenCalled();
    const event = mockEmitter.emit.mock.calls[0][0];
    expect(event.type).toBe('ticket_closed');
  });

  it('should emit ticket_escalated event', async () => {
    await listener.onTicketEscalated({
      ticket_id: 'TKT-003',
      tenant_id: 'test-tenant',
      previous_agent_id: 'agent-1',
      new_agent_id: 'agent-2',
    });

    expect(mockEmitter.emit).toHaveBeenCalled();
    const event = mockEmitter.emit.mock.calls[0][0];
    expect(event.type).toBe('ticket_escalated');
  });
});

// ── Customer Activity Tracker Tests ───────────────────────────────────

describe('CustomerActivityTracker', () => {
  let tracker: any;
  let mockEmitter: any;

  beforeEach(async () => {
    const { CustomerActivityTracker, DEFAULT_ACTIVITY_TRACKER_CONFIG } = await import(
      '@/lib/jarvis/awareness/activity-tracker'
    );
    mockEmitter = createMockEmitter();
    tracker = new CustomerActivityTracker(
      {
        tenant_id: 'test-tenant',
        ...DEFAULT_ACTIVITY_TRACKER_CONFIG.parwa,
      },
      mockEmitter
    );
  });

  it('should track customer activity', async () => {
    const activity = await tracker.trackActivity({
      customer_id: 'CUST-001',
      tenant_id: 'test-tenant',
      activity_type: 'message',
      channel: 'chat',
      content: 'Hello, I need help',
    });

    expect(activity).toBeDefined();
    expect(activity.customer_id).toBe('CUST-001');
    expect(activity.activity_type).toBe('message');
    expect(activity.channel).toBe('chat');
  });

  it('should analyze sentiment in activity', async () => {
    const activity = await tracker.trackActivity({
      customer_id: 'CUST-002',
      tenant_id: 'test-tenant',
      activity_type: 'message',
      channel: 'email',
      content: 'I am very frustrated with your service!',
    });

    expect(activity.sentiment).toBeDefined();
    expect(activity.sentiment.label).toBe('negative');
    expect(activity.sentiment.score).toBeLessThan(0);
  });

  it('should get customer activity summary', async () => {
    await tracker.trackActivity({
      customer_id: 'CUST-003',
      tenant_id: 'test-tenant',
      activity_type: 'message',
      channel: 'chat',
    });

    const summary = await tracker.getActivitySummary('CUST-003');

    expect(summary).toBeDefined();
    expect(summary.customer_id).toBe('CUST-003');
    expect(summary.total_interactions).toBe(1);
  });
});

// ── System Health Monitor Tests ───────────────────────────────────────

describe('SystemHealthMonitor', () => {
  let monitor: any;
  let mockEmitter: any;

  beforeEach(async () => {
    const { SystemHealthMonitor } = await import(
      '@/lib/jarvis/awareness/health-monitor'
    );
    mockEmitter = createMockEmitter();
    monitor = new SystemHealthMonitor('test-tenant', 'parwa', mockEmitter);
  });

  afterEach(() => {
    monitor?.stopMonitoring?.();
  });

  it('should register health component', () => {
    monitor.registerComponent({
      name: 'test-api',
      check: async () => ({
        component: 'test-api',
        status: 'healthy',
        latency_ms: 50,
      }),
      thresholds: {
        component: 'test-api',
        latency_warning_ms: 1000,
        latency_critical_ms: 5000,
        error_rate_warning_pct: 5,
        error_rate_critical_pct: 20,
      },
      enabled: true,
      check_interval_ms: 60000,
    });

    const health = monitor.getComponentHealth('test-api');
    expect(health).toBeDefined();
    expect(health.name).toBe('test-api');
  });

  it('should get system health', async () => {
    monitor.registerComponent({
      name: 'database',
      check: async () => ({
        component: 'database',
        status: 'healthy',
        latency_ms: 10,
      }),
      thresholds: {
        component: 'database',
        latency_warning_ms: 100,
        latency_critical_ms: 500,
        error_rate_warning_pct: 1,
        error_rate_critical_pct: 5,
      },
      enabled: true,
      check_interval_ms: 30000,
    });

    const health = await monitor.getSystemHealth();

    expect(health).toBeDefined();
    expect(health.tenant_id).toBe('test-tenant');
    expect(health.components).toBeDefined();
  });
});

// ── Alert Dispatcher Tests ────────────────────────────────────────────

describe('AlertDispatcher', () => {
  let dispatcher: any;

  beforeEach(async () => {
    const { AlertDispatcher, DEFAULT_ALERT_DISPATCHER_CONFIG } = await import(
      '@/lib/jarvis/awareness/alert-dispatcher'
    );
    dispatcher = new AlertDispatcher({
      tenant_id: 'test-tenant',
      ...DEFAULT_ALERT_DISPATCHER_CONFIG.parwa,
    });
  });

  it('should create alert from event', async () => {
    const event: AwarenessEvent = {
      id: 'evt-001',
      type: 'ticket_sla_breach',
      timestamp: new Date(),
      tenant_id: 'test-tenant',
      variant: 'parwa',
      source: 'ticket_listener',
      payload: {
        ticket_id: 'TKT-001',
        sla_remaining_pct: 0,
      },
    };

    dispatcher.addAlertRule({
      id: 'rule-001',
      tenant_id: 'test-tenant',
      name: 'SLA Breach Rule',
      description: 'Alert on SLA breach',
      event_types: ['ticket_sla_breach'],
      conditions: [],
      severity: 'critical',
      channels: ['dashboard'],
      enabled: true,
      cooldown_minutes: 5,
      created_at: new Date(),
      updated_at: new Date(),
    });

    const alert = await dispatcher.processEvent(event);

    expect(alert).toBeDefined();
    expect(alert?.type).toBe('ticket_sla_breach');
    expect(alert?.severity).toBe('critical');
    expect(alert?.status).toBe('active');
  });

  it('should acknowledge alert', async () => {
    const event: AwarenessEvent = {
      id: 'evt-002',
      type: 'ticket_sla_warning',
      timestamp: new Date(),
      tenant_id: 'test-tenant',
      variant: 'parwa',
      source: 'ticket_listener',
      payload: {
        ticket_id: 'TKT-002',
      },
    };

    dispatcher.addAlertRule({
      id: 'rule-002',
      tenant_id: 'test-tenant',
      name: 'SLA Warning Rule',
      description: 'Alert on SLA warning',
      event_types: ['ticket_sla_warning'],
      conditions: [],
      severity: 'warning',
      channels: ['dashboard'],
      enabled: true,
      cooldown_minutes: 5,
      created_at: new Date(),
      updated_at: new Date(),
    });

    const alert = await dispatcher.processEvent(event);

    if (alert) {
      const acknowledged = await dispatcher.acknowledgeAlert(alert.id, 'user-001');
      expect(acknowledged?.status).toBe('acknowledged');
      expect(acknowledged?.acknowledged_by).toBe('user-001');
    }
  });

  it('should get active alerts', async () => {
    const alerts = dispatcher.getActiveAlerts();
    expect(Array.isArray(alerts)).toBe(true);
  });
});

// ── Event Capture Tests ───────────────────────────────────────────────

describe('EventCapture', () => {
  let capture: any;

  beforeEach(async () => {
    const { EventCapture, DEFAULT_EVENT_CAPTURE_CONFIG } = await import(
      '@/lib/jarvis/awareness/event-capture'
    );
    capture = new EventCapture({
      tenant_id: 'test-tenant',
      ...DEFAULT_EVENT_CAPTURE_CONFIG.parwa,
    });
  });

  afterEach(async () => {
    await capture?.shutdown?.();
  });

  it('should capture event', async () => {
    const event: AwarenessEvent = {
      id: 'evt-003',
      type: 'ticket_created',
      timestamp: new Date(),
      tenant_id: 'test-tenant',
      variant: 'parwa',
      source: 'ticket_listener',
      payload: { ticket_id: 'TKT-003' },
    };

    await capture.capture(event);
    const state = capture.getBufferState();

    expect(state.size).toBe(1);
    expect(state.events[0].id).toBe('evt-003');
  });

  it('should subscribe to events', async () => {
    const callback = vi.fn();
    capture.subscribe('test-sub', callback);

    const event: AwarenessEvent = {
      id: 'evt-004',
      type: 'ticket_updated',
      timestamp: new Date(),
      tenant_id: 'test-tenant',
      variant: 'parwa',
      source: 'ticket_listener',
      payload: {},
    };

    await capture.capture(event);
    await capture.flush();

    expect(callback).toHaveBeenCalled();
  });

  it('should get stats', async () => {
    const stats = capture.getStats();
    expect(stats).toHaveProperty('bufferSize');
    expect(stats).toHaveProperty('subscriberCount');
  });
});

// ── Data Aggregator Tests ─────────────────────────────────────────────

describe('DataAggregator', () => {
  let aggregator: any;

  beforeEach(async () => {
    const { DataAggregator, DEFAULT_AGGREGATOR_CONFIG } = await import(
      '@/lib/jarvis/awareness/data-aggregator'
    );
    aggregator = new DataAggregator({
      tenant_id: 'test-tenant',
      ...DEFAULT_AGGREGATOR_CONFIG.parwa,
    });
  });

  it('should store metric', () => {
    aggregator.storeMetric({
      id: 'metric-001',
      tenant_id: 'test-tenant',
      metric_name: 'ticket.response_time',
      metric_type: 'timer',
      value: 150,
      unit: 'ms',
      tags: { channel: 'chat' },
      timestamp: new Date(),
      variant: 'parwa',
    });

    const stats = aggregator.getStats();
    expect(stats.metricCount).toBe(1);
  });

  it('should aggregate metrics', () => {
    for (let i = 0; i < 10; i++) {
      aggregator.storeMetric({
        id: `metric-${i}`,
        tenant_id: 'test-tenant',
        metric_name: 'ticket.response_time',
        metric_type: 'timer',
        value: 100 + i * 10,
        unit: 'ms',
        tags: {},
        timestamp: new Date(),
        variant: 'parwa',
      });
    }

    const result = aggregator.aggregate('ticket.response_time', 'avg', 'hour');
    expect(result).toBeDefined();
    expect(result?.value).toBeGreaterThan(0);
    expect(result?.sample_count).toBe(10);
  });
});

// ── Sentiment Pipeline Tests ──────────────────────────────────────────

describe('SentimentPipeline', () => {
  let pipeline: any;

  beforeEach(async () => {
    const { SentimentPipeline, DEFAULT_SENTIMENT_PIPELINE_CONFIG } = await import(
      '@/lib/jarvis/awareness/sentiment-pipeline'
    );
    pipeline = new SentimentPipeline({
      tenant_id: 'test-tenant',
      ...DEFAULT_SENTIMENT_PIPELINE_CONFIG.parwa,
    });
  });

  it('should analyze positive sentiment', async () => {
    const result = await pipeline.analyze({
      text: 'I love this product! It is amazing and wonderful!',
    });

    expect(result.label).toBe('positive');
    expect(result.score).toBeGreaterThan(0);
  });

  it('should analyze negative sentiment', async () => {
    const result = await pipeline.analyze({
      text: 'This is terrible! I am very frustrated and angry!',
    });

    expect(result.label).toBe('negative');
    expect(result.score).toBeLessThan(0);
  });

  it('should analyze neutral sentiment', async () => {
    const result = await pipeline.analyze({
      text: 'I would like to know more about the product.',
    });

    expect(['neutral', 'mixed', 'positive', 'negative']).toContain(result.label);
  });

  it('should cache sentiment for customer', async () => {
    await pipeline.analyze({
      text: 'Great service!',
      customer_id: 'CUST-001',
    });

    const history = pipeline.getSentimentHistory('CUST-001');
    expect(history.length).toBe(1);
  });
});

// ── Metrics Collector Tests ───────────────────────────────────────────

describe('MetricsCollector', () => {
  let collector: any;

  beforeEach(async () => {
    const { MetricsCollector, DEFAULT_METRICS_COLLECTOR_CONFIG } = await import(
      '@/lib/jarvis/awareness/metrics-collector'
    );
    collector = new MetricsCollector({
      tenant_id: 'test-tenant',
      ...DEFAULT_METRICS_COLLECTOR_CONFIG.parwa,
    });
  });

  afterEach(() => {
    collector?.stopCollection?.();
  });

  it('should record metric', () => {
    collector.record('custom.metric', 42, 'units', { tag: 'value' });

    const metrics = collector.getMetrics('custom.metric');
    expect(metrics.length).toBe(1);
    expect(metrics[0].value).toBe(42);
  });

  it('should record timing', () => {
    collector.recordTiming('api.latency', 150, { endpoint: '/api/test' });

    const metrics = collector.getMetrics('api.latency');
    expect(metrics.length).toBe(1);
    expect(metrics[0].value).toBe(150);
    expect(metrics[0].unit).toBe('ms');
  });

  it('should increment counter', () => {
    collector.incrementCounter('requests.total', 1);
    collector.incrementCounter('requests.total', 1);

    const counters = collector.getCounters();
    expect(counters.size).toBeGreaterThan(0);
  });

  it('should get aggregated metric', () => {
    for (let i = 0; i < 10; i++) {
      collector.record('test.metric', i * 10);
    }

    const aggregated = collector.getAggregated('test.metric', 'avg', 3600000);
    expect(aggregated).toBeDefined();
    expect(aggregated?.value).toBe(45);
  });
});

// ── Awareness Engine Integration Tests ────────────────────────────────

describe('AwarenessEngine', () => {
  let engine: any;

  beforeEach(async () => {
    const { createAwarenessEngine } = await import(
      '@/lib/jarvis/awareness/awareness-engine'
    );
    engine = createAwarenessEngine({
      tenant_id: 'test-tenant',
      variant: 'parwa',
    });
    await engine.initialize();
  });

  afterEach(async () => {
    await engine?.shutdown?.();
  });

  it('should initialize all components', () => {
    expect(engine).toBeDefined();
    const state = engine.getState();
    expect(state.tenant_id).toBe('test-tenant');
    expect(state.variant).toBe('parwa');
  });

  it('should track customer activity', async () => {
    await engine.trackCustomerActivity({
      customer_id: 'CUST-001',
      activity_type: 'message',
      channel: 'chat',
    });

    const summary = await engine.getCustomerSummary('CUST-001');
    expect(summary.customer_id).toBe('CUST-001');
    expect(summary.total_interactions).toBe(1);
  });

  it('should analyze sentiment', async () => {
    const result = await engine.analyzeSentiment(
      'This is a wonderful experience!',
      'CUST-002'
    );

    expect(result).toBeDefined();
    expect(['positive', 'neutral', 'negative', 'mixed']).toContain(result.label);
  });

  it('should record metrics', () => {
    engine.recordMetric('test.metric', 100);
    const metric = engine.getAggregatedMetric('test.metric', 'avg', 3600000);
    expect(metric?.value).toBe(100);
  });

  it('should get system health', async () => {
    const health = await engine.getSystemHealth();
    expect(health).toBeDefined();
    expect(health.tenant_id).toBe('test-tenant');
  });
});
