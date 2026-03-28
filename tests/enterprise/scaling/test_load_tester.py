"""
Tests for Load Tester Module - Week 52, Builder 4
"""

import pytest
from datetime import datetime, timedelta
import asyncio

from enterprise.scaling.load_tester import (
    LoadTester,
    LoadTestConfig,
    LoadTestResult,
    LoadTestMetrics,
    LoadTestStatus,
    LoadPattern,
    RequestGenerator,
    MetricsAggregator,
    RequestResult,
    LoadTestScenario,
)
from enterprise.scaling.stress_tester import (
    StressTester,
    StressTestConfig,
    StressTestResult,
    StressTestStatus,
    StressTestType,
    StressPoint,
    BreakingPoint,
    SystemMonitor,
    ResourceStressTester,
    StressTestScenarios,
)
from enterprise.scaling.benchmark_runner import (
    BenchmarkRunner,
    BenchmarkConfig,
    BenchmarkReport,
    BenchmarkStats,
    BenchmarkStatus,
    BenchmarkCategory,
    BenchmarkResult,
    BenchmarkScenarios,
    PerformanceRegression,
)


# ============================================================================
# Load Tester Tests
# ============================================================================

class TestLoadTestConfig:
    """Tests for LoadTestConfig class"""

    def test_init(self):
        """Test config initialization"""
        config = LoadTestConfig(
            name="Test",
            target_url="http://test.com",
        )
        assert config.name == "Test"
        assert config.duration_seconds == 60
        assert config.concurrent_users == 10

    def test_custom_config(self):
        """Test custom config values"""
        config = LoadTestConfig(
            name="Custom",
            target_url="http://test.com",
            duration_seconds=120,
            concurrent_users=50,
            pattern=LoadPattern.SPIKE,
        )
        assert config.duration_seconds == 120
        assert config.concurrent_users == 50
        assert config.pattern == LoadPattern.SPIKE


class TestRequestGenerator:
    """Tests for RequestGenerator class"""

    def test_init(self):
        """Test generator initialization"""
        config = LoadTestConfig(name="Test", target_url="http://test.com")
        gen = RequestGenerator(config)
        assert gen.config == config

    def test_get_current_load_constant(self):
        """Test constant load pattern"""
        config = LoadTestConfig(
            name="Test",
            target_url="http://test.com",
            concurrent_users=100,
            ramp_up_seconds=10,
            pattern=LoadPattern.CONSTANT,
        )
        gen = RequestGenerator(config)

        # Before ramp-up
        load = gen.get_current_load(5)
        assert load < 100

        # After ramp-up
        load = gen.get_current_load(15)
        assert load == 100

    def test_get_current_load_ramp_up(self):
        """Test ramp-up load pattern"""
        config = LoadTestConfig(
            name="Test",
            target_url="http://test.com",
            concurrent_users=100,
            duration_seconds=60,
            ramp_up_seconds=10,
            pattern=LoadPattern.RAMP_UP,
        )
        gen = RequestGenerator(config)

        load_early = gen.get_current_load(10)
        load_late = gen.get_current_load(50)
        assert load_late > load_early

    def test_get_think_time(self):
        """Test think time generation"""
        config = LoadTestConfig(
            name="Test",
            target_url="http://test.com",
            think_time_min=0.5,
            think_time_max=1.5,
        )
        gen = RequestGenerator(config)

        for _ in range(10):
            think = gen.get_think_time()
            assert 0.5 <= think <= 1.5


class TestMetricsAggregator:
    """Tests for MetricsAggregator class"""

    def test_init(self):
        """Test aggregator initialization"""
        agg = MetricsAggregator()
        assert len(agg.results) == 0

    def test_add_result(self):
        """Test adding result"""
        agg = MetricsAggregator()
        result = RequestResult(
            request_id="test-1",
            timestamp=datetime.utcnow(),
            duration_ms=100,
            status_code=200,
            success=True,
        )
        agg.add_result(result)
        assert len(agg.results) == 1

    def test_get_metrics(self):
        """Test getting metrics"""
        agg = MetricsAggregator()
        for i in range(10):
            agg.add_result(RequestResult(
                request_id=f"test-{i}",
                timestamp=datetime.utcnow(),
                duration_ms=100 + i * 10,
                status_code=200 if i < 8 else 500,
                success=i < 8,
                response_size=1000,
            ))

        metrics = agg.get_metrics()
        assert metrics.total_requests == 10
        assert metrics.successful_requests == 8
        assert metrics.failed_requests == 2
        assert metrics.min_latency_ms == 100
        assert metrics.max_latency_ms == 190


