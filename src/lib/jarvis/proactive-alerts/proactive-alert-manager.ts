/**
 * JARVIS Proactive Alert Manager - Week 6 (Phase 2)
 *
 * Main coordinator for proactive alerts.
 * Manages SLA monitoring, escalation detection, and sentiment alerts.
 */

import type { Variant } from '@/types/variant';
import type { AlertSeverity } from '@/types/awareness';
import { 
  DEFAULT_PROACTIVE_ALERTS_CONFIG,
  PROACTIVE_ALERTS_VARIANT_LIMITS,
} from './types';
import type {
  ProactiveAlert,
  ProactiveAlertType,
  AlertUrgency,
  AlertState,
  ProactiveAlertsConfig,
  ProactiveAlertsStats,
  ProactiveAlertEvent,
  ProactiveAlertEventType,
  SLATicketStatus,
  SLABreachPrediction,
  EscalationRule,
  EscalationStatus,
  SentimentStatus,
  SentimentAlert,
  RecommendedAction,
} from './types';

// ── Event Emitter ─────────────────────────────────────────────────────

type EventCallback = (event: ProactiveAlertEvent) => void;

class ProactiveEventEmitter {
  private listeners: Map<ProactiveAlertEventType, Set<EventCallback>> = new Map();

  on(event: ProactiveAlertEventType, callback: EventCallback): () => void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event)!.add(callback);
    return () => this.listeners.get(event)?.delete(callback);
  }

  emit(event: ProactiveAlertEvent): void {
    const callbacks = this.listeners.get(event.type);
    if (callbacks) {
      for (const callback of callbacks) {
        try {
          callback(event);
        } catch (error) {
          console.error('Proactive alert event callback error:', error);
        }
      }
    }
  }

  clear(): void {
    this.listeners.clear();
  }
}

// ── Alert Store ───────────────────────────────────────────────────────

class ProactiveAlertStore {
  private alerts: Map<string, ProactiveAlert> = new Map();
  private byTarget: Map<string, Set<string>> = new Map();
  private byType: Map<ProactiveAlertType, Set<string>> = new Map();
  private maxAlerts: number;

  constructor(maxAlerts: number = 1000) {
    this.maxAlerts = maxAlerts;
  }

  add(alert: ProactiveAlert): void {
    this.alerts.set(alert.id, alert);

    // Index by target
    const targetKey = `${alert.target_type}:${alert.target_id}`;
    if (!this.byTarget.has(targetKey)) {
      this.byTarget.set(targetKey, new Set());
    }
    this.byTarget.get(targetKey)!.add(alert.id);

    // Index by type
    if (!this.byType.has(alert.type)) {
      this.byType.set(alert.type, new Set());
    }
    this.byType.get(alert.type)!.add(alert.id);

    // Evict old alerts if needed
    if (this.alerts.size > this.maxAlerts) {
      this.evictOldest();
    }
  }

  get(id: string): ProactiveAlert | undefined {
    return this.alerts.get(id);
  }

  update(id: string, updates: Partial<ProactiveAlert>): ProactiveAlert | undefined {
    const alert = this.alerts.get(id);
    if (!alert) return undefined;

    const updated = { ...alert, ...updates, updated_at: new Date() };
    this.alerts.set(id, updated);
    return updated;
  }

  delete(id: string): boolean {
    const alert = this.alerts.get(id);
    if (!alert) return false;

    this.alerts.delete(id);
    const targetKey = `${alert.target_type}:${alert.target_id}`;
    this.byTarget.get(targetKey)?.delete(id);
    this.byType.get(alert.type)?.delete(id);
    return true;
  }

  getByTarget(targetType: string, targetId: string): ProactiveAlert[] {
    const targetKey = `${targetType}:${targetId}`;
    const ids = this.byTarget.get(targetKey);
    if (!ids) return [];

    return Array.from(ids)
      .map(id => this.alerts.get(id))
      .filter((a): a is ProactiveAlert => a !== undefined);
  }

