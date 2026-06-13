"""
PARWA Jarvis Notification Agent Node

Handles proactive notifications to users. When Jarvis decides the user
needs to know about something (but no automated action is needed),
this agent crafts and delivers the right notification.
"""

import time
from datetime import datetime, timezone
from typing import Any, Dict

from app.logger import get_logger
from app.services.jarvis_agents.zai_client import get_zai_client

logger = get_logger("jarvis_notification_agent")


def notification_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Notification agent: crafts and sends proactive notifications.

    Uses ZAI SDK to write natural-sounding notifications that read
    like they came from a human colleague, not a robot.

    Args:
        state: Current JarvisCommandState dict.

    Returns:
        Dict with updated AGENT group fields.
    """
    start_time = time.monotonic()

    try:
        company_id = state.get("company_id", "")
        awareness = state.get("awareness_snapshot", {})
        router_params = state.get("router_parameters", {})

        context = {
            "alert_type": state.get("alert_type", ""),
            "alert_severity": state.get("alert_severity", "info"),
            "alert_message": state.get("alert_message", ""),
            "alert_details": state.get("alert_details", {}),
            "system_health": awareness.get("system_health", "unknown"),
            "quality_score": awareness.get("quality_score"),
            "ticket_volume_today": awareness.get("ticket_volume_today", 0),
            "router_parameters": router_params,
            "company_id": company_id,
        }

        # If user NL command, build notification from the command
        raw_input = state.get("raw_input", "")
        if raw_input:
            context["user_command"] = raw_input

        zai = get_zai_client()
        user_message = (
            f"Notification needed:\n"
            f"  Alert: {state.get('alert_type', 'system_event')}\n"
            f"  Severity: {state.get('alert_severity', 'info')}\n"
            f"  System health: {awareness.get('system_health', 'unknown')}\n"
        )
        if raw_input:
            user_message += f"  User command: '{raw_input}'\n"
        user_message += (
            f"\nCraft a notification for the user. It should read like a "
            f"human colleague telling them about an issue — not a system alert."
        )

        decision = zai.chat("notification_agent", user_message, context)

        # If user NL command, use it to customize the notification
        if router_params.get("parsed_command"):
            parsed = router_params["parsed_command"]
            if parsed.get("action") not in ("unknown", None):
                decision["title"] = f"Command: {parsed['action']}"
                decision["action_required"] = False

        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)

        result = {
            "agent_type": "notification",
            "agent_action": decision.get("action", "notify"),
            "agent_decision": decision,
            "agent_reasoning": decision.get("message", "Notification agent decision"),
            "agent_source": decision.get("_source", "unknown"),
            "node_outputs": {"notification_agent": decision},
            "audit_trail": [{
                "step": "notification_agent",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": decision.get("action", "notify"),
                "channel": decision.get("channel", "chat"),
                "severity": decision.get("severity", "info"),
                "title": decision.get("title", "")[:100],
                "source": decision.get("_source", "unknown"),
                "elapsed_ms": elapsed_ms,
            }],
        }

        logger.info(
            "notification_agent: company=%s, channel=%s, severity=%s, ms=%.1f",
            company_id, decision.get("channel"), decision.get("severity"), elapsed_ms,
        )

        return result

    except Exception as e:
        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
        logger.exception("notification_agent_error: ms=%.1f", elapsed_ms)
        return {
            "agent_type": "notification",
            "agent_action": "notify",
            "agent_decision": {
                "action": "notify", "channel": "chat",
                "severity": "info", "title": "System Notification",
                "message": "Jarvis detected a system event.",
            },
            "agent_reasoning": f"Error fallback: {str(e)[:200]}",
            "agent_source": "error_fallback",
            "errors": [f"notification_agent: {str(e)[:200]}"],
            "node_outputs": {"notification_agent": {"error": str(e)[:200]}},
        }
