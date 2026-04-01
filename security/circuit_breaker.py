"""
PARWA Circuit Breaker (BC-012)

Prevents cascading failures by wrapping external service calls.
Three states: CLOSED (normal), OPEN (failing), HALF_OPEN (probing).

BC-012 Requirements:
- 5 consecutive failures trigger OPEN state (not 3, not 10)
- 60 seconds timeout before transitioning to HALF_OPEN
- HALF_OPEN allows up to 3 probe requests; success -> CLOSED, fail -> OPEN

Usage:
    breaker = CircuitBreaker("external_api")

    async def call_service():
        async with breaker:
            response = await httpx.get("https://api.example.com")
            return response.json()
"""

import enum
import time
from typing import Optional


class CircuitState(enum.Enum):
    """Circuit breaker states."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


# BC-012: Exactly 5 failures to trip the circuit
DEFAULT_FAILURE_THRESHOLD = 5

# BC-012: Exactly 60 seconds before retry
DEFAULT_RECOVERY_TIMEOUT = 60

# HALF_OPEN: Allow multiple probe requests to test recovery
HALF_OPEN_MAX_REQUESTS = 3


class CircuitBreaker:
    """Circuit breaker for protecting external service calls.

    State transitions:
    CLOSED -> OPEN: After `failure_threshold` consecutive failures
    OPEN -> HALF_OPEN: After `recovery_timeout` seconds
    HALF_OPEN -> CLOSED: After 1 successful request
    HALF_OPEN -> OPEN: After 1 failed request

    BC-012: 5 failures, 60s timeout.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = DEFAULT_FAILURE_THRESHOLD,
        recovery_timeout: float = DEFAULT_RECOVERY_TIMEOUT,
    ):
        if not name:
            raise ValueError("Circuit breaker name is required")
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._last_state_change_time: float = time.time()
        self._half_open_requests = 0

    @property
    def state(self) -> CircuitState:
        """Get current circuit state, checking for timeout transitions."""
        if self._state == CircuitState.OPEN:
            # Check if recovery timeout has elapsed
            if self._last_failure_time is not None:
                elapsed = time.time() - self._last_failure_time
                if elapsed >= self.recovery_timeout:
                    self._transition_to(CircuitState.HALF_OPEN)
        return self._state

    @property
    def failure_count(self) -> int:
        return self._failure_count

    @property
    def last_failure_time(self) -> Optional[float]:
        return self._last_failure_time

    def can_execute(self) -> bool:
        """Check if a request can be executed through the circuit.

        Returns:
            True if CLOSED or HALF_OPEN (with available probe slots).
            False if OPEN or HALF_OPEN with no probe slots.
        """
        current_state = self.state  # triggers timeout check

        if current_state == CircuitState.CLOSED:
            return True

        if current_state == CircuitState.HALF_OPEN:
            return self._half_open_requests < HALF_OPEN_MAX_REQUESTS

        return False  # OPEN

    def record_success(self) -> None:
        """Record a successful request."""
        self._success_count += 1

        current_state = self.state  # trigger timeout transition

        if current_state == CircuitState.HALF_OPEN:
            # Success in HALF_OPEN -> back to CLOSED
            self._transition_to(CircuitState.CLOSED)
        elif current_state == CircuitState.CLOSED:
            # Reset failure count on success in CLOSED state
            self._failure_count = 0

    def record_failure(self) -> None:
        """Record a failed request."""
        self._failure_count += 1

        current_state = self.state  # trigger timeout transition

        # Only update last_failure_time if not already in OPEN state
        # (to avoid resetting the recovery timer)
        if current_state != CircuitState.OPEN:
            self._last_failure_time = time.time()

        if current_state == CircuitState.HALF_OPEN:
            # Failure in HALF_OPEN -> back to OPEN
            self._transition_to(CircuitState.OPEN)
        elif current_state == CircuitState.CLOSED:
            if self._failure_count >= self.failure_threshold:
                # Threshold reached -> OPEN
                self._transition_to(CircuitState.OPEN)

    def record_call(self) -> None:
        """Record that a call was attempted (for HALF_OPEN tracking)."""
        if self.state == CircuitState.HALF_OPEN:
            self._half_open_requests += 1

    def reset(self) -> None:
        """Manually reset the circuit breaker to CLOSED state."""
        self._transition_to(CircuitState.CLOSED)

    def force_open(self) -> None:
        """Manually force the circuit breaker to OPEN state."""
        self._transition_to(CircuitState.OPEN)

    def _transition_to(self, new_state: CircuitState) -> None:
        """Handle state transition with bookkeeping."""
        self._state = new_state
        self._last_state_change_time = time.time()

        # Reset counters based on transition
        if new_state == CircuitState.CLOSED:
            self._failure_count = 0
            self._success_count = 0
            self._half_open_requests = 0
        elif new_state == CircuitState.OPEN:
            self._last_failure_time = time.time()
            self._half_open_requests = 0
        elif new_state == CircuitState.HALF_OPEN:
            self._half_open_requests = 0
            self._success_count = 0

    def get_status(self) -> dict:
        """Get circuit breaker status for monitoring."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "last_failure_time": self._last_failure_time,
            "last_state_change": self._last_state_change_time,
        }
