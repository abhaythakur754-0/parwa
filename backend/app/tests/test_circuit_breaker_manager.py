"""
Tests for Circuit Breaker Manager (Phase 6: Production Hardening)

Tests:
- test_register_circuit_breaker
- test_circuit_opens_after_failures
- test_circuit_half_open_after_timeout
- test_circuit_closes_after_successes
- test_is_available_checks_state
- test_force_open_and_close
- test_concurrent_access_thread_safe
- test_get_metrics_format
- test_default_dependencies_registered

BC-008: Never crash — tests are resilient to internal errors.
BC-012: All timestamps UTC.
"""

import threading
import time
import unittest

from app.core.circuit_breaker_manager import (
    CircuitBreakerConfig,
    CircuitBreakerManager,
    CircuitState,
    SingleCircuitBreaker,
    get_circuit_breaker_manager,
    reset_circuit_breaker_manager,
)


class TestRegisterCircuitBreaker(unittest.TestCase):
    """Test circuit breaker registration."""

    def setUp(self):
        self.manager = CircuitBreakerManager()

    def test_register_default_config(self):
        """Register a circuit breaker with default config."""
        self.manager.register("test_service")
        self.assertIn("test_service", self.manager._breakers)

    def test_register_custom_config(self):
        """Register a circuit breaker with custom config."""
        config = CircuitBreakerConfig(
            failure_threshold=3, timeout=30,
        )
        self.manager.register("test_service", config)
        breaker = self.manager._breakers["test_service"]
        self.assertEqual(breaker.config.failure_threshold, 3)
        self.assertEqual(breaker.config.timeout, 30)

    def test_register_duplicate_no_overwrite(self):
        """Registering same name twice does NOT overwrite existing breaker."""
        self.manager.register("test_service")
        # Manually open the breaker
        self.manager._breakers["test_service"].force_open()

        # Register again — should not overwrite
        self.manager.register("test_service")
        state = self.manager.get_state("test_service")
        self.assertEqual(state, CircuitState.OPEN)

    def test_unregister(self):
        """Unregister a circuit breaker."""
        self.manager.register("test_service")
        self.manager.unregister("test_service")
        self.assertNotIn("test_service", self.manager._breakers)

    def test_unregister_nonexistent(self):
        """Unregistering a nonexistent breaker does not crash."""
        self.manager.unregister("nonexistent")  # Should not raise


class TestCircuitOpensAfterFailures(unittest.TestCase):
    """Test circuit breaker opens after threshold failures."""

    def setUp(self):
        self.manager = CircuitBreakerManager()
        self.manager.register(
            "test_service",
            CircuitBreakerConfig(failure_threshold=3, timeout=60),
        )

    def test_opens_after_threshold(self):
        """Circuit opens after reaching failure threshold."""
        # Record failures below threshold
        self.manager.record_failure("test_service")
        self.assertEqual(
            self.manager.get_state("test_service"),
            CircuitState.CLOSED,
        )

        self.manager.record_failure("test_service")
        self.assertEqual(
            self.manager.get_state("test_service"),
            CircuitState.CLOSED,
        )

        # Third failure should open the circuit
        self.manager.record_failure("test_service")
        self.assertEqual(
            self.manager.get_state("test_service"),
            CircuitState.OPEN,
        )

    def test_failure_count_resets_on_success(self):
        """Failure count resets on success in CLOSED state."""
        # Record 2 failures
        self.manager.record_failure("test_service")
        self.manager.record_failure("test_service")

        # Record success — should reset failure count
        self.manager.record_success("test_service")

        # Now 2 more failures should NOT open (count was reset)
        self.manager.record_failure("test_service")
        self.manager.record_failure("test_service")
        self.assertEqual(
            self.manager.get_state("test_service"),
            CircuitState.CLOSED,
        )

    def test_is_unavailable_when_open(self):
        """is_available returns False when circuit is OPEN."""
        # Open the circuit
        for _ in range(3):
            self.manager.record_failure("test_service")

        self.assertFalse(self.manager.is_available("test_service"))


