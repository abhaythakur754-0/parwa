"""
Unified Variant Graph — ONE Graph, ALL Capabilities, Tier-Based Restrictions.

This replaces the 3 SEPARATE variant graphs:
  - mini_parwa/graph.py  (10 nodes — SKIPPED signal extraction, techniques, reasoning)
  - parwa/graph.py       (22 nodes — medium depth)
  - parwa_high/graph.py  (27 nodes — deepest)

With ONE graph that has ALL 27 nodes and ALL variants traverse the
SAME pipeline depth. The ONLY difference is what each variant is
ALLOWED TO DO (controlled by tier_permissions.py).

WHY THIS MATTERS:
  Before: Mini went classify → generate (2 steps, dumb responses)
  After:  Mini goes through FULL 27-node pipeline (same as High)
          but can't EXECUTE refunds/compensation (restricted actions)

  The variant's INTELLIGENCE comes from the depth of reasoning,
  not from which nodes it skips. All variants should be SMART
  (deep reasoning), but RESTRICTED (can't do certain actions).

Graph Topology (ALL variants — 32 nodes):
  START
    → pii_check → empathy_check → emergency_check → gsd_state
    → classify → smart_enrichment → [deep_enrichment_router]
      → complaint_handler | retention_negotiator | billing_resolver
      | tech_diagnostic | shipping_tracker | (skip)
    → extract_signals → technique_select
    → reasoning_chain → context_enrich → context_compress
    → generate → crp_compress → clara_quality_gate
    → self_healing_loop (if quality failed — diagnoses + corrects)
    → quality_retry (if failed, max retries based on tier)
    → maker_llm_validator (LLM-based intelligent validation)
    → loophole_check (scans for 25 loophole categories)
    → confidence_assess → context_health → dedup
    → auto_fix (detect + execute automated fixes, tier-gated)
    → refund_preview_batch (show refunds to customer FIRST, batch process)
    → strategic_decision (if tier allows, else skip)
    → peer_review (if tier allows, else skip)
    → auto_action → format → END

NEW NODES (5):
  28. self_healing_loop — OpenClaw-inspired self-correction loop
  29. maker_llm_validator — LLM-based intelligent response validation
  30. loophole_check — Scans for 25 loophole categories + auto-corrects
  31. auto_fix — Detects and executes automated fixes (tier-gated)
  32. refund_preview_batch — Shows refunds to customer first, batch processes

INTER-NODE COMMUNICATION:
  All nodes now read from and write to the node_comm_bus.
  This fixes the 'nodes not talking to each other' problem.
  - Nodes POST insights/warnings/corrections to the bus
  - Nodes READ messages from previous nodes before processing
  - This makes the pipeline a COLLABORATIVE multi-agent system

KEY DIFFERENCE FROM OLD ARCHITECTURE:
  - Old: Mini skipped nodes → dumber responses
  - New: Mini goes through ALL nodes → smart responses
  - Restrictions are on ACTIONS (refund, compensation), not REASONING

Permission Enforcement Points:
  1. smart_enrichment: Checks if variant CAN do enrichment actions
  2. deep_enrichment: Checks if variant CAN execute deep actions
  3. auto_fix: Checks if variant CAN execute fixes (Mini needs approval)
  4. refund_preview_batch: Checks if variant CAN execute refunds
  5. auto_action: Checks tier_permissions before executing any action
  6. strategic_decision: Only executes if tier has strategic permission
  7. peer_review: Always runs (quality check, not an action)
  8. generate: Injects permission_context into prompt so LLM knows
     what it can/cannot offer
  9. maker_llm_validator: Validates and improves response via LLM
  10. self_healing_loop: Diagnoses quality issues and applies corrections

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
from app.core.variant_engine.tier_permissions import (
    check_permission,
    get_execution_limit,
    get_max_retries,
    get_permissions,
    get_quality_threshold,
    get_restricted_actions,
    build_permission_context,
    needs_approval,
)
from app.logger import get_logger

logger = get_logger("unified_variant_graph")


# ══════════════════════════════════════════════════════════════════
# UNIFIED ROUTING FUNCTIONS
# ══════════════════════════════════════════════════════════════════
# ALL variants go through the SAME routing logic.
# variant_tier only affects WHAT ACTIONS are allowed, not the path.


def route_after_pii(state: ParwaGraphState) -> str:
    """After PII check → always empathy check."""
    return "empathy_check"


def route_after_empathy(state: ParwaGraphState) -> str:
    """After empathy check → always emergency check."""
    return "emergency_check"


def route_after_emergency(state: ParwaGraphState) -> str:
    """After emergency check → gsd_state (always).

    Emergency bypass now goes through gsd_state first (which handles
    the state machine transition), THEN to format if emergency.
    """
    emergency_flag = state.get("emergency_flag", False)
    if emergency_flag:
        return "gsd_state"  # GSD will route to format for emergency
    return "gsd_state"


def route_after_gsd(state: ParwaGraphState) -> str:
    """After GSD state → classify (normal) or format (emergency).

    ALL variants go through classify — even Mini. This is the KEY
    change from the old architecture where Mini skipped classify.
    """
    emergency_flag = state.get("emergency_flag", False)
    step_outputs = state.get("step_outputs", {})
    gsd_output = step_outputs.get("gsd_state", {})

    # Emergency escalation bypasses the pipeline
    if emergency_flag:
        return "format"

    if isinstance(gsd_output, dict) and gsd_output.get("to_state") == "escalate":
        return "format"

    # ALL variants go to classify — no shortcuts
    return "classify"


def route_after_classify(state: ParwaGraphState) -> str:
    """After classify → ALWAYS smart_enrichment.

    KEY CHANGE: Mini used to go classify → generate (skipping
    enrichment, signals, techniques). Now ALL variants go through
    smart_enrichment → extract_signals → technique_select → reasoning.

    This makes Mini JUST AS SMART as Pro/High — the difference
    is only in what ACTIONS it's allowed to take.
    """
    return "smart_enrichment"


# Intent to deep enrichment mapping — SAME for all variants
INTENT_DEEP_ENRICHMENT_MAP = {
    "complaint": "complaint_handler",
    "feedback": "complaint_handler",
    "review": "complaint_handler",
    "dissatisfied": "complaint_handler",
    "unhappy": "complaint_handler",
    "bad_experience": "complaint_handler",
    "cancellation": "retention_negotiator",
    "cancel": "retention_negotiator",
    "unsubscribe": "retention_negotiator",
    "leave": "retention_negotiator",
    "switch": "retention_negotiator",
    "billing": "billing_resolver",
    "payment": "billing_resolver",
    "refund": "billing_resolver",
    "charge": "billing_resolver",
    "invoice": "billing_resolver",
    "overcharge": "billing_resolver",
    "subscription": "billing_resolver",
    "technical": "tech_diagnostic",
    "bug": "tech_diagnostic",
    "error": "tech_diagnostic",
    "not_working": "tech_diagnostic",
    "broken": "tech_diagnostic",
    "crash": "tech_diagnostic",
    "technical_support": "tech_diagnostic",
    "password_reset": "tech_diagnostic",
    "login_issue": "tech_diagnostic",
    "account_access": "tech_diagnostic",
    "shipping": "shipping_tracker",
    "delivery": "shipping_tracker",
    "tracking": "shipping_tracker",
    "order": "shipping_tracker",
    "package": "shipping_tracker",
    "late_delivery": "shipping_tracker",
    "missing_order": "shipping_tracker",
}


def route_after_smart_enrichment(state: ParwaGraphState) -> str:
    """After smart_enrichment → intent-specific deep enrichment OR extract_signals.

    ALL variants go through the SAME routing. Deep enrichment agents
    still run for ALL tiers — they just check tier_permissions before
    EXECUTING any restricted actions.
    """
    classification = state.get("classification", {})
    intent = classification.get("intent", "").lower()

    # Check if intent maps to a deep enrichment node
    deep_node = INTENT_DEEP_ENRICHMENT_MAP.get(intent)
    if deep_node:
        return deep_node

    # Check secondary intents
    secondary_intents = classification.get("secondary_intents", [])
    for sec_intent in secondary_intents:
        deep_node = INTENT_DEEP_ENRICHMENT_MAP.get(sec_intent.lower())
        if deep_node:
            return deep_node

    # No deep enrichment needed → extract signals
    return "extract_signals"


def route_after_deep_enrichment(state: ParwaGraphState) -> str:
    """After deep enrichment → always extract_signals."""
    return "extract_signals"


def route_after_extract_signals(state: ParwaGraphState) -> str:
    """After extract_signals → always technique_select."""
    return "technique_select"


def route_after_technique_select(state: ParwaGraphState) -> str:
    """After technique_select → always reasoning_chain.

    ALL variants do reasoning. This is what makes responses SMART.
    """
    return "reasoning_chain"


def route_after_reasoning(state: ParwaGraphState) -> str:
    """After reasoning_chain → always context_enrich."""
    return "context_enrich"


def route_after_context_enrich(state: ParwaGraphState) -> str:
    """After context_enrich → always context_compress.

    ALL variants compress context — this saves tokens and
    improves response quality regardless of tier.
    """
    return "context_compress"


def route_after_context_compress(state: ParwaGraphState) -> str:
    """After context_compress → always generate."""
    return "generate"


def route_after_generate(state: ParwaGraphState) -> str:
    """After generate → always crp_compress."""
    return "crp_compress"


def route_after_crp(state: ParwaGraphState) -> str:
    """After CRP compress → always CLARA quality gate.

    ALL variants go through quality gate. The threshold differs:
    Mini: 70%, Pro: 80%, High: 90%.
    """
    return "clara_quality_gate"


def route_after_quality_gate(state: ParwaGraphState) -> str:
    """After quality gate → self_healing_loop or maker_llm_validator.

    NEW ARCHITECTURE: Instead of going directly to quality_retry,
    we first go through self_healing_loop which DIAGNOSES what
    went wrong and applies CORRECTIONS to the context.

    Then quality_retry → generate (with improved context).

    If quality passed → skip to maker_llm_validator for LLM-based
    intelligent validation.

    Retry logic is tier-dependent:
    - Mini: max 1 retry
    - Pro: max 2 retries
    - High: max 3 retries

    But ALL variants get at least 1 retry through self-healing.
    """
    variant_tier = state.get("variant_tier", "mini_parwa")
    quality_passed = state.get("quality_passed", True)
    retry_count = state.get("quality_retry_count", 0)
    max_retries = get_max_retries(variant_tier)

    if not quality_passed and retry_count < max_retries:
        return "self_healing_loop"  # Diagnose + correct → then retry

    return "maker_llm_validator"  # Quality OK → LLM validation


def route_after_quality_retry(state: ParwaGraphState) -> str:
    """After quality_retry → back to generate."""
    return "generate"


def route_after_confidence(state: ParwaGraphState) -> str:
    """After confidence_assess → context_health.

    ALL variants go through context_health — it's a quality check,
    not an action.
    """
    return "context_health"


def route_after_context_health(state: ParwaGraphState) -> str:
    """After context_health → dedup."""
    return "dedup"


def route_after_dedup(state: ParwaGraphState) -> str:
    """After dedup → strategic_decision or auto_action.

    Strategic decision is a PERMISSION-GATED action:
    - Mini: NOT allowed → skip to auto_action
    - Pro: NOT allowed → skip to auto_action
    - High: ALLOWED → go through strategic_decision → peer_review

    BUT: Even Mini/Pro benefit from the REASONING about strategy
    (the node runs analysis), they just can't EXECUTE the decision.
    So we route ALL through strategic_decision, which checks
    permissions internally.
    """
    # ALL variants go through strategic_decision
    # The node itself checks permissions and only EXECUTES
    # if allowed — otherwise it just ANALYZES
    return "strategic_decision"


def route_after_strategic_decision(state: ParwaGraphState) -> str:
    """After strategic_decision → peer_review."""
    return "peer_review"


def route_after_peer_review(state: ParwaGraphState) -> str:
    """After peer_review → auto_action."""
    return "auto_action"


def route_after_auto_action(state: ParwaGraphState) -> str:
    """After auto_action → format."""
    return "format"


# ══════════════════════════════════════════════════════════════════
# GRAPH BUILDER
# ══════════════════════════════════════════════════════════════════


def build_unified_variant_graph() -> StateGraph:
    """Build the UNIFIED variant LangGraph StateGraph.

    Creates ONE graph with ALL 32 nodes. ALL variant tiers traverse
    the FULL pipeline. Restrictions are on ACTIONS, not PATH.

    Node Count: 32 (27 original + 5 new: self_healing_loop, maker_llm_validator,
                   loophole_check, auto_fix, refund_preview_batch)

    Returns:
        Compiled LangGraph StateGraph ready for execution.
    """
    # ── Import nodes from parwa_high (superset — has ALL nodes) ──
    from app.core.parwa_high.nodes import (
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
        # Deep enrichment nodes
        complaint_handler_node,
        retention_negotiator_node,
        billing_resolver_node,
        tech_diagnostic_node,
        shipping_tracker_node,
    )
    from app.core.variant_engine.nodes import (
        auto_fix_node,
        refund_preview_batch_node,
        self_healing_loop_node,
        loophole_check_node,
        maker_llm_validator_node,
    )

    graph = StateGraph(ParwaGraphState)

    # ── Add ALL 32 nodes ──────────────────────────────────────────
    # Pre-processing (4 nodes)
    graph.add_node("pii_check", pii_check_node)
    graph.add_node("empathy_check", empathy_check_node)
    graph.add_node("emergency_check", emergency_check_node)
    graph.add_node("gsd_state", gsd_state_node)

    # Classification + Enrichment (8 nodes)
    graph.add_node("classify", classify_node)
    graph.add_node("smart_enrichment", smart_enrichment_node)
    graph.add_node("complaint_handler", complaint_handler_node)
    graph.add_node("retention_negotiator", retention_negotiator_node)
    graph.add_node("billing_resolver", billing_resolver_node)
    graph.add_node("tech_diagnostic", tech_diagnostic_node)
    graph.add_node("shipping_tracker", shipping_tracker_node)
    graph.add_node("extract_signals", extract_signals_node)

    # Reasoning + Context (5 nodes)
    graph.add_node("technique_select", technique_select_node)
    graph.add_node("reasoning_chain", reasoning_chain_node)
    graph.add_node("context_enrich", context_enrich_node)
    graph.add_node("context_compress", context_compress_node)
    graph.add_node("generate", generate_node)

    # Quality + Compression (4 nodes)
    graph.add_node("crp_compress", crp_compress_node)
    graph.add_node("clara_quality_gate", clara_quality_gate_node)
    graph.add_node("quality_retry", quality_retry_node)
    graph.add_node("confidence_assess", confidence_assess_node)

    # NEW: Self-healing + Validation (3 nodes)
    graph.add_node("self_healing_loop", self_healing_loop_node)
    graph.add_node("maker_llm_validator", maker_llm_validator_node)
    graph.add_node("loophole_check", loophole_check_node)

    # High-tier validation (3 nodes)
    graph.add_node("context_health", context_health_node)
    graph.add_node("dedup", dedup_node)
    graph.add_node("strategic_decision", strategic_decision_node)

    # NEW: Action nodes (2 nodes)
    graph.add_node("auto_fix", auto_fix_node)
    graph.add_node("refund_preview_batch", refund_preview_batch_node)

    # Final (3 nodes)
    graph.add_node("peer_review", peer_review_node)
    graph.add_node("auto_action", auto_action_node)
    graph.add_node("format", format_node)

    # ── Set entry point ──────────────────────────────────────────
    graph.set_entry_point("pii_check")

    # ── Wire edges — ALL variants take the SAME path ──────────────

    # Pre-processing
    graph.add_conditional_edges(
        "pii_check", route_after_pii,
        {"empathy_check": "empathy_check"},
    )
    graph.add_conditional_edges(
        "empathy_check", route_after_empathy,
        {"emergency_check": "emergency_check"},
    )
    graph.add_conditional_edges(
        "emergency_check", route_after_emergency,
        {"gsd_state": "gsd_state"},
    )
    graph.add_conditional_edges(
        "gsd_state", route_after_gsd,
        {"classify": "classify", "format": "format"},
    )

    # Classification + Enrichment
    graph.add_conditional_edges(
        "classify", route_after_classify,
        {"smart_enrichment": "smart_enrichment"},
    )
    graph.add_conditional_edges(
        "smart_enrichment", route_after_smart_enrichment,
        {
            "complaint_handler": "complaint_handler",
            "retention_negotiator": "retention_negotiator",
            "billing_resolver": "billing_resolver",
            "tech_diagnostic": "tech_diagnostic",
            "shipping_tracker": "shipping_tracker",
            "extract_signals": "extract_signals",
        },
    )

    # All deep enrichment → extract_signals
    for deep_node in [
        "complaint_handler", "retention_negotiator", "billing_resolver",
        "tech_diagnostic", "shipping_tracker",
    ]:
        graph.add_conditional_edges(
            deep_node, route_after_deep_enrichment,
            {"extract_signals": "extract_signals"},
        )

    # Reasoning + Context
    graph.add_conditional_edges(
        "extract_signals", route_after_extract_signals,
        {"technique_select": "technique_select"},
    )
    graph.add_conditional_edges(
        "technique_select", route_after_technique_select,
        {"reasoning_chain": "reasoning_chain"},
    )
    graph.add_conditional_edges(
        "reasoning_chain", route_after_reasoning,
        {"context_enrich": "context_enrich"},
    )
    graph.add_conditional_edges(
        "context_enrich", route_after_context_enrich,
        {"context_compress": "context_compress"},
    )
    graph.add_conditional_edges(
        "context_compress", route_after_context_compress,
        {"generate": "generate"},
    )

    # Quality + Compression + Self-Healing Loop (NEW ARCHITECTURE)
    # generate → crp_compress → clara_quality_gate
    #   → self_healing_loop (diagnoses + corrects if quality failed)
    #   → quality_retry (back to generate if still failing)
    #   → maker_llm_validator (LLM-based intelligent validation)
    #   → loophole_check (scans for 25 loophole categories)
    #   → confidence_assess
    graph.add_edge("generate", "crp_compress")
    graph.add_edge("crp_compress", "clara_quality_gate")

    # After quality gate: self_healing_loop (diagnoses + applies corrections)
    # then quality_retry if needed, or maker_llm_validator if passed
    graph.add_conditional_edges(
        "clara_quality_gate", route_after_quality_gate,
        {
            "self_healing_loop": "self_healing_loop",
            "maker_llm_validator": "maker_llm_validator",
        },
    )

    # Self-healing loop → quality_retry (back to generate)
    graph.add_conditional_edges(
        "self_healing_loop", route_after_quality_retry,
        {"generate": "generate"},
    )

    # Maker LLM validator → loophole check
    graph.add_conditional_edges(
        "maker_llm_validator", route_after_reasoning,  # Always → loophole_check
        {"loophole_check": "loophole_check"},
    )

    # Loophole check → confidence assess
    graph.add_conditional_edges(
        "loophole_check", route_after_confidence,
        {"confidence_assess": "confidence_assess"},
    )

    # Confidence assess → context health
    graph.add_conditional_edges(
        "confidence_assess", route_after_confidence,
        {"context_health": "context_health"},
    )
    graph.add_conditional_edges(
        "context_health", route_after_context_health,
        {"dedup": "dedup"},
    )

    # Dedup → auto_fix → refund_preview_batch → strategic_decision
    graph.add_conditional_edges(
        "dedup", route_after_dedup,
        {"auto_fix": "auto_fix"},
    )
    graph.add_conditional_edges(
        "auto_fix", route_after_auto_action,
        {"refund_preview_batch": "refund_preview_batch"},
    )
    graph.add_conditional_edges(
        "refund_preview_batch", route_after_strategic_decision,
        {"strategic_decision": "strategic_decision"},
    )
    graph.add_conditional_edges(
        "strategic_decision", route_after_strategic_decision,
        {"peer_review": "peer_review"},
    )

    # Final
    graph.add_conditional_edges(
        "peer_review", route_after_peer_review,
        {"auto_action": "auto_action"},
    )
    graph.add_conditional_edges(
        "auto_action", route_after_auto_action,
        {"format": "format"},
    )
    graph.add_edge("format", END)

    # ── Compile ──────────────────────────────────────────────────
    compiled = graph.compile()

    logger.info(
        "unified_variant_graph_built: nodes=32, "
        "philosophy=same_capability_different_restrictions, "
        "all_tiers_traverse_full_pipeline, "
        "new_nodes=self_healing_loop+maker_llm_validator+loophole_check+auto_fix+refund_preview_batch, "
        "comm_bus=enabled",
    )

    return compiled


# ══════════════════════════════════════════════════════════════════
# PIPELINE RUNNER
# ══════════════════════════════════════════════════════════════════


# Singleton graph instance
_graph_instance: Optional[Any] = None


class UnifiedVariantPipeline:
    """Unified variant pipeline — ALL tiers go through the SAME 27-node graph.

    This replaces MiniParwaPipeline, ParwaPipeline, and ParwaHighPipeline
    with a SINGLE pipeline that treats all variants equally in terms
    of intelligence, but differently in terms of authorization.

    Usage:
        pipeline = UnifiedVariantPipeline()
        result = await pipeline.run(initial_state)
        # OR
        result = await pipeline.process_ticket(
            query="I need a refund",
            company_id="comp_123",
            variant_tier="mini_parwa",  # Same graph, different restrictions
        )

    Key Insight:
        The variant_tier field in state controls WHAT the variant can DO,
        not HOW it thinks. Mini goes through the same deep reasoning as High,
        but can't execute refunds, compensation, or strategic decisions.
    """

    def __init__(self) -> None:
        """Initialize the pipeline by building the unified graph."""
        try:
            self._graph = build_unified_variant_graph()
            logger.info(
                "UnifiedVariantPipeline initialized: 32 nodes, "
                "all tiers traverse full pipeline, "
                "self-healing+maker_llm+loophole+auto_fix+refund_preview enabled",
            )
        except Exception:
            logger.exception(
                "UnifiedVariantPipeline init failed — graph build error",
            )
            self._graph = None

    async def run(self, state: ParwaGraphState) -> ParwaGraphState:
        """Invoke the unified variant pipeline with the given state.

        Before running, injects the permission context into state
        so all nodes know what the current tier is allowed to do.

        Args:
            state: Initial ParwaGraphState to process.

        Returns:
            Final ParwaGraphState after pipeline execution.
        """
        try:
            if self._graph is None:
                logger.error(
                    "UnifiedVariantPipeline graph is None — returning input state",
                )
                return state

            # ── INJECT PERMISSION CONTEXT ──────────────────────────
            # This is the KEY step — inject what the variant CAN/CANNOT do
            # into the state so nodes can check permissions.
            variant_tier = state.get("variant_tier", "mini_parwa")

            permission_context = build_permission_context(variant_tier)
            state["permission_context"] = permission_context

            # Also inject quality threshold and max retries from permissions
            state["quality_threshold"] = get_quality_threshold(variant_tier)
            state["max_quality_retries"] = get_max_retries(variant_tier)
            state["restricted_actions"] = get_restricted_actions(variant_tier)

            logger.info(
                "unified_pipeline_start: tier=%s, restricted_actions=%s, "
                "quality_threshold=%.2f, max_retries=%d",
                variant_tier,
                permission_context.get("restricted_actions", []),
                permission_context.get("key_limits", {}).get("quality_threshold", 0.7),
                permission_context.get("key_limits", {}).get("max_retries", 1),
            )

            # ── RUN THE GRAPH ─────────────────────────────────────
            start = time.monotonic()
            result = await self._graph.ainvoke(state)
            total_ms = round((time.monotonic() - start) * 1000, 2)

            if isinstance(result, dict):
                result["total_latency_ms"] = total_ms
                result["billing_tokens"] = result.get("generation_tokens", 0)

            logger.info(
                "unified_pipeline_complete: tier=%s, ms=%.1f, "
                "status=%s, quality=%.2f, steps=%s",
                variant_tier,
                total_ms,
                result.get("pipeline_status", "unknown") if isinstance(result, dict) else "unknown",
                result.get("quality_score", 0) if isinstance(result, dict) else 0,
                result.get("steps_completed", []) if isinstance(result, dict) else [],
            )

            return result

        except Exception:
            logger.exception("UnifiedVariantPipeline.run failed")
            state["pipeline_status"] = "failed"
            state["errors"] = state.get("errors", []) + ["pipeline_execution_failed"]
            return state

    async def process_ticket(
        self,
        query: str,
        company_id: str,
        variant_tier: str = "mini_parwa",
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
            variant_tier: 'mini_parwa' | 'parwa' | 'parwa_high'.
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
                variant_instance_id = f"inst_{variant_tier}_{company_id}"

            initial_state = create_initial_state(
                query=query,
                company_id=company_id,
                variant_tier=variant_tier,
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


def get_unified_graph() -> Any:
    """Get or create the singleton unified variant graph.

    Returns:
        Compiled LangGraph StateGraph.
    """
    global _graph_instance

    if _graph_instance is not None:
        return _graph_instance

    try:
        _graph_instance = build_unified_variant_graph()
        return _graph_instance
    except Exception:
        logger.exception("get_unified_graph_error")
        return None
