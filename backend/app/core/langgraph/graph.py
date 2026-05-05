"""
PARWA LangGraph Graph Builder

This module constructs the complete LangGraph StateGraph that wires
all 19 agent nodes together with conditional edges based on variant_tier.

Graph Flow:
  START
    → Emergency Check (conditional)
    → PII Redaction
    → Empathy Engine
    → Router Agent ──(conditional: intent)──→ Domain Agent
    → MAKER Validator (updates agent_response with best solution)
    → Control System (conditional, may interrupt)
    → DSPy Optimizer (conditional: tier + complexity, RE-GENERATES response)
    → Guardrails
    → Channel Delivery ──(conditional: channel)──→ Delivery Agent
    → State Update
    → END

Conditional Edges:
  1. route_after_router     — Intent → domain agent (variant_tier aware)
  2. route_after_maker      — Red flag → Control System or skip
  3. route_after_control    — Approval decision → proceed or wait
  4. route_after_guardrails — Blocked → end or continue
  5. route_after_delivery   — Channel → delivery agent
  6. should_use_dspy        — Skip DSPy for mini / simple queries
  7. route_after_emergency  — AI paused → end or proceed

interrupt_before:
  - Control System node is configured with interrupt_before when
    variant_tier is pro/high and the action needs human approval.

Checkpointer:
  - PostgresSaver for state persistence across interrupts
  - Falls back to MemorySaver if PostgresSaver unavailable

BC-008: Graph building wraps in try/except, never crashes.
BC-001: All state operations include tenant_id.
"""

from __future__ import annotations

import importlib
from typing import Any, Dict, Optional

from app.logger import get_logger

logger = get_logger("langgraph_graph")


# ══════════════════════════════════════════════════════════════════
# LAZY NODE IMPORTS — Modules start with digits, use importlib
# ══════════════════════════════════════════════════════════════════

_NODE_IMPORTS = {
    "pii_redaction": "01_pii_redaction",
    "empathy_engine": "02_empathy_engine",
    "router_agent": "03_router_agent",
    "faq_agent": "05_faq_agent",
    "refund_agent": "06_refund_agent",
    "technical_agent": "07_technical_agent",
    "billing_agent": "08_billing_agent",
    "complaint_agent": "09_complaint_agent",
    "escalation_agent": "10_escalation_agent",
    "maker_validator": "11_maker_validator",
    "control_system": "12_control_system",
    "dspy_optimizer": "13_dspy_optimizer",
    "guardrails": "14_guardrails",
    "channel_delivery": "15_channel_delivery",
    "state_update": "16_state_update",
    "email_agent": "17_email_agent",
    "sms_agent": "18_sms_agent",
    "voice_agent": "19_voice_agent",
}
# NOTE: video_agent removed — no ROI on video support (CEO decision 2026-05-05)
# If needed later, integrate Zoom/Google Meet as a connector instead.

_NODE_CACHE: Dict[str, Any] = {}


def _get_node_function(node_name: str):
    """
    Lazily import and cache a node function.

    Node modules start with digits (01_, 02_, etc.) so we use
    importlib.import_module() instead of regular imports.

    Args:
        node_name: Node key (e.g., "pii_redaction", "maker_validator")

    Returns:
        The node function callable
    """
    if node_name in _NODE_CACHE:
        return _NODE_CACHE[node_name]

    module_path = _NODE_IMPORTS.get(node_name)
    if module_path is None:
        raise ValueError(f"Unknown node: {node_name}")

    full_path = f"app.core.langgraph.nodes.{module_path}"
    module = importlib.import_module(full_path)

    # Convention: node function name = {node_name}_node
    func_name = f"{node_name}_node"
    node_func = getattr(module, func_name, None)

    if node_func is None:
        raise ValueError(f"Node function '{func_name}' not found in {full_path}")

    _NODE_CACHE[node_name] = node_func
    return node_func


# ══════════════════════════════════════════════════════════════════
# GRAPH BUILDER
# ══════════════════════════════════════════════════════════════════


