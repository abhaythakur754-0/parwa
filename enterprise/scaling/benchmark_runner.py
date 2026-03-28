"""
Benchmark Runner Module - Week 52, Builder 4
Benchmark execution and reporting
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Tuple
import asyncio
import json
import logging
import statistics
import time
import uuid

logger = logging.getLogger(__name__)


class BenchmarkStatus(Enum):
    """Benchmark status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class BenchmarkCategory(Enum):
    """Benchmark category"""
    PERFORMANCE = "performance"
    LATENCY = "latency"
    THROUGHPUT = "throughput"
    MEMORY = "memory"
    CPU = "cpu"
    CUSTOM = "custom"


@dataclass
class BenchmarkConfig:
    """Benchmark configuration"""
    name: str
    category: BenchmarkCategory
    description: str = ""
    iterations: int = 100
    warmup_iterations: int = 10
    timeout_seconds: float = 300.0
    baseline: Optional[float] = None
    threshold: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkResult:
    """Single benchmark iteration result"""
    iteration: int
    duration_ns: int
    success: bool
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkStats:
    """Aggregated benchmark statistics"""
    total_iterations: int = 0
    successful_iterations: int = 0
    failed_iterations: int = 0
    min_ns: int = 0
    max_ns: int = 0
    mean_ns: float = 0
    median_ns: float = 0
    std_dev_ns: float = 0
    p50_ns: float = 0
    p75_ns: float = 0
    p90_ns: float = 0
    p95_ns: float = 0
    p99_ns: float = 0
    ops_per_second: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "total_iterations": self.total_iterations,
            "successful_iterations": self.successful_iterations,
            "failed_iterations": self.failed_iterations,
            "min_ns": self.min_ns,
            "max_ns": self.max_ns,
            "mean_ns": self.mean_ns,
            "median_ns": self.median_ns,
            "std_dev_ns": self.std_dev_ns,
            "p50_ns": self.p50_ns,
            "p75_ns": self.p75_ns,
            "p90_ns": self.p90_ns,
            "p95_ns": self.p95_ns,
            "p99_ns": self.p99_ns,
            "ops_per_second": self.ops_per_second,
        }


@dataclass
class BenchmarkReport:
    """Complete benchmark report"""
    benchmark_id: str
    config: BenchmarkConfig
    status: BenchmarkStatus
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    stats: BenchmarkStats = field(default_factory=BenchmarkStats)
    results: List[BenchmarkResult] = field(default_factory=list)
    comparison: Optional[Dict[str, Any]] = None
    passed: Optional[bool] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "benchmark_id": self.benchmark_id,
            "name": self.config.name,
            "category": self.config.category.value,
            "status": self.status.value,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "stats": self.stats.to_dict(),
            "passed": self.passed,
            "comparison": self.comparison,
        }


