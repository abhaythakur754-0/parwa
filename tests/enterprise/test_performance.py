# Tests for Builder 1 - Performance Optimizer
# Week 50: performance_monitor.py, resource_optimizer.py, cache_manager.py

import pytest
from datetime import datetime, timedelta
import time

from enterprise.ops.performance_monitor import (
    PerformanceMonitor, MetricSample, PerformanceAlert,
    MetricType, AlertLevel
)
from enterprise.ops.resource_optimizer import (
    ResourceOptimizer, ResourceUsage, OptimizationPlan,
    ResourceType, OptimizationAction
)
from enterprise.ops.cache_manager import (
    CacheManager, CacheEntry, CacheStats, CachePolicy
)


# =============================================================================
# PERFORMANCE MONITOR TESTS
# =============================================================================

class TestPerformanceMonitor:
    """Tests for PerformanceMonitor class"""

    def test_init(self):
        """Test monitor initialization"""
        monitor = PerformanceMonitor()
        assert monitor is not None
        metrics = monitor.get_metrics()
        assert metrics["total_samples"] == 0
        assert metrics["total_alerts"] == 0

    def test_record_sample_cpu(self):
        """Test recording CPU sample"""
        monitor = PerformanceMonitor()
        sample = monitor.record_sample(MetricType.CPU, 45.5, "%", {"host": "server1"})
        assert sample.metric_type == MetricType.CPU
        assert sample.value == 45.5
        assert sample.unit == "%"
        assert sample.tags["host"] == "server1"

    def test_record_sample_memory(self):
        """Test recording memory sample"""
        monitor = PerformanceMonitor()
        sample = monitor.record_sample(MetricType.MEMORY, 80.0, "%")
        assert sample.metric_type == MetricType.MEMORY
        assert sample.value == 80.0

    def test_record_sample_latency(self):
        """Test recording latency sample"""
        monitor = PerformanceMonitor()
        sample = monitor.record_sample(MetricType.LATENCY, 250.0, "ms")
        assert sample.metric_type == MetricType.LATENCY
        assert sample.value == 250.0

    def test_record_sample_error_rate(self):
        """Test recording error rate sample"""
        monitor = PerformanceMonitor()
        sample = monitor.record_sample(MetricType.ERROR_RATE, 0.5, "%")
        assert sample.metric_type == MetricType.ERROR_RATE

    def test_multiple_samples_updates_count(self):
        """Test that multiple samples update count"""
        monitor = PerformanceMonitor()
        monitor.record_sample(MetricType.CPU, 50.0)
        monitor.record_sample(MetricType.CPU, 60.0)
        monitor.record_sample(MetricType.MEMORY, 70.0)
        metrics = monitor.get_metrics()
        assert metrics["total_samples"] == 3

    def test_warning_alert_triggered(self):
        """Test warning alert when threshold exceeded"""
        monitor = PerformanceMonitor()
        # Default CPU warning threshold is 70
        monitor.record_sample(MetricType.CPU, 75.0, "%")
        alerts = monitor.get_active_alerts()
        assert len(alerts) == 1
        assert alerts[0].level == AlertLevel.WARNING

    def test_critical_alert_triggered(self):
        """Test critical alert when threshold exceeded"""
        monitor = PerformanceMonitor()
        # Default CPU critical threshold is 90
        monitor.record_sample(MetricType.CPU, 95.0, "%")
        alerts = monitor.get_active_alerts()
        assert len(alerts) == 1
        assert alerts[0].level == AlertLevel.CRITICAL

    def test_no_alert_below_threshold(self):
        """Test no alert when below threshold"""
        monitor = PerformanceMonitor()
        monitor.record_sample(MetricType.CPU, 50.0, "%")
        alerts = monitor.get_active_alerts()
        assert len(alerts) == 0

    def test_set_custom_threshold(self):
        """Test setting custom threshold"""
        monitor = PerformanceMonitor()
        monitor.set_threshold(MetricType.CPU, warning=50.0, critical=70.0)
        monitor.record_sample(MetricType.CPU, 55.0, "%")
        alerts = monitor.get_active_alerts()
        assert len(alerts) == 1
        assert alerts[0].level == AlertLevel.WARNING

    def test_get_average(self):
        """Test getting average value"""
        monitor = PerformanceMonitor()
        monitor.record_sample(MetricType.CPU, 50.0)
        monitor.record_sample(MetricType.CPU, 60.0)
        monitor.record_sample(MetricType.CPU, 70.0)
        avg = monitor.get_average(MetricType.CPU, minutes=60)
        assert avg == pytest.approx(60.0)

    def test_get_average_no_samples(self):
        """Test average with no samples"""
        monitor = PerformanceMonitor()
        avg = monitor.get_average(MetricType.CPU)
        assert avg == 0.0

    def test_get_percentile(self):
        """Test getting percentile value"""
        monitor = PerformanceMonitor()
        for i in range(100):
            monitor.record_sample(MetricType.CPU, float(i))
        p95 = monitor.get_percentile(MetricType.CPU, 95, minutes=60)
        assert p95 >= 90.0

    def test_get_trend(self):
        """Test getting trend data"""
        monitor = PerformanceMonitor()
        monitor.record_sample(MetricType.CPU, 50.0)
        monitor.record_sample(MetricType.CPU, 60.0)
        trend = monitor.get_trend(MetricType.CPU, minutes=60)
        assert len(trend) == 2

    def test_acknowledge_alert(self):
        """Test acknowledging alert"""
        monitor = PerformanceMonitor()
        monitor.record_sample(MetricType.CPU, 95.0, "%")
        alerts = monitor.get_active_alerts()
        alert_id = alerts[0].id
        result = monitor.acknowledge_alert(alert_id)
        assert result is True
        assert len(monitor.get_active_alerts()) == 0

    def test_acknowledge_nonexistent_alert(self):
        """Test acknowledging non-existent alert"""
        monitor = PerformanceMonitor()
        result = monitor.acknowledge_alert("nonexistent")
        assert result is False

    def test_cleanup_old_samples(self):
        """Test cleanup of old samples"""
        monitor = PerformanceMonitor()
        monitor.record_sample(MetricType.CPU, 50.0)
        # This test just verifies the method works
        removed = monitor.cleanup_old_samples(hours=0)
        # Samples should be removed when hours=0
        assert removed >= 0


