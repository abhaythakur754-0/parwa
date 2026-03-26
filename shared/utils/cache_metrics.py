"""
Cache Metrics for PARWA Performance Optimization.

Week 26 - Builder 3: Redis Cache Deep Optimization
Target: Hit rate tracking, latency tracking, Prometheus export

Features:
- Hit rate tracking
- Miss rate tracking
- Latency tracking
- Memory usage monitoring
- Eviction tracking
- Prometheus export
"""

import time
import logging
from typing import Any, Optional, Dict, List
from dataclasses import dataclass, field
from collections import defaultdict
from prometheus_client import Counter, Histogram, Gauge, Info
import asyncio

logger = logging.getLogger(__name__)


# Prometheus metrics
CACHE_HITS = Counter(
    "parwa_cache_hits_total",
    "Total cache hits",
    ["cache_type", "client_id"]
)
CACHE_MISSES = Counter(
    "parwa_cache_misses_total",
    "Total cache misses",
    ["cache_type", "client_id"]
)
CACHE_LATENCY = Histogram(
    "parwa_cache_latency_seconds",
    "Cache operation latency",
    ["cache_type", "operation"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]
)
CACHE_MEMORY = Gauge(
    "parwa_cache_memory_bytes",
    "Cache memory usage in bytes",
    ["cache_type"]
)
CACHE_ENTRIES = Gauge(
    "parwa_cache_entries",
    "Number of cache entries",
    ["cache_type"]
)
CACHE_EVICTIONS = Counter(
    "parwa_cache_evictions_total",
    "Total cache evictions",
    ["cache_type", "reason"]
)
CACHE_HIT_RATE = Gauge(
    "parwa_cache_hit_rate",
    "Cache hit rate",
    ["cache_type"]
)


@dataclass
class CacheMetrics:
    """Cache metrics data."""
    cache_type: str
    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    evictions: int = 0
    total_latency_ms: float = 0.0
    operation_count: int = 0
    memory_bytes: int = 0
    entry_count: int = 0
    created_at: float = field(default_factory=time.time)

    @property
    def hit_rate(self) -> float:
        """Calculate hit rate."""
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return self.hits / total

    @property
    def miss_rate(self) -> float:
        """Calculate miss rate."""
        return 1.0 - self.hit_rate

    @property
    def avg_latency_ms(self) -> float:
        """Calculate average latency."""
        if self.operation_count == 0:
            return 0.0
        return self.total_latency_ms / self.operation_count


@dataclass
class LatencyBucket:
    """Latency histogram bucket."""
    threshold_ms: float
    count: int = 0


