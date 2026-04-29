/**
 * JARVIS Context Manager (Week 3 - Phase 1)
 *
 * Manages conversation context for command processing.
 * Handles session state, conversation history, and context tracking.
 */

import type {
  CommandContext,
  ConversationTurn,
  UserPreferences,
  IntentAction,
  EntityResult,
} from '@/types/command';

// ── Context Manager Configuration ─────────────────────────────────────

interface ContextManagerConfig {
  max_history_turns: number;
  context_expiry_minutes: number;
  default_preferences: UserPreferences;
}

const DEFAULT_CONFIG: ContextManagerConfig = {
  max_history_turns: 50,
  context_expiry_minutes: 60,
  default_preferences: {
    confirmation_required: true,
    notification_preferences: {
      email: true,
      push: true,
      sms: false,
    },
    display_format: 'detailed',
  },
};

// ── Context Manager Class ─────────────────────────────────────────────

export class ContextManager {
  private config: ContextManagerConfig;
  private contexts: Map<string, CommandContext> = new Map();
  private cleanupInterval: NodeJS.Timeout | null = null;

  constructor(config?: Partial<ContextManagerConfig>) {
    this.config = { ...DEFAULT_CONFIG, ...config };
    this.startCleanupInterval();
  }

  /**
   * Create or get context for a session
   */
  getContext(sessionId: string, initialData?: Partial<CommandContext>): CommandContext {
    let context = this.contexts.get(sessionId);

    if (!context || this.isExpired(context)) {
      context = this.createContext(sessionId, initialData);
      this.contexts.set(sessionId, context);
    } else {
      context.updated_at = new Date();
    }

    return context;
  }

  /**
   * Update context
   */
  updateContext(sessionId: string, updates: Partial<CommandContext>): CommandContext | null {
    const context = this.contexts.get(sessionId);
    if (!context) return null;

    const updated = { ...context, ...updates, updated_at: new Date() };
    this.contexts.set(sessionId, updated);
    return updated;
  }

  /**
   * Add conversation turn
   */
  addTurn(
    sessionId: string,
    turn: Omit<ConversationTurn, 'id' | 'timestamp'>
  ): ConversationTurn {
    const context = this.contexts.get(sessionId);
    if (!context) {
      throw new Error(`Context not found for session: ${sessionId}`);
    }

    const newTurn: ConversationTurn = {
      id: this.generateTurnId(),
      ...turn,
      timestamp: new Date(),
    };

    context.conversation_history.push(newTurn);
    context.updated_at = new Date();

    // Trim history if needed
    while (context.conversation_history.length > this.config.max_history_turns) {
      context.conversation_history.shift();
    }

    this.contexts.set(sessionId, context);
    return newTurn;
  }

  /**
   * Get recent conversation turns
   */
  getRecentTurns(sessionId: string, limit: number = 10): ConversationTurn[] {
    const context = this.contexts.get(sessionId);
    if (!context) return [];

    return context.conversation_history.slice(-limit);
  }

  /**
   * Get last user turn
   */
  getLastUserTurn(sessionId: string): ConversationTurn | undefined {
    const context = this.contexts.get(sessionId);
    if (!context) return undefined;

    for (let i = context.conversation_history.length - 1; i >= 0; i--) {
      if (context.conversation_history[i].role === 'user') {
        return context.conversation_history[i];
      }
    }
    return undefined;
  }

  /**
   * Set current ticket context
   */
  setCurrentTicket(sessionId: string, ticketId: string | undefined): void {
    this.updateContext(sessionId, { current_ticket: ticketId });
  }

  /**
   * Set current customer context
   */
  setCurrentCustomer(sessionId: string, customerId: string | undefined): void {
    this.updateContext(sessionId, { current_customer: customerId });
  }

  /**
   * Set current agent context
   */
  setCurrentAgent(sessionId: string, agentId: string | undefined): void {
    this.updateContext(sessionId, { current_agent: agentId });
  }

  /**
   * Set active filters
   */
  setActiveFilters(sessionId: string, filters: Record<string, unknown>): void {
    this.updateContext(sessionId, { active_filters: filters });
  }

  /**
   * Update active filters (merge)
   */
  updateActiveFilters(sessionId: string, filters: Record<string, unknown>): void {
    const context = this.contexts.get(sessionId);
    if (!context) return;

    this.updateContext(sessionId, {
      active_filters: { ...context.active_filters, ...filters },
    });
  }

  /**
   * Clear active filters
   */
  clearActiveFilters(sessionId: string): void {
    this.updateContext(sessionId, { active_filters: {} });
  }

  /**
   * Set page context
   */
  setPageContext(sessionId: string, pageContext: string | undefined): void {
    this.updateContext(sessionId, { page_context: pageContext });
  }

