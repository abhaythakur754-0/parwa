"""Month 4 Monitoring Metrics — Real-time dashboard data.

Tracks accuracy, resolution rate, escalation rate, and per-variant
performance metrics. Used by the batch test runner to generate reports.
"""
from __future__ import annotations

import threading
from typing import Any
from collections import defaultdict


class MetricsCollector:
    """Collects and aggregates pipeline metrics for monitoring dashboard."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tickets: list[dict[str, Any]] = []
        self._variant_stats: dict[str, dict[str, Any]] = defaultdict(lambda: {
            "total": 0,
            "intent_correct": 0,
            "sentiment_correct": 0,
            "escalation_correct": 0,
            "action_correct": 0,
            "autonomous_resolution": 0,
            "total_confidence": 0.0,
            "total_quality": 0.0,
            "total_tokens": 0,
            "total_time_ms": 0,
        })

    def record_ticket(self, result: dict[str, Any]) -> None:
        """Record a single ticket result."""
        with self._lock:
            self._tickets.append(result)
            variant = result.get("variant", "parwa")
            stats = self._variant_stats[variant]
            stats["total"] += 1

            if result.get("intent_correct"):
                stats["intent_correct"] += 1
            if result.get("sentiment_correct"):
                stats["sentiment_correct"] += 1
            if result.get("escalation_correct"):
                stats["escalation_correct"] += 1
            if result.get("action_correct"):
                stats["action_correct"] += 1
            if result.get("autonomous_resolution"):
                stats["autonomous_resolution"] += 1
            stats["total_confidence"] += result.get("intent_confidence", 0)
            stats["total_quality"] += result.get("quality_score", 0)
            stats["total_tokens"] += result.get("total_tokens", 0)
            stats["total_time_ms"] += result.get("time_ms", 0)

    def get_dashboard(self) -> dict[str, Any]:
        """Get current metrics dashboard data."""
        with self._lock:
            dashboard = {}
            for variant, stats in self._variant_stats.items():
                total = stats["total"]
                if total == 0:
                    continue
                dashboard[variant] = {
                    "total_tickets": total,
                    "intent_accuracy": round(stats["intent_correct"] / total * 100, 1),
                    "sentiment_accuracy": round(stats["sentiment_correct"] / total * 100, 1),
                    "escalation_accuracy": round(stats["escalation_correct"] / total * 100, 1),
                    "action_accuracy": round(stats["action_correct"] / total * 100, 1),
                    "autonomous_resolution_rate": round(stats["autonomous_resolution"] / total * 100, 1),
                    "avg_confidence": round(stats["total_confidence"] / total, 3),
                    "avg_quality_score": round(stats["total_quality"] / total, 3),
                    "total_tokens_used": stats["total_tokens"],
                    "avg_time_ms": round(stats["total_time_ms"] / total, 0),
                }
            return dashboard

    def get_per_ticket_details(self) -> list[dict[str, Any]]:
        """Get per-ticket details for all recorded tickets."""
        with self._lock:
            return list(self._tickets)

    def reset(self) -> None:
        """Reset all metrics."""
        with self._lock:
            self._tickets.clear()
            self._variant_stats.clear()


# Global singleton
_collector: MetricsCollector | None = None


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector."""
    global _collector
    if _collector is None:
        _collector = MetricsCollector()
    return _collector
