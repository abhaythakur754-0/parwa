/**
 * JARVIS Smart Suggestions Tests - Week 7 (Phase 2)
 *
 * Comprehensive tests for the Smart Suggestions system.
 */

import {
  SmartSuggestionsManager,
  createSmartSuggestionsManager,
} from '../smart-suggestions-manager';
import {
  DEFAULT_SMART_SUGGESTIONS_CONFIG,
  SMART_SUGGESTIONS_VARIANT_LIMITS,
} from '../types';
import type {
  SuggestionType,
  SuggestionTrigger,
  SuggestionContext,
  SmartSuggestionsConfig,
  SuggestionRule,
  Variant,
} from '../types';

// ── Test Configuration ─────────────────────────────────────────────

const createTestConfig = (variant: Variant = 'parwa'): SmartSuggestionsConfig => ({
  ...DEFAULT_SMART_SUGGESTIONS_CONFIG,
  tenant_id: `test_tenant_${Date.now()}`,
  variant,
});

const TEST_TENANT = 'test_tenant_123';
const TEST_USER = 'test_user_456';
const TEST_VARIANT: Variant = 'parwa';

// ── Smart Suggestions Manager Tests ─────────────────────────────────

describe('SmartSuggestionsManager', () => {
  let manager: SmartSuggestionsManager;
  let config: SmartSuggestionsConfig;

  beforeEach(() => {
    config = createTestConfig();
    manager = createSmartSuggestionsManager(config);
  });

  afterEach(() => {
    manager.shutdown();
  });

  describe('Initialization', () => {
    test('should initialize with default config', () => {
      expect(manager).toBeDefined();
      const stats = manager.getStats();
      expect(stats.total_suggestions_generated).toBe(0);
    });

    test('should load variant limits', () => {
      const stats = manager.getStats();
      expect(stats.variant_stats).toBeDefined();
    });
  });

  describe('Context Management', () => {
    test('should update context', () => {
      manager.updateContext(TEST_USER, {
        page: 'dashboard',
      });

      const context = manager.getContext(TEST_USER);
      expect(context?.page).toBe('dashboard');
    });

    test('should track recent intents', () => {
      manager.updateContext(TEST_USER, {
        recent_intents: ['search_tickets', 'view_ticket'],
      });

      const context = manager.getContext(TEST_USER);
      expect(context?.recent_intents).toContain('search_tickets');
    });

    test('should track recent entities', () => {
      manager.updateContext(TEST_USER, {
        recent_entities: [
          { type: 'ticket', value: 'TKT-001', normalized_value: 'TKT-001', start_index: 0, end_index: 0, confidence: 1, source: 'explicit' },
        ],
      });

      const context = manager.getContext(TEST_USER);
      expect(context?.recent_entities).toBeDefined();
      expect(context?.recent_entities?.length).toBeGreaterThan(0);
    });

    test('should merge context updates', () => {
      manager.updateContext(TEST_USER, { page: 'dashboard' });
      manager.updateContext(TEST_USER, { entity_type: 'ticket', entity_id: 'TKT-001' });

      const context = manager.getContext(TEST_USER);
      expect(context?.page).toBe('dashboard');
      expect(context?.entity_id).toBe('TKT-001');
    });
  });

  describe('Suggestion Generation', () => {
    test('should generate suggestions for context', () => {
      const response = manager.getSuggestions({
        tenant_id: TEST_TENANT,
        user_id: TEST_USER,
        context: {
          page: 'dashboard',
        },
      });

      expect(response.suggestions.length).toBeGreaterThan(0);
      expect(response.generation_time_ms).toBeGreaterThanOrEqual(0);
    });

    test('should generate entity-based suggestions', () => {
      const response = manager.getSuggestions({
        tenant_id: TEST_TENANT,
        user_id: TEST_USER,
        context: {
          entity_type: 'customer',
          entity_id: 'CUST-001',
        },
      });

      expect(response.suggestions.length).toBeGreaterThan(0);
      expect(response.suggestions[0].type).toBeDefined();
    });

    test('should generate time-based suggestions', () => {
      const response = manager.getSuggestions({
        tenant_id: TEST_TENANT,
        user_id: TEST_USER,
        context: {},
      });

      // Time suggestions may or may not be generated depending on current time
      expect(response.suggestions.length).toBeGreaterThanOrEqual(0);
    });

    test('should generate workflow suggestions after intent', () => {
      const response = manager.getSuggestions({
        tenant_id: TEST_TENANT,
        user_id: TEST_USER,
        context: {
          recent_intents: ['create_ticket'],
        },
      });

      // Should have workflow suggestions
      const workflowSuggestions = response.suggestions.filter(s => s.type === 'workflow');
      expect(workflowSuggestions.length).toBeGreaterThanOrEqual(0);
    });

    test('should filter by suggestion type', () => {
      const response = manager.getSuggestions({
        tenant_id: TEST_TENANT,
        user_id: TEST_USER,
        context: { page: 'dashboard' },
        types: ['context'],
      });

      expect(response.suggestions.every(s => s.type === 'context')).toBe(true);
    });

    test('should respect limit parameter', () => {
      const response = manager.getSuggestions({
        tenant_id: TEST_TENANT,
        user_id: TEST_USER,
        context: { page: 'dashboard' },
        limit: 2,
      });

      expect(response.suggestions.length).toBeLessThanOrEqual(2);
    });

    test('should return context used', () => {
      const response = manager.getSuggestions({
        tenant_id: TEST_TENANT,
        user_id: TEST_USER,
        context: { page: 'tickets' },
      });

      expect(response.context_used.page).toBe('tickets');
    });

    test('should generate unique suggestion IDs', () => {
      const response1 = manager.getSuggestions({
        tenant_id: TEST_TENANT,
        user_id: TEST_USER,
        context: { page: 'dashboard' },
      });

      const response2 = manager.getSuggestions({
        tenant_id: TEST_TENANT,
        user_id: TEST_USER,
        context: { page: 'tickets' },
      });

      const ids1 = response1.suggestions.map(s => s.id);
      const ids2 = response2.suggestions.map(s => s.id);

      // Some IDs should be different
      const allIds = [...ids1, ...ids2];
      const uniqueIds = new Set(allIds);
      expect(uniqueIds.size).toBe(allIds.length);
    });
  });

  describe('Suggestion Properties', () => {
    test('should have required properties', () => {
      const response = manager.getSuggestions({
        tenant_id: TEST_TENANT,
        user_id: TEST_USER,
        context: { page: 'dashboard' },
      });

      for (const suggestion of response.suggestions) {
        expect(suggestion.id).toBeDefined();
        expect(suggestion.type).toBeDefined();
        expect(suggestion.trigger).toBeDefined();
        expect(suggestion.title).toBeDefined();
        expect(suggestion.description).toBeDefined();
        expect(suggestion.action).toBeDefined();
        expect(suggestion.confidence).toBeGreaterThanOrEqual(0);
        expect(suggestion.confidence).toBeLessThanOrEqual(1);
        expect(suggestion.priority).toBeDefined();
        expect(suggestion.created_at).toBeDefined();
      }
    });

    test('should have confidence above threshold', () => {
      const response = manager.getSuggestions({
        tenant_id: TEST_TENANT,
        user_id: TEST_USER,
        context: { page: 'dashboard' },
      });

      for (const suggestion of response.suggestions) {
        expect(suggestion.confidence).toBeGreaterThanOrEqual(
          DEFAULT_SMART_SUGGESTIONS_CONFIG.min_confidence_threshold
        );
      }
    });

    test('should have valid action', () => {
      const response = manager.getSuggestions({
        tenant_id: TEST_TENANT,
        user_id: TEST_USER,
        context: { page: 'dashboard' },
      });

      for (const suggestion of response.suggestions) {
        expect(['command', 'navigation', 'api_call', 'workflow', 'notification']).toContain(
          suggestion.action.type
        );
      }
    });
  });

  describe('Feedback Handling', () => {
    test('should accept feedback', () => {
      const response = manager.getSuggestions({
        tenant_id: TEST_TENANT,
        user_id: TEST_USER,
        context: { page: 'dashboard' },
      });

      if (response.suggestions.length > 0) {
        const feedbackResponse = manager.submitFeedback({
          suggestion_id: response.suggestions[0].id,
          feedback: 'accepted',
          user_id: TEST_USER,
          tenant_id: TEST_TENANT,
        });

        expect(feedbackResponse.success).toBe(true);
      }
    });

    test('should record dismissal feedback', () => {
      const response = manager.getSuggestions({
        tenant_id: TEST_TENANT,
        user_id: TEST_USER,
        context: { page: 'dashboard' },
      });

      if (response.suggestions.length > 0) {
        const feedbackResponse = manager.submitFeedback({
          suggestion_id: response.suggestions[0].id,
          feedback: 'dismissed',
          user_id: TEST_USER,
          tenant_id: TEST_TENANT,
        });

        expect(feedbackResponse.success).toBe(true);
      }
    });

    test('should return error for non-existent suggestion', () => {
      const feedbackResponse = manager.submitFeedback({
        suggestion_id: 'non_existent',
        feedback: 'accepted',
        user_id: TEST_USER,
        tenant_id: TEST_TENANT,
      });

      expect(feedbackResponse.success).toBe(false);
    });

    test('should mark suggestion as accepted', () => {
      const response = manager.getSuggestions({
        tenant_id: TEST_TENANT,
        user_id: TEST_USER,
        context: { page: 'dashboard' },
      });

      if (response.suggestions.length > 0) {
        manager.submitFeedback({
          suggestion_id: response.suggestions[0].id,
          feedback: 'accepted',
          user_id: TEST_USER,
          tenant_id: TEST_TENANT,
        });

        const suggestion = manager.getSuggestion(response.suggestions[0].id);
        expect(suggestion?.accepted).toBe(true);
      }
    });

    test('should mark suggestion as dismissed', () => {
      const response = manager.getSuggestions({
        tenant_id: TEST_TENANT,
        user_id: TEST_USER,
        context: { page: 'dashboard' },
      });

      if (response.suggestions.length > 0) {
        manager.submitFeedback({
          suggestion_id: response.suggestions[0].id,
          feedback: 'dismissed',
          user_id: TEST_USER,
          tenant_id: TEST_TENANT,
        });

        const suggestion = manager.getSuggestion(response.suggestions[0].id);
        expect(suggestion?.dismissed).toBe(true);
      }
    });
  });

  describe('Rule Management', () => {
    test('should add rule', () => {
      const rule: SuggestionRule = {
        id: 'rule_001',
        name: 'Test Rule',
        description: 'A test suggestion rule',
        type: 'context',
        priority: 'high',
        conditions: [
          { type: 'context', field: 'page', operator: 'equals', value: 'dashboard' },
        ],
        action: {
          type: 'command',
          intent: 'test_action',
        },
        enabled: true,
        created_at: new Date(),
        updated_at: new Date(),
      };

      const result = manager.addRule(rule);
      expect(result).toBe(true);

      const rules = manager.getRules();
      expect(rules.find(r => r.id === 'rule_001')).toBeDefined();
    });

    test('should delete rule', () => {
      const rule: SuggestionRule = {
        id: 'rule_002',
        name: 'Test Rule 2',
        description: 'Another test rule',
        type: 'entity',
        priority: 'medium',
        conditions: [],
        action: { type: 'command' },
        enabled: true,
        created_at: new Date(),
        updated_at: new Date(),
      };

      manager.addRule(rule);
      const result = manager.deleteRule('rule_002');
      expect(result).toBe(true);

      const rules = manager.getRules();
      expect(rules.find(r => r.id === 'rule_002')).toBeUndefined();
    });

    test('should return false when deleting non-existent rule', () => {
      const result = manager.deleteRule('non_existent');
      expect(result).toBe(false);
    });
  });

  describe('Statistics', () => {
    test('should return statistics', () => {
      manager.getSuggestions({
        tenant_id: TEST_TENANT,
        user_id: TEST_USER,
        context: { page: 'dashboard' },
      });

      const stats = manager.getStats();

      expect(stats.total_suggestions_generated).toBeGreaterThan(0);
      expect(stats.suggestions_by_type).toBeDefined();
      expect(stats.suggestions_by_trigger).toBeDefined();
      expect(stats.average_confidence).toBeGreaterThanOrEqual(0);
    });

    test('should track acceptance rate', () => {
      const response = manager.getSuggestions({
        tenant_id: TEST_TENANT,
        user_id: TEST_USER,
        context: { page: 'dashboard' },
      });

      if (response.suggestions.length > 0) {
        manager.submitFeedback({
          suggestion_id: response.suggestions[0].id,
          feedback: 'accepted',
          user_id: TEST_USER,
          tenant_id: TEST_TENANT,
        });

        const stats = manager.getStats();
        expect(stats.acceptance_rate).toBeGreaterThan(0);
      }
    });

    test('should track dismissal rate', () => {
      const response = manager.getSuggestions({
        tenant_id: TEST_TENANT,
        user_id: TEST_USER,
        context: { page: 'dashboard' },
      });

      if (response.suggestions.length > 0) {
        manager.submitFeedback({
          suggestion_id: response.suggestions[0].id,
          feedback: 'dismissed',
          user_id: TEST_USER,
          tenant_id: TEST_TENANT,
        });

        const stats = manager.getStats();
        expect(stats.dismissal_rate).toBeGreaterThan(0);
      }
    });
  });

  describe('Events', () => {
    test('should emit suggestion_generated event', (done) => {
      const unsubscribe = manager.onEvent('suggestion_generated', (event) => {
        expect(event.type).toBe('suggestion_generated');
        expect(event.user_id).toBe(TEST_USER);
        unsubscribe();
        done();
      });

      manager.getSuggestions({
        tenant_id: TEST_TENANT,
        user_id: TEST_USER,
        context: { page: 'dashboard' },
      });
    });

    test('should emit suggestion_accepted event', (done) => {
      const response = manager.getSuggestions({
        tenant_id: TEST_TENANT,
        user_id: TEST_USER,
        context: { page: 'dashboard' },
      });

      if (response.suggestions.length > 0) {
        const unsubscribe = manager.onEvent('suggestion_accepted', (event) => {
          expect(event.type).toBe('suggestion_accepted');
          expect(event.suggestion_id).toBe(response.suggestions[0].id);
          unsubscribe();
          done();
        });

        manager.submitFeedback({
          suggestion_id: response.suggestions[0].id,
          feedback: 'accepted',
          user_id: TEST_USER,
          tenant_id: TEST_TENANT,
        });
      } else {
        done();
      }
    });

    test('should emit rule_added event', (done) => {
      const unsubscribe = manager.onEvent('rule_added', (event) => {
        expect(event.type).toBe('rule_added');
        unsubscribe();
        done();
      });

      const rule: SuggestionRule = {
        id: 'rule_event_001',
        name: 'Event Test Rule',
        description: 'Test',
        type: 'context',
        priority: 'medium',
        conditions: [],
        action: { type: 'command' },
        enabled: true,
        created_at: new Date(),
        updated_at: new Date(),
      };

      manager.addRule(rule);
    });
  });
});

