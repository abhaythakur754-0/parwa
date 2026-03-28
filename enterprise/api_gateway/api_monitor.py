"""API Monitor - Metrics collection and analysis"""
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import logging
import time
import threading
from collections import defaultdict

logger = logging.getLogger(__name__)

@dataclass
class RequestMetric:
    request_id: str
    endpoint: str
    method: str
    status_code: int
    latency_ms: float
    timestamp: float = field(default_factory=time.time)
    tenant_id: Optional[str] = None
    error: Optional[str] = None

class APIMonitor:
    def __init__(self, max_metrics: int = 10000):
        self.max_metrics = max_metrics
        self._metrics: List[RequestMetric] = []
        self._lock = threading.Lock()
        self._endpoint_stats: Dict[str, Dict] = defaultdict(lambda: {"count": 0, "total_latency": 0, "errors": 0, "status_codes": defaultdict(int)})
        self._hourly_stats: Dict[str, Dict] = defaultdict(lambda: {"requests": 0, "errors": 0, "total_latency": 0})

    def record_request(self, request_id: str, endpoint: str, method: str, status_code: int, latency_ms: float, tenant_id: str = None, error: str = None) -> None:
        metric = RequestMetric(
            request_id=request_id,
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            latency_ms=latency_ms,
            tenant_id=tenant_id,
            error=error
        )

        with self._lock:
            self._metrics.append(metric)
            if len(self._metrics) > self.max_metrics:
                self._metrics.pop(0)

            stats = self._endpoint_stats[endpoint]
            stats["count"] += 1
            stats["total_latency"] += latency_ms
            if error:
                stats["errors"] += 1
            stats["status_codes"][status_code] += 1

            hour_key = datetime.utcnow().strftime("%Y-%m-%d-%H")
            hourly = self._hourly_stats[hour_key]
            hourly["requests"] += 1
            hourly["total_latency"] += latency_ms
            if error:
                hourly["errors"] += 1

    def get_metrics(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                {
                    "request_id": m.request_id,
                    "endpoint": m.endpoint,
                    "method": m.method,
                    "status_code": m.status_code,
                    "latency_ms": m.latency_ms,
                    "timestamp": m.timestamp,
                    "tenant_id": m.tenant_id,
                    "error": m.error
                }
                for m in self._metrics[-limit:]
            ]

    def get_endpoint_stats(self, endpoint: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            if endpoint:
                stats = self._endpoint_stats.get(endpoint, {})
                return {
                    "endpoint": endpoint,
                    "count": stats.get("count", 0),
                    "avg_latency_ms": round(stats.get("total_latency", 0) / stats.get("count", 1), 2) if stats.get("count", 0) > 0 else 0,
                    "errors": stats.get("errors", 0),
                    "error_rate": round(stats.get("errors", 0) / stats.get("count", 1) * 100, 2) if stats.get("count", 0) > 0 else 0,
                    "status_codes": dict(stats.get("status_codes", {}))
                }
            else:
                result = {}
                for ep, stats in self._endpoint_stats.items():
                    result[ep] = {
                        "count": stats["count"],
                        "avg_latency_ms": round(stats["total_latency"] / stats["count"], 2) if stats["count"] > 0 else 0,
                        "errors": stats["errors"],
                        "error_rate": round(stats["errors"] / stats["count"] * 100, 2) if stats["count"] > 0 else 0
                    }
                return result

    def get_latency_stats(self) -> Dict[str, Any]:
        with self._lock:
            if not self._metrics:
                return {"avg": 0, "min": 0, "max": 0, "p50": 0, "p95": 0, "p99": 0}

            latencies = sorted([m.latency_ms for m in self._metrics])
            count = len(latencies)

            return {
                "avg": round(sum(latencies) / count, 2),
                "min": latencies[0],
                "max": latencies[-1],
                "p50": latencies[int(count * 0.5)] if count > 0 else 0,
                "p95": latencies[int(count * 0.95)] if count > 0 else 0,
                "p99": latencies[int(count * 0.99)] if count > 0 else 0
            }

    def get_hourly_stats(self, hours: int = 24) -> Dict[str, Any]:
        with self._lock:
            result = {}
            now = datetime.utcnow()
            for i in range(hours):
                hour = (now - timedelta(hours=i)).strftime("%Y-%m-%d-%H")
                if hour in self._hourly_stats:
                    stats = self._hourly_stats[hour]
                    result[hour] = {
                        "requests": stats["requests"],
                        "errors": stats["errors"],
                        "avg_latency": round(stats["total_latency"] / stats["requests"], 2) if stats["requests"] > 0 else 0
                    }
            return result

    def get_summary(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._metrics)
            errors = sum(1 for m in self._metrics if m.error)
            latencies = [m.latency_ms for m in self._metrics]

            return {
                "total_requests": total,
                "total_errors": errors,
                "error_rate": round(errors / total * 100, 2) if total > 0 else 0,
                "avg_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else 0,
                "unique_endpoints": len(self._endpoint_stats),
                "unique_tenants": len(set(m.tenant_id for m in self._metrics if m.tenant_id))
            }

    def clear_metrics(self) -> int:
        with self._lock:
            count = len(self._metrics)
            self._metrics.clear()
            self._endpoint_stats.clear()
            self._hourly_stats.clear()
            return count
