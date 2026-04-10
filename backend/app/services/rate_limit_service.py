"""
PARWA Advanced Rate Limit Service (F-018)

Per-endpoint-category rate limiting with progressive backoff.
Fails open when Redis is unavailable (falls back to in-memory).
Supports per-email identification for auth endpoints.
"""

import hashlib
import time
from typing import Optional

from app.logger import get_logger

logger = get_logger("rate_limit_service")


# ── Endpoint category definitions ──────────────────────────────────

CATEGORY_CONFIG = {
    "auth_login": {
        "limit": 10,
        "window": 60,
        "scope": "email",
        "backoff_seconds": [0, 2, 4, 8, 900],
        "lockout_duration": 900,
    },
    "auth_mfa": {
        "limit": 10,
        "window": 60,
        "scope": "email",
        "backoff_seconds": [0, 2, 4, 8, 900],
        "lockout_duration": 900,
    },
    "auth_phone_send": {
        "limit": 5,
        "window": 300,
        "scope": "ip",
        "backoff_seconds": [0, 2, 4, 8, 900],
        "lockout_duration": 900,
    },
    "auth_phone_verify": {
        "limit": 20,
        "window": 300,
        "scope": "ip",
        "backoff_seconds": [0, 2, 4, 8, 300],
        "lockout_duration": 300,
    },
    "auth_reset": {
        "limit": 3,
        "window": 3600,
        "scope": "email",
        "backoff_seconds": [0, 2, 4, 8, 900],
        "lockout_duration": 900,
    },
    "financial": {
        "limit": 20,
        "window": 60,
        "scope": "user",
        "backoff_seconds": [0, 2, 4, 8, 300],
        "lockout_duration": 300,
    },
    "general_get": {
        "limit": 100,
        "window": 60,
        "scope": "ip",
        "backoff_seconds": [0, 2, 4, 8, 60],
        "lockout_duration": 60,
    },
    "general_post": {
        "limit": 100,
        "window": 60,
        "scope": "ip",
        "backoff_seconds": [0, 2, 4, 8, 60],
        "lockout_duration": 60,
    },
    "integration": {
        "limit": 60,
        "window": 60,
        "scope": "api_key",
        "backoff_seconds": [0, 2, 4, 8, 60],
        "lockout_duration": 60,
    },
    "demo_chat": {
        "limit": 60,
        "window": 300,
        "scope": "ip_hash",
        "backoff_seconds": [0, 2, 4, 8, 60],
        "lockout_duration": 60,
    },
}


class RateLimitResult:
    """Result of a rate limit check."""

    def __init__(
        self,
        allowed: bool,
        remaining: int,
        limit: int,
        reset_at: float,
        retry_after: Optional[int] = None,
        backoff_seconds: Optional[int] = None,
    ):
        self.allowed = allowed
        self.remaining = remaining
        self.limit = limit
        self.reset_at = reset_at
        self.retry_after = retry_after
        self.backoff_seconds = backoff_seconds

    def to_headers(self) -> dict:
        headers = {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(
                max(self.remaining, 0)
            ),
            "X-RateLimit-Reset": str(int(self.reset_at)),
        }
        if self.retry_after is not None:
            headers["Retry-After"] = str(self.retry_after)
        return headers


