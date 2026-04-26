/**
 * JARVIS Ticket Event Listeners (Week 2 - Phase 1)
 *
 * Monitors ticket lifecycle events and emits awareness events.
 * Handles: create, update, assign, close, escalate, reopen, priority change, SLA
 */

import type {
  AwarenessEvent,
  AwarenessEventType,
  TicketEventListenerConfig,
  AlertSeverity,
  VARIANT_AWARENESS_CAPABILITIES,
} from '@/types/awareness';

// ── Event Emitter Interface ──────────────────────────────────────────

export interface EventEmitter {
  emit(event: AwarenessEvent): Promise<void>;
}

// ── Ticket Event Data Types ──────────────────────────────────────────

export interface TicketEventData {
  ticket_id: string;
  tenant_id: string;
  customer_id?: string;
  agent_id?: string;
  previous_status?: string;
  new_status?: string;
  previous_priority?: string;
  new_priority?: string;
  previous_agent_id?: string;
  new_agent_id?: string;
  sla_due_at?: Date;
  sla_remaining_pct?: number;
  channel?: string;
  created_at?: Date;
  tags?: string[];
  category?: string;
  metadata?: Record<string, unknown>;
}

// ── Ticket Event Listener Class ──────────────────────────────────────

export class TicketEventListener {
  private config: TicketEventListenerConfig;
  private eventEmitter: EventEmitter;
  private slaTimers: Map<string, NodeJS.Timeout> = new Map();
  private slaWarnings: Map<string, boolean> = new Map();

  constructor(config: TicketEventListenerConfig, emitter: EventEmitter) {
    this.config = config;
    this.eventEmitter = emitter;
  }

  /**
   * Handle ticket created event
   */
  async onTicketCreated(data: TicketEventData): Promise<void> {
    if (!this.isEnabled('ticket_created')) return;

    const event = this.createEvent('ticket_created', data);
    await this.eventEmitter.emit(event);

    // Set up SLA monitoring if applicable
    if (data.sla_due_at) {
      this.setupSLAMonitoring(data);
    }

    // Check for high volume spike
    await this.checkVolumeSpike(data.tenant_id);
  }

  /**
   * Handle ticket updated event
   */
  async onTicketUpdated(data: TicketEventData): Promise<void> {
    if (!this.isEnabled('ticket_updated')) return;

    const event = this.createEvent('ticket_updated', data);
    await this.eventEmitter.emit(event);
  }

  /**
   * Handle ticket assigned event
   */
  async onTicketAssigned(data: TicketEventData): Promise<void> {
    if (!this.isEnabled('ticket_assigned')) return;

    const event = this.createEvent('ticket_assigned', {
      ...data,
      metadata: {
        ...data.metadata,
        previous_agent_id: data.previous_agent_id,
        new_agent_id: data.new_agent_id,
      },
    });
    await this.eventEmitter.emit(event);
  }

  /**
   * Handle ticket closed event
   */
  async onTicketClosed(data: TicketEventData): Promise<void> {
    if (!this.isEnabled('ticket_closed')) return;

    // Clear SLA monitoring
    this.clearSLAMonitoring(data.ticket_id);

    const event = this.createEvent('ticket_closed', data);
    await this.eventEmitter.emit(event);
  }

  /**
   * Handle ticket escalated event
   */
  async onTicketEscalated(data: TicketEventData): Promise<void> {
    if (!this.isEnabled('ticket_escalated')) return;

    const event = this.createEvent('ticket_escalated', {
      ...data,
      metadata: {
        ...data.metadata,
        escalation_reason: data.metadata?.escalation_reason,
        escalated_from: data.previous_agent_id,
        escalated_to: data.new_agent_id,
      },
    });
    await this.eventEmitter.emit(event);
  }

  /**
   * Handle ticket reopened event
   */
  async onTicketReopened(data: TicketEventData): Promise<void> {
    if (!this.isEnabled('ticket_reopened')) return;

    const event = this.createEvent('ticket_reopened', data);
    await this.eventEmitter.emit(event);

    // Re-setup SLA monitoring if applicable
    if (data.sla_due_at) {
      this.setupSLAMonitoring(data);
    }
  }

  /**
   * Handle ticket priority changed event
   */
  async onTicketPriorityChanged(data: TicketEventData): Promise<void> {
    if (!this.isEnabled('ticket_priority_changed')) return;

    const event = this.createEvent('ticket_priority_changed', {
      ...data,
      metadata: {
        ...data.metadata,
        previous_priority: data.previous_priority,
        new_priority: data.new_priority,
      },
    });
    await this.eventEmitter.emit(event);
  }

  /**
   * Setup SLA monitoring for a ticket
   */
  private setupSLAMonitoring(data: TicketEventData): void {
    const { ticket_id, sla_due_at, sla_remaining_pct = 100 } = data;
    if (!sla_due_at) return;

    // Clear existing timer if any
    this.clearSLAMonitoring(ticket_id);

    const now = new Date();
    const dueTime = new Date(sla_due_at);
    const totalMs = dueTime.getTime() - now.getTime();

    if (totalMs <= 0) {
      // Already breached
      this.emitSLABreach(data);
      return;
    }

    // Calculate warning time
    const warningThreshold = this.config.sla_warning_threshold_pct / 100;
    const breachThreshold = this.config.sla_breach_threshold_pct / 100;

    const warningMs = totalMs * (1 - warningThreshold);
    const breachMs = totalMs * (1 - breachThreshold);

    // Set warning timer
    if (warningMs > 0) {
      const warningTimer = setTimeout(() => {
        this.emitSLAWarning(data);
      }, warningMs);
      this.slaTimers.set(`${ticket_id}_warning`, warningTimer);
    }

    // Set breach timer
    if (breachMs > 0) {
      const breachTimer = setTimeout(() => {
        this.emitSLABreach(data);
      }, breachMs);
      this.slaTimers.set(`${ticket_id}_breach`, breachTimer);
    }
  }

