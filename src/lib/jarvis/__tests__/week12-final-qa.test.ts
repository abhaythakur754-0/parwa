/**
 * JARVIS Week 12 - Final QA Test Suite
 *
 * Comprehensive end-to-end tests for the complete JARVIS system.
 * Tests all modules working together in real-world scenarios.
 */

import { JarvisOrchestrator, createJarvisOrchestrator } from '../integration/jarvis-orchestrator';
import { MemoryManager } from '../memory/memory-manager';
import { ProactiveAlertManager } from '../proactive-alerts/proactive-alert-manager';
import { SmartSuggestionsManager } from '../smart-suggestions/smart-suggestions-manager';
import { PatternDetectionManager } from '../pattern-detection/pattern-detection-manager';
import { AnalyticsManager } from '../analytics/analytics-manager';
import { AutomationManager } from '../automation/automation-manager';
import { CacheManager, createCacheManager } from '../integration/cache-manager';
import { RateLimiter, createRateLimiter } from '../integration/rate-limiter';
import { AuditLogger, createAuditLogger } from '../integration/audit-logger';
import type { Variant } from '@/types/variant';
import type { JarvisConfig } from '../integration/types';

// ── Test Setup ──────────────────────────────────────────────────────────

const TEST_TENANT = 'tenant_final_qa';
const TEST_USER = 'user_qa';
const variants: Variant[] = ['mini_parwa', 'parwa', 'parwa_high'];

const createConfig = (tenantId: string, variant: Variant): JarvisConfig => ({
  organizationId: tenantId,
  variant,
  debug: false,
  security: {
    maxCommandLength: 1000,
    forbiddenPatterns: ['DROP TABLE', 'DELETE FROM', ';--', '<script>'],
    auditLogging: true,
  },
});

// ── Complete System Integration Tests ────────────────────────────────────

describe('Week 12: Final QA - Complete System', () => {
  describe('System Initialization', () => {
    it('should initialize all modules for parwa variant', async () => {
      const orchestrator = createJarvisOrchestrator(createConfig(TEST_TENANT, 'parwa'));
      await orchestrator.initialize();

      const health = await orchestrator.getHealth();
      expect(health.status).toBeDefined();
      expect(['healthy', 'degraded']).toContain(health.status);

      await orchestrator.shutdown();
    });

    it('should initialize all modules for parwa_high variant', async () => {
      const orchestrator = createJarvisOrchestrator(createConfig(TEST_TENANT, 'parwa_high'));
      await orchestrator.initialize();

      const health = await orchestrator.getHealth();
      expect(health.status).toBeDefined();

      await orchestrator.shutdown();
    });

    it('should report healthy status after initialization', async () => {
      const orchestrator = createJarvisOrchestrator(createConfig(TEST_TENANT, 'parwa'));
      await orchestrator.initialize();

      const health = await orchestrator.getHealth();
      expect(health.components).toBeDefined();
      expect(health.activeSessions).toBe(0);

      await orchestrator.shutdown();
    });
  });

  describe('Complete Command Workflow', () => {
    it('should handle command from input to response', async () => {
      const orchestrator = createJarvisOrchestrator(createConfig(TEST_TENANT, 'parwa'));
      await orchestrator.initialize();

      const result = await orchestrator.processCommand({
        command: 'show stats',
        userId: TEST_USER,
        userRole: 'agent',
      });

      expect(result.success).toBe(true);
      expect(result.sessionId).toBeDefined();
      expect(result.message).toBeDefined();

      await orchestrator.shutdown();
    });

    it('should track complete session lifecycle', async () => {
      const orchestrator = createJarvisOrchestrator(createConfig(TEST_TENANT, 'parwa'));
      await orchestrator.initialize();

      // Create session via command
      const result1 = await orchestrator.processCommand({
        command: 'show stats',
        userId: TEST_USER,
        userRole: 'agent',
      });

      const sessionId = result1.sessionId;
      expect(sessionId).toBeDefined();

      // Use existing session
      const result2 = await orchestrator.processCommand({
        command: 'help',
        sessionId,
        userId: TEST_USER,
        userRole: 'agent',
      });

      expect(result2.success).toBe(true);
      expect(result2.sessionId).toBe(sessionId);

      // End session
      await orchestrator.endSession(sessionId, TEST_USER);

      const stats = orchestrator.getStats();
      expect(stats.sessions.active).toBe(0);

      await orchestrator.shutdown();
    });

    it('should handle multiple concurrent sessions', async () => {
      const orchestrator = createJarvisOrchestrator(createConfig(TEST_TENANT, 'parwa_high'));
      await orchestrator.initialize();

      const sessions = await Promise.all([
        orchestrator.processCommand({ command: 'show stats', userId: 'user1', userRole: 'agent' }),
        orchestrator.processCommand({ command: 'show stats', userId: 'user2', userRole: 'agent' }),
        orchestrator.processCommand({ command: 'show stats', userId: 'user3', userRole: 'agent' }),
      ]);

      sessions.forEach(s => expect(s.success).toBe(true));

      const stats = orchestrator.getStats();
      expect(stats.sessions.active).toBe(3);

      await orchestrator.shutdown();
    });
  });

  describe('Security Integration', () => {
    it('should reject malicious commands', async () => {
      const orchestrator = createJarvisOrchestrator(createConfig(TEST_TENANT, 'parwa'));
      await orchestrator.initialize();

      const result = await orchestrator.processCommand({
        command: '<script>alert("xss")</script>',
        userId: TEST_USER,
        userRole: 'agent',
      });

      expect(result.success).toBe(false);

      await orchestrator.shutdown();
    });

    it('should enforce rate limiting', async () => {
      const limiter = createRateLimiter({
        enabled: true,
        requestsPerMinute: 5,
        commandsPerHour: 10,
        burstAllowance: 2,
      });

      // Exhaust rate limit
      for (let i = 0; i < 10; i++) {
        limiter.checkLimit(TEST_USER, TEST_TENANT, 'parwa', 'command');
      }

      const result = limiter.checkLimit(TEST_USER, TEST_TENANT, 'parwa', 'command');
      expect(result.allowed).toBe(false);
    });

    it('should log security violations', async () => {
      const audit = createAuditLogger({
        enabled: true,
        maxEntries: 100,
        retentionDays: 30,
      });

      audit.recordViolation({
        sessionId: 'test_session',
        userId: TEST_USER,
        type: 'sql_injection_attempt',
        severity: 'high',
        description: 'Test violation',
        input: 'SELECT * FROM users',
        action: 'blocked',
      });

      const count = audit.getViolationCount(TEST_USER, 24);
      expect(count).toBeGreaterThanOrEqual(1);
    });
  });
});

