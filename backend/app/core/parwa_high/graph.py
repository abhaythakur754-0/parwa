"""
High Parwa LangGraph Pipeline — Builds and runs the 20-node pipeline.

Pipeline: pii_check -> empathy_check -> emergency_check -> gsd_state
        -> classify -> extract_signals -> technique_select
        -> reasoning_chain -> context_enrich -> context_compress
        -> generate -> crp_compress -> clara_quality_gate
        -> quality_retry (max 2) -> confidence_assess
        -> context_health -> dedup -> strategic_decision
        -> peer_review -> format -> END

Connected Frameworks (Tier 1 + Tier 2 + Tier 3):
  - CLARA (Quality Gate) — Strictest: threshold 95, 8-check
  - CRP (Token Compression) — 30-40% token reduction
  - GSD (State Engine) — Conversation state machine tracking
  - Smart Router (F-054) — Model tier selection (Heavy for High)
  - Technique Router (BC-013) — Technique selection (Tier 1+2+3)
  - Confidence Scoring (F-059) — Response confidence assessment
  - CoT, ReAct, Reverse Thinking, Step-Back, ThoT (Tier 2)
  - GST, UoT, ToT, Self-Consistency, Reflexion, Least-to-Most (Tier 3)

Architecture:
  - LangGraph StateGraph with conditional edges
  - Code-orchestrated routing (FREE, no LLM for routing)
  - Emergency bypass: emergency_check -> gsd_state -> format (skip pipeline)
  - Quality retry loop: clara_quality_gate -> quality_retry -> generate (max 2)
  - High: Tier 1+2+3 techniques with context compression + peer review

BC-001: company_id first parameter on public methods.
BC-008: Every public method wrapped in try/except — never crash.
BC-012: All timestamps UTC.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from langgraph.graph import StateGraph, END

from app.core.parwa_graph_state import (
    ParwaGraphState,
    create_initial_state,
)
from app.core.variant_router import (
    route_after_pii,
    route_after_empathy,
    route_after_emergency,
    route_after_extract_signals,
    route_after_technique_select,
    route_after_context_compress,
    route_after_quality_gate,
    route_after_context_health,
    route_after_dedup,
)
from app.core.parwa_high.nodes import (
    pii_check_node,
    empathy_check_node,
    emergency_check_node,
    gsd_state_node,
    classify_node,
    extract_signals_node,
    technique_select_node,
    reasoning_chain_node,
    context_enrich_node,
    context_compress_node,
    generate_node,
    crp_compress_node,
    clara_quality_gate_node,
    quality_retry_node,
    confidence_assess_node,
    context_health_node,
    dedup_node,
    strategic_decision_node,
    peer_review_node,
    format_node,
)
from app.logger import get_logger

logger = get_logger("parwa_high_graph")


# ══════════════════════════════════════════════════════════════════
# ROUTING FUNCTIONS (Code-orchestrated = FREE)
# ══════════════════════════════════════════════════════════════════


def route_after_gsd(state: ParwaGraphState) -> str:
    """Route after GSD state node.

    If emergency + escalate state -> skip to format.
    Otherwise -> classify (High goes classify before extract_signals).
    """
    emergency_flag = state.get("emergency_flag", False)
    step_outputs = state.get("step_outputs", {})
    gsd_output = step_outputs.get("gsd_state", {})

    if emergency_flag:
        return "format"

    if isinstance(gsd_output, dict) and gsd_output.get("to_state") == "escalate":
        return "format"

    return "classify"


def route_after_classify_high(state: ParwaGraphState) -> str:
    """Route after classify — High goes to extract_signals."""
    return "extract_signals"


def route_after_reasoning(state: ParwaGraphState) -> str:
    """Route after reasoning_chain -> always context_enrich."""
    return "context_enrich"


def route_after_context_enrich(state: ParwaGraphState) -> str:
    """Route after context_enrich -> always context_compress (High-specific)."""
    return "context_compress"


def route_after_crp(state: ParwaGraphState) -> str:
    """Route after CRP compress -> always CLARA quality gate."""
    return "clara_quality_gate"


def route_after_clara_high(state: ParwaGraphState) -> str:
    """Route after CLARA quality gate for High.

    High: If quality failed and retries remain -> quality_retry (-> generate)
         If quality passed or retries exhausted -> confidence_assess
         Max retries = 2 for High.
    """
    quality_passed = state.get("quality_passed", True)
    retry_count = state.get("quality_retry_count", 0)
    max_retries = 2  # High: max 2 retries

    if not quality_passed and retry_count < max_retries:
        return "quality_retry"

    return "confidence_assess"


def route_after_quality_retry(state: ParwaGraphState) -> str:
    """Route after quality_retry -> back to generate for retry."""
    return "generate"


def route_after_confidence(state: ParwaGraphState) -> str:
    """Route after confidence_assess -> context_health (High-specific)."""
    return "context_health"


def route_after_strategic_decision(state: ParwaGraphState) -> str:
    """Route after strategic_decision -> peer_review."""
    return "peer_review"


def route_after_peer_review(state: ParwaGraphState) -> str:
    """Route after peer_review -> format."""
    return "format"


# ══════════════════════════════════════════════════════════════════
# GRAPH BUILDER
# ══════════════════════════════════════════════════════════════════


def build_parwa_high_graph() -> StateGraph:
    """Build the High Parwa LangGraph StateGraph.

    Creates the graph with all 20 nodes and conditional edges.

    Returns:
        Compiled LangGraph StateGraph ready for execution.
    """
    graph = StateGraph(ParwaGraphState)

    # ── Add all 20 nodes ──────────────────────────────────────────
    graph.add_node("pii_check", pii_check_node)
    graph.add_node("empathy_check", empathy_check_node)
    graph.add_node("emergency_check", emergency_check_node)
    graph.add_node("gsd_state", gsd_state_node)
    graph.add_node("classify", classify_node)
    graph.add_node("extract_signals", extract_signals_node)
    graph.add_node("technique_select", technique_select_node)
    graph.add_node("reasoning_chain", reasoning_chain_node)
    graph.add_node("context_enrich", context_enrich_node)
    graph.add_node("context_compress", context_compress_node)
    graph.add_node("generate", generate_node)
    graph.add_node("crp_compress", crp_compress_node)
    graph.add_node("clara_quality_gate", clara_quality_gate_node)
    graph.add_node("quality_retry", quality_retry_node)
    graph.add_node("confidence_assess", confidence_assess_node)
    graph.add_node("context_health", context_health_node)
    graph.add_node("dedup", dedup_node)
    graph.add_node("strategic_decision", strategic_decision_node)
    graph.add_node("peer_review", peer_review_node)
    graph.add_node("format", format_node)

    # ── Set entry point ──────────────────────────────────────────
    graph.set_entry_point("pii_check")

    # ── Add edges ────────────────────────────────────────────────
    # pii_check -> empathy_check (always)
    graph.add_conditional_edges(
        "pii_check",
        route_after_pii,
        {"empathy_check": "empathy_check"},
    )

    # empathy_check -> emergency_check (always)
    graph.add_conditional_edges(
        "empathy_check",
        route_after_empathy,
        {"emergency_check": "emergency_check"},
    )

    # emergency_check -> gsd_state (always — emergency handled in gsd routing)
    graph.add_conditional_edges(
        "emergency_check",
        route_after_emergency,
        {
            "gsd_state": "gsd_state",
            "format": "format",  # Legacy emergency bypass
        },
    )

    # gsd_state -> classify (normal) OR format (emergency/escalate)
    graph.add_conditional_edges(
        "gsd_state",
        route_after_gsd,
        {
            "classify": "classify",
            "format": "format",
        },
    )

    # classify -> extract_signals (High: always goes deeper)
    graph.add_conditional_edges(
        "classify",
        route_after_classify_high,
        {"extract_signals": "extract_signals"},
    )

    # extract_signals -> technique_select (always)
    graph.add_conditional_edges(
        "extract_signals",
        route_after_extract_signals,
        {"technique_select": "technique_select"},
    )

    # technique_select -> context_compress (High: compress before generate)
    graph.add_conditional_edges(
        "technique_select",
        route_after_technique_select,
        {
            "reasoning_chain": "reasoning_chain",
            "context_compress": "context_compress",
        },
    )

    # reasoning_chain -> context_enrich (always)
    graph.add_conditional_edges(
        "reasoning_chain",
        route_after_reasoning,
        {"context_enrich": "context_enrich"},
    )

    # context_enrich -> context_compress (High-specific)
    graph.add_conditional_edges(
        "context_enrich",
        route_after_context_enrich,
        {"context_compress": "context_compress"},
    )

    # context_compress -> generate (always)
    graph.add_conditional_edges(
        "context_compress",
        route_after_context_compress,
        {"generate": "generate"},
    )

    # generate -> crp_compress (always)
    graph.add_edge("generate", "crp_compress")

    # crp_compress -> clara_quality_gate (always)
    graph.add_edge("crp_compress", "clara_quality_gate")

    # clara_quality_gate -> quality_retry (if failed) OR confidence_assess (passed)
    graph.add_conditional_edges(
        "clara_quality_gate",
        route_after_clara_high,
        {
            "quality_retry": "quality_retry",
            "confidence_assess": "confidence_assess",
        },
    )

    # quality_retry -> generate (retry loop)
    graph.add_conditional_edges(
        "quality_retry",
        route_after_quality_retry,
        {"generate": "generate"},
    )

    # confidence_assess -> context_health (High-specific)
    graph.add_conditional_edges(
        "confidence_assess",
        route_after_confidence,
        {"context_health": "context_health"},
    )

    # context_health -> dedup (always)
    graph.add_conditional_edges(
        "context_health",
        route_after_context_health,
        {"dedup": "dedup"},
    )

    # dedup -> strategic_decision (always)
    graph.add_conditional_edges(
        "dedup",
        route_after_dedup,
        {"strategic_decision": "strategic_decision"},
    )

    # strategic_decision -> peer_review (always)
    graph.add_conditional_edges(
        "strategic_decision",
        route_after_strategic_decision,
        {"peer_review": "peer_review"},
    )

    # peer_review -> format (always)
    graph.add_conditional_edges(
        "peer_review",
        route_after_peer_review,
        {"format": "format"},
    )

    # format -> END (always)
    graph.add_edge("format", END)

    # ── Compile the graph ────────────────────────────────────────
    compiled = graph.compile()

    logger.info(
        "parwa_high_graph_built",
        nodes=20,
        frameworks="CLARA+CRP+GSD+CoT+ReAct+Reverse+StepBack+ThoT+GST+UoT+ToT+SelfConsistency+Reflexion+LeastToMost",
    )

    return compiled


# ══════════════════════════════════════════════════════════════════
# PIPELINE RUNNER
# ══════════════════════════════════════════════════════════════════


class ParwaHighPipeline:
    """High Parwa pipeline — runs the 20-node LangGraph pipeline.

    Connected Frameworks (Tier 1 + Tier 2 + Tier 3):
      - CLARA: Quality gate (strictest: threshold 95, 8-check)
      - CRP: Token compression (30-40% reduction)
      - GSD: Conversation state machine tracking
      - Smart Router: Model tier selection (Heavy for High)
      - Technique Router: Technique selection (Tier 1+2+3)
      - Confidence Scoring: Response confidence assessment
      - CoT, ReAct, Reverse, Step-Back, ThoT (Tier 2)
      - GST, UoT, ToT, Self-Consistency, Reflexion, Least-to-Most (Tier 3)

    Usage:
        pipeline = ParwaHighPipeline()
        result = await pipeline.run(initial_state)
        # OR
        result = await pipeline.process_ticket(
            query="I need a refund",
            company_id="comp_123",
            industry="ecommerce",
            channel="chat",
        )
    """

    def __init__(self) -> None:
        """Initialize the pipeline by building the graph."""
        try:
            self._graph = build_parwa_high_graph()
            logger.info("ParwaHighPipeline initialized with 20 nodes + 6 Tier 1 + 5 Tier 2 + 6 Tier 3 frameworks")
        except Exception:
            logger.exception("ParwaHighPipeline init failed — graph build error")
            self._graph = None

    async def run(self, state: ParwaGraphState) -> ParwaGraphState:
        """Invoke the LangGraph pipeline with the given state.

        Args:
            state: Initial ParwaGraphState to process.

        Returns:
            Final ParwaGraphState after pipeline execution.
        """
        try:
            if self._graph is None:
                logger.error("ParwaHighPipeline graph is None — returning input state")
                return state

            start = time.monotonic()
            result = await self._graph.ainvoke(state)
            total_ms = round((time.monotonic() - start) * 1000, 2)

            if isinstance(result, dict):
                result["total_latency_ms"] = total_ms
                result["billing_tokens"] = result.get("generation_tokens", 0)

            logger.info(
                "parwa_high_pipeline_complete",
                total_latency_ms=total_ms,
                pipeline_status=result.get("pipeline_status", "unknown") if isinstance(result, dict) else "unknown",
                company_id=state.get("company_id", ""),
                quality_score=result.get("quality_score", 0) if isinstance(result, dict) else 0,
                steps_completed=result.get("steps_completed", []) if isinstance(result, dict) else [],
            )

            return result

        except Exception:
            logger.exception("ParwaHighPipeline.run failed")
            state["pipeline_status"] = "failed"
            state["errors"] = state.get("errors", []) + ["pipeline_execution_failed"]
            return state

    async def process_ticket(
        self,
        query: str,
        company_id: str,
        industry: str = "general",
        channel: str = "chat",
        customer_id: str = "",
        customer_tier: str = "free",
        conversation_id: str = "",
        ticket_id: str = "",
        variant_instance_id: str = "",
    ) -> Dict[str, Any]:
        """Convenience method: create initial state and run pipeline.

        BC-001: company_id is first parameter.

        Args:
            query: Customer's raw message.
            company_id: Tenant identifier (BC-001).
            industry: 'ecommerce' | 'logistics' | 'saas' | 'general'.
            channel: 'chat' | 'email' | 'phone' | 'web_widget' | 'social'.
            customer_id: Customer identifier.
            customer_tier: Customer subscription tier.
            conversation_id: For multi-turn tracking.
            ticket_id: Ticket identifier (auto-generated if empty).
            variant_instance_id: Specific variant instance.

        Returns:
            Dict with the final pipeline state.
        """
        try:
            if not ticket_id:
                ticket_id = f"tkt_{uuid.uuid4().hex[:12]}"

            if not conversation_id:
                conversation_id = f"conv_{uuid.uuid4().hex[:12]}"

            if not variant_instance_id:
                variant_instance_id = f"inst_high_{company_id}"

            initial_state = create_initial_state(
                query=query,
                company_id=company_id,
                variant_tier="parwa_high",
                variant_instance_id=variant_instance_id,
                industry=industry,
                channel=channel,
                conversation_id=conversation_id,
                ticket_id=ticket_id,
                customer_id=customer_id,
                customer_tier=customer_tier,
            )

            result = await self.run(initial_state)

            if hasattr(result, "__dict__"):
                return dict(result)
            return dict(result) if isinstance(result, dict) else {"error": "unexpected_result_type"}

        except Exception:
            logger.exception("process_ticket failed")
            return {
                "pipeline_status": "failed",
                "company_id": company_id,
                "error": "process_ticket_failed",
            }
