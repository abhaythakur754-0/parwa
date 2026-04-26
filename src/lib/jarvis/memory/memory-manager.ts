/**
 * JARVIS Memory Manager - Week 5 (Phase 2)
 *
 * Main API for the Memory System.
 * Provides high-level memory operations, pattern learning, and context integration.
 */

import type { Variant } from '@/types/variant';
import type { IntentAction, EntityResult, ConversationTurn } from '@/types/command';
import { MemoryStore, createMemoryStore } from './memory-store';
import { DEFAULT_MEMORY_CONFIG } from './types';
import type {
  MemoryEntry,
  MemoryType,
  MemoryImportance,
  MemoryQuery,
  MemorySearchResult,
  MemoryConfig,
  MemoryStats,
  MemoryEvent,
  MemoryEventType,
  UserMemoryContent,
  ConversationMemoryContent,
  EntityMemoryContent,
  LearnedPatternContent,
  EntityMention,
} from './types';

// ── Event Emitter ─────────────────────────────────────────────────────

type EventCallback = (event: MemoryEvent) => void;

class MemoryEventEmitter {
  private listeners: Map<MemoryEventType, Set<EventCallback>> = new Map();

  on(event: MemoryEventType, callback: EventCallback): () => void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event)!.add(callback);
    return () => this.listeners.get(event)?.delete(callback);
  }

  emit(event: MemoryEvent): void {
    const callbacks = this.listeners.get(event.type);
    if (callbacks) {
      for (const callback of callbacks) {
        try {
          callback(event);
        } catch (error) {
          console.error('Memory event callback error:', error);
        }
      }
    }
  }

  clear(): void {
    this.listeners.clear();
  }
}

// ── Memory Manager ────────────────────────────────────────────────────

export class MemoryManager {
  private store: MemoryStore;
  private config: MemoryConfig;
  private eventEmitter: MemoryEventEmitter;
  private variant: Variant;

  constructor(variant: Variant, config?: Partial<MemoryConfig>) {
    this.variant = variant;
    this.config = { ...DEFAULT_MEMORY_CONFIG, ...config };
    this.store = createMemoryStore();
    this.eventEmitter = new MemoryEventEmitter();
  }

  // ── User Memory Operations ─────────────────────────────────────────

  /**
   * Store a user preference
   */
  setUserPreference(
    tenantId: string,
    userId: string,
    category: UserMemoryContent['category'],
    key: string,
    value: unknown,
    contextTriggers?: string[]
  ): MemoryEntry {
    const content: UserMemoryContent = {
      category,
      key,
      value,
      frequency: 1,
      last_used: new Date(),
      context_triggers: contextTriggers,
    };

    // Check if preference already exists
    const existing = this.findUserPreference(tenantId, userId, category, key);
    if (existing) {
      // Update existing
      const updated = this.store.update(existing.id, {
        content: JSON.stringify(content),
        metadata: { ...existing.metadata, preference_data: content },
        last_accessed_at: new Date(),
      });
      this.emitEvent('preference_updated', userId, tenantId, { key, value });
      return updated!;
    }

    const memory = this.store.create(
      tenantId,
      userId,
      'user_preference',
      JSON.stringify(content),
      { preference_data: content, source: 'explicit' },
      'high'
    );

    this.emitEvent('memory_created', userId, tenantId, { type: 'user_preference', key });
    return memory;
  }

  /**
   * Get a user preference
   */
  getUserPreference(
    tenantId: string,
    userId: string,
    category: string,
    key: string
  ): unknown | undefined {
    const preference = this.findUserPreference(tenantId, userId, category, key);
    if (!preference) return undefined;

    // Update frequency and last_used
    const prefData = preference.metadata.preference_data as UserMemoryContent | undefined;
    if (prefData) {
      prefData.frequency = (prefData.frequency ?? 0) + 1;
      prefData.last_used = new Date();
      this.store.update(preference.id, {
        metadata: { ...preference.metadata, preference_data: prefData },
      });
    }

    return prefData?.value;
  }

  /**
   * Get all user preferences for a category
   */
  getUserPreferencesByCategory(
    tenantId: string,
    userId: string,
    category: string
  ): Map<string, unknown> {
    const preferences = this.store.getUserPreferences(tenantId, userId);
    const result = new Map<string, unknown>();

    for (const pref of preferences) {
      const prefData = pref.metadata.preference_data as UserMemoryContent | undefined;
      if (prefData && prefData.category === category) {
        result.set(prefData.key, prefData.value);
      }
    }

    return result;
  }