class TestLoadTester:
    """Tests for LoadTester class"""

    def test_init(self):
        """Test tester initialization"""
        tester = LoadTester()
        assert len(tester.tests) == 0

    @pytest.mark.asyncio
    async def test_run_test(self):
        """Test running a load test"""
        tester = LoadTester()
        config = LoadTestConfig(
            name="Quick Test",
            target_url="http://test.com",
            duration_seconds=1,
            concurrent_users=2,
            ramp_up_seconds=0,
        )

        result = await tester.run_test(config)
        assert result.status == LoadTestStatus.COMPLETED
        assert result.metrics.total_requests > 0

    def test_get_test(self):
        """Test getting test result"""
        tester = LoadTester()
        result = LoadTestResult(
            test_id="test-123",
            config=LoadTestConfig(name="Test", target_url="http://test.com"),
            status=LoadTestStatus.PENDING,
        )
        tester.tests["test-123"] = result

        retrieved = tester.get_test("test-123")
        assert retrieved.test_id == "test-123"

    def test_get_all_tests(self):
        """Test getting all tests"""
        tester = LoadTester()
        tester.tests["1"] = LoadTestResult(
            test_id="1",
            config=LoadTestConfig(name="T1", target_url="http://test.com"),
            status=LoadTestStatus.COMPLETED,
        )
        tester.tests["2"] = LoadTestResult(
            test_id="2",
            config=LoadTestConfig(name="T2", target_url="http://test.com"),
            status=LoadTestStatus.COMPLETED,
        )

        all_tests = tester.get_all_tests()
        assert len(all_tests) == 2


class TestLoadTestScenario:
    """Tests for LoadTestScenario class"""

    def test_smoke_test(self):
        """Test smoke test scenario"""
        config = LoadTestScenario.smoke_test("http://test.com")
        assert config.name == "Smoke Test"
        assert config.duration_seconds == 30

    def test_load_test(self):
        """Test load test scenario"""
        config = LoadTestScenario.load_test("http://test.com")
        assert config.name == "Load Test"
        assert config.concurrent_users == 50

    def test_stress_test(self):
        """Test stress test scenario"""
        config = LoadTestScenario.stress_test("http://test.com")
        assert config.concurrent_users == 200
        assert config.pattern == LoadPattern.RAMP_UP

    def test_spike_test(self):
        """Test spike test scenario"""
        config = LoadTestScenario.spike_test("http://test.com")
        assert config.pattern == LoadPattern.SPIKE

    def test_soak_test(self):
        """Test soak test scenario"""
        config = LoadTestScenario.soak_test("http://test.com")
        assert config.duration_seconds == 3600


# ============================================================================
# Stress Tester Tests
# ============================================================================

class TestSystemMonitor:
    """Tests for SystemMonitor class"""

    def test_init(self):
        """Test monitor initialization"""
        monitor = SystemMonitor()
        assert "cpu" in monitor.metrics

    def test_record(self):
        """Test recording metric"""
        monitor = SystemMonitor()
        monitor.record("cpu", 50)
        assert len(monitor.metrics["cpu"]) == 1

    def test_get_average(self):
        """Test getting average"""
        monitor = SystemMonitor()
        monitor.record("cpu", 40)
        monitor.record("cpu", 50)
        monitor.record("cpu", 60)
        avg = monitor.get_average("cpu")
        assert avg == 50

    def test_get_trend_increasing(self):
        """Test trend detection - increasing"""
        monitor = SystemMonitor()
        for i in range(10):
            monitor.record("cpu", i * 10)
        trend = monitor.get_trend("cpu")
        assert trend == "increasing"


class TestStressTestConfig:
    """Tests for StressTestConfig class"""

    def test_init(self):
        """Test config initialization"""
        config = StressTestConfig(
            name="Test",
            test_type=StressTestType.BREAKPOINT,
            target="http://test.com",
        )
        assert config.test_type == StressTestType.BREAKPOINT

    def test_custom_config(self):
        """Test custom config"""
        config = StressTestConfig(
            name="Custom",
            test_type=StressTestType.SATURATION,
            target="http://test.com",
            initial_load=50,
            max_load=500,
            increment=25,
        )
        assert config.initial_load == 50
        assert config.max_load == 500


