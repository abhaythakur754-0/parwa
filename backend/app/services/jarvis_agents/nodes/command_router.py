"""
PARWA Jarvis Command Router Agent Node

The FIRST node in the command graph. When an alert comes in from the
Awareness Engine, or a user types a natural language command, this node
decides which specialist agent should handle it.

Uses ZAI SDK (LLM) for intelligent routing. Falls back to rule-based
routing if LLM fails (BC-008).
"""

import json
import time
from datetime import datetime, timezone
from typing import Any, Dict

from app.logger import get_logger
from app.services.jarvis_agents.zai_client import get_zai_client

logger = get_logger("jarvis_command_router")


def command_router_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Route an alert or user command to the appropriate agent.

    Decision Process:
      1. If trigger_type='user_nl': Try regex parser first (fast), then LLM
      2. If trigger_type='alert': Use ZAI SDK LLM to analyze and route
      3. If LLM fails: Fall back to rule-based routing
      4. Write routing decision to state

    Args:
        state: Current JarvisCommandState dict.

    Returns:
        Dict with updated ROUTER group fields.
    """
    start_time = time.monotonic()

    try:
        trigger_type = state.get("trigger_type", "unknown")
        company_id = state.get("company_id", "")
        session_id = state.get("session_id", "")

        context = _build_router_context(state)

        if trigger_type == "user_nl":
            router_result = _route_user_command(state, context)
        elif trigger_type == "alert":
            router_result = _route_alert(state, context)
        else:
            router_result = {
                "agent": "notification_agent",
                "reasoning": f"Unknown trigger type: {trigger_type}",
                "urgency": "low",
                "parameters": {},
            }

        valid_agents = {
            "escalation_agent", "sla_protection_agent",
            "quality_recovery_agent", "reassignment_agent",
            "notification_agent", "pipeline_query_agent",
            "no_action",
        }
        selected_agent = router_result.get("agent", "notification_agent")
        if selected_agent not in valid_agents:
            if selected_agent + "_agent" in valid_agents:
                selected_agent = selected_agent + "_agent"
            else:
                selected_agent = "notification_agent"

        router_decision = selected_agent.replace("_agent", "")
        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)

        result = {
            "router_decision": router_decision,
            "router_reasoning": router_result.get("reasoning", ""),
            "router_urgency": router_result.get("urgency", "medium"),
            "router_parameters": router_result.get("parameters", {}),
            "router_source": router_result.get("_source", "unknown"),
            "node_outputs": {"command_router": router_result},
            "audit_trail": [{
                "step": "command_router",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "trigger": trigger_type,
                "selected_agent": selected_agent,
                "reasoning": router_result.get("reasoning", "")[:200],
                "urgency": router_result.get("urgency", "medium"),
                "source": router_result.get("_source", "unknown"),
                "elapsed_ms": elapsed_ms,
            }],
        }

        logger.info(
            "command_router: company=%s, session=%s, trigger=%s, "
            "agent=%s, urgency=%s, source=%s, ms=%.1f",
            company_id, session_id, trigger_type,
            selected_agent, router_result.get("urgency", "medium"),
            router_result.get("_source", "unknown"), elapsed_ms,
        )

        return result

    except Exception as e:
        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
        logger.exception("command_router_error: ms=%.1f", elapsed_ms)
        return {
            "router_decision": "notification",
            "router_reasoning": f"Router error: {str(e)[:200]}",
            "router_urgency": "low",
            "router_parameters": {},
            "router_source": "error_fallback",
            "errors": [f"command_router: {str(e)[:200]}"],
            "node_outputs": {"command_router": {"error": str(e)[:200]}},
        }


def _build_router_context(state: Dict[str, Any]) -> Dict[str, Any]:
    """Build the context dict for the LLM."""
    context = {
        "company_id": state.get("company_id", ""),
        "variant_tier": state.get("variant_tier", "mini_parwa"),
    }
    if state.get("alert_type"):
        context["alert_type"] = state["alert_type"]
        context["severity"] = state.get("alert_severity", "info")
        context["message"] = state.get("alert_message", "")
        context["alert_details"] = state.get("alert_details", {})
    snapshot = state.get("awareness_snapshot", {})
    if snapshot:
        context["system_health"] = snapshot.get("system_health", "unknown")
        context["quality_score"] = snapshot.get("quality_score")
        context["drift_score"] = snapshot.get("drift_score")
        context["ticket_volume_today"] = snapshot.get("ticket_volume_today", 0)
        context["ticket_volume_spike"] = snapshot.get("ticket_volume_spike", False)
        context["agent_pool_utilization"] = snapshot.get("agent_pool_utilization")
    if state.get("raw_input"):
        context["raw_input"] = state["raw_input"]
    return context


def _route_alert(state: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Route an awareness alert using ZAI SDK."""
    zai = get_zai_client()
    alert_type = state.get("alert_type", "unknown")
    severity = state.get("alert_severity", "info")
    alert_message = state.get("alert_message", "")
    user_message = (
        f"Awareness alert received:\n"
        f"  Type: {alert_type}\n"
        f"  Severity: {severity}\n"
        f"  Message: {alert_message}\n\n"
        f"Which agent should handle this? Consider the current system state."
    )
    return zai.chat("command_router", user_message, context)


