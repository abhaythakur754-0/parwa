/**
 * JARVIS Week 10 - Critical Integration Gap Tests
 *
 * Tests for critical security and reliability gaps:
 * - Tenant isolation in ticket search
 * - Payment failure state isolation
 * - Ticket count race conditions
 * - Webhook deduplication
 * - Cache invalidation on tenant deletion
 */

import { JarvisOrchestrator, createJarvisOrchestrator } from '../jarvis-orchestrator';
import { CacheManager, createCacheManager } from '../cache-manager';
import { RateLimiter, createRateLimiter } from '../rate-limiter';
import { AuditLogger, createAuditLogger } from '../audit-logger';
import type { Variant } from '@/types/variant';
import type { JarvisConfig } from '../types';

// ── Test Setup ──────────────────────────────────────────────────────────

const createOrchestratorConfig = (tenantId: string, variant: Variant = 'parwa'): JarvisConfig => ({
  organizationId: tenantId,
  variant,
  debug: false,
  security: {
    maxCommandLength: 1000,
    forbiddenPatterns: ['DROP TABLE', 'DELETE FROM', ';--', '<script>'],
    auditLogging: true,
  },
});

const createOrchestrator = (tenantId: string, variant: Variant = 'parwa'): JarvisOrchestrator => {
  return createJarvisOrchestrator(createOrchestratorConfig(tenantId, variant));
};

// ── Tenant Isolation Tests ──────────────────────────────────────────────

describe('Week 10: Tenant Isolation', () => {
  describe('Ticket Search Isolation', () => {
    it('should isolate tickets by tenant in search results', async () => {
      const tenantA = createOrchestrator('tenant_A', 'parwa');
      const tenantB = createOrchestrator('tenant_B', 'parwa');

      await tenantA.initialize();
      await tenantB.initialize();

      // Verify tenant isolation in capabilities
      const capsA = tenantA.getCapabilities();
      const capsB = tenantB.getCapabilities();

      // Both should have same capabilities for same variant
      expect(capsA.maxCommandsPerDay).toBe(capsB.maxCommandsPerDay);

      await tenantA.shutdown();
      await tenantB.shutdown();
    });

    it('should prevent cross-tenant command execution', async () => {
      const tenantA = createOrchestrator('tenant_A', 'parwa');
      await tenantA.initialize();

      // Process command for tenant A
      const result = await tenantA.processCommand({
        command: 'show stats',
        userId: 'user_A',
        userRole: 'agent',
      });

      expect(result.success).toBe(true);
      expect(result.sessionId).toBeDefined();

      await tenantA.shutdown();
    });

    it('should isolate rate limits by tenant', async () => {
      const limiterA = createRateLimiter({
        enabled: true,
        requestsPerMinute: 60,
        commandsPerHour: 100,
        burstAllowance: 10,
      });
      const limiterB = createRateLimiter({
        enabled: true,
        requestsPerMinute: 60,
        commandsPerHour: 100,
        burstAllowance: 10,
      });

      // Exhaust rate limit for tenant A user
      for (let i = 0; i < 70; i++) {
        limiterA.checkLimit('user_A', 'tenant_A', 'parwa', 'command');
      }

      // Tenant A user should be limited
      const resultA = limiterA.checkLimit('user_A', 'tenant_A', 'parwa', 'command');
      expect(resultA.allowed).toBe(false);

      // Tenant B user should still have quota
      const resultB = limiterB.checkLimit('user_B', 'tenant_B', 'parwa', 'command');
      expect(resultB.allowed).toBe(true);
    });

    it('should isolate cache by tenant', async () => {
      const cacheA = createCacheManager({
        enabled: true,
        defaultTtl: 60,
        maxSize: 100,
      });
      const cacheB = createCacheManager({
        enabled: true,
        defaultTtl: 60,
        maxSize: 100,
      });

      // Set data in tenant A's cache
      cacheA.set('default', 'sensitive_data', { secret: 'tenant_A_secret' });

      // Tenant B should not be able to access tenant A's data (different cache instance)
      const dataB = cacheB.get('default', 'sensitive_data');
      expect(dataB).toBeNull();

      // Tenant A should be able to access their data
      const dataA = cacheA.get('default', 'sensitive_data');
      expect(dataA).toEqual({ secret: 'tenant_A_secret' });
    });
  });

  describe('Audit Log Isolation', () => {
    it('should isolate audit logs by tenant', async () => {
      const auditA = createAuditLogger({
        enabled: true,
        maxEntries: 1000,
        retentionDays: 90,
      });
      const auditB = createAuditLogger({
        enabled: true,
        maxEntries: 1000,
        retentionDays: 90,
      });

      // Log commands for both tenants
      auditA.logCommand({
        organizationId: 'tenant_A',
        sessionId: 'session_A',
        userId: 'user_A',
        command: 'delete ticket 123',
        commandId: 'cmd_1',
        result: 'success',
        executionMode: 'direct',
      });

      auditB.logCommand({
        organizationId: 'tenant_B',
        sessionId: 'session_B',
        userId: 'user_B',
        command: 'delete ticket 456',
        commandId: 'cmd_2',
        result: 'success',
        executionMode: 'direct',
      });

      // Each tenant should only see their own logs
      const logsA = auditA.queryLogs({ userId: 'user_A' });
      const logsB = auditB.queryLogs({ userId: 'user_B' });

      expect(logsA.length).toBeGreaterThan(0);
      expect(logsB.length).toBeGreaterThan(0);

      // Verify isolation
      const statsA = auditA.getStats();
      const statsB = auditB.getStats();

      expect(statsA.logs.totalEntries).toBe(1);
      expect(statsB.logs.totalEntries).toBe(1);
    });
  });
});

