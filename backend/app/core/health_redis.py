"""
Redis-backed Provider Health Tracking (HEALTH-1)

Distributed health tracking for LLM providers.
Replaces in-memory class-level shared state with Redis persistence.

Key Structure:
- parwa:global:health:{registry_key} - Provider health hash
- parwa:global:health:daily_reset - Last daily reset timestamp

This enables horizontal scaling of workers with shared health state.
"""

import logging
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Dict, Optional, Any

import redis.asyncio as aioredis

logger = logging.getLogger("parwa.health_redis")

# Redis key prefixes
REDIS_KEY_PREFIX = "parwa:global:health"
DAILY_RESET_KEY = f"{REDIS_KEY_PREFIX}:daily_reset"


@dataclass
class ProviderHealthData:
    """Health data stored in Redis for each provider+model combo."""

    provider: str
    model_id: str
    is_healthy: bool = True
    consecutive_failures: int = 0
    last_failure_at: str = ""  # ISO timestamp
    last_error: str = ""
    daily_count: int = 0
    daily_limit: int = 14400
    minute_count: int = 0
    minute_limit: int = 30000
    minute_window_start: float = 0.0
    rate_limited_until: float = 0.0
    total_requests: int = 0
    total_successes: int = 0
    total_failures: int = 0
    avg_latency_ms: float = 0.0
    circuit_state: str = "closed"  # closed, open, half-open

    def to_redis_hash(self) -> Dict[str, str]:
        """Convert to Redis hash fields (all strings)."""
        return {k: str(v) for k, v in asdict(self).items()}

    @classmethod
    def from_redis_hash(cls, data: Dict[str, str]) -> "ProviderHealthData":
        """Create from Redis hash fields."""
        return cls(
            provider=data.get("provider", ""),
            model_id=data.get("model_id", ""),
            is_healthy=data.get("is_healthy", "True") == "True",
            consecutive_failures=int(data.get("consecutive_failures", "0")),
            last_failure_at=data.get("last_failure_at", ""),
            last_error=data.get("last_error", ""),
            daily_count=int(data.get("daily_count", "0")),
            daily_limit=int(data.get("daily_limit", "14400")),
            minute_count=int(data.get("minute_count", "0")),
            minute_limit=int(data.get("minute_limit", "30000")),
            minute_window_start=float(data.get("minute_window_start", "0.0")),
            rate_limited_until=float(data.get("rate_limited_until", "0.0")),
            total_requests=int(data.get("total_requests", "0")),
            total_successes=int(data.get("total_successes", "0")),
            total_failures=int(data.get("total_failures", "0")),
            avg_latency_ms=float(data.get("avg_latency_ms", "0.0")),
            circuit_state=data.get("circuit_state", "closed"),
        )


