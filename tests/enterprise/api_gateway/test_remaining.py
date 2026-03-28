"""Tests for Circuit Breaker, Transformer, and API Monitor"""
import pytest
import time
from enterprise.api_gateway.circuit_breaker import (
    CircuitBreaker, CircuitState, CircuitBreakerConfig
)
from enterprise.api_gateway.transformer import (
    Transformer, TransformPhase
)
from enterprise.api_gateway.api_monitor import APIMonitor


class TestCircuitBreaker:
    """Tests for CircuitBreaker"""

    @pytest.fixture
    def cb(self):
        return CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=3, success_threshold=2, timeout_seconds=1))

    def test_initial_state_closed(self, cb):
        assert cb.state == CircuitState.CLOSED

    def test_can_execute_when_closed(self, cb):
        assert cb.can_execute() is True

    def test_opens_after_failures(self, cb):
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_cannot_execute_when_open(self, cb):
        for _ in range(3):
            cb.record_failure()
        assert cb.can_execute() is False

    def test_transitions_to_half_open(self, cb):
        for _ in range(3):
            cb.record_failure()
        time.sleep(1.1)
        assert cb.state == CircuitState.HALF_OPEN

    def test_closes_after_successes_in_half_open(self, cb):
        for _ in range(3):
            cb.record_failure()
        time.sleep(1.1)
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_success()
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_get_stats(self, cb):
        cb.record_success()
        cb.record_failure()
        stats = cb.get_stats()
        assert stats["total_calls"] == 2

    def test_reset(self, cb):
        for _ in range(3):
            cb.record_failure()
        cb.reset()
        assert cb.state == CircuitState.CLOSED

    def test_force_open(self, cb):
        cb.force_open()
        assert cb.state == CircuitState.OPEN


class TestTransformer:
    """Tests for Transformer"""

    @pytest.fixture
    def transformer(self):
        return Transformer()

    def test_transform_request(self, transformer):
        def add_header(data):
            if "headers" not in data:
                data["headers"] = {}
            data["headers"]["X-Custom"] = "test"
            return data

        transformer.add_rule("add_header", add_header, TransformPhase.REQUEST)
        result = transformer.transform_request({"body": "test"})
        assert result["headers"]["X-Custom"] == "test"

    def test_transform_response(self, transformer):
        def add_timestamp(data):
            data["timestamp"] = 12345
            return data

        transformer.add_rule("add_ts", add_timestamp, TransformPhase.RESPONSE)
        result = transformer.transform_response({"status": 200})
        assert result["timestamp"] == 12345

    def test_disable_rule(self, transformer):
        def modify(data):
            data["modified"] = True
            return data

        transformer.add_rule("test", modify)
        transformer.disable_rule("test")
        result = transformer.transform_request({})
        assert "modified" not in result

    def test_enable_rule(self, transformer):
        def modify(data):
            data["modified"] = True
            return data

        transformer.add_rule("test", modify)
        transformer.disable_rule("test")
        transformer.enable_rule("test")
        result = transformer.transform_request({})
        assert result["modified"] is True

    def test_remove_rule(self, transformer):
        transformer.add_rule("test", lambda x: x)
        result = transformer.remove_rule("test")
        assert result is True

    def test_get_rules(self, transformer):
        transformer.add_rule("test", lambda x: x)
        rules = transformer.get_rules()
        assert len(rules) == 1

    def test_get_metrics(self, transformer):
        transformer.add_rule("test", lambda x: x)
        transformer.transform_request({})
        metrics = transformer.get_metrics()
        assert metrics["requests_transformed"] == 1

    def test_clear_rules(self, transformer):
        transformer.add_rule("test", lambda x: x)
        count = transformer.clear_rules()
        assert count == 1


class TestAPIMonitor:
    """Tests for APIMonitor"""

    @pytest.fixture
    def monitor(self):
        return APIMonitor(max_metrics=100)

    def test_record_request(self, monitor):
        monitor.record_request("req_001", "/api/test", "GET", 200, 50.0)
        metrics = monitor.get_metrics(limit=1)
        assert len(metrics) == 1
        assert metrics[0]["endpoint"] == "/api/test"

    def test_get_endpoint_stats(self, monitor):
        monitor.record_request("req_001", "/api/test", "GET", 200, 50.0)
        monitor.record_request("req_002", "/api/test", "GET", 500, 100.0, error="Internal Error")

        stats = monitor.get_endpoint_stats("/api/test")
        assert stats["count"] == 2
        assert stats["errors"] == 1

    def test_get_all_endpoint_stats(self, monitor):
        monitor.record_request("req_001", "/api/a", "GET", 200, 50.0)
        monitor.record_request("req_002", "/api/b", "GET", 200, 50.0)

        stats = monitor.get_endpoint_stats()
        assert "/api/a" in stats
        assert "/api/b" in stats

    def test_get_latency_stats(self, monitor):
        monitor.record_request("req_001", "/api/test", "GET", 200, 10.0)
        monitor.record_request("req_002", "/api/test", "GET", 200, 20.0)
        monitor.record_request("req_003", "/api/test", "GET", 200, 30.0)

        stats = monitor.get_latency_stats()
        assert stats["avg"] == 20.0
        assert stats["min"] == 10.0
        assert stats["max"] == 30.0

    def test_get_summary(self, monitor):
        monitor.record_request("req_001", "/api/test", "GET", 200, 50.0)
        monitor.record_request("req_002", "/api/test", "GET", 500, 100.0, error="Error")

        summary = monitor.get_summary()
        assert summary["total_requests"] == 2
        assert summary["total_errors"] == 1
        assert summary["error_rate"] == 50.0

    def test_clear_metrics(self, monitor):
        monitor.record_request("req_001", "/api/test", "GET", 200, 50.0)
        count = monitor.clear_metrics()
        assert count == 1

    def test_tenant_tracking(self, monitor):
        monitor.record_request("req_001", "/api/test", "GET", 200, 50.0, tenant_id="tenant_001")
        summary = monitor.get_summary()
        assert summary["unique_tenants"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