  getByType(type: ProactiveAlertType): ProactiveAlert[] {
    const ids = this.byType.get(type);
    if (!ids) return [];

    return Array.from(ids)
      .map(id => this.alerts.get(id))
      .filter((a): a is ProactiveAlert => a !== undefined);
  }

  getActive(): ProactiveAlert[] {
    return Array.from(this.alerts.values())
      .filter(a => a.state !== 'resolved' && a.state !== 'expired');
  }

  count(): number {
    return this.alerts.size;
  }

  clear(): void {
    this.alerts.clear();
    this.byTarget.clear();
    this.byType.clear();
  }

  private evictOldest(): void {
    const sorted = Array.from(this.alerts.values())
      .filter(a => a.state === 'resolved' || a.state === 'expired')
      .sort((a, b) => a.created_at.getTime() - b.created_at.getTime());

    for (let i = 0; i < Math.min(sorted.length, 100); i++) {
      this.delete(sorted[i].id);
    }
  }
}

// ── Proactive Alert Manager ────────────────────────────────────────────

export class ProactiveAlertManager {
  private config: ProactiveAlertsConfig;
  private variant: Variant;
  private variantLimits: typeof PROACTIVE_ALERTS_VARIANT_LIMITS[Variant];
  private store: ProactiveAlertStore;
  private eventEmitter: ProactiveEventEmitter;
  
  // SLA tracking
  private slaTickets: Map<string, SLATicketStatus> = new Map();
  
  // Escalation tracking
  private escalationRules: Map<string, EscalationRule> = new Map();
  private escalationStatuses: Map<string, EscalationStatus> = new Map();
  
  // Sentiment tracking
  private sentimentStatuses: Map<string, SentimentStatus> = new Map();
  
  // Statistics
  private stats: ProactiveAlertsStats = {
    total_alerts_generated: 0,
    alerts_by_type: {} as Record<ProactiveAlertType, number>,
    alerts_by_severity: {} as Record<AlertSeverity, number>,
    avg_resolution_time_ms: 0,
    avg_acknowledgement_time_ms: 0,
    sla_stats: {
      breaches_prevented: 0,
      predictions_made: 0,
      prediction_accuracy: 0,
    },
    escalation_stats: {
      total_escalations: 0,
      auto_escalations: 0,
      avg_time_to_escalate_ms: 0,
    },
    sentiment_stats: {
      alerts_triggered: 0,
      avg_sentiment_score: 0,
      declining_customers_detected: 0,
    },
  };

  // Check intervals
  private slaCheckInterval: NodeJS.Timeout | null = null;
  private escalationCheckInterval: NodeJS.Timeout | null = null;
  private sentimentCheckInterval: NodeJS.Timeout | null = null;

  constructor(config: ProactiveAlertsConfig) {
    this.config = config;
    this.variant = config.variant;
    this.variantLimits = PROACTIVE_ALERTS_VARIANT_LIMITS[config.variant];
    this.store = new ProactiveAlertStore(this.config.max_active_alerts);
    this.eventEmitter = new ProactiveEventEmitter();
    
    this.initializeDefaultRules();
    this.startMonitoring();
  }

  // ── SLA Monitoring ───────────────────────────────────────────────────

