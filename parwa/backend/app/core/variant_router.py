"""
Variant Router — V2 Unified PARWA Pipeline

Previously routed between 3 separate variant pipelines (mini 10-node,
parwa 15-node, parwa_high 27-node). Now ALL tiers use the SAME 8-node
PARWA pipeline — Node 2 (Smart Route) handles tier-based decisions
internally.

This module is preserved for backward compatibility. All routing
functions now return the unified pipeline node names.

BC-001: company_id first parameter on public methods.
BC-008: Every function has a safe default — never crashes.
BC-012: All timestamps UTC.
"""

from __future__ import annotations

from typing import List

from app.logger import get_logger

logger = get_logger("variant_router")


# ══════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════

# 8-node pipeline node names
NODE_INGEST_CLASSIFY = "node_1"
NODE_SMART_ROUTE = "node_2"
NODE_KNOWLEDGE_FETCH = "node_3"
NODE_REASONING_ENGINE = "node_4"
NODE_ACT_VERIFY = "node_5"
NODE_QUALITY_FORMAT = "node_6"
NODE_SIMPLE_RESOLVER = "node_7"
NODE_SUPER_NODE = "node_8"

# Legacy node name constants (for backward compatibility with any code
# that references the old pipeline node names)
NODE_PII = "node_1"
NODE_EMPATHY = "node_1"
NODE_EMERGENCY = "node_1"
NODE_CLASSIFY = "node_1"
NODE_EXTRACT_SIGNALS = "node_3"
NODE_TECHNIQUE_SELECT = "node_4"
NODE_CONTEXT_COMPRESS = "node_4"
NODE_GENERATE = "node_4"
NODE_QUALITY_GATE = "node_6"
NODE_CONTEXT_HEALTH = "node_6"
NODE_DEDUP = "node_6"
NODE_FORMAT = "node_6"
NODE_END = "__end__"

ALL_NODES = [
    NODE_INGEST_CLASSIFY,
    NODE_SMART_ROUTE,
    NODE_KNOWLEDGE_FETCH,
    NODE_REASONING_ENGINE,
    NODE_ACT_VERIFY,
    NODE_QUALITY_FORMAT,
    NODE_SIMPLE_RESOLVER,
    NODE_SUPER_NODE,
]


# ══════════════════════════════════════════════════════════════════
# ROUTING FUNCTIONS (backward-compatible stubs)
# ══════════════════════════════════════════════════════════════════
# These functions are kept for backward compatibility. They are NOT
# used by the new 8-node pipeline (which has its own routing in
# graph_v2.py), but may be referenced by external code or tests.


def route_after_pii(state: dict) -> str:
    """Legacy stub. Routing is now handled inside graph_v2.py."""
    try:
        return NODE_SMART_ROUTE
    except Exception:
        return NODE_SMART_ROUTE


def route_after_empathy(state: dict) -> str:
    """Legacy stub. Routing is now handled inside graph_v2.py."""
    try:
        return NODE_SMART_ROUTE
    except Exception:
        return NODE_SMART_ROUTE


def route_after_emergency(state: dict) -> str:
    """Legacy stub. Routing is now handled inside graph_v2.py."""
    try:
        return NODE_SMART_ROUTE
    except Exception:
        return NODE_SMART_ROUTE


def route_after_classify(state: dict) -> str:
    """Legacy stub. Routing is now handled inside graph_v2.py."""
    try:
        return NODE_KNOWLEDGE_FETCH
    except Exception:
        return NODE_KNOWLEDGE_FETCH


def route_after_extract_signals(state: dict) -> str:
    """Legacy stub. Routing is now handled inside graph_v2.py."""
    try:
        return NODE_KNOWLEDGE_FETCH
    except Exception:
        return NODE_KNOWLEDGE_FETCH


def route_after_technique_select(state: dict) -> str:
    """Legacy stub. Routing is now handled inside graph_v2.py."""
    try:
        return NODE_REASONING_ENGINE
    except Exception:
        return NODE_REASONING_ENGINE


def route_after_context_compress(state: dict) -> str:
    """Legacy stub. Routing is now handled inside graph_v2.py."""
    try:
        return NODE_ACT_VERIFY
    except Exception:
        return NODE_ACT_VERIFY


