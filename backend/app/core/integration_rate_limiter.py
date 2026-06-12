"""
Per-Integration Rate Limiter (Phase 10: Rate Limiting & Error Handling)

Tracks API calls per integration per company_id (BC-001) with configurable
rate limits using a sliding window counter for both per-minute and per-second
granularity.

Features:
- Per-integration configurable rate limits (requests_per_minute, requests_per_second)
- Sliding window counters with automatic expiry
- Thread-safe via RLock
- Polite throttling: wait_for_quota() blocks until quota available
- Background cleanup thread removes expired counters every 60 seconds
- Falls back to "custom" rate limits for unknown integrations

BC-001: Every counter scoped by company_id.
BC-008: Never crash — all public methods wrapped in try/except.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.logger import get_logger

logger = get_logger("integration_rate_limiter")


# ══════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════


DEFAULT_RATE_LIMITS: Dict[str, Dict[str, int]] = {
    "hubspot": {"requests_per_minute": 100, "requests_per_second": 10},
    "shopify": {"requests_per_minute": 120, "requests_per_second": 4},
    "salesforce": {"requests_per_minute": 100, "requests_per_second": 5},
    "slack": {"requests_per_minute": 60, "requests_per_second": 1},
    "twilio": {"requests_per_minute": 60, "requests_per_second": 1},
    "brevo": {"requests_per_minute": 60, "requests_per_second": 10},
    "custom": {"requests_per_minute": 30, "requests_per_second": 2},
}


@dataclass
class WindowCounter:
    """Sliding window counter for a single time granularity."""

    limit: int
    window_seconds: int
    timestamps: List[float] = field(default_factory=list)

    def record(self, now: float) -> None:
        """Record a call at the given time."""
        self._expire(now)
        self.timestamps.append(now)

    def count(self, now: float) -> int:
        """Return current count within the window."""
        self._expire(now)
        return len(self.timestamps)

    def is_limited(self, now: float) -> bool:
        """Return True if the rate limit is exceeded."""
        return self.count(now) >= self.limit

    def _expire(self, now: float) -> None:
        """Remove timestamps outside the sliding window."""
        cutoff = now - self.window_seconds
        # Optimized: timestamps are in order, find first valid index
        idx = 0
        for i, ts in enumerate(self.timestamps):
            if ts >= cutoff:
                idx = i
                break
        else:
            idx = len(self.timestamps)
        if idx > 0:
            self.timestamps = self.timestamps[idx:]

    def clear(self) -> None:
        """Clear all counters (used on disconnect)."""
        self.timestamps.clear()


@dataclass
class IntegrationCounters:
    """Per-integration rate limit counters for a single company."""

    per_minute: WindowCounter
    per_second: WindowCounter

    def clear(self) -> None:
        """Clear all counters."""
        self.per_minute.clear()
        self.per_second.clear()


# ══════════════════════════════════════════════════════════════════
# INTEGRATION RATE LIMITER
# ══════════════════════════════════════════════════════════════════


class IntegrationRateLimiter:
    """Per-integration, per-company rate limiter with sliding windows.

    Usage:
        limiter = IntegrationRateLimiter()
        if limiter.check_rate_limit("twilio", "comp_123"):
            # proceed with API call
        else:
            # rate limited — retry later
    """

    def __init__(
        self,
        rate_limits: Optional[Dict[str, Dict[str, int]]] = None,
    ) -> None:
        self._rate_limits = rate_limits or DEFAULT_RATE_LIMITS.copy()
        # Key: (integration_name, company_id) -> IntegrationCounters
        self._counters: Dict[Tuple[str, str], IntegrationCounters] = {}
        self._lock = threading.RLock()
        self._stopped = False

        # Background cleanup thread
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            name="rate_limiter_cleanup",
            daemon=True,
        )
        self._cleanup_thread.start()

    def _get_limits(self, integration_name: str) -> Dict[str, int]:
        """Get rate limits for an integration, falling back to 'custom'."""
        return self._rate_limits.get(
            integration_name,
            self._rate_limits.get("custom", DEFAULT_RATE_LIMITS["custom"]),
        )

    def _get_or_create_counters(
        self, integration_name: str, company_id: str,
    ) -> IntegrationCounters:
        """Get or create counters for an integration+company pair."""
        key = (integration_name, company_id)
        if key not in self._counters:
            limits = self._get_limits(integration_name)
            self._counters[key] = IntegrationCounters(
                per_minute=WindowCounter(
                    limit=limits["requests_per_minute"],
                    window_seconds=60,
                ),
                per_second=WindowCounter(
                    limit=limits["requests_per_second"],
                    window_seconds=1,
                ),
            )
        return self._counters[key]

    def check_rate_limit(self, integration_name: str, company_id: str) -> bool:
        """Check if a call is allowed under the rate limit.

        Returns True if allowed, False if rate limited.
        Does NOT consume quota — call record_call() after a successful check.
        """
        try:
            with self._lock:
                now = time.time()
                counters = self._get_or_create_counters(integration_name, company_id)
                if counters.per_second.is_limited(now):
                    logger.debug(
                        "rate_limited_per_second integration=%s company=%s count=%d limit=%d",
                        integration_name, company_id,
                        counters.per_second.count(now), counters.per_second.limit,
                    )
                    return False
                if counters.per_minute.is_limited(now):
                    logger.debug(
                        "rate_limited_per_minute integration=%s company=%s count=%d limit=%d",
                        integration_name, company_id,
                        counters.per_minute.count(now), counters.per_minute.limit,
                    )
                    return False
                return True
        except Exception:
            logger.exception(
                "rate_limit_check_failed integration=%s company=%s",
                integration_name, company_id,
            )
            return True  # BC-008: Allow on error

    def record_call(self, integration_name: str, company_id: str) -> None:
        """Record that a call was made (consumes quota)."""
        try:
            with self._lock:
                now = time.time()
                counters = self._get_or_create_counters(integration_name, company_id)
                counters.per_minute.record(now)
                counters.per_second.record(now)
        except Exception:
            logger.exception(
                "rate_limit_record_failed integration=%s company=%s",
                integration_name, company_id,
            )

    def wait_for_quota(
        self, integration_name: str, company_id: str, timeout: float = 30.0,
    ) -> bool:
        """Block until quota is available or timeout expires.

        Returns True if quota became available, False if timed out.
        Uses polite polling with short sleeps.
        """
        deadline = time.time() + timeout
        poll_interval = 0.1  # 100ms polling

        while time.time() < deadline:
            try:
                if self.check_rate_limit(integration_name, company_id):
                    return True
            except Exception:
                return True  # BC-008: Allow on error

            remaining = deadline - time.time()
            if remaining <= 0:
                break

            time.sleep(min(poll_interval, remaining))

        logger.warning(
            "wait_for_quota_timeout integration=%s company=%s timeout=%.1fs",
            integration_name, company_id, timeout,
        )
        return False

    def get_rate_limit_status(
        self, integration_name: str, company_id: str,
    ) -> Dict[str, Any]:
        """Return current rate limit usage stats for an integration+company."""
        try:
            with self._lock:
                now = time.time()
                limits = self._get_limits(integration_name)
                key = (integration_name, company_id)
                if key in self._counters:
                    counters = self._counters[key]
                    minute_count = counters.per_minute.count(now)
                    second_count = counters.per_second.count(now)
                else:
                    minute_count = 0
                    second_count = 0

                return {
                    "integration": integration_name,
                    "company_id": company_id,
                    "requests_per_minute_limit": limits["requests_per_minute"],
                    "requests_per_second_limit": limits["requests_per_second"],
                    "current_minute_count": minute_count,
                    "current_second_count": second_count,
                    "minute_remaining": max(0, limits["requests_per_minute"] - minute_count),
                    "second_remaining": max(0, limits["requests_per_second"] - second_count),
                    "is_limited": minute_count >= limits["requests_per_minute"]
                                  or second_count >= limits["requests_per_second"],
                }
        except Exception:
            logger.exception(
                "get_rate_limit_status_failed integration=%s company=%s",
                integration_name, company_id,
            )
            return {
                "integration": integration_name,
                "company_id": company_id,
                "error": "Failed to retrieve rate limit status",
            }

    def clear_integration(self, integration_name: str, company_id: str) -> None:
        """Clear all rate limit counters for an integration+company.

        Used when an integration is disconnected.
        """
        try:
            with self._lock:
                key = (integration_name, company_id)
                if key in self._counters:
                    self._counters[key].clear()
                    logger.info(
                        "rate_limit_cleared integration=%s company=%s",
                        integration_name, company_id,
                    )
        except Exception:
            logger.exception(
                "rate_limit_clear_failed integration=%s company=%s",
                integration_name, company_id,
            )

    def update_rate_limit(
        self, integration_name: str,
        requests_per_minute: int,
        requests_per_second: int,
    ) -> None:
        """Update rate limits for an integration type.

        Note: This updates the template for future counters. Existing counters
        retain their old limits until they expire and are recreated.
        """
        try:
            with self._lock:
                self._rate_limits[integration_name] = {
                    "requests_per_minute": requests_per_minute,
                    "requests_per_second": requests_per_second,
                }
                logger.info(
                    "rate_limit_updated integration=%s rpm=%d rps=%d",
                    integration_name, requests_per_minute, requests_per_second,
                )
        except Exception:
            logger.exception(
                "rate_limit_update_failed integration=%s", integration_name,
            )

    def get_all_status(self, company_id: str) -> Dict[str, Any]:
        """Get rate limit status for all integrations for a company."""
        try:
            with self._lock:
                now = time.time()
                result = {}
                for (intg, cid), counters in self._counters.items():
                    if cid != company_id:
                        continue
                    limits = self._get_limits(intg)
                    minute_count = counters.per_minute.count(now)
                    second_count = counters.per_second.count(now)
                    result[intg] = {
                        "requests_per_minute_limit": limits["requests_per_minute"],
                        "requests_per_second_limit": limits["requests_per_second"],
                        "current_minute_count": minute_count,
                        "current_second_count": second_count,
                        "is_limited": minute_count >= limits["requests_per_minute"]
                                      or second_count >= limits["requests_per_second"],
                    }
                return result
        except Exception:
            logger.exception("get_all_status_failed company=%s", company_id)
            return {}

    # ── Background Cleanup ──────────────────────────────────────────

    def _cleanup_loop(self) -> None:
        """Remove expired counters every 60 seconds."""
        while not self._stopped:
            time.sleep(60)
            try:
                self._cleanup()
            except Exception:
                logger.exception("rate_limiter_cleanup_failed")

    def _cleanup(self) -> None:
        """Remove counters with no recent activity."""
        with self._lock:
            now = time.time()
            stale_keys = []
            for key, counters in self._counters.items():
                # If both windows are empty, the counter is stale
                if not counters.per_minute.timestamps and not counters.per_second.timestamps:
                    stale_keys.append(key)

            for key in stale_keys:
                del self._counters[key]

            if stale_keys:
                logger.debug(
                    "rate_limiter_cleanup removed=%d remaining=%d",
                    len(stale_keys), len(self._counters),
                )

    def stop(self) -> None:
        """Stop the background cleanup thread."""
        self._stopped = True


# ══════════════════════════════════════════════════════════════════
# SINGLETON
# ══════════════════════════════════════════════════════════════════

_instance: Optional[IntegrationRateLimiter] = None
_instance_lock = threading.Lock()


def get_integration_rate_limiter() -> IntegrationRateLimiter:
    """Get the singleton IntegrationRateLimiter instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = IntegrationRateLimiter()
                logger.info("integration_rate_limiter_initialized")
    return _instance


def reset_integration_rate_limiter() -> None:
    """Reset the singleton instance (for testing only)."""
    global _instance
    with _instance_lock:
        if _instance is not None:
            _instance.stop()
        _instance = None