  // ── Conversation Memory Operations ─────────────────────────────────

  /**
   * Store conversation memory
   */
  storeConversation(
    tenantId: string,
    userId: string,
    sessionId: string,
    turns: ConversationTurn[],
    summary?: string,
    entities?: EntityResult[]
  ): MemoryEntry {
    const conversationId = `conv_${sessionId}_${Date.now()}`;
    
    // Extract entity mentions
    const entityMentions: EntityMention[] = [];
    if (entities) {
      for (const entity of entities) {
        const existing = entityMentions.find(
          e => e.entity_type === entity.type && e.entity_id === entity.value
        );
        if (existing) {
          existing.mention_count++;
          existing.last_mentioned = new Date();
        } else {
          entityMentions.push({
            entity_type: entity.type,
            entity_id: entity.value,
            mention_count: 1,
            last_mentioned: new Date(),
          });
        }
      }
    }

    const content: ConversationMemoryContent = {
      conversation_id: conversationId,
      session_id: sessionId,
      summary: summary || this.generateSummary(turns),
      turns: turns.map(t => ({
        role: t.role,
        content: t.content,
        timestamp: t.timestamp,
        intent: t.intent,
        entities: t.entities,
      })),
      topics: this.extractTopics(turns),
      entities_mentioned: entityMentions,
      resolution_status: 'resolved',
    };

    const memory = this.store.create(
      tenantId,
      userId,
      'conversation',
      JSON.stringify(content),
      { 
        conversation_data: content,
        session_id: sessionId,
        conversation_id: conversationId,
        entities,
        source: 'explicit',
      },
      'medium'
    );

    // Store entity memories
    for (const mention of entityMentions) {
      this.storeEntityMention(
        tenantId,
        userId,
        mention.entity_type,
        mention.entity_id,
        mention.entity_name,
        content.summary
      );
    }

    this.emitEvent('memory_created', userId, tenantId, { type: 'conversation' });
    return memory;
  }

  /**
   * Get conversation history
   */
  getConversationHistory(
    tenantId: string,
    userId: string,
    limit: number = 10
  ): MemoryEntry[] {
    const result = this.store.query({
      tenant_id: tenantId,
      user_id: userId,
      types: ['conversation'],
      limit,
    });

    return result.memories;
  }

  /**
   * Find similar conversations
   */
  findSimilarConversations(
    tenantId: string,
    userId: string,
    query: string,
    limit: number = 5
  ): MemoryEntry[] {
    const result = this.store.query({
      tenant_id: tenantId,
      user_id: userId,
      types: ['conversation'],
      text_query: query,
      limit,
    });

    return result.memories;
  }

  // ── Entity Memory Operations ─────────────────────────────────────────

  /**
   * Store entity mention
   */
  storeEntityMention(
    tenantId: string,
    userId: string,
    entityType: string,
    entityId: string,
    entityName?: string,
    context?: string
  ): MemoryEntry {
    // Check if entity already tracked
    const existing = this.store.getByEntity(entityType, entityId)
      .find(m => m.user_id === userId && m.type === 'entity_mention');

    if (existing) {
      // Update existing
      const entityData = existing.metadata.entity_data as EntityMemoryContent | undefined;
      if (entityData) {
        entityData.mention_count++;
        entityData.last_mentioned = new Date();
        if (context) {
          entityData.contexts.push({
            conversation_id: '',
            context_summary: context,
            timestamp: new Date(),
          });
        }
        return this.store.update(existing.id, {
          metadata: { ...existing.metadata, entity_data: entityData },
        })!;
      }
    }

    const content: EntityMemoryContent = {
      entity_type: entityType as EntityMemoryContent['entity_type'],
      entity_id: entityId,
      entity_name: entityName,
      mention_count: 1,
      first_mentioned: new Date(),
      last_mentioned: new Date(),
      contexts: context ? [{
        conversation_id: '',
        context_summary: context,
        timestamp: new Date(),
      }] : [],
      related_entities: [],
    };

    const memory = this.store.create(
      tenantId,
      userId,
      'entity_mention',
      JSON.stringify(content),
      {
        entity_data: content,
        entities: [{ type: entityType, value: entityId, normalized_value: entityId, start_index: 0, end_index: 0, confidence: 1, source: 'explicit' }],
        source: 'inferred',
      },
      'medium'
    );

    this.emitEvent('memory_created', userId, tenantId, { type: 'entity_mention', entity_id: entityId });
    return memory;
  }

