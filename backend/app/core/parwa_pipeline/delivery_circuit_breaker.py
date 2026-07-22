"""
Per-channel circuit breaker for Node 6.5 Deliver (BC-015).

Stops the pipeline from hammering a known-down provider. After N failures
in a row on a given channel (configurable via DELIVERY_CB_FAILURE_THRESHOLD),
the breaker opens and subsequent dispatch attempts on that channel fast-fail
with DeliveryCircuitOpenError — no network call is made. After a cooldown
period (DELIVERY_CB_RESET_SECONDS) the breaker half-opens, allowing one
trial dispatch through to probe provider health.

State is in-process (thread-safe via threading.Lock). For multi-process
deployments, also persist open state in Redis (TODO — not required for v1
since the LangGraph checkpointer already serializes state and one celery
worker per queue is the default deploy shape).

Building Codes:
  BC-008: Never crashes — breaker failures fall through to fallback chain.
  BC-012: Structured errors, no stack traces leaked.
  BC-015: Customer delivery is a separate pipeline node.
"""

from __future__ import annotations

import threading
import time
from typing import Dict

from app.config import get_settings


class _BreakerState:
    """Mutable per-channel state. Lives behind the global lock."""

    __slots__ = ("failures", "last_failure_at", "is_open")

    def __init__(self) -> None:
        self.failures: int = 0
        self.last_failure_at: float = 0.0
        self.is_open: bool = False


class DeliveryCircuitBreaker:
    """Per-channel circuit breaker for delivery dispatches.

    Thread-safe. Module-level singleton via get_delivery_circuit_breaker().

    Lifecycle:
      CLOSED   — normal operation, dispatches go through
      OPEN     — too many consecutive failures, fast-fail
      HALF_OPEN — cooldown elapsed, allow ONE trial dispatch
                  → success → CLOSED, failures reset
                  → failure → OPEN, cooldown restarts
    """

    def __init__(
        self,
        threshold: int | None = None,
        reset_seconds: int | None = None,
    ) -> None:
        settings = get_settings()
        self._threshold = threshold if threshold is not None else settings.DELIVERY_CB_FAILURE_THRESHOLD
        self._reset_seconds = reset_seconds if reset_seconds is not None else settings.DELIVERY_CB_RESET_SECONDS
        self._states: Dict[str, _BreakerState] = {}
        self._lock = threading.Lock()

    def is_open(self, channel: str) -> bool:
        """Check whether the breaker is currently open for this channel.

        Side effect: if the cooldown has elapsed, flips the breaker to
        half-open (returns False so a trial dispatch can go through).
        """
        with self._lock:
            state = self._states.get(channel)
            if state is None or not state.is_open:
                return False

            # Cooldown elapsed → half-open: allow one probe
            elapsed = time.time() - state.last_failure_at
            if elapsed >= self._reset_seconds:
                state.is_open = False
                state.failures = 0
                return False

            return True

    def record_success(self, channel: str) -> None:
        """Record a successful dispatch. Resets failures to 0, closes breaker."""
        with self._lock:
            state = self._states.setdefault(channel, _BreakerState())
            state.failures = 0
            state.is_open = False
            state.last_failure_at = 0.0

    def record_failure(self, channel: str) -> bool:
        """Record a failed dispatch. Returns True if this caused the breaker
        to open (so the caller can emit a metric / log a warning).
        """
        with self._lock:
            state = self._states.setdefault(channel, _BreakerState())
            state.failures += 1
            state.last_failure_at = time.time()

            if state.failures >= self._threshold and not state.is_open:
                state.is_open = True
                return True  # just opened
            return False

    def reset(self, channel: str | None = None) -> None:
        """Force-reset the breaker for a channel (or all channels)."""
        with self._lock:
            if channel is None:
                self._states.clear()
            else:
                self._states.pop(channel, None)

    def get_channel_state(self, channel: str) -> dict:
        """Read-only snapshot of state — for observability / metrics."""
        with self._lock:
            state = self._states.get(channel)
            if state is None:
                return {
                    "failures": 0,
                    "last_failure_at": 0.0,
                    "is_open": False,
                    "threshold": self._threshold,
                    "reset_seconds": self._reset_seconds,
                }
            return {
                "failures": state.failures,
                "last_failure_at": state.last_failure_at,
                "is_open": state.is_open,
                "threshold": self._threshold,
                "reset_seconds": self._reset_seconds,
            }

    @property
    def channels_tracked(self) -> int:
        with self._lock:
            return len(self._states)


# ── Singleton accessor ────────────────────────────────────────────

_singleton: DeliveryCircuitBreaker | None = None
_singleton_lock = threading.Lock()


def get_delivery_circuit_breaker() -> DeliveryCircuitBreaker:
    """Get the process-wide delivery circuit breaker."""
    global _singleton
    if _singleton is None:
        with _singleton_lock:
            if _singleton is None:
                _singleton = DeliveryCircuitBreaker()
    return _singleton


def reset_delivery_circuit_breaker(channel: str | None = None) -> None:
    """Reset the process-wide breaker (mostly for tests)."""
    cb = get_delivery_circuit_breaker()
    cb.reset(channel)
