"""AgentMetrics — Per-agent performance tracking and reporting.

Tracks and reports metrics for each of the 6 agents:
  - Tickets processed count
  - Average latency per agent
  - Technique usage frequency
  - Error rate
  - Confidence score averages

AgentMetrics is designed to be a singleton that accumulates metrics
across ALL tickets (not per-ticket). This enables dashboard-style
monitoring and alerting in production.

Usage:
    metrics = get_agent_metrics()
    metrics.record_agent_run("Knowledge Agent", context)
    report = metrics.summary()
    # {"Knowledge Agent": {"total_runs": 50, "avg_latency_ms": 120, ...}}
"""

from __future__ import annotations

import logging
import threading
from typing import Any

logger = logging.getLogger("parwa.agents.metrics")


class AgentMetrics:
    """Thread-safe per-agent metrics accumulator.

    Tracks aggregate performance metrics across all tickets processed
    by each agent. Designed for production monitoring dashboards.

    Thread Safety:
        All operations are protected by a threading lock to ensure
        safe concurrent access from multiple ticket processing threads.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data: dict[str, dict[str, Any]] = {}
        self._initialize_all_agents()

    def _initialize_all_agents(self) -> None:
        """Initialize metrics storage for all 6 agents."""
        for name in [
            "Router Agent",
            "Knowledge Agent",
            "Reasoning Agent",
            "Action Agent",
            "Compliance Agent",
            "Proactive Agent",
        ]:
            self._data[name] = {
                "total_runs": 0,
                "total_latency_ms": 0.0,
                "avg_latency_ms": 0.0,
                "min_latency_ms": float("inf"),
                "max_latency_ms": 0.0,
                "total_errors": 0,
                "error_rate": 0.0,
                "framework_usage": {},
                "confidence_scores": [],
                "avg_confidence": 0.0,
                "node_timings": {},
            }

    def record_agent_run(self, agent_name: str, context: Any) -> None:
        """Record metrics from a completed agent run.

        Args:
            agent_name: The agent's display name.
            context: The AgentContext from the completed run.
        """
        with self._lock:
            if agent_name not in self._data:
                self._data[agent_name] = {
                    "total_runs": 0,
                    "total_latency_ms": 0.0,
                    "avg_latency_ms": 0.0,
                    "min_latency_ms": float("inf"),
                    "max_latency_ms": 0.0,
                    "total_errors": 0,
                    "error_rate": 0.0,
                    "framework_usage": {},
                    "confidence_scores": [],
                    "avg_confidence": 0.0,
                    "node_timings": {},
                }

            d = self._data[agent_name]
            d["total_runs"] += 1

            # Latency tracking
            elapsed = context.elapsed_ms if hasattr(context, "elapsed_ms") else 0.0
            d["total_latency_ms"] += elapsed
            d["avg_latency_ms"] = d["total_latency_ms"] / d["total_runs"]
            if elapsed < d["min_latency_ms"]:
                d["min_latency_ms"] = elapsed
            if elapsed > d["max_latency_ms"]:
                d["max_latency_ms"] = elapsed

            # Error tracking
            error_count = context.error_count if hasattr(context, "error_count") else 0
            d["total_errors"] += error_count
            d["error_rate"] = d["total_errors"] / d["total_runs"]

            # Framework usage tracking
            frameworks = context.frameworks_used if hasattr(context, "frameworks_used") else []
            for fw in frameworks:
                d["framework_usage"][fw] = d["framework_usage"].get(fw, 0) + 1

            # Node timing tracking
            node_timings = context.node_timings if hasattr(context, "node_timings") else {}
            for node_name, timing in node_timings.items():
                if node_name not in d["node_timings"]:
                    d["node_timings"][node_name] = {
                        "total_ms": 0.0,
                        "count": 0,
                        "avg_ms": 0.0,
                    }
                d["node_timings"][node_name]["total_ms"] += timing
                d["node_timings"][node_name]["count"] += 1
                d["node_timings"][node_name]["avg_ms"] = (
                    d["node_timings"][node_name]["total_ms"]
                    / d["node_timings"][node_name]["count"]
                )

            logger.debug(
                "AgentMetrics: recorded %s run #%d (%.1fms, %d errors, %d frameworks)",
                agent_name, d["total_runs"], elapsed, error_count, len(frameworks),
            )

    def record_confidence(self, agent_name: str, confidence: float) -> None:
        """Record a confidence score for an agent.

        Args:
            agent_name: The agent's display name.
            confidence: Confidence score (0.0 to 1.0).
        """
        with self._lock:
            if agent_name not in self._data:
                return
            d = self._data[agent_name]
            d["confidence_scores"].append(confidence)
            # Keep last 1000 scores to avoid unbounded memory
            if len(d["confidence_scores"]) > 1000:
                d["confidence_scores"] = d["confidence_scores"][-1000:]
            d["avg_confidence"] = sum(d["confidence_scores"]) / len(d["confidence_scores"])

    def get_agent_metrics(self, agent_name: str) -> dict[str, Any]:
        """Get metrics for a specific agent."""
        with self._lock:
            return dict(self._data.get(agent_name, {}))

    def summary(self) -> dict[str, dict[str, Any]]:
        """Get a summary of all agent metrics.

        Returns:
            Dict mapping agent names to their metric summaries.
        """
        with self._lock:
            result = {}
            for name, data in self._data.items():
                result[name] = {
                    "total_runs": data["total_runs"],
                    "avg_latency_ms": round(data["avg_latency_ms"], 2),
                    "min_latency_ms": round(data["min_latency_ms"], 2) if data["min_latency_ms"] != float("inf") else 0.0,
                    "max_latency_ms": round(data["max_latency_ms"], 2),
                    "error_rate": round(data["error_rate"], 4),
                    "avg_confidence": round(data["avg_confidence"], 4),
                    "top_frameworks": sorted(
                        data["framework_usage"].items(),
                        key=lambda x: x[1],
                        reverse=True,
                    )[:5],
                    "total_errors": data["total_errors"],
                }
            return result

    def reset(self) -> None:
        """Reset all metrics (useful for testing)."""
        with self._lock:
            self._data.clear()
            self._initialize_all_agents()


# Singleton instance
_agent_metrics: AgentMetrics | None = None
_metrics_lock = threading.Lock()


def get_agent_metrics() -> AgentMetrics:
    """Get or create the singleton AgentMetrics instance."""
    global _agent_metrics
    if _agent_metrics is None:
        with _metrics_lock:
            if _agent_metrics is None:
                _agent_metrics = AgentMetrics()
    return _agent_metrics


def reset_agent_metrics() -> None:
    """Reset the singleton metrics instance (for testing)."""
    global _agent_metrics
    with _metrics_lock:
        _agent_metrics = None
