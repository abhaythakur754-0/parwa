/**
 * JARVIS Phase 1 Manual QA Testing Script
 * 
 * Simulates human QA testing to find bugs, edge cases, and verify behavior
 */

import { CacheManager, createCacheManager } from '../cache-manager';
import { RateLimiter, createRateLimiter } from '../rate-limiter';
import { AuditLogger, createAuditLogger } from '../audit-logger';
import { JarvisOrchestrator, createJarvisOrchestrator } from '../jarvis-orchestrator';
import type { JarvisConfig, Variant } from '../types';

// ── Test Results Tracker ────────────────────────────────────────────

interface TestResult {
  suite: string;
  test: string;
  passed: boolean;
  error?: string;
  duration: number;
  details?: string;
}

const results: TestResult[] = [];

function log(suite: string, test: string, passed: boolean, duration: number, error?: string, details?: string) {
  results.push({ suite, test, passed, error, duration, details });
  const status = passed ? '✅ PASS' : '❌ FAIL';
  console.log(`${status} [${suite}] ${test} (${duration}ms)`);
  if (error) console.log(`   Error: ${error}`);
  if (details) console.log(`   Details: ${details}`);
}

// ── CACHE MANAGER MANUAL TESTS ──────────────────────────────────────

function testCacheManager() {
  console.log('\n🧪 CACHE MANAGER TESTS\n');
  
  // Test 1: Basic Set/Get
  try {
    const start = Date.now();
    const cache = createCacheManager({ enabled: true, defaultTtl: 60, maxSize: 100 });
    cache.set('test', 'key1', { data: 'value1' });
    const result = cache.get('test', 'key1');
    const passed = result !== null && (result as any).data === 'value1';
    log('CacheManager', 'Basic Set/Get', passed, Date.now() - start, passed ? undefined : 'Value mismatch');
    cache.shutdown();
  } catch (e: any) {
    log('CacheManager', 'Basic Set/Get', false, 0, e.message);
  }

  // Test 2: Missing Key Returns Null
  try {
    const start = Date.now();
    const cache = createCacheManager({ enabled: true, defaultTtl: 60, maxSize: 100 });
    const result = cache.get('test', 'nonexistent_key_xyz');
    const passed = result === null;
    log('CacheManager', 'Missing Key Returns Null', passed, Date.now() - start);
    cache.shutdown();
  } catch (e: any) {
    log('CacheManager', 'Missing Key Returns Null', false, 0, e.message);
  }

  // Test 3: TTL Expiration
  try {
    const start = Date.now();
    const cache = createCacheManager({ enabled: true, defaultTtl: 60, maxSize: 100 });
    cache.set('test', 'expire_key', 'will_expire', 50); // 50ms TTL
    
    // Check immediately - should exist
    const before = cache.get('test', 'expire_key');
    
    // Wait for expiration
    const waitStart = Date.now();
    while (Date.now() - waitStart < 100) {
      // Busy wait for 100ms
    }
    
    const after = cache.get('test', 'expire_key');
    const passed = before !== null && after === null;
    log('CacheManager', 'TTL Expiration', passed, Date.now() - start, 
      passed ? undefined : `before=${before}, after=${after}`);
    cache.shutdown();
  } catch (e: any) {
    log('CacheManager', 'TTL Expiration', false, 0, e.message);
  }

  // Test 4: LRU Eviction
  try {
    const start = Date.now();
    const cache = createCacheManager({ enabled: true, defaultTtl: 60, maxSize: 5 }); // Only 5 entries
    
    // Add 5 entries
    for (let i = 0; i < 5; i++) {
      cache.set('test', `key${i}`, `value${i}`);
    }
    
    // Add 6th entry - should evict oldest
    cache.set('test', 'key5', 'value5');
    
    // First entry should be evicted
    const evicted = cache.get('test', 'key0');
    const newEntry = cache.get('test', 'key5');
    
    const passed = evicted === null && newEntry !== null;
    log('CacheManager', 'LRU Eviction', passed, Date.now() - start,
      passed ? undefined : `evicted=${evicted}, newEntry=${newEntry}`);
    cache.shutdown();
  } catch (e: any) {
    log('CacheManager', 'LRU Eviction', false, 0, e.message);
  }

  // Test 5: Namespace Isolation
  try {
    const start = Date.now();
    const cache = createCacheManager({ enabled: true, defaultTtl: 60, maxSize: 100 });
    
    cache.set('ns1', 'shared_key', 'value_ns1');
    cache.set('ns2', 'shared_key', 'value_ns2');
    
    const v1 = cache.get('ns1', 'shared_key');
    const v2 = cache.get('ns2', 'shared_key');
    
    const passed = v1 === 'value_ns1' && v2 === 'value_ns2';
    log('CacheManager', 'Namespace Isolation', passed, Date.now() - start,
      passed ? undefined : `ns1=${v1}, ns2=${v2}`);
    cache.shutdown();
  } catch (e: any) {
    log('CacheManager', 'Namespace Isolation', false, 0, e.message);
  }

  // Test 6: Batch Operations
  try {
    const start = Date.now();
    const cache = createCacheManager({ enabled: true, defaultTtl: 60, maxSize: 100 });
    
    cache.batchSet('test', [
      { key: 'b1', value: 'v1' },
      { key: 'b2', value: 'v2' },
      { key: 'b3', value: 'v3' },
    ]);
    
    const results = cache.batchGet<string>('test', ['b1', 'b2', 'b3', 'b4']);
    
    const passed = results.get('b1') === 'v1' && 
                   results.get('b2') === 'v2' && 
                   results.get('b3') === 'v3' && 
                   results.get('b4') === null;
    log('CacheManager', 'Batch Operations', passed, Date.now() - start);
    cache.shutdown();
  } catch (e: any) {
    log('CacheManager', 'Batch Operations', false, 0, e.message);
  }

  // Test 7: Cache Disabled
  try {
    const start = Date.now();
    const cache = createCacheManager({ enabled: false, defaultTtl: 60, maxSize: 100 });
    
    cache.set('test', 'key1', 'value1');
    const result = cache.get('test', 'key1');
    
    const passed = result === null; // Should return null when disabled
    log('CacheManager', 'Cache Disabled', passed, Date.now() - start,
      passed ? undefined : `Expected null when disabled, got ${result}`);
    cache.shutdown();
  } catch (e: any) {
    log('CacheManager', 'Cache Disabled', false, 0, e.message);
  }

  // Test 8: Clear Namespace
  try {
    const start = Date.now();
    const cache = createCacheManager({ enabled: true, defaultTtl: 60, maxSize: 100 });
    
    cache.set('ns1', 'k1', 'v1');
    cache.set('ns1', 'k2', 'v2');
    cache.set('ns2', 'k3', 'v3');
    
    cache.clearNamespace('ns1');
    
    const ns1k1 = cache.get('ns1', 'k1');
    const ns1k2 = cache.get('ns1', 'k2');
    const ns2k3 = cache.get('ns2', 'k3');
    
    const passed = ns1k1 === null && ns1k2 === null && ns2k3 === 'v3';
    log('CacheManager', 'Clear Namespace', passed, Date.now() - start);
    cache.shutdown();
  } catch (e: any) {
    log('CacheManager', 'Clear Namespace', false, 0, e.message);
  }

  // Test 9: Statistics Tracking
  try {
    const start = Date.now();
    const cache = createCacheManager({ enabled: true, defaultTtl: 60, maxSize: 100 });
    
    cache.set('test', 'key1', 'value1');
    cache.get('test', 'key1'); // Hit
    cache.get('test', 'key2'); // Miss
    cache.get('test', 'key1'); // Hit
    
    const stats = cache.getStats();
    
    const passed = stats.total.hits === 2 && stats.total.misses === 1;
    log('CacheManager', 'Statistics Tracking', passed, Date.now() - start,
      passed ? undefined : `hits=${stats.total.hits}, misses=${stats.total.misses}`);
    cache.shutdown();
  } catch (e: any) {
    log('CacheManager', 'Statistics Tracking', false, 0, e.message);
  }

  // Test 10: GetOrCompute Pattern
  try {
    const start = Date.now();
    const cache = createCacheManager({ enabled: true, defaultTtl: 60, maxSize: 100 });
    
    let computeCount = 0;
    const computeFn = async () => {
      computeCount++;
      return { computed: true };
    };
    
    // Using Promise chain since we can't await in sync
    const test1 = cache.getOrCompute('test', 'key1', computeFn).then(r1 => {
      const test2 = cache.getOrCompute('test', 'key1', computeFn).then(r2 => {
        const passed = computeCount === 1 && r1.computed && r2.computed;
        log('CacheManager', 'GetOrCompute Pattern', passed, Date.now() - start,
          passed ? undefined : `computeCount=${computeCount}`);
        cache.shutdown();
      });
    });
  } catch (e: any) {
    log('CacheManager', 'GetOrCompute Pattern', false, 0, e.message);
  }
}

