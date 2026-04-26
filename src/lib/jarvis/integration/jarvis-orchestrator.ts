/**
 * JARVIS Orchestrator - Week 4 (Phase 1)
 *
 * Main orchestrator that integrates Awareness Engine and Command Processing.
 * Provides a unified API for JARVIS operations.
 */

import type { Variant } from '@/types/variant';
import type { AwarenessState, Alert, SystemHealth } from '@/types/awareness';
import type { CommandResult, Draft, CommandContext } from '@/types/command';
import {
  AwarenessEngine,
  getAwarenessEngine,
  createAwarenessEngine,
} from '../awareness';
import {
  CommandProcessor,
  getCommandProcessor,
  createCommandProcessor,
} from '../command';
import {
  CacheManager,
  createCacheManager,
  CacheKeys,
} from './cache-manager';
import {
  RateLimiter,
  createRateLimiter,
} from './rate-limiter';
import {
  AuditLogger,
  createAuditLogger,
} from './audit-logger';
import type {
  JarvisConfig,
  JarvisState,
  ProcessJarvisCommandRequest,
  ProcessJarvisCommandResponse,
  IntegrationEvent,
  IntegrationEventType,
  IntegrationHealth,
  ComponentHealthStatus,
  SuggestedAction,
  DraftPreview,
  SecurityViolation,
  JarvisVariantCapabilities,
  JARVIS_VARIANT_CAPABILITIES,
  DEFAULT_CACHE_CONFIG,
  DEFAULT_RATE_LIMIT_CONFIG,
  DEFAULT_SECURITY_CONFIG,
} from './types';

// ── Session Manager ────────────────────────────────────────────────

class SessionManager {
  private sessions: Map<string, JarvisState> = new Map();
  private maxSessions: number;

  constructor(maxSessions: number = 1000) {
    this.maxSessions = maxSessions;
  }

  create(
    sessionId: string,
    organizationId: string,
    variant: Variant,
    awarenessState: AwarenessState,
    commandContext: CommandContext
  ): JarvisState {
    // Enforce max sessions
    if (this.sessions.size >= this.maxSessions) {
      this.evictOldest();
    }

    const state: JarvisState = {
      sessionId,
      organizationId,
      variant,
      awareness: awarenessState,
      commandContext,
      activeDrafts: new Map(),
      pendingAlerts: [],
      metrics: {
        commandsProcessed: 0,
        directExecutions: 0,
        approvalRequired: 0,
        commandsApproved: 0,
        commandsRejected: 0,
        avgResponseTime: 0,
        cacheHitRate: 0,
        errors: 0,
      },
      createdAt: new Date(),
      lastActivityAt: new Date(),
    };

    this.sessions.set(sessionId, state);
    return state;
  }

  get(sessionId: string): JarvisState | undefined {
    return this.sessions.get(sessionId);
  }

  update(sessionId: string, updates: Partial<JarvisState>): JarvisState | undefined {
    const state = this.sessions.get(sessionId);
    if (state) {
      Object.assign(state, updates);
      state.lastActivityAt = new Date();
    }
    return state;
  }

  delete(sessionId: string): boolean {
    return this.sessions.delete(sessionId);
  }

  has(sessionId: string): boolean {
    return this.sessions.has(sessionId);
  }

  getActiveCount(): number {
    return this.sessions.size;
  }

  getByOrganization(orgId: string): JarvisState[] {
    return Array.from(this.sessions.values()).filter(s => s.organizationId === orgId);
  }

  private evictOldest(): void {
    let oldest: string | null = null;
    let oldestTime = Infinity;

    for (const [id, state] of this.sessions) {
      if (state.lastActivityAt.getTime() < oldestTime) {
        oldestTime = state.lastActivityAt.getTime();
        oldest = id;
      }
    }

    if (oldest) {
      this.sessions.delete(oldest);
    }
  }

  clear(): void {
    this.sessions.clear();
  }
}

// ── Event Emitter ──────────────────────────────────────────────────

type EventCallback = (event: IntegrationEvent) => void;

class IntegrationEventEmitter {
  private listeners: Map<IntegrationEventType, Set<EventCallback>> = new Map();