def route_after_generate(state: dict) -> str:
    """Legacy stub. Routing is now handled inside graph_v2.py."""
    try:
        return NODE_QUALITY_FORMAT
    except Exception:
        return NODE_QUALITY_FORMAT


def route_after_quality_gate(state: dict) -> str:
    """Legacy stub. Routing is now handled inside graph_v2.py."""
    try:
        return NODE_FORMAT
    except Exception:
        return NODE_FORMAT


def route_after_context_health(state: dict) -> str:
    """Legacy stub. Routing is now handled inside graph_v2.py."""
    try:
        return NODE_QUALITY_FORMAT
    except Exception:
        return NODE_QUALITY_FORMAT


def route_after_dedup(state: dict) -> str:
    """Legacy stub. Routing is now handled inside graph_v2.py."""
    try:
        return NODE_QUALITY_FORMAT
    except Exception:
        return NODE_QUALITY_FORMAT


# ══════════════════════════════════════════════════════════════════
# PIPELINE DEFINITIONS
# ══════════════════════════════════════════════════════════════════


def get_mini_pipeline_steps() -> List[str]:
    """Get the pipeline steps for Mini Parwa.

    All tiers now use the same 8-node pipeline. Kept for compatibility.
    """
    return ALL_NODES[:]


def get_pro_pipeline_steps() -> List[str]:
    """Get the pipeline steps for Pro Parwa.

    All tiers now use the same 8-node pipeline. Kept for compatibility.
    """
    return ALL_NODES[:]


def get_high_pipeline_steps() -> List[str]:
    """Get the pipeline steps for High Parwa.

    All tiers now use the same 8-node pipeline. Kept for compatibility.
    """
    return ALL_NODES[:]


# ══════════════════════════════════════════════════════════════════
# ROUTER CLASS
# ══════════════════════════════════════════════════════════════════


class VariantRouter:
    """Code-orchestrated router for the Variant Engine.

    In V2, all tiers use the same 8-node pipeline. Node 2 handles
    tier-aware routing internally. This class is preserved for
    backward compatibility with existing code.
    """

    def __init__(self) -> None:
        """Initialize the router."""
        logger.info(
            "VariantRouter V2 initialized — unified 8-node pipeline "
            "(tier routing handled by Node 2)"
        )

    # Instance method wrappers (backward compatibility)
    def route_after_pii(self, state: dict) -> str:
        return route_after_pii(state)

    def route_after_empathy(self, state: dict) -> str:
        return route_after_empathy(state)

    def route_after_emergency(self, state: dict) -> str:
        return route_after_emergency(state)

    def route_after_classify(self, state: dict) -> str:
        return route_after_classify(state)

    def route_after_extract_signals(self, state: dict) -> str:
        return route_after_extract_signals(state)

    def route_after_technique_select(self, state: dict) -> str:
        return route_after_technique_select(state)

    def route_after_context_compress(self, state: dict) -> str:
        return route_after_context_compress(state)

    def route_after_generate(self, state: dict) -> str:
        return route_after_generate(state)

    def route_after_quality_gate(self, state: dict) -> str:
        return route_after_quality_gate(state)

    def route_after_context_health(self, state: dict) -> str:
        return route_after_context_health(state)

    def route_after_dedup(self, state: dict) -> str:
        return route_after_dedup(state)

    def get_pipeline_steps(self, variant_tier: str) -> List[str]:
        """Get the pipeline step list — same for all tiers now.

        Args:
            variant_tier: 'mini_parwa' | 'parwa' | 'parwa_high'.

        Returns:
            Ordered list of 8 node names.
        """
        return ALL_NODES[:]

    def get_all_conditional_edges(self) -> dict:
        """Get all conditional edge mappings (legacy interface).

        Returns:
            Dict mapping old node names to routing functions.
        """
        return {
            NODE_PII: route_after_pii,
            NODE_EMPATHY: route_after_empathy,
            NODE_EMERGENCY: route_after_emergency,
            NODE_CLASSIFY: route_after_classify,
            NODE_EXTRACT_SIGNALS: route_after_extract_signals,
            NODE_TECHNIQUE_SELECT: route_after_technique_select,
            NODE_CONTEXT_COMPRESS: route_after_context_compress,
            NODE_GENERATE: route_after_generate,
            NODE_QUALITY_GATE: route_after_quality_gate,
            NODE_CONTEXT_HEALTH: route_after_context_health,
            NODE_DEDUP: route_after_dedup,
        }