def _route_user_command(state: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Route a user NL command. Try regex first, then LLM."""
    raw_input = state.get("raw_input", "")
    company_id = state.get("company_id", "")

    # Step 0: Try product command parser first (shadow mode, billing, variants, etc.)
    try:
        from app.services.jarvis_product_commands import parse_product_command
        product_parsed = parse_product_command(
            company_id=company_id, raw_input=raw_input,
            session_id=state.get("session_id", ""),
        )
        if product_parsed.get("confidence", 0) >= 0.70 and product_parsed.get("is_product_command"):
            # Product commands go to a dedicated "product_command" agent type
            # which the executor will handle via execute_product_command()
            return {
                "_source": "product_command_parser",
                "agent": "notification_agent",  # Default agent for routing
                "reasoning": f"Product command matched: '{product_parsed.get('action')}' with confidence {product_parsed.get('confidence', 0):.2f}",
                "urgency": "medium",
                "parameters": {
                    "original_action": product_parsed.get("action", ""),
                    "parsed_command": product_parsed,
                    "is_product_command": True,
                },
            }
    except Exception:
        logger.debug("product_command_parser_failed, trying base parser", exc_info=True)

    # Step 1: Regex parser (fast, no LLM)
    try:
        from app.services.jarvis_command_service import parse_natural_language_command
        parsed = parse_natural_language_command(
            company_id=company_id, raw_input=raw_input,
            session_id=state.get("session_id", ""),
        )
        if parsed.get("confidence", 0) >= 0.65 and parsed.get("action") != "unknown":
            agent_mapping = {
                "pause_ai": "escalation_agent",
                "resume_ai": "notification_agent",
                "pause_refunds": "escalation_agent",
                "resume_refunds": "notification_agent",
                "check_system_health": "pipeline_query_agent",
                "show_errors": "pipeline_query_agent",
                "escalate_urgent": "escalation_agent",
                "add_agents": "reassignment_agent",
                "disable_last_rule": "notification_agent",
                "export_report": "notification_agent",
                "call_customer": "notification_agent",
                "show_ticket_details": "pipeline_query_agent",
                "check_quality": "pipeline_query_agent",
                "check_volume": "pipeline_query_agent",
                "check_agents": "pipeline_query_agent",
                "check_drift": "pipeline_query_agent",
            }
            action = parsed.get("action", "")
            mapped_agent = agent_mapping.get(action, "notification_agent")
            return {
                "_source": "regex_parser",
                "agent": mapped_agent,
                "reasoning": f"Regex matched action '{action}' with confidence {parsed.get('confidence', 0):.2f}",
                "urgency": "high" if mapped_agent == "escalation_agent" else "medium",
                "parameters": {"original_action": action, "parsed_command": parsed},
            }
    except Exception:
        logger.debug("regex_parser_failed, using_llm", exc_info=True)

    # Step 2: LLM routing
    zai = get_zai_client()
    user_message = f"User command: '{raw_input}'\n\nWhich agent should handle this?"
    return zai.chat("command_router", user_message, context)
