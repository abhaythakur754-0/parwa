/**
 * JARVIS Integration Types - Week 4 (Phase 1)
 *
 * Type definitions for the JARVIS integration layer.
 * Provides unified types for connecting Awareness Engine and Command Processing.
 */

import type { Variant as VariantType } from '@/types/variant';
import type { AwarenessState, Alert, SystemHealth, SentimentAnalysis } from '@/types/awareness';
import type {
  Command,
  CommandResult,
  ProcessCommandResponse,
  Draft,
  ApprovalRequest,
  CommandContext
} from '@/types/command';

// Re-export Variant for use in other integration modules
export type Variant = VariantType;

// ── Integration Configuration ─────────────────────────────────────

export type Industry = 
  | 'saas'
  | 'ecommerce'
  | 'logistics'
  | 'finance'
  | 'education'
  | 'real_estate'
  | 'manufacturing'
  | 'consulting'
  | 'agency'
  | 'nonprofit'
  | 'hospitality'
  | 'retail'
  | 'other';

export interface JarvisConfig {
  /** Organization/tenant ID */
  organizationId: string;
  /** Variant level for capability gating */
  variant: Variant;
  /** Industry for domain-specific knowledge */
  industry?: Industry;
  /** Enable debug logging */
  debug?: boolean;
  /** Cache configuration */
  cache?: CacheConfig;
  /** Rate limiting configuration */
  rateLimit?: RateLimitConfig;
  /** Security configuration */
  security?: SecurityConfig;
}

export interface CacheConfig {
  /** Enable caching */
  enabled: boolean;
  /** Default TTL in seconds */
  defaultTtl: number;
  /** Maximum cache size (entries) */
  maxSize: number;
  /** Redis URL for distributed cache (optional) */
  redisUrl?: string;
}

export interface RateLimitConfig {
  /** Enable rate limiting */
  enabled: boolean;
  /** Requests per minute per user */
  requestsPerMinute: number;
  /** Commands per hour */
  commandsPerHour: number;
  /** Burst allowance */
  burstAllowance: number;
}

export interface SecurityConfig {
  /** Enable input sanitization */
  sanitizeInput: boolean;
  /** Enable command validation */
  validateCommands: boolean;
  /** Enable audit logging */
  auditLogging: boolean;
  /** Maximum command length */
  maxCommandLength: number;
  /** Forbidden patterns (regex strings) */
  forbiddenPatterns: string[];
}

// ── Integration State ────────────────────────────────────────────

export interface JarvisState {
  /** Session ID */
  sessionId: string;
  /** Organization ID */
  organizationId: string;
  /** Variant */
  variant: Variant;
  /** Industry for domain-specific responses */
  industry?: Industry;
  /** Awareness state from Awareness Engine */
  awareness: AwarenessState;
  /** Command context from Command Processing */
  commandContext: CommandContext;
  /** Active drafts awaiting approval */
  activeDrafts: Map<string, Draft>;
  /** Pending alerts */
  pendingAlerts: Alert[];
  /** Session metrics */
  metrics: SessionMetrics;
  /** Created timestamp */
  createdAt: Date;
  /** Last activity timestamp */
  lastActivityAt: Date;
}

export interface SessionMetrics {
  /** Total commands processed */
  commandsProcessed: number;
  /** Commands executed directly */
  directExecutions: number;
  /** Commands requiring approval */
  approvalRequired: number;
  /** Commands approved */
  commandsApproved: number;
  /** Commands rejected */
  commandsRejected: number;
  /** Average response time (ms) */
  avgResponseTime: number;
  /** Cache hit rate */
  cacheHitRate: number;
  /** Errors encountered */
  errors: number;
}

// ── Integration Events ───────────────────────────────────────────

export type IntegrationEventType =
  | 'session_created'
  | 'session_expired'
  | 'command_received'
  | 'command_executed'
  | 'command_draft_created'
  | 'command_approved'
  | 'command_rejected'
  | 'alert_triggered'
  | 'alert_acknowledged'
  | 'health_changed'
  | 'cache_hit'
  | 'cache_miss'
  | 'rate_limited'
  | 'security_violation'
  | 'error';

export interface IntegrationEvent {
  /** Event type */
  type: IntegrationEventType;
  /** Session ID */
  sessionId: string;
  /** Organization ID */
  organizationId: string;
  /** Timestamp */
  timestamp: Date;
  /** Event payload */
  payload: Record<string, unknown>;
  /** Related entity IDs */
  relatedIds?: {
    commandId?: string;
    draftId?: string;
    alertId?: string;
    ticketId?: string;
    customerId?: string;
  };
}

// ── Unified API Types ────────────────────────────────────────────

