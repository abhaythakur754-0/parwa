"""
Tests for Real-time Monitor Module - Week 53, Builder 1
"""

import pytest
from datetime import datetime, timedelta
import asyncio
import threading

from enterprise.monitoring.realtime_monitor import (
    RealtimeMonitor,
    MonitorTarget,
    MonitorResult,
    MonitorStatus,
    HealthStatus,
    MetricSample,
    MetricType,
    MetricBuffer,
    MonitorFactory,
)
from enterprise.monitoring.metric_aggregator import (
    MetricAggregator,
    MetricSeries,
    MetricPoint,
    AggregatedMetric,
    AggregationType,
    TimeWindow,
    MetricRegistry,
    MultiMetricAggregator,
)
from enterprise.monitoring.health_aggregator import (
    HealthAggregator,
    HealthCheck,
    ComponentHealth,
    SystemHealth,
    HealthHistory,
    HealthCheckRegistry,
)


# ============================================================================
# Realtime Monitor Tests
# ============================================================================

class TestMetricSample:
    """Tests for MetricSample class"""

    def test_init(self):
        """Test metric sample initialization"""
        sample = MetricSample(
            name="cpu",
            value=50.0,
            metric_type=MetricType.GAUGE,
        )
        assert sample.name == "cpu"
        assert sample.value == 50.0
        assert sample.metric_type == MetricType.GAUGE

    def test_with_labels(self):
        """Test metric sample with labels"""
        sample = MetricSample(
            name="cpu",
            value=75.0,
            metric_type=MetricType.GAUGE,
            labels={"host": "server1"},
        )
        assert sample.labels["host"] == "server1"


class TestMonitorTarget:
    """Tests for MonitorTarget class"""

    def test_init(self):
        """Test target initialization"""
        target = MonitorTarget(
            name="web-server",
            target_type="host",
        )
        assert target.name == "web-server"
        assert target.target_type == "host"
        assert target.enabled is True

    def test_custom_settings(self):
        """Test target with custom settings"""
        target = MonitorTarget(
            name="api-server",
            target_type="service",
            check_interval=30.0,
            timeout=5.0,
            enabled=False,
        )
        assert target.check_interval == 30.0
        assert target.timeout == 5.0
        assert target.enabled is False


class TestMetricBuffer:
    """Tests for MetricBuffer class"""

    def test_init(self):
        """Test buffer initialization"""
        buffer = MetricBuffer()
        assert len(buffer.get_all_names()) == 0

    def test_add(self):
        """Test adding samples"""
        buffer = MetricBuffer()
        sample = MetricSample("cpu", 50.0, MetricType.GAUGE)
        buffer.add(sample)
        assert "cpu" in buffer.get_all_names()

    def test_get_samples(self):
        """Test getting samples"""
        buffer = MetricBuffer()
        for i in range(5):
            buffer.add(MetricSample("cpu", 50.0 + i, MetricType.GAUGE))

        samples = buffer.get_samples("cpu")
        assert len(samples) == 5

    def test_max_size(self):
        """Test max size enforcement"""
        buffer = MetricBuffer(max_size=5)
        for i in range(10):
            buffer.add(MetricSample("cpu", float(i), MetricType.GAUGE))

        samples = buffer.get_samples("cpu", limit=100)
        assert len(samples) == 5

    def test_clear(self):
        """Test clearing buffer"""
        buffer = MetricBuffer()
        buffer.add(MetricSample("cpu", 50.0, MetricType.GAUGE))
        buffer.clear("cpu")
        assert "cpu" not in buffer.get_all_names()

    def test_clear_all(self):
        """Test clearing all"""
        buffer = MetricBuffer()
        buffer.add(MetricSample("cpu", 50.0, MetricType.GAUGE))
        buffer.add(MetricSample("mem", 60.0, MetricType.GAUGE))
        buffer.clear()
        assert len(buffer.get_all_names()) == 0


