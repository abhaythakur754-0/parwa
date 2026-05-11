"""
RedisHealthTracker — Redis-backed provider health tracking for Smart Router.

Stores ProviderUsage data in Redis hash sets so all Celery workers share
the same health/rate-limit state.  Key pattern:

    health:{provider}:{model_id}   (Redis hash)
        daily_count           int
        minute_count          int
        minute_window_start   float
        rate_limited_until    float
        consecutive_failures  int
        last_error            str
        is_healthy            str  ("1" or "0")

    health:last_daily_reset   (Redis string — date stamp)

BC-008: Falls back to an in-memory dict when Redis is unavailable.

Usage inside ProviderHealthTracker.__init__:
    from app.core.redis_health_tracker import RedisHealthTracker
    tracker = RedisHealthTracker()
    tracker.record_success(provider, model_id, tokens_used)
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("parwa.redis_health_tracker")

# ── Redis import with graceful fallback (BC-008) ────────────────────

_HAS_REDIS = False
_redis_module = None

try:
    import redis as _redis_sync
    _HAS_REDIS = True
    _redis_module = _redis_sync
except ImportError:
    logger.warning(
        "redis package not installed — RedisHealthTracker will use "
        "in-memory fallback.  Install with: pip install redis"
    )

# ── Redis URL resolution ────────────────────────────────────────────


def _get_redis_url() -> Optional[str]:
    """Resolve REDIS_URL from settings or env var (BC-011)."""
    try:
        from app.config import get_settings
        settings = get_settings()
        if hasattr(settings, "REDIS_URL") and settings.REDIS_URL:
            return settings.REDIS_URL
    except Exception:
        pass
    return os.environ.get("REDIS_URL", "")


def _create_redis_client() -> Any:
    """Create a synchronous Redis client from the resolved URL.

    Returns None if URL is missing or connection fails (BC-008).
    """
    if not _HAS_REDIS or _redis_module is None:
        return None
    url = _get_redis_url()
    if not url:
        logger.debug("REDIS_URL not set — using in-memory health tracker")
        return None
    try:
        client = _redis_module.Redis.from_url(
            url,
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
            retry_on_timeout=True,
            health_check_interval=30,
        )
        # Verify connectivity with a quick ping
        client.ping()
        logger.info("RedisHealthTracker connected to Redis")
        return client
    except Exception as exc:
        logger.warning(
            "Redis connection failed — falling back to in-memory tracker: %s",
            exc,
        )
        return None


# ── Default limits when MODEL_REGISTRY lookup fails ─────────────────

_DEFAULT_DAILY_LIMIT = 14400
_DEFAULT_MINUTE_LIMIT = 30000
_DEFAULT_FAILURE_THRESHOLD = 3
_DEFAULT_RATE_LIMIT_COOLDOWN = 60
_DEFAULT_RETRY_AFTER = 60


# ── RedisHealthTracker ──────────────────────────────────────────────


class RedisHealthTracker:
    """Redis-backed health tracker for provider+model combinations.

    All state is stored in Redis hash sets so that multiple Celery
    workers (and multiple ProviderHealthTracker instances) see the same
    health data.  When Redis is unavailable, every operation silently
    falls back to a process-local in-memory dict (BC-008).

    Methods mirror the interface of ProviderHealthTracker so that
    ProviderHealthTracker can delegate to either backend seamlessly.
    """

    # ── Construction ────────────────────────────────────────────

    def __init__(self) -> None:
        """Initialise the tracker, attempting a Redis connection."""
        self._redis: Any = _create_redis_client()
        self._use_redis: bool = self._redis is not None
        # In-memory fallback dict: registry_key -> dict of fields
        self._mem: Dict[str, Dict[str, Any]] = {}
        self._mem_last_daily_reset: str = ""
        if self._use_redis:
            logger.info("RedisHealthTracker using Redis backend")
        else:
            logger.info("RedisHealthTracker using in-memory fallback")

    # ── Internal helpers ────────────────────────────────────────

    @staticmethod
    def _redis_key(provider: str, model_id: str) -> str:
        """Build the Redis hash key: health:{provider}:{model_id}."""
        return f"health:{provider}:{model_id}"

    def _registry_key(self, provider: str, model_id: str) -> str:
        """Build the in-memory dict key (matches smart_router convention)."""
        return f"{model_id}-{provider}"

    def _reset_daily_if_needed(self) -> None:
        """Reset daily counters at midnight UTC (BC-012)."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if self._use_redis:
            try:
                last_reset = self._redis.get("health:last_daily_reset")
                if last_reset == today:
                    return
                # Reset all health:* hashes — set daily_count to 0
                keys = self._redis.keys("health:*")
                pipe = self._redis.pipeline()
                for key in keys:
                    if isinstance(key, str) and key != "health:last_daily_reset":
                        pipe.hset(key, "daily_count", 0)
                pipe.set("health:last_daily_reset", today)
                pipe.execute()
                logger.info(
                    "RedisHealthTracker: daily usage reset for %s (found %d keys)",
                    today, len(keys),
                )
            except Exception as exc:
                logger.warning("RedisHealthTracker daily reset failed: %s", exc)
        else:
            if today != self._mem_last_daily_reset:
                logger.info(
                    "RedisHealthTracker (mem): daily reset for %s (was %s)",
                    today, self._mem_last_daily_reset,
                )
                self._mem_last_daily_reset = today
                for fields in self._mem.values():
                    fields["daily_count"] = 0

    def _get_limits(self, provider: str, model_id: str) -> tuple:
        """Return (daily_limit, minute_limit) from MODEL_REGISTRY.

        Falls back to defaults if the registry key is not found.
        """
        try:
            from app.core.smart_router import MODEL_REGISTRY
            rk = f"{model_id}-{provider}"
            config = MODEL_REGISTRY.get(rk)
            if config is not None:
                return config.max_requests_per_day, config.max_tokens_per_minute
        except Exception:
            pass
        return _DEFAULT_DAILY_LIMIT, _DEFAULT_MINUTE_LIMIT

    def _ensure_mem_entry(self, provider: str, model_id: str) -> Dict[str, Any]:
        """Get or create an in-memory tracking entry."""
        rk = self._registry_key(provider, model_id)
        if rk not in self._mem:
            daily_limit, minute_limit = self._get_limits(provider, model_id)
            self._mem[rk] = {
                "provider": provider,
                "model_id": model_id,
                "daily_count": 0,
                "daily_limit": daily_limit,
                "minute_count": 0,
                "minute_limit": minute_limit,
                "minute_window_start": 0.0,
                "rate_limited_until": 0.0,
                "consecutive_failures": 0,
                "last_error": "",
                "is_healthy": "1",
            }
        return self._mem[rk]

    # ── Public API ──────────────────────────────────────────────

    def record_success(
        self,
        provider: str,
        model_id: str,
        tokens_used: int = 0,
    ) -> None:
        """Record a successful API call.  Resets consecutive failures."""
        self._reset_daily_if_needed()
        if self._use_redis:
            self._record_success_redis(provider, model_id, tokens_used)
        else:
            self._record_success_mem(provider, model_id, tokens_used)

    def _record_success_redis(
        self, provider: str, model_id: str, tokens_used: int,
    ) -> None:
        key = self._redis_key(provider, model_id)
        try:
            now = time.time()
            pipe = self._redis.pipeline()
            # Reset failure tracking
            pipe.hset(key, "consecutive_failures", 0)
            pipe.hset(key, "last_error", "")
            pipe.hset(key, "is_healthy", "1")
            # Increment daily count atomically
            pipe.hincrby(key, "daily_count", 1)
            # Minute-window token tracking
            window_start = self._redis.hget(key, "minute_window_start")
            if window_start is None or (now - float(window_start)) > 60:
                pipe.hset(key, "minute_window_start", now)
                pipe.hset(key, "minute_count", tokens_used)
            else:
                pipe.hincrby(key, "minute_count", tokens_used)
            pipe.execute()
            logger.debug(
                "RedisHealthTracker success: %s (tokens=%d)",
                key, tokens_used,
            )
        except Exception as exc:
            logger.warning(
                "RedisHealthTracker record_success failed, using mem: %s", exc,
            )
            self._record_success_mem(provider, model_id, tokens_used)

    def _record_success_mem(
        self, provider: str, model_id: str, tokens_used: int,
    ) -> None:
        entry = self._ensure_mem_entry(provider, model_id)
        entry["consecutive_failures"] = 0
        entry["last_error"] = ""
        entry["is_healthy"] = "1"
        entry["daily_count"] += 1
        now = time.time()
        if now - entry["minute_window_start"] > 60:
            entry["minute_window_start"] = now
            entry["minute_count"] = tokens_used
        else:
            entry["minute_count"] += tokens_used

    def record_failure(
        self,
        provider: str,
        model_id: str,
        error_msg: str = "Unknown error",
    ) -> None:
        """Record a failed API call.  Marks unhealthy after threshold."""
        if self._use_redis:
            self._record_failure_redis(provider, model_id, error_msg)
        else:
            self._record_failure_mem(provider, model_id, error_msg)

    def _record_failure_redis(
        self, provider: str, model_id: str, error_msg: str,
    ) -> None:
        key = self._redis_key(provider, model_id)
        try:
            pipe = self._redis.pipeline()
            pipe.hincrby(key, "consecutive_failures", 1)
            pipe.hset(key, "last_error", error_msg[:256])
            pipe.execute()
            # Read back to check threshold
            failures = int(self._redis.hget(key, "consecutive_failures") or 0)
            if failures >= _DEFAULT_FAILURE_THRESHOLD:
                self._redis.hset(key, "is_healthy", "0")
                logger.warning(
                    "RedisHealthTracker: %s UNHEALTHY after %d failures: %s",
                    key, failures, error_msg,
                )
            else:
                logger.debug(
                    "RedisHealthTracker: %s failure %d: %s",
                    key, failures, error_msg,
                )
        except Exception as exc:
            logger.warning(
                "RedisHealthTracker record_failure failed, using mem: %s", exc,
            )
            self._record_failure_mem(provider, model_id, error_msg)

    def _record_failure_mem(
        self, provider: str, model_id: str, error_msg: str,
    ) -> None:
        entry = self._ensure_mem_entry(provider, model_id)
        entry["consecutive_failures"] += 1
        entry["last_error"] = error_msg[:256]
        if entry["consecutive_failures"] >= _DEFAULT_FAILURE_THRESHOLD:
            entry["is_healthy"] = "0"
            logger.warning(
                "RedisHealthTracker (mem): %s UNHEALTHY after %d failures",
                self._registry_key(provider, model_id),
                entry["consecutive_failures"],
            )

    def record_rate_limit(
        self,
        provider: str,
        model_id: str,
        retry_after_seconds: int = 0,
    ) -> None:
        """Record a 429 rate limit.  Sets cooldown timer."""
        if self._use_redis:
            self._record_rate_limit_redis(provider, model_id, retry_after_seconds)
        else:
            self._record_rate_limit_mem(provider, model_id, retry_after_seconds)

    def _record_rate_limit_redis(
        self, provider: str, model_id: str, retry_after_seconds: int,
    ) -> None:
        key = self._redis_key(provider, model_id)
        try:
            cooldown = max(
                retry_after_seconds if retry_after_seconds > 0 else _DEFAULT_RETRY_AFTER,
                _DEFAULT_RATE_LIMIT_COOLDOWN,
            )
            until = time.time() + cooldown
            pipe = self._redis.pipeline()
            pipe.hset(key, "rate_limited_until", str(until))
            pipe.hset(key, "last_error", f"rate_limited_for_{cooldown}s")
            pipe.execute()
            logger.warning(
                "RedisHealthTracker: rate limited %s for %ds",
                key, cooldown,
            )
        except Exception as exc:
            logger.warning(
                "RedisHealthTracker record_rate_limit failed, using mem: %s", exc,
            )
            self._record_rate_limit_mem(provider, model_id, retry_after_seconds)

    def _record_rate_limit_mem(
        self, provider: str, model_id: str, retry_after_seconds: int,
    ) -> None:
        entry = self._ensure_mem_entry(provider, model_id)
        cooldown = max(
            retry_after_seconds if retry_after_seconds > 0 else _DEFAULT_RETRY_AFTER,
            _DEFAULT_RATE_LIMIT_COOLDOWN,
        )
        entry["rate_limited_until"] = time.time() + cooldown
        entry["last_error"] = f"rate_limited_for_{cooldown}s"

    def is_available(self, provider: str, model_id: str) -> bool:
        """Check if a provider+model is usable (healthy + under limits)."""
        self._reset_daily_if_needed()
        if self._use_redis:
            return self._is_available_redis(provider, model_id)
        return self._is_available_mem(provider, model_id)

    def _is_available_redis(self, provider: str, model_id: str) -> bool:
        key = self._redis_key(provider, model_id)
        try:
            data = self._redis.hgetall(key)
            if not data:
                return True  # No data → assume available
            # Health check
            if data.get("is_healthy", "1") == "0":
                return False
            # Rate limit cooldown
            until = float(data.get("rate_limited_until", 0))
            if until > time.time():
                return False
            # Daily limit
            daily_count = int(data.get("daily_count", 0))
            daily_limit = int(data.get("daily_limit", _DEFAULT_DAILY_LIMIT))
            if daily_limit > 0 and daily_count >= daily_limit:
                logger.debug(
                    "%s: daily limit reached (%d/%d)",
                    key, daily_count, daily_limit,
                )
                return False
            return True
        except Exception as exc:
            logger.warning(
                "RedisHealthTracker is_available failed, using mem: %s", exc,
            )
            return self._is_available_mem(provider, model_id)

    def _is_available_mem(self, provider: str, model_id: str) -> bool:
        rk = self._registry_key(provider, model_id)
        if rk not in self._mem:
            return True
        entry = self._mem[rk]
        if entry.get("is_healthy", "1") == "0":
            return False
        if entry["rate_limited_until"] > time.time():
            return False
        if entry["daily_count"] >= entry["daily_limit"]:
            return False
        return True

    def get_daily_usage(self, provider: str, model_id: str) -> int:
        """Get today's usage count for a provider+model."""
        self._reset_daily_if_needed()
        if self._use_redis:
            return self._get_daily_usage_redis(provider, model_id)
        return self._get_daily_usage_mem(provider, model_id)

    def _get_daily_usage_redis(self, provider: str, model_id: str) -> int:
        key = self._redis_key(provider, model_id)
        try:
            val = self._redis.hget(key, "daily_count")
            return int(val) if val is not None else 0
        except Exception:
            return self._get_daily_usage_mem(provider, model_id)

    def _get_daily_usage_mem(self, provider: str, model_id: str) -> int:
        rk = self._registry_key(provider, model_id)
        if rk not in self._mem:
            return 0
        return int(self._mem[rk]["daily_count"])

    def get_daily_remaining(self, provider: str, model_id: str) -> int:
        """Get remaining daily requests for a provider+model."""
        self._reset_daily_if_needed()
        if self._use_redis:
            return self._get_daily_remaining_redis(provider, model_id)
        return self._get_daily_remaining_mem(provider, model_id)

    def _get_daily_remaining_redis(self, provider: str, model_id: str) -> int:
        key = self._redis_key(provider, model_id)
        try:
            daily_count = int(self._redis.hget(key, "daily_count") or 0)
            daily_limit = int(self._redis.hget(key, "daily_limit") or _DEFAULT_DAILY_LIMIT)
            return max(0, daily_limit - daily_count)
        except Exception:
            return self._get_daily_remaining_mem(provider, model_id)

    def _get_daily_remaining_mem(self, provider: str, model_id: str) -> int:
        rk = self._registry_key(provider, model_id)
        if rk not in self._mem:
            daily_limit, _ = self._get_limits(provider, model_id)
            return daily_limit
        entry = self._mem[rk]
        return max(0, entry["daily_limit"] - entry["daily_count"])

    def check_rate_limit(self, provider: str, model_id: str) -> bool:
        """Check if a provider+model is currently rate limited."""
        if self._use_redis:
            return self._check_rate_limit_redis(provider, model_id)
        return self._check_rate_limit_mem(provider, model_id)

    def _check_rate_limit_redis(self, provider: str, model_id: str) -> bool:
        key = self._redis_key(provider, model_id)
        try:
            until = self._redis.hget(key, "rate_limited_until")
            if until is None:
                return False
            return float(until) > time.time()
        except Exception:
            return self._check_rate_limit_mem(provider, model_id)

    def _check_rate_limit_mem(self, provider: str, model_id: str) -> bool:
        rk = self._registry_key(provider, model_id)
        if rk not in self._mem:
            return False
        return self._mem[rk]["rate_limited_until"] > time.time()

    def reset_daily_counts(self) -> None:
        """Force-reset all daily counters."""
        if self._use_redis:
            self._reset_daily_counts_redis()
        self._reset_daily_counts_mem()

    def _reset_daily_counts_redis(self) -> None:
        try:
            keys = self._redis.keys("health:*")
            pipe = self._redis.pipeline()
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            for key in keys:
                if isinstance(key, str) and key != "health:last_daily_reset":
                    pipe.hset(key, "daily_count", 0)
            pipe.set("health:last_daily_reset", today)
            pipe.execute()
            logger.info("RedisHealthTracker: daily counts force-reset via Redis")
        except Exception as exc:
            logger.warning(
                "RedisHealthTracker reset_daily_counts (redis) failed: %s", exc,
            )

    def _reset_daily_counts_mem(self) -> None:
        for entry in self._mem.values():
            entry["daily_count"] = 0
        self._mem_last_daily_reset = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        logger.info("RedisHealthTracker: daily counts force-reset (in-memory)")

    def get_all_status(self) -> dict:
        """Return health overview for all tracked provider+model combos."""
        self._reset_daily_if_needed()
        if self._use_redis:
            return self._get_all_status_redis()
        return self._get_all_status_mem()

    def _get_all_status_redis(self) -> dict:
        try:
            keys = self._redis.keys("health:*")
            status: Dict[str, dict] = {}
            now = time.time()
            for key in keys:
                if not isinstance(key, str) or key == "health:last_daily_reset":
                    continue
                # key format: health:{provider}:{model_id}
                parts = key.split(":", 2)
                if len(parts) < 3:
                    continue
                provider = parts[1]
                model_id = parts[2]
                rk = self._registry_key(provider, model_id)
                data = self._redis.hgetall(key)
                if not data:
                    continue
                daily_count = int(data.get("daily_count", 0))
                daily_limit = int(data.get("daily_limit", _DEFAULT_DAILY_LIMIT))
                minute_count = int(data.get("minute_count", 0))
                minute_limit = int(data.get("minute_limit", _DEFAULT_MINUTE_LIMIT))
                rate_until = float(data.get("rate_limited_until", 0))
                status[rk] = {
                    "provider": provider,
                    "model_id": model_id,
                    "is_healthy": data.get("is_healthy", "1") == "1",
                    "daily_count": daily_count,
                    "daily_limit": daily_limit,
                    "daily_remaining": max(0, daily_limit - daily_count),
                    "minute_count": minute_count,
                    "minute_limit": minute_limit,
                    "consecutive_failures": int(data.get("consecutive_failures", 0)),
                    "last_error": data.get("last_error", ""),
                    "rate_limited": rate_until > now,
                }
            return status
        except Exception as exc:
            logger.warning(
                "RedisHealthTracker get_all_status (redis) failed: %s", exc,
            )
            return self._get_all_status_mem()

    def _get_all_status_mem(self) -> dict:
        status: Dict[str, dict] = {}
        now = time.time()
        for rk, entry in self._mem.items():
            daily_count = int(entry.get("daily_count", 0))
            daily_limit = int(entry.get("daily_limit", _DEFAULT_DAILY_LIMIT))
            status[rk] = {
                "provider": entry.get("provider", ""),
                "model_id": entry.get("model_id", ""),
                "is_healthy": entry.get("is_healthy", "1") == "1",
                "daily_count": daily_count,
                "daily_limit": daily_limit,
                "daily_remaining": max(0, daily_limit - daily_count),
                "minute_count": int(entry.get("minute_count", 0)),
                "minute_limit": int(entry.get("minute_limit", _DEFAULT_MINUTE_LIMIT)),
                "consecutive_failures": int(entry.get("consecutive_failures", 0)),
                "last_error": entry.get("last_error", ""),
                "rate_limited": entry.get("rate_limited_until", 0) > now,
            }
        return status
