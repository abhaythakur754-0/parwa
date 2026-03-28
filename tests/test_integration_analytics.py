"""
Week 58 - Builder 5 Tests: Integration Analytics Module
Unit tests for Integration Metrics, Health Monitor, and Usage Analytics
"""

import pytest
import time
from parwa_integration_hub.integration_metrics import (
    IntegrationMetrics, Metric, MetricType,
    HealthMonitor, HealthCheck, HealthStatus,
    UsageAnalytics
)


class TestIntegrationMetrics:
    """Tests for IntegrationMetrics class"""

    @pytest.fixture
    def metrics(self):
        """Create test metrics instance"""
        return IntegrationMetrics()

    def test_increment_counter(self, metrics):
        """Test counter increment"""
        metrics.increment("requests_total")
        metrics.increment("requests_total")

        value = metrics.get_counter("requests_total")
        assert value == 2

    def test_increment_with_value(self, metrics):
        """Test counter increment with value"""
        metrics.increment("bytes_sent", 1024)

        value = metrics.get_counter("bytes_sent")
        assert value == 1024

    def test_decrement_counter(self, metrics):
        """Test counter decrement"""
        metrics.increment("counter", 10)
        metrics.decrement("counter", 3)

        value = metrics.get_counter("counter")
        assert value == 7

    def test_set_gauge(self, metrics):
        """Test gauge set"""
        metrics.set_gauge("active_connections", 42)

        value = metrics.get_gauge("active_connections")
        assert value == 42

    def test_observe_histogram(self, metrics):
        """Test histogram observation"""
        for i in range(10):
            metrics.observe("latency_ms", i * 10)

        hist = metrics.get_histogram("latency_ms")

        assert hist["count"] == 10
        assert hist["min"] == 0
        assert hist["max"] == 90

    def test_histogram_percentiles(self, metrics):
        """Test histogram percentiles"""
        for i in range(100):
            metrics.observe("response_time", i)

        hist = metrics.get_histogram("response_time")

        assert hist["p50"] >= 45 and hist["p50"] <= 55
        assert hist["p95"] >= 90
        assert hist["p99"] >= 95

    def test_get_summary(self, metrics):
        """Test summary statistics"""
        for i in range(5):
            metrics.observe("request_size", 100 * (i + 1))

        summary = metrics.get_summary("request_size")

        assert summary["count"] == 5
        assert summary["sum"] == 1500
        assert summary["min"] == 100
        assert summary["max"] == 500

    def test_counter_with_labels(self, metrics):
        """Test counter with labels"""
        metrics.increment("requests", labels={"endpoint": "/api/users"})
        metrics.increment("requests", labels={"endpoint": "/api/orders"})

        value = metrics.get_counter("requests", labels={"endpoint": "/api/users"})
        assert value == 1

    def test_gauge_with_labels(self, metrics):
        """Test gauge with labels"""
        metrics.set_gauge("queue_size", 10, labels={"queue": "email"})
        metrics.set_gauge("queue_size", 20, labels={"queue": "sms"})

        value = metrics.get_gauge("queue_size", labels={"queue": "email"})
        assert value == 10

    def test_get_all_metrics(self, metrics):
        """Test get all metrics"""
        metrics.increment("counter1")
        metrics.set_gauge("gauge1", 42)
        metrics.observe("hist1", 100)

        all_metrics = metrics.get_all_metrics()

        assert "counters" in all_metrics
        assert "gauges" in all_metrics
        assert "histograms" in all_metrics