class RateLimitService:
    """Advanced rate limit service with per-endpoint-category limits.

    Fails open when Redis unavailable (in-memory fallback).
    Per-email scope for auth endpoints.
    Progressive backoff on failures.
    """

    def __init__(self, redis_client=None):
        self._redis = redis_client
        self._in_memory = {}  # fallback store
        self._failures = {}  # failure tracking for backoff
        self._redis_time_offset: float = 0

    def get_category_config(self, category: str) -> dict:
        """Get configuration for an endpoint category."""
        return CATEGORY_CONFIG.get(category, CATEGORY_CONFIG["general_get"])

    def classify_path(self, path: str, method: str = "GET") -> str:
        """Classify a request path into an endpoint category."""
        if path == "/api/auth/login" and method == "POST":
            return "auth_login"
        if path == "/api/auth/mfa" and method == "POST":
            return "auth_mfa"
        if path == "/api/auth/phone/send" and method == "POST":
            return "auth_phone_send"
        if path == "/api/auth/phone/verify" and method == "POST":
            return "auth_phone_verify"
        if path in (
            "/api/auth/forgot-password",
            "/api/auth/reset-password",
        ) and method == "POST":
            return "auth_reset"
        if path.startswith("/api/billing/"):
            return "financial"
        if path.startswith("/api/integrations/"):
            return "integration"
        if path == "/api/public/demo/chat":
            return "demo_chat"
        if method == "GET":
            return "general_get"
        return "general_post"

    def _now(self) -> float:
        """Get current time with Redis offset applied (G01)."""
        return time.time() + self._redis_time_offset

    def _make_key(self, category: str, identifier: str) -> str:
        raw = f"{category}\x00{identifier}"
        hash_part = hashlib.sha256(
            raw.encode("utf-8")
        ).hexdigest()[:16]
        return f"parwa:rl:{hash_part}"

    def _make_failure_key(
        self, category: str, identifier: str,
    ) -> str:
        raw = f"{category}\x00{identifier}"
        hash_part = hashlib.sha256(
            raw.encode("utf-8")
        ).hexdigest()[:16]
        return f"parwa:rl:fail:{hash_part}"

    async def sync_redis_time(self) -> None:
        """Fetch Redis TIME and compute offset for sync use.

        F-018: Use Redis server time for consistency.
        Computes offset = redis_time - local_time so that
        check_rate_limit (sync) can use time.time() + offset.
        """
        if not self._redis:
            return
        try:
            redis_time_tuple = self._redis.time()
            redis_ts = float(
                redis_time_tuple[0]
                + redis_time_tuple[1] / 1_000_000
            )
            self._redis_time_offset = redis_ts - time.time()
        except Exception:
            logger.debug("redis_time_sync_failed")

    def check_rate_limit(
        self,
        category: str,
        identifier: str,
    ) -> RateLimitResult:
        """Check if a request is allowed under rate limits.

        F-018: Uses Redis TIME offset when available.
        """
        config = self.get_category_config(category)
        limit = config["limit"]
        window = config["window"]
        key = self._make_key(category, identifier)
        now = self._now()

        # Check lockout first
        if self.is_locked_out(category, identifier):
            fail_info = self._get_failure_info(
                category, identifier
            )
            lockout_dur = config["lockout_duration"]
            retry_after = max(
                int(lockout_dur - (now - fail_info.get("locked_at", now))), 1
            )
            return RateLimitResult(
                allowed=False,
                remaining=0,
                limit=limit,
                reset_at=now + retry_after,
                retry_after=retry_after,
            )

        # Try Redis first, fallback to in-memory
        try:
            return self._check_redis(key, limit, window, now)
        except Exception:
            logger.warning(
                "rate_limit_redis_fail",
                category=category,
            )
            return self._check_in_memory(
                key, limit, window, now
            )

    def _check_redis(
        self, key: str, limit: int, window: int, now: float,
    ) -> RateLimitResult:
        if not self._redis:
            return self._check_in_memory(
                key, limit, window, now
            )
        pipe = self._redis.pipeline()
        window_key = f"{key}:win"
        pipe.zremrangebyscore(window_key, 0, now - window)
        pipe.zcard(window_key)
        pipe.zadd(window_key, {str(now): now})
        pipe.expire(window_key, window + 1)
        results = pipe.execute()
        count = results[1]
        window_start = now - window
        pipe2 = self._redis.pipeline()
        pipe2.zrangebyscore(
            window_key, window_start, now
        )
        min_results = pipe2.execute()
        if min_results:
            oldest = float(min_results[0])
            reset_at = oldest + window
        else:
            reset_at = now + window
        remaining = max(limit - count - 1, 0)
        if count >= limit:
            retry_after = max(int(reset_at - now), 1)
            return RateLimitResult(
                allowed=False,
                remaining=0,
                limit=limit,
                reset_at=reset_at,
                retry_after=retry_after,
            )
        return RateLimitResult(
            allowed=True,
            remaining=remaining,
            limit=limit,
            reset_at=reset_at,
        )

    def _check_in_memory(
        self, key: str, limit: int, window: int, now: float,
    ) -> RateLimitResult:
        if key not in self._in_memory:
            self._in_memory[key] = []
        window_start = now - window
        self._in_memory[key] = [
            ts for ts in self._in_memory[key]
            if ts > window_start
        ]
        count = len(self._in_memory[key])
        if self._in_memory[key]:
            oldest = min(self._in_memory[key])
            reset_at = oldest + window
        else:
            reset_at = now + window
        remaining = max(limit - count - 1, 0)
        if count >= limit:
            retry_after = max(int(reset_at - now), 1)
            return RateLimitResult(
                allowed=False,
                remaining=0,
                limit=limit,
                reset_at=reset_at,
                retry_after=retry_after,
            )
        self._in_memory[key].append(now)
        return RateLimitResult(
            allowed=True,
            remaining=remaining,
            limit=limit,
            reset_at=reset_at,
        )

    def record_failure(
        self, category: str, identifier: str,
    ) -> Optional[int]:
        """Record a failure and return backoff seconds.

        G01: Uses Redis time offset when available.
        """
        config = self.get_category_config(category)
        backoffs = config["backoff_seconds"]
        fail_key = self._make_failure_key(
            category, identifier
        )
        now = self._now()
        info = self._get_failure_info(category, identifier)
        count = info.get("count", 0)
        first_fail = info.get("first_fail", now)
        if now - first_fail > 3600:
            count = 0
        count += 1
        self._failures[fail_key] = {
            "count": count,
            "first_fail": first_fail,
            "last_fail": now,
            "locked_at": None,
        }
        if count < len(backoffs):
            return backoffs[count]
        lockout_dur = config["lockout_duration"]
        self._failures[fail_key]["locked_at"] = now
        return lockout_dur

    def _get_failure_info(
        self, category: str, identifier: str,
    ) -> dict:
        fail_key = self._make_failure_key(
            category, identifier
        )
        return self._failures.get(fail_key, {})

    def is_locked_out(
        self, category: str, identifier: str,
    ) -> bool:
        """Check if identifier is currently locked out.

        G01: Uses Redis time offset when available.
        """
        config = self.get_category_config(category)
        fail_key = self._make_failure_key(
            category, identifier
        )
        info = self._failures.get(fail_key)
        if not info or info.get("locked_at") is None:
            return False
        lockout_dur = config["lockout_duration"]
        now = self._now()
        if now - info["locked_at"] < lockout_dur:
            return True
        info["locked_at"] = None
        info["count"] = 0
        return False

    def reset(self, category: str, identifier: str) -> None:
        """Reset lockout and failure count."""
        fail_key = self._make_failure_key(
            category, identifier
        )
        rl_key = self._make_key(category, identifier)
        self._failures.pop(fail_key, None)
        self._in_memory.pop(rl_key, None)

    async def extract_identifier(
        self,
        category: str,
        request,
    ) -> str:
        """Extract identifier based on category scope."""
        config = self.get_category_config(category)
        scope = config["scope"]
        if scope == "email":
            return await self._extract_email(request)
        if scope == "ip":
            return self._extract_ip(request)
        if scope == "ip_hash":
            ip = self._extract_ip(request)
            return hashlib.sha256(
                ip.encode("utf-8")
            ).hexdigest()[:16]
        if scope == "api_key":
            return self._extract_api_key_id(request)
        if scope == "user":
            return self._extract_user_id(request)
        return self._extract_ip(request)

    async def _extract_email(self, request) -> str:
        try:
            body = await request.json()
        except Exception:
            body = {}
        email = body.get("email", "")
        if not email:
            email = (
                request.query_params.get("email", "")
                if hasattr(request, "query_params")
                else ""
            )
        return email.strip().lower() or "unknown"

    def _extract_ip(self, request) -> str:
        if request.client and request.client.host:
            return request.client.host
        real = request.headers.get("X-Real-IP", "")
        if real:
            return real.strip()
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return "unknown"

    def _extract_api_key_id(self, request) -> str:
        api_key = getattr(
            request.state, "api_key", None
        )
        if api_key and "id" in api_key:
            return api_key["id"]
        return "unknown"

    def _extract_user_id(self, request) -> str:
        user = getattr(
            request.state, "user", None
        )
        if user and hasattr(user, "id"):
            return user.id
        return "unknown"


# Singleton instance
rate_limit_service = RateLimitService()


def get_rate_limit_service() -> RateLimitService:
    return rate_limit_service
