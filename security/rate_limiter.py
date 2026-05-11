"""
PARWA Rate Limiter (BC-011 / BC-012)

Sliding window rate limiting with progressive lockout.
Redis-backed but fails OPEN when Redis is down (BC-011).

Key behaviors:
- Per-company_id rate limiting (BC-001)
- Sliding window (not fixed window) for accuracy
- Progressive lockout: repeated violations increase cooldown
- Redis failure -> allow all requests (fail-open, BC-011)
- X-RateLimit headers set on every response (BC-012)
- L-04 FIX: Periodic cleanup of stale rate limit entries
"""

import enum
import hashlib
import threading
import time
from typing import Optional

from backend.app.logger import get_logger

logger = get_logger("rate_limiter")

# L-04: Interval between automatic cleanup sweeps (seconds)
CLEANUP_INTERVAL_SECONDS = 300  # 5 minutes


class LockoutLevel(enum.IntEnum):
    """Progressive lockout levels - cooldown doubles each time."""

    NONE = 0       # No lockout
    LEVEL_1 = 1    # 60 seconds
    LEVEL_2 = 2    # 120 seconds
    LEVEL_3 = 3    # 240 seconds
    LEVEL_4 = 4    # 480 seconds
    LEVEL_5 = 5    # 900 seconds (15 minutes, max)


# Cooldown durations in seconds per lockout level
LOCKOUT_DURATIONS = {
    LockoutLevel.NONE: 0,
    LockoutLevel.LEVEL_1: 60,
    LockoutLevel.LEVEL_2: 120,
    LockoutLevel.LEVEL_3: 240,
    LockoutLevel.LEVEL_4: 480,
    LockoutLevel.LEVEL_5: 900,
}

# Default rate limits
DEFAULT_REQUESTS_PER_WINDOW = 100
DEFAULT_WINDOW_SECONDS = 60

# Redis key prefix
RATE_LIMIT_PREFIX = "parwa:ratelimit:"


class RateLimitResult:
    """Result of a rate limit check."""

    def __init__(
        self,
        allowed: bool,
        remaining: int,
        limit: int,
        reset_at: float,
        lockout_level: int = 0,
        retry_after: Optional[int] = None,
    ):
        self.allowed = allowed
        self.remaining = remaining
        self.limit = limit
        self.reset_at = reset_at
        self.lockout_level = lockout_level
        self.retry_after = retry_after  # seconds until lockout expires

    def to_headers(self) -> dict:
        """Generate X-RateLimit-* headers (BC-012)."""
        headers = {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(max(self.remaining, 0)),
            "X-RateLimit-Reset": str(int(self.reset_at)),
        }
        if self.retry_after is not None:
            headers["Retry-After"] = str(self.retry_after)
        return headers


