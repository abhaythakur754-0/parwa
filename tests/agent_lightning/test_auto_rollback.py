"""
Tests for Auto-Rollback System.

Tests verify:
- Drift detection works
- Performance monitoring works
- Rollback executes in <60s
- Alerts trigger correctly
"""

import pytest
from unittest.mock import Mock, patch
import sys
import os
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from agent_lightning.deployment.auto_rollback.drift_detector import (
    DriftDetector,
    DriftType,
    DriftResult,
    get_drift_detector
)
from agent_lightning.deployment.auto_rollback.performance_monitor import (
    PerformanceMonitor,
    MetricBaseline,
    PerformanceAlert,
    get_performance_monitor
)
from agent_lightning.deployment.auto_rollback.rollback_executor import (
    RollbackExecutor,
    RollbackConfig,
    RollbackResult,
    RollbackTrigger,
    get_rollback_executor
)
from agent_lightning.deployment.auto_rollback.alert_manager import (
    AlertManager,
    AlertSeverity,
    AlertChannel,
    Alert,
    get_alert_manager
)


class TestDriftDetector:
    """Tests for Drift Detector."""

    def test_initialization(self):
        """Test detector initializes correctly."""
        detector = DriftDetector()

        assert detector.accuracy_threshold == 0.05
        assert detector.latency_threshold == 0.30
        assert detector.window_size == 100

    def test_set_baselines(self):
        """Test setting baselines."""
        detector = DriftDetector()

        detector.set_baselines(
            accuracy=0.90,
            latency_ms=200.0,
            error_rate=0.01
        )

        stats = detector.get_stats()
        assert stats["baselines"]["accuracy"] == 0.90
        assert stats["baselines"]["latency_ms"] == 200.0

    def test_accuracy_drift_detection(self):
        """Test detecting accuracy drift."""
        detector = DriftDetector()
        detector.set_baselines(accuracy=0.90, latency_ms=200.0)

        # Record poor accuracy (<5% drop)
        for _ in range(50):
            detector.record_accuracy(True)
        for _ in range(50):
            detector.record_accuracy(False)  # 50% accuracy

        result = detector.detect_accuracy_drift()

        assert result.is_drifted
        assert result.drift_magnitude > 0.05
        assert result.drift_type == DriftType.ACCURACY

    def test_no_drift_when_within_threshold(self):
        """Test no drift when within threshold."""
        detector = DriftDetector(accuracy_threshold=0.10)
        detector.set_baselines(accuracy=0.90, latency_ms=200.0)

        # Record acceptable accuracy (85%)
        for _ in range(85):
            detector.record_accuracy(True)
        for _ in range(15):
            detector.record_accuracy(False)

        result = detector.detect_accuracy_drift()

        assert not result.is_drifted

    def test_latency_drift_detection(self):
        """Test detecting latency degradation."""
        detector = DriftDetector()
        detector.set_baselines(accuracy=0.90, latency_ms=100.0)

        # Record high latency (>30% increase)
        for _ in range(100):
            detector.record_latency(200.0)  # 100% increase

        result = detector.detect_latency_drift()

        assert result.is_drifted
        assert result.drift_type == DriftType.LATENCY

    def test_error_rate_detection(self):
        """Test detecting high error rate."""
        detector = DriftDetector(error_rate_threshold=0.10)

        # Record high error rate
        for _ in range(15):
            detector.record_error(True)

        result = detector.detect_error_rate_drift()

        assert result.is_drifted
        assert result.drift_type == DriftType.ERROR_RATE

    def test_detect_all_drifts(self):
        """Test detecting all drift types."""
        detector = DriftDetector()
        detector.set_baselines(accuracy=0.90, latency_ms=100.0)

        # Record good metrics
        for _ in range(100):
            detector.record_accuracy(True)
            detector.record_latency(100.0)

        results = detector.detect_all_drifts()

        assert len(results) == 3
        assert all(isinstance(r, DriftResult) for r in results)

    def test_has_critical_drift(self):
        """Test checking for critical drift."""
        detector = DriftDetector()
        detector.set_baselines(accuracy=0.90, latency_ms=100.0)

        # Record good metrics - no drift
        for _ in range(100):
            detector.record_accuracy(True)
            detector.record_latency(100.0)

        has_drift, drift_type = detector.has_critical_drift()
        assert not has_drift

    def test_factory_function(self):
        """Test factory function."""
        detector = get_drift_detector(accuracy_threshold=0.03)
        assert detector.accuracy_threshold == 0.03