  /**
   * Track a ticket for SLA monitoring
   */
  trackSLATicket(
    ticketId: string,
    slaDeadline: Date,
    slaType: SLATicketStatus['sla_type'] = 'resolution'
  ): SLATicketStatus {
    const now = new Date();
    const created_at = now;
    const timeRemainingMs = slaDeadline.getTime() - now.getTime();
    const totalDurationMs = slaDeadline.getTime() - created_at.getTime();
    const pctRemaining = totalDurationMs > 0 ? (timeRemainingMs / totalDurationMs) * 100 : 0;

    let status: SLATicketStatus['status'] = 'on_track';
    if (timeRemainingMs <= 0) {
      status = 'breached';
    } else if (pctRemaining <= this.config.sla_monitoring.critical_threshold_pct) {
      status = 'critical';
    } else if (pctRemaining <= this.config.sla_monitoring.warning_threshold_pct) {
      status = 'warning';
    }

    const slaStatus: SLATicketStatus = {
      ticket_id: ticketId,
      sla_type: slaType,
      sla_deadline: slaDeadline,
      created_at,
      status,
      time_remaining_ms: timeRemainingMs,
      pct_remaining: pctRemaining,
    };

    // Predict breach if enabled
    if (this.variantLimits.sla_prediction && this.config.sla_monitoring.prediction_enabled) {
      const prediction = this.predictSLABreach(slaStatus);
      if (prediction) {
        slaStatus.predicted_breach = true;
        slaStatus.predicted_breach_time = prediction.predicted_breach_time;
        slaStatus.at_risk_reasons = prediction.contributing_factors;
      }
    }

    this.slaTickets.set(ticketId, slaStatus);

    // Generate alert if needed
    if (status === 'critical' || status === 'warning') {
      this.generateSLAAlert(slaStatus);
    }

    return slaStatus;
  }

  /**
   * Update SLA status for a ticket
   */
  updateSLATicket(ticketId: string, updates: Partial<SLATicketStatus>): SLATicketStatus | undefined {
    const status = this.slaTickets.get(ticketId);
    if (!status) return undefined;

    const updated = { ...status, ...updates };
    this.slaTickets.set(ticketId, updated);
    return updated;
  }

  /**
   * Remove ticket from SLA monitoring
   */
  untrackSLATicket(ticketId: string): boolean {
    return this.slaTickets.delete(ticketId);
  }

  /**
   * Get SLA status for a ticket
   */
  getSLAStatus(ticketId: string): SLATicketStatus | undefined {
    return this.slaTickets.get(ticketId);
  }

  /**
   * Get all tickets at risk
   */
  getTicketsAtRisk(): SLATicketStatus[] {
    return Array.from(this.slaTickets.values())
      .filter(s => s.status === 'warning' || s.status === 'critical' || s.predicted_breach);
  }

  // ── Escalation Management ────────────────────────────────────────────

  /**
   * Check if ticket needs escalation
   */
  checkEscalationNeeded(
    ticketId: string,
    ticketData: {
      priority: string;
      status: string;
      created_at: Date;
      customer_tier?: string;
      current_agent_id?: string;
    }
  ): EscalationStatus | null {
    if (!this.config.escalation.enabled) return null;

    const matchingRules = this.findMatchingEscalationRules(ticketData);
    if (matchingRules.length === 0) return null;

    const rule = matchingRules[0]; // Use highest priority rule
    const existingStatus = this.escalationStatuses.get(ticketId);

    if (existingStatus) {
      return this.checkNextEscalation(existingStatus, rule, ticketData);
    }

    // Create new escalation status
    const status: EscalationStatus = {
      ticket_id: ticketId,
      current_level: 0,
      escalation_history: [],
    };

    // Check if should escalate immediately
    const timeInStatus = Date.now() - ticketData.created_at.getTime();
    if (timeInStatus > rule.auto_escalate_after_minutes * 60 * 1000) {
      this.performEscalation(status, rule, 1, 'Auto-escalation: time threshold exceeded');
    }

    this.escalationStatuses.set(ticketId, status);
    return status;
  }

  /**
   * Add escalation rule
   */
  addEscalationRule(rule: EscalationRule): void {
    this.escalationRules.set(rule.id, rule);
  }

  /**
   * Remove escalation rule
   */
  removeEscalationRule(ruleId: string): boolean {
    return this.escalationRules.delete(ruleId);
  }

  /**
   * Get escalation status for a ticket
   */
  getEscalationStatus(ticketId: string): EscalationStatus | undefined {
    return this.escalationStatuses.get(ticketId);
  }

