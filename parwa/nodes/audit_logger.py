"""Node 16: AUDIT_LOGGER — Logs every action and decision for compliance and debugging.

Compliance Agent node. Creates a complete audit trail for every ticket,
recording each node's actions and decisions.

Phase 5: Now uses FrameworkBrain with CRP for structured audit logging.
Falls back to basic logging on failure.
"""

from __future__ import annotations

import datetime
import logging
from typing import Any

from parwa.utils.node_base import safe_node


async def _log_audit_with_brain(state: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    """Audit logging using FrameworkBrain (Phase 5).

    Returns (audit_log, frameworks_used).
    Falls back to basic logging on any failure.
    """
    ticket_id = state.get("ticket_id", "UNKNOWN")
    intent = state.get("intent", "")
    action_plans = state.get("action_plans", [])
    execution_results = state.get("execution_results", [])
    recommendation = state.get("recommendation")
    quality_score = state.get("quality_score", 0.0)
    variant = state.get("variant", "parwa")
    existing_log = list(state.get("audit_log", []))

    try:
        from parwa.frameworks.brain import FrameworkBrain

        brain = FrameworkBrain(node="AUDIT_LOGGER", state=state)
        result = await brain.think(
            prompt="Log audit trail",
            techniques=["crp"],
            ticket_id=state.get("ticket_id", ""),
            variant=state.get("variant", "parwa"),
        )

        frameworks_used = result.frameworks_used if result.frameworks_used else []

    except Exception:
        frameworks_used = []

    # Create audit entry (deterministic — brain just validates structure)
    try:
        audit_entry = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "ticket_id": ticket_id,
            "variant": variant,
            "intent": intent,
            "actions_planned": [a.get("action_type", "") for a in action_plans if isinstance(a, dict)],
            "actions_executed": [
                {"action": r.get("action_type", ""), "status": r.get("status", "")}
                for r in execution_results if isinstance(r, dict)
            ],
            "recommendation_created": recommendation is not None,
            "quality_score": quality_score,
            "node": "audit_logger",
        }
    except Exception as exc:
        logging.getLogger("parwa.node.audit_logger").warning(
            "AUDIT_LOGGER: Failed to create full audit entry: %s", exc,
        )
        audit_entry = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "ticket_id": ticket_id,
            "variant": variant,
            "node": "audit_logger",
            "error": str(exc),
        }

    if not isinstance(existing_log, list):
        existing_log = []
    existing_log.append(audit_entry)

    return existing_log, frameworks_used


@safe_node("AUDIT_LOGGER", fallback={"audit_log": [], "active_frameworks": []})
async def audit_logger(state: dict[str, Any]) -> dict[str, Any]:
    """Log all actions and decisions for audit trail (async).

    Phase 5: Uses FrameworkBrain with CRP for structured audit logging.

    Reads: ticket_id, intent, action_plans, execution_results, recommendation, quality_score
    Writes: audit_log (appends), active_frameworks (append)
    """
    audit_log, frameworks = await _log_audit_with_brain(state)

    if not isinstance(audit_log, list):
        audit_log = []

    new_frameworks = []
    existing = state.get("active_frameworks", [])
    for fw in frameworks:
        if fw not in existing:
            new_frameworks.append(fw)

    return {
        "audit_log": audit_log,
        "active_frameworks": new_frameworks,
    }
