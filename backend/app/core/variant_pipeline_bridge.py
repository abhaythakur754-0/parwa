"""
Variant Pipeline Bridge — V2 Unified PARWA Pipeline

Routes ALL messages through the SINGLE 8-node PARWA pipeline.
Replaces the old multi-variant system (mini_parwa 10-node, parwa 15-node,
parwa_high 27-node) with one unified pipeline where Node 2 (Smart Route)
handles tier-based complexity routing internally.

Architecture:
  jarvis_service.send_message()
       ├─ (onboarding + variant_tier set)
       │    → variant_pipeline_bridge.process_onboarding_message()
       │         → 8-node PARWA pipeline (variant_tier in state)
       │
       ├─ (onboarding + no variant_tier)
       │    → _call_ai_provider() (direct AI, legacy)
       │
       └─ (customer_care)
            → variant_pipeline_bridge.process_customer_care_message()
                 → 8-node PARWA pipeline (variant_tier in state)

Pipeline (8 nodes, same for all tiers):
  Node 1 (Ingest+Classify) → Node 2 (Smart Route)
    ├── simple_path  → Node 3 (Knowledge) → Node 7 (Simple Resolver)
    │                     ├── PASS → finalize_simple → END
    │                     └── auto_upgraded → Node 4 path
    └── complex_path → Node 3 (Knowledge) → Node 4 (Reasoning)
                                                  → Node 5 (Act+Verify)
                                                  → Node 6 (Quality)
                                                    ├── PASS → wiki_finalize → END
                                                    ├── FAIL + loops < 2 → Node 4 (loop)
                                                    └── FAIL + loops >= 2 → Node 8 (Super Node)
                                                                          → END

Tier differences are handled INSIDE Node 2:
  - mini_parwa: more queries routed to simple_path, tighter budgets
  - parwa: balanced routing, standard budgets
  - parwa_high: more queries routed to complex_path, higher budgets

BC-001: company_id first parameter on public methods.
BC-008: Every public method wrapped in try/except — never crash.
BC-012: All timestamps UTC.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.variant_tier_mapper import (
    resolve_tier_from_context,
    resolve_industry_from_context,
    get_tier_metadata,
)
from app.core.parwa_pipeline.state_v2 import PipelineV2State
from app.logger import get_logger

logger = get_logger("variant_pipeline_bridge")


# ══════════════════════════════════════════════════════════════════
# PIPELINE SINGLETON (lazy-initialized)
# ══════════════════════════════════════════════════════════════════

_parwa_pipeline_graph = None


def _get_parwa_pipeline_graph():
    """Get or create the unified 8-node PARWA pipeline singleton."""
    global _parwa_pipeline_graph
    if _parwa_pipeline_graph is None:
        try:
            from app.core.parwa_pipeline.graph_v2 import build_parwa_pipeline
            graph = build_parwa_pipeline()
            _parwa_pipeline_graph = graph.compile()
            logger.info("Unified 8-node PARWA pipeline compiled and ready")
        except Exception:
            logger.exception("Failed to build/compile PARWA pipeline")
    return _parwa_pipeline_graph


# ══════════════════════════════════════════════════════════════════
# PIPELINE RESULT
# ══════════════════════════════════════════════════════════════════


class PipelineResult:
    """Result from processing a message through the PARWA pipeline.

    This class is preserved for backward compatibility — all downstream
    consumers (jarvis_service, jarvis_orchestrator, jarvis_cc_service,
    API routes) depend on this interface.
    """

    def __init__(
        self,
        response_text: str,
        variant_tier: str,
        industry: str,
        pipeline_status: str = "completed",
        quality_score: float = 0.0,
        total_latency_ms: float = 0.0,
        billing_tokens: int = 0,
        steps_completed: Optional[List[str]] = None,
        technique_used: str = "",
        emergency_flag: bool = False,
        empathy_score: float = 0.5,
        classification_intent: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.response_text = response_text
        self.variant_tier = variant_tier
        self.industry = industry
        self.pipeline_status = pipeline_status
        self.quality_score = quality_score
        self.total_latency_ms = total_latency_ms
        self.billing_tokens = billing_tokens
        self.steps_completed = steps_completed or []
        self.technique_used = technique_used
        self.emergency_flag = emergency_flag
        self.empathy_score = empathy_score
        self.classification_intent = classification_intent
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for logging/metadata."""
        return {
            "variant_tier": self.variant_tier,
            "industry": self.industry,
            "pipeline_status": self.pipeline_status,
            "quality_score": self.quality_score,
            "total_latency_ms": self.total_latency_ms,
            "billing_tokens": self.billing_tokens,
            "steps_completed": self.steps_completed,
            "technique_used": self.technique_used,
            "emergency_flag": self.emergency_flag,
            "empathy_score": self.empathy_score,
            "classification_intent": self.classification_intent,
        }


