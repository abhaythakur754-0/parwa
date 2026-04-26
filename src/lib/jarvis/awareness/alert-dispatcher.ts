/**
 * JARVIS Alert Dispatcher (Week 2 - Phase 1)
 *
 * Handles alert creation, routing, and delivery to appropriate channels.
 * Supports multi-channel alerts: dashboard, email, Slack, SMS, webhook
 */

import type {
  Alert,
  AlertSeverity,
  AlertChannel,
  AlertRule,
  AlertCondition,
  AlertAction,
  AwarenessEvent,
  AwarenessEventType,
} from '@/types/awareness';

// ── Alert Channel Handlers ───────────────────────────────────────────

export interface AlertChannelHandler {
  send(alert: Alert): Promise<{ success: boolean; error?: string }>;
  isAvailable(): boolean;
}

// ── Alert Dispatcher Configuration ───────────────────────────────────

export interface AlertDispatcherConfig {
  tenant_id: string;
  variant: 'mini_parwa' | 'parwa' | 'parwa_high';
  enabled_channels: AlertChannel[];
  cooldown_minutes: number;
  max_active_alerts: number;
  deduplication_window_minutes: number;
}

// ── Alert Dispatcher Class ───────────────────────────────────────────

export class AlertDispatcher {
  private config: AlertDispatcherConfig;
  private channelHandlers: Map<AlertChannel, AlertChannelHandler> = new Map();
  private activeAlerts: Map<string, Alert> = new Map();
  private alertRules: Map<string, AlertRule> = new Map();
  private lastAlertTime: Map<string, Date> = new Map();
  private alertHistory: Alert[] = [];
  private maxHistorySize = 1000;

  constructor(config: AlertDispatcherConfig) {
    this.config = config;
    this.registerDefaultChannelHandlers();
  }

  /**
   * Register a channel handler
   */
  registerChannelHandler(channel: AlertChannel, handler: AlertChannelHandler): void {
    this.channelHandlers.set(channel, handler);
  }

  /**
   * Process an awareness event and potentially create alerts
   */
  async processEvent(event: AwarenessEvent): Promise<Alert | null> {
    // Find matching rules
    const matchingRules = this.findMatchingRules(event);

    if (matchingRules.length === 0) {
      return null;
    }

    // Use the highest priority rule
    const rule = this.selectHighestPriorityRule(matchingRules);

    // Check cooldown
    if (this.isInCooldown(rule, event)) {
      return null;
    }

    // Check deduplication
    const dedupKey = this.getDeduplicationKey(event, rule);
    if (this.isDuplicateAlert(dedupKey)) {
      return null;
    }

    // Create alert
    const alert = await this.createAlert(event, rule);

    // Dispatch to channels
    await this.dispatchAlert(alert);

    // Update cooldown tracking
    this.lastAlertTime.set(rule.id, new Date());

    return alert;
  }

  /**
   * Create an alert from an event and rule
   */
  async createAlert(event: AwarenessEvent, rule: AlertRule): Promise<Alert> {
    const alert: Alert = {
      id: this.generateAlertId(),
      tenant_id: event.tenant_id,
      type: event.type,
      severity: rule.severity,
      title: this.generateAlertTitle(event),
      message: this.generateAlertMessage(event),
      source: event.source,
      status: 'active',
      created_at: new Date(),
      channels: this.filterChannelsByVariant(rule.channels),
      metadata: {
        event_id: event.id,
        rule_id: rule.id,
        event_payload: event.payload,
      },
      actions: this.generateActions(event),
    };

    // Store in active alerts
    this.activeAlerts.set(alert.id, alert);

    // Add to history
    this.alertHistory.push(alert);
    if (this.alertHistory.length > this.maxHistorySize) {
      this.alertHistory.shift();
    }

    return alert;
  }

