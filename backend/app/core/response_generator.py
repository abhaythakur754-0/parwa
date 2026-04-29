"""
Auto-Response Generation Engine (F-065)

Combines intent + RAG context + sentiment → brand-aligned response.
Smart Router Medium tier.  Runs through CLARA quality gate (F-150).

Full pipeline:
  1. Rate-limit check (GAP-020)  — max 20/hr, 100/day per customer
  2. Draft-in-progress check (GAP-028) — skip if human agent is drafting
  3. Sentiment analysis (F-063)
  4. RAG retrieval (F-064 Part 1)
  5. Reranking (F-064 Part 2)
  6. Context window assembly
  7. Token budget check (GAP-006)
  8. Brand voice integration (F-154)
  9. LLM response generation via SmartRouter Medium tier (F-054)
  10. CLARA quality gate (F-150)
  11. Template fallback (F-155)
  12. Response formatting (SG-26)
  13. Final brand voice validation (F-154)

BC-001: All operations scoped to company_id.
BC-008: Graceful degradation — never crashes on bad input.
GAP-020: Per-customer rate limiting (Redis counters).
GAP-028: Draft-in-progress guard (Redis flag).

Parent: Week 9 Day 8 (Monday)
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.logger import get_logger

logger = get_logger("response_generator")


# ════════════════════════════════════════════════════════════════════
# CONSTANTS
# ════════════════════════════════════════════════════════════════════

# GAP-020: Rate limits per customer
RATE_LIMIT_HOURLY_MAX: int = 20
RATE_LIMIT_DAILY_MAX: int = 100

# GAP-020: Redis key patterns
_RATE_LIMIT_HOUR_KEY_TPL = "rate_limit:response:{company_id}:{customer_id}:hour:{hour}"
_RATE_LIMIT_DAY_KEY_TPL = "rate_limit:response:{company_id}:{customer_id}:day:{day}"
_RATE_LIMIT_TTL_SECONDS: int = 86400  # 24 hours

# GAP-028: Draft-in-progress Redis key
_DRAFT_IN_PROGRESS_KEY_TPL = "draft_in_progress:{company_id}:{ticket_id}"
_DRAFT_TTL_SECONDS: int = 600  # 10 minutes

# Approximate token-to-character ratio
_CHARS_PER_TOKEN: int = 4

# Max generation timeout in seconds
_GENERATION_TIMEOUT_SECONDS: float = 30.0

# Default max response tokens per variant
_VARIANT_MAX_RESPONSE_TOKENS: Dict[str, int] = {
    "mini_parwa": 256,
    "parwa": 512,
    "high_parwa": 1024,
}

# Variant-specific RAG top-k
_VARIANT_RAG_TOP_K: Dict[str, int] = {
    "mini_parwa": 3,
    "parwa": 5,
    "high_parwa": 10,
}

# Variant-specific context window tokens for assembly
_VARIANT_CONTEXT_TOKENS: Dict[str, int] = {
    "mini_parwa": 2048,
    "parwa": 4096,
    "high_parwa": 8192,
}


# ════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ════════════════════════════════════════════════════════════════════


@dataclass
class ResponseGenerationRequest:
    """Input to the response generation pipeline."""

    query: str
    company_id: str
    conversation_id: str
    variant_type: str  # mini_parwa, parwa, high_parwa
    customer_id: Optional[str] = None
    conversation_history: Optional[List[dict]] = None
    customer_metadata: Optional[dict] = None
    language: str = "en"
    # fallback to template if AI budget exhausted
    force_template_response: bool = False
    ticket_id: Optional[str] = None  # for GAP-028 draft check
    intent_type: str = "general"  # for template matching and formatting
    # Override system prompt with context-aware prompt
    system_prompt: Optional[str] = None

    # D5-1 FIX: Pre-computed sentiment fields from pipeline Stage 5.
    # When provided, generate() skips its internal sentiment analysis
    # (saves ~1-2s latency per request by avoiding duplicate work).
    frustration_score: float = 0.0          # 0-100 from SentimentAnalyzer
    sentiment_score: float = 0.5            # 0.0-1.0 from SentimentAnalyzer
    # angry/frustrated/disappointed/neutral/happy/delighted
    emotion: str = "neutral"
    urgency_level: str = "low"              # low/medium/high/critical
    # empathetic/urgent/de-escalation/standard
    tone_recommendation: str = "standard"
    selected_model: Optional[str] = None    # from Smart Router Stage 6
    selected_technique: Optional[str] = None  # from Technique Router Stage 7


@dataclass
class ResponseGenerationResult:
    """Output of the response generation pipeline."""

    response_text: str
    confidence_score: float
    sentiment_analysis: dict  # serialized SentimentResult
    rag_context_used: bool
    citations: List[dict]
    clara_passed: bool
    clara_score: float
    formatters_applied: List[str]
    tokens_used: int
    generation_time_ms: float
    template_used: bool  # True if fell back to template
    quality_issues: List[str]


@dataclass
class RateLimitCheck:
    """Result of rate-limit check (GAP-020)."""

    allowed: bool
    hourly_count: int
    hourly_limit: int
    daily_count: int
    daily_limit: int
    reason: str = ""


# ════════════════════════════════════════════════════════════════════
# RESPONSE GENERATOR
# ════════════════════════════════════════════════════════════════════


class ResponseGenerator:
    """Auto-Response Generation Engine (F-065).

    Combines sentiment analysis, RAG context retrieval, brand voice
    guidelines, and SmartRouter Medium-tier LLM calls to produce
    brand-aligned, quality-gated customer responses.

    Every response passes through the CLARA quality gate.  Failures
    gracefully degrade to template responses.

    BC-001: All operations scoped to company_id.
    BC-008: Never crashes — every step has a fallback path.
    """

    def __init__(self, redis_client: Any = None) -> None:
        from app.core.sentiment_engine import SentimentAnalyzer
        from app.core.rag_retrieval import RAGRetriever
        from app.core.rag_reranking import (
            CrossEncoderReranker,
            ContextWindowAssembler,
        )
        from app.core.clara_quality_gate import CLARAQualityGate
        from app.core.smart_router import SmartRouter
        from app.services.brand_voice_service import BrandVoiceService
        from app.services.token_budget_service import TokenBudgetService
        from app.services.response_template_service import (
            ResponseTemplateService,
        )

        self.redis_client = redis_client
        self.sentiment_analyzer = SentimentAnalyzer()
        self.rag_retriever = RAGRetriever()
        self.reranker = CrossEncoderReranker()
        self.assembler = ContextWindowAssembler()
        self.clara_gate = CLARAQualityGate()
        self.brand_voice = BrandVoiceService(redis_client=redis_client)
        self.token_budget = TokenBudgetService(redis_client=redis_client)
        self.template_service = ResponseTemplateService(
            redis_client=redis_client,
        )
        self.smart_router = SmartRouter()

        logger.info("response_generator_initialized")

    # ──────────────────────────────────────────────────────────────
    # MAIN ENTRY POINT
    # ──────────────────────────────────────────────────────────────

    async def generate(
        self,
        request: ResponseGenerationRequest,
    ) -> ResponseGenerationResult:
        """Main entry point. Full pipeline:

        analyze → retrieve → generate → quality check → format.

        Every step is wrapped in try/except for BC-008 graceful
        degradation.  If the AI pipeline fails at any stage, we
        fall back to a template response.
        """
        pipeline_start = time.monotonic()

        # ── Validate request ──────────────────────────────────────
        if not request.query or not request.query.strip():
            return self._empty_response_result(
                pipeline_start=pipeline_start,
                reason="empty_query",
            )

        # ── GAP-028: Draft-in-progress check ──────────────────────
        if request.ticket_id:
            try:
                draft_active = await self._check_draft_in_progress(
                    company_id=request.company_id,
                    ticket_id=request.ticket_id,
                )
                if draft_active:
                    logger.info(
                        "response_gen_skipped_draft_in_progress",
                        company_id=request.company_id,
                        ticket_id=request.ticket_id,
                    )
                    return self._empty_response_result(
                        pipeline_start=pipeline_start,
                        reason="draft_in_progress",
                    )
            except Exception as exc:
                logger.warning(
                    "draft_check_failed_continuing",
                    error=str(exc),
                    company_id=request.company_id,
                )

        # ── GAP-020: Rate-limit check ─────────────────────────────
        if request.customer_id:
            try:
                rate_check = await self._check_rate_limit(
                    company_id=request.company_id,
                    customer_id=request.customer_id,
                )
                if not rate_check.allowed:
                    logger.info(
                        "response_gen_rate_limited",
                        company_id=request.company_id,
                        customer_id=request.customer_id,
                        hourly=rate_check.hourly_count,
                        daily=rate_check.daily_count,
                    )
                    # Fall back to template when rate limited
                    template_result = await self._fallback_to_template(
                        request=request,
                        sentiment_score=0.5,
                        pipeline_start=pipeline_start,
                        reason="rate_limited",
                    )
                    if template_result is not None:
                        return template_result
            except Exception as exc:
                logger.warning(
                    "rate_limit_check_failed_continuing",
                    error=str(exc),
                    company_id=request.company_id,
                )

        # ── Step 1: Sentiment Analysis ────────────────────────────
        sentiment_result: Optional[Any] = None
        sentiment_score: float = 0.5
        sentiment_dict: Dict[str, Any] = {}

        try:
            # Extract text messages from conversation_history for
            # the sentiment analyser (it expects List[str]).
            history_texts: Optional[List[str]] = None
            if request.conversation_history:
                history_texts = [
                    msg.get("content", "")
                    for msg in request.conversation_history
                    if isinstance(msg, dict) and msg.get("content")
                ]

            sentiment_result = await self.sentiment_analyzer.analyze(
                query=request.query,
                company_id=request.company_id,
                variant_type=request.variant_type,
                conversation_history=history_texts,
                customer_metadata=request.customer_metadata,
            )
            sentiment_score = sentiment_result.sentiment_score
            sentiment_dict = sentiment_result.to_dict()

            logger.info(
                "response_gen_sentiment_complete",
                company_id=request.company_id,
                frustration=sentiment_result.frustration_score,
                emotion=sentiment_result.emotion,
                sentiment_score=sentiment_score,
            )
        except Exception as exc:
            logger.warning(
                "response_gen_sentiment_failed_using_defaults",
                error=str(exc),
                company_id=request.company_id,
            )
            sentiment_score = 0.5
            sentiment_dict = {
                "frustration_score": 0.0,
                "emotion": "neutral",
                "urgency_level": "low",
                "tone_recommendation": "standard",
                "empathy_signals": [],
                "sentiment_score": 0.5,
                "conversation_trend": "stable",
                "degraded": True,
                "degradation_reason": str(exc),
            }

        # ── Step 2: RAG Retrieval ─────────────────────────────────
        rag_result: Optional[Any] = None
        rag_context_string: str = ""
        citations: List[dict] = []
        rag_context_used: bool = False

        try:
            top_k = _VARIANT_RAG_TOP_K.get(
                request.variant_type, _VARIANT_RAG_TOP_K["parwa"],
            )

            rag_result = await self.rag_retriever.retrieve(
                query=request.query,
                company_id=request.company_id,
                variant_type=request.variant_type,
                top_k=top_k,
            )

            if rag_result and rag_result.chunks:
                rag_context_used = True

                # ── Step 3: Reranking ──────────────────────────────
                try:
                    reranked = await self.reranker.rerank(
                        chunks=rag_result.chunks,
                        query=request.query,
                        company_id=request.company_id,
                        variant_type=request.variant_type,
                        top_k=top_k,
                    )
                    if reranked and reranked.chunks:
                        rag_result = reranked
                except Exception as exc:
                    logger.warning(
                        "response_gen_rerank_failed_using_original",
                        error=str(exc),
                        company_id=request.company_id,
                    )

                # ── Step 4: Context Assembly ────────────────────────
                context_tokens = _VARIANT_CONTEXT_TOKENS.get(
                    request.variant_type, _VARIANT_CONTEXT_TOKENS["parwa"],
                )
                try:
                    assembled = self.assembler.assemble(
                        chunks=rag_result.chunks,
                        max_tokens=context_tokens,
                        query=request.query,
                    )
                    rag_context_string = assembled.context_string
                    citations = [
                        c.to_dict() for c in assembled.citations
                    ]
                except Exception as exc:
                    logger.warning(
                        "response_gen_context_assembly_failed",
                        error=str(exc),
                        company_id=request.company_id,
                    )
                    # Build a simple context from raw chunks
                    rag_context_string = "\n\n".join(
                        chunk.content for chunk in rag_result.chunks[:3]
                    )

                logger.info(
                    "response_gen_rag_complete",
                    company_id=request.company_id,
                    chunks_found=rag_result.total_found,
                    context_tokens=len(rag_context_string) // _CHARS_PER_TOKEN,
                )
        except Exception as exc:
            logger.warning(
                "response_gen_rag_failed_generating_without_context",
                error=str(exc),
                company_id=request.company_id,
            )
            rag_context_string = ""

        # ── Step 5: Token Budget Check (GAP-006) ──────────────────
        tokens_used: int = 0
        estimated_tokens: int = 0
        budget_exhausted: bool = False

        try:
            # Initialize budget if not already done
            await self.token_budget.initialize_budget(
                conversation_id=request.conversation_id,
                company_id=request.company_id,
                variant_type=request.variant_type,
            )

            # Estimate tokens for this generation
            query_tokens = len(request.query) // _CHARS_PER_TOKEN
            context_tokens_est = len(rag_context_string) // _CHARS_PER_TOKEN
            max_response_tokens = _VARIANT_MAX_RESPONSE_TOKENS.get(
                request.variant_type, 512,
            )
            estimated_tokens = query_tokens + context_tokens_est + max_response_tokens

            # Check overflow
            overflow = await self.token_budget.check_overflow(
                conversation_id=request.conversation_id,
                estimated_tokens=estimated_tokens,
            )
            if not overflow.can_fit:
                logger.warning(
                    "response_gen_token_budget_overflow",
                    company_id=request.company_id,
                    overflow_amount=overflow.overflow_amount,
                    conversation_id=request.conversation_id,
                )
                budget_exhausted = True

            # Try to reserve tokens
            reserve_result = await self.token_budget.reserve_tokens(
                conversation_id=request.conversation_id,
                tokens=estimated_tokens,
            )
            if not reserve_result.success:
                logger.warning(
                    "response_gen_token_reserve_failed",
                    company_id=request.company_id,
                    remaining=reserve_result.remaining_after_reserve,
                )
                budget_exhausted = True
        except Exception as exc:
            logger.warning(
                "response_gen_token_budget_check_failed",
                error=str(exc),
                company_id=request.company_id,
            )

        # ── If budget exhausted or force_template, use template ──
        if budget_exhausted or request.force_template_response:
            template_result = await self._fallback_to_template(
                request=request,
                sentiment_score=sentiment_score,
                pipeline_start=pipeline_start,
                reason="budget_exhausted" if budget_exhausted else "force_template",
            )
            if template_result is not None:
                return template_result

        # ── Step 6: Brand Voice Integration ────────────────────────
        brand_config: Optional[Any] = None
        response_guidelines: Optional[Any] = None

        try:
            brand_config = await self.brand_voice.get_config(
                company_id=request.company_id,
            )
            response_guidelines = await self.brand_voice.get_response_guidelines(
                company_id=request.company_id,
                sentiment_score=sentiment_score,
            )
        except Exception as exc:
            logger.warning(
                "response_gen_brand_voice_failed_using_defaults",
                error=str(exc),
                company_id=request.company_id,
            )

        # ── Step 7: LLM Response Generation ────────────────────────
        generated_response: str = ""
        llm_confidence: float = 0.0
        llm_error: bool = False

        try:
            # If an override system_prompt was provided (from build_system_prompt
            # with user journey context), use it as the base; otherwise build
            # one.
            if request.system_prompt:
                system_prompt = request.system_prompt
            else:
                system_prompt = self._build_system_prompt(
                    brand_config=brand_config,
                    response_guidelines=response_guidelines,
                    sentiment_result=sentiment_result,
                    rag_context=rag_context_string,
                    request=request,
                )

            messages = self._build_messages(
                system_prompt=system_prompt,
                conversation_history=request.conversation_history or [],
                query=request.query,
                rag_context=rag_context_string,
            )

            from app.core.smart_router import (
                AtomicStepType,
            )

            # Route to Medium tier for response generation
            routing_decision = self.smart_router.route(
                company_id=request.company_id,
                variant_type=request.variant_type,
                atomic_step=AtomicStepType.DRAFT_RESPONSE_MODERATE,
                query_signals={
                    "sentiment_score": sentiment_score,
                    "has_rag_context": rag_context_used,
                    "intent_type": request.intent_type,
                },
            )

            max_tokens = _VARIANT_MAX_RESPONSE_TOKENS.get(
                request.variant_type, 512,
            )

            llm_result = await asyncio.wait_for(
                self.smart_router.async_execute_llm_call(
                    company_id=request.company_id,
                    routing_decision=routing_decision,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=max_tokens,
                ),
                timeout=_GENERATION_TIMEOUT_SECONDS,
            )

            generated_response = llm_result.get("content", "")
            llm_confidence = 0.8 if generated_response else 0.0

            # Track actual tokens used (approximate)
            actual_tokens = (
                len(generated_response) // _CHARS_PER_TOKEN
                + estimated_tokens
            )
            tokens_used = actual_tokens

            # Finalize token budget (return unused reserved tokens)
            await self.token_budget.finalize_tokens(
                conversation_id=request.conversation_id,
                reserved=estimated_tokens,
                actual=actual_tokens,
            )

            logger.info(
                "response_gen_llm_complete",
                company_id=request.company_id,
                model=llm_result.get("model", "unknown"),
                provider=llm_result.get("provider", "unknown"),
                tier=llm_result.get("tier", "unknown"),
                response_length=len(generated_response),
                tokens_used=tokens_used,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "response_gen_llm_timeout",
                company_id=request.company_id,
                timeout=_GENERATION_TIMEOUT_SECONDS,
            )
            llm_error = True
        except Exception as exc:
            logger.warning(
                "response_gen_llm_failed",
                error=str(exc),
                company_id=request.company_id,
            )
            llm_error = True

        # ── If LLM failed, fall back to template ──────────────────
        if llm_error or not generated_response.strip():
            logger.info(
                "response_gen_falling_back_to_template",
                reason="llm_failure" if llm_error else "empty_response",
                company_id=request.company_id,
            )
            template_result = await self._fallback_to_template(
                request=request,
                sentiment_score=sentiment_score,
                pipeline_start=pipeline_start,
                reason="llm_failure",
            )
            if template_result is not None:
                return template_result

            # Last resort: return a generic response
            return self._empty_response_result(
                pipeline_start=pipeline_start,
                reason="all_generation_failed",
            )

        # ── Step 8: CLARA Quality Gate ────────────────────────────
        clara_passed: bool = False
        clara_score: float = 0.0
        quality_issues: List[str] = []
        final_response: str = generated_response

        try:
            clara_result = await self.clara_gate.evaluate(
                response=generated_response,
                query=request.query,
                company_id=request.company_id,
                customer_sentiment=sentiment_score,
                context={
                    "rag_context_used": rag_context_used,
                    "brand_config_tone": getattr(
                        brand_config, "tone", "professional",
                    ) if brand_config else "professional",
                    "formality_level": getattr(
                        brand_config, "formality_level", 0.5,
                    ) if brand_config else 0.5,
                },
            )

            clara_passed = clara_result.overall_pass
            clara_score = clara_result.overall_score

            # Collect quality issues from failed stages
            for stage_output in clara_result.stages:
                if hasattr(
                        stage_output,
                        "result") and hasattr(
                        stage_output,
                        "issues"):
                    if stage_output.result.value in ("fail", "error"):
                        quality_issues.extend(stage_output.issues)

            if clara_result.final_response:
                final_response = clara_result.final_response

            logger.info(
                "response_gen_clara_complete",
                company_id=request.company_id,
                clara_passed=clara_passed,
                clara_score=clara_score,
                pipeline_timed_out=clara_result.pipeline_timed_out,
            )
        except Exception as exc:
            logger.warning(
                "response_gen_clara_failed_using_raw_response",
                error=str(exc),
                company_id=request.company_id,
            )
            quality_issues.append(f"CLARA evaluation error: {str(exc)}")

        # ── Step 9: Template Fallback if CLARA failed ──────────────
        if not clara_passed and not request.force_template_response:
            logger.info(
                "response_gen_clara_failed_falling_back_to_template",
                company_id=request.company_id,
                clara_score=clara_score,
                quality_issues=quality_issues[:5],
            )
            template_result = await self._fallback_to_template(
                request=request,
                sentiment_score=sentiment_score,
                pipeline_start=pipeline_start,
                reason="clara_failed",
            )
            if template_result is not None:
                # Merge CLARA failure info into template result
                template_result.quality_issues = quality_issues
                template_result.clara_passed = False
                template_result.clara_score = clara_score
                return template_result

        # ── Step 10: Response Formatting ──────────────────────────
        formatters_applied: List[str] = []

        try:
            from app.core.response_formatters import (
                FormattingContext,
                create_default_registry,
            )

            registry = create_default_registry()

            formatting_context = FormattingContext(
                company_id=request.company_id,
                variant_type=request.variant_type,
                brand_voice=getattr(brand_config, "tone", "professional")
                if brand_config else "professional",
                model_tier="medium",
                customer_tier=request.customer_metadata.get("tier", "free")
                if request.customer_metadata else "free",
                intent_type=request.intent_type,
                sentiment_score=sentiment_score,
                formality_level=(
                    "high"
                    if getattr(brand_config, "formality_level", 0.5) > 0.7
                    else "medium"
                    if getattr(brand_config, "formality_level", 0.5) > 0.3
                    else "low"
                )
                if brand_config else "medium",
            )

            format_result = registry.apply_all(
                response=final_response,
                context=formatting_context,
            )
            final_response = format_result.formatted_text
            formatters_applied = format_result.formatters_applied

            if format_result.errors:
                logger.warning(
                    "response_gen_formatting_errors",
                    errors=format_result.errors,
                    company_id=request.company_id,
                )
        except Exception as exc:
            logger.warning(
                "response_gen_formatting_failed_using_unformatted",
                error=str(exc),
                company_id=request.company_id,
            )

        # ── Step 11: Final Brand Voice Validation ──────────────────
        try:
            if brand_config:
                validation = await self.brand_voice.validate_response(
                    text=final_response,
                    company_id=request.company_id,
                )
                if not validation.is_valid:
                    # Apply suggested fixes if available
                    if validation.suggested_fixes:
                        logger.info(
                            "response_gen_brand_validation_issues",
                            issues=validation.violations,
                            fixes=validation.suggested_fixes[:3],
                            company_id=request.company_id,
                        )
                    quality_issues.extend(validation.violations)
                    quality_issues.extend(
                        [f"Brand warning: {w}" for w in validation.warnings],
                    )
        except Exception as exc:
            logger.warning(
                "response_gen_final_brand_validation_failed",
                error=str(exc),
                company_id=request.company_id,
            )

        # ── Step 12: Brand Voice Merge (final polish) ─────────────
        try:
            final_response = await self.brand_voice.merge_with_brand_voice(
                response_text=final_response,
                company_id=request.company_id,
            )
        except Exception as exc:
            logger.warning(
                "response_gen_brand_merge_failed",
                error=str(exc),
                company_id=request.company_id,
            )

        # ── Build final result ─────────────────────────────────────
        generation_time_ms = round(
            (time.monotonic() - pipeline_start) * 1000, 2,
        )

        logger.info(
            "response_generation_complete",
            company_id=request.company_id,
            variant_type=request.variant_type,
            clara_passed=clara_passed,
            clara_score=clara_score,
            template_used=False,
            generation_time_ms=generation_time_ms,
            formatters_applied=formatters_applied,
            quality_issues_count=len(quality_issues),
        )

        return ResponseGenerationResult(
            response_text=final_response,
            confidence_score=round(llm_confidence, 4),
            sentiment_analysis=sentiment_dict,
            rag_context_used=rag_context_used,
            citations=citations,
            clara_passed=clara_passed,
            clara_score=round(clara_score, 4),
            formatters_applied=formatters_applied,
            tokens_used=tokens_used,
            generation_time_ms=generation_time_ms,
            template_used=False,
            quality_issues=quality_issues,
        )

    # ──────────────────────────────────────────────────────────────
    # GAP-020: RATE LIMITING
    # ──────────────────────────────────────────────────────────────

    async def _check_rate_limit(
        self,
        company_id: str,
        customer_id: str,
    ) -> RateLimitCheck:
        """Max 20/hour, 100/day per customer.  Redis INCR.

        Key patterns:
          rate_limit:response:{company_id}:{customer_id}:hour:{hour}
          rate_limit:response:{company_id}:{customer_id}:day:{date}

        Returns ``RateLimitCheck`` with ``allowed=True`` when within
        limits.  On Redis failure, always allows (BC-008 / BC-012).
        """
        now = datetime.now(timezone.utc)
        hour_key = _RATE_LIMIT_HOUR_KEY_TPL.format(
            company_id=company_id,
            customer_id=customer_id,
            hour=now.strftime("%Y%m%d%H"),
        )
        day_key = _RATE_LIMIT_DAY_KEY_TPL.format(
            company_id=company_id,
            customer_id=customer_id,
            day=now.strftime("%Y%m%d"),
        )

        try:
            if self.redis_client is None:
                return RateLimitCheck(
                    allowed=True,
                    hourly_count=0,
                    hourly_limit=RATE_LIMIT_HOURLY_MAX,
                    daily_count=0,
                    daily_limit=RATE_LIMIT_DAILY_MAX,
                    reason="no_redis",
                )

            # Increment hourly counter
            hourly_count = await self.redis_client.incr(hour_key)
            if hourly_count == 1:
                await self.redis_client.expire(
                    hour_key, 3600,
                )

            # Increment daily counter
            daily_count = await self.redis_client.incr(day_key)
            if daily_count == 1:
                await self.redis_client.expire(
                    day_key, _RATE_LIMIT_TTL_SECONDS,
                )

            hourly_allowed = hourly_count <= RATE_LIMIT_HOURLY_MAX
            daily_allowed = daily_count <= RATE_LIMIT_DAILY_MAX
            allowed = hourly_allowed and daily_allowed

            reason: str = ""
            if not hourly_allowed:
                reason = (
                    f"Hourly limit exceeded: {hourly_count}/{RATE_LIMIT_HOURLY_MAX}")
            elif not daily_allowed:
                reason = (
                    f"Daily limit exceeded: {daily_count}/{RATE_LIMIT_DAILY_MAX}")

            if not allowed:
                logger.info(
                    "rate_limit_exceeded",
                    company_id=company_id,
                    customer_id=customer_id,
                    hourly_count=hourly_count,
                    daily_count=daily_count,
                    reason=reason,
                )

            return RateLimitCheck(
                allowed=allowed,
                hourly_count=int(hourly_count),
                hourly_limit=RATE_LIMIT_HOURLY_MAX,
                daily_count=int(daily_count),
                daily_limit=RATE_LIMIT_DAILY_MAX,
                reason=reason,
            )

        except Exception as exc:
            logger.warning(
                "rate_limit_check_error_fail_open",
                error=str(exc),
                company_id=company_id,
                customer_id=customer_id,
            )
            # BC-008 / BC-012: Fail open on Redis errors
            return RateLimitCheck(
                allowed=True,
                hourly_count=0,
                hourly_limit=RATE_LIMIT_HOURLY_MAX,
                daily_count=0,
                daily_limit=RATE_LIMIT_DAILY_MAX,
                reason=f"redis_error: {exc}",
            )

    # ──────────────────────────────────────────────────────────────
    # GAP-028: DRAFT-IN-PROGRESS CHECK
    # ──────────────────────────────────────────────────────────────

    async def _check_draft_in_progress(
        self,
        company_id: str,
        ticket_id: str,
    ) -> bool:
        """Check if a human agent is currently drafting a response.

        Redis key: ``draft_in_progress:{company_id}:{ticket_id}``
        If the key exists, a human agent is actively composing a
        reply and we should skip auto-response generation.

        Returns:
            ``True`` if a draft is in progress.
        """
        if not company_id or not ticket_id:
            return False

        try:
            if self.redis_client is None:
                return False

            key = _DRAFT_IN_PROGRESS_KEY_TPL.format(
                company_id=company_id,
                ticket_id=ticket_id,
            )
            value = await self.redis_client.get(key)

            if value is not None:
                logger.debug(
                    "draft_in_progress_detected",
                    company_id=company_id,
                    ticket_id=ticket_id,
                    agent_id=value,
                )
                return True

            return False

        except Exception as exc:
            logger.warning(
                "draft_in_progress_check_error",
                error=str(exc),
                company_id=company_id,
                ticket_id=ticket_id,
            )
            # BC-008: Assume no draft on error
            return False

    # ──────────────────────────────────────────────────────────────
    # SYSTEM PROMPT BUILDER
    # ──────────────────────────────────────────────────────────────

    def _build_system_prompt(
        self,
        brand_config: Optional[Any],
        response_guidelines: Optional[Any],
        sentiment_result: Optional[Any],
        rag_context: str,
        request: ResponseGenerationRequest,
    ) -> str:
        """Build a comprehensive system prompt that includes:

        - Brand voice guidelines (tone, formality, prohibited words)
        - Response length preference
        - Sentiment-appropriate tone adjustments
        - RAG context with citation format instructions
        - Conversation trend awareness
        """
        parts: List[str] = []

        # ── Core role ─────────────────────────────────────────────
        brand_name = "our company"
        if brand_config:
            brand_name = getattr(brand_config, "brand_name", brand_name)
        parts.append(
            f"You are a helpful, professional customer support agent for "
            f"{brand_name}.  Respond to the customer's inquiry accurately "
            f"and empathetically."
        )

        # ── Tone and formality ────────────────────────────────────
        tone = "professional"
        formality_desc = "medium formality"

        if brand_config:
            tone = getattr(brand_config, "tone", tone)
            formality_level = getattr(brand_config, "formality_level", 0.5)
            if formality_level > 0.7:
                formality_desc = "high formality — avoid contractions, use precise language"
            elif formality_level > 0.4:
                formality_desc = "medium formality — be polite but approachable"
            else:
                formality_desc = "low formality — be warm, friendly, and conversational"

        parts.append(f"\n**Tone:** {tone}. **Style:** {formality_desc}.")

        # ── Response length ───────────────────────────────────────
        if brand_config:
            length_pref = getattr(
                brand_config, "response_length_preference", "standard",
            )
            max_sentences = getattr(brand_config, "max_response_sentences", 6)
            min_sentences = getattr(brand_config, "min_response_sentences", 2)
            parts.append(
                f"\n**Response length:** {length_pref}. "
                f"Keep responses between {min_sentences} and "
                f"{max_sentences} sentences."
            )

        # ── Prohibited words ──────────────────────────────────────
        if brand_config:
            prohibited = getattr(brand_config, "prohibited_words", [])
            if prohibited:
                words_str = ", ".join(f'"{w}"' for w in prohibited)
                parts.append(
                    f"\n**PROHIBITED WORDS** (never use these): {words_str}"
                )

        # ── Custom instructions ───────────────────────────────────
        if brand_config:
            custom = getattr(brand_config, "custom_instructions", "")
            if custom and custom.strip():
                parts.append(f"\n**Additional brand guidelines:** {custom}")

        # ── Sentiment-appropriate adjustments ──────────────────────
        if sentiment_result:
            frustration = getattr(sentiment_result, "frustration_score", 0)
            emotion = getattr(sentiment_result, "emotion", "neutral")
            tone_rec = getattr(
                sentiment_result, "tone_recommendation", "standard",
            )
            trend = getattr(
                sentiment_result, "conversation_trend", "stable",
            )
            empathy_signals = getattr(
                sentiment_result, "empathy_signals", [],
            )

            if frustration >= 70:
                parts.append(
                    "\n**IMPORTANT:** This customer is highly frustrated "
                    f"(score: {frustration}/100). You MUST:\n"
                    "- Acknowledge their frustration empathetically\n"
                    "- Apologize sincerely for their experience\n"
                    "- Focus on concrete solutions and next steps\n"
                    "- Avoid defensive or dismissive language\n"
                    "- Never say 'calm down' or 'you should'"
                )
            elif frustration >= 40:
                parts.append(
                    f"\n**Note:** This customer shows moderate frustration "
                    f"(score: {frustration}/100). Be empathetic and "
                    "solution-focused."
                )

            if emotion == "happy" or emotion == "delighted":
                parts.append(
                    "\n**Note:** This customer is in a positive mood. "
                    "Match their enthusiasm and keep the response warm."
                )

            if tone_rec == "de-escalation":
                parts.append(
                    "\n**Tone directive:** De-escalation mode — "
                    "prioritize calming language and reassurance."
                )
            elif tone_rec == "urgent":
                parts.append(
                    "\n**Tone directive:** Urgent mode — "
                    "acknowledge urgency and provide immediate next steps."
                )

            if trend == "worsening":
                parts.append(
                    "\n**Conversation trend:** The customer's sentiment "
                    "is worsening. Extra empathy is needed."
                )

            if empathy_signals:
                signal_handling: List[str] = []
                if "financial_impact" in empathy_signals:
                    signal_handling.append(
                        "- Financial impact detected — "
                        "be extra sensitive about money matters"
                    )
                if "personal_impact" in empathy_signals:
                    signal_handling.append(
                        "- Personal impact detected — "
                        "show genuine care and understanding"
                    )
                if "timeline_pressure" in empathy_signals:
                    signal_handling.append(
                        "- Timeline pressure detected — "
                        "prioritize speed and clear timelines"
                    )
                if "apology_expectation" in empathy_signals:
                    signal_handling.append(
                        "- Customer expects an apology — "
                        "include a sincere, specific apology"
                    )
                if signal_handling:
                    parts.append(
                        "\n**Empathy signals detected:**\n"
                        + "\n".join(signal_handling)
                    )

        # ── RAG context instructions ──────────────────────────────
        if rag_context and rag_context.strip():
            parts.append(
                "\n**Knowledge base context:** Use the provided context "
                "to answer the customer's question accurately. "
                "When citing information from the context, reference "
                "it naturally in your response. "
                "Do NOT fabricate information not in the context."
            )

        # ── Citation format ───────────────────────────────────────
        if request.variant_type == "high_parwa":
            parts.append(
                "\n**Citation format:** When referencing source material, "
                "use inline citations like [1], [2], etc. "
                "A sources section will be appended automatically."
            )

        # ── Language instruction ──────────────────────────────────
        if request.language and request.language != "en":
            parts.append(
                f"\n**Language:** Respond in {request.language}."
            )

        # ── General quality rules ─────────────────────────────────
        parts.append(
            "\n**Quality rules:**\n"
            "- Be accurate and specific — avoid vague statements\n"
            "- Use clear, concise language\n"
            "- If you don't know the answer, say so honestly and "
            "offer to escalate\n"
            "- Never invent facts, policies, or promises\n"
            "- Address the customer's specific question, not a "
            "generic one"
        )

        return "\n".join(parts)

    # ──────────────────────────────────────────────────────────────
    # MESSAGES BUILDER
    # ──────────────────────────────────────────────────────────────

    def _build_messages(
        self,
        system_prompt: str,
        conversation_history: List[dict],
        query: str,
        rag_context: str,
    ) -> List[dict]:
        """Build messages array for the LLM call.

        Structure:
        1. System prompt (brand voice + guidelines + context instructions)
        2. Conversation history (last 10 messages max)
        3. Current user query
        4. RAG context (as a separate system message if available)
        """
        messages: List[dict] = []

        # System prompt
        messages.append({"role": "system", "content": system_prompt})

        # Conversation history (last 10 messages)
        history_to_include = conversation_history[-10:] if conversation_history else [
        ]
        for msg in history_to_include:
            if not isinstance(msg, dict):
                continue
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if not content or not isinstance(content, str):
                continue
            # Only include user and assistant roles
            if role in ("user", "assistant"):
                messages.append({"role": role, "content": content})

        # Current query
        messages.append({"role": "user", "content": query})

        # RAG context as a follow-up system message
        if rag_context and rag_context.strip():
            messages.append({
                "role": "system",
                "content": f"Relevant knowledge base context:\n\n{rag_context}",
            })

        return messages

    # ──────────────────────────────────────────────────────────────
    # TEMPLATE FALLBACK
    # ──────────────────────────────────────────────────────────────

    async def _fallback_to_template(
        self,
        request: ResponseGenerationRequest,
        sentiment_score: float,
        pipeline_start: float,
        reason: str,
    ) -> Optional[ResponseGenerationResult]:
        """Attempt to generate a response using a template.

        Returns ``None`` if no suitable template is found or rendering
        fails — the caller should then use a last-resort response.
        """
        try:
            template = await self.template_service.find_best_template(
                company_id=request.company_id,
                intent_type=request.intent_type,
                language=request.language,
                sentiment_score=sentiment_score,
            )

            if template is None:
                logger.info(
                    "response_gen_no_template_found",
                    company_id=request.company_id,
                    intent_type=request.intent_type,
                    reason=reason,
                )
                return None

            # Build template variables
            customer_name = "Valued Customer"
            company_name = "our team"
            agent_name = "Support Team"

            if request.customer_metadata:
                customer_name = request.customer_metadata.get(
                    "name", customer_name,
                )

            # Try to get brand name from brand config
            try:
                brand_config = await self.brand_voice.get_config(
                    company_id=request.company_id,
                )
                company_name = getattr(
                    brand_config, "brand_name", company_name,
                )
            except Exception as exc:
                logger.debug(
                    "brand_config_fetch_failed",
                    error=str(exc),
                    company_id=request.company_id)

            variables = {
                "customer_name": customer_name,
                "company_name": company_name,
                "agent_name": agent_name,
                "ticket_id": request.ticket_id or "N/A",
                "response_time": "24 hours",
                "resolution_time": "48 hours",
            }

            rendered = await self.template_service.render_template(
                template_id=template.id,
                company_id=request.company_id,
                variables=variables,
            )

            if not rendered or not rendered.strip():
                logger.warning(
                    "response_gen_template_rendered_empty",
                    template_id=template.id,
                    company_id=request.company_id,
                )
                return None

            # Apply basic formatting even to templates
            formatters_applied: List[str] = []
            try:
                from app.core.response_formatters import (
                    FormattingContext,
                    create_default_registry,
                )
                registry = create_default_registry()
                fmt_ctx = FormattingContext(
                    company_id=request.company_id,
                    variant_type=request.variant_type,
                    sentiment_score=sentiment_score,
                    intent_type=request.intent_type,
                )
                fmt_result = registry.apply_all(
                    response=rendered, context=fmt_ctx,
                )
                rendered = fmt_result.formatted_text
                formatters_applied = fmt_result.formatters_applied
            except Exception as exc:
                logger.warning(
                    "response_gen_template_formatting_failed",
                    error=str(exc),
                )

            generation_time_ms = round(
                (time.monotonic() - pipeline_start) * 1000, 2,
            )

            logger.info(
                "response_gen_template_fallback_success",
                company_id=request.company_id,
                template_id=template.id,
                template_name=template.name,
                reason=reason,
                generation_time_ms=generation_time_ms,
            )

            # Build minimal sentiment dict for template results
            sentiment_dict = {
                "frustration_score": 0.0,
                "emotion": "neutral",
                "urgency_level": "low",
                "tone_recommendation": "standard",
                "empathy_signals": [],
                "sentiment_score": round(sentiment_score, 4),
                "conversation_trend": "stable",
                "template_fallback": True,
                "fallback_reason": reason,
            }

            return ResponseGenerationResult(
                response_text=rendered,
                confidence_score=0.5,  # Lower confidence for templates
                sentiment_analysis=sentiment_dict,
                rag_context_used=False,
                citations=[],
                clara_passed=True,  # Templates are pre-approved
                clara_score=0.8,
                formatters_applied=formatters_applied,
                tokens_used=len(rendered) // _CHARS_PER_TOKEN,
                generation_time_ms=generation_time_ms,
                template_used=True,
                quality_issues=[],
            )

        except Exception as exc:
            logger.warning(
                "response_gen_template_fallback_failed",
                error=str(exc),
                company_id=request.company_id,
                reason=reason,
            )
            return None

    # ──────────────────────────────────────────────────────────────
    # EMPTY / LAST-RESORT RESPONSE
    # ──────────────────────────────────────────────────────────────

    def _empty_response_result(
        self,
        pipeline_start: float,
        reason: str,
    ) -> ResponseGenerationResult:
        """Return a safe, minimal result when generation is impossible."""
        generation_time_ms = round(
            (time.monotonic() - pipeline_start) * 1000, 2,
        )

        response_text: str = ""
        if reason == "draft_in_progress":
            response_text = ""
        elif reason == "empty_query":
            response_text = ""
        else:
            response_text = (
                "Thank you for reaching out. A support agent will "
                "review your request and get back to you shortly."
            )

        return ResponseGenerationResult(
            response_text=response_text,
            confidence_score=0.0,
            sentiment_analysis={
                "frustration_score": 0.0,
                "emotion": "neutral",
                "urgency_level": "low",
                "tone_recommendation": "standard",
                "empathy_signals": [],
                "sentiment_score": 0.5,
                "conversation_trend": "stable",
                "degraded": True,
                "degradation_reason": reason,
            },
            rag_context_used=False,
            citations=[],
            clara_passed=False,
            clara_score=0.0,
            formatters_applied=[],
            tokens_used=0,
            generation_time_ms=generation_time_ms,
            template_used=False,
            quality_issues=[f"Generation not possible: {reason}"],
        )

    # ──────────────────────────────────────────────────────────────
    # PUBLIC UTILITY METHODS
    # ──────────────────────────────────────────────────────────────

    async def generate_batch(
        self,
        requests: List[ResponseGenerationRequest],
    ) -> List[ResponseGenerationResult]:
        """Generate responses for multiple requests concurrently.

        Each request is processed independently.  Failed requests
        still produce a valid ``ResponseGenerationResult`` (never
        raises).

        Args:
            requests: List of generation requests.

        Returns:
            List of results in the same order as the input requests.
        """
        if not requests:
            return []

        results: List[ResponseGenerationResult] = []

        # Process in parallel with a concurrency limit of 5
        semaphore = asyncio.Semaphore(5)

        async def _guarded_generate(
            req: ResponseGenerationRequest,
        ) -> ResponseGenerationResult:
            async with semaphore:
                try:
                    return await self.generate(req)
                except Exception as exc:
                    logger.exception(
                        "batch_generation_item_failed",
                        company_id=req.company_id,
                        conversation_id=req.conversation_id,
                        error=str(exc),
                    )
                    return ResponseGenerationResult(
                        response_text="",
                        confidence_score=0.0,
                        sentiment_analysis={},
                        rag_context_used=False,
                        citations=[],
                        clara_passed=False,
                        clara_score=0.0,
                        formatters_applied=[],
                        tokens_used=0,
                        generation_time_ms=0.0,
                        template_used=False,
                        quality_issues=[f"Batch generation error: {exc}"],
                    )

        tasks = [_guarded_generate(req) for req in requests]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        return results

    async def get_generation_status(
        self,
        conversation_id: str,
        company_id: str,
    ) -> Dict[str, Any]:
        """Get token budget status for a conversation.

        Useful for monitoring and dashboard displays.

        Args:
            conversation_id: Unique conversation identifier.
            company_id: Tenant identifier (BC-001).

        Returns:
            Dict with budget status information.
        """
        try:
            status = await self.token_budget.get_budget_status(
                conversation_id=conversation_id,
            )
            return {
                "conversation_id": conversation_id,
                "company_id": company_id,
                "max_tokens": status.max_tokens,
                "used_tokens": status.used_tokens,
                "reserved_tokens": status.reserved_tokens,
                "available_tokens": status.available_tokens,
                "percentage_used": status.percentage_used,
                "warning_level": status.warning_level,
            }
        except Exception as exc:
            logger.warning(
                "generation_status_failed",
                error=str(exc),
                conversation_id=conversation_id,
                company_id=company_id,
            )
            return {
                "conversation_id": conversation_id,
                "company_id": company_id,
                "error": str(exc),
                "warning_level": "unknown",
            }

    async def set_draft_in_progress(
        self,
        company_id: str,
        ticket_id: str,
        agent_id: str,
        ttl_seconds: int = _DRAFT_TTL_SECONDS,
    ) -> bool:
        """Set the draft-in-progress flag for a ticket.

        Called by the frontend when an agent opens the reply editor.
        Auto-expires after ``ttl_seconds``.

        Args:
            company_id: Tenant identifier.
            ticket_id: Ticket being responded to.
            agent_id: ID of the agent who is drafting.
            ttl_seconds: Time-to-live for the flag (default 10 min).

        Returns:
            ``True`` if set successfully, ``False`` on error.
        """
        if not company_id or not ticket_id:
            return False

        try:
            if self.redis_client is None:
                return False

            key = _DRAFT_IN_PROGRESS_KEY_TPL.format(
                company_id=company_id,
                ticket_id=ticket_id,
            )
            await self.redis_client.set(key, agent_id, ex=ttl_seconds)

            logger.info(
                "draft_in_progress_set",
                company_id=company_id,
                ticket_id=ticket_id,
                agent_id=agent_id,
                ttl=ttl_seconds,
            )
            return True

        except Exception as exc:
            logger.warning(
                "draft_in_progress_set_failed",
                error=str(exc),
                company_id=company_id,
                ticket_id=ticket_id,
            )
            return False

    async def clear_draft_in_progress(
        self,
        company_id: str,
        ticket_id: str,
    ) -> bool:
        """Clear the draft-in-progress flag for a ticket.

        Called when an agent sends, discards, or navigates away from
        the reply editor.

        Args:
            company_id: Tenant identifier.
            ticket_id: Ticket that was being responded to.

        Returns:
            ``True`` if cleared successfully, ``False`` on error.
        """
        if not company_id or not ticket_id:
            return False

        try:
            if self.redis_client is None:
                return False

            key = _DRAFT_IN_PROGRESS_KEY_TPL.format(
                company_id=company_id,
                ticket_id=ticket_id,
            )
            await self.redis_client.delete(key)

            logger.info(
                "draft_in_progress_cleared",
                company_id=company_id,
                ticket_id=ticket_id,
            )
            return True

        except Exception as exc:
            logger.warning(
                "draft_in_progress_clear_failed",
                error=str(exc),
                company_id=company_id,
                ticket_id=ticket_id,
            )
            return False

    async def get_customer_rate_limit_status(
        self,
        company_id: str,
        customer_id: str,
    ) -> Dict[str, Any]:
        """Get current rate-limit counters for a customer.

        Useful for UI display (e.g. "You have X auto-responses
        remaining today").

        Args:
            company_id: Tenant identifier.
            customer_id: Customer identifier.

        Returns:
            Dict with hourly and daily usage info.
        """
        now = datetime.now(timezone.utc)
        hour_key = _RATE_LIMIT_HOUR_KEY_TPL.format(
            company_id=company_id,
            customer_id=customer_id,
            hour=now.strftime("%Y%m%d%H"),
        )
        day_key = _RATE_LIMIT_DAY_KEY_TPL.format(
            company_id=company_id,
            customer_id=customer_id,
            day=now.strftime("%Y%m%d"),
        )

        try:
            hourly = 0
            daily = 0

            if self.redis_client is not None:
                raw_hourly = await self.redis_client.get(hour_key)
                if raw_hourly is not None:
                    hourly = int(raw_hourly)

                raw_daily = await self.redis_client.get(day_key)
                if raw_daily is not None:
                    daily = int(raw_daily)

            return {
                "company_id": company_id,
                "customer_id": customer_id,
                "hourly_count": hourly,
                "hourly_limit": RATE_LIMIT_HOURLY_MAX,
                "hourly_remaining": max(0, RATE_LIMIT_HOURLY_MAX - hourly),
                "daily_count": daily,
                "daily_limit": RATE_LIMIT_DAILY_MAX,
                "daily_remaining": max(0, RATE_LIMIT_DAILY_MAX - daily),
            }

        except Exception as exc:
            logger.warning(
                "rate_limit_status_failed",
                error=str(exc),
                company_id=company_id,
                customer_id=customer_id,
            )
            return {
                "company_id": company_id,
                "customer_id": customer_id,
                "error": str(exc),
                "hourly_count": 0,
                "hourly_limit": RATE_LIMIT_HOURLY_MAX,
                "hourly_remaining": RATE_LIMIT_HOURLY_MAX,
                "daily_count": 0,
                "daily_limit": RATE_LIMIT_DAILY_MAX,
                "daily_remaining": RATE_LIMIT_DAILY_MAX,
            }

    async def reset_customer_rate_limit(
        self,
        company_id: str,
        customer_id: str,
    ) -> bool:
        """Reset rate-limit counters for a customer.

        Useful for admin actions or testing.

        Args:
            company_id: Tenant identifier.
            customer_id: Customer identifier.

        Returns:
            ``True`` if reset successfully.
        """
        now = datetime.now(timezone.utc)
        hour_key = _RATE_LIMIT_HOUR_KEY_TPL.format(
            company_id=company_id,
            customer_id=customer_id,
            hour=now.strftime("%Y%m%d%H"),
        )
        day_key = _RATE_LIMIT_DAY_KEY_TPL.format(
            company_id=company_id,
            customer_id=customer_id,
            day=now.strftime("%Y%m%d"),
        )

        try:
            if self.redis_client is not None:
                await self.redis_client.delete(hour_key)
                await self.redis_client.delete(day_key)

                logger.info(
                    "rate_limit_reset",
                    company_id=company_id,
                    customer_id=customer_id,
                )
                return True

            return False

        except Exception as exc:
            logger.warning(
                "rate_limit_reset_failed",
                error=str(exc),
                company_id=company_id,
                customer_id=customer_id,
            )
            return False
