"""
State Update Node — Group 11: Final State Persistence

Runs at the END of every flow. Performs all final bookkeeping:
persistence, audit logging, ticket management, metrics, and
Agent Lightning 50-mistake rule checks.

Persistence Steps (in order):
  1. Write audit log
  2. Persist GSD state
  3. Update ticket (create if needed, update if existing)
  4. Push to Jarvis awareness feed
  5. Update metrics counters
  6. Check Agent Lightning 50-mistake rule
  7. Record node execution log entry

State Contract:
  Reads:  Everything — this is the final bookkeeping node.
          Key fields: tenant_id, conversation_id, ticket_id,
          customer_id, variant_tier, agent_response, delivery_status,
          gsd_state, intent, agent_type, approval_decision
  Writes: ticket_created, ticket_updated, ticket_status,
          gsd_state_persisted, audit_log_written, metrics_updated,
          jarvis_feed_pushed, fifty_mistake_check,
          node_execution_log (append), delivery_timestamp, delivery_status

BC-008: If persistence fails, log error but don't crash. Each
        sub-step is independently wrapped so one failure doesn't
        block the others.
BC-001: All log entries include tenant_id for multi-tenant isolation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List
from uuid import uuid4

from app.logger import get_logger

logger = get_logger("node_state_update")


# ──────────────────────────────────────────────────────────────
# Default fallback values for State Update output
# ──────────────────────────────────────────────────────────────

_DEFAULT_STATE_UPDATE: Dict[str, Any] = {
    "ticket_created": False,
    "ticket_updated": False,
    "ticket_status": "open",
    "gsd_state_persisted": False,
    "audit_log_written": False,
    "metrics_updated": False,
    "jarvis_feed_pushed": False,
    "fifty_mistake_check": {},
}


# ═══════════════════════════════════════════════════════════════
# Sub-step 1: Write Audit Log
# ═══════════════════════════════════════════════════════════════


def _write_audit_log(state: Dict[str, Any], tenant_id: str) -> bool:
    """
    Write an audit log entry for this conversation flow.

    Uses the production state_serialization module if available,
    otherwise logs to the application logger as a fallback.

    Args:
        state: Current ParwaGraphState dict.
        tenant_id: Tenant identifier (BC-001).

    Returns:
        True if audit log was written successfully.
    """
    try:
        from app.core.state_serialization import write_audit_log  # type: ignore[import-untyped]

        write_audit_log(
            tenant_id=tenant_id,
            conversation_id=state.get("conversation_id", ""),
            customer_id=state.get("customer_id", ""),
            intent=state.get("intent", "unknown"),
            agent_type=state.get("agent_type", ""),
            action_type=state.get("action_type", "informational"),
            approval_decision=state.get("approval_decision", ""),
            delivery_status=state.get("delivery_status", ""),
        )
        return True

    except ImportError:
        logger.info(
            "state_serialization_unavailable_audit_log",
            tenant_id=tenant_id,
        )
    except Exception as exc:
        logger.warning(
            "audit_log_write_failed",
            tenant_id=tenant_id,
            error=str(exc),
        )

    return False


# ═══════════════════════════════════════════════════════════════
# Sub-step 2: Persist GSD State
# ═══════════════════════════════════════════════════════════════


def _persist_gsd_state(state: Dict[str, Any], tenant_id: str) -> bool:
    """
    Persist the GSD (Guided Support Dialogue) state to database.

    Uses the production gsd_engine module if available.

    Args:
        state: Current ParwaGraphState dict.
        tenant_id: Tenant identifier (BC-001).

    Returns:
        True if GSD state was persisted successfully.
    """
    try:
        from app.core.gsd_engine import persist_state  # type: ignore[import-untyped]

        persist_state(
            tenant_id=tenant_id,
            conversation_id=state.get("conversation_id", ""),
            gsd_state=state.get("gsd_state", "new"),
            gsd_step=state.get("gsd_step", ""),
            customer_id=state.get("customer_id", ""),
        )
        return True

    except ImportError:
        logger.info(
            "gsd_engine_unavailable_persist",
            tenant_id=tenant_id,
        )
    except Exception as exc:
        logger.warning(
            "gsd_state_persist_failed",
            tenant_id=tenant_id,
            error=str(exc),
        )

    return False


# ═══════════════════════════════════════════════════════════════
# Sub-step 3: Update Ticket
# ═══════════════════════════════════════════════════════════════


def _update_ticket(state: Dict[str, Any], tenant_id: str) -> Dict[str, Any]:
    """
    Create or update the support ticket for this conversation.

    If ticket_id is empty, creates a new ticket. Otherwise updates
    the existing ticket with the latest state.

    Args:
        state: Current ParwaGraphState dict.
        tenant_id: Tenant identifier (BC-001).

    Returns:
        Dict with ticket_created, ticket_updated, ticket_status, ticket_id.
    """
    ticket_id = state.get("ticket_id", "")
    ticket_created = False
    ticket_updated = False
    ticket_status = state.get("ticket_status", "open")

    try:
        from app.core.state_serialization import (  # type: ignore[import-untyped]
            create_ticket,
            update_ticket,
        )

        if not ticket_id:
            # Create new ticket
            result = create_ticket(
                tenant_id=tenant_id,
                customer_id=state.get("customer_id", ""),
                conversation_id=state.get("conversation_id", ""),
                intent=state.get("intent", "general"),
                agent_type=state.get("agent_type", ""),
                priority=state.get("urgency", "low"),
            )
            ticket_id = result.get("ticket_id", "")
            ticket_created = bool(ticket_id)
            ticket_status = result.get("status", "open")
        else:
            # Update existing ticket
            update_ticket(
                ticket_id=ticket_id,
                tenant_id=tenant_id,
                status=ticket_status,
                agent_type=state.get("agent_type", ""),
                resolution=state.get("agent_response", "")[:500],
            )
            ticket_updated = True

    except ImportError:
        logger.info(
            "state_serialization_unavailable_ticket",
            tenant_id=tenant_id,
        )
    except Exception as exc:
        logger.warning(
            "ticket_update_failed",
            tenant_id=tenant_id,
            ticket_id=ticket_id,
            error=str(exc),
        )

    return {
        "ticket_created": ticket_created,
        "ticket_updated": ticket_updated,
        "ticket_status": ticket_status,
        "ticket_id": ticket_id,
    }


# ═══════════════════════════════════════════════════════════════
# Sub-step 4: Push to Jarvis Awareness Feed
# ═══════════════════════════════════════════════════════════════


def _push_jarvis_feed(state: Dict[str, Any], tenant_id: str) -> bool:
    """
    Push state summary to Jarvis Command Center awareness feed.

    Allows Jarvis to maintain system-wide awareness of all
    conversation flows in real-time.

    Args:
        state: Current ParwaGraphState dict.
        tenant_id: Tenant identifier (BC-001).

    Returns:
        True if pushed successfully.
    """
    try:
        from app.core.state_serialization import push_jarvis_feed  # type: ignore[import-untyped]

        push_jarvis_feed(
            tenant_id=tenant_id,
            conversation_id=state.get("conversation_id", ""),
            customer_id=state.get("customer_id", ""),
            intent=state.get("intent", "general"),
            agent_type=state.get("agent_type", ""),
            delivery_status=state.get("delivery_status", ""),
            variant_tier=state.get("variant_tier", "mini"),
        )
        return True

    except ImportError:
        logger.info(
            "state_serialization_unavailable_jarvis",
            tenant_id=tenant_id,
        )
    except Exception as exc:
        logger.warning(
            "jarvis_feed_push_failed",
            tenant_id=tenant_id,
            error=str(exc),
        )

    return False


# ═══════════════════════════════════════════════════════════════
# Sub-step 5: Update Metrics Counters
# ═══════════════════════════════════════════════════════════════


def _update_metrics(state: Dict[str, Any], tenant_id: str) -> bool:
    """
    Increment metrics counters for this tenant and flow.

    Tracks conversation counts, response times, channel usage,
    agent utilization, and tier-specific metrics.

    Args:
        state: Current ParwaGraphState dict.
        tenant_id: Tenant identifier (BC-001).

    Returns:
        True if metrics were updated successfully.
    """
    try:
        from app.core.state_serialization import update_metrics  # type: ignore[import-untyped]

        update_metrics(
            tenant_id=tenant_id,
            variant_tier=state.get("variant_tier", "mini"),
            channel=state.get("delivery_channel", state.get("channel", "email")),
            intent=state.get("intent", "general"),
            agent_type=state.get("agent_type", ""),
            delivery_status=state.get("delivery_status", ""),
        )
        return True

    except ImportError:
        logger.info(
            "state_serialization_unavailable_metrics",
            tenant_id=tenant_id,
        )
    except Exception as exc:
        logger.warning(
            "metrics_update_failed",
            tenant_id=tenant_id,
            error=str(exc),
        )

    return False


# ═══════════════════════════════════════════════════════════════
# Sub-step 6: Agent Lightning 50-Mistake Rule Check
# ═══════════════════════════════════════════════════════════════


def _check_fifty_mistake_rule(state: Dict[str, Any], tenant_id: str) -> Dict[str, Any]:
    """
    Check the Agent Lightning 50-mistake rule for this agent.

    If an agent accumulates 50 mistakes, it triggers automatic
    retraining. This check increments the mistake counter if
    the current interaction was flagged as a mistake.

    Args:
        state: Current ParwaGraphState dict.
        tenant_id: Tenant identifier (BC-001).

    Returns:
        Dict with agent_id, mistake_count, training_needed.
    """
    result: Dict[str, Any] = {
        "agent_id": state.get("agent_type", ""),
        "mistake_count": 0,
        "training_needed": False,
    }

    try:
        from app.core.state_serialization import check_fifty_mistake  # type: ignore[import-untyped]

        check_result = check_fifty_mistake(
            tenant_id=tenant_id,
            agent_id=state.get("agent_type", ""),
            red_flag=state.get("red_flag", False),
            guardrails_passed=state.get("guardrails_passed", True),
        )

        result = {
            "agent_id": state.get("agent_type", ""),
            "mistake_count": check_result.get("mistake_count", 0),
            "training_needed": check_result.get("training_needed", False),
        }

    except ImportError:
        logger.info(
            "state_serialization_unavailable_fifty_mistake",
            tenant_id=tenant_id,
        )
    except Exception as exc:
        logger.warning(
            "fifty_mistake_check_failed",
            tenant_id=tenant_id,
            error=str(exc),
        )

    return result


# ═══════════════════════════════════════════════════════════════
# LangGraph Node Function
# ═══════════════════════════════════════════════════════════════


def state_update_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    State Update Node — Final persistence and bookkeeping.

    Runs at the END of every flow. Performs all final bookkeeping:
      1. Write audit log
      2. Persist GSD state
      3. Update ticket (create if needed, update if existing)
      4. Push to Jarvis awareness feed
      5. Update metrics counters
      6. Check Agent Lightning 50-mistake rule
      7. Record node execution log entry

    Each sub-step is independently wrapped so one failure doesn't
    block the others (BC-008).

    Args:
        state: Current ParwaGraphState dict.

    Returns:
        Partial state update with persistence status fields.
    """
    tenant_id = state.get("tenant_id", "unknown")
    now = datetime.now(timezone.utc).isoformat()

    logger.info(
        "state_update_node_start",
        tenant_id=tenant_id,
        variant_tier=state.get("variant_tier", "mini"),
        conversation_id=state.get("conversation_id", ""),
    )

    try:
        # ── Step 1: Write Audit Log ──────────────────────────────
        audit_log_written = _write_audit_log(state, tenant_id)

        # ── Step 2: Persist GSD State ────────────────────────────
        gsd_state_persisted = _persist_gsd_state(state, tenant_id)

        # ── Step 3: Update Ticket ────────────────────────────────
        ticket_result = _update_ticket(state, tenant_id)

        # ── Step 4: Push to Jarvis Awareness Feed ────────────────
        jarvis_feed_pushed = _push_jarvis_feed(state, tenant_id)

        # ── Step 5: Update Metrics Counters ──────────────────────
        metrics_updated = _update_metrics(state, tenant_id)

        # ── Step 6: Check Agent Lightning 50-Mistake Rule ───────
        fifty_mistake_check = _check_fifty_mistake_rule(state, tenant_id)

        # ── Step 7: Record node execution log entry ──────────────
        node_log_entry: Dict[str, Any] = {
            "node_name": "state_update",
            "timestamp": now,
            "status": "completed",
            "tenant_id": tenant_id,
            "audit_log_written": audit_log_written,
            "gsd_state_persisted": gsd_state_persisted,
            "ticket_created": ticket_result.get("ticket_created", False),
            "jarvis_feed_pushed": jarvis_feed_pushed,
            "metrics_updated": metrics_updated,
        }

        # ── Determine delivery status ────────────────────────────
        current_delivery_status = state.get("delivery_status", "pending")
        if current_delivery_status == "pending":
            delivery_status = "processing"
        else:
            delivery_status = current_delivery_status

        # ── Build state update ───────────────────────────────────
        result: Dict[str, Any] = {
            "ticket_created": ticket_result.get("ticket_created", False),
            "ticket_updated": ticket_result.get("ticket_updated", False),
            "ticket_status": ticket_result.get("ticket_status", "open"),
            "gsd_state_persisted": gsd_state_persisted,
            "audit_log_written": audit_log_written,
            "metrics_updated": metrics_updated,
            "jarvis_feed_pushed": jarvis_feed_pushed,
            "fifty_mistake_check": fifty_mistake_check,
            "node_execution_log": [node_log_entry],
            "delivery_timestamp": now,
            "delivery_status": delivery_status,
        }

        # Include ticket_id if a new one was created
        new_ticket_id = ticket_result.get("ticket_id", "")
        if new_ticket_id:
            result["ticket_id"] = new_ticket_id

        # ── Log summary ──────────────────────────────────────────
        logger.info(
            "state_update_node_completed",
            tenant_id=tenant_id,
            audit_log_written=audit_log_written,
            gsd_state_persisted=gsd_state_persisted,
            ticket_created=ticket_result.get("ticket_created", False),
            ticket_updated=ticket_result.get("ticket_updated", False),
            jarvis_feed_pushed=jarvis_feed_pushed,
            metrics_updated=metrics_updated,
            training_needed=fifty_mistake_check.get("training_needed", False),
        )

        return result

    except Exception as exc:
        logger.error(
            "state_update_node_fatal_error",
            tenant_id=tenant_id,
            error=str(exc),
        )

        # BC-008: On fatal error, log but don't crash
        # Return safe defaults with error recorded
        error_log_entry: Dict[str, Any] = {
            "node_name": "state_update",
            "timestamp": now,
            "status": "error",
            "tenant_id": tenant_id,
            "error": str(exc),
        }

        return {
            **_DEFAULT_STATE_UPDATE,
            "node_execution_log": [error_log_entry],
            "delivery_timestamp": now,
            "delivery_status": state.get("delivery_status", "pending"),
            "errors": [f"State update node failed: {exc}"],
        }
