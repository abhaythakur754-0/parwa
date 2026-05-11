"""
PARWA Jarvis Escalation Agent Node

Handles situations where tickets or issues need human intervention.
When Jarvis detects a critical alert (ticket spike, emergency state,
quality collapse), this agent decides HOW to escalate.

Like a senior support rep saying: "This is beyond AI — let me get a human."
"""

import json
import time
from datetime import datetime, timezone
from typing import Any, Dict

from app.logger import get_logger
from app.services.jarvis_agents.zai_client import get_zai_client

logger = get_logger("jarvis_escalation_agent")


def escalation_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Escalation agent: decides how to escalate critical issues.

    Uses ZAI SDK to reason about the best escalation strategy.
    Falls back to rule-based decisions if LLM fails.

    Args:
        state: Current JarvisCommandState dict.

    Returns:
        Dict with updated AGENT group fields.
    """
    start_time = time.monotonic()

    try:
        company_id = state.get("company_id", "")
        session_id = state.get("session_id", "")
        alert_type = state.get("alert_type", "")
        alert_severity = state.get("alert_severity", "info")
        alert_message = state.get("alert_message", "")
        alert_details = state.get("alert_details", {})
        router_parameters = state.get("router_parameters", {})
        awareness = state.get("awareness_snapshot", {})

        # Build context for LLM
        context = {
            "alert_type": alert_type,
            "alert_severity": alert_severity,
            "alert_message": alert_message,
            "alert_details": alert_details,
            "router_parameters": router_parameters,
            "system_health": awareness.get("system_health", "unknown"),
            "ticket_volume_today": awareness.get("ticket_volume_today", 0),
            "ticket_volume_spike": awareness.get("ticket_volume_spike", False),
            "quality_score": awareness.get("quality_score"),
            "active_agents": awareness.get("active_agents", 0),
            "agent_pool_utilization": awareness.get("agent_pool_utilization"),
            "company_id": company_id,
        }

        # Ask the LLM: how should we escalate?
        zai = get_zai_client()
        user_message = (
            f"Critical situation detected:\n"
            f"  Alert: {alert_type} (severity: {alert_severity})\n"
            f"  Message: {alert_message}\n"
            f"  System health: {awareness.get('system_health', 'unknown')}\n"
            f"  Ticket volume: {awareness.get('ticket_volume_today', 0)} today "
            f"(spike: {awareness.get('ticket_volume_spike', False)})\n"
            f"  Active agents: {awareness.get('active_agents', 0)}\n\n"
            f"How should we escalate this? Decide the escalation scope, tier, and strategy."
        )

        decision = zai.chat("escalation_agent", user_message, context)

        # If user NL command had a specific action, merge it in
        if router_parameters.get("original_action") == "pause_ai":
            decision["action"] = "escalate"
            decision["scope"] = "all_channels"
            decision["escalation_tier"] = "manager"
            decision["reason"] = "User requested AI pause — full escalation"

        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)

        result = {
            "agent_type": "escalation",
            "agent_action": decision.get("action", "escalate"),
            "agent_decision": decision,
            "agent_reasoning": decision.get("reason", "Escalation agent decision"),
            "agent_source": decision.get("_source", "unknown"),
            "node_outputs": {"escalation_agent": decision},
            "audit_trail": [{
                "step": "escalation_agent",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": decision.get("action", "escalate"),
                "scope": decision.get("scope", "unknown"),
                "tier": decision.get("escalation_tier", "unknown"),
                "source": decision.get("_source", "unknown"),
                "elapsed_ms": elapsed_ms,
            }],
        }

        logger.info(
            "escalation_agent: company=%s, action=%s, scope=%s, tier=%s, ms=%.1f",
            company_id, decision.get("action"), decision.get("scope"),
            decision.get("escalation_tier"), elapsed_ms,
        )

        return result

    except Exception as e:
        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
        logger.exception("escalation_agent_error: ms=%.1f", elapsed_ms)
        return {
            "agent_type": "escalation",
            "agent_action": "escalate",
            "agent_decision": {"action": "escalate", "scope": "all_urgent", "escalation_tier": "tier1"},
            "agent_reasoning": f"Error fallback: {str(e)[:200]}",
            "agent_source": "error_fallback",
            "errors": [f"escalation_agent: {str(e)[:200]}"],
            "node_outputs": {"escalation_agent": {"error": str(e)[:200]}},
        }
