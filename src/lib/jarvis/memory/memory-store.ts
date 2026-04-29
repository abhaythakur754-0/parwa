/**
 * JARVIS Memory Store - Week 5 (Phase 2)
 *
 * In-memory storage layer for the Memory System.
 * Provides CRUD operations, querying, and automatic cleanup.
 */

import type { Variant } from '@/types/variant';
import type {
  MemoryEntry,
  MemoryType,
  MemoryImportance,
  MemoryStatus,
  MemoryQuery,
  MemorySearchResult,
  MemoryStats,
  MemoryConfig,
  DEFAULT_MEMORY_CONFIG,
} from './types';

// ── Memory Store Configuration ────────────────────────────────────────

interface MemoryStoreConfig {
  maxTotalMemories: number;
  maxMemoriesPerUser: number;
  cleanupIntervalMs: number;
  decayThresholdDays: number;
}

const DEFAULT_STORE_CONFIG: MemoryStoreConfig = {
  maxTotalMemories: 100000,
  maxMemoriesPerUser: 10000,
  cleanupIntervalMs: 60000, // 1 minute
  decayThresholdDays: 30,
};

// ── In-Memory Storage ─────────────────────────────────────────────────

class MemoryStorage {
  private memories: Map<string, MemoryEntry> = new Map();
  private userIndex: Map<string, Set<string>> = new Map(); // userId -> memoryIds
  private typeIndex: Map<MemoryType, Set<string>> = new Map(); // type -> memoryIds
  private tenantIndex: Map<string, Set<string>> = new Map(); // tenantId -> memoryIds
  private entityIndex: Map<string, Set<string>> = new Map(); // entityType:entityId -> memoryIds

  add(memory: MemoryEntry): void {
    // Add to main storage
    this.memories.set(memory.id, memory);

    // Update user index
    const userKey = `${memory.tenant_id}:${memory.user_id}`;
    if (!this.userIndex.has(userKey)) {
      this.userIndex.set(userKey, new Set());
    }
    this.userIndex.get(userKey)!.add(memory.id);

    // Update type index
    if (!this.typeIndex.has(memory.type)) {
      this.typeIndex.set(memory.type, new Set());
    }
    this.typeIndex.get(memory.type)!.add(memory.id);

    // Update tenant index
    if (!this.tenantIndex.has(memory.tenant_id)) {
      this.tenantIndex.set(memory.tenant_id, new Set());
    }
    this.tenantIndex.get(memory.tenant_id)!.add(memory.id);

    // Update entity index if applicable
    if (memory.metadata.entities) {
      for (const entity of memory.metadata.entities) {
        const entityKey = `${entity.type}:${entity.value}`;
        if (!this.entityIndex.has(entityKey)) {
          this.entityIndex.set(entityKey, new Set());
        }
        this.entityIndex.get(entityKey)!.add(memory.id);
      }
    }
  }

  get(id: string): MemoryEntry | undefined {
    return this.memories.get(id);
  }

  update(id: string, updates: Partial<MemoryEntry>): MemoryEntry | undefined {
    const memory = this.memories.get(id);
    if (!memory) return undefined;

    const updated = { ...memory, ...updates };
    this.memories.set(id, updated);
    return updated;
  }

  delete(id: string): boolean {
    const memory = this.memories.get(id);
    if (!memory) return false;

    // Remove from main storage
    this.memories.delete(id);

    // Remove from indexes
    const userKey = `${memory.tenant_id}:${memory.user_id}`;
    this.userIndex.get(userKey)?.delete(id);
    this.typeIndex.get(memory.type)?.delete(id);
    this.tenantIndex.get(memory.tenant_id)?.delete(id);

    if (memory.metadata.entities) {
      for (const entity of memory.metadata.entities) {
        const entityKey = `${entity.type}:${entity.value}`;
        this.entityIndex.get(entityKey)?.delete(id);
      }
    }

    return true;
  }

  getByUser(tenantId: string, userId: string): MemoryEntry[] {
    const userKey = `${tenantId}:${userId}`;
    const ids = this.userIndex.get(userKey);
    if (!ids) return [];

    return Array.from(ids)
      .map(id => this.memories.get(id))
      .filter((m): m is MemoryEntry => m !== undefined);
  }

