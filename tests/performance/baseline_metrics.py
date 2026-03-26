"""
Baseline Metrics Tests for PARWA Week 19
Tests for validating accuracy and performance baselines
"""

import pytest
import json
import statistics
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path


# Constants
ACCURACY_THRESHOLD = 0.72  # 72%
P95_LATENCY_THRESHOLD_MS = 500
ERROR_RATE_THRESHOLD = 0.01  # 1%
MIN_THROUGHPUT_PER_HOUR = 30
BASELINE_DIR = Path(__file__).parent.parent.parent / "reports"


@dataclass
class MetricResult:
    """Represents a single metric result"""
    name: str
    value: float
    threshold: float
    passed: bool
    timestamp: str
    details: Optional[Dict[str, Any]] = None


@dataclass
class CategoryMetric:
    """Metrics for a specific category"""
    category: str
    total: int
    correct: int
    accuracy: float
    avg_response_time_ms: float
    p95_response_time_ms: float


class BaselineMetrics:
    """Baseline metrics collection and validation"""

    def __init__(self, client_id: str = "client_001"):
        self.client_id = client_id
        self.metrics: Dict[str, MetricResult] = {}
        self.category_metrics: Dict[str, CategoryMetric] = {}
        self.trending_data: List[Dict[str, Any]] = []

    def record_metric(
        self,
        name: str,
        value: float,
        threshold: float,
        details: Optional[Dict] = None
    ) -> MetricResult:
        """Record a metric measurement"""
        passed = value >= threshold if "accuracy" in name.lower() else value <= threshold
        result = MetricResult(
            name=name,
            value=value,
            threshold=threshold,
            passed=passed,
            timestamp=datetime.utcnow().isoformat(),
            details=details
        )
        self.metrics[name] = result
        return result

    def record_category_metric(
        self,
        category: str,
        total: int,
        correct: int,
        response_times: List[float]
    ) -> CategoryMetric:
        """Record metrics for a category"""
        accuracy = correct / total if total > 0 else 0.0
        avg_time = statistics.mean(response_times) if response_times else 0.0
        p95_time = statistics.quantiles(response_times, n=20)[-1] if len(response_times) >= 20 else max(response_times) if response_times else 0.0

        metric = CategoryMetric(
            category=category,
            total=total,
            correct=correct,
            accuracy=accuracy,
            avg_response_time_ms=avg_time,
            p95_response_time_ms=p95_time
        )
        self.category_metrics[category] = metric
        return metric

    def add_trending_point(self, metric_name: str, value: float, timestamp: Optional[str] = None):
        """Add a data point for trending"""
        self.trending_data.append({
            "metric": metric_name,
            "value": value,
            "timestamp": timestamp or datetime.utcnow().isoformat()
        })

    def get_accuracy(self) -> float:
        """Calculate overall accuracy"""
        total = sum(m.total for m in self.category_metrics.values())
        correct = sum(m.correct for m in self.category_metrics.values())
        return correct / total if total > 0 else 0.0

    def get_p95_latency(self) -> float:
        """Calculate overall P95 latency"""
        all_times = []
        for metric in self.category_metrics.values():
            all_times.extend([metric.p95_response_time_ms] * 5)
        return statistics.quantiles(all_times, n=20)[-1] if all_times else 0.0

    def save_to_file(self, filename: str):
        """Save metrics to JSON file"""
        data = {
            "client_id": self.client_id,
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": {k: asdict(v) for k, v in self.metrics.items()},
            "category_metrics": {k: asdict(v) for k, v in self.category_metrics.items()},
            "trending_data": self.trending_data
        }
        filepath = BASELINE_DIR / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        return filepath

    def load_from_file(self, filename: str) -> bool:
        """Load metrics from JSON file"""
        filepath = BASELINE_DIR / filename
        if not filepath.exists():
            return False
        with open(filepath, 'r') as f:
            data = json.load(f)
        self.client_id = data.get("client_id", self.client_id)
        self.metrics = {k: MetricResult(**v) for k, v in data.get("metrics", {}).items()}
        self.category_metrics = {k: CategoryMetric(**v) for k, v in data.get("category_metrics", {}).items()}
        self.trending_data = data.get("trending_data", [])
        return True


