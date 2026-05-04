"""
PARWA LangGraph Conditional Edge Functions

These functions are used as conditional edges in the LangGraph StateGraph.
Each function reads from ParwaGraphState and returns the name of the next
node to execute.

Edge Functions:
  1. route_after_router     — Intent-based routing to domain agents
  2. route_after_maker      — Red flag → Control System or DSPy
  3. route_after_control    — Approval decision → proceed or wait
  4. route_after_guardrails — Blocked → end or continue to delivery
  5. route_after_delivery   — Channel-based routing to delivery agents
  6. should_use_dspy        — Whether DSPy optimization should run
  7. should_compress_context — Whether context compression is needed

Design Rules:
  - Every edge function takes state: ParwaGraphState as input
  - Every edge function returns a string (next node name)
  - variant_tier drives routing decisions
  - Graceful fallback for unknown states (BC-008)
"""

from __future__ import annotations

from typing import Dict

from app.core.langgraph.config import (
    get_available_agents,
    get_available_channels,
    is_voice_enabled,
    is_video_enabled,
    map_intent_to_agent,
    needs_human_approval,
    classify_action_type,
    VariantTier,
)
from app.logger import get_logger

logger = get_logger("langgraph_edges")


# ══════════════════════════════════════════════════════════════════
# EDGE 1: Route After Router Agent
# ──────────────────────────────────────────────────────────────────
# Routes based on classified intent + variant_tier agent availability
# ══════════════════════════════════════════════════════════════════

def route_after_router(state: Dict) -> str:
    """
    Route to the appropriate domain agent based on classified intent.

    Respects variant_tier agent availability:
      - mini: faq, technical, billing
      - pro:  faq, refund, technical, billing, complaint, escalation
      - high: faq, refund, technical, billing, complaint, escalation

    If the target agent is not available for this tier, falls back
    to the tier's configured fallback agent.

    Args:
        state: Current ParwaGraphState dict

    Returns:
        Node name string for the target domain agent
    """
    intent = state.get("intent", "general")
    variant_tier = state.get("variant_tier", "mini")
    target_agent = map_intent_to_agent(intent, variant_tier)

    # Validate the agent is available (double-check)
    available = get_available_agents(variant_tier)
    if target_agent not in available:
        # Fall back to the first available agent
        target_agent = available[0] if available else "faq_agent"

    logger.info(
        "router_edge_routing",
        intent=intent,
        variant_tier=variant_tier,
        target_agent=target_agent,
    )

    return f"{target_agent}_agent"


# ══════════════════════════════════════════════════════════════════
# EDGE 2: Route After MAKER Validator
# ──────────────────────────────────────────────────────────────────
# If MAKER flagged a red flag → go to Control System
# If MAKER passed → skip to DSPy Optimizer (or Guardrails if no DSPy)
# ══════════════════════════════════════════════════════════════════

def route_after_maker(state: Dict) -> str:
    """
    Route after MAKER validation.

    If red_flag is True → Control System (for human approval)
    If red_flag is False → DSPy Optimizer (skip Control System)

    Args:
        state: Current ParwaGraphState dict

    Returns:
        Node name: "control_system" or "dspy_optimizer"
    """
    red_flag = state.get("red_flag", False)
    action_type = state.get("action_type", "informational")
    variant_tier = state.get("variant_tier", "mini")

    # Check if this action type needs human approval for this tier
    approval_needed = needs_human_approval(action_type, variant_tier)

    if red_flag or approval_needed:
        logger.info(
            "maker_edge_to_control",
            red_flag=red_flag,
            approval_needed=approval_needed,
            action_type=action_type,
            variant_tier=variant_tier,
        )
        return "control_system"

    # No red flag and no approval needed — skip Control System
    return "dspy_optimizer"