class CacheMetricsCollector:
    """
    Cache metrics collector with Prometheus integration.

    Features:
    - Hit/miss rate tracking
    - Latency distribution
    - Memory usage monitoring
    - Eviction tracking
    - Prometheus export
    """

    # Latency histogram buckets (in milliseconds)
    LATENCY_BUCKETS = [0.1, 0.5, 1, 2, 5, 10, 25, 50, 100, 250, 500, 1000]

    def __init__(self, enable_prometheus: bool = True):
        """
        Initialize metrics collector.

        Args:
            enable_prometheus: Whether to export to Prometheus.
        """
        self.enable_prometheus = enable_prometheus
        self._metrics: Dict[str, CacheMetrics] = {}
        self._latency_histograms: Dict[str, List[LatencyBucket]] = {}
        self._client_metrics: Dict[str, Dict[str, CacheMetrics]] = defaultdict(
            lambda: {}
        )

        # Initialize latency histograms
        for bucket in self.LATENCY_BUCKETS:
            pass

    def record_hit(
        self,
        cache_type: str,
        client_id: str = "default",
        latency_ms: float = 0.0
    ) -> None:
        """
        Record a cache hit.

        Args:
            cache_type: Type of cache (response, query, session).
            client_id: Client/tenant ID.
            latency_ms: Operation latency in milliseconds.
        """
        # Update metrics
        if cache_type not in self._metrics:
            self._metrics[cache_type] = CacheMetrics(cache_type=cache_type)

        self._metrics[cache_type].hits += 1
        self._metrics[cache_type].operation_count += 1
        self._metrics[cache_type].total_latency_ms += latency_ms

        # Update client metrics
        if client_id not in self._client_metrics[cache_type]:
            self._client_metrics[cache_type][client_id] = CacheMetrics(
                cache_type=cache_type
            )
        self._client_metrics[cache_type][client_id].hits += 1

        # Update latency histogram
        self._update_latency_histogram(cache_type, latency_ms)

        # Export to Prometheus
        if self.enable_prometheus:
            CACHE_HITS.labels(cache_type=cache_type, client_id=client_id).inc()
            CACHE_LATENCY.labels(cache_type=cache_type, operation="get").observe(
                latency_ms / 1000
            )
            self._update_prometheus_hit_rate(cache_type)

    def record_miss(
        self,
        cache_type: str,
        client_id: str = "default",
        latency_ms: float = 0.0
    ) -> None:
        """
        Record a cache miss.

        Args:
            cache_type: Type of cache.
            client_id: Client/tenant ID.
            latency_ms: Operation latency in milliseconds.
        """
        if cache_type not in self._metrics:
            self._metrics[cache_type] = CacheMetrics(cache_type=cache_type)

        self._metrics[cache_type].misses += 1
        self._metrics[cache_type].operation_count += 1
        self._metrics[cache_type].total_latency_ms += latency_ms

        if client_id not in self._client_metrics[cache_type]:
            self._client_metrics[cache_type][client_id] = CacheMetrics(
                cache_type=cache_type
            )
        self._client_metrics[cache_type][client_id].misses += 1

        self._update_latency_histogram(cache_type, latency_ms)

        if self.enable_prometheus:
            CACHE_MISSES.labels(cache_type=cache_type, client_id=client_id).inc()
            CACHE_LATENCY.labels(cache_type=cache_type, operation="get").observe(
                latency_ms / 1000
            )
            self._update_prometheus_hit_rate(cache_type)

    def record_set(
        self,
        cache_type: str,
        latency_ms: float = 0.0,
        size_bytes: int = 0
    ) -> None:
        """
        Record a cache set operation.

        Args:
            cache_type: Type of cache.
            latency_ms: Operation latency in milliseconds.
            size_bytes: Size of cached data in bytes.
        """
        if cache_type not in self._metrics:
            self._metrics[cache_type] = CacheMetrics(cache_type=cache_type)

        self._metrics[cache_type].sets += 1
        self._metrics[cache_type].operation_count += 1
        self._metrics[cache_type].total_latency_ms += latency_ms
        self._metrics[cache_type].memory_bytes += size_bytes
        self._metrics[cache_type].entry_count += 1

        self._update_latency_histogram(cache_type, latency_ms)

        if self.enable_prometheus:
            CACHE_LATENCY.labels(cache_type=cache_type, operation="set").observe(
                latency_ms / 1000
            )
            CACHE_ENTRIES.labels(cache_type=cache_type).inc()
            CACHE_MEMORY.labels(cache_type=cache_type).inc(size_bytes)

    def record_delete(
        self,
        cache_type: str,
        latency_ms: float = 0.0,
        size_bytes: int = 0
    ) -> None:
        """
        Record a cache delete operation.

        Args:
            cache_type: Type of cache.
            latency_ms: Operation latency in milliseconds.
            size_bytes: Size of deleted data in bytes.
        """
        if cache_type not in self._metrics:
            self._metrics[cache_type] = CacheMetrics(cache_type=cache_type)

        self._metrics[cache_type].deletes += 1
        self._metrics[cache_type].operation_count += 1
        self._metrics[cache_type].total_latency_ms += latency_ms
        self._metrics[cache_type].memory_bytes -= size_bytes
        self._metrics[cache_type].entry_count -= 1

        self._update_latency_histogram(cache_type, latency_ms)

        if self.enable_prometheus:
            CACHE_LATENCY.labels(cache_type=cache_type, operation="delete").observe(
                latency_ms / 1000
            )
            CACHE_ENTRIES.labels(cache_type=cache_type).dec()
            CACHE_MEMORY.labels(cache_type=cache_type).dec(size_bytes)

    def record_eviction(
        self,
        cache_type: str,
        reason: str = "ttl_expired",
        size_bytes: int = 0
    ) -> None:
        """
        Record a cache eviction.

        Args:
            cache_type: Type of cache.
            reason: Reason for eviction.
            size_bytes: Size of evicted data in bytes.
        """
        if cache_type not in self._metrics:
            self._metrics[cache_type] = CacheMetrics(cache_type=cache_type)

        self._metrics[cache_type].evictions += 1
        self._metrics[cache_type].memory_bytes -= size_bytes
        self._metrics[cache_type].entry_count -= 1

        if self.enable_prometheus:
            CACHE_EVICTIONS.labels(cache_type=cache_type, reason=reason).inc()
            CACHE_ENTRIES.labels(cache_type=cache_type).dec()
            CACHE_MEMORY.labels(cache_type=cache_type).dec(size_bytes)

    def _update_latency_histogram(
        self,
        cache_type: str,
        latency_ms: float
    ) -> None:
        """
        Update latency histogram.

        Args:
            cache_type: Type of cache.
            latency_ms: Latency in milliseconds.
        """
        if cache_type not in self._latency_histograms:
            self._latency_histograms[cache_type] = [
                LatencyBucket(threshold_ms=threshold)
                for threshold in self.LATENCY_BUCKETS
            ]

        for bucket in self._latency_histograms[cache_type]:
            if latency_ms <= bucket.threshold_ms:
                bucket.count += 1

    def _update_prometheus_hit_rate(self, cache_type: str) -> None:
        """Update Prometheus hit rate gauge."""
        if cache_type in self._metrics:
            hit_rate = self._metrics[cache_type].hit_rate
            CACHE_HIT_RATE.labels(cache_type=cache_type).set(hit_rate)

    def get_metrics(self, cache_type: str) -> Optional[CacheMetrics]:
        """
        Get metrics for a cache type.

        Args:
            cache_type: Type of cache.

        Returns:
            CacheMetrics or None.
        """
        return self._metrics.get(cache_type)

    def get_all_metrics(self) -> Dict[str, CacheMetrics]:
        """
        Get all cache metrics.

        Returns:
            Dictionary of cache metrics.
        """
        return dict(self._metrics)

    def get_client_metrics(
        self,
        cache_type: str,
        client_id: str
    ) -> Optional[CacheMetrics]:
        """
        Get metrics for a specific client.

        Args:
            cache_type: Type of cache.
            client_id: Client/tenant ID.

        Returns:
            CacheMetrics or None.
        """
        return self._client_metrics[cache_type].get(client_id)

    def get_latency_percentile(
        self,
        cache_type: str,
        percentile: float
    ) -> Optional[float]:
        """
        Get latency at a specific percentile.

        Args:
            cache_type: Type of cache.
            percentile: Percentile (0-100).

        Returns:
            Latency in milliseconds or None.
        """
        if cache_type not in self._latency_histograms:
            return None

        total_count = sum(
            bucket.count for bucket in self._latency_histograms[cache_type]
        )
        if total_count == 0:
            return None

        target_count = total_count * (percentile / 100)
        cumulative = 0

        for bucket in self._latency_histograms[cache_type]:
            cumulative += bucket.count
            if cumulative >= target_count:
                return bucket.threshold_ms

        return self._latency_histograms[cache_type][-1].threshold_ms

    def get_report(self) -> Dict[str, Any]:
        """
        Generate a comprehensive metrics report.

        Returns:
            Dictionary with metrics report.
        """
        report = {
            "caches": {},
            "overall": {
                "total_hits": 0,
                "total_misses": 0,
                "overall_hit_rate": 0.0,
            }
        }

        total_hits = 0
        total_misses = 0

        for cache_type, metrics in self._metrics.items():
            report["caches"][cache_type] = {
                "hits": metrics.hits,
                "misses": metrics.misses,
                "hit_rate": round(metrics.hit_rate * 100, 2),
                "avg_latency_ms": round(metrics.avg_latency_ms, 3),
                "memory_bytes": metrics.memory_bytes,
                "entry_count": metrics.entry_count,
                "evictions": metrics.evictions,
                "p50_latency_ms": self.get_latency_percentile(cache_type, 50),
                "p95_latency_ms": self.get_latency_percentile(cache_type, 95),
                "p99_latency_ms": self.get_latency_percentile(cache_type, 99),
            }

            total_hits += metrics.hits
            total_misses += metrics.misses

        report["overall"]["total_hits"] = total_hits
        report["overall"]["total_misses"] = total_misses

        total = total_hits + total_misses
        if total > 0:
            report["overall"]["overall_hit_rate"] = round(
                (total_hits / total) * 100, 2
            )

        return report

    def reset(self) -> None:
        """Reset all metrics."""
        self._metrics.clear()
        self._latency_histograms.clear()
        self._client_metrics.clear()


# Global metrics collector
_collector: Optional[CacheMetricsCollector] = None


def get_cache_metrics() -> CacheMetricsCollector:
    """Get the global cache metrics collector."""
    global _collector
    if _collector is None:
        _collector = CacheMetricsCollector()
    return _collector


__all__ = [
    "CacheMetrics",
    "LatencyBucket",
    "CacheMetricsCollector",
    "get_cache_metrics",
]
