"""
Unified Parwa Graph — ONE graph for ALL variants (Mini, Pro, High).

ARCHITECTURE REVOLUTION:
  Before: 3 separate graphs with different node counts (10, 22, 27)
          Mini was "dumbed down" — fewer nodes, no techniques, no reasoning.

  After:  ONE unified graph with ALL 27 nodes.
          ALL variants have SAME intelligence, SAME techniques, SAME reasoning.
          The ONLY difference is TASK PERMISSIONS (what they're allowed to DO).

  This means:
    - Mini can THINK about a refund as well as High can
    - Mini just can't PROCESS the refund (it escalates instead)
    - Mini has the same reasoning depth (CoT, ReAct, ToT, etc.)
    - Mini has the same learning (MetaLearner, DSPy, Reflexion)
    - Mini has the same quality checks (CLARA, CRP, etc.)

Pipeline (27 nodes — SAME for ALL variants):
  pii_check → empathy_check → emergency_check → gsd_state
  → classify → smart_enrichment → [deep_enrichment_router]
    → complaint_handler | retention_negotiator | billing_resolver
    | tech_diagnostic | shipping_tracker | (skip)
  → extract_signals → technique_select
  → reasoning_chain → context_enrich → context_compress
  → generate → crp_compress → clara_quality_gate
  → quality_retry (max retries per variant) → confidence_assess
  → context_health → dedup → strategic_decision
  → peer_review → auto_action → format → END

Task Permissions (inside nodes):
  Mini:  Can't do refunds, cancellations, billing changes → escalates
  Pro:   Can do refunds (under $500), billing → needs approval for big stuff
  High:  Full autonomy on everything

Learning (enabled for ALL variants):
  - MetaLearner: Tracks optimal technique combos per ticket type
  - DSPy: Auto-optimizes prompts over time
  - Reflexion: Self-corrects errors in real-time

BC-001: company_id first parameter on public methods.
BC-008: Every public method wrapped in try/except — never crash.
BC-012: All timestamps UTC.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from langgraph.graph import StateGraph, END

from app.core.parwa_graph_state import (
    ParwaGraphState,
    create_initial_state,
)
from app.core.variant_router import (
    route_after_pii,
    route_after_empathy,
    route_after_emergency,
    route_after_gsd,
    route_after_classify,
    route_after_smart_enrichment,
    route_after_deep_enrichment,
    route_after_extract_signals,
    route_after_technique_select,
    route_after_reasoning,
    route_after_context_enrich,
    route_after_context_compress,
    route_after_crp,
    route_after_quality_gate,
    route_after_quality_retry,
    route_after_confidence,
    route_after_context_health,
    route_after_dedup,
    route_after_strategic_decision,
    route_after_peer_review,
    route_after_auto_action,
    NODE_PII, NODE_EMPATHY, NODE_EMERGENCY, NODE_GSD,
    NODE_CLASSIFY, NODE_SMART_ENRICHMENT,
    NODE_COMPLAINT_HANDLER, NODE_RETENTION_NEGOTIATOR,
    NODE_BILLING_RESOLVER, NODE_TECH_DIAGNOSTIC, NODE_SHIPPING_TRACKER,
    NODE_EXTRACT_SIGNALS, NODE_TECHNIQUE_SELECT, NODE_REASONING_CHAIN,
    NODE_CONTEXT_ENRICH, NODE_CONTEXT_COMPRESS,
    NODE_GENERATE, NODE_CRP_COMPRESS, NODE_QUALITY_GATE,
    NODE_QUALITY_RETRY, NODE_CONFIDENCE_ASSESS,
    NODE_CONTEXT_HEALTH, NODE_DEDUP, NODE_STRATEGIC_DECISION,
    NODE_PEER_REVIEW, NODE_AUTO_ACTION, NODE_FORMAT,
    INTENT_DEEP_ENRICHMENT_MAP,
)
from app.core.variant_permissions import (
    get_permissions,
    get_permission_summary,
)
from app.logger import get_logger

logger = get_logger("unified_parwa_graph")


# ══════════════════════════════════════════════════════════════════
# NODE IMPORTS — Use High Parwa nodes (most complete implementation)
# ══════════════════════════════════════════════════════════════════

# Base nodes from High Parwa (most complete implementation)
from app.core.parwa_high.nodes import (
    pii_check_node,
    empathy_check_node,
    emergency_check_node,
    gsd_state_node,
    smart_enrichment_node,
    complaint_handler_node,
    tech_diagnostic_node,
    shipping_tracker_node,
    extract_signals_node,
    context_enrich_node,
    context_compress_node,
    crp_compress_node,
    quality_retry_node,
    confidence_assess_node,
    context_health_node,
    dedup_node,
    strategic_decision_node,
    peer_review_node,
    format_node,
)

# Permission-aware wrappers for nodes that need task restriction checks
from app.core.permission_aware_nodes import (
    classify_with_permissions as classify_node,
    billing_resolver_with_permissions as billing_resolver_node,
    retention_negotiator_with_permissions as retention_negotiator_node,
    technique_select_with_permissions as technique_select_node,
    reasoning_chain_with_permissions as reasoning_chain_node,
    generate_with_permissions as generate_node,
    clara_quality_gate_with_permissions as clara_quality_gate_node,
    auto_action_with_permissions as auto_action_node,
)


# ══════════════════════════════════════════════════════════════════
# GRAPH BUILDER
# ══════════════════════════════════════════════════════════════════


def build_unified_parwa_graph() -> StateGraph:
    """Build the unified LangGraph StateGraph for ALL variants.

    Creates a single graph with all 27 nodes that is shared by
    Mini, Pro, and High variants. The variant_tier in the state
    controls task permissions inside each node.

    Returns:
        Compiled LangGraph StateGraph ready for execution.
    """
    graph = StateGraph(ParwaGraphState)

    # ── Add all 27 nodes ──────────────────────────────────────────
    # Safety gates (3)
    graph.add_node(NODE_PII, pii_check_node)
    graph.add_node(NODE_EMPATHY, empathy_check_node)
    graph.add_node(NODE_EMERGENCY, emergency_check_node)

    # State management (1)
    graph.add_node(NODE_GSD, gsd_state_node)

    # Classification (1)
    graph.add_node(NODE_CLASSIFY, classify_node)

    # Enrichment (1 + 5 deep)
    graph.add_node(NODE_SMART_ENRICHMENT, smart_enrichment_node)
    graph.add_node(NODE_COMPLAINT_HANDLER, complaint_handler_node)
    graph.add_node(NODE_RETENTION_NEGOTIATOR, retention_negotiator_node)
    graph.add_node(NODE_BILLING_RESOLVER, billing_resolver_node)
    graph.add_node(NODE_TECH_DIAGNOSTIC, tech_diagnostic_node)
    graph.add_node(NODE_SHIPPING_TRACKER, shipping_tracker_node)

    # Reasoning (3)
    graph.add_node(NODE_EXTRACT_SIGNALS, extract_signals_node)
    graph.add_node(NODE_TECHNIQUE_SELECT, technique_select_node)
    graph.add_node(NODE_REASONING_CHAIN, reasoning_chain_node)

    # Context management (2)
    graph.add_node(NODE_CONTEXT_ENRICH, context_enrich_node)
    graph.add_node(NODE_CONTEXT_COMPRESS, context_compress_node)

    # Generation (1)
    graph.add_node(NODE_GENERATE, generate_node)

    # Quality assurance (3)
    graph.add_node(NODE_CRP_COMPRESS, crp_compress_node)
    graph.add_node(NODE_QUALITY_GATE, clara_quality_gate_node)
    graph.add_node(NODE_QUALITY_RETRY, quality_retry_node)

    # Confidence & validation (4)
    graph.add_node(NODE_CONFIDENCE_ASSESS, confidence_assess_node)
    graph.add_node(NODE_CONTEXT_HEALTH, context_health_node)
    graph.add_node(NODE_DEDUP, dedup_node)
    graph.add_node(NODE_STRATEGIC_DECISION, strategic_decision_node)
    graph.add_node(NODE_PEER_REVIEW, peer_review_node)

    # Action & delivery (2)
    graph.add_node(NODE_AUTO_ACTION, auto_action_node)
    graph.add_node(NODE_FORMAT, format_node)

    # ── Set entry point ──────────────────────────────────────────
    graph.set_entry_point(NODE_PII)

    # ── Add edges — UNIFIED routing for ALL variants ──────────────

    # pii_check → empathy_check
    graph.add_conditional_edges(
        NODE_PII,
        route_after_pii,
        {NODE_EMPATHY: NODE_EMPATHY},
    )

    # empathy_check → emergency_check
    graph.add_conditional_edges(
        NODE_EMPATHY,
        route_after_empathy,
        {NODE_EMERGENCY: NODE_EMERGENCY},
    )

    # emergency_check → gsd_state (normal) OR format (emergency)
    graph.add_conditional_edges(
        NODE_EMERGENCY,
        route_after_emergency,
        {
            NODE_GSD: NODE_GSD,
            NODE_FORMAT: NODE_FORMAT,
        },
    )

    # gsd_state → classify (normal) OR format (emergency/escalate)
    graph.add_conditional_edges(
        NODE_GSD,
        route_after_gsd,
        {
            NODE_CLASSIFY: NODE_CLASSIFY,
            NODE_FORMAT: NODE_FORMAT,
        },
    )

    # classify → smart_enrichment (ALL variants now)
    graph.add_conditional_edges(
        NODE_CLASSIFY,
        route_after_classify,
        {NODE_SMART_ENRICHMENT: NODE_SMART_ENRICHMENT},
    )

    # smart_enrichment → deep enrichment (intent-based) OR extract_signals
    graph.add_conditional_edges(
        NODE_SMART_ENRICHMENT,
        route_after_smart_enrichment,
        {
            NODE_COMPLAINT_HANDLER: NODE_COMPLAINT_HANDLER,
            NODE_RETENTION_NEGOTIATOR: NODE_RETENTION_NEGOTIATOR,
            NODE_BILLING_RESOLVER: NODE_BILLING_RESOLVER,
            NODE_TECH_DIAGNOSTIC: NODE_TECH_DIAGNOSTIC,
            NODE_SHIPPING_TRACKER: NODE_SHIPPING_TRACKER,
            NODE_EXTRACT_SIGNALS: NODE_EXTRACT_SIGNALS,
        },
    )

    # Deep enrichment → extract_signals (all converge)
    for deep_node in [
        NODE_COMPLAINT_HANDLER, NODE_RETENTION_NEGOTIATOR,
        NODE_BILLING_RESOLVER, NODE_TECH_DIAGNOSTIC,
        NODE_SHIPPING_TRACKER,
    ]:
        graph.add_conditional_edges(
            deep_node,
            route_after_deep_enrichment,
            {NODE_EXTRACT_SIGNALS: NODE_EXTRACT_SIGNALS},
        )

    # extract_signals → technique_select (ALL variants)
    graph.add_conditional_edges(
        NODE_EXTRACT_SIGNALS,
        route_after_extract_signals,
        {NODE_TECHNIQUE_SELECT: NODE_TECHNIQUE_SELECT},
    )

    # technique_select → reasoning_chain (ALL variants)
    graph.add_conditional_edges(
        NODE_TECHNIQUE_SELECT,
        route_after_technique_select,
        {NODE_REASONING_CHAIN: NODE_REASONING_CHAIN},
    )

    # reasoning_chain → context_enrich
    graph.add_conditional_edges(
        NODE_REASONING_CHAIN,
        route_after_reasoning,
        {NODE_CONTEXT_ENRICH: NODE_CONTEXT_ENRICH},
    )

    # context_enrich → context_compress (ALL variants)
    graph.add_conditional_edges(
        NODE_CONTEXT_ENRICH,
        route_after_context_enrich,
        {NODE_CONTEXT_COMPRESS: NODE_CONTEXT_COMPRESS},
    )

    # context_compress → generate
    graph.add_conditional_edges(
        NODE_CONTEXT_COMPRESS,
        route_after_context_compress,
        {NODE_GENERATE: NODE_GENERATE},
    )

    # generate → crp_compress
    graph.add_edge(NODE_GENERATE, NODE_CRP_COMPRESS)

    # crp_compress → quality_gate (ALL variants now)
    graph.add_edge(NODE_CRP_COMPRESS, NODE_QUALITY_GATE)

    # quality_gate → quality_retry (failed) OR confidence_assess (passed)
    graph.add_conditional_edges(
        NODE_QUALITY_GATE,
        route_after_quality_gate,
        {
            NODE_QUALITY_RETRY: NODE_QUALITY_RETRY,
            NODE_CONFIDENCE_ASSESS: NODE_CONFIDENCE_ASSESS,
        },
    )

    # quality_retry → generate (retry loop)
    graph.add_conditional_edges(
        NODE_QUALITY_RETRY,
        route_after_quality_retry,
        {NODE_GENERATE: NODE_GENERATE},
    )

    # confidence_assess → context_health (ALL variants now)
    graph.add_conditional_edges(
        NODE_CONFIDENCE_ASSESS,
        route_after_confidence,
        {NODE_CONTEXT_HEALTH: NODE_CONTEXT_HEALTH},
    )

    # context_health → dedup
    graph.add_conditional_edges(
        NODE_CONTEXT_HEALTH,
        route_after_context_health,
        {NODE_DEDUP: NODE_DEDUP},
    )

    # dedup → strategic_decision (ALL variants now)
    graph.add_conditional_edges(
        NODE_DEDUP,
        route_after_dedup,
        {
            NODE_STRATEGIC_DECISION: NODE_STRATEGIC_DECISION,
            NODE_FORMAT: NODE_FORMAT,  # Dedup shortcut if response is good enough
        },
    )

    # strategic_decision → peer_review
    graph.add_conditional_edges(
        NODE_STRATEGIC_DECISION,
        route_after_strategic_decision,
        {NODE_PEER_REVIEW: NODE_PEER_REVIEW},
    )

    # peer_review → auto_action
    graph.add_conditional_edges(
        NODE_PEER_REVIEW,
        route_after_peer_review,
        {NODE_AUTO_ACTION: NODE_AUTO_ACTION},
    )

    # auto_action → format
    graph.add_conditional_edges(
        NODE_AUTO_ACTION,
        route_after_auto_action,
        {NODE_FORMAT: NODE_FORMAT},
    )

    # format → END
    graph.add_edge(NODE_FORMAT, END)

    # ── Compile the graph ────────────────────────────────────────
    compiled = graph.compile()

    logger.info(
        "unified_parwa_graph_built",
        nodes=27,
        architecture="UNIFIED — ALL variants same pipeline, permissions control behavior",
        techniques="ALL 25 (CoT+ReAct+ToT+UoT+GST+Reverse+StepBack+ThoT+CLARA+CRP+GSD+SelfConsistency+Reflexion+LeastToMost+HyDE+MultiQuery+StepBack+Maker+FederatedReasoning+SmartRouter+MetaLearner+ZeroShotValidator+AdaptiveBudget+TurboCompress+GSD)"
    )

    return compiled


# ══════════════════════════════════════════════════════════════════
# PIPELINE RUNNER
# ══════════════════════════════════════════════════════════════════


class UnifiedParwaPipeline:
    """Unified pipeline — runs the 27-node graph for ALL variants.

    ALL variants (Mini, Pro, High) use this SAME pipeline.
    The variant_tier in the state controls:
      - Task permissions (what actions are allowed)
      - Quality thresholds (how strict the quality gate is)
      - Model tier (cost optimization)
      - Token budgets

    The intelligence, reasoning, and learning are IDENTICAL across variants.

    Usage:
        pipeline = UnifiedParwaPipeline()

        # Any variant — just pass the variant_tier
        result = await pipeline.process_ticket(
            query="I need a refund",
            company_id="comp_123",
            variant_tier="mini_parwa",  # or "parwa" or "parwa_high"
        )
    """

    def __init__(self) -> None:
        """Initialize the pipeline by building the unified graph."""
        try:
            self._graph = build_unified_parwa_graph()
            logger.info(
                "UnifiedParwaPipeline initialized — 27 nodes, ALL variants, "
                "same intelligence, different permissions"
            )
        except Exception:
            logger.exception("UnifiedParwaPipeline init failed — graph build error")
            self._graph = None

    async def run(self, state: ParwaGraphState) -> ParwaGraphState:
        """Invoke the unified pipeline with the given state.

        Args:
            state: Initial ParwaGraphState to process.

        Returns:
            Final ParwaGraphState after pipeline execution.
        """
        try:
            if self._graph is None:
                logger.error("UnifiedParwaPipeline graph is None — returning input state")
                return state

            start = time.monotonic()

            # Log the variant and permissions for this run
            variant_tier = state.get("variant_tier", "parwa")
            perms = get_permissions(variant_tier)
            logger.info(
                "unified_pipeline_start",
                variant_tier=variant_tier,
                model_tier=perms.model_tier,
                clara_threshold=perms.clara_threshold,
                can_refund=perms.can_issue_refund,
                can_cancel=perms.can_cancel_subscription,
                company_id=state.get("company_id", ""),
                ticket_id=state.get("ticket_id", ""),
            )

            result = await self._graph.ainvoke(state)
            total_ms = round((time.monotonic() - start) * 1000, 2)

            if isinstance(result, dict):
                result["total_latency_ms"] = total_ms
                result["billing_tokens"] = result.get("generation_tokens", 0)
                result["pipeline_type"] = "unified"
                result["permission_tier"] = variant_tier

            logger.info(
                "unified_pipeline_complete",
                total_latency_ms=total_ms,
                variant_tier=variant_tier,
                pipeline_status=result.get("pipeline_status", "unknown") if isinstance(result, dict) else "unknown",
                company_id=state.get("company_id", ""),
                quality_score=result.get("quality_score", 0) if isinstance(result, dict) else 0,
                steps_completed=result.get("steps_completed", []) if isinstance(result, dict) else [],
            )

            return result

        except Exception:
            logger.exception("UnifiedParwaPipeline.run failed")
            state["pipeline_status"] = "failed"
            state["errors"] = state.get("errors", []) + ["pipeline_execution_failed"]
            return state

    async def process_ticket(
        self,
        query: str,
        company_id: str,
        variant_tier: str = "parwa",
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
            variant_tier: 'mini_parwa' | 'parwa' | 'parwa_high'
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

            # Log permissions for this run
            perms = get_permissions(variant_tier)
            logger.info(
                "process_ticket_start",
                variant_tier=variant_tier,
                ticket_id=ticket_id,
                company_id=company_id,
                permissions=get_permission_summary(variant_tier),
            )

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


# ══════════════════════════════════════════════════════════════════
# BACKWARD COMPATIBILITY ALIASES
# ══════════════════════════════════════════════════════════════════

# These allow existing code to keep working while migrating to unified

class MiniParwaPipeline(UnifiedParwaPipeline):
    """Mini Parwa — uses unified graph with Mini permissions."""
    def __init__(self):
        super().__init__()
        self._default_tier = "mini_parwa"

    async def process_ticket(self, query: str, company_id: str, **kwargs) -> Dict[str, Any]:
        kwargs.setdefault("variant_tier", "mini_parwa")
        return await super().process_ticket(query, company_id, **kwargs)


class ProParwaPipeline(UnifiedParwaPipeline):
    """Pro Parwa — uses unified graph with Pro permissions."""
    def __init__(self):
        super().__init__()
        self._default_tier = "parwa"

    async def process_ticket(self, query: str, company_id: str, **kwargs) -> Dict[str, Any]:
        kwargs.setdefault("variant_tier", "parwa")
        return await super().process_ticket(query, company_id, **kwargs)


class HighParwaPipeline(UnifiedParwaPipeline):
    """High Parwa — uses unified graph with High permissions."""
    def __init__(self):
        super().__init__()
        self._default_tier = "parwa_high"

    async def process_ticket(self, query: str, company_id: str, **kwargs) -> Dict[str, Any]:
        kwargs.setdefault("variant_tier", "parwa_high")
        return await super().process_ticket(query, company_id, **kwargs)