class TestRealtimeMonitor:
    """Tests for RealtimeMonitor class"""

    def test_init(self):
        """Test monitor initialization"""
        monitor = RealtimeMonitor()
        assert monitor.status == MonitorStatus.STOPPED
        assert len(monitor.targets) == 0

    def test_add_target(self):
        """Test adding target"""
        monitor = RealtimeMonitor()
        target = MonitorTarget("server1", "host")
        monitor.add_target(target)
        assert "server1" in monitor.targets

    def test_remove_target(self):
        """Test removing target"""
        monitor = RealtimeMonitor()
        monitor.add_target(MonitorTarget("server1", "host"))
        result = monitor.remove_target("server1")
        assert result is True
        assert "server1" not in monitor.targets

    def test_remove_nonexistent(self):
        """Test removing nonexistent target"""
        monitor = RealtimeMonitor()
        result = monitor.remove_target("nonexistent")
        assert result is False

    def test_register_checker(self):
        """Test registering checker"""
        monitor = RealtimeMonitor()
        monitor.register_checker("host", lambda t: MonitorResult(t.name, HealthStatus.HEALTHY, 10))
        assert "host" in monitor._checkers

    def test_add_callback(self):
        """Test adding callback"""
        monitor = RealtimeMonitor()
        calls = []
        monitor.add_callback(lambda r: calls.append(r))
        assert len(monitor._callbacks) == 1

    @pytest.mark.asyncio
    async def test_check_target(self):
        """Test checking target"""
        monitor = RealtimeMonitor()
        monitor.register_checker("host", lambda t: MonitorResult(
            target=t.name,
            status=HealthStatus.HEALTHY,
            response_time_ms=10.0,
        ))

        target = MonitorTarget("server1", "host")
        monitor.add_target(target)

        result = await monitor.check_target(target)
        assert result.status == HealthStatus.HEALTHY
        assert result.target == "server1"

    def test_get_status(self):
        """Test getting status"""
        monitor = RealtimeMonitor()
        status = monitor.get_status()
        assert status["status"] == "stopped"
        assert status["targets"] == 0

    def test_start_stop_status(self):
        """Test start/stop status changes"""
        monitor = RealtimeMonitor()
        # Just test status changes without actually starting the loop
        monitor.status = MonitorStatus.RUNNING
        assert monitor.status == MonitorStatus.RUNNING
        monitor.status = MonitorStatus.STOPPED
        assert monitor.status == MonitorStatus.STOPPED

    def test_pause_resume(self):
        """Test pause/resume"""
        monitor = RealtimeMonitor()
        monitor.status = MonitorStatus.RUNNING
        monitor.pause()
        assert monitor.status == MonitorStatus.PAUSED
        monitor.resume()
        assert monitor.status == MonitorStatus.RUNNING


class TestMonitorFactory:
    """Tests for MonitorFactory class"""

    def test_create_system_monitor(self):
        """Test creating system monitor"""
        monitor = MonitorFactory.create_system_monitor()
        assert monitor.check_interval == 30.0

    def test_create_service_monitor(self):
        """Test creating service monitor"""
        monitor = MonitorFactory.create_service_monitor()
        assert "service" in monitor._checkers

    def test_create_endpoint_monitor(self):
        """Test creating endpoint monitor"""
        monitor = MonitorFactory.create_endpoint_monitor()
        assert "endpoint" in monitor._checkers


# ============================================================================
# Metric Aggregator Tests
# ============================================================================

class TestMetricSeries:
    """Tests for MetricSeries class"""

    def test_init(self):
        """Test series initialization"""
        series = MetricSeries(name="cpu")
        assert series.name == "cpu"
        assert len(series.points) == 0

    def test_add_point(self):
        """Test adding point"""
        series = MetricSeries(name="cpu")
        series.add_point(50.0)
        assert len(series.points) == 1

    def test_get_values(self):
        """Test getting values"""
        series = MetricSeries(name="cpu")
        series.add_point(10)
        series.add_point(20)
        series.add_point(30)
        values = series.get_values()
        assert values == [10, 20, 30]

    def test_get_latest(self):
        """Test getting latest"""
        series = MetricSeries(name="cpu")
        assert series.get_latest() is None
        series.add_point(50)
        series.add_point(60)
        assert series.get_latest() == 60