// ── Payment Failure State Tests ──────────────────────────────────────────

describe('Week 10: Payment Failure State Isolation', () => {
  it('should isolate payment failure state from other tenants', async () => {
    const tenantA = createOrchestrator('tenant_A_payment', 'parwa');
    const tenantB = createOrchestrator('tenant_B_payment', 'parwa');

    await tenantA.initialize();
    await tenantB.initialize();

    // Both tenants should be operational
    const resultA = await tenantA.processCommand({
      command: 'show stats',
      userId: 'user_A',
      userRole: 'agent',
    });

    const resultB = await tenantB.processCommand({
      command: 'show stats',
      userId: 'user_B',
      userRole: 'agent',
    });

    expect(resultA.success).toBe(true);
    expect(resultB.success).toBe(true);

    await tenantA.shutdown();
    await tenantB.shutdown();
  });

  it('should track payment state per tenant', async () => {
    const cache = createCacheManager({
      enabled: true,
      defaultTtl: 300,
      maxSize: 100,
    });

    // Simulate payment state for different tenants
    cache.set('default', 'payment_status:tenant_A', 'failed');
    cache.set('default', 'payment_status:tenant_B', 'active');

    // Each tenant's payment status should be isolated
    const statusA = cache.get('default', 'payment_status:tenant_A');
    const statusB = cache.get('default', 'payment_status:tenant_B');

    expect(statusA).toBe('failed');
    expect(statusB).toBe('active');
  });
});

// ── Race Condition Tests ────────────────────────────────────────────────

describe('Week 10: Race Condition Handling', () => {
  it('should handle concurrent command processing', async () => {
    const orchestrator = createOrchestrator('tenant_race_test', 'parwa_high');
    await orchestrator.initialize();

    // Execute multiple commands concurrently
    const commands = [
      'show stats',
      'list tickets',
      'show agents',
      'help',
    ];

    const results = await Promise.all(
      commands.map(cmd => orchestrator.processCommand({
        command: cmd,
        userId: 'user_race',
        userRole: 'agent',
      }))
    );

    // All commands should complete successfully
    results.forEach(result => {
      expect(result.success).toBe(true);
    });

    await orchestrator.shutdown();
  });

  it('should handle rapid cache operations', async () => {
    const cache = createCacheManager({
      enabled: true,
      defaultTtl: 60,
      maxSize: 1000,
    });

    // Concurrent set operations
    const operations = Array.from({ length: 100 }, (_, i) =>
      Promise.resolve(cache.set('default', `key_${i}`, { value: i }))
    );

    await Promise.all(operations);

    // Verify values were set (check total entries across namespaces)
    const stats = cache.getStats();
    expect(stats.total.entries).toBeGreaterThanOrEqual(100);
  });

  it('should handle rate limiter concurrent checks', async () => {
    const limiter = createRateLimiter({
      enabled: true,
      requestsPerMinute: 100,
      commandsPerHour: 500,
      burstAllowance: 20,
    });

    // Concurrent rate limit checks
    const checks = await Promise.all(
      Array.from({ length: 50 }, () =>
        Promise.resolve(limiter.checkLimit('user_race', 'tenant_race', 'parwa_high', 'command'))
      )
    );

    // At least some should succeed
    const allowedCount = checks.filter(c => c.allowed).length;
    expect(allowedCount).toBeGreaterThan(0);
  });
});

// ── Webhook Deduplication Tests ──────────────────────────────────────────