class SlidingWindowCounter:
    """In-memory sliding window rate limiter.

    In production, this will be replaced with Redis-backed implementation.
    The interface is identical so switching is transparent.
    BC-011: Rate limiting per company_id (BC-001 tenant isolation).

    L-04 FIX: Adds periodic cleanup of stale entries to prevent
    unbounded memory growth from abandoned clients.
    """

    def __init__(
        self,
        requests_per_window: int = DEFAULT_REQUESTS_PER_WINDOW,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
    ):
        self.requests_per_window = requests_per_window
        self.window_seconds = window_seconds
        # In-memory store: {key: [(timestamp, count)]}
        self._windows: dict = {}
        self._lock = threading.Lock()

    def check_rate_limit(
        self,
        company_id: str,
        client_ip: str = "",
    ) -> RateLimitResult:
        """Check if a request is allowed under the rate limit.

        Uses sliding window algorithm:
        - Maintain windows of `window_seconds` length
        - Count requests in the current window
        - If count >= limit, reject

        Args:
            company_id: Tenant ID (BC-001 - tenant-isolated limits).
            client_ip: Client IP for additional granularity.

        Returns:
            RateLimitResult with allowed/denied status and header values.
        """
        now = time.time()
        key = self._make_key(company_id, client_ip)
        window_start = now - self.window_seconds

        with self._lock:
            # Get existing windows for this key
            if key not in self._windows:
                self._windows[key] = []

            # Clean up expired windows
            self._windows[key] = [
                (ts, count) for ts, count in self._windows[key]
                if ts > window_start
            ]

            # Count requests in current window
            total_requests = sum(count for _, count in self._windows[key])

        # Calculate reset time
        if self._windows[key]:
            oldest = min(ts for ts, _ in self._windows[key])
            reset_at = oldest + self.window_seconds
        else:
            reset_at = now + self.window_seconds

        remaining = max(self.requests_per_window - total_requests, 0)

        if total_requests >= self.requests_per_window:
            # Rate limited
            retry_after = max(int(reset_at - now), 1)
            return RateLimitResult(
                allowed=False,
                remaining=0,
                limit=self.requests_per_window,
                reset_at=reset_at,
                retry_after=retry_after,
            )

        # Record this request
        with self._lock:
            self._windows[key].append((now, 1))

        return RateLimitResult(
            allowed=True,
            remaining=remaining - 1,
            limit=self.requests_per_window,
            reset_at=reset_at,
        )

    def _make_key(self, company_id: str, client_ip: str) -> str:
        """Build rate limit key with company_id namespace (BC-001).

        Uses SHA-256 hash of combined parts to guarantee
        no collision, even if company_id or client_ip contain
        special characters. BC-001: Tenant-isolated rate limiting.
        """
        raw = f"{company_id}\x00{client_ip}"
        hash_part = hashlib.sha256(
            raw.encode("utf-8")
        ).hexdigest()[:16]
        return f"{RATE_LIMIT_PREFIX}{hash_part}"

    def cleanup_stale_entries(self) -> int:
        """Remove expired entries from all windows.

        L-04 FIX: Prevents unbounded memory growth from abandoned
        clients. Should be called periodically (e.g. every 5 minutes).

        Returns:
            Number of entries removed.
        """
        removed = 0
        now = time.time()
        cutoff = now - self.window_seconds

        with self._lock:
            stale_keys = []
            for key, entries in self._windows.items():
                # Filter expired entries
                before = len(entries)
                self._windows[key] = [
                    (ts, count) for ts, count in entries
                    if ts > cutoff
                ]
                after = len(self._windows[key])
                removed += before - after

                # Remove empty keys entirely
                if not self._windows[key]:
                    stale_keys.append(key)

            for key in stale_keys:
                del self._windows[key]

        if removed > 0:
            logger.debug(
                "rate_limiter_cleanup: removed %d stale entries, "
                "%d empty keys",
                removed, len(stale_keys),
            )

        return removed


class ProgressiveLockout:
    """Progressive lockout for repeated rate limit violations.

    Each time a client hits the rate limit, the lockout level increases.
    The cooldown period doubles with each level
    (60s -> 120s -> 240s -> 480s -> 900s).
    After a successful request within the window, the lockout resets.

    BC-011: Not just a flat rate limit - progressive enforcement.
    """

    def __init__(self, max_level: int = 5, decay_seconds: float = 300):
        self.max_level = max_level
        self.decay_seconds = decay_seconds
        # In-memory store: {key: {"level": int, "last_violation": float}}
        self._violations: dict = {}

    def record_violation(
        self, company_id: str, client_ip: str = ""
    ) -> int:
        """Record a rate limit violation and return the lockout level.

        Args:
            company_id: Tenant ID (BC-001).
            client_ip: Client IP for granularity.

        Returns:
            Lockout level (0-5).
        """
        key = self._make_key(company_id, client_ip)
        now = time.time()

        if key not in self._violations:
            self._violations[key] = {
                "level": 0,
                "last_violation": 0,
            }

        record = self._violations[key]

        # Reset if enough time has passed since last violation
        if now - record["last_violation"] > self.decay_seconds:
            record["level"] = 0

        # Increase lockout level
        record["level"] = min(record["level"] + 1, self.max_level)
        record["last_violation"] = now

        return record["level"]

    def get_lockout_remaining(
        self, company_id: str, client_ip: str = ""
    ) -> int:
        """Get remaining lockout time in seconds.

        Args:
            company_id: Tenant ID (BC-001).
            client_ip: Client IP.

        Returns:
            Seconds remaining in lockout (0 if not locked out).
        """
        key = self._make_key(company_id, client_ip)

        if key not in self._violations:
            return 0

        record = self._violations[key]
        level = LockoutLevel(record["level"])

        if level == LockoutLevel.NONE:
            return 0

        cooldown = LOCKOUT_DURATIONS.get(level, 0)
        if cooldown == 0:
            return 0

        elapsed = time.time() - record["last_violation"]
        remaining = cooldown - elapsed

        if remaining <= 0:
            # Lockout expired - reset level
            record["level"] = LockoutLevel.NONE
            return 0

        return int(remaining)

    def is_locked_out(
        self, company_id: str, client_ip: str = ""
    ) -> bool:
        """Check if a client is currently locked out."""
        return self.get_lockout_remaining(company_id, client_ip) > 0

    def reset(self, company_id: str, client_ip: str = "") -> None:
        """Reset lockout level for a client."""
        key = self._make_key(company_id, client_ip)
        if key in self._violations:
            self._violations[key]["level"] = LockoutLevel.NONE

    def cleanup_stale_entries(self) -> int:
        """Remove expired violation records.

        L-04 FIX: Prevents memory leaks from old lockout records.

        Returns:
            Number of entries removed.
        """
        removed = 0
        now = time.time()

        stale_keys = []
        for key, record in self._violations.items():
            if now - record["last_violation"] > self.decay_seconds * 3:
                stale_keys.append(key)

        for key in stale_keys:
            del self._violations[key]
            removed += 1

        return removed

    def _make_key(self, company_id: str, client_ip: str) -> str:
        """Build lockout key using SHA-256 hash (BC-001)."""
        raw = f"{company_id}\x00{client_ip}"
        hash_part = hashlib.sha256(
            raw.encode("utf-8")
        ).hexdigest()[:16]
        return f"{RATE_LIMIT_PREFIX}lockout:{hash_part}"


