/**
 * JARVIS Rate Limiter - Week 4 (Phase 1)
 *
 * Token bucket rate limiter for protecting JARVIS endpoints.
 * Supports per-user, per-organization, and global rate limits.
 */

import type { RateLimitConfig, Variant } from './types';

// ── Rate Limit Types ───────────────────────────────────────────────

interface TokenBucket {
  tokens: number;
  lastRefill: number;
  maxTokens: number;
  refillRate: number; // tokens per millisecond
}

interface RateLimitResult {
  allowed: boolean;
  remainingTokens: number;
  resetAt: number;
  retryAfterMs: number;
  limit: number;
}

interface UserRateLimit {
  minute: TokenBucket;
  hour: TokenBucket;
  day: TokenBucket;
}

interface RateLimitEntry {
  user: UserRateLimit;
  org: TokenBucket;
  global: TokenBucket;
  violations: number;
  lastViolation: number;
  blocked: boolean;
  blockedUntil: number;
}

// ── Rate Limiter Configuration ─────────────────────────────────────

interface RateLimiterOptions {
  /** Global rate limit (requests per minute) */
  globalLimit: number;
  /** Organization rate limit (requests per minute) */
  orgLimit: number;
  /** User rate limit (requests per minute) */
  userLimit: number;
  /** Commands per hour */
  commandsPerHour: number;
  /** Commands per day */
  commandsPerDay: number;
  /** Burst allowance */
  burstAllowance: number;
  /** Block duration after violations (ms) */
  blockDuration: number;
  /** Violations before blocking */
  violationThreshold: number;
}

const DEFAULT_OPTIONS: RateLimiterOptions = {
  globalLimit: 10000,
  orgLimit: 1000,
  userLimit: 60,
  commandsPerHour: 100,
  commandsPerDay: 500,
  burstAllowance: 10,
  blockDuration: 300000, // 5 minutes
  violationThreshold: 10,
};

// ── Variant-specific limits ────────────────────────────────────────

const VARIANT_LIMITS: Record<Variant, Partial<RateLimiterOptions>> = {
  mini_parwa: {
    userLimit: 30,
    commandsPerHour: 50,
    commandsPerDay: 100,
    burstAllowance: 5,
  },
  parwa: {
    userLimit: 60,
    commandsPerHour: 100,
    commandsPerDay: 500,
    burstAllowance: 10,
  },
  parwa_high: {
    userLimit: 120,
    commandsPerHour: -1, // Unlimited
    commandsPerDay: -1, // Unlimited
    burstAllowance: 20,
  },
};

// ── Rate Limiter ───────────────────────────────────────────────────

export class RateLimiter {
  private entries: Map<string, RateLimitEntry> = new Map();
  private config: RateLimitConfig;
  private options: RateLimiterOptions;
  private globalBucket: TokenBucket;
  private stats = {
    totalRequests: 0,
    allowedRequests: 0,
    blockedRequests: 0,
    activeUsers: 0,
  };

  constructor(config: RateLimitConfig, options?: Partial<RateLimiterOptions>) {
    this.config = config;
    this.options = { ...DEFAULT_OPTIONS, ...options };
    
    // Initialize global bucket
    this.globalBucket = {
      tokens: this.options.globalLimit,
      lastRefill: Date.now(),
      maxTokens: this.options.globalLimit,
      refillRate: this.options.globalLimit / 60000, // tokens per ms
    };
  }

