"""
Week 58 - Builder 5: Integration Analytics Module
Integration metrics, health monitoring, and usage analytics
"""

import time
import threading
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import logging
import math

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Metric types"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


class HealthStatus(Enum):
    """Health status levels"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class Metric:
    """Metric data point"""
    name: str
    value: float
    metric_type: MetricType
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class HealthCheck:
    """Health check result"""
    name: str
    status: HealthStatus
    message: str = ""
    latency_ms: float = 0
    last_check: float = field(default_factory=time.time)
    consecutive_failures: int = 0


class IntegrationMetrics:
    """
    Integration metrics collection and aggregation
    """

    def __init__(self):
        self.counters: Dict[str, float] = defaultdict(float)
        self.gauges: Dict[str, float] = {}
        self.histograms: Dict[str, List[float]] = defaultdict(list)
        self.summaries: Dict[str, Dict[str, float]] = defaultdict(
            lambda: {"count": 0, "sum": 0, "min": float("inf"), "max": float("-inf")}
        )
        self.metrics_history: Dict[str, List[Metric]] = defaultdict(list)
        self.lock = threading.Lock()

    def increment(self, name: str, value: float = 1,
                  labels: Dict[str, str] = None) -> None:
        """Increment a counter metric"""
        with self.lock:
            key = self._make_key(name, labels)
            self.counters[key] += value
            self._record_metric(name, value, MetricType.COUNTER, labels)

    def decrement(self, name: str, value: float = 1,
                  labels: Dict[str, str] = None) -> None:
        """Decrement a counter metric"""
        self.increment(name, -value, labels)

    def set_gauge(self, name: str, value: float,
                  labels: Dict[str, str] = None) -> None:
        """Set a gauge metric"""
        with self.lock:
            key = self._make_key(name, labels)
            self.gauges[key] = value
            self._record_metric(name, value, MetricType.GAUGE, labels)

    def observe(self, name: str, value: float,
                labels: Dict[str, str] = None) -> None:
        """Record an observation for histogram/summary"""
        with self.lock:
            key = self._make_key(name, labels)
            self.histograms[key].append(value)
            summary = self.summaries[key]
            summary["count"] += 1
            summary["sum"] += value
            summary["min"] = min(summary["min"], value)
            summary["max"] = max(summary["max"], value)
            self._record_metric(name, value, MetricType.HISTOGRAM, labels)

    def _make_key(self, name: str, labels: Dict[str, str] = None) -> str:
        """Create metric key with labels"""
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    def _record_metric(self, name: str, value: float,
                       metric_type: MetricType,
                       labels: Dict[str, str] = None) -> None:
        """Record metric in history"""
        metric = Metric(
            name=name,
            value=value,
            metric_type=metric_type,
            labels=labels or {}
        )
        self.metrics_history[name].append(metric)
        # Keep last 1000 entries per metric
        if len(self.metrics_history[name]) > 1000:
            self.metrics_history[name] = self.metrics_history[name][-1000:]

    def get_counter(self, name: str, labels: Dict[str, str] = None) -> float:
        """Get counter value"""
        key = self._make_key(name, labels)
        return self.counters.get(key, 0)

    def get_gauge(self, name: str, labels: Dict[str, str] = None) -> float:
        """Get gauge value"""
        key = self._make_key(name, labels)
        return self.gauges.get(key, 0)

    def get_histogram(self, name: str,
                      labels: Dict[str, str] = None) -> Dict[str, float]:
        """Get histogram statistics"""
        key = self._make_key(name, labels)
        values = self.histograms.get(key, [])
        if not values:
            return {"count": 0, "min": 0, "max": 0, "avg": 0, "p50": 0, "p95": 0, "p99": 0}

        sorted_values = sorted(values)
        return {
            "count": len(values),
            "min": sorted_values[0],
            "max": sorted_values[-1],
            "avg": sum(values) / len(values),
            "p50": self._percentile(sorted_values, 50),
            "p95": self._percentile(sorted_values, 95),
            "p99": self._percentile(sorted_values, 99)
        }

    def _percentile(self, sorted_values: List[float], p: float) -> float:
        """Calculate percentile"""
        if not sorted_values:
            return 0
        k = (len(sorted_values) - 1) * p / 100
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return sorted_values[int(k)]
        return sorted_values[int(f)] * (c - k) + sorted_values[int(c)] * (k - f)

    def get_summary(self, name: str,
                    labels: Dict[str, str] = None) -> Dict[str, float]:
        """Get summary statistics"""
        key = self._make_key(name, labels)
        summary = self.summaries.get(key)
        if not summary or summary["count"] == 0:
            return {"count": 0, "sum": 0, "avg": 0, "min": 0, "max": 0}
        return {
            "count": summary["count"],
            "sum": summary["sum"],
            "avg": summary["sum"] / summary["count"],
            "min": summary["min"],
            "max": summary["max"]
        }

    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all metrics"""
        return {
            "counters": dict(self.counters),
            "gauges": dict(self.gauges),
            "histograms": {k: self.get_histogram(k.split("{")[0])
                          for k in self.histograms.keys()},
            "summaries": {k: self.get_summary(k.split("{")[0])
                         for k in self.summaries.keys()}
        }


