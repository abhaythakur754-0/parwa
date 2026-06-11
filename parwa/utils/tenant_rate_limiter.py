"""Per-tenant rate limiter for PARWA.

Extends the global rate limiter with per-tenant (per-variant) rate limits.
This prevents a single tenant from exhausting the entire rate budget
and ensures fair resource allocation across variants.

Variant-based limits:
- Mini: 10 requests/min (basic tier)
- PARWA: 30 requests/min (standard tier)
- High: 60 requests/min (premium tier)

Uses the existing token bucket implementation from rate_limiter.py.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from parwa.utils.rate_limiter import RateLimiter

logger = logging.getLogger("parwa.tenant_rate_limiter")


# ─── Per-variant rate limits ────────────────────────────────────────────────────
# These are the DEFAULT limits. Override with env vars for production.
VARIANT_RATE_LIMITS: dict[str, dict[str, float]] = {
    "mini": {
        "rate": 10.0,       # 10 requests
        "period": 60.0,     # per minute
        "capacity": 5,      # burst of 5
    },
    "parwa": {
        "rate": 30.0,       # 30 requests
        "period": 60.0,     # per minute
        "capacity": 15,     # burst of 15
    },
    "high": {
        "rate": 60.0,       # 60 requests
        "period": 60.0,     # per minute
        "capacity": 30,     # burst of 30
    },
}


class TenantRateLimiter:
    """Per-tenant rate limiter that tracks limits by tenant_id and variant.

    Each tenant gets their own RateLimiter instance based on their variant.
    This ensures that:
    1. A single tenant can't exceed their variant's limits
    2. Different variants get different rate limits
    3. One tenant's usage doesn't affect another tenant's limits

    Example:
        limiter = TenantRateLimiter()
        limiter.acquire("tenant_abc", "parwa")  # blocks if tenant_abc at limit
        limiter.acquire("tenant_xyz", "mini")   # independent limit
    """

    def __init__(
        self,
        variant_limits: dict[str, dict[str, float]] | None = None,
    ) -> None:
        """Initialize the tenant rate limiter.

        Args:
            variant_limits: Override default variant rate limits.
                Format: {"mini": {"rate": 10, "period": 60, "capacity": 5}}
        """
        self._limits = variant_limits or VARIANT_RATE_LIMITS
        self._limiters: dict[str, RateLimiter] = {}
        self._lock = threading.Lock()
        self._last_cleanup: float = time.monotonic()

    def _get_limiter(self, tenant_id: str, variant: str) -> RateLimiter:
        """Get or create a rate limiter for a specific tenant+variant.

        Args:
            tenant_id: The tenant identifier.
            variant: The PARWA variant (mini, parwa, high).

        Returns:
            A RateLimiter instance for this tenant+variant combo.
        """
        key = f"{tenant_id}:{variant}"

        if key not in self._limiters:
            # Get rate limits for this variant
            config = self._limits.get(variant, self._limits.get("parwa", {
                "rate": 30.0, "period": 60.0, "capacity": 15,
            }))

            self._limiters[key] = RateLimiter(
                rate=config["rate"],
                period=config["period"],
                capacity=int(config.get("capacity", config["rate"])),
            )
            logger.debug(
                "tenant_rate_limiter: created limiter for tenant=%s variant=%s "
                "(rate=%.0f/%.0fs, capacity=%d)",
                tenant_id, variant, config["rate"], config["period"],
                int(config.get("capacity", config["rate"])),
            )

        return self._limiters[key]

    def acquire(
        self,
        tenant_id: str,
        variant: str = "parwa",
        timeout: float | None = None,
    ) -> bool:
        """Acquire a token for a tenant (sync, blocking).

        Args:
            tenant_id: The tenant identifier.
            variant: The PARWA variant.
            timeout: Maximum seconds to wait. None = wait forever.

        Returns:
            True if token acquired, False if timed out.
        """
        limiter = self._get_limiter(tenant_id, variant)
        acquired = limiter.acquire(timeout=timeout)

        if not acquired:
            logger.warning(
                "tenant_rate_limiter: tenant=%s variant=%s rate limited (timeout)",
                tenant_id, variant,
            )

        # Periodic cleanup of stale limiters
        self._maybe_cleanup()

        return acquired

    async def async_acquire(
        self,
        tenant_id: str,
        variant: str = "parwa",
        timeout: float | None = None,
    ) -> bool:
        """Acquire a token for a tenant (async, non-blocking).

        Args:
            tenant_id: The tenant identifier.
            variant: The PARWA variant.
            timeout: Maximum seconds to wait. None = wait forever.

        Returns:
            True if token acquired, False if timed out.
        """
        limiter = self._get_limiter(tenant_id, variant)
        acquired = await limiter.async_acquire(timeout=timeout)

        if not acquired:
            logger.warning(
                "tenant_rate_limiter: tenant=%s variant=%s rate limited (async timeout)",
                tenant_id, variant,
            )

        self._maybe_cleanup()

        return acquired

    def try_acquire(self, tenant_id: str, variant: str = "parwa") -> bool:
        """Try to acquire a token without blocking.

        Returns:
            True if token acquired immediately, False otherwise.
        """
        limiter = self._get_limiter(tenant_id, variant)
        return limiter.try_acquire()

    def get_tenant_usage(self, tenant_id: str, variant: str = "parwa") -> dict[str, Any]:
        """Get rate limit usage info for a tenant.

        Returns:
            Dict with available_tokens, rate, period, capacity.
        """
        key = f"{tenant_id}:{variant}"
        if key not in self._limiters:
            return {"available_tokens": 0, "active": False}

        limiter = self._limiters[key]
        return {
            "available_tokens": limiter.available_tokens,
            "rate": limiter.rate,
            "period": limiter.period,
            "capacity": limiter.capacity,
            "active": True,
        }

    def _maybe_cleanup(self, max_age: float = 3600.0) -> None:
        """Periodically remove stale tenant limiters.

        Args:
            max_age: Seconds after which inactive limiters are removed.
        """
        now = time.monotonic()
        if now - self._last_cleanup < 300:  # Check every 5 minutes
            return

        with self._lock:
            # Re-check after acquiring lock
            if now - self._last_cleanup < 300:
                return

            # Remove limiters with full capacity (completely unused)
            stale_keys = []
            for key, limiter in self._limiters.items():
                if limiter.available_tokens >= limiter.capacity:
                    stale_keys.append(key)

            for key in stale_keys:
                del self._limiters[key]

            if stale_keys:
                logger.debug(
                    "tenant_rate_limiter: cleaned up %d stale limiters",
                    len(stale_keys),
                )

            self._last_cleanup = now


# ─── Global tenant rate limiter ──────────────────────────────────────────────────

_tenant_limiter: TenantRateLimiter | None = None


def get_tenant_rate_limiter() -> TenantRateLimiter:
    """Get or create the global tenant rate limiter."""
    global _tenant_limiter
    if _tenant_limiter is None:
        _tenant_limiter = TenantRateLimiter()
    return _tenant_limiter
