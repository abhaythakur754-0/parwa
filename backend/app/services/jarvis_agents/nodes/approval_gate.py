"""
PARWA Jarvis Approval Gate Node (Phase 4)

A LangGraph node for human-in-the-loop approval of Jarvis actions.
This sits in the COMMAND graph between specialist agents and the
command executor.

GRAPH TOPOLOGY (Phase 4):
  START → command_router → [agent_selector] → specialist_agent
        → approval_gate → command_executor → END

The approval_gate is a CRITICAL safety layer. Before Jarvis executes
any action, this node checks whether the action needs human approval
based on the variant tier:

  - mini_parwa: ALL actions need approval (Jarvis is in observe mode)
  - parwa: Only escalation + monetary actions need approval
  - parwa_high: Only emergency actions need approval

If approval is needed:
  - Sets execution_status = "pending_approval"
  - Creates an approval request record
  - Returns the approval details for the UI to display

If no approval needed:
  - Passes through to command_executor with execution_status = "approved"

This node ensures Jarvis never takes an action that's beyond its
authorization level for the current variant tier. It's the guardrail
that makes multi-agentic AI SAFE.

BC-008: Never crash — if approval check fails, default to requiring approval.
BC-012: All timestamps UTC.
"""

import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.logger import get_logger
from app.services.jarvis_agents.variant_bridge import (
    check_jarvis_approval_needed,
    get_variant_aware_command_config,
)

logger = get_logger("jarvis_approval_gate")


