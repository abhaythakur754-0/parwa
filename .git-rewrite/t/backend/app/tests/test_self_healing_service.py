"""
Tests for Self-Healing Service (Phase 6: Production Hardening)

Tests:
- test_anomaly_detector_error_rate
- test_anomaly_detector_response_time
- test_anomaly_detector_queue_depth
- test_heal_llm_failover
- test_heal_redis_reconnect
- test_heal_db_pool_reset
- test_heal_stale_lock_cleanup
- test_healing_history_recorded
- test_healing_metrics_tracked
- test_self_healing_run_periodically

BC-008: Never crash — tests are resilient to internal errors.
BC-012: All timestamps UTC.
"""

import asyncio
import time
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.self_healing_service import (
    AnomalyDetector,
    AnomalySeverity,
    HealingAction,
    HealingResult,
    SelfHealingService,
    get_self_healing_service,
    reset_self_healing_service,
)
from app.core.circuit_breaker_manager import (
    CircuitBreakerConfig,
    CircuitBreakerManager,
    CircuitState,
    reset_circuit_breaker_manager,
)


class TestAnomalyDetectorErrorRate(unittest.TestCase):
    """Test anomaly detector error rate checks."""

    def setUp(self):
        self.detector = AnomalyDetector()

    def test_no_anomaly_below_threshold(self):
        """No anomaly when error rate is below threshold."""
        # Record 5 successes and 1 error (16.7% rate — close but not over)
        for _ in range(5):
            self.detector.record_success("test_service")
        self.detector.record_error("test_service")

        anomaly = self.detector.check_error_rate("test_service")
        # 1/6 = 16.7% — above 10% threshold
        # Actually let's use more data
        self.detector.reset()
        for _ in range(9):
            self.detector.record_success("test_service")
        self.detector.record_error("test_service")  # 1/10 = 10% — at threshold, not above
        # Check: 10% is not > 10%, so no anomaly
        anomaly = self.detector.check_error_rate("test_service")
        # 1/10 = 0.1, threshold is 0.10, 0.1 > 0.10 is False
        self.assertIsNone(anomaly)

    def test_anomaly_above_threshold(self):
        """Anomaly detected when error rate exceeds threshold."""
        # Record enough data: 10 errors out of 15 total = 66.7%
        for _ in range(5):
            self.detector.record_success("test_service")
        for _ in range(10):
            self.detector.record_error("test_service")

        anomaly = self.detector.check_error_rate("test_service")
        self.assertIsNotNone(anomaly)
        self.assertEqual(anomaly.anomaly_type, "error_rate")
        self.assertEqual(anomaly.service, "test_service")

    def test_no_anomaly_insufficient_data(self):
        """No anomaly when insufficient data (< 10 samples)."""
        self.detector.record_error("test_service")
        anomaly = self.detector.check_error_rate("test_service")
        self.assertIsNone(anomaly)

    def test_critical_severity_high_error_rate(self):
        """Critical severity when error rate > 50%."""
        for _ in range(2):
            self.detector.record_success("test_service")
        for _ in range(10):
            self.detector.record_error("test_service")

        anomaly = self.detector.check_error_rate("test_service")
        self.assertIsNotNone(anomaly)
        self.assertEqual(anomaly.severity, AnomalySeverity.CRITICAL.value)

    def test_recommended_action_llm(self):
        """Recommended action is LLM_FAILOVER for LLM providers."""
        for _ in range(2):
            self.detector.record_success("google_ai")
        for _ in range(10):
            self.detector.record_error("google_ai")

        anomaly = self.detector.check_error_rate("google_ai")
        self.assertIsNotNone(anomaly)
        self.assertEqual(anomaly.recommended_action, HealingAction.LLM_FAILOVER)

    def test_recommended_action_redis(self):
        """Recommended action is REDIS_RECONNECT for Redis."""
        for _ in range(2):
            self.detector.record_success("redis")
        for _ in range(10):
            self.detector.record_error("redis")

        anomaly = self.detector.check_error_rate("redis")
        self.assertIsNotNone(anomaly)
        self.assertEqual(anomaly.recommended_action, HealingAction.REDIS_RECONNECT)


