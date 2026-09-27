"""
PARWA Jarvis Reassignment Agent Node

Handles ticket load balancing and agent reassignment. When one agent
or variant is overloaded, this agent moves tickets to underutilized ones.
"""

import time
from datetime import datetime, timezone
from typing import Any, Dict

from app.logger import get_logger
from app.services.jarvis_agents.zai_client import get_zai_client

logger = get_logger("jarvis_reassignment_agent")


def reassignment_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Reassignment agent: balances ticket load across agents.

    Uses ZAI SDK to analyze load distribution and decide which
    tickets to move where.

    Args:
        state: Current JarvisCommandState dict.

    Returns:
        Dict with updated AGENT group fields.
    """
    start_time = time.monotonic()

    try:
        company_id = state.get("company_id", "")
        awareness = state.get("awareness_snapshot", {})

        context = {
            "alert_type": state.get("alert_type", ""),
            "alert_severity": state.get("alert_severity", "info"),
            "alert_details": state.get("alert_details", {}),
            "active_agents": awareness.get("active_agents", 0),
            "agent_pool_capacity": awareness.get("agent_pool_capacity", 0),
            "agent_pool_utilization": awareness.get("agent_pool_utilization"),
            "ticket_volume_today": awareness.get("ticket_volume_today", 0),
            "variant_tier": state.get("variant_tier", "mini_parwa"),
            "company_id": company_id,
        }

        zai = get_zai_client()
        user_message = (
            f"Agent pool overload detected:\n"
            f"  Active agents: {awareness.get('active_agents', 0)} / "
            f"{awareness.get('agent_pool_capacity', 0)}\n"
            f"  Utilization: {awareness.get('agent_pool_utilization', 'unknown')}%\n"
            f"  Ticket volume today: {awareness.get('ticket_volume_today', 0)}\n"
            f"  Variant tier: {state.get('variant_tier', 'mini_parwa')}\n\n"
            f"Which tickets should be reassigned and to where?"
        )

        decision = zai.chat("reassignment_agent", user_message, context)

        # If user asked to add agents, merge that in
        router_params = state.get("router_parameters", {})
        if router_params.get("original_action") == "add_agents":
            decision["action"] = "reassign"
            decision["upgrade_suggested"] = True
            decision["reason"] = "User requested agent addition — load expansion needed"

        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)

        result = {
            "agent_type": "reassignment",
            "agent_action": decision.get("action", "reassign"),
            "agent_decision": decision,
            "agent_reasoning": decision.get("reason", "Reassignment agent decision"),
            "agent_source": decision.get("_source", "unknown"),
            "node_outputs": {"reassignment_agent": decision},
            "audit_trail": [{
                "step": "reassignment_agent",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": decision.get("action", "reassign"),
                "ticket_count": decision.get("ticket_count", 0),
                "upgrade_suggested": decision.get("upgrade_suggested", False),
                "source": decision.get("_source", "unknown"),
                "elapsed_ms": elapsed_ms,
            }],
        }

        logger.info(
            "reassignment_agent: company=%s, action=%s, tickets=%s, upgrade=%s, ms=%.1f",
            company_id, decision.get("action"), decision.get("ticket_count"),
            decision.get("upgrade_suggested"), elapsed_ms,
        )

        return result

    except Exception as e:
        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
        logger.exception("reassignment_agent_error: ms=%.1f", elapsed_ms)
        return {
            "agent_type": "reassignment",
            "agent_action": "reassign",
            "agent_decision": {"action": "reassign", "ticket_count": 0},
            "agent_reasoning": f"Error fallback: {str(e)[:200]}",
            "agent_source": "error_fallback",
            "errors": [f"reassignment_agent: {str(e)[:200]}"],
            "node_outputs": {"reassignment_agent": {"error": str(e)[:200]}},
        }