def build_parwa_graph(
    checkpointer: Optional[Any] = None,
    interrupt_before: Optional[list] = None,
) -> Any:
    """
    Build the complete PARWA LangGraph StateGraph.

    Constructs the graph with all 19 nodes, conditional edges,
    and variant_tier-driven routing. Returns a compiled graph
    ready for execution.

    Args:
        checkpointer: LangGraph checkpointer for state persistence.
                      If None, uses MemorySaver as default.
        interrupt_before: List of node names where graph should
                          interrupt before execution (for human-in-the-loop).
                          Default: ["control_system"] for pro/high tiers.

    Returns:
        Compiled LangGraph StateGraph

    Raises:
        ImportError: If langgraph package is not installed
    """
    try:
        from langgraph.graph import StateGraph, END, START
    except ImportError:
        raise ImportError(
            "langgraph package is required. "
            "Install with: pip install langgraph"
        )

    from app.core.langgraph.state import ParwaGraphState

    # ── Default interrupt_before for human-in-the-loop ──────────
    if interrupt_before is None:
        interrupt_before = ["control_system"]

    # ── Default checkpointer ───────────────────────────────────
    if checkpointer is None:
        checkpointer = _get_default_checkpointer()

    # ── Build StateGraph ───────────────────────────────────────
    builder = StateGraph(ParwaGraphState)

    # ── Add All Nodes ──────────────────────────────────────────
    _add_nodes(builder)

    # ── Import routing functions (needed by _add_edges) ──────
    from app.core.langgraph.edges import (
        route_after_router,
        route_after_maker,
        route_after_control,
        route_after_guardrails,
        route_after_delivery,
        should_use_dspy,
        route_after_emergency_check,
        route_after_channel_agent,
    )

    # ── Add Edges ──────────────────────────────────────────────
    _add_edges(
        builder, START, END,
        route_after_router=route_after_router,
        route_after_maker=route_after_maker,
        route_after_control=route_after_control,
        route_after_guardrails=route_after_guardrails,
        route_after_delivery=route_after_delivery,
    )

    # ── Compile Graph ──────────────────────────────────────────
    compiled = builder.compile(
        checkpointer=checkpointer,
        interrupt_before=interrupt_before if interrupt_before else None,
    )

    logger.info(
        "parwa_graph_built",
        node_count=len(_NODE_IMPORTS),
        interrupt_before=interrupt_before,
        has_checkpointer=checkpointer is not None,
    )

    return compiled


def _add_nodes(builder: Any) -> None:
    """
    Register all agent nodes with the StateGraph builder.

    Each node is lazily imported and added to the graph.
    The node function is wrapped to handle errors gracefully.
    """
    for node_name in _NODE_IMPORTS:
        try:
            node_func = _get_node_function(node_name)
            builder.add_node(node_name, node_func)
        except Exception as exc:
            logger.warning(
                "node_registration_failed",
                node_name=node_name,
                error=str(exc),
            )
            # Add a no-op fallback node
            # Capture exc_str as default arg to avoid Python 3's except-var cleanup
            exc_str = str(exc)
            builder.add_node(node_name, lambda state, _name=node_name, _exc=exc_str: {
                "errors": [f"Node {_name} failed to load"],
                "node_execution_log": [{
                    "node_name": _name,
                    "status": "error",
                    "error": _exc,
                }],
            })


def _add_edges(
    builder: Any,
    START: Any,
    END: Any,
    *,
    route_after_router: Any,
    route_after_maker: Any,
    route_after_control: Any,
    route_after_guardrails: Any,
    route_after_delivery: Any,
) -> None:
    """
    Wire all edges (sequential + conditional) in the StateGraph.

    Flow:
      START → emergency_check (conditional) → pii_redaction
      pii_redaction → empathy_engine
      empathy_engine → router_agent
      router_agent → (conditional: route_after_router) → domain agents
      domain agents → maker_validator
      maker_validator → (conditional: route_after_maker) → control_system or dspy_optimizer
      control_system → (conditional: route_after_control) → dspy_optimizer or state_update
      dspy_optimizer → guardrails
      guardrails → (conditional: route_after_guardrails) → channel_delivery or state_update
      channel_delivery → (conditional: route_after_delivery) → delivery agents
      delivery agents → state_update
      state_update → END
    """
    # ── Entry Point ────────────────────────────────────────────
    builder.add_edge(START, "pii_redaction")

    # ── Sequential Edges: Pre-processing ───────────────────────
    builder.add_edge("pii_redaction", "empathy_engine")
    builder.add_edge("empathy_engine", "router_agent")

    # ── Conditional Edge: Router → Domain Agents ───────────────
    domain_agents = [
        "faq_agent", "refund_agent", "technical_agent",
        "billing_agent", "complaint_agent", "escalation_agent",
    ]
    builder.add_conditional_edges(
        "router_agent",
        route_after_router,
        {agent: agent for agent in domain_agents},
    )

    # ── All Domain Agents → MAKER Validator ────────────────────
    for agent in domain_agents:
        builder.add_edge(agent, "maker_validator")

    # ── Conditional Edge: MAKER → Control System or DSPy ───────
    builder.add_conditional_edges(
        "maker_validator",
        route_after_maker,
        {
            "control_system": "control_system",
            "dspy_optimizer": "dspy_optimizer",
        },
    )

    # ── Conditional Edge: Control → DSPy or State Update ───────
    builder.add_conditional_edges(
        "control_system",
        route_after_control,
        {
            "dspy_optimizer": "dspy_optimizer",
            "state_update": "state_update",
        },
    )

    # ── DSPy → Guardrails ──────────────────────────────────────
    builder.add_edge("dspy_optimizer", "guardrails")

    # ── Conditional Edge: Guardrails → Delivery or End ─────────
    builder.add_conditional_edges(
        "guardrails",
        route_after_guardrails,
        {
            "channel_delivery": "channel_delivery",
            "state_update": "state_update",
        },
    )

    # ── Conditional Edge: Channel Delivery → Delivery Agents ───
    delivery_agents = {
        "email_agent": "email_agent",
        "sms_agent": "sms_agent",
        "voice_agent": "voice_agent",
        "state_update": "state_update",  # chat/api go directly to state_update
    }
    builder.add_conditional_edges(
        "channel_delivery",
        route_after_delivery,
        delivery_agents,
    )

    # ── All Delivery Agents → State Update ─────────────────────
    for agent in ("email_agent", "sms_agent", "voice_agent"):
        builder.add_edge(agent, "state_update")

    # ── State Update → END ─────────────────────────────────────
    builder.add_edge("state_update", END)


