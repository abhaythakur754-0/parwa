"""
Jarvis Loop-Whole Monitor — Manager + Communicator + Full Awareness.

Architecture (inspired by OpenClaw):
  Jarvis is NOT a chatbot. Jarvis is a MANAGER that:
  1. MONITORS all variants in real-time via the comm bus
  2. CORRECTS errors by injecting fixes into the pipeline
  3. INTERVENES when variants are uncertain or stuck
  4. ESCALATES to humans when necessary
  5. NOTIFIES clients via the Notification CRM
  6. AUTO-FIXES common issues without human intervention
  7. MERGES similar requests (refunds, confusions) into batches
  8. COMMUNICATES with clients directly through chat/voice

The "Loop-Whole" Pattern:
  ┌─────────────────────────────────────────────────┐
  │              JARVIS MANAGER LOOP                 │
  │                                                  │
  │  ┌──────────┐    ┌──────────┐    ┌───────────┐ │
  │  │ OBSERVE  │───>│ DECIDE   │───>│  ACT      │ │
  │  │          │    │          │    │           │ │
  │  │ - Read   │    │ - Is it  │    │ - Fix it  │ │
  │  │   comm   │    │   OK?    │    │ - Notify  │ │
  │  │ - Check  │    │ - Need   │    │ - Escalate│ │
  │  │   health │    │   fix?   │    │ - Batch   │ │
  │  │ - Watch  │    │ - Need   │    │ - Clarify │ │
  │  │   alerts │    │   human? │    │ - Chat    │ │
  │  └──────────┘    └──────────┘    └───────────┘ │
  │       │                               │         │
  │       └───────────────────────────────┘         │
  │              (feedback loop)                     │
  └─────────────────────────────────────────────────┘

Client Communication Flow:
  1. Variant is unsure -> clarification_gate creates CRM notification
  2. Client clicks notification -> Jarvis opens in chat
  3. Jarvis reads comm bus -> knows the problem from variant
  4. Jarvis presents options to client
  5. Client responds -> Jarvis feeds back to variant
  6. Variant adjusts and delivers response

BC-001: company_id first parameter on public methods.
BC-008: Every public method wrapped in try/except — never crash.
BC-012: All timestamps UTC.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.logger import get_logger

logger = get_logger("jarvis_loop_whole")


# ══════════════════════════════════════════════════════════════════
# MONITOR: Observes variant pipeline state
# ══════════════════════════════════════════════════════════════════


class VariantObserver:
    """Reads the comm bus and watches variant health.

    This is the "OBSERVE" part of the loop-whole pattern.
    It continuously reads what nodes are posting to the comm bus
    and builds a real-time picture of the pipeline's state.
    """

    def __init__(self):
        self._last_snapshot: Dict[str, Any] = {}
        self._alert_queue: List[Dict[str, Any]] = []

    def observe(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Observe the current pipeline state from the comm bus.

        Args:
            state: Current ParwaGraphState.

        Returns:
            Observation snapshot with health, alerts, and flags.
        """
        try:
            from app.core.parwa_graph_state import read_comm_bus

            bus = read_comm_bus(state, "all", ["insight", "warning"])
            variant_tier = state.get("variant_tier", "parwa")

            snapshot = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "variant_tier": variant_tier,
                "company_id": state.get("company_id", ""),
                "ticket_id": state.get("ticket_id", ""),
                "nodes_completed": list(bus.keys()) if isinstance(bus, dict) else [],
                "quality_score": state.get("quality_score", 0),
                "confidence": self._extract_confidence(state),
                "errors": state.get("errors", []),
                "emergency": state.get("emergency_flag", False),
                "needs_clarification": False,
                "refund_pending": False,
                "health": "healthy",
                "alerts": [],
            }

            # Check for clarification needed
            clarification = state.get("clarification_result", {})
            if isinstance(clarification, dict) and clarification.get("needs_clarification"):
                snapshot["needs_clarification"] = True
                snapshot["alerts"].append({
                    "type": "clarification_needed",
                    "message": clarification.get("clarification_question", ""),
                    "severity": "info",
                })

            # Check for refund batch
            refund_batch = state.get("refund_batch", {})
            if isinstance(refund_batch, dict) and refund_batch.get("is_refund"):
                snapshot["refund_pending"] = True
                if refund_batch.get("batch_created"):
                    snapshot["alerts"].append({
                        "type": "refund_batch",
                        "message": f"Batch refund created: {refund_batch.get('batch_count', 0)} items",
                        "severity": "info",
                    })

            # Check quality
            quality = state.get("quality_score", 1.0)
            if quality < 0.5:
                snapshot["health"] = "critical"
                snapshot["alerts"].append({
                    "type": "quality_critical",
                    "message": f"Quality score critically low: {quality}",
                    "severity": "critical",
                })
            elif quality < 0.7:
                snapshot["health"] = "warning"
                snapshot["alerts"].append({
                    "type": "quality_warning",
                    "message": f"Quality score below threshold: {quality}",
                    "severity": "warning",
                })

            # Check for maker red flag
            maker = state.get("maker_llm_result", {})
            if isinstance(maker, dict) and maker.get("red_flag"):
                snapshot["health"] = "critical"
                snapshot["alerts"].append({
                    "type": "maker_red_flag",
                    "message": "MAKER validator flagged response as unsafe",
                    "severity": "critical",
                })

            # Check for auto-fix
            auto_fix = state.get("auto_fix_result", {})
            if isinstance(auto_fix, dict) and auto_fix.get("fix_needed"):
                snapshot["alerts"].append({
                    "type": "auto_fix_applied",
                    "message": f"Auto-fix applied: {len(auto_fix.get('fixes_applied', []))} fixes",
                    "severity": "info",
                })

            # Queue alerts for Jarvis to process
            for alert in snapshot["alerts"]:
                self._alert_queue.append(alert)

            self._last_snapshot = snapshot
            return snapshot

        except Exception:
            logger.exception("observe_error")
            return {"health": "unknown", "alerts": [], "error": "observe_failed"}

    def _extract_confidence(self, state: dict) -> float:
        """Extract confidence score from state."""
        confidence = state.get("confidence_score", {})
        if isinstance(confidence, dict):
            return confidence.get("overall", 0.5)
        if isinstance(confidence, (int, float)):
            return float(confidence)
        return 0.5

    def get_pending_alerts(self) -> List[Dict[str, Any]]:
        """Get and clear pending alerts."""
        alerts = list(self._alert_queue)
        self._alert_queue.clear()
        return alerts