  getByType(type: MemoryType): MemoryEntry[] {
    const ids = this.typeIndex.get(type);
    if (!ids) return [];

    return Array.from(ids)
      .map(id => this.memories.get(id))
      .filter((m): m is MemoryEntry => m !== undefined);
  }

  getByEntity(entityType: string, entityId: string): MemoryEntry[] {
    const entityKey = `${entityType}:${entityId}`;
    const ids = this.entityIndex.get(entityKey);
    if (!ids) return [];

    return Array.from(ids)
      .map(id => this.memories.get(id))
      .filter((m): m is MemoryEntry => m !== undefined);
  }

  query(predicate: (memory: MemoryEntry) => boolean): MemoryEntry[] {
    const results: MemoryEntry[] = [];
    for (const memory of this.memories.values()) {
      if (predicate(memory)) {
        results.push(memory);
      }
    }
    return results;
  }

  count(): number {
    return this.memories.size;
  }

  countByUser(tenantId: string, userId: string): number {
    const userKey = `${tenantId}:${userId}`;
    return this.userIndex.get(userKey)?.size ?? 0;
  }

  clear(): void {
    this.memories.clear();
    this.userIndex.clear();
    this.typeIndex.clear();
    this.tenantIndex.clear();
    this.entityIndex.clear();
  }

  getAll(): MemoryEntry[] {
    return Array.from(this.memories.values());
  }

  getOldest(): MemoryEntry | undefined {
    let oldest: MemoryEntry | undefined;
    for (const memory of this.memories.values()) {
      if (!oldest || memory.created_at < oldest.created_at) {
        oldest = memory;
      }
    }
    return oldest;
  }

  evictOldest(count: number): number {
    const sorted = Array.from(this.memories.values())
      .sort((a, b) => a.last_accessed_at.getTime() - b.last_accessed_at.getTime());

    let evicted = 0;
    for (let i = 0; i < count && i < sorted.length; i++) {
      if (sorted[i].importance !== 'critical') {
        this.delete(sorted[i].id);
        evicted++;
      }
    }
    return evicted;
  }
}

// ── Memory Store ──────────────────────────────────────────────────────

export class MemoryStore {
  private storage: MemoryStorage;
  private config: MemoryStoreConfig;
  private cleanupInterval: NodeJS.Timeout | null = null;
  private stats = {
    totalCreated: 0,
    totalAccessed: 0,
    totalUpdated: 0,
    totalDeleted: 0,
    totalEvicted: 0,
  };

  constructor(config?: Partial<MemoryStoreConfig>) {
    this.config = { ...DEFAULT_STORE_CONFIG, ...config };
    this.storage = new MemoryStorage();
    this.startCleanup();
  }

  /**
   * Create a new memory entry
   */
  create(
    tenantId: string,
    userId: string,
    type: MemoryType,
    content: string,
    metadata: Record<string, unknown> = {},
    importance: MemoryImportance = 'medium',
    expiresInHours?: number
  ): MemoryEntry {
    // Check user limit
    const userCount = this.storage.countByUser(tenantId, userId);
    if (userCount >= this.config.maxMemoriesPerUser) {
      this.evictUserMemories(tenantId, userId, 1);
    }

    // Check total limit
    if (this.storage.count() >= this.config.maxTotalMemories) {
      this.storage.evictOldest(10);
    }

    const now = new Date();
    const memory: MemoryEntry = {
      id: this.generateId(),
      tenant_id: tenantId,
      user_id: userId,
      type,
      content,
      metadata: {
        ...metadata,
        source: (metadata.source as "inferred" | "explicit" | "learned") ?? 'explicit',
      },
      importance,
      status: 'active',
      access_count: 0,
      last_accessed_at: now,
      created_at: now,
      expires_at: expiresInHours 
        ? new Date(now.getTime() + expiresInHours * 60 * 60 * 1000)
        : undefined,
    };

    this.storage.add(memory);
    this.stats.totalCreated++;

    return memory;
  }

  /**
   * Get a memory by ID
   */
  get(id: string, incrementAccess: boolean = true): MemoryEntry | undefined {
    const memory = this.storage.get(id);
    if (memory && incrementAccess) {
      this.storage.update(id, {
        access_count: memory.access_count + 1,
        last_accessed_at: new Date(),
      });
      this.stats.totalAccessed++;
    }
    return memory;
  }

