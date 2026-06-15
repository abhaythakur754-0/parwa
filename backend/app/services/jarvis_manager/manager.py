"""
Jarvis Manager — The brain that ties Monitor + Intervention + Notification together.

This is the main entry point for Jarvis's management capabilities.
It coordinates monitoring, intervention, notification, and knowledge base.

Flow:
  1. Variant processes ticket → result comes in
  2. JarvisMonitor analyzes result → generates events
  3. For each event → JarvisIntervention acts
  4. Actions that need client input → NotificationManager creates notifications
  5. Client clicks notification → Jarvis opens chat with full context
  6. Resolution → knowledge base entry for future learning

Usage:
    jarvis = JarvisManager(company_id="comp_123")

    # After variant pipeline runs
    analysis = jarvis.process_pipeline_result(pipeline_result)

    # Get dashboard data
    notifications = jarvis.get_dashboard_notifications()

    # Client clicks notification
    context = jarvis.open_notification(batch_id)

    # Resolve
    jarvis.resolve_notification(batch_id, resolution="Approved refund")
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.logger import get_logger
from app.services.jarvis_manager.monitor import JarvisMonitor, MonitoringEvent
from app.services.jarvis_manager.intervention import (
    JarvisIntervention,
    InterventionType,
    InterventionResult,
)
from app.services.notification_crm.manager import NotificationManager
from app.services.notification_crm.models import NotificationType

logger = get_logger("jarvis_manager")


class PipelineAnalysis:
    """Analysis result from processing a pipeline result through Jarvis."""

    def __init__(self):
        self.events: List[MonitoringEvent] = []
        self.interventions: List[InterventionResult] = []
        self.notifications_created: int = 0
        self.auto_resolve_possible: bool = False
        self.needs_human: bool = False
        self.quality_score: float = 0.0
        self.confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "events": [e.to_dict() for e in self.events],
            "interventions": [i.to_dict() for i in self.interventions],
            "notifications_created": self.notifications_created,
            "auto_resolve_possible": self.auto_resolve_possible,
            "needs_human": self.needs_human,
            "quality_score": self.quality_score,
            "confidence": self.confidence,
        }


class JarvisManager:
    """Jarvis Manager — The brain that ties it all together.

    Jarvis is NOT a chatbot. It's a MANAGER that:
      - Monitors all variant executions
      - Intervenes when variants make mistakes
      - Notifies clients when their input is needed
      - Learns from every resolution
      - Has COMPLETE AWARENESS of system state

    This is the "loop whole" architecture where Jarvis is at the center,
    connecting variants, clients, and the knowledge base in a feedback loop.
    """

    def __init__(self, company_id: str):
        self.company_id = company_id
        self._monitor = JarvisMonitor(company_id)
        self._intervention = JarvisIntervention(company_id)
        self._notification_mgr = NotificationManager(company_id)

    def process_pipeline_result(
        self,
        pipeline_result: Dict[str, Any],
    ) -> PipelineAnalysis:
        """Process a variant pipeline result through Jarvis.

        This is the main method called after every variant execution.
        It:
          1. Monitors the result for issues
          2. Intervenes on any problems found
          3. Creates notifications for client-facing actions
          4. Updates knowledge base

        Args:
            pipeline_result: The result from the unified variant pipeline.

        Returns:
            PipelineAnalysis with events, interventions, and notifications.
        """
        analysis = PipelineAnalysis()

        # Step 1: Monitor — detect issues
        events = self._monitor.analyze_pipeline_result(pipeline_result)
        analysis.events = events

        # Step 2: Intervene — act on issues
        for event in events:
            intervention = self._handle_event(event, pipeline_result)
            if intervention:
                analysis.interventions.append(intervention)

                # Step 3: Create notifications for client-facing actions
                if intervention.intervention_type in (
                    InterventionType.ASK_CLIENT,
                    InterventionType.ESCALATE,
                    InterventionType.NOTIFY,
                ):
                    notif = self._create_notification_from_intervention(
                        intervention, pipeline_result
                    )
                    if notif:
                        analysis.notifications_created += 1

        # Compute analysis summary
        confidence = pipeline_result.get("confidence_score", 0.0)
        quality_score = pipeline_result.get("quality_score", 0.0)

        analysis.confidence = confidence
        analysis.quality_score = quality_score
        analysis.auto_resolve_possible = (
            confidence >= 0.7
            and quality_score >= 0.7
            and not pipeline_result.get("ask_client_needed", False)
            and not pipeline_result.get("red_flag", False)
        )
        analysis.needs_human = any(
            i.intervention_type == InterventionType.ESCALATE
            for i in analysis.interventions
        )

        logger.info(
            "jarvis_processed_pipeline_result",
            company_id=self.company_id,
            ticket_id=pipeline_result.get("ticket_id", ""),
            events=len(events),
            interventions=len(analysis.interventions),
            notifications=analysis.notifications_created,
            auto_resolve=analysis.auto_resolve_possible,
            needs_human=analysis.needs_human,
        )

        return analysis

    def get_dashboard_notifications(self) -> List[Dict[str, Any]]:
        """Get notifications for the dashboard, refunds FIRST."""
        return self._notification_mgr.get_dashboard_notifications()

    def open_notification(self, batch_id: str) -> Dict[str, Any]:
        """Open a notification — client clicked it.

        Returns full context for Jarvis to start a conversation.
        """
        return self._notification_mgr.open_notification(batch_id)

    def resolve_notification(
        self,
        batch_id: str,
        resolution: str,
        resolution_data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Resolve a notification and add to knowledge base."""
        return self._notification_mgr.resolve_notification(
            batch_id, resolution, resolution_data
        )

    def get_awareness_snapshot(self) -> Dict[str, Any]:
        """Get complete awareness snapshot — what Jarvis knows right now."""
        return self._monitor.get_awareness_snapshot()

    def get_monitoring_stats(self) -> Dict[str, Any]:
        """Get monitoring statistics."""
        return self._monitor.get_stats()

    def get_knowledge_entries(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get knowledge base entries."""
        return self._notification_mgr.get_knowledge_entries(limit)

    def get_quality_score(self) -> Dict[str, Any]:
        """Get overall quality score for this company.

        This is the metric that answers: "Can AI replace humans?"
        """
        stats = self._monitor.get_stats()
        total = max(stats.get("total_tickets", 0), 1)

        return {
            "company_id": self.company_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "auto_resolve_rate": stats.get("auto_resolve_rate", 0.0),
            "ask_client_rate": stats.get("ask_client_rate", 0.0),
            "escalation_rate": stats.get("escalation_rate", 0.0),
            "quality_failure_rate": stats.get("quality_failure_rate", 0.0),
            "avg_confidence": stats.get("avg_confidence", 0.0),
            "avg_quality_score": stats.get("avg_quality_score", 0.0),
            "avg_latency_ms": stats.get("avg_latency_ms", 0.0),
            "human_replacement_score": self._compute_human_replacement_score(stats),
            "honest_assessment": self._get_honest_assessment(stats),
        }

    def _handle_event(
        self,
        event: MonitoringEvent,
        pipeline_result: Dict[str, Any],
    ) -> Optional[InterventionResult]:
        """Handle a monitoring event by choosing the right intervention."""
        handlers = {
            "ask_client_needed": lambda: self._intervention.handle_ask_client(pipeline_result),
            "low_confidence": lambda: self._intervention.handle_low_confidence(pipeline_result),
            "quality_gate_failed": lambda: self._intervention.handle_quality_failure(pipeline_result),
            "maker_red_flag": lambda: self._intervention.handle_maker_red_flag(pipeline_result),
            "escalation": lambda: InterventionResult(
                intervention_type=InterventionType.ESCALATE,
                success=True,
                company_id=self.company_id,
                ticket_id=event.ticket_id,
                details={"reason": "variant_escalated"},
            ),
        }

        handler = handlers.get(event.event_type)
        if handler:
            try:
                return handler()
            except Exception:
                logger.exception(f"handler failed for event type: {event.event_type}")
        return None

    def _create_notification_from_intervention(
        self,
        intervention: InterventionResult,
        pipeline_result: Dict[str, Any],
    ) -> Optional[Any]:
        """Create a notification from an intervention."""
        try:
            if intervention.intervention_type == InterventionType.ASK_CLIENT:
                return self._notification_mgr.create_notification(
                    notification_type="ask_client",
                    title=f"Needs your input: {intervention.details.get('question', '')[:50]}",
                    description=intervention.details.get("question", ""),
                    customer_id=pipeline_result.get("customer_id", ""),
                    ticket_id=intervention.ticket_id,
                    conversation_id=pipeline_result.get("conversation_id", ""),
                    variant_tier=pipeline_result.get("variant_tier", ""),
                    confidence=pipeline_result.get("confidence_score", 0.0),
                    context=pipeline_result,
                    ask_client_question=intervention.details.get("question", ""),
                    ask_client_options=intervention.details.get("options", []),
                )

            elif intervention.intervention_type == InterventionType.ESCALATE:
                return self._notification_mgr.create_notification(
                    notification_type="escalation",
                    title=f"Escalation needed: {intervention.details.get('reason', '')[:50]}",
                    description=intervention.details.get("reason", ""),
                    customer_id=pipeline_result.get("customer_id", ""),
                    ticket_id=intervention.ticket_id,
                    confidence=pipeline_result.get("confidence_score", 0.0),
                    context=pipeline_result,
                )

            return None

        except Exception:
            logger.exception("_create_notification_from_intervention failed")
            return None

    def _compute_human_replacement_score(self, stats: Dict[str, Any]) -> float:
        """Compute an honest human-replacement score (0-100).

        Based on actual metrics, not wishful thinking.
        """
        total = max(stats.get("total_tickets", 0), 1)
        auto_rate = stats.get("auto_resolved", 0) / total
        ask_rate = stats.get("asked_client", 0) / total
        esc_rate = stats.get("escalated", 0) / total
        avg_conf = stats.get("avg_confidence", 0.0)
        avg_quality = stats.get("avg_quality_score", 0.0)

        # Weighted score
        score = (
            auto_rate * 40 +          # 40% weight on auto-resolve
            (1 - esc_rate) * 20 +     # 20% weight on low escalation
            avg_conf * 20 +           # 20% weight on confidence
            avg_quality * 20          # 20% weight on quality
        )

        return round(score, 1)

    def _get_honest_assessment(self, stats: Dict[str, Any]) -> str:
        """Get an honest assessment of whether AI can replace humans."""
        total = max(stats.get("total_tickets", 0), 1)
        auto_rate = stats.get("auto_resolved", 0) / total
        esc_rate = stats.get("escalated", 0) / total

        if stats.get("total_tickets", 0) < 10:
            return "Insufficient data — need at least 10 tickets for assessment"

        if auto_rate >= 0.9 and esc_rate < 0.05:
            return "AI is performing at senior level — can handle 90%+ autonomously"
        elif auto_rate >= 0.7 and esc_rate < 0.1:
            return "AI is performing at junior level — can handle most routine tasks, needs supervision for complex cases"
        elif auto_rate >= 0.5:
            return "AI is performing at intern level — can handle simple tasks, needs guidance for most things"
        else:
            return "AI needs significant improvement — currently requires human oversight for most tasks"