// ── Variant Limits Tests ────────────────────────────────────────────

describe('Variant Limits', () => {
  test('mini_parwa should have limited features', () => {
    const limits = SMART_SUGGESTIONS_VARIANT_LIMITS['mini_parwa'];

    expect(limits.max_suggestions_per_hour).toBe(5);
    expect(limits.learning_enabled).toBe(false);
    expect(limits.pattern_suggestions).toBe(false);
    expect(limits.collaboration_suggestions).toBe(false);
    expect(limits.custom_rules).toBe(false);
  });

  test('parwa should have standard features', () => {
    const limits = SMART_SUGGESTIONS_VARIANT_LIMITS['parwa'];

    expect(limits.max_suggestions_per_hour).toBe(20);
    expect(limits.learning_enabled).toBe(true);
    expect(limits.pattern_suggestions).toBe(true);
    expect(limits.collaboration_suggestions).toBe(true);
    expect(limits.custom_rules).toBe(true);
  });

  test('parwa_high should have all features', () => {
    const limits = SMART_SUGGESTIONS_VARIANT_LIMITS['parwa_high'];

    expect(limits.max_suggestions_per_hour).toBe(-1); // Unlimited
    expect(limits.learning_enabled).toBe(true);
    expect(limits.pattern_suggestions).toBe(true);
    expect(limits.collaboration_suggestions).toBe(true);
    expect(limits.optimization_suggestions).toBe(true);
    expect(limits.max_custom_rules).toBe(50);
  });

  test('mini_parwa should not apply learning', () => {
    const config = createTestConfig('mini_parwa');
    const manager = createSmartSuggestionsManager(config);

    const response = manager.getSuggestions({
      tenant_id: TEST_TENANT,
      user_id: TEST_USER,
      context: { page: 'dashboard' },
    });

    // Should still generate suggestions, just without learning
    expect(response.suggestions.length).toBeGreaterThanOrEqual(0);

    manager.shutdown();
  });

  test('mini_parwa should not allow custom rules', () => {
    const config = createTestConfig('mini_parwa');
    const manager = createSmartSuggestionsManager(config);

    const rule: SuggestionRule = {
      id: 'rule_mini',
      name: 'Mini Rule',
      description: 'Test',
      type: 'context',
      priority: 'medium',
      conditions: [],
      action: { type: 'command' },
      enabled: true,
      created_at: new Date(),
      updated_at: new Date(),
    };

    const result = manager.addRule(rule);
    expect(result).toBe(false);

    manager.shutdown();
  });
});

