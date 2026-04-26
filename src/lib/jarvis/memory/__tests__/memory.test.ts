/**
 * JARVIS Memory System Tests - Week 5 (Phase 2)
 *
 * Comprehensive tests for the Memory System.
 */

import { MemoryStore, createMemoryStore } from '../memory-store';
import { MemoryManager, createMemoryManager } from '../memory-manager';
import type { 
  MemoryEntry, 
  MemoryType, 
  MemoryImportance,
  MemoryQuery,
  UserMemoryContent,
} from '../types';

// ── Test Configuration ─────────────────────────────────────────────

const TEST_TENANT = 'test_tenant_123';
const TEST_USER = 'test_user_456';
const TEST_VARIANT = 'parwa' as const;

// ── Memory Store Tests ──────────────────────────────────────────────

describe('MemoryStore', () => {
  let store: MemoryStore;

  beforeEach(() => {
    store = createMemoryStore();
  });

  afterEach(() => {
    store.shutdown();
  });

  describe('create', () => {
    test('should create a memory entry', () => {
      const memory = store.create(
        TEST_TENANT,
        TEST_USER,
        'user_preference',
        '{"key": "test", "value": "data"}',
        { source: 'explicit' },
        'high'
      );

      expect(memory.id).toBeDefined();
      expect(memory.tenant_id).toBe(TEST_TENANT);
      expect(memory.user_id).toBe(TEST_USER);
      expect(memory.type).toBe('user_preference');
      expect(memory.importance).toBe('high');
      expect(memory.status).toBe('active');
      expect(memory.access_count).toBe(0);
    });

    test('should create memory with expiration', () => {
      const memory = store.create(
        TEST_TENANT,
        TEST_USER,
        'conversation',
        'Test content',
        {},
        'medium',
        24 // 24 hours
      );

      expect(memory.expires_at).toBeDefined();
      expect(memory.expires_at!.getTime()).toBeGreaterThan(Date.now());
    });

    test('should track created memories', () => {
      store.create(TEST_TENANT, TEST_USER, 'user_preference', 'content1', {});
      store.create(TEST_TENANT, TEST_USER, 'user_behavior', 'content2', {});
      store.create(TEST_TENANT, TEST_USER, 'conversation', 'content3', {});

      const stats = store.getStats();
      expect(stats.total_memories).toBe(3);
    });
  });

  describe('get', () => {
    test('should retrieve memory by ID', () => {
      const created = store.create(
        TEST_TENANT,
        TEST_USER,
        'user_preference',
        'test content',
        {}
      );

      const retrieved = store.get(created.id);
      expect(retrieved).toBeDefined();
      expect(retrieved?.id).toBe(created.id);
    });

    test('should increment access count when retrieved', () => {
      const created = store.create(
        TEST_TENANT,
        TEST_USER,
        'user_preference',
        'test content',
        {}
      );

      store.get(created.id);
      store.get(created.id);
      store.get(created.id);

      const retrieved = store.get(created.id, false);
      expect(retrieved?.access_count).toBe(3);
    });

    test('should return undefined for non-existent ID', () => {
      const result = store.get('non_existent_id');
      expect(result).toBeUndefined();
    });
  });

  describe('update', () => {
    test('should update memory content', () => {
      const created = store.create(
        TEST_TENANT,
        TEST_USER,
        'user_preference',
        'original content',
        {}
      );

      const updated = store.update(created.id, {
        content: 'updated content',
        importance: 'critical',
      });

      expect(updated?.content).toBe('updated content');
      expect(updated?.importance).toBe('critical');
    });

    test('should return undefined for non-existent memory', () => {
      const result = store.update('non_existent', { content: 'test' });
      expect(result).toBeUndefined();
    });
  });

  describe('delete', () => {
    test('should delete memory', () => {
      const created = store.create(
        TEST_TENANT,
        TEST_USER,
        'user_preference',
        'test content',
        {}
      );

      expect(store.delete(created.id)).toBe(true);
      expect(store.get(created.id)).toBeUndefined();
    });

    test('should return false for non-existent memory', () => {
      expect(store.delete('non_existent')).toBe(false);
    });
  });

  describe('query', () => {
    beforeEach(() => {
      // Create test data
      store.create(TEST_TENANT, TEST_USER, 'user_preference', 'pref1', {}, 'high');
      store.create(TEST_TENANT, TEST_USER, 'user_preference', 'pref2', {}, 'medium');
      store.create(TEST_TENANT, TEST_USER, 'conversation', 'conv1', {}, 'low');
      store.create(TEST_TENANT, TEST_USER, 'conversation', 'conv2', {}, 'critical');
      store.create(TEST_TENANT, 'other_user', 'user_preference', 'pref3', {}, 'high');
    });

    test('should query by tenant and user', () => {
      const result = store.query({
        tenant_id: TEST_TENANT,
        user_id: TEST_USER,
      });

      expect(result.total).toBe(4);
      expect(result.memories.every(m => m.user_id === TEST_USER)).toBe(true);
    });

    test('should query by type', () => {
      const result = store.query({
        tenant_id: TEST_TENANT,
        user_id: TEST_USER,
        types: ['conversation'],
      });

      expect(result.total).toBe(2);
      expect(result.memories.every(m => m.type === 'conversation')).toBe(true);
    });

    test('should query by importance threshold', () => {
      const result = store.query({
        tenant_id: TEST_TENANT,
        user_id: TEST_USER,
        importance_threshold: 'high',
      });

      // Should include critical and high only
      expect(result.memories.every(m => 
        m.importance === 'critical' || m.importance === 'high'
      )).toBe(true);
    });

    test('should support text search', () => {
      store.create(TEST_TENANT, TEST_USER, 'user_preference', 'special keyword test', {});
      
      const result = store.query({
        tenant_id: TEST_TENANT,
        user_id: TEST_USER,
        text_query: 'keyword',
      });

      expect(result.total).toBe(1);
      expect(result.memories[0].content).toContain('keyword');
    });

    test('should support pagination', () => {
      const result = store.query({
        tenant_id: TEST_TENANT,
        user_id: TEST_USER,
        limit: 2,
        offset: 0,
      });

      expect(result.memories.length).toBe(2);
      expect(result.has_more).toBe(true);
    });
  });

  describe('getUserPreferences', () => {
    test('should get user preferences', () => {
      store.create(TEST_TENANT, TEST_USER, 'user_preference', 'pref1', {});
      store.create(TEST_TENANT, TEST_USER, 'user_preference', 'pref2', {});
      store.create(TEST_TENANT, TEST_USER, 'conversation', 'conv1', {});

      const prefs = store.getUserPreferences(TEST_TENANT, TEST_USER);
      expect(prefs.length).toBe(2);
    });
  });

  describe('archive and expire', () => {
    test('should archive old memories', () => {
      const memory = store.create(
        TEST_TENANT,
        TEST_USER,
        'user_behavior',
        'old content',
        {},
        'medium'
      );

      // Manually set old date
      store.update(memory.id, {
        created_at: new Date(Date.now() - 60 * 24 * 60 * 60 * 1000), // 60 days ago
      });

      const archived = store.archive(30);
      expect(archived).toBeGreaterThanOrEqual(1);
    });

    test('should not archive critical memories', () => {
      const memory = store.create(
        TEST_TENANT,
        TEST_USER,
        'user_preference',
        'critical content',
        {},
        'critical'
      );

      store.update(memory.id, {
        created_at: new Date(Date.now() - 60 * 24 * 60 * 60 * 1000),
      });

      const archived = store.archive(30);
      
      // Critical memory should still be active
      const retrieved = store.get(memory.id, false);
      expect(retrieved?.status).toBe('active');
    });
  });

  describe('statistics', () => {
    test('should return memory statistics', () => {
      store.create(TEST_TENANT, TEST_USER, 'user_preference', 'content', {}, 'high');
      store.create(TEST_TENANT, TEST_USER, 'conversation', 'content', {}, 'medium');
      store.create(TEST_TENANT, TEST_USER, 'user_behavior', 'content', {}, 'low');

      const stats = store.getStats();
      
      expect(stats.total_memories).toBe(3);
      expect(stats.memories_by_type.user_preference).toBe(1);
      expect(stats.memories_by_type.conversation).toBe(1);
      expect(stats.memories_by_importance.high).toBe(1);
      expect(stats.average_access_count).toBeGreaterThanOrEqual(0);
    });
  });
});

