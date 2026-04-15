"""
PARWA Prometheus Metrics Registry (Day 21, BC-012)

Provides a lightweight Prometheus-compatible metrics system without
external dependencies (no prometheus_client library required).

Metrics defined:
- parwa_http_requests_total (counter) — by method, path, status_code
- parwa_http_request_duration_seconds (histogram) — by method, path
- parwa_active_websocket_connections (gauge)
- parwa_celery_queue_depth (gauge) — by queue_name
- parwa_celery_task_duration_seconds (histogram) — by task_name
- parwa_celery_task_total (counter) — by task_name, status
- parwa_db_query_duration_seconds (histogram)
- parwa_db_pool_size (gauge)
- parwa_redis_commands_total (counter) — by command
- parwa_redis_operation_duration_seconds (histogram)

Security: Metrics MUST NOT expose tenant-specific data (loophole check).
"""

import threading
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.logger import get_logger

logger = get_logger("metrics")


# ── Metric Types ───────────────────────────────────────────────────


@dataclass
class CounterMetric:
    """Prometheus counter: monotonically increasing value.

    Attributes:
        name: Metric name.
        help_text: Help text for Prometheus.
        value: Current counter value.
        labels: Label set -> value mapping for labeled counters.
    """
    name: str
    help_text: str
    value: float = 0.0
    labels: Dict[str, float] = field(
        default_factory=lambda: defaultdict(float),
    )

    def inc(self, value: float = 1.0) -> None:
        """Increment the counter by value (must be >= 0)."""
        if value < 0:
            logger.warning(
                "counter_negative_increment",
                extra={"name": self.name, "value": value},
            )
            return
        self.value += value

    def inc_labels(self, value: float, **labels: str) -> None:
        """Increment a labeled counter."""
        if value < 0:
            return
        key = self._label_key(labels)
        self.labels[key] += value

    def _label_key(self, labels: Dict[str, str]) -> str:
        """Build a stable key from label dict."""
        parts = sorted(labels.items())
        return ",".join(f'{k}="{v}"' for k, v in parts)

    def render(self) -> str:
        """Render as Prometheus text format."""
        lines = [
            f"# HELP {self.name} {self.help_text}",
            f"# TYPE {self.name} counter",
            f"{self.name} {self.value}",
        ]
        for label_key, val in sorted(self.labels.items()):
            if label_key:
                lines.append(f'{self.name}{{{label_key}}} {val}')
        return "\n".join(lines)


@dataclass
class GaugeMetric:
    """Prometheus gauge: value can go up or down.

    Attributes:
        name: Metric name.
        help_text: Help text for Prometheus.
        value: Current gauge value.
        labels: Label set -> value mapping.
    """
    name: str
    help_text: str
    value: float = 0.0
    labels: Dict[str, float] = field(
        default_factory=lambda: defaultdict(float),
    )

    def set(self, value: float) -> None:
        """Set the gauge to a specific value."""
        self.value = value

    def inc(self, value: float = 1.0) -> None:
        """Increment the gauge."""
        self.value += value

    def dec(self, value: float = 1.0) -> None:
        """Decrement the gauge."""
        self.value -= value

    def set_labels(self, value: float, **labels: str) -> None:
        """Set a labeled gauge value."""
        key = self._label_key(labels)
        self.labels[key] = value

    def inc_labels(self, value: float, **labels: str) -> None:
        """Increment a labeled gauge."""
        key = self._label_key(labels)
        self.labels[key] += value

    def _label_key(self, labels: Dict[str, str]) -> str:
        """Build a stable key from label dict."""
        parts = sorted(labels.items())
        return ",".join(f'{k}="{v}"' for k, v in parts)

    def render(self) -> str:
        """Render as Prometheus text format."""
        lines = [
            f"# HELP {self.name} {self.help_text}",
            f"# TYPE {self.name} gauge",
            f"{self.name} {self.value}",
        ]
        for label_key, val in sorted(self.labels.items()):
            if label_key:
                lines.append(f'{self.name}{{{label_key}}} {val}')
        return "\n".join(lines)