  /**
   * Get entity memory
   */
  getEntityMemory(
    tenantId: string,
    userId: string,
    entityType: string,
    entityId: string
  ): MemoryEntry | undefined {
    const memories = this.store.getByEntity(entityType, entityId)
      .filter(m => m.tenant_id === tenantId && m.user_id === userId && m.type === 'entity_mention');

    if (memories.length > 0) {
      return this.store.get(memories[0].id);
    }
    return undefined;
  }

  /**
   * Get frequently mentioned entities
   */
  getFrequentEntities(
    tenantId: string,
    userId: string,
    entityType?: string,
    limit: number = 10
  ): MemoryEntry[] {
    const result = this.store.query({
      tenant_id: tenantId,
      user_id: userId,
      types: ['entity_mention'],
      entity_filter: entityType ? { entity_type: entityType } : undefined,
      limit,
    });

    return result.memories.sort(
      (a, b) => {
        const dataA = a.metadata.entity_data as EntityMemoryContent | undefined;
        const dataB = b.metadata.entity_data as EntityMemoryContent | undefined;
        return (dataB?.mention_count ?? 0) - (dataA?.mention_count ?? 0);
      }
    );
  }

  // ── Pattern Learning ────────────────────────────────────────────────

  /**
   * Learn a pattern from user behavior
   */
  learnPattern(
    tenantId: string,
    userId: string,
    patternType: LearnedPatternContent['pattern_type'],
    triggerConditions: unknown[],
    expectedAction: IntentAction,
    confidence: number = 0.5
  ): MemoryEntry | undefined {
    // Check variant allows pattern learning
    const limits = this.config.variant_limits[this.variant];
    if (!limits.pattern_learning_enabled) {
      return undefined;
    }

    // Check if similar pattern exists
    const existing = this.findSimilarPattern(tenantId, userId, patternType, triggerConditions);
    if (existing) {
      // Strengthen existing pattern
      const patternData = existing.metadata.pattern_data as LearnedPatternContent | undefined;
      if (patternData) {
        patternData.occurrences++;
        patternData.confidence = Math.min(1, patternData.confidence + 0.1);
        patternData.last_occurred = new Date();
        
        const updated = this.store.update(existing.id, {
          metadata: { ...existing.metadata, pattern_data: patternData },
        });
        this.emitEvent('pattern_learned', userId, tenantId, { pattern_type: patternType });
        return updated!;
      }
    }

    const content: LearnedPatternContent = {
      pattern_type: patternType,
      pattern_data: {
        trigger_conditions: triggerConditions.map(t => ({
          type: 'context' as const,
          value: t,
          operator: 'equals' as const,
        })),
        expected_actions: [{
          intent: expectedAction,
          probability: confidence,
        }],
      },
      confidence,
      occurrences: 1,
      last_occurred: new Date(),
      predictive_value: confidence,
    };

    const memory = this.store.create(
      tenantId,
      userId,
      'learned_pattern',
      JSON.stringify(content),
      { pattern_data: content, source: 'learned' },
      'medium'
    );

    this.emitEvent('pattern_learned', userId, tenantId, { pattern_type: patternType });
    return memory;
  }

  /**
   * Get patterns that match current context
   */
  getMatchingPatterns(
    tenantId: string,
    userId: string,
    context: Record<string, unknown>
  ): MemoryEntry[] {
    const patterns = this.store.getLearnedPatterns(tenantId, userId);
    
    return patterns.filter(pattern => {
      const patternData = pattern.metadata.pattern_data as LearnedPatternContent | undefined;
      if (!patternData) return false;

      // Check if any trigger condition matches
      for (const condition of patternData.pattern_data.trigger_conditions) {
        const contextValue = context[condition.type];
        if (contextValue !== undefined && contextValue === condition.value) {
          return true;
        }
      }
      return false;
    }).sort((a, b) => {
      const dataA = a.metadata.pattern_data as LearnedPatternContent | undefined;
      const dataB = b.metadata.pattern_data as LearnedPatternContent | undefined;
      return (dataB?.confidence ?? 0) - (dataA?.confidence ?? 0);
    });
  }

  // ── Memory Retrieval ─────────────────────────────────────────────────

  /**
   * Search memories
   */
  search(query: MemoryQuery): MemorySearchResult {
    return this.store.query(query);
  }

  /**
   * Get relevant context for a query
   */
  getRelevantContext(
    tenantId: string,
    userId: string,
    query: string,
    limit: number = 5
  ): MemoryEntry[] {
    const result = this.store.query({
      tenant_id: tenantId,
      user_id: userId,
      text_query: query,
      limit,
    });

    return result.memories;
  }