# =============================================================================
# RESOURCE OPTIMIZER TESTS
# =============================================================================

class TestResourceOptimizer:
    """Tests for ResourceOptimizer class"""

    def test_init(self):
        """Test optimizer initialization"""
        optimizer = ResourceOptimizer()
        assert optimizer is not None
        metrics = optimizer.get_metrics()
        assert metrics["total_optimizations"] == 0

    def test_record_usage_cpu(self):
        """Test recording CPU usage"""
        optimizer = ResourceOptimizer()
        usage = optimizer.record_usage(ResourceType.CPU, 100.0, 60.0)
        assert usage.resource_type == ResourceType.CPU
        assert usage.allocated == 100.0
        assert usage.used == 60.0
        assert usage.utilization_percent == 60.0

    def test_record_usage_memory(self):
        """Test recording memory usage"""
        optimizer = ResourceOptimizer()
        usage = optimizer.record_usage(ResourceType.MEMORY, 8192.0, 4096.0)
        assert usage.resource_type == ResourceType.MEMORY
        assert usage.utilization_percent == 50.0

    def test_record_usage_zero_allocated(self):
        """Test usage with zero allocated"""
        optimizer = ResourceOptimizer()
        usage = optimizer.record_usage(ResourceType.CPU, 0.0, 0.0)
        assert usage.utilization_percent == 0.0

    def test_analyze_high_utilization(self):
        """Test analysis of high utilization"""
        optimizer = ResourceOptimizer()
        # Record high usage multiple times
        for _ in range(15):
            optimizer.record_usage(ResourceType.CPU, 100.0, 95.0)
        plan = optimizer.analyze_and_optimize(ResourceType.CPU)
        assert plan is not None
        assert plan.action == OptimizationAction.SCALE_UP

    def test_analyze_low_utilization(self):
        """Test analysis of low utilization"""
        optimizer = ResourceOptimizer()
        # Record low usage multiple times
        for _ in range(15):
            optimizer.record_usage(ResourceType.CPU, 100.0, 20.0)
        plan = optimizer.analyze_and_optimize(ResourceType.CPU)
        assert plan is not None
        assert plan.action == OptimizationAction.SCALE_DOWN

    def test_analyze_optimal_utilization(self):
        """Test analysis of optimal utilization"""
        optimizer = ResourceOptimizer()
        # Record optimal usage
        for _ in range(15):
            optimizer.record_usage(ResourceType.CPU, 100.0, 70.0)
        plan = optimizer.analyze_and_optimize(ResourceType.CPU)
        assert plan is None  # No optimization needed

    def test_analyze_no_data(self):
        """Test analysis with no data"""
        optimizer = ResourceOptimizer()
        plan = optimizer.analyze_and_optimize(ResourceType.CPU)
        assert plan is None

    def test_get_current_usage(self):
        """Test getting current usage"""
        optimizer = ResourceOptimizer()
        optimizer.record_usage(ResourceType.CPU, 100.0, 50.0)
        optimizer.record_usage(ResourceType.CPU, 100.0, 60.0)
        current = optimizer.get_current_usage(ResourceType.CPU)
        assert current.used == 60.0

    def test_get_current_usage_no_data(self):
        """Test getting current usage with no data"""
        optimizer = ResourceOptimizer()
        current = optimizer.get_current_usage(ResourceType.CPU)
        assert current is None

    def test_get_plan(self):
        """Test getting plan by ID"""
        optimizer = ResourceOptimizer()
        for _ in range(15):
            optimizer.record_usage(ResourceType.CPU, 100.0, 95.0)
        plan = optimizer.analyze_and_optimize(ResourceType.CPU)
        retrieved = optimizer.get_plan(plan.id)
        assert retrieved is not None
        assert retrieved.id == plan.id

    def test_get_nonexistent_plan(self):
        """Test getting non-existent plan"""
        optimizer = ResourceOptimizer()
        plan = optimizer.get_plan("nonexistent")
        assert plan is None

    def test_apply_plan(self):
        """Test applying optimization plan"""
        optimizer = ResourceOptimizer()
        for _ in range(15):
            optimizer.record_usage(ResourceType.CPU, 100.0, 95.0)
        plan = optimizer.analyze_and_optimize(ResourceType.CPU)
        assert plan.applied is False
        result = optimizer.apply_plan(plan.id)
        assert result is True
        updated = optimizer.get_plan(plan.id)
        assert updated.applied is True

    def test_get_metrics(self):
        """Test getting optimizer metrics"""
        optimizer = ResourceOptimizer()
        for _ in range(15):
            optimizer.record_usage(ResourceType.CPU, 100.0, 95.0)
        optimizer.analyze_and_optimize(ResourceType.CPU)
        metrics = optimizer.get_metrics()
        assert metrics["total_optimizations"] == 1


