"""
Week 59 - Builder 3: Performance Testing Module
Performance testing, latency tracking, and resource monitoring
"""

import time
import threading
import statistics
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import logging
import math

logger = logging.getLogger(__name__)


class BenchmarkType(Enum):
    """Benchmark types"""
    THROUGHPUT = "throughput"
    LATENCY = "latency"
    MEMORY = "memory"
    CPU = "cpu"
    CUSTOM = "custom"


class MetricType(Enum):
    """Metric types"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"


@dataclass
class BenchmarkResult:
    """Benchmark execution result"""
    name: str
    benchmark_type: BenchmarkType
    value: float
    unit: str = ""
    iterations: int = 1
    duration_ms: float = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class LatencyMeasurement:
    """Latency measurement record"""
    operation: str
    latency_ms: float
    timestamp: float = field(default_factory=time.time)
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class ResourceSnapshot:
    """Resource usage snapshot"""
    cpu_percent: float = 0
    memory_mb: float = 0
    io_read_bytes: int = 0
    io_write_bytes: int = 0
    timestamp: float = field(default_factory=time.time)


class PerformanceTester:
    """
    Performance tester for benchmarks and profiling
    """

    def __init__(self):
        self.benchmarks: Dict[str, BenchmarkResult] = {}
        self.baseline_results: Dict[str, float] = {}
        self.lock = threading.Lock()
        self.stats: Dict[str, List[float]] = defaultdict(list)

    def run_benchmark(self, name: str, func: Callable,
                      iterations: int = 100,
                      benchmark_type: BenchmarkType = BenchmarkType.LATENCY,
                      warmup: int = 10) -> BenchmarkResult:
        """Run a benchmark"""
        # Warmup
        for _ in range(warmup):
            try:
                func()
            except Exception:
                pass

        # Actual benchmark
        times = []
        start_total = time.time()

        for _ in range(iterations):
            start = time.perf_counter()
            try:
                func()
            except Exception as e:
                logger.warning(f"Benchmark iteration failed: {e}")
            end = time.perf_counter()
            times.append((end - start) * 1000)  # ms

        total_duration = (time.time() - start_total) * 1000

        result = BenchmarkResult(
            name=name,
            benchmark_type=benchmark_type,
            value=statistics.mean(times) if times else 0,
            unit="ms",
            iterations=iterations,
            duration_ms=total_duration,
            metadata={
                "min": min(times) if times else 0,
                "max": max(times) if times else 0,
                "stddev": statistics.stdev(times) if len(times) > 1 else 0
            }
        )

        with self.lock:
            self.benchmarks[name] = result
            self.stats[name] = times

        return result

    def compare_with_baseline(self, name: str, threshold_pct: float = 10) -> Dict[str, Any]:
        """Compare result with baseline"""
        result = self.benchmarks.get(name)
        baseline = self.baseline_results.get(name)

        if not result or baseline is None:
            return {"status": "no_comparison"}

        diff_pct = ((result.value - baseline) / baseline) * 100

        return {
            "name": name,
            "current": result.value,
            "baseline": baseline,
            "diff_pct": diff_pct,
            "regression": diff_pct > threshold_pct,
            "improvement": diff_pct < -threshold_pct
        }

    def set_baseline(self, name: str, value: float = None) -> None:
        """Set baseline value"""
        if value is None:
            result = self.benchmarks.get(name)
            if result:
                value = result.value
            else:
                return

        with self.lock:
            self.baseline_results[name] = value

    def get_benchmark(self, name: str) -> Optional[BenchmarkResult]:
        """Get benchmark by name"""
        return self.benchmarks.get(name)

    def get_all_benchmarks(self) -> Dict[str, BenchmarkResult]:
        """Get all benchmark results"""
        return dict(self.benchmarks)


class LatencyTracker:
    """
    Latency tracker for P50/P95/P99 measurements
    """

    def __init__(self):
        self.measurements: Dict[str, List[LatencyMeasurement]] = defaultdict(list)
        self.percentiles: Dict[str, Dict[str, float]] = {}
        self.lock = threading.Lock()
        self.max_measurements = 10000

    def record(self, operation: str, latency_ms: float,
               tags: Dict[str, str] = None) -> None:
        """Record a latency measurement"""
        measurement = LatencyMeasurement(
            operation=operation,
            latency_ms=latency_ms,
            tags=tags or {}
        )

        with self.lock:
            self.measurements[operation].append(measurement)

            # Limit stored measurements
            if len(self.measurements[operation]) > self.max_measurements:
                self.measurements[operation] = \
                    self.measurements[operation][-self.max_measurements:]

    def get_percentile(self, operation: str, percentile: float) -> float:
        """Get latency at percentile"""
        measurements = self.measurements.get(operation, [])
        if not measurements:
            return 0

        values = sorted([m.latency_ms for m in measurements])
        idx = int(len(values) * percentile / 100)
        idx = min(idx, len(values) - 1)

        return values[idx]

    def calculate_percentiles(self, operation: str) -> Dict[str, float]:
        """Calculate P50, P95, P99"""
        measurements = self.measurements.get(operation, [])
        if not measurements:
            return {"p50": 0, "p95": 0, "p99": 0, "avg": 0}

        values = sorted([m.latency_ms for m in measurements])

        def get_p(p: float) -> float:
            idx = int(len(values) * p / 100)
            return values[min(idx, len(values) - 1)]

        result = {
            "p50": get_p(50),
            "p95": get_p(95),
            "p99": get_p(99),
            "avg": sum(values) / len(values),
            "min": values[0],
            "max": values[-1],
            "count": len(values)
        }

        with self.lock:
            self.percentiles[operation] = result

        return result

    def get_stats(self, operation: str) -> Dict[str, Any]:
        """Get latency statistics"""
        return self.calculate_percentiles(operation)

    def get_all_stats(self) -> Dict[str, Dict[str, float]]:
        """Get stats for all operations"""
        return {
            op: self.calculate_percentiles(op)
            for op in self.measurements.keys()
        }

    def clear(self, operation: str = None) -> None:
        """Clear measurements"""
        with self.lock:
            if operation:
                self.measurements[operation] = []
            else:
                self.measurements.clear()


class ResourceMonitor:
    """
    Resource monitor for CPU, memory, and I/O tracking
    """

    def __init__(self, sample_interval: float = 1.0):
        self.sample_interval = sample_interval
        self.snapshots: List[ResourceSnapshot] = []
        self.current: ResourceSnapshot = ResourceSnapshot()
        self.running = False
        self.lock = threading.Lock()
        self.max_snapshots = 3600  # 1 hour at 1s intervals

    def start(self) -> None:
        """Start monitoring"""
        self.running = True
        thread = threading.Thread(target=self._monitor_loop, daemon=True)
        thread.start()

    def stop(self) -> None:
        """Stop monitoring"""
        self.running = False

    def _monitor_loop(self) -> None:
        """Monitoring loop"""
        while self.running:
            self._sample()
            time.sleep(self.sample_interval)

    def _sample(self) -> None:
        """Take a resource sample"""
        # Mock resource sampling (in real impl, use psutil)
        import random
        snapshot = ResourceSnapshot(
            cpu_percent=random.uniform(10, 80),
            memory_mb=random.uniform(100, 500),
            io_read_bytes=random.randint(0, 10000),
            io_write_bytes=random.randint(0, 5000)
        )

        with self.lock:
            self.current = snapshot
            self.snapshots.append(snapshot)

            if len(self.snapshots) > self.max_snapshots:
                self.snapshots = self.snapshots[-self.max_snapshots:]

    def get_current(self) -> ResourceSnapshot:
        """Get current resource usage"""
        return self.current

    def get_history(self, duration_seconds: int = 60) -> List[ResourceSnapshot]:
        """Get resource history"""
        cutoff = time.time() - duration_seconds
        with self.lock:
            return [s for s in self.snapshots if s.timestamp > cutoff]

    def get_statistics(self, duration_seconds: int = 60) -> Dict[str, Any]:
        """Get resource statistics"""
        history = self.get_history(duration_seconds)
        if not history:
            return {}

        cpu_values = [s.cpu_percent for s in history]
        memory_values = [s.memory_mb for s in history]

        return {
            "duration_seconds": duration_seconds,
            "samples": len(history),
            "cpu": {
                "avg": statistics.mean(cpu_values),
                "max": max(cpu_values),
                "min": min(cpu_values)
            },
            "memory": {
                "avg_mb": statistics.mean(memory_values),
                "max_mb": max(memory_values),
                "min_mb": min(memory_values)
            }
        }

    def record_snapshot(self, cpu: float, memory: float) -> None:
        """Manually record a snapshot"""
        snapshot = ResourceSnapshot(
            cpu_percent=cpu,
            memory_mb=memory
        )
        with self.lock:
            self.snapshots.append(snapshot)
            self.current = snapshot

    def get_average_cpu(self, duration_seconds: int = 60) -> float:
        """Get average CPU usage"""
        stats = self.get_statistics(duration_seconds)
        return stats.get("cpu", {}).get("avg", 0)

    def get_average_memory(self, duration_seconds: int = 60) -> float:
        """Get average memory usage"""
        stats = self.get_statistics(duration_seconds)
        return stats.get("memory", {}).get("avg_mb", 0)