class TestStressTester:
    """Tests for StressTester class"""

    def test_init(self):
        """Test tester initialization"""
        tester = StressTester()
        assert len(tester.tests) == 0

    @pytest.mark.asyncio
    async def test_run_test(self):
        """Test running a stress test"""
        tester = StressTester()
        config = StressTestConfig(
            name="Quick Stress",
            test_type=StressTestType.BREAKPOINT,
            target="http://test.com",
            initial_load=5,
            max_load=10,
            increment=5,
            increment_interval=1,
            warmup_duration=0,
            cooldown_duration=0,
        )

        result = await tester.run_test(config)
        assert result.status == StressTestStatus.COMPLETED
        assert len(result.data_points) > 0

    def test_get_test(self):
        """Test getting test result"""
        tester = StressTester()
        result = StressTestResult(
            test_id="stress-123",
            config=StressTestConfig(
                name="Test",
                test_type=StressTestType.BREAKPOINT,
                target="http://test.com",
            ),
            status=StressTestStatus.PENDING,
        )
        tester.tests["stress-123"] = result

        retrieved = tester.get_test("stress-123")
        assert retrieved.test_id == "stress-123"


class TestResourceStressTester:
    """Tests for ResourceStressTester class"""

    def test_init(self):
        """Test resource stress tester initialization"""
        tester = ResourceStressTester()
        assert len(tester.tests) == 0

    @pytest.mark.asyncio
    async def test_stress_cpu(self):
        """Test CPU stress"""
        tester = ResourceStressTester()
        result = await tester.stress_cpu(threads=2, duration_seconds=1)
        assert result["status"] == "completed"
        assert result["operations"] > 0


class TestStressTestScenarios:
    """Tests for StressTestScenarios class"""

    def test_find_breaking_point(self):
        """Test breaking point scenario"""
        config = StressTestScenarios.find_breaking_point("http://test.com")
        assert config.test_type == StressTestType.BREAKPOINT

    def test_find_saturation_point(self):
        """Test saturation point scenario"""
        config = StressTestScenarios.find_saturation_point("http://test.com")
        assert config.test_type == StressTestType.SATURATION

    def test_endurance_test(self):
        """Test endurance scenario"""
        config = StressTestScenarios.endurance_test("http://test.com")
        assert config.test_type == StressTestType.ENDURANCE


# ============================================================================
# Benchmark Runner Tests
# ============================================================================

class TestBenchmarkConfig:
    """Tests for BenchmarkConfig class"""

    def test_init(self):
        """Test config initialization"""
        config = BenchmarkConfig(
            name="Test",
            category=BenchmarkCategory.PERFORMANCE,
        )
        assert config.name == "Test"
        assert config.iterations == 100

    def test_custom_config(self):
        """Test custom config"""
        config = BenchmarkConfig(
            name="Custom",
            category=BenchmarkCategory.LATENCY,
            iterations=500,
            warmup_iterations=50,
            threshold=1000.0,
        )
        assert config.iterations == 500
        assert config.threshold == 1000.0


class TestBenchmarkStats:
    """Tests for BenchmarkStats class"""

    def test_init(self):
        """Test stats initialization"""
        stats = BenchmarkStats()
        assert stats.total_iterations == 0

    def test_to_dict(self):
        """Test to_dict method"""
        stats = BenchmarkStats(
            total_iterations=100,
            mean_ns=1000.0,
            ops_per_second=1000000.0,
        )
        d = stats.to_dict()
        assert d["total_iterations"] == 100
        assert d["mean_ns"] == 1000.0


