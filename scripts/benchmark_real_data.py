#!/usr/bin/env python3
"""
Benchmark Script for Real Client Data
Runs performance benchmarks against real client data patterns.
"""
import os
import sys
import time
import json
import argparse
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
import statistics
import concurrent.futures
import threading

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.app.core.config import settings


@dataclass
class BenchmarkMetric:
    """Single benchmark measurement."""
    name: str
    value: float
    unit: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkResult:
    """Aggregated benchmark result."""
    benchmark_name: str
    iterations: int
    metrics: List[BenchmarkMetric]
    passed: bool
    threshold: Optional[float] = None
    threshold_type: Optional[str] = None  # "max", "min"
    started_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    completed_at: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "benchmark_name": self.benchmark_name,
            "iterations": self.iterations,
            "passed": self.passed,
            "threshold": self.threshold,
            "threshold_type": self.threshold_type,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "metrics": [asdict(m) for m in self.metrics],
            "summary": self._calculate_summary()
        }
    
    def _calculate_summary(self) -> Dict:
        if not self.metrics:
            return {}
        
        values = [m.value for m in self.metrics]
        return {
            "min": round(min(values), 3),
            "max": round(max(values), 3),
            "mean": round(statistics.mean(values), 3),
            "median": round(statistics.median(values), 3),
            "stdev": round(statistics.stdev(values), 3) if len(values) > 1 else 0,
            "p95": round(sorted(values)[int(len(values) * 0.95)], 3) if values else 0,
            "p99": round(sorted(values)[int(len(values) * 0.99)], 3) if values else 0,
        }


