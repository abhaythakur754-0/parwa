"""
Tests for API Gateway remaining modules (Builders 3, 4, 5)
- Circuit Breaker
- Transformer
- API Monitor
"""

import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from enterprise.api_gateway.circuit_breaker import (
    CircuitBreaker, CircuitState, CircuitBreakerConfig,
    CircuitStats, CircuitBreakerRegistry
)
from enterprise.api_gateway.transformer import (
    Transformer, TransformRule, TransformType, TransformContext,
    TransformResult, create_header_add_rule, create_header_remove_rule,
    create_body_transform_rule
)
from enterprise.api_gateway.api_monitor import (
    APIMonitor, RequestMetric, EndpointMetrics, LatencyStats
)


# =============================================================================
# CIRCUIT BREAKER TESTS
# =============================================================================

class TestCircuitBreakerConfig:
    """Tests for CircuitBreakerConfig"""

    def test_default_config(self):
        config = CircuitBreakerConfig()
        assert config.failure_threshold == 5
        assert config.success_threshold == 3
        assert config.recovery_timeout == 30.0
        assert config.half_open_max_calls == 1

    def test_custom_config(self):
        config = CircuitBreakerConfig(
            failure_threshold=10,
            success_threshold=5,
            recovery_timeout=60.0,
            half_open_max_calls=3
        )
        assert config.failure_threshold == 10
        assert config.success_threshold == 5
        assert config.recovery_timeout == 60.0
        assert config.half_open_max_calls == 3


class TestCircuitBreaker:
    """Tests for CircuitBreaker"""

    @pytest.fixture
    def circuit_breaker(self):
        return CircuitBreaker(
            name="test-cb",
            config=CircuitBreakerConfig(
                failure_threshold=3,
                success_threshold=2,
                recovery_timeout=1.0
            )
        )

    def test_initial_state_is_closed(self, circuit_breaker):
        assert circuit_breaker.get_state() == CircuitState.CLOSED

    def test_can_execute_when_closed(self, circuit_breaker):
        assert circuit_breaker.can_execute() is True

    def test_record_success_in_closed_state(self, circuit_breaker):
        circuit_breaker.record_success()
        assert circuit_breaker.get_state() == CircuitState.CLOSED
        stats = circuit_breaker.get_stats()
        assert stats.successful_requests == 1
        assert stats.consecutive_successes == 1

    def test_record_failure_in_closed_state(self, circuit_breaker):
        circuit_breaker.record_failure()
        assert circuit_breaker.get_state() == CircuitState.CLOSED
        stats = circuit_breaker.get_stats()
        assert stats.failed_requests == 1
        assert stats.consecutive_failures == 1

    def test_opens_after_failure_threshold(self, circuit_breaker):
        # Record failures up to threshold
        for _ in range(3):
            circuit_breaker.record_failure()

        assert circuit_breaker.get_state() == CircuitState.OPEN

    def test_cannot_execute_when_open(self, circuit_breaker):
        # Force open
        for _ in range(3):
            circuit_breaker.record_failure()

        assert circuit_breaker.can_execute() is False

    def test_transitions_to_half_open_after_timeout(self, circuit_breaker):
        # Force open
        for _ in range(3):
            circuit_breaker.record_failure()

        assert circuit_breaker.get_state() == CircuitState.OPEN

        # Wait for recovery timeout
        time.sleep(1.1)

        # Should transition to half-open on next can_execute
        assert circuit_breaker.can_execute() is True
        assert circuit_breaker.get_state() == CircuitState.HALF_OPEN

    def test_half_open_to_closed_on_successes(self, circuit_breaker):
        # Force open
        for _ in range(3):
            circuit_breaker.record_failure()

        # Wait for recovery timeout
        time.sleep(1.1)
        circuit_breaker.can_execute()  # Trigger half-open

        # Record successes
        circuit_breaker.record_success()
        circuit_breaker.record_success()

        assert circuit_breaker.get_state() == CircuitState.CLOSED

    def test_half_open_to_open_on_failure(self, circuit_breaker):
        # Force open
        for _ in range(3):
            circuit_breaker.record_failure()

        # Wait for recovery timeout
        time.sleep(1.1)
        circuit_breaker.can_execute()  # Trigger half-open

        # Record failure
        circuit_breaker.record_failure()

        assert circuit_breaker.get_state() == CircuitState.OPEN

    def test_reset(self, circuit_breaker):
        # Force open
        for _ in range(3):
            circuit_breaker.record_failure()

        circuit_breaker.reset()
        assert circuit_breaker.get_state() == CircuitState.CLOSED
        stats = circuit_breaker.get_stats()
        assert stats.total_requests == 0

    def test_force_open(self, circuit_breaker):
        circuit_breaker.force_open()
        assert circuit_breaker.get_state() == CircuitState.OPEN

    def test_force_close(self, circuit_breaker):
        circuit_breaker.force_open()
        circuit_breaker.force_close()
        assert circuit_breaker.get_state() == CircuitState.CLOSED

    def test_get_metrics(self, circuit_breaker):
        circuit_breaker.record_success()
        circuit_breaker.record_failure()

        metrics = circuit_breaker.get_metrics()
        assert metrics["name"] == "test-cb"
        assert metrics["state"] == "closed"
        assert metrics["total_requests"] == 2
        assert metrics["successful_requests"] == 1
        assert metrics["failed_requests"] == 1

    def test_get_stats(self, circuit_breaker):
        circuit_breaker.record_success()
        stats = circuit_breaker.get_stats()
        assert isinstance(stats, CircuitStats)
        assert stats.successful_requests == 1


