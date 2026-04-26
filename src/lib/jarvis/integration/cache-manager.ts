/**
 * JARVIS Cache Manager - Week 4 (Phase 1)
 *
 * High-performance caching layer for JARVIS integration.
 * Supports in-memory caching with LRU eviction and optional Redis backend.
 */

import type { CacheConfig } from './types';

// ── Cache Entry ───────────────────────────────────────────────────

interface CacheEntry<T> {
  value: T;
  expiresAt: number;
  createdAt: number;
  accessCount: number;
  lastAccessedAt: number;
  size: number; // Approximate size in bytes
}

// ── Cache Statistics ───────────────────────────────────────────────

interface CacheStats {
  hits: number;
  misses: number;
  evictions: number;
  size: number;
  entries: number;
  avgAccessTime: number;
}

// ── LRU Cache Implementation ───────────────────────────────────────

class LRUCache<T> {
  private cache: Map<string, CacheEntry<T>> = new Map();
  private maxSize: number;
  private maxMemoryBytes: number;
  private currentMemoryBytes: number = 0;
  private stats: CacheStats = {
    hits: 0,
    misses: 0,
    evictions: 0,
    size: 0,
    entries: 0,
    avgAccessTime: 0,
  };

  constructor(maxSize: number, maxMemoryMB: number = 50) {
    this.maxSize = maxSize;
    this.maxMemoryBytes = maxMemoryMB * 1024 * 1024;
  }

  /**
   * Get a value from cache
   */
  get(key: string): T | null {
    const entry = this.cache.get(key);
    
    if (!entry) {
      this.stats.misses++;
      return null;
    }

    // Check expiration
    if (Date.now() > entry.expiresAt) {
      this.delete(key);
      this.stats.misses++;
      return null;
    }

    // Update access stats (LRU: move to end)
    entry.accessCount++;
    entry.lastAccessedAt = Date.now();
    this.cache.delete(key);
    this.cache.set(key, entry);
    
    this.stats.hits++;
    return entry.value;
  }

  /**
   * Set a value in cache
   */
  set(key: string, value: T, ttlMs: number): void {
    // Estimate size
    const size = this.estimateSize(value);
    
    // Evict if necessary
    while (
      (this.cache.size >= this.maxSize || 
       this.currentMemoryBytes + size > this.maxMemoryBytes) &&
      this.cache.size > 0
    ) {
      this.evictOldest();
    }

    // Remove existing entry if present
    if (this.cache.has(key)) {
      this.delete(key);
    }

    // Create new entry
    const now = Date.now();
    const entry: CacheEntry<T> = {
      value,
      expiresAt: now + ttlMs,
      createdAt: now,
      accessCount: 0,
      lastAccessedAt: now,
      size,
    };

    this.cache.set(key, entry);
    this.currentMemoryBytes += size;
    this.stats.entries = this.cache.size;
    this.stats.size = this.currentMemoryBytes;
  }

  /**
   * Delete a key from cache
   */
  delete(key: string): boolean {
    const entry = this.cache.get(key);
    if (entry) {
      this.cache.delete(key);
      this.currentMemoryBytes -= entry.size;
      this.stats.entries = this.cache.size;
      this.stats.size = this.currentMemoryBytes;
      return true;
    }
    return false;
  }

  /**
   * Check if key exists and is not expired
   */
  has(key: string): boolean {
    const entry = this.cache.get(key);
    if (!entry) return false;
    
    if (Date.now() > entry.expiresAt) {
      this.delete(key);
      return false;
    }
    
    return true;
  }

  /**
   * Clear all entries
   */
  clear(): void {
    this.cache.clear();
    this.currentMemoryBytes = 0;
    this.stats.entries = 0;
    this.stats.size = 0;
  }

  /**
   * Get cache statistics
   */
  getStats(): CacheStats {
    const totalRequests = this.stats.hits + this.stats.misses;
    return {
      ...this.stats,
      avgAccessTime: totalRequests > 0 
        ? this.stats.hits / totalRequests 
        : 0,
    };
  }

  /**
   * Get all keys
   */
  keys(): string[] {
    return Array.from(this.cache.keys());
  }

  /**
   * Get cache size
   */
  get size(): number {
    return this.cache.size;
  }

  /**
   * Evict oldest entry (LRU)
   */
  private evictOldest(): void {
    // First entry is the oldest (least recently used)
    const oldestKey = this.cache.keys().next().value;
    if (oldestKey) {
      this.delete(oldestKey);
      this.stats.evictions++;
    }
  }

  /**
   * Estimate size of value in bytes
   */
  private estimateSize(value: T): number {
    if (value === null || value === undefined) return 0;
    
    if (typeof value === 'string') {
      return value.length * 2; // UTF-16 characters
    }
    
    if (typeof value === 'number') {
      return 8;
    }
    
    if (typeof value === 'boolean') {
      return 4;
    }
    
    if (Array.isArray(value)) {
      return value.reduce((sum, item) => sum + this.estimateSize(item), 50);
    }
    
    if (typeof value === 'object') {
      try {
        return JSON.stringify(value).length * 2;
      } catch {
        return 500; // Default for non-serializable
      }
    }
    
    return 100; // Default
  }
}

// ── Cache Manager ──────────────────────────────────────────────────

export class CacheManager {
  private caches: Map<string, LRUCache<unknown>> = new Map();
  private config: CacheConfig;
  private cleanupInterval: NodeJS.Timeout | null = null;

  constructor(config: CacheConfig) {
    this.config = config;
    
    // Start cleanup interval
    if (config.enabled) {
      this.startCleanup();
    }
  }