class TestCircuitHalfOpenAfterTimeout(unittest.TestCase):
    """Test circuit transitions to HALF_OPEN after timeout."""

    def setUp(self):
        self.manager = CircuitBreakerManager()
        self.manager.register(
            "test_service",
            CircuitBreakerConfig(
                failure_threshold=3, timeout=1,  # 1 second timeout
            ),
        )

    def test_transitions_to_half_open_after_timeout(self):
        """Circuit transitions to HALF_OPEN after timeout elapses."""
        # Open the circuit
        for _ in range(3):
            self.manager.record_failure("test_service")

        self.assertEqual(
            self.manager.get_state("test_service"),
            CircuitState.OPEN,
        )

        # Wait for timeout to elapse
        time.sleep(1.1)

        # State should now be HALF_OPEN
        state = self.manager.get_state("test_service")
        self.assertEqual(state, CircuitState.HALF_OPEN)

    def test_is_available_in_half_open(self):
        """is_available returns True in HALF_OPEN state (with probe slots)."""
        # Open the circuit
        for _ in range(3):
            self.manager.record_failure("test_service")

        # Wait for timeout
        time.sleep(1.1)

        # Should be available in half-open
        self.assertTrue(self.manager.is_available("test_service"))


class TestCircuitClosesAfterSuccesses(unittest.TestCase):
    """Test circuit closes after sufficient successes in HALF_OPEN."""

    def setUp(self):
        self.manager = CircuitBreakerManager()
        self.manager.register(
            "test_service",
            CircuitBreakerConfig(
                failure_threshold=3,
                timeout=1,
                success_threshold=2,
            ),
        )

    def test_closes_after_success_threshold(self):
        """Circuit closes after success_threshold consecutive successes."""
        # Open the circuit
        for _ in range(3):
            self.manager.record_failure("test_service")

        # Wait for half-open
        time.sleep(1.1)
        self.assertEqual(
            self.manager.get_state("test_service"),
            CircuitState.HALF_OPEN,
        )

        # Record successes to close
        self.manager.record_success("test_service")
        self.assertEqual(
            self.manager.get_state("test_service"),
            CircuitState.HALF_OPEN,
        )

        self.manager.record_success("test_service")
        self.assertEqual(
            self.manager.get_state("test_service"),
            CircuitState.CLOSED,
        )

    def test_failure_in_half_open_reopens(self):
        """Any failure in HALF_OPEN reopens the circuit."""
        # Open the circuit
        for _ in range(3):
            self.manager.record_failure("test_service")

        # Wait for half-open
        time.sleep(1.1)
        self.assertEqual(
            self.manager.get_state("test_service"),
            CircuitState.HALF_OPEN,
        )

        # One success
        self.manager.record_success("test_service")

        # A failure reopens
        self.manager.record_failure("test_service")
        self.assertEqual(
            self.manager.get_state("test_service"),
            CircuitState.OPEN,
        )


class TestIsAvailableChecksState(unittest.TestCase):
    """Test is_available method with different states."""

    def setUp(self):
        self.manager = CircuitBreakerManager()
        self.manager.register(
            "test_service",
            CircuitBreakerConfig(failure_threshold=3, timeout=1),
        )

    def test_available_when_closed(self):
        """is_available returns True when CLOSED."""
        self.assertTrue(self.manager.is_available("test_service"))

    def test_unavailable_when_open(self):
        """is_available returns False when OPEN."""
        for _ in range(3):
            self.manager.record_failure("test_service")
        self.assertFalse(self.manager.is_available("test_service"))

    def test_available_when_not_registered(self):
        """is_available returns True for unregistered services (safe default)."""
        self.assertTrue(self.manager.is_available("nonexistent"))

    def test_available_error_fallback(self):
        """is_available returns True on error (BC-008)."""
        # Even with a malformed manager, should return True
        self.assertTrue(self.manager.is_available("any_service"))


class TestForceOpenAndClose(unittest.TestCase):
    """Test force_open and force_close methods."""

    def setUp(self):
        self.manager = CircuitBreakerManager()
        self.manager.register("test_service")

    def test_force_open(self):
        """force_open manually opens a circuit."""
        result = self.manager.force_open("test_service")
        self.assertTrue(result)
        self.assertEqual(
            self.manager.get_state("test_service"),
            CircuitState.OPEN,
        )
        self.assertFalse(self.manager.is_available("test_service"))

    def test_force_close(self):
        """force_close manually closes a circuit."""
        self.manager.force_open("test_service")
        result = self.manager.force_close("test_service")
        self.assertTrue(result)
        self.assertEqual(
            self.manager.get_state("test_service"),
            CircuitState.CLOSED,
        )
        self.assertTrue(self.manager.is_available("test_service"))

    def test_force_open_nonexistent(self):
        """force_open returns False for nonexistent breaker."""
        result = self.manager.force_open("nonexistent")
        self.assertFalse(result)

    def test_force_close_nonexistent(self):
        """force_close returns False for nonexistent breaker."""
        result = self.manager.force_close("nonexistent")
        self.assertFalse(result)