# ══════════════════════════════════════════════════════════════════
# CUSTOMER CARE ENTRY POINT
# ══════════════════════════════════════════════════════════════════


async def process_customer_care_message(
    query: str,
    company_id: str,
    session_context: Dict[str, Any],
    conversation_id: str = "",
    ticket_id: str = "",
    channel: str = "chat",
    customer_id: str = "",
    customer_tier: str = "free",
) -> PipelineResult:
    """Process a customer care message through the 8-node PARWA pipeline.

    This is the entry point called by jarvis_service when handling
    customer_care type sessions.

    Flow:
      1. Resolve variant_tier from session context
      2. Resolve industry from session context
      3. Build PipelineV2State with variant_tier
      4. Run through the unified 8-node pipeline
      5. Return a PipelineResult with response + metadata

    Args:
        query: Customer's raw message.
        company_id: Tenant identifier (BC-001).
        session_context: The Jarvis session's context_json (dict).
        conversation_id: For multi-turn tracking.
        ticket_id: Ticket identifier.
        channel: Communication channel.
        customer_id: Customer identifier.
        customer_tier: Customer subscription tier.

    Returns:
        PipelineResult with response text and all pipeline metadata.
    """
    start = time.monotonic()
    try:
        # ── Step 1: Resolve variant tier from context ──
        variant_tier = _resolve_tier_from_session(session_context)

        # ── Step 2: Resolve industry from context ──
        industry = _resolve_industry_from_session(session_context)

        # ── Step 3: Get variant instance_id from context ──
        variant_instance_id = session_context.get(
            "variant_instance_id", f"inst_{variant_tier}_{company_id}",
        )

        logger.info(
            "process_customer_care_message: tier=%s, industry=%s, "
            "company_id=%s, instance=%s",
            variant_tier, industry, company_id, variant_instance_id,
        )

        # ── Step 4: Run through unified pipeline ──
        result = await _run_parwa_pipeline(
            variant_tier=variant_tier,
            query=query,
            company_id=company_id,
            industry=industry,
            variant_instance_id=variant_instance_id,
            conversation_id=conversation_id,
            ticket_id=ticket_id,
            channel=channel,
            customer_id=customer_id,
            customer_tier=customer_tier,
        )

        # ── Step 5: Execute external tool actions (post-pipeline) ──
        try:
            from app.core.external_tool_executor import execute_pipeline_actions

            customer_email = session_context.get("customer_email", "")
            customer_phone = session_context.get("customer_phone", "")

            raw_result = result.metadata or {}
            raw_result["emergency_flag"] = result.emergency_flag
            raw_result["quality_score"] = result.quality_score
            raw_result["pipeline_status"] = result.pipeline_status

            tool_results = await execute_pipeline_actions(
                variant_tier=variant_tier,
                company_id=company_id,
                pipeline_result=raw_result,
                customer_email=customer_email,
                customer_phone=customer_phone,
                ticket_number=ticket_id,
                ticket_id=ticket_id,
            )

            if tool_results:
                result.metadata["external_tool_results"] = {
                    k: {"channel": v.channel.value if hasattr(v.channel, 'value') else v.channel,
                        "success": v.success,
                        "message_id": v.message_id, "error": v.error}
                    for k, v in tool_results.items()
                }
                result.metadata["tools_executed"] = len(tool_results)
                result.metadata["tools_succeeded"] = sum(
                    1 for v in tool_results.values() if v.success
                )

        except Exception as tool_exc:
            logger.warning(
                "external_tool_execution_failed (non-blocking): %s",
                str(tool_exc)[:200],
            )

        total_ms = round((time.monotonic() - start) * 1000, 2)
        logger.info(
            "process_customer_care_message_complete: tier=%s, status=%s, "
            "latency=%sms, quality=%.1f",
            variant_tier, result.pipeline_status, total_ms,
            result.quality_score,
        )

        return result

    except Exception:
        total_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception(
            "process_customer_care_message failed: company_id=%s, "
            "latency=%sms",
            company_id, total_ms,
        )
        return PipelineResult(
            response_text=(
                "I apologize, I'm having trouble processing your request "
                "right now. A team member will follow up with you shortly."
            ),
            variant_tier=session_context.get("variant_tier", "mini_parwa"),
            industry=session_context.get("industry", "general"),
            pipeline_status="failed",
            total_latency_ms=total_ms,
            metadata={"error": "pipeline_bridge_failed"},
        )


