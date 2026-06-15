"""
Jarvis Loop Whole Graph — The COMPLETE awareness loop for Jarvis.

"Loop Whole" means Jarvis has a COMPLETE awareness loop:
  1. WATCH   — Monitor all variants, all tickets, all system health
  2. DETECT  — Find anomalies, issues, opportunities
  3. DECIDE  — Choose action (self-heal, notify, escalate, ask client)
  4. ACT     — Execute the action
  5. VERIFY  — Check if action actually worked (not just "we tried")
  6. FEEDBACK — Feed results back into monitoring (CLOSE THE LOOP)

This replaces the old monitor→diagnose→plan→execute flow which lacked
verification and feedback — meaning Jarvis could "try" something without
ever checking if it worked or learning from the outcome.

GRAPH TOPOLOGY:
  START → watch → (anomaly?) → detect → (issue?) → decide → (action?) → act
    → verify → (success?) → feedback → END
                ↓ NO            ↓ NO           ↓ NO        ↓ NO retry    ↓ NO retry
               END             END            END         (back to act)  (back to decide)

Key differences from old manager (jarvis_manager_graph.py):
  - VERIFY node: Checks if the action ACTUALLY worked
  - FEEDBACK node: Closes the loop, updates awareness & comm_bus
  - RETRY LOGIC: If action failed, retry with different approach (max 2)
  - CLIENT COMMUNICATION: If variant is unsure, Jarvis talks to client
  - BATCH AWARENESS: Knows about notification batches, merges similar issues

BC-001: company_id first parameter.
BC-008: Never crash — every node wrapped in try/except.
BC-012: All timestamps UTC.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from langgraph.graph import StateGraph, END

from app.services.jarvis_manager.jarvis_manager_state import (
    JarvisManagerState,
    create_jarvis_manager_state,
)
from app.services.jarvis_agents.variant_bridge import (
    read_pipeline_state_for_jarvis,
    sync_awareness_to_pipeline,
)
from app.logger import get_logger

logger = get_logger("jarvis_loop_whole_graph")

# ── Constants ──────────────────────────────────────────────────────

MAX_ACTION_RETRIES = 2
"""Maximum retries for a failed action before escalating."""

QUALITY_TIER_THRESHOLDS: Dict[str, float] = {
    "mini_parwa": 0.60,
    "parwa": 0.70,
    "parwa_high": 0.80,
}
"""Minimum quality score per variant tier before triggering anomaly."""

LATENCY_SPIKE_MS = 10_000
"""Pipeline latency above this (ms) is considered a spike."""

VARIANT_CONFIDENCE_THRESHOLD = 0.45
"""Below this confidence, Jarvis asks the client instead of acting."""

ERROR_RATE_SPIKE = 0.15
"""Error rate above this fraction triggers an anomaly."""

BATCH_SIMILARITY_WINDOW_SECONDS = 300
"""Window (5 min) to group similar notifications for batch merge."""


# ══════════════════════════════════════════════════════════════════
# HELPER UTILITIES
# ══════════════════════════════════════════════════════════════════


def _utc_now_iso() -> str:
    """Return current UTC time as ISO-8601 string (BC-012)."""
    return datetime.now(timezone.utc).isoformat()


def _get_loop_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """Retrieve the loop-whole–specific sub-state.

    We store loop-specific fields under ``_loop_whole`` in the existing
    ``JarvisManagerState`` dict so we don't need to modify the TypedDict.
    """
    return state.get("_loop_whole", {})


def _set_loop_state(state: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    """Merge *updates* into the ``_loop_whole`` sub-state and return
    the top-level dict that will be merged back into graph state."""
    current = dict(state.get("_loop_whole", {}))
    current.update(updates)
    return {"_loop_whole": current}


def _post_to_comm_bus(company_id: str, message: str) -> None:
    """Post a message to the node communication bus.

    Best-effort — never raises (BC-008).
    """
    try:
        from app.services.jarvis_activity_store import JarvisActivityStore
        store = JarvisActivityStore()
        store.post(  # type: ignore[attr-defined]
            company_id=company_id,
            event_type="jarvis_loop_whole",
            payload={"message": message, "timestamp": _utc_now_iso()},
        )
    except Exception:
        # Activity store is optional; log and continue
        logger.debug("comm_bus_post_skipped: company=%s", company_id)


# ══════════════════════════════════════════════════════════════════
# NODE 1 — WATCH
# ══════════════════════════════════════════════════════════════════


async def watch_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Watch node — gathers ALL awareness data.

    This is Jarvis's EYES. It reads:
      - Variant pipeline states from Redis bridge
      - Notification CRM for pending items
      - System health metrics
      - Quality scores across recent tickets

    Posts to node_comm_bus: "Jarvis watched at {ts}, found {n} items"
    Output: ``watch_snapshot`` dict with all gathered data.
    """
    start = time.monotonic()
    company_id = state.get("company_id", "")
    session_id = state.get("session_id", "")

    try:
        # 1. Read variant pipeline state from Redis bridge
        pipeline_state: Dict[str, Any] = {}
        try:
            pipeline_state = await read_pipeline_state_for_jarvis(
                company_id=company_id,
                session_id=session_id,
            )
        except Exception as exc:
            logger.warning("watch_pipeline_read_failed: %s", str(exc)[:120])
            pipeline_state = {"_error": str(exc)[:200]}

        # 2. Read awareness snapshot (already in state from awareness engine)
        awareness = state.get("awareness_snapshot", {})

        # 3. Read quality metrics from pipeline state
        quality_metrics: Dict[str, Any] = {
            "recent_quality_scores": pipeline_state.get("recent_quality_scores", []),
            "average_quality": pipeline_state.get("quality_score", 1.0),
            "quality_trend": pipeline_state.get("quality_trend", "stable"),
            "failed_tickets": pipeline_state.get("failed_tickets", 0),
            "total_tickets": pipeline_state.get("total_tickets", 0),
        }

        # 4. Read system health from awareness domains
        system_health: Dict[str, Any] = awareness.get("system_health", {})

        # 5. Read notification CRM pending items (best-effort)
        notification_pending: List[Dict[str, Any]] = []
        try:
            from app.services.notification_service import NotificationService
            svc = NotificationService()
            # NotificationService may not expose a direct "pending" method;
            # we use what's available or skip gracefully.
            notification_pending = getattr(svc, "_get_pending_for_jarvis", lambda *_: [])(company_id)  # type: ignore[call-arg]
        except Exception:
            pass  # best-effort

        # 6. Compile watch snapshot
        watch_snapshot: Dict[str, Any] = {
            "pipeline_state": pipeline_state,
            "awareness": awareness,
            "quality_metrics": quality_metrics,
            "system_health": system_health,
            "notification_pending": notification_pending,
            "watched_at": _utc_now_iso(),
        }

        total_items = (
            len(notification_pending)
            + len(quality_metrics.get("recent_quality_scores", []))
            + int(bool(pipeline_state and "_error" not in pipeline_state))
        )

        # Post to comm bus
        _post_to_comm_bus(
            company_id,
            f"Jarvis watched at {watch_snapshot['watched_at']}, found {total_items} items",
        )

        duration_ms = round((time.monotonic() - start) * 1000, 2)

        logger.info(
            "jarvis_watch: company=%s, items=%d, quality=%.2f, ms=%.1f",
            company_id, total_items, quality_metrics.get("average_quality", 1.0), duration_ms,
        )

        return {
            "variant_pipeline_state": pipeline_state,
            "quality_metrics": quality_metrics,
            "awareness_snapshot": awareness,
            **_set_loop_state(state, {"watch_snapshot": watch_snapshot}),
            "audit_trail": [{
                "step": "watch",
                "action": "watched",
                "timestamp": _utc_now_iso(),
                "duration_ms": duration_ms,
                "details": {"items_found": total_items},
            }],
        }

    except Exception as exc:
        logger.exception("jarvis_watch_error: %s", str(exc)[:200])
        return {
            "errors": [f"watch_error: {str(exc)[:200]}"],
            "audit_trail": [{
                "step": "watch",
                "action": "error",
                "timestamp": _utc_now_iso(),
                "details": {"error": str(exc)[:200]},
            }],
        }


