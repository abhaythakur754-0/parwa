"""
Performance Benchmarking for Agent Lightning 94%.

Comprehensive performance benchmarking with:
- Accuracy benchmark
- Speed benchmark
- Memory benchmark
- Throughput benchmark
- Comparison reports
"""

import asyncio
import time
import statistics
import tracemalloc
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import json

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class BenchmarkType(str, Enum):
    """Types of benchmarks."""
    ACCURACY = "accuracy"
    SPEED = "speed"
    MEMORY = "memory"
    THROUGHPUT = "throughput"


class BenchmarkStatus(str, Enum):
    """Status of benchmark run."""
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"


@dataclass
class BenchmarkMetric:
    """Single benchmark metric result."""
    name: str
    value: float
    unit: str
    target: Optional[float] = None
    threshold: Optional[float] = None
    passed: bool = True
    details: str = ""

    def check_pass(self) -> None:
        """Check if metric passes threshold."""
        if self.threshold is not None:
            self.passed = self.value >= self.threshold
        elif self.target is not None:
            # Allow 5% variance from target
            self.passed = abs(self.value - self.target) / self.target <= 0.05


@dataclass
class BenchmarkResult:
    """Result for a single benchmark type."""
    benchmark_type: BenchmarkType
    timestamp: str
    metrics: List[BenchmarkMetric] = field(default_factory=list)
    status: BenchmarkStatus = BenchmarkStatus.PASSED
    duration_seconds: float = 0.0
    sample_count: int = 0

    def __post_init__(self):
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def calculate_status(self) -> None:
        """Calculate overall status from metrics."""
        if not self.metrics:
            self.status = BenchmarkStatus.WARNING
            return

        all_passed = all(m.passed for m in self.metrics)
        if all_passed:
            self.status = BenchmarkStatus.PASSED
        else:
            failed_count = sum(1 for m in self.metrics if not m.passed)
            if failed_count > len(self.metrics) // 2:
                self.status = BenchmarkStatus.FAILED
            else:
                self.status = BenchmarkStatus.WARNING


@dataclass
class ComparisonReport:
    """Full comparison report across all benchmarks."""
    report_id: str
    timestamp: str
    results: List[BenchmarkResult]
    overall_status: BenchmarkStatus
    summary: Dict[str, Any]
    recommendations: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "report_id": self.report_id,
            "timestamp": self.timestamp,
            "overall_status": self.overall_status.value,
            "summary": self.summary,
            "recommendations": self.recommendations,
            "results": [
                {
                    "type": r.benchmark_type.value,
                    "status": r.status.value,
                    "duration_seconds": r.duration_seconds,
                    "sample_count": r.sample_count,
                    "metrics": [
                        {
                            "name": m.name,
                            "value": m.value,
                            "unit": m.unit,
                            "passed": m.passed,
                            "details": m.details
                        }
                        for m in r.metrics
                    ]
                }
                for r in self.results
            ]
        }