class TestHealthMonitor:
    """Tests for HealthMonitor class"""

    @pytest.fixture
    def monitor(self):
        """Create test health monitor"""
        return HealthMonitor()

    def test_register_check(self, monitor):
        """Test health check registration"""
        monitor.register_check("api-endpoint")

        assert "api-endpoint" in monitor.health_checks

    def test_record_healthy_check(self, monitor):
        """Test recording healthy check"""
        monitor.register_check("api-endpoint")

        check = monitor.record_check("api-endpoint", is_healthy=True)

        assert check.status == HealthStatus.HEALTHY
        assert check.consecutive_failures == 0

    def test_record_unhealthy_check(self, monitor):
        """Test recording unhealthy check"""
        monitor.register_check("api-endpoint", threshold=2)

        monitor.record_check("api-endpoint", is_healthy=False)
        check = monitor.record_check("api-endpoint", is_healthy=False)

        assert check.status == HealthStatus.UNHEALTHY

    def test_degraded_status(self, monitor):
        """Test degraded status"""
        monitor.register_check("api-endpoint", threshold=3)

        check = monitor.record_check("api-endpoint", is_healthy=False)

        assert check.status == HealthStatus.DEGRADED

    def test_get_health(self, monitor):
        """Test get health status"""
        monitor.register_check("api-endpoint")
        monitor.record_check("api-endpoint", is_healthy=True)

        check = monitor.get_health("api-endpoint")

        assert check is not None
        assert check.status == HealthStatus.HEALTHY

    def test_get_all_health(self, monitor):
        """Test get all health statuses"""
        monitor.register_check("endpoint1")
        monitor.register_check("endpoint2")

        health = monitor.get_all_health()

        assert len(health) == 2

    def test_get_uptime(self, monitor):
        """Test uptime calculation"""
        monitor.register_check("api-endpoint")

        for _ in range(8):
            monitor.record_check("api-endpoint", is_healthy=True)
        for _ in range(2):
            monitor.record_check("api-endpoint", is_healthy=False)

        uptime = monitor.get_uptime("api-endpoint")

        assert uptime == 80.0  # 8/10 = 80%

    def test_get_status_summary(self, monitor):
        """Test status summary"""
        monitor.register_check("ep1")
        monitor.register_check("ep2")
        monitor.register_check("ep3")

        monitor.record_check("ep1", is_healthy=True)
        monitor.record_check("ep2", is_healthy=True)
        monitor.record_check("ep3", is_healthy=False)

        summary = monitor.get_status_summary()

        assert summary.get("healthy", 0) == 2

    def test_set_alert_threshold(self, monitor):
        """Test setting alert threshold"""
        monitor.register_check("api-endpoint")
        monitor.set_alert_threshold("api-endpoint", 5)

        assert monitor.alert_thresholds["api-endpoint"]["consecutive_failures"] == 5

    def test_get_unhealthy(self, monitor):
        """Test get unhealthy endpoints"""
        monitor.register_check("healthy-ep", threshold=1)
        monitor.register_check("unhealthy-ep", threshold=1)

        monitor.record_check("healthy-ep", is_healthy=True)
        monitor.record_check("unhealthy-ep", is_healthy=False)

        unhealthy = monitor.get_unhealthy()

        assert "unhealthy-ep" in unhealthy
        assert "healthy-ep" not in unhealthy


class TestUsageAnalytics:
    """Tests for UsageAnalytics class"""

    @pytest.fixture
    def analytics(self):
        """Create test analytics instance"""
        return UsageAnalytics()

    def test_record_usage(self, analytics):
        """Test recording usage"""
        analytics.record_usage(
            integration="stripe",
            endpoint="/charges",
            requests=10,
            errors=2,
            latency_ms=150
        )

        assert "stripe" in analytics.usage_data
        assert len(analytics.usage_data["stripe"]) == 1

    def test_get_usage_stats(self, analytics):
        """Test get usage statistics"""
        for i in range(5):
            analytics.record_usage(
                integration="stripe",
                endpoint="/charges",
                requests=10,
                errors=1 if i % 2 == 0 else 0,
                latency_ms=100 + i * 10
            )

        stats = analytics.get_usage_stats("stripe", window_seconds=3600)

        assert stats["requests"] == 50
        assert stats["errors"] == 3

    def test_get_usage_stats_empty(self, analytics):
        """Test get usage stats for empty integration"""
        stats = analytics.get_usage_stats("nonexistent")

        assert stats["requests"] == 0
        assert stats["errors"] == 0

    def test_detect_patterns(self, analytics):
        """Test pattern detection"""
        for i in range(100):
            analytics.record_usage(
                integration="api",
                endpoint="/test",
                requests=10
            )

        patterns = analytics.detect_patterns("api")

        assert "patterns" in patterns
        assert patterns["confidence"] > 0

    def test_detect_patterns_insufficient_data(self, analytics):
        """Test pattern detection with insufficient data"""
        for i in range(5):
            analytics.record_usage("api", "/test", 1)

        patterns = analytics.detect_patterns("api")

        assert patterns["confidence"] == 0

    def test_forecast_usage(self, analytics):
        """Test usage forecasting"""
        for i in range(30):
            analytics.record_usage(
                integration="api",
                endpoint="/test",
                requests=100
            )

        forecast = analytics.forecast_usage("api")

        assert forecast > 0

    def test_forecast_insufficient_data(self, analytics):
        """Test forecast with insufficient data"""
        for i in range(10):
            analytics.record_usage("api", "/test", 1)

        forecast = analytics.forecast_usage("api")

        assert forecast >= 0

    def test_get_trends(self, analytics):
        """Test get trends"""
        for i in range(50):
            analytics.record_usage(
                integration="api",
                endpoint="/test",
                requests=10,
                latency_ms=100
            )

        trends = analytics.get_trends("api")

        assert "hourly" in trends
        assert "daily" in trends
        assert "weekly" in trends

    def test_get_report(self, analytics):
        """Test usage report"""
        analytics.record_usage("api1", "/test", 10)
        analytics.record_usage("api2", "/test", 20)

        report = analytics.get_report()

        assert "integrations" in report
        assert len(report["integrations"]) == 2

    def test_get_single_integration_report(self, analytics):
        """Test single integration report"""
        analytics.record_usage("api1", "/test", 10)

        report = analytics.get_report("api1")

        assert report["integration"] == "api1"
        assert "trends" in report