  on(event: IntegrationEventType, callback: EventCallback): () => void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event)!.add(callback);

    // Return unsubscribe function
    return () => {
      this.listeners.get(event)?.delete(callback);
    };
  }

  emit(event: IntegrationEvent): void {
    const callbacks = this.listeners.get(event.type);
    if (callbacks) {
      for (const callback of callbacks) {
        try {
          callback(event);
        } catch (error) {
          console.error('Event callback error:', error);
        }
      }
    }
  }

  clear(): void {
    this.listeners.clear();
  }
}

// ── JARVIS Orchestrator ────────────────────────────────────────────

export class JarvisOrchestrator {
  private config: JarvisConfig;
  private awarenessEngine: AwarenessEngine | null = null;
  private commandProcessor: CommandProcessor | null = null;
  private cacheManager: CacheManager;
  private rateLimiter: RateLimiter;
  private auditLogger: AuditLogger;
  private sessionManager: SessionManager;
  private eventEmitter: IntegrationEventEmitter;
  private startTime: Date;
  private isInitialized: boolean = false;

  constructor(config: JarvisConfig) {
    this.config = config;
    this.startTime = new Date();

    // Initialize support components
    this.cacheManager = createCacheManager(config.cache ?? {
      enabled: true,
      defaultTtl: 300,
      maxSize: 1000,
    });

    this.rateLimiter = createRateLimiter(config.rateLimit ?? {
      enabled: true,
      requestsPerMinute: 60,
      commandsPerHour: 100,
      burstAllowance: 10,
    });

    this.auditLogger = createAuditLogger({
      enabled: config.security?.auditLogging ?? true,
      maxEntries: 10000,
      retentionDays: 90,
    });

    this.sessionManager = new SessionManager(
      this.getCapabilities().maxConcurrentSessions
    );

    this.eventEmitter = new IntegrationEventEmitter();
  }

  /**
   * Initialize JARVIS components
   */
  async initialize(): Promise<void> {
    if (this.isInitialized) return;

    // Initialize Awareness Engine
    this.awarenessEngine = await createAwarenessEngine({
      tenant_id: this.config.organizationId,
      variant: this.config.variant,
    });

    // Initialize Command Processor
    this.commandProcessor = createCommandProcessor({
      tenant_id: this.config.organizationId,
      variant: this.config.variant,
    });
    await this.commandProcessor.initialize();

    this.isInitialized = true;

    this.emitEvent({
      type: 'session_created',
      sessionId: 'system',
      organizationId: this.config.organizationId,
      timestamp: new Date(),
      payload: { message: 'JARVIS initialized' },
    });
  }

  /**
   * Process a natural language command
   */
  async processCommand(
    request: ProcessJarvisCommandRequest
  ): Promise<ProcessJarvisCommandResponse> {
    const startTime = Date.now();
    let sessionId = request.sessionId;

    try {
      // Ensure initialization
      if (!this.isInitialized) {
        await this.initialize();
      }

      // Security validation
      const validationResult = this.validateInput(request.command);
      if (!validationResult.valid) {
        return this.createErrorResponse(
          sessionId || 'unknown',
          validationResult.error || 'Invalid input',
          'security_violation'
        );
      }

      // Rate limiting
      const rateLimitResult = this.rateLimiter.checkLimit(
        request.userId,
        this.config.organizationId,
        this.config.variant,
        'command'
      );

      if (!rateLimitResult.allowed) {
        this.auditLogger.recordViolation({
          sessionId: sessionId || 'unknown',
          userId: request.userId,
          type: 'excessive_requests',
          severity: 'medium',
          description: 'Rate limit exceeded',
          input: request.command.slice(0, 100),
          action: 'rate_limit',
        });

        return this.createErrorResponse(
          sessionId || 'unknown',
          `Rate limit exceeded. Retry after ${Math.ceil(rateLimitResult.retryAfterMs / 1000)} seconds.`,
          'rate_limited'
        );
      }

      // Get or create session
      if (!sessionId || !this.sessionManager.has(sessionId)) {
        sessionId = this.generateSessionId();
        await this.createSession(sessionId, request.userId);
      }

      const session = this.sessionManager.get(sessionId)!;

      // Update context with request context
      if (request.context) {
        session.commandContext.page_context = request.context.currentPage || session.commandContext.page_context;
        session.commandContext.current_ticket = request.context.activeTicketId || session.commandContext.current_ticket;
        session.commandContext.current_customer = request.context.activeCustomerId || session.commandContext.current_customer;
        if (request.context.filters) {
          session.commandContext.active_filters = request.context.filters;
        }
      }

      // Check cache for similar commands
      const cacheKey = CacheKeys.commandContext(sessionId);
      const cachedContext = this.cacheManager.get<{ result: CommandResult }>('commands', cacheKey);

      // Process command through Command Processor
      const commandResult = await this.commandProcessor!.process({
        text: request.command,
        session_id: sessionId,
        context: session.commandContext,
      });

      // Update session metrics
      this.updateMetrics(session, Date.now() - startTime);

      // Log command execution
      this.auditLogger.logCommand({
        organizationId: this.config.organizationId,
        sessionId,
        userId: request.userId,
        command: request.command,
        commandId: commandResult.command?.id || sessionId,
        result: commandResult.command?.status === 'completed' ? 'success' : 'failure',
        executionMode: commandResult.approval_required ? 'draft' : 'direct',
      });

      // Create response
      const response: ProcessJarvisCommandResponse = {
        sessionId,
        commandId: commandResult.command?.id || sessionId,
        success: commandResult.command?.status === 'completed',
        message: commandResult.message || 'Command processed',
        resultType: commandResult.approval_required ? 'draft_created' : 'direct_execution',
        suggestions: commandResult.suggestions?.map((s, i) => ({
          type: 'command' as const,
          label: typeof s === 'string' ? s : (s.description || s.intent),
          priority: i + 1,
        })) || [],
        timestamp: new Date(),
      };

      // Add draft details if created
      if (commandResult.draft) {
        response.draft = this.createDraftPreview(commandResult.draft);
        session.activeDrafts.set(commandResult.draft.id, commandResult.draft);
      }

      return response;
    } catch (error) {
      console.error('JARVIS command processing error:', error);
      
      return this.createErrorResponse(
        sessionId || 'unknown',
        error instanceof Error ? error.message : 'Internal error',
        'error'
      );
    }
  }

  /**
   * Approve a draft
   */
  async approveDraft(
    draftId: string,
    sessionId: string,
    userId: string,
    comment?: string
  ): Promise<ProcessJarvisCommandResponse> {
    const session = this.sessionManager.get(sessionId);
    if (!session) {
      return this.createErrorResponse(sessionId, 'Session not found', 'error');
    }

    const draft = session.activeDrafts.get(draftId);
    if (!draft) {
      return this.createErrorResponse(sessionId, 'Draft not found', 'error');
    }

    // Execute approved draft
    const result = await this.commandProcessor!.approveDraft(draftId, userId, comment);

    // Update session
    session.activeDrafts.delete(draftId);
    session.metrics.commandsApproved++;

    // Log approval
    this.auditLogger.logApproval({
      organizationId: this.config.organizationId,
      sessionId,
      userId,
      draftId,
      action: 'approve',
      comment,
    });

    return {
      sessionId,
      commandId: draftId,
      success: result.success,
      message: result.message || 'Draft approved and executed',
      resultType: 'direct_execution',
      timestamp: new Date(),
    };
  }

  /**
   * Reject a draft
   */
  async rejectDraft(
    draftId: string,
    sessionId: string,
    userId: string,
    reason?: string
  ): Promise<ProcessJarvisCommandResponse> {
    const session = this.sessionManager.get(sessionId);
    if (!session) {
      return this.createErrorResponse(sessionId, 'Session not found', 'error');
    }

    const draft = session.activeDrafts.get(draftId);
    if (!draft) {
      return this.createErrorResponse(sessionId, 'Draft not found', 'error');
    }

    // Reject draft
    this.commandProcessor!.rejectDraft(draftId, userId, reason || 'No reason provided');

    // Update session
    session.activeDrafts.delete(draftId);
    session.metrics.commandsRejected++;

    // Log rejection
    this.auditLogger.logApproval({
      organizationId: this.config.organizationId,
      sessionId,
      userId,
      draftId,
      action: 'reject',
      comment: reason,
    });

    return {
      sessionId,
      commandId: draftId,
      success: true,
      message: 'Draft rejected',
      resultType: 'direct_execution',
      timestamp: new Date(),
    };
  }

  /**
   * Get session state
   */
  getSession(sessionId: string): JarvisState | undefined {
    return this.sessionManager.get(sessionId);
  }

  /**
   * End a session
   */
  async endSession(sessionId: string, userId: string): Promise<void> {
    const session = this.sessionManager.get(sessionId);
    if (session) {
      this.auditLogger.logSession({
        organizationId: this.config.organizationId,
        sessionId,
        userId,
        action: 'end',
        metadata: {
          commandsProcessed: session.metrics.commandsProcessed,
          duration: Date.now() - session.createdAt.getTime(),
        },
      });

      this.sessionManager.delete(sessionId);
    }
  }

  /**
   * Get awareness state
   */
  async getAwarenessState(): Promise<AwarenessState | null> {
    if (!this.awarenessEngine) return null;
    return this.awarenessEngine.getState();
  }

  /**
   * Get system health
   */
  async getHealth(): Promise<IntegrationHealth> {
    const now = new Date();
    const awarenessHealth = await this.checkAwarenessHealth();
    const commandHealth = await this.checkCommandHealth();

    const status = this.determineOverallStatus([awarenessHealth, commandHealth]);

    return {
      status,
      timestamp: now,
      components: {
        awarenessEngine: awarenessHealth,
        commandProcessor: commandHealth,
        cache: this.checkCacheHealth(),
        rateLimiter: this.checkRateLimiterHealth(),
        auditLogger: this.checkAuditHealth(),
      },
      activeSessions: this.sessionManager.getActiveCount(),
      memoryUsage: process.memoryUsage().heapUsed / 1024 / 1024,
      uptime: (now.getTime() - this.startTime.getTime()) / 1000,
    };
  }

  /**
   * Get pending alerts
   */
  async getPendingAlerts(): Promise<Alert[]> {
    if (!this.awarenessEngine) return [];
    const state = await this.awarenessEngine.getState();
    return (state as any)?.active_alerts || (state as any)?.alerts || [];
  }

  /**
   * Acknowledge an alert
   */
  async acknowledgeAlert(
    alertId: string,
    userId: string,
    sessionId: string
  ): Promise<boolean> {
    if (!this.awarenessEngine) return false;

    const result = await this.awarenessEngine.acknowledgeAlert(alertId, userId);

    if (result !== null) {
      this.auditLogger.logAlert({
        organizationId: this.config.organizationId,
        sessionId,
        userId,
        alertId,
        action: 'acknowledge',
      });
      return true;
    }

    return false;
  }

  /**
   * Subscribe to integration events
   */
  onEvent(event: IntegrationEventType, callback: (event: IntegrationEvent) => void): () => void {
    return this.eventEmitter.on(event, callback);
  }

  /**
   * Get capabilities for current variant
   */
  getCapabilities(): JarvisVariantCapabilities {
    const capabilities: Record<Variant, JarvisVariantCapabilities> = {
      mini_parwa: {
        maxCommandsPerDay: 100,
        maxConcurrentSessions: 1,
        memoryRetentionHours: 24,
        proactiveAlerts: false,
        smartSuggestions: false,
        patternDetection: false,
        maxCacheSize: 10,
        advancedAnalytics: false,
        voiceCommands: false,
        apiAccess: 'none',
      },
      parwa: {
        maxCommandsPerDay: 500,
        maxConcurrentSessions: 3,
        memoryRetentionHours: 168,
        proactiveAlerts: true,
        smartSuggestions: true,
        patternDetection: true,
        maxCacheSize: 50,
        advancedAnalytics: true,
        voiceCommands: false,
        apiAccess: 'read',
      },
      parwa_high: {
        maxCommandsPerDay: -1,
        maxConcurrentSessions: 10,
        memoryRetentionHours: 720,
        proactiveAlerts: true,
        smartSuggestions: true,
        patternDetection: true,
        maxCacheSize: 200,
        advancedAnalytics: true,
        voiceCommands: true,
        apiAccess: 'full',
      },
    };

    return capabilities[this.config.variant];
  }

  /**
   * Get statistics
   */
  getStats(): {
    sessions: { active: number };
    cache: { hitRate: number };
    rateLimit: { totalRequests: number; blockRate: number };
    audit: { totalEntries: number };
  } {
    const cacheStats = this.cacheManager.getStats();
    const rateLimitStats = this.rateLimiter.getStats();
    const auditStats = this.auditLogger.getStats();

    return {
      sessions: { active: this.sessionManager.getActiveCount() },
      cache: { hitRate: cacheStats.hitRate },
      rateLimit: {
        totalRequests: rateLimitStats.totalRequests,
        blockRate: rateLimitStats.blockRate,
      },
      audit: { totalEntries: auditStats.logs.totalEntries },
    };
  }

  /**
   * Shutdown JARVIS
   */
  async shutdown(): Promise<void> {
    this.cacheManager.shutdown();
    this.auditLogger.shutdown();
    this.sessionManager.clear();
    this.eventEmitter.clear();
    this.isInitialized = false;
  }

  // ── Private Methods ─────────────────────────────────────────────

  private async createSession(sessionId: string, userId: string): Promise<void> {
    const awarenessState = await this.awarenessEngine?.getState();
    const commandContext = this.getDefaultCommandContext(sessionId);

    this.sessionManager.create(
      sessionId,
      this.config.organizationId,
      this.config.variant,
      awarenessState || this.getDefaultAwarenessState(),
      commandContext
    );

    this.auditLogger.logSession({
      organizationId: this.config.organizationId,
      sessionId,
      userId,
      action: 'create',
    });
  }

  private getDefaultAwarenessState(): AwarenessState {
    return {
      tenant_id: this.config.organizationId,
      variant: this.config.variant,
      health: {
        status: 'healthy',
        components: [],
        last_check: new Date(),
        incidents: [],
      },
      active_alerts: [],
      recent_activities: [],
      sentiment_summary: null,
      aggregated_metrics: [],
    } as unknown as AwarenessState;
  }

  private getDefaultCommandContext(sessionId: string): CommandContext {
    return {
      session_id: sessionId,
      tenant_id: this.config.organizationId,
      variant: this.config.variant,
      conversation_history: [],
      page_context: null,
      current_ticket: null,
      current_customer: null,
      active_filters: {},
      user_preferences: {},
      created_at: new Date(),
      last_activity: new Date(),
    } as unknown as CommandContext;
  }