class AccuracyBenchmark:
    """
    Accuracy benchmark for Agent Lightning.

    Measures classification accuracy across categories.
    """

    ACCURACY_TARGET = 0.94

    def __init__(self, test_cases: Optional[List[Dict[str, Any]]] = None):
        """
        Initialize accuracy benchmark.

        Args:
            test_cases: Optional test cases for benchmarking
        """
        self.test_cases = test_cases or self._get_default_test_cases()

    def _get_default_test_cases(self) -> List[Dict[str, Any]]:
        """Get default test cases for accuracy benchmarking."""
        return [
            # E-commerce queries
            {"query": "I want a refund for my order", "expected": "refund", "category": "ecommerce"},
            {"query": "Where is my package?", "expected": "shipping", "category": "ecommerce"},
            {"query": "The item arrived damaged", "expected": "returns", "category": "ecommerce"},
            {"query": "How do I track my order?", "expected": "shipping", "category": "ecommerce"},
            {"query": "I need to cancel my order", "expected": "cancellation", "category": "ecommerce"},

            # SaaS queries
            {"query": "How do I upgrade my plan?", "expected": "billing", "category": "saas"},
            {"query": "I can't log into my account", "expected": "account", "category": "saas"},
            {"query": "The API is returning errors", "expected": "technical", "category": "saas"},
            {"query": "How do I integrate with Slack?", "expected": "integration", "category": "saas"},
            {"query": "I need to add more users", "expected": "billing", "category": "saas"},

            # Healthcare queries
            {"query": "How do I schedule an appointment?", "expected": "scheduling", "category": "healthcare"},
            {"query": "What are your operating hours?", "expected": "faq", "category": "healthcare"},
            {"query": "I need to request my medical records", "expected": "records", "category": "healthcare"},
            {"query": "How do I refill my prescription?", "expected": "prescription", "category": "healthcare"},
            {"query": "I need to speak to a doctor", "expected": "escalation", "category": "healthcare"},

            # Financial queries
            {"query": "What is my account balance?", "expected": "account", "category": "financial"},
            {"query": "I want to dispute a transaction", "expected": "dispute", "category": "financial"},
            {"query": "How do I transfer funds?", "expected": "transaction", "category": "financial"},
            {"query": "I need to report fraud", "expected": "fraud", "category": "financial"},
            {"query": "What are your loan rates?", "expected": "products", "category": "financial"},

            # Escalation scenarios
            {"query": "I want to speak to a manager!", "expected": "escalation", "category": "escalation"},
            {"query": "This is unacceptable service!", "expected": "escalation", "category": "escalation"},
            {"query": "I'm filing a formal complaint", "expected": "escalation", "category": "escalation"},

            # FAQ queries
            {"query": "What are your business hours?", "expected": "faq", "category": "faq"},
            {"query": "How can I contact support?", "expected": "faq", "category": "faq"},
            {"query": "What payment methods do you accept?", "expected": "faq", "category": "faq"},
        ]

    async def run(
        self,
        predict_fn: Callable[[str], Tuple[str, float]]
    ) -> BenchmarkResult:
        """
        Run accuracy benchmark.

        Args:
            predict_fn: Function that takes query and returns (prediction, confidence)

        Returns:
            BenchmarkResult with accuracy metrics
        """
        start_time = time.time()
        metrics: List[BenchmarkMetric] = []

        correct_predictions = 0
        total_predictions = len(self.test_cases)
        category_results: Dict[str, Dict[str, int]] = {}
        confidence_scores: List[float] = []

        for case in self.test_cases:
            query = case["query"]
            expected = case["expected"]
            category = case.get("category", "general")

            try:
                prediction, confidence = await predict_fn(query)
                confidence_scores.append(confidence)

                if category not in category_results:
                    category_results[category] = {"correct": 0, "total": 0}

                category_results[category]["total"] += 1

                # Check if prediction is correct (allowing for semantic equivalence)
                is_correct = self._is_prediction_correct(prediction, expected)
                if is_correct:
                    correct_predictions += 1
                    category_results[category]["correct"] += 1

            except Exception as e:
                logger.error({
                    "event": "accuracy_benchmark_error",
                    "query": query[:50],
                    "error": str(e)
                })

        # Calculate overall accuracy
        overall_accuracy = correct_predictions / total_predictions if total_predictions > 0 else 0

        metrics.append(BenchmarkMetric(
            name="overall_accuracy",
            value=overall_accuracy,
            unit="percentage",
            threshold=self.ACCURACY_TARGET,
            details=f"{correct_predictions}/{total_predictions} correct predictions"
        ))
        metrics[-1].check_pass()

        # Calculate per-category accuracy
        for category, results in category_results.items():
            cat_accuracy = results["correct"] / results["total"] if results["total"] > 0 else 0
            metrics.append(BenchmarkMetric(
                name=f"{category}_accuracy",
                value=cat_accuracy,
                unit="percentage",
                threshold=self.ACCURACY_TARGET,
                details=f"{results['correct']}/{results['total']} correct"
            ))
            metrics[-1].check_pass()

        # Calculate average confidence
        if confidence_scores:
            avg_confidence = statistics.mean(confidence_scores)
            metrics.append(BenchmarkMetric(
                name="average_confidence",
                value=avg_confidence,
                unit="score",
                details=f"Min: {min(confidence_scores):.3f}, Max: {max(confidence_scores):.3f}"
            ))

        duration = time.time() - start_time

        result = BenchmarkResult(
            benchmark_type=BenchmarkType.ACCURACY,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metrics=metrics,
            duration_seconds=duration,
            sample_count=total_predictions
        )
        result.calculate_status()

        logger.info({
            "event": "accuracy_benchmark_complete",
            "accuracy": overall_accuracy,
            "passed": metrics[0].passed,
            "duration_seconds": duration
        })

        return result

    def _is_prediction_correct(self, prediction: str, expected: str) -> bool:
        """Check if prediction matches expected with semantic equivalence."""
        if prediction == expected:
            return True

        # Semantic equivalence groups
        equivalence_groups = [
            {"refund", "returns", "cancellation"},
            {"shipping", "order_status", "tracking"},
            {"escalation", "complaint", "manager"},
            {"billing", "payment", "invoice"},
            {"account", "login", "auth"},
            {"technical", "bug", "error"},
        ]

        for group in equivalence_groups:
            if prediction in group and expected in group:
                return True

        return False