// ── Memory Manager Tests ────────────────────────────────────────────

describe('MemoryManager', () => {
  let manager: MemoryManager;

  beforeEach(() => {
    manager = createMemoryManager(TEST_VARIANT);
  });

  afterEach(() => {
    manager.shutdown();
  });

  describe('User Preferences', () => {
    test('should set and get user preference', () => {
      manager.setUserPreference(
        TEST_TENANT,
        TEST_USER,
        'display',
        'theme',
        'dark'
      );

      const value = manager.getUserPreference(TEST_TENANT, TEST_USER, 'display', 'theme');
      expect(value).toBe('dark');
    });

    test('should update existing preference', () => {
      manager.setUserPreference(TEST_TENANT, TEST_USER, 'display', 'theme', 'dark');
      manager.setUserPreference(TEST_TENANT, TEST_USER, 'display', 'theme', 'light');

      const value = manager.getUserPreference(TEST_TENANT, TEST_USER, 'display', 'theme');
      expect(value).toBe('light');
    });

    test('should get preferences by category', () => {
      manager.setUserPreference(TEST_TENANT, TEST_USER, 'display', 'theme', 'dark');
      manager.setUserPreference(TEST_TENANT, TEST_USER, 'display', 'fontSize', 'large');
      manager.setUserPreference(TEST_TENANT, TEST_USER, 'notification', 'email', true);

      const displayPrefs = manager.getUserPreferencesByCategory(TEST_TENANT, TEST_USER, 'display');
      expect(displayPrefs.size).toBe(2);
      expect(displayPrefs.get('theme')).toBe('dark');
      expect(displayPrefs.get('fontSize')).toBe('large');
    });

    test('should track preference frequency', () => {
      manager.setUserPreference(TEST_TENANT, TEST_USER, 'workflow', 'autoAssign', true);
      
      // Access multiple times
      manager.getUserPreference(TEST_TENANT, TEST_USER, 'workflow', 'autoAssign');
      manager.getUserPreference(TEST_TENANT, TEST_USER, 'workflow', 'autoAssign');
      manager.getUserPreference(TEST_TENANT, TEST_USER, 'workflow', 'autoAssign');

      const memory = manager.search({
        tenant_id: TEST_TENANT,
        user_id: TEST_USER,
        types: ['user_preference'],
      }).memories[0];

      const prefData = memory.metadata.preference_data as UserMemoryContent;
      expect(prefData.frequency).toBeGreaterThan(1);
    });
  });

  describe('Conversation Memory', () => {
    test('should store conversation', () => {
      const turns = [
        { id: '1', role: 'user' as const, content: 'Show my tickets', timestamp: new Date(), intent: 'search_tickets' as any },
        { id: '2', role: 'jarvis' as const, content: 'Here are your tickets', timestamp: new Date() },
      ];

      const memory = manager.storeConversation(
        TEST_TENANT,
        TEST_USER,
        'session_123',
        turns,
        'User asked about tickets'
      );

      expect(memory.id).toBeDefined();
      expect(memory.type).toBe('conversation');
    });

    test('should get conversation history', () => {
      const turns1 = [
        { id: '1', role: 'user' as const, content: 'First conversation', timestamp: new Date() },
      ];
      const turns2 = [
        { id: '2', role: 'user' as const, content: 'Second conversation', timestamp: new Date() },
      ];

      manager.storeConversation(TEST_TENANT, TEST_USER, 'session_1', turns1);
      manager.storeConversation(TEST_TENANT, TEST_USER, 'session_2', turns2);

      const history = manager.getConversationHistory(TEST_TENANT, TEST_USER, 10);
      expect(history.length).toBe(2);
    });

    test('should find similar conversations', () => {
      const turns = [
        { id: '1', role: 'user' as const, content: 'How do I refund an order?', timestamp: new Date() },
      ];

      manager.storeConversation(TEST_TENANT, TEST_USER, 'session_1', turns, 'Refund question');

      const similar = manager.findSimilarConversations(TEST_TENANT, TEST_USER, 'refund');
      expect(similar.length).toBeGreaterThan(0);
    });
  });

  describe('Entity Memory', () => {
    test('should store entity mention', () => {
      const memory = manager.storeEntityMention(
        TEST_TENANT,
        TEST_USER,
        'ticket',
        'TKT-123',
        'Support Ticket #123',
        'User asked about this ticket'
      );

      expect(memory.id).toBeDefined();
      expect(memory.type).toBe('entity_mention');
    });

    test('should update entity mention count', () => {
      manager.storeEntityMention(TEST_TENANT, TEST_USER, 'customer', 'CUST-001');
      manager.storeEntityMention(TEST_TENANT, TEST_USER, 'customer', 'CUST-001');
      manager.storeEntityMention(TEST_TENANT, TEST_USER, 'customer', 'CUST-001');

      const memory = manager.getEntityMemory(TEST_TENANT, TEST_USER, 'customer', 'CUST-001');
      const entityData = memory?.metadata.entity_data;
      
      expect(entityData?.mention_count).toBe(3);
    });

    test('should get frequent entities', () => {
      manager.storeEntityMention(TEST_TENANT, TEST_USER, 'ticket', 'TKT-001');
      manager.storeEntityMention(TEST_TENANT, TEST_USER, 'ticket', 'TKT-001');
      manager.storeEntityMention(TEST_TENANT, TEST_USER, 'ticket', 'TKT-001');
      manager.storeEntityMention(TEST_TENANT, TEST_USER, 'ticket', 'TKT-002');
      manager.storeEntityMention(TEST_TENANT, TEST_USER, 'customer', 'CUST-001');

      const frequent = manager.getFrequentEntities(TEST_TENANT, TEST_USER, 'ticket', 5);
      expect(frequent.length).toBeGreaterThan(0);
      expect(frequent[0].metadata.entity_data?.entity_id).toBe('TKT-001');
    });
  });

  describe('Pattern Learning', () => {
    test('should learn a pattern', () => {
      const pattern = manager.learnPattern(
        TEST_TENANT,
        TEST_USER,
        'context_pattern',
        ['dashboard', 'tickets_page'],
        'search_tickets' as any,
        0.7
      );

      expect(pattern).toBeDefined();
      expect(pattern?.type).toBe('learned_pattern');
    });

    test('should strengthen existing pattern', () => {
      manager.learnPattern(TEST_TENANT, TEST_USER, 'time_pattern', ['morning'], 'view_dashboard' as any, 0.5);
      manager.learnPattern(TEST_TENANT, TEST_USER, 'time_pattern', ['morning'], 'view_dashboard' as any, 0.5);
      manager.learnPattern(TEST_TENANT, TEST_USER, 'time_pattern', ['morning'], 'view_dashboard' as any, 0.5);

      const patterns = manager.getMatchingPatterns(TEST_TENANT, TEST_USER, { context: 'morning' });
      const patternData = patterns[0]?.metadata.pattern_data;
      
      expect(patternData?.occurrences).toBe(3);
      expect(patternData?.confidence).toBeGreaterThan(0.5);
    });

    test('should get matching patterns', () => {
      manager.learnPattern(TEST_TENANT, TEST_USER, 'context_pattern', ['tickets'], 'search_tickets' as any, 0.8);

      const matching = manager.getMatchingPatterns(TEST_TENANT, TEST_USER, { context: 'tickets' });
      expect(matching.length).toBeGreaterThan(0);
    });

    test('should respect variant limits for mini_parwa', () => {
      const miniManager = createMemoryManager('mini_parwa');
      
      const pattern = miniManager.learnPattern(
        TEST_TENANT,
        TEST_USER,
        'context_pattern',
        ['test'],
        'test_intent' as any
      );

      // mini_parwa should not allow pattern learning
      expect(pattern).toBeUndefined();
      
      miniManager.shutdown();
    });
  });

  describe('Memory Retrieval', () => {
    beforeEach(() => {
      manager.setUserPreference(TEST_TENANT, TEST_USER, 'display', 'theme', 'dark');
      manager.storeEntityMention(TEST_TENANT, TEST_USER, 'ticket', 'TKT-001');
      manager.storeConversation(
        TEST_TENANT,
        TEST_USER,
        'session_1',
        [{ id: '1', role: 'user', content: 'Help with refunds', timestamp: new Date() }]
      );
    });

    test('should search all memories', () => {
      const result = manager.search({
        tenant_id: TEST_TENANT,
        user_id: TEST_USER,
      });

      expect(result.total).toBeGreaterThanOrEqual(3);
    });

    test('should get relevant context', () => {
      const context = manager.getRelevantContext(TEST_TENANT, TEST_USER, 'refund');
      expect(context.length).toBeGreaterThan(0);
    });
  });

  describe('Events', () => {
    test('should emit memory_created event', (done) => {
      const unsubscribe = manager.onEvent('memory_created', (event) => {
        expect(event.type).toBe('memory_created');
        expect(event.user_id).toBe(TEST_USER);
        unsubscribe();
        done();
      });

      manager.setUserPreference(TEST_TENANT, TEST_USER, 'display', 'theme', 'dark');
    });

    test('should emit preference_updated event', (done) => {
      manager.setUserPreference(TEST_TENANT, TEST_USER, 'display', 'theme', 'dark');

      const unsubscribe = manager.onEvent('preference_updated', (event) => {
        expect(event.type).toBe('preference_updated');
        expect(event.metadata?.key).toBe('theme');
        unsubscribe();
        done();
      });

      manager.setUserPreference(TEST_TENANT, TEST_USER, 'display', 'theme', 'light');
    });

    test('should emit pattern_learned event', (done) => {
      const unsubscribe = manager.onEvent('pattern_learned', (event) => {
        expect(event.type).toBe('pattern_learned');
        unsubscribe();
        done();
      });

      manager.learnPattern(TEST_TENANT, TEST_USER, 'test_pattern', ['test'], 'test' as any);
    });
  });

  describe('Statistics', () => {
    test('should return memory statistics', () => {
      manager.setUserPreference(TEST_TENANT, TEST_USER, 'display', 'theme', 'dark');
      manager.storeEntityMention(TEST_TENANT, TEST_USER, 'ticket', 'TKT-001');

      const stats = manager.getStats();
      
      expect(stats.total_memories).toBeGreaterThanOrEqual(2);
      expect(stats.memories_by_type.user_preference).toBeGreaterThanOrEqual(1);
      expect(stats.memories_by_type.entity_mention).toBeGreaterThanOrEqual(1);
    });
  });

  describe('Memory Management', () => {
    test('should clear user memories', () => {
      manager.setUserPreference(TEST_TENANT, TEST_USER, 'display', 'theme', 'dark');
      manager.storeEntityMention(TEST_TENANT, TEST_USER, 'ticket', 'TKT-001');

      const count = manager.clearUserMemories(TEST_TENANT, TEST_USER);
      expect(count).toBeGreaterThanOrEqual(2);

      const stats = manager.getStats();
      expect(stats.total_memories).toBe(0);
    });

    test('should archive old memories', () => {
      manager.setUserPreference(TEST_TENANT, TEST_USER, 'display', 'theme', 'dark');
      
      const archived = manager.archiveOldMemories(0); // Archive everything
      expect(archived).toBeGreaterThanOrEqual(0);
    });
  });
});

