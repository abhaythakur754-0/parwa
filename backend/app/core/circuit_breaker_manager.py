"""
Circuit Breaker Manager (Phase 6: Production Hardening)

Manages circuit breakers for ALL external dependencies:
- LLM providers (Google AI, Cerebras, Groq)
- Redis
- PostgreSQL
- Paddle API
- Twilio API
- Brevo API
- Shopify API
- Any custom integrations

Features:
- Per-dependency circuit breaker with configurable thresholds
- Half-open state for automatic recovery testing
- Prometheus metrics export
- Health check integration
- Automatic fallback routing when circuit is open
- Thread-safe operations

This module provides a SYSTEM-LEVEL circuit breaker layer that complements
the existing per-provider+model circuit breaker in model_failover.py and
the per-endpoint circuit breaker in security/circuit_breaker.py.

BC-001: company_id first parameter on public methods where applicable.
BC-008: Never crash — every public method wrapped in try/except.
BC-012: All timestamps UTC.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from app.logger import get_logger

logger = get_logger("circuit_breaker_manager")


# ══════════════════════════════════════════════════════════════════
# ENUMS
# ══════════════════════════════════════════════════════════════════


class CircuitState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"        # Normal operation
    OPEN = "open"            # Failing, requests blocked
    HALF_OPEN = "half_open"  # Testing recovery


# ══════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════


@dataclass
class CircuitBreakerConfig:
    """Configuration for a single circuit breaker.

    Attributes:
        failure_threshold: Number of failures before opening the circuit.
        success_threshold: Consecutive successes in half-open to close.
        timeout: Seconds in OPEN state before transitioning to HALF_OPEN.
        window_size: Rolling window in seconds for failure counting.
        half_open_max_calls: Max test calls allowed in HALF_OPEN state.
    """
    failure_threshold: int = 5
    success_threshold: int = 3
    timeout: int = 60
    window_size: int = 300
    half_open_max_calls: int = 3


# ══════════════════════════════════════════════════════════════════
# INDIVIDUAL CIRCUIT BREAKER
# ══════════════════════════════════════════════════════════════════


class SingleCircuitBreaker:
    """Individual circuit breaker for one dependency.

    State transitions:
        CLOSED -> OPEN: After `failure_threshold` failures within window
        OPEN -> HALF_OPEN: After `timeout` seconds
        HALF_OPEN -> CLOSED: After `success_threshold` consecutive successes
        HALF_OPEN -> OPEN: After any failure

    Thread-safe via RLock.
    """

    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
    ) -> None:
        self.name = name
        self.config = config or CircuitBreakerConfig()

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        self._last_failure_time: Optional[float] = None
        self._last_state_change_time: float = time.time()
        self._opened_at: Optional[float] = None
        self._total_failures = 0
        self._total_successes = 0
        self._lock = threading.RLock()

    @property
    def state(self) -> CircuitState:
        """Get current state, checking for automatic transitions."""
        with self._lock:
            if self._state == CircuitState.OPEN:
                if self._should_transition_to_half_open():
                    self._transition_to(CircuitState.HALF_OPEN)
            return self._state

    def _should_transition_to_half_open(self) -> bool:
        """Check if enough time has elapsed to try half-open."""
        if self._opened_at is None:
            return True
        elapsed = time.time() - self._opened_at
        return elapsed >= self.config.timeout

    def is_available(self) -> bool:
        """Check if the dependency is available (circuit closed or half-open)."""
        with self._lock:
            current_state = self.state  # Triggers timeout check
            if current_state == CircuitState.CLOSED:
                return True
            if current_state == CircuitState.HALF_OPEN:
                return self._half_open_calls < self.config.half_open_max_calls
            return False  # OPEN

    def record_success(self) -> None:
        """Record a successful call."""
        with self._lock:
            self._total_successes += 1
            current_state = self.state  # Trigger timeout transition

            if current_state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    self._transition_to(CircuitState.CLOSED)
                    logger.info(
                        "circuit_closed_after_recovery name=%s successes=%d",
                        self.name, self._success_count,
                    )
            elif current_state == CircuitState.CLOSED:
                # Reset failure count on success
                self._failure_count = 0
                self._success_count += 1

    def record_failure(self) -> None:
        """Record a failed call."""
        with self._lock:
            self._total_failures += 1
            self._failure_count += 1
            current_state = self.state  # Trigger timeout transition

            if current_state == CircuitState.HALF_OPEN:
                # Any failure in half-open -> back to open
                self._transition_to(CircuitState.OPEN)
                logger.warning(
                    "circuit_reopened_from_half_open name=%s",
                    self.name,
                )
            elif current_state == CircuitState.CLOSED:
                if self._failure_count >= self.config.failure_threshold:
                    self._transition_to(CircuitState.OPEN)
                    logger.warning(
                        "circuit_opened name=%s failures=%d threshold=%d",
                        self.name,
                        self._failure_count,
                        self.config.failure_threshold,
                    )

            self._last_failure_time = time.time()

    def record_call(self) -> None:
        """Record that a call was attempted (for HALF_OPEN tracking)."""
        with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self._half_open_calls += 1

    def force_open(self) -> None:
        """Manually open a circuit (for maintenance)."""
        with self._lock:
            self._transition_to(CircuitState.OPEN)
            logger.info("circuit_force_opened name=%s", self.name)

    def force_close(self) -> None:
        """Manually close a circuit (for recovery)."""
        with self._lock:
            self._transition_to(CircuitState.CLOSED)
            logger.info("circuit_force_closed name=%s", self.name)

    def reset(self) -> None:
        """Reset the circuit breaker to CLOSED state."""
        with self._lock:
            self._transition_to(CircuitState.CLOSED)

    def _transition_to(self, new_state: CircuitState) -> None:
        """Handle state transition with bookkeeping."""
        old_state = self._state
        self._state = new_state
        self._last_state_change_time = time.time()

        if new_state == CircuitState.CLOSED:
            self._failure_count = 0
            self._success_count = 0
            self._half_open_calls = 0
            self._opened_at = None
        elif new_state == CircuitState.OPEN:
            self._opened_at = time.time()
            self._half_open_calls = 0
            self._success_count = 0
        elif new_state == CircuitState.HALF_OPEN:
            self._half_open_calls = 0
            self._success_count = 0

        logger.info(
            "circuit_state_change name=%s old_state=%s new_state=%s",
            self.name, old_state.value, new_state.value,
        )

    def get_status(self) -> Dict[str, Any]:
        """Get circuit breaker status for monitoring."""
        with self._lock:
            current_state = self.state  # Trigger timeout check
            return {
                "name": self.name,
                "state": current_state.value,
                "failure_count": self._failure_count,
                "failure_threshold": self.config.failure_threshold,
                "success_count": self._success_count,
                "success_threshold": self.config.success_threshold,
                "timeout_seconds": self.config.timeout,
                "last_failure_time": (
                    datetime.fromtimestamp(
                        self._last_failure_time, tz=timezone.utc
                    ).isoformat()
                    if self._last_failure_time
                    else None
                ),
                "last_state_change": (
                    datetime.fromtimestamp(
                        self._last_state_change_time, tz=timezone.utc
                    ).isoformat()
                ),
                "total_failures": self._total_failures,
                "total_successes": self._total_successes,
                "is_available": self.is_available(),
            }


# ══════════════════════════════════════════════════════════════════
# CIRCUIT BREAKER MANAGER
# ══════════════════════════════════════════════════════════════════


class CircuitBreakerManager:
    """
    Central manager for all circuit breakers.

    Manages circuit breakers for ALL external dependencies with:
    - Thread-safe operations
    - Automatic state transitions
    - Configurable per-dependency thresholds
    - Health reporting for /health and /ready endpoints
    - Prometheus-compatible metrics

    Usage:
        manager = CircuitBreakerManager()
        manager.register("google_ai", CircuitBreakerConfig(failure_threshold=3))
        manager.register("redis", CircuitBreakerConfig(failure_threshold=10))

        # Before making a call:
        if manager.is_available("google_ai"):
            try:
                result = call_google_ai(...)
                manager.record_success("google_ai")
            except Exception:
                manager.record_failure("google_ai")
                # Use fallback
        else:
            # Circuit is open, use fallback immediately

    BC-008: Never crash — all public methods wrapped in try/except.
    BC-012: All timestamps UTC.
    """

    def __init__(self) -> None:
        self._breakers: Dict[str, SingleCircuitBreaker] = {}
        self._lock = threading.RLock()

    def register(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
    ) -> None:
        """Register a new circuit breaker.

        If a breaker with the same name already exists, it will NOT be
        replaced (to avoid overwriting runtime state).

        Args:
            name: Unique identifier for the dependency.
            config: Configuration for the circuit breaker.
        """
        try:
            with self._lock:
                if name in self._breakers:
                    logger.debug(
                        "circuit_already_registered name=%s", name,
                    )
                    return
                self._breakers[name] = SingleCircuitBreaker(
                    name=name, config=config,
                )
                logger.info(
                    "circuit_registered name=%s failure_threshold=%d timeout=%d",
                    name,
                    (config or CircuitBreakerConfig()).failure_threshold,
                    (config or CircuitBreakerConfig()).timeout,
                )
        except Exception:
            logger.exception(
                "circuit_register_failed name=%s", name,
            )

    def unregister(self, name: str) -> None:
        """Remove a circuit breaker.

        Args:
            name: Unique identifier for the dependency.
        """
        try:
            with self._lock:
                if name in self._breakers:
                    del self._breakers[name]
                    logger.info("circuit_unregistered name=%s", name)
        except Exception:
            logger.exception(
                "circuit_unregister_failed name=%s", name,
            )

    def is_available(self, name: str) -> bool:
        """Check if the dependency is available (circuit closed or half-open).

        Returns True if the circuit is CLOSED or HALF_OPEN (with available
        probe slots). Returns False if the circuit is OPEN or the breaker
        doesn't exist.

        BC-008: Returns True (assume available) if breaker not found,
        so missing breakers don't block traffic.
        """
        try:
            with self._lock:
                breaker = self._breakers.get(name)
                if breaker is None:
                    return True  # Assume available if not registered
                return breaker.is_available()
        except Exception:
            logger.exception(
                "circuit_is_available_failed name=%s", name,
            )
            return True  # BC-008: Assume available on error

    def record_success(self, name: str) -> None:
        """Record a successful call to a dependency.

        Args:
            name: Dependency identifier.
        """
        try:
            with self._lock:
                breaker = self._breakers.get(name)
                if breaker is not None:
                    breaker.record_success()
        except Exception:
            logger.exception(
                "circuit_record_success_failed name=%s", name,
            )

    def record_failure(self, name: str) -> None:
        """Record a failed call to a dependency.

        Args:
            name: Dependency identifier.
        """
        try:
            with self._lock:
                breaker = self._breakers.get(name)
                if breaker is not None:
                    breaker.record_failure()
        except Exception:
            logger.exception(
                "circuit_record_failure_failed name=%s", name,
            )

    def get_state(self, name: str) -> CircuitState:
        """Get current circuit state for a dependency.

        Returns CLOSED if the breaker doesn't exist (safe default).
        """
        try:
            with self._lock:
                breaker = self._breakers.get(name)
                if breaker is None:
                    return CircuitState.CLOSED
                return breaker.state
        except Exception:
            logger.exception(
                "circuit_get_state_failed name=%s", name,
            )
            return CircuitState.CLOSED  # BC-008: Safe default

    def get_all_states(self) -> Dict[str, Dict[str, Any]]:
        """Get states of all circuit breakers.

        Returns a dict mapping dependency name to its status dict.
        """
        try:
            with self._lock:
                result = {}
                for name, breaker in self._breakers.items():
                    result[name] = breaker.get_status()
                return result
        except Exception:
            logger.exception("circuit_get_all_states_failed")
            return {}

    def force_open(self, name: str) -> bool:
        """Manually open a circuit (for maintenance).

        Returns True if the breaker was found and opened.
        """
        try:
            with self._lock:
                breaker = self._breakers.get(name)
                if breaker is not None:
                    breaker.force_open()
                    return True
                logger.warning(
                    "circuit_force_open_not_found name=%s", name,
                )
                return False
        except Exception:
            logger.exception(
                "circuit_force_open_failed name=%s", name,
            )
            return False

    def force_close(self, name: str) -> bool:
        """Manually close a circuit (for recovery).

        Returns True if the breaker was found and closed.
        """
        try:
            with self._lock:
                breaker = self._breakers.get(name)
                if breaker is not None:
                    breaker.force_close()
                    return True
                logger.warning(
                    "circuit_force_close_not_found name=%s", name,
                )
                return False
        except Exception:
            logger.exception(
                "circuit_force_close_failed name=%s", name,
            )
            return False

    def get_metrics(self) -> Dict[str, Any]:
        """Get Prometheus-compatible metrics for all circuit breakers.

        Returns a dict with:
        - 'metrics': List of Prometheus-format metric strings
        - 'summary': Aggregated counts
        """
        try:
            with self._lock:
                lines: List[str] = []
                total_open = 0
                total_closed = 0
                total_half_open = 0

                # Help and type definitions
                lines.append(
                    "# HELP parwa_circuit_breaker_state "
                    "Circuit breaker state (1=current, 0=not current)"
                )
                lines.append(
                    "# TYPE parwa_circuit_breaker_state gauge"
                )

                lines.append(
                    "# HELP parwa_circuit_breaker_failures_total "
                    "Total failures recorded for this circuit breaker"
                )
                lines.append(
                    "# TYPE parwa_circuit_breaker_failures_total counter"
                )

                lines.append(
                    "# HELP parwa_circuit_breaker_successes_total "
                    "Total successes recorded for this circuit breaker"
                )
                lines.append(
                    "# TYPE parwa_circuit_breaker_successes_total counter"
                )

                for name, breaker in self._breakers.items():
                    status = breaker.get_status()
                    state = status["state"]

                    # State gauge
                    for state_name in ("closed", "open", "half_open"):
                        value = 1 if state == state_name else 0
                        lines.append(
                            f'parwa_circuit_breaker_state'
                            f'{{name="{name}",state="{state_name}"}} {value}'
                        )

                    # Failure counter
                    lines.append(
                        f'parwa_circuit_breaker_failures_total'
                        f'{{name="{name}"}} {status["total_failures"]}'
                    )

                    # Success counter
                    lines.append(
                        f'parwa_circuit_breaker_successes_total'
                        f'{{name="{name}"}} {status["total_successes"]}'
                    )

                    if state == "open":
                        total_open += 1
                    elif state == "half_open":
                        total_half_open += 1
                    else:
                        total_closed += 1

                # Summary gauge
                lines.append(
                    f'parwa_circuit_breakers_total{{state="closed"}} {total_closed}'
                )
                lines.append(
                    f'parwa_circuit_breakers_total{{state="open"}} {total_open}'
                )
                lines.append(
                    f'parwa_circuit_breakers_total{{state="half_open"}} {total_half_open}'
                )

                return {
                    "metrics_text": "\n".join(lines),
                    "summary": {
                        "total": len(self._breakers),
                        "closed": total_closed,
                        "open": total_open,
                        "half_open": total_half_open,
                    },
                }
        except Exception:
            logger.exception("circuit_get_metrics_failed")
            return {
                "metrics_text": "",
                "summary": {
                    "total": 0,
                    "closed": 0,
                    "open": 0,
                    "half_open": 0,
                },
            }

    def reset_all(self) -> None:
        """Reset all circuit breakers (useful for testing)."""
        try:
            with self._lock:
                for breaker in self._breakers.values():
                    breaker.reset()
                logger.info("circuit_all_reset count=%d", len(self._breakers))
        except Exception:
            logger.exception("circuit_reset_all_failed")

    def get_open_circuits(self) -> List[str]:
        """Get list of dependency names with OPEN circuits."""
        try:
            with self._lock:
                open_names = []
                for name, breaker in self._breakers.items():
                    if breaker.state == CircuitState.OPEN:
                        open_names.append(name)
                return open_names
        except Exception:
            logger.exception("circuit_get_open_circuits_failed")
            return []

    def get_health_summary(self) -> Dict[str, Any]:
        """Get a health summary suitable for /health and /ready endpoints.

        Returns dict with:
        - 'status': 'healthy', 'degraded', or 'unhealthy'
        - 'open_circuits': List of open circuit names
        - 'half_open_circuits': List of half-open circuit names
        - 'total_circuits': Total number of registered circuits
        """
        try:
            with self._lock:
                open_circuits = []
                half_open_circuits = []

                for name, breaker in self._breakers.items():
                    state = breaker.state
                    if state == CircuitState.OPEN:
                        open_circuits.append(name)
                    elif state == CircuitState.HALF_OPEN:
                        half_open_circuits.append(name)

                # Determine overall status
                if not open_circuits and not half_open_circuits:
                    status = "healthy"
                elif not open_circuits:
                    status = "degraded"
                else:
                    status = "unhealthy"

                return {
                    "status": status,
                    "open_circuits": open_circuits,
                    "half_open_circuits": half_open_circuits,
                    "total_circuits": len(self._breakers),
                    "timestamp": (
                        datetime.now(timezone.utc).isoformat()
                    ),
                }
        except Exception:
            logger.exception("circuit_get_health_summary_failed")
            return {
                "status": "unknown",
                "open_circuits": [],
                "half_open_circuits": [],
                "total_circuits": 0,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }


# ══════════════════════════════════════════════════════════════════
# SINGLETON
# ══════════════════════════════════════════════════════════════════

_manager: Optional[CircuitBreakerManager] = None
_manager_lock = threading.Lock()


def get_circuit_breaker_manager() -> CircuitBreakerManager:
    """Get the singleton CircuitBreakerManager instance.

    Registers default dependencies on first call:
    - google_ai: 3 failures, 60s timeout
    - cerebras: 3 failures, 60s timeout
    - groq: 5 failures, 60s timeout
    - redis: 10 failures, 30s timeout
    - postgresql: 5 failures, 30s timeout
    - paddle: 3 failures, 120s timeout
    - twilio: 3 failures, 60s timeout
    - brevo: 3 failures, 60s timeout
    - shopify: 3 failures, 60s timeout
    """
    global _manager
    if _manager is None:
        with _manager_lock:
            if _manager is None:
                _manager = CircuitBreakerManager()
                # Register default dependencies
                _manager.register(
                    "google_ai",
                    CircuitBreakerConfig(failure_threshold=3, timeout=60),
                )
                _manager.register(
                    "cerebras",
                    CircuitBreakerConfig(failure_threshold=3, timeout=60),
                )
                _manager.register(
                    "groq",
                    CircuitBreakerConfig(failure_threshold=5, timeout=60),
                )
                _manager.register(
                    "redis",
                    CircuitBreakerConfig(failure_threshold=10, timeout=30),
                )
                _manager.register(
                    "postgresql",
                    CircuitBreakerConfig(failure_threshold=5, timeout=30),
                )
                _manager.register(
                    "paddle",
                    CircuitBreakerConfig(failure_threshold=3, timeout=120),
                )
                _manager.register(
                    "twilio",
                    CircuitBreakerConfig(failure_threshold=3, timeout=60),
                )
                _manager.register(
                    "brevo",
                    CircuitBreakerConfig(failure_threshold=3, timeout=60),
                )
                _manager.register(
                    "shopify",
                    CircuitBreakerConfig(failure_threshold=3, timeout=60),
                )
                logger.info(
                    "circuit_breaker_manager_initialized dependencies=%d",
                    len(_manager._breakers),
                )
    return _manager


def reset_circuit_breaker_manager() -> None:
    """Reset the singleton manager (for testing only)."""
    global _manager
    with _manager_lock:
        if _manager is not None:
            _manager.reset_all()
        _manager = None
