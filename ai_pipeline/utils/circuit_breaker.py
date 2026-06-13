"""Circuit breaker for external API calls in PARWA.

Prevents cascading failures when external services (LLM, CRM, payment gateway)
are down. After a threshold of failures, the circuit opens and all requests
fail fast instead of retrying and timing out.

States:
- CLOSED: Normal operation. Requests go through. Failures are counted.
- OPEN: Circuit is tripped. All requests fail fast immediately.
- HALF_OPEN: Testing if service recovered. One request allowed through.

Thread-safe and async-safe implementation.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger("parwa.circuit_breaker")


class CircuitState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Circuit breaker that prevents cascading failures.

    When an external service starts failing, the breaker opens after
    `failure_threshold` consecutive failures, causing all subsequent
    requests to fail fast for `recovery_timeout` seconds.

    After the timeout, the breaker enters HALF_OPEN state and allows
    one request through. If it succeeds, the breaker closes. If it
    fails, the breaker opens again.

    Supports both sync and async operations.

    Example:
        breaker = CircuitBreaker("llm_api", failure_threshold=5, recovery_timeout=30)

        # Sync
        result = breaker.call(lambda: llm.invoke(prompt))

        # Async
        result = await breaker.acall(lambda: llm.ainvoke(prompt))
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 1,
    ) -> None:
        """Initialize the circuit breaker.

        Args:
            name: Human-readable name for logging (e.g. "llm_api", "crm_api").
            failure_threshold: Number of consecutive failures before opening.
            recovery_timeout: Seconds to wait before trying half-open.
            half_open_max_calls: Requests allowed through in half-open state.
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float = 0.0
        self._half_open_calls: int = 0
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        """Current circuit state (checks for recovery timeout)."""
        with self._lock:
            if self._state == CircuitState.OPEN:
                if time.monotonic() - self._last_failure_time >= self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                    logger.info(
                        "circuit_breaker: %s transitioning OPEN → HALF_OPEN "
                        "(recovery_timeout=%.0fs elapsed)",
                        self.name, self.recovery_timeout,
                    )
            return self._state

    def _can_execute(self) -> bool:
        """Check if a request can go through."""
        with self._lock:
            if self._state == CircuitState.CLOSED:
                return True
            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls < self.half_open_max_calls:
                    self._half_open_calls += 1
                    return True
                return False
            # OPEN state
            return False

    def _on_success(self) -> None:
        """Record a successful call."""
        with self._lock:
            self._failure_count = 0
            self._success_count += 1

            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.CLOSED
                logger.info(
                    "circuit_breaker: %s transitioning HALF_OPEN → CLOSED (success)",
                    self.name,
                )

    def _on_failure(self) -> None:
        """Record a failed call."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()

            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                logger.warning(
                    "circuit_breaker: %s transitioning HALF_OPEN → OPEN (failure)",
                    self.name,
                )
            elif self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(
                    "circuit_breaker: %s transitioning CLOSED → OPEN "
                    "(%d consecutive failures, threshold=%d)",
                    self.name, self._failure_count, self.failure_threshold,
                )

    def call(self, fn: Callable[[], Any], fallback: Any = None) -> Any:
        """Execute a sync function through the circuit breaker.

        Args:
            fn: The function to call.
            fallback: Value to return if circuit is open.

        Returns:
            The function result, or fallback if circuit is open.

        Raises:
            CircuitOpenError: If circuit is open and no fallback provided.
        """
        if not self._can_execute():
            logger.warning("circuit_breaker: %s is OPEN, failing fast", self.name)
            if fallback is not None:
                return fallback
            raise CircuitOpenError(
                f"Circuit breaker '{self.name}' is open. "
                f"Retry after {self.recovery_timeout}s."
            )

        try:
            result = fn()
            self._on_success()
            return result
        except Exception as exc:
            self._on_failure()
            raise

    async def acall(self, fn: Callable[[], Any], fallback: Any = None) -> Any:
        """Execute an async function through the circuit breaker.

        Args:
            fn: The async function to call.
            fallback: Value to return if circuit is open.

        Returns:
            The function result, or fallback if circuit is open.

        Raises:
            CircuitOpenError: If circuit is open and no fallback provided.
        """
        if not self._can_execute():
            logger.warning("circuit_breaker: %s is OPEN, failing fast (async)", self.name)
            if fallback is not None:
                return fallback
            raise CircuitOpenError(
                f"Circuit breaker '{self.name}' is open. "
                f"Retry after {self.recovery_timeout}s."
            )

        try:
            result = await fn()
            self._on_success()
            return result
        except Exception as exc:
            self._on_failure()
            raise

    def reset(self) -> None:
        """Manually reset the circuit breaker to CLOSED state."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._half_open_calls = 0
            logger.info("circuit_breaker: %s manually reset to CLOSED", self.name)

    def get_stats(self) -> dict[str, Any]:
        """Get circuit breaker statistics."""
        with self._lock:
            return {
                "name": self.name,
                "state": self._state,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "failure_threshold": self.failure_threshold,
                "recovery_timeout": self.recovery_timeout,
                "last_failure_time": self._last_failure_time,
            }


class CircuitOpenError(Exception):
    """Raised when a circuit breaker is open and no fallback is provided."""
    pass


# ─── Global circuit breakers for PARWA external services ──────────────────────────

_llm_breaker: CircuitBreaker | None = None
_crm_breaker: CircuitBreaker | None = None
_payment_breaker: CircuitBreaker | None = None


def get_llm_circuit_breaker() -> CircuitBreaker:
    """Get or create the LLM API circuit breaker.

    Default: 5 consecutive failures → open for 30 seconds.
    Configurable via PARWA_LLM_CB_THRESHOLD and PARWA_LLM_CB_TIMEOUT env vars.
    """
    global _llm_breaker
    if _llm_breaker is None:
        import os
        threshold = 5
        timeout = 30.0
        try:
            threshold = int(os.getenv("PARWA_LLM_CB_THRESHOLD", "5"))
        except (ValueError, TypeError):
            pass
        try:
            timeout = float(os.getenv("PARWA_LLM_CB_TIMEOUT", "30"))
        except (ValueError, TypeError):
            pass
        _llm_breaker = CircuitBreaker(
            "llm_api", failure_threshold=threshold, recovery_timeout=timeout,
        )
    return _llm_breaker


def get_crm_circuit_breaker() -> CircuitBreaker:
    """Get or create the CRM API circuit breaker.

    Default: 3 consecutive failures → open for 60 seconds.
    """
    global _crm_breaker
    if _crm_breaker is None:
        _crm_breaker = CircuitBreaker(
            "crm_api", failure_threshold=3, recovery_timeout=60.0,
        )
    return _crm_breaker


def get_payment_circuit_breaker() -> CircuitBreaker:
    """Get or create the payment gateway circuit breaker.

    Default: 2 consecutive failures → open for 120 seconds.
    More conservative since payment errors are critical.
    """
    global _payment_breaker
    if _payment_breaker is None:
        _payment_breaker = CircuitBreaker(
            "payment_api", failure_threshold=2, recovery_timeout=120.0,
        )
    return _payment_breaker
