/**
 * JARVIS Real-time Event Capture (Week 2 - Phase 1)
 *
 * Captures, buffers, and processes awareness events in real-time.
 * Handles event ingestion, buffering, and delivery to subscribers.
 */

import type {
  AwarenessEvent,
  AwarenessEventType,
  EventCaptureConfig,
  EventBuffer,
  EventSubscription,
} from '@/types/awareness';

// ── Event Callback Types ─────────────────────────────────────────────

export type EventCallback = (event: AwarenessEvent) => Promise<void>;
export type EventFilter = (event: AwarenessEvent) => boolean;

// ── Event Capture Class ──────────────────────────────────────────────

export class EventCapture {
  private config: EventCaptureConfig;
  private buffer: AwarenessEvent[] = [];
  private subscribers: Map<string, EventSubscription> = new Map();
  private callbacks: Map<string, { filter?: EventFilter; callback: EventCallback }> = new Map();
  private flushTimer: NodeJS.Timeout | null = null;
  private isProcessing = false;
  private deadLetterQueue: AwarenessEvent[] = [];

  constructor(config: EventCaptureConfig) {
    this.config = config;
    this.startFlushTimer();
  }

  /**
   * Capture an event
   */
  async capture(event: AwarenessEvent): Promise<void> {
    // Validate event
    if (!this.validateEvent(event)) {
      console.warn(`[EventCapture] Invalid event: ${event.id}`);
      return;
    }

    // Add to buffer
    this.buffer.push(event);

    // Check if buffer is full
    if (this.buffer.length >= this.config.buffer_size) {
      await this.flush();
    }
  }

  /**
   * Capture multiple events
   */
  async captureBatch(events: AwarenessEvent[]): Promise<void> {
    for (const event of events) {
      await this.capture(event);
    }
  }

  /**
   * Subscribe to events
   */
  subscribe(
    id: string,
    callback: EventCallback,
    filter?: EventFilter
  ): () => void {
    this.callbacks.set(id, { callback, filter });

    // Return unsubscribe function
    return () => {
      this.callbacks.delete(id);
    };
  }

  /**
   * Add a webhook subscription
   */
  addSubscription(subscription: EventSubscription): void {
    this.subscribers.set(subscription.id, subscription);
  }

  /**
   * Remove a subscription
   */
  removeSubscription(subscriptionId: string): boolean {
    return this.subscribers.delete(subscriptionId);
  }

  /**
   * Flush the buffer and process events
   */
  async flush(): Promise<void> {
    if (this.isProcessing || this.buffer.length === 0) return;

    this.isProcessing = true;

    try {
      const events = [...this.buffer];
      this.buffer = [];

      // Process each event
      for (const event of events) {
        await this.processEvent(event);
      }
    } catch (error) {
      console.error('[EventCapture] Flush error:', error);
    } finally {
      this.isProcessing = false;
    }
  }

  /**
   * Get current buffer state
   */
  getBufferState(): EventBuffer {
    return {
      events: [...this.buffer],
      size: this.buffer.length,
      oldest_timestamp: this.buffer[0]?.timestamp,
      newest_timestamp: this.buffer[this.buffer.length - 1]?.timestamp,
    };
  }

  /**
   * Get dead letter queue
   */
  getDeadLetterQueue(): AwarenessEvent[] {
    return [...this.deadLetterQueue];
  }

  /**
   * Clear dead letter queue
   */
  clearDeadLetterQueue(): void {
    this.deadLetterQueue = [];
  }

  /**
   * Get statistics
   */
  getStats(): {
    bufferSize: number;
    subscriberCount: number;
    callbackCount: number;
    deadLetterCount: number;
  } {
    return {
      bufferSize: this.buffer.length,
      subscriberCount: this.subscribers.size,
      callbackCount: this.callbacks.size,
      deadLetterCount: this.deadLetterQueue.length,
    };
  }

  /**
   * Shutdown the event capture
   */
  async shutdown(): Promise<void> {
    if (this.flushTimer) {
      clearInterval(this.flushTimer);
      this.flushTimer = null;
    }

    // Final flush
    await this.flush();
  }

  // ── Private Methods ────────────────────────────────────────────────

  /**
   * Validate an event
   */
  private validateEvent(event: AwarenessEvent): boolean {
    if (!event.id || !event.type || !event.tenant_id) {
      return false;
    }

    if (!this.config.enabled_sources.includes(event.source)) {
      return false;
    }

    return true;
  }