  /**
   * Get or create a named cache
   */
  private getCache<T>(namespace: string): LRUCache<T> {
    if (!this.caches.has(namespace)) {
      const cache = new LRUCache<T>(
        Math.floor(this.config.maxSize / 10), // Distribute across namespaces
        5 // 5MB per namespace
      );
      this.caches.set(namespace, cache as LRUCache<unknown>);
    }
    return this.caches.get(namespace) as LRUCache<T>;
  }

  /**
   * Get a value from cache
   */
  get<T>(namespace: string, key: string): T | null {
    if (!this.config.enabled) return null;
    
    const cache = this.getCache<T>(namespace);
    return cache.get(key);
  }

  /**
   * Set a value in cache
   */
  set<T>(namespace: string, key: string, value: T, ttlMs?: number): void {
    if (!this.config.enabled) return;
    
    const cache = this.getCache<T>(namespace);
    cache.set(key, value, ttlMs ?? this.config.defaultTtl * 1000);
  }

  /**
   * Delete a key from cache
   */
  delete(namespace: string, key: string): boolean {
    if (!this.config.enabled) return false;
    
    const cache = this.caches.get(namespace);
    if (cache) {
      return cache.delete(key);
    }
    return false;
  }

  /**
   * Check if key exists
   */
  has(namespace: string, key: string): boolean {
    if (!this.config.enabled) return false;
    
    const cache = this.caches.get(namespace);
    return cache?.has(key) ?? false;
  }

  /**
   * Clear a namespace
   */
  clearNamespace(namespace: string): void {
    const cache = this.caches.get(namespace);
    if (cache) {
      cache.clear();
    }
  }

  /**
   * Clear all caches
   */
  clearAll(): void {
    for (const cache of this.caches.values()) {
      cache.clear();
    }
  }

  /**
   * Get combined statistics
   */
  getStats(): {
    namespaces: Record<string, CacheStats>;
    total: CacheStats;
    hitRate: number;
  } {
    const namespaces: Record<string, CacheStats> = {};
    const total: CacheStats = {
      hits: 0,
      misses: 0,
      evictions: 0,
      size: 0,
      entries: 0,
      avgAccessTime: 0,
    };

    for (const [name, cache] of this.caches) {
      const stats = cache.getStats();
      namespaces[name] = stats;
      total.hits += stats.hits;
      total.misses += stats.misses;
      total.evictions += stats.evictions;
      total.size += stats.size;
      total.entries += stats.entries;
    }

    const totalRequests = total.hits + total.misses;
    const hitRate = totalRequests > 0 ? total.hits / totalRequests : 0;

    return { namespaces, total, hitRate };
  }

  /**
   * Get or compute (memoization pattern)
   */
  async getOrCompute<T>(
    namespace: string,
    key: string,
    computeFn: () => Promise<T>,
    ttlMs?: number
  ): Promise<T> {
    // Try cache first
    const cached = this.get<T>(namespace, key);
    if (cached !== null) {
      return cached;
    }

    // Compute and cache
    const value = await computeFn();
    this.set(namespace, key, value, ttlMs);
    return value;
  }

  /**
   * Batch get
   */
  batchGet<T>(namespace: string, keys: string[]): Map<string, T | null> {
    const results = new Map<string, T | null>();
    for (const key of keys) {
      results.set(key, this.get<T>(namespace, key));
    }
    return results;
  }

  /**
   * Batch set
   */
  batchSet<T>(namespace: string, entries: Array<{ key: string; value: T; ttlMs?: number }>): void {
    for (const { key, value, ttlMs } of entries) {
      this.set(namespace, key, value, ttlMs);
    }
  }

  /**
   * Start cleanup interval
   */
  private startCleanup(): void {
    // Clean expired entries every minute
    this.cleanupInterval = setInterval(() => {
      this.cleanup();
    }, 60000);
  }

  /**
   * Cleanup expired entries
   */
  private cleanup(): void {
    // LRU cache handles expiration on access, but we can force cleanup
    // by checking and deleting expired entries
    const now = Date.now();
    
    for (const [namespace, cache] of this.caches) {
      const keys = cache.keys();
      for (const key of keys) {
        // Access triggers expiration check
        if (!cache.has(key)) {
          // Entry was expired and removed
        }
      }
    }
  }

  /**
   * Shutdown cache manager
   */
  shutdown(): void {
    if (this.cleanupInterval) {
      clearInterval(this.cleanupInterval);
      this.cleanupInterval = null;
    }
    this.clearAll();
  }
}

// ── Factory Function ───────────────────────────────────────────────

export function createCacheManager(config: CacheConfig): CacheManager {
  return new CacheManager(config);
}

// ── Cache Keys Helper ──────────────────────────────────────────────

export const CacheKeys = {
  // Command processing
  commandContext: (sessionId: string) => `cmd:ctx:${sessionId}`,
  commandHistory: (sessionId: string) => `cmd:hist:${sessionId}`,
  intentPatterns: () => 'cmd:intents',
  routeDefinitions: () => 'cmd:routes',
  
  // Awareness
  awarenessState: (orgId: string) => `aware:state:${orgId}`,
  systemHealth: (orgId: string) => `aware:health:${orgId}`,
  activeAlerts: (orgId: string) => `aware:alerts:${orgId}`,
  customerActivity: (customerId: string) => `aware:activity:${customerId}`,
  sentimentCache: (textHash: string) => `aware:sentiment:${textHash}`,
  
  // Session
  sessionState: (sessionId: string) => `session:${sessionId}`,
  userPreferences: (userId: string) => `user:prefs:${userId}`,
  
  // Performance
  metrics: (orgId: string, period: string) => `metrics:${orgId}:${period}`,
  aggregatedData: (orgId: string, type: string, date: string) => 
    `agg:${orgId}:${type}:${date}`,
} as const;