class HealthMonitor:
    """
    Health monitoring for integration endpoints
    """

    def __init__(self):
        self.health_checks: Dict[str, HealthCheck] = {}
        self.uptime_records: Dict[str, List[bool]] = defaultdict(list)
        self.alert_thresholds: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()

    def register_check(self, name: str, threshold: int = 3) -> None:
        """Register a health check"""
        with self.lock:
            self.health_checks[name] = HealthCheck(
                name=name,
                status=HealthStatus.UNKNOWN
            )
            self.alert_thresholds[name] = {
                "consecutive_failures": threshold
            }

    def record_check(self, name: str, is_healthy: bool,
                     latency_ms: float = 0,
                     message: str = "") -> HealthCheck:
        """Record a health check result"""
        with self.lock:
            check = self.health_checks.get(name)
            if not check:
                check = HealthCheck(name=name, status=HealthStatus.UNKNOWN)
                self.health_checks[name] = check

            check.last_check = time.time()
            check.latency_ms = latency_ms
            check.message = message

            if is_healthy:
                check.status = HealthStatus.HEALTHY
                check.consecutive_failures = 0
            else:
                check.consecutive_failures += 1
                threshold = self.alert_thresholds.get(name, {}).get(
                    "consecutive_failures", 3
                )
                if check.consecutive_failures >= threshold:
                    check.status = HealthStatus.UNHEALTHY
                else:
                    check.status = HealthStatus.DEGRADED

            # Record uptime
            self.uptime_records[name].append(is_healthy)
            if len(self.uptime_records[name]) > 1000:
                self.uptime_records[name] = self.uptime_records[name][-1000:]

            return check

    def get_health(self, name: str) -> Optional[HealthCheck]:
        """Get health check status"""
        return self.health_checks.get(name)

    def get_all_health(self) -> Dict[str, HealthCheck]:
        """Get all health checks"""
        return dict(self.health_checks)

    def get_uptime(self, name: str, window: int = 100) -> float:
        """Get uptime percentage"""
        records = self.uptime_records.get(name, [])
        if not records:
            return 0.0
        window_records = records[-window:]
        return sum(window_records) / len(window_records) * 100

    def get_status_summary(self) -> Dict[str, int]:
        """Get status counts"""
        summary = defaultdict(int)
        for check in self.health_checks.values():
            summary[check.status.value] += 1
        return dict(summary)

    def set_alert_threshold(self, name: str,
                            consecutive_failures: int) -> None:
        """Set alert threshold for a check"""
        with self.lock:
            if name not in self.alert_thresholds:
                self.alert_thresholds[name] = {}
            self.alert_thresholds[name]["consecutive_failures"] = consecutive_failures

    def get_unhealthy(self) -> List[str]:
        """Get list of unhealthy endpoints"""
        return [
            name for name, check in self.health_checks.items()
            if check.status == HealthStatus.UNHEALTHY
        ]


