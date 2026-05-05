"""
Variant Pipeline Bridge: Routes customer care messages through the correct pipeline.

This is the connection point between the Jarvis customer care system and
the Mini Parwa / Parwa / Parwa High LangGraph pipelines.

When a customer care message comes in:
  1. Look up the variant tier from the session context (set during handoff)
  2. Resolve the full VariantConfig (tier + industry)
  3. Run the message through the appropriate pipeline
  4. Return the response + metadata to the Jarvis service

The Jarvis onboarding chat is NEVER touched — this bridge only activates
for customer_care type sessions (after handoff).

Pipeline Selection:
  - mini_parwa (Starter): 10-node pipeline, Tier 1 techniques
  - parwa (Growth):       15-node pipeline, Tier 1+2 techniques
  - parwa_high (High):    20-node pipeline, all techniques

Architecture:
  jarvis_service.send_message()
       ↓ (customer_care path)
  variant_pipeline_bridge.process_customer_care_message()
       ↓
  resolve_variant_tier() from session context
       ↓
  MiniParwaPipeline.process_ticket()  (or Pro/High in future)
       ↓
  Return: response_text, metadata, knowledge_used

BC-001: company_id first parameter on public methods.
BC-008: Every public method wrapped in try/except — never crash.
BC-012: All timestamps UTC.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.core.variant_tier_mapper import (
    resolve_tier_from_context,
    resolve_industry_from_context,
    get_tier_metadata,
)
from app.logger import get_logger

logger = get_logger("variant_pipeline_bridge")


# ══════════════════════════════════════════════════════════════════
# PIPELINE SINGLETONS (lazy-initialized)
# ══════════════════════════════════════════════════════════════════

_mini_parwa_pipeline: Optional[Any] = None
_parwa_pipeline: Optional[Any] = None
_parwa_high_pipeline: Optional[Any] = None


def _get_mini_parwa_pipeline() -> Any:
    """Get or create the Mini Parwa pipeline singleton."""
    global _mini_parwa_pipeline
    if _mini_parwa_pipeline is None:
        try:
            from app.core.mini_parwa.graph import MiniParwaPipeline
            _mini_parwa_pipeline = MiniParwaPipeline()
            logger.info("MiniParwaPipeline singleton initialized for bridge")
        except Exception:
            logger.exception("Failed to initialize MiniParwaPipeline")
    return _mini_parwa_pipeline


def _get_parwa_pipeline() -> Any:
    """Get or create the Pro Parwa pipeline singleton (future)."""
    global _parwa_pipeline
    if _parwa_pipeline is None:
        try:
            # Future: from app.core.parwa.graph import ParwaPipeline
            logger.info("ParwaPipeline not yet implemented — will use Mini fallback")
        except Exception:
            logger.exception("Failed to initialize ParwaPipeline")
    return _parwa_pipeline


def _get_parwa_high_pipeline() -> Any:
    """Get or create the High Parwa pipeline singleton (future)."""
    global _parwa_high_pipeline
    if _parwa_high_pipeline is None:
        try:
            # Future: from app.core.parwa_high.graph import ParwaHighPipeline
            logger.info("ParwaHighPipeline not yet implemented — will use Mini fallback")
        except Exception:
            logger.exception("Failed to initialize ParwaHighPipeline")
    return _parwa_high_pipeline


# ══════════════════════════════════════════════════════════════════
# PIPELINE RESULT
# ══════════════════════════════════════════════════════════════════


class PipelineResult:
    """Result from processing a message through a variant pipeline."""

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
# MAIN ENTRY POINT
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
    """Process a customer care message through the appropriate variant pipeline.

    This is the main entry point called by jarvis_service when handling
    customer_care type sessions.

    Flow:
      1. Resolve variant_tier from session context
      2. Resolve industry from session context
      3. Select the appropriate pipeline
      4. Run the message through the pipeline
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

        # ── Step 4: Select and run pipeline ──
        if variant_tier == "mini_parwa":
            result = await _run_mini_parwa(
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
        elif variant_tier == "parwa_high":
            # Future: Run ParwaHigh pipeline
            # For now, falls through to Mini Parwa
            logger.info(
                "parwa_high not yet implemented — using mini_parwa fallback",
            )
            result = await _run_mini_parwa(
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
        else:
            # Default: parwa (Growth) — also falls through to Mini for now
            logger.info(
                "parwa not yet implemented — using mini_parwa fallback",
            )
            result = await _run_mini_parwa(
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
            "process_customer_care_message_complete: tier=%s, status=%s, "
            "latency=%sms, quality=%.1f, steps=%d",
            variant_tier, result.pipeline_status, total_ms,
            result.quality_score, len(result.steps_completed),
        )

        return result

    except Exception:
        total_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception(
            "process_customer_care_message failed: company_id=%s, "
            "latency=%sms",
            company_id, total_ms,
        )
        # BC-008: Return a safe fallback result
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
    """Synchronous wrapper for process_customer_care_message.

    Handles the async/sync bridge for calling from jarvis_service
    which is synchronous. Uses ThreadPoolExecutor if no event loop.

    Args:
        Same as process_customer_care_message.

    Returns:
        PipelineResult with response text and all pipeline metadata.
    """
    try:
        try:
            loop = asyncio.get_running_loop()
            # We're inside an existing event loop — use thread pool
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(
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
                )
                return future.result(timeout=30)
        except RuntimeError:
            # No event loop — safe to use asyncio.run
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
                )
            )
    except Exception:
        logger.exception("process_customer_care_message_sync failed")
        return PipelineResult(
            response_text=(
                "I apologize, I'm having trouble processing your request. "
                "A team member will follow up shortly."
            ),
            variant_tier="mini_parwa",
            industry="general",
            pipeline_status="failed",
            metadata={"error": "sync_wrapper_failed"},
        )