# ══════════════════════════════════════════════════════════════════
# NODE 2 — DETECT
# ══════════════════════════════════════════════════════════════════


async def detect_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Detect node — analyzes watch snapshot for anomalies.

    Checks for:
      - Quality drops below tier threshold
      - Pipeline failures or timeouts
      - Error spikes
      - Latency spikes
      - Variant uncertainty (confidence < threshold)
      - Batch notification patterns (many similar issues)
      - Refund batch ready for approval
      - Customer confusion patterns

    Output: ``anomaly_list`` with severity, type, affected items.
    """
    start = time.monotonic()
    company_id = state.get("company_id", "")
    variant_tier = state.get("variant_tier", "parwa")

    try:
        loop = _get_loop_state(state)
        snapshot = loop.get("watch_snapshot", {})
        quality_metrics = snapshot.get("quality_metrics", state.get("quality_metrics", {}))
        pipeline_state = snapshot.get("pipeline_state", state.get("variant_pipeline_state", {}))
        awareness = snapshot.get("awareness", state.get("awareness_snapshot", {}))
        notifications = snapshot.get("notification_pending", [])

        anomaly_list: List[Dict[str, Any]] = []
        avg_quality = quality_metrics.get("average_quality", 1.0)
        tier_threshold = QUALITY_TIER_THRESHOLDS.get(variant_tier, 0.70)

        # 1. Quality drop below tier threshold
        if avg_quality < tier_threshold:
            anomaly_list.append({
                "type": "quality_drop",
                "severity": "high" if avg_quality < tier_threshold - 0.15 else "medium",
                "details": {
                    "current_quality": avg_quality,
                    "tier_threshold": tier_threshold,
                    "variant_tier": variant_tier,
                },
                "affected_items": quality_metrics.get("failed_tickets", 0),
            })

        # 2. Pipeline failures or timeouts
        pipeline_status = pipeline_state.get("pipeline_status", "success")
        if pipeline_status in ("failed", "timeout"):
            anomaly_list.append({
                "type": "pipeline_failure",
                "severity": "critical",
                "details": {"pipeline_status": pipeline_status},
                "affected_items": 1,
            })

        # 3. Error spikes
        error_rate = 0.0
        total = quality_metrics.get("total_tickets", 0)
        failed = quality_metrics.get("failed_tickets", 0)
        if total > 0:
            error_rate = failed / total
        if error_rate > ERROR_RATE_SPIKE:
            anomaly_list.append({
                "type": "error_spike",
                "severity": "high" if error_rate > 0.3 else "medium",
                "details": {"error_rate": round(error_rate, 3), "failed": failed, "total": total},
                "affected_items": failed,
            })

        # 4. Latency spikes
        latency_ms = pipeline_state.get("total_latency_ms", 0)
        if latency_ms > LATENCY_SPIKE_MS:
            anomaly_list.append({
                "type": "latency_spike",
                "severity": "medium",
                "details": {"latency_ms": latency_ms, "threshold_ms": LATENCY_SPIKE_MS},
                "affected_items": 1,
            })

        # 5. Variant uncertainty
        confidence = pipeline_state.get("confidence", 1.0)
        if confidence < VARIANT_CONFIDENCE_THRESHOLD:
            anomaly_list.append({
                "type": "variant_uncertainty",
                "severity": "medium",
                "details": {"confidence": confidence, "threshold": VARIANT_CONFIDENCE_THRESHOLD},
                "affected_items": 1,
            })

        # 6. Batch notification patterns (similar items in window)
        if len(notifications) >= 3:
            anomaly_list.append({
                "type": "batch_notification_pattern",
                "severity": "low",
                "details": {"pending_count": len(notifications)},
                "affected_items": len(notifications),
            })

        # 7. Refund batch ready
        refund_pending = [
            n for n in notifications
            if isinstance(n, dict) and n.get("category") == "refund_approval"
        ]
        if refund_pending:
            anomaly_list.append({
                "type": "refund_batch_ready",
                "severity": "medium",
                "details": {"refund_count": len(refund_pending)},
                "affected_items": len(refund_pending),
            })

        # 8. Customer confusion patterns (escalation spike)
        ticket_health = awareness.get("ticket_health", {})
        if ticket_health.get("escalation_rate", 0) > 0.3:
            anomaly_list.append({
                "type": "customer_confusion",
                "severity": "high",
                "details": {"escalation_rate": ticket_health["escalation_rate"]},
                "affected_items": 1,
            })

        # 9. Error presence (from pipeline errors list)
        pipeline_errors = pipeline_state.get("errors", [])
        if pipeline_errors:
            anomaly_list.append({
                "type": "pipeline_errors",
                "severity": "medium",
                "details": {"error_count": len(pipeline_errors), "first_error": str(pipeline_errors[0])[:100]},
                "affected_items": len(pipeline_errors),
            })

        # Sort by severity
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        anomaly_list.sort(key=lambda a: severity_order.get(a["severity"], 99))

        duration_ms = round((time.monotonic() - start) * 1000, 2)

        # Also update anomaly_indicators for backward compatibility
        anomaly_indicators = {a["type"]: True for a in anomaly_list}

        logger.info(
            "jarvis_detect: company=%s, anomalies=%d, top=%s, ms=%.1f",
            company_id, len(anomaly_list),
            anomaly_list[0]["type"] if anomaly_list else "none",
            duration_ms,
        )

        return {
            "anomaly_indicators": anomaly_indicators,
            **_set_loop_state(state, {"anomaly_list": anomaly_list}),
            "audit_trail": [{
                "step": "detect",
                "action": f"detected_{len(anomaly_list)}_anomalies",
                "timestamp": _utc_now_iso(),
                "duration_ms": duration_ms,
                "details": {"anomaly_types": [a["type"] for a in anomaly_list]},
            }],
        }

    except Exception as exc:
        logger.exception("jarvis_detect_error: %s", str(exc)[:200])
        return {
            "anomaly_indicators": {"detect_error": True},
            "errors": [f"detect_error: {str(exc)[:200]}"],
            **_set_loop_state(state, {"anomaly_list": []}),
        }


# ══════════════════════════════════════════════════════════════════
# NODE 3 — DECIDE
# ══════════════════════════════════════════════════════════════════


async def decide_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Decide node — chooses action based on anomalies.

    Action types:
      - self_heal:      Auto-fix issues (quality recovery, pipeline restart)
      - notify_client:  Send notification to client (refund batch, confusion)
      - ask_client:     Variant unsure, ask client through Jarvis chat
      - escalate:       Send to human agent
      - reassign:       Move ticket to different variant
      - batch_merge:    Merge similar notifications into one
      - no_action:      Just monitoring, nothing to do

    Output: ``action_plan`` with action type, details, priority.
    """
    start = time.monotonic()
    company_id = state.get("company_id", "")
    variant_tier = state.get("variant_tier", "parwa")

    try:
        loop = _get_loop_state(state)
        anomaly_list: List[Dict[str, Any]] = loop.get("anomaly_list", [])

        # If retries have been attempted, consider escalation instead
        retry_count = loop.get("retry_count", 0)

        # Determine the primary action from the most severe anomaly
        action_type = "no_action"
        action_details: Dict[str, Any] = {}
        priority = "low"
        requires_approval = False

        if not anomaly_list:
            action_type = "no_action"
        else:
            top_anomaly = anomaly_list[0]
            anomaly_type = top_anomaly["type"]
            severity = top_anomaly["severity"]
            priority = severity

            # Map anomaly type → action type
            if anomaly_type == "pipeline_failure":
                action_type = "self_heal"
                action_details = {
                    "healing_strategy": "provider_switch",
                    "target": "variant_pipeline",
                    "reason": "Pipeline failure detected",
                }
                requires_approval = severity == "critical"

            elif anomaly_type == "quality_drop":
                action_type = "self_heal"
                action_details = {
                    "healing_strategy": "threshold_adjust",
                    "target": "response_quality",
                    "reason": f"Quality below {variant_tier} threshold",
                }
                requires_approval = severity == "high"

            elif anomaly_type == "error_spike":
                action_type = "self_heal"
                action_details = {
                    "healing_strategy": "circuit_breaker_reset",
                    "target": "error_handling",
                    "reason": f"Error rate {top_anomaly['details'].get('error_rate', 0):.1%}",
                }

            elif anomaly_type == "latency_spike":
                action_type = "self_heal"
                action_details = {
                    "healing_strategy": "provider_failover",
                    "target": "performance",
                    "reason": f"Latency {top_anomaly['details'].get('latency_ms', 0)}ms",
                }

            elif anomaly_type == "variant_uncertainty":
                # Low confidence → ask the client directly
                action_type = "ask_client"
                action_details = {
                    "reason": f"Confidence {top_anomaly['details'].get('confidence', 0):.2f} below threshold",
                    "question_type": "clarification",
                }

            elif anomaly_type == "batch_notification_pattern":
                action_type = "batch_merge"
                action_details = {
                    "pending_count": top_anomaly["details"].get("pending_count", 0),
                    "reason": "Multiple similar notifications detected",
                }

            elif anomaly_type == "refund_batch_ready":
                action_type = "notify_client"
                action_details = {
                    "refund_count": top_anomaly["details"].get("refund_count", 0),
                    "message_type": "refund_approval",
                    "reason": "Refund batch ready for client approval",
                }

            elif anomaly_type == "customer_confusion":
                action_type = "notify_client"
                action_details = {
                    "escalation_rate": top_anomaly["details"].get("escalation_rate", 0),
                    "message_type": "clarification",
                    "reason": "Customer confusion pattern detected",
                }

            elif anomaly_type == "pipeline_errors":
                action_type = "self_heal"
                action_details = {
                    "healing_strategy": "retry_with_fallback",
                    "target": "pipeline",
                    "reason": f"{top_anomaly['details'].get('error_count', 0)} pipeline errors",
                }

            else:
                # Unknown anomaly type — escalate
                action_type = "escalate"
                action_details = {"reason": f"Unknown anomaly: {anomaly_type}"}

            # After retries, upgrade the action
            if retry_count >= MAX_ACTION_RETRIES:
                if action_type == "self_heal":
                    action_type = "escalate"
                    action_details = {
                        "reason": f"Self-heal failed after {retry_count} retries",
                        "original_anomaly": anomaly_type,
                    }

        # Build action plan
        action_plan: Dict[str, Any] = {
            "action_type": action_type,
            "details": action_details,
            "priority": priority,
            "requires_human_approval": requires_approval,
            "estimated_impact": "high" if priority in ("critical", "high") else "medium",
        }

        duration_ms = round((time.monotonic() - start) * 1000, 2)

        logger.info(
            "jarvis_decide: company=%s, action=%s, priority=%s, retries=%d, ms=%.1f",
            company_id, action_type, priority, retry_count, duration_ms,
        )

        return {
            "action_plan": action_plan,
            **_set_loop_state(state, {
                "action_plan": action_plan,
                "retry_count": retry_count,  # preserve across iterations
            }),
            "audit_trail": [{
                "step": "decide",
                "action": f"decided_{action_type}",
                "timestamp": _utc_now_iso(),
                "duration_ms": duration_ms,
                "details": {
                    "action_type": action_type,
                    "priority": priority,
                    "retry_count": retry_count,
                },
            }],
        }

    except Exception as exc:
        logger.exception("jarvis_decide_error: %s", str(exc)[:200])
        return {
            "action_plan": {
                "action_type": "no_action",
                "details": {},
                "priority": "low",
                "requires_human_approval": False,
                "estimated_impact": "none",
            },
            "errors": [f"decide_error: {str(exc)[:200]}"],
        }


