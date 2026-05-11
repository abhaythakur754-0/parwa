"""
PARWA LangGraph Multi-Agent System

This package implements the multi-agent LangGraph architecture for PARWA,
replacing the old sequential pipeline with a state-graph based approach
that supports conditional routing, MAKER validation, and tier-driven
agent availability.

Key Components:
  - state.py:    ParwaGraphState TypedDict (24 groups, ~155 fields)
  - config.py:   Variant tier configs, MAKER modes, technique access maps
  - edges.py:    Conditional edge functions for LangGraph routing
  - nodes/:      Individual agent node implementations
  - graph.py:    Main graph builder (build_parwa_graph, invoke_parwa_graph)
  - checkpointer.py: PostgresSaver state persistence

Architecture:
  START -> PII Redaction -> Empathy Engine -> Router Agent
    -> [FAQ / Refund / Technical / Billing / Complaint / Escalation]
    -> MAKER Validator -> Control System -> DSPy Optimizer
    -> Guardrails -> Channel Delivery -> [Email / SMS / Voice / Video]
    -> State Update -> END

variant_tier drives:
  - Agent availability (mini=3, pro=6, high=all)
  - MAKER mode (efficiency/balanced/conservative)
  - Technique access (T1 only / T1+T2 / T1+T2+T3)
  - Channel availability (voice=pro+high, video=high)
  - Approval requirements (none/money+vip/all risky)

API Endpoint:
  POST /api/v1/workflow/langgraph/process
"""

from app.core.langgraph.state import ParwaGraphState, create_initial_state
from app.core.langgraph.config import (
    VARIANT_CONFIG,
    MAKER_CONFIG,
    TECHNIQUE_TIER_ACCESS,
    AGENT_AVAILABILITY,
    CHANNEL_AVAILABILITY,
    CONTROL_CONFIG,
    INTENT_AGENT_MAP,
    ACTION_TYPE_MAP,
    VariantTier,
    MakerMode,
    SystemMode,
    EmergencyState,
    ApprovalDecision,
    ActionType,
    get_variant_config,
    get_maker_config,
    get_available_agents,
    get_available_techniques,
    get_available_channels,
    is_voice_enabled,
    is_video_enabled,
    map_intent_to_agent,
    classify_action_type,
    needs_human_approval,
    get_maker_k_value,
    validate_variant_tier,
    get_all_valid_tiers,
)
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
from app.core.langgraph.graph import (
    build_parwa_graph,
    invoke_parwa_graph,
    _get_node_function,
    _fallback_response,
    _NODE_IMPORTS,
)
from app.core.langgraph.checkpointer import (
    get_checkpointer,
    get_thread_id,
    reset_checkpointer,
)

__all__ = [
    # State
    "ParwaGraphState",
    "create_initial_state",
    # Config
    "VARIANT_CONFIG",
    "MAKER_CONFIG",
    "TECHNIQUE_TIER_ACCESS",
    "AGENT_AVAILABILITY",
    "CHANNEL_AVAILABILITY",
    "CONTROL_CONFIG",
    "INTENT_AGENT_MAP",
    "ACTION_TYPE_MAP",
    # Enums
    "VariantTier",
    "MakerMode",
    "SystemMode",
    "EmergencyState",
    "ApprovalDecision",
    "ActionType",
    # Helper functions
    "get_variant_config",
    "get_maker_config",
    "get_available_agents",
    "get_available_techniques",
    "get_available_channels",
    "is_voice_enabled",
    "is_video_enabled",
    "map_intent_to_agent",
    "classify_action_type",
    "needs_human_approval",
    "get_maker_k_value",
    "validate_variant_tier",
    "get_all_valid_tiers",
    # Edges
    "route_after_router",
    "route_after_maker",
    "route_after_control",
    "route_after_guardrails",
    "route_after_delivery",
    "should_use_dspy",
    "route_after_emergency_check",
    "route_after_channel_agent",
    # Graph
    "build_parwa_graph",
    "invoke_parwa_graph",
    # Checkpointer
    "get_checkpointer",
    "get_thread_id",
    "reset_checkpointer",
]