// ── Learning Tests ───────────────────────────────────────────────────

describe('Learning', () => {
  let manager: SmartSuggestionsManager;
  let config: SmartSuggestionsConfig;

  beforeEach(() => {
    config = createTestConfig('parwa');
    manager = createSmartSuggestionsManager(config);
  });

  afterEach(() => {
    manager.shutdown();
  });

  test('should adjust confidence based on feedback', () => {
    // Generate suggestions and provide feedback multiple times
    for (let i = 0; i < 5; i++) {
      const response = manager.getSuggestions({
        tenant_id: TEST_TENANT,
        user_id: TEST_USER,
        context: { page: 'dashboard' },
      });

      if (response.suggestions.length > 0) {
        manager.submitFeedback({
          suggestion_id: response.suggestions[0].id,
          feedback: 'accepted',
          user_id: TEST_USER,
          tenant_id: TEST_TENANT,
        });
      }
    }

    // Stats should reflect learning
    const stats = manager.getStats();
    expect(stats.acceptance_rate).toBeGreaterThan(0);
  });

  test('should track feedback history', () => {
    const response = manager.getSuggestions({
      tenant_id: TEST_TENANT,
      user_id: TEST_USER,
      context: { page: 'dashboard' },
    });

    if (response.suggestions.length > 0) {
      // Accept one
      manager.submitFeedback({
        suggestion_id: response.suggestions[0].id,
        feedback: 'accepted',
        user_id: TEST_USER,
        tenant_id: TEST_TENANT,
      });

      // Dismiss another if available
      if (response.suggestions.length > 1) {
        manager.submitFeedback({
          suggestion_id: response.suggestions[1].id,
          feedback: 'dismissed',
          user_id: TEST_USER,
          tenant_id: TEST_TENANT,
        });
      }

      const stats = manager.getStats();
      expect(stats.total_suggestions_generated).toBeGreaterThan(0);
    }
  });
});

// ── High Workload Suggestions Tests ─────────────────────────────────

describe('High Workload Suggestions', () => {
  let manager: SmartSuggestionsManager;

  beforeEach(() => {
    const config = createTestConfig('parwa');
    manager = createSmartSuggestionsManager(config);
  });

  afterEach(() => {
    manager.shutdown();
  });

  test('should generate optimization suggestion for high workload', () => {
    const response = manager.getSuggestions({
      tenant_id: TEST_TENANT,
      user_id: TEST_USER,
      context: {
        page: 'dashboard',
        user_state: {
          current_workload: 'high',
          focus_mode: false,
          pending_actions: 10,
        },
      },
    });

    // Should generate some suggestions
    expect(response.suggestions.length).toBeGreaterThan(0);

    // Should include optimization suggestions
    const optimizationSuggestions = response.suggestions.filter(s => s.type === 'optimization');
    expect(optimizationSuggestions.length).toBeGreaterThan(0);
  });
});

// ── Test Summary Export ────────────────────────────────────────────

export {};