class TestCircuitBreakerRegistry:
    """Tests for CircuitBreakerRegistry"""

    @pytest.fixture
    def registry(self):
        return CircuitBreakerRegistry()

    def test_get_or_create(self, registry):
        cb1 = registry.get_or_create("service-a")
        assert cb1 is not None
        assert cb1.name == "service-a"

        cb2 = registry.get_or_create("service-a")
        assert cb1 is cb2  # Same instance

    def test_get(self, registry):
        registry.get_or_create("service-a")
        cb = registry.get("service-a")
        assert cb is not None

        assert registry.get("nonexistent") is None

    def test_remove(self, registry):
        registry.get_or_create("service-a")
        result = registry.remove("service-a")
        assert result is True
        assert registry.get("service-a") is None

    def test_get_all_states(self, registry):
        registry.get_or_create("service-a")
        registry.get_or_create("service-b")

        states = registry.get_all_states()
        assert "service-a" in states
        assert "service-b" in states
        assert states["service-a"] == CircuitState.CLOSED

    def test_get_all_metrics(self, registry):
        registry.get_or_create("service-a")
        metrics = registry.get_all_metrics()
        assert "service-a" in metrics

    def test_reset_all(self, registry):
        cb = registry.get_or_create("service-a")
        cb.force_open()

        registry.reset_all()
        assert cb.get_state() == CircuitState.CLOSED


# =============================================================================
# TRANSFORMER TESTS
# =============================================================================

class TestTransformRule:
    """Tests for TransformRule"""

    def test_default_rule(self):
        rule = TransformRule(
            name="test-rule",
            transform_type=TransformType.HEADER_ADD
        )
        assert rule.enabled is True
        assert rule.priority == 0

    def test_custom_rule(self):
        rule = TransformRule(
            name="test-rule",
            transform_type=TransformType.HEADER_ADD,
            target="X-Custom-Header",
            value="test-value",
            priority=10
        )
        assert rule.target == "X-Custom-Header"
        assert rule.value == "test-value"
        assert rule.priority == 10