  private generateSessionId(): string {
    return `jarvis_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  private validateInput(input: string): { valid: boolean; error?: string } {
    const config = this.config.security;

    if (!config) return { valid: true };

    // Check length
    if (input.length > config.maxCommandLength) {
      return { valid: false, error: 'Command too long' };
    }

    // Check forbidden patterns (case-insensitive)
    for (const pattern of config.forbiddenPatterns) {
      const regex = new RegExp(pattern, 'i');
      if (regex.test(input)) {
        return { valid: false, error: 'Forbidden pattern detected' };
      }
    }

    return { valid: true };
  }

  private updateMetrics(session: JarvisState, responseTime: number): void {
    session.metrics.commandsProcessed++;
    session.metrics.avgResponseTime =
      (session.metrics.avgResponseTime * (session.metrics.commandsProcessed - 1) + responseTime) /
      session.metrics.commandsProcessed;
    session.lastActivityAt = new Date();
  }

  private generateSuggestions(
    result: { success: boolean; message?: string; mode?: string },
    session: JarvisState
  ): SuggestedAction[] {
    const capabilities = this.getCapabilities();
    const suggestions: SuggestedAction[] = [];

    if (!capabilities.smartSuggestions) {
      return suggestions;
    }

    // Add contextual suggestions based on result and session state
    if (session.activeDrafts.size > 0) {
      suggestions.push({
        type: 'acknowledgment',
        label: `Review ${session.activeDrafts.size} pending draft(s)`,
        priority: 1,
        icon: 'clipboard-list',
      });
    }

    if (session.pendingAlerts.length > 0) {
      suggestions.push({
        type: 'acknowledgment',
        label: `${session.pendingAlerts.length} alerts need attention`,
        priority: 2,
        icon: 'alert-triangle',
      });
    }

    return suggestions;
  }

  private async getAwarenessUpdates(session: JarvisState): Promise<{ newAlerts?: Alert[] } | undefined> {
    if (!this.awarenessEngine) return undefined;

    const state = await this.awarenessEngine.getState();
    if (!state) return undefined;

    // Find new alerts - use active_alerts or alerts depending on type
    const alerts = (state as any).active_alerts || (state as any).alerts || [];
    const existingIds = new Set(session.pendingAlerts.map(a => a.id));
    const newAlerts = alerts.filter((a: Alert) => !existingIds.has(a.id));

    if (newAlerts.length > 0) {
      session.pendingAlerts.push(...newAlerts);
      return { newAlerts };
    }

    return undefined;
  }

  private createDraftPreview(draft: Draft): DraftPreview {
    // Draft has a preview property with the actual preview data
    // Return the preview directly or construct from draft
    if (draft.preview) {
      return {
        id: draft.id,
        command: draft.command_id,
        changes: draft.preview.changes.map(c => ({
          field: c.field,
          currentValue: c.current_value,
          newValue: c.new_value,
          description: c.description,
        })),
        affectedItems: draft.preview.affected_items.map(i => ({
          type: (i.type === 'automation' ? 'team' : i.type) as 'ticket' | 'customer' | 'agent' | 'team' | 'billing',
          id: i.id,
          label: i.name || i.id,
          impactLevel: draft.preview.estimated_impact as 'info' | 'warning' | 'critical',
        })),
        riskLevel: draft.preview.estimated_impact,
        expiresAt: draft.expires_at,
      };
    }
    
    // Fallback for drafts without preview
    return {
      id: draft.id,
      command: draft.command_id,
      changes: [],
      affectedItems: [],
      riskLevel: 'medium',
      expiresAt: draft.expires_at,
    };
  }

  private createErrorResponse(
    sessionId: string,
    message: string,
    resultType: 'error' | 'rate_limited' | 'security_violation'
  ): ProcessJarvisCommandResponse {
    return {
      sessionId,
      commandId: '',
      success: false,
      message,
      resultType: 'error',
      timestamp: new Date(),
    };
  }

  private emitEvent(event: IntegrationEvent): void {
    this.eventEmitter.emit(event);
  }

  private async checkAwarenessHealth(): Promise<ComponentHealthStatus> {
    try {
      const state = await this.awarenessEngine?.getState();
      const healthStatus = (state as any)?.health?.status || 'healthy';
      return {
        status: healthStatus,
        lastCheck: new Date(),
      };
    } catch {
      return {
        status: 'unhealthy',
        lastError: 'Failed to get awareness state',
        lastCheck: new Date(),
      };
    }
  }

  private async checkCommandHealth(): Promise<ComponentHealthStatus> {
    try {
      const available = this.commandProcessor?.getAvailableCommands();
      return {
        status: available && available.length > 0 ? 'healthy' : 'degraded',
        lastCheck: new Date(),
      };
    } catch {
      return {
        status: 'unhealthy',
        lastError: 'Failed to get available commands',
        lastCheck: new Date(),
      };
    }
  }

  private checkCacheHealth(): ComponentHealthStatus {
    const stats = this.cacheManager.getStats();
    return {
      status: stats.hitRate > 0.5 ? 'healthy' : 'degraded',
      lastCheck: new Date(),
    };
  }

  private checkRateLimiterHealth(): ComponentHealthStatus {
    const stats = this.rateLimiter.getStats();
    return {
      status: stats.blockRate < 0.1 ? 'healthy' : 'degraded',
      lastCheck: new Date(),
    };
  }

  private checkAuditHealth(): ComponentHealthStatus {
    const stats = this.auditLogger.getStats();
    return {
      status: 'healthy',
      lastCheck: new Date(),
    };
  }

  private determineOverallStatus(components: ComponentHealthStatus[]): 'healthy' | 'degraded' | 'unhealthy' {
    const hasUnhealthy = components.some(c => c.status === 'unhealthy');
    const hasDegraded = components.some(c => c.status === 'degraded');

    if (hasUnhealthy) return 'unhealthy';
    if (hasDegraded) return 'degraded';
    return 'healthy';
  }
}

// ── Factory Functions ──────────────────────────────────────────────

export function createJarvisOrchestrator(config: JarvisConfig): JarvisOrchestrator {
  return new JarvisOrchestrator(config);
}

// ── Singleton Registry ─────────────────────────────────────────────

const orchestrators = new Map<string, JarvisOrchestrator>();

export function getJarvisOrchestrator(config: JarvisConfig): JarvisOrchestrator {
  const key = config.organizationId;
  
  if (!orchestrators.has(key)) {
    orchestrators.set(key, createJarvisOrchestrator(config));
  }
  
  return orchestrators.get(key)!;
}

export async function shutdownJarvisOrchestrator(organizationId: string): Promise<void> {
  const orchestrator = orchestrators.get(organizationId);
  if (orchestrator) {
    await orchestrator.shutdown();
    orchestrators.delete(organizationId);
  }
}

export async function shutdownAllOrchestrators(): Promise<void> {
  for (const orchestrator of orchestrators.values()) {
    await orchestrator.shutdown();
  }
  orchestrators.clear();
}