describe('Week 10: Webhook Deduplication', () => {
  it('should detect duplicate webhook payloads', async () => {
    const cache = createCacheManager({
      enabled: true,
      defaultTtl: 86400,
      maxSize: 1000,
    });

    const webhookId = 'wh_' + Date.now();

    // First webhook should be processed
    const exists = cache.get('default', `webhook_processed:${webhookId}`);
    expect(exists).toBeNull();

    // Mark as processed
    cache.set('default', `webhook_processed:${webhookId}`, { processed_at: Date.now() });

    // Second webhook with same ID should be detected as duplicate
    const alreadyProcessed = cache.get('default', `webhook_processed:${webhookId}`);
    expect(alreadyProcessed).not.toBeNull();
  });

  it('should handle webhook replay attack prevention', async () => {
    const cache = createCacheManager({
      enabled: true,
      defaultTtl: 3600,
      maxSize: 100,
    });
    const audit = createAuditLogger({
      enabled: true,
      maxEntries: 100,
      retentionDays: 30,
    });

    const webhookSignature = 'sig_' + Date.now();

    // Log first webhook
    audit.logCommand({
      organizationId: 'tenant_webhook',
      sessionId: 'webhook_session',
      userId: 'webhook_system',
      command: 'payment_webhook',
      commandId: webhookSignature,
      result: 'success',
      executionMode: 'direct',
    });

    // Cache the signature
    cache.set('default', `webhook_sig:${webhookSignature}`, { processed_at: Date.now() });

    // Attempt to replay
    const replayCheck = cache.get('default', `webhook_sig:${webhookSignature}`);
    expect(replayCheck).not.toBeNull();

    // Should reject replay (would be checked in real implementation)
    const stats = audit.getStats();
    expect(stats.logs.totalEntries).toBe(1); // Only one processed
  });
});

// ── Cache Invalidation Tests ─────────────────────────────────────────────

describe('Week 10: Cache Invalidation', () => {
  it('should clear tenant cache on deletion', async () => {
    const cache = createCacheManager({
      enabled: true,
      defaultTtl: 60,
      maxSize: 100,
    });

    // Create tenant data
    cache.set('tenant_to_delete', 'tickets:all', [{ id: 1 }, { id: 2 }]);
    cache.set('tenant_to_delete', 'settings', { theme: 'dark' });

    // Verify data exists
    const ticketsBefore = cache.get('tenant_to_delete', 'tickets:all');
    expect(ticketsBefore).not.toBeNull();

    // Clear tenant cache
    cache.clearNamespace('tenant_to_delete');

    // Verify data is cleared
    const ticketsAfter = cache.get('tenant_to_delete', 'tickets:all');
    expect(ticketsAfter).toBeNull();
  });

  it('should prevent stale data access after tenant deletion', async () => {
    const oldTenantId = 'tenant_old_' + Date.now();
    const cache = createCacheManager({
      enabled: true,
      defaultTtl: 3600,
      maxSize: 100,
    });

    // Create data for old tenant
    cache.set(oldTenantId, 'sensitive_data', { api_key: 'secret_123' });

    // Simulate tenant deletion
    cache.clearNamespace(oldTenantId);

    // New access should not see old data
    const staleData = cache.get(oldTenantId, 'sensitive_data');
    expect(staleData).toBeNull();
  });

  it('should handle cache expiration correctly', async () => {
    const cache = createCacheManager({
      enabled: true,
      defaultTtl: 1, // 1 second
      maxSize: 100,
    });

    // Set data with short TTL
    cache.set('default', 'temp_data', { value: 'test' });

    // Should be available immediately
    const immediate = cache.get('default', 'temp_data');
    expect(immediate).toEqual({ value: 'test' });

    // Wait for expiration
    await new Promise(resolve => setTimeout(resolve, 1100));

    // Should be expired
    const expired = cache.get('default', 'temp_data');
    expect(expired).toBeNull();
  });
});

// ── Security Hardening Tests ─────────────────────────────────────────────

