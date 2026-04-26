/**
 * JARVIS Audit Logger - Week 4 (Phase 1)
 *
 * Comprehensive audit logging for JARVIS operations.
 * Tracks all commands, decisions, and security events.
 */

import type { AuditLogEntry, AuditAction, SecurityViolation, SecurityViolationType } from './types';

// ── Audit Logger Configuration ─────────────────────────────────────

interface AuditLoggerConfig {
  /** Enable audit logging */
  enabled: boolean;
  /** Maximum entries to keep in memory */
  maxEntries: number;
  /** Log retention in days */
  retentionDays: number;
  /** Include IP addresses */
  logIpAddresses: boolean;
  /** Include user agents */
  logUserAgents: boolean;
  /** Log level */
  logLevel: 'debug' | 'info' | 'warn' | 'error';
  /** Flush interval (ms) */
  flushInterval: number;
}

const DEFAULT_CONFIG: AuditLoggerConfig = {
  enabled: true,
  maxEntries: 10000,
  retentionDays: 90,
  logIpAddresses: true,
  logUserAgents: true,
  logLevel: 'info',
  flushInterval: 5000,
};

// ── In-Memory Log Store ────────────────────────────────────────────

class AuditLogStore {
  private entries: AuditLogEntry[] = [];
  private maxEntries: number;

  constructor(maxEntries: number) {
    this.maxEntries = maxEntries;
  }

  add(entry: AuditLogEntry): void {
    this.entries.push(entry);
    
    // Enforce max entries
    if (this.entries.length > this.maxEntries) {
      this.entries = this.entries.slice(-this.maxEntries);
    }
  }

  query(filter: AuditFilter): AuditLogEntry[] {
    let results = [...this.entries];

    if (filter.organizationId) {
      results = results.filter(e => e.organizationId === filter.organizationId);
    }
    if (filter.sessionId) {
      results = results.filter(e => e.sessionId === filter.sessionId);
    }
    if (filter.userId) {
      results = results.filter(e => e.userId === filter.userId);
    }
    if (filter.action) {
      results = results.filter(e => e.action === filter.action);
    }
    if (filter.resourceType) {
      results = results.filter(e => e.resourceType === filter.resourceType);
    }
    if (filter.result) {
      results = results.filter(e => e.result === filter.result);
    }
    if (filter.startDate) {
      results = results.filter(e => e.timestamp >= filter.startDate!);
    }
    if (filter.endDate) {
      results = results.filter(e => e.timestamp <= filter.endDate!);
    }

    // Sort by timestamp descending
    results.sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime());

    // Apply pagination
    const offset = filter.offset ?? 0;
    const limit = filter.limit ?? 100;
    return results.slice(offset, offset + limit);
  }

  count(filter: AuditFilter): number {
    return this.query(filter).length;
  }

  clear(): void {
    this.entries = [];
  }

  prune(retentionDays: number): number {
    const cutoff = new Date(Date.now() - retentionDays * 24 * 60 * 60 * 1000);
    const initialLength = this.entries.length;
    this.entries = this.entries.filter(e => e.timestamp >= cutoff);
    return initialLength - this.entries.length;
  }

  getStats(): { totalEntries: number; oldestEntry: Date | null; newestEntry: Date | null } {
    if (this.entries.length === 0) {
      return { totalEntries: 0, oldestEntry: null, newestEntry: null };
    }
    return {
      totalEntries: this.entries.length,
      oldestEntry: this.entries[0]?.timestamp ?? null,
      newestEntry: this.entries[this.entries.length - 1]?.timestamp ?? null,
    };
  }
}

interface AuditFilter {
  organizationId?: string;
  sessionId?: string;
  userId?: string;
  action?: AuditAction;
  resourceType?: string;
  result?: 'success' | 'failure' | 'pending';
  startDate?: Date;
  endDate?: Date;
  offset?: number;
  limit?: number;
}

// ── Security Violation Store ───────────────────────────────────────

class SecurityViolationStore {
  private violations: SecurityViolation[] = [];
  private maxEntries: number;

  constructor(maxEntries: number) {
    this.maxEntries = maxEntries;
  }

  add(violation: SecurityViolation): void {
    this.violations.push(violation);
    if (this.violations.length > this.maxEntries) {
      this.violations = this.violations.slice(-this.maxEntries);
    }
  }

