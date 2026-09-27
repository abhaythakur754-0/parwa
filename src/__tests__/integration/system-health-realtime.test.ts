/**
 * PARWA Integration Tests — System Health Real-Time Updates (Day 4)
 *
 * End-to-end integration tests verifying:
 * 1. Socket events → system health store → overall status
 * 2. Service degradation cascading to overall status
 * 3. Alert lifecycle: new → acknowledge → clear
 * 4. Maintenance mode flow
 * 5. Queue metrics integration
 */

import { useSystemHealthStore } from '@/lib/system-health-store';

// ── Setup ─────────────────────────────────────────────────────────────

beforeEach(() => {
  useSystemHealthStore.setState({
    overallStatus: 'healthy',
    services: [],
    queues: [],
    alerts: [],
    isMaintenance: false,
    maintenanceMessage: null,
    lastUpdated: null,
    isLoading: false,
  });
});

// ── Integration: Health Status Cascading ──────────────────────────────

describe('Integration: health status cascading', () => {
  it('should transition from healthy → degraded → down as services degrade', () => {
    const store = useSystemHealthStore.getState();

    // All healthy
    store.handleSystemHealth({
      services: [
        { name: 'api', status: 'healthy', latency_ms: 30, uptime: 99.9 },
        { name: 'database', status: 'healthy', latency_ms: 10, uptime: 99.99 },
      ],
    });
    expect(useSystemHealthStore.getState().overallStatus).toBe('healthy');

    // One degraded
    store.handleSystemHealth({
      services: [
        { name: 'api', status: 'healthy', latency_ms: 30, uptime: 99.9 },
        { name: 'database', status: 'degraded', latency_ms: 500, uptime: 95.0, message: 'Replication lag' },
      ],
    });
    expect(useSystemHealthStore.getState().overallStatus).toBe('degraded');

    // One down
    store.handleSystemHealth({
      services: [
        { name: 'api', status: 'healthy', latency_ms: 30, uptime: 99.9 },
        { name: 'database', status: 'down', latency_ms: 0, uptime: 0, message: 'Connection refused' },
      ],
    });
    expect(useSystemHealthStore.getState().overallStatus).toBe('down');
  });

  it('should recover from down to healthy', () => {
    const store = useSystemHealthStore.getState();

    // Down
    store.handleSystemHealth({
      services: [{ name: 'api', status: 'down', latency_ms: 0, uptime: 0 }],
    });
    expect(useSystemHealthStore.getState().overallStatus).toBe('down');

    // Recovered
    store.handleSystemHealth({
      services: [{ name: 'api', status: 'healthy', latency_ms: 40, uptime: 99.9 }],
    });
    expect(useSystemHealthStore.getState().overallStatus).toBe('healthy');
  });
});

// ── Integration: Partial Service Updates ──────────────────────────────

describe('Integration: partial service updates', () => {
  it('should merge partial updates without losing other services', () => {
    const store = useSystemHealthStore.getState();

    // Initial: 3 services
    store.handleSystemHealth({
      services: [
        { name: 'api', status: 'healthy', latency_ms: 30, uptime: 99.9 },
        { name: 'database', status: 'healthy', latency_ms: 10, uptime: 99.99 },
        { name: 'redis', status: 'healthy', latency_ms: 5, uptime: 99.95 },
      ],
    });

    // Partial update: only database changes
    store.handleSystemHealth({
      services: [
        { name: 'database', status: 'degraded', latency_ms: 300, uptime: 98.0 },
      ],
    });

    const state = useSystemHealthStore.getState();
    expect(state.services.length).toBe(3);
    expect(state.overallStatus).toBe('degraded');

    // Other services should be unchanged
    const api = state.services.find((s) => s.name === 'api');
    expect(api?.status).toBe('healthy');
    expect(api?.latencyMs).toBe(30);

    // Updated service
    const db = state.services.find((s) => s.name === 'database');
    expect(db?.status).toBe('degraded');
    expect(db?.latencyMs).toBe(300);
  });
});

// ── Integration: Alert Lifecycle ──────────────────────────────────────

describe('Integration: alert lifecycle', () => {
  it('should create alerts from system:error events and manage them', () => {
    const store = useSystemHealthStore.getState();

    // Error arrives
    store.handleSystemError({
      id: 'err-int-1',
      severity: 'critical',
      title: 'Database Connection Pool Exhausted',
      message: 'All 100 connections are in use',
      timestamp: new Date().toISOString(),
      service: 'database',
    });

    // Warning arrives
    store.handleSystemError({
      id: 'err-int-2',
      severity: 'warning',
      title: 'High Queue Depth',
      message: 'Default queue has 500 pending tasks',
      timestamp: new Date().toISOString(),
      service: 'celery',
    });

    let state = useSystemHealthStore.getState();
    expect(state.alerts.length).toBe(2);
    expect(state.getActiveAlerts().length).toBe(2);

    // Acknowledge one
    store.acknowledgeAlert('err-int-1');
    state = useSystemHealthStore.getState();
    expect(state.getActiveAlerts().length).toBe(1);
    expect(state.getActiveAlerts()[0].id).toBe('err-int-2');

    // Clear all
    store.clearAlerts();
    expect(useSystemHealthStore.getState().alerts.length).toBe(0);
  });

  it('should not duplicate alerts with same id', () => {
    const store = useSystemHealthStore.getState();

    store.handleSystemError({ id: 'dup-1', severity: 'error', title: 'T1', message: 'M1', timestamp: new Date().toISOString() });
    store.handleSystemError({ id: 'dup-1', severity: 'error', title: 'T1', message: 'M1', timestamp: new Date().toISOString() });

    expect(useSystemHealthStore.getState().alerts.length).toBe(1);
  });
});