def process_customer_care_message_sync(
    query: str,
    company_id: str,
    session_context: Dict[str, Any],
    conversation_id: str = "",
    ticket_id: str = "",
    channel: str = "chat",
    customer_id: str = "",
    customer_tier: str = "free",
) -> PipelineResult:
    """Sync wrapper for process_customer_care_message.

    Used by synchronous code paths (e.g., task runners).
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(
                asyncio.run,
                process_customer_care_message(
                    query=query,
                    company_id=company_id,
                    session_context=session_context,
                    conversation_id=conversation_id,
                    ticket_id=ticket_id,
                    channel=channel,
                    customer_id=customer_id,
                    customer_tier=customer_tier,
                ),
            ).result()
    else:
        return asyncio.run(
            process_customer_care_message(
                query=query,
                company_id=company_id,
                session_context=session_context,
                conversation_id=conversation_id,
                ticket_id=ticket_id,
                channel=channel,
                customer_id=customer_id,
                customer_tier=customer_tier,
            ),
        )


# ══════════════════════════════════════════════════════════════════
# ONBOARDING ENTRY POINT
# ══════════════════════════════════════════════════════════════════


async def process_onboarding_message(
    query: str,
    company_id: str,
    session_context: Dict[str, Any],
    conversation_id: str = "",
    ticket_id: str = "",
    channel: str = "chat",
    customer_id: str = "",
    customer_tier: str = "free",
) -> PipelineResult:
    """Process an onboarding message through the 8-node PARWA pipeline.

    Called by onboarding_jarvis_orchestrator when the user has selected
    a variant tier during onboarding.

    Args:
        query: Customer's raw message.
        company_id: Tenant identifier (BC-001).
        session_context: The Jarvis session's context_json (dict).
        conversation_id: For multi-turn tracking.
        ticket_id: Ticket identifier.
        channel: Communication channel.
        customer_id: Customer identifier.
        customer_tier: Customer subscription tier.

    Returns:
        PipelineResult with response text and all pipeline metadata.
    """
    start = time.monotonic()
    try:
        variant_tier = _resolve_tier_from_session(session_context)
        industry = _resolve_industry_from_session(session_context)
        variant_instance_id = session_context.get(
            "variant_instance_id", f"inst_{variant_tier}_{company_id}",
        )

        logger.info(
            "process_onboarding_message: tier=%s, industry=%s, "
            "company_id=%s",
            variant_tier, industry, company_id,
        )

        result = await _run_parwa_pipeline(
            variant_tier=variant_tier,
            query=query,
            company_id=company_id,
            industry=industry,
            variant_instance_id=variant_instance_id,
            conversation_id=conversation_id,
            ticket_id=ticket_id,
            channel=channel,
            customer_id=customer_id,
            customer_tier=customer_tier,
        )

        total_ms = round((time.monotonic() - start) * 1000, 2)
        logger.info(
            "process_onboarding_message_complete: tier=%s, status=%s, "
            "latency=%sms, quality=%.1f",
            variant_tier, result.pipeline_status, total_ms,
            result.quality_score,
        )

        return result

    except Exception:
        total_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception(
            "process_onboarding_message failed: company_id=%s, "
            "latency=%sms",
            company_id, total_ms,
        )
        return PipelineResult(
            response_text=(
                "I'm currently unable to process your request. "
                "A team member will get back to you shortly."
            ),
            variant_tier=session_context.get("variant_tier", "mini_parwa"),
            industry=session_context.get("industry", "general"),
            pipeline_status="failed",
            total_latency_ms=total_ms,
            metadata={"error": "onboarding_pipeline_failed"},
        )


def process_onboarding_message_sync(
    query: str,
    company_id: str,
    session_context: Dict[str, Any],
    conversation_id: str = "",
    ticket_id: str = "",
    channel: str = "chat",
    customer_id: str = "",
    customer_tier: str = "free",
) -> PipelineResult:
    """Sync wrapper for process_onboarding_message."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(
                asyncio.run,
                process_onboarding_message(
                    query=query,
                    company_id=company_id,
                    session_context=session_context,
                    conversation_id=conversation_id,
                    ticket_id=ticket_id,
                    channel=channel,
                    customer_id=customer_id,
                    customer_tier=customer_tier,
                ),
            ).result()
    else:
        return asyncio.run(
            process_onboarding_message(
                query=query,
                company_id=company_id,
                session_context=session_context,
                conversation_id=conversation_id,
                ticket_id=ticket_id,
                channel=channel,
                customer_id=customer_id,
                customer_tier=customer_tier,
            ),
        )


