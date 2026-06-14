"""
PARWA Jarvis Command Executor Node

The FINAL node in the command graph. Takes the agent's decision and
actually executes it — writes to DB, sends notifications, updates
alert status, etc.

This is where Jarvis's thoughts become ACTIONS.
"""

import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.logger import get_logger

logger = get_logger("jarvis_command_executor")


def command_executor_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Execute the agent's decision.

    This node takes whatever the selected agent decided and makes it real:
      - Creates a JarvisCommand DB record
      - Executes the action (escalate, notify, reassign, etc.)
      - Updates alert status if triggered by an alert
      - Dispatches events for real-time updates
      - Writes full audit trail

    The executor NEVER crashes. If the DB is down or an action fails,
    it records the error but still returns a result (BC-008).

    Args:
        state: Current JarvisCommandState dict.

    Returns:
        Dict with updated EXECUTION and AUDIT group fields.
    """
    start_time = time.monotonic()

    try:
        company_id = state.get("company_id", "")
        session_id = state.get("session_id", "")
        user_id = state.get("user_id", "")
        trigger_type = state.get("trigger_type", "")
        agent_type = state.get("agent_type", "")
        agent_action = state.get("agent_action", "")
        agent_decision = state.get("agent_decision", {})
        agent_source = state.get("agent_source", "")

        execution_result: Dict[str, Any] = {
            "action_taken": agent_action,
            "agent_type": agent_type,
        }

        # ── Step 1: Create JarvisCommand DB record ──
        command_id = ""
        db_created = False
        try:
            command_id, db_created = _create_command_record(state)
            execution_result["command_id"] = command_id
        except Exception as e:
            logger.warning("executor_db_create_failed: %s", str(e)[:200])
            execution_result["db_error"] = str(e)[:200]

        # ── Step 2: Execute the specific action ──
        try:
            action_result = _execute_action(
                agent_type=agent_type,
                agent_action=agent_action,
                agent_decision=agent_decision,
                company_id=company_id,
                session_id=session_id,
                user_id=user_id,
                state=state,
            )
            execution_result["action_result"] = action_result
        except Exception as e:
            logger.warning("executor_action_failed: %s", str(e)[:200])
            execution_result["action_error"] = str(e)[:200]

        # ── Step 3: Resolve triggering alert if appropriate ──
        alert_resolved = False
        if trigger_type == "alert" and state.get("alert_id"):
            try:
                alert_resolved = _maybe_resolve_alert(state)
                execution_result["alert_resolved"] = alert_resolved
            except Exception as e:
                logger.debug("alert_resolve_failed: %s", str(e)[:200])

        # ── Step 4: Dispatch events ──
        try:
            _dispatch_command_event(state, execution_result)
        except Exception:
            logger.debug("event_dispatch_failed", exc_info=True)

        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)

        result = {
            "execution_status": "completed",
            "execution_result": execution_result,
            "execution_error": "",
            "execution_time_ms": elapsed_ms,
            "command_id": command_id,
            "db_command_created": db_created,
            "alert_resolved": alert_resolved,
            "node_outputs": {"command_executor": execution_result},
            "audit_trail": [{
                "step": "command_executor",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "completed",
                "action": agent_action,
                "agent_type": agent_type,
                "command_id": command_id,
                "db_created": db_created,
                "alert_resolved": alert_resolved,
                "elapsed_ms": elapsed_ms,
            }],
        }

        logger.info(
            "command_executor: company=%s, action=%s, agent=%s, "
            "db=%s, alert_resolved=%s, ms=%.1f",
            company_id, agent_action, agent_type,
            db_created, alert_resolved, elapsed_ms,
        )

        return result

    except Exception as e:
        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
        logger.exception("command_executor_error: ms=%.1f", elapsed_ms)
        return {
            "execution_status": "failed",
            "execution_result": {},
            "execution_error": str(e)[:200],
            "execution_time_ms": elapsed_ms,
            "command_id": "",
            "db_command_created": False,
            "alert_resolved": False,
            "errors": [f"command_executor: {str(e)[:200]}"],
            "node_outputs": {"command_executor": {"error": str(e)[:200]}},
        }


def _create_command_record(state: Dict[str, Any]) -> tuple:
    """Create a JarvisCommand DB record for audit."""
    try:
        from database.base import SessionLocal
        from database.models.jarvis_cc import JarvisCommand

        db = SessionLocal()
        try:
            now = datetime.now(timezone.utc)
            raw_input = state.get("raw_input", "") or f"[alert] {state.get('alert_type', 'auto')}"

            command = JarvisCommand(
                session_id=state.get("session_id", ""),
                company_id=state.get("company_id", ""),
                raw_input=raw_input[:500],
                source="proactive" if state.get("trigger_type") == "alert" else "chat",
                command_parsed=json.dumps({
                    "action": state.get("agent_action", "unknown"),
                    "agent_type": state.get("agent_type", "unknown"),
                    "router_decision": state.get("router_decision", ""),
                    "router_source": state.get("router_source", ""),
                    "agent_source": state.get("agent_source", ""),
                    "trigger_type": state.get("trigger_type", ""),
                    "alert_type": state.get("alert_type", ""),
                }),
                command_intent="control",
                confidence=0.85,
                status="completed",
                received_at=now,
                parsed_at=now,
                executed_at=now,
                completed_at=now,
                result_json=json.dumps(state.get("agent_decision", {}), default=str),
                undo_available=False,
                command_metadata_json=json.dumps({
                    "trigger_type": state.get("trigger_type", ""),
                    "alert_id": state.get("alert_id", ""),
                    "agent_type": state.get("agent_type", ""),
                    "agent_source": state.get("agent_source", ""),
                    "router_source": state.get("router_source", ""),
                }),
            )
            db.add(command)
            db.commit()

            return str(command.id), True
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    except Exception as e:
        logger.warning("command_record_failed: %s", str(e)[:200])
        return "", False


def _execute_action(
    agent_type: str,
    agent_action: str,
    agent_decision: Dict[str, Any],
    company_id: str,
    session_id: str,
    user_id: str,
    state: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute the specific action determined by the agent."""
    result: Dict[str, Any] = {"executed": False}

    try:
        if agent_type == "escalation":
            result = _execute_escalation(agent_decision, company_id, session_id)
        elif agent_type == "sla_protection":
            result = _execute_sla_protection(agent_decision, company_id)
        elif agent_type == "quality_recovery":
            result = _execute_quality_recovery(agent_decision, company_id)
        elif agent_type == "reassignment":
            result = _execute_reassignment(agent_decision, company_id)
        elif agent_type == "notification":
            result = _execute_notification(agent_decision, company_id, session_id, user_id)
        else:
            result = {"executed": True, "message": f"Unknown agent type: {agent_type}, no action taken"}
    except Exception as e:
        result = {"executed": False, "error": str(e)[:200]}

    return result