class SpeedBenchmark:
    """
    Speed benchmark for Agent Lightning.

    Measures response latency and throughput.
    """

    TARGET_P50_MS = 100
    TARGET_P95_MS = 200
    TARGET_P99_MS = 500

    def __init__(self, sample_queries: Optional[List[str]] = None):
        """
        Initialize speed benchmark.

        Args:
            sample_queries: Optional queries for benchmarking
        """
        self.sample_queries = sample_queries or self._get_default_queries()

    def _get_default_queries(self) -> List[str]:
        """Get default queries for speed benchmarking."""
        return [
            "What are your business hours?",
            "I need a refund",
            "Where is my order?",
            "How do I reset my password?",
            "I want to speak to a manager",
            "What is your return policy?",
            "My payment was declined",
            "How do I cancel my subscription?",
            "I'm having technical issues",
            "Can I change my shipping address?",
        ]

    async def run(
        self,
        predict_fn: Callable[[str], Tuple[str, float]],
        iterations: int = 10
    ) -> BenchmarkResult:
        """
        Run speed benchmark.

        Args:
            predict_fn: Function that takes query and returns prediction
            iterations: Number of iterations per query

        Returns:
            BenchmarkResult with speed metrics
        """
        start_time = time.time()
        metrics: List[BenchmarkMetric] = []

        latencies: List[float] = []
        errors = 0

        for _ in range(iterations):
            for query in self.sample_queries:
                try:
                    iter_start = time.perf_counter()
                    await predict_fn(query)
                    iter_end = time.perf_counter()

                    latency_ms = (iter_end - iter_start) * 1000
                    latencies.append(latency_ms)

                except Exception as e:
                    errors += 1
                    logger.error({
                        "event": "speed_benchmark_error",
                        "query": query[:30],
                        "error": str(e)
                    })

        if latencies:
            # Calculate percentile latencies
            latencies_sorted = sorted(latencies)
            p50_idx = int(len(latencies_sorted) * 0.50)
            p95_idx = int(len(latencies_sorted) * 0.95)
            p99_idx = int(len(latencies_sorted) * 0.99)

            p50 = latencies_sorted[p50_idx]
            p95 = latencies_sorted[p95_idx]
            p99 = latencies_sorted[p99_idx]

            metrics.append(BenchmarkMetric(
                name="p50_latency",
                value=p50,
                unit="ms",
                threshold=self.TARGET_P50_MS,
                details=f"Target: {self.TARGET_P50_MS}ms"
            ))
            metrics[-1].check_pass()

            metrics.append(BenchmarkMetric(
                name="p95_latency",
                value=p95,
                unit="ms",
                threshold=self.TARGET_P95_MS,
                details=f"Target: {self.TARGET_P95_MS}ms"
            ))
            metrics[-1].check_pass()

            metrics.append(BenchmarkMetric(
                name="p99_latency",
                value=p99,
                unit="ms",
                threshold=self.TARGET_P99_MS,
                details=f"Target: {self.TARGET_P99_MS}ms"
            ))
            metrics[-1].check_pass()

            # Average and min/max
            metrics.append(BenchmarkMetric(
                name="avg_latency",
                value=statistics.mean(latencies),
                unit="ms",
                details=f"Min: {min(latencies):.2f}ms, Max: {max(latencies):.2f}ms"
            ))

            metrics.append(BenchmarkMetric(
                name="min_latency",
                value=min(latencies),
                unit="ms"
            ))

            metrics.append(BenchmarkMetric(
                name="max_latency",
                value=max(latencies),
                unit="ms"
            ))

        # Error rate
        total_requests = iterations * len(self.sample_queries)
        error_rate = errors / total_requests if total_requests > 0 else 0
        metrics.append(BenchmarkMetric(
            name="error_rate",
            value=error_rate,
            unit="percentage",
            threshold=0.01,  # Max 1% error rate
            details=f"{errors}/{total_requests} errors"
        ))
        metrics[-1].check_pass()

        duration = time.time() - start_time

        result = BenchmarkResult(
            benchmark_type=BenchmarkType.SPEED,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metrics=metrics,
            duration_seconds=duration,
            sample_count=total_requests
        )
        result.calculate_status()

        logger.info({
            "event": "speed_benchmark_complete",
            "p50_ms": p50 if latencies else None,
            "p95_ms": p95 if latencies else None,
            "p99_ms": p99 if latencies else None,
            "duration_seconds": duration
        })

        return result


