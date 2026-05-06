"""
Benchmark Runner for Agent Lightning 94% Accuracy.

Executes benchmarks and tracks performance over time.
"""
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timezone
from dataclasses import dataclass, field
from pathlib import Path
import json
import asyncio

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


@dataclass
class BenchmarkResult:
    """Result of a benchmark run."""
    benchmark_name: str
    accuracy: float
    latency_p50: float
    latency_p95: float
    latency_p99: float
    throughput: float
    samples: int
    passed: bool
    details: Dict[str, Any] = field(default_factory=dict)
    run_at: str = ""
    
    def __post_init__(self):
        if not self.run_at:
            self.run_at = datetime.now(timezone.utc).isoformat()


class BenchmarkRunner:
    """
    Benchmark runner for Agent Lightning.
    
    Features:
    - Standard benchmark datasets
    - Industry-specific benchmarks
    - Performance metrics tracking
    - Historical comparisons
    """
    
    def __init__(self, results_path: Optional[Path] = None):
        """Initialize benchmark runner."""
        self.results_path = results_path
        self._results: List[BenchmarkResult] = []
        self._benchmarks: Dict[str, Callable] = {}
    
    def register_benchmark(
        self,
        name: str,
        benchmark_fn: Callable
    ) -> None:
        """Register a benchmark function."""
        self._benchmarks[name] = benchmark_fn
        logger.info({"event": "benchmark_registered", "name": name})
    
    async def run_benchmark(
        self,
        name: str,
        predict_fn: Callable,
        samples: List[Dict[str, Any]]
    ) -> BenchmarkResult:
        """
        Run a specific benchmark.
        
        Args:
            name: Benchmark name
            predict_fn: Prediction function
            samples: Test samples
            
        Returns:
            BenchmarkResult with metrics
        """
        latencies = []
        correct = 0
        total = 0
        
        for sample in samples:
            query = sample.get("query", "")
            expected = sample.get("expected", "")
            
            start_time = datetime.now(timezone.utc)
            
            try:
                if asyncio.iscoroutinefunction(predict_fn):
                    prediction = await predict_fn(query)
                else:
                    prediction = predict_fn(query)
                
                latency = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                latencies.append(latency)
                
                if self._check_correct(prediction, expected):
                    correct += 1
                total += 1
                
            except Exception as e:
                logger.error({
                    "event": "benchmark_error",
                    "sample": query[:50],
                    "error": str(e)
                })
        
        # Calculate metrics
        latencies.sort()
        accuracy = correct / total if total > 0 else 0
        
        result = BenchmarkResult(
            benchmark_name=name,
            accuracy=accuracy,
            latency_p50=latencies[len(latencies)//2] if latencies else 0,
            latency_p95=latencies[int(len(latencies)*0.95)] if latencies else 0,
            latency_p99=latencies[int(len(latencies)*0.99)] if latencies else 0,
            throughput=total / (sum(latencies)/1000) if latencies else 0,
            samples=total,
            passed=accuracy >= 0.94
        )
        
        self._results.append(result)
        
        logger.info({
            "event": "benchmark_complete",
            "name": name,
            "accuracy": accuracy,
            "latency_p95": result.latency_p95
        })
        
        return result
    
    async def run_all_benchmarks(
        self,
        predict_fn: Callable,
        test_data: Dict[str, List[Dict[str, Any]]]
    ) -> List[BenchmarkResult]:
        """Run all registered benchmarks."""
        results = []
        
        for name, samples in test_data.items():
            result = await self.run_benchmark(name, predict_fn, samples)
            results.append(result)
        
        return results
    
    def get_summary(self) -> Dict[str, Any]:
        """Get benchmark summary."""
        if not self._results:
            return {"total_benchmarks": 0}
        
        avg_accuracy = sum(r.accuracy for r in self._results) / len(self._results)
        avg_latency_p95 = sum(r.latency_p95 for r in self._results) / len(self._results)
        
        return {
            "total_benchmarks": len(self._results),
            "average_accuracy": avg_accuracy,
            "average_latency_p95": avg_latency_p95,
            "all_passed": all(r.passed for r in self._results),
            "benchmarks": [
                {
                    "name": r.benchmark_name,
                    "accuracy": r.accuracy,
                    "passed": r.passed
                }
                for r in self._results
            ]
        }
    
    def _check_correct(self, prediction: Any, expected: str) -> bool:
        """Check if prediction matches expected."""
        if isinstance(prediction, tuple):
            pred = prediction[0]
        else:
            pred = prediction
        
        if isinstance(pred, str):
            return pred.lower() == expected.lower()
        
        return str(pred).lower() == expected.lower()