def approval_gate_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Check if a Jarvis command needs human approval before execution.

    Approval rules by variant_tier:
      - mini_parwa: ALL actions need approval (Jarvis is in observe mode)
      - parwa: Only escalation + monetary actions need approval
      - parwa_high: Only emergency actions need approval

    If approval is needed:
      - Sets execution_status = "pending_approval"
      - Writes a JarvisMessage asking for approval
      - Returns the approval request details

    If no approval needed:
      - Passes through to command_executor
      - Sets execution_status = "approved"

    Args:
        state: Current JarvisCommandState dict.

    Returns:
        Dict with updated EXECUTION group fields (execution_status,
        execution_result with approval details).
    """
    start_time = time.monotonic()

    try:
        company_id = state.get("company_id", "")
        session_id = state.get("session_id", "")
        user_id = state.get("user_id", "")
        variant_tier = state.get("variant_tier", "mini_parwa")
        agent_type = state.get("agent_type", "")
        agent_action = state.get("agent_action", "")
        agent_decision = state.get("agent_decision", {})
        agent_reasoning = state.get("agent_reasoning", "")

        # ── Check if approval is needed ──
        approval_check = check_jarvis_approval_needed(
            company_id=company_id,
            variant_tier=variant_tier,
            agent_type=agent_type,
            agent_action=agent_action,
        )

        approval_needed = approval_check.get("approval_needed", True)
        approval_reason = approval_check.get("reason", "Unknown")
        approval_type = approval_check.get("approval_type", "human")

        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)

        if approval_needed:
            # ── Create approval request ──
            approval_request = _create_approval_request(
                company_id=company_id,
                session_id=session_id,
                user_id=user_id,
                agent_type=agent_type,
                agent_action=agent_action,
                agent_decision=agent_decision,
                agent_reasoning=agent_reasoning,
                approval_reason=approval_reason,
                variant_tier=variant_tier,
            )

            result = {
                "execution_status": "pending_approval",
                "execution_result": {
                    "status": "pending_approval",
                    "approval_request_id": approval_request.get(
                        "request_id", "",
                    ),
                    "approval_type": approval_type,
                    "approval_reason": approval_reason,
                    "variant_tier": variant_tier,
                    "agent_type": agent_type,
                    "agent_action": agent_action,
                    "requested_at": datetime.now(timezone.utc).isoformat(),
                },
                "execution_time_ms": elapsed_ms,
                "node_outputs": {"approval_gate": approval_request},
                "audit_trail": [{
                    "step": "approval_gate",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "status": "pending_approval",
                    "approval_type": approval_type,
                    "approval_reason": approval_reason[:200],
                    "variant_tier": variant_tier,
                    "agent_type": agent_type,
                    "agent_action": agent_action,
                    "elapsed_ms": elapsed_ms,
                }],
            }

            logger.info(
                "approval_gate: PENDING — company=%s, session=%s, "
                "agent=%s, action=%s, tier=%s, reason=%s, ms=%.1f",
                company_id, session_id, agent_type, agent_action,
                variant_tier, approval_reason[:100], elapsed_ms,
            )

            return result

        else:
            # ── Auto-approved: pass through to executor ──
            result = {
                "execution_status": "approved",
                "execution_result": {
                    "status": "auto_approved",
                    "approval_type": approval_type,
                    "approval_reason": approval_reason,
                    "variant_tier": variant_tier,
                    "approved_at": datetime.now(timezone.utc).isoformat(),
                },
                "node_outputs": {"approval_gate": {
                    "status": "auto_approved",
                    "approval_type": approval_type,
                    "approval_reason": approval_reason[:200],
                    "variant_tier": variant_tier,
                }},
                "audit_trail": [{
                    "step": "approval_gate",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "status": "auto_approved",
                    "approval_type": approval_type,
                    "variant_tier": variant_tier,
                    "agent_type": agent_type,
                    "agent_action": agent_action,
                    "elapsed_ms": elapsed_ms,
                }],
            }

            logger.info(
                "approval_gate: AUTO-APPROVED — company=%s, session=%s, "
                "agent=%s, action=%s, tier=%s, ms=%.1f",
                company_id, session_id, agent_type, agent_action,
                variant_tier, elapsed_ms,
            )

            return result

    except Exception as e:
        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
        logger.exception("approval_gate_error: ms=%.1f", elapsed_ms)

        # BC-008: On error, require approval (safest default)
        return {
            "execution_status": "pending_approval",
            "execution_result": {
                "status": "pending_approval",
                "approval_type": "human",
                "approval_reason": (
                    f"Approval gate error: {str(e)[:200]}. "
                    f"Requiring human approval for safety."
                ),
                "error": str(e)[:200],
            },
            "execution_time_ms": elapsed_ms,
            "errors": [f"approval_gate: {str(e)[:200]}"],
            "node_outputs": {"approval_gate": {"error": str(e)[:200]}},
        }


def _create_approval_request(
    company_id: str,
    session_id: str,
    user_id: str,
    agent_type: str,
    agent_action: str,
    agent_decision: Dict[str, Any],
    agent_reasoning: str,
    approval_reason: str,
    variant_tier: str,
) -> Dict[str, Any]:
    """Create a structured approval request for the UI.

    This builds the approval request that gets displayed to the human
    operator. It includes all context needed to make an informed
    approval/rejection decision.

    Args:
        company_id: Company ID for BC-001.
        session_id: CC session ID.
        user_id: User ID for the approval request.
        agent_type: Which agent is requesting approval.
        agent_action: What action the agent wants to take.
        agent_decision: Full agent decision dict.
        agent_reasoning: Agent's reasoning for the decision.
        approval_reason: Why human approval is needed.
        variant_tier: Current variant tier.

    Returns:
        Dict with approval request details.
    """
    import uuid

    request_id = f"apr_{uuid.uuid4().hex[:16]}"

    request = {
        "request_id": request_id,
        "company_id": company_id,
        "session_id": session_id,
        "requested_by": user_id,
        "agent_type": agent_type,
        "agent_action": agent_action,
        "agent_decision_summary": _summarize_decision(agent_decision),
        "agent_reasoning": agent_reasoning[:500] if agent_reasoning else "",
        "approval_reason": approval_reason,
        "variant_tier": variant_tier,
        "requested_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
        "expires_at": None,  # No expiry by default
    }

    # Try to persist the approval request to DB
    try:
        _persist_approval_request(request)
    except Exception as e:
        logger.debug(
            "approval_request_persist_failed: id=%s, error=%s",
            request_id, str(e)[:200],
        )

    return request


def _summarize_decision(decision: Dict[str, Any]) -> Dict[str, Any]:
    """Create a concise summary of the agent decision for the approval UI.

    Args:
        decision: Full agent decision dict.

    Returns:
        Summary dict with key fields only.
    """
    if not decision:
        return {}

    # Extract the most important fields for the approval UI
    summary: Dict[str, Any] = {}

    # Common fields across all agent types
    for key in ("action", "scope", "strategy", "reason", "escalation_tier",
                "channel", "severity", "ticket_count", "from_agent", "to_agent"):
        if key in decision:
            summary[key] = decision[key]

    # Include the decision source (LLM vs rule-based)
    if "_source" in decision:
        summary["decision_source"] = decision["_source"]

    return summary


def _persist_approval_request(request: Dict[str, Any]) -> None:
    """Persist the approval request to DB for audit trail.

    Args:
        request: Approval request dict.
    """
    try:
        from database.base import SessionLocal
        from database.models.jarvis import JarvisMessage, JarvisSession

        db = SessionLocal()
        try:
            session = db.query(JarvisSession).filter(
                JarvisSession.id == request["session_id"],
                JarvisSession.company_id == request["company_id"],
            ).first()

            if session:
                # Create an approval request message in the chat
                content = (
                    f"**Approval Required**\n\n"
                    f"Jarvis wants to: **{request['agent_action']}** "
                    f"(via {request['agent_type']} agent)\n\n"
                    f"Reason: {request['approval_reason']}\n\n"
                    f"Agent reasoning: {request['agent_reasoning'][:300]}\n\n"
                    f"Variant tier: {request['variant_tier']}\n\n"
                    f"Request ID: `{request['request_id']}`"
                )

                msg = JarvisMessage(
                    session_id=request["session_id"],
                    role="jarvis",
                    content=content,
                    message_type="approval_request",
                    metadata_json=json.dumps({
                        "request_id": request["request_id"],
                        "agent_type": request["agent_type"],
                        "agent_action": request["agent_action"],
                        "approval_reason": request["approval_reason"],
                        "variant_tier": request["variant_tier"],
                        "decision_summary": request["agent_decision_summary"],
                        "injected_by": "jarvis_approval_gate",
                    }),
                )
                db.add(msg)
                db.commit()

        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    except Exception as e:
        logger.debug(
            "approval_request_db_failed: id=%s, error=%s",
            request.get("request_id", ""), str(e)[:200],
        )


def process_approval_response(
    company_id: str,
    request_id: str,
    approved: bool,
    approver_id: str,
    approver_notes: str = "",
) -> Dict[str, Any]:
    """Process a human approval/rejection response.

    Called by the API when a human approves or rejects a pending
    Jarvis action. Updates the approval request status and, if
    approved, re-runs the command graph from the approval_gate
    with execution_status="approved".

    Args:
        company_id: Company ID for BC-001.
        request_id: The approval request ID.
        approved: Whether the action was approved.
        approver_id: ID of the human who approved/rejected.
        approver_notes: Optional notes from the approver.

    Returns:
        Dict with the approval response result.
    """
    try:
        result = {
            "request_id": request_id,
            "company_id": company_id,
            "approved": approved,
            "approver_id": approver_id,
            "approver_notes": approver_notes,
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }

        if approved:
            result["status"] = "approved"
            result["next_step"] = "command_executor"
        else:
            result["status"] = "rejected"
            result["next_step"] = "end"

        logger.info(
            "approval_response: request=%s, approved=%s, "
            "approver=%s, company=%s",
            request_id, approved, approver_id, company_id,
        )

        return result

    except Exception as e:
        logger.warning(
            "approval_response_failed: request=%s, error=%s",
            request_id, str(e)[:200],
        )
        return {
            "request_id": request_id,
            "status": "error",
            "error": str(e)[:200],
        }