class TestTimeWindow:
    """Tests for TimeWindow class"""

    def test_init(self):
        """Test window initialization"""
        window = TimeWindow()
        assert len(window.get_values()) == 0

    def test_add(self):
        """Test adding values"""
        window = TimeWindow()
        window.add(50.0)
        window.add(60.0)
        assert len(window.get_values()) == 2

    def test_get_count(self):
        """Test getting count"""
        window = TimeWindow()
        for i in range(5):
            window.add(float(i))
        assert window.get_count() == 5


class TestMetricAggregator:
    """Tests for MetricAggregator class"""

    def test_init(self):
        """Test aggregator initialization"""
        agg = MetricAggregator()
        assert len(agg.series) == 0

    def test_record(self):
        """Test recording metric"""
        agg = MetricAggregator()
        agg.record("cpu", 50.0)
        assert "cpu" in agg.series

    def test_record_batch(self):
        """Test recording batch"""
        agg = MetricAggregator()
        agg.record_batch({"cpu": 50, "memory": 60})
        assert "cpu" in agg.series
        assert "memory" in agg.series

    def test_aggregate_avg(self):
        """Test average aggregation"""
        agg = MetricAggregator()
        for i in range(10):
            agg.record("cpu", float(i * 10))

        result = agg.aggregate("cpu", AggregationType.AVG)
        assert result is not None
        assert result.value == 45.0

    def test_aggregate_sum(self):
        """Test sum aggregation"""
        agg = MetricAggregator()
        for i in range(5):
            agg.record("cpu", float(i + 1))

        result = agg.aggregate("cpu", AggregationType.SUM)
        assert result.value == 15.0

    def test_aggregate_min_max(self):
        """Test min/max aggregation"""
        agg = MetricAggregator()
        for i in range(10):
            agg.record("cpu", float(i * 10))

        min_result = agg.aggregate("cpu", AggregationType.MIN)
        max_result = agg.aggregate("cpu", AggregationType.MAX)
        assert min_result.value == 0
        assert max_result.value == 90

    def test_aggregate_percentile(self):
        """Test percentile aggregation"""
        agg = MetricAggregator()
        for i in range(100):
            agg.record("cpu", float(i))

        p50 = agg.aggregate("cpu", AggregationType.P50)
        p95 = agg.aggregate("cpu", AggregationType.P95)
        assert p50.value is not None
        assert p95.value > p50.value

    def test_get_latest(self):
        """Test getting latest"""
        agg = MetricAggregator()
        agg.record("cpu", 50)
        agg.record("cpu", 60)
        assert agg.get_latest("cpu") == 60

    def test_get_all_latest(self):
        """Test getting all latest"""
        agg = MetricAggregator()
        agg.record("cpu", 50)
        agg.record("memory", 60)
        latest = agg.get_all_latest()
        assert latest["cpu"] == 50
        assert latest["memory"] == 60

    def test_get_statistics(self):
        """Test getting statistics"""
        agg = MetricAggregator()
        for i in range(10):
            agg.record("cpu", 50.0)

        stats = agg.get_statistics("cpu")
        assert stats["count"] == 10
        assert stats["avg"] == 50.0

    def test_clear(self):
        """Test clearing"""
        agg = MetricAggregator()
        agg.record("cpu", 50)
        agg.clear("cpu")
        assert "cpu" not in agg.series


