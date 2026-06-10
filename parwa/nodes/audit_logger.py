"""Node 16: AUDIT_LOGGER — Logs every action and decision for compliance and debugging.

Compliance Agent node. Creates a complete audit trail for every ticket,
recording each node's actions and decisions. This node does NOT use LLM.
"""

from __future__ import annotations

import datetime
from typing import Any

from parwa.utils.node_base import safe_node


@safe_node("AUDIT_LOGGER", fallback={"audit_log": []})
async def audit_logger(state: dict[str, Any]) -> dict[str, Any]:
    """Log all actions and decisions for audit trail (async).

    Reads: ticket_id, intent, action_plans, execution_results, recommendation, quality_score
    Writes: audit_log (appends)
    """
    ticket_id = state.get("ticket_id", "UNKNOWN")
    intent = state.get("intent", "")
    action_plans = state.get("action_plans", [])
    execution_results = state.get("execution_results", [])
    recommendation = state.get("recommendation")
    quality_score = state.get("quality_score", 0.0)
    variant = state.get("variant", "parwa")

    existing_log = list(state.get("audit_log", []))

    # Create audit entry
    audit_entry = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "ticket_id": ticket_id,
        "variant": variant,
        "intent": intent,
        "actions_planned": [a.get("action_type", "") for a in action_plans],
        "actions_executed": [
            {"action": r.get("action_type", ""), "status": r.get("status", "")}
            for r in execution_results
        ],
        "recommendation_created": recommendation is not None,
        "quality_score": quality_score,
        "node": "audit_logger",
    }

    existing_log.append(audit_entry)

    return {"audit_log": existing_log}