  /**
   * Update a memory
   */
  update(id: string, updates: Partial<MemoryEntry>): MemoryEntry | undefined {
    const updated = this.storage.update(id, {
      ...updates,
      last_accessed_at: new Date(),
    });
    if (updated) {
      this.stats.totalUpdated++;
    }
    return updated;
  }

  /**
   * Delete a memory
   */
  delete(id: string): boolean {
    const deleted = this.storage.delete(id);
    if (deleted) {
      this.stats.totalDeleted++;
    }
    return deleted;
  }

  /**
   * Query memories
   */
  query(query: MemoryQuery): MemorySearchResult {
    const startTime = Date.now();

    let memories = this.storage.query(m => {
      // Filter by tenant
      if (m.tenant_id !== query.tenant_id) return false;

      // Filter by user
      if (query.user_id && m.user_id !== query.user_id) return false;

      // Filter by types
      if (query.types && query.types.length > 0 && !query.types.includes(m.type)) return false;

      // Filter by importance
      if (query.importance_threshold) {
        const importanceOrder: MemoryImportance[] = ['critical', 'high', 'medium', 'low'];
        const thresholdIndex = importanceOrder.indexOf(query.importance_threshold);
        const memoryIndex = importanceOrder.indexOf(m.importance);
        if (memoryIndex > thresholdIndex) return false;
      }

      // Filter by time range
      if (query.time_range) {
        if (m.created_at < query.time_range.start || m.created_at > query.time_range.end) {
          return false;
        }
      }

      // Filter by entity
      if (query.entity_filter) {
        const hasEntity = m.metadata.entities?.some(
          e => e.type === query.entity_filter!.entity_type &&
               (!query.entity_filter!.entity_id || e.value === query.entity_filter!.entity_id)
        );
        if (!hasEntity) return false;
      }

      // Filter by status
      if (m.status === 'expired') return false;

      return true;
    });

    // Text search if provided
    if (query.text_query) {
      const lowerQuery = query.text_query.toLowerCase();
      memories = memories.filter(m => 
        m.content.toLowerCase().includes(lowerQuery) ||
        (m.metadata.tags?.some(tag => tag.toLowerCase().includes(lowerQuery)) ?? false)
      );
    }

    // Sort by importance and recency
    const importanceOrder: MemoryImportance[] = ['critical', 'high', 'medium', 'low'];
    memories.sort((a, b) => {
      const importanceDiff = importanceOrder.indexOf(a.importance) - importanceOrder.indexOf(b.importance);
      if (importanceDiff !== 0) return importanceDiff;
      return b.last_accessed_at.getTime() - a.last_accessed_at.getTime();
    });

    // Pagination
    const total = memories.length;
    const offset = query.offset ?? 0;
    const limit = query.limit ?? 100;
    const paginatedMemories = memories.slice(offset, offset + limit);

    return {
      memories: paginatedMemories,
      total,
      has_more: offset + limit < total,
      search_time_ms: Date.now() - startTime,
    };
  }

  /**
   * Get memories by user
   */
  getByUser(tenantId: string, userId: string, type?: MemoryType): MemoryEntry[] {
    let memories = this.storage.getByUser(tenantId, userId);
    if (type) {
      memories = memories.filter(m => m.type === type);
    }
    return memories.sort((a, b) => b.last_accessed_at.getTime() - a.last_accessed_at.getTime());
  }

  /**
   * Get memories by entity
   */
  getByEntity(entityType: string, entityId: string): MemoryEntry[] {
    return this.storage.getByEntity(entityType, entityId);
  }

  /**
   * Get recent memories
   */
  getRecent(tenantId: string, userId: string, limit: number = 10): MemoryEntry[] {
    const memories = this.storage.getByUser(tenantId, userId);
    return memories
      .filter(m => m.status === 'active')
      .sort((a, b) => b.created_at.getTime() - a.created_at.getTime())
      .slice(0, limit);
  }

  /**
   * Get user preferences
   */
  getUserPreferences(tenantId: string, userId: string): MemoryEntry[] {
    return this.storage.getByUser(tenantId, userId)
      .filter(m => m.type === 'user_preference' && m.status === 'active');
  }