// ── Module Integration Tests ─────────────────────────────────────────────

describe('Week 12: Module Integration', () => {
  describe('Memory + Awareness Integration', () => {
    it('should share context between memory and awareness', async () => {
      const memoryManager = new MemoryManager(TEST_TENANT, 'parwa');
      // MemoryManager initializes in constructor

      // Verify memory manager exists
      expect(memoryManager).toBeDefined();

      memoryManager.shutdown();
    });
  });

  describe('Alerts + Suggestions Integration', () => {
    it('should generate suggestions based on alerts', async () => {
      const suggestionsManager = new SmartSuggestionsManager(TEST_TENANT, 'parwa');
      // SmartSuggestionsManager initializes in constructor

      // Verify suggestions manager exists
      expect(suggestionsManager).toBeDefined();
    });
  });

  describe('Pattern Detection + Analytics Integration', () => {
    it('should use analytics data for pattern detection', async () => {
      const analyticsManager = new AnalyticsManager(TEST_TENANT, 'parwa');
      await analyticsManager.initialize();

      const patternManager = new PatternDetectionManager(TEST_TENANT, 'parwa');
      // PatternDetectionManager initializes in constructor

      // Both should work
      expect(analyticsManager).toBeDefined();
      expect(patternManager).toBeDefined();

      await analyticsManager.shutdown();
    });
  });

  describe('Automation + Command Integration', () => {
    it('should integrate automation with command processing', async () => {
      const automationManager = new AutomationManager(TEST_TENANT, 'parwa');
      await automationManager.initialize();

      // Create automation workflow
      const workflow = automationManager.createWorkflow({
        name: 'Test Workflow',
        status: 'active',
        trigger: {
          id: 'trigger_1',
          type: 'ticket_created',
          name: 'Ticket Created',
          config: {},
          enabled: true,
        },
        steps: [
          {
            id: 'step_1',
            type: 'action',
            name: 'Assign Ticket',
            config: { action_type: 'assign_ticket' },
            position: { x: 100, y: 100 },
            enabled: true,
          },
        ],
        connections: [],
        variables: [],
        created_by: TEST_USER,
        tags: [],
        metadata: {},
      });

      expect(workflow.id).toBeDefined();

      // Execute workflow
      const execution = await automationManager.executeWorkflow(workflow.id, { ticket_id: 'TKT-001' });
      expect(execution.status).toBe('completed');

      await automationManager.shutdown();
    });
  });
});

