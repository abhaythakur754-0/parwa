"""
PARWA Jarvis SLA Protection Agent Node

Prevents SLA breaches by identifying at-risk tickets and taking
protective action before deadlines are missed.
"""

import time
from datetime import datetime, timezone
from typing import Any, Dict

from app.logger import get_logger
from app.services.jarvis_agents.zai_client import get_zai_client

logger = get_logger("jarvis_sla_protection_agent")


def sla_protection_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """SLA Protection agent: prevents SLA breaches.

    Uses ZAI SDK to analyze at-risk tickets and decide the best
    protection strategy.

    Args:
        state: Current JarvisCommandState dict.

    Returns:
        Dict with updated AGENT group fields.
    """
    start_time = time.monotonic()

    try:
        company_id = state.get("company_id", "")
        alert_details = state.get("alert_details", {})
        awareness = state.get("awareness_snapshot", {})

        context = {
            "alert_type": state.get("alert_type", ""),
            "alert_severity": state.get("alert_severity", "info"),
            "alert_details": alert_details,
            "system_health": awareness.get("system_health", "unknown"),
            "ticket_volume_today": awareness.get("ticket_volume_today", 0),
            "active_agents": awareness.get("active_agents", 0),
            "quality_score": awareness.get("quality_score"),
            "company_id": company_id,
        }

        zai = get_zai_client()
        user_message = (
            f"SLA breach risk detected:\n"
            f"  Alert: {state.get('alert_type', 'sla_breach_risk')}\n"
            f"  Severity: {state.get('alert_severity', 'info')}\n"
            f"  Message: {state.get('alert_message', '')}\n"
            f"  Active tickets: {awareness.get('ticket_volume_today', 0)}\n"
            f"  Active agents: {awareness.get('active_agents', 0)}\n\n"
            f"What SLA protection strategy should we use?"
        )

        decision = zai.chat("sla_protection_agent", user_message, context)

        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)

        result = {
            "agent_type": "sla_protection",
            "agent_action": decision.get("action", "protect_sla"),
            "agent_decision": decision,
            "agent_reasoning": decision.get("recommendation", "SLA protection decision"),
            "agent_source": decision.get("_source", "unknown"),
            "node_outputs": {"sla_protection_agent": decision},
            "audit_trail": [{
                "step": "sla_protection_agent",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": decision.get("action", "protect_sla"),
                "strategy": decision.get("strategy", "unknown"),
                "at_risk_count": decision.get("at_risk_count", 0),
                "source": decision.get("_source", "unknown"),
                "elapsed_ms": elapsed_ms,
            }],
        }

        logger.info(
            "sla_protection_agent: company=%s, action=%s, strategy=%s, ms=%.1f",
            company_id, decision.get("action"), decision.get("strategy"), elapsed_ms,
        )

        return result

    except Exception as e:
        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
        logger.exception("sla_protection_agent_error: ms=%.1f", elapsed_ms)
        return {
            "agent_type": "sla_protection",
            "agent_action": "protect_sla",
            "agent_decision": {"action": "protect_sla", "strategy": "prioritize", "at_risk_count": 0},
            "agent_reasoning": f"Error fallback: {str(e)[:200]}",
            "agent_source": "error_fallback",
            "errors": [f"sla_protection_agent: {str(e)[:200]}"],
            "node_outputs": {"sla_protection_agent": {"error": str(e)[:200]}},
        }