  /**
   * Get learned patterns
   */
  getLearnedPatterns(tenantId: string, userId: string): MemoryEntry[] {
    return this.storage.getByUser(tenantId, userId)
      .filter(m => m.type === 'learned_pattern' && m.status === 'active');
  }

  /**
   * Archive old memories
   */
  archive(olderThanDays: number): number {
    const cutoff = new Date(Date.now() - olderThanDays * 24 * 60 * 60 * 1000);
    const toArchive = this.storage.query(m => 
      m.created_at < cutoff && 
      m.status === 'active' && 
      m.importance !== 'critical'
    );

    for (const memory of toArchive) {
      this.storage.update(memory.id, { status: 'archived' });
    }

    return toArchive.length;
  }

  /**
   * Expire memories
   */
  expire(): number {
    const now = new Date();
    const toExpire = this.storage.query(m => 
      (m.expires_at && m.expires_at < now) || 
      m.status === 'decayed'
    );

    for (const memory of toExpire) {
      this.storage.update(memory.id, { status: 'expired' });
    }

    return toExpire.length;
  }

  /**
   * Get statistics
   */
  getStats(): MemoryStats {
    const memories = this.storage.getAll();
    const now = new Date();

    const byType: Record<MemoryType, number> = {
      user_preference: 0,
      user_behavior: 0,
      conversation: 0,
      entity_mention: 0,
      context_snapshot: 0,
      learned_pattern: 0,
      feedback_memory: 0,
    };

    const byImportance: Record<MemoryImportance, number> = {
      critical: 0,
      high: 0,
      medium: 0,
      low: 0,
    };

    let totalAccessCount = 0;
    let oldest: Date | undefined;
    let newest: Date | undefined;
    let storageSize = 0;

    for (const memory of memories) {
      if (memory.status !== 'expired') {
        byType[memory.type]++;
        byImportance[memory.importance]++;
        totalAccessCount += memory.access_count;
        storageSize += memory.content.length * 2; // Rough estimate

        if (!oldest || memory.created_at < oldest) oldest = memory.created_at;
        if (!newest || memory.created_at > newest) newest = memory.created_at;
      }
    }

    return {
      total_memories: memories.filter(m => m.status !== 'expired').length,
      memories_by_type: byType,
      memories_by_importance: byImportance,
      average_access_count: memories.length > 0 ? totalAccessCount / memories.length : 0,
      oldest_memory: oldest,
      newest_memory: newest,
      consolidation_stats: {
        last_run: undefined,
        total_consolidated: 0,
        total_archived: 0,
      },
      storage_size_bytes: storageSize,
    };
  }

  /**
   * Clear all memories
   */
  clear(): void {
    this.storage.clear();
  }

  /**
   * Shutdown
   */
  shutdown(): void {
    if (this.cleanupInterval) {
      clearInterval(this.cleanupInterval);
      this.cleanupInterval = null;
    }
    this.storage.clear();
  }

  // ── Private Methods ───────────────────────────────────────────────

  private generateId(): string {
    return `mem_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  private startCleanup(): void {
    this.cleanupInterval = setInterval(() => {
      this.expire();
      this.archive(this.config.decayThresholdDays);
    }, this.config.cleanupIntervalMs);
  }

  private evictUserMemories(tenantId: string, userId: string, count: number): number {
    const memories = this.storage.getByUser(tenantId, userId)
      .filter(m => m.importance !== 'critical' && m.status === 'active')
      .sort((a, b) => a.last_accessed_at.getTime() - b.last_accessed_at.getTime());

    let evicted = 0;
    for (let i = 0; i < count && i < memories.length; i++) {
      this.storage.delete(memories[i].id);
      evicted++;
    }

    this.stats.totalEvicted += evicted;
    return evicted;
  }
}

// ── Factory Function ─────────────────────────────────────────────────

export function createMemoryStore(config?: Partial<MemoryStoreConfig>): MemoryStore {
  return new MemoryStore(config);
}

// ── Singleton Instance ────────────────────────────────────────────────

let defaultStore: MemoryStore | null = null;

export function getMemoryStore(): MemoryStore {
  if (!defaultStore) {
    defaultStore = new MemoryStore();
  }
  return defaultStore;
}

export function shutdownMemoryStore(): void {
  if (defaultStore) {
    defaultStore.shutdown();
    defaultStore = null;
  }
}
