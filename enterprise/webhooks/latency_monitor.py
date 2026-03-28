# Latency Monitor - Week 47 Builder 5
# Delivery latency monitoring and alerting

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
import statistics
import uuid


class LatencyLevel(Enum):
    EXCELLENT = "excellent"  # < 100ms
    GOOD = "good"           # < 500ms
    MODERATE = "moderate"   # < 1000ms
    SLOW = "slow"           # < 3000ms
    CRITICAL = "critical"   # >= 3000ms


@dataclass
class LatencyRecord:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    webhook_id: str = ""
    tenant_id: str = ""
    url: str = ""
    latency_ms: float = 0.0
    level: LatencyLevel = LatencyLevel.GOOD
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class LatencyStats:
    webhook_id: str = ""
    count: int = 0
    min_ms: float = float('inf')
    max_ms: float = 0.0
    avg_ms: float = 0.0
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    std_dev: float = 0.0


@dataclass
class LatencyAlert:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    webhook_id: str = ""
    alert_type: str = ""
    threshold_ms: float = 0.0
    actual_value_ms: float = 0.0
    message: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    acknowledged: bool = False


class LatencyMonitor:
    """Monitors webhook delivery latency"""

    def __init__(self):
        self._records: Dict[str, List[LatencyRecord]] = {}
        self._stats: Dict[str, LatencyStats] = {}
        self._alerts: List[LatencyAlert] = []
        self._alert_callbacks: List[Any] = []
        self._thresholds = {
            "excellent_ms": 100,
            "good_ms": 500,
            "moderate_ms": 1000,
            "slow_ms": 3000,
            "p95_alert_ms": 2000,
            "p99_alert_ms": 5000
        }

    def classify_latency(self, latency_ms: float) -> LatencyLevel:
        """Classify latency into a level"""
        if latency_ms < self._thresholds["excellent_ms"]:
            return LatencyLevel.EXCELLENT
        elif latency_ms < self._thresholds["good_ms"]:
            return LatencyLevel.GOOD
        elif latency_ms < self._thresholds["moderate_ms"]:
            return LatencyLevel.MODERATE
        elif latency_ms < self._thresholds["slow_ms"]:
            return LatencyLevel.SLOW
        return LatencyLevel.CRITICAL

    def record_latency(
        self,
        webhook_id: str,
        tenant_id: str,
        url: str,
        latency_ms: float
    ) -> LatencyRecord:
        """Record a latency measurement"""
        level = self.classify_latency(latency_ms)
        record = LatencyRecord(
            webhook_id=webhook_id,
            tenant_id=tenant_id,
            url=url,
            latency_ms=latency_ms,
            level=level
        )

        if webhook_id not in self._records:
            self._records[webhook_id] = []
        self._records[webhook_id].append(record)

        self._update_stats(webhook_id)
        self._check_alerts(webhook_id, latency_ms)

        return record

    def _update_stats(self, webhook_id: str) -> None:
        """Update latency statistics"""
        records = self._records.get(webhook_id, [])
        if not records:
            return

        latencies = [r.latency_ms for r in records]

        stats = LatencyStats(webhook_id=webhook_id)
        stats.count = len(latencies)
        stats.min_ms = min(latencies)
        stats.max_ms = max(latencies)
        stats.avg_ms = statistics.mean(latencies)

        if len(latencies) >= 2:
            stats.std_dev = statistics.stdev(latencies)

        sorted_latencies = sorted(latencies)
        n = len(sorted_latencies)

        # Percentiles
        stats.p50_ms = sorted_latencies[int(n * 0.5)] if n > 0 else 0
        stats.p95_ms = sorted_latencies[int(n * 0.95)] if n > 0 else 0
        stats.p99_ms = sorted_latencies[int(n * 0.99)] if n > 0 else 0

        self._stats[webhook_id] = stats

    def _check_alerts(self, webhook_id: str, latency_ms: float) -> None:
        """Check if alerts should be triggered"""
        stats = self._stats.get(webhook_id)
        if not stats or stats.count < 10:
            return

        alerts_to_send = []

        # P95 alert
        if stats.p95_ms > self._thresholds["p95_alert_ms"]:
            alert = LatencyAlert(
                webhook_id=webhook_id,
                alert_type="p95_threshold_exceeded",
                threshold_ms=self._thresholds["p95_alert_ms"],
                actual_value_ms=stats.p95_ms,
                message=f"P95 latency ({stats.p95_ms:.0f}ms) exceeds threshold ({self._thresholds['p95_alert_ms']}ms)"
            )
            alerts_to_send.append(alert)

        # P99 alert
        if stats.p99_ms > self._thresholds["p99_alert_ms"]:
            alert = LatencyAlert(
                webhook_id=webhook_id,
                alert_type="p99_threshold_exceeded",
                threshold_ms=self._thresholds["p99_alert_ms"],
                actual_value_ms=stats.p99_ms,
                message=f"P99 latency ({stats.p99_ms:.0f}ms) exceeds threshold ({self._thresholds['p99_alert_ms']}ms)"
            )
            alerts_to_send.append(alert)

        # Critical latency alert
        if latency_ms > self._thresholds["slow_ms"]:
            alert = LatencyAlert(
                webhook_id=webhook_id,
                alert_type="critical_latency",
                threshold_ms=self._thresholds["slow_ms"],
                actual_value_ms=latency_ms,
                message=f"Critical latency detected: {latency_ms:.0f}ms"
            )
            alerts_to_send.append(alert)

        for alert in alerts_to_send:
            self._alerts.append(alert)
            self._notify_callbacks(alert)

    def _notify_callbacks(self, alert: LatencyAlert) -> None:
        """Notify registered callbacks of an alert"""
        for callback in self._alert_callbacks:
            try:
                callback(alert)
            except Exception:
                pass

    def register_alert_callback(self, callback: Any) -> None:
        """Register a callback for latency alerts"""
        self._alert_callbacks.append(callback)

    def set_threshold(self, name: str, value_ms: float) -> None:
        """Set a latency threshold"""
        if name in self._thresholds:
            self._thresholds[name] = value_ms

    def get_stats(self, webhook_id: str) -> Optional[LatencyStats]:
        """Get latency statistics for a webhook"""
        return self._stats.get(webhook_id)

    def get_all_stats(self) -> List[LatencyStats]:
        """Get statistics for all webhooks"""
        return list(self._stats.values())

    def get_slow_webhooks(
        self,
        threshold_ms: float = 1000.0
    ) -> List[LatencyStats]:
        """Get webhooks with average latency above threshold"""
        return [
            stats for stats in self._stats.values()
            if stats.avg_ms > threshold_ms
        ]

    def get_latency_distribution(
        self,
        webhook_id: str
    ) -> Dict[str, int]:
        """Get distribution of latency levels"""
        records = self._records.get(webhook_id, [])
        distribution = {level.value: 0 for level in LatencyLevel}

        for record in records:
            distribution[record.level.value] += 1

        return distribution

    def get_trend(
        self,
        webhook_id: str,
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """Get latency trend over time"""
        records = self._records.get(webhook_id, [])
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        recent = [r for r in records if r.timestamp >= cutoff]

        # Group by hour
        trend = []
        for i in range(hours):
            hour_start = datetime.utcnow() - timedelta(hours=i+1)
            hour_end = datetime.utcnow() - timedelta(hours=i)

            hour_records = [
                r for r in recent
                if hour_start <= r.timestamp < hour_end
            ]

            if hour_records:
                latencies = [r.latency_ms for r in hour_records]
                trend.append({
                    "hour": hour_start.strftime("%Y-%m-%d %H:00"),
                    "avg_ms": statistics.mean(latencies),
                    "min_ms": min(latencies),
                    "max_ms": max(latencies),
                    "count": len(latencies)
                })

        return list(reversed(trend))

    def get_alerts(
        self,
        webhook_id: Optional[str] = None,
        unacknowledged_only: bool = False
    ) -> List[LatencyAlert]:
        """Get latency alerts"""
        alerts = self._alerts

        if webhook_id:
            alerts = [a for a in alerts if a.webhook_id == webhook_id]

        if unacknowledged_only:
            alerts = [a for a in alerts if not a.acknowledged]

        return alerts

    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert"""
        for alert in self._alerts:
            if alert.id == alert_id:
                alert.acknowledged = True
                return True
        return False

    def get_summary(self) -> Dict[str, Any]:
        """Get global latency summary"""
        all_stats = list(self._stats.values())

        if not all_stats:
            return {
                "total_webhooks": 0,
                "global_avg_ms": 0,
                "global_p95_ms": 0,
                "global_p99_ms": 0
            }

        # Calculate global metrics
        all_avgs = [s.avg_ms for s in all_stats]
        all_p95s = [s.p95_ms for s in all_stats]
        all_p99s = [s.p99_ms for s in all_stats]

        return {
            "total_webhooks": len(all_stats),
            "global_avg_ms": statistics.mean(all_avgs),
            "global_p95_ms": statistics.mean(all_p95s) if all_p95s else 0,
            "global_p99_ms": statistics.mean(all_p99s) if all_p99s else 0,
            "slow_webhooks": len(self.get_slow_webhooks()),
            "unacknowledged_alerts": len(self.get_alerts(unacknowledged_only=True)),
            "thresholds": self._thresholds.copy()
        }

    def cleanup_old_records(
        self,
        max_records_per_webhook: int = 10000
    ) -> int:
        """Remove old records to limit memory"""
        removed = 0

        for webhook_id in self._records:
            records = self._records[webhook_id]
            if len(records) > max_records_per_webhook:
                # Keep only most recent
                self._records[webhook_id] = records[-max_records_per_webhook:]
                removed += len(records) - max_records_per_webhook
                self._update_stats(webhook_id)

        return removed