# ══════════════════════════════════════════════════════════════════
# PIPELINE RUNNERS
# ══════════════════════════════════════════════════════════════════


async def _run_mini_parwa(
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
    """Run a message through the Mini Parwa 10-node pipeline.

    Pipeline: pii_check → empathy_check → emergency_check → gsd_state
              → extract_signals → classify → generate → crp_compress
              → clara_quality_gate → format

    Connected Frameworks (Tier 1 — Always Active):
      - CLARA (Quality Gate)
      - CRP (Token Compression)
      - GSD (State Engine)
      - Smart Router (Light tier)
      - Technique Router (Tier 1 only)
      - Confidence Scoring

    Args:
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
        pipeline = _get_mini_parwa_pipeline()

        if pipeline is None:
            logger.error("MiniParwaPipeline not available — returning fallback")
            return PipelineResult(
                response_text=(
                    "I'm experiencing a temporary issue. "
                    "Our team has been notified and will respond shortly."
                ),
                variant_tier="mini_parwa",
                industry=industry,
                pipeline_status="pipeline_unavailable",
            )

        # Run through Mini Parwa's process_ticket method
        result = await pipeline.process_ticket(
            query=query,
            company_id=company_id,
            industry=industry,
            channel=channel,
            customer_id=customer_id,
            customer_tier=customer_tier,
            conversation_id=conversation_id,
            ticket_id=ticket_id,
            variant_instance_id=variant_instance_id,
        )

        # Extract the formatted response from pipeline result
        response_text = result.get("formatted_response", "") or result.get(
            "generated_response", ""
        )

        # If pipeline generated an emergency escalation response
        if result.get("emergency_flag", False):
            emergency_type = result.get("emergency_type", "")
            response_text = result.get("formatted_response", "") or (
                "Your message has been flagged for priority handling. "
                "A senior team member will contact you directly. "
                f"Reference: {result.get('ticket_id', 'N/A')}"
            )

        # If no response was generated, use fallback
        if not response_text:
            classification = result.get("classification", {})
            intent = classification.get("intent", "general")
            # Use template response based on intent
            from app.core.mini_parwa.nodes import TEMPLATE_RESPONSES
            response_text = TEMPLATE_RESPONSES.get(
                intent, TEMPLATE_RESPONSES["general"],
            )

        return PipelineResult(
            response_text=response_text,
            variant_tier="mini_parwa",
            industry=industry,
            pipeline_status=result.get("pipeline_status", "completed"),
            quality_score=result.get("quality_score", 0.0),
            total_latency_ms=result.get("total_latency_ms", 0.0),
            billing_tokens=result.get("billing_tokens", 0),
            steps_completed=result.get("steps_completed", []),
            technique_used=result.get("technique", ""),
            emergency_flag=result.get("emergency_flag", False),
            empathy_score=result.get("empathy_score", 0.5),
            classification_intent=result.get("classification", {}).get("intent", ""),
            metadata={
                "ticket_id": result.get("ticket_id", ""),
                "conversation_id": result.get("conversation_id", ""),
                "pii_detected": result.get("pii_detected", False),
                "gsd_state": result.get("step_outputs", {}).get(
                    "gsd_state", {},
                ).get("to_state", ""),
                "crp_compression_ratio": result.get("step_outputs", {}).get(
                    "crp_compress", {},
                ).get("compression_ratio", 1.0),
                "clara_passed": result.get("step_outputs", {}).get(
                    "clara_quality_gate", {},
                ).get("passed", True),
            },
        )

    except Exception:
        logger.exception("_run_mini_parwa failed")
        return PipelineResult(
            response_text=(
                "I apologize for the inconvenience. "
                "Our team will follow up with you shortly."
            ),
            variant_tier="mini_parwa",
            industry=industry,
            pipeline_status="failed",
            metadata={"error": "mini_parwa_execution_failed"},
        )


# ══════════════════════════════════════════════════════════════════
# CONTEXT RESOLUTION HELPERS
# ══════════════════════════════════════════════════════════════════


def _resolve_tier_from_session(session_context: Dict[str, Any]) -> str:
    """Resolve the variant tier from a customer care session's context.

    The context_json should contain variant_tier set during handoff.
    If not present, tries to resolve from variant_id/selected_variants.

    Args:
        session_context: The Jarvis session's context_json (dict).

    Returns:
        Backend pipeline tier string.
    """
    try:
        # Direct tier (set during handoff — best path)
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
        return "mini_parwa"


def _resolve_industry_from_session(session_context: Dict[str, Any]) -> str:
    """Resolve the industry from a customer care session's context.

    Args:
        session_context: The Jarvis session's context_json (dict).

    Returns:
        Backend industry enum value.
    """
    try:
        industry = session_context.get("industry")
        return resolve_industry_from_context(industry=industry)
    except Exception:
        return "general"


# ══════════════════════════════════════════════════════════════════
# HEALTH CHECK
# ══════════════════════════════════════════════════════════════════


def health_check() -> Dict[str, Any]:
    """Check if the variant pipeline bridge is operational.

    Returns:
        Dict with status and available pipelines.
    """
    try:
        pipelines_available = {}

        mini = _get_mini_parwa_pipeline()
        pipelines_available["mini_parwa"] = mini is not None

        # Pro and High not yet implemented
        pipelines_available["parwa"] = False
        pipelines_available["parwa_high"] = False

        all_ok = any(pipelines_available.values())

        return {
            "status": "healthy" if all_ok else "degraded",
            "pipelines": pipelines_available,
            "bridge_version": "1.0.0",
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception:
        return {
            "status": "unhealthy",
            "pipelines": {},
            "error": "health_check_failed",
        }