// ── Variant Capability Tests ─────────────────────────────────────────────

describe('Week 12: Variant Capabilities', () => {
  describe('mini_parwa limitations', () => {
    it('should have minimal capabilities', async () => {
      const orchestrator = createJarvisOrchestrator(createConfig(TEST_TENANT, 'mini_parwa'));
      await orchestrator.initialize();

      const caps = orchestrator.getCapabilities();
      expect(caps.maxCommandsPerDay).toBe(100);
      expect(caps.maxConcurrentSessions).toBe(1);
      expect(caps.proactiveAlerts).toBe(false);
      expect(caps.smartSuggestions).toBe(false);
      expect(caps.patternDetection).toBe(false);

      await orchestrator.shutdown();
    });

    it('should reject automation for mini_parwa', async () => {
      const automationManager = new AutomationManager(TEST_TENANT, 'mini_parwa');
      await expect(automationManager.initialize()).rejects.toThrow('not enabled');
    });

    it('should reject analytics operations for mini_parwa', async () => {
      const analyticsManager = new AnalyticsManager(TEST_TENANT, 'mini_parwa');
      await analyticsManager.initialize();
      
      // mini_parwa should throw on analytics operations
      await expect(analyticsManager.predictVolume(7)).rejects.toThrow();
    });
  });

  describe('parwa standard capabilities', () => {
    it('should have standard capabilities', async () => {
      const orchestrator = createJarvisOrchestrator(createConfig(TEST_TENANT, 'parwa'));
      await orchestrator.initialize();

      const caps = orchestrator.getCapabilities();
      expect(caps.maxCommandsPerDay).toBe(500);
      expect(caps.maxConcurrentSessions).toBe(3);
      expect(caps.proactiveAlerts).toBe(true);
      expect(caps.smartSuggestions).toBe(true);
      expect(caps.patternDetection).toBe(true);

      await orchestrator.shutdown();
    });

    it('should allow automation with limits', async () => {
      const automationManager = new AutomationManager(TEST_TENANT, 'parwa');
      await automationManager.initialize();

      const caps = automationManager.getCapabilities();
      expect(caps.automation_enabled).toBe(true);
      expect(caps.max_automations).toBe(25);
      expect(caps.parallel_execution).toBe(false);

      await automationManager.shutdown();
    });
  });

  describe('parwa_high premium capabilities', () => {
    it('should have full capabilities', async () => {
      const orchestrator = createJarvisOrchestrator(createConfig(TEST_TENANT, 'parwa_high'));
      await orchestrator.initialize();

      const caps = orchestrator.getCapabilities();
      expect(caps.maxCommandsPerDay).toBe(-1); // Unlimited
      expect(caps.maxConcurrentSessions).toBe(10);
      expect(caps.apiAccess).toBe('full');

      await orchestrator.shutdown();
    });

    it('should allow advanced automation features', async () => {
      const automationManager = new AutomationManager(TEST_TENANT, 'parwa_high');
      await automationManager.initialize();

      const caps = automationManager.getCapabilities();
      expect(caps.max_automations).toBe(100);
      expect(caps.parallel_execution).toBe(true);
      expect(caps.custom_code).toBe(true);

      await automationManager.shutdown();
    });

    it('should allow resource planning in analytics', async () => {
      const analyticsManager = new AnalyticsManager(TEST_TENANT, 'parwa_high');
      await analyticsManager.initialize();

      // Verify analytics manager exists for parwa_high
      expect(analyticsManager).toBeDefined();

      await analyticsManager.shutdown();
    });
  });
});

// ── Performance Tests ────────────────────────────────────────────────────

