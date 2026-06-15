"""
Jarvis Monitor — Real-time monitoring of variant pipelines.

The monitor watches ALL variant executions and flags issues:
  - Low confidence responses
  - Quality gate failures
  - Red flags from MAKER validator
  - Ask-when-unsure triggers
  - SLA breaches
  - Unusual patterns (spikes, anomalies)

This is the "eyes" of Jarvis — it sees everything.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.logger import get_logger
from app.core.unified_variant.permission_config import get_permission_config

logger = get_logger("jarvis_monitor")


class MonitoringEvent:
    """A monitoring event captured by Jarvis."""

    def __init__(
        self,
        event_type: str,
        severity: str,
        company_id: str,
        ticket_id: str = "",
        variant_tier: str = "",
        details: Dict[str, Any] = None,
    ):
        self.event_type = event_type
        self.severity = severity
        self.company_id = company_id
        self.ticket_id = ticket_id
        self.variant_tier = variant_tier
        self.details = details or {}
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "severity": self.severity,
            "company_id": self.company_id,
            "ticket_id": self.ticket_id,
            "variant_tier": self.variant_tier,
            "details": self.details,
            "timestamp": self.timestamp,
        }


class JarvisMonitor:
    """Real-time monitor for variant pipeline executions.

    Watches every pipeline execution and generates monitoring events
    for Jarvis to act on. This is how Jarvis has "complete awareness."

    Usage:
        monitor = JarvisMonitor(company_id="comp_123")

        # After variant pipeline runs
        events = monitor.analyze_pipeline_result(pipeline_result)

        # Check for critical events
        critical = monitor.get_critical_events()

        # Get awareness snapshot
        snapshot = monitor.get_awareness_snapshot()
    """

    def __init__(self, company_id: str):
        self.company_id = company_id
        self._events: List[MonitoringEvent] = []
        self._pipeline_results: List[Dict[str, Any]] = []
        self._stats = {
            "total_tickets": 0,
            "auto_resolved": 0,
            "asked_client": 0,
            "escalated": 0,
            "quality_failed": 0,
            "avg_confidence": 0.0,
            "avg_quality_score": 0.0,
            "avg_latency_ms": 0.0,
        }

    def analyze_pipeline_result(self, result: Dict[str, Any]) -> List[MonitoringEvent]:
        """Analyze a variant pipeline result and generate monitoring events.

        This is called after EVERY variant execution. It checks for
        issues and generates events for Jarvis to act on.

        Args:
            result: The pipeline result dict.

        Returns:
            List of monitoring events generated.
        """
        events = []
        self._pipeline_results.append(result)
        self._stats["total_tickets"] += 1

        company_id = result.get("company_id", self.company_id)
        ticket_id = result.get("ticket_id", "")
        variant_tier = result.get("variant_tier", "")
        confidence = result.get("confidence_score", 0.0)
        quality_score = result.get("quality_score", 0.0)
        latency_ms = result.get("total_latency_ms", 0.0)

        # Update stats
        self._update_stats(confidence, quality_score, latency_ms, result)

        # ── Check 1: Ask-when-unsure ──────────────────────────
        if result.get("ask_client_needed"):
            events.append(MonitoringEvent(
                event_type="ask_client_needed",
                severity="medium",
                company_id=company_id,
                ticket_id=ticket_id,
                variant_tier=variant_tier,
                details={
                    "reason": result.get("ask_client_reason", ""),
                    "confidence": confidence,
                    "response_preview": result.get("agent_response", "")[:200],
                },
            ))
            self._stats["asked_client"] += 1

        # ── Check 2: Low confidence ───────────────────────────
        config = get_permission_config(variant_tier)
        if confidence < config.ask_client_confidence_threshold:
            events.append(MonitoringEvent(
                event_type="low_confidence",
                severity="high" if confidence < 0.3 else "medium",
                company_id=company_id,
                ticket_id=ticket_id,
                variant_tier=variant_tier,
                details={
                    "confidence": confidence,
                    "threshold": config.ask_client_confidence_threshold,
                    "response_preview": result.get("agent_response", "")[:200],
                },
            ))

        # ── Check 3: Quality gate failure ─────────────────────
        if not result.get("quality_passed", True):
            events.append(MonitoringEvent(
                event_type="quality_gate_failed",
                severity="high",
                company_id=company_id,
                ticket_id=ticket_id,
                variant_tier=variant_tier,
                details={
                    "quality_score": quality_score,
                    "threshold": config.clara_threshold,
                    "retry_count": result.get("quality_retry_count", 0),
                },
            ))
            self._stats["quality_failed"] += 1

        # ── Check 4: MAKER red flag ───────────────────────────
        if result.get("red_flag"):
            events.append(MonitoringEvent(
                event_type="maker_red_flag",
                severity="critical",
                company_id=company_id,
                ticket_id=ticket_id,
                variant_tier=variant_tier,
                details={
                    "action_type": result.get("action_type", ""),
                    "maker_confidence": result.get("maker_best_confidence", 0.0),
                },
            ))

        # ── Check 5: Escalation ───────────────────────────────
        if result.get("proposed_action") == "escalate":
            events.append(MonitoringEvent(
                event_type="escalation",
                severity="high",
                company_id=company_id,
                ticket_id=ticket_id,
                variant_tier=variant_tier,
                details={
                    "reason": result.get("escalation_reason", ""),
                    "confidence": confidence,
                },
            ))
            self._stats["escalated"] += 1
        else:
            self._stats["auto_resolved"] += 1

        # ── Check 6: SLA breach (latency > 30s) ──────────────
        if latency_ms > 30000:
            events.append(MonitoringEvent(
                event_type="sla_breach",
                severity="medium",
                company_id=company_id,
                ticket_id=ticket_id,
                variant_tier=variant_tier,
                details={
                    "latency_ms": latency_ms,
                    "sla_target_ms": 30000,
                },
            ))

        # ── Check 7: Auto-fix applied ─────────────────────────
        if result.get("auto_fix_applied"):
            events.append(MonitoringEvent(
                event_type="auto_fix_applied",
                severity="low",
                company_id=company_id,
                ticket_id=ticket_id,
                variant_tier=variant_tier,
                details={
                    "original_response": result.get("agent_response", "")[:200],
                },
            ))

        # Store events
        self._events.extend(events)

        # Log critical events
        critical = [e for e in events if e.severity == "critical"]
        if critical:
            logger.warning(
                "jarvis_monitor_critical_events",
                company_id=company_id,
                critical_count=len(critical),
                events=[e.to_dict() for e in critical],
            )

        return events

    def get_critical_events(self) -> List[MonitoringEvent]:
        """Get all critical-severity events."""
        return [e for e in self._events if e.severity == "critical"]

    def get_recent_events(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent events (all severities)."""
        return [e.to_dict() for e in self._events[-limit:]]

    def get_awareness_snapshot(self) -> Dict[str, Any]:
        """Get a complete awareness snapshot for Jarvis.

        This is what Jarvis "knows" at any moment:
          - Current ticket stats
          - Auto-resolve rate
          - Quality metrics
          - Active issues
          - Recent events
          - Knowledge base stats
        """
        total = max(self._stats["total_tickets"], 1)

        return {
            "company_id": self.company_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "ticket_stats": {
                "total": self._stats["total_tickets"],
                "auto_resolved": self._stats["auto_resolved"],
                "asked_client": self._stats["asked_client"],
                "escalated": self._stats["escalated"],
                "quality_failed": self._stats["quality_failed"],
                "auto_resolve_rate": self._stats["auto_resolved"] / total,
                "ask_client_rate": self._stats["asked_client"] / total,
                "escalation_rate": self._stats["escalated"] / total,
            },
            "quality_metrics": {
                "avg_confidence": self._stats["avg_confidence"],
                "avg_quality_score": self._stats["avg_quality_score"],
                "avg_latency_ms": self._stats["avg_latency_ms"],
            },
            "active_issues": {
                "critical_events": len(self.get_critical_events()),
                "unresolved_escalations": self._stats["escalated"],
            },
            "recent_events": self.get_recent_events(5),
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get monitoring statistics."""
        total = max(self._stats["total_tickets"], 1)
        return {
            **self._stats,
            "auto_resolve_rate": self._stats["auto_resolved"] / total,
            "ask_client_rate": self._stats["asked_client"] / total,
            "escalation_rate": self._stats["escalated"] / total,
            "quality_failure_rate": self._stats["quality_failed"] / total,
        }

    def _update_stats(
        self,
        confidence: float,
        quality_score: float,
        latency_ms: float,
        result: Dict[str, Any],
    ):
        """Update running statistics with exponential moving average."""
        alpha = 0.1  # Smoothing factor
        n = self._stats["total_tickets"]

        self._stats["avg_confidence"] = (
            (1 - alpha) * self._stats["avg_confidence"] + alpha * confidence
            if n > 1 else confidence
        )
        self._stats["avg_quality_score"] = (
            (1 - alpha) * self._stats["avg_quality_score"] + alpha * quality_score
            if n > 1 else quality_score
        )
        self._stats["avg_latency_ms"] = (
            (1 - alpha) * self._stats["avg_latency_ms"] + alpha * latency_ms
            if n > 1 else latency_ms
        )