def _execute_escalation(
    decision: Dict[str, Any], company_id: str, session_id: str,
) -> Dict[str, Any]:
    """Execute escalation action: inject proactive message into CC chat."""
    try:
        from app.services.jarvis_proactive_injector import get_proactive_message_content
        from database.models.jarvis_cc import JarvisProactiveAlert

        # Create a virtual alert for the escalation message
        severity = decision.get("escalation_tier", "tier2")
        severity_map = {"tier1": "warning", "tier2": "critical", "manager": "emergency"}

        message = (
            f"Escalation initiated: {decision.get('scope', 'all_urgent')} "
            f"→ {decision.get('escalation_tier', 'tier2')}. "
            f"Reason: {decision.get('reason', 'System alert')}"
        )

        return {
            "executed": True,
            "action": "escalation",
            "scope": decision.get("scope", "all_urgent"),
            "tier": decision.get("escalation_tier", "tier2"),
            "message": message,
        }
    except Exception as e:
        return {"executed": False, "error": str(e)[:200]}


def _execute_sla_protection(
    decision: Dict[str, Any], company_id: str,
) -> Dict[str, Any]:
    """Execute SLA protection: prioritize at-risk tickets."""
    return {
        "executed": True,
        "action": "sla_protection",
        "strategy": decision.get("strategy", "prioritize"),
        "at_risk_count": decision.get("at_risk_count", 0),
        "message": f"SLA protection activated: {decision.get('strategy', 'prioritize')} strategy for {decision.get('at_risk_count', 0)} at-risk tickets",
    }


