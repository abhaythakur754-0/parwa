"""
Week 59 - Builder 3 Tests: Performance Testing Module
Unit tests for Performance Tester, Latency Tracker, and Resource Monitor
"""

import pytest
import time
from parwa_testing_qa.performance_testing import (
    PerformanceTester, BenchmarkResult, BenchmarkType,
    LatencyTracker, LatencyMeasurement,
    ResourceMonitor, ResourceSnapshot
)


class TestPerformanceTester:
    """Tests for PerformanceTester class"""

    @pytest.fixture
    def tester(self):
        """Create performance tester"""
        return PerformanceTester()

    def test_run_benchmark(self, tester):
        """Test benchmark execution"""
        result = tester.run_benchmark(
            name="test_op",
            func=lambda: time.sleep(0.001),
            iterations=10,
            warmup=2
        )

        assert result.name == "test_op"
        assert result.iterations == 10
        assert result.value > 0

    def test_compare_with_baseline(self, tester):
        """Test baseline comparison"""
        tester.run_benchmark("test", lambda: None, iterations=5)
        tester.set_baseline("test")

        # Run again to have comparison
        tester.run_benchmark("test", lambda: None, iterations=5)
        comparison = tester.compare_with_baseline("test")

        # Comparison should have baseline and current values
        assert "baseline" in comparison
        assert "current" in comparison
        assert "diff_pct" in comparison

    def test_set_baseline(self, tester):
        """Test setting baseline"""
        tester.run_benchmark("test", lambda: None, iterations=5)
        tester.set_baseline("test")

        assert tester.baseline_results["test"] is not None

    def test_get_benchmark(self, tester):
        """Test get benchmark"""
        tester.run_benchmark("test", lambda: None, iterations=5)
        result = tester.get_benchmark("test")

        assert result is not None
        assert result.name == "test"

    def test_get_all_benchmarks(self, tester):
        """Test get all benchmarks"""
        tester.run_benchmark("test1", lambda: None, iterations=5)
        tester.run_benchmark("test2", lambda: None, iterations=5)

        benchmarks = tester.get_all_benchmarks()
        assert len(benchmarks) == 2


class TestLatencyTracker:
    """Tests for LatencyTracker class"""

    @pytest.fixture
    def tracker(self):
        """Create latency tracker"""
        return LatencyTracker()

    def test_record(self, tracker):
        """Test latency recording"""
        tracker.record("api_call", 150.5)
        tracker.record("api_call", 200.0)

        measurements = tracker.measurements["api_call"]
        assert len(measurements) == 2

    def test_get_percentile(self, tracker):
        """Test percentile calculation"""
        for i in range(100):
            tracker.record("op", i)

        p50 = tracker.get_percentile("op", 50)
        p95 = tracker.get_percentile("op", 95)
        p99 = tracker.get_percentile("op", 99)

        assert p50 >= 45 and p50 <= 55
        assert p95 >= 90
        assert p99 >= 95

    def test_calculate_percentiles(self, tracker):
        """Test percentile calculation"""
        for i in range(100):
            tracker.record("op", i)

        stats = tracker.calculate_percentiles("op")

        assert "p50" in stats
        assert "p95" in stats
        assert "p99" in stats
        assert "avg" in stats

    def test_get_stats(self, tracker):
        """Test statistics"""
        tracker.record("op", 100)
        tracker.record("op", 200)

        stats = tracker.get_stats("op")
        assert stats["count"] == 2
        assert stats["min"] == 100
        assert stats["max"] == 200

    def test_get_all_stats(self, tracker):
        """Test all stats"""
        tracker.record("op1", 100)
        tracker.record("op2", 200)

        all_stats = tracker.get_all_stats()
        assert "op1" in all_stats
        assert "op2" in all_stats

    def test_clear(self, tracker):
        """Test clear measurements"""
        tracker.record("op", 100)
        tracker.clear("op")

        assert len(tracker.measurements["op"]) == 0


class TestResourceMonitor:
    """Tests for ResourceMonitor class"""

    @pytest.fixture
    def monitor(self):
        """Create resource monitor"""
        return ResourceMonitor()

    def test_start_stop(self, monitor):
        """Test start/stop monitoring"""
        monitor.start()
        assert monitor.running is True

        monitor.stop()
        assert monitor.running is False

    def test_get_current(self, monitor):
        """Test get current resource usage"""
        monitor.record_snapshot(50.0, 256.0)
        current = monitor.get_current()

        assert current.cpu_percent == 50.0
        assert current.memory_mb == 256.0

    def test_get_history(self, monitor):
        """Test get history"""
        monitor.record_snapshot(30.0, 100.0)
        monitor.record_snapshot(40.0, 150.0)

        history = monitor.get_history(60)
        assert len(history) >= 2

    def test_get_statistics(self, monitor):
        """Test statistics"""
        for i in range(10):
            monitor.record_snapshot(float(i * 10), float(i * 50))

        stats = monitor.get_statistics(60)

        assert "cpu" in stats
        assert "memory" in stats
        assert stats["samples"] >= 1

    def test_record_snapshot(self, monitor):
        """Test manual snapshot recording"""
        monitor.record_snapshot(75.0, 512.0)

        assert len(monitor.snapshots) == 1
        assert monitor.current.cpu_percent == 75.0

    def test_get_average_cpu(self, monitor):
        """Test average CPU"""
        monitor.record_snapshot(50.0, 100.0)
        monitor.record_snapshot(70.0, 100.0)

        avg = monitor.get_average_cpu(60)
        assert avg >= 50.0 and avg <= 70.0

    def test_get_average_memory(self, monitor):
        """Test average memory"""
        monitor.record_snapshot(50.0, 200.0)
        monitor.record_snapshot(50.0, 400.0)

        avg = monitor.get_average_memory(60)
        assert avg >= 200.0 and avg <= 400.0
