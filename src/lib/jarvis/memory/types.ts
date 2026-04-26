/**
 * JARVIS Memory System Types - Week 5 (Phase 2)
 *
 * Type definitions for the Memory System.
 * Provides persistent memory across sessions for users, conversations, and entities.
 */

import type { Variant } from '@/types/variant';
import type { IntentAction, EntityResult } from '@/types/command';

// ── Memory Entry Types ───────────────────────────────────────────────

export type MemoryType = 
  | 'user_preference'     // User preferences and settings
  | 'user_behavior'       // User behavior patterns
  | 'conversation'        // Conversation history
  | 'entity_mention'      // Entity mentions in conversations
  | 'context_snapshot'    // Context snapshots for recovery
  | 'learned_pattern'     // Learned patterns from interactions
  | 'feedback_memory';    // User feedback memory

export type MemoryImportance = 'critical' | 'high' | 'medium' | 'low';

export type MemoryStatus = 'active' | 'archived' | 'decayed' | 'expired';

// ── Base Memory Entry ────────────────────────────────────────────────

export interface MemoryEntry {
  id: string;
  tenant_id: string;
  user_id: string;
  type: MemoryType;
  content: string;
  embedding?: number[];              // Vector embedding for semantic search
  metadata: MemoryMetadata;
  importance: MemoryImportance;
  status: MemoryStatus;
  access_count: number;
  last_accessed_at: Date;
  created_at: Date;
  expires_at?: Date;
  consolidated_from?: string[];      // IDs of memories this was consolidated from
}

export interface MemoryMetadata {
  session_id?: string;
  conversation_id?: string;
  intent?: IntentAction;
  entities?: EntityResult[];
  sentiment?: 'positive' | 'negative' | 'neutral';
  confidence?: number;
  source: 'explicit' | 'inferred' | 'learned';
  tags?: string[];
  [key: string]: unknown;
}

// ── User Memory ───────────────────────────────────────────────────────

export interface UserMemory extends MemoryEntry {
  type: 'user_preference' | 'user_behavior';
  content: string;
  preference_data?: UserMemoryContent;
}

export interface UserMemoryContent {
  category: 'communication' | 'workflow' | 'display' | 'notification' | 'shortcuts';
  key: string;
  value: unknown;
  frequency?: number;               // How often this preference is used
  last_used?: Date;
  context_triggers?: string[];      // Contexts where this applies
}

// ── Conversation Memory ───────────────────────────────────────────────

export interface ConversationMemory extends MemoryEntry {
  type: 'conversation';
  content: string;
  conversation_data?: ConversationMemoryContent;
}

export interface ConversationMemoryContent {
  conversation_id: string;
  session_id: string;
  summary: string;                  // AI-generated summary
  turns: ConversationTurnMemory[];
  topics: string[];
  entities_mentioned: EntityMention[];
  resolution_status: 'resolved' | 'unresolved' | 'escalated';
  satisfaction_score?: number;
}

export interface ConversationTurnMemory {
  role: 'user' | 'jarvis' | 'system';
  content: string;
  timestamp: Date;
  intent?: IntentAction;
  entities?: EntityResult[];
}

export interface EntityMention {
  entity_type: string;
  entity_id: string;
  entity_name?: string;
  mention_count: number;
  last_mentioned: Date;
  context?: string;
}

// ── Entity Memory ─────────────────────────────────────────────────────

export interface EntityMemory extends MemoryEntry {
  type: 'entity_mention';
  content: string;
  entity_data?: EntityMemoryContent;
}

export interface EntityMemoryContent {
  entity_type: 'ticket' | 'customer' | 'agent' | 'team' | 'product' | 'order';
  entity_id: string;
  entity_name?: string;
  mention_count: number;
  first_mentioned: Date;
  last_mentioned: Date;
  contexts: EntityContext[];
  related_entities: RelatedEntity[];
}

export interface EntityContext {
  conversation_id: string;
  context_summary: string;
  timestamp: Date;
}

export interface RelatedEntity {
  entity_type: string;
  entity_id: string;
  relationship: string;
  strength: number;                 // 0-1 relationship strength
}

// ── Learned Pattern Memory ────────────────────────────────────────────

export interface LearnedPatternMemory extends MemoryEntry {
  type: 'learned_pattern';
  content: string;
  pattern_data?: LearnedPatternContent;
}

export interface LearnedPatternContent {
  pattern_type: 'command_sequence' | 'time_pattern' | 'context_pattern' | 'entity_pattern';
  pattern_data: PatternData;
  confidence: number;
  occurrences: number;
  last_occurred: Date;
  predictive_value: number;         // How useful for predictions
}

export interface PatternData {
  trigger_conditions: PatternCondition[];
  expected_actions: ExpectedAction[];
  context_requirements?: string[];
}

