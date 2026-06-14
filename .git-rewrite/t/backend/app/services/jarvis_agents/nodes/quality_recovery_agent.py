"""
PARWA Jarvis Quality Recovery Agent Node

Handles quality score drops and model drift. When Jarvis notices
that response quality is declining, this agent takes corrective action.
"""

import time
from datetime import datetime, timezone
from typing import Any, Dict

from app.logger import get_logger
from app.services.jarvis_agents.zai_client import get_zai_client

logger = get_logger("jarvis_quality_recovery_agent")


def quality_recovery_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Quality Recovery agent: recovers from quality drops.

    Uses ZAI SDK to analyze quality metrics and decide the best
    recovery strategy.

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
            "quality_score": awareness.get("quality_score"),
            "drift_score": awareness.get("drift_score"),
            "drift_status": awareness.get("drift_status", "none"),
            "system_health": awareness.get("system_health", "unknown"),
            "company_id": company_id,
        }

        zai = get_zai_client()
        user_message = (
            f"Quality issue detected:\n"
            f"  Alert: {state.get('alert_type', 'quality_drop')}\n"
            f"  Current quality score: {awareness.get('quality_score', 'unknown')}\n"
            f"  Drift status: {awareness.get('drift_status', 'none')}\n"
            f"  Drift score: {awareness.get('drift_score', 'unknown')}\n"
            f"  System health: {awareness.get('system_health', 'unknown')}\n\n"
            f"What quality recovery strategy should we use?"
        )

        decision = zai.chat("quality_recovery_agent", user_message, context)

        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)

        result = {
            "agent_type": "quality_recovery",
            "agent_action": decision.get("action", "recover_quality"),
            "agent_decision": decision,
            "agent_reasoning": decision.get("steps", ["Quality recovery decision"]),
            "agent_source": decision.get("_source", "unknown"),
            "node_outputs": {"quality_recovery_agent": decision},
            "audit_trail": [{
                "step": "quality_recovery_agent",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": decision.get("action", "recover_quality"),
                "strategy": decision.get("strategy", "unknown"),
                "current_score": decision.get("current_score"),
                "target_score": decision.get("target_score"),
                "source": decision.get("_source", "unknown"),
                "elapsed_ms": elapsed_ms,
            }],
        }

        logger.info(
            "quality_recovery_agent: company=%s, action=%s, strategy=%s, ms=%.1f",
            company_id, decision.get("action"), decision.get("strategy"), elapsed_ms,
        )

        return result

    except Exception as e:
        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
        logger.exception("quality_recovery_agent_error: ms=%.1f", elapsed_ms)
        return {
            "agent_type": "quality_recovery",
            "agent_action": "recover_quality",
            "agent_decision": {"action": "recover_quality", "strategy": "switch_technique"},
            "agent_reasoning": f"Error fallback: {str(e)[:200]}",
            "agent_source": "error_fallback",
            "errors": [f"quality_recovery_agent: {str(e)[:200]}"],
            "node_outputs": {"quality_recovery_agent": {"error": str(e)[:200]}},
        }