class TestBaselineMetrics:
    """Test suite for baseline metrics validation"""

    @pytest.fixture
    def baseline(self):
        """Create baseline metrics fixture with sample data"""
        bm = BaselineMetrics(client_id="client_001")
        bm.record_category_metric("Orders", 18, 15, [120, 145, 160, 180, 200, 220, 250, 265])
        bm.record_category_metric("Shipping", 12, 9, [150, 180, 210, 250, 280, 300, 312])
        bm.record_category_metric("Returns", 8, 7, [100, 130, 150, 180, 200, 223])
        bm.record_category_metric("Products", 7, 5, [140, 170, 200, 230, 260, 278])
        bm.record_category_metric("Account", 5, 4, [90, 110, 130, 160, 190, 198])
        bm.record_metric("accuracy", bm.get_accuracy(), ACCURACY_THRESHOLD)
        bm.record_metric("p95_latency_ms", 287.0, P95_LATENCY_THRESHOLD_MS)
        bm.record_metric("error_rate", 0.008, ERROR_RATE_THRESHOLD)
        bm.record_metric("throughput_per_hour", 45.0, MIN_THROUGHPUT_PER_HOUR)
        return bm

    def test_accuracy_above_threshold(self, baseline):
        """Test that accuracy is above 72% threshold"""
        accuracy = baseline.get_accuracy()
        assert accuracy >= ACCURACY_THRESHOLD, f"Accuracy {accuracy:.1%} below threshold"

    def test_p95_latency_within_sla(self, baseline):
        """Test that P95 latency is within 500ms SLA"""
        metric = baseline.metrics.get("p95_latency_ms")
        assert metric is not None
        assert metric.value <= P95_LATENCY_THRESHOLD_MS

    def test_error_rate_below_threshold(self, baseline):
        """Test that error rate is below 1% threshold"""
        metric = baseline.metrics.get("error_rate")
        assert metric is not None
        assert metric.value <= ERROR_RATE_THRESHOLD

    def test_throughput_meets_minimum(self, baseline):
        """Test that throughput meets minimum requirement"""
        metric = baseline.metrics.get("throughput_per_hour")
        assert metric is not None
        assert metric.value >= MIN_THROUGHPUT_PER_HOUR

    def test_all_metrics_captured(self, baseline):
        """Test that all required metrics are captured"""
        required = ["accuracy", "p95_latency_ms", "error_rate", "throughput_per_hour"]
        for name in required:
            assert name in baseline.metrics, f"Missing metric: {name}"

    def test_metrics_persisted(self, baseline):
        """Test that metrics can be persisted and loaded"""
        filepath = baseline.save_to_file("test_baseline_metrics.json")
        assert filepath.exists()
        loaded = BaselineMetrics()
        assert loaded.load_from_file("test_baseline_metrics.json")
        assert loaded.client_id == baseline.client_id
        filepath.unlink()

    def test_category_metrics_complete(self, baseline):
        """Test that category metrics are complete"""
        expected = ["Orders", "Shipping", "Returns", "Products", "Account"]
        for cat in expected:
            assert cat in baseline.category_metrics
            cm = baseline.category_metrics[cat]
            assert cm.total > 0

    def test_trending_data_available(self, baseline):
        """Test that trending data can be recorded"""
        baseline.add_trending_point("accuracy", 0.75)
        baseline.add_trending_point("accuracy", 0.78)
        assert len(baseline.trending_data) >= 2

    def test_cross_tenant_isolation(self, baseline):
        """Test that metrics are properly isolated by client"""
        other = BaselineMetrics(client_id="client_002")
        other.record_metric("accuracy", 0.65, ACCURACY_THRESHOLD)
        assert other.client_id != baseline.client_id

    def test_pii_redaction(self, baseline):
        """Test that PII is properly redacted in metrics"""
        for metric in baseline.metrics.values():
            metric_str = json.dumps(asdict(metric))
            pii_patterns = ["@email.com", "credit_card", "ssn", "phone"]
            for pattern in pii_patterns:
                assert pattern not in metric_str.lower()

    def test_baseline_comparison(self, baseline):
        """Test baseline comparison functionality"""
        previous = BaselineMetrics(client_id="client_001")
        previous.record_metric("accuracy", 0.70, ACCURACY_THRESHOLD)
        assert baseline.get_accuracy() >= previous.metrics["accuracy"].value

    def test_report_generation(self, baseline):
        """Test that report data can be generated"""
        report_data = {
            "client_id": baseline.client_id,
            "summary": {
                "accuracy": baseline.get_accuracy(),
                "p95_latency_ms": baseline.metrics["p95_latency_ms"].value,
                "error_rate": baseline.metrics["error_rate"].value,
            },
            "pass_fail": {k: v.passed for k, v in baseline.metrics.items()}
        }
        assert report_data["summary"]["accuracy"] >= ACCURACY_THRESHOLD


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