  query(filter: {
    sessionId?: string;
    userId?: string;
    type?: SecurityViolationType;
    severity?: 'low' | 'medium' | 'high' | 'critical';
    startDate?: Date;
    endDate?: Date;
  }): SecurityViolation[] {
    let results = [...this.violations];

    if (filter.sessionId) {
      results = results.filter(v => v.sessionId === filter.sessionId);
    }
    if (filter.userId) {
      results = results.filter(v => v.userId === filter.userId);
    }
    if (filter.type) {
      results = results.filter(v => v.type === filter.type);
    }
    if (filter.severity) {
      results = results.filter(v => v.severity === filter.severity);
    }
    if (filter.startDate) {
      results = results.filter(v => v.timestamp >= filter.startDate!);
    }
    if (filter.endDate) {
      results = results.filter(v => v.timestamp <= filter.endDate!);
    }

    return results.sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime());
  }

  countByUser(userId: string, since: Date): number {
    return this.violations.filter(
      v => v.userId === userId && v.timestamp >= since
    ).length;
  }

  clear(): void {
    this.violations = [];
  }
}

// ── Audit Logger ───────────────────────────────────────────────────

export class AuditLogger {
  private config: AuditLoggerConfig;
  private logStore: AuditLogStore;
  private violationStore: SecurityViolationStore;
  private flushTimer: NodeJS.Timeout | null = null;
  private pendingEntries: AuditLogEntry[] = [];

  constructor(config: Partial<AuditLoggerConfig> = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config };
    this.logStore = new AuditLogStore(this.config.maxEntries);
    this.violationStore = new SecurityViolationStore(this.config.maxEntries);
    