class TestPerformanceMonitor:
    """Tests for Performance Monitor."""

    def test_initialization(self):
        """Test monitor initializes correctly."""
        monitor = PerformanceMonitor()
        assert monitor.window_size == 1000

    def test_record_accuracy(self):
        """Test recording accuracy measurements."""
        monitor = PerformanceMonitor()

        monitor.record_accuracy(True)
        monitor.record_accuracy(True)
        monitor.record_accuracy(False)

        assert monitor.get_current_accuracy() == pytest.approx(2/3, rel=0.1)

    def test_record_latency(self):
        """Test recording latency measurements."""
        monitor = PerformanceMonitor()

        for latency in [100, 150, 200, 250, 300]:
            monitor.record_latency(latency)

        percentiles = monitor.get_latency_percentiles()

        assert percentiles["p50"] == 200
        assert percentiles["p95"] >= 200

    def test_set_baseline(self):
        """Test setting metric baselines."""
        monitor = PerformanceMonitor()

        monitor.set_baseline("accuracy", 0.90, std_dev=0.02)
        monitor.set_baseline("latency_p95", 250.0)

        stats = monitor.get_stats()
        assert "accuracy" in stats["baselines"]
        assert "latency_p95" in stats["baselines"]

    def test_check_all_metrics(self):
        """Test checking all metrics."""
        monitor = PerformanceMonitor()
        monitor.set_baseline("accuracy", 0.90)

        # Good metrics
        for _ in range(100):
            monitor.record_accuracy(True)
            monitor.record_latency(100.0)

        alerts = monitor.check_all_metrics()
        assert isinstance(alerts, list)

    def test_factory_function(self):
        """Test factory function."""
        monitor = get_performance_monitor(window_size=500)
        assert monitor.window_size == 500


class TestRollbackExecutor:
    """Tests for Rollback Executor."""

    def test_initialization(self):
        """Test executor initializes correctly."""
        executor = RollbackExecutor()
        assert executor.config.max_rollback_time_seconds == 60.0
        assert executor.get_current_version() == "v1.0.0"

    def test_set_version(self):
        """Test setting model version."""
        executor = RollbackExecutor()

        executor.set_current_version("v1.1.0")

        assert executor.get_current_version() == "v1.1.0"
        assert executor.get_previous_version() == "v1.0.0"

    def test_can_rollback(self):
        """Test rollback permission check."""
        executor = RollbackExecutor()

        # No previous version initially
        can_rollback, reason = executor.can_rollback()
        assert "No previous version" in reason

        # Set a new version
        executor.set_current_version("v1.1.0")

        # Now should be able to rollback
        can_rollback, reason = executor.can_rollback()
        assert can_rollback

    def test_execute_rollback_success(self):
        """Test successful rollback execution."""
        executor = RollbackExecutor()

        # Set up versions
        executor.set_current_version("v1.1.0")

        # Execute rollback
        result = executor.execute_rollback(trigger=RollbackTrigger.MANUAL)

        assert result.success
        assert result.previous_version == "v1.1.0"
        assert result.target_version == "v1.0.0"
        assert result.rollback_time_seconds < 60.0

    def test_rollback_within_target_time(self):
        """Test that rollback completes within 60 seconds."""
        config = RollbackConfig(max_rollback_time_seconds=60.0)
        executor = RollbackExecutor(config=config)

        executor.set_current_version("v1.1.0")
        result = executor.execute_rollback()

        assert result.success
        assert result.rollback_time_seconds < 60.0

    def test_rollback_cooldown(self):
        """Test rollback cooldown enforcement."""
        config = RollbackConfig(cooldown_seconds=1.0, max_rollbacks_per_hour=10)
        executor = RollbackExecutor(config=config)

        executor.set_current_version("v1.1.0")
        result1 = executor.execute_rollback()
        assert result1.success

        # Set up for another rollback
        executor.set_current_version("v1.2.0")

        # Immediate second rollback should be blocked
        result2 = executor.execute_rollback()
        assert not result2.success
        assert "Cooldown" in result2.error_message

    def test_max_rollbacks_per_hour(self):
        """Test max rollbacks per hour limit."""
        config = RollbackConfig(
            cooldown_seconds=0.1,
            max_rollbacks_per_hour=2
        )
        executor = RollbackExecutor(config=config)

        executor.set_current_version("v1.1.0")
        result1 = executor.execute_rollback()
        assert result1.success

        # Wait for cooldown
        time.sleep(0.2)
        executor.set_current_version("v1.2.0")
        result2 = executor.execute_rollback()
        assert result2.success

        # Wait for cooldown
        time.sleep(0.2)
        executor.set_current_version("v1.3.0")
        result3 = executor.execute_rollback()
        assert not result3.success
        assert "Max rollbacks" in result3.error_message

    def test_rollback_history(self):
        """Test rollback history tracking."""
        executor = RollbackExecutor()

        executor.set_current_version("v1.1.0")
        executor.execute_rollback()

        history = executor.get_rollback_history()

        assert len(history) == 1
        assert history[0].success

    def test_factory_function(self):
        """Test factory function."""
        executor = get_rollback_executor(max_rollback_time=30.0)
        assert executor.config.max_rollback_time_seconds == 30.0


