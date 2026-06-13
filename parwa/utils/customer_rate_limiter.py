"""Per-customer rate limiting to prevent abuse.

Month 4 production hardening: Limits how many tickets a customer can submit
in a given time window. Prevents spam/abuse while allowing legitimate
high-volume customers.
"""
from __future__ import annotations

import time
import threading
from typing import Any


class CustomerRateLimiter:
    """Rate limiter that tracks per-customer ticket submission rates.

    Default limits:
    - 10 tickets per hour per customer
    - 50 tickets per day per customer
    - Enterprise customers get 3x limits
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hourly: dict[str, list[float]] = {}  # customer_id -> list of timestamps
        self._daily: dict[str, list[float]] = {}
        self._hourly_limit = 10
        self._daily_limit = 50
        self._enterprise_multiplier = 3

    def check_rate(self, customer_id: str, customer_tier: str = "standard") -> tuple[bool, str]:
        """Check if customer can submit another ticket.

        Returns (allowed, reason_if_blocked).
        """
        now = time.monotonic()
        hour_ago = now - 3600
        day_ago = now - 86400

        hourly_limit = self._hourly_limit
        daily_limit = self._daily_limit
        if customer_tier in ("enterprise", "vip"):
            hourly_limit *= self._enterprise_multiplier
            daily_limit *= self._enterprise_multiplier

        with self._lock:
            # Clean old entries
            self._hourly.setdefault(customer_id, [])
            self._daily.setdefault(customer_id, [])
            self._hourly[customer_id] = [t for t in self._hourly[customer_id] if t > hour_ago]
            self._daily[customer_id] = [t for t in self._daily[customer_id] if t > day_ago]

            if len(self._hourly[customer_id]) >= hourly_limit:
                return False, f"Hourly limit reached ({hourly_limit} tickets/hour)"
            if len(self._daily[customer_id]) >= daily_limit:
                return False, f"Daily limit reached ({daily_limit} tickets/day)"

            # Record this submission
            self._hourly[customer_id].append(now)
            self._daily[customer_id].append(now)
            return True, ""

    def get_remaining(self, customer_id: str, customer_tier: str = "standard") -> dict[str, int]:
        """Get remaining ticket submissions for a customer."""
        now = time.monotonic()
        hour_ago = now - 3600
        day_ago = now - 86400

        hourly_limit = self._hourly_limit
        daily_limit = self._daily_limit
        if customer_tier in ("enterprise", "vip"):
            hourly_limit *= self._enterprise_multiplier
            daily_limit *= self._enterprise_multiplier

        with self._lock:
            hourly_count = len([t for t in self._hourly.get(customer_id, []) if t > hour_ago])
            daily_count = len([t for t in self._daily.get(customer_id, []) if t > day_ago])

        return {
            "hourly_remaining": max(0, hourly_limit - hourly_count),
            "daily_remaining": max(0, daily_limit - daily_count),
        }


# Global singleton
_limiter: CustomerRateLimiter | None = None


def get_customer_rate_limiter() -> CustomerRateLimiter:
    """Get the global customer rate limiter."""
    global _limiter
    if _limiter is None:
        _limiter = CustomerRateLimiter()
    return _limiter
