"""API Monitor - Metrics collection and monitoring for API Gateway"""
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
import logging
import time
import threading
from collections import defaultdict
import statistics

logger = logging.getLogger(__name__)


class MetricType(str, Enum):
    """Types of metrics"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class RequestMetric:
    """A single request metric"""
    request_id: str
    endpoint: str
    method: str
    status_code: int
    latency_ms: float
    tenant_id: Optional[str] = None
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EndpointMetrics:
    """Aggregated metrics for an endpoint"""
    endpoint: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_latency_ms: float = 0.0
    latencies: List[float] = field(default_factory=list)
    status_codes: Dict[int, int] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    last_request_time: Optional[datetime] = None


@dataclass
class LatencyStats:
    """Latency statistics"""
    min_ms: float = 0.0
    max_ms: float = 0.0
    avg_ms: float = 0.0
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0


class APIMonitor:
    """
    API Monitor for collecting and analyzing API metrics.

    Features:
    - Request counting by endpoint
    - Latency tracking and percentiles
    - Error tracking and categorization
    - Status code distribution
    - Tenant-specific metrics
    - Real-time statistics
    """

    def __init__(
        self,
        name: str = "api-monitor",
        max_latency_samples: int = 1000,
        retention_hours: int = 24
    ):
        self.name = name
        self.max_latency_samples = max_latency_samples
        self.retention_hours = retention_hours

        # Endpoint metrics
        self._endpoint_metrics: Dict[str, EndpointMetrics] = defaultdict(
            lambda: EndpointMetrics(endpoint="unknown")
        )

        # Recent requests for time-based queries
        self._recent_requests: List[RequestMetric] = []

        # Global metrics
        self._global_metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_latency_ms": 0.0
        }

        # Tenant-specific metrics
        self._tenant_metrics: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "total_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "total_latency_ms": 0.0
            }
        )

        self._lock = threading.Lock()

        logger.info(f"API Monitor '{name}' initialized")

    def record_request(
        self,
        request_id: str,
        endpoint: str,
        method: str,
        status_code: int,
        latency_ms: float,
        tenant_id: Optional[str] = None,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Record a request metric.

        Args:
            request_id: Unique request identifier
            endpoint: API endpoint path
            method: HTTP method
            status_code: Response status code
            latency_ms: Request latency in milliseconds
            tenant_id: Optional tenant identifier
            error: Optional error message
            metadata: Optional additional metadata
        """
        metric = RequestMetric(
            request_id=request_id,
            endpoint=endpoint,
            method=method.upper(),
            status_code=status_code,
            latency_ms=latency_ms,
            tenant_id=tenant_id,
            error=error,
            metadata=metadata or {}
        )

        with self._lock:
            # Update global metrics
            self._global_metrics["total_requests"] += 1
            self._global_metrics["total_latency_ms"] += latency_ms

            if 200 <= status_code < 400:
                self._global_metrics["successful_requests"] += 1
            else:
                self._global_metrics["failed_requests"] += 1

            # Update endpoint metrics
            ep_metrics = self._endpoint_metrics[endpoint]
            ep_metrics.endpoint = endpoint
            ep_metrics.total_requests += 1
            ep_metrics.total_latency_ms += latency_ms
            ep_metrics.last_request_time = datetime.utcnow()

            if 200 <= status_code < 400:
                ep_metrics.successful_requests += 1
            else:
                ep_metrics.failed_requests += 1
                if error:
                    ep_metrics.errors.append(error)
                    # Keep only recent errors
                    if len(ep_metrics.errors) > 100:
                        ep_metrics.errors = ep_metrics.errors[-100:]

            # Track status codes
            ep_metrics.status_codes[status_code] = ep_metrics.status_codes.get(status_code, 0) + 1

            # Track latencies (with sample limit)
            ep_metrics.latencies.append(latency_ms)
            if len(ep_metrics.latencies) > self.max_latency_samples:
                ep_metrics.latencies = ep_metrics.latencies[-self.max_latency_samples:]

            # Update tenant metrics
            if tenant_id:
                self._tenant_metrics[tenant_id]["total_requests"] += 1
                self._tenant_metrics[tenant_id]["total_latency_ms"] += latency_ms
                if 200 <= status_code < 400:
                    self._tenant_metrics[tenant_id]["successful_requests"] += 1
                else:
                    self._tenant_metrics[tenant_id]["failed_requests"] += 1

            # Add to recent requests
            self._recent_requests.append(metric)

            # Cleanup old requests based on retention
            self._cleanup_old_requests()

    def get_metrics(self, endpoint: Optional[str] = None) -> Dict[str, Any]:
        """
        Get metrics (optionally for a specific endpoint).

        Args:
            endpoint: Optional endpoint to filter by

        Returns:
            Dictionary of metrics
        """
        with self._lock:
            if endpoint:
                if endpoint in self._endpoint_metrics:
                    ep = self._endpoint_metrics[endpoint]
                    return {
                        "endpoint": endpoint,
                        "total_requests": ep.total_requests,
                        "successful_requests": ep.successful_requests,
                        "failed_requests": ep.failed_requests,
                        "success_rate": (
                            ep.successful_requests / ep.total_requests * 100
                            if ep.total_requests > 0 else 100
                        ),
                        "status_codes": dict(ep.status_codes),
                        "error_count": len(ep.errors),
                        "last_request_time": ep.last_request_time.isoformat() if ep.last_request_time else None
                    }
                return {}

            # Return all metrics
            return {
                "global": dict(self._global_metrics),
                "endpoints": {
                    ep: {
                        "total_requests": m.total_requests,
                        "successful_requests": m.successful_requests,
                        "failed_requests": m.failed_requests,
                        "success_rate": (
                            m.successful_requests / m.total_requests * 100
                            if m.total_requests > 0 else 100
                        )
                    }
                    for ep, m in self._endpoint_metrics.items()
                },
                "tenants": dict(self._tenant_metrics)
            }

    def get_latency_stats(self, endpoint: Optional[str] = None) -> LatencyStats:
        """
        Get latency statistics.

        Args:
            endpoint: Optional endpoint to filter by

        Returns:
            LatencyStats with min, max, avg, and percentiles
        """
        with self._lock:
            latencies = []

            if endpoint:
                if endpoint in self._endpoint_metrics:
                    latencies = self._endpoint_metrics[endpoint].latencies
            else:
                # Combine all latencies
                for ep_metrics in self._endpoint_metrics.values():
                    latencies.extend(ep_metrics.latencies)

            if not latencies:
                return LatencyStats()

            sorted_latencies = sorted(latencies)
            n = len(sorted_latencies)

            return LatencyStats(
                min_ms=sorted_latencies[0],
                max_ms=sorted_latencies[-1],
                avg_ms=statistics.mean(sorted_latencies),
                p50_ms=sorted_latencies[int(n * 0.50)] if n > 0 else 0,
                p95_ms=sorted_latencies[int(n * 0.95)] if n > 0 else 0,
                p99_ms=sorted_latencies[int(n * 0.99)] if n > 0 else 0
            )

    def get_error_summary(self, endpoint: Optional[str] = None) -> Dict[str, Any]:
        """
        Get error summary.

        Args:
            endpoint: Optional endpoint to filter by

        Returns:
            Dictionary with error counts and recent errors
        """
        with self._lock:
            if endpoint:
                if endpoint in self._endpoint_metrics:
                    ep = self._endpoint_metrics[endpoint]
                    return {
                        "endpoint": endpoint,
                        "total_errors": ep.failed_requests,
                        "error_rate": (
                            ep.failed_requests / ep.total_requests * 100
                            if ep.total_requests > 0 else 0
                        ),
                        "recent_errors": ep.errors[-10:],
                        "status_codes": dict(ep.status_codes)
                    }
                return {}

            # Aggregate across all endpoints
            total_errors = sum(
                ep.failed_requests for ep in self._endpoint_metrics.values()
            )
            total_requests = sum(
                ep.total_requests for ep in self._endpoint_metrics.values()
            )

            all_errors = []
            for ep in self._endpoint_metrics.values():
                all_errors.extend(ep.errors)

            return {
                "total_errors": total_errors,
                "error_rate": (total_errors / total_requests * 100) if total_requests > 0 else 0,
                "recent_errors": all_errors[-20:],
                "endpoints_with_errors": [
                    ep for ep, m in self._endpoint_metrics.items()
                    if m.failed_requests > 0
                ]
            }

    def get_tenant_metrics(self, tenant_id: str) -> Dict[str, Any]:
        """
        Get metrics for a specific tenant.

        Args:
            tenant_id: Tenant identifier

        Returns:
            Dictionary of tenant metrics
        """
        with self._lock:
            if tenant_id in self._tenant_metrics:
                metrics = self._tenant_metrics[tenant_id]
                return {
                    "tenant_id": tenant_id,
                    **metrics,
                    "success_rate": (
                        metrics["successful_requests"] / metrics["total_requests"] * 100
                        if metrics["total_requests"] > 0 else 100
                    ),
                    "avg_latency_ms": (
                        metrics["total_latency_ms"] / metrics["total_requests"]
                        if metrics["total_requests"] > 0 else 0
                    )
                }
            return {"tenant_id": tenant_id, "total_requests": 0}

    def get_recent_requests(
        self,
        limit: int = 100,
        endpoint: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get recent requests.

        Args:
            limit: Maximum number of requests to return
            endpoint: Optional endpoint filter
            tenant_id: Optional tenant filter

        Returns:
            List of request dictionaries
        """
        with self._lock:
            requests = self._recent_requests

            if endpoint:
                requests = [r for r in requests if r.endpoint == endpoint]
            if tenant_id:
                requests = [r for r in requests if r.tenant_id == tenant_id]

            return [
                {
                    "request_id": r.request_id,
                    "endpoint": r.endpoint,
                    "method": r.method,
                    "status_code": r.status_code,
                    "latency_ms": r.latency_ms,
                    "tenant_id": r.tenant_id,
                    "error": r.error,
                    "timestamp": r.timestamp.isoformat()
                }
                for r in requests[-limit:]
            ]

    def get_top_endpoints(self, by: str = "requests", limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get top endpoints by metric.

        Args:
            by: Metric to sort by ('requests', 'latency', 'errors')
            limit: Maximum number of endpoints to return

        Returns:
            List of endpoint dictionaries
        """
        with self._lock:
            endpoints = list(self._endpoint_metrics.values())

            if by == "requests":
                endpoints.sort(key=lambda x: x.total_requests, reverse=True)
            elif by == "latency":
                endpoints.sort(
                    key=lambda x: x.total_latency_ms / x.total_requests if x.total_requests > 0 else 0,
                    reverse=True
                )
            elif by == "errors":
                endpoints.sort(key=lambda x: x.failed_requests, reverse=True)

            return [
                {
                    "endpoint": ep.endpoint,
                    "total_requests": ep.total_requests,
                    "successful_requests": ep.successful_requests,
                    "failed_requests": ep.failed_requests,
                    "avg_latency_ms": ep.total_latency_ms / ep.total_requests if ep.total_requests > 0 else 0
                }
                for ep in endpoints[:limit]
            ]

    def _cleanup_old_requests(self) -> None:
        """Remove requests older than retention period"""
        cutoff = datetime.utcnow() - timedelta(hours=self.retention_hours)
        self._recent_requests = [
            r for r in self._recent_requests if r.timestamp > cutoff
        ]

    def reset_metrics(self, endpoint: Optional[str] = None) -> None:
        """Reset metrics (optionally for a specific endpoint)"""
        with self._lock:
            if endpoint:
                if endpoint in self._endpoint_metrics:
                    self._endpoint_metrics[endpoint] = EndpointMetrics(endpoint=endpoint)
            else:
                self._endpoint_metrics.clear()
                self._tenant_metrics.clear()
                self._recent_requests.clear()
                self._global_metrics = {
                    "total_requests": 0,
                    "successful_requests": 0,
                    "failed_requests": 0,
                    "total_latency_ms": 0.0
                }
        logger.info(f"Reset metrics for: {endpoint or 'all'}")

    def get_health(self) -> Dict[str, Any]:
        """Get monitor health status"""
        with self._lock:
            total = self._global_metrics["total_requests"]
            success_rate = (
                self._global_metrics["successful_requests"] / total * 100
                if total > 0 else 100
            )

            # Determine health status
            if success_rate >= 99:
                status = "healthy"
            elif success_rate >= 95:
                status = "degraded"
            else:
                status = "unhealthy"

            return {
                "status": status,
                "success_rate": round(success_rate, 2),
                "total_requests": total,
                "endpoints_monitored": len(self._endpoint_metrics),
                "tenants_monitored": len(self._tenant_metrics),
                "recent_requests_count": len(self._recent_requests)
            }