  // ── Sentiment Monitoring ─────────────────────────────────────────────

  /**
   * Track sentiment for a customer/ticket
   */
  trackSentiment(
    customerId: string,
    ticketId: string,
    sentiment: SentimentStatus['current_sentiment']
  ): SentimentStatus | null {
    if (!this.variantLimits.sentiment_tracking) return null;

    const key = `${customerId}:${ticketId}`;
    const existing = this.sentimentStatuses.get(key);

    if (existing) {
      // Update trend
      const prevScore = existing.current_sentiment.score;
      const newScore = sentiment.score;
      const scoreChange = newScore - prevScore;

      let trend: SentimentStatus['sentiment_trend'] = 'stable';
      if (scoreChange < -this.config.sentiment_monitoring.declining_threshold) {
        trend = 'declining';
      } else if (scoreChange > this.config.sentiment_monitoring.declining_threshold) {
        trend = 'improving';
      }

      if (newScore < this.config.sentiment_monitoring.negative_threshold) {
        trend = 'critical';
      }

      const updated: SentimentStatus = {
        ...existing,
        current_sentiment: sentiment,
        sentiment_trend: trend,
        trend_strength: Math.abs(scoreChange),
        messages_analyzed: existing.messages_analyzed + 1,
        last_analyzed_at: new Date(),
        alert_triggered: trend === 'critical' || trend === 'declining',
      };

      this.sentimentStatuses.set(key, updated);

      // Generate alert if needed
      if (updated.alert_triggered && !existing.alert_triggered) {
        this.generateSentimentAlert(customerId, ticketId, existing.current_sentiment, sentiment);
      }

      return updated;
    }

    // Create new status
    const status: SentimentStatus = {
      customer_id: customerId,
      ticket_id: ticketId,
      current_sentiment: sentiment,
      sentiment_trend: sentiment.score < this.config.sentiment_monitoring.negative_threshold ? 'critical' : 'stable',
      trend_strength: 0,
      messages_analyzed: 1,
      last_analyzed_at: new Date(),
      alert_triggered: sentiment.score < this.config.sentiment_monitoring.negative_threshold,
    };

    this.sentimentStatuses.set(key, status);

    if (status.alert_triggered) {
      this.generateSentimentAlert(customerId, ticketId, undefined, sentiment);
    }

    return status;
  }

  /**
   * Get sentiment status
   */
  getSentimentStatus(customerId: string, ticketId: string): SentimentStatus | undefined {
    return this.sentimentStatuses.get(`${customerId}:${ticketId}`);
  }

  /**
   * Get customers with declining sentiment
   */
  getDecliningSentimentCustomers(): SentimentStatus[] {
    return Array.from(this.sentimentStatuses.values())
      .filter(s => s.sentiment_trend === 'declining' || s.sentiment_trend === 'critical');
  }

  // ── Alert Management ────────────────────────────────────────────────

  /**
   * Get active alerts
   */
  getActiveAlerts(): ProactiveAlert[] {
    return this.store.getActive();
  }

  /**
   * Get alert by ID
   */
  getAlert(alertId: string): ProactiveAlert | undefined {
    return this.store.get(alertId);
  }

  /**
   * Get alerts for a target
   */
  getAlertsForTarget(targetType: string, targetId: string): ProactiveAlert[] {
    return this.store.getByTarget(targetType, targetId);
  }

  /**
   * Acknowledge an alert
   */
  acknowledgeAlert(alertId: string, acknowledgedBy: string): ProactiveAlert | undefined {
    const alert = this.store.update(alertId, {
      state: 'acknowledged',
      acknowledged_at: new Date(),
      acknowledged_by: acknowledgedBy,
    });

    if (alert) {
      this.emitEvent('proactive_alert_acknowledged', alert.tenant_id, { alert_id: alertId, acknowledged_by: acknowledgedBy });
    }

    return alert;
  }