class MemoryBenchmark:
    """
    Memory benchmark for Agent Lightning.

    Measures memory usage during operations.
    """

    MAX_MEMORY_MB = 500
    MAX_PEAK_MEMORY_MB = 1000

    def __init__(self, sample_queries: Optional[List[str]] = None):
        """
        Initialize memory benchmark.

        Args:
            sample_queries: Optional queries for benchmarking
        """
        self.sample_queries = sample_queries or self._get_default_queries()

    def _get_default_queries(self) -> List[str]:
        """Get default queries for memory benchmarking."""
        return [
            "I need a refund for my order #12345",
            "Where is my package? It's been 2 weeks!",
            "The product quality is terrible and I want my money back",
            "How do I change my shipping address for order #67890?",
            "I've been charged twice for the same order",
        ]

    async def run(
        self,
        predict_fn: Callable[[str], Tuple[str, float]],
        iterations: int = 100
    ) -> BenchmarkResult:
        """
        Run memory benchmark.

        Args:
            predict_fn: Function that takes query and returns prediction
            iterations: Number of iterations for memory profiling

        Returns:
            BenchmarkResult with memory metrics
        """
        start_time = time.time()
        metrics: List[BenchmarkMetric] = []

        # Start memory tracking
        tracemalloc.start()

        memory_samples: List[float] = []

        for i in range(iterations):
            query = self.sample_queries[i % len(self.sample_queries)]

            try:
                await predict_fn(query)

                # Sample memory usage
                current, peak = tracemalloc.get_traced_memory()
                memory_samples.append(current / 1024 / 1024)  # Convert to MB

            except Exception as e:
                logger.error({
                    "event": "memory_benchmark_error",
                    "iteration": i,
                    "error": str(e)
                })

        # Get final memory stats
        current_mb, peak_mb = tracemalloc.get_traced_memory()
        current_mb /= 1024 * 1024
        peak_mb /= 1024 * 1024

        tracemalloc.stop()

        # Memory metrics
        metrics.append(BenchmarkMetric(
            name="current_memory_mb",
            value=current_mb,
            unit="MB",
            threshold=self.MAX_MEMORY_MB,
            details=f"After {iterations} iterations"
        ))
        metrics[-1].check_pass()

        metrics.append(BenchmarkMetric(
            name="peak_memory_mb",
            value=peak_mb,
            unit="MB",
            threshold=self.MAX_PEAK_MEMORY_MB,
            details=f"Peak during {iterations} iterations"
        ))
        metrics[-1].check_pass()

        if memory_samples:
            metrics.append(BenchmarkMetric(
                name="avg_memory_mb",
                value=statistics.mean(memory_samples),
                unit="MB",
                details=f"Average across {len(memory_samples)} samples"
            ))

            metrics.append(BenchmarkMetric(
                name="memory_stability",
                value=statistics.stdev(memory_samples),
                unit="MB",
                details="Standard deviation of memory usage"
            ))

        duration = time.time() - start_time

        result = BenchmarkResult(
            benchmark_type=BenchmarkType.MEMORY,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metrics=metrics,
            duration_seconds=duration,
            sample_count=iterations
        )
        result.calculate_status()

        logger.info({
            "event": "memory_benchmark_complete",
            "current_mb": current_mb,
            "peak_mb": peak_mb,
            "duration_seconds": duration
        })

        return result