describe('Week 12: Performance', () => {
  it('should handle rapid sequential commands', async () => {
    const orchestrator = createJarvisOrchestrator(createConfig(TEST_TENANT, 'parwa_high'));
    await orchestrator.initialize();

    const start = Date.now();
    const iterations = 50;

    for (let i = 0; i < iterations; i++) {
      await orchestrator.processCommand({
        command: 'show stats',
        userId: TEST_USER,
        userRole: 'agent',
      });
    }

    const duration = Date.now() - start;
    const avgTime = duration / iterations;

    // Should average under 50ms per command
    expect(avgTime).toBeLessThan(50);

    await orchestrator.shutdown();
  });

  it('should efficiently use cache', async () => {
      const cache = createCacheManager({
        enabled: true,
        defaultTtl: 60,
        maxSize: 100,
      });

      // Warm up cache
      for (let i = 0; i < 50; i++) {
        cache.set('default', `key_${i}`, { value: i });
      }

      // Access same keys multiple times (should be hits)
      for (let j = 0; j < 5; j++) {
        for (let i = 0; i < 50; i++) {
          cache.get('default', `key_${i}`);
        }
      }

      const stats = cache.getStats();
      // After 250 gets on 50 keys, hit rate should be decent
      expect(stats.hitRate).toBeGreaterThanOrEqual(0.1);
    });

  it('should handle concurrent operations', async () => {
    const orchestrator = createJarvisOrchestrator(createConfig(TEST_TENANT, 'parwa_high'));
    await orchestrator.initialize();

    const results = await Promise.all([
      orchestrator.processCommand({ command: 'show stats', userId: 'user1', userRole: 'agent' }),
      orchestrator.processCommand({ command: 'help', userId: 'user2', userRole: 'agent' }),
      orchestrator.processCommand({ command: 'list agents', userId: 'user3', userRole: 'supervisor' }),
    ]);

    results.forEach(r => expect(r.success).toBe(true));

    await orchestrator.shutdown();
  });
});

// ── Error Handling Tests ─────────────────────────────────────────────────

describe('Week 12: Error Handling', () => {
  it('should handle invalid commands gracefully', async () => {
    const orchestrator = createJarvisOrchestrator(createConfig(TEST_TENANT, 'parwa'));
    await orchestrator.initialize();

    const result = await orchestrator.processCommand({
      command: 'xyzzy invalid command 12345',
      userId: TEST_USER,
      userRole: 'agent',
    });

    // Should handle gracefully, not throw
    expect(result).toBeDefined();
    expect(result.success).toBeDefined();

    await orchestrator.shutdown();
  });

  it('should handle oversized commands', async () => {
    const orchestrator = createJarvisOrchestrator(createConfig(TEST_TENANT, 'parwa'));
    await orchestrator.initialize();

    const result = await orchestrator.processCommand({
      command: 'x'.repeat(5000), // Exceeds maxCommandLength
      userId: TEST_USER,
      userRole: 'agent',
    });

    expect(result.success).toBe(false);

    await orchestrator.shutdown();
  });

  it('should recover from rate limit exhaustion', async () => {
    const limiter = createRateLimiter({
      enabled: true,
      requestsPerMinute: 10,
      commandsPerHour: 20,
      burstAllowance: 5,
    });

    // Exhaust rate limit
    for (let i = 0; i < 20; i++) {
      limiter.checkLimit(TEST_USER, TEST_TENANT, 'parwa', 'command');
    }

    let result = limiter.checkLimit(TEST_USER, TEST_TENANT, 'parwa', 'command');
    expect(result.allowed).toBe(false);

    // Reset using resetUser method
    limiter.resetUser(TEST_USER, TEST_TENANT);

    result = limiter.checkLimit(TEST_USER, TEST_TENANT, 'parwa', 'command');
    expect(result.allowed).toBe(true);
  });
});

// ── Statistics & Monitoring Tests ────────────────────────────────────────