  /**
   * Resolve an alert
   */
  resolveAlert(alertId: string, resolvedBy: string, note?: string): ProactiveAlert | undefined {
    const alert = this.store.update(alertId, {
      state: 'resolved',
      resolved_at: new Date(),
      resolved_by: resolvedBy,
      resolution_note: note,
    });

    if (alert) {
      this.emitEvent('proactive_alert_resolved', alert.tenant_id, { alert_id: alertId, resolved_by: resolvedBy });
    }

    return alert;
  }

  // ── Statistics ───────────────────────────────────────────────────────

  /**
   * Get statistics
   */
  getStats(): ProactiveAlertsStats {
    return { ...this.stats };
  }

  // ── Events ───────────────────────────────────────────────────────────

  /**
   * Subscribe to events
   */
  onEvent(event: ProactiveAlertEventType, callback: (event: ProactiveAlertEvent) => void): () => void {
    return this.eventEmitter.on(event, callback);
  }

  // ── Shutdown ────────────────────────────────────────────────────────

  /**
   * Shutdown the manager
   */
  shutdown(): void {
    if (this.slaCheckInterval) clearInterval(this.slaCheckInterval);
    if (this.escalationCheckInterval) clearInterval(this.escalationCheckInterval);
    if (this.sentimentCheckInterval) clearInterval(this.sentimentCheckInterval);
    
    this.store.clear();
    this.slaTickets.clear();
    this.escalationStatuses.clear();
    this.sentimentStatuses.clear();
    this.eventEmitter.clear();
  }

  // ── Private Methods ────────────────────────────────────────────────

  private initializeDefaultRules(): void {
    // Default escalation rule
    this.addEscalationRule({
      id: 'default_priority_escalation',
      tenant_id: this.config.tenant_id,
      name: 'Priority Ticket Escalation',
      description: 'Escalate high priority tickets that are not addressed',
      conditions: [
        { type: 'priority_level', operator: 'eq', value: 'high' },
      ],
      levels: [
        { level: 1, notify_roles: ['team_lead'], notify_channels: ['dashboard', 'email'], time_limit_minutes: 30 },
        { level: 2, notify_roles: ['manager'], notify_channels: ['dashboard', 'email', 'sms'], time_limit_minutes: 60 },
        { level: 3, notify_roles: ['director'], notify_channels: ['dashboard', 'email', 'sms'], time_limit_minutes: 120 },
      ],
      auto_escalate_after_minutes: 30,
      max_escalation_level: this.variantLimits.max_escalation_levels,
      enabled: true,
      priority: 1,
      created_at: new Date(),
      updated_at: new Date(),
    });
  }

  private startMonitoring(): void {
    // SLA monitoring
    this.slaCheckInterval = setInterval(() => {
      this.checkSLATickets();
    }, this.config.sla_monitoring.check_interval_seconds * 1000);

    // Escalation monitoring
    this.escalationCheckInterval = setInterval(() => {
      this.checkEscalations();
    }, 60000); // Every minute

    // Sentiment monitoring
    this.sentimentCheckInterval = setInterval(() => {
      this.checkSentimentStatuses();
    }, this.config.sentiment_monitoring.check_interval_seconds * 1000);
  }

  private checkSLATickets(): void {
    const now = new Date();

    for (const [ticketId, status] of this.slaTickets) {
      const timeRemainingMs = status.sla_deadline.getTime() - now.getTime();
      const totalDurationMs = status.sla_deadline.getTime() - status.created_at.getTime();
      const pctRemaining = totalDurationMs > 0 ? (timeRemainingMs / totalDurationMs) * 100 : 0;

      // Update status
      let newStatus = status.status;
      if (timeRemainingMs <= 0) {
        newStatus = 'breached';
      } else if (pctRemaining <= this.config.sla_monitoring.critical_threshold_pct) {
        newStatus = 'critical';
      } else if (pctRemaining <= this.config.sla_monitoring.warning_threshold_pct) {
        newStatus = 'warning';
      }

      if (newStatus !== status.status) {
        this.updateSLATicket(ticketId, { status: newStatus, time_remaining_ms: timeRemainingMs, pct_remaining: pctRemaining });
        
        if (newStatus === 'critical' || newStatus === 'warning') {
          this.generateSLAAlert({ ...status, status: newStatus, time_remaining_ms: timeRemainingMs, pct_remaining: pctRemaining });
        }
      }
    }
  }