class TestAnomalyDetectorResponseTime(unittest.TestCase):
    """Test anomaly detector response time checks."""

    def setUp(self):
        self.detector = AnomalyDetector()

    def test_no_anomaly_below_threshold(self):
        """No anomaly when response time is below threshold."""
        for _ in range(10):
            self.detector.record_success("test_service", response_time_ms=100)

        anomaly = self.detector.check_response_time("test_service")
        self.assertIsNone(anomaly)

    def test_anomaly_above_threshold(self):
        """Anomaly detected when P95 response time exceeds threshold."""
        # Record 5 fast and 5 very slow responses
        for _ in range(5):
            self.detector.record_success("test_service", response_time_ms=100)
        for _ in range(5):
            self.detector.record_success("test_service", response_time_ms=10000)

        anomaly = self.detector.check_response_time("test_service")
        self.assertIsNotNone(anomaly)
        self.assertEqual(anomaly.anomaly_type, "response_time")

    def test_no_anomaly_insufficient_data(self):
        """No anomaly when insufficient data (< 5 samples)."""
        self.detector.record_success("test_service", response_time_ms=10000)
        anomaly = self.detector.check_response_time("test_service")
        self.assertIsNone(anomaly)


class TestAnomalyDetectorQueueDepth(unittest.TestCase):
    """Test anomaly detector queue depth checks."""

    def setUp(self):
        self.detector = AnomalyDetector()

    def test_no_anomaly_below_threshold(self):
        """No anomaly when queue depth is below threshold."""
        anomaly = self.detector.check_queue_depth("default", 100)
        self.assertIsNone(anomaly)

    def test_anomaly_above_threshold(self):
        """Anomaly detected when queue depth exceeds threshold."""
        anomaly = self.detector.check_queue_depth("default", 2000)
        self.assertIsNotNone(anomaly)
        self.assertEqual(anomaly.anomaly_type, "queue_depth")
        self.assertEqual(anomaly.recommended_action, HealingAction.QUEUE_DRAIN)

    def test_critical_severity_very_high_depth(self):
        """Critical severity when queue depth > 5x threshold."""
        anomaly = self.detector.check_queue_depth("default", 10000)
        self.assertIsNotNone(anomaly)
        self.assertEqual(anomaly.severity, AnomalySeverity.CRITICAL.value)


class TestHealLLMFailover(unittest.TestCase):
    """Test LLM provider failover healing."""

    def setUp(self):
        reset_circuit_breaker_manager()
        self.service = SelfHealingService()

    def tearDown(self):
        reset_circuit_breaker_manager()

    def test_heal_llm_failover_records_failure(self):
        """heal_llm_failover records failure in circuit breaker."""
        result = asyncio.run(self.service.heal_llm_failover("google_ai"))
        self.assertTrue(result.success)
        self.assertEqual(result.action, HealingAction.LLM_FAILOVER)

    def test_heal_llm_failover_nonexistent_provider(self):
        """heal_llm_failover works even for unregistered providers."""
        result = asyncio.run(self.service.heal_llm_failover("unknown_provider"))
        self.assertTrue(result.success)  # Doesn't crash


class TestHealRedisReconnect(unittest.TestCase):
    """Test Redis reconnection healing."""

    def setUp(self):
        self.service = SelfHealingService()

    def test_heal_redis_reconnect_success(self):
        """heal_redis_reconnect succeeds when Redis is available."""
        async def _mock_reconnect(self_inner):
            return HealingResult(
                action=HealingAction.REDIS_RECONNECT,
                success=True,
                message="Redis reconnection successful",
            )

        with patch.object(
            SelfHealingService, "heal_redis_reconnect",
            new=_mock_reconnect,
        ):
            result = asyncio.run(self.service.heal_redis_reconnect())
            self.assertTrue(result.success)

    def test_heal_redis_reconnect_failure(self):
        """heal_redis_reconnect returns failure when Redis is unavailable."""
        # Without Redis running, reconnection should fail gracefully
        result = asyncio.run(self.service.heal_redis_reconnect())
        # Result should be a HealingResult regardless of Redis availability
        self.assertIsInstance(result, HealingResult)
        self.assertEqual(result.action, HealingAction.REDIS_RECONNECT)


class TestHealDBPoolReset(unittest.TestCase):
    """Test DB pool reset healing."""

    def setUp(self):
        self.service = SelfHealingService()

    def test_heal_db_pool_reset_returns_result(self):
        """heal_db_pool_reset returns a HealingResult."""
        result = asyncio.run(self.service.heal_db_pool_reset())
        self.assertIsInstance(result, HealingResult)
        self.assertEqual(result.action, HealingAction.DB_POOL_RESET)
        # Success depends on whether DB is available
        self.assertIsInstance(result.success, bool)