// ── Integration: Maintenance Mode ─────────────────────────────────────

describe('Integration: maintenance mode flow', () => {
  it('should handle maintenance on → off lifecycle', () => {
    const store = useSystemHealthStore.getState();

    // Enter maintenance
    store.handleSystemMaintenance({
      is_maintenance: true,
      message: 'Database migration in progress (ETA: 30 min)',
    });

    let state = useSystemHealthStore.getState();
    expect(state.isMaintenance).toBe(true);
    expect(state.maintenanceMessage).toBe('Database migration in progress (ETA: 30 min)');

    // Should auto-create maintenance alert
    const maintenanceAlert = state.alerts.find((a) => a.type === 'maintenance');
    expect(maintenanceAlert).toBeDefined();

    // Exit maintenance
    store.handleSystemMaintenance({ is_maintenance: false });
    state = useSystemHealthStore.getState();
    expect(state.isMaintenance).toBe(false);
    expect(state.maintenanceMessage).toBeNull();
  });
});

// ── Integration: Queue Metrics ────────────────────────────────────────

describe('Integration: queue metrics updates', () => {
  it('should track queue metrics over time', () => {
    const store = useSystemHealthStore.getState();

    // Initial queue state
    store.handleSystemQueueDepth({
      queues: [
        { queue_name: 'default', pending: 10, active: 5, completed: 200, failed: 2 },
        { queue_name: 'priority', pending: 3, active: 2, completed: 100, failed: 0 },
      ],
    });

    let state = useSystemHealthStore.getState();
    expect(state.queues.length).toBe(2);

    // Queue state update — default queue grows
    store.handleSystemQueueDepth({
      queues: [
        { queue_name: 'default', pending: 50, active: 8, completed: 220, failed: 5 },
      ],
    });

    state = useSystemHealthStore.getState();
    // Priority queue should still be there
    expect(state.queues.length).toBe(2);

    // Default queue should be updated
    const defaultQ = state.queues.find((q) => q.queueName === 'default');
    expect(defaultQ?.pending).toBe(50);
    expect(defaultQ?.failed).toBe(5);

    // Priority queue unchanged
    const priorityQ = state.queues.find((q) => q.queueName === 'priority');
    expect(priorityQ?.pending).toBe(3);
  });
});

// ── Integration: Full Health → Alert → Recovery Flow ──────────────────

describe('Integration: full health monitoring flow', () => {
  it('should handle complete degradation and recovery cycle', () => {
    const store = useSystemHealthStore.getState();

    // 1. All healthy
    store.handleSystemHealth({
      services: [
        { name: 'api', status: 'healthy', latency_ms: 30, uptime: 99.9 },
        { name: 'redis', status: 'healthy', latency_ms: 5, uptime: 99.95 },
      ],
    });
    expect(useSystemHealthStore.getState().overallStatus).toBe('healthy');

    // 2. Redis starts degrading
    store.handleSystemHealth({
      services: [{ name: 'redis', status: 'degraded', latency_ms: 200, uptime: 97.0 }],
    });
    expect(useSystemHealthStore.getState().overallStatus).toBe('degraded');

    // 3. Error alert comes in
    store.handleSystemError({
      id: 'err-redis-1',
      severity: 'warning',
      title: 'Redis Memory Warning',
      message: 'Redis memory usage at 85%',
      timestamp: new Date().toISOString(),
      service: 'redis',
    });
    expect(useSystemHealthStore.getState().getActiveAlerts().length).toBe(1);

    // 4. Redis goes down
    store.handleSystemHealth({
      services: [{ name: 'redis', status: 'down', latency_ms: 0, uptime: 0 }],
    });
    expect(useSystemHealthStore.getState().overallStatus).toBe('down');

    // 5. Another error
    store.handleSystemError({
      id: 'err-redis-2',
      severity: 'critical',
      title: 'Redis Connection Lost',
      message: 'Cannot connect to Redis server',
      timestamp: new Date().toISOString(),
      service: 'redis',
    });
    expect(useSystemHealthStore.getState().getActiveAlerts().length).toBe(2);

    // 6. Acknowledge warnings
    store.acknowledgeAlert('err-redis-1');
    expect(useSystemHealthStore.getState().getActiveAlerts().length).toBe(1);

    // 7. Redis recovers
    store.handleSystemHealth({
      services: [{ name: 'redis', status: 'healthy', latency_ms: 8, uptime: 99.9 }],
    });
    expect(useSystemHealthStore.getState().overallStatus).toBe('healthy');

    // 8. Clear all alerts
    store.clearAlerts();
    expect(useSystemHealthStore.getState().alerts.length).toBe(0);
  });
});