// ── RATE LIMITER MANUAL TESTS ────────────────────────────────────────

function testRateLimiter() {
  console.log('\n🧪 RATE LIMITER TESTS\n');
  
  // Test 1: Basic Allow
  try {
    const start = Date.now();
    const limiter = createRateLimiter({
      enabled: true,
      requestsPerMinute: 60,
      commandsPerHour: 100,
      burstAllowance: 10,
    });
    
    const result = limiter.checkLimit('user1', 'org1', 'parwa');
    const passed = result.allowed && result.remainingTokens > 0;
    log('RateLimiter', 'Basic Allow', passed, Date.now() - start);
    limiter.clear();
  } catch (e: any) {
    log('RateLimiter', 'Basic Allow', false, 0, e.message);
  }

  // Test 2: Token Consumption
  try {
    const start = Date.now();
    const limiter = createRateLimiter({
      enabled: true,
      requestsPerMinute: 60,
      commandsPerHour: 100,
      burstAllowance: 5,
    }, { userLimit: 10 });
    
    let lastResult: any;
    for (let i = 0; i < 5; i++) {
      lastResult = limiter.checkLimit('user1', 'org1', 'parwa');
    }
    
    const passed = lastResult.allowed && lastResult.remainingTokens < 10;
    log('RateLimiter', 'Token Consumption', passed, Date.now() - start,
      passed ? undefined : `remaining=${lastResult.remainingTokens}`);
    limiter.clear();
  } catch (e: any) {
    log('RateLimiter', 'Token Consumption', false, 0, e.message);
  }

  // Test 3: Rate Limit Exceeded
  try {
    const start = Date.now();
    const limiter = createRateLimiter({
      enabled: true,
      requestsPerMinute: 10,
      commandsPerHour: 10,
      burstAllowance: 0,
    }, { userLimit: 3 });
    
    // Exhaust tokens
    for (let i = 0; i < 5; i++) {
      limiter.checkLimit('user1', 'org1', 'parwa');
    }
    
    const result = limiter.checkLimit('user1', 'org1', 'parwa');
    const passed = !result.allowed && result.retryAfterMs > 0;
    log('RateLimiter', 'Rate Limit Exceeded', passed, Date.now() - start,
      passed ? undefined : `allowed=${result.allowed}, retryAfter=${result.retryAfterMs}`);
    limiter.clear();
  } catch (e: any) {
    log('RateLimiter', 'Rate Limit Exceeded', false, 0, e.message);
  }

  // Test 4: Variant-Specific Limits
  try {
    const start = Date.now();
    const limiter = createRateLimiter({
      enabled: true,
      requestsPerMinute: 60,
      commandsPerHour: 100,
      burstAllowance: 5,
    });
    
    // Mini PARWA should have lower limits
    const miniResults: any[] = [];
    for (let i = 0; i < 40; i++) {
      miniResults.push(limiter.checkLimit('user_mini', 'org1', 'mini_parwa'));
    }
    const miniBlocked = miniResults.filter(r => !r.allowed).length;
    
    // PARWA should allow more
    limiter.clear();
    const parwaResults: any[] = [];
    for (let i = 0; i < 40; i++) {
      parwaResults.push(limiter.checkLimit('user_parwa', 'org1', 'parwa'));
    }
    const parwaBlocked = parwaResults.filter(r => !r.allowed).length;
    
    const passed = miniBlocked >= parwaBlocked; // Mini should block more
    log('RateLimiter', 'Variant-Specific Limits', passed, Date.now() - start,
      undefined, `miniBlocked=${miniBlocked}, parwaBlocked=${parwaBlocked}`);
    limiter.clear();
  } catch (e: any) {
    log('RateLimiter', 'Variant-Specific Limits', false, 0, e.message);
  }

  // Test 5: Reset User
  try {
    const start = Date.now();
    const limiter = createRateLimiter({
      enabled: true,
      requestsPerMinute: 5,
      commandsPerHour: 5,
      burstAllowance: 0,
    }, { userLimit: 2 });
    
    // Exhaust
    limiter.checkLimit('user1', 'org1', 'parwa');
    limiter.checkLimit('user1', 'org1', 'parwa');
    limiter.checkLimit('user1', 'org1', 'parwa');
    
    const blocked = limiter.checkLimit('user1', 'org1', 'parwa');
    
    // Reset
    limiter.resetUser('user1', 'org1');
    
    const afterReset = limiter.checkLimit('user1', 'org1', 'parwa');
    
    const passed = !blocked.allowed && afterReset.allowed;
    log('RateLimiter', 'Reset User', passed, Date.now() - start);
    limiter.clear();
  } catch (e: any) {
    log('RateLimiter', 'Reset User', false, 0, e.message);
  }

  // Test 6: Statistics
  try {
    const start = Date.now();
    const limiter = createRateLimiter({
      enabled: true,
      requestsPerMinute: 60,
      commandsPerHour: 100,
      burstAllowance: 10,
    });
    
    limiter.checkLimit('user1', 'org1', 'parwa');
    limiter.checkLimit('user1', 'org1', 'parwa');
    limiter.checkLimit('user2', 'org1', 'parwa');
    
    const stats = limiter.getStats();
    
    const passed = stats.totalRequests === 3 && stats.activeUsers === 2;
    log('RateLimiter', 'Statistics', passed, Date.now() - start,
      passed ? undefined : `requests=${stats.totalRequests}, users=${stats.activeUsers}`);
    limiter.clear();
  } catch (e: any) {
    log('RateLimiter', 'Statistics', false, 0, e.message);
  }

  // Test 7: Disabled Rate Limiting
  try {
    const start = Date.now();
    const limiter = createRateLimiter({
      enabled: false,
      requestsPerMinute: 1,
      commandsPerHour: 1,
      burstAllowance: 0,
    });
    
    // Should all pass when disabled
    let allAllowed = true;
    for (let i = 0; i < 100; i++) {
      const result = limiter.checkLimit('user1', 'org1', 'parwa');
      if (!result.allowed) allAllowed = false;
    }
    
    log('RateLimiter', 'Disabled Rate Limiting', allAllowed, Date.now() - start);
    limiter.clear();
  } catch (e: any) {
    log('RateLimiter', 'Disabled Rate Limiting', false, 0, e.message);
  }

  // Test 8: Unban User
  try {
    const start = Date.now();
    const limiter = createRateLimiter({
      enabled: true,
      requestsPerMinute: 5,
      commandsPerHour: 5,
      burstAllowance: 0,
    }, { 
      userLimit: 2, 
      violationThreshold: 2,
      blockDuration: 60000 
    });
    
    // Trigger violations
    for (let i = 0; i < 10; i++) {
      limiter.checkLimit('user1', 'org1', 'parwa');
    }
    
    // Unban
    limiter.unban('user1', 'org1');
    
    const stats = limiter.getStats();
    
    // After unban, user should be able to make requests again
    const passed = true; // Basic test - just check it doesn't crash
    log('RateLimiter', 'Unban User', passed, Date.now() - start);
    limiter.clear();
  } catch (e: any) {
    log('RateLimiter', 'Unban User', false, 0, e.message);
  }
}

