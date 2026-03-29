"""Circuit Breaker Pattern Implementation"""
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
import logging
import time
import threading

logger = logging.getLogger(__name__)

class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5
    success_threshold: int = 3
    timeout_seconds: int = 60
    half_open_max_calls: int = 3

@dataclass
class CircuitStats:
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    last_failure_time: Optional[float] = None
    last_state_change: float = field(default_factory=time.time)

class CircuitBreaker:
    def __init__(self, name: str, config: CircuitBreakerConfig = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._stats = CircuitStats()
        self._lock = threading.Lock()
        self._half_open_calls = 0

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._transition_to(CircuitState.HALF_OPEN)
            return self._state

    def _should_attempt_reset(self) -> bool:
        if not self._stats.last_failure_time:
            return False
        return time.time() - self._stats.last_failure_time >= self.config.timeout_seconds

    def _transition_to(self, new_state: CircuitState) -> None:
        old_state = self._state
        self._state = new_state
        self._stats.last_state_change = time.time()
        self._half_open_calls = 0
        self._stats.consecutive_successes = 0
        self._stats.consecutive_failures = 0
        logger.info(f"Circuit breaker '{self.name}' transitioned: {old_state.value} -> {new_state.value}")

    def can_execute(self) -> bool:
        with self._lock:
            if self._state == CircuitState.CLOSED:
                return True
            elif self._state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._transition_to(CircuitState.HALF_OPEN)
                    return True
                return False
            elif self._state == CircuitState.HALF_OPEN:
                return self._half_open_calls < self.config.half_open_max_calls
        return False

    def record_success(self) -> None:
        with self._lock:
            self._stats.total_calls += 1
            self._stats.successful_calls += 1
            self._stats.consecutive_successes += 1
            self._stats.consecutive_failures = 0

            if self._state == CircuitState.HALF_OPEN:
                self._half_open_calls += 1
                if self._stats.consecutive_successes >= self.config.success_threshold:
                    self._transition_to(CircuitState.CLOSED)

    def record_failure(self) -> None:
        with self._lock:
            self._stats.total_calls += 1
            self._stats.failed_calls += 1
            self._stats.consecutive_failures += 1
            self._stats.consecutive_successes = 0
            self._stats.last_failure_time = time.time()

            if self._state == CircuitState.CLOSED:
                if self._stats.consecutive_failures >= self.config.failure_threshold:
                    self._transition_to(CircuitState.OPEN)
            elif self._state == CircuitState.HALF_OPEN:
                self._transition_to(CircuitState.OPEN)

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "name": self.name,
                "state": self._state.value,
                "total_calls": self._stats.total_calls,
                "successful_calls": self._stats.successful_calls,
                "failed_calls": self._stats.failed_calls,
                "consecutive_failures": self._stats.consecutive_failures,
                "consecutive_successes": self._stats.consecutive_successes,
                "failure_rate": round(self._stats.failed_calls / self._stats.total_calls * 100, 2) if self._stats.total_calls > 0 else 0
            }

    def reset(self) -> None:
        with self._lock:
            self._transition_to(CircuitState.CLOSED)
            self._stats = CircuitStats()

    def force_open(self) -> None:
        with self._lock:
            self._transition_to(CircuitState.OPEN)
            self._stats.last_failure_time = time.time()