  /**
   * Clear SLA monitoring for a ticket
   */
  private clearSLAMonitoring(ticketId: string): void {
    const warningKey = `${ticketId}_warning`;
    const breachKey = `${ticketId}_breach`;

    if (this.slaTimers.has(warningKey)) {
      clearTimeout(this.slaTimers.get(warningKey)!);
      this.slaTimers.delete(warningKey);
    }

    if (this.slaTimers.has(breachKey)) {
      clearTimeout(this.slaTimers.get(breachKey)!);
      this.slaTimers.delete(breachKey);
    }

    this.slaWarnings.delete(ticketId);
  }

  /**
   * Emit SLA warning event
   */
  private async emitSLAWarning(data: TicketEventData): Promise<void> {
    if (!this.isEnabled('ticket_sla_warning')) return;

    this.slaWarnings.set(data.ticket_id, true);

    const event = this.createEvent('ticket_sla_warning', {
      ...data,
      metadata: {
        ...data.metadata,
        sla_remaining_pct: this.config.sla_warning_threshold_pct,
      },
    });
    await this.eventEmitter.emit(event);
  }

  /**
   * Emit SLA breach event
   */
  private async emitSLABreach(data: TicketEventData): Promise<void> {
    if (!this.isEnabled('ticket_sla_breach')) return;

    const event = this.createEvent('ticket_sla_breach', {
      ...data,
      metadata: {
        ...data.metadata,
        sla_remaining_pct: 0,
        breached_at: new Date().toISOString(),
      },
    });
    await this.eventEmitter.emit(event);
  }

  /**
   * Check for high volume spike
   */
  private async checkVolumeSpike(tenantId: string): Promise<void> {
    // This would integrate with the metrics collector
    // For now, we'll emit an event if threshold is exceeded
    // The actual volume check would be done by querying recent metrics
  }

  /**
   * Check if an event type is enabled for this listener
   */
  private isEnabled(eventType: AwarenessEventType): boolean {
    return this.config.enabled_events.includes(eventType);
  }

  /**
   * Create an awareness event
   */
  private createEvent(
    type: AwarenessEventType,
    data: TicketEventData
  ): AwarenessEvent {
    return {
      id: this.generateEventId(),
      type,
      timestamp: new Date(),
      tenant_id: data.tenant_id,
      variant: this.config.variant,
      source: 'ticket_listener',
      payload: {
        ticket_id: data.ticket_id,
        customer_id: data.customer_id,
        agent_id: data.agent_id,
        status: data.new_status,
        priority: data.new_priority,
        channel: data.channel,
        category: data.category,
        tags: data.tags,
        ...data.metadata,
      },
      metadata: {
        correlation_id: data.metadata?.correlation_id as string | undefined,
      },
    };
  }

  /**
   * Generate unique event ID
   */
  private generateEventId(): string {
    return `evt_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * Update listener configuration
   */
  updateConfig(config: Partial<TicketEventListenerConfig>): void {
    this.config = { ...this.config, ...config };
  }

  /**
   * Shutdown listener and clear all timers
   */
  shutdown(): void {
    for (const timer of this.slaTimers.values()) {
      clearTimeout(timer);
    }
    this.slaTimers.clear();
    this.slaWarnings.clear();
  }
}

// ── Factory Function ─────────────────────────────────────────────────

export function createTicketListener(
  config: TicketEventListenerConfig,
  emitter: EventEmitter
): TicketEventListener {
  return new TicketEventListener(config, emitter);
}

// ── Default Configuration by Variant ─────────────────────────────────

export const DEFAULT_TICKET_LISTENER_CONFIG: Record<
  string,
  Omit<TicketEventListenerConfig, 'tenant_id'>
> = {
  mini_parwa: {
    variant: 'mini_parwa',
    enabled_events: [
      'ticket_created',
      'ticket_closed',
      'ticket_sla_breach',
    ],
    sla_warning_threshold_pct: 20,
    sla_breach_threshold_pct: 0,
    high_volume_threshold: 200,
    queue_buildup_threshold: 50,
  },
  parwa: {
    variant: 'parwa',
    enabled_events: [
      'ticket_created',
      'ticket_updated',
      'ticket_assigned',
      'ticket_closed',
      'ticket_escalated',
      'ticket_reopened',
      'ticket_priority_changed',
      'ticket_sla_warning',
      'ticket_sla_breach',
    ],
    sla_warning_threshold_pct: 25,
    sla_breach_threshold_pct: 0,
    high_volume_threshold: 300,
    queue_buildup_threshold: 40,
  },
  parwa_high: {
    variant: 'parwa_high',
    enabled_events: [
      'ticket_created',
      'ticket_updated',
      'ticket_assigned',
      'ticket_closed',
      'ticket_escalated',
      'ticket_reopened',
      'ticket_priority_changed',
      'ticket_sla_warning',
      'ticket_sla_breach',
    ],
    sla_warning_threshold_pct: 30,
    sla_breach_threshold_pct: 0,
    high_volume_threshold: 500,
    queue_buildup_threshold: 30,
  },
};
