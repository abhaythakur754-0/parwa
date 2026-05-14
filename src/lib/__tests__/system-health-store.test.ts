/**
 * PARWA System Health Store — Unit Tests (Day 4)
 *
 * Tests system health monitoring: service status, queue metrics,
 * alerts, maintenance mode, and Socket.io event handlers.
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

// ── handleSystemHealth (Socket.io handler) ─────────────────────────────

describe('system-health-store: handleSystemHealth', () => {
  it('should update services and compute overall status', () => {
    const store = useSystemHealthStore.getState();
    store.handleSystemHealth({
      services: [
        { name: 'api', status: 'healthy', latency_ms: 45, uptime: 99.9 },
        { name: 'database', status: 'healthy', latency_ms: 12, uptime: 99.99 },
        { name: 'redis', status: 'degraded', latency_ms: 200, uptime: 98.5, message: 'High memory usage' },
      ],
    });

    const state = useSystemHealthStore.getState();
    expect(state.services.length).toBe(3);
    expect(state.overallStatus).toBe('degraded');
    expect(state.lastUpdated).toBeDefined();
  });

  it('should set overallStatus to "down" if any service is down', () => {
    const store = useSystemHealthStore.getState();
    store.handleSystemHealth({
      services: [
        { name: 'api', status: 'healthy', latency_ms: 45, uptime: 99.9 },
        { name: 'email', status: 'down', latency_ms: 0, uptime: 0, message: 'SMTP timeout' },
      ],
    });

    expect(useSystemHealthStore.getState().overallStatus).toBe('down');
  });

  it('should merge services by name (update existing)', () => {
    const store = useSystemHealthStore.getState();

    // First update
    store.handleSystemHealth({
      services: [{ name: 'api', status: 'healthy', latency_ms: 45, uptime: 99.9 }],
    });

    // Second update — same service, different status
    store.handleSystemHealth({
      services: [{ name: 'api', status: 'degraded', latency_ms: 300, uptime: 99.5 }],
    });

    const state = useSystemHealthStore.getState();
    expect(state.services.length).toBe(1);
    expect(state.services[0].status).toBe('degraded');
    expect(state.services[0].latencyMs).toBe(300);
  });

  it('should set overallStatus to "healthy" when all services are healthy', () => {
    const store = useSystemHealthStore.getState();
    store.handleSystemHealth({
      services: [
        { name: 'api', status: 'healthy', latency_ms: 45, uptime: 99.9 },
        { name: 'database', status: 'healthy', latency_ms: 10, uptime: 99.99 },
      ],
    });

    expect(useSystemHealthStore.getState().overallStatus).toBe('healthy');
  });
});

// ── handleSystemQueueDepth (Socket.io handler) ────────────────────────

describe('system-health-store: handleSystemQueueDepth', () => {
  it('should update queue metrics', () => {
    const store = useSystemHealthStore.getState();
    store.handleSystemQueueDepth({
      queues: [
        { queue_name: 'default', pending: 5, active: 3, completed: 100, failed: 2 },
        { queue_name: 'priority', pending: 1, active: 1, completed: 50, failed: 0 },
      ],
    });

    const state = useSystemHealthStore.getState();
    expect(state.queues.length).toBe(2);
    expect(state.queues[0].queueName).toBe('default');
    expect(state.queues[0].pending).toBe(5);
  });

  it('should merge queues by name', () => {
    const store = useSystemHealthStore.getState();

    store.handleSystemQueueDepth({
      queues: [{ queue_name: 'default', pending: 5, active: 3, completed: 100, failed: 2 }],
    });

    store.handleSystemQueueDepth({
      queues: [{ queue_name: 'default', pending: 10, active: 2, completed: 120, failed: 3 }],
    });

    const state = useSystemHealthStore.getState();
    expect(state.queues.length).toBe(1);
    expect(state.queues[0].pending).toBe(10);
  });

  it('should accept array format directly', () => {
    const store = useSystemHealthStore.getState();
    store.handleSystemQueueDepth([
      { queue_name: 'emails', pending: 2, active: 1, completed: 30, failed: 0 },
    ]);

    expect(useSystemHealthStore.getState().queues.length).toBe(1);
  });
});

// ── handleSystemError (Socket.io handler) ──────────────────────────────

describe('system-health-store: handleSystemError', () => {
  it('should add an error alert', () => {
    const store = useSystemHealthStore.getState();
    store.handleSystemError({
      id: 'err-1',
      severity: 'critical',
      title: 'Database Connection Failed',
      message: 'Unable to connect to primary database',
      timestamp: new Date().toISOString(),
      service: 'database',
    });

    const state = useSystemHealthStore.getState();
    expect(state.alerts.length).toBe(1);
    expect(state.alerts[0].type).toBe('error');
    expect(state.alerts[0].service).toBe('database');
  });

  it('should map non-critical severity to warning type', () => {
    const store = useSystemHealthStore.getState();
    store.handleSystemError({
      id: 'warn-1',
      severity: 'warning',
      title: 'High Queue Depth',
      message: 'Queue depth exceeds threshold',
      timestamp: new Date().toISOString(),
    });

    expect(useSystemHealthStore.getState().alerts[0].type).toBe('warning');
  });

  it('should not add duplicate alerts by id', () => {
    const store = useSystemHealthStore.getState();
    store.handleSystemError({ id: 'dup-1', severity: 'error', title: 'T1', message: 'M1', timestamp: new Date().toISOString() });
    store.handleSystemError({ id: 'dup-1', severity: 'error', title: 'T1', message: 'M1', timestamp: new Date().toISOString() });

    expect(useSystemHealthStore.getState().alerts.length).toBe(1);
  });
});

// ── handleSystemMaintenance (Socket.io handler) ───────────────────────

describe('system-health-store: handleSystemMaintenance', () => {
  it('should set maintenance mode on', () => {
    const store = useSystemHealthStore.getState();
    store.handleSystemMaintenance({
      is_maintenance: true,
      message: 'Scheduled maintenance from 2AM-4AM UTC',
    });

    const state = useSystemHealthStore.getState();
    expect(state.isMaintenance).toBe(true);
    expect(state.maintenanceMessage).toBe('Scheduled maintenance from 2AM-4AM UTC');
  });

  it('should clear maintenance mode', () => {
    const store = useSystemHealthStore.getState();
    store.handleSystemMaintenance({ is_maintenance: true, message: 'Under maintenance' });
    store.handleSystemMaintenance({ is_maintenance: false });

    expect(useSystemHealthStore.getState().isMaintenance).toBe(false);
    expect(useSystemHealthStore.getState().maintenanceMessage).toBeNull();
  });

  it('should add a maintenance alert when entering maintenance', () => {
    const store = useSystemHealthStore.getState();
    store.handleSystemMaintenance({ is_maintenance: true, message: 'DB upgrade' });

    const state = useSystemHealthStore.getState();
    const maintenanceAlert = state.alerts.find((a) => a.type === 'maintenance');
    expect(maintenanceAlert).toBeDefined();
    expect(maintenanceAlert?.message).toContain('DB upgrade');
  });
});

// ── acknowledgeAlert ──────────────────────────────────────────────────

describe('system-health-store: acknowledgeAlert', () => {
  it('should mark alert as acknowledged', () => {
    const store = useSystemHealthStore.getState();
    store.handleSystemError({ id: 'err-1', severity: 'error', title: 'T1', message: 'M1', timestamp: new Date().toISOString() });

    store.acknowledgeAlert('err-1');

    const alert = useSystemHealthStore.getState().alerts.find((a) => a.id === 'err-1');
    expect(alert?.acknowledged).toBe(true);
  });
});

// ── clearAlerts ───────────────────────────────────────────────────────

describe('system-health-store: clearAlerts', () => {
  it('should remove all alerts', () => {
    const store = useSystemHealthStore.getState();
    store.handleSystemError({ id: 'err-1', severity: 'error', title: 'T1', message: 'M1', timestamp: new Date().toISOString() });
    store.handleSystemError({ id: 'err-2', severity: 'warning', title: 'T2', message: 'M2', timestamp: new Date().toISOString() });

    store.clearAlerts();

    expect(useSystemHealthStore.getState().alerts.length).toBe(0);
  });
});

// ── Computed: getUnhealthyServices ────────────────────────────────────

describe('system-health-store: getUnhealthyServices', () => {
  it('should return only non-healthy services', () => {
    const store = useSystemHealthStore.getState();
    store.handleSystemHealth({
      services: [
        { name: 'api', status: 'healthy', latency_ms: 45, uptime: 99.9 },
        { name: 'database', status: 'degraded', latency_ms: 200, uptime: 98.5 },
        { name: 'email', status: 'down', latency_ms: 0, uptime: 0 },
      ],
    });

    const unhealthy = store.getUnhealthyServices();
    expect(unhealthy.length).toBe(2);
    expect(unhealthy.map((s) => s.name)).toEqual(expect.arrayContaining(['database', 'email']));
  });
});

// ── Computed: getActiveAlerts ─────────────────────────────────────────

describe('system-health-store: getActiveAlerts', () => {
  it('should return only unacknowledged alerts', () => {
    const store = useSystemHealthStore.getState();
    store.handleSystemError({ id: 'err-1', severity: 'error', title: 'T1', message: 'M1', timestamp: new Date().toISOString() });
    store.handleSystemError({ id: 'err-2', severity: 'warning', title: 'T2', message: 'M2', timestamp: new Date().toISOString() });

    store.acknowledgeAlert('err-1');

    const active = store.getActiveAlerts();
    expect(active.length).toBe(1);
    expect(active[0].id).toBe('err-2');
  });
});

// ── Computed: getServiceByName ────────────────────────────────────────

describe('system-health-store: getServiceByName', () => {
  it('should find service by name', () => {
    const store = useSystemHealthStore.getState();
    store.handleSystemHealth({
      services: [{ name: 'api', status: 'healthy', latency_ms: 45, uptime: 99.9 }],
    });

    const api = store.getServiceByName('api');
    expect(api).toBeDefined();
    expect(api?.status).toBe('healthy');
  });

  it('should return undefined for unknown service', () => {
    expect(useSystemHealthStore.getState().getServiceByName('nonexistent')).toBeUndefined();
  });
});

// ── fetchSystemHealth (API) ───────────────────────────────────────────

describe('system-health-store: fetchSystemHealth', () => {
  it('should handle 404 gracefully', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({ ok: false, status: 404 });

    await useSystemHealthStore.getState().fetchSystemHealth();

    expect(useSystemHealthStore.getState().isLoading).toBe(false);
  });

  it('should parse and set health data from API', async () => {
    const mockData = {
      services: [
        { name: 'api', status: 'healthy', latency_ms: 50, uptime: 99.9 },
      ],
      queues: [
        { queue_name: 'default', pending: 3, active: 2, completed: 200, failed: 1 },
      ],
      overall_status: 'healthy',
    };

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockData),
    });

    await useSystemHealthStore.getState().fetchSystemHealth();

    const state = useSystemHealthStore.getState();
    expect(state.services.length).toBe(1);
    expect(state.queues.length).toBe(1);
    expect(state.overallStatus).toBe('healthy');
    expect(state.isLoading).toBe(false);
  });
});