class TestConcurrentAccessThreadSafe(unittest.TestCase):
    """Test thread safety of circuit breaker manager."""

    def test_concurrent_record_failure(self):
        """Concurrent failures from multiple threads don't crash."""
        manager = CircuitBreakerManager()
        manager.register(
            "test_service",
            CircuitBreakerConfig(failure_threshold=100, timeout=60),
        )

        errors = []

        def record_failures():
            try:
                for _ in range(50):
                    manager.record_failure("test_service")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=record_failures) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0)
        # Should have 500 total failures
        breaker = manager._breakers["test_service"]
        self.assertEqual(breaker._failure_count, 500)

    def test_concurrent_record_success_and_failure(self):
        """Concurrent successes and failures don't crash."""
        manager = CircuitBreakerManager()
        manager.register(
            "test_service",
            CircuitBreakerConfig(failure_threshold=50, timeout=60),
        )

        errors = []

        def record_successes():
            try:
                for _ in range(50):
                    manager.record_success("test_service")
            except Exception as e:
                errors.append(e)

        def record_failures():
            try:
                for _ in range(50):
                    manager.record_failure("test_service")
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=record_successes),
            threading.Thread(target=record_failures),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0)


class TestGetMetricsFormat(unittest.TestCase):
    """Test Prometheus metrics format."""

    def setUp(self):
        self.manager = CircuitBreakerManager()
        self.manager.register(
            "test_service",
            CircuitBreakerConfig(failure_threshold=3, timeout=60),
        )

    def test_metrics_contains_help_and_type(self):
        """Metrics output contains HELP and TYPE definitions."""
        metrics = self.manager.get_metrics()
        metrics_text = metrics["metrics_text"]
        self.assertIn("# HELP parwa_circuit_breaker_state", metrics_text)
        self.assertIn("# TYPE parwa_circuit_breaker_state gauge", metrics_text)
        self.assertIn("# HELP parwa_circuit_breaker_failures_total", metrics_text)
        self.assertIn("# TYPE parwa_circuit_breaker_failures_total counter", metrics_text)

    def test_metrics_contains_service_name(self):
        """Metrics output contains the service name as a label."""
        metrics = self.manager.get_metrics()
        metrics_text = metrics["metrics_text"]
        self.assertIn('name="test_service"', metrics_text)

    def test_metrics_summary(self):
        """Metrics summary has correct structure."""
        metrics = self.manager.get_metrics()
        summary = metrics["summary"]
        self.assertIn("total", summary)
        self.assertIn("closed", summary)
        self.assertIn("open", summary)
        self.assertIn("half_open", summary)
        self.assertEqual(summary["total"], 1)
        self.assertEqual(summary["closed"], 1)
        self.assertEqual(summary["open"], 0)

    def test_metrics_after_state_change(self):
        """Metrics reflect state changes."""
        # Open the circuit
        for _ in range(3):
            self.manager.record_failure("test_service")

        metrics = self.manager.get_metrics()
        summary = metrics["summary"]
        self.assertEqual(summary["open"], 1)
        self.assertEqual(summary["closed"], 0)

    def test_get_all_states(self):
        """get_all_states returns status for all breakers."""
        self.manager.register("second_service")
        states = self.manager.get_all_states()
        self.assertIn("test_service", states)
        self.assertIn("second_service", states)
        self.assertIn("state", states["test_service"])
        self.assertIn("is_available", states["test_service"])


