"""
PARWA LangGraph Multi-Agent System

This package implements the multi-agent LangGraph architecture for PARWA,
replacing the old sequential pipeline with a state-graph based approach
that supports conditional routing, MAKER validation, and tier-driven
agent availability.

Key Components:
  - state.py:    ParwaGraphState TypedDict (18 groups, ~117 fields)
  - config.py:   Variant tier configs, MAKER modes, technique access maps
  - edges.py:    Conditional edge functions for LangGraph routing
  - nodes/:      Individual agent node implementations
  - graph.py:    Main graph builder (Phase 3)
  - checkpointer.py: PostgresSaver state persistence (Phase 3)

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
"""

from app.core.langgraph.state import ParwaGraphState
from app.core.langgraph.config import (
    VARIANT_CONFIG,
    MAKER_CONFIG,
    TECHNIQUE_TIER_ACCESS,
    AGENT_AVAILABILITY,
    CHANNEL_AVAILABILITY,
    VariantTier,
    MakerMode,
)

__all__ = [
    "ParwaGraphState",
    "VARIANT_CONFIG",
    "MAKER_CONFIG",
    "TECHNIQUE_TIER_ACCESS",
    "AGENT_AVAILABILITY",
    "CHANNEL_AVAILABILITY",
    "VariantTier",
    "MakerMode",
]