class BenchmarkRunner:
    """
    Main benchmark execution engine.
    """

    def __init__(self):
        self.benchmarks: Dict[str, BenchmarkReport] = {}
        self._suites: Dict[str, List[str]] = {}
        self._baselines: Dict[str, float] = {}

    def set_baseline(self, benchmark_name: str, baseline_ns: float) -> None:
        """Set baseline for a benchmark"""
        self._baselines[benchmark_name] = baseline_ns

    async def run_benchmark(
        self,
        config: BenchmarkConfig,
        benchmark_fn: Callable,
        setup_fn: Optional[Callable] = None,
        teardown_fn: Optional[Callable] = None,
    ) -> BenchmarkReport:
        """Run a single benchmark"""
        benchmark_id = str(uuid.uuid4())[:8]
        report = BenchmarkReport(
            benchmark_id=benchmark_id,
            config=config,
            status=BenchmarkStatus.PENDING,
        )
        self.benchmarks[benchmark_id] = report

        report.start_time = datetime.utcnow()
        report.status = BenchmarkStatus.RUNNING

        try:
            # Setup
            if setup_fn:
                await self._run_async(setup_fn)

            # Warmup
            for i in range(config.warmup_iterations):
                try:
                    await self._run_async(benchmark_fn)
                except Exception as e:
                    logger.warning(f"Warmup iteration {i} failed: {e}")

            # Main benchmark
            for i in range(config.iterations):
                result = await self._run_iteration(i, benchmark_fn)
                report.results.append(result)

            # Teardown
            if teardown_fn:
                await self._run_async(teardown_fn)

            # Calculate statistics
            report.stats = self._calculate_stats(report.results)

            # Compare with baseline
            if config.name in self._baselines or config.baseline:
                baseline = self._baselines.get(config.name, config.baseline)
                report.comparison = self._compare_with_baseline(
                    report.stats.mean_ns, baseline
                )

            # Check threshold
            if config.threshold:
                report.passed = report.stats.mean_ns <= config.threshold
            else:
                report.passed = True

            report.status = BenchmarkStatus.COMPLETED

        except Exception as e:
            report.status = BenchmarkStatus.FAILED
            report.metadata["error"] = str(e)
            logger.error(f"Benchmark {benchmark_id} failed: {e}")

        report.end_time = datetime.utcnow()
        return report

    async def _run_iteration(
        self,
        iteration: int,
        benchmark_fn: Callable,
    ) -> BenchmarkResult:
        """Run a single benchmark iteration"""
        start = time.perf_counter_ns()

        try:
            await self._run_async(benchmark_fn)
            duration = time.perf_counter_ns() - start
            return BenchmarkResult(
                iteration=iteration,
                duration_ns=duration,
                success=True,
            )

        except Exception as e:
            duration = time.perf_counter_ns() - start
            return BenchmarkResult(
                iteration=iteration,
                duration_ns=duration,
                success=False,
                error=str(e),
            )

    async def _run_async(self, fn: Callable) -> Any:
        """Run function, handling sync/async"""
        import asyncio
        result = fn()
        if asyncio.iscoroutine(result):
            return await result
        return result

    def _calculate_stats(self, results: List[BenchmarkResult]) -> BenchmarkStats:
        """Calculate benchmark statistics"""
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]

        if not successful:
            return BenchmarkStats(
                total_iterations=len(results),
                successful_iterations=0,
                failed_iterations=len(failed),
            )

        durations = [r.duration_ns for r in successful]
        durations_sorted = sorted(durations)

        def percentile(values: List[int], p: float) -> float:
            if not values:
                return 0
            index = (p / 100) * (len(values) - 1)
            lower = int(index)
            upper = lower + 1
            if upper >= len(values):
                return float(values[-1])
            weight = index - lower
            return values[lower] * (1 - weight) + values[upper] * weight

        # Calculate ops per second
        mean_ns = statistics.mean(durations)
        ops_per_second = 1e9 / mean_ns if mean_ns > 0 else 0

        return BenchmarkStats(
            total_iterations=len(results),
            successful_iterations=len(successful),
            failed_iterations=len(failed),
            min_ns=min(durations),
            max_ns=max(durations),
            mean_ns=mean_ns,
            median_ns=statistics.median(durations),
            std_dev_ns=statistics.stdev(durations) if len(durations) >= 2 else 0,
            p50_ns=percentile(durations_sorted, 50),
            p75_ns=percentile(durations_sorted, 75),
            p90_ns=percentile(durations_sorted, 90),
            p95_ns=percentile(durations_sorted, 95),
            p99_ns=percentile(durations_sorted, 99),
            ops_per_second=ops_per_second,
        )

    def _compare_with_baseline(
        self,
        mean_ns: float,
        baseline_ns: float,
    ) -> Dict[str, Any]:
        """Compare with baseline"""
        if baseline_ns == 0:
            return {"error": "Baseline is zero"}

        change_percent = ((mean_ns - baseline_ns) / baseline_ns) * 100

        return {
            "baseline_ns": baseline_ns,
            "current_ns": mean_ns,
            "change_percent": change_percent,
            "improved": mean_ns < baseline_ns,
        }

    def create_suite(self, name: str, benchmark_ids: List[str]) -> None:
        """Create a benchmark suite"""
        self._suites[name] = benchmark_ids

    async def run_suite(
        self,
        suite_name: str,
        benchmarks: List[Tuple[BenchmarkConfig, Callable]],
    ) -> List[BenchmarkReport]:
        """Run all benchmarks in a suite"""
        reports = []

        for config, benchmark_fn in benchmarks:
            report = await self.run_benchmark(config, benchmark_fn)
            reports.append(report)

        return reports

    def get_report(self, benchmark_id: str) -> Optional[BenchmarkReport]:
        """Get benchmark report by ID"""
        return self.benchmarks.get(benchmark_id)

    def get_all_reports(self) -> List[BenchmarkReport]:
        """Get all benchmark reports"""
        return list(self.benchmarks.values())

    def export_results(self, format: str = "json") -> str:
        """Export benchmark results"""
        data = {
            "exported_at": datetime.utcnow().isoformat(),
            "benchmarks": [r.to_dict() for r in self.benchmarks.values()],
        }

        if format == "json":
            return json.dumps(data, indent=2)

        return str(data)

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all benchmarks"""
        reports = self.get_all_reports()

        return {
            "total_benchmarks": len(reports),
            "passed": sum(1 for r in reports if r.passed is True),
            "failed": sum(1 for r in reports if r.passed is False),
            "pending": sum(1 for r in reports if r.status == BenchmarkStatus.PENDING),
            "running": sum(1 for r in reports if r.status == BenchmarkStatus.RUNNING),
            "completed": sum(1 for r in reports if r.status == BenchmarkStatus.COMPLETED),
            "errors": sum(1 for r in reports if r.status == BenchmarkStatus.FAILED),
        }


class BenchmarkScenarios:
    """
    Predefined benchmark scenarios.
    """

    @staticmethod
    def latency_benchmark(name: str, threshold_ns: float = None) -> BenchmarkConfig:
        """Create latency benchmark config"""
        return BenchmarkConfig(
            name=name,
            category=BenchmarkCategory.LATENCY,
            iterations=1000,
            warmup_iterations=100,
            threshold=threshold_ns,
        )

    @staticmethod
    def throughput_benchmark(name: str, baseline: float = None) -> BenchmarkConfig:
        """Create throughput benchmark config"""
        return BenchmarkConfig(
            name=name,
            category=BenchmarkCategory.THROUGHPUT,
            iterations=100,
            warmup_iterations=20,
            baseline=baseline,
        )

    @staticmethod
    def memory_benchmark(name: str) -> BenchmarkConfig:
        """Create memory benchmark config"""
        return BenchmarkConfig(
            name=name,
            category=BenchmarkCategory.MEMORY,
            iterations=50,
            warmup_iterations=10,
        )

    @staticmethod
    def cpu_benchmark(name: str) -> BenchmarkConfig:
        """Create CPU benchmark config"""
        return BenchmarkConfig(
            name=name,
            category=BenchmarkCategory.CPU,
            iterations=100,
            warmup_iterations=20,
        )


class PerformanceRegression:
    """
    Detect performance regressions.
    """

    def __init__(self, threshold_percent: float = 10.0):
        self.threshold_percent = threshold_percent
        self.history: Dict[str, List[float]] = {}

    def record(self, benchmark_name: str, value_ns: float) -> None:
        """Record a benchmark result"""
        if benchmark_name not in self.history:
            self.history[benchmark_name] = []
        self.history[benchmark_name].append(value_ns)

    def check_regression(
        self,
        benchmark_name: str,
        current_value: float,
    ) -> Dict[str, Any]:
        """Check for performance regression"""
        history = self.history.get(benchmark_name, [])

        if not history:
            return {
                "has_regression": False,
                "reason": "No history available",
            }

        baseline = statistics.mean(history[-10:])  # Average of last 10
        change_percent = ((current_value - baseline) / baseline) * 100

        has_regression = change_percent > self.threshold_percent

        return {
            "has_regression": has_regression,
            "baseline_ns": baseline,
            "current_ns": current_value,
            "change_percent": change_percent,
            "threshold_percent": self.threshold_percent,
        }

    def get_trend(self, benchmark_name: str) -> str:
        """Get performance trend"""
        history = self.history.get(benchmark_name, [])

        if len(history) < 5:
            return "insufficient_data"

        first_half = statistics.mean(history[:len(history)//2])
        second_half = statistics.mean(history[len(history)//2:])

        change = ((second_half - first_half) / first_half) * 100

        if change > 5:
            return "degrading"
        elif change < -5:
            return "improving"
        return "stable"