class TestMetricRegistry:
    """Tests for MetricRegistry class"""

    def test_init(self):
        """Test registry initialization"""
        registry = MetricRegistry()
        assert registry.aggregator is not None

    def test_define_metric(self):
        """Test defining metric"""
        registry = MetricRegistry()
        registry.define_metric(
            name="cpu",
            description="CPU usage",
            unit="percent",
        )
        assert "cpu" in registry._definitions

    def test_get_definition(self):
        """Test getting definition"""
        registry = MetricRegistry()
        registry.define_metric("cpu", "CPU usage", "percent")
        defn = registry.get_definition("cpu")
        assert defn["name"] == "cpu"


class TestMultiMetricAggregator:
    """Tests for MultiMetricAggregator class"""

    def test_init(self):
        """Test initialization"""
        multi = MultiMetricAggregator()
        assert len(multi.aggregators) == 0

    def test_get_aggregator(self):
        """Test getting aggregator"""
        multi = MultiMetricAggregator()
        agg = multi.get_aggregator("system")
        assert agg is not None
        assert "system" in multi.aggregators

    def test_record(self):
        """Test recording"""
        multi = MultiMetricAggregator()
        multi.record("system", "cpu", 50)
        multi.record("system", "memory", 60)
        latest = multi.get_all_latest()
        assert "system" in latest


# ============================================================================
# Health Aggregator Tests
# ============================================================================

class TestHealthCheck:
    """Tests for HealthCheck class"""

    def test_init(self):
        """Test check initialization"""
        check = HealthCheck(
            name="database",
            status=HealthStatus.HEALTHY,
        )
        assert check.name == "database"
        assert check.status == HealthStatus.HEALTHY

    def test_to_dict(self):
        """Test to_dict method"""
        check = HealthCheck(
            name="api",
            status=HealthStatus.DEGRADED,
            message="Slow response",
        )
        d = check.to_dict()
        assert d["name"] == "api"
        assert d["status"] == "degraded"


class TestComponentHealth:
    """Tests for ComponentHealth class"""

    def test_init(self):
        """Test component health initialization"""
        health = ComponentHealth(
            component="database",
            status=HealthStatus.HEALTHY,
        )
        assert health.component == "database"
        assert health.is_healthy is True

    def test_unhealthy(self):
        """Test unhealthy component"""
        health = ComponentHealth(
            component="cache",
            status=HealthStatus.UNHEALTHY,
        )
        assert health.is_healthy is False

    def test_to_dict(self):
        """Test to_dict method"""
        health = ComponentHealth(
            component="api",
            status=HealthStatus.HEALTHY,
            checks=[HealthCheck("test", HealthStatus.HEALTHY)],
        )
        d = health.to_dict()
        assert d["component"] == "api"
        assert len(d["checks"]) == 1


class TestSystemHealth:
    """Tests for SystemHealth class"""

    def test_init(self):
        """Test system health initialization"""
        health = SystemHealth(status=HealthStatus.HEALTHY)
        assert health.status == HealthStatus.HEALTHY
        assert health.healthy_count == 0

    def test_counts(self):
        """Test count properties"""
        health = SystemHealth(
            status=HealthStatus.HEALTHY,
            components={
                "db": ComponentHealth("db", HealthStatus.HEALTHY),
                "cache": ComponentHealth("cache", HealthStatus.UNHEALTHY),
            },
        )
        assert health.healthy_count == 1
        assert health.total_count == 2


class TestHealthHistory:
    """Tests for HealthHistory class"""

    def test_init(self):
        """Test history initialization"""
        history = HealthHistory()
        assert len(history._history) == 0

    def test_record(self):
        """Test recording"""
        history = HealthHistory()
        history.record("db", HealthStatus.HEALTHY)
        assert len(history._history["db"]) == 1

    def test_get_uptime(self):
        """Test uptime calculation"""
        history = HealthHistory()
        for _ in range(10):
            history.record("db", HealthStatus.HEALTHY)

        uptime = history.get_uptime("db")
        assert uptime == 100.0

    def test_get_uptime_partial(self):
        """Test partial uptime"""
        history = HealthHistory()
        for i in range(10):
            status = HealthStatus.HEALTHY if i < 7 else HealthStatus.UNHEALTHY
            history.record("db", status)

        uptime = history.get_uptime("db")
        assert uptime == 70.0