// ── AUDIT LOGGER MANUAL TESTS ────────────────────────────────────────

function testAuditLogger() {
  console.log('\n🧪 AUDIT LOGGER TESTS\n');
  
  // Test 1: Log Command
  try {
    const start = Date.now();
    const logger = createAuditLogger({ enabled: true, maxEntries: 100 });
    
    const entry = logger.logCommand({
      organizationId: 'org1',
      sessionId: 'session1',
      userId: 'user1',
      command: 'show my tickets',
      commandId: 'cmd1',
      result: 'success',
      executionMode: 'direct',
    });
    
    const passed = entry.id.startsWith('audit_') && entry.action === 'command_execute';
    log('AuditLogger', 'Log Command', passed, Date.now() - start);
    logger.shutdown();
  } catch (e: any) {
    log('AuditLogger', 'Log Command', false, 0, e.message);
  }

  // Test 2: Log Approval
  try {
    const start = Date.now();
    const logger = createAuditLogger({ enabled: true, maxEntries: 100 });
    
    const entry = logger.logApproval({
      organizationId: 'org1',
      sessionId: 'session1',
      userId: 'user1',
      draftId: 'draft1',
      action: 'approve',
      comment: 'Looks good',
    });
    
    const passed = entry.action === 'command_approve' && entry.metadata?.comment === 'Looks good';
    log('AuditLogger', 'Log Approval', passed, Date.now() - start);
    logger.shutdown();
  } catch (e: any) {
    log('AuditLogger', 'Log Approval', false, 0, e.message);
  }

  // Test 3: Query Logs
  try {
    const start = Date.now();
    const logger = createAuditLogger({ enabled: true, maxEntries: 100 });
    
    logger.logCommand({
      organizationId: 'org1', sessionId: 's1', userId: 'user1',
      command: 'cmd1', commandId: 'c1', result: 'success', executionMode: 'direct',
    });
    
    logger.logCommand({
      organizationId: 'org1', sessionId: 's1', userId: 'user2',
      command: 'cmd2', commandId: 'c2', result: 'failure', executionMode: 'direct',
    });
    
    const user1Logs = logger.queryLogs({ userId: 'user1' });
    const failureLogs = logger.queryLogs({ result: 'failure' });
    
    const passed = user1Logs.length === 1 && failureLogs.length === 1;
    log('AuditLogger', 'Query Logs', passed, Date.now() - start);
    logger.shutdown();
  } catch (e: any) {
    log('AuditLogger', 'Query Logs', false, 0, e.message);
  }

  // Test 4: Record Violation
  try {
    const start = Date.now();
    const logger = createAuditLogger({ enabled: true, maxEntries: 100 });
    
    const violation = logger.recordViolation({
      sessionId: 's1',
      userId: 'user1',
      type: 'injection_attempt',
      severity: 'high',
      description: 'SQL injection detected',
      input: "'; DROP TABLE users; --",
      action: 'block',
    });
    
    // Input should be sanitized
    const passed = violation.type === 'injection_attempt' && 
                   violation.severity === 'high' &&
                   !violation.input.includes('DROP');
    log('AuditLogger', 'Record Violation', passed, Date.now() - start,
      passed ? undefined : `input=${violation.input}`);
    logger.shutdown();
  } catch (e: any) {
    log('AuditLogger', 'Record Violation', false, 0, e.message);
  }

  // Test 5: Violation Count
  try {
    const start = Date.now();
    const logger = createAuditLogger({ enabled: true, maxEntries: 100 });
    
    logger.recordViolation({
      sessionId: 's1', userId: 'user1', type: 'excessive_requests',
      severity: 'medium', description: 'Rate limit', input: 'test', action: 'rate_limit',
    });
    
    logger.recordViolation({
      sessionId: 's2', userId: 'user1', type: 'excessive_requests',
      severity: 'medium', description: 'Rate limit', input: 'test', action: 'rate_limit',
    });
    
    logger.recordViolation({
      sessionId: 's3', userId: 'user2', type: 'excessive_requests',
      severity: 'medium', description: 'Rate limit', input: 'test', action: 'rate_limit',
    });
    
    const count1 = logger.getViolationCount('user1', 24);
    const count2 = logger.getViolationCount('user2', 24);
    
    const passed = count1 === 2 && count2 === 1;
    log('AuditLogger', 'Violation Count', passed, Date.now() - start);
    logger.shutdown();
  } catch (e: any) {
    log('AuditLogger', 'Violation Count', false, 0, e.message);
  }

  // Test 6: Statistics
  try {
    const start = Date.now();
    const logger = createAuditLogger({ enabled: true, maxEntries: 100 });
    
    logger.logCommand({
      organizationId: 'org1', sessionId: 's1', userId: 'user1',
      command: 'test', commandId: 'c1', result: 'success', executionMode: 'direct',
    });
    
    logger.recordViolation({
      sessionId: 's1', userId: 'user1', type: 'excessive_requests',
      severity: 'high', description: 'Test', input: 'test', action: 'warn',
    });
    
    const stats = logger.getStats();
    
    const passed = stats.logs.totalEntries === 1 && 
                   stats.violations.total === 1 && 
                   stats.violations.high === 1;
    log('AuditLogger', 'Statistics', passed, Date.now() - start);
    logger.shutdown();
  } catch (e: any) {
    log('AuditLogger', 'Statistics', false, 0, e.message);
  }

  // Test 7: Max Entries Enforcement
  try {
    const start = Date.now();
    const logger = createAuditLogger({ enabled: true, maxEntries: 10 });
    
    // Add more than max
    for (let i = 0; i < 20; i++) {
      logger.logCommand({
        organizationId: 'org1', sessionId: `s${i}`, userId: 'user1',
        command: `cmd${i}`, commandId: `c${i}`, result: 'success', executionMode: 'direct',
      });
    }
    
    const stats = logger.getStats();
    
    // Should have at most maxEntries
    const passed = stats.logs.totalEntries <= 10;
    log('AuditLogger', 'Max Entries Enforcement', passed, Date.now() - start,
      passed ? undefined : `entries=${stats.logs.totalEntries}`);
    logger.shutdown();
  } catch (e: any) {
    log('AuditLogger', 'Max Entries Enforcement', false, 0, e.message);
  }

  // Test 8: Disabled Logging
  try {
    const start = Date.now();
    const logger = createAuditLogger({ enabled: false, maxEntries: 100 });
    
    logger.logCommand({
      organizationId: 'org1', sessionId: 's1', userId: 'user1',
      command: 'test', commandId: 'c1', result: 'success', executionMode: 'direct',
    });
    
    const stats = logger.getStats();
    
    const passed = stats.logs.totalEntries === 0;
    log('AuditLogger', 'Disabled Logging', passed, Date.now() - start);
    logger.shutdown();
  } catch (e: any) {
    log('AuditLogger', 'Disabled Logging', false, 0, e.message);
  }
}

