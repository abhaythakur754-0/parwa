"""Rate limiter for PARWA LLM and API calls.

Token bucket rate limiter to prevent overwhelming external APIs.
Thread-safe implementation for concurrent ticket processing.
"""

from __future__ import annotations

import threading
import time
from typing import Any


class RateLimiter:
    """Token bucket rate limiter.

    Allows up to `rate` requests per `period` seconds.
    Bursts up to `capacity` requests are allowed, then throttled.

    Example:
        limiter = RateLimiter(rate=10, period=60)  # 10 requests per minute
        limiter.acquire()  # blocks until a token is available
        result = llm.invoke(prompt)
    """

    def __init__(
        self,
        rate: float = 10.0,
        period: float = 60.0,
        capacity: int | None = None,
    ) -> None:
        """Initialize the rate limiter.

        Args:
            rate: Number of requests allowed per period.
            period: Time period in seconds.
            capacity: Maximum burst size (defaults to rate).
        """
        self.rate = rate
        self.period = period
        self.capacity = capacity or int(rate)
        self._tokens: float = float(self.capacity)
        self._last_refill: float = time.monotonic()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        tokens_to_add = (elapsed / self.period) * self.rate
        self._tokens = min(self.capacity, self._tokens + tokens_to_add)
        self._last_refill = now

    def acquire(self, timeout: float | None = None) -> bool:
        """Acquire a token, blocking if necessary.

        Args:
            timeout: Maximum time to wait in seconds. None = wait forever.

        Returns:
            True if token acquired, False if timed out.
        """
        deadline = None
        if timeout is not None:
            deadline = time.monotonic() + timeout

        while True:
            with self._lock:
                self._refill()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return True

            # No token available — wait a bit
            if deadline is not None and time.monotonic() >= deadline:
                return False

            wait_time = min(0.1, self.period / self.rate) if self.rate > 0 else 0.1
            time.sleep(wait_time)

    def try_acquire(self) -> bool:
        """Try to acquire a token without blocking.

        Returns:
            True if token acquired immediately, False otherwise.
        """
        with self._lock:
            self._refill()
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return True
            return False

    @property
    def available_tokens(self) -> float:
        """Current number of available tokens (approximate)."""
        with self._lock:
            self._refill()
            return self._tokens


# Global rate limiters for different API types
_llm_limiter: RateLimiter | None = None
_api_limiter: RateLimiter | None = None


def get_llm_rate_limiter() -> RateLimiter:
    """Get or create the global LLM rate limiter.

    Default: 60 requests per minute (1 per second) with burst of 10.
    Configurable via PARWA_LLM_RATE and PARWA_LLM_PERIOD env vars.
    """
    global _llm_limiter
    if _llm_limiter is None:
        import os
        rate = float(os.getenv("PARWA_LLM_RATE", "60"))
        period = float(os.getenv("PARWA_LLM_PERIOD", "60"))
        _llm_limiter = RateLimiter(rate=rate, period=period, capacity=10)
    return _llm_limiter


def get_api_rate_limiter() -> RateLimiter:
    """Get or create the global API rate limiter.

    Default: 120 requests per minute (2 per second) with burst of 20.
    Configurable via PARWA_API_RATE and PARWA_API_PERIOD env vars.
    """
    global _api_limiter
    if _api_limiter is None:
        import os
        rate = float(os.getenv("PARWA_API_RATE", "120"))
        period = float(os.getenv("PARWA_API_PERIOD", "60"))
        _api_limiter = RateLimiter(rate=rate, period=period, capacity=20)
    return _api_limiter