class UsageAnalytics:
    """
    Usage analytics and trend analysis
    """

    def __init__(self):
        self.usage_data: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.patterns: Dict[str, Dict[str, Any]] = {}
        self.forecasts: Dict[str, float] = {}
        self.lock = threading.Lock()

    def record_usage(self, integration: str, endpoint: str,
                     requests: int = 1, errors: int = 0,
                     latency_ms: float = 0) -> None:
        """Record usage data"""
        with self.lock:
            record = {
                "endpoint": endpoint,
                "requests": requests,
                "errors": errors,
                "latency_ms": latency_ms,
                "timestamp": time.time()
            }
            self.usage_data[integration].append(record)

            # Keep last 10000 records
            if len(self.usage_data[integration]) > 10000:
                self.usage_data[integration] = self.usage_data[integration][-10000:]

    def get_usage_stats(self, integration: str,
                        window_seconds: int = 3600) -> Dict[str, Any]:
        """Get usage statistics for time window"""
        records = self.usage_data.get(integration, [])
        cutoff = time.time() - window_seconds
        window_records = [r for r in records if r["timestamp"] > cutoff]

        if not window_records:
            return {"requests": 0, "errors": 0, "avg_latency_ms": 0}

        total_requests = sum(r["requests"] for r in window_records)
        total_errors = sum(r["errors"] for r in window_records)
        latencies = [r["latency_ms"] for r in window_records if r["latency_ms"] > 0]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0

        return {
            "requests": total_requests,
            "errors": total_errors,
            "error_rate": total_errors / total_requests if total_requests > 0 else 0,
            "avg_latency_ms": avg_latency,
            "records_count": len(window_records)
        }

    def detect_patterns(self, integration: str) -> Dict[str, Any]:
        """Detect usage patterns"""
        records = self.usage_data.get(integration, [])
        if len(records) < 10:
            return {"patterns": [], "confidence": 0}

        # Simple pattern detection - hourly distribution
        hourly = defaultdict(int)
        for record in records:
            hour = int((record["timestamp"] % 86400) // 3600)
            hourly[hour] += record["requests"]

        peak_hour = max(hourly.keys(), key=lambda h: hourly[h])
        low_hour = min(hourly.keys(), key=lambda h: hourly[h])

        pattern = {
            "peak_hour": peak_hour,
            "peak_requests": hourly[peak_hour],
            "low_hour": low_hour,
            "low_requests": hourly[low_hour],
            "hourly_distribution": dict(hourly)
        }

        with self.lock:
            self.patterns[integration] = pattern

        return {
            "patterns": [pattern],
            "confidence": min(1.0, len(records) / 1000)
        }

    def forecast_usage(self, integration: str,
                       horizon_hours: int = 24) -> float:
        """Simple usage forecast based on historical data"""
        records = self.usage_data.get(integration, [])
        if len(records) < 24:
            return 0.0

        # Get recent hourly data
        now = time.time()
        hourly_requests = []
        for i in range(24):
            hour_start = now - (i + 1) * 3600
            hour_end = now - i * 3600
            hour_requests = sum(
                r["requests"] for r in records
                if hour_start < r["timestamp"] <= hour_end
            )
            hourly_requests.append(hour_requests)

        # Simple moving average forecast
        if hourly_requests:
            forecast = sum(hourly_requests) / len(hourly_requests)
        else:
            forecast = 0

        with self.lock:
            self.forecasts[integration] = forecast

        return forecast

    def get_trends(self, integration: str) -> Dict[str, Any]:
        """Get usage trends"""
        stats_1h = self.get_usage_stats(integration, 3600)
        stats_24h = self.get_usage_stats(integration, 86400)
        stats_7d = self.get_usage_stats(integration, 604800)

        return {
            "hourly": stats_1h,
            "daily": stats_24h,
            "weekly": stats_7d,
            "forecast": self.forecasts.get(integration, 0),
            "patterns": self.patterns.get(integration, {})
        }

    def get_report(self, integration: str = None) -> Dict[str, Any]:
        """Generate usage report"""
        if integration:
            return {
                "integration": integration,
                "trends": self.get_trends(integration),
                "patterns": self.detect_patterns(integration)
            }

        return {
            "integrations": list(self.usage_data.keys()),
            "trends": {
                name: self.get_trends(name)
                for name in self.usage_data.keys()
            }
        }
