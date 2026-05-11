"""
Pro Parwa LangGraph Pipeline — Builds and runs the 22-node pipeline.

Pipeline: pii_check -> empathy_check -> emergency_check -> gsd_state
        -> classify -> smart_enrichment -> [deep_enrichment_router]
          -> complaint_handler | retention_negotiator | billing_resolver
          | tech_diagnostic | shipping_tracker | (skip)
        -> extract_signals -> technique_select
        -> reasoning_chain -> context_enrich -> generate
        -> crp_compress -> clara_quality_gate -> quality_retry
        -> confidence_assess -> auto_action -> format -> END

Connected Frameworks (Tier 1 + Tier 2):
  - CLARA (Quality Gate) — Enhanced: threshold 85, 5-check + advanced
  - CRP (Token Compression) — 30-40% token reduction
  - GSD (State Engine) — Conversation state machine tracking
  - Smart Router (F-054) — Model tier selection (Medium for Pro)
  - Technique Router (BC-013) — Technique selection (Tier 1+2)
  - Confidence Scoring (F-059) — Response confidence assessment
  - CoT (Chain of Thought) — Step-by-step reasoning (Tier 2)
  - ReAct — Reasoning + acting (Tier 2)
  - Reverse Thinking — Inversion-based reasoning (Tier 2)
  - Step-Back — Broader context seeking (Tier 2)
  - ThoT (Thread of Thought) — Multi-turn continuity (Tier 2)

Architecture:
  - LangGraph StateGraph with conditional edges
  - Code-orchestrated routing (FREE, no LLM for routing)
  - Emergency bypass: emergency_check -> gsd_state -> format (skip pipeline)
  - Quality retry loop: clara_quality_gate -> quality_retry -> generate (max 1)
  - Pro: Tier 1+2 techniques (CLARA, CRP, GSD + CoT, ReAct, Reverse, Step-Back, ThoT)

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
    route_after_quality_gate,
)
from app.core.parwa.nodes import (
    smart_enrichment_node,
    auto_action_node,
    pii_check_node,
    empathy_check_node,
    emergency_check_node,
    gsd_state_node,
    classify_node,
    extract_signals_node,
    technique_select_node,
    reasoning_chain_node,
    context_enrich_node,
    generate_node,
    crp_compress_node,
    clara_quality_gate_node,
    quality_retry_node,
    confidence_assess_node,
    format_node,
    # Deep enrichment nodes
    complaint_handler_node,
    retention_negotiator_node,
    billing_resolver_node,
    tech_diagnostic_node,
    shipping_tracker_node,
)
from app.logger import get_logger

logger = get_logger("parwa_graph")


# ══════════════════════════════════════════════════════════════════
# ROUTING FUNCTIONS (Code-orchestrated = FREE)
# ══════════════════════════════════════════════════════════════════


def route_after_gsd(state: ParwaGraphState) -> str:
    """Route after GSD state node.

    If emergency + escalate state -> skip to format.
    Otherwise -> classify (Pro goes classify before extract_signals).
    """
    emergency_flag = state.get("emergency_flag", False)
    step_outputs = state.get("step_outputs", {})
    gsd_output = step_outputs.get("gsd_state", {})

    # Emergency escalation bypasses the entire pipeline
    if emergency_flag:
        return "format"

    # Check if GSD suggests escalation
    if isinstance(gsd_output, dict) and gsd_output.get("to_state") == "escalate":
        return "format"

    return "classify"


def route_after_classify_pro(state: ParwaGraphState) -> str:
    """Route after classify — Pro goes to smart_enrichment first.

    Mini: classify -> generate (shortcut)
    Pro: classify -> smart_enrichment -> extract_signals (go deeper)
    """
    return "smart_enrichment"


# Intent to deep enrichment mapping
INTENT_DEEP_ENRICHMENT_MAP = {
    "complaint": "complaint_handler",
    "feedback": "complaint_handler",
    "cancellation": "retention_negotiator",
    "cancel": "retention_negotiator",
    "billing": "billing_resolver",
    "payment": "billing_resolver",
    "refund": "billing_resolver",
    "technical": "tech_diagnostic",
    "bug": "tech_diagnostic",
    "shipping": "shipping_tracker",
    "delivery": "shipping_tracker",
    "tracking": "shipping_tracker",
    "order": "shipping_tracker",
}


def route_after_smart_enrichment_deep(state: ParwaGraphState) -> str:
    """Route after smart_enrichment to intent-specific deep enrichment.

    If the intent matches a deep enrichment node, route there.
    Otherwise, skip directly to extract_signals (no deep enrichment needed).
    """
    classification = state.get("classification", {})
    intent = classification.get("intent", "").lower()

    # Check if intent maps to a deep enrichment node
    deep_node = INTENT_DEEP_ENRICHMENT_MAP.get(intent)
    if deep_node:
        return deep_node

    # Also check secondary intents
    secondary_intents = classification.get("secondary_intents", [])
    for sec_intent in secondary_intents:
        deep_node = INTENT_DEEP_ENRICHMENT_MAP.get(sec_intent.lower())
        if deep_node:
            return deep_node

    # No deep enrichment needed
    return "extract_signals"


def route_after_deep_enrichment(state: ParwaGraphState) -> str:
    """Route after deep enrichment → always extract_signals."""
    return "extract_signals"


def route_after_reasoning(state: ParwaGraphState) -> str:
    """Route after reasoning_chain -> always context_enrich."""
    return "context_enrich"


def route_after_context_enrich(state: ParwaGraphState) -> str:
    """Route after context_enrich -> always generate."""
    return "generate"


def route_after_crp(state: ParwaGraphState) -> str:
    """Route after CRP compress -> always CLARA quality gate."""
    return "clara_quality_gate"


def route_after_clara_pro(state: ParwaGraphState) -> str:
    """Route after CLARA quality gate for Pro.

    Pro: If quality failed and retries remain -> quality_retry (-> generate)
         If quality passed or retries exhausted -> confidence_assess
    """
    quality_passed = state.get("quality_passed", True)
    retry_count = state.get("quality_retry_count", 0)
    max_retries = 1

    if not quality_passed and retry_count < max_retries:
        return "quality_retry"

    return "confidence_assess"


def route_after_quality_retry(state: ParwaGraphState) -> str:
    """Route after quality_retry -> back to generate for retry."""
    return "generate"


def route_after_confidence(state: ParwaGraphState) -> str:
    """Route after confidence_assess -> auto_action (then format)."""
    return "auto_action"


def route_after_auto_action(state: ParwaGraphState) -> str:
    """Route after auto_action -> always format."""
    return "format"


# ══════════════════════════════════════════════════════════════════
# GRAPH BUILDER
# ══════════════════════════════════════════════════════════════════


def build_parwa_graph() -> StateGraph:
    """Build the Pro Parwa LangGraph StateGraph.

    Creates the graph with all 22 nodes and conditional edges:
      - pii_check -> empathy_check (always)
      - empathy_check -> emergency_check (always)
      - emergency_check -> gsd_state (always — emergency handled in gsd routing)
      - gsd_state -> classify (normal) OR format (emergency/escalate)
      - classify -> smart_enrichment (Pro: enrichment before signals)
      - smart_enrichment -> deep enrichment (intent-specific) OR extract_signals (skip)
      - deep enrichment -> extract_signals (all converge)
      - extract_signals -> technique_select (always)
      - technique_select -> reasoning_chain (always)
      - reasoning_chain -> context_enrich (always)
      - context_enrich -> generate (always)
      - generate -> crp_compress (always)
      - crp_compress -> clara_quality_gate (always)
      - clara_quality_gate -> quality_retry (if quality failed) OR confidence_assess (passed)
      - quality_retry -> generate (retry loop, max 1)
      - confidence_assess -> format (always)
      - format -> END

    Returns:
        Compiled LangGraph StateGraph ready for execution.
    """
    # Create the graph with our state type
    graph = StateGraph(ParwaGraphState)

    # ── Add all 22 nodes ──────────────────────────────────────────
    graph.add_node("smart_enrichment", smart_enrichment_node)
    graph.add_node("auto_action", auto_action_node)
    graph.add_node("pii_check", pii_check_node)
    graph.add_node("empathy_check", empathy_check_node)
    graph.add_node("emergency_check", emergency_check_node)
    graph.add_node("gsd_state", gsd_state_node)
    graph.add_node("classify", classify_node)
    graph.add_node("extract_signals", extract_signals_node)
    graph.add_node("technique_select", technique_select_node)
    graph.add_node("reasoning_chain", reasoning_chain_node)
    graph.add_node("context_enrich", context_enrich_node)
    graph.add_node("generate", generate_node)
    graph.add_node("crp_compress", crp_compress_node)
    graph.add_node("clara_quality_gate", clara_quality_gate_node)
    graph.add_node("quality_retry", quality_retry_node)
    graph.add_node("confidence_assess", confidence_assess_node)
    graph.add_node("format", format_node)
    # Deep enrichment nodes (5 intent-specific)
    graph.add_node("complaint_handler", complaint_handler_node)
    graph.add_node("retention_negotiator", retention_negotiator_node)
    graph.add_node("billing_resolver", billing_resolver_node)
    graph.add_node("tech_diagnostic", tech_diagnostic_node)
    graph.add_node("shipping_tracker", shipping_tracker_node)

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

    # classify -> smart_enrichment (Pro: enrichment before signals)
    graph.add_conditional_edges(
        "classify",
        route_after_classify_pro,
        {"smart_enrichment": "smart_enrichment"},
    )

    # smart_enrichment -> deep enrichment (intent-specific) OR extract_signals (skip)
    graph.add_conditional_edges(
        "smart_enrichment",
        route_after_smart_enrichment_deep,
        {
            "complaint_handler": "complaint_handler",
            "retention_negotiator": "retention_negotiator",
            "billing_resolver": "billing_resolver",
            "tech_diagnostic": "tech_diagnostic",
            "shipping_tracker": "shipping_tracker",
            "extract_signals": "extract_signals",
        },
    )

    # Deep enrichment -> extract_signals (all converge)
    for deep_node in ["complaint_handler", "retention_negotiator", "billing_resolver", "tech_diagnostic", "shipping_tracker"]:
        graph.add_conditional_edges(
            deep_node,
            route_after_deep_enrichment,
            {"extract_signals": "extract_signals"},
        )

    # extract_signals -> technique_select (always)
    graph.add_conditional_edges(
        "extract_signals",
        route_after_extract_signals,
        {"technique_select": "technique_select"},
    )

    # technique_select -> reasoning_chain (always for Pro)
    graph.add_conditional_edges(
        "technique_select",
        route_after_technique_select,
        {
            "reasoning_chain": "reasoning_chain",
            "generate": "reasoning_chain",  # Pro always does reasoning
        },
    )

    # reasoning_chain -> context_enrich (always)
    graph.add_conditional_edges(
        "reasoning_chain",
        route_after_reasoning,
        {"context_enrich": "context_enrich"},
    )

    # context_enrich -> generate (always)
    graph.add_conditional_edges(
        "context_enrich",
        route_after_context_enrich,
        {"generate": "generate"},
    )

    # generate -> crp_compress (always — CRP is Tier 1 active)
    graph.add_edge("generate", "crp_compress")

    # crp_compress -> clara_quality_gate (always — CLARA is Tier 1 active)
    graph.add_edge("crp_compress", "clara_quality_gate")

    # clara_quality_gate -> quality_retry (if failed) OR confidence_assess (passed)
    graph.add_conditional_edges(
        "clara_quality_gate",
        route_after_clara_pro,
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

    # confidence_assess -> auto_action (enrichment actions)
    graph.add_conditional_edges(
        "confidence_assess",
        route_after_confidence,
        {"auto_action": "auto_action"},
    )

    # auto_action -> format (always)
    graph.add_conditional_edges(
        "auto_action",
        route_after_auto_action,
        {"format": "format"},
    )

    # format -> END (always)
    graph.add_edge("format", END)

    # ── Compile the graph ────────────────────────────────────────
    compiled = graph.compile()

    logger.info(
        "parwa_graph_built",
        nodes=22,
        frameworks="CLARA+CRP+GSD+CoT+ReAct+ReverseThinking+StepBack+ThoT+5DeepEnrichment",
    )

    return compiled


# ══════════════════════════════════════════════════════════════════
# PIPELINE RUNNER
# ══════════════════════════════════════════════════════════════════


class ParwaPipeline:
    """Pro Parwa pipeline — runs the 15-node LangGraph pipeline.

    Connected Frameworks (Tier 1 + Tier 2):
      - CLARA: Quality gate (enhanced: threshold 85, 5-check + advanced)
      - CRP: Token compression (30-40% reduction)
      - GSD: Conversation state machine tracking
      - Smart Router: Model tier selection (Medium for Pro)
      - Technique Router: Technique selection (Tier 1+2)
      - Confidence Scoring: Response confidence assessment
      - CoT: Chain of Thought (Tier 2 — conditional)
      - ReAct: Reasoning + Acting (Tier 2 — conditional)
      - Reverse Thinking: Inversion reasoning (Tier 2 — conditional)
      - Step-Back: Broader context (Tier 2 — conditional)
      - ThoT: Thread of Thought (Tier 2 — conditional)

    Usage:
        pipeline = ParwaPipeline()
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
            self._graph = build_parwa_graph()
            logger.info("ParwaPipeline initialized with 22 nodes + 6 Tier 1 + 5 Tier 2 frameworks + 5 Enhancement Engines + 5 Deep Enrichment")
        except Exception:
            logger.exception("ParwaPipeline init failed — graph build error")
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
                logger.error("ParwaPipeline graph is None — returning input state")
                return state

            start = time.monotonic()
            result = await self._graph.ainvoke(state)
            total_ms = round((time.monotonic() - start) * 1000, 2)

            # Update total latency
            if isinstance(result, dict):
                result["total_latency_ms"] = total_ms
                result["billing_tokens"] = result.get("generation_tokens", 0)

            logger.info(
                "parwa_pipeline_complete",
                total_latency_ms=total_ms,
                pipeline_status=result.get("pipeline_status", "unknown") if isinstance(result, dict) else "unknown",
                company_id=state.get("company_id", ""),
                quality_score=result.get("quality_score", 0) if isinstance(result, dict) else 0,
                steps_completed=result.get("steps_completed", []) if isinstance(result, dict) else [],
            )

            return result

        except Exception:
            logger.exception("ParwaPipeline.run failed")
            # Return the input state with error info
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
                variant_instance_id = f"inst_pro_{company_id}"

            initial_state = create_initial_state(
                query=query,
                company_id=company_id,
                variant_tier="parwa",
                variant_instance_id=variant_instance_id,
                industry=industry,
                channel=channel,
                conversation_id=conversation_id,
                ticket_id=ticket_id,
                customer_id=customer_id,
                customer_tier=customer_tier,
            )

            result = await self.run(initial_state)

            # Convert TypedDict to regular dict for cleaner output
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