class ThroughputBenchmark:
    """
    Throughput benchmark for Agent Lightning.

    Measures requests per second under various loads.
    """

    TARGET_RPS = 100
    TARGET_CONCURRENT_RPS = 50

    def __init__(self, sample_queries: Optional[List[str]] = None):
        """
        Initialize throughput benchmark.

        Args:
            sample_queries: Optional queries for benchmarking
        """
        self.sample_queries = sample_queries or self._get_default_queries()

    def _get_default_queries(self) -> List[str]:
        """Get default queries for throughput benchmarking."""
        return [
            "What are your hours?",
            "I need help",
            "Where is my order?",
            "Refund please",
            "Manager!",
        ]

    async def run(
        self,
        predict_fn: Callable[[str], Tuple[str, float]],
        duration_seconds: int = 10,
        concurrent_users: int = 10
    ) -> BenchmarkResult:
        """
        Run throughput benchmark.

        Args:
            predict_fn: Function that takes query and returns prediction
            duration_seconds: Duration of benchmark in seconds
            concurrent_users: Number of concurrent users

        Returns:
            BenchmarkResult with throughput metrics
        """
        start_time = time.time()
        metrics: List[BenchmarkMetric] = []

        request_count = 0
        errors = 0
        latencies: List[float] = []

        async def worker(worker_id: int) -> Tuple[int, int, List[float]]:
            """Worker that sends requests for duration."""
            local_count = 0
            local_errors = 0
            local_latencies: List[float] = []

            end_time = time.time() + duration_seconds

            while time.time() < end_time:
                query = self.sample_queries[local_count % len(self.sample_queries)]

                try:
                    req_start = time.perf_counter()
                    await predict_fn(query)
                    req_end = time.perf_counter()

                    local_latencies.append((req_end - req_start) * 1000)
                    local_count += 1

                except Exception:
                    local_errors += 1

            return local_count, local_errors, local_latencies

        # Run concurrent workers
        tasks = [worker(i) for i in range(concurrent_users)]
        results = await asyncio.gather(*tasks)

        # Aggregate results
        for count, err, lats in results:
            request_count += count
            errors += err
            latencies.extend(lats)

        # Calculate RPS
        actual_duration = time.time() - start_time
        rps = request_count / actual_duration if actual_duration > 0 else 0

        metrics.append(BenchmarkMetric(
            name="requests_per_second",
            value=rps,
            unit="rps",
            threshold=self.TARGET_RPS,
            details=f"{request_count} requests in {actual_duration:.2f}s"
        ))
        metrics[-1].check_pass()

        metrics.append(BenchmarkMetric(
            name="concurrent_users",
            value=concurrent_users,
            unit="users"
        ))

        metrics.append(BenchmarkMetric(
            name="total_requests",
            value=request_count,
            unit="requests"
        ))

        metrics.append(BenchmarkMetric(
            name="error_count",
            value=errors,
            unit="errors"
        ))

        if latencies:
            metrics.append(BenchmarkMetric(
                name="avg_latency_under_load",
                value=statistics.mean(latencies),
                unit="ms",
                details=f"Under {concurrent_users} concurrent users"
            ))

        # Throughput per user
        rps_per_user = rps / concurrent_users if concurrent_users > 0 else 0
        metrics.append(BenchmarkMetric(
            name="rps_per_user",
            value=rps_per_user,
            unit="rps/user"
        ))

        result = BenchmarkResult(
            benchmark_type=BenchmarkType.THROUGHPUT,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metrics=metrics,
            duration_seconds=actual_duration,
            sample_count=request_count
        )
        result.calculate_status()

        logger.info({
            "event": "throughput_benchmark_complete",
            "rps": rps,
            "concurrent_users": concurrent_users,
            "total_requests": request_count,
            "duration_seconds": actual_duration
        })

        return result