class TestHealthAggregator:
    """Tests for HealthAggregator class"""

    def test_init(self):
        """Test aggregator initialization"""
        agg = HealthAggregator()
        assert len(agg.components) == 0

    def test_register_component(self):
        """Test registering component"""
        agg = HealthAggregator()
        agg.register_component("database")
        assert "database" in agg.components

    def test_unregister_component(self):
        """Test unregistering component"""
        agg = HealthAggregator()
        agg.register_component("database")
        result = agg.unregister_component("database")
        assert result is True
        assert "database" not in agg.components

    def test_update_health(self):
        """Test updating health"""
        agg = HealthAggregator()
        agg.register_component("api")

        check = HealthCheck("endpoint", HealthStatus.HEALTHY)
        agg.update_health("api", check)

        comp = agg.get_health("api")
        assert comp.status == HealthStatus.HEALTHY

    def test_add_check(self):
        """Test adding check"""
        agg = HealthAggregator()
        check = agg.add_check("db", "connection", HealthStatus.HEALTHY, "OK")
        assert check.status == HealthStatus.HEALTHY

    def test_get_system_health(self):
        """Test getting system health"""
        agg = HealthAggregator()
        agg.register_component("db")
        agg.register_component("cache")

        agg.add_check("db", "conn", HealthStatus.HEALTHY)
        agg.add_check("cache", "conn", HealthStatus.UNHEALTHY)

        health = agg.get_system_health()
        assert health.status == HealthStatus.UNHEALTHY
        assert len(health.issues) == 1

    def test_get_summary(self):
        """Test getting summary"""
        agg = HealthAggregator()
        agg.register_component("db")
        agg.add_check("db", "test", HealthStatus.HEALTHY)

        summary = agg.get_summary()
        assert summary["overall_status"] == "healthy"
        assert summary["healthy_count"] == 1

    def test_is_healthy(self):
        """Test is_healthy check"""
        agg = HealthAggregator()
        agg.register_component("api")
        agg.add_check("api", "test", HealthStatus.HEALTHY)

        assert agg.is_healthy("api") is True
        assert agg.is_healthy() is True

    def test_reset(self):
        """Test reset"""
        agg = HealthAggregator()
        agg.register_component("api")
        agg.add_check("api", "test", HealthStatus.UNHEALTHY)

        agg.reset("api")
        comp = agg.get_health("api")
        assert comp.status == HealthStatus.UNKNOWN


class TestHealthCheckRegistry:
    """Tests for HealthCheckRegistry class"""

    def test_init(self):
        """Test registry initialization"""
        agg = HealthAggregator()
        registry = HealthCheckRegistry(agg)
        assert registry.aggregator == agg

    def test_register(self):
        """Test registering checker"""
        agg = HealthAggregator()
        registry = HealthCheckRegistry(agg)
        registry.register("api", lambda: {"status": "healthy"})
        assert "api" in registry._checkers

    @pytest.mark.asyncio
    async def test_run_check(self):
        """Test running check"""
        agg = HealthAggregator()
        registry = HealthCheckRegistry(agg)
        registry.register("api", lambda: HealthCheck("api", HealthStatus.HEALTHY))

        result = await registry.run_check("api")
        assert result.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_run_all_checks(self):
        """Test running all checks"""
        agg = HealthAggregator()
        registry = HealthCheckRegistry(agg)
        registry.register("api1", lambda: HealthCheck("api1", HealthStatus.HEALTHY))
        registry.register("api2", lambda: HealthCheck("api2", HealthStatus.HEALTHY))

        results = await registry.run_all_checks()
        assert len(results) == 2