class RealDataBenchmark:
    """Benchmarks using real client data patterns."""
    
    def __init__(self, client_id: str, iterations: int = 100):
        self.client_id = client_id
        self.iterations = iterations
        self.results: List[BenchmarkResult] = []
        self.baselines: Dict[str, float] = {}
    
    def load_baselines(self, baseline_file: Optional[str] = None) -> Dict:
        """Load performance baselines."""
        default_baselines = {
            "api_response_p95_ms": 500,
            "api_response_p99_ms": 1000,
            "db_query_avg_ms": 50,
            "db_query_p95_ms": 100,
            "cache_hit_rate": 0.8,
            "throughput_min_rps": 100,
            "error_rate_max": 0.01,
        }
        
        if baseline_file and os.path.exists(baseline_file):
            with open(baseline_file, "r") as f:
                loaded = json.load(f)
                default_baselines.update(loaded)
        
        self.baselines = default_baselines
        return self.baselines
    
    # ==================== API Benchmarks ====================
    
    def benchmark_ticket_list_api(self) -> BenchmarkResult:
        """Benchmark: Ticket list API response time."""
        print("  📋 Benchmarking ticket list API...")
        
        from backend.app.services.ticket_service import TicketService
        
        service = TicketService()
        metrics = []
        
        for i in range(self.iterations):
            start = time.perf_counter()
            try:
                service.get_tickets(client_id=self.client_id, page=1, limit=20)
                duration_ms = (time.perf_counter() - start) * 1000
                metrics.append(BenchmarkMetric(
                    name="response_time",
                    value=duration_ms,
                    unit="ms",
                    metadata={"iteration": i}
                ))
            except Exception as e:
                metrics.append(BenchmarkMetric(
                    name="response_time",
                    value=-1,
                    unit="ms",
                    metadata={"iteration": i, "error": str(e)}
                ))
        
        result = BenchmarkResult(
            benchmark_name="ticket_list_api",
            iterations=self.iterations,
            metrics=metrics,
            passed=self._check_threshold(metrics, "max", self.baselines.get("api_response_p95_ms", 500)),
            threshold=self.baselines.get("api_response_p95_ms", 500),
            threshold_type="max"
        )
        result.completed_at = datetime.utcnow().isoformat()
        
        self.results.append(result)
        return result
    
    def benchmark_ticket_detail_api(self) -> BenchmarkResult:
        """Benchmark: Ticket detail API response time."""
        print("  📄 Benchmarking ticket detail API...")
        
        from backend.app.services.ticket_service import TicketService
        
        service = TicketService()
        metrics = []
        
        # Use sample ticket IDs
        sample_ids = [f"ticket_{i:04d}" for i in range(self.iterations)]
        
        for i, ticket_id in enumerate(sample_ids):
            start = time.perf_counter()
            try:
                service.get_ticket(ticket_id=ticket_id, client_id=self.client_id)
                duration_ms = (time.perf_counter() - start) * 1000
                metrics.append(BenchmarkMetric(
                    name="response_time",
                    value=duration_ms,
                    unit="ms",
                    metadata={"ticket_id": ticket_id}
                ))
            except Exception:
                duration_ms = (time.perf_counter() - start) * 1000
                metrics.append(BenchmarkMetric(
                    name="response_time",
                    value=duration_ms,
                    unit="ms",
                    metadata={"ticket_id": ticket_id, "found": False}
                ))
        
        result = BenchmarkResult(
            benchmark_name="ticket_detail_api",
            iterations=self.iterations,
            metrics=metrics,
            passed=self._check_threshold(metrics, "max", 300),
            threshold=300,
            threshold_type="max"
        )
        result.completed_at = datetime.utcnow().isoformat()
        
        self.results.append(result)
        return result
    
    def benchmark_approvals_api(self) -> BenchmarkResult:
        """Benchmark: Approvals API response time."""
        print("  ✅ Benchmarking approvals API...")
        
        from backend.app.services.approval_service import ApprovalService
        
        service = ApprovalService()
        metrics = []
        
        for i in range(self.iterations):
            start = time.perf_counter()
            try:
                service.get_approvals(client_id=self.client_id, status="pending")
                duration_ms = (time.perf_counter() - start) * 1000
                metrics.append(BenchmarkMetric(
                    name="response_time",
                    value=duration_ms,
                    unit="ms"
                ))
            except Exception as e:
                metrics.append(BenchmarkMetric(
                    name="response_time",
                    value=-1,
                    unit="ms",
                    metadata={"error": str(e)}
                ))
        
        result = BenchmarkResult(
            benchmark_name="approvals_api",
            iterations=self.iterations,
            metrics=metrics,
            passed=self._check_threshold(metrics, "max", 400),
            threshold=400,
            threshold_type="max"
        )
        result.completed_at = datetime.utcnow().isoformat()
        
        self.results.append(result)
        return result
    
    def benchmark_jarvis_command(self) -> BenchmarkResult:
        """Benchmark: Jarvis command processing time."""
        print("  🤖 Benchmarking Jarvis commands...")
        
        from backend.app.services.jarvis_service import JarvisService
        
        service = JarvisService()
        metrics = []
        
        commands = [
            "What's the status of my orders?",
            "How many tickets are pending?",
            "Show me today's analytics",
            "What's the CSAT score?",
            "List recent escalations"
        ]
        
        for i in range(self.iterations):
            command = commands[i % len(commands)]
            start = time.perf_counter()
            try:
                service.send_command(client_id=self.client_id, command=command)
                duration_ms = (time.perf_counter() - start) * 1000
                metrics.append(BenchmarkMetric(
                    name="response_time",
                    value=duration_ms,
                    unit="ms",
                    metadata={"command": command}
                ))
            except Exception as e:
                metrics.append(BenchmarkMetric(
                    name="response_time",
                    value=-1,
                    unit="ms",
                    metadata={"command": command, "error": str(e)}
                ))
        
        result = BenchmarkResult(
            benchmark_name="jarvis_command",
            iterations=self.iterations,
            metrics=metrics,
            passed=self._check_threshold(metrics, "max", 1000),
            threshold=1000,
            threshold_type="max"
        )
        result.completed_at = datetime.utcnow().isoformat()
        
        self.results.append(result)
        return result
    
    # ==================== Database Benchmarks ====================
    
    def benchmark_database_queries(self) -> BenchmarkResult:
        """Benchmark: Database query performance."""
        print("  🗄️ Benchmarking database queries...")
        
        from backend.app.core.database import get_db
        
        db = next(get_db())
        metrics = []
        
        queries = [
            ("SELECT * FROM tickets WHERE client_id = %s LIMIT 20", (self.client_id,)),
            ("SELECT COUNT(*) FROM tickets WHERE client_id = %s", (self.client_id,)),
            ("SELECT * FROM approvals WHERE client_id = %s AND status = 'pending'", (self.client_id,)),
        ]
        
        for i in range(self.iterations):
            query, params = queries[i % len(queries)]
            start = time.perf_counter()
            try:
                db.execute(query, params)
                duration_ms = (time.perf_counter() - start) * 1000
                metrics.append(BenchmarkMetric(
                    name="query_time",
                    value=duration_ms,
                    unit="ms",
                    metadata={"query_type": "select"}
                ))
            except Exception:
                metrics.append(BenchmarkMetric(
                    name="query_time",
                    value=-1,
                    unit="ms"
                ))
        
        result = BenchmarkResult(
            benchmark_name="database_queries",
            iterations=self.iterations,
            metrics=metrics,
            passed=self._check_threshold(metrics, "max", self.baselines.get("db_query_p95_ms", 100)),
            threshold=self.baselines.get("db_query_p95_ms", 100),
            threshold_type="max"
        )
        result.completed_at = datetime.utcnow().isoformat()
        
        self.results.append(result)
        return result
    
    # ==================== Cache Benchmarks ====================
    
    def benchmark_cache_performance(self) -> BenchmarkResult:
        """Benchmark: Redis cache performance."""
        print("  💾 Benchmarking cache...")
        
        try:
            import redis
            r = redis.from_url(settings.REDIS_URL)
        except Exception:
            print("  ⚠️ Redis not available, skipping")
            return BenchmarkResult(
                benchmark_name="cache_performance",
                iterations=0,
                metrics=[],
                passed=True
            )
        
        metrics = []
        test_key = f"benchmark:{self.client_id}:test"
        
        for i in range(self.iterations):
            # SET operation
            start = time.perf_counter()
            r.set(test_key, f"value_{i}", ex=60)
            set_time = (time.perf_counter() - start) * 1000
            
            # GET operation
            start = time.perf_counter()
            r.get(test_key)
            get_time = (time.perf_counter() - start) * 1000
            
            metrics.append(BenchmarkMetric(
                name="set_time",
                value=set_time,
                unit="ms"
            ))
            metrics.append(BenchmarkMetric(
                name="get_time",
                value=get_time,
                unit="ms"
            ))
        
        result = BenchmarkResult(
            benchmark_name="cache_performance",
            iterations=self.iterations * 2,
            metrics=metrics,
            passed=self._check_threshold(metrics, "max", 10),
            threshold=10,
            threshold_type="max"
        )
        result.completed_at = datetime.utcnow().isoformat()
        
        self.results.append(result)
        return result
    
    # ==================== Load Benchmarks ====================
    
    def benchmark_concurrent_load(self, concurrent_users: int = 10) -> BenchmarkResult:
        """Benchmark: Concurrent user load."""
        print(f"  👥 Benchmarking {concurrent_users} concurrent users...")
        
        from backend.app.services.ticket_service import TicketService
        
        metrics = []
        lock = threading.Lock()
        
        def user_session(user_id: int):
            service = TicketService()
            for i in range(10):
                start = time.perf_counter()
                try:
                    service.get_tickets(client_id=self.client_id, page=1, limit=20)
                    duration_ms = (time.perf_counter() - start) * 1000
                    with lock:
                        metrics.append(BenchmarkMetric(
                            name="response_time",
                            value=duration_ms,
                            unit="ms",
                            metadata={"user_id": user_id, "request": i}
                        ))
                except Exception:
                    pass
        
        start_time = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_users) as executor:
            futures = [executor.submit(user_session, i) for i in range(concurrent_users)]
            concurrent.futures.wait(futures)
        
        total_time = time.time() - start_time
        throughput = len(metrics) / total_time if total_time > 0 else 0
        
        # Add throughput metric
        metrics.append(BenchmarkMetric(
            name="throughput",
            value=throughput,
            unit="rps",
            metadata={"concurrent_users": concurrent_users}
        ))
        
        result = BenchmarkResult(
            benchmark_name=f"concurrent_load_{concurrent_users}users",
            iterations=len(metrics),
            metrics=metrics,
            passed=self._check_threshold(metrics[:concurrent_users * 10], "max", 500) and throughput >= 50,
            threshold=500,
            threshold_type="max"
        )
        result.completed_at = datetime.utcnow().isoformat()
        
        self.results.append(result)
        return result
    
    # ==================== Helper Methods ====================
    
    def _check_threshold(self, metrics: List[BenchmarkMetric], threshold_type: str, threshold: float) -> bool:
        """Check if metrics meet threshold."""
        values = [m.value for m in metrics if m.value > 0]  # Exclude errors
        if not values:
            return False
        
        if threshold_type == "max":
            p95 = sorted(values)[int(len(values) * 0.95)]
            return p95 < threshold
        elif threshold_type == "min":
            return min(values) >= threshold
        
        return True
    
    def run_all_benchmarks(self) -> Dict:
        """Run all benchmarks."""
        print(f"\n🚀 Running benchmarks for client: {self.client_id}")
        print(f"   Iterations per benchmark: {self.iterations}")
        print("-" * 50)
        
        # Load baselines
        self.load_baselines()
        
        # Run API benchmarks
        self.benchmark_ticket_list_api()
        self.benchmark_ticket_detail_api()
        self.benchmark_approvals_api()
        self.benchmark_jarvis_command()
        
        # Run infrastructure benchmarks
        self.benchmark_database_queries()
        self.benchmark_cache_performance()
        
        # Run load benchmarks
        self.benchmark_concurrent_load(10)
        self.benchmark_concurrent_load(50)
        
        # Generate report
        return self.generate_report()
    
    def generate_report(self) -> Dict:
        """Generate benchmark report."""
        all_passed = all(r.passed for r in self.results)
        
        report = {
            "client_id": self.client_id,
            "timestamp": datetime.utcnow().isoformat(),
            "all_passed": all_passed,
            "summary": {
                "total_benchmarks": len(self.results),
                "passed": len([r for r in self.results if r.passed]),
                "failed": len([r for r in self.results if not r.passed]),
            },
            "benchmarks": [r.to_dict() for r in self.results],
            "baselines": self.baselines,
            "recommendations": self._generate_recommendations()
        }
        
        return report
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on results."""
        recommendations = []
        
        for result in self.results:
            if not result.passed:
                summary = result.to_dict().get("summary", {})
                p95 = summary.get("p95", 0)
                
                if result.benchmark_name.startswith("concurrent"):
                    recommendations.append(
                        f"Optimize {result.benchmark_name}: P95 {p95}ms exceeds 500ms. "
                        "Consider connection pooling or query optimization."
                    )
                elif "api" in result.benchmark_name:
                    recommendations.append(
                        f"API {result.benchmark_name} slow: P95 {p95}ms. "
                        "Check database indexes and caching."
                    )
                elif "database" in result.benchmark_name:
                    recommendations.append(
                        f"Database queries slow: P95 {p95}ms. "
                        "Review query plans and add indexes."
                    )
        
        return recommendations


def main():
    parser = argparse.ArgumentParser(description="PARWA Real Data Benchmarks")
    parser.add_argument("--client", "-c", required=True, help="Client ID")
    parser.add_argument("--iterations", "-i", type=int, default=100, help="Iterations per benchmark")
    parser.add_argument("--output", "-o", help="Output file for results")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--baseline-file", "-b", help="Baseline file to compare against")
    
    args = parser.parse_args()
    
    benchmark = RealDataBenchmark(
        client_id=args.client,
        iterations=args.iterations
    )
    
    if args.baseline_file:
        benchmark.load_baselines(args.baseline_file)
    
    report = benchmark.run_all_benchmarks()
    
    print("\n" + "=" * 50)
    print("Benchmark Summary")
    print("=" * 50)
    print(f"Total benchmarks: {report['summary']['total_benchmarks']}")
    print(f"✅ Passed: {report['summary']['passed']}")
    print(f"❌ Failed: {report['summary']['failed']}")
    print(f"\nOverall: {'✅ ALL PASSED' if report['all_passed'] else '❌ SOME FAILED'}")
    
    if report['recommendations']:
        print("\nRecommendations:")
        for i, rec in enumerate(report['recommendations'], 1):
            print(f"  {i}. {rec}")
    
    if args.output:
        with open(args.output, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\n📄 Report saved to: {args.output}")
    
    if args.json:
        print(json.dumps(report, indent=2))
    
    return 0 if report['all_passed'] else 1


if __name__ == "__main__":
    sys.exit(main())