  private checkEscalations(): void {
    if (!this.config.escalation.auto_escalate) return;

    for (const [ticketId, status] of this.escalationStatuses) {
      const rule = this.findMatchingEscalationRules({} as any)[0];
      if (!rule) continue;

      const lastEscalation = status.escalation_history[status.escalation_history.length - 1];
      if (!lastEscalation) continue;

      const level = rule.levels.find(l => l.level === status.current_level);
      if (!level?.time_limit_minutes) continue;

      const timeSinceEscalation = Date.now() - lastEscalation.timestamp.getTime();
      if (timeSinceEscalation > level.time_limit_minutes * 60 * 1000) {
        if (status.current_level < rule.max_escalation_level) {
          this.performEscalation(status, rule, status.current_level + 1, 'Auto-escalation: response time exceeded');
        }
      }
    }
  }

  private checkSentimentStatuses(): void {
    // Sentiment is updated on-demand, this is just for cleanup
    const cutoff = new Date(Date.now() - 24 * 60 * 60 * 1000); // 24 hours
    
    for (const [key, status] of this.sentimentStatuses) {
      if (status.last_analyzed_at < cutoff) {
        this.sentimentStatuses.delete(key);
      }
    }
  }

  private predictSLABreach(status: SLATicketStatus): SLABreachPrediction | null {
    // Simple prediction based on time remaining and historical patterns
    const timeRemainingMs = status.time_remaining_ms;
    const predictionHorizonMs = this.config.sla_monitoring.prediction_horizon_hours * 60 * 60 * 1000;

    if (timeRemainingMs > predictionHorizonMs) return null;

    // Calculate predicted breach time based on average resolution time
    // In production, this would use ML models
    const avgResolutionTimeMs = 4 * 60 * 60 * 1000; // 4 hours average
    const predictedBreachTime = new Date(Date.now() + avgResolutionTimeMs - timeRemainingMs);

    if (predictedBreachTime > status.sla_deadline) {
      this.stats.sla_stats.predictions_made++;
      return {
        ticket_id: status.ticket_id,
        sla_type: status.sla_type,
        predicted_breach_time: predictedBreachTime,
        confidence: 0.7,
        contributing_factors: ['Limited time remaining', 'Historical resolution patterns'],
        recommended_interventions: ['Reassign to available agent', 'Escalate to team lead'],
      };
    }

    return null;
  }

  private findMatchingEscalationRules(ticketData: Record<string, unknown>): EscalationRule[] {
    return Array.from(this.escalationRules.values())
      .filter(rule => rule.enabled && rule.tenant_id === this.config.tenant_id)
      .sort((a, b) => a.priority - b.priority);
  }

  private checkNextEscalation(
    status: EscalationStatus,
    rule: EscalationRule,
    ticketData: Record<string, unknown>
  ): EscalationStatus | null {
    const lastEscalation = status.escalation_history[status.escalation_history.length - 1];
    if (!lastEscalation) return null;

    const timeSinceEscalation = Date.now() - lastEscalation.timestamp.getTime();
    const level = rule.levels.find(l => l.level === status.current_level);

    if (level?.time_limit_minutes && timeSinceEscalation > level.time_limit_minutes * 60 * 1000) {
      if (status.current_level < rule.max_escalation_level) {
        this.performEscalation(status, rule, status.current_level + 1, 'Time limit exceeded');
      }
    }

    return status;
  }