class TestTransformer:
    """Tests for Transformer"""

    @pytest.fixture
    def transformer(self):
        return Transformer(name="test-transformer")

    def test_transform_request_empty(self, transformer):
        result = transformer.transform_request(headers={})
        assert result.success is True
        assert "headers" in result.data

    def test_add_header_transform(self, transformer):
        rule = TransformRule(
            name="add-api-version",
            transform_type=TransformType.HEADER_ADD,
            target="X-API-Version",
            value="v1"
        )
        transformer.add_transform(rule, "request")

        result = transformer.transform_request(headers={})
        assert result.success is True
        assert result.data["headers"]["X-API-Version"] == "v1"
        assert "add-api-version" in result.transforms_applied

    def test_remove_header_transform(self, transformer):
        rule = TransformRule(
            name="remove-auth",
            transform_type=TransformType.HEADER_REMOVE,
            source="Authorization"
        )
        transformer.add_transform(rule, "request")

        result = transformer.transform_request(
            headers={"Authorization": "Bearer token", "Content-Type": "application/json"}
        )
        assert result.success is True
        assert "Authorization" not in result.data["headers"]
        assert "Content-Type" in result.data["headers"]

    def test_rename_header_transform(self, transformer):
        rule = TransformRule(
            name="rename-token",
            transform_type=TransformType.HEADER_RENAME,
            source="X-Old-Token",
            target="X-New-Token"
        )
        transformer.add_transform(rule, "request")

        result = transformer.transform_request(
            headers={"X-Old-Token": "value123"}
        )
        assert result.success is True
        assert "X-New-Token" in result.data["headers"]
        assert result.data["headers"]["X-New-Token"] == "value123"
        assert "X-Old-Token" not in result.data["headers"]

    def test_body_transform(self, transformer):
        def uppercase_body(body):
            if isinstance(body, dict):
                return {k: v.upper() if isinstance(v, str) else v for k, v in body.items()}
            return body

        rule = TransformRule(
            name="uppercase-values",
            transform_type=TransformType.BODY_TRANSFORM,
            transform_func=uppercase_body
        )
        transformer.add_transform(rule, "request")

        result = transformer.transform_request(
            headers={},
            body={"name": "test", "value": "hello"}
        )
        assert result.success is True
        assert result.data["body"]["name"] == "TEST"
        assert result.data["body"]["value"] == "HELLO"

    def test_query_add_transform(self, transformer):
        rule = TransformRule(
            name="add-api-key",
            transform_type=TransformType.QUERY_ADD,
            target="api_key",
            value="default-key"
        )
        transformer.add_transform(rule, "request")

        result = transformer.transform_request(
            headers={},
            query_params={"page": "1"}
        )
        assert result.success is True
        assert result.data["query_params"]["api_key"] == "default-key"

    def test_query_remove_transform(self, transformer):
        rule = TransformRule(
            name="remove-internal",
            transform_type=TransformType.QUERY_REMOVE,
            source="internal_token"
        )
        transformer.add_transform(rule, "request")

        result = transformer.transform_request(
            headers={},
            query_params={"internal_token": "secret", "page": "1"}
        )
        assert result.success is True
        assert "internal_token" not in result.data["query_params"]

    def test_path_rewrite_transform(self, transformer):
        rule = TransformRule(
            name="rewrite-legacy",
            transform_type=TransformType.PATH_REWRITE,
            source=r"/v1/",
            target="/v2/"
        )
        transformer.add_transform(rule, "request")

        result = transformer.transform_request(
            headers={},
            path="/v1/users/123"
        )
        assert result.success is True
        assert result.data["path"] == "/v2/users/123"

    def test_transform_response(self, transformer):
        rule = TransformRule(
            name="add-server-header",
            transform_type=TransformType.HEADER_ADD,
            target="X-Server",
            value="api-gateway"
        )
        transformer.add_transform(rule, "response")

        result = transformer.transform_response(headers={})
        assert result.success is True
        assert result.data["headers"]["X-Server"] == "api-gateway"

    def test_priority_ordering(self, transformer):
        # Lower priority runs after higher priority
        rule1 = TransformRule(
            name="low-priority",
            transform_type=TransformType.HEADER_ADD,
            target="X-Order",
            value="first",
            priority=1
        )
        rule2 = TransformRule(
            name="high-priority",
            transform_type=TransformType.HEADER_ADD,
            target="X-Order",
            value="second",
            priority=10
        )
        transformer.add_transform(rule1, "request")
        transformer.add_transform(rule2, "request")

        result = transformer.transform_request(headers={})
        # High priority runs first, then low priority overwrites
        assert result.data["headers"]["X-Order"] == "first"

    def test_conditional_transform(self, transformer):
        def condition(data):
            return "X-Skip-Transform" not in data.get("headers", {})

        rule = TransformRule(
            name="conditional-header",
            transform_type=TransformType.HEADER_ADD,
            target="X-Added",
            value="yes",
            condition=condition
        )
        transformer.add_transform(rule, "request")

        # Without skip header
        result1 = transformer.transform_request(headers={})
        assert result1.data["headers"].get("X-Added") == "yes"

        # With skip header
        result2 = transformer.transform_request(headers={"X-Skip-Transform": "true"})
        assert result2.data["headers"].get("X-Added") is None

    def test_remove_transform(self, transformer):
        rule = TransformRule(
            name="test-rule",
            transform_type=TransformType.HEADER_ADD,
            target="X-Test",
            value="test"
        )
        transformer.add_transform(rule, "request")

        result = transformer.remove_transform("test-rule", "request")
        assert result is True
        assert len(transformer.get_all_transforms("request")) == 0

    def test_enable_disable_transform(self, transformer):
        rule = TransformRule(
            name="test-rule",
            transform_type=TransformType.HEADER_ADD,
            target="X-Test",
            value="test"
        )
        transformer.add_transform(rule, "request")

        transformer.disable_transform("test-rule", "request")
        result = transformer.transform_request(headers={})
        assert "X-Test" not in result.data["headers"]

        transformer.enable_transform("test-rule", "request")
        result = transformer.transform_request(headers={})
        assert result.data["headers"]["X-Test"] == "test"

    def test_get_metrics(self, transformer):
        rule = TransformRule(
            name="test-rule",
            transform_type=TransformType.HEADER_ADD,
            target="X-Test",
            value="test"
        )
        transformer.add_transform(rule, "request")

        transformer.transform_request(headers={})
        metrics = transformer.get_metrics()
        assert metrics["total_transforms"] == 1
        assert metrics["successful_transforms"] == 1

    def test_clear_transforms(self, transformer):
        transformer.add_transform(TransformRule("r1", TransformType.HEADER_ADD), "request")
        transformer.add_transform(TransformRule("r2", TransformType.HEADER_ADD), "response")

        transformer.clear_transforms("request")
        assert len(transformer.get_all_transforms("request")) == 0
        assert len(transformer.get_all_transforms("response")) == 1


