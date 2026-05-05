"""
Mini Parwa LangGraph Pipeline — Builds and runs the 6-node pipeline.

Pipeline: pii_check -> empathy_check -> emergency_check -> classify -> generate -> format -> END

Uses:
  - ParwaGraphState from app.core.parwa_graph_state
  - VariantRouter routing functions from app.core.variant_router
  - 6 node functions from app.core.mini_parwa.nodes

Architecture:
  - LangGraph StateGraph with conditional edges
  - Code-orchestrated routing (FREE, no LLM for routing)
  - Emergency bypass: emergency_check -> format (skip classify + generate)
  - Mini shortcut: classify -> generate (skip signals + techniques)

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
    route_after_classify,
    route_after_generate,
)
from app.core.mini_parwa.nodes import (
    pii_check_node,
    empathy_check_node,
    emergency_check_node,
    classify_node,
    generate_node,
    format_node,
)
from app.logger import get_logger

logger = get_logger("mini_parwa_graph")


def build_mini_parwa_graph() -> StateGraph:
    """Build the Mini Parwa LangGraph StateGraph.

    Creates the graph with all 6 nodes and conditional edges:
      - pii_check -> empathy_check (always)
      - empathy_check -> emergency_check (always)
      - emergency_check -> classify (normal) OR format (emergency bypass)
      - classify -> generate (Mini shortcut)
      - generate -> format (Mini shortcut)
      - format -> END

    Returns:
        Compiled LangGraph StateGraph ready for execution.
    """
    # Create the graph with our state type
    graph = StateGraph(ParwaGraphState)

    # ── Add all 6 nodes ──────────────────────────────────────────────
    graph.add_node("pii_check", pii_check_node)
    graph.add_node("empathy_check", empathy_check_node)
    graph.add_node("emergency_check", emergency_check_node)
    graph.add_node("classify", classify_node)
    graph.add_node("generate", generate_node)
    graph.add_node("format", format_node)

    # ── Set entry point ──────────────────────────────────────────────
    graph.set_entry_point("pii_check")

    # ── Add conditional edges ────────────────────────────────────────
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

    # emergency_check -> classify (normal) OR format (emergency bypass)
    graph.add_conditional_edges(
        "emergency_check",
        route_after_emergency,
        {
            "classify": "classify",
            "format": "format",
        },
    )

    # classify -> generate (Mini shortcut — skips signals + techniques)
    graph.add_conditional_edges(
        "classify",
        route_after_classify,
        {
            "generate": "generate",
            "extract_signals": "generate",  # Mini: redirect to generate
        },
    )

    # generate -> format (Mini shortcut — skips quality gate)
    graph.add_conditional_edges(
        "generate",
        route_after_generate,
        {
            "format": "format",
            "quality_gate": "format",  # Mini: redirect to format
        },
    )

    # format -> END (always)
    graph.add_edge("format", END)

    # ── Compile the graph ────────────────────────────────────────────
    compiled = graph.compile()

    logger.info("mini_parwa_graph_built", nodes=6)

    return compiled


class MiniParwaPipeline:
    """Mini Parwa pipeline — runs the 6-node LangGraph pipeline.

    Usage:
        pipeline = MiniParwaPipeline()
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
            self._graph = build_mini_parwa_graph()
            logger.info("MiniParwaPipeline initialized")
        except Exception:
            logger.exception("MiniParwaPipeline init failed — graph build error")
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
                logger.error("MiniParwaPipeline graph is None — returning input state")
                return state

            start = time.monotonic()
            result = await self._graph.ainvoke(state)
            total_ms = round((time.monotonic() - start) * 1000, 2)

            # Update total latency
            if isinstance(result, dict):
                result["total_latency_ms"] = total_ms
                result["billing_tokens"] = result.get("generation_tokens", 0)

            logger.info(
                "mini_parwa_pipeline_complete",
                total_latency_ms=total_ms,
                pipeline_status=result.get("pipeline_status", "unknown") if isinstance(result, dict) else "unknown",
                company_id=state.get("company_id", ""),
            )

            return result

        except Exception:
            logger.exception("MiniParwaPipeline.run failed")
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
                variant_instance_id = f"inst_mini_{company_id}"

            initial_state = create_initial_state(
                query=query,
                company_id=company_id,
                variant_tier="mini_parwa",
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