# ══════════════════════════════════════════════════════════════════
# VARIANT TIER CHECK
# ══════════════════════════════════════════════════════════════════


def has_variant_tier_in_context(session_context: Dict[str, Any]) -> bool:
    """Check if a session context has a variant tier set.

    Used by jarvis_service to decide whether to route through the
    PARWA pipeline or fall back to direct AI.

    Args:
        session_context: The Jarvis session's context_json (dict).

    Returns:
        True if variant_tier or enough context exists to resolve one.
    """
    try:
        if not session_context or not isinstance(session_context, dict):
            return False

        # Direct tier
        if session_context.get("variant_tier"):
            return True

        # Variant ID that maps to a tier
        if session_context.get("variant_id"):
            return True

        # Selected variants from onboarding
        selected = session_context.get("selected_variants")
        if selected and isinstance(selected, list) and len(selected) > 0:
            return True

        return False

    except Exception:
        return False


# ══════════════════════════════════════════════════════════════════
# UNIFIED PIPELINE RUNNER
# ══════════════════════════════════════════════════════════════════


async def _run_pipeline(
    variant_tier: str,
    query: str,
    company_id: str,
    industry: str,
    variant_instance_id: str = "",
    conversation_id: str = "",
    ticket_id: str = "",
    channel: str = "chat",
    customer_id: str = "",
    customer_tier: str = "free",
) -> PipelineResult:
    """Run the unified 8-node PARWA pipeline.

    ALL tiers (mini_parwa, parwa, parwa_high) use the same pipeline.
    The variant_tier is passed in the state — Node 2 (Smart Route) reads it
    to make tier-aware complexity routing decisions.

    This function is the single pipeline runner, replacing the old
    _run_mini_parwa / _run_parwa / _run_parwa_high trio.
    """
    return await _run_parwa_pipeline(
        variant_tier=variant_tier,
        query=query,
        company_id=company_id,
        industry=industry,
        variant_instance_id=variant_instance_id,
        conversation_id=conversation_id,
        ticket_id=ticket_id,
        channel=channel,
        customer_id=customer_id,
        customer_tier=customer_tier,
    )


