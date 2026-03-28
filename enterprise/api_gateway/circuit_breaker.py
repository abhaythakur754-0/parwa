"""Circuit Breaker - Fault tolerance pattern for API calls"""
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
import logging
import time
import threading

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation, requests pass through
    OPEN = "open"          # Failing, requests are blocked
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitStats:
    """Statistics for circuit breaker"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    last_state_change: Optional[float] = None


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker"""
    failure_threshold: int = 5  # Failures before opening
    success_threshold: int = 3  # Successes in half-open to close
    recovery_timeout: float = 30.0  # Seconds before trying half-open
    half_open_max_calls: int = 1  # Max calls allowed in half-open


class CircuitBreaker:
    """
    Circuit Breaker pattern implementation for fault tolerance.

    States:
    - CLOSED: Normal operation, all requests pass through
    - OPEN: Circuit is open, all requests fail fast
    - HALF_OPEN: Testing if service has recovered

    Features:
    - Configurable failure threshold
    - Automatic recovery after timeout
    - Half-open state for gradual recovery
    - Thread-safe operations
    """

    def __init__(
        self,
        name: str = "default",
        config: Optional[CircuitBreakerConfig] = None
    ):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._stats = CircuitStats()
        self._lock = threading.Lock()
        self._half_open_calls = 0
        logger.info(f"Circuit breaker '{name}' initialized in CLOSED state")

    def can_execute(self) -> bool:
        """
        Check if a request can be executed.

        Returns:
            True if request can proceed, False if circuit is open
        """
        with self._lock:
            current_time = time.time()

            if self._state == CircuitState.CLOSED:
                return True

            elif self._state == CircuitState.OPEN:
                # Check if recovery timeout has passed
                if self._stats.last_failure_time is not None:
                    elapsed = current_time - self._stats.last_failure_time
                    if elapsed >= self.config.recovery_timeout:
                        self._transition_to(CircuitState.HALF_OPEN)
                        return True
                return False

            elif self._state == CircuitState.HALF_OPEN:
                # Allow limited requests in half-open state
                if self._half_open_calls < self.config.half_open_max_calls:
                    self._half_open_calls += 1
                    return True
                return False

            return False

    def record_success(self) -> None:
        """Record a successful request"""
        with self._lock:
            self._stats.total_requests += 1
            self._stats.successful_requests += 1
            self._stats.consecutive_successes += 1
            self._stats.consecutive_failures = 0
            self._stats.last_success_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                if self._stats.consecutive_successes >= self.config.success_threshold:
                    self._transition_to(CircuitState.CLOSED)

            logger.debug(f"Circuit breaker '{self.name}' recorded success")

    def record_failure(self) -> None:
        """Record a failed request"""
        with self._lock:
            self._stats.total_requests += 1
            self._stats.failed_requests += 1
            self._stats.consecutive_failures += 1
            self._stats.consecutive_successes = 0
            self._stats.last_failure_time = time.time()

            if self._state == CircuitState.CLOSED:
                if self._stats.consecutive_failures >= self.config.failure_threshold:
                    self._transition_to(CircuitState.OPEN)

            elif self._state == CircuitState.HALF_OPEN:
                self._transition_to(CircuitState.OPEN)

            logger.debug(f"Circuit breaker '{self.name}' recorded failure")

    def get_state(self) -> CircuitState:
        """Get current circuit state"""
        with self._lock:
            # Check for automatic state transition
            if self._state == CircuitState.OPEN:
                current_time = time.time()
                if self._stats.last_failure_time is not None:
                    elapsed = current_time - self._stats.last_failure_time
                    if elapsed >= self.config.recovery_timeout:
                        return CircuitState.HALF_OPEN
            return self._state

    def get_stats(self) -> CircuitStats:
        """Get circuit breaker statistics"""
        with self._lock:
            return CircuitStats(
                total_requests=self._stats.total_requests,
                successful_requests=self._stats.successful_requests,
                failed_requests=self._stats.failed_requests,
                consecutive_failures=self._stats.consecutive_failures,
                consecutive_successes=self._stats.consecutive_successes,
                last_failure_time=self._stats.last_failure_time,
                last_success_time=self._stats.last_success_time,
                last_state_change=self._stats.last_state_change
            )

    def reset(self) -> None:
        """Reset circuit breaker to closed state"""
        with self._lock:
            self._transition_to(CircuitState.CLOSED)
            self._stats = CircuitStats()
            logger.info(f"Circuit breaker '{self.name}' reset to CLOSED")

    def force_open(self) -> None:
        """Force circuit to open state"""
        with self._lock:
            self._transition_to(CircuitState.OPEN)
            logger.warning(f"Circuit breaker '{self.name}' forced to OPEN")

    def force_close(self) -> None:
        """Force circuit to closed state"""
        with self._lock:
            self._transition_to(CircuitState.CLOSED)
            logger.info(f"Circuit breaker '{self.name}' forced to CLOSED")

    def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to a new state"""
        old_state = self._state
        self._state = new_state
        self._stats.last_state_change = time.time()

        if new_state == CircuitState.HALF_OPEN:
            self._half_open_calls = 0
            self._stats.consecutive_successes = 0

        logger.info(
            f"Circuit breaker '{self.name}' transitioned: "
            f"{old_state.value} -> {new_state.value}"
        )

    def get_metrics(self) -> Dict[str, Any]:
        """Get circuit breaker metrics"""
        with self._lock:
            return {
                "name": self.name,
                "state": self._state.value,
                "total_requests": self._stats.total_requests,
                "successful_requests": self._stats.successful_requests,
                "failed_requests": self._stats.failed_requests,
                "consecutive_failures": self._stats.consecutive_failures,
                "consecutive_successes": self._stats.consecutive_successes,
                "failure_threshold": self.config.failure_threshold,
                "success_threshold": self.config.success_threshold,
                "recovery_timeout": self.config.recovery_timeout,
                "success_rate": (
                    self._stats.successful_requests / self._stats.total_requests * 100
                    if self._stats.total_requests > 0 else 100
                )
            }


class CircuitBreakerRegistry:
    """
    Registry for managing multiple circuit breakers.
    """

    def __init__(self):
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()

    def get_or_create(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None
    ) -> CircuitBreaker:
        """Get existing or create new circuit breaker"""
        with self._lock:
            if name not in self._breakers:
                self._breakers[name] = CircuitBreaker(name, config)
            return self._breakers[name]

    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker by name"""
        with self._lock:
            return self._breakers.get(name)

    def remove(self, name: str) -> bool:
        """Remove circuit breaker"""
        with self._lock:
            if name in self._breakers:
                del self._breakers[name]
                return True
            return False

    def get_all_states(self) -> Dict[str, CircuitState]:
        """Get states of all circuit breakers"""
        with self._lock:
            return {name: cb.get_state() for name, cb in self._breakers.items()}

    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get metrics for all circuit breakers"""
        with self._lock:
            return {name: cb.get_metrics() for name, cb in self._breakers.items()}

    def reset_all(self) -> None:
        """Reset all circuit breakers"""
        with self._lock:
            for cb in self._breakers.values():
                cb.reset()