  /**
   * Update user preferences
   */
  updatePreferences(sessionId: string, preferences: Partial<UserPreferences>): void {
    const context = this.contexts.get(sessionId);
    if (!context) return;

    this.updateContext(sessionId, {
      preferences: { ...context.preferences, ...preferences },
    });
  }

  /**
   * Check if context has required info for intent
   */
  hasRequiredContext(
    sessionId: string,
    requiredFields: string[]
  ): { hasAll: boolean; missing: string[] } {
    const context = this.contexts.get(sessionId);
    const missing: string[] = [];

    if (!context) {
      return { hasAll: false, missing: requiredFields };
    }

    for (const field of requiredFields) {
      const value = (context as unknown as Record<string, unknown>)[field];
      if (value === undefined || value === null || value === '') {
        missing.push(field);
      }
    }

    return { hasAll: missing.length === 0, missing };
  }

  /**
   * Get context summary for AI
   */
  getContextSummary(sessionId: string): string {
    const context = this.contexts.get(sessionId);
    if (!context) return 'No active context.';

    const parts: string[] = [];

    if (context.current_ticket) {
      parts.push(`Current ticket: ${context.current_ticket}`);
    }

    if (context.current_customer) {
      parts.push(`Current customer: ${context.current_customer}`);
    }

    if (context.current_agent) {
      parts.push(`Current agent: ${context.current_agent}`);
    }

    if (context.page_context) {
      parts.push(`Page context: ${context.page_context}`);
    }

    if (Object.keys(context.active_filters).length > 0) {
      parts.push(`Active filters: ${JSON.stringify(context.active_filters)}`);
    }

    const recentTurns = context.conversation_history.slice(-3);
    if (recentTurns.length > 0) {
      parts.push(
        'Recent conversation:',
        ...recentTurns.map((t) => `  ${t.role}: ${t.content.slice(0, 100)}...`)
      );
    }

    return parts.join('\n') || 'No active context.';
  }

  /**
   * Clear context for session
   */
  clearContext(sessionId: string): void {
    this.contexts.delete(sessionId);
  }

  /**
   * Get all active sessions
   */
  getActiveSessions(): string[] {
    return Array.from(this.contexts.keys());
  }

  /**
   * Get context count
   */
  getContextCount(): number {
    return this.contexts.size;
  }

  /**
   * Shutdown context manager
   */
  shutdown(): void {
    if (this.cleanupInterval) {
      clearInterval(this.cleanupInterval);
      this.cleanupInterval = null;
    }
    this.contexts.clear();
  }

  // ── Private Methods ────────────────────────────────────────────────

  /**
   * Create new context
   */
  private createContext(
    sessionId: string,
    initialData?: Partial<CommandContext>
  ): CommandContext {
    const now = new Date();

    return {
      session_id: sessionId,
      tenant_id: initialData?.tenant_id || 'default',
      variant: initialData?.variant || 'parwa',
      user_id: initialData?.user_id || '',
      user_role: initialData?.user_role || 'agent',
      conversation_history: initialData?.conversation_history || [],
      current_ticket: initialData?.current_ticket,
      current_customer: initialData?.current_customer,
      current_agent: initialData?.current_agent,
      active_filters: initialData?.active_filters || {},
      page_context: initialData?.page_context,
      timezone: initialData?.timezone || 'UTC',
      locale: initialData?.locale || 'en',
      preferences: {
        ...this.config.default_preferences,
        ...initialData?.preferences,
      },
      permissions: initialData?.permissions || [],
      created_at: now,
      updated_at: now,
    };
  }

  /**
   * Check if context is expired
   */
  private isExpired(context: CommandContext): boolean {
    const expiryMs = this.config.context_expiry_minutes * 60 * 1000;
    return Date.now() - context.updated_at.getTime() > expiryMs;
  }

  /**
   * Start cleanup interval
   */
  private startCleanupInterval(): void {
    this.cleanupInterval = setInterval(() => {
      this.cleanupExpired();
    }, 5 * 60 * 1000); // Every 5 minutes
  }

  /**
   * Cleanup expired contexts
   */
  private cleanupExpired(): void {
    for (const [sessionId, context] of this.contexts) {
      if (this.isExpired(context)) {
        this.contexts.delete(sessionId);
      }
    }
  }

  /**
   * Generate turn ID
   */
  private generateTurnId(): string {
    return `turn_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }
}

// ── Singleton instance ───────────────────────────────────────────────

let contextManagerInstance: ContextManager | null = null;

export function getContextManager(config?: Partial<ContextManagerConfig>): ContextManager {
  if (!contextManagerInstance) {
    contextManagerInstance = new ContextManager(config);
  }
  return contextManagerInstance;
}

// ── Factory Function ─────────────────────────────────────────────────

export function createContextManager(config?: Partial<ContextManagerConfig>): ContextManager {
  return new ContextManager(config);
}