  /**
   * Dispatch alert to configured channels
   */
  async dispatchAlert(alert: Alert): Promise<Map<AlertChannel, { success: boolean; error?: string }>> {
    const results = new Map<AlertChannel, { success: boolean; error?: string }>();

    for (const channel of alert.channels) {
      const handler = this.channelHandlers.get(channel);

      if (!handler || !handler.isAvailable()) {
        results.set(channel, { success: false, error: 'Channel not available' });
        continue;
      }

      try {
        const result = await handler.send(alert);
        results.set(channel, result);
      } catch (error) {
        results.set(channel, { success: false, error: (error as Error).message });
      }
    }

    return results;
  }

  /**
   * Acknowledge an alert
   */
  async acknowledgeAlert(
    alertId: string,
    acknowledgedBy: string,
    notes?: string
  ): Promise<Alert | null> {
    const alert = this.activeAlerts.get(alertId);
    if (!alert) return null;

    alert.status = 'acknowledged';
    alert.acknowledged_at = new Date();
    alert.acknowledged_by = acknowledgedBy;
    alert.metadata.acknowledgement_notes = notes;

    return alert;
  }

  /**
   * Resolve an alert
   */
  async resolveAlert(alertId: string, resolvedBy?: string): Promise<Alert | null> {
    const alert = this.activeAlerts.get(alertId);
    if (!alert) return null;

    alert.status = 'resolved';
    alert.resolved_at = new Date();
    alert.metadata.resolved_by = resolvedBy;

    // Remove from active alerts
    this.activeAlerts.delete(alertId);

    return alert;
  }

  /**
   * Get all active alerts
   */
  getActiveAlerts(options?: {
    severity?: AlertSeverity;
    type?: AwarenessEventType;
  }): Alert[] {
    let alerts = Array.from(this.activeAlerts.values());

    if (options?.severity) {
      alerts = alerts.filter((a) => a.severity === options.severity);
    }

    if (options?.type) {
      alerts = alerts.filter((a) => a.type === options.type);
    }

    return alerts.sort(
      (a, b) => b.created_at.getTime() - a.created_at.getTime()
    );
  }

  /**
   * Get alert by ID
   */
  getAlert(alertId: string): Alert | undefined {
    return this.activeAlerts.get(alertId) || this.alertHistory.find((a) => a.id === alertId);
  }

  /**
   * Add an alert rule
   */
  addAlertRule(rule: AlertRule): void {
    this.alertRules.set(rule.id, rule);
  }

  /**
   * Remove an alert rule
   */
  removeAlertRule(ruleId: string): boolean {
    return this.alertRules.delete(ruleId);
  }

  /**
   * Get all alert rules
   */
  getAlertRules(): AlertRule[] {
    return Array.from(this.alertRules.values());
  }

  /**
   * Get alert history
   */
  getAlertHistory(options?: {
    limit?: number;
    offset?: number;
    severity?: AlertSeverity;
  }): { alerts: Alert[]; total: number } {
    let alerts = [...this.alertHistory];

    if (options?.severity) {
      alerts = alerts.filter((a) => a.severity === options.severity);
    }

    const total = alerts.length;
    const offset = options?.offset || 0;
    const limit = options?.limit || 50;

    alerts = alerts
      .sort((a, b) => b.created_at.getTime() - a.created_at.getTime())
      .slice(offset, offset + limit);

    return { alerts, total };
  }

  // ── Private Methods ────────────────────────────────────────────────

  /**
   * Find rules matching the event
   */
  private findMatchingRules(event: AwarenessEvent): AlertRule[] {
    const matching: AlertRule[] = [];

    for (const rule of this.alertRules.values()) {
      if (!rule.enabled) continue;
      if (!rule.event_types.includes(event.type)) continue;

      // Check conditions
      if (this.matchesConditions(event, rule.conditions)) {
        matching.push(rule);
      }
    }

    return matching;
  }