class TestConvenienceFunctions:
    """Tests for convenience functions"""

    def test_create_header_add_rule(self):
        rule = create_header_add_rule("add-version", "X-Version", "v1")
        assert rule.name == "add-version"
        assert rule.transform_type == TransformType.HEADER_ADD
        assert rule.target == "X-Version"
        assert rule.value == "v1"

    def test_create_header_remove_rule(self):
        rule = create_header_remove_rule("remove-auth", "Authorization")
        assert rule.name == "remove-auth"
        assert rule.transform_type == TransformType.HEADER_REMOVE
        assert rule.source == "Authorization"

    def test_create_body_transform_rule(self):
        func = lambda x: x
        rule = create_body_transform_rule("transform-body", func)
        assert rule.name == "transform-body"
        assert rule.transform_type == TransformType.BODY_TRANSFORM
        assert rule.transform_func is func


# =============================================================================
# API MONITOR TESTS
# =============================================================================

class TestAPIMonitor:
    """Tests for APIMonitor"""

    @pytest.fixture
    def monitor(self):
        return APIMonitor(name="test-monitor")

    def test_initial_state(self, monitor):
        metrics = monitor.get_metrics()
        assert metrics["global"]["total_requests"] == 0

    def test_record_request(self, monitor):
        monitor.record_request(
            request_id="req-001",
            endpoint="/api/users",
            method="GET",
            status_code=200,
            latency_ms=50.0
        )

        metrics = monitor.get_metrics()
        assert metrics["global"]["total_requests"] == 1
        assert metrics["global"]["successful_requests"] == 1

    def test_record_failed_request(self, monitor):
        monitor.record_request(
            request_id="req-001",
            endpoint="/api/users",
            method="GET",
            status_code=500,
            latency_ms=100.0,
            error="Internal server error"
        )

        metrics = monitor.get_metrics()
        assert metrics["global"]["total_requests"] == 1
        assert metrics["global"]["failed_requests"] == 1

    def test_record_request_with_tenant(self, monitor):
        monitor.record_request(
            request_id="req-001",
            endpoint="/api/users",
            method="GET",
            status_code=200,
            latency_ms=50.0,
            tenant_id="tenant-001"
        )

        tenant_metrics = monitor.get_tenant_metrics("tenant-001")
        assert tenant_metrics["tenant_id"] == "tenant-001"
        assert tenant_metrics["total_requests"] == 1

    def test_get_endpoint_metrics(self, monitor):
        monitor.record_request(
            request_id="req-001",
            endpoint="/api/users",
            method="GET",
            status_code=200,
            latency_ms=50.0
        )
        monitor.record_request(
            request_id="req-002",
            endpoint="/api/users",
            method="POST",
            status_code=201,
            latency_ms=75.0
        )

        metrics = monitor.get_metrics(endpoint="/api/users")
        assert metrics["endpoint"] == "/api/users"
        assert metrics["total_requests"] == 2

    def test_get_latency_stats(self, monitor):
        for i in range(10):
            monitor.record_request(
                request_id=f"req-{i}",
                endpoint="/api/test",
                method="GET",
                status_code=200,
                latency_ms=float(i * 10 + 10)
            )

        stats = monitor.get_latency_stats("/api/test")
        assert stats.min_ms == 10.0
        assert stats.max_ms == 100.0
        assert stats.avg_ms == 55.0
        assert stats.p50_ms > 0
        assert stats.p95_ms > 0
        assert stats.p99_ms > 0

    def test_get_latency_stats_all_endpoints(self, monitor):
        for i in range(5):
            monitor.record_request(
                request_id=f"req-{i}",
                endpoint="/api/test1",
                method="GET",
                status_code=200,
                latency_ms=10.0
            )
            monitor.record_request(
                request_id=f"req-{i + 5}",
                endpoint="/api/test2",
                method="GET",
                status_code=200,
                latency_ms=20.0
            )

        stats = monitor.get_latency_stats()
        assert stats.min_ms == 10.0
        assert stats.max_ms == 20.0

    def test_get_error_summary(self, monitor):
        monitor.record_request(
            request_id="req-001",
            endpoint="/api/users",
            method="GET",
            status_code=200,
            latency_ms=50.0
        )
        monitor.record_request(
            request_id="req-002",
            endpoint="/api/users",
            method="GET",
            status_code=500,
            latency_ms=100.0,
            error="Database error"
        )

        summary = monitor.get_error_summary("/api/users")
        assert summary["total_errors"] == 1
        assert summary["error_rate"] == 50.0
        assert "Database error" in summary["recent_errors"]

    def test_get_recent_requests(self, monitor):
        for i in range(5):
            monitor.record_request(
                request_id=f"req-{i}",
                endpoint="/api/test",
                method="GET",
                status_code=200,
                latency_ms=50.0
            )

        recent = monitor.get_recent_requests(limit=3)
        assert len(recent) == 3

    def test_get_recent_requests_filtered(self, monitor):
        monitor.record_request(
            request_id="req-001",
            endpoint="/api/users",
            method="GET",
            status_code=200,
            latency_ms=50.0,
            tenant_id="tenant-001"
        )
        monitor.record_request(
            request_id="req-002",
            endpoint="/api/orders",
            method="GET",
            status_code=200,
            latency_ms=50.0,
            tenant_id="tenant-002"
        )

        filtered = monitor.get_recent_requests(endpoint="/api/users")
        assert len(filtered) == 1
        assert filtered[0]["endpoint"] == "/api/users"

        filtered2 = monitor.get_recent_requests(tenant_id="tenant-001")
        assert len(filtered2) == 1

    def test_get_top_endpoints_by_requests(self, monitor):
        # Add different request counts
        for i in range(10):
            monitor.record_request("req", "/api/users", "GET", 200, 10.0)
        for i in range(5):
            monitor.record_request("req", "/api/orders", "GET", 200, 10.0)
        for i in range(3):
            monitor.record_request("req", "/api/products", "GET", 200, 10.0)

        top = monitor.get_top_endpoints(by="requests", limit=2)
        assert len(top) == 2
        assert top[0]["endpoint"] == "/api/users"
        assert top[0]["total_requests"] == 10

    def test_get_top_endpoints_by_errors(self, monitor):
        monitor.record_request("req", "/api/users", "GET", 500, 10.0, error="e1")
        monitor.record_request("req", "/api/users", "GET", 500, 10.0, error="e2")
        monitor.record_request("req", "/api/orders", "GET", 500, 10.0, error="e3")

        top = monitor.get_top_endpoints(by="errors")
        assert top[0]["endpoint"] == "/api/users"
        assert top[0]["failed_requests"] == 2

    def test_reset_metrics(self, monitor):
        monitor.record_request("req", "/api/test", "GET", 200, 50.0)
        monitor.reset_metrics()

        metrics = monitor.get_metrics()
        assert metrics["global"]["total_requests"] == 0

    def test_reset_endpoint_metrics(self, monitor):
        monitor.record_request("req", "/api/test1", "GET", 200, 50.0)
        monitor.record_request("req", "/api/test2", "GET", 200, 50.0)

        monitor.reset_metrics(endpoint="/api/test1")

        metrics = monitor.get_metrics()
        assert "/api/test2" in metrics["endpoints"]
        # test1 should be gone or have 0 requests

    def test_get_health(self, monitor):
        # All successful
        for i in range(10):
            monitor.record_request("req", "/api/test", "GET", 200, 50.0)

        health = monitor.get_health()
        assert health["status"] == "healthy"
        assert health["success_rate"] == 100.0

    def test_get_health_degraded(self, monitor):
        # 96% success rate
        for i in range(96):
            monitor.record_request("req", "/api/test", "GET", 200, 50.0)
        for i in range(4):
            monitor.record_request("req", "/api/test", "GET", 500, 50.0)

        health = monitor.get_health()
        assert health["status"] == "degraded"

    def test_get_health_unhealthy(self, monitor):
        # 90% success rate
        for i in range(90):
            monitor.record_request("req", "/api/test", "GET", 200, 50.0)
        for i in range(10):
            monitor.record_request("req", "/api/test", "GET", 500, 50.0)

        health = monitor.get_health()
        assert health["status"] == "unhealthy"

    def test_status_code_tracking(self, monitor):
        monitor.record_request("req", "/api/test", "GET", 200, 50.0)
        monitor.record_request("req", "/api/test", "GET", 200, 50.0)
        monitor.record_request("req", "/api/test", "GET", 404, 50.0)
        monitor.record_request("req", "/api/test", "GET", 500, 50.0)

        metrics = monitor.get_metrics(endpoint="/api/test")
        assert metrics["status_codes"][200] == 2
        assert metrics["status_codes"][404] == 1
        assert metrics["status_codes"][500] == 1