@dataclass
class HistogramMetric:
    """Prometheus histogram: tracks distribution of values.

    Uses pre-defined bucket boundaries for percentile approximation.
    Default buckets: [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]

    Attributes:
        name: Metric name.
        help_text: Help text for Prometheus.
        buckets: Bucket boundaries.
        counts: Bucket -> count mapping.
        sum_value: Sum of all observed values.
        count: Total number of observations.
    """
    name: str
    help_text: str
    buckets: List[float] = field(default_factory=lambda: [
        0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10,
    ])
    counts: Dict[float, int] = field(default_factory=dict)
    sum_value: float = 0.0
    count: int = 0
    labels: Dict[str, Dict] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize bucket counts to 0."""
        for b in self.buckets:
            if b not in self.counts:
                self.counts[b] = 0

    def observe(self, value: float, **labels: str) -> None:
        """Record an observed value."""
        if labels:
            key = self._label_key(labels)
            if key not in self.labels:
                self.labels[key] = {
                    "counts": {b: 0 for b in self.buckets},
                    "sum": 0.0,
                    "count": 0,
                }
            entry = self.labels[key]
            entry["count"] += 1
            entry["sum"] += value
            for b in self.buckets:
                if value <= b:
                    entry["counts"][b] += 1
        else:
            self.count += 1
            self.sum_value += value
            for b in self.buckets:
                if value <= b:
                    self.counts[b] += 1

    def _label_key(self, labels: Dict[str, str]) -> str:
        """Build a stable key from label dict."""
        parts = sorted(labels.items())
        return ",".join(f'{k}="{v}"' for k, v in parts)

    def render(self) -> str:
        """Render as Prometheus text format."""
        lines = [
            f"# HELP {self.name} {self.help_text}",
            f"# TYPE {self.name} histogram",
        ]

        # Main (unlabeled) metrics
        for b in sorted(self.buckets):
            le = f"{b}"
            if b == float("inf"):
                le = "+Inf"
            lines.append(
                f'{self.name}_bucket{{le="{le}"}} {self.counts.get(b, 0)}'
            )
        lines.append(f"{self.name}_count {self.count}")
        lines.append(f"{self.name}_sum {self.sum_value}")

        # Labeled metrics
        for label_key, entry in sorted(self.labels.items()):
            for b in sorted(self.buckets):
                le = f"{b}"
                if b == float("inf"):
                    le = "+Inf"
                lines.append(
                    f'{self.name}_bucket{{le="{le}",{label_key}}} '
                    f'{entry["counts"].get(b, 0)}'
                )
            lines.append(
                f'{self.name}_count{{{label_key}}} {entry["count"]}'
            )
            lines.append(
                f'{self.name}_sum{{{label_key}}} {entry["sum"]}'
            )

        return "\n".join(lines)


# ── Metrics Registry ───────────────────────────────────────────────


class MetricsRegistry:
    """Thread-safe Prometheus metrics registry.

    All metrics are registered here and can be rendered as
    Prometheus text format for scraping.
    """

    def __init__(self):
        self._metrics: Dict[str, Any] = {}
        self._lock = threading.Lock()

    def counter(
        self, name: str, help_text: str,
    ) -> CounterMetric:
        """Get or create a counter metric."""
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = CounterMetric(
                    name=name, help_text=help_text,
                )
            return self._metrics[name]

    def gauge(
        self, name: str, help_text: str,
    ) -> GaugeMetric:
        """Get or create a gauge metric."""
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = GaugeMetric(
                    name=name, help_text=help_text,
                )
            return self._metrics[name]

    def histogram(
        self, name: str, help_text: str,
        buckets: Optional[List[float]] = None,
    ) -> HistogramMetric:
        """Get or create a histogram metric."""
        with self._lock:
            if name not in self._metrics:
                kwargs = {"name": name, "help_text": help_text}
                if buckets is not None:
                    kwargs["buckets"] = buckets
                self._metrics[name] = HistogramMetric(**kwargs)
            return self._metrics[name]

    def render_all(self) -> str:
        """Render all registered metrics as Prometheus text format."""
        with self._lock:
            parts = []
            for metric in self._metrics.values():
                parts.append(metric.render())
            return "\n\n".join(parts)

    def clear(self) -> None:
        """Clear all metrics (used in tests)."""
        with self._lock:
            self._metrics.clear()


# ── Global Registry Instance ───────────────────────────────────────

registry = MetricsRegistry()

# ── Pre-registered Metrics ─────────────────────────────────────────

# HTTP metrics
http_requests_total = registry.counter(
    "parwa_http_requests_total",
    "Total HTTP requests by method, path, and status code",
)
http_request_duration = registry.histogram(
    "parwa_http_request_duration_seconds",
    "HTTP request duration in seconds by method and path",
)

# WebSocket metrics
active_websocket_connections = registry.gauge(
    "parwa_active_websocket_connections",
    "Number of active WebSocket connections",
)

# Celery metrics
celery_queue_depth = registry.gauge(
    "parwa_celery_queue_depth",
    "Current queue depth by queue name",
)
celery_task_duration = registry.histogram(
    "parwa_celery_task_duration_seconds",
    "Celery task execution duration in seconds by task name",
)
celery_task_total = registry.counter(
    "parwa_celery_task_total",
    "Total Celery tasks by task name and status",
)

# Database metrics
db_query_duration = registry.histogram(
    "parwa_db_query_duration_seconds",
    "Database query duration in seconds",
)
db_pool_size = registry.gauge(
    "parwa_db_pool_size",
    "Database connection pool size (used and max)",
)

# Redis metrics
redis_commands_total = registry.counter(
    "parwa_redis_commands_total",
    "Total Redis commands by command type",
)
redis_operation_duration = registry.histogram(
    "parwa_redis_operation_duration_seconds",
    "Redis operation duration in seconds by command",
)


# ── Helper Functions ───────────────────────────────────────────────


def record_http_request(
    method: str, path: str, status_code: int,
    duration: float,
) -> None:
    """Record an HTTP request metric.

    Path is normalized to prevent cardinality explosion:
    - UUIDs replaced with :id
    - Numeric IDs replaced with :id
    - Query strings stripped

    Args:
        method: HTTP method (GET, POST, etc.).
        path: Request path.
        status_code: Response status code.
        duration: Request duration in seconds.
    """
    normalized = _normalize_path(path)
    http_requests_total.inc_labels(
        1.0,
        method=method,
        path=normalized,
        status=str(status_code),
    )
    http_request_duration.observe(
        duration,
        method=method,
        path=normalized,
    )


def record_celery_task(
    task_name: str, status: str, duration: float,
) -> None:
    """Record a Celery task execution metric.

    Args:
        task_name: Name of the Celery task.
        status: Task status (success, failure, retry).
        duration: Task duration in seconds.
    """
    celery_task_total.inc_labels(
        1.0,
        task_name=task_name,
        status=status,
    )
    celery_task_duration.observe(
        duration,
        task_name=task_name,
    )


def record_db_query(duration: float) -> None:
    """Record a database query duration.

    Args:
        duration: Query duration in seconds.
    """
    db_query_duration.observe(duration)


def update_db_pool(used: int, max_size: int) -> None:
    """Update database pool size gauge.

    Args:
        used: Number of connections in use.
        max_size: Maximum pool size.
    """
    db_pool_size.set_labels(used, state="used")
    db_pool_size.set_labels(max_size, state="max")


def record_redis_command(command: str, duration: float) -> None:
    """Record a Redis command metric.

    Args:
        command: Redis command type (GET, SET, etc.).
        duration: Command duration in seconds.
    """
    redis_commands_total.inc_labels(1.0, command=command)
    redis_operation_duration.observe(duration, command=command)


def _normalize_path(path: str) -> str:
    """Normalize a URL path to prevent metric cardinality explosion.

    Replaces UUIDs and numeric IDs with :id placeholder.

    Args:
        path: Raw URL path.

    Returns:
        Normalized path safe for Prometheus labels.
    """
    import re

    # Strip query string
    path = path.split("?")[0]

    # Replace UUIDs with :id
    path = re.sub(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        ":id", path, flags=re.IGNORECASE,
    )

    # Replace numeric segments with :id (but keep version numbers)
    # Only replace standalone numeric path segments
    path = re.sub(r"/\d+(?=/|$)", "/:id", path)

    return path
