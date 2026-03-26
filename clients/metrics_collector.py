"""
Metrics Collector for PARWA
Collects accuracy, performance, and satisfaction metrics
"""

import json
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, asdict, field
from collections import defaultdict
import statistics


# Constants
REPORTS_DIR = Path(__file__).parent.parent / "reports"
METRICS_EXPORT_INTERVAL = 300  # 5 minutes


@dataclass
class AccuracyMetric:
    """Single accuracy measurement"""
    timestamp: str
    ticket_id: str
    category: str
    predicted_correct: bool
    confidence: float
    human_feedback: Optional[str] = None
    resolution_type: str = "auto"  # auto, escalated, human


@dataclass
class PerformanceMetric:
    """Single performance measurement"""
    timestamp: str
    operation: str
    duration_ms: float
    success: bool
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SatisfactionMetric:
    """Customer satisfaction measurement"""
    timestamp: str
    ticket_id: str
    csat_score: Optional[int] = None  # 1-5
    feedback_text: Optional[str] = None
    resolved: bool = False
    response_helpful: Optional[bool] = None


class MetricsCollector:
    """Collects and stores metrics for PARWA"""

    def __init__(self, client_id: str):
        self.client_id = client_id
        self._lock = threading.Lock()

        # Storage
        self._accuracy_metrics: List[AccuracyMetric] = []
        self._performance_metrics: List[PerformanceMetric] = []
        self._satisfaction_metrics: List[SatisfactionMetric] = []

        # Aggregations
        self._category_stats: Dict[str, Dict] = defaultdict(lambda: {
            "total": 0, "correct": 0, "response_times": []
        })

        # Callbacks
        self._alert_callbacks: List[Callable] = []

        # Export thread
        self._export_thread: Optional[threading.Thread] = None
        self._running = False

    # ==================== Accuracy Metrics ====================

    def record_accuracy(
        self,
        ticket_id: str,
        category: str,
        predicted_correct: bool,
        confidence: float,
        human_feedback: Optional[str] = None,
        resolution_type: str = "auto"
    ) -> AccuracyMetric:
        """Record an accuracy measurement"""
        metric = AccuracyMetric(
            timestamp=datetime.utcnow().isoformat(),
            ticket_id=ticket_id,
            category=category,
            predicted_correct=predicted_correct,
            confidence=confidence,
            human_feedback=human_feedback,
            resolution_type=resolution_type
        )

        with self._lock:
            self._accuracy_metrics.append(metric)

            # Update category stats
            stats = self._category_stats[category]
            stats["total"] += 1
            if predicted_correct:
                stats["correct"] += 1

        return metric

    def get_accuracy(self, category: Optional[str] = None) -> float:
        """Get accuracy rate (optionally filtered by category)"""
        with self._lock:
            if category:
                stats = self._category_stats.get(category, {})
                total = stats.get("total", 0)
                correct = stats.get("correct", 0)
            else:
                total = sum(s["total"] for s in self._category_stats.values())
                correct = sum(s["correct"] for s in self._category_stats.values())

        return correct / total if total > 0 else 0.0

    def get_accuracy_by_category(self) -> Dict[str, float]:
        """Get accuracy breakdown by category"""
        result = {}
        with self._lock:
            for category, stats in self._category_stats.items():
                total = stats["total"]
                correct = stats["correct"]
                result[category] = correct / total if total > 0 else 0.0
        return result

    # ==================== Performance Metrics ====================

    def record_performance(
        self,
        operation: str,
        duration_ms: float,
        success: bool = True,
        error_message: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> PerformanceMetric:
        """Record a performance measurement"""
        metric = PerformanceMetric(
            timestamp=datetime.utcnow().isoformat(),
            operation=operation,
            duration_ms=duration_ms,
            success=success,
            error_message=error_message,
            metadata=metadata or {}
        )

        with self._lock:
            self._performance_metrics.append(metric)

            # Update category response times
            if "category" in (metadata or {}):
                cat = metadata["category"]
                self._category_stats[cat]["response_times"].append(duration_ms)

        # Check for alerts
        if not success or duration_ms > 500:  # Alert threshold
            self._check_alerts(metric)

        return metric

    def get_latency_percentiles(self, operation: Optional[str] = None) -> Dict[str, float]:
        """Get latency percentiles"""
        with self._lock:
            times = [
                m.duration_ms for m in self._performance_metrics
                if operation is None or m.operation == operation
            ]

        if not times:
            return {"p50": 0, "p95": 0, "p99": 0}

        return {
            "p50": statistics.quantiles(times, n=2)[0] if len(times) >= 2 else times[0],
            "p95": statistics.quantiles(times, n=20)[-1] if len(times) >= 20 else max(times),
            "p99": statistics.quantiles(times, n=100)[-1] if len(times) >= 100 else max(times)
        }

    def get_error_rate(self) -> float:
        """Get error rate"""
        with self._lock:
            total = len(self._performance_metrics)
            errors = sum(1 for m in self._performance_metrics if not m.success)

        return errors / total if total > 0 else 0.0

    def get_throughput(self, hours: float = 1.0) -> float:
        """Get throughput (operations per hour)"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        cutoff_str = cutoff.isoformat()

        with self._lock:
            count = sum(
                1 for m in self._performance_metrics
                if m.timestamp >= cutoff_str
            )

        return count / hours

    # ==================== Satisfaction Metrics ====================

    def record_satisfaction(
        self,
        ticket_id: str,
        csat_score: Optional[int] = None,
        feedback_text: Optional[str] = None,
        resolved: bool = False,
        response_helpful: Optional[bool] = None
    ) -> SatisfactionMetric:
        """Record a satisfaction measurement"""
        metric = SatisfactionMetric(
            timestamp=datetime.utcnow().isoformat(),
            ticket_id=ticket_id,
            csat_score=csat_score,
            feedback_text=feedback_text,
            resolved=resolved,
            response_helpful=response_helpful
        )

        with self._lock:
            self._satisfaction_metrics.append(metric)

        return metric

    def get_csat(self) -> Optional[float]:
        """Get average CSAT score"""
        with self._lock:
            scores = [m.csat_score for m in self._satisfaction_metrics if m.csat_score]

        return statistics.mean(scores) if scores else None

    def get_resolution_rate(self) -> float:
        """Get resolution rate"""
        with self._lock:
            total = len(self._satisfaction_metrics)
            resolved = sum(1 for m in self._satisfaction_metrics if m.resolved)

        return resolved / total if total > 0 else 0.0

    # ==================== Trending ====================

    def get_trending_data(self, metric_type: str, hours: int = 24) -> List[Dict]:
        """Get trending data for a metric type"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        cutoff_str = cutoff.isoformat()

        result = []

        with self._lock:
            if metric_type == "accuracy":
                for m in self._accuracy_metrics:
                    if m.timestamp >= cutoff_str:
                        result.append({
                            "timestamp": m.timestamp,
                            "value": 1 if m.predicted_correct else 0,
                            "category": m.category
                        })
            elif metric_type == "latency":
                for m in self._performance_metrics:
                    if m.timestamp >= cutoff_str:
                        result.append({
                            "timestamp": m.timestamp,
                            "value": m.duration_ms,
                            "operation": m.operation
                        })

        return result

    # ==================== Export ====================

    def export_accuracy_baseline(self) -> Path:
        """Export accuracy baseline to JSON"""
        data = {
            "client_id": self.client_id,
            "timestamp": datetime.utcnow().isoformat(),
            "overall_accuracy": self.get_accuracy(),
            "accuracy_by_category": self.get_accuracy_by_category(),
            "total_tickets": sum(s["total"] for s in self._category_stats.values()),
            "common_mistakes": self._get_common_mistakes(),
            "resolution_breakdown": self._get_resolution_breakdown()
        }

        filepath = REPORTS_DIR / "baseline_accuracy.json"
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

        return filepath

    def export_performance_baseline(self) -> Path:
        """Export performance baseline to JSON"""
        latencies = self.get_latency_percentiles()

        data = {
            "client_id": self.client_id,
            "timestamp": datetime.utcnow().isoformat(),
            "p50_latency_ms": latencies["p50"],
            "p95_latency_ms": latencies["p95"],
            "p99_latency_ms": latencies["p99"],
            "throughput_per_hour": self.get_throughput(),
            "error_rate": self.get_error_rate(),
            "operations_count": len(self._performance_metrics)
        }

        filepath = REPORTS_DIR / "baseline_performance.json"
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

        return filepath

    def _get_common_mistakes(self) -> List[Dict]:
        """Identify common mistake patterns"""
        mistakes = defaultdict(int)

        with self._lock:
            for m in self._accuracy_metrics:
                if not m.predicted_correct and m.human_feedback:
                    mistakes[m.human_feedback] += 1

        return [
            {"pattern": k, "count": v}
            for k, v in sorted(mistakes.items(), key=lambda x: -x[1])[:5]
        ]

    def _get_resolution_breakdown(self) -> Dict[str, int]:
        """Get breakdown by resolution type"""
        breakdown = defaultdict(int)

        with self._lock:
            for m in self._accuracy_metrics:
                breakdown[m.resolution_type] += 1

        return dict(breakdown)

    # ==================== Alerting ====================

    def add_alert_callback(self, callback: Callable):
        """Add a callback for alerts"""
        self._alert_callbacks.append(callback)

    def _check_alerts(self, metric: PerformanceMetric):
        """Check if metric should trigger alert"""
        alert = None

        if not metric.success:
            alert = {
                "type": "error",
                "message": f"Operation failed: {metric.operation}",
                "details": metric.error_message
            }
        elif metric.duration_ms > 500:
            alert = {
                "type": "latency",
                "message": f"High latency: {metric.operation}",
                "details": f"{metric.duration_ms:.0f}ms exceeds 500ms threshold"
            }

        if alert:
            for callback in self._alert_callbacks:
                try:
                    callback(alert)
                except Exception:
                    pass  # Don't fail on callback errors

    # ==================== Integration ====================

    def export_to_monitoring(self) -> Dict[str, Any]:
        """Export metrics for monitoring systems"""
        return {
            "client_id": self.client_id,
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": {
                "accuracy": self.get_accuracy(),
                "accuracy_by_category": self.get_accuracy_by_category(),
                "latency_percentiles": self.get_latency_percentiles(),
                "error_rate": self.get_error_rate(),
                "throughput": self.get_throughput(),
                "csat": self.get_csat(),
                "resolution_rate": self.get_resolution_rate()
            }
        }

    def start_auto_export(self, interval: int = METRICS_EXPORT_INTERVAL):
        """Start automatic export thread"""
        if self._running:
            return

        self._running = True

        def export_loop():
            while self._running:
                time.sleep(interval)
                self.export_accuracy_baseline()
                self.export_performance_baseline()

        self._export_thread = threading.Thread(target=export_loop, daemon=True)
        self._export_thread.start()

    def stop_auto_export(self):
        """Stop automatic export thread"""
        self._running = False
        if self._export_thread:
            self._export_thread.join(timeout=5)


# Module-level collector instance
_collector: Optional[MetricsCollector] = None


def get_collector(client_id: str = "client_001") -> MetricsCollector:
    """Get or create metrics collector for client"""
    global _collector
    if _collector is None or _collector.client_id != client_id:
        _collector = MetricsCollector(client_id)
    return _collector