  /**
   * Check if request is allowed
   */
  checkLimit(
    userId: string,
    orgId: string,
    variant: Variant,
    commandType?: 'command' | 'query' | 'mutation'
  ): RateLimitResult {
    this.stats.totalRequests++;

    if (!this.config.enabled) {
      return this.allowResult(-1);
    }

    const key = `${orgId}:${userId}`;
    const entry = this.getOrCreateEntry(key, variant);
    const now = Date.now();

    // Check if blocked
    if (entry.blocked && now < entry.blockedUntil) {
      this.stats.blockedRequests++;
      return this.blockResult(entry.blockedUntil - now);
    }

    // Refill tokens
    this.refillTokens(entry, now);
    this.refillGlobalTokens(now);

    // Check global limit
    if (this.globalBucket.tokens < 1) {
      this.recordViolation(entry, now);
      this.stats.blockedRequests++;
      return this.denyResult(this.globalBucket);
    }

    // Check org limit
    if (entry.org.tokens < 1) {
      this.recordViolation(entry, now);
      this.stats.blockedRequests++;
      return this.denyResult(entry.org);
    }

    // Check user limits
    const userBucket = this.selectUserBucket(entry, commandType);
    if (userBucket.tokens < 1) {
      this.recordViolation(entry, now);
      this.stats.blockedRequests++;
      return this.denyResult(userBucket);
    }

    // Consume tokens
    this.globalBucket.tokens--;
    entry.org.tokens--;
    userBucket.tokens--;

    this.stats.allowedRequests++;
    return this.allowResult(userBucket.tokens);
  }

  /**
   * Check command-specific rate limit
   */
  checkCommandLimit(
    userId: string,
    orgId: string,
    variant: Variant,
    isRisky: boolean
  ): RateLimitResult {
    const key = `${orgId}:${userId}:cmd`;
    const now = Date.now();

    // Risky commands have stricter limits
    const limit = isRisky ? 10 : VARIANT_LIMITS[variant].commandsPerHour ?? this.options.commandsPerHour;
    
    // Unlimited for PARWA High
    if (limit === -1) {
      return this.allowResult(-1);
    }

    // Create command bucket if needed
    if (!this.entries.has(key)) {
      this.entries.set(key, this.createEntry(variant));
    }

    const entry = this.entries.get(key)!;
    this.refillTokens(entry, now);

    if (entry.user.hour.tokens < 1) {
      return this.denyResult(entry.user.hour);
    }

    entry.user.hour.tokens--;
    return this.allowResult(entry.user.hour.tokens);
  }

  /**
   * Record a violation
   */
  private recordViolation(entry: RateLimitEntry, now: number): void {
    entry.violations++;
    entry.lastViolation = now;

    if (entry.violations >= this.options.violationThreshold) {
      entry.blocked = true;
      entry.blockedUntil = now + this.options.blockDuration;
    }
  }

  /**
   * Get or create rate limit entry
   */
  private getOrCreateEntry(key: string, variant: Variant): RateLimitEntry {
    if (!this.entries.has(key)) {
      this.entries.set(key, this.createEntry(variant));
      this.stats.activeUsers = this.entries.size;
    }
    return this.entries.get(key)!;
  }

  /**
   * Create a new rate limit entry
   */
  private createEntry(variant: Variant): RateLimitEntry {
    const variantConfig = VARIANT_LIMITS[variant];
    const userLimit = variantConfig.userLimit ?? this.options.userLimit;
    const commandsPerHour = variantConfig.commandsPerHour ?? this.options.commandsPerHour;
    const commandsPerDay = variantConfig.commandsPerDay ?? this.options.commandsPerDay;
    const burst = variantConfig.burstAllowance ?? this.options.burstAllowance;

    return {
      user: {
        minute: {
          tokens: userLimit + burst,
          lastRefill: Date.now(),
          maxTokens: userLimit + burst,
          refillRate: userLimit / 60000,
        },
        hour: {
          tokens: commandsPerHour === -1 ? 1000000 : commandsPerHour,
          lastRefill: Date.now(),
          maxTokens: commandsPerHour === -1 ? 1000000 : commandsPerHour,
          refillRate: commandsPerHour === -1 ? 1000000 : commandsPerHour / 3600000,
        },
        day: {
          tokens: commandsPerDay === -1 ? 10000000 : commandsPerDay,
          lastRefill: Date.now(),
          maxTokens: commandsPerDay === -1 ? 10000000 : commandsPerDay,
          refillRate: commandsPerDay === -1 ? 10000000 : commandsPerDay / 86400000,
        },
      },
      org: {
        tokens: this.options.orgLimit,
        lastRefill: Date.now(),
        maxTokens: this.options.orgLimit,
        refillRate: this.options.orgLimit / 60000,
      },
      global: this.globalBucket,
      violations: 0,
      lastViolation: 0,
      blocked: false,
      blockedUntil: 0,
    };
  }