# ══════════════════════════════════════════════════════════════════
# EDGE 3: Route After Control System
# ──────────────────────────────────────────────────────────────────
# Based on approval decision:
#   approved/auto_approved → DSPy Optimizer
#   rejected → END (with rejection message)
#   needs_human_approval → wait (interrupt_before handles this)
# ══════════════════════════════════════════════════════════════════

def route_after_control(state: Dict) -> str:
    """
    Route after Control System approval decision.

    approved / auto_approved → DSPy Optimizer
    rejected → state_update (with rejection logged)
    needs_human_approval → END (LangGraph interrupt handles this)

    Args:
        state: Current ParwaGraphState dict

    Returns:
        Node name string
    """
    decision = state.get("approval_decision", "approved")

    if decision in ("approved", "auto_approved"):
        return "dspy_optimizer"
    elif decision == "rejected":
        # Log rejection and go to state update to record it
        return "state_update"
    elif decision == "needs_human_approval":
        # This should be handled by LangGraph's interrupt_before
        # If we reach here, it means the interrupt wasn't configured
        # Fall back to state_update to avoid getting stuck
        logger.warning(
            "control_edge_human_approval_without_interrupt",
            decision=decision,
        )
        return "state_update"

    # Unknown decision — proceed with caution
    logger.warning(
        "control_edge_unknown_decision",
        decision=decision,
    )
    return "dspy_optimizer"


# ══════════════════════════════════════════════════════════════════
# EDGE 4: Route After Guardrails
# ──────────────────────────────────────────────────────────────────
# If guardrails blocked → END (with blocked reason)
# If guardrails passed → Channel Delivery
# ══════════════════════════════════════════════════════════════════

def route_after_guardrails(state: Dict) -> str:
    """
    Route after guardrails check.

    If guardrails_passed is True → channel_delivery
    If guardrails_passed is False → state_update (with blocked reason)

    Args:
        state: Current ParwaGraphState dict

    Returns:
        Node name string
    """
    passed = state.get("guardrails_passed", True)

    if passed:
        return "channel_delivery"
    else:
        blocked_reason = state.get("guardrails_blocked_reason", "Unknown guardrail violation")
        logger.warning(
            "guardrails_edge_blocked",
            blocked_reason=blocked_reason,
        )
        return "state_update"


# ══════════════════════════════════════════════════════════════════
# EDGE 5: Route After Channel Delivery
# ──────────────────────────────────────────────────────────────────
# Route to the appropriate channel-specific delivery agent
# based on the output channel and variant_tier availability
# ══════════════════════════════════════════════════════════════════

def route_after_delivery(state: Dict) -> str:
    """
    Route to the channel-specific delivery agent.

    Respects variant_tier channel availability:
      - mini: email, sms, chat, api (no voice, no video)
      - pro:  email, sms, chat, api, voice (no video)
      - high: email, sms, chat, api, voice, video

    If the requested channel is not available for this tier,
    falls back to email.

    Args:
        state: Current ParwaGraphState dict

    Returns:
        Node name string for the channel delivery agent
    """
    channel = state.get("channel", "email")
    variant_tier = state.get("variant_tier", "mini")
    available_channels = get_available_channels(variant_tier)

    # Check if the channel is available for this tier
    if channel not in available_channels:
        # Fall back to email (always available)
        logger.info(
            "delivery_edge_channel_unavailable_fallback",
            requested_channel=channel,
            fallback_channel="email",
            variant_tier=variant_tier,
        )
        channel = "email"

    # Map channel to node name
    channel_node_map = {
        "email": "email_agent",
        "sms": "sms_agent",
        "chat": "chat_delivery",    # Chat goes through WebSocket, no separate agent
        "api": "api_delivery",      # API delivery is just state_update
        "voice": "voice_agent",
        "video": "video_agent",
    }

    node_name = channel_node_map.get(channel, "email_agent")

    # Special handling: chat and api don't need separate delivery nodes
    if node_name in ("chat_delivery", "api_delivery"):
        return "state_update"

    logger.info(
        "delivery_edge_routing",
        channel=channel,
        variant_tier=variant_tier,
        node_name=node_name,
    )

    return node_name