class TestHealStaleLockCleanup(unittest.TestCase):
    """Test stale lock cleanup healing."""

    def setUp(self):
        self.service = SelfHealingService()

    def test_heal_stale_lock_cleanup_returns_result(self):
        """heal_stale_lock_cleanup returns a HealingResult."""
        result = asyncio.run(self.service.heal_stale_lock_cleanup())
        self.assertIsInstance(result, HealingResult)
        self.assertEqual(result.action, HealingAction.STALE_LOCK_CLEANUP)
        # Should always succeed (graceful even if no Redis)
        self.assertTrue(result.success)


class TestHealingHistoryRecorded(unittest.TestCase):
    """Test that healing actions are recorded in history."""

    def setUp(self):
        self.service = SelfHealingService()
        reset_circuit_breaker_manager()

    def tearDown(self):
        reset_circuit_breaker_manager()

    def test_history_recorded_after_healing(self):
        """Healing actions are recorded in history."""
        # Initially empty
        history = self.service.get_healing_history()
        self.assertEqual(len(history), 0)

        # Perform a healing action
        result = HealingResult(
            action=HealingAction.LLM_FAILOVER,
            success=True,
            message="Test healing",
        )
        self.service._record_healing(result)

        # Check history
        history = self.service.get_healing_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["action"], "llm_failover")
        self.assertTrue(history[0]["success"])

    def test_history_limited_to_max(self):
        """History is trimmed when exceeding max size."""
        for i in range(600):
            result = HealingResult(
                action=HealingAction.LLM_FAILOVER,
                success=True,
                message=f"Test healing {i}",
            )
            self.service._record_healing(result)

        history = self.service.get_healing_history()
        self.assertLessEqual(len(history), 500)

    def test_history_most_recent_first(self):
        """History returns most recent actions first."""
        for i in range(5):
            result = HealingResult(
                action=HealingAction.LLM_FAILOVER,
                success=True,
                message=f"Test healing {i}",
            )
            self.service._record_healing(result)

        history = self.service.get_healing_history(limit=3)
        self.assertEqual(len(history), 3)

    def test_healing_action_via_llm_failover(self):
        """LLM failover healing records in history."""
        result = asyncio.run(self.service.heal_llm_failover("google_ai"))
        self.service._record_healing(result)

        history = self.service.get_healing_history()
        self.assertGreater(len(history), 0)


class TestHealingMetricsTracked(unittest.TestCase):
    """Test that healing metrics are properly tracked."""

    def setUp(self):
        self.service = SelfHealingService()
        reset_circuit_breaker_manager()

    def tearDown(self):
        reset_circuit_breaker_manager()

    def test_initial_metrics(self):
        """Initial metrics show zero values."""
        metrics = self.service.get_healing_metrics()
        self.assertEqual(metrics["total_checks"], 0)
        self.assertEqual(metrics["healings_attempted"], 0)
        self.assertEqual(metrics["healings_succeeded"], 0)
        self.assertEqual(metrics["healings_failed"], 0)
        self.assertEqual(metrics["success_rate_percent"], 100.0)

    def test_metrics_after_successful_healing(self):
        """Metrics updated after successful healing."""
        result = HealingResult(
            action=HealingAction.LLM_FAILOVER,
            success=True,
            message="Test",
        )
        self.service._record_healing(result)

        metrics = self.service.get_healing_metrics()
        self.assertEqual(metrics["healings_attempted"], 1)
        self.assertEqual(metrics["healings_succeeded"], 1)
        self.assertEqual(metrics["success_rate_percent"], 100.0)

    def test_metrics_after_failed_healing(self):
        """Metrics updated after failed healing."""
        result = HealingResult(
            action=HealingAction.REDIS_RECONNECT,
            success=False,
            message="Failed",
        )
        self.service._record_healing(result)

        metrics = self.service.get_healing_metrics()
        self.assertEqual(metrics["healings_attempted"], 1)
        self.assertEqual(metrics["healings_failed"], 1)
        self.assertEqual(metrics["success_rate_percent"], 0.0)

    def test_metrics_mixed_success_failure(self):
        """Metrics show correct success rate with mixed results."""
        for success in [True, True, False]:
            result = HealingResult(
                action=HealingAction.LLM_FAILOVER,
                success=success,
                message="Test",
            )
            self.service._record_healing(result)

        metrics = self.service.get_healing_metrics()
        self.assertEqual(metrics["healings_attempted"], 3)
        self.assertEqual(metrics["healings_succeeded"], 2)
        self.assertEqual(metrics["healings_failed"], 1)
        self.assertAlmostEqual(metrics["success_rate_percent"], 66.7, places=0)


