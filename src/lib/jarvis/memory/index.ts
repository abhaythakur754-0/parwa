/**
 * JARVIS Memory System - Week 5 (Phase 2)
 *
 * Provides persistent memory capabilities for JARVIS.
 * Includes user preferences, conversation history, entity tracking, and pattern learning.
 */

// Types
export type {
  MemoryType,
  MemoryImportance,
  MemoryStatus,
  MemoryEntry,
  MemoryMetadata,
  UserMemory,
  UserMemoryContent,
  ConversationMemory,
  ConversationMemoryContent,
  ConversationTurnMemory,
  EntityMention,
  EntityMemory,
  EntityMemoryContent,
  EntityContext,
  RelatedEntity,
  LearnedPatternMemory,
  LearnedPatternContent,
  PatternData,
  PatternCondition,
  ExpectedAction,
  MemoryQuery,
  MemorySearchResult,
  ConsolidationConfig,
  ConsolidationResult,
  MemorySummary,
  MemoryConfig,
  VariantMemoryLimits,
  MemoryStats,
  MemoryEventType,
  MemoryEvent,
  CreateMemoryRequest,
  UpdateMemoryRequest,
} from './types';

export { DEFAULT_MEMORY_CONFIG } from './types';

// Memory Store
export {
  MemoryStore,
  createMemoryStore,
  getMemoryStore,
  shutdownMemoryStore,
} from './memory-store';

// Memory Manager
export {
  MemoryManager,
  createMemoryManager,
  getMemoryManager,
  shutdownMemoryManager,
  shutdownAllMemoryManagers,
} from './memory-manager';