  private performEscalation(
    status: EscalationStatus,
    rule: EscalationRule,
    newLevel: number,
    reason: string
  ): void {
    const level = rule.levels.find(l => l.level === newLevel);
    if (!level) return;

    status.current_level = newLevel;
    status.escalated_at = new Date();
    status.escalated_to = level.notify_user_ids || level.notify_roles;
    status.next_escalation_at = level.time_limit_minutes
      ? new Date(Date.now() + level.time_limit_minutes * 60 * 1000)
      : undefined;

    status.escalation_history.push({
      level: newLevel,
      to_users: level.notify_user_ids || level.notify_roles,
      reason,
      timestamp: new Date(),
    });

    this.stats.escalation_stats.total_escalations++;
    this.stats.escalation_stats.auto_escalations++;

    this.emitEvent('escalation_triggered', this.config.tenant_id, {
      ticket_id: status.ticket_id,
      level: newLevel,
      reason,
    });
  }

  private generateSLAAlert(status: SLATicketStatus): ProactiveAlert | undefined {
    const alertType = status.status === 'critical' ? 'sla_breach_imminent' : 'sla_breach_prediction';
    
    const alert = this.createAlert({
      type: alertType,
      severity: status.status === 'critical' ? 'critical' : 'warning',
      urgency: status.status === 'critical' ? 'immediate' : 'urgent',
      target_type: 'ticket',
      target_id: status.ticket_id,
      title: status.status === 'critical' 
        ? `SLA Breach Imminent - Ticket ${status.ticket_id}`
        : `SLA Warning - Ticket ${status.ticket_id}`,
      message: `SLA ${status.sla_type} deadline approaching. ${Math.round(status.pct_remaining)}% time remaining.`,
      trigger_metrics: [
        { name: 'time_remaining', value: status.time_remaining_ms / 1000 / 60, unit: 'minutes' },
        { name: 'pct_remaining', value: status.pct_remaining, unit: '%' },
      ],
      threshold_values: {
        time_remaining: { 
          current: status.time_remaining_ms / 1000 / 60, 
          threshold: this.config.sla_monitoring.warning_threshold_pct 
        },
      },
      recommended_actions: [
        {
          id: 'view_ticket',
          priority: 1,
          type: 'navigation',
          label: 'View Ticket',
          description: 'Open ticket details',
          endpoint: `/dashboard/tickets/${status.ticket_id}`,
          auto_executable: false,
          estimated_impact: 'high',
        },
        {
          id: 'reassign',
          priority: 2,
          type: 'command',
          label: 'Reassign Ticket',
          description: 'Assign to available agent',
          command: `reassign ticket ${status.ticket_id}`,
          auto_executable: false,
          estimated_impact: 'high',
        },
      ],
      prediction_confidence: status.predicted_breach ? 0.7 : undefined,
      predicted_time: status.predicted_breach_time,
      time_remaining_ms: status.time_remaining_ms,
    });

    return alert;
  }

  private generateSentimentAlert(
    customerId: string,
    ticketId: string,
    previousSentiment: SentimentStatus['current_sentiment'] | undefined,
    currentSentiment: SentimentStatus['current_sentiment']
  ): ProactiveAlert | undefined {
    const changeType = currentSentiment.score < this.config.sentiment_monitoring.negative_threshold
      ? 'critical_level'
      : 'gradual_decline';

    const alert = this.createAlert({
      type: 'sentiment_declining',
      severity: changeType === 'critical_level' ? 'critical' : 'warning',
      urgency: changeType === 'critical_level' ? 'urgent' : 'high',
      target_type: 'customer',
      target_id: customerId,
      title: `Customer Sentiment Alert - ${customerId}`,
      message: `Customer sentiment has ${changeType.replace('_', ' ')}. Current score: ${currentSentiment.score.toFixed(2)}`,
      trigger_metrics: [
        { name: 'sentiment_score', value: currentSentiment.score, unit: 'score', trend: 'decreasing' },
        { name: 'sentiment_confidence', value: currentSentiment.confidence, unit: 'pct' },
      ],
      threshold_values: {
        sentiment_score: { 
          current: currentSentiment.score, 
          threshold: this.config.sentiment_monitoring.negative_threshold 
        },
      },
      recommended_actions: [
        {
          id: 'view_customer',
          priority: 1,
          type: 'navigation',
          label: 'View Customer',
          description: 'Open customer profile',
          endpoint: `/dashboard/customers/${customerId}`,
          auto_executable: false,
          estimated_impact: 'high',
        },
        {
          id: 'create_followup',
          priority: 2,
          type: 'command',
          label: 'Create Follow-up',
          description: 'Schedule follow-up with customer',
          command: `create followup for customer ${customerId}`,
          auto_executable: false,
          estimated_impact: 'medium',
        },
      ],
    });

    this.stats.sentiment_stats.alerts_triggered++;

    return alert;
  }