  /**
   * Check if event matches all conditions
   */
  private matchesConditions(event: AwarenessEvent, conditions: AlertCondition[]): boolean {
    if (conditions.length === 0) return true;

    for (const condition of conditions) {
      const value = this.getNestedValue(event.payload, condition.field);

      switch (condition.operator) {
        case 'eq':
          if (value !== condition.value) return false;
          break;
        case 'neq':
          if (value === condition.value) return false;
          break;
        case 'gt':
          if (typeof value !== 'number' || value <= (condition.value as number))
            return false;
          break;
        case 'gte':
          if (typeof value !== 'number' || value < (condition.value as number))
            return false;
          break;
        case 'lt':
          if (typeof value !== 'number' || value >= (condition.value as number))
            return false;
          break;
        case 'lte':
          if (typeof value !== 'number' || value > (condition.value as number))
            return false;
          break;
        case 'contains':
          if (typeof value !== 'string' || !value.includes(condition.value as string))
            return false;
          break;
        case 'matches':
          if (typeof value !== 'string') return false;
          try {
            const regex = new RegExp(condition.value as string);
            if (!regex.test(value)) return false;
          } catch {
            return false;
          }
          break;
      }
    }

    return true;
  }

  /**
   * Get nested value from object
   */
  private getNestedValue(obj: Record<string, unknown>, path: string): unknown {
    return path.split('.').reduce((current, key) => {
      if (current && typeof current === 'object') {
        return (current as Record<string, unknown>)[key];
      }
      return undefined;
    }, obj as unknown);
  }

  /**
   * Select highest priority rule
   */
  private selectHighestPriorityRule(rules: AlertRule[]): AlertRule {
    const severityPriority: Record<AlertSeverity, number> = {
      critical: 4,
      warning: 3,
      info: 2,
      opportunity: 1,
    };

    return rules.sort(
      (a, b) => severityPriority[b.severity] - severityPriority[a.severity]
    )[0];
  }

  /**
   * Check if rule is in cooldown
   */
  private isInCooldown(rule: AlertRule, event: AwarenessEvent): boolean {
    const lastTime = this.lastAlertTime.get(rule.id);
    if (!lastTime) return false;

    const cooldownMs = rule.cooldown_minutes * 60 * 1000;
    return Date.now() - lastTime.getTime() < cooldownMs;
  }

  /**
   * Check for duplicate alert
   */
  private isDuplicateAlert(dedupKey: string): boolean {
    const recentAlerts = this.alertHistory.filter(
      (a) =>
        Date.now() - a.created_at.getTime() <
        this.config.deduplication_window_minutes * 60 * 1000
    );
    return recentAlerts.some((a) => a.metadata.dedup_key === dedupKey);
  }

  /**
   * Generate deduplication key
   */
  private getDeduplicationKey(event: AwarenessEvent, rule: AlertRule): string {
    return `${event.type}_${rule.id}_${event.tenant_id}`;
  }

  /**
   * Filter channels based on variant
   */
  private filterChannelsByVariant(channels: AlertChannel[]): AlertChannel[] {
    const variantChannels: Record<string, AlertChannel[]> = {
      mini_parwa: ['dashboard'],
      parwa: ['dashboard', 'email', 'slack'],
      parwa_high: ['dashboard', 'email', 'slack', 'sms', 'webhook'],
    };

    const allowed = variantChannels[this.config.variant] || ['dashboard'];
    return channels.filter((c) => allowed.includes(c) && this.config.enabled_channels.includes(c));
  }

  /**
   * Generate alert title
   */
  private generateAlertTitle(event: AwarenessEvent): string {
    const titles: Record<AwarenessEventType, string> = {
      ticket_created: 'New Ticket Created',
      ticket_updated: 'Ticket Updated',
      ticket_assigned: 'Ticket Assigned',
      ticket_closed: 'Ticket Closed',
      ticket_escalated: 'Ticket Escalated',
      ticket_reopened: 'Ticket Reopened',
      ticket_priority_changed: 'Ticket Priority Changed',
      ticket_sla_breach: 'SLA Breach Detected',
      ticket_sla_warning: 'SLA Warning',
      customer_message_received: 'Customer Message Received',
      customer_sentiment_changed: 'Customer Sentiment Changed',
      customer_churn_risk: 'Churn Risk Alert',
      customer_resolved: 'Customer Issue Resolved',
      system_health_degraded: 'System Health Degraded',
      system_health_recovered: 'System Health Recovered',
      agent_performance_drop: 'Agent Performance Drop Detected',
      queue_buildup_detected: 'Queue Buildup Detected',
      high_volume_spike: 'High Volume Spike',
      alert_triggered: 'Alert Triggered',
      alert_acknowledged: 'Alert Acknowledged',
      alert_resolved: 'Alert Resolved',
      alert_escalated: 'Alert Escalated',
    };

    return titles[event.type] || `Alert: ${event.type}`;
  }