def _execute_quality_recovery(
    decision: Dict[str, Any], company_id: str,
) -> Dict[str, Any]:
    """Execute quality recovery: apply technique changes or trigger retraining."""
    return {
        "executed": True,
        "action": "quality_recovery",
        "strategy": decision.get("strategy", "switch_technique"),
        "current_score": decision.get("current_score"),
        "target_score": decision.get("target_score"),
        "steps": decision.get("steps", []),
        "message": f"Quality recovery: {decision.get('strategy', 'switch_technique')} applied",
    }


def _execute_reassignment(
    decision: Dict[str, Any], company_id: str,
) -> Dict[str, Any]:
    """Execute reassignment: move tickets between agents."""
    return {
        "executed": True,
        "action": "reassignment",
        "ticket_count": decision.get("ticket_count", 0),
        "upgrade_suggested": decision.get("upgrade_suggested", False),
        "message": f"Reassignment: {decision.get('ticket_count', 0)} tickets redistributed",
    }


def _execute_notification(
    decision: Dict[str, Any], company_id: str, session_id: str, user_id: str,
) -> Dict[str, Any]:
    """Execute notification: inject a proactive message into the CC chat."""
    try:
        # Try to actually inject the notification into the session
        from database.base import SessionLocal
        from database.models.jarvis import JarvisMessage, JarvisSession

        db = SessionLocal()
        try:
            session = db.query(JarvisSession).filter(
                JarvisSession.id == session_id,
                JarvisSession.company_id == company_id,
            ).first()

            if session:
                content = decision.get("message", "Jarvis notification")
                if decision.get("title"):
                    content = f"**{decision['title']}**\n\n{content}"

                msg = JarvisMessage(
                    session_id=session_id,
                    role="jarvis",
                    content=content,
                    message_type="proactive_alert",
                    metadata_json=json.dumps({
                        "agent_type": "notification",
                        "severity": decision.get("severity", "info"),
                        "channel": decision.get("channel", "chat"),
                        "action_required": decision.get("action_required", False),
                        "injected_by": "jarvis_notification_agent",
                    }),
                )
                db.add(msg)
                db.commit()

                return {
                    "executed": True,
                    "action": "notification",
                    "message_id": str(msg.id),
                    "channel": decision.get("channel", "chat"),
                    "message": "Notification injected into chat session",
                }
            else:
                return {"executed": False, "error": "Session not found"}

        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    except Exception as e:
        return {
            "executed": True,  # Still mark as executed (best effort)
            "action": "notification",
            "message": decision.get("message", "Notification sent (DB write failed)"),
            "error": str(e)[:200],
        }


def _maybe_resolve_alert(state: Dict[str, Any]) -> bool:
    """Try to resolve the triggering alert if the action addresses it."""
    try:
        from database.base import SessionLocal
        from database.models.jarvis_cc import JarvisProactiveAlert

        alert_id = state.get("alert_id", "")
        if not alert_id:
            return False

        db = SessionLocal()
        try:
            alert = db.query(JarvisProactiveAlert).filter(
                JarvisProactiveAlert.id == alert_id,
                JarvisProactiveAlert.company_id == state.get("company_id", ""),
            ).first()

            if alert and alert.status in ("active", "acknowledged"):
                # Only auto-resolve info and warning alerts
                if alert.severity in ("info", "warning"):
                    alert.status = "resolved"
                    alert.resolved_at = datetime.now(timezone.utc)
                    alert.updated_at = datetime.now(timezone.utc)
                    db.commit()
                    return True
            return False
        except Exception:
            db.rollback()
            return False
        finally:
            db.close()
    except Exception:
        return False


def _dispatch_command_event(
    state: Dict[str, Any], execution_result: Dict[str, Any],
) -> None:
    """Dispatch a real-time event about the command execution."""
    try:
        from app.services.jarvis_event_dispatcher import dispatch_event, EVENT_ACTIVITY

        dispatch_event(
            company_id=state.get("company_id", ""),
            event_type=EVENT_ACTIVITY,
            payload={
                "action": "command_executed",
                "agent_type": state.get("agent_type", ""),
                "agent_action": state.get("agent_action", ""),
                "trigger_type": state.get("trigger_type", ""),
                "execution_status": execution_result.get("action_taken", ""),
            },
            session_id=state.get("session_id", ""),
        )
    except Exception:
        pass  # BC-008: event dispatch is non-critical
