"""
Tests for security/circuit_breaker.py

Tests state transitions: CLOSED -> OPEN -> HALF_OPEN -> CLOSED (BC-012).
BC-012: 5 failures threshold, 60s recovery timeout.
"""

import time

import pytest

from security.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
)


class TestCircuitBreakerInit:
    """Tests for CircuitBreaker initialization."""

    def test_default_failure_threshold_is_5(self):
        cb = CircuitBreaker("test")
        assert cb.failure_threshold == 5

    def test_default_recovery_timeout_is_60(self):
        cb = CircuitBreaker("test")
        assert cb.recovery_timeout == 60

    def test_initial_state_is_closed(self):
        cb = CircuitBreaker("test")
        assert cb.state == CircuitState.CLOSED

    def test_initial_failure_count_is_0(self):
        cb = CircuitBreaker("test")
        assert cb.failure_count == 0

    def test_name_required(self):
        with pytest.raises(ValueError, match="name is required"):
            CircuitBreaker("")

    def test_custom_threshold(self):
        cb = CircuitBreaker("test", failure_threshold=3)
        assert cb.failure_threshold == 3

    def test_custom_timeout(self):
        cb = CircuitBreaker("test", recovery_timeout=30)
        assert cb.recovery_timeout == 30


class TestClosedState:
    """Tests for CLOSED state behavior."""

    def test_can_execute_in_closed(self):
        cb = CircuitBreaker("test")
        assert cb.can_execute() is True

    def test_stays_closed_after_success(self):
        cb = CircuitBreaker("test")
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_stays_closed_under_threshold(self):
        cb = CircuitBreaker("test", failure_threshold=5)
        for _ in range(4):
            cb.record_failure()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 4

    def test_resets_failure_count_on_success(self):
        cb = CircuitBreaker("test", failure_threshold=5)
        for _ in range(3):
            cb.record_failure()
        cb.record_success()
        assert cb.failure_count == 0

    def test_multiple_successes_no_change(self):
        cb = CircuitBreaker("test")
        for _ in range(10):
            cb.record_success()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0


class TestOpenState:
    """Tests for OPEN state transition."""

    def test_opens_after_threshold_failures(self):
        cb = CircuitBreaker("test", failure_threshold=5)
        for _ in range(5):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_cannot_execute_when_open(self):
        cb = CircuitBreaker("test", failure_threshold=5)
        for _ in range(5):
            cb.record_failure()
        assert cb.can_execute() is False

    def test_exact_threshold_5(self):
        """BC-012: Exactly 5 failures, not 3, not 10."""
        cb = CircuitBreaker("test", failure_threshold=5)
        # 4 failures - still closed
        for _ in range(4):
            cb.record_failure()
        assert cb.state == CircuitState.CLOSED
        # 5th failure - opens
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_over_threshold_immediately_open(self):
        cb = CircuitBreaker("test", failure_threshold=5)
        for _ in range(10):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_last_failure_time_set(self):
        cb = CircuitBreaker("test", failure_threshold=3)
        before = time.time()
        for _ in range(3):
            cb.record_failure()
        assert cb.last_failure_time is not None
        assert cb.last_failure_time >= before

    def test_extra_failures_in_open_dont_crash(self):
        cb = CircuitBreaker("test", failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        for _ in range(10):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN


class TestHalfOpenState:
    """Tests for HALF_OPEN state transition."""

    def test_transitions_to_half_open_after_timeout(self):
        cb = CircuitBreaker(
            "test", failure_threshold=3, recovery_timeout=0.1
        )
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN

        time.sleep(0.15)
        # Accessing state triggers timeout check
        assert cb.state == CircuitState.HALF_OPEN

    def test_can_execute_in_half_open(self):
        cb = CircuitBreaker(
            "test", failure_threshold=3, recovery_timeout=0.1
        )
        for _ in range(3):
            cb.record_failure()
        time.sleep(0.15)
        assert cb.can_execute() is True

    def test_success_closes_circuit(self):
        cb = CircuitBreaker(
            "test", failure_threshold=3, recovery_timeout=0.1
        )
        for _ in range(3):
            cb.record_failure()
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_failure_reopens_circuit(self):
        cb = CircuitBreaker(
            "test", failure_threshold=3, recovery_timeout=0.1
        )
        for _ in range(3):
            cb.record_failure()
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_closed_resets_failure_count(self):
        cb = CircuitBreaker(
            "test", failure_threshold=3, recovery_timeout=0.1
        )
        for _ in range(3):
            cb.record_failure()
        time.sleep(0.15)
        cb.record_success()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0


class TestManualOperations:
    """Tests for manual reset and force open."""

    def test_manual_reset(self):
        cb = CircuitBreaker("test", failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_force_open(self):
        cb = CircuitBreaker("test")
        cb.force_open()
        assert cb.state == CircuitState.OPEN
        assert cb.can_execute() is False

    def test_reset_from_half_open(self):
        cb = CircuitBreaker(
            "test", failure_threshold=3, recovery_timeout=0.1
        )
        for _ in range(3):
            cb.record_failure()
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED


class TestGetStatus:
    """Tests for get_status() monitoring."""

    def test_returns_dict(self):
        cb = CircuitBreaker("test")
        status = cb.get_status()
        assert isinstance(status, dict)

    def test_has_all_fields(self):
        cb = CircuitBreaker("my_service")
        status = cb.get_status()
        expected_keys = {
            "name", "state", "failure_count",
            "failure_threshold", "recovery_timeout",
            "last_failure_time", "last_state_change",
        }
        assert set(status.keys()) == expected_keys

    def test_name_in_status(self):
        cb = CircuitBreaker("payment_service")
        assert cb.get_status()["name"] == "payment_service"

    def test_state_in_status(self):
        cb = CircuitBreaker("test")
        assert cb.get_status()["state"] == "closed"


class TestRecordCall:
    """Tests for record_call() HALF_OPEN tracking."""

    def test_record_call_in_half_open(self):
        cb = CircuitBreaker(
            "test", failure_threshold=3, recovery_timeout=0.1
        )
        for _ in range(3):
            cb.record_failure()
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_call()
        # After 1 call in HALF_OPEN, should still allow execution
        # until max probes
        assert cb.can_execute() is True