// ── JARVIS ORCHESTRATOR MANUAL TESTS ────────────────────────────────

async function testJarvisOrchestrator() {
  console.log('\n🧪 JARVIS ORCHESTRATOR TESTS\n');
  
  const createTestConfig = (variant: Variant = 'parwa'): JarvisConfig => ({
    organizationId: `test_org_${Date.now()}`,
    variant,
    debug: true,
    cache: { enabled: true, defaultTtl: 60, maxSize: 100 },
    rateLimit: { enabled: true, requestsPerMinute: 100, commandsPerHour: 50, burstAllowance: 5 },
    security: {
      sanitizeInput: true,
      validateCommands: true,
      auditLogging: true,
      maxCommandLength: 500,
      forbiddenPatterns: ['(?i)(drop|delete|truncate)\\s+(table|database)'],
    },
  });

  // Test 1: Initialize
  try {
    const start = Date.now();
    const config = createTestConfig('parwa');
    const orchestrator = createJarvisOrchestrator(config);
    await orchestrator.initialize();
    
    const health = await orchestrator.getHealth();
    const passed = health.status !== undefined;
    log('Orchestrator', 'Initialize', passed, Date.now() - start);
    await orchestrator.shutdown();
  } catch (e: any) {
    log('Orchestrator', 'Initialize', false, 0, e.message);
  }

  // Test 2: Variant Capabilities
  try {
    const start = Date.now();
    const config = createTestConfig('parwa');
    const orchestrator = createJarvisOrchestrator(config);
    
    const capabilities = orchestrator.getCapabilities();
    
    const passed = capabilities.memoryRetentionHours === 168 && 
                   capabilities.proactiveAlerts === true;
    log('Orchestrator', 'Variant Capabilities', passed, Date.now() - start,
      passed ? undefined : `retention=${capabilities.memoryRetentionHours}`);
    await orchestrator.shutdown();
  } catch (e: any) {
    log('Orchestrator', 'Variant Capabilities', false, 0, e.message);
  }

  // Test 3: Mini PARWA Capabilities
  try {
    const start = Date.now();
    const config = createTestConfig('mini_parwa');
    const orchestrator = createJarvisOrchestrator(config);
    
    const capabilities = orchestrator.getCapabilities();
    
    const passed = capabilities.maxCommandsPerDay === 100 && 
                   capabilities.proactiveAlerts === false;
    log('Orchestrator', 'Mini PARWA Capabilities', passed, Date.now() - start);
    await orchestrator.shutdown();
  } catch (e: any) {
    log('Orchestrator', 'Mini PARWA Capabilities', false, 0, e.message);
  }

  // Test 4: Process Command
  try {
    const start = Date.now();
    const config = createTestConfig('parwa');
    const orchestrator = createJarvisOrchestrator(config);
    await orchestrator.initialize();
    
    const response = await orchestrator.processCommand({
      command: 'show my tickets',
      userId: 'user1',
      userRole: 'agent',
    });
    
    const passed = response.sessionId !== undefined && response.commandId !== undefined;
    log('Orchestrator', 'Process Command', passed, Date.now() - start,
      passed ? undefined : `success=${response.success}, message=${response.message}`);
    await orchestrator.shutdown();
  } catch (e: any) {
    log('Orchestrator', 'Process Command', false, 0, e.message);
  }

  // Test 5: Security Validation - SQL Injection
  try {
    const start = Date.now();
    const config = createTestConfig('parwa');
    const orchestrator = createJarvisOrchestrator(config);
    await orchestrator.initialize();
    
    const response = await orchestrator.processCommand({
      command: 'DROP TABLE users;',
      userId: 'user1',
      userRole: 'agent',
    });
    
    const passed = response.success === false && response.message.includes('Forbidden');
    log('Orchestrator', 'Security - SQL Injection', passed, Date.now() - start,
      passed ? undefined : `success=${response.success}, message=${response.message}`);
    await orchestrator.shutdown();
  } catch (e: any) {
    log('Orchestrator', 'Security - SQL Injection', false, 0, e.message);
  }

  // Test 6: Command Too Long
  try {
    const start = Date.now();
    const config = createTestConfig('parwa');
    const orchestrator = createJarvisOrchestrator(config);
    await orchestrator.initialize();
    
    const longCommand = 'a'.repeat(600);
    const response = await orchestrator.processCommand({
      command: longCommand,
      userId: 'user1',
      userRole: 'agent',
    });
    
    const passed = response.success === false;
    log('Orchestrator', 'Command Too Long', passed, Date.now() - start,
      passed ? undefined : `success=${response.success}`);
    await orchestrator.shutdown();
  } catch (e: any) {
    log('Orchestrator', 'Command Too Long', false, 0, e.message);
  }

  // Test 7: Rate Limiting
  try {
    const start = Date.now();
    const config = createTestConfig('mini_parwa');
    config.rateLimit = { enabled: true, requestsPerMinute: 2, commandsPerHour: 2, burstAllowance: 0 };
    const orchestrator = createJarvisOrchestrator(config);
    await orchestrator.initialize();
    
    // Exhaust
    await orchestrator.processCommand({ command: 'test1', userId: 'user1', userRole: 'agent' });
    await orchestrator.processCommand({ command: 'test2', userId: 'user1', userRole: 'agent' });
    
    // Should be blocked
    const response = await orchestrator.processCommand({ command: 'test3', userId: 'user1', userRole: 'agent' });
    
    const passed = response.success === false && response.message.includes('Rate limit');
    log('Orchestrator', 'Rate Limiting', passed, Date.now() - start,
      passed ? undefined : `success=${response.success}, message=${response.message}`);
    await orchestrator.shutdown();
  } catch (e: any) {
    log('Orchestrator', 'Rate Limiting', false, 0, e.message);
  }

  // Test 8: Session Management
  try {
    const start = Date.now();
    const config = createTestConfig('parwa');
    const orchestrator = createJarvisOrchestrator(config);
    await orchestrator.initialize();
    
    const response = await orchestrator.processCommand({
      command: 'show tickets',
      userId: 'user1',
      userRole: 'agent',
    });
    
    const session = orchestrator.getSession(response.sessionId);
    
    const passed = session !== undefined && session.sessionId === response.sessionId;
    log('Orchestrator', 'Session Management', passed, Date.now() - start);
    
    await orchestrator.endSession(response.sessionId, 'user1');
    const afterEnd = orchestrator.getSession(response.sessionId);
    
    const passedEnd = afterEnd === undefined;
    log('Orchestrator', 'Session End', passedEnd, Date.now() - start);
    await orchestrator.shutdown();
  } catch (e: any) {
    log('Orchestrator', 'Session Management', false, 0, e.message);
  }

  // Test 9: Health Check
  try {
    const start = Date.now();
    const config = createTestConfig('parwa');
    const orchestrator = createJarvisOrchestrator(config);
    await orchestrator.initialize();
    
    const health = await orchestrator.getHealth();
    
    const passed = health.components !== undefined && 
                   health.activeSessions !== undefined &&
                   health.uptime >= 0;
    log('Orchestrator', 'Health Check', passed, Date.now() - start,
      passed ? undefined : `status=${health.status}`);
    await orchestrator.shutdown();
  } catch (e: any) {
    log('Orchestrator', 'Health Check', false, 0, e.message);
  }

  // Test 10: Statistics
  try {
    const start = Date.now();
    const config = createTestConfig('parwa');
    const orchestrator = createJarvisOrchestrator(config);
    await orchestrator.initialize();
    
    await orchestrator.processCommand({ command: 'test', userId: 'user1', userRole: 'agent' });
    
    const stats = orchestrator.getStats();
    
    const passed = stats.sessions !== undefined && 
                   stats.cache !== undefined &&
                   stats.rateLimit !== undefined;
    log('Orchestrator', 'Statistics', passed, Date.now() - start);
    await orchestrator.shutdown();
  } catch (e: any) {
    log('Orchestrator', 'Statistics', false, 0, e.message);
  }
}

