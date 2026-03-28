"""Webhook Analytics - Delivery Metrics and Monitoring"""
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

@dataclass
class DeliveryMetrics:
    webhook_id: str
    total_deliveries: int = 0
    successful_deliveries: int = 0
    failed_deliveries: int = 0
    total_latency_ms: float = 0
    last_delivery: Optional[datetime] = None

    @property
    def success_rate(self) -> float:
        return (self.successful_deliveries / self.total_deliveries * 100) if self.total_deliveries > 0 else 100.0

    @property
    def average_latency_ms(self) -> float:
        return self.total_latency_ms / self.total_deliveries if self.total_deliveries > 0 else 0

class WebhookAnalytics:
    def __init__(self):
        self._webhook_metrics: Dict[str, DeliveryMetrics] = {}
        self._hourly_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"total": 0, "success": 0, "failed": 0, "latency": []})
        self._daily_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"total": 0, "success": 0, "failed": 0})
        self._latency_history: List[float] = []
        self._max_latency_history = 10000

    def record_delivery(self, webhook_id: str, success: bool, latency_ms: float) -> None:
        if webhook_id not in self._webhook_metrics:
            self._webhook_metrics[webhook_id] = DeliveryMetrics(webhook_id=webhook_id)

        metrics = self._webhook_metrics[webhook_id]
        metrics.total_deliveries += 1
        metrics.total_latency_ms += latency_ms
        metrics.last_delivery = datetime.utcnow()

        if success:
            metrics.successful_deliveries += 1
        else:
            metrics.failed_deliveries += 1

        self._latency_history.append(latency_ms)
        if len(self._latency_history) > self._max_latency_history:
            self._latency_history.pop(0)

        hour_key = datetime.utcnow().strftime("%Y-%m-%d-%H")
        self._hourly_stats[hour_key]["total"] += 1
        self._hourly_stats[hour_key]["latency"].append(latency_ms)
        if success:
            self._hourly_stats[hour_key]["success"] += 1
        else:
            self._hourly_stats[hour_key]["failed"] += 1

        day_key = datetime.utcnow().strftime("%Y-%m-%d")
        self._daily_stats[day_key]["total"] += 1
        if success:
            self._daily_stats[day_key]["success"] += 1
        else:
            self._daily_stats[day_key]["failed"] += 1

    def get_webhook_metrics(self, webhook_id: str) -> Optional[Dict[str, Any]]:
        metrics = self._webhook_metrics.get(webhook_id)
        if not metrics:
            return None
        return {
            "webhook_id": webhook_id,
            "total_deliveries": metrics.total_deliveries,
            "successful_deliveries": metrics.successful_deliveries,
            "failed_deliveries": metrics.failed_deliveries,
            "success_rate": round(metrics.success_rate, 2),
            "average_latency_ms": round(metrics.average_latency_ms, 2),
            "last_delivery": metrics.last_delivery.isoformat() if metrics.last_delivery else None
        }

    def get_all_metrics(self) -> Dict[str, Any]:
        total_deliveries = sum(m.total_deliveries for m in self._webhook_metrics.values())
        successful = sum(m.successful_deliveries for m in self._webhook_metrics.values())
        failed = sum(m.failed_deliveries for m in self._webhook_metrics.values())

        return {
            "total_webhooks": len(self._webhook_metrics),
            "total_deliveries": total_deliveries,
            "successful_deliveries": successful,
            "failed_deliveries": failed,
            "overall_success_rate": round((successful / total_deliveries * 100) if total_deliveries > 0 else 100, 2)
        }

    def get_latency_stats(self) -> Dict[str, float]:
        if not self._latency_history:
            return {"avg": 0, "min": 0, "max": 0, "p50": 0, "p95": 0, "p99": 0}

        sorted_latencies = sorted(self._latency_history)
        count = len(sorted_latencies)

        return {
            "avg": round(sum(sorted_latencies) / count, 2),
            "min": round(sorted_latencies[0], 2),
            "max": round(sorted_latencies[-1], 2),
            "p50": round(sorted_latencies[int(count * 0.5)], 2),
            "p95": round(sorted_latencies[int(count * 0.95)], 2),
            "p99": round(sorted_latencies[int(count * 0.99)], 2)
        }

    def get_hourly_stats(self, hours: int = 24) -> Dict[str, Any]:
        result = {}
        now = datetime.utcnow()
        for i in range(hours):
            hour = (now - timedelta(hours=i)).strftime("%Y-%m-%d-%H")
            if hour in self._hourly_stats:
                stats = self._hourly_stats[hour]
                latencies = stats.get("latency", [])
                result[hour] = {
                    "total": stats["total"],
                    "success": stats["success"],
                    "failed": stats["failed"],
                    "avg_latency": round(sum(latencies) / len(latencies), 2) if latencies else 0
                }
        return result

    def get_daily_stats(self, days: int = 7) -> Dict[str, Any]:
        result = {}
        now = datetime.utcnow()
        for i in range(days):
            day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
            if day in self._daily_stats:
                result[day] = self._daily_stats[day]
        return result

    def get_failing_webhooks(self, threshold: float = 50.0) -> List[Dict[str, Any]]:
        failing = []
        for webhook_id, metrics in self._webhook_metrics.items():
            if metrics.success_rate < threshold:
                failing.append({
                    "webhook_id": webhook_id,
                    "success_rate": round(metrics.success_rate, 2),
                    "total_deliveries": metrics.total_deliveries,
                    "failed_deliveries": metrics.failed_deliveries
                })
        return sorted(failing, key=lambda x: x["success_rate"])

    def clear_metrics(self) -> int:
        count = len(self._webhook_metrics)
        self._webhook_metrics.clear()
        self._hourly_stats.clear()
        self._daily_stats.clear()
        self._latency_history.clear()
        return count