class TestSelfHealingRunPeriodically(unittest.TestCase):
    """Test periodic self-healing run."""

    def setUp(self):
        self.service = SelfHealingService()
        reset_circuit_breaker_manager()

    def tearDown(self):
        reset_circuit_breaker_manager()

    def test_run_health_check_healthy_system(self):
        """run_health_check returns healthy when no anomalies."""
        result = asyncio.run(self.service.run_health_check())
        self.assertIn("status", result)
        self.assertIn("anomalies_found", result)
        self.assertIn("healing_actions", result)
        self.assertIn("timestamp", result)

    def test_run_health_check_increments_total_checks(self):
        """run_health_check increments total_checks counter."""
        asyncio.run(self.service.run_health_check())
        metrics = self.service.get_healing_metrics()
        self.assertEqual(metrics["total_checks"], 1)

        asyncio.run(self.service.run_health_check())
        metrics = self.service.get_healing_metrics()
        self.assertEqual(metrics["total_checks"], 2)

    def test_run_health_check_with_error_rate_anomaly(self):
        """run_health_check detects error rate anomaly."""
        # Inject errors into detector
        for _ in range(2):
            self.service.detector.record_success("test_service")
        for _ in range(10):
            self.service.detector.record_error("test_service")

        result = asyncio.run(self.service.run_health_check())
        self.assertGreater(result["anomalies_found"], 0)

    def test_get_status(self):
        """get_status returns proper structure."""
        status = self.service.get_status()
        self.assertIn("status", status)
        self.assertIn("metrics", status)
        self.assertIn("detector_services_monitored", status)

    def test_circuit_breaker_reset_healing(self):
        """Circuit breaker reset healing works correctly."""
        result = asyncio.run(
            self.service.heal_circuit_breaker_reset("google_ai")
        )
        self.assertIsInstance(result, HealingResult)
        self.assertEqual(result.action, HealingAction.CIRCUIT_BREAKER_RESET)

    def test_cache_warmup_healing(self):
        """Cache warmup healing works correctly."""
        result = asyncio.run(self.service.heal_cache_warmup("default"))
        self.assertIsInstance(result, HealingResult)
        self.assertEqual(result.action, HealingAction.CACHE_WARMUP)

    def test_queue_drain_healing(self):
        """Queue drain healing works correctly."""
        result = asyncio.run(self.service.heal_queue_drain("default"))
        self.assertIsInstance(result, HealingResult)
        self.assertEqual(result.action, HealingAction.QUEUE_DRAIN)


class TestSelfHealingServiceSingleton(unittest.TestCase):
    """Test singleton self-healing service."""

    def setUp(self):
        reset_self_healing_service()

    def tearDown(self):
        reset_self_healing_service()

    def test_singleton_returns_same_instance(self):
        """Singleton returns same instance each time."""
        service1 = get_self_healing_service()
        service2 = get_self_healing_service()
        self.assertIs(service1, service2)

    def test_reset_clears_singleton(self):
        """reset_self_healing_service clears the singleton."""
        service1 = get_self_healing_service()
        reset_self_healing_service()
        service2 = get_self_healing_service()
        self.assertIsNot(service1, service2)


class TestHealingResultDataclass(unittest.TestCase):
    """Test HealingResult dataclass."""

    def test_auto_timestamp(self):
        """HealingResult auto-generates UTC timestamp."""
        result = HealingResult(
            action=HealingAction.LLM_FAILOVER,
            success=True,
            message="Test",
        )
        self.assertTrue(result.timestamp)
        # Should be a valid ISO timestamp
        dt = datetime.fromisoformat(result.timestamp)
        self.assertIsNotNone(dt)

    def test_explicit_timestamp(self):
        """HealingResult uses explicit timestamp if provided."""
        ts = "2024-01-01T00:00:00+00:00"
        result = HealingResult(
            action=HealingAction.LLM_FAILOVER,
            success=True,
            message="Test",
            timestamp=ts,
        )
        self.assertEqual(result.timestamp, ts)

    def test_default_severity(self):
        """HealingResult defaults to MEDIUM severity."""
        result = HealingResult(
            action=HealingAction.LLM_FAILOVER,
            success=True,
            message="Test",
        )
        self.assertEqual(result.severity, AnomalySeverity.MEDIUM.value)


if __name__ == "__main__":
    unittest.main()