  /**
   * Generate alert message
   */
  private generateAlertMessage(event: AwarenessEvent): string {
    const payload = event.payload;
    const ticketId = payload.ticket_id ? `Ticket #${payload.ticket_id}` : '';
    const customerId = payload.customer_id ? `Customer: ${payload.customer_id}` : '';

    switch (event.type) {
      case 'ticket_sla_breach':
        return `SLA breach detected for ${ticketId}. Immediate attention required.`;
      case 'ticket_sla_warning':
        return `SLA warning for ${ticketId}. ${payload.sla_remaining_pct}% time remaining.`;
      case 'customer_sentiment_changed':
        return `Sentiment changed for ${customerId}. Current: ${(payload.current_sentiment as { label?: string })?.label || 'unknown'}`;
      case 'customer_churn_risk':
        return `Churn risk detected for ${customerId}. Risk score: ${payload.risk_score}`;
      case 'system_health_degraded':
        return `System health degraded. Component: ${payload.component}`;
      case 'system_health_recovered':
        return `System health recovered. Component: ${payload.component}`;
      case 'queue_buildup_detected':
        return `Queue buildup detected. Current queue size: ${payload.queue_size}`;
      case 'high_volume_spike':
        return `High volume spike detected. Current: ${payload.current_volume}`;
      default:
        return `${event.type} event from ${event.source}`;
    }
  }

  /**
   * Generate actions for an alert
   */
  private generateActions(event: AwarenessEvent): AlertAction[] {
    const actions: AlertAction[] = [];
    const payload = event.payload;

    switch (event.type) {
      case 'ticket_sla_breach':
      case 'ticket_sla_warning':
        if (payload.ticket_id) {
          actions.push({
            id: 'view_ticket',
            label: 'View Ticket',
            type: 'execute',
            endpoint: `/dashboard/tickets/${payload.ticket_id}`,
          });
          actions.push({
            id: 'assign_agent',
            label: 'Assign Agent',
            type: 'draft',
            command: `assign ticket ${payload.ticket_id} to`,
          });
        }
        break;
      case 'customer_churn_risk':
        if (payload.customer_id) {
          actions.push({
            id: 'view_customer',
            label: 'View Customer',
            type: 'execute',
            endpoint: `/dashboard/customers/${payload.customer_id}`,
          });
          actions.push({
            id: 'create_followup',
            label: 'Create Follow-up',
            type: 'draft',
            command: `create followup for customer ${payload.customer_id}`,
          });
        }
        break;
      case 'system_health_degraded':
        actions.push({
          id: 'view_health',
          label: 'View Health Dashboard',
          type: 'execute',
          endpoint: '/dashboard/system-health',
        });
        break;
    }

    return actions;
  }

  /**
   * Register default channel handlers
   */
  private registerDefaultChannelHandlers(): void {
    // Dashboard handler (always available)
    this.registerChannelHandler('dashboard', {
      isAvailable: () => true,
      send: async (alert) => {
        // In production, this would push to a WebSocket or similar
        console.log(`[Dashboard Alert] ${alert.title}: ${alert.message}`);
        return { success: true };
      },
    });

    // Email handler
    this.registerChannelHandler('email', {
      isAvailable: () => true, // Would check if email service is configured
      send: async (alert) => {
        console.log(`[Email Alert] ${alert.title}: ${alert.message}`);
        // Would integrate with email service
        return { success: true };
      },
    });

    // Slack handler
    this.registerChannelHandler('slack', {
      isAvailable: () => false, // Would check if Slack is configured
      send: async (alert) => {
        console.log(`[Slack Alert] ${alert.title}: ${alert.message}`);
        return { success: false, error: 'Slack not configured' };
      },
    });

    // SMS handler
    this.registerChannelHandler('sms', {
      isAvailable: () => false, // Would check if SMS is configured
      send: async (alert) => {
        console.log(`[SMS Alert] ${alert.title}: ${alert.message}`);
        return { success: false, error: 'SMS not configured' };
      },
    });

    // Webhook handler
    this.registerChannelHandler('webhook', {
      isAvailable: () => false, // Would check if webhooks are configured
      send: async (alert) => {
        console.log(`[Webhook Alert] ${alert.title}: ${alert.message}`);
        return { success: false, error: 'Webhook not configured' };
      },
    });
  }