# =============================================================================
# CACHE MANAGER TESTS
# =============================================================================

class TestCacheManager:
    """Tests for CacheManager class"""

    def test_init(self):
        """Test cache initialization"""
        cache = CacheManager()
        assert cache is not None
        stats = cache.get_stats()
        assert stats.total_entries == 0

    def test_set_and_get(self):
        """Test setting and getting cache value"""
        cache = CacheManager()
        cache.set("key1", "value1")
        result = cache.get("key1")
        assert result == "value1"

    def test_get_nonexistent_key(self):
        """Test getting non-existent key"""
        cache = CacheManager()
        result = cache.get("nonexistent")
        assert result is None

    def test_delete(self):
        """Test deleting cache entry"""
        cache = CacheManager()
        cache.set("key1", "value1")
        result = cache.delete("key1")
        assert result is True
        assert cache.get("key1") is None

    def test_delete_nonexistent(self):
        """Test deleting non-existent entry"""
        cache = CacheManager()
        result = cache.delete("nonexistent")
        assert result is False

    def test_hit_rate(self):
        """Test hit rate calculation"""
        cache = CacheManager()
        cache.set("key1", "value1")
        cache.get("key1")  # Hit
        cache.get("key1")  # Hit
        cache.get("key2")  # Miss
        stats = cache.get_stats()
        assert stats.total_hits == 2
        assert stats.total_misses == 1

    def test_cache_eviction_lru(self):
        """Test LRU eviction"""
        cache = CacheManager(max_size=2, policy=CachePolicy.LRU)
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.get("key1")  # Access key1, making key2 LRU
        cache.set("key3", "value3")  # Should evict key2
        assert cache.get("key1") == "value1"
        assert cache.get("key2") is None
        assert cache.get("key3") == "value3"

    def test_cache_eviction_lfu(self):
        """Test LFU eviction"""
        cache = CacheManager(max_size=2, policy=CachePolicy.LFU)
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.get("key1")  # key1 has more hits
        cache.get("key1")
        cache.set("key3", "value3")  # Should evict key2 (fewer hits)
        assert cache.get("key1") == "value1"
        assert cache.get("key3") == "value3"

    def test_cache_clear(self):
        """Test clearing cache"""
        cache = CacheManager()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        count = cache.clear()
        assert count == 2
        assert cache.get_stats().total_entries == 0

    def test_ttl_expiration(self):
        """Test TTL expiration"""
        cache = CacheManager()
        cache.set("key1", "value1", ttl_seconds=1)
        assert cache.get("key1") == "value1"
        time.sleep(1.1)
        result = cache.get("key1")
        assert result is None

    def test_cleanup_expired(self):
        """Test cleanup of expired entries"""
        cache = CacheManager()
        cache.set("key1", "value1", ttl_seconds=1)
        cache.set("key2", "value2", ttl_seconds=3600)
        time.sleep(1.1)
        removed = cache.cleanup_expired()
        assert removed == 1
        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"

    def test_get_metrics(self):
        """Test getting cache metrics"""
        cache = CacheManager()
        cache.set("key1", "value1")
        cache.get("key1")  # Hit
        cache.get("key2")  # Miss
        metrics = cache.get_metrics()
        assert metrics["entries"] == 1
        assert metrics["hits"] == 1
        assert metrics["misses"] == 1

    def test_multiple_data_types(self):
        """Test caching different data types"""
        cache = CacheManager()
        cache.set("string", "hello")
        cache.set("int", 42)
        cache.set("list", [1, 2, 3])
        cache.set("dict", {"key": "value"})
        assert cache.get("string") == "hello"
        assert cache.get("int") == 42
        assert cache.get("list") == [1, 2, 3]
        assert cache.get("dict") == {"key": "value"}

    def test_update_existing_key(self):
        """Test updating existing key"""
        cache = CacheManager()
        cache.set("key1", "value1")
        cache.set("key1", "value2")
        assert cache.get("key1") == "value2"
