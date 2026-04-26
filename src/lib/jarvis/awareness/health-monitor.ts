/**
 * JARVIS System Health Monitor (Week 2 - Phase 1)
 *
 * Monitors system health, component status, and emits health-related events.
 * Handles: component health checks, latency monitoring, error rate tracking
 */

import type {
  AwarenessEvent,
  HealthStatus,
  ComponentHealth,
  SystemHealth,
  HealthCheckResult,
  HealthThreshold,
} from '@/types/awareness';

// ── Event Emitter Interface ──────────────────────────────────────────

export interface EventEmitter {
  emit(event: AwarenessEvent): Promise<void>;
}

// ── Health Check Function Type ───────────────────────────────────────

export type HealthCheckFunction = () => Promise<HealthCheckResult>;

// ── Component Definition ─────────────────────────────────────────────

export interface ComponentDefinition {
  name: string;
  check: HealthCheckFunction;
  thresholds: HealthThreshold;
  enabled: boolean;
  check_interval_ms: number;
}

// ── System Health Monitor Class ──────────────────────────────────────

export class SystemHealthMonitor {
  private tenantId: string;
  private variant: 'mini_parwa' | 'parwa' | 'parwa_high';
  private eventEmitter: EventEmitter;
  private components: Map<string, ComponentDefinition> = new Map();
  private healthCache: Map<string, ComponentHealth> = new Map();
  private checkIntervals: Map<string, NodeJS.Timeout> = new Map();
  private lastHealthStatus: HealthStatus = 'unknown';
  private incidentCount24h: number = 0;
  private lastIncidentReset: Date = new Date();

  constructor(
    tenantId: string,
    variant: 'mini_parwa' | 'parwa' | 'parwa_high',
    emitter: EventEmitter
  ) {
    this.tenantId = tenantId;
    this.variant = variant;
    this.eventEmitter = emitter;
  }

  /**
   * Register a component for health monitoring
   */
  registerComponent(definition: ComponentDefinition): void {
    this.components.set(definition.name, definition);

    // Initialize health cache
    this.healthCache.set(definition.name, {
      name: definition.name,
      status: 'unknown',
      last_check: new Date(),
    });
  }

  /**
   * Start monitoring all registered components
   */
  startMonitoring(): void {
    for (const [name, component] of this.components) {
      if (component.enabled) {
        this.startComponentMonitoring(name);
      }
    }
  }

  /**
   * Stop all monitoring
   */
  stopMonitoring(): void {
    for (const timer of this.checkIntervals.values()) {
      clearInterval(timer);
    }
    this.checkIntervals.clear();
  }

  /**
   * Get current system health
   */
  async getSystemHealth(): Promise<SystemHealth> {
    // Reset incident counter every 24 hours
    this.resetIncidentCounterIfNeeded();

    // Collect all component health
    const components: ComponentHealth[] = [];
    let overallStatus: HealthStatus = 'healthy';
    let totalUptime = 0;
    let healthyCount = 0;

    for (const [name, health] of this.healthCache) {
      components.push(health);
      if (health.status === 'healthy') {
        healthyCount++;
      } else if (health.status === 'degraded' && overallStatus === 'healthy') {
        overallStatus = 'degraded';
      } else if (health.status === 'critical') {
        overallStatus = 'critical';
      }
    }

    // Calculate uptime percentage
    if (components.length > 0) {
      totalUptime = (healthyCount / components.length) * 100;
    }

    // Check for status change
    if (overallStatus !== this.lastHealthStatus) {
      await this.handleHealthStatusChange(overallStatus);
    }

    this.lastHealthStatus = overallStatus;

    return {
      tenant_id: this.tenantId,
      overall_status: overallStatus,
      components,
      checked_at: new Date(),
      uptime_percentage: totalUptime,
      incident_count_24h: this.incidentCount24h,
    };
  }

  /**
   * Get health for a specific component
   */
  getComponentHealth(componentName: string): ComponentHealth | undefined {
    return this.healthCache.get(componentName);
  }