async def _run_parwa_pipeline(
    variant_tier: str,
    query: str,
    company_id: str,
    industry: str,
    variant_instance_id: str = "",
    conversation_id: str = "",
    ticket_id: str = "",
    channel: str = "chat",
    customer_id: str = "",
    customer_tier: str = "free",
) -> PipelineResult:
    """Run a message through the unified 8-node PARWA pipeline.

    Builds a PipelineV2State, invokes the compiled LangGraph,
    and returns a PipelineResult with the response + metadata.

    Pipeline:
      Node 1 (Ingest+Classify) → Node 2 (Smart Route)
        ├── simple → Node 3 (Knowledge) → Node 7 (Simple Resolver)
        └── complex → Node 3 → Node 4 (Reasoning) → Node 5 (Act+Verify)
                       → Node 6 (Quality) → [loop or Node 8 or END]

    Args:
        variant_tier: 'mini_parwa' | 'parwa' | 'parwa_high'.
                      Node 2 reads this for tier-aware routing.
        query: Customer's raw message.
        company_id: Tenant identifier (BC-001).
        industry: Industry enum value.
        variant_instance_id: Specific variant instance.
        conversation_id: For multi-turn tracking.
        ticket_id: Ticket identifier.
        channel: Communication channel.
        customer_id: Customer identifier.
        customer_tier: Customer subscription tier.

    Returns:
        PipelineResult with response + full pipeline metadata.
    """
    try:
        graph = _get_parwa_pipeline_graph()

        if graph is None:
            logger.error("PARWA pipeline graph not available — returning fallback")
            return PipelineResult(
                response_text=(
                    "I'm experiencing a temporary issue. "
                    "Our team has been notified and will respond shortly."
                ),
                variant_tier=variant_tier,
                industry=industry,
                pipeline_status="pipeline_unavailable",
            )

        # Generate IDs if not provided
        if not ticket_id:
            import uuid
            ticket_id = f"tkt_{uuid.uuid4().hex[:12]}"
        if not conversation_id:
            import uuid
            conversation_id = f"conv_{uuid.uuid4().hex[:12]}"

        # Build PipelineV2State — the input for the 8-node pipeline
        initial_state: PipelineV2State = {
            "ticket_id": ticket_id,
            "tenant_id": company_id,
            "query": query,
            "channel_type": channel,
            "variant_tier": variant_tier,
            "customer_context": {
                "customer_id": customer_id,
                "customer_tier": customer_tier,
                "industry": industry,
            },
            "metadata": {
                "variant_instance_id": variant_instance_id,
                "conversation_id": conversation_id,
                "company_id": company_id,
            },
            "loop_count": 0,
            "current_path": "",
            "status": "",
            "technique_log": [],
            "errors": [],
        }

        # Run the pipeline
        result = await graph.ainvoke(initial_state)

        # Extract response from pipeline result
        response_text = (
            result.get("final_response", "")
            or result.get("formatted_response", "")
            or result.get("combined_answer", "")
            or result.get("simple_answer", "")
            or result.get("super_node_answer", "")
        )

        # Debug logging — see exactly what the pipeline returned
        logger.info(
            "pipeline_result_debug: ticket=%s status=%s quality=%.0f%% "
            "final_response=%dchars formatted_response=%dchars "
            "combined_answer=%dchars simple_answer=%dchars "
            "super_node_answer=%dchars response_text=%dchars "
            "route=%s path=%s",
            ticket_id[:8] if ticket_id else "?",
            result.get("status", "?"),
            (result.get("quality_score", 0) or result.get("simple_confidence", 0) or 0) * 100,
            len(result.get("final_response", "") or ""),
            len(result.get("formatted_response", "") or ""),
            len(result.get("combined_answer", "") or ""),
            len(result.get("simple_answer", "") or ""),
            len(result.get("super_node_answer", "") or ""),
            len(response_text or ""),
            result.get("route_decision", "?"),
            result.get("current_path", "?"),
        )

        # Build steps_completed from technique_log
        technique_log = result.get("technique_log", [])
        steps_completed = [
            entry.get("technique", "") or entry.get("node", "")
            for entry in technique_log
            if entry.get("technique") or entry.get("node")
        ]

        # Determine pipeline status from state
        status = result.get("status", "completed")
        if status in ("resolved",):
            pipeline_status = "completed"
        elif status in ("escalated",):
            pipeline_status = "escalated"
        elif status in ("stuck",):
            pipeline_status = "stuck"
        else:
            pipeline_status = status or "completed"

        # Get quality score (max of all quality scores)
        quality_score = max(
            result.get("quality_score", 0.0),
            result.get("simple_confidence", 0.0),
            result.get("reasoning_confidence", 0.0),
            result.get("super_node_quality", 0.0),
            result.get("classification_confidence", 0.0),
        )

        # Get resolution path info
        route_decision = result.get("route_decision", "unknown")
        current_path = result.get("current_path", "")
        loop_count = result.get("loop_count", 0)

        # Extract classification info
        classification_intent = result.get("ticket_type", "")
        complexity = result.get("complexity", "")

        # Token usage
        total_tokens = (
            result.get("total_token_usage", 0)
            or result.get("node_1_token_usage", 0)
            + result.get("node_3_token_usage", 0)
            + result.get("node_4_token_usage", 0)
            + result.get("node_5_token_usage", 0)
            + result.get("node_6_token_usage", 0)
            + result.get("node_8_token_usage", 0)
        )

        # Techniques used
        techniques_used = result.get("techniques_used", [])

        return PipelineResult(
            response_text=response_text or (
                "I apologize for the inconvenience. "
                "Our team will follow up with you shortly."
            ),
            variant_tier=variant_tier,
            industry=industry,
            pipeline_status=pipeline_status,
            quality_score=quality_score,
            total_latency_ms=result.get("total_latency_ms", 0.0),
            billing_tokens=total_tokens,
            steps_completed=steps_completed,
            technique_used=", ".join(techniques_used[:3]) if techniques_used else route_decision,
            emergency_flag=False,
            empathy_score=0.5,
            classification_intent=classification_intent,
            metadata={
                "ticket_id": ticket_id,
                "conversation_id": conversation_id,
                "route_decision": route_decision,
                "current_path": current_path,
                "complexity": complexity,
                "loop_count": loop_count,
                "techniques_used": techniques_used,
                "quality_passed": result.get("quality_passed", False),
                "auto_upgraded": result.get("auto_upgraded", False),
                "wiki_patterns_found": len(result.get("wiki_patterns", [])),
                "knowledge_sufficient": result.get("knowledge_sufficient", True),
                "actions_taken": len(result.get("actions_taken", [])),
                "errors": result.get("errors", []),
            },
        )

    except Exception:
        logger.exception("_run_parwa_pipeline failed")
        return PipelineResult(
            response_text=(
                "I apologize for the inconvenience. "
                "Our team will follow up with you shortly."
            ),
            variant_tier=variant_tier,
            industry=industry,
            pipeline_status="failed",
            metadata={"error": "parwa_pipeline_execution_failed"},
        )