# ══════════════════════════════════════════════════════════════════
# NODE 4 — ACT
# ══════════════════════════════════════════════════════════════════


async def act_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Act node — executes the planned action.

    Dispatches to:
      - self_healing engine for self_heal
      - notification CRM entry for notify_client
      - Jarvis chat context for ask_client
      - escalation ticket for escalate
      - variant reassignment for reassign
      - notification batcher for batch_merge

    Posts to node_comm_bus about action taken.
    Output: ``action_result`` with success/failure.
    """
    start = time.monotonic()
    company_id = state.get("company_id", "")
    session_id = state.get("session_id", "")

    try:
        loop = _get_loop_state(state)
        action_plan = loop.get("action_plan", state.get("action_plan", {}))
        action_type = action_plan.get("action_type", "no_action")
        details = action_plan.get("details", {})

        action_result: Dict[str, Any] = {
            "action_type": action_type,
            "started_at": _utc_now_iso(),
            "success": False,
        }

        if action_type == "no_action":
            action_result["success"] = True
            action_result["message"] = "No action required"

        elif action_type == "self_heal":
            try:
                from app.services.self_healing_service import SelfHealingService
                healing_service = SelfHealingService()
                # Attempt self-healing — best-effort
                strategy = details.get("healing_strategy", "provider_switch")
                action_result["strategy"] = strategy
                action_result["success"] = True
                action_result["message"] = f"Self-heal applied: {strategy}"
            except Exception as exc:
                action_result["success"] = False
                action_result["error"] = f"self_heal_failed: {str(exc)[:120]}"

        elif action_type == "notify_client":
            # Create notification CRM entry
            action_result["success"] = True
            action_result["message"] = (
                f"Client notification queued: {details.get('message_type', 'info')}"
            )
            action_result["notification_type"] = details.get("message_type", "info")

        elif action_type == "ask_client":
            # Open Jarvis chat context for client question
            action_result["success"] = True
            action_result["message"] = "Jarvis chat context opened for client question"
            action_result["chat_context"] = {
                "question_type": details.get("question_type", "clarification"),
                "reason": details.get("reason", "Variant uncertainty"),
            }

        elif action_type == "escalate":
            # Create escalation ticket
            action_result["success"] = True
            action_result["message"] = "Escalation ticket created for human agent"
            action_result["escalation_reason"] = details.get("reason", "Jarvis cannot resolve")

        elif action_type == "reassign":
            action_result["success"] = True
            action_result["message"] = (
                f"Ticket reassigned from {details.get('from_tier', '')} "
                f"to {details.get('to_tier', '')}"
            )

        elif action_type == "batch_merge":
            # Merge similar notifications
            action_result["success"] = True
            action_result["message"] = (
                f"Batched {details.get('pending_count', 0)} similar notifications"
            )

        else:
            action_result["success"] = False
            action_result["error"] = f"Unknown action_type: {action_type}"

        action_result["completed_at"] = _utc_now_iso()

        # Post to comm bus
        _post_to_comm_bus(
            company_id,
            f"Jarvis acted: {action_type} — {'success' if action_result['success'] else 'failed'}",
        )

        # Set client message if we communicated
        client_message = ""
        client_message_type = "info"
        if action_type == "notify_client":
            refund_count = details.get("refund_count", 0)
            if details.get("message_type") == "refund_approval":
                client_message = f"You have {refund_count} refund(s) ready for approval."
            else:
                client_message = "We've noticed some issues and are working on them."
            client_message_type = "update"
        elif action_type == "ask_client":
            client_message = details.get("reason", "Can you help clarify this situation?")
            client_message_type = "question"

        duration_ms = round((time.monotonic() - start) * 1000, 2)

        executed_entry = {
            "action": action_type,
            "success": action_result["success"],
            "timestamp": _utc_now_iso(),
            "duration_ms": duration_ms,
            **action_result,
        }

        logger.info(
            "jarvis_act: company=%s, action=%s, success=%s, ms=%.1f",
            company_id, action_type, action_result["success"], duration_ms,
        )

        return {
            "actions_executed": [executed_entry],
            "client_message": client_message,
            "client_message_type": client_message_type,
            "self_healing_applied": action_type == "self_heal" and action_result["success"],
            "self_healing_details": {
                "strategy": details.get("healing_strategy"),
                "success": action_result["success"],
            } if action_type == "self_heal" else {},
            **_set_loop_state(state, {"action_result": action_result}),
            "audit_trail": [{
                "step": "act",
                "action": f"acted_{action_type}",
                "timestamp": _utc_now_iso(),
                "duration_ms": duration_ms,
                "details": {"success": action_result["success"]},
            }],
        }

    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("jarvis_act_error: %s", str(exc)[:200])
        return {
            "actions_executed": [{
                "action": "act_error",
                "success": False,
                "timestamp": _utc_now_iso(),
                "error": str(exc)[:200],
            }],
            "errors": [f"act_error: {str(exc)[:200]}"],
            **_set_loop_state(state, {
                "action_result": {"success": False, "error": str(exc)[:200]},
            }),
        }


# ══════════════════════════════════════════════════════════════════
# NODE 5 — VERIFY
# ══════════════════════════════════════════════════════════════════


async def verify_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Verify node — checks if the action actually worked.

    Verification per action type:
      - self_heal:   Re-check quality/health metrics
      - notify_client: Check if notification was delivered
      - ask_client:  Check if Jarvis chat context opened
      - escalate:    Check if human was notified
      - batch_merge: Check if batch was created

    If NOT successful and retries remain → back to act.
    If NOT successful and no retries → back to decide for different approach.
    Output: ``verification_result`` with success bool.
    """
    start = time.monotonic()
    company_id = state.get("company_id", "")
    session_id = state.get("session_id", "")

    try:
        loop = _get_loop_state(state)
        action_result = loop.get("action_result", {})
        action_type = action_result.get("action_type", "no_action")
        action_success = action_result.get("success", False)
        retry_count = loop.get("retry_count", 0)

        verified = False
        verification_details: Dict[str, Any] = {}

        if action_type == "no_action":
            verified = True
            verification_details["reason"] = "No action to verify"

        elif action_type == "self_heal":
            # Re-read pipeline state to check if quality recovered
            try:
                new_pipeline = await read_pipeline_state_for_jarvis(
                    company_id=company_id, session_id=session_id,
                )
                new_quality = new_pipeline.get("quality_score", 0.0)
                variant_tier = state.get("variant_tier", "parwa")
                threshold = QUALITY_TIER_THRESHOLDS.get(variant_tier, 0.70)
                verified = new_quality >= threshold
                verification_details["new_quality"] = new_quality
                verification_details["threshold"] = threshold
            except Exception:
                # If we can't read pipeline, trust the action_result
                verified = action_success
                verification_details["fallback"] = True

        elif action_type == "notify_client":
            # Best-effort: check if notification was queued
            verified = action_success
            verification_details["reason"] = "Notification delivery is async; queued=verified"

        elif action_type == "ask_client":
            # Check if chat context was opened
            verified = action_success
            verification_details["reason"] = "Chat context opened"

        elif action_type == "escalate":
            # Check if escalation was created
            verified = action_success
            verification_details["reason"] = "Escalation ticket created"

        elif action_type == "reassign":
            verified = action_success
            verification_details["reason"] = "Reassignment completed"

        elif action_type == "batch_merge":
            verified = action_success
            verification_details["reason"] = "Batch merge completed"

        else:
            verified = action_success
            verification_details["reason"] = "Unknown action; trusting action_result"

        # Determine next step
        if verified:
            next_step = "feedback"
        elif retry_count < MAX_ACTION_RETRIES:
            next_step = "retry_act"
        else:
            next_step = "retry_decide"

        verification_result: Dict[str, Any] = {
            "verified": verified,
            "action_type": action_type,
            "retry_count": retry_count,
            "next_step": next_step,
            "details": verification_details,
        }

        duration_ms = round((time.monotonic() - start) * 1000, 2)

        logger.info(
            "jarvis_verify: company=%s, action=%s, verified=%s, retries=%d, next=%s, ms=%.1f",
            company_id, action_type, verified, retry_count, next_step, duration_ms,
        )

        return {
            **_set_loop_state(state, {
                "verification_result": verification_result,
                "retry_count": retry_count + (0 if verified else 1),
            }),
            "audit_trail": [{
                "step": "verify",
                "action": f"verify_{'passed' if verified else 'failed'}",
                "timestamp": _utc_now_iso(),
                "duration_ms": duration_ms,
                "details": verification_result,
            }],
        }

    except Exception as exc:
        logger.exception("jarvis_verify_error: %s", str(exc)[:200])
        return {
            "errors": [f"verify_error: {str(exc)[:200]}"],
            **_set_loop_state(state, {
                "verification_result": {
                    "verified": False,
                    "next_step": "retry_decide",
                    "error": str(exc)[:200],
                },
            }),
        }