    if (this.config.enabled) {
      this.startFlushTimer();
    }
  }

  /**
   * Log a command execution
   */
  logCommand(
    params: {
      organizationId: string;
      sessionId: string;
      userId: string;
      command: string;
      commandId: string;
      result: 'success' | 'failure' | 'pending';
      executionMode: 'direct' | 'draft';
      changes?: Record<string, { from: unknown; to: unknown }>;
      ipAddress?: string;
      userAgent?: string;
    }
  ): AuditLogEntry {
    const entry: AuditLogEntry = {
      id: this.generateId(),
      organizationId: params.organizationId,
      sessionId: params.sessionId,
      userId: params.userId,
      timestamp: new Date(),
      action: params.executionMode === 'direct' ? 'command_execute' : 'command_draft',
      resourceType: 'command',
      resourceId: params.commandId,
      command: params.command,
      result: params.result,
      changes: params.changes,
      ipAddress: this.config.logIpAddresses ? params.ipAddress : undefined,
      userAgent: this.config.logUserAgents ? params.userAgent : undefined,
    };

    this.addEntry(entry);
    return entry;
  }

  /**
   * Log an approval action
   */
  logApproval(
    params: {
      organizationId: string;
      sessionId: string;
      userId: string;
      draftId: string;
      action: 'approve' | 'reject';
      comment?: string;
      ipAddress?: string;
    }
  ): AuditLogEntry {
    const entry: AuditLogEntry = {
      id: this.generateId(),
      organizationId: params.organizationId,
      sessionId: params.sessionId,
      userId: params.userId,
      timestamp: new Date(),
      action: params.action === 'approve' ? 'command_approve' : 'command_reject',
      resourceType: 'draft',
      resourceId: params.draftId,
      result: 'success',
      metadata: { comment: params.comment },
      ipAddress: this.config.logIpAddresses ? params.ipAddress : undefined,
    };

    this.addEntry(entry);
    return entry;
  }

  /**
   * Log an alert action
   */
  logAlert(
    params: {
      organizationId: string;
      sessionId: string;
      userId: string;
      alertId: string;
      action: 'acknowledge' | 'resolve';
      details?: string;
    }
  ): AuditLogEntry {
    const entry: AuditLogEntry = {
      id: this.generateId(),
      organizationId: params.organizationId,
      sessionId: params.sessionId,
      userId: params.userId,
      timestamp: new Date(),
      action: params.action === 'acknowledge' ? 'alert_acknowledge' : 'alert_resolve',
      resourceType: 'alert',
      resourceId: params.alertId,
      result: 'success',
      metadata: { details: params.details },
    };

    this.addEntry(entry);
    return entry;
  }

  /**
   * Log a session event
   */
  logSession(
    params: {
      organizationId: string;
      sessionId: string;
      userId: string;
      action: 'create' | 'end';
      metadata?: Record<string, unknown>;
    }
  ): AuditLogEntry {
    const entry: AuditLogEntry = {
      id: this.generateId(),
      organizationId: params.organizationId,
      sessionId: params.sessionId,
      userId: params.userId,
      timestamp: new Date(),
      action: params.action === 'create' ? 'session_create' : 'session_end',
      resourceType: 'session',
      resourceId: params.sessionId,
      result: 'success',
      metadata: params.metadata,
    };

    this.addEntry(entry);
    return entry;
  }

  /**
   * Log an access denied event
   */
  logAccessDenied(
    params: {
      organizationId: string;
      sessionId: string;
      userId: string;
      resourceType: string;
      resourceId: string;
      reason: string;
      ipAddress?: string;
    }
  ): AuditLogEntry {
    const entry: AuditLogEntry = {
      id: this.generateId(),
      organizationId: params.organizationId,
      sessionId: params.sessionId,
      userId: params.userId,
      timestamp: new Date(),
      action: 'access_denied',
      resourceType: params.resourceType,
      resourceId: params.resourceId,
      result: 'failure',
      metadata: { reason: params.reason },
      ipAddress: this.config.logIpAddresses ? params.ipAddress : undefined,
    };

    this.addEntry(entry);
    return entry;
  }

  /**
   * Record a security violation
   */
  recordViolation(
    params: {
      sessionId: string;
      userId: string;
      type: SecurityViolationType;
      severity: 'low' | 'medium' | 'high' | 'critical';
      description: string;
      input: string;
      action: 'warn' | 'block' | 'rate_limit' | 'ban';
      ipAddress?: string;
    }
  ): SecurityViolation {
    const violation: SecurityViolation = {
      id: this.generateId(),
      sessionId: params.sessionId,
      userId: params.userId,
      timestamp: new Date(),
      type: params.type,
      severity: params.severity,
      description: params.description,
      input: this.sanitizeInput(params.input),
      action: params.action,
      ipAddress: this.config.logIpAddresses ? params.ipAddress : undefined,
    };

    this.violationStore.add(violation);
    return violation;
  }

  /**
   * Query audit logs
   */
  queryLogs(filter: AuditFilter): AuditLogEntry[] {
    return this.logStore.query(filter);
  }

  /**
   * Query security violations
   */
  queryViolations(filter: {
    sessionId?: string;
    userId?: string;
    type?: SecurityViolationType;
    severity?: 'low' | 'medium' | 'high' | 'critical';
    startDate?: Date;
    endDate?: Date;
  }): SecurityViolation[] {
    return this.violationStore.query(filter);
  }

  /**
   * Get violation count for a user
   */
  getViolationCount(userId: string, withinHours: number = 24): number {
    const since = new Date(Date.now() - withinHours * 60 * 60 * 1000);
    return this.violationStore.countByUser(userId, since);
  }

  /**
   * Get log statistics
   */
  getStats(): {
    logs: { totalEntries: number; oldestEntry: Date | null; newestEntry: Date | null };
    violations: { total: number; critical: number; high: number };
  } {
    const violations = this.violationStore.query({});
    return {
      logs: this.logStore.getStats(),
      violations: {
        total: violations.length,
        critical: violations.filter(v => v.severity === 'critical').length,
        high: violations.filter(v => v.severity === 'high').length,
      },
    };
  }

  /**
   * Clear all logs
   */
  clear(): void {
    this.logStore.clear();
    this.violationStore.clear();
    this.pendingEntries = [];
  }

  /**
   * Prune old entries
   */
  prune(): number {
    return this.logStore.prune(this.config.retentionDays);
  }

  /**
   * Shutdown
   */
  shutdown(): void {
    if (this.flushTimer) {
      clearInterval(this.flushTimer);
      this.flushTimer = null;
    }
    this.flush();
  }

  // ── Private Methods ─────────────────────────────────────────────

  private addEntry(entry: AuditLogEntry): void {
    if (!this.config.enabled) return;

    this.pendingEntries.push(entry);
    
    // Flush immediately for errors or if batch is large
    if (
      entry.result === 'failure' ||
      this.pendingEntries.length >= 100
    ) {
      this.flush();
    }
  }

  private flush(): void {
    if (this.pendingEntries.length === 0) return;

    for (const entry of this.pendingEntries) {
      this.logStore.add(entry);
    }
    
    this.pendingEntries = [];
  }

  private startFlushTimer(): void {
    this.flushTimer = setInterval(() => {
      this.flush();
      this.prune();
    }, this.config.flushInterval);
  }

  private generateId(): string {
    return `audit_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  private sanitizeInput(input: string): string {
    // Truncate and remove sensitive data
    const maxLen = 200;
    let sanitized = input.length > maxLen ? input.slice(0, maxLen) + '...' : input;
    
    // Remove potential secrets
    sanitized = sanitized.replace(/[a-zA-Z0-9]{32,}/g, '[REDACTED]');
    sanitized = sanitized.replace(/[0-9]{13,16}/g, '[REDACTED]');
    
    return sanitized;
  }
}

// ── Factory Function ───────────────────────────────────────────────

export function createAuditLogger(config?: Partial<AuditLoggerConfig>): AuditLogger {
  return new AuditLogger(config);
}

// ── Singleton Instance ─────────────────────────────────────────────

let defaultLogger: AuditLogger | null = null;

export function getAuditLogger(): AuditLogger {
  if (!defaultLogger) {
    defaultLogger = new AuditLogger();
  }
  return defaultLogger;
}

export function shutdownAuditLogger(): void {
  if (defaultLogger) {
    defaultLogger.shutdown();
    defaultLogger = null;
  }
}