  /**
   * Process a single event
   */
  private async processEvent(event: AwarenessEvent): Promise<void> {
    let success = false;
    let attempts = 0;

    while (!success && attempts < this.config.retry_attempts) {
      attempts++;

      try {
        // Notify callbacks
        await this.notifyCallbacks(event);

        // Notify webhook subscribers
        await this.notifySubscribers(event);

        success = true;
      } catch (error) {
        console.error(
          `[EventCapture] Processing attempt ${attempts} failed:`,
          error
        );

        if (attempts < this.config.retry_attempts) {
          // Exponential backoff
          await this.delay(Math.pow(2, attempts) * 100);
        }
      }
    }

    if (!success && this.config.dead_letter_enabled) {
      this.deadLetterQueue.push(event);
    }
  }

  /**
   * Notify registered callbacks
   */
  private async notifyCallbacks(event: AwarenessEvent): Promise<void> {
    const promises: Promise<void>[] = [];

    for (const [id, { callback, filter }] of this.callbacks) {
      // Apply filter if present
      if (filter && !filter(event)) {
        continue;
      }

      // Wrap callback result in Promise.resolve to handle sync callbacks
      promises.push(
        Promise.resolve(callback(event)).catch((error) => {
          console.error(`[EventCapture] Callback ${id} error:`, error);
        })
      );
    }

    await Promise.allSettled(promises);
  }

  /**
   * Notify webhook subscribers
   */
  private async notifySubscribers(event: AwarenessEvent): Promise<void> {
    const promises: Promise<void>[] = [];

    for (const [id, subscription] of this.subscribers) {
      if (!subscription.enabled) continue;

      // Check if subscription wants this event type
      if (
        subscription.event_types.length > 0 &&
        !subscription.event_types.includes(event.type)
      ) {
        continue;
      }

      promises.push(this.sendWebhook(subscription, event));
    }

    await Promise.allSettled(promises);
  }

  /**
   * Send webhook to subscriber
   */
  private async sendWebhook(
    subscription: EventSubscription,
    event: AwarenessEvent
  ): Promise<void> {
    try {
      const response = await fetch(subscription.callback_url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(subscription.secret && { 'X-Signature': this.generateSignature(event, subscription.secret) }),
        },
        body: JSON.stringify(event),
      });

      if (!response.ok) {
        throw new Error(`Webhook failed: ${response.status}`);
      }
    } catch (error) {
      console.error(`[EventCapture] Webhook ${subscription.id} failed:`, error);
      throw error;
    }
  }

  /**
   * Generate signature for webhook
   */
  private generateSignature(event: AwarenessEvent, secret: string): string {
    // Simple HMAC-like signature (in production, use proper crypto)
    const payload = JSON.stringify(event);
    return Buffer.from(`${payload}:${secret}`).toString('base64').slice(0, 32);
  }

  /**
   * Start the flush timer
   */
  private startFlushTimer(): void {
    this.flushTimer = setInterval(() => {
      this.flush().catch((error) => {
        console.error('[EventCapture] Flush timer error:', error);
      });
    }, this.config.flush_interval_ms);
  }

  /**
   * Delay helper
   */
  private delay(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
}

// ── Factory Function ─────────────────────────────────────────────────

export function createEventCapture(config: EventCaptureConfig): EventCapture {
  return new EventCapture(config);
}

// ── Default Configuration by Variant ─────────────────────────────────

export const DEFAULT_EVENT_CAPTURE_CONFIG: Record<
  string,
  Omit<EventCaptureConfig, 'tenant_id'>
> = {
  mini_parwa: {
    enabled_sources: ['ticket_listener', 'health_monitor'],
    buffer_size: 50,
    flush_interval_ms: 5000,
    retry_attempts: 2,
    dead_letter_enabled: false,
  },
  parwa: {
    enabled_sources: ['ticket_listener', 'activity_tracker', 'health_monitor', 'alert_dispatcher'],
    buffer_size: 200,
    flush_interval_ms: 2000,
    retry_attempts: 3,
    dead_letter_enabled: true,
  },
  parwa_high: {
    enabled_sources: ['*'],
    buffer_size: 500,
    flush_interval_ms: 1000,
    retry_attempts: 5,
    dead_letter_enabled: true,
  },
};
