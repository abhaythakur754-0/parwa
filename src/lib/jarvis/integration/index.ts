/**
 * JARVIS Integration Layer - Week 4 (Phase 1)
 *
 * Complete integration layer connecting Awareness Engine and Command Processing.
 * Provides unified API for JARVIS operations with caching, rate limiting, and security.
 *
 * Components:
 * - JarvisOrchestrator: Main orchestrator for all JARVIS operations
 * - CacheManager: High-performance caching layer
 * - RateLimiter: Token bucket rate limiting
 * - AuditLogger: Comprehensive audit logging
 */

// Main Orchestrator
export {
  JarvisOrchestrator,
  createJarvisOrchestrator,
  getJarvisOrchestrator,
  shutdownJarvisOrchestrator,
  shutdownAllOrchestrators,
} from './jarvis-orchestrator';

// Cache Manager
export {
  CacheManager,
  createCacheManager,
  CacheKeys,
} from './cache-manager';

// Rate Limiter
export {
  RateLimiter,
  createRateLimiter,
  createRateLimitMiddleware,
} from './rate-limiter';

// Audit Logger
export {
  AuditLogger,
  createAuditLogger,
  getAuditLogger,
  shutdownAuditLogger,
} from './audit-logger';

// Re-export types
export type {
  JarvisConfig,
  JarvisState,
  CacheConfig,
  RateLimitConfig,
  SecurityConfig,
  SessionMetrics,
  IntegrationEventType,
  IntegrationEvent,
  ProcessJarvisCommandRequest,
  ProcessJarvisCommandResponse,
  DraftPreview,
  DraftChangePreview,
  AffectedItemPreview,
  ApprovalRequirements,
  SuggestedAction,
  ContextUpdate,
  AwarenessUpdate,
  IntegrationHealth,
  ComponentHealthStatus,
  AuditLogEntry,
  AuditAction,
  PerformanceMetrics,
  SecurityViolation,
  SecurityViolationType,
  JarvisVariantCapabilities,
} from './types';

export {
  JARVIS_VARIANT_CAPABILITIES,
  DEFAULT_CACHE_CONFIG,
  DEFAULT_RATE_LIMIT_CONFIG,
  DEFAULT_SECURITY_CONFIG,
} from './types';
