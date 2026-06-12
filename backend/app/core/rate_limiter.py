"""
PARWA Phase 3 — Token Bucket Rate Limiter

Implements a token-bucket algorithm for rate-limiting outbound API calls
to third-party providers.  Provider presets encode known rate limits so
that callers can obtain a pre-configured limiter without manual tuning.

Usage
-----
    limiter = create_provider_limiter("hubspot")
    if limiter.acquire():
        response = await call_hubspot_api(...)
    else:
        # back-off or queue
        ...

    # Or wait until a token is available
    if await limiter.wait_for_token(timeout=10.0):
        response = await call_hubspot_api(...)
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Provider presets: (max_tokens, refill_rate_per_second)
# ------------------------------------------------------------------
PROVIDER_PRESETS: Dict[str, tuple[int, float]] = {
    "hubspot": (100, 10.0),
    "salesforce": (100, 5.0),
    "shopify": (40, 0.5),
    "slack": (60, 1.0),
    "stripe": (100, 25.0),
    "github": (60, 1.0),
    "zendesk": (200, 10.0),
    "twilio": (100, 10.0),
    "sendgrid": (100, 3.0),
}


class RateLimiter:
    """Token-bucket rate limiter.

    Parameters
    ----------
    max_tokens:
        Bucket capacity — maximum number of tokens that can accumulate.
    refill_rate:
        Tokens added per second.
    """

    def __init__(self, max_tokens: int, refill_rate: float) -> None:
        if max_tokens < 1:
            raise ValueError("max_tokens must be >= 1")
        if refill_rate <= 0:
            raise ValueError("refill_rate must be > 0")

        self._max_tokens = max_tokens
        self._refill_rate = refill_rate
        self._tokens: float = float(max_tokens)
        self._last_refill: float = time.monotonic()
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Internal refill
    # ------------------------------------------------------------------

    def _refill(self) -> None:
        """Add tokens elapsed since last refill (no lock — caller must hold)."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        tokens_to_add = elapsed * self._refill_rate
        self._tokens = min(self._max_tokens, self._tokens + tokens_to_add)
        self._last_refill = now

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def acquire(self, tokens: int = 1) -> bool:
        """Try to consume *tokens* from the bucket.

        Returns ``True`` if tokens were available and consumed, ``False``
        otherwise.  Does not block.
        """
        if tokens < 1:
            raise ValueError("tokens must be >= 1")
        async with self._lock:
            self._refill()
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False

    async def wait_for_token(self, timeout: float = 30.0) -> bool:
        """Block until at least one token is available or *timeout* elapses.

        Returns ``True`` if a token was acquired, ``False`` on timeout.
        """
        if timeout <= 0:
            return await self.acquire()

        deadline = time.monotonic() + timeout
        while True:
            if await self.acquire():
                return True

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False

            # Sleep for a small fraction to avoid busy-waiting
            wait_time = min(0.1, remaining / self._refill_rate)
            if wait_time <= 0:
                wait_time = 0.01
            await asyncio.sleep(wait_time)

    async def get_remaining(self) -> int:
        """Return the current number of available tokens (floor)."""
        async with self._lock:
            self._refill()
            return int(self._tokens)

    @property
    def max_tokens(self) -> int:
        return self._max_tokens

    @property
    def refill_rate(self) -> float:
        return self._refill_rate


def create_provider_limiter(provider: str) -> RateLimiter:
    """Factory that returns a :class:`RateLimiter` configured for *provider*.

    Uses the preset values from :data:`PROVIDER_PRESETS`.  Falls back to
    conservative defaults (10 tokens, 1/s) for unknown providers.

    Parameters
    ----------
    provider:
        Case-insensitive provider name (e.g. ``"hubspot"``).

    Returns
    -------
    RateLimiter
    """
    try:
        key = provider.lower().strip()
        if key in PROVIDER_PRESETS:
            max_tokens, refill_rate = PROVIDER_PRESETS[key]
            logger.info(
                "Creating rate limiter for %s: %d tokens, %.1f/s",
                key,
                max_tokens,
                refill_rate,
            )
            return RateLimiter(max_tokens=max_tokens, refill_rate=refill_rate)

        logger.warning(
            "No preset for provider '%s' — using conservative defaults", provider
        )
        return RateLimiter(max_tokens=10, refill_rate=1.0)
    except Exception as exc:
        logger.error("Failed to create provider limiter for %s: %s", provider, exc)
        return RateLimiter(max_tokens=10, refill_rate=1.0)