class TestAlertManager:
    """Tests for Alert Manager."""

    def test_initialization(self):
        """Test manager initializes correctly."""
        manager = AlertManager()
        assert len(manager.get_alert_history()) == 0

    def test_create_alert(self):
        """Test creating an alert."""
        manager = AlertManager()

        alert = manager.create_alert(
            title="Test Alert",
            message="This is a test",
            severity=AlertSeverity.WARNING
        )

        assert alert.alert_id == "alert_1"
        assert alert.title == "Test Alert"
        assert alert.severity == AlertSeverity.WARNING

    def test_alert_severity_routing(self):
        """Test that alerts route to correct channels by severity."""
        manager = AlertManager()

        # INFO should only go to log
        manager.create_alert("Info", "Test", severity=AlertSeverity.INFO)
        history = manager.get_alert_history()
        assert history[-1].channel == AlertChannel.LOG

    def test_acknowledge_alert(self):
        """Test acknowledging an alert."""
        manager = AlertManager()

        alert = manager.create_alert("Test", "Test message", severity=AlertSeverity.INFO)

        result = manager.acknowledge_alert(alert.alert_id, "admin@example.com")

        assert result
        # All alerts with this ID should be acknowledged
        unacknowledged = manager.get_unacknowledged_alerts()
        for a in unacknowledged:
            assert a.alert_id != alert.alert_id, "Alert should be acknowledged"

    def test_alert_history(self):
        """Test alert history retrieval."""
        manager = AlertManager()

        # Create alerts - each creates multiple alerts for different channels
        for i in range(5):
            manager.create_alert(f"Alert {i}", "Test", severity=AlertSeverity.INFO)

        history = manager.get_alert_history()
        # With INFO severity, only 1 channel (log) per alert
        assert len(history) == 5

    def test_stats(self):
        """Test alert statistics."""
        manager = AlertManager()

        # Use INFO so only 1 channel each
        manager.create_alert("Critical", "Test", severity=AlertSeverity.INFO)
        manager.create_alert("Warning", "Test", severity=AlertSeverity.INFO)

        stats = manager.get_stats()

        assert stats["total_alerts"] == 2
        assert stats["by_severity"]["info"] == 2

    def test_factory_function(self):
        """Test factory function."""
        manager = get_alert_manager(slack_webhook="https://example.com/webhook")
        assert manager.slack_webhook == "https://example.com/webhook"


class TestAutoRollbackIntegration:
    """Integration tests for the full auto-rollback system."""

    def test_full_rollback_workflow(self):
        """Test complete auto-rollback workflow."""
        # 1. Set up components
        drift_detector = get_drift_detector()
        performance_monitor = get_performance_monitor()
        rollback_executor = get_rollback_executor()
        alert_manager = get_alert_manager()

        # 2. Set baselines
        drift_detector.set_baselines(
            accuracy=0.90,
            latency_ms=100.0,
            error_rate=0.01
        )
        performance_monitor.set_baseline("accuracy", 0.90)

        # 3. Simulate normal operation
        for _ in range(100):
            drift_detector.record_accuracy(True)
            drift_detector.record_latency(100.0)
            performance_monitor.record_accuracy(True)
            performance_monitor.record_latency(100.0)

        # No drift should be detected
        has_drift, _ = drift_detector.has_critical_drift()
        assert not has_drift

        # 4. Simulate degradation
        for _ in range(100):
            drift_detector.record_accuracy(False)  # Accuracy drops
            drift_detector.record_latency(300.0)  # Latency increases
            performance_monitor.record_accuracy(False)
            performance_monitor.record_latency(300.0)

        # 5. Detect drift
        has_drift, drift_type = drift_detector.has_critical_drift()
        assert has_drift

        # 6. Create alert
        alert = alert_manager.create_alert(
            title=f"Drift Detected: {drift_type.value}",
            message="Model performance degradation detected",
            severity=AlertSeverity.CRITICAL
        )

        assert alert.alert_id is not None

        # 7. Set up version for rollback
        rollback_executor.set_current_version("v2.0.0")

        # 8. Execute rollback
        result = rollback_executor.execute_rollback(
            trigger=RollbackTrigger.ACCURACY_DRIFT,
            metadata={"drift_type": drift_type.value}
        )

        assert result.success
        assert result.rollback_time_seconds < 60.0

        # 9. Verify rollback
        assert rollback_executor.get_current_version() == "v1.0.0"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