export interface ProcessJarvisCommandRequest {
  /** Natural language command */
  command: string;
  /** Session ID (optional, will create if not provided) */
  sessionId?: string;
  /** User ID making the request */
  userId: string;
  /** User role for permission checks */
  userRole: string;
  /** Additional context */
  context?: {
    currentPage?: string;
    activeTicketId?: string;
    activeCustomerId?: string;
    filters?: Record<string, unknown>;
  };
  /** Override execution mode */
  forceMode?: 'direct' | 'draft';
}

export interface ProcessJarvisCommandResponse {
  /** Session ID */
  sessionId: string;
  /** Command ID */
  commandId: string;
  /** Success status */
  success: boolean;
  /** Response message */
  message: string;
  /** Result type */
  resultType: 'direct_execution' | 'draft_created' | 'error';
  /** Execution result (for direct execution) */
  result?: CommandResult;
  /** Draft details (for draft mode) */
  draft?: DraftPreview;
  /** Suggested follow-up actions */
  suggestions?: SuggestedAction[];
  /** Context updates */
  contextUpdates?: ContextUpdate[];
  /** Awareness updates */
  awarenessUpdates?: AwarenessUpdate;
  /** Response timestamp */
  timestamp: Date;
}

export interface DraftPreview {
  /** Draft ID */
  id: string;
  /** Original command */
  command: string;
  /** Changes to be made */
  changes: DraftChangePreview[];
  /** Affected items */
  affectedItems: AffectedItemPreview[];
  /** Risk level */
  riskLevel: 'low' | 'medium' | 'high' | 'critical';
  /** Expiry time */
  expiresAt: Date;
  /** Approval requirements */
  approvalRequirements?: ApprovalRequirements;
}

export interface DraftChangePreview {
  field: string;
  currentValue: unknown;
  newValue: unknown;
  description: string;
}

export interface AffectedItemPreview {
  type: 'ticket' | 'customer' | 'agent' | 'team' | 'billing';
  id: string;
  label: string;
  impactLevel: 'info' | 'warning' | 'critical';
}

export interface ApprovalRequirements {
  minApprovers: number;
  requiredRoles: string[];
  currentApprovals: number;
  pendingApprovers: string[];
}

export interface SuggestedAction {
  /** Action type */
  type: 'command' | 'navigation' | 'external' | 'acknowledgment';
  /** Action label */
  label: string;
  /** Command to execute (for type: command) */
  command?: string;
  /** URL to navigate (for type: navigation) */
  url?: string;
  /** Priority (1 = highest) */
  priority: number;
  /** Icon name */
  icon?: string;
}

export interface ContextUpdate {
  key: string;
  value: unknown;
  previousValue?: unknown;
}

export interface AwarenessUpdate {
  /** New alerts */
  newAlerts?: Alert[];
  /** Health status changes */
  healthChanges?: SystemHealth;
  /** Sentiment updates */
  sentimentUpdates?: SentimentAnalysis[];
}

// ── Health Check Types ────────────────────────────────────────────

export interface IntegrationHealth {
  /** Overall status */
  status: 'healthy' | 'degraded' | 'unhealthy';
  /** Timestamp */
  timestamp: Date;
  /** Component health */
  components: {
    awarenessEngine: ComponentHealthStatus;
    commandProcessor: ComponentHealthStatus;
    cache: ComponentHealthStatus;
    rateLimiter: ComponentHealthStatus;
    auditLogger: ComponentHealthStatus;
  };
  /** Active sessions */
  activeSessions: number;
  /** Memory usage (MB) */
  memoryUsage: number;
  /** Uptime (seconds) */
  uptime: number;
}

export interface ComponentHealthStatus {
  status: 'healthy' | 'degraded' | 'unhealthy';
  latency?: number;
  errorRate?: number;
  lastError?: string;
  lastCheck: Date;
}

// ── Audit Log Types ──────────────────────────────────────────────

export interface AuditLogEntry {
  /** Entry ID */
  id: string;
  /** Organization ID */
  organizationId: string;
  /** Session ID */
  sessionId: string;
  /** User ID */
  userId: string;
  /** Timestamp */
  timestamp: Date;
  /** Action type */
  action: AuditAction;
  /** Resource type */
  resourceType: string;
  /** Resource ID */
  resourceId: string;
  /** Command (if applicable) */
  command?: string;
  /** Result */
  result: 'success' | 'failure' | 'pending';
  /** Changes made */
  changes?: Record<string, { from: unknown; to: unknown }>;
  /** IP address */
  ipAddress?: string;
  /** User agent */
  userAgent?: string;
  /** Additional metadata */
  metadata?: Record<string, unknown>;
}