# ══════════════════════════════════════════════════════════════════
# CONTEXT RESOLUTION HELPERS
# ══════════════════════════════════════════════════════════════════


def _resolve_tier_from_session(session_context: Dict[str, Any]) -> str:
    """Resolve the variant tier from a session's context.

    The context_json should contain variant_tier set during handoff
    or during onboarding when user selects a tier on Models page.
    If not present, tries to resolve from variant_id/selected_variants.

    Args:
        session_context: The Jarvis session's context_json (dict).

    Returns:
        Backend pipeline tier string.
    """
    try:
        # Direct tier (set during handoff or Models page selection — best path)
        tier = session_context.get("variant_tier")
        if tier and tier in ("mini_parwa", "parwa", "parwa_high"):
            return tier

        # Try to resolve from variant_id
        variant_id = session_context.get("variant_id")
        if variant_id:
            return resolve_tier_from_context(variant_id=variant_id)

        # Try to resolve from selected_variants
        selected_variants = session_context.get("selected_variants")
        if selected_variants:
            return resolve_tier_from_context(
                selected_variants=selected_variants,
            )

        # Default: mini_parwa (safest, cheapest)
        return "mini_parwa"

    except Exception:
        logger.warning("Failed to resolve tier from session context, defaulting to mini_parwa", exc_info=True)
        return "mini_parwa"


def _resolve_industry_from_session(session_context: Dict[str, Any]) -> str:
    """Resolve the industry from a session's context.

    Args:
        session_context: The Jarvis session's context_json (dict).

    Returns:
        Backend industry enum value.
    """
    try:
        industry = session_context.get("industry")
        return resolve_industry_from_context(industry=industry)
    except Exception:
        logger.warning("Failed to resolve industry from session context, defaulting to general", exc_info=True)
        return "general"


# ══════════════════════════════════════════════════════════════════
# HEALTH CHECK
# ══════════════════════════════════════════════════════════════════


def health_check() -> Dict[str, Any]:
    """Check if the variant pipeline bridge is operational.

    Returns:
        Dict with status and pipeline availability.
    """
    try:
        graph = _get_parwa_pipeline_graph()
        available = graph is not None

        return {
            "status": "healthy" if available else "degraded",
            "pipeline": "parwa_pipeline_v2_8node",
            "available": available,
            "supports_tiers": ["mini_parwa", "parwa", "parwa_high"],
            "bridge_version": "3.0.0",
            "supports_onboarding": True,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception:
        return {
            "status": "unhealthy",
            "pipeline": "parwa_pipeline_v2_8node",
            "available": False,
            "error": "health_check_failed",
        }