class TestLatencyStats:
    """Tests for LatencyStats dataclass"""

    def test_default_stats(self):
        stats = LatencyStats()
        assert stats.min_ms == 0.0
        assert stats.max_ms == 0.0
        assert stats.avg_ms == 0.0

    def test_custom_stats(self):
        stats = LatencyStats(
            min_ms=10.0,
            max_ms=100.0,
            avg_ms=50.0,
            p50_ms=45.0,
            p95_ms=95.0,
            p99_ms=99.0
        )
        assert stats.min_ms == 10.0
        assert stats.p99_ms == 99.0


class TestRequestMetric:
    """Tests for RequestMetric dataclass"""

    def test_default_metric(self):
        metric = RequestMetric(
            request_id="req-001",
            endpoint="/api/test",
            method="GET",
            status_code=200,
            latency_ms=50.0
        )
        assert metric.request_id == "req-001"
        assert metric.tenant_id is None
        assert metric.error is None
        assert metric.timestamp is not None

    def test_full_metric(self):
        metric = RequestMetric(
            request_id="req-001",
            endpoint="/api/test",
            method="POST",
            status_code=500,
            latency_ms=100.0,
            tenant_id="tenant-001",
            error="Database error",
            metadata={"key": "value"}
        )
        assert metric.tenant_id == "tenant-001"
        assert metric.error == "Database error"
        assert metric.metadata["key"] == "value"


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestIntegration:
    """Integration tests for all modules"""

    def test_circuit_breaker_with_monitor(self):
        """Test circuit breaker with monitoring"""
        monitor = APIMonitor()
        cb = CircuitBreaker(
            "test-service",
            CircuitBreakerConfig(failure_threshold=3, recovery_timeout=0.5)
        )

        # Record some failures
        for i in range(3):
            if cb.can_execute():
                # Simulate failure
                cb.record_failure()
                monitor.record_request(
                    f"req-{i}",
                    "/api/service",
                    "GET",
                    500,
                    100.0,
                    error="Service unavailable"
                )

        # Circuit should be open
        assert cb.get_state() == CircuitState.OPEN
        assert cb.can_execute() is False

        # Check monitor captured failures
        metrics = monitor.get_metrics()
        assert metrics["global"]["failed_requests"] == 3

    def test_transformer_with_circuit_breaker(self):
        """Test transformer integration with circuit breaker"""
        transformer = Transformer()
        cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=2))

        # Add transform
        transformer.add_transform(
            TransformRule("add-header", TransformType.HEADER_ADD, target="X-Request-ID", value="123"),
            "request"
        )

        # Transform request
        result = transformer.transform_request(headers={})

        # Simulate processing with circuit breaker
        if cb.can_execute():
            # Simulate success
            cb.record_success()

        assert cb.get_state() == CircuitState.CLOSED
        assert result.data["headers"]["X-Request-ID"] == "123"

    def test_full_api_gateway_workflow(self):
        """Test full workflow: transform -> monitor -> circuit breaker"""
        monitor = APIMonitor()
        transformer = Transformer()
        cb = CircuitBreaker("api-service", CircuitBreakerConfig(failure_threshold=5))

        # Setup transformer
        transformer.add_transform(
            TransformRule("add-tenant", TransformType.HEADER_ADD, target="X-Tenant-ID", value="tenant-001"),
            "request"
        )

        # Process requests
        for i in range(10):
            # Transform request
            result = transformer.transform_request(headers={"Content-Type": "application/json"})

            # Check circuit breaker
            if cb.can_execute():
                # Simulate request processing
                latency = 50.0 + (i * 5)
                status = 200 if i < 8 else 500  # Last 2 fail

                if status == 200:
                    cb.record_success()
                else:
                    cb.record_failure()

                # Record in monitor
                monitor.record_request(
                    f"req-{i}",
                    "/api/data",
                    "GET",
                    status,
                    latency,
                    tenant_id="tenant-001",
                    error="Error" if status != 200 else None
                )

        # Verify metrics
        metrics = monitor.get_metrics()
        assert metrics["global"]["total_requests"] == 10

        health = monitor.get_health()
        assert health["success_rate"] == 80.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
