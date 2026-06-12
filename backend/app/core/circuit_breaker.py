"""
PARWA Phase 3 — Circuit Breaker

Implements the CLOSED → OPEN → HALF_OPEN state machine for protecting
downstream service calls.  When failures exceed *failure_threshold* the
circuit opens and all calls are rejected immediately.  After
*recovery_timeout* seconds the circuit enters HALF_OPEN and allows a
limited number of probe calls.  A successful probe closes the circuit;
a failed probe reopens it.

Usage
-----
    breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60.0)

    # As a callable guard
    result = await breaker.call(my_async_func, arg1, arg2)

    # As an async context manager
    async with breaker:
        result = await my_async_func(arg1, arg2)
"""

from __future__ import annotations

import asyncio
import enum
import logging
import time
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class CircuitState(enum.Enum):
    """Possible states of a circuit breaker."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    """Raised when a call is attempted while the circuit is open."""


class CircuitBreaker:
    """Thread-safe (asyncio-safe) circuit breaker.

    Parameters
    ----------
    failure_threshold:
        Number of consecutive failures required to open the circuit.
    recovery_timeout:
        Seconds to wait in OPEN state before transitioning to HALF_OPEN.
    half_open_max:
        Maximum number of probe calls allowed in HALF_OPEN state.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max: int = 1,
    ) -> None:
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        if recovery_timeout <= 0:
            raise ValueError("recovery_timeout must be > 0")
        if half_open_max < 1:
            raise ValueError("half_open_max must be >= 1")

        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._half_open_max = half_open_max

        self._failure_count: int = 0
        self._success_count: int = 0
        self._state: CircuitState = CircuitState.CLOSED
        self._last_failure_time: float = 0.0
        self._half_open_calls: int = 0

        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    @property
    def is_available(self) -> bool:
        """Return ``True`` if the circuit allows a call attempt."""
        state = self._get_state_locked()
        return state in (CircuitState.CLOSED, CircuitState.HALF_OPEN)

    @property
    def state(self) -> CircuitState:
        """Current circuit state (time-aware)."""
        return self._get_state_locked()

    @property
    def failure_count(self) -> int:
        return self._failure_count

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    async def call(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """Execute *func* with circuit-breaker protection.

        If the circuit is OPEN, raises :class:`CircuitOpenError` instead
        of calling *func*.

        Returns the result of *func* on success.  On failure the exception
        is re-raised after recording the failure.
        """
        current_state = await self._compute_state()

        if current_state == CircuitState.OPEN:
            logger.warning("Circuit is OPEN — call rejected")
            raise CircuitOpenError("Circuit is open; calls are not allowed")

        if current_state == CircuitState.HALF_OPEN:
            async with self._lock:
                if self._half_open_calls >= self._half_open_max:
                    logger.warning(
                        "Circuit is HALF_OPEN and probe limit reached — call rejected"
                    )
                    raise CircuitOpenError(
                        "Circuit is half-open and probe limit reached"
                    )
                self._half_open_calls += 1

        try:
            result = await func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as exc:
            self.record_failure()
            raise

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def record_success(self) -> None:
        """Record a successful call — resets failure count and closes circuit."""
        self._failure_count = 0
        self._success_count += 1
        self._half_open_calls = 0
        self._state = CircuitState.CLOSED
        logger.debug("Success recorded — circuit CLOSED")

    def record_failure(self) -> None:
        """Record a failed call — increments failure count and may open circuit."""
        self._failure_count += 1
        self._last_failure_time = time.monotonic()

        if self._state == CircuitState.HALF_OPEN:
            logger.warning("Probe failed — circuit re-OPENED")
            self._state = CircuitState.OPEN
            self._half_open_calls = 0
        elif self._failure_count >= self._failure_threshold:
            logger.warning(
                "Failure threshold reached (%d) — circuit OPENED",
                self._failure_threshold,
            )
            self._state = CircuitState.OPEN
        else:
            logger.debug(
                "Failure recorded (%d/%d)", self._failure_count, self._failure_threshold
            )

    # ------------------------------------------------------------------
    # Internal state machine
    # ------------------------------------------------------------------

    async def _compute_state(self) -> CircuitState:
        """Return the current state, applying time-based recovery logic."""
        async with self._lock:
            if self._state == CircuitState.OPEN:
                elapsed = time.monotonic() - self._last_failure_time
                if elapsed >= self._recovery_timeout:
                    logger.info(
                        "Recovery timeout elapsed (%.1fs) — circuit → HALF_OPEN",
                        elapsed,
                    )
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
            return self._state

    def _get_state_locked(self) -> CircuitState:
        """Synchronous state snapshot — no lock (for read-only property)."""
        if self._state == CircuitState.OPEN:
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self._recovery_timeout:
                return CircuitState.HALF_OPEN
        return self._state

    # ------------------------------------------------------------------
    # Context manager support
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "CircuitBreaker":
        """Enter the context — raise if circuit is unavailable."""
        current_state = await self._compute_state()
        if current_state == CircuitState.OPEN:
            raise CircuitOpenError("Circuit is open; cannot enter context")

        if current_state == CircuitState.HALF_OPEN:
            async with self._lock:
                if self._half_open_calls >= self._half_open_max:
                    raise CircuitOpenError(
                        "Circuit is half-open and probe limit reached"
                    )
                self._half_open_calls += 1

        return self

    async def __aexit__(
        self,
        exc_type: Optional[type] = None,
        exc_val: Optional[BaseException] = None,
        exc_tb: Optional[Any] = None,
    ) -> bool:
        """Exit the context — record success or failure."""
        if exc_type is not None:
            self.record_failure()
        else:
            self.record_success()
        return False  # do not suppress exceptions