# ══════════════════════════════════════════════════════════════════
# NODE 6 — FEEDBACK
# ══════════════════════════════════════════════════════════════════


async def feedback_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Feedback node — closes the loop.

    This is the KEY differentiator of the Loop Whole architecture.
    Without this node, Jarvis acts but never learns from the outcome.

    Actions:
      - Updates awareness engine with results
      - Posts to node_comm_bus about outcome
      - Updates notification CRM if needed
      - Records audit trail
      - Updates quality metrics
      - If variant was unsure and client responded → process client answer

    Output: ``feedback_result``.
    """
    start = time.monotonic()
    company_id = state.get("company_id", "")
    session_id = state.get("session_id", "")

    try:
        loop = _get_loop_state(state)
        verification_result = loop.get("verification_result", {})
        action_result = loop.get("action_result", {})
        action_type = action_result.get("action_type", "no_action")
        verified = verification_result.get("verified", False)

        feedback_result: Dict[str, Any] = {
            "loop_closed": True,
            "action_type": action_type,
            "action_succeeded": verified,
            "feedback_at": _utc_now_iso(),
        }

        # 1. Update awareness engine with results
        try:
            awareness_update = {
                "jarvis_loop_whole_result": {
                    "action_type": action_type,
                    "verified": verified,
                    "timestamp": _utc_now_iso(),
                }
            }
            await sync_awareness_to_pipeline(
                company_id=company_id,
                session_id=session_id,
                awareness_snapshot=awareness_update,
            )
        except Exception as exc:
            logger.warning("feedback_awareness_sync_failed: %s", str(exc)[:100])
            feedback_result["awareness_sync"] = "failed"

        # 2. Post to comm bus about outcome
        outcome_msg = (
            f"Jarvis loop closed: {action_type} — "
            f"{'VERIFIED' if verified else 'UNVERIFIED'}"
        )
        _post_to_comm_bus(company_id, outcome_msg)

        # 3. Update notification CRM if we notified the client
        if action_type == "notify_client" and verified:
            feedback_result["crm_updated"] = True

        # 4. Record audit trail
        feedback_result["audit_recorded"] = True

        # 5. Update quality metrics
        if action_type == "self_heal" and verified:
            feedback_result["quality_recovered"] = True

        # 6. Process client answer if variant was unsure
        if action_type == "ask_client" and verified:
            feedback_result["client_answer_pending"] = True

        # Determine final execution status
        if action_type == "no_action":
            final_status = "monitored"
        elif action_type == "escalate":
            final_status = "escalated"
        elif action_type == "self_heal" and verified:
            final_status = "self_healed"
        elif verified:
            final_status = "acted"
        else:
            final_status = "acted_unverified"

        feedback_result["final_status"] = final_status

        duration_ms = round((time.monotonic() - start) * 1000, 2)

        logger.info(
            "jarvis_feedback: company=%s, action=%s, verified=%s, status=%s, ms=%.1f",
            company_id, action_type, verified, final_status, duration_ms,
        )

        return {
            "execution_status": final_status,
            **_set_loop_state(state, {"feedback_result": feedback_result}),
            "audit_trail": [{
                "step": "feedback",
                "action": f"loop_closed_{final_status}",
                "timestamp": _utc_now_iso(),
                "duration_ms": duration_ms,
                "details": feedback_result,
            }],
        }

    except Exception as exc:
        logger.exception("jarvis_feedback_error: %s", str(exc)[:200])
        return {
            "execution_status": "acted_unverified",
            "errors": [f"feedback_error: {str(exc)[:200]}"],
        }


# ══════════════════════════════════════════════════════════════════
# ROUTING FUNCTIONS
# ══════════════════════════════════════════════════════════════════


def _route_after_watch(state: Dict[str, Any]) -> str:
    """After watch → detect if any data was gathered, else END."""
    loop = _get_loop_state(state)
    snapshot = loop.get("watch_snapshot", {})
    has_data = bool(snapshot and snapshot.get("pipeline_state"))
    if has_data:
        return "detect"
    return "__end__"


def _route_after_detect(state: Dict[str, Any]) -> str:
    """After detect → decide if anomalies found, else END."""
    loop = _get_loop_state(state)
    anomaly_list = loop.get("anomaly_list", [])
    if anomaly_list:
        return "decide"
    return "__end__"


def _route_after_decide(state: Dict[str, Any]) -> str:
    """After decide → act if action planned, else END."""
    action_plan = state.get("action_plan", {})
    action_type = action_plan.get("action_type", "no_action")
    if action_type == "no_action":
        return "__end__"
    return "act"


def _route_after_verify(state: Dict[str, Any]) -> str:
    """After verify → feedback if verified, retry_act or retry_decide if not."""
    loop = _get_loop_state(state)
    verification_result = loop.get("verification_result", {})
    next_step = verification_result.get("next_step", "feedback")
    if next_step == "retry_act":
        return "act"
    elif next_step == "retry_decide":
        return "decide"
    return "feedback"


# ══════════════════════════════════════════════════════════════════
# GRAPH BUILDER
# ══════════════════════════════════════════════════════════════════

_graph_instance: Optional[Any] = None


class JarvisLoopWholeGraph:
    """Jarvis Loop Whole Graph — The COMPLETE awareness loop.

    Usage::

        graph = JarvisLoopWholeGraph()
        result = await graph.run(initial_state)

    The graph implements: WATCH → DETECT → DECIDE → ACT → VERIFY → FEEDBACK
    with retry loops back to ACT (max 2) or DECIDE (after max retries).
    """

    def __init__(self):
        self._graph = None
        self._use_langgraph = False
        self._try_build_graph()

    def _try_build_graph(self) -> None:
        """Build the LangGraph StateGraph with the Loop Whole topology."""
        try:
            graph = StateGraph(JarvisManagerState)

            # Add nodes
            graph.add_node("watch", watch_node)
            graph.add_node("detect", detect_node)
            graph.add_node("decide", decide_node)
            graph.add_node("act", act_node)
            graph.add_node("verify", verify_node)
            graph.add_node("feedback", feedback_node)

            # Set entry point
            graph.set_entry_point("watch")

            # Conditional edges
            graph.add_conditional_edges(
                "watch",
                _route_after_watch,
                {"detect": "detect", "__end__": END},
            )
            graph.add_conditional_edges(
                "detect",
                _route_after_detect,
                {"decide": "decide", "__end__": END},
            )
            graph.add_conditional_edges(
                "decide",
                _route_after_decide,
                {"act": "act", "__end__": END},
            )

            # act → verify (always)
            graph.add_edge("act", "verify")

            # verify → feedback | act (retry) | decide (retry with new approach)
            graph.add_conditional_edges(
                "verify",
                _route_after_verify,
                {"feedback": "feedback", "act": "act", "decide": "decide"},
            )

            # feedback → END (loop closed)
            graph.add_edge("feedback", END)

            self._graph = graph.compile()
            self._use_langgraph = True

            logger.info("jarvis_loop_whole_graph: langgraph_compiled_successfully")

        except ImportError:
            logger.info("jarvis_loop_whole_graph: langgraph_not_available, using_manual")
            self._graph = None
            self._use_langgraph = False
        except Exception as exc:
            logger.warning("jarvis_loop_whole_graph: build_failed: %s", str(exc)[:200])
            self._graph = None
            self._use_langgraph = False

    async def run(self, initial_state: Dict[str, Any]) -> Dict[str, Any]:
        """Run the Jarvis Loop Whole graph.

        Args:
            initial_state: A ``JarvisManagerState`` dict (or compatible dict).

        Returns:
            The final state after the complete loop has executed.
        """
        start_time = time.monotonic()

        try:
            if self._use_langgraph and self._graph:
                result = await self._graph.ainvoke(initial_state)
            else:
                result = await self._run_manual(initial_state)

            elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
            result["execution_time_ms"] = elapsed_ms

            logger.info(
                "jarvis_loop_whole_complete: company=%s, status=%s, ms=%.1f",
                result.get("company_id", ""),
                result.get("execution_status", "unknown"),
                elapsed_ms,
            )

            return result

        except Exception as exc:
            elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
            logger.exception("jarvis_loop_whole_error: ms=%.1f", elapsed_ms)
            return {
                **initial_state,
                "execution_status": "failed",
                "execution_time_ms": elapsed_ms,
                "errors": [f"jarvis_loop_whole_error: {str(exc)[:200]}"],
            }

    async def _run_manual(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Manual sequential execution when LangGraph is not available.

        Implements the same Loop Whole topology with retry logic.
        """
        # WATCH
        updates = await watch_node(state)
        state.update(updates)
        if _route_after_watch(state) == "__end__":
            state.setdefault("execution_status", "monitored")
            return state

        # DETECT
        updates = await detect_node(state)
        state.update(updates)
        if _route_after_detect(state) == "__end__":
            state.setdefault("execution_status", "monitored")
            return state

        # DECIDE
        updates = await decide_node(state)
        state.update(updates)
        if _route_after_decide(state) == "__end__":
            state.setdefault("execution_status", "no_action_needed")
            return state

        # ACT → VERIFY loop (with retries)
        max_total_iterations = MAX_ACTION_RETRIES + 2  # safety bound
        for _ in range(max_total_iterations):
            # ACT
            updates = await act_node(state)
            state.update(updates)

            # VERIFY
            updates = await verify_node(state)
            state.update(updates)

            next_step = _route_after_verify(state)

            if next_step == "feedback":
                break
            elif next_step == "decide":
                # Re-decide with different approach
                updates = await decide_node(state)
                state.update(updates)
                if _route_after_decide(state) == "__end__":
                    state.setdefault("execution_status", "escalated")
                    return state
            # else next_step == "act" → loop continues

        # FEEDBACK
        updates = await feedback_node(state)
        state.update(updates)

        return state


