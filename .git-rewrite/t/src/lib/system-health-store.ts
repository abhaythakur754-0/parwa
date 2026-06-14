/**
 * PARWA System Health Store
 *
 * Zustand store for real-time system health monitoring.
 * Tracks service statuses, queue metrics, and active alerts.
 * Fed by Socket.io events and periodic API polling.
 */

import { create } from 'zustand';
import { v4 as uuid } from 'uuid';

// ── Types ────────────────────────────────────────────────────────────

export type HealthStatus = 'healthy' | 'degraded' | 'down';
export type ServiceName =
  | 'api'
  | 'database'
  | 'redis'
  | 'celery'
  | 'langgraph'
  | 'socketio'
  | 'email'
  | 'sms';

export interface ServiceHealth {
  name: ServiceName;
  status: HealthStatus;
  latencyMs: number;
  lastChecked: string;
  uptime: number;
  message?: string;
}

export interface QueueMetrics {
  queueName: string;
  pending: number;
  active: number;
  completed: number;
  failed: number;
}

export interface SystemAlert {
  id: string;
  type: 'error' | 'warning' | 'maintenance';
  title: string;
  message: string;
  timestamp: string;
  acknowledged: boolean;
  service?: ServiceName;
}

export interface SystemHealthState {
  overallStatus: HealthStatus;
  services: ServiceHealth[];
  queues: QueueMetrics[];
  alerts: SystemAlert[];
  isMaintenance: boolean;
  maintenanceMessage: string | null;
  lastUpdated: string | null;
  isLoading: boolean;

  // Socket.io event handlers
  handleSystemHealth: (data: any) => void;
  handleSystemQueueDepth: (data: any) => void;
  handleSystemError: (data: any) => void;
  handleSystemMaintenance: (data: any) => void;

  // API
  fetchSystemHealth: () => Promise<void>;

  // Actions
  acknowledgeAlert: (id: string) => void;
  clearAlerts: () => void;

  // Computed
  getUnhealthyServices: () => ServiceHealth[];
  getActiveAlerts: () => SystemAlert[];
  getServiceByName: (name: ServiceName) => ServiceHealth | undefined;
}

// ── Display Helpers ──────────────────────────────────────────────────

export const SERVICE_LABELS: Record<ServiceName, string> = {
  api: 'API Server',
  database: 'Database',
  redis: 'Redis Cache',
  celery: 'Celery Workers',
  langgraph: 'LangGraph Engine',
  socketio: 'WebSocket Server',
  email: 'Email Service',
  sms: 'SMS Service',
};

export const HEALTH_STATUS_LABELS: Record<HealthStatus, string> = {
  healthy: 'Healthy',
  degraded: 'Degraded',
  down: 'Down',
};

export const HEALTH_STATUS_COLORS: Record<HealthStatus, string> = {
  healthy: 'bg-emerald-400',
  degraded: 'bg-amber-400',
  down: 'bg-red-400',
};

export const HEALTH_STATUS_DOT_COLORS: Record<HealthStatus, string> = {
  healthy: 'text-emerald-500',
  degraded: 'text-amber-500',
  down: 'text-red-500',
};

export const ALERT_TYPE_COLORS: Record<SystemAlert['type'], string> = {
  error: 'from-red-500 to-red-400',
  warning: 'from-amber-500 to-amber-400',
  maintenance: 'from-zinc-500 to-zinc-400',
};

// ── Constants ────────────────────────────────────────────────────────

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// ── Helpers ──────────────────────────────────────────────────────────

function computeOverallStatus(services: ServiceHealth[]): HealthStatus {
  if (services.some((s) => s.status === 'down')) return 'down';
  if (services.some((s) => s.status === 'degraded')) return 'degraded';
  return 'healthy';
}

function normalizeServiceHealth(s: Record<string, unknown>): ServiceHealth {
  return {
    name: (s.name || s.service_name || 'api') as ServiceName,
    status: (s.status || 'healthy') as HealthStatus,
    latencyMs: Number(s.latency_ms ?? s.latencyMs ?? 0),
    lastChecked: String(s.last_checked || s.lastChecked || new Date().toISOString()),
    uptime: Number(s.uptime ?? 99.9),
    message: s.message ? String(s.message) : undefined,
  };
}

function normalizeQueueMetrics(q: Record<string, unknown>): QueueMetrics {
  return {
    queueName: String(q.queue_name || q.queueName || q.name || 'default'),
    pending: Number(q.pending ?? 0),
    active: Number(q.active ?? 0),
    completed: Number(q.completed ?? 0),
    failed: Number(q.failed ?? 0),
  };
}

// ── Store ────────────────────────────────────────────────────────────