  /**
   * Get memory by ID
   */
  getMemory(id: string): MemoryEntry | undefined {
    return this.store.get(id);
  }

  // ── Statistics & Management ────────────────────────────────────────

  /**
   * Get memory statistics
   */
  getStats(): MemoryStats {
    return this.store.getStats();
  }

  /**
   * Clear all memories for a user
   */
  clearUserMemories(tenantId: string, userId: string): number {
    const memories = this.store.getByUser(tenantId, userId);
    let count = 0;
    for (const memory of memories) {
      if (this.store.delete(memory.id)) {
        count++;
      }
    }
    return count;
  }

  /**
   * Archive old memories
   */
  archiveOldMemories(olderThanDays?: number): number {
    const days = olderThanDays ?? this.config.memory_retention_days;
    return this.store.archive(days);
  }

  /**
   * Subscribe to memory events
   */
  onEvent(event: MemoryEventType, callback: (event: MemoryEvent) => void): () => void {
    return this.eventEmitter.on(event, callback);
  }

  /**
   * Shutdown memory manager
   */
  shutdown(): void {
    this.store.shutdown();
    this.eventEmitter.clear();
  }

  // ── Private Methods ───────────────────────────────────────────────

  private findUserPreference(
    tenantId: string,
    userId: string,
    category: string,
    key: string
  ): MemoryEntry | undefined {
    const preferences = this.store.getUserPreferences(tenantId, userId);
    return preferences.find(p => {
      const prefData = p.metadata.preference_data as UserMemoryContent | undefined;
      return prefData?.category === category && prefData?.key === key;
    });
  }

  private findSimilarPattern(
    tenantId: string,
    userId: string,
    patternType: string,
    triggerConditions: unknown[]
  ): MemoryEntry | undefined {
    const patterns = this.store.getLearnedPatterns(tenantId, userId);
    
    return patterns.find(pattern => {
      const patternData = pattern.metadata.pattern_data as LearnedPatternContent | undefined;
      if (!patternData || patternData.pattern_type !== patternType) return false;
      
      // Simple similarity check
      const conditions = patternData.pattern_data.trigger_conditions;
      if (conditions.length !== triggerConditions.length) return false;
      
      for (let i = 0; i < conditions.length; i++) {
        if (conditions[i].value !== triggerConditions[i]) return false;
      }
      return true;
    });
  }

  private generateSummary(turns: ConversationTurn[]): string {
    if (turns.length === 0) return 'Empty conversation';
    
    // Simple summary: first user message truncated
    const userTurn = turns.find(t => t.role === 'user');
    if (userTurn) {
      return userTurn.content.slice(0, 100) + (userTurn.content.length > 100 ? '...' : '');
    }
    return 'Conversation without user input';
  }

  private extractTopics(turns: ConversationTurn[]): string[] {
    const topics: Set<string> = new Set();
    
    for (const turn of turns) {
      if (turn.intent) {
        topics.add(turn.intent);
      }
      if (turn.entities) {
        for (const entity of turn.entities) {
          topics.add(entity.type);
        }
      }
    }
    
    return Array.from(topics);
  }

  private emitEvent(
    type: MemoryEventType,
    userId: string,
    tenantId: string,
    metadata?: Record<string, unknown>
  ): void {
    this.eventEmitter.emit({
      type,
      user_id: userId,
      tenant_id: tenantId,
      timestamp: new Date(),
      metadata,
    });
  }
}

// ── Factory Function ─────────────────────────────────────────────────

export function createMemoryManager(
  variant: Variant,
  config?: Partial<MemoryConfig>
): MemoryManager {
  return new MemoryManager(variant, config);
}

// ── Singleton Registry ────────────────────────────────────────────────

const managers = new Map<string, MemoryManager>();

export function getMemoryManager(
  tenantId: string,
  variant: Variant,
  config?: Partial<MemoryConfig>
): MemoryManager {
  const key = `${tenantId}:${variant}`;
  
  if (!managers.has(key)) {
    managers.set(key, createMemoryManager(variant, config));
  }
  
  return managers.get(key)!;
}

export function shutdownMemoryManager(tenantId: string, variant: Variant): void {
  const key = `${tenantId}:${variant}`;
  const manager = managers.get(key);
  if (manager) {
    manager.shutdown();
    managers.delete(key);
  }
}

export function shutdownAllMemoryManagers(): void {
  for (const manager of managers.values()) {
    manager.shutdown();
  }
  managers.clear();
}