# ══════════════════════════════════════════════════════════════════
# EDGE 6: Should Use DSPy Optimizer
# ──────────────────────────────────────────────────────────────────
# Determines whether DSPy prompt optimization should run
# ══════════════════════════════════════════════════════════════════

def should_use_dspy(state: Dict) -> str:
    """
    Determine whether to run DSPy prompt optimization.

    DSPy optimization is:
      - Always skipped for mini tier (cost optimization)
      - Applied for pro tier on complex queries (complexity > 0.5)
      - Always applied for high tier

    Args:
        state: Current ParwaGraphState dict

    Returns:
        "dspy_optimizer" or "guardrails"
    """
    variant_tier = state.get("variant_tier", "mini")
    complexity = state.get("complexity_score", 0.0)

    if variant_tier == VariantTier.MINI.value:
        # Skip DSPy for mini — not worth the token cost
        return "guardrails"
    elif variant_tier == VariantTier.PRO.value:
        # Only use DSPy for complex queries on pro
        if complexity > 0.5:
            return "dspy_optimizer"
        return "guardrails"
    else:
        # Always use DSPy for high tier
        return "dspy_optimizer"


# ══════════════════════════════════════════════════════════════════
# EDGE 7: Should Compress Context
# ──────────────────────────────────────────────────────────────────
# Determines whether context compression should run before generation
# ══════════════════════════════════════════════════════════════════

def should_compress_context(state: Dict) -> str:
    """
    Determine whether context compression should run.

    Context compression runs when:
      - Context health score drops below 0.7
      - Token usage is approaching budget limits
      - High tier always gets compression check

    Args:
        state: Current ParwaGraphState dict

    Returns:
        "context_compression" or "domain_agent" (skip compression)
    """
    variant_tier = state.get("variant_tier", "mini")
    context_health = state.get("context_health", 1.0)

    # High tier always checks compression
    if variant_tier == VariantTier.HIGH.value:
        if context_health < 0.9:
            return "context_compression"
        return "domain_agent"

    # Pro tier compresses when health is moderate
    if variant_tier == VariantTier.PRO.value:
        if context_health < 0.7:
            return "context_compression"
        return "domain_agent"

    # Mini tier only compresses when health is critical
    if context_health < 0.5:
        return "context_compression"

    return "domain_agent"


# ══════════════════════════════════════════════════════════════════
# EDGE 8: Route After Emergency Check
# ──────────────────────────────────────────────────────────────────
# If AI is paused or emergency state → END
# Otherwise → proceed with normal flow
# ══════════════════════════════════════════════════════════════════

def route_after_emergency_check(state: Dict) -> str:
    """
    Check emergency state before processing.

    If AI is globally paused → state_update (log and end)
    If emergency state is full_stop → state_update
    Otherwise → pii_redaction (normal flow)

    Args:
        state: Current ParwaGraphState dict

    Returns:
        Node name string
    """
    ai_paused = state.get("ai_paused", False)
    emergency_state = state.get("emergency_state", "normal")

    if ai_paused:
        logger.warning(
            "emergency_edge_ai_paused",
            emergency_state=emergency_state,
        )
        return "state_update"

    if emergency_state == "full_stop":
        logger.warning(
            "emergency_edge_full_stop",
            emergency_state=emergency_state,
        )
        return "state_update"

    # Normal flow
    return "pii_redaction"


# ══════════════════════════════════════════════════════════════════
# EDGE 9: Route After Channel Agent
# ──────────────────────────────────────────────────────────────────
# After a channel-specific agent delivers, go to state_update
# ══════════════════════════════════════════════════════════════════

def route_after_channel_agent(state: Dict) -> str:
    """
    After a channel-specific agent completes, go to state_update
    for persistence and audit.

    Args:
        state: Current ParwaGraphState dict

    Returns:
        "state_update"
    """
    return "state_update"