export const useSystemHealthStore = create<SystemHealthState>((set, get) => ({
  overallStatus: 'healthy',
  services: [],
  queues: [],
  alerts: [],
  isMaintenance: false,
  maintenanceMessage: null,
  lastUpdated: null,
  isLoading: false,

  // ── Socket.io Event Handlers ─────────────────────────────────────

  handleSystemHealth: (data: any) => {
    const incomingServices: ServiceHealth[] = Array.isArray(data.services)
      ? data.services.map((s: Record<string, unknown>) => normalizeServiceHealth(s))
      : [];

    set((state) => {
      // Merge incoming services with existing — update by name
      const serviceMap = new Map(state.services.map((s) => [s.name, s]));
      for (const s of incomingServices) {
        serviceMap.set(s.name, s);
      }
      const services = Array.from(serviceMap.values());
      const overallStatus = computeOverallStatus(services);

      return {
        services,
        overallStatus,
        lastUpdated: new Date().toISOString(),
      };
    });
  },

  handleSystemQueueDepth: (data: any) => {
    const incomingQueues: QueueMetrics[] = Array.isArray(data.queues)
      ? data.queues.map((q: Record<string, unknown>) => normalizeQueueMetrics(q))
      : Array.isArray(data)
        ? data.map((q: Record<string, unknown>) => normalizeQueueMetrics(q))
        : [];

    if (incomingQueues.length === 0) return;

    set((state) => {
      // Merge by queueName
      const queueMap = new Map(state.queues.map((q) => [q.queueName, q]));
      for (const q of incomingQueues) {
        queueMap.set(q.queueName, q);
      }
      const queues = Array.from(queueMap.values());

      return {
        queues,
        lastUpdated: new Date().toISOString(),
      };
    });
  },

  handleSystemError: (data: any) => {
    const alert: SystemAlert = {
      id: String(data.id || uuid()),
      type: (data.severity === 'critical' || data.severity === 'error' ? 'error' : 'warning') as SystemAlert['type'],
      title: String(data.title || data.message || 'System Error'),
      message: String(data.message || data.description || ''),
      timestamp: String(data.timestamp || data.created_at || new Date().toISOString()),
      acknowledged: false,
      service: data.service ? (data.service as ServiceName) : undefined,
    };

    set((state) => {
      // Avoid duplicate alerts by id
      if (state.alerts.some((a) => a.id === alert.id)) {
        return state;
      }
      return {
        alerts: [alert, ...state.alerts],
        lastUpdated: new Date().toISOString(),
      };
    });
  },

  handleSystemMaintenance: (data: any) => {
    const isMaintenance = Boolean(data.is_maintenance ?? data.isMaintenance ?? data.active ?? false);
    const maintenanceMessage = isMaintenance
      ? String(data.message || data.maintenance_message || data.maintenanceMessage || 'System is under maintenance')
      : null;

    set({
      isMaintenance,
      maintenanceMessage,
      lastUpdated: new Date().toISOString(),
    });

    // If entering maintenance, also add a maintenance alert
    if (isMaintenance) {
      set((state) => ({
        alerts: [
          {
            id: uuid(),
            type: 'maintenance' as const,
            title: 'Scheduled Maintenance',
            message: maintenanceMessage || 'System is under maintenance',
            timestamp: new Date().toISOString(),
            acknowledged: false,
          },
          ...state.alerts,
        ],
      }));
    }
  },

  // ── API ──────────────────────────────────────────────────────────

  fetchSystemHealth: async () => {
    set({ isLoading: true });
    try {
      const res = await fetch(`${API_BASE}/api/v1/system/health`, {
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
      });

      if (!res.ok) {
        if (res.status === 404 || res.status === 502 || res.status === 503) {
          set({ isLoading: false });
          return;
        }
        throw new Error(`Failed to fetch system health: ${res.status}`);
      }

      const data = await res.json();

      // Parse services
      const rawServices = Array.isArray(data.services)
        ? data.services
        : Array.isArray(data)
          ? data
          : [];
      const services: ServiceHealth[] = rawServices.map((s: Record<string, unknown>) =>
        normalizeServiceHealth(s)
      );

      // Parse queues
      const rawQueues = Array.isArray(data.queues) ? data.queues : [];
      const queues: QueueMetrics[] = rawQueues.map((q: Record<string, unknown>) =>
        normalizeQueueMetrics(q)
      );

      // Parse alerts
      const rawAlerts = Array.isArray(data.alerts) ? data.alerts : [];
      const incomingAlerts: SystemAlert[] = rawAlerts.map((a: Record<string, unknown>) => ({
        id: String(a.id || uuid()),
        type: (a.type || 'warning') as SystemAlert['type'],
        title: String(a.title || 'Alert'),
        message: String(a.message || ''),
        timestamp: String(a.timestamp || a.created_at || new Date().toISOString()),
        acknowledged: Boolean(a.acknowledged ?? false),
        service: a.service ? (a.service as ServiceName) : undefined,
      }));

      const overallStatus = data.overall_status
        ? (data.overall_status as HealthStatus)
        : computeOverallStatus(services);

      const isMaintenance = Boolean(data.is_maintenance ?? data.isMaintenance ?? false);
      const maintenanceMessage = isMaintenance
        ? String(data.maintenance_message || data.maintenanceMessage || null)
        : null;

      set((state) => {
        // Merge alerts — keep existing acknowledged state
        const existingAlertMap = new Map(state.alerts.map((a) => [a.id, a]));
        const alerts = incomingAlerts.map((a) => {
          const existing = existingAlertMap.get(a.id);
          if (existing) {
            return { ...a, acknowledged: existing.acknowledged };
          }
          return a;
        });

        return {
          services,
          queues,
          overallStatus,
          isMaintenance,
          maintenanceMessage,
          alerts,
          lastUpdated: new Date().toISOString(),
          isLoading: false,
        };
      });
    } catch {
      // On error, keep existing state
      set({ isLoading: false });
    }
  },

  // ── Actions ──────────────────────────────────────────────────────

  acknowledgeAlert: (id: string) => {
    set((state) => ({
      alerts: state.alerts.map((a) =>
        a.id === id ? { ...a, acknowledged: true } : a
      ),
    }));
  },

  clearAlerts: () => {
    set({ alerts: [] });
  },

  // ── Computed ─────────────────────────────────────────────────────

  getUnhealthyServices: () => {
    return get().services.filter((s) => s.status !== 'healthy');
  },

  getActiveAlerts: () => {
    return get().alerts.filter((a) => !a.acknowledged);
  },

  getServiceByName: (name: ServiceName) => {
    return get().services.find((s) => s.name === name);
  },
}));