  /**
   * Run a single health check for a component
   */
  async checkComponent(componentName: string): Promise<ComponentHealth> {
    const component = this.components.get(componentName);
    if (!component) {
      return {
        name: componentName,
        status: 'unknown',
        last_check: new Date(),
        message: 'Component not registered',
      };
    }

    try {
      const result = await component.check();
      const health: ComponentHealth = {
        name: result.component,
        status: result.status,
        latency_ms: result.latency_ms,
        last_check: new Date(),
        message: result.message,
        details: result.details,
      };

      // Determine status based on thresholds
      const status = this.evaluateThresholds(health, component.thresholds);
      health.status = status;

      // Update cache
      this.healthCache.set(componentName, health);

      return health;
    } catch (error) {
      const health: ComponentHealth = {
        name: componentName,
        status: 'critical',
        last_check: new Date(),
        message: `Health check failed: ${(error as Error).message}`,
      };

      this.healthCache.set(componentName, health);
      return health;
    }
  }

  /**
   * Start monitoring a specific component
   */
  private startComponentMonitoring(componentName: string): void {
    const component = this.components.get(componentName);
    if (!component) return;

    // Clear existing interval
    const existing = this.checkIntervals.get(componentName);
    if (existing) {
      clearInterval(existing);
    }

    // Run initial check
    this.checkComponent(componentName);

    // Set up periodic checks
    const interval = setInterval(async () => {
      const previousHealth = this.healthCache.get(componentName);
      await this.checkComponent(componentName);
      const newHealth = this.healthCache.get(componentName);

      // Check for status change
      if (previousHealth && newHealth && previousHealth.status !== newHealth.status) {
        await this.handleComponentStatusChange(componentName, previousHealth.status, newHealth.status);
      }
    }, component.check_interval_ms);

    this.checkIntervals.set(componentName, interval);
  }

  /**
   * Evaluate component health against thresholds
   */
  private evaluateThresholds(
    health: ComponentHealth,
    thresholds: HealthThreshold
  ): HealthStatus {
    // Check latency
    if (health.latency_ms !== undefined) {
      if (health.latency_ms >= thresholds.latency_critical_ms) {
        return 'critical';
      }
      if (health.latency_ms >= thresholds.latency_warning_ms) {
        return 'degraded';
      }
    }

    // Check error rate
    if (health.error_rate !== undefined) {
      if (health.error_rate >= thresholds.error_rate_critical_pct) {
        return 'critical';
      }
      if (health.error_rate >= thresholds.error_rate_warning_pct) {
        return 'degraded';
      }
    }

    return health.status;
  }

  /**
   * Handle component status change
   */
  private async handleComponentStatusChange(
    componentName: string,
    previousStatus: HealthStatus,
    newStatus: HealthStatus
  ): Promise<void> {
    // Increment incident counter for critical status
    if (newStatus === 'critical') {
      this.incidentCount24h++;
    }

    // Emit event based on transition
    if (newStatus === 'critical' || newStatus === 'degraded') {
      const eventType = newStatus === 'critical'
        ? 'system_health_degraded'
        : 'system_health_degraded';

      const event: AwarenessEvent = {
        id: this.generateEventId(),
        type: eventType,
        timestamp: new Date(),
        tenant_id: this.tenantId,
        variant: this.variant,
        source: 'health_monitor',
        payload: {
          component: componentName,
          previous_status: previousStatus,
          new_status: newStatus,
          health: this.healthCache.get(componentName),
        },
      };
      await this.eventEmitter.emit(event);
    } else if (newStatus === 'healthy' && previousStatus !== 'healthy') {
      const event: AwarenessEvent = {
        id: this.generateEventId(),
        type: 'system_health_recovered',
        timestamp: new Date(),
        tenant_id: this.tenantId,
        variant: this.variant,
        source: 'health_monitor',
        payload: {
          component: componentName,
          previous_status: previousStatus,
          new_status: newStatus,
          health: this.healthCache.get(componentName),
        },
      };
      await this.eventEmitter.emit(event);
    }
  }