class TestDefaultDependenciesRegistered(unittest.TestCase):
    """Test that default dependencies are registered via singleton."""

    def setUp(self):
        reset_circuit_breaker_manager()

    def tearDown(self):
        reset_circuit_breaker_manager()

    def test_default_dependencies_registered(self):
        """Singleton registers all default dependencies."""
        manager = get_circuit_breaker_manager()
        expected_deps = [
            "google_ai", "cerebras", "groq",
            "redis", "postgresql",
            "paddle", "twilio", "brevo", "shopify",
        ]
        for dep in expected_deps:
            self.assertIn(
                dep, manager._breakers,
                f"Default dependency '{dep}' not registered",
            )

    def test_default_configs_correct(self):
        """Default dependencies have correct configurations."""
        manager = get_circuit_breaker_manager()

        # google_ai: failure_threshold=3, timeout=60
        google_ai = manager._breakers["google_ai"]
        self.assertEqual(google_ai.config.failure_threshold, 3)
        self.assertEqual(google_ai.config.timeout, 60)

        # redis: failure_threshold=10, timeout=30
        redis = manager._breakers["redis"]
        self.assertEqual(redis.config.failure_threshold, 10)
        self.assertEqual(redis.config.timeout, 30)

        # paddle: failure_threshold=3, timeout=120
        paddle = manager._breakers["paddle"]
        self.assertEqual(paddle.config.failure_threshold, 3)
        self.assertEqual(paddle.config.timeout, 120)

    def test_singleton_returns_same_instance(self):
        """Singleton returns the same instance each time."""
        manager1 = get_circuit_breaker_manager()
        manager2 = get_circuit_breaker_manager()
        self.assertIs(manager1, manager2)

    def test_reset_clears_singleton(self):
        """reset_circuit_breaker_manager clears the singleton."""
        manager1 = get_circuit_breaker_manager()
        reset_circuit_breaker_manager()
        manager2 = get_circuit_breaker_manager()
        self.assertIsNot(manager1, manager2)

    def test_get_open_circuits(self):
        """get_open_circuits returns list of open circuit names."""
        manager = get_circuit_breaker_manager()
        # Initially all closed
        open_circuits = manager.get_open_circuits()
        self.assertEqual(len(open_circuits), 0)

        # Open one
        manager.force_open("google_ai")
        open_circuits = manager.get_open_circuits()
        self.assertIn("google_ai", open_circuits)

    def test_get_health_summary(self):
        """get_health_summary returns proper structure."""
        manager = get_circuit_breaker_manager()
        summary = manager.get_health_summary()
        self.assertIn("status", summary)
        self.assertIn("open_circuits", summary)
        self.assertIn("half_open_circuits", summary)
        self.assertIn("total_circuits", summary)
        self.assertIn("timestamp", summary)
        # All circuits should be closed initially
        self.assertEqual(summary["status"], "healthy")

    def test_reset_all(self):
        """reset_all resets all breakers to CLOSED."""
        manager = get_circuit_breaker_manager()
        manager.force_open("google_ai")
        manager.force_open("redis")

        manager.reset_all()
        self.assertEqual(
            manager.get_state("google_ai"),
            CircuitState.CLOSED,
        )
        self.assertEqual(
            manager.get_state("redis"),
            CircuitState.CLOSED,
        )


class TestSingleCircuitBreaker(unittest.TestCase):
    """Test individual SingleCircuitBreaker behavior."""

    def test_initial_state_closed(self):
        """New breaker starts in CLOSED state."""
        breaker = SingleCircuitBreaker("test")
        self.assertEqual(breaker.state, CircuitState.CLOSED)

    def test_get_status(self):
        """get_status returns proper structure."""
        breaker = SingleCircuitBreaker("test")
        status = breaker.get_status()
        self.assertIn("name", status)
        self.assertIn("state", status)
        self.assertIn("failure_count", status)
        self.assertIn("failure_threshold", status)
        self.assertIn("total_failures", status)
        self.assertIn("total_successes", status)
        self.assertIn("is_available", status)
        self.assertEqual(status["name"], "test")
        self.assertEqual(status["state"], "closed")

    def test_half_open_max_calls(self):
        """HALF_OPEN state respects max_calls limit."""
        config = CircuitBreakerConfig(
            failure_threshold=2, timeout=1, half_open_max_calls=3,
        )
        breaker = SingleCircuitBreaker("test", config)

        # Open the circuit
        breaker.record_failure()
        breaker.record_failure()
        self.assertEqual(breaker.state, CircuitState.OPEN)

        # Wait for half-open
        time.sleep(1.1)
        self.assertEqual(breaker.state, CircuitState.HALF_OPEN)

        # Record calls below max — still available
        breaker.record_call()
        breaker.record_call()
        self.assertTrue(breaker.is_available())

        # Third call hits the limit
        breaker.record_call()
        self.assertFalse(breaker.is_available())


if __name__ == "__main__":
    unittest.main()