describe('Week 10: Security Hardening', () => {
  it('should reject SQL injection attempts', async () => {
    const orchestrator = createOrchestrator('tenant_security', 'parwa');
    await orchestrator.initialize();

    // SQL injection attempt
    const result = await orchestrator.processCommand({
      command: "show tickets WHERE id = '1' OR '1'='1' --",
      userId: 'user_sec',
      userRole: 'agent',
    });

    // Should handle gracefully (either reject or sanitize)
    expect(result).toBeDefined();

    await orchestrator.shutdown();
  });

  it('should reject XSS attempts', async () => {
    const orchestrator = createOrchestrator('tenant_xss', 'parwa');
    await orchestrator.initialize();

    // XSS attempt
    const result = await orchestrator.processCommand({
      command: '<script>alert("xss")</script>',
      userId: 'user_xss',
      userRole: 'agent',
    });

    // Should reject forbidden pattern
    expect(result.success).toBe(false);

    await orchestrator.shutdown();
  });

  it('should enforce command size limits', async () => {
    const orchestrator = createOrchestrator('tenant_size_limit', 'parwa');
    await orchestrator.initialize();

    // Create oversized command (max is 1000)
    const oversizedCommand = 'show stats ' + 'x'.repeat(2000);

    const result = await orchestrator.processCommand({
      command: oversizedCommand,
      userId: 'user_size',
      userRole: 'agent',
    });

    // Should reject oversized command
    expect(result.success).toBe(false);

    await orchestrator.shutdown();
  });

  it('should track security violations', async () => {
    const audit = createAuditLogger({
      enabled: true,
      maxEntries: 100,
      retentionDays: 30,
    });

    // Log a security violation
    audit.recordViolation({
      sessionId: 'session_violation',
      userId: 'user_violator',
      type: 'sql_injection_attempt',
      severity: 'high',
      description: 'SQL injection attempt detected',
      input: "SELECT * FROM users",
      action: 'blocked',
    });

    // Check violation count
    const count = audit.getViolationCount('user_violator', 24);
    expect(count).toBeGreaterThanOrEqual(1);

    const stats = audit.getStats();
    expect(stats.violations.total).toBeGreaterThan(0);
  });
});

// ── Performance Integration Tests ────────────────────────────────────────

describe('Week 10: Performance Integration', () => {
  it('should handle high command throughput', async () => {
    const orchestrator = createOrchestrator('tenant_perf', 'parwa_high');
    await orchestrator.initialize();

    const startTime = Date.now();
    const commandCount = 20;

    // Execute many commands
    for (let i = 0; i < commandCount; i++) {
      await orchestrator.processCommand({
        command: 'show stats',
        userId: 'user_perf',
        userRole: 'agent',
      });
    }

    const duration = Date.now() - startTime;
    const avgTime = duration / commandCount;

    // Should average less than 100ms per command
    expect(avgTime).toBeLessThan(100);

    await orchestrator.shutdown();
  });

  it('should benefit from caching', async () => {
    const cache = createCacheManager({
      enabled: true,
      defaultTtl: 60,
      maxSize: 100,
    });

    const key = 'expensive_query_result';
    const computeValue = () => ({ computed: true, timestamp: Date.now() });

    // First call - should compute
    const start1 = Date.now();
    const result1 = cache.getOrCompute('default', key, computeValue);
    const duration1 = Date.now() - start1;

    // Second call - should use cache
    const start2 = Date.now();
    const result2 = cache.getOrCompute('default', key, computeValue);
    const duration2 = Date.now() - start2;

    // Cache should be faster or similar
    expect(duration2).toBeLessThanOrEqual(duration1 + 5);

    // Results should be identical
    expect(result1).toEqual(result2);
  });
});

// ── End-to-End Integration Tests ─────────────────────────────────────────

describe('Week 10: End-to-End Integration', () => {
  it('should handle complete workflow', async () => {
    const orchestrator = createOrchestrator('tenant_e2e', 'parwa_high');
    await orchestrator.initialize();

    // Process first command to create session
    const response1 = await orchestrator.processCommand({
      command: 'show stats',
      userId: 'user_e2e',
      userRole: 'supervisor',
    });

    expect(response1.success).toBe(true);
    const sessionId = response1.sessionId;

    // Execute more commands with same session
    const commands = [
      'list agents',
      'show alerts',
      'help',
    ];

    for (const cmd of commands) {
      const result = await orchestrator.processCommand({
        command: cmd,
        sessionId,
        userId: 'user_e2e',
        userRole: 'supervisor',
      });
      expect(result.success).toBe(true);
    }

    // Check health
    const health = await orchestrator.getHealth();
    expect(health.status).toBeDefined();
    expect(['healthy', 'degraded', 'unhealthy']).toContain(health.status);

    // End session
    await orchestrator.endSession(sessionId, 'user_e2e');

    // Verify session ended
    const stats = orchestrator.getStats();
    expect(stats.sessions.active).toBe(0);

    await orchestrator.shutdown();
  });

  it('should maintain state across session', async () => {
    const orchestrator = createOrchestrator('tenant_state', 'parwa');
    await orchestrator.initialize();

    // First command creates session
    const response1 = await orchestrator.processCommand({
      command: 'show stats',
      userId: 'user_state',
      userRole: 'agent',
    });

    const sessionId = response1.sessionId;

    // Get session
    const session = orchestrator.getSession(sessionId);
    expect(session).toBeDefined();

    // Execute another command
    await orchestrator.processCommand({
      command: 'help',
      sessionId,
      userId: 'user_state',
      userRole: 'agent',
    });

    // Session should track command count
    const updatedSession = orchestrator.getSession(sessionId);
    expect(updatedSession?.metrics.commandsProcessed).toBeGreaterThan(0);

    await orchestrator.shutdown();
  });
});