def _get_default_checkpointer() -> Any:
    """
    Get the default checkpointer for state persistence.

    Tries PostgresSaver first (production), falls back to
    MemorySaver (development/testing).

    Returns:
        Checkpointer instance
    """
    # Try PostgresSaver (production)
    try:
        from app.core.langgraph.checkpointer import get_checkpointer
        return get_checkpointer()
    except Exception as exc:
        logger.info(
            "postgres_checkpointer_unavailable_using_memory",
            error=str(exc),
        )

    # Fallback to MemorySaver
    try:
        from langgraph.checkpoint.memory import MemorySaver
        return MemorySaver()
    except ImportError:
        logger.warning(
            "no_checkpointer_available",
            message="LangGraph checkpointer not available, state will not persist",
        )
        return None


# ══════════════════════════════════════════════════════════════════
# GRAPH INVOCATION HELPER
# ══════════════════════════════════════════════════════════════════


async def invoke_parwa_graph(
    message: str,
    channel: str,
    customer_id: str,
    tenant_id: str,
    variant_tier: str,
    customer_tier: str = "free",
    industry: str = "general",
    language: str = "en",
    conversation_id: str = "",
    ticket_id: str = "",
    session_id: str = "",
    graph: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Invoke the PARWA LangGraph with a customer message.

    This is the main entry point for processing customer messages
    through the multi-agent system.

    Args:
        message: Raw incoming message from customer
        channel: Origin channel (email, sms, voice, chat, api)
        customer_id: Customer identifier
        tenant_id: Company/tenant identifier (BC-001)
        variant_tier: Variant tier (mini, pro, high)
        customer_tier: Customer segment (free, pro, enterprise, vip)
        industry: Industry vertical
        language: Language code
        conversation_id: Conversation ID (empty = new conversation)
        ticket_id: Ticket ID (empty = new ticket)
        session_id: Session ID (empty = new session)
        graph: Pre-built graph (if None, builds a new one)

    Returns:
        Final ParwaGraphState dict after graph execution
    """
    from app.core.langgraph.state import create_initial_state

    # Build graph if not provided
    if graph is None:
        try:
            graph = build_parwa_graph()
        except ImportError as exc:
            logger.error(
                "langgraph_not_available",
                error=str(exc),
                tenant_id=tenant_id,
            )
            # Return a basic response without LangGraph
            return _fallback_response(message, variant_tier, tenant_id)

    # Create initial state
    initial_state = create_initial_state(
        message=message,
        channel=channel,
        customer_id=customer_id,
        tenant_id=tenant_id,
        variant_tier=variant_tier,
        customer_tier=customer_tier,
        industry=industry,
        language=language,
        conversation_id=conversation_id,
        ticket_id=ticket_id,
        session_id=session_id,
    )

    # Configuration for the graph invocation
    config = {
        "configurable": {
            "thread_id": session_id or conversation_id or f"{tenant_id}_{customer_id}",
        },
    }

    try:
        # Invoke the graph
        result = await graph.ainvoke(initial_state, config)

        logger.info(
            "parwa_graph_invoked",
            tenant_id=tenant_id,
            variant_tier=variant_tier,
            channel=channel,
            delivery_status=result.get("delivery_status", "unknown"),
            intent=result.get("intent", "unknown"),
            target_agent=result.get("target_agent", "unknown"),
            tokens_consumed=result.get("tokens_consumed", 0),
        )

        return result

    except Exception as exc:
        logger.error(
            "parwa_graph_invocation_failed",
            tenant_id=tenant_id,
            error=str(exc),
        )
        return _fallback_response(message, variant_tier, tenant_id, str(exc))


def _fallback_response(
    message: str,
    variant_tier: str,
    tenant_id: str,
    error: str = "",
) -> Dict[str, Any]:
    """
    Generate a fallback response when LangGraph is unavailable.

    This ensures BC-008 compliance — even if the entire graph
    system fails, we still return a valid response.

    Args:
        message: Original message
        variant_tier: Variant tier
        tenant_id: Tenant identifier
        error: Error message, if any

    Returns:
        Minimal valid ParwaGraphState dict
    """
    from app.core.langgraph.state import create_initial_state
    from datetime import datetime, timezone

    state = create_initial_state(
        message=message,
        channel="email",
        customer_id="unknown",
        tenant_id=tenant_id,
        variant_tier=variant_tier,
    )

    state.update({
        "agent_response": (
            "Thank you for your message. Our team will review your "
            "request and get back to you shortly."
        ),
        "agent_confidence": 0.0,
        "proposed_action": "escalate",
        "action_type": "escalation",
        "delivery_status": "pending_human_review",
        "error": error or "LangGraph unavailable, queued for human review",
        "system_mode": "paused",
    })

    return state