class RedisHealthTracker:
    """
    Redis-backed provider health tracker.

    Provides atomic operations for health state across multiple workers.
    Uses Redis WATCH/MULTI/EXEC for atomic read-modify-write operations.
    """

    CONSECUTIVE_FAILURE_THRESHOLD = 3
    RATE_LIMIT_COOLDOWN_SECONDS = 60
    RATE_LIMIT_RETRY_AFTER_DEFAULT = 60
    HEALTH_TTL = 86400 * 7  # 7 days TTL for health data

    def __init__(self, redis_client: aioredis.Redis):
        """Initialize with Redis client."""
        self._redis = redis_client

    def _get_health_key(self, registry_key: str) -> str:
        """Get Redis key for a provider health hash."""
        return f"{REDIS_KEY_PREFIX}:{registry_key}"

    async def _reset_daily_if_needed(self) -> bool:
        """Reset daily counters at midnight UTC. Returns True if reset occurred."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        last_reset = await self._redis.get(DAILY_RESET_KEY)

        if last_reset:
            last_reset = (
                last_reset.decode("utf-8")
                if isinstance(last_reset, bytes)
                else last_reset
            )

        if today != last_reset:
            logger.info(
                "Daily usage reset triggered for %s (was %s)", today, last_reset
            )

            # Use Lua script for atomic reset
            lua_script = """
            local prefix = ARGV[1]
            local today = ARGV[2]
            local reset_count = 0

            -- Set the daily reset marker
            redis.call('SET', KEYS[1], today)

            -- Find all health keys and reset daily_count
            local cursor = '0'
            repeat
                local result = redis.call('SCAN', cursor, 'MATCH', prefix .. ':*', 'COUNT', 100)
                cursor = result[1]
                local keys = result[2]

                for _, key in ipairs(keys) do
                    redis.call('HSET', key, 'daily_count', '0')
                    reset_count = reset_count + 1
                end
            until cursor == '0'

            return reset_count
            """

            # Execute the reset
            try:
                await self._redis.eval(
                    lua_script,
                    1,  # Number of keys
                    DAILY_RESET_KEY,
                    REDIS_KEY_PREFIX,
                    today,
                )
                return True
            except Exception as e:
                logger.error("Failed to reset daily counters: %s", e)
                return False

        return False

    async def get_health_data(self, registry_key: str) -> Optional[ProviderHealthData]:
        """Get health data for a provider+model combo."""
        key = self._get_health_key(registry_key)
        data = await self._redis.hgetall(key)

        if not data:
            return None

        # Convert bytes to strings
        str_data = {k.decode(): v.decode() for k, v in data.items()}
        return ProviderHealthData.from_redis_hash(str_data)

    async def set_health_data(
        self, registry_key: str, data: ProviderHealthData
    ) -> None:
        """Set health data for a provider+model combo."""
        key = self._get_health_key(registry_key)
        await self._redis.hset(key, mapping=data.to_redis_hash())
        await self._redis.expire(key, self.HEALTH_TTL)

    async def record_success(
        self,
        registry_key: str,
        provider: str,
        model_id: str,
        latency_ms: float = 0.0,
        tokens_used: int = 0,
        daily_limit: int = 14400,
        minute_limit: int = 30000,
    ) -> None:
        """
        Record a successful API call.

        Resets consecutive failure count, increments daily/minute counters,
        updates rolling average latency.
        """
        await self._reset_daily_if_needed()

        key = self._get_health_key(registry_key)

        # Lua script for atomic update
        lua_script = """
        local key = KEYS[1]
        local now = tonumber(ARGV[1])
        local latency_ms = tonumber(ARGV[2])
        local tokens_used = tonumber(ARGV[3])
        local daily_limit = tonumber(ARGV[4])
        local minute_limit = tonumber(ARGV[5])
        local provider = ARGV[6]
        local model_id = ARGV[7]

        -- Get current values
        local daily_count = tonumber(redis.call('HGET', key, 'daily_count') or '0')
        local minute_count = tonumber(redis.call('HGET', key, 'minute_count') or '0')
        local minute_window_start = tonumber(redis.call('HGET', key, 'minute_window_start') or '0')
        local total_requests = tonumber(redis.call('HGET', key, 'total_requests') or '0')
        local total_successes = tonumber(redis.call('HGET', key, 'total_successes') or '0')
        local avg_latency_ms = tonumber(redis.call('HGET', key, 'avg_latency_ms') or '0')

        -- Reset minute window if needed
        if now - minute_window_start > 60 then
            minute_window_start = now
            minute_count = 0
        end

        -- Update counters
        daily_count = daily_count + 1
        minute_count = minute_count + tokens_used
        total_requests = total_requests + 1
        total_successes = total_successes + 1

        -- Update rolling average latency
        if latency_ms > 0 then
            avg_latency_ms = ((avg_latency_ms * (total_successes - 1)) + latency_ms) / total_successes
        end

        -- Set all fields
        redis.call('HMSET', key,
            'provider', provider,
            'model_id', model_id,
            'is_healthy', 'true',
            'consecutive_failures', '0',
            'last_error', '',
            'daily_count', tostring(daily_count),
            'daily_limit', tostring(daily_limit),
            'minute_count', tostring(minute_count),
            'minute_limit', tostring(minute_limit),
            'minute_window_start', tostring(minute_window_start),
            'total_requests', tostring(total_requests),
            'total_successes', tostring(total_successes),
            'avg_latency_ms', tostring(avg_latency_ms),
            'circuit_state', 'closed'
        )

        return 1
        """

        try:
            await self._redis.eval(
                lua_script,
                1,
                key,
                str(time.time()),
                str(latency_ms),
                str(tokens_used),
                str(daily_limit),
                str(minute_limit),
                provider,
                model_id,
            )
        except Exception as e:
            logger.error("Failed to record success for %s: %s", registry_key, e)

    async def record_failure(
        self,
        registry_key: str,
        provider: str,
        model_id: str,
        error_msg: str = "Unknown error",
        daily_limit: int = 14400,
        minute_limit: int = 30000,
    ) -> bool:
        """
        Record a failed API call.

        Increments consecutive failure count, marks unhealthy after threshold.
        Returns True if provider was marked unhealthy.
        """
        key = self._get_health_key(registry_key)

        # Lua script for atomic update
        lua_script = """
        local key = KEYS[1]
        local now_str = ARGV[1]
        local error_msg = ARGV[2]
        local threshold = tonumber(ARGV[3])
        local provider = ARGV[4]
        local model_id = ARGV[5]
        local daily_limit = ARGV[6]
        local minute_limit = ARGV[7]

        -- Get current values
        local consecutive_failures = tonumber(redis.call('HGET', key, 'consecutive_failures') or '0')
        local total_requests = tonumber(redis.call('HGET', key, 'total_requests') or '0')
        local total_failures = tonumber(redis.call('HGET', key, 'total_failures') or '0')

        -- Increment counters
        consecutive_failures = consecutive_failures + 1
        total_requests = total_requests + 1
        total_failures = total_failures + 1

        -- Check if should mark unhealthy
        local is_healthy = 'true'
        local circuit_state = 'closed'
        if consecutive_failures >= threshold then
            is_healthy = 'false'
            circuit_state = 'open'
        end

        -- Set all fields
        redis.call('HMSET', key,
            'provider', provider,
            'model_id', model_id,
            'is_healthy', is_healthy,
            'consecutive_failures', tostring(consecutive_failures),
            'last_failure_at', now_str,
            'last_error', error_msg,
            'total_requests', tostring(total_requests),
            'total_failures', tostring(total_failures),
            'circuit_state', circuit_state,
            'daily_limit', daily_limit,
            'minute_limit', minute_limit
        )

        return consecutive_failures
        """

        try:
            result = await self._redis.eval(
                lua_script,
                1,
                key,
                datetime.now(timezone.utc).isoformat(),
                error_msg[:200],  # Truncate long error messages
                str(self.CONSECUTIVE_FAILURE_THRESHOLD),
                provider,
                model_id,
                str(daily_limit),
                str(minute_limit),
            )

            consecutive_failures = int(result)
            if consecutive_failures >= self.CONSECUTIVE_FAILURE_THRESHOLD:
                logger.warning(
                    "Provider %s marked UNHEALTHY after %d consecutive failures: %s",
                    registry_key,
                    consecutive_failures,
                    error_msg,
                )
                return True
            else:
                logger.debug(
                    "Recorded failure for %s (consecutive=%d): %s",
                    registry_key,
                    consecutive_failures,
                    error_msg,
                )
                return False

        except Exception as e:
            logger.error("Failed to record failure for %s: %s", registry_key, e)
            return False

    async def record_rate_limit(
        self,
        registry_key: str,
        provider: str,
        model_id: str,
        retry_after_seconds: int = 0,
    ) -> None:
        """Record a 429 rate limit response. Sets cooldown timer."""
        key = self._get_health_key(registry_key)

        cooldown = max(
            (
                retry_after_seconds
                if retry_after_seconds > 0
                else self.RATE_LIMIT_RETRY_AFTER_DEFAULT
            ),
            self.RATE_LIMIT_COOLDOWN_SECONDS,
        )
        rate_limited_until = time.time() + cooldown

        await self._redis.hset(
            key,
            mapping={
                "provider": provider,
                "model_id": model_id,
                "rate_limited_until": str(rate_limited_until),
                "last_error": f"rate_limited_for_{cooldown}s",
            },
        )

        logger.warning(
            "Rate limited: %s for %d seconds (retry_after=%d)",
            registry_key,
            cooldown,
            retry_after_seconds,
        )

    async def is_available(self, registry_key: str) -> bool:
        """Check if a provider+model is usable (healthy + under limits + not rate limited)."""
        await self._reset_daily_if_needed()

        data = await self.get_health_data(registry_key)
        if not data:
            return True  # No data = assume available

        # Check health
        if not data.is_healthy:
            return False

        # Check rate limit cooldown
        if data.rate_limited_until > time.time():
            return False

        # Check daily limit
        if data.daily_count >= data.daily_limit:
            logger.debug(
                "%s: daily limit reached (%d/%d)",
                registry_key,
                data.daily_count,
                data.daily_limit,
            )
            return False

        return True

    async def get_daily_usage(self, registry_key: str) -> int:
        """Get today's usage count for a provider+model."""
        await self._reset_daily_if_needed()
        data = await self.get_health_data(registry_key)
        return data.daily_count if data else 0

    async def get_daily_remaining(
        self, registry_key: str, default_limit: int = 14400
    ) -> int:
        """Get remaining daily requests for a provider+model."""
        await self._reset_daily_if_needed()
        data = await self.get_health_data(registry_key)
        if not data:
            return default_limit
        return max(0, data.daily_limit - data.daily_count)

    async def check_rate_limit(self, registry_key: str) -> bool:
        """Check if a provider+model is currently rate limited."""
        data = await self.get_health_data(registry_key)
        if not data:
            return False
        return data.rate_limited_until > time.time()

    async def reset_provider(self, registry_key: str) -> None:
        """Manually reset a provider to healthy state."""
        key = self._get_health_key(registry_key)
        await self._redis.hset(
            key,
            mapping={
                "is_healthy": "true",
                "consecutive_failures": "0",
                "circuit_state": "closed",
                "last_error": "manually_reset",
            },
        )
        logger.info("Provider %s manually reset to healthy", registry_key)

    async def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        """Return health overview for all tracked provider+model combos."""
        await self._reset_daily_if_needed()

        status: Dict[str, Dict[str, Any]] = {}

        # Scan all health keys
        cursor = 0
        while True:
            cursor, keys = await self._redis.scan(
                cursor=cursor,
                match=f"{REDIS_KEY_PREFIX}:*",
                count=100,
            )

            for key in keys:
                if isinstance(key, bytes):
                    key = key.decode("utf-8")

                # Skip the daily reset key
                if key == DAILY_RESET_KEY:
                    continue

                # Extract registry_key from full key
                registry_key = key.replace(f"{REDIS_KEY_PREFIX}:", "")

                data = await self.get_health_data(registry_key)
                if data:
                    status[registry_key] = {
                        "provider": data.provider,
                        "model_id": data.model_id,
                        "is_healthy": data.is_healthy,
                        "daily_count": data.daily_count,
                        "daily_limit": data.daily_limit,
                        "daily_remaining": max(0, data.daily_limit - data.daily_count),
                        "minute_count": data.minute_count,
                        "minute_limit": data.minute_limit,
                        "consecutive_failures": data.consecutive_failures,
                        "last_error": data.last_error,
                        "last_failure_at": data.last_failure_at,
                        "rate_limited": data.rate_limited_until > time.time(),
                        "total_requests": data.total_requests,
                        "total_successes": data.total_successes,
                        "total_failures": data.total_failures,
                        "avg_latency_ms": data.avg_latency_ms,
                        "circuit_state": data.circuit_state,
                    }

            if cursor == 0:
                break

        return status

    async def reset_daily_counts(self) -> None:
        """Force-reset all daily counters."""
        lua_script = """
        local prefix = ARGV[1]
        local reset_count = 0

        local cursor = '0'
        repeat
            local result = redis.call('SCAN', cursor, 'MATCH', prefix .. ':*', 'COUNT', 100)
            cursor = result[1]
            local keys = result[2]

            for _, key in ipairs(keys) do
                redis.call('HSET', key, 'daily_count', '0')
                reset_count = reset_count + 1
            end
        until cursor == '0'

        return reset_count
        """

        try:
            await self._redis.eval(lua_script, 0, REDIS_KEY_PREFIX)
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            await self._redis.set(DAILY_RESET_KEY, today)
            logger.info("Daily counts force-reset")
        except Exception as e:
            logger.error("Failed to force-reset daily counts: %s", e)


# Singleton instance
_redis_health_tracker: Optional[RedisHealthTracker] = None


async def get_redis_health_tracker() -> RedisHealthTracker:
    """Get or create the singleton Redis health tracker."""
    global _redis_health_tracker

    if _redis_health_tracker is None:
        from app.core.redis import get_redis_client

        redis_client = await get_redis_client()
        _redis_health_tracker = RedisHealthTracker(redis_client)

    return _redis_health_tracker