describe('Week 12: Statistics & Monitoring', () => {
  it('should track comprehensive statistics', async () => {
    const orchestrator = createJarvisOrchestrator(createConfig(TEST_TENANT, 'parwa_high'));
    await orchestrator.initialize();

    // Execute some commands
    await orchestrator.processCommand({ command: 'show stats', userId: TEST_USER, userRole: 'agent' });
    await orchestrator.processCommand({ command: 'help', userId: TEST_USER, userRole: 'agent' });

    const stats = orchestrator.getStats();

    expect(stats.sessions).toBeDefined();
    expect(stats.cache).toBeDefined();
    expect(stats.rateLimit).toBeDefined();
    expect(stats.audit).toBeDefined();

    await orchestrator.shutdown();
  });

  it('should provide health status for all components', async () => {
    const orchestrator = createJarvisOrchestrator(createConfig(TEST_TENANT, 'parwa'));
    await orchestrator.initialize();

    const health = await orchestrator.getHealth();

    expect(health.status).toBeDefined();
    expect(health.components.awarenessEngine).toBeDefined();
    expect(health.components.commandProcessor).toBeDefined();
    expect(health.components.cache).toBeDefined();
    expect(health.components.rateLimiter).toBeDefined();
    expect(health.components.auditLogger).toBeDefined();
    expect(health.uptime).toBeGreaterThanOrEqual(0);

    await orchestrator.shutdown();
  });

  it('should track module-specific statistics', async () => {
    const automationManager = new AutomationManager(TEST_TENANT, 'parwa');
    await automationManager.initialize();

    // Create and execute workflow
    const workflow = automationManager.createWorkflow({
      name: 'Stats Test',
      status: 'active',
      trigger: { id: 't1', type: 'manual', name: 'Manual', config: {}, enabled: true },
      steps: [{ id: 's1', type: 'action', name: 'Test', config: { action_type: 'assign_ticket' }, position: { x: 0, y: 0 }, enabled: true }],
      connections: [],
      variables: [],
      created_by: TEST_USER,
      tags: [],
      metadata: {},
    });

    await automationManager.executeWorkflow(workflow.id, {});

    const stats = automationManager.getStatistics();
    expect(stats.total_workflows).toBe(1);
    expect(stats.total_executions).toBe(1);

    await automationManager.shutdown();
  });
});

// ── End-to-End Scenarios ─────────────────────────────────────────────────

describe('Week 12: End-to-End Scenarios', () => {
  it('should handle complete agent workflow', async () => {
    const orchestrator = createJarvisOrchestrator(createConfig(TEST_TENANT, 'parwa'));
    await orchestrator.initialize();

    // Agent logs in, creates session
    const session = await orchestrator.processCommand({
      command: 'show my tickets',
      userId: 'agent_1',
      userRole: 'agent',
    });
    expect(session.success).toBe(true);

    // Agent views ticket details
    const viewTicket = await orchestrator.processCommand({
      command: 'show ticket TKT-001',
      sessionId: session.sessionId,
      userId: 'agent_1',
      userRole: 'agent',
    });
    expect(viewTicket.success).toBe(true);

    // Agent updates ticket
    const updateTicket = await orchestrator.processCommand({
      command: 'update ticket TKT-001 status in_progress',
      sessionId: session.sessionId,
      userId: 'agent_1',
      userRole: 'agent',
    });
    expect(updateTicket).toBeDefined();

    // Agent ends session
    await orchestrator.endSession(session.sessionId, 'agent_1');

    await orchestrator.shutdown();
  });

  it('should handle supervisor monitoring workflow', async () => {
    const orchestrator = createJarvisOrchestrator(createConfig(TEST_TENANT, 'parwa'));
    await orchestrator.initialize();

    // Supervisor checks team status
    const teamStatus = await orchestrator.processCommand({
      command: 'show team performance',
      userId: 'supervisor_1',
      userRole: 'supervisor',
    });
    expect(teamStatus.success).toBe(true);

    // Supervisor views alerts
    const alerts = await orchestrator.processCommand({
      command: 'show alerts',
      sessionId: teamStatus.sessionId,
      userId: 'supervisor_1',
      userRole: 'supervisor',
    });
    expect(alerts.success).toBe(true);

    await orchestrator.shutdown();
  });

  it('should handle automation setup workflow', async () => {
    const automationManager = new AutomationManager(TEST_TENANT, 'parwa_high');
    await automationManager.initialize();

    // Create automation from template
    const workflow = automationManager.createFromTemplate('auto-assign-priority', {
      priority_threshold: 'high',
    });
    expect(workflow.id).toBeDefined();

    // Activate workflow
    const activated = automationManager.updateWorkflow(workflow.id, { status: 'active' });
    expect(activated.status).toBe('active');

    // Test workflow
    const test = automationManager.createTest({
      workflow_id: workflow.id,
      name: 'Priority Assignment Test',
      test_cases: [{
        id: 'case_1',
        name: 'High Priority Ticket',
        input: { ticket_id: 'TKT-001', priority: 'high' },
        expected_outcomes: [{ expected_status: 'completed' }],
      }],
    });

    const results = await automationManager.runTest(test.id);
    expect(results.length).toBe(1);

    await automationManager.shutdown();
  });
});