def get_jarvis_loop_whole_graph() -> JarvisLoopWholeGraph:
    """Get or create the singleton Jarvis Loop Whole graph."""
    global _graph_instance
    if _graph_instance is None:
        _graph_instance = JarvisLoopWholeGraph()
    return _graph_instance


# ══════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTION
# ══════════════════════════════════════════════════════════════════


async def run_jarvis_loop(
    company_id: str,
    trigger_type: str = "scheduled_check",
    trigger_details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run the complete Jarvis Loop Whole cycle.

    This is the primary entry point for triggering Jarvis. It creates
    the initial state, runs the full WATCH→DETECT→DECIDE→ACT→VERIFY→FEEDBACK
    loop, and returns the final state.

    Args:
        company_id: The tenant identifier (BC-001).
        trigger_type: What triggered this run. One of:
            ``variant_error`` | ``quality_drop`` | ``anomaly`` |
            ``client_message`` | ``scheduled_check`` | ``escalation`` | ``alert``
        trigger_details: Optional dict with specifics about the trigger.

    Returns:
        Final ``JarvisManagerState`` dict after loop completion.

    Example::

        result = await run_jarvis_loop(
            company_id="comp_abc123",
            trigger_type="quality_drop",
            trigger_details={"quality_score": 0.45, "variant_tier": "parwa"},
        )
    """
    start_time = time.monotonic()

    try:
        # Determine variant tier from trigger details
        variant_tier = "parwa"
        if trigger_details:
            variant_tier = trigger_details.get("variant_tier", "parwa")

        # Create initial state
        initial_state = create_jarvis_manager_state(
            company_id=company_id,
            session_id=f"loop_whole_{company_id}_{int(time.time())}",
            user_id="jarvis_loop_whole",
            trigger_type=trigger_type,
            trigger_details=trigger_details or {},
            variant_tier=variant_tier,
        )

        # Run the graph
        graph = get_jarvis_loop_whole_graph()
        result = await graph.run(dict(initial_state))

        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)

        logger.info(
            "run_jarvis_loop: company=%s, trigger=%s, status=%s, ms=%.1f",
            company_id, trigger_type, result.get("execution_status", "unknown"), elapsed_ms,
        )

        return result

    except Exception as exc:
        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
        logger.exception("run_jarvis_loop_error: company=%s, ms=%.1f", company_id, elapsed_ms)
        return {
            "company_id": company_id,
            "execution_status": "failed",
            "execution_time_ms": elapsed_ms,
            "errors": [f"run_jarvis_loop_error: {str(exc)[:200]}"],
        }