class TestBenchmarkRunner:
    """Tests for BenchmarkRunner class"""

    def test_init(self):
        """Test runner initialization"""
        runner = BenchmarkRunner()
        assert len(runner.benchmarks) == 0

    def test_set_baseline(self):
        """Test setting baseline"""
        runner = BenchmarkRunner()
        runner.set_baseline("test_bench", 1000.0)
        assert runner._baselines["test_bench"] == 1000.0

    @pytest.mark.asyncio
    async def test_run_benchmark(self):
        """Test running a benchmark"""
        runner = BenchmarkRunner()
        config = BenchmarkConfig(
            name="Quick Bench",
            category=BenchmarkCategory.PERFORMANCE,
            iterations=10,
            warmup_iterations=2,
        )

        async def bench_fn():
            await asyncio.sleep(0.001)
            return True

        report = await runner.run_benchmark(config, bench_fn)
        assert report.status == BenchmarkStatus.COMPLETED
        assert report.stats.successful_iterations == 10

    def test_get_report(self):
        """Test getting report"""
        runner = BenchmarkRunner()
        report = BenchmarkReport(
            benchmark_id="bench-123",
            config=BenchmarkConfig(name="Test", category=BenchmarkCategory.PERFORMANCE),
            status=BenchmarkStatus.COMPLETED,
        )
        runner.benchmarks["bench-123"] = report

        retrieved = runner.get_report("bench-123")
        assert retrieved.benchmark_id == "bench-123"

    def test_get_summary(self):
        """Test getting summary"""
        runner = BenchmarkRunner()
        runner.benchmarks["1"] = BenchmarkReport(
            benchmark_id="1",
            config=BenchmarkConfig(name="T1", category=BenchmarkCategory.PERFORMANCE),
            status=BenchmarkStatus.COMPLETED,
            passed=True,
        )
        runner.benchmarks["2"] = BenchmarkReport(
            benchmark_id="2",
            config=BenchmarkConfig(name="T2", category=BenchmarkCategory.PERFORMANCE),
            status=BenchmarkStatus.COMPLETED,
            passed=False,
        )

        summary = runner.get_summary()
        assert summary["total_benchmarks"] == 2
        assert summary["passed"] == 1
        assert summary["failed"] == 1

    def test_export_results(self):
        """Test exporting results"""
        runner = BenchmarkRunner()
        runner.benchmarks["1"] = BenchmarkReport(
            benchmark_id="1",
            config=BenchmarkConfig(name="T1", category=BenchmarkCategory.PERFORMANCE),
            status=BenchmarkStatus.COMPLETED,
        )

        exported = runner.export_results("json")
        assert "benchmarks" in exported


class TestBenchmarkScenarios:
    """Tests for BenchmarkScenarios class"""

    def test_latency_benchmark(self):
        """Test latency benchmark config"""
        config = BenchmarkScenarios.latency_benchmark("test", threshold_ns=1000)
        assert config.category == BenchmarkCategory.LATENCY
        assert config.threshold == 1000

    def test_throughput_benchmark(self):
        """Test throughput benchmark config"""
        config = BenchmarkScenarios.throughput_benchmark("test", baseline=500.0)
        assert config.category == BenchmarkCategory.THROUGHPUT
        assert config.baseline == 500.0

    def test_memory_benchmark(self):
        """Test memory benchmark config"""
        config = BenchmarkScenarios.memory_benchmark("test")
        assert config.category == BenchmarkCategory.MEMORY

    def test_cpu_benchmark(self):
        """Test CPU benchmark config"""
        config = BenchmarkScenarios.cpu_benchmark("test")
        assert config.category == BenchmarkCategory.CPU


class TestPerformanceRegression:
    """Tests for PerformanceRegression class"""

    def test_init(self):
        """Test regression detector initialization"""
        detector = PerformanceRegression(threshold_percent=10.0)
        assert detector.threshold_percent == 10.0

    def test_record(self):
        """Test recording value"""
        detector = PerformanceRegression()
        detector.record("test", 100.0)
        assert len(detector.history["test"]) == 1

    def test_check_regression_no_history(self):
        """Test check with no history"""
        detector = PerformanceRegression()
        result = detector.check_regression("test", 100.0)
        assert result["has_regression"] is False

    def test_check_regression_improvement(self):
        """Test check with improvement"""
        detector = PerformanceRegression()
        for _ in range(10):
            detector.record("test", 100.0)

        result = detector.check_regression("test", 90.0)  # 10% faster
        assert result["has_regression"] is False

    def test_check_regression_detected(self):
        """Test regression detection"""
        detector = PerformanceRegression(threshold_percent=5.0)
        for _ in range(10):
            detector.record("test", 100.0)

        result = detector.check_regression("test", 110.0)  # 10% slower
        assert result["has_regression"] is True

    def test_get_trend_improving(self):
        """Test trend - improving"""
        detector = PerformanceRegression()
        for i in range(10):
            detector.record("test", 100.0 - i * 2)  # Getting faster

        trend = detector.get_trend("test")
        assert trend == "improving"

    def test_get_trend_degrading(self):
        """Test trend - degrading"""
        detector = PerformanceRegression()
        for i in range(10):
            detector.record("test", 100.0 + i * 5)  # Getting slower

        trend = detector.get_trend("test")
        assert trend == "degrading"