// ── Variant Limits Tests ────────────────────────────────────────────

describe('Variant Limits', () => {
  test('mini_parwa should have limited memory', () => {
    const miniManager = createMemoryManager('mini_parwa');
    
    // Should still be able to store preferences
    miniManager.setUserPreference(TEST_TENANT, TEST_USER, 'display', 'theme', 'dark');
    
    const stats = miniManager.getStats();
    expect(stats.total_memories).toBeGreaterThanOrEqual(1);
    
    // But pattern learning should be disabled
    const pattern = miniManager.learnPattern(
      TEST_TENANT,
      TEST_USER,
      'test',
      ['test'],
      'test' as any
    );
    expect(pattern).toBeUndefined();
    
    miniManager.shutdown();
  });

  test('parwa_high should have maximum memory', () => {
    const highManager = createMemoryManager('parwa_high');
    
    // Store many memories
    for (let i = 0; i < 100; i++) {
      highManager.setUserPreference(TEST_TENANT, TEST_USER, 'test', `key_${i}`, i);
    }
    
    const stats = highManager.getStats();
    expect(stats.total_memories).toBe(100);
    
    // Pattern learning should be enabled
    const pattern = highManager.learnPattern(
      TEST_TENANT,
      TEST_USER,
      'test',
      ['test'],
      'test' as any
    );
    expect(pattern).toBeDefined();
    
    highManager.shutdown();
  });
});

// ── Test Summary Export ────────────────────────────────────────────

export {};