  private createAlert(params: {
    type: ProactiveAlertType;
    severity: AlertSeverity;
    urgency: AlertUrgency;
    target_type: ProactiveAlert['target_type'];
    target_id: string;
    title: string;
    message: string;
    trigger_metrics: ProactiveAlert['trigger_metrics'];
    threshold_values: ProactiveAlert['threshold_values'];
    recommended_actions: RecommendedAction[];
    prediction_confidence?: number;
    predicted_time?: Date;
    time_remaining_ms?: number;
  }): ProactiveAlert | undefined {
    const alert: ProactiveAlert = {
      id: this.generateId(),
      tenant_id: this.config.tenant_id,
      type: params.type,
      severity: params.severity,
      urgency: params.urgency,
      state: 'pending',
      target_type: params.target_type,
      target_id: params.target_id,
      title: params.title,
      message: params.message,
      prediction_confidence: params.prediction_confidence,
      predicted_time: params.predicted_time,
      time_remaining_ms: params.time_remaining_ms,
      trigger_metrics: params.trigger_metrics,
      threshold_values: params.threshold_values,
      recommended_actions: params.recommended_actions,
      created_at: new Date(),
      updated_at: new Date(),
      escalation_level: 0,
      metadata: {},
    };

    this.store.add(alert);
    this.stats.total_alerts_generated++;
    this.stats.alerts_by_type[params.type] = (this.stats.alerts_by_type[params.type] || 0) + 1;
    this.stats.alerts_by_severity[params.severity] = (this.stats.alerts_by_severity[params.severity] || 0) + 1;

    this.emitEvent('proactive_alert_created', this.config.tenant_id, { alert_id: alert.id });

    return alert;
  }

  private generateId(): string {
    return `pa_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  private emitEvent(type: ProactiveAlertEventType, tenantId: string, payload: Record<string, unknown>): void {
    this.eventEmitter.emit({
      type,
      tenant_id: tenantId,
      timestamp: new Date(),
      payload,
    });
  }
}

// ── Factory Functions ─────────────────────────────────────────────────

export function createProactiveAlertManager(config: ProactiveAlertsConfig): ProactiveAlertManager {
  return new ProactiveAlertManager(config);
}

// ── Singleton Registry ────────────────────────────────────────────────

const managers = new Map<string, ProactiveAlertManager>();

export function getProactiveAlertManager(config: ProactiveAlertsConfig): ProactiveAlertManager {
  const key = config.tenant_id;
  
  if (!managers.has(key)) {
    managers.set(key, createProactiveAlertManager(config));
  }
  
  return managers.get(key)!;
}

export function shutdownProactiveAlertManager(tenantId: string): void {
  const manager = managers.get(tenantId);
  if (manager) {
    manager.shutdown();
    managers.delete(tenantId);
  }
}

export function shutdownAllProactiveAlertManagers(): void {
  for (const manager of managers.values()) {
    manager.shutdown();
  }
  managers.clear();
}