class PerformanceBenchmark:
    """
    Main performance benchmark orchestrator.

    Runs all benchmark types and generates comparison reports.
    """

    def __init__(self, output_dir: Optional[Path] = None):
        """
        Initialize performance benchmark.

        Args:
            output_dir: Directory to save benchmark reports
        """
        self.output_dir = output_dir or Path("reports/benchmarks")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.accuracy_benchmark = AccuracyBenchmark()
        self.speed_benchmark = SpeedBenchmark()
        self.memory_benchmark = MemoryBenchmark()
        self.throughput_benchmark = ThroughputBenchmark()

        self._results: List[BenchmarkResult] = []

    async def run_all(
        self,
        predict_fn: Callable[[str], Tuple[str, float]],
        config: Optional[Dict[str, Any]] = None
    ) -> ComparisonReport:
        """
        Run all benchmarks.

        Args:
            predict_fn: Prediction function to benchmark
            config: Optional configuration for benchmarks

        Returns:
            ComparisonReport with all results
        """
        config = config or {}
        self._results = []

        logger.info({
            "event": "performance_benchmark_start",
            "config": config
        })

        # Run accuracy benchmark
        logger.info("Running accuracy benchmark...")
        accuracy_result = await self.accuracy_benchmark.run(predict_fn)
        self._results.append(accuracy_result)

        # Run speed benchmark
        logger.info("Running speed benchmark...")
        speed_result = await self.speed_benchmark.run(
            predict_fn,
            iterations=config.get("speed_iterations", 10)
        )
        self._results.append(speed_result)

        # Run memory benchmark
        logger.info("Running memory benchmark...")
        memory_result = await self.memory_benchmark.run(
            predict_fn,
            iterations=config.get("memory_iterations", 100)
        )
        self._results.append(memory_result)

        # Run throughput benchmark
        logger.info("Running throughput benchmark...")
        throughput_result = await self.throughput_benchmark.run(
            predict_fn,
            duration_seconds=config.get("throughput_duration", 10),
            concurrent_users=config.get("concurrent_users", 10)
        )
        self._results.append(throughput_result)

        # Generate report
        report = self._generate_report()

        # Save report
        await self._save_report(report)

        logger.info({
            "event": "performance_benchmark_complete",
            "overall_status": report.overall_status.value
        })

        return report

    def _generate_report(self) -> ComparisonReport:
        """Generate comparison report from all results."""
        # Calculate overall status
        statuses = [r.status for r in self._results]
        if all(s == BenchmarkStatus.PASSED for s in statuses):
            overall_status = BenchmarkStatus.PASSED
        elif any(s == BenchmarkStatus.FAILED for s in statuses):
            overall_status = BenchmarkStatus.FAILED
        else:
            overall_status = BenchmarkStatus.WARNING

        # Build summary
        summary = {
            "total_benchmarks": len(self._results),
            "passed": sum(1 for r in self._results if r.status == BenchmarkStatus.PASSED),
            "warnings": sum(1 for r in self._results if r.status == BenchmarkStatus.WARNING),
            "failed": sum(1 for r in self._results if r.status == BenchmarkStatus.FAILED),
        }

        # Add key metrics to summary
        for result in self._results:
            for metric in result.metrics:
                if metric.name in ["overall_accuracy", "p95_latency", "peak_memory_mb", "requests_per_second"]:
                    summary[metric.name] = metric.value

        # Generate recommendations
        recommendations = self._generate_recommendations()

        report_id = f"benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        return ComparisonReport(
            report_id=report_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            results=self._results,
            overall_status=overall_status,
            summary=summary,
            recommendations=recommendations
        )

    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on benchmark results."""
        recommendations = []

        for result in self._results:
            failed_metrics = [m for m in result.metrics if not m.passed]

            if result.benchmark_type == BenchmarkType.ACCURACY:
                if result.status != BenchmarkStatus.PASSED:
                    recommendations.append(
                        "Accuracy below 94% target - consider additional training data"
                    )

            elif result.benchmark_type == BenchmarkType.SPEED:
                if any(m.name == "p95_latency" and not m.passed for m in result.metrics):
                    recommendations.append(
                        "P95 latency exceeds 200ms - consider model optimization"
                    )

            elif result.benchmark_type == BenchmarkType.MEMORY:
                if any(m.name == "peak_memory_mb" and not m.passed for m in result.metrics):
                    recommendations.append(
                        "Memory usage high - consider batching or caching optimization"
                    )

            elif result.benchmark_type == BenchmarkType.THROUGHPUT:
                if any(m.name == "requests_per_second" and not m.passed for m in result.metrics):
                    recommendations.append(
                        "Throughput below target - consider scaling or load balancing"
                    )

        if not recommendations:
            recommendations.append("All benchmarks passed - system performing well")

        return recommendations

    async def _save_report(self, report: ComparisonReport) -> None:
        """Save report to file."""
        report_path = self.output_dir / f"{report.report_id}.json"

        with open(report_path, 'w') as f:
            json.dump(report.to_dict(), f, indent=2)

        logger.info({
            "event": "benchmark_report_saved",
            "path": str(report_path)
        })

    def get_results(self) -> List[BenchmarkResult]:
        """Get all benchmark results."""
        return self._results


def generate_benchmark_report(report: ComparisonReport) -> str:
    """Generate human-readable benchmark report."""
    lines = [
        "=" * 70,
        "AGENT LIGHTNING 94% PERFORMANCE BENCHMARK REPORT",
        "=" * 70,
        f"Report ID: {report.report_id}",
        f"Timestamp: {report.timestamp}",
        f"Overall Status: {report.overall_status.value.upper()}",
        "",
        "SUMMARY",
        "-" * 40,
        f"Total Benchmarks: {report.summary['total_benchmarks']}",
        f"Passed: {report.summary['passed']}",
        f"Warnings: {report.summary['warnings']}",
        f"Failed: {report.summary['failed']}",
        "",
    ]

    for result in report.results:
        status_icon = "✓" if result.status == BenchmarkStatus.PASSED else "!" if result.status == BenchmarkStatus.WARNING else "✗"
        lines.extend([
            f"{status_icon} {result.benchmark_type.value.upper()} BENCHMARK",
            f"  Duration: {result.duration_seconds:.2f}s",
            f"  Samples: {result.sample_count}",
            ""
        ])

        for metric in result.metrics:
            passed_icon = "✓" if metric.passed else "✗"
            lines.append(f"    {passed_icon} {metric.name}: {metric.value:.4f} {metric.unit}")
            if metric.details:
                lines.append(f"       {metric.details}")
        lines.append("")

    lines.extend([
        "RECOMMENDATIONS",
        "-" * 40,
    ])

    for rec in report.recommendations:
        lines.append(f"  • {rec}")

    lines.extend([
        "",
        "=" * 70,
    ])

    return "\n".join(lines)


async def run_benchmark(predict_fn: Callable[[str], Tuple[str, float]]) -> ComparisonReport:
    """
    Quick function to run all benchmarks.

    Args:
        predict_fn: Prediction function to benchmark

    Returns:
        ComparisonReport with all results
    """
    benchmark = PerformanceBenchmark()
    return await benchmark.run_all(predict_fn)


if __name__ == "__main__":
    # Example usage with mock prediction function
    async def mock_predict(query: str) -> Tuple[str, float]:
        """Mock prediction function for testing."""
        await asyncio.sleep(0.05)  # Simulate processing

        query_lower = query.lower()

        if "refund" in query_lower:
            return "refund", 0.95
        elif "manager" in query_lower:
            return "escalation", 0.90
        elif "order" in query_lower:
            return "shipping", 0.92
        else:
            return "faq", 0.88

    report = asyncio.run(run_benchmark(mock_predict))
    print(generate_benchmark_report(report))