  /**
   * Refill tokens for an entry
   */
  private refillTokens(entry: RateLimitEntry, now: number): void {
    this.refillBucket(entry.user.minute, now);
    this.refillBucket(entry.user.hour, now);
    this.refillBucket(entry.user.day, now);
    this.refillBucket(entry.org, now);
  }

  /**
   * Refill global bucket
   */
  private refillGlobalTokens(now: number): void {
    this.refillBucket(this.globalBucket, now);
  }

  /**
   * Refill a single bucket
   */
  private refillBucket(bucket: TokenBucket, now: number): void {
    const elapsed = now - bucket.lastRefill;
    const refill = elapsed * bucket.refillRate;
    bucket.tokens = Math.min(bucket.maxTokens, bucket.tokens + refill);
    bucket.lastRefill = now;
  }

  /**
   * Select appropriate user bucket
   */
  private selectUserBucket(entry: RateLimitEntry, commandType?: string): TokenBucket {
    switch (commandType) {
      case 'mutation':
        return entry.user.hour; // Mutations use hourly bucket
      case 'command':
        return entry.user.minute; // Commands use minute bucket
      default:
        return entry.user.minute;
    }
  }

  /**
   * Create allow result
   */
  private allowResult(remaining: number): RateLimitResult {
    return {
      allowed: true,
      remainingTokens: remaining,
      resetAt: Date.now() + 60000,
      retryAfterMs: 0,
      limit: -1,
    };
  }

  /**
   * Create deny result
   */
  private denyResult(bucket: TokenBucket): RateLimitResult {
    const retryAfter = Math.ceil((bucket.maxTokens - bucket.tokens) / bucket.refillRate);
    return {
      allowed: false,
      remainingTokens: 0,
      resetAt: Date.now() + retryAfter,
      retryAfterMs: retryAfter,
      limit: bucket.maxTokens,
    };
  }

  /**
   * Create block result
   */
  private blockResult(duration: number): RateLimitResult {
    return {
      allowed: false,
      remainingTokens: 0,
      resetAt: Date.now() + duration,
      retryAfterMs: duration,
      limit: 0,
    };
  }

  /**
   * Get statistics
   */
  getStats(): {
    totalRequests: number;
    allowedRequests: number;
    blockedRequests: number;
    blockRate: number;
    activeUsers: number;
    globalTokens: number;
  } {
    return {
      ...this.stats,
      blockRate: this.stats.totalRequests > 0
        ? this.stats.blockedRequests / this.stats.totalRequests
        : 0,
      globalTokens: Math.floor(this.globalBucket.tokens),
    };
  }

  /**
   * Reset limits for a user
   */
  resetUser(userId: string, orgId: string): void {
    const key = `${orgId}:${userId}`;
    this.entries.delete(key);
  }

  /**
   * Clear all entries
   */
  clear(): void {
    this.entries.clear();
    this.stats = {
      totalRequests: 0,
      allowedRequests: 0,
      blockedRequests: 0,
      activeUsers: 0,
    };
  }

  /**
   * Unban a user
   */
  unban(userId: string, orgId: string): void {
    const key = `${orgId}:${userId}`;
    const entry = this.entries.get(key);
    if (entry) {
      entry.blocked = false;
      entry.blockedUntil = 0;
      entry.violations = 0;
    }
  }
}

// ── Factory Function ───────────────────────────────────────────────

export function createRateLimiter(
  config: RateLimitConfig,
  options?: Partial<RateLimiterOptions>
): RateLimiter {
  return new RateLimiter(config, options);
}

// ── Express-like Middleware Helper ─────────────────────────────────

export function createRateLimitMiddleware(limiter: RateLimiter) {
  return (userId: string, orgId: string, variant: Variant): RateLimitResult => {
    return limiter.checkLimit(userId, orgId, variant);
  };
}
