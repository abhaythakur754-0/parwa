"""
Latency Tracking for Agent Lightning 94%.

Comprehensive latency tracking with:
- P50/P95/P99 tracking
- Latency distribution
- Slow query detection
- Latency alerts
- Historical tracking
"""

import asyncio
import time
import statistics
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
from pathlib import Path
import json
import threading

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class LatencyAlertSeverity(str, Enum):
    """Severity levels for latency alerts."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class QueryCategory(str, Enum):
    """Categories for query classification."""
    LIGHT = "light"       # FAQ, simple queries
    MEDIUM = "medium"     # Standard support queries
    HEAVY = "heavy"       # Complex queries, escalations
    UNKNOWN = "unknown"


@dataclass
class LatencyRecord:
    """Record of a single latency measurement."""
    timestamp: str
    latency_ms: float
    query: str
    category: QueryCategory = QueryCategory.UNKNOWN
    client_id: Optional[str] = None
    model_used: Optional[str] = None
    success: bool = True
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp,
            "latency_ms": self.latency_ms,
            "query": self.query[:100],  # Truncate for storage
            "category": self.category.value,
            "client_id": self.client_id,
            "model_used": self.model_used,
            "success": self.success,
            "error": self.error
        }


@dataclass
class LatencyAlert:
    """Alert for latency threshold violations."""
    timestamp: str
    severity: LatencyAlertSeverity
    message: str
    latency_ms: float
    threshold_ms: float
    category: QueryCategory
    client_id: Optional[str] = None
    query: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp,
            "severity": self.severity.value,
            "message": self.message,
            "latency_ms": self.latency_ms,
            "threshold_ms": self.threshold_ms,
            "category": self.category.value,
            "client_id": self.client_id,
            "query": self.query[:100] if self.query else None
        }


@dataclass
class PercentileStats:
    """Percentile statistics for latency."""
    p50: float = 0.0
    p75: float = 0.0
    p90: float = 0.0
    p95: float = 0.0
    p99: float = 0.0
    min: float = 0.0
    max: float = 0.0
    mean: float = 0.0
    std: float = 0.0
    count: int = 0


@dataclass
class LatencyDistribution:
    """Distribution of latencies across buckets."""
    buckets: Dict[str, int] = field(default_factory=dict)  # bucket_name -> count
    total_count: int = 0

    def get_percentage(self, bucket: str) -> float:
        """Get percentage of requests in bucket."""
        if self.total_count == 0:
            return 0.0
        return (self.buckets.get(bucket, 0) / self.total_count) * 100


class SlowQueryDetector:
    """
    Detects and tracks slow queries.

    Identifies queries that exceed latency thresholds.
    """

    # Default thresholds in milliseconds
    DEFAULT_THRESHOLDS = {
        QueryCategory.LIGHT: 100,
        QueryCategory.MEDIUM: 200,
        QueryCategory.HEAVY: 500,
        QueryCategory.UNKNOWN: 300
    }

    def __init__(
        self,
        thresholds: Optional[Dict[QueryCategory, float]] = None,
        slow_query_multiplier: float = 2.0
    ):
        """
        Initialize slow query detector.

        Args:
            thresholds: Custom thresholds per category
            slow_query_multiplier: Multiplier for baseline to detect anomalies
        """
        self.thresholds = thresholds or self.DEFAULT_THRESHOLDS.copy()
        self.slow_query_multiplier = slow_query_multiplier
        self._baselines: Dict[QueryCategory, float] = {}
        self._slow_queries: List[LatencyRecord] = []
        self._lock = threading.Lock()

    def is_slow(self, record: LatencyRecord) -> bool:
        """
        Check if a query is slow.

        Args:
            record: Latency record to check

        Returns:
            True if query is slow
        """
        threshold = self.thresholds.get(record.category, 300)

        # Check absolute threshold
        if record.latency_ms > threshold:
            return True

        # Check against dynamic baseline
        baseline = self._baselines.get(record.category)
        if baseline and record.latency_ms > baseline * self.slow_query_multiplier:
            return True

        return False

    def add_record(self, record: LatencyRecord) -> Optional[LatencyAlert]:
        """
        Add a record and check for slow query.

        Args:
            record: Latency record to add

        Returns:
            LatencyAlert if slow query detected, None otherwise
        """
        with self._lock:
            if self.is_slow(record):
                self._slow_queries.append(record)

                # Generate alert
                threshold = self.thresholds.get(record.category, 300)
                severity = LatencyAlertSeverity.WARNING
                if record.latency_ms > threshold * 2:
                    severity = LatencyAlertSeverity.CRITICAL

                return LatencyAlert(
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    severity=severity,
                    message=f"Slow query detected: {record.latency_ms:.0f}ms exceeds {threshold:.0f}ms threshold",
                    latency_ms=record.latency_ms,
                    threshold_ms=threshold,
                    category=record.category,
                    client_id=record.client_id,
                    query=record.query
                )

            return None

    def update_baseline(self, category: QueryCategory, baseline: float) -> None:
        """Update baseline for a category."""
        with self._lock:
            self._baselines[category] = baseline

    def get_slow_queries(self, limit: int = 100) -> List[LatencyRecord]:
        """Get recent slow queries."""
        with self._lock:
            return self._slow_queries[-limit:]


class LatencyAlertManager:
    """
    Manages latency alerts and notifications.

    Tracks alerts and triggers callbacks when thresholds are exceeded.
    """

    def __init__(
        self,
        alert_callbacks: Optional[List[Callable[[LatencyAlert], None]]] = None
    ):
        """
        Initialize alert manager.

        Args:
            alert_callbacks: Callbacks to invoke on alerts
        """
        self.alert_callbacks = alert_callbacks or []
        self._alerts: deque = deque(maxlen=1000)  # Keep last 1000 alerts
        self._lock = threading.Lock()
        self._alert_counts: Dict[LatencyAlertSeverity, int] = defaultdict(int)

    def add_alert(self, alert: LatencyAlert) -> None:
        """
        Add an alert and trigger callbacks.

        Args:
            alert: Alert to add
        """
        with self._lock:
            self._alerts.append(alert)
            self._alert_counts[alert.severity] += 1

        # Trigger callbacks
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error({
                    "event": "alert_callback_error",
                    "error": str(e)
                })

        # Log the alert
        log_data = {
            "event": "latency_alert",
            "severity": alert.severity.value,
            "latency_ms": alert.latency_ms,
            "threshold_ms": alert.threshold_ms,
            "category": alert.category.value,
            "client_id": alert.client_id,
            "message": alert.message
        }

        if alert.severity == LatencyAlertSeverity.CRITICAL:
            logger.error(log_data)
        elif alert.severity == LatencyAlertSeverity.WARNING:
            logger.warning(log_data)
        else:
            logger.info(log_data)

    def get_alerts(
        self,
        severity: Optional[LatencyAlertSeverity] = None,
        limit: int = 100
    ) -> List[LatencyAlert]:
        """
        Get alerts, optionally filtered by severity.

        Args:
            severity: Filter by severity (optional)
            limit: Maximum number of alerts to return

        Returns:
            List of alerts
        """
        with self._lock:
            alerts = list(self._alerts)

            if severity:
                alerts = [a for a in alerts if a.severity == severity]

            return alerts[-limit:]

    def get_alert_counts(self) -> Dict[str, int]:
        """Get count of alerts by severity."""
        with self._lock:
            return {k.value: v for k, v in self._alert_counts.items()}

    def clear_alerts(self) -> None:
        """Clear all alerts."""
        with self._lock:
            self._alerts.clear()
            self._alert_counts.clear()


class HistoricalLatencyTracker:
    """
    Tracks latency history over time.

    Stores aggregated metrics at regular intervals.
    """

    def __init__(self, history_size: int = 1440):  # 1 day at 1-minute intervals
        """
        Initialize historical tracker.

        Args:
            history_size: Number of intervals to keep
        """
        self.history_size = history_size
        self._history: deque = deque(maxlen=history_size)
        self._current_interval: Dict[str, List[float]] = defaultdict(list)
        self._interval_start: Optional[datetime] = None
        self._lock = threading.Lock()

    def add_latency(self, record: LatencyRecord) -> None:
        """
        Add a latency record.

        Args:
            record: Latency record to add
        """
        with self._lock:
            now = datetime.now(timezone.utc)
            minute_key = now.strftime("%Y-%m-%d %H:%M")

            self._current_interval[minute_key].append(record.latency_ms)

    def aggregate_interval(self) -> Optional[Dict[str, Any]]:
        """
        Aggregate current interval and store in history.

        Returns:
            Aggregated metrics for the interval
        """
        with self._lock:
            if not self._current_interval:
                return None

            minute_key = list(self._current_interval.keys())[0]
            latencies = self._current_interval[minute_key]

            if not latencies:
                return None

            latencies_sorted = sorted(latencies)
            count = len(latencies_sorted)

            aggregated = {
                "timestamp": minute_key,
                "count": count,
                "mean": statistics.mean(latencies_sorted),
                "min": min(latencies_sorted),
                "max": max(latencies_sorted),
                "p50": latencies_sorted[int(count * 0.50)],
                "p95": latencies_sorted[int(count * 0.95)] if count >= 20 else latencies_sorted[-1],
                "p99": latencies_sorted[int(count * 0.99)] if count >= 100 else latencies_sorted[-1],
            }

            self._history.append(aggregated)
            self._current_interval.clear()

            return aggregated

    def get_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get historical data for the last N hours.

        Args:
            hours: Number of hours of history to return

        Returns:
            List of aggregated metrics per minute
        """
        with self._lock:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
            cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M")

            return [
                h for h in self._history
                if h["timestamp"] >= cutoff_str
            ]

    def get_trend(self, metric: str = "p95", hours: int = 1) -> Dict[str, Any]:
        """
        Get trend for a specific metric.

        Args:
            metric: Metric to analyze (p50, p95, p99, mean)
            hours: Hours of history to analyze

        Returns:
            Trend analysis with direction and rate
        """
        history = self.get_history(hours)

        if len(history) < 2:
            return {"trend": "insufficient_data", "values": []}

        values = [h.get(metric, 0) for h in history]

        # Calculate trend direction
        first_half = statistics.mean(values[:len(values)//2])
        second_half = statistics.mean(values[len(values)//2:])

        if second_half > first_half * 1.1:
            direction = "increasing"
        elif second_half < first_half * 0.9:
            direction = "decreasing"
        else:
            direction = "stable"

        rate = (second_half - first_half) / first_half * 100 if first_half > 0 else 0

        return {
            "trend": direction,
            "rate_percent": rate,
            "first_half_avg": first_half,
            "second_half_avg": second_half,
            "values": values
        }


class LatencyTracker:
    """
    Main latency tracking orchestrator.

    Combines all latency tracking components for comprehensive monitoring.
    """

    # Default latency thresholds in milliseconds
    DEFAULT_P50_THRESHOLD = 100
    DEFAULT_P95_THRESHOLD = 200
    DEFAULT_P99_THRESHOLD = 500

    def __init__(
        self,
        client_id: Optional[str] = None,
        output_dir: Optional[Path] = None,
        alert_callbacks: Optional[List[Callable[[LatencyAlert], None]]] = None
    ):
        """
        Initialize latency tracker.

        Args:
            client_id: Optional client identifier
            output_dir: Directory to save latency reports
            alert_callbacks: Callbacks for latency alerts
        """
        self.client_id = client_id
        self.output_dir = output_dir or Path("reports/latency")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize components
        self.slow_query_detector = SlowQueryDetector()
        self.alert_manager = LatencyAlertManager(alert_callbacks)
        self.historical_tracker = HistoricalLatencyTracker()

        # Latency storage
        self._latencies: Dict[QueryCategory, List[float]] = defaultdict(list)
        self._records: deque = deque(maxlen=10000)  # Keep last 10k records
        self._lock = threading.Lock()

        # Thresholds
        self.p50_threshold = self.DEFAULT_P50_THRESHOLD
        self.p95_threshold = self.DEFAULT_P95_THRESHOLD
        self.p99_threshold = self.DEFAULT_P99_THRESHOLD

    def categorize_query(self, query: str) -> QueryCategory:
        """
        Categorize a query based on content.

        Args:
            query: Query string to categorize

        Returns:
            QueryCategory for the query
        """
        query_lower = query.lower()

        # Heavy tier keywords
        heavy_keywords = ["manager", "supervisor", "complaint", "urgent", "legal", "lawsuit", "fraud"]
        if any(kw in query_lower for kw in heavy_keywords):
            return QueryCategory.HEAVY

        # Medium tier keywords
        medium_keywords = ["refund", "cancel", "dispute", "problem", "issue", "error", "wrong", "broken", "damaged"]
        if any(kw in query_lower for kw in medium_keywords):
            return QueryCategory.MEDIUM

        # Light tier keywords
        light_keywords = ["hours", "policy", "how do i", "what is", "where is", "when", "contact", "help"]
        if any(kw in query_lower for kw in light_keywords):
            return QueryCategory.LIGHT

        return QueryCategory.UNKNOWN

    async def track(
        self,
        query: str,
        latency_ms: float,
        model_used: Optional[str] = None,
        success: bool = True,
        error: Optional[str] = None
    ) -> Optional[LatencyAlert]:
        """
        Track a latency measurement.

        Args:
            query: Query that was processed
            latency_ms: Latency in milliseconds
            model_used: Model that processed the query
            success: Whether the query was successful
            error: Error message if failed

        Returns:
            LatencyAlert if slow query detected, None otherwise
        """
        category = self.categorize_query(query)

        record = LatencyRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            latency_ms=latency_ms,
            query=query,
            category=category,
            client_id=self.client_id,
            model_used=model_used,
            success=success,
            error=error
        )

        with self._lock:
            self._latencies[category].append(latency_ms)
            self._records.append(record)

        # Track in historical tracker
        self.historical_tracker.add_latency(record)

        # Check for slow query
        alert = self.slow_query_detector.add_record(record)

        if alert:
            self.alert_manager.add_alert(alert)

        # Log if significant
        if latency_ms > self.p95_threshold:
            logger.warning({
                "event": "high_latency",
                "latency_ms": latency_ms,
                "category": category.value,
                "query": query[:50],
                "threshold_ms": self.p95_threshold
            })

        return alert

    def get_percentiles(self, category: Optional[QueryCategory] = None) -> PercentileStats:
        """
        Get percentile statistics.

        Args:
            category: Optional category to filter by

        Returns:
            PercentileStats with all percentiles
        """
        with self._lock:
            if category:
                latencies = self._latencies.get(category, [])
            else:
                latencies = [l for lats in self._latencies.values() for l in lats]

        if not latencies:
            return PercentileStats()

        latencies_sorted = sorted(latencies)
        count = len(latencies_sorted)

        return PercentileStats(
            p50=latencies_sorted[int(count * 0.50)],
            p75=latencies_sorted[int(count * 0.75)],
            p90=latencies_sorted[int(count * 0.90)],
            p95=latencies_sorted[int(count * 0.95)] if count >= 20 else latencies_sorted[-1],
            p99=latencies_sorted[int(count * 0.99)] if count >= 100 else latencies_sorted[-1],
            min=min(latencies_sorted),
            max=max(latencies_sorted),
            mean=statistics.mean(latencies_sorted),
            std=statistics.stdev(latencies_sorted) if count > 1 else 0,
            count=count
        )

    def get_distribution(self, category: Optional[QueryCategory] = None) -> LatencyDistribution:
        """
        Get latency distribution across buckets.

        Args:
            category: Optional category to filter by

        Returns:
            LatencyDistribution with bucket counts
        """
        with self._lock:
            if category:
                latencies = self._latencies.get(category, [])
            else:
                latencies = [l for lats in self._latencies.values() for l in lats]

        # Define buckets
        buckets = {
            "0-50ms": 0,
            "50-100ms": 0,
            "100-200ms": 0,
            "200-500ms": 0,
            "500-1000ms": 0,
            "1000ms+": 0
        }

        for lat in latencies:
            if lat < 50:
                buckets["0-50ms"] += 1
            elif lat < 100:
                buckets["50-100ms"] += 1
            elif lat < 200:
                buckets["100-200ms"] += 1
            elif lat < 500:
                buckets["200-500ms"] += 1
            elif lat < 1000:
                buckets["500-1000ms"] += 1
            else:
                buckets["1000ms+"] += 1

        return LatencyDistribution(
            buckets=buckets,
            total_count=len(latencies)
        )

    def get_slow_queries(self, limit: int = 50) -> List[LatencyRecord]:
        """
        Get recent slow queries.

        Args:
            limit: Maximum number to return

        Returns:
            List of slow query records
        """
        return self.slow_query_detector.get_slow_queries(limit)

    def get_alerts(
        self,
        severity: Optional[LatencyAlertSeverity] = None,
        limit: int = 50
    ) -> List[LatencyAlert]:
        """
        Get recent alerts.

        Args:
            severity: Optional severity filter
            limit: Maximum number to return

        Returns:
            List of alerts
        """
        return self.alert_manager.get_alerts(severity, limit)

    def get_historical_trend(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get latency trend over time.

        Args:
            hours: Hours of history to analyze

        Returns:
            Trend analysis
        """
        return self.historical_tracker.get_trend("p95", hours)

    def get_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive latency summary.

        Returns:
            Summary dictionary with all metrics
        """
        overall_stats = self.get_percentiles()
        distribution = self.get_distribution()
        alert_counts = self.alert_manager.get_alert_counts()
        trend = self.get_historical_trend()

        # Per-category stats
        category_stats = {}
        for cat in QueryCategory:
            stats = self.get_percentiles(cat)
            if stats.count > 0:
                category_stats[cat.value] = {
                    "p50": stats.p50,
                    "p95": stats.p95,
                    "p99": stats.p99,
                    "mean": stats.mean,
                    "count": stats.count
                }

        return {
            "overall": {
                "p50": overall_stats.p50,
                "p75": overall_stats.p75,
                "p90": overall_stats.p90,
                "p95": overall_stats.p95,
                "p99": overall_stats.p99,
                "mean": overall_stats.mean,
                "min": overall_stats.min,
                "max": overall_stats.max,
                "count": overall_stats.count
            },
            "thresholds": {
                "p50_threshold": self.p50_threshold,
                "p95_threshold": self.p95_threshold,
                "p99_threshold": self.p99_threshold
            },
            "distribution": distribution.buckets,
            "by_category": category_stats,
            "alerts": alert_counts,
            "trend": trend,
            "slow_query_count": len(self.slow_query_detector.get_slow_queries(1000))
        }

    async def save_report(self) -> Path:
        """
        Save latency report to file.

        Returns:
            Path to saved report
        """
        report_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = self.output_dir / f"latency_report_{report_id}.json"

        report = {
            "report_id": report_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "client_id": self.client_id,
            "summary": self.get_summary(),
            "recent_alerts": [a.to_dict() for a in self.get_alerts(limit=20)],
            "slow_queries": [r.to_dict() for r in self.get_slow_queries(20)]
        }

        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)

        logger.info({
            "event": "latency_report_saved",
            "path": str(report_path)
        })

        return report_path

    def reset(self) -> None:
        """Reset all tracking data."""
        with self._lock:
            self._latencies.clear()
            self._records.clear()

        self.alert_manager.clear_alerts()
        logger.info({"event": "latency_tracker_reset"})


def generate_latency_report(tracker: LatencyTracker) -> str:
    """
    Generate human-readable latency report.

    Args:
        tracker: LatencyTracker instance

    Returns:
        Formatted report string
    """
    summary = tracker.get_summary()
    overall = summary["overall"]
    thresholds = summary["thresholds"]

    # Status indicators
    p50_status = "✓" if overall["p50"] <= thresholds["p50_threshold"] else "✗"
    p95_status = "✓" if overall["p95"] <= thresholds["p95_threshold"] else "✗"
    p99_status = "✓" if overall["p99"] <= thresholds["p99_threshold"] else "✗"

    lines = [
        "=" * 60,
        "LATENCY TRACKING REPORT",
        "=" * 60,
        f"Total Requests: {overall['count']}",
        "",
        "PERCENTILE STATISTICS",
        "-" * 40,
        f"{p50_status} P50:  {overall['p50']:.2f}ms (threshold: {thresholds['p50_threshold']}ms)",
        f"  P75:  {overall['p75']:.2f}ms",
        f"  P90:  {overall['p90']:.2f}ms",
        f"{p95_status} P95:  {overall['p95']:.2f}ms (threshold: {thresholds['p95_threshold']}ms)",
        f"{p99_status} P99:  {overall['p99']:.2f}ms (threshold: {thresholds['p99_threshold']}ms)",
        "",
        f"  Mean: {overall['mean']:.2f}ms",
        f"  Min:  {overall['min']:.2f}ms",
        f"  Max:  {overall['max']:.2f}ms",
        "",
        "LATENCY DISTRIBUTION",
        "-" * 40,
    ]

    for bucket, count in summary["distribution"].items():
        pct = (count / overall["count"] * 100) if overall["count"] > 0 else 0
        bar = "█" * int(pct / 5)
        lines.append(f"  {bucket:15s}: {count:5d} ({pct:5.1f}%) {bar}")

    if summary["by_category"]:
        lines.extend([
            "",
            "BY CATEGORY",
            "-" * 40,
        ])

        for cat, stats in summary["by_category"].items():
            lines.append(f"  {cat}:")
            lines.append(f"    P50: {stats['p50']:.2f}ms, P95: {stats['p95']:.2f}ms, Count: {stats['count']}")

    lines.extend([
        "",
        "ALERTS",
        "-" * 40,
    ])

    for severity, count in summary["alerts"].items():
        lines.append(f"  {severity}: {count}")

    lines.extend([
        "",
        "TREND (24h)",
        "-" * 40,
        f"  Direction: {summary['trend'].get('trend', 'N/A')}",
        f"  Rate: {summary['trend'].get('rate_percent', 0):.1f}%",
        "",
        f"  Slow Queries: {summary['slow_query_count']}",
        "",
        "=" * 60,
    ])

    return "\n".join(lines)


# Decorator for automatic latency tracking
def track_latency(tracker: LatencyTracker, model_name: Optional[str] = None):
    """
    Decorator to automatically track function latency.

    Args:
        tracker: LatencyTracker instance
        model_name: Name of model being used

    Usage:
        @track_latency(tracker, model_name="gpt-4")
        async def process_query(query: str) -> str:
            ...
    """
    def decorator(func: Callable):
        async def wrapper(*args, **kwargs):
            # Try to extract query from args
            query = args[0] if args else str(kwargs)

            start_time = time.perf_counter()
            success = True
            error = None

            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                error = str(e)
                raise
            finally:
                end_time = time.perf_counter()
                latency_ms = (end_time - start_time) * 1000

                await tracker.track(
                    query=query,
                    latency_ms=latency_ms,
                    model_used=model_name,
                    success=success,
                    error=error
                )

        return wrapper
    return decorator


if __name__ == "__main__":
    # Example usage
    async def main():
        tracker = LatencyTracker(client_id="test_client")

        # Simulate some queries
        queries = [
            ("What are your hours?", 45),
            ("I need a refund!", 150),
            ("Where is my order?", 80),
            ("I want to speak to a manager!", 450),
            ("How do I reset my password?", 60),
            ("This is unacceptable!", 600),
            ("What is your return policy?", 35),
        ]

        for query, latency in queries:
            await tracker.track(query, latency)

        print(generate_latency_report(tracker))

        await tracker.save_report()

    asyncio.run(main())