export type AuditAction =
  | 'command_execute'
  | 'command_draft'
  | 'command_approve'
  | 'command_reject'
  | 'alert_acknowledge'
  | 'alert_resolve'
  | 'session_create'
  | 'session_end'
  | 'cache_clear'
  | 'settings_change'
  | 'access_denied';

// ── Performance Types ────────────────────────────────────────────

export interface PerformanceMetrics {
  /** Timestamp */
  timestamp: Date;
  /** Response times (ms) */
  responseTimes: {
    p50: number;
    p95: number;
    p99: number;
    max: number;
  };
  /** Throughput (requests/sec) */
  throughput: number;
  /** Error rate */
  errorRate: number;
  /** Cache performance */
  cache: {
    hits: number;
    misses: number;
    hitRate: number;
    evictions: number;
  };
  /** Queue depth */
  queueDepth: number;
  /** Active connections */
  activeConnections: number;
}

// ── Security Types ───────────────────────────────────────────────

export interface SecurityViolation {
  /** Violation ID */
  id: string;
  /** Session ID */
  sessionId: string;
  /** User ID */
  userId: string;
  /** Timestamp */
  timestamp: Date;
  /** Violation type */
  type: SecurityViolationType;
  /** Severity */
  severity: 'low' | 'medium' | 'high' | 'critical';
  /** Description */
  description: string;
  /** Input that triggered violation */
  input: string;
  /** Action taken */
  action: 'warn' | 'block' | 'rate_limit' | 'ban';
  /** IP address */
  ipAddress?: string;
}

export type SecurityViolationType =
  | 'injection_attempt'
  | 'excessive_requests'
  | 'unauthorized_access'
  | 'suspicious_pattern'
  | 'forbidden_command'
  | 'data_exfiltration_attempt';

// ── Variant Capabilities ──────────────────────────────────────────

export interface JarvisVariantCapabilities {
  /** Maximum commands per day */
  maxCommandsPerDay: number;
  /** Maximum concurrent sessions */
  maxConcurrentSessions: number;
  /** Memory retention (hours) */
  memoryRetentionHours: number;
  /** Enable proactive alerts */
  proactiveAlerts: boolean;
  /** Enable smart suggestions */
  smartSuggestions: boolean;
  /** Enable pattern detection */
  patternDetection: boolean;
  /** Maximum cache size (MB) */
  maxCacheSize: number;
  /** Enable advanced analytics */
  advancedAnalytics: boolean;
  /** Enable voice commands */
  voiceCommands: boolean;
  /** Enable API access */
  apiAccess: 'none' | 'read' | 'full';
}

export const JARVIS_VARIANT_CAPABILITIES: Record<Variant, JarvisVariantCapabilities> = {
  mini_parwa: {
    maxCommandsPerDay: 100,
    maxConcurrentSessions: 1,
    memoryRetentionHours: 24,
    proactiveAlerts: false,
    smartSuggestions: false,
    patternDetection: false,
    maxCacheSize: 10,
    advancedAnalytics: false,
    voiceCommands: false,
    apiAccess: 'none',
  },
  parwa: {
    maxCommandsPerDay: 500,
    maxConcurrentSessions: 3,
    memoryRetentionHours: 168, // 7 days
    proactiveAlerts: true,
    smartSuggestions: true,
    patternDetection: true,
    maxCacheSize: 50,
    advancedAnalytics: true,
    voiceCommands: false,
    apiAccess: 'read',
  },
  parwa_high: {
    maxCommandsPerDay: -1, // Unlimited
    maxConcurrentSessions: 10,
    memoryRetentionHours: 720, // 30 days
    proactiveAlerts: true,
    smartSuggestions: true,
    patternDetection: true,
    maxCacheSize: 200,
    advancedAnalytics: true,
    voiceCommands: true,
    apiAccess: 'full',
  },
};

// ── Default Configurations ────────────────────────────────────────

export const DEFAULT_CACHE_CONFIG: CacheConfig = {
  enabled: true,
  defaultTtl: 300, // 5 minutes
  maxSize: 1000,
};

export const DEFAULT_RATE_LIMIT_CONFIG: RateLimitConfig = {
  enabled: true,
  requestsPerMinute: 60,
  commandsPerHour: 100,
  burstAllowance: 10,
};

export const DEFAULT_SECURITY_CONFIG: SecurityConfig = {
  sanitizeInput: true,
  validateCommands: true,
  auditLogging: true,
  maxCommandLength: 1000,
  forbiddenPatterns: [
    // Note: These patterns are used with case-insensitive flag 'i' in JarvisOrchestrator
    '(drop|delete|truncate)\\s+(table|database)',
    '(insert|update)\\s+.*\\s+(password|credential)',
    '<script[^>]*>.*?</script>',
    'javascript:',
    'on(error|load|click)\\s*=',
  ],
};