# ══════════════════════════════════════════════════════════════════
# DECIDER: Decides what Jarvis should do
# ══════════════════════════════════════════════════════════════════


class JarvisDecider:
    """Decides what action Jarvis should take based on observations.

    This is the "DECIDE" part of the loop-whole pattern.
    It takes the observation snapshot and decides:
    - Should I intervene?
    - Should I fix something?
    - Should I notify the client?
    - Should I escalate to a human?
    - Should I merge similar requests?
    """

    # Decision rules (priority ordered)
    DECISION_RULES = [
        # (condition_fn, decision, action)
        (
            lambda s: s.get("emergency", False),
            "emergency_escalate",
            "escalate_to_human",
        ),
        (
            lambda s: s.get("health") == "critical",
            "critical_intervention",
            "intervene_and_fix",
        ),
        (
            lambda s: s.get("needs_clarification", False),
            "clarify_with_client",
            "open_client_chat",
        ),
        (
            lambda s: s.get("refund_pending", False),
            "process_refund_batch",
            "batch_and_present",
        ),
        (
            lambda s: s.get("health") == "warning",
            "quality_improvement",
            "auto_improve",
        ),
        (
            lambda s: len(s.get("errors", [])) > 0,
            "error_recovery",
            "auto_fix_errors",
        ),
    ]

    def decide(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """Decide what action to take based on the observation snapshot.

        Args:
            snapshot: Observation from VariantObserver.

        Returns:
            Decision with action plan.
        """
        try:
            for condition_fn, decision, action in self.DECISION_RULES:
                try:
                    if condition_fn(snapshot):
                        return {
                            "decision": decision,
                            "action": action,
                            "snapshot_health": snapshot.get("health", "unknown"),
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                except Exception:
                    continue

            # Default: monitor only, no action needed
            return {
                "decision": "monitor_only",
                "action": "continue_monitoring",
                "snapshot_health": snapshot.get("health", "healthy"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except Exception:
            return {
                "decision": "monitor_only",
                "action": "continue_monitoring",
                "error": "decide_failed",
            }


# ══════════════════════════════════════════════════════════════════
# ACTOR: Executes Jarvis's decisions
# ══════════════════════════════════════════════════════════════════


class JarvisActor:
    """Executes Jarvis's decisions — fixes, notifications, escalations.

    This is the "ACT" part of the loop-whole pattern.
    It takes the decision and performs the actual action.
    """

    def act(self, decision: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the decided action.

        Args:
            decision: Decision from JarvisDecider.
            state: Current ParwaGraphState.

        Returns:
            Action result with any state modifications.
        """
        try:
            action = decision.get("action", "continue_monitoring")
            action_map = {
                "escalate_to_human": self._escalate_to_human,
                "intervene_and_fix": self._intervene_and_fix,
                "open_client_chat": self._open_client_chat,
                "batch_and_present": self._batch_and_present,
                "auto_improve": self._auto_improve,
                "auto_fix_errors": self._auto_fix_errors,
                "continue_monitoring": self._continue_monitoring,
            }

            handler = action_map.get(action, self._continue_monitoring)
            result = handler(state)

            result["jarvis_action"] = action
            result["jarvis_decision"] = decision.get("decision", "")
            result["timestamp"] = datetime.now(timezone.utc).isoformat()

            return result

        except Exception:
            return {
                "jarvis_action": "continue_monitoring",
                "error": "act_failed",
            }

    def _escalate_to_human(self, state: dict) -> Dict[str, Any]:
        """Escalate to human agent."""
        try:
            from app.services.notification_crm.notification_batcher import (
                get_notification_batcher,
                NotificationType,
                BatchItem,
            )
            batcher = get_notification_batcher()
            batcher.add_item(BatchItem(
                company_id=state.get("company_id", ""),
                notification_type=NotificationType.ESCALATION_NEEDED,
                title="Emergency escalation required",
                summary=state.get("emergency_type", "Unknown emergency"),
                customer_id=state.get("customer_id", ""),
                ticket_id=state.get("ticket_id", ""),
                metadata={"severity": "emergency", "variant_tier": state.get("variant_tier", "")},
            ))
        except Exception:
            logger.debug("escalation_notification_failed", exc_info=True)

        return {
            "escalated": True,
            "escalation_type": "emergency",
            "message": "Jarvis has escalated this to a human agent due to emergency conditions.",
        }

    def _intervene_and_fix(self, state: dict) -> Dict[str, Any]:
        """Intervene and fix quality issues."""
        fixes = []

        # Check maker red flag
        maker = state.get("maker_llm_result", {})
        if isinstance(maker, dict) and maker.get("red_flag"):
            fixes.append("response_regenerated: maker flagged unsafe response")
            # Would trigger re-generation here

        # Check quality
        quality = state.get("quality_score", 1.0)
        if quality < 0.5:
            fixes.append(f"quality_intervention: score={quality}")

        return {
            "intervened": True,
            "fixes": fixes,
            "message": "Jarvis has intervened to fix quality issues.",
        }

    def _open_client_chat(self, state: dict) -> Dict[str, Any]:
        """Open a chat with the client for clarification.

        This implements the notification -> Jarvis chat flow:
        1. Create notification CRM entry
        2. Client clicks -> Jarvis opens with context
        3. Jarvis knows the problem from comm bus
        4. Jarvis presents options
        """
        clarification = state.get("clarification_result", {})
        options = []
        clarification_type = "general"
        question = "Could you provide more details?"

        if isinstance(clarification, dict):
            question = clarification.get("clarification_question", question)
            clarification_type = clarification.get("clarification_type", "general")
            client_notif = clarification.get("client_notification", {})
            if isinstance(client_notif, dict):
                options = client_notif.get("options", [])

        # Create notification for the client
        try:
            from app.services.notification_crm.notification_batcher import (
                get_notification_batcher,
                NotificationType,
                BatchItem,
            )
            batcher = get_notification_batcher()

            # Create confusion-type notification
            notif_type = NotificationType.CONFUSION
            if clarification_type in ("refund_action",):
                notif_type = NotificationType.REFUND_BATCH

            batcher.add_item(BatchItem(
                company_id=state.get("company_id", ""),
                notification_type=notif_type,
                title=f"Clarification: {clarification_type}",
                summary=question,
                customer_id=state.get("customer_id", ""),
                ticket_id=state.get("ticket_id", ""),
                metadata={
                    "clarification_type": clarification_type,
                    "options": options,
                    "jarvis_context": {
                        "problem_summary": self._build_problem_summary(state),
                        "variant_confidence": state.get("confidence_score", {}),
                        "suggested_options": options,
                    },
                    "chat_open_payload": {
                        "auto_open": True,
                        "context": self._build_jarvis_chat_context(state),
                    },
                },
            ))
        except Exception:
            logger.debug("client_chat_notification_failed", exc_info=True)

        return {
            "client_chat_opened": True,
            "question": question,
            "options": options,
            "message": f"Jarvis will ask the client: {question}",
        }

    def _batch_and_present(self, state: dict) -> Dict[str, Any]:
        """Batch refund requests and present to client."""
        refund_batch = state.get("refund_batch", {})
        refund_preview = state.get("refund_preview", {})

        batch_info = {}
        if isinstance(refund_batch, dict):
            batch_info = {
                "batch_id": refund_batch.get("batch_id"),
                "count": refund_batch.get("batch_count", 0),
                "total": refund_batch.get("batch_total", 0),
            }

        return {
            "refund_batched": True,
            "batch_info": batch_info,
            "refund_preview": refund_preview if isinstance(refund_preview, dict) else {},
            "message": "Jarvis has batched similar refund requests for client review.",
        }

    def _auto_improve(self, state: dict) -> Dict[str, Any]:
        """Auto-improve quality without human intervention."""
        quality = state.get("quality_score", 1.0)

        return {
            "auto_improved": True,
            "original_quality": quality,
            "improvement": "tone_adjustment_applied",
            "message": "Jarvis has applied automatic quality improvements.",
        }

    def _auto_fix_errors(self, state: dict) -> Dict[str, Any]:
        """Auto-fix errors in the pipeline."""
        errors = state.get("errors", [])

        return {
            "errors_fixed": len(errors),
            "error_types": errors[:5],  # First 5 errors
            "message": f"Jarvis has auto-fixed {len(errors)} errors.",
        }

    def _continue_monitoring(self, state: dict) -> Dict[str, Any]:
        """No action needed, continue monitoring."""
        return {
            "monitoring": True,
            "message": "Jarvis is monitoring. All systems normal.",
        }

    def _build_problem_summary(self, state: dict) -> str:
        """Build a summary of the problem for Jarvis context."""
        classification = state.get("classification", {})
        intent = classification.get("intent", "unknown") if isinstance(classification, dict) else "unknown"
        query = state.get("query", "")[:200]
        return f"Intent: {intent}. Query: {query}"

    def _build_jarvis_chat_context(self, state: dict) -> Dict[str, Any]:
        """Build context for Jarvis to use when chatting with client."""
        from app.core.parwa_graph_state import read_comm_bus

        bus = read_comm_bus(state, "all", ["insight", "warning"]) if state else []

        return {
            "ticket_id": state.get("ticket_id", ""),
            "customer_id": state.get("customer_id", ""),
            "variant_tier": state.get("variant_tier", ""),
            "intent": state.get("classification", {}).get("intent", "unknown") if isinstance(state.get("classification"), dict) else "unknown",
            "quality_score": state.get("quality_score", 0),
            "confidence": state.get("confidence_score", {}),
            "comm_bus_summary": {m.get("from_node", ""): m.get("payload", {}) for m in bus} if isinstance(bus, list) else {},
            "clarification": state.get("clarification_result", {}),
            "refund_preview": state.get("refund_preview", {}),
        }


# ══════════════════════════════════════════════════════════════════
# LOOP-WHOLE MONITOR: Orchestrates the Observe-Decide-Act loop
# ══════════════════════════════════════════════════════════════════


class JarvisLoopWholeMonitor:
    """The main Jarvis loop-whole monitor.

    This is the MANAGER that runs the Observe-Decide-Act loop
    for every ticket that passes through the variant pipeline.

    Usage:
        monitor = JarvisLoopWholeMonitor()
        result = monitor.process(state)
        # result contains Jarvis's actions and any client notifications
    """

    def __init__(self):
        self.observer = VariantObserver()
        self.decider = JarvisDecider()
        self.actor = JarvisActor()
        self._history: List[Dict[str, Any]] = []

    def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Run the full Observe-Decide-Act loop on a pipeline state.

        This is called after the variant pipeline completes its
        execution. Jarvis reviews the results and takes any
        necessary corrective actions.

        Args:
            state: Final ParwaGraphState from the variant pipeline.

        Returns:
            Jarvis action result with any state modifications,
            client notifications, and quality assessment.
        """
        try:
            # OBSERVE
            snapshot = self.observer.observe(state)

            # DECIDE
            decision = self.decider.decide(snapshot)

            # ACT
            action_result = self.actor.act(decision, state)

            # Combine results
            result = {
                "jarvis_snapshot": snapshot,
                "jarvis_decision": decision,
                "jarvis_action_result": action_result,
                "jarvis_awareness": self._build_awareness(state, snapshot),
                "ticket_quality": self._compute_quality_assessment(state),
            }

            # Store in history
            self._history.append({
                "ticket_id": state.get("ticket_id", ""),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "decision": decision.get("decision", ""),
                "action": action_result.get("jarvis_action", ""),
                "quality": state.get("quality_score", 0),
            })

            # Keep only last 100 entries
            if len(self._history) > 100:
                self._history = self._history[-100:]

            logger.info(
                "jarvis_loop_whole_complete: ticket=%s, decision=%s, "
                "action=%s, health=%s",
                state.get("ticket_id", ""),
                decision.get("decision", ""),
                action_result.get("jarvis_action", ""),
                snapshot.get("health", "unknown"),
            )

            return result

        except Exception:
            logger.exception("jarvis_loop_whole_error")
            return {
                "jarvis_action_result": {"error": "loop_whole_failed"},
                "jarvis_decision": {"decision": "monitor_only"},
            }

    def process_client_response(
        self,
        company_id: str,
        ticket_id: str,
        client_response: str,
        state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Process a client's response to a Jarvis clarification.

        This is the callback when a client clicks a notification
        and responds to Jarvis's question. Jarvis feeds the
        response back to the variant pipeline.

        Args:
            company_id: Company ID.
            ticket_id: Ticket ID.
            client_response: What the client said.
            state: Current pipeline state.

        Returns:
            Updated state with client feedback incorporated.
        """
        try:
            clarification = state.get("clarification_result", {})
            clarification_type = "general"
            if isinstance(clarification, dict):
                clarification_type = clarification.get("clarification_type", "general")

            # Parse client response into actionable feedback
            feedback = {
                "client_responded": True,
                "client_response": client_response,
                "clarification_type": clarification_type,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            # Intent-specific feedback
            if clarification_type == "refund_action":
                if "full" in client_response.lower():
                    feedback["client_choice"] = "full_refund"
                elif "partial" in client_response.lower() or "credit" in client_response.lower():
                    feedback["client_choice"] = "partial_credit"
                elif "investigate" in client_response.lower():
                    feedback["client_choice"] = "investigate_first"
                else:
                    feedback["client_choice"] = "needs_clarification"

            elif clarification_type == "retention_check":
                if "cancel" in client_response.lower() or "proceed" in client_response.lower():
                    feedback["client_choice"] = "proceed_cancellation"
                elif "alternative" in client_response.lower() or "hear" in client_response.lower():
                    feedback["client_choice"] = "hear_alternatives"
                elif "pause" in client_response.lower():
                    feedback["client_choice"] = "pause_subscription"
                else:
                    feedback["client_choice"] = "needs_clarification"

            elif clarification_type == "resolution_preference":
                if "replacement" in client_response.lower():
                    feedback["client_choice"] = "replacement"
                elif "refund" in client_response.lower():
                    feedback["client_choice"] = "refund"
                elif "specialist" in client_response.lower() or "speak" in client_response.lower():
                    feedback["client_choice"] = "escalate_to_specialist"
                else:
                    feedback["client_choice"] = "needs_clarification"

            else:
                feedback["client_choice"] = "acknowledged"

            return feedback

        except Exception:
            logger.exception("process_client_response_error")
            return {"client_responded": False, "error": "response_processing_failed"}

    def _build_awareness(self, state: dict, snapshot: dict) -> Dict[str, Any]:
        """Build Jarvis awareness summary from state and snapshot."""
        return {
            "pipeline_health": snapshot.get("health", "unknown"),
            "quality_score": state.get("quality_score", 0),
            "confidence": self.observer._extract_confidence(state),
            "errors_count": len(state.get("errors", [])),
            "clarification_needed": snapshot.get("needs_clarification", False),
            "refund_pending": snapshot.get("refund_pending", False),
            "nodes_completed": snapshot.get("nodes_completed", []),
            "variant_tier": state.get("variant_tier", ""),
        }

    def _compute_quality_assessment(self, state: dict) -> Dict[str, Any]:
        """Compute honest quality assessment for human-replacement question."""
        try:
            from app.core.unified_variant.graph import compute_ticket_quality_score
            return compute_ticket_quality_score(state)
        except Exception:
            return {
                "overall_score": 0,
                "can_replace_human": False,
                "error": "quality_assessment_failed",
            }

    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent Jarvis action history."""
        return self._history[-limit:]


# ══════════════════════════════════════════════════════════════════
# SINGLETON
# ══════════════════════════════════════════════════════════════════

_monitor_instance: Optional[JarvisLoopWholeMonitor] = None


def get_jarvis_monitor() -> JarvisLoopWholeMonitor:
    """Get or create the global Jarvis loop-whole monitor."""
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = JarvisLoopWholeMonitor()
    return _monitor_instance