  /**
   * Handle overall system health status change
   */
  private async handleHealthStatusChange(newStatus: HealthStatus): Promise<void> {
    if (newStatus === 'critical' || newStatus === 'degraded') {
      const event: AwarenessEvent = {
        id: this.generateEventId(),
        type: 'system_health_degraded',
        timestamp: new Date(),
        tenant_id: this.tenantId,
        variant: this.variant,
        source: 'health_monitor',
        payload: {
          overall_status: newStatus,
          previous_status: this.lastHealthStatus,
        },
      };
      await this.eventEmitter.emit(event);
    } else if (newStatus === 'healthy' && this.lastHealthStatus !== 'healthy') {
      const event: AwarenessEvent = {
        id: this.generateEventId(),
        type: 'system_health_recovered',
        timestamp: new Date(),
        tenant_id: this.tenantId,
        variant: this.variant,
        source: 'health_monitor',
        payload: {
          overall_status: newStatus,
          previous_status: this.lastHealthStatus,
        },
      };
      await this.eventEmitter.emit(event);
    }
  }

  /**
   * Reset incident counter if 24 hours have passed
   */
  private resetIncidentCounterIfNeeded(): void {
    const now = new Date();
    const hoursSinceReset =
      (now.getTime() - this.lastIncidentReset.getTime()) / (60 * 60 * 1000);

    if (hoursSinceReset >= 24) {
      this.incidentCount24h = 0;
      this.lastIncidentReset = now;
    }
  }

  /**
   * Generate unique event ID
   */
  private generateEventId(): string {
    return `evt_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * Add a simple HTTP health check component
   */
  addHttpHealthCheck(
    name: string,
    url: string,
    thresholds: Partial<HealthThreshold> = {},
    intervalMs: number = 60000
  ): void {
    const defaultThresholds: HealthThreshold = {
      component: name,
      latency_warning_ms: 1000,
      latency_critical_ms: 5000,
      error_rate_warning_pct: 5,
      error_rate_critical_pct: 20,
    };

    const check: HealthCheckFunction = async () => {
      const start = Date.now();
      try {
        const response = await fetch(url, { method: 'GET' });
        const latency = Date.now() - start;

        return {
          component: name,
          status: response.ok ? 'healthy' : 'degraded',
          latency_ms: latency,
          message: response.ok ? 'OK' : `HTTP ${response.status}`,
          details: {
            status_code: response.status,
            url,
          },
        };
      } catch (error) {
        return {
          component: name,
          status: 'critical' as HealthStatus,
          latency_ms: Date.now() - start,
          message: `Connection failed: ${(error as Error).message}`,
        };
      }
    };

    this.registerComponent({
      name,
      check,
      thresholds: { ...defaultThresholds, ...thresholds },
      enabled: true,
      check_interval_ms: intervalMs,
    });
  }

  /**
   * Add a database health check component
   */
  addDatabaseHealthCheck(
    name: string,
    checkFn: () => Promise<{ latency_ms: number; error?: string }>,
    thresholds: Partial<HealthThreshold> = {},
    intervalMs: number = 30000
  ): void {
    const defaultThresholds: HealthThreshold = {
      component: name,
      latency_warning_ms: 100,
      latency_critical_ms: 500,
      error_rate_warning_pct: 1,
      error_rate_critical_pct: 5,
    };

    const check: HealthCheckFunction = async () => {
      try {
        const result = await checkFn();
        return {
          component: name,
          status: result.error ? 'critical' : 'healthy',
          latency_ms: result.latency_ms,
          message: result.error || 'Database connection OK',
        };
      } catch (error) {
        return {
          component: name,
          status: 'critical' as HealthStatus,
          latency_ms: 0,
          message: `Database check failed: ${(error as Error).message}`,
        };
      }
    };

    this.registerComponent({
      name,
      check,
      thresholds: { ...defaultThresholds, ...thresholds },
      enabled: true,
      check_interval_ms: intervalMs,
    });
  }
}

// ── Factory Function ─────────────────────────────────────────────────

export function createHealthMonitor(
  tenantId: string,
  variant: 'mini_parwa' | 'parwa' | 'parwa_high',
  emitter: EventEmitter
): SystemHealthMonitor {
  return new SystemHealthMonitor(tenantId, variant, emitter);
}

// ── Default Check Intervals by Variant ───────────────────────────────

export const DEFAULT_CHECK_INTERVALS: Record<string, number> = {
  mini_parwa: 60000, // 1 minute
  parwa: 30000, // 30 seconds
  parwa_high: 15000, // 15 seconds
};