class RateLimiter:
    """Combined rate limiter with sliding window + progressive lockout.

    BC-011: Fails OPEN when Redis is down.
    BC-001: Per-company_id isolation.
    BC-012: X-RateLimit headers on every response.
    L-04: Periodic cleanup of stale entries.
    """

    def __init__(
        self,
        requests_per_window: int = DEFAULT_REQUESTS_PER_WINDOW,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
        max_lockout_level: int = 5,
    ):
        self.window = SlidingWindowCounter(
            requests_per_window=requests_per_window,
            window_seconds=window_seconds,
        )
        self.lockout = ProgressiveLockout(
            max_level=max_lockout_level
        )
        # L-04: Start background cleanup thread
        self._cleanup_thread: Optional[threading.Thread] = None
        self._cleanup_stop = threading.Event()
        self._start_cleanup_thread()

    def _start_cleanup_thread(self) -> None:
        """Start a daemon thread that periodically cleans up stale entries."""
        if self._cleanup_thread is not None:
            return

        def _cleanup_loop():
            while not self._cleanup_stop.wait(CLEANUP_INTERVAL_SECONDS):
                try:
                    w = self.window.cleanup_stale_entries()
                    l = self.lockout.cleanup_stale_entries()
                    if w > 0 or l > 0:
                        logger.info(
                            "periodic_cleanup: window=%d lockout=%d",
                            w, l,
                        )
                except Exception as exc:
                    logger.error(
                        "periodic_cleanup_error: %s", exc,
                    )

        self._cleanup_thread = threading.Thread(
            target=_cleanup_loop,
            daemon=True,
            name="rate-limiter-cleanup",
        )
        self._cleanup_thread.start()
        logger.info(
            "rate_limiter_cleanup_thread_started: interval=%ds",
            CLEANUP_INTERVAL_SECONDS,
        )

    def stop_cleanup(self) -> None:
        """Stop the cleanup thread. Call on shutdown."""
        self._cleanup_stop.set()
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5)

    def check(
        self,
        company_id: str,
        client_ip: str = "",
    ) -> RateLimitResult:
        """Check if a request is allowed.

        First checks lockout status, then sliding window rate limit.
        If rate limited, records a violation for progressive lockout.

        Args:
            company_id: Tenant ID (BC-001).
            client_ip: Client IP.

        Returns:
            RateLimitResult with allowed status and header values.
        """
        # Check progressive lockout first
        if self.lockout.is_locked_out(company_id, client_ip):
            remaining = self.lockout.get_lockout_remaining(
                company_id, client_ip
            )
            lockout_key = self.lockout._make_key(
                company_id, client_ip
            )
            level = self.lockout._violations.get(
                lockout_key, {}
            ).get("level", 1)
            return RateLimitResult(
                allowed=False,
                remaining=0,
                limit=self.window.requests_per_window,
                reset_at=time.time() + remaining,
                lockout_level=level,
                retry_after=remaining,
            )

        # Check sliding window
        result = self.window.check_rate_limit(company_id, client_ip)

        if not result.allowed:
            # Record violation for progressive lockout
            level = self.lockout.record_violation(
                company_id, client_ip
            )
            result.lockout_level = level

        return result