  /**
   * Generate unique alert ID
   */
  private generateAlertId(): string {
    return `alert_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * Update configuration
   */
  updateConfig(config: Partial<AlertDispatcherConfig>): void {
    this.config = { ...this.config, ...config };
  }

  /**
   * Clear all active alerts
   */
  clearAllAlerts(): void {
    this.activeAlerts.clear();
  }

  /**
   * Get active alert count
   */
  getActiveAlertCount(): number {
    return this.activeAlerts.size;
  }
}

// ── Factory Function ─────────────────────────────────────────────────

export function createAlertDispatcher(
  config: AlertDispatcherConfig
): AlertDispatcher {
  return new AlertDispatcher(config);
}

// ── Default Configuration by Variant ─────────────────────────────────

export const DEFAULT_ALERT_DISPATCHER_CONFIG: Record<
  string,
  Omit<AlertDispatcherConfig, 'tenant_id'>
> = {
  mini_parwa: {
    variant: 'mini_parwa',
    enabled_channels: ['dashboard'],
    cooldown_minutes: 30,
    max_active_alerts: 10,
    deduplication_window_minutes: 15,
  },
  parwa: {
    variant: 'parwa',
    enabled_channels: ['dashboard', 'email', 'slack'],
    cooldown_minutes: 15,
    max_active_alerts: 50,
    deduplication_window_minutes: 10,
  },
  parwa_high: {
    variant: 'parwa_high',
    enabled_channels: ['dashboard', 'email', 'slack', 'sms', 'webhook'],
    cooldown_minutes: 5,
    max_active_alerts: 100,
    deduplication_window_minutes: 5,
  },
};

// ── Default Alert Rules ──────────────────────────────────────────────

export const DEFAULT_ALERT_RULES: Omit<AlertRule, 'tenant_id' | 'id' | 'created_at' | 'updated_at'>[] = [
  {
    name: 'SLA Breach Alert',
    description: 'Alert when a ticket SLA is breached',
    event_types: ['ticket_sla_breach'],
    conditions: [],
    severity: 'critical',
    channels: ['dashboard', 'email'],
    enabled: true,
    cooldown_minutes: 5,
  },
  {
    name: 'SLA Warning Alert',
    description: 'Alert when a ticket is approaching SLA deadline',
    event_types: ['ticket_sla_warning'],
    conditions: [],
    severity: 'warning',
    channels: ['dashboard'],
    enabled: true,
    cooldown_minutes: 10,
  },
  {
    name: 'Churn Risk Alert',
    description: 'Alert when a customer shows churn risk signs',
    event_types: ['customer_churn_risk'],
    conditions: [],
    severity: 'warning',
    channels: ['dashboard', 'email'],
    enabled: true,
    cooldown_minutes: 60,
  },
  {
    name: 'System Health Critical',
    description: 'Alert when system health is critical',
    event_types: ['system_health_degraded'],
    conditions: [{ field: 'new_status', operator: 'eq', value: 'critical' }],
    severity: 'critical',
    channels: ['dashboard', 'email', 'slack'],
    enabled: true,
    cooldown_minutes: 5,
  },
  {
    name: 'Negative Sentiment Alert',
    description: 'Alert when customer sentiment turns negative',
    event_types: ['customer_sentiment_changed'],
    conditions: [{ field: 'current_sentiment.label', operator: 'eq', value: 'negative' }],
    severity: 'info',
    channels: ['dashboard'],
    enabled: true,
    cooldown_minutes: 30,
  },
];