export interface PatternCondition {
  type: 'time' | 'context' | 'entity' | 'intent' | 'user_state';
  value: unknown;
  operator: 'equals' | 'contains' | 'before' | 'after' | 'between';
}

export interface ExpectedAction {
  intent: IntentAction;
  probability: number;
  typical_params?: Record<string, unknown>;
}

// ── Memory Retrieval Types ────────────────────────────────────────────

export interface MemoryQuery {
  tenant_id: string;
  user_id?: string;
  types?: MemoryType[];
  text_query?: string;
  entity_filter?: {
    entity_type: string;
    entity_id?: string;
  };
  intent_filter?: IntentAction[];
  time_range?: {
    start: Date;
    end: Date;
  };
  importance_threshold?: MemoryImportance;
  limit?: number;
  offset?: number;
  include_embeddings?: boolean;
}

export interface MemorySearchResult {
  memories: MemoryEntry[];
  total: number;
  has_more: boolean;
  search_time_ms: number;
  relevance_scores?: Map<string, number>;
}

// ── Memory Consolidation Types ────────────────────────────────────────

export interface ConsolidationConfig {
  min_memories_to_consolidate: number;
  max_age_hours: number;
  similarity_threshold: number;
  importance_decay_factor: number;
  consolidation_interval_hours: number;
}

export interface ConsolidationResult {
  consolidated_count: number;
  archived_count: number;
  expired_count: number;
  new_summaries: MemoryEntry[];
  processing_time_ms: number;
}

export interface MemorySummary {
  id: string;
  source_memory_ids: string[];
  summary_text: string;
  key_entities: EntityMention[];
  time_range: {
    start: Date;
    end: Date;
  };
  importance: MemoryImportance;
}

// ── Memory Configuration ──────────────────────────────────────────────

export interface MemoryConfig {
  enabled: boolean;
  max_memories_per_user: number;
  memory_retention_days: number;
  consolidation_enabled: boolean;
  embedding_enabled: boolean;
  embedding_model?: string;
  importance_decay_days: number;
  access_boost_factor: number;
  variant_limits: Record<Variant, VariantMemoryLimits>;
}

export interface VariantMemoryLimits {
  max_memories: number;
  max_conversation_history: number;
  retention_days: number;
  semantic_search_enabled: boolean;
  pattern_learning_enabled: boolean;
}

export const DEFAULT_MEMORY_CONFIG: MemoryConfig = {
  enabled: true,
  max_memories_per_user: 10000,
  memory_retention_days: 30,
  consolidation_enabled: true,
  embedding_enabled: false,
  importance_decay_days: 7,
  access_boost_factor: 1.5,
  variant_limits: {
    mini_parwa: {
      max_memories: 100,
      max_conversation_history: 10,
      retention_days: 7,
      semantic_search_enabled: false,
      pattern_learning_enabled: false,
    },
    parwa: {
      max_memories: 1000,
      max_conversation_history: 50,
      retention_days: 30,
      semantic_search_enabled: true,
      pattern_learning_enabled: true,
    },
    parwa_high: {
      max_memories: 10000,
      max_conversation_history: 200,
      retention_days: 90,
      semantic_search_enabled: true,
      pattern_learning_enabled: true,
    },
  },
};

// ── Memory Statistics ─────────────────────────────────────────────────

export interface MemoryStats {
  total_memories: number;
  memories_by_type: Record<MemoryType, number>;
  memories_by_importance: Record<MemoryImportance, number>;
  average_access_count: number;
  oldest_memory?: Date;
  newest_memory?: Date;
  consolidation_stats: {
    last_run?: Date;
    total_consolidated: number;
    total_archived: number;
  };
  storage_size_bytes: number;
}

// ── Memory Events ─────────────────────────────────────────────────────

export type MemoryEventType = 
  | 'memory_created'
  | 'memory_accessed'
  | 'memory_updated'
  | 'memory_consolidated'
  | 'memory_archived'
  | 'memory_expired'
  | 'pattern_learned'
  | 'preference_updated';

export interface MemoryEvent {
  type: MemoryEventType;
  memory_id?: string;
  user_id: string;
  tenant_id: string;
  timestamp: Date;
  metadata?: Record<string, unknown>;
}

// ── Factory Types ─────────────────────────────────────────────────────

export interface CreateMemoryRequest {
  tenant_id: string;
  user_id: string;
  type: MemoryType;
  content: string;
  metadata?: Partial<MemoryMetadata>;
  importance?: MemoryImportance;
  expires_in_hours?: number;
}

export interface UpdateMemoryRequest {
  content?: string | Record<string, unknown>;
  metadata?: Partial<MemoryMetadata>;
  importance?: MemoryImportance;
  increment_access?: boolean;
}