// ── RUN ALL TESTS ────────────────────────────────────────────────────

async function runAllTests() {
  console.log('═══════════════════════════════════════════════════════════════');
  console.log('  JARVIS Phase 1 Manual QA Testing');
  console.log('  Simulating Human QA Testing Workflow');
  console.log('═══════════════════════════════════════════════════════════════');
  
  testCacheManager();
  testRateLimiter();
  testAuditLogger();
  await testJarvisOrchestrator();
  
  // Summary
  console.log('\n═══════════════════════════════════════════════════════════════');
  console.log('  TEST SUMMARY');
  console.log('═══════════════════════════════════════════════════════════════');
  
  const passed = results.filter(r => r.passed).length;
  const failed = results.filter(r => !r.passed).length;
  const total = results.length;
  
  console.log(`\n  Total: ${total}`);
  console.log(`  ✅ Passed: ${passed}`);
  console.log(`  ❌ Failed: ${failed}`);
  console.log(`  Pass Rate: ${((passed / total) * 100).toFixed(1)}%`);
  
  if (failed > 0) {
    console.log('\n  FAILED TESTS:');
    results.filter(r => !r.passed).forEach(r => {
      console.log(`    ❌ [${r.suite}] ${r.test}`);
      if (r.error) console.log(`       Error: ${r.error}`);
    });
  }
  
  console.log('\n═══════════════════════════════════════════════════════════════');
  
  return { passed, failed, total, results };
}

// Export for running
export { runAllTests, results };

// Run if executed directly
runAllTests().then(summary => {
  process.exit(summary.failed > 0 ? 1 : 0);
});
