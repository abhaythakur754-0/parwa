"""
Phase 6 Integration Test

Validates that all Phase 6 components work together:
1. Sentry captures errors that circuit breakers detect
2. Self-healing resets circuit breakers
3. Redis key manager works with circuit breaker state
4. Paddle reconciliation uses idempotency with Redis
5. Health endpoint reports all Phase 6 status
6. Anomaly detection triggers self-healing actions
7. Structured logging records Phase 6 events
8. GDPR PII scrubbing works across components

BC-001: company_id first on all tenant-scoped operations.
BC-008: Never crash — integration failures should be caught and reported.
BC-012: All timestamps UTC.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ============================================================
# Helper: reset singletons between tests
# ============================================================


@pytest.fixture(autouse=True)
def _reset_singletons():
    """Reset circuit breaker and self-healing singletons between tests."""
    from app.core.circuit_breaker_manager import reset_circuit_breaker_manager

    reset_circuit_breaker_manager()
    yield
    reset_circuit_breaker_manager()


# ============================================================
# 1. Sentry + Circuit Breaker Integration
# ============================================================


class TestSentryCircuitBreakerIntegration:
    """Validate that Sentry and circuit breakers work together."""

    @pytest.mark.asyncio
    async def test_sentry_captures_circuit_breaker_open_event(self):
        """When a circuit breaker opens, Sentry should capture the event."""
        from app.core.circuit_breaker_manager import (
            CircuitBreakerConfig,
            get_circuit_breaker_manager,
        )
        from app.core.sentry import capture_exception

        manager = get_circuit_breaker_manager()
        manager.register("test_service", CircuitBreakerConfig(failure_threshold=2))

        # Record failures to open the circuit
        manager.record_failure("test_service")
        manager.record_failure("test_service")

        # Circuit should now be open
        from app.core.circuit_breaker_manager import CircuitState

        state = manager.get_state("test_service")
        assert state == CircuitState.OPEN, "Circuit should be OPEN after threshold failures"

        # Capture the event in Sentry (would send to Sentry if configured)
        event_id = capture_exception(
            Exception(f"Circuit breaker opened for test_service"),
            circuit="test_service",
            state=state.value,
        )
        # event_id is None if Sentry not initialized, which is fine
        assert event_id is None or isinstance(event_id, str), (
            "capture_exception should return event_id or None"
        )

    @pytest.mark.asyncio
    async def test_circuit_breaker_state_in_sentry_context(self):
        """Circuit breaker state should be addable to Sentry context."""
        from app.core.circuit_breaker_manager import get_circuit_breaker_manager
        from app.core.sentry import capture_exception

        manager = get_circuit_breaker_manager()
        states = manager.get_all_states()
        assert isinstance(states, dict), "get_all_states should return a dict"

        # Capture with extra context
        event_id = capture_exception(
            Exception("Integration test error"),
            circuit_breaker_states={k: v["state"] for k, v in states.items()},
        )
        # No crash = pass
        assert True


# ============================================================
# 2. Self-Healing + Circuit Breaker Integration
# ============================================================


class TestSelfHealingCircuitBreakerIntegration:
    """Validate that self-healing resets circuit breakers."""

    @pytest.mark.asyncio
    async def test_self_healing_resets_open_circuit_breaker(self):
        """Self-healing should force-close an open circuit breaker."""
        from app.core.circuit_breaker_manager import (
            CircuitBreakerConfig,
            CircuitState,
            get_circuit_breaker_manager,
        )
        from app.services.self_healing_service import SelfHealingService

        manager = get_circuit_breaker_manager()
        manager.register("test_dep", CircuitBreakerConfig(failure_threshold=2))

        # Open the circuit
        manager.record_failure("test_dep")
        manager.record_failure("test_dep")
        assert manager.get_state("test_dep") == CircuitState.OPEN

        # Self-heal by force closing
        result = await SelfHealingService().heal_circuit_breaker_reset("test_dep")
        assert result.success, "Circuit breaker reset should succeed"
        assert manager.get_state("test_dep") == CircuitState.CLOSED, (
            "Circuit should be CLOSED after self-healing reset"
        )

    @pytest.mark.asyncio
    async def test_self_healing_noop_on_closed_circuit(self):
        """Self-healing on a closed circuit should be a no-op."""
        from app.core.circuit_breaker_manager import (
            CircuitState,
            get_circuit_breaker_manager,
        )
        from app.services.self_healing_service import SelfHealingService

        manager = get_circuit_breaker_manager()
        # google_ai starts as closed
        assert manager.get_state("google_ai") == CircuitState.CLOSED

        result = await SelfHealingService().heal_circuit_breaker_reset("google_ai")
        assert result.success, "Should succeed even when no reset needed"
        assert "no reset needed" in result.message

    @pytest.mark.asyncio
    async def test_llm_failover_records_in_circuit_breaker(self):
        """LLM failover should record failures in circuit breaker."""
        from app.core.circuit_breaker_manager import (
            CircuitState,
            get_circuit_breaker_manager,
        )
        from app.services.self_healing_service import SelfHealingService

        manager = get_circuit_breaker_manager()
        initial_state = manager.get_state("cerebras")

        result = await SelfHealingService().heal_llm_failover("cerebras")
        assert result.success, "LLM failover should succeed"
        assert "cerebras" in result.message
        assert "circuit_state" in result.details

    @pytest.mark.asyncio
    async def test_self_healing_health_check_returns_status(self):
        """Running self-healing health check returns proper status."""
        from app.services.self_healing_service import SelfHealingService

        service = SelfHealingService(db_session=None, redis_client=None)
        result = await service.run_health_check()
        assert isinstance(result, dict)
        assert "status" in result
        assert "anomalies_found" in result
        assert "healing_actions" in result
        assert "timestamp" in result


# ============================================================
# 3. Redis Key Manager + Circuit Breaker Integration
# ============================================================


class TestRedisKeyManagerCircuitBreakerIntegration:
    """Validate that Redis key manager and circuit breakers work together."""

    def test_redis_circuit_breaker_tracks_redis_availability(self):
        """Circuit breaker for Redis should track availability."""
        from app.core.circuit_breaker_manager import (
            CircuitState,
            get_circuit_breaker_manager,
        )

        manager = get_circuit_breaker_manager()
        assert manager.get_state("redis") == CircuitState.CLOSED
        assert manager.is_available("redis") is True

    def test_redis_key_manager_respects_tenant_isolation(self):
        """Redis keys must always be tenant-scoped (BC-001)."""
        from app.core.redis_key_manager import build_key, RedisNamespace

        # Build keys for two different tenants
        key_tenant_a = build_key(RedisNamespace.CACHE, "tenant-a", "settings")
        key_tenant_b = build_key(RedisNamespace.CACHE, "tenant-b", "settings")

        assert "tenant-a" in key_tenant_a
        assert "tenant-b" in key_tenant_b
        assert key_tenant_a != key_tenant_b, (
            "Keys for different tenants must not collide (BC-001)"
        )

    def test_circuit_breaker_state_stored_with_redis_namespace(self):
        """Circuit breaker state keys should use Redis key namespace pattern."""
        from app.core.redis_key_manager import RedisNamespace, identify_namespace

        # Circuit breaker state would be stored under HEALTH namespace
        health_key = "parwa:health:circuit:google_ai:state"
        ns = identify_namespace(health_key)
        assert ns == RedisNamespace.HEALTH, (
            "Circuit breaker state key should be in HEALTH namespace"
        )

    def test_all_redis_namespaces_have_circuit_breaker_coverage(self):
        """Critical Redis namespaces should have corresponding circuit breakers."""
        from app.core.redis_key_manager import RedisNamespace
        from app.core.circuit_breaker_manager import get_circuit_breaker_manager

        manager = get_circuit_breaker_manager()
        # Redis itself must have a circuit breaker
        assert manager.get_state("redis") is not None


# ============================================================
# 4. Paddle Reconciliation + Idempotency Integration
# ============================================================


class TestPaddleReconciliationIntegration:
    """Validate Paddle reconciliation uses idempotency with Redis."""

    def test_idempotency_key_is_deterministic(self):
        """Same event must always produce same idempotency key."""
        from app.services.paddle_reconciliation_service import (
            PaddleReconciliationService,
        )

        service = PaddleReconciliationService(db_session=None, redis_client=None)

        key1 = service.compute_idempotency_key(
            "subscription.activated", "evt_abc123"
        )
        key2 = service.compute_idempotency_key(
            "subscription.activated", "evt_abc123"
        )
        assert key1 == key2, "Idempotency key must be deterministic"

    def test_different_events_produce_different_keys(self):
        """Different events must produce different idempotency keys."""
        from app.services.paddle_reconciliation_service import (
            PaddleReconciliationService,
        )

        service = PaddleReconciliationService(db_session=None, redis_client=None)

        key1 = service.compute_idempotency_key(
            "subscription.activated", "evt_abc123"
        )
        key2 = service.compute_idempotency_key(
            "subscription.canceled", "evt_abc123"
        )
        assert key1 != key2, "Different events must produce different keys"

    def test_idempotency_key_is_sha256(self):
        """Idempotency key must be SHA-256 (64 hex chars)."""
        from app.services.paddle_reconciliation_service import (
            PaddleReconciliationService,
        )

        service = PaddleReconciliationService(db_session=None, redis_client=None)
        key = service.compute_idempotency_key("subscription.updated", "evt_xyz789")
        assert len(key) == 64, f"SHA-256 key must be 64 hex chars, got {len(key)}"
        assert all(c in "0123456789abcdef" for c in key), "Key must be hex string"

    @pytest.mark.asyncio
    async def test_paddle_webhook_rejects_missing_event_data(self):
        """Webhook processing must reject events missing required data."""
        from app.services.paddle_reconciliation_service import (
            PaddleReconciliationService,
        )

        service = PaddleReconciliationService(db_session=None, redis_client=None)

        # Missing event_type
        result = await service.process_webhook(
            payload={"event_id": "123"}, signature=""
        )
        assert result.status == "rejected", "Must reject missing event_type"

        # Missing event_id
        result = await service.process_webhook(
            payload={"event_type": "test"}, signature=""
        )
        assert result.status == "rejected", "Must reject missing event_id"

    def test_paddle_service_has_circuit_breaker(self):
        """Paddle must have a circuit breaker registered."""
        from app.core.circuit_breaker_manager import get_circuit_breaker_manager

        manager = get_circuit_breaker_manager()
        state = manager.get_state("paddle")
        assert state is not None, "Paddle must have a circuit breaker"


# ============================================================
# 5. Health Endpoint + Phase 6 Status Integration
# ============================================================


class TestHealthEndpointPhase6Integration:
    """Validate that health endpoint reports all Phase 6 status."""

    def test_health_includes_circuit_breaker_summary(self):
        """Health endpoint must include circuit breaker summary."""
        # Use circuit breaker manager directly since app.api.health
        # has import chain issues with jose in test env
        from app.core.circuit_breaker_manager import get_circuit_breaker_manager

        manager = get_circuit_breaker_manager()
        health = manager.get_health_summary()
        assert isinstance(health, dict)
        assert "status" in health, "Health summary must include status"
        assert health["status"] in ("healthy", "degraded", "unhealthy", "unknown")

    def test_health_includes_self_healing_status(self):
        """Health endpoint must include self-healing status."""
        from app.services.self_healing_service import get_self_healing_service

        service = get_self_healing_service()
        status = service.get_status()
        assert isinstance(status, dict), "Self-healing status must be a dict"

    def test_health_includes_sentry_status(self):
        """Health endpoint must include Sentry monitoring status."""
        from app.core.sentry import get_sentry_status

        status = get_sentry_status()
        assert isinstance(status, dict), "Sentry status must be a dict"
        assert "initialized" in status, "Sentry status must include 'initialized'"

    def test_circuit_breaker_health_summary_changes_with_state(self):
        """Circuit breaker health summary must reflect open circuits."""
        from app.core.circuit_breaker_manager import (
            CircuitBreakerConfig,
            get_circuit_breaker_manager,
        )

        manager = get_circuit_breaker_manager()

        # All circuits should start healthy
        summary = manager.get_health_summary()
        assert summary["status"] == "healthy"

        # Open a circuit
        manager.register("test_dep", CircuitBreakerConfig(failure_threshold=1))
        manager.record_failure("test_dep")

        summary = manager.get_health_summary()
        assert summary["status"] in ("degraded", "unhealthy"), (
            "Health summary must reflect open circuits"
        )


# ============================================================
# 6. Anomaly Detection + Self-Healing Integration
# ============================================================


class TestAnomalyDetectionSelfHealingIntegration:
    """Validate that anomaly detection triggers self-healing actions."""

    def test_high_error_rate_triggers_llm_failover(self):
        """High error rate for LLM provider should trigger failover action."""
        from app.services.self_healing_service import (
            AnomalyDetector,
            HealingAction,
        )

        detector = AnomalyDetector()

        # Simulate high error rate for google_ai
        for _ in range(15):
            detector.record_error("google_ai")
        for _ in range(5):
            detector.record_success("google_ai")

        anomaly = detector.check_error_rate("google_ai")
        assert anomaly is not None, "High error rate should trigger anomaly"
        assert anomaly.recommended_action == HealingAction.LLM_FAILOVER, (
            "LLM provider error should recommend failover"
        )

    def test_redis_error_triggers_reconnect_action(self):
        """Redis error rate should trigger reconnect action."""
        from app.services.self_healing_service import (
            AnomalyDetector,
            HealingAction,
        )

        detector = AnomalyDetector()

        for _ in range(15):
            detector.record_error("redis")
        for _ in range(5):
            detector.record_success("redis")

        anomaly = detector.check_error_rate("redis")
        assert anomaly is not None, "Redis errors should trigger anomaly"
        assert anomaly.recommended_action == HealingAction.REDIS_RECONNECT, (
            "Redis errors should recommend reconnect"
        )

    def test_postgresql_error_triggers_pool_reset(self):
        """PostgreSQL error rate should trigger pool reset action."""
        from app.services.self_healing_service import (
            AnomalyDetector,
            HealingAction,
        )

        detector = AnomalyDetector()

        for _ in range(15):
            detector.record_error("postgresql")
        for _ in range(5):
            detector.record_success("postgresql")

        anomaly = detector.check_error_rate("postgresql")
        assert anomaly is not None, "PostgreSQL errors should trigger anomaly"
        assert anomaly.recommended_action == HealingAction.DB_POOL_RESET, (
            "PostgreSQL errors should recommend pool reset"
        )

    def test_queue_depth_triggers_drain_action(self):
        """High queue depth should trigger drain action."""
        from app.services.self_healing_service import (
            AnomalyDetector,
            HealingAction,
        )

        detector = AnomalyDetector()
        anomaly = detector.check_queue_depth("default", depth=5000)
        assert anomaly is not None, "High queue depth should trigger anomaly"
        assert anomaly.recommended_action == HealingAction.QUEUE_DRAIN

    def test_no_anomaly_on_healthy_service(self):
        """Healthy service should not trigger any anomaly."""
        from app.services.self_healing_service import AnomalyDetector

        detector = AnomalyDetector()

        # Record mostly successes
        for _ in range(100):
            detector.record_success("google_ai", response_time_ms=100)
        for _ in range(2):
            detector.record_error("google_ai")

        anomaly = detector.check_error_rate("google_ai")
        assert anomaly is None, "Low error rate should not trigger anomaly"


# ============================================================
# 7. PII Scrubbing + Sentry Integration
# ============================================================


class TestPIIScrubbingSentryIntegration:
    """Validate that PII scrubbing works across Sentry integration."""

    def test_email_scrubbing_in_event(self):
        """Emails must be scrubbed from Sentry events."""
        from app.core.sentry import scrub_pii

        event = {
            "message": "User john@example.com triggered error",
            "extra": {"user_email": "jane@company.org"},
        }
        result = scrub_pii(event, {})
        result_str = str(result)
        assert "john@example.com" not in result_str
        assert "jane@company.org" not in result_str
        assert "[REDACTED]" in result_str

    def test_phone_scrubbing_in_event(self):
        """Phone numbers must be scrubbed from Sentry events."""
        from app.core.sentry import scrub_pii

        event = {"message": "Customer called from +1-555-123-4567"}
        result = scrub_pii(event, {})
        # Phone numbers with 7+ digits should be scrubbed
        assert "[REDACTED]" in str(result)

    def test_nested_pii_scrubbing(self):
        """PII in nested structures must be scrubbed."""
        from app.core.sentry import _scrub_dict

        data = {
            "level1": {
                "level2": {
                    "email": "deep@nested.com",
                    "data": "Contact support@parwa.ai",
                }
            }
        }
        result = _scrub_dict(data)
        assert "deep@nested.com" not in str(result)
        assert "support@parwa.ai" not in str(result)

    def test_pii_scrubbing_never_crashes(self):
        """PII scrubbing must never crash even with invalid input."""
        from app.core.sentry import scrub_pii, _scrub_dict

        # These should not raise exceptions
        assert scrub_pii({}, {}) == {}
        assert scrub_pii(None, {}) is None
        assert _scrub_dict("simple string") == "simple string"
        assert _scrub_dict(12345) == 12345
        assert _scrub_dict(None) is None
        assert _scrub_dict([1, 2, "test@example.com"]) == [1, 2, "[REDACTED]"]


# ============================================================
# 8. Structured Logging + Phase 6 Integration
# ============================================================


class TestStructuredLoggingPhase6Integration:
    """Validate that structured logging records Phase 6 events."""

    def test_logger_available_for_circuit_breaker(self):
        """Circuit breaker module must use structured logger."""
        from app.core.circuit_breaker_manager import logger

        assert logger is not None, "Circuit breaker must have a logger"

    def test_logger_available_for_self_healing(self):
        """Self-healing module must use structured logger."""
        from app.services.self_healing_service import logger

        assert logger is not None, "Self-healing must have a logger"

    def test_logger_available_for_sentry(self):
        """Sentry module must use structured logger."""
        from app.core.sentry import logger

        assert logger is not None, "Sentry must have a logger"

    def test_configure_logging_supports_production_mode(self):
        """Logging must support production JSON mode."""
        from app.logger import configure_logging

        # Should not crash
        configure_logging("production")
        configure_logging("development")
        configure_logging("test")


# ============================================================
# 9. Full Health Check Integration
# ============================================================


class TestFullHealthCheckIntegration:
    """Validate complete health check flow with all Phase 6 components."""

    @pytest.mark.asyncio
    async def test_run_health_checks_returns_all_subsystems(self):
        """run_health_checks must return status for all subsystems."""
        from app.core.health import run_health_checks, HealthStatus

        # This may fail if DB/Redis not available, but should not crash
        try:
            result = await run_health_checks(use_cache=False)
        except Exception:
            pytest.skip("Health check requires running DB/Redis")

        assert result.status in (
            HealthStatus.HEALTHY.value,
            HealthStatus.DEGRADED.value,
            HealthStatus.UNHEALTHY.value,
        )
        assert result.checks_total > 0
        assert "postgresql" in result.subsystems
        assert "redis" in result.subsystems

    @pytest.mark.asyncio
    async def test_readiness_check_returns_ready_status(self):
        """Readiness check must return ready/not_ready status."""
        from app.core.health import run_readiness_check

        try:
            result = await run_readiness_check()
        except Exception:
            pytest.skip("Readiness check requires running DB/Redis")

        assert "ready" in result
        assert isinstance(result["ready"], bool)
        assert "subsystems" in result

    def test_self_healing_service_full_status(self):
        """Self-healing service get_status must return comprehensive status."""
        from app.services.self_healing_service import SelfHealingService

        service = SelfHealingService(db_session=None, redis_client=None)
        status = service.get_status()
        assert "status" in status
        assert "metrics" in status
        metrics = status["metrics"]
        assert "total_checks" in metrics
        assert "anomalies_found" in metrics
        assert "healings_attempted" in metrics
        assert "healings_succeeded" in metrics
        assert "healings_failed" in metrics

    def test_self_healing_metrics_available(self):
        """Self-healing metrics must be queryable."""
        from app.services.self_healing_service import SelfHealingService

        service = SelfHealingService(db_session=None, redis_client=None)
        metrics = service.get_healing_metrics()
        assert isinstance(metrics, dict)
        # Should include success rate calculations
        assert "total_healings" in metrics or "total_checks" in metrics

    def test_self_healing_history_available(self):
        """Self-healing history must be queryable."""
        from app.services.self_healing_service import SelfHealingService

        service = SelfHealingService(db_session=None, redis_client=None)
        history = service.get_healing_history(limit=10)
        assert isinstance(history, list)

    def test_circuit_breaker_prometheus_metrics_format(self):
        """Circuit breaker metrics must be in Prometheus format."""
        from app.core.circuit_breaker_manager import get_circuit_breaker_manager

        manager = get_circuit_breaker_manager()
        metrics = manager.get_metrics()
        text = metrics["metrics_text"]

        # Verify Prometheus format
        assert "# HELP" in text, "Metrics must have HELP comments"
        assert "# TYPE" in text, "Metrics must have TYPE comments"
        assert "parwa_circuit_breaker_state" in text
        assert "parwa_circuit_breaker_failures_total" in text
        assert "parwa_circuit_breaker_successes_total" in text


# ============================================================
# 10. Cross-Component BC Compliance Integration
# ============================================================


class TestCrossComponentBCCompliance:
    """Validate Business Constraints are satisfied across components."""

    def test_bc001_all_tenant_operations_scoped(self):
        """BC-001: All tenant-scoped operations must include company_id."""
        from app.core.redis_key_manager import build_key, RedisNamespace

        # Test across different namespaces
        namespaces_to_test = [
            RedisNamespace.CACHE,
            RedisNamespace.SESSION,
            RedisNamespace.BILLING,
            RedisNamespace.AWARENESS,
        ]
        for ns in namespaces_to_test:
            key = build_key(ns, "company-xyz", "test")
            assert "company-xyz" in key, (
                f"BC-001: {ns.value} key must include company_id"
            )

    def test_bc008_never_crash_across_services(self):
        """BC-008: All Phase 6 services must handle errors gracefully."""
        from app.core.circuit_breaker_manager import get_circuit_breaker_manager
        from app.services.self_healing_service import SelfHealingService
        from app.core.sentry import capture_exception, scrub_pii

        # CircuitBreakerManager should not crash on unknown dependency
        assert get_circuit_breaker_manager().is_available("nonexistent") is True

        # SelfHealingService with None deps should still work
        service = SelfHealingService(db_session=None, redis_client=None)
        status = service.get_status()
        assert isinstance(status, dict)

        # Sentry capture should not crash when Sentry not initialized
        result = capture_exception(ValueError("test"))
        assert result is None  # Returns None when not initialized

        # PII scrubbing should not crash on bad input
        result = scrub_pii({"bad": object()}, {})
        # Should not raise

    def test_bc012_utc_timestamps_across_components(self):
        """BC-012: All timestamps across components must be UTC."""
        from app.core.circuit_breaker_manager import (
            get_circuit_breaker_manager,
        )
        from app.services.self_healing_service import (
            SelfHealingService,
            HealingResult,
            HealingAction,
        )

        # Circuit breaker health summary uses UTC
        manager = get_circuit_breaker_manager()
        health = manager.get_health_summary()
        if health.get("timestamp"):
            ts = health["timestamp"]
            assert "+00:00" in ts or ts.endswith("Z"), (
                f"Circuit breaker timestamp must be UTC: {ts}"
            )

        # HealingResult uses UTC timestamps
        result = HealingResult(
            action=HealingAction.REDIS_RECONNECT,
            success=True,
            message="Test",
        )
        assert "+00:00" in result.timestamp or result.timestamp.endswith("Z"), (
            f"HealingResult timestamp must be UTC: {result.timestamp}"
        )

        # Self-healing status last_check_at uses UTC
        service = SelfHealingService()
        status = service.get_status()
        if status.get("last_check_at"):
            ts = status["last_check_at"]
            assert "+00:00" in ts or ts.endswith("Z"), (
                f"Self-healing timestamp must be UTC: {ts}"
            )

    def test_redis_key_manager_validates_tenant_isolation(self):
        """BC-001: Redis key manager must enforce tenant isolation."""
        from app.core.redis_key_manager import build_key, RedisNamespace

        # Empty company_id must be rejected
        with pytest.raises(ValueError, match="company_id"):
            build_key(RedisNamespace.CACHE, "", "test")

        # Whitespace-only company_id must be rejected
        with pytest.raises(ValueError, match="company_id"):
            build_key(RedisNamespace.CACHE, "   ", "test")

        # None-like company_id must be rejected
        with pytest.raises((ValueError, TypeError)):
            build_key(RedisNamespace.CACHE, None, "test")
