"""
PARWA Pipeline V2 — Graph Definition

Wires all 8 nodes with LangGraph StateGraph.

Flow:
  Node 1 (Ingest+Classify) → Node 2 (Smart Route)
    ├── simple_path  → Node 3 (Knowledge) → Node 7 (Simple Resolver)
    │                     └── auto_upgraded → Node 4 (Reasoning) path
    └── complex_path → Node 3 (Knowledge) → Node 4 (Reasoning)
                                                  → Node 5 (Act+Verify)
                                                  → Node 6 (Quality)
                                                    ├── PASS → END (resolved)
                                                    ├── FAIL + loops < 2 → Node 4 (loop)
                                                    └── FAIL + loops >= 2 → Node 8 (Super Node)
                                                                          ├── PASS → END (resolved)
                                                                          └── FAIL → END (escalated)
"""

from __future__ import annotations

import logging
from typing import Literal

from langgraph.graph import END, StateGraph

from app.core.parwa_pipeline.config import (
    MAX_QUALITY_LOOPS,
    PATH_COMPLEX,
    PATH_SIMPLE,
    QUALITY_LOOP_THRESHOLD,
    QUALITY_PASS_THRESHOLD,
)
from app.core.parwa_pipeline.nodes.node_1_ingest_classify import node_1_ingest_classify
from app.core.parwa_pipeline.nodes.node_2_smart_route import node_2_smart_route
from app.core.parwa_pipeline.nodes.node_3_knowledge_fetch import node_3_knowledge_fetch
from app.core.parwa_pipeline.nodes.node_4_reasoning_engine import node_4_reasoning_engine
from app.core.parwa_pipeline.nodes.node_5_act_verify import node_5_act_verify
from app.core.parwa_pipeline.nodes.node_6_quality_format import node_6_quality_format
from app.core.parwa_pipeline.nodes.node_7_simple_resolver import node_7_simple_resolver
from app.core.parwa_pipeline.nodes.node_8_super_node import node_8_super_node
from app.core.parwa_pipeline.state_v2 import PipelineV2State

logger = logging.getLogger("parwa.pipeline.graph_v2")


# ── Edge Functions ────────────────────────────────────────────────


def _route_after_node_2(state: PipelineV2State) -> Literal["node_3", "__end__"]:
    """After Node 2: route to knowledge fetch (shared node for both paths)."""
    return "node_3"


def _route_after_node_3(state: PipelineV2State) -> Literal["node_7", "node_4"]:
    """After Node 3: simple path → Node 7, complex path → Node 4."""
    path = state.get("route_decision", state.get("current_path", "simple_path"))
    if path == "simple_path":
        return "node_7"
    return "node_4"


def _route_after_node_7(state: PipelineV2State) -> Literal["node_4", "__end__"]:
    """After Node 7: safety net check."""
    if state.get("auto_upgraded", False):
        logger.info("Node 7 safety net triggered → upgrading to Node 4 (complex path)")
        return "node_4"
    # Simple resolver passed — use its answer
    return "__end__"


def _route_after_node_6(state: PipelineV2State) -> Literal["node_4", "node_8", "__end__"]:
    """After Node 6: quality gate decision.

    PASS (quality >= 90%) → END (resolved)
    FAIL + loops < MAX → Node 4 (retry)
    FAIL + loops >= MAX → Node 8 (Super Node)
    """
    quality = state.get("quality_score", 0.0)
    loop_count = state.get("loop_count", 0)

    if quality >= QUALITY_PASS_THRESHOLD:
        logger.info(
            "Quality PASSED: score=%.2f >= %.2f → resolved",
            quality, QUALITY_PASS_THRESHOLD,
        )
        return "__end__"

    if loop_count < MAX_QUALITY_LOOPS:
        logger.info(
            "Quality FAILED: score=%.2f, loop=%d/%d → back to Node 4",
            quality, loop_count + 1, MAX_QUALITY_LOOPS,
        )
        return "node_4"

    logger.info(
        "Quality FAILED after %d loops: score=%.2f → Node 8 (Super Node)",
        MAX_QUALITY_LOOPS, quality,
    )
    return "node_8"


def _route_after_node_8(state: PipelineV2State) -> Literal["__end__"]:
    """After Node 8: always end (either resolved or escalated)."""
    return "__end__"


# ── State Updater for Quality Loop ─────────────────────────────────


def _increment_loop(state: PipelineV2State) -> dict:
    """Increment loop counter when looping back to Node 4."""
    return {"loop_count": state.get("loop_count", 0) + 1}


def _finalize_simple(state: PipelineV2State) -> dict:
    """Set final response from simple resolver."""
    return {
        "final_response": state.get("simple_answer", ""),
        "status": "resolved",
        "formatted_response": state.get("simple_answer", ""),
        "quality_passed": True,
    }


# ── Build Graph ───────────────────────────────────────────────────


def build_parwa_pipeline() -> StateGraph:
    """Build the 8-node PARWA pipeline graph.

    Usage:
        graph = build_parwa_pipeline()
        compiled = graph.compile()
        result = await compiled.ainvoke(initial_state)
    """
    graph = StateGraph(PipelineV2State)

    # ── Add Nodes ─────────────────────────────────────────────────
    graph.add_node("node_1", node_1_ingest_classify)
    graph.add_node("node_2", node_2_smart_route)
    graph.add_node("node_3", node_3_knowledge_fetch)
    graph.add_node("node_4", node_4_reasoning_engine)
    graph.add_node("node_5", node_5_act_verify)
    graph.add_node("node_6", node_6_quality_format)
    graph.add_node("node_7", node_7_simple_resolver)
    graph.add_node("node_8", node_8_super_node)
    graph.add_node("increment_loop", _increment_loop)
    graph.add_node("finalize_simple", _finalize_simple)

    # ── Add Edges ─────────────────────────────────────────────────

    # Entry → Node 1
    graph.set_entry_point("node_1")

    # Node 1 → Node 2
    graph.add_edge("node_1", "node_2")

    # Node 2 → Node 3 (always go to knowledge fetch)
    graph.add_edge("node_2", "node_3")

    # Node 3 → SPLIT: simple → Node 7, complex → Node 4
    graph.add_conditional_edges("node_3", _route_after_node_3, {
        "node_7": "node_7",
        "node_4": "node_4",
    })

    # Node 7 (Simple Resolver) → SPLIT: pass → finalize, safety net → Node 4
    graph.add_conditional_edges("node_7", _route_after_node_7, {
        "node_4": "node_4",
        "__end__": "finalize_simple",
    })

    # Node 4 (Reasoning) → Node 5
    graph.add_edge("node_4", "node_5")

    # Node 5 (Act+Verify) → Node 6
    graph.add_edge("node_5", "node_6")

    # Node 6 (Quality) → SPLIT: pass → end, fail → loop or super
    graph.add_conditional_edges("node_6", _route_after_node_6, {
        "__end__": "__end__",
        "node_4": "increment_loop",
        "node_8": "node_8",
    })

    # Increment loop counter → back to Node 4
    graph.add_edge("increment_loop", "node_4")

    # Node 8 (Super Node) → END
    graph.add_edge("node_8", "__end__")

    # Finalize simple → END
    graph.add_edge("finalize_simple", "__end__")

    logger.info("PARWA Pipeline V2 built: 8 nodes, dual path, quality loop (max %d)", MAX_QUALITY_LOOPS)

    return graph