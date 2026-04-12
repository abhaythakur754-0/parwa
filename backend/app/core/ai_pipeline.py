"""
PARWA AI Processing Pipeline (P2 — End-to-End Intelligence)

Chains all Week 8-12 AI services into a single orchestrated pipeline that
transforms a raw customer message into a brand-aligned, quality-checked,
guardrail-verified AI response.

Pipeline Stages:
    1. Edge Case Detection  — empty/emoji/code/malicious queries
    2. Prompt Injection Scan — security defense
    3. Signal Extraction    — 10 signals for routing decisions
    4. Intent Classification — multi-label intent classification
    5. Sentiment Analysis   — frustration, emotion, urgency, tone
    6. Smart Router         — model selection (Light/Medium/Heavy)
    7. Technique Router     — reasoning technique selection
    8. RAG Retrieval        — knowledge base search + reranking
    9. Response Generation  — AI response with model + technique
   10. CLARA Quality Gate   — 5-stage quality check
   11. Output Guardrails    — safety, policy, PII leak check
   12. Confidence Scoring   — calibrated 0-100 score
   13. Brand Voice Merge    — company-specific tone/style

BC-007: AI Model Interaction
BC-008: State Management
BC-010: Data Lifecycle & Compliance
BC-011: Authentication & Security
BC-012: Error Handling & Resilience
BC-013: AI Technique Routing (3-Tier)
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("parwa.ai_pipeline")


# ── Pipeline Data Classes ─────────────────────────────────────────


@dataclass
class PipelineContext:
    """Carries all intermediate state through the pipeline stages.

    Each stage populates its relevant fields. Downstream stages
    read upstream fields. This replaces passing 15+ parameters.
    """

    # Input
    query: str
    company_id: str
    conversation_id: str
    variant_type: str = "parwa"
    customer_id: Optional[str] = None
    conversation_history: Optional[List[dict]] = None
    customer_metadata: Optional[dict] = None
    language: str = "en"
    ticket_id: Optional[str] = None

    # Stage 1: Edge Case
    edge_case_action: Optional[str] = None
    edge_case_message: Optional[str] = None
    is_edge_case: bool = False

    # Stage 2: Prompt Injection
    injection_detected: bool = False
    injection_severity: str = "none"
    injection_blocked: bool = False
    injection_matches: List[dict] = field(default_factory=list)

    # Stage 3: Signal Extraction
    extracted_signals: Optional[dict] = None
    query_signals: Optional[Any] = None  # QuerySignals from TechniqueRouter

    # Stage 4: Classification
    intent_type: str = "general"
    intent_confidence: float = 0.0
    secondary_intents: List[str] = field(default_factory=list)

    # Stage 5: Sentiment
    frustration_score: float = 0.0
    sentiment_score: float = 0.5
    emotion: Optional[str] = None
    urgency_level: str = "normal"
    tone_recommendation: Optional[str] = None
    customer_tier: str = "standard"

    # Stage 6: Smart Router
    selected_model: Optional[str] = None
    selected_provider: Optional[str] = None
    selected_tier: str = "light"

    # Stage 7: Technique Router
    selected_technique: Optional[str] = None
    technique_tier: Optional[str] = None
    technique_fallback: Optional[str] = None

    # Stage 8: RAG
    rag_context: str = ""
    rag_chunks: List[dict] = field(default_factory=list)
    rag_citations: List[dict] = field(default_factory=list)
    rag_context_used: bool = False

    # Stage 9: Response Generation
    raw_response: str = ""
    response_text: str = ""
    generation_time_ms: float = 0.0
    tokens_used: int = 0

    # Stage 10: CLARA Quality Gate
    clara_passed: bool = True
    clara_score: float = 100.0
    clara_issues: List[str] = field(default_factory=list)
    clara_suggestions_applied: bool = False

    # Stage 11: Guardrails
    guardrails_passed: bool = True
    guardrails_blocked: bool = False
    guardrails_severity: str = "none"
    guardrails_report: Optional[dict] = None

    # Stage 12: Confidence
    confidence_score: float = 0.0
    confidence_threshold: float = 75.0
    confidence_auto_action: bool = False

    # Stage 13: Brand Voice
    brand_voice_applied: bool = False
    final_response: str = ""

    # Metadata
    pipeline_time_ms: float = 0.0
    stages_completed: List[str] = field(default_factory=list)
    stages_failed: List[str] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class PipelineResult:
    """Final output of the AI processing pipeline."""

    response: str
    confidence_score: float
    auto_action: bool  # Can this response be sent without human review?
    intent_type: str
    frustration_score: float
    sentiment_score: float
    urgency_level: str
    technique_used: Optional[str]
    model_used: Optional[str]
    rag_context_used: bool
    citations: List[dict]
    is_edge_case: bool
    injection_blocked: bool
    guardrails_blocked: bool
    clara_passed: bool
    pipeline_time_ms: float
    stages_completed: List[str]
    stages_failed: List[str]
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── Pipeline Orchestrator ─────────────────────────────────────────


class AIPipeline:
    """End-to-end AI processing pipeline for PARWA.

    Chains 13 stages from raw input to final response.
    Each stage has its own error handling (BC-012).
    Failed stages degrade gracefully rather than crash the pipeline.

    Usage::

        pipeline = AIPipeline()
        result = await pipeline.process(PipelineContext(
            query="How do I get a refund?",
            company_id="comp_123",
            conversation_id="conv_456",
            variant_type="parwa",
        ))
    """

    # Timeout per stage in seconds (BC-012)
    STAGE_TIMEOUTS = {
        "edge_case": 2,
        "injection_scan": 3,
        "signal_extraction": 5,
        "classification": 5,
        "sentiment": 5,
        "smart_router": 3,
        "technique_router": 2,
        "rag_retrieval": 8,
        "response_generation": 20,
        "clara_quality": 5,
        "guardrails": 5,
        "confidence_scoring": 3,
        "brand_voice": 3,
    }

    def __init__(self, redis_client: Any = None):
        self._redis_client = redis_client
        self._edge_case_handlers = None
        self._injection_detector = None
        self._signal_extractor = None
        self._classification_engine = None
        self._sentiment_analyzer = None
        self._smart_router = None
        self._technique_router = None
        self._rag_reranker = None
        self._response_generator = None
        self._clara_gate = None
        self._guardrails_engine = None
        self._confidence_engine = None
        self._brand_voice_svc = None

    # ── Lazy Service Initialization ───────────────────────────

    def _get_edge_case_handlers(self):
        if self._edge_case_handlers is None:
            try:
                from app.core.edge_case_handlers import (
                    EmptyQueryHandler, TooLongQueryHandler,
                    UnsupportedLanguageHandler, EmojisOnlyHandler,
                    CodeBlocksHandler, DuplicateQueryHandler,
                    EmbeddedImagesHandler, MultiQuestionHandler,
                    NonExistentTicketHandler, MaliciousHTMLHandler,
                    FAQMatchHandler, BelowConfidenceHandler,
                    MaintenanceModeHandler, ExpiredContextHandler,
                    BlockedUserHandler, PricingRequestHandler,
                    LegalTerminologyHandler, CompetitorMentionHandler,
                    SystemCommandsHandler, TimeoutHandler,
                )
                # Instantiate handlers in priority order
                self._edge_case_handlers = [
                    h() for h in [
                        EmptyQueryHandler, MaintenanceModeHandler,
                        BlockedUserHandler, MaliciousHTMLHandler,
                        TooLongQueryHandler, EmojisOnlyHandler,
                        CodeBlocksHandler, UnsupportedLanguageHandler,
                        EmbeddedImagesHandler, DuplicateQueryHandler,
                        MultiQuestionHandler, NonExistentTicketHandler,
                        FAQMatchHandler, PricingRequestHandler,
                        LegalTerminologyHandler, CompetitorMentionHandler,
                        SystemCommandsHandler, BelowConfidenceHandler,
                        ExpiredContextHandler, TimeoutHandler,
                    ]
                ]
            except Exception as exc:
                logger.warning("Edge case handlers init failed: %s", exc)
                self._edge_case_handlers = []
        return self._edge_case_handlers

    def _get_injection_detector(self):
        if self._injection_detector is None:
            try:
                from app.core.prompt_injection_defense import PromptInjectionDetector
                self._injection_detector = PromptInjectionDetector()
            except Exception as exc:
                logger.warning("PromptInjectionDetector init failed: %s", exc)
        return self._injection_detector

    def _get_signal_extractor(self):
        if self._signal_extractor is None:
            try:
                from app.core.signal_extraction import (
                    SignalExtractor, SignalExtractionRequest,
                )
                self._signal_extractor = SignalExtractor()
            except Exception as exc:
                logger.warning("SignalExtractor init failed: %s", exc)
        return self._signal_extractor

    def _get_classification_engine(self):
        if self._classification_engine is None:
            try:
                from app.core.classification_engine import ClassificationEngine
                self._classification_engine = ClassificationEngine()
            except Exception as exc:
                logger.warning("ClassificationEngine init failed: %s", exc)
        return self._classification_engine

    def _get_sentiment_analyzer(self):
        if self._sentiment_analyzer is None:
            try:
                from app.core.sentiment_engine import SentimentAnalyzer
                self._sentiment_analyzer = SentimentAnalyzer()
            except Exception as exc:
                logger.warning("SentimentAnalyzer init failed: %s", exc)
        return self._sentiment_analyzer

    def _get_smart_router(self):
        if self._smart_router is None:
            try:
                from app.core.smart_router import SmartRouter
                self._smart_router = SmartRouter()
            except Exception as exc:
                logger.warning("SmartRouter init failed: %s", exc)
        return self._smart_router

    def _get_technique_router(self):
        if self._technique_router is None:
            try:
                from app.core.technique_router import TechniqueRouter
                self._technique_router = TechniqueRouter()
            except Exception as exc:
                logger.warning("TechniqueRouter init failed: %s", exc)
        return self._technique_router

    def _get_rag_reranker(self):
        if self._rag_reranker is None:
            try:
                from app.core.rag_reranking import CrossEncoderReranker
                self._rag_reranker = CrossEncoderReranker()
            except Exception as exc:
                logger.warning("CrossEncoderReranker init failed: %s", exc)
        return self._rag_reranker

    def _get_response_generator(self):
        if self._response_generator is None:
            try:
                from app.core.response_generator import ResponseGenerator
                self._response_generator = ResponseGenerator(
                    redis_client=self._redis_client,
                )
            except Exception as exc:
                logger.warning("ResponseGenerator init failed: %s", exc)
        return self._response_generator

    def _get_clara_gate(self):
        if self._clara_gate is None:
            try:
                from app.core.clara_quality_gate import CLARAQualityGate
                self._clara_gate = CLARAQualityGate()
            except Exception as exc:
                logger.warning("CLARAQualityGate init failed: %s", exc)
        return self._clara_gate

    def _get_guardrails_engine(self):
        if self._guardrails_engine is None:
            try:
                from app.core.guardrails_engine import GuardrailsEngine
                self._guardrails_engine = GuardrailsEngine()
            except Exception as exc:
                logger.warning("GuardrailsEngine init failed: %s", exc)
        return self._guardrails_engine

    def _get_confidence_engine(self):
        if self._confidence_engine is None:
            try:
                from app.core.confidence_scoring_engine import (
                    ConfidenceScoringEngine,
                )
                self._confidence_engine = ConfidenceScoringEngine()
            except Exception as exc:
                logger.warning("ConfidenceScoringEngine init failed: %s", exc)
        return self._confidence_engine

    def _get_brand_voice_service(self, company_id: str):
        try:
            from app.services.brand_voice_service import BrandVoiceService
            # BrandVoiceService needs a db session, handled at call site
            return BrandVoiceService
        except ImportError:
            return None

    # ── Main Pipeline Entry Point ─────────────────────────────

    async def process(self, ctx: PipelineContext) -> PipelineResult:
        """Run the full AI processing pipeline.

        Executes 13 stages sequentially. Each stage has its own
        error handling — failures degrade gracefully (BC-012).

        Args:
            ctx: PipelineContext with input fields populated.

        Returns:
            PipelineResult with final response and all metadata.
        """
        start_time = time.time()
        logger.info(
            "AI Pipeline started: company_id=%s, variant=%s, query=%s",
            ctx.company_id, ctx.variant_type, ctx.query[:80],
        )

        # Stage 1: Edge Case Detection
        await self._run_stage("edge_case", ctx, self._stage_edge_case)

        # If edge case blocks processing, return early
        if ctx.is_edge_case and ctx.edge_case_action == "block":
            return self._build_result(ctx, start_time)

        # Stage 2: Prompt Injection Scan
        self._run_stage_sync("injection_scan", ctx, self._stage_injection_scan)

        # If injection blocked, return early
        if ctx.injection_blocked:
            return self._build_result(ctx, start_time)

        # Stage 3: Signal Extraction
        await self._run_stage("signal_extraction", ctx, self._stage_signal_extraction)

        # Stages 4-5: Classification + Sentiment (can run in parallel)
        await asyncio.gather(
            self._run_stage("classification", ctx, self._stage_classification),
            self._run_stage("sentiment", ctx, self._stage_sentiment),
        )

        # Stage 6-7: Routing (model + technique)
        self._run_stage_sync("smart_router", ctx, self._stage_smart_router)
        self._run_stage_sync("technique_router", ctx, self._stage_technique_router)

        # Stage 8: RAG Retrieval
        await self._run_stage("rag_retrieval", ctx, self._stage_rag_retrieval)

        # Stage 9: Response Generation
        await self._run_stage("response_generation", ctx, self._stage_response_generation)

        # Stage 10: CLARA Quality Gate
        await self._run_stage("clara_quality", ctx, self._stage_clara_quality)

        # If CLARA failed and has suggestions, re-generate once
        if not ctx.clara_passed and ctx.clara_suggestions_applied and ctx.raw_response:
            await self._run_stage(
                "response_regeneration", ctx, self._stage_response_generation,
            )

        # Stage 11: Output Guardrails
        self._run_stage_sync("guardrails", ctx, self._stage_guardrails)

        # If guardrails blocked, use safe fallback
        if ctx.guardrails_blocked:
            ctx.response_text = self._get_safe_fallback_response(ctx)
            ctx.stages_completed.append("safe_fallback")

        # Stage 12: Confidence Scoring
        self._run_stage_sync(
            "confidence_scoring", ctx, self._stage_confidence_scoring,
        )

        # Stage 13: Brand Voice
        self._run_stage_sync("brand_voice", ctx, self._stage_brand_voice)

        # Set final response
        ctx.final_response = ctx.response_text or ctx.raw_response or self._get_safe_fallback_response(ctx)

        return self._build_result(ctx, start_time)

    # ── Stage Execution Helpers ───────────────────────────────

    async def _run_stage(self, name: str, ctx: PipelineContext, stage_fn):
        """Run an async pipeline stage with timeout and error handling."""
        timeout = self.STAGE_TIMEOUTS.get(name, 10)
        try:
            await asyncio.wait_for(stage_fn(ctx), timeout=timeout)
            ctx.stages_completed.append(name)
        except asyncio.TimeoutError:
            logger.warning("Pipeline stage '%s' timed out after %ds", name, timeout)
            ctx.stages_failed.append(name)
        except Exception as exc:
            logger.error("Pipeline stage '%s' failed: %s", name, exc)
            ctx.stages_failed.append(name)
            ctx.error = str(exc)

    def _run_stage_sync(self, name: str, ctx: PipelineContext, stage_fn):
        """Run a sync pipeline stage with error handling."""
        try:
            stage_fn(ctx)
            ctx.stages_completed.append(name)
        except Exception as exc:
            logger.error("Pipeline stage '%s' failed: %s", name, exc)
            ctx.stages_failed.append(name)

    # ── Stage 1: Edge Case Detection ─────────────────────────

    async def _stage_edge_case(self, ctx: PipelineContext) -> None:
        """Detect edge cases that should short-circuit the pipeline."""
        handlers = self._get_edge_case_handlers()
        if not handlers:
            return

        context = {
            "company_id": ctx.company_id,
            "variant_type": ctx.variant_type,
            "conversation_history": ctx.conversation_history or [],
        }

        for handler in handlers:
            try:
                if handler.can_handle(ctx.query, context):
                    result = handler.handle(ctx.query, context)
                    if result and hasattr(result, "action"):
                        ctx.is_edge_case = True
                        ctx.edge_case_action = result.action.value if hasattr(result.action, "value") else str(result.action)
                        if hasattr(result, "response") and result.response:
                            ctx.edge_case_message = result.response
                        if ctx.edge_case_action == "block":
                            ctx.response_text = ctx.edge_case_message or "I cannot process this request."
                            return
                        break
            except Exception as exc:
                logger.debug("Edge case handler %s failed: %s", type(handler).__name__, exc)
                continue

    # ── Stage 2: Prompt Injection Scan ────────────────────────

    def _stage_injection_scan(self, ctx: PipelineContext) -> None:
        """Scan for prompt injection attacks."""
        detector = self._get_injection_detector()
        if not detector:
            return

        try:
            result = detector.scan(ctx.query, tenant_id=ctx.company_id, conversation_id=ctx.conversation_id)
            if result:
                if hasattr(result, "is_injection"):
                    ctx.injection_detected = result.is_injection
                if hasattr(result, "severity"):
                    ctx.injection_severity = result.severity or "none"
                if hasattr(result, "action"):
                    action = result.action if isinstance(result.action, str) else str(result.action)
                    ctx.injection_blocked = action in ("block", "reject", "BLOCK", "REJECT")
                if hasattr(result, "matches"):
                    ctx.injection_matches = [
                        {"pattern": m.pattern, "type": m.type, "severity": m.severity}
                        for m in (result.matches or [])
                    ]

                if ctx.injection_blocked:
                    ctx.response_text = (
                        "I noticed something unusual about your request. "
                        "I'm here to help with customer support questions. "
                        "Could you rephrase your question?"
                    )
                    logger.warning(
                        "Prompt injection blocked: company=%s, severity=%s",
                        ctx.company_id, ctx.injection_severity,
                    )
        except Exception as exc:
            logger.error("Injection scan failed: %s", exc)

    # ── Stage 3: Signal Extraction ────────────────────────────

    async def _stage_signal_extraction(self, ctx: PipelineContext) -> None:
        """Extract 10 signals for routing decisions."""
        extractor = self._get_signal_extractor()
        if not extractor:
            return

        try:
            from app.core.signal_extraction import SignalExtractionRequest
            request = SignalExtractionRequest(
                query=ctx.query,
                company_id=ctx.company_id,
                variant_type=ctx.variant_type,
                customer_tier=ctx.customer_metadata.get("tier", "free") if ctx.customer_metadata else "free",
                turn_count=len(ctx.conversation_history or []),
                conversation_history=[m.get("content", "") for m in ctx.conversation_history] if ctx.conversation_history else None,
                customer_metadata=ctx.customer_metadata,
            )
            signals = await extractor.extract(request)
            ctx.extracted_signals = signals.to_dict() if hasattr(signals, "to_dict") else {}

            # Build QuerySignals for TechniqueRouter
            if hasattr(extractor, "to_query_signals"):
                ctx.query_signals = extractor.to_query_signals(signals)
        except Exception as exc:
            logger.error("Signal extraction failed: %s", exc)

    # ── Stage 4: Intent Classification ────────────────────────

    async def _stage_classification(self, ctx: PipelineContext) -> None:
        """Classify the intent of the customer query."""
        engine = self._get_classification_engine()
        if not engine:
            return

        try:
            result = await engine.classify(
                ctx.query,
                context=ctx.extracted_signals,
                variant_type=ctx.variant_type,
            )
            if result:
                if hasattr(result, "primary_intent"):
                    ctx.intent_type = result.primary_intent or "general"
                if hasattr(result, "confidence"):
                    ctx.intent_confidence = result.confidence or 0.0
                if hasattr(result, "secondary_intents"):
                    ctx.secondary_intents = result.secondary_intents or []
        except Exception as exc:
            logger.error("Classification failed: %s", exc)

    # ── Stage 5: Sentiment Analysis ───────────────────────────

    async def _stage_sentiment(self, ctx: PipelineContext) -> None:
        """Analyze sentiment, frustration, emotion, urgency."""
        analyzer = self._get_sentiment_analyzer()
        if not analyzer:
            return

        try:
            result = await analyzer.analyze(
                ctx.query,
                context=ctx.extracted_signals,
                conversation_history=ctx.conversation_history,
            )
            if result:
                if hasattr(result, "frustration_score"):
                    ctx.frustration_score = result.frustration_score or 0.0
                if hasattr(result, "sentiment_score"):
                    ctx.sentiment_score = result.sentiment_score or 0.5
                if hasattr(result, "emotion"):
                    ctx.emotion = result.emotion
                if hasattr(result, "urgency"):
                    ctx.urgency_level = result.urgency or "normal"
                if hasattr(result, "tone_recommendation"):
                    ctx.tone_recommendation = result.tone_recommendation
                if hasattr(result, "customer_tier"):
                    ctx.customer_tier = result.customer_tier or "standard"
        except Exception as exc:
            logger.error("Sentiment analysis failed: %s", exc)

    # ── Stage 6: Smart Router (Model Selection) ───────────────

    def _stage_smart_router(self, ctx: PipelineContext) -> None:
        """Select the AI model based on query complexity and variant."""
        router = self._get_smart_router()
        if not router:
            ctx.selected_model = "gemini-2.0-flash"
            ctx.selected_provider = "google"
            ctx.selected_tier = "light"
            return

        try:
            result = router.route(
                ctx.query,
                context=ctx.extracted_signals,
                variant_type=ctx.variant_type,
            )
            if result:
                if hasattr(result, "model_id"):
                    ctx.selected_model = result.model_id
                if hasattr(result, "provider"):
                    ctx.selected_provider = result.provider
                if hasattr(result, "tier"):
                    ctx.selected_tier = result.tier.value if hasattr(result.tier, "value") else str(result.tier)
        except Exception as exc:
            logger.error("Smart routing failed: %s", exc)
            ctx.selected_model = "gemini-2.0-flash"
            ctx.selected_provider = "google"
            ctx.selected_tier = "light"

    # ── Stage 7: Technique Router ─────────────────────────────

    def _stage_technique_router(self, ctx: PipelineContext) -> None:
        """Select the reasoning technique based on signals."""
        router = self._get_technique_router()
        if not router or not ctx.query_signals:
            ctx.selected_technique = "crp"  # Tier 1 always-active
            ctx.technique_tier = "tier_1"
            return

        try:
            result = router.route(ctx.query_signals)
            if result:
                if hasattr(result, "technique"):
                    tech = result.technique
                    ctx.selected_technique = tech.value if hasattr(tech, "value") else str(tech)
                if hasattr(result, "tier"):
                    ctx.technique_tier = result.tier.value if hasattr(result.tier, "value") else str(result.tier)
                if hasattr(result, "fallback"):
                    fb = result.fallback
                    ctx.technique_fallback = fb.value if hasattr(fb, "value") else str(fb)
        except Exception as exc:
            logger.error("Technique routing failed: %s", exc)
            ctx.selected_technique = "crp"

    # ── Stage 8: RAG Retrieval + Reranking ────────────────────

    async def _stage_rag_retrieval(self, ctx: PipelineContext) -> None:
        """Retrieve relevant knowledge base chunks and rerank."""
        reranker = self._get_rag_reranker()
        if not reranker:
            return

        try:
            assembled = await reranker.rerank(
                query=ctx.query,
                chunks=[],
                strategy="auto",
                top_k=5,
                filters={
                    "company_id": ctx.company_id,
                    "variant_type": ctx.variant_type,
                },
            )
            if assembled:
                if hasattr(assembled, "context_text"):
                    ctx.rag_context = assembled.context_text or ""
                if hasattr(assembled, "to_dict"):
                    d = assembled.to_dict()
                    ctx.rag_chunks = d.get("chunks", [])
                    ctx.rag_citations = d.get("citations", [])
                ctx.rag_context_used = bool(ctx.rag_context)
        except Exception as exc:
            logger.error("RAG retrieval failed: %s", exc)

    # ── Stage 9: Response Generation ──────────────────────────

    async def _stage_response_generation(self, ctx: PipelineContext) -> None:
        """Generate AI response using selected model and technique."""
        generator = self._get_response_generator()
        if not generator:
            # Fallback: use raw response from a basic template
            if not ctx.response_text:
                ctx.response_text = self._get_template_response(ctx)
            return

        gen_start = time.time()
        try:
            from app.core.response_generator import ResponseGenerationRequest
            request = ResponseGenerationRequest(
                query=ctx.query,
                company_id=ctx.company_id,
                conversation_id=ctx.conversation_id,
                variant_type=ctx.variant_type,
                customer_id=ctx.customer_id,
                conversation_history=ctx.conversation_history,
                customer_metadata=ctx.customer_metadata,
                language=ctx.language,
                ticket_id=ctx.ticket_id,
                intent_type=ctx.intent_type,
            )
            result = await generator.generate(request)
            if result:
                if hasattr(result, "response_text"):
                    ctx.raw_response = result.response_text
                    ctx.response_text = result.response_text
                if hasattr(result, "confidence_score"):
                    # Use generation confidence as baseline
                    pass
                if hasattr(result, "rag_context_used"):
                    ctx.rag_context_used = result.rag_context_used
                if hasattr(result, "citations"):
                    ctx.rag_citations = result.citations or []
                if hasattr(result, "tokens_used"):
                    ctx.tokens_used = result.tokens_used or 0
                if hasattr(result, "generation_time_ms"):
                    ctx.generation_time_ms = result.generation_time_ms or 0.0
                if hasattr(result, "clara_passed"):
                    ctx.clara_passed = result.clara_passed
                if hasattr(result, "clara_score"):
                    ctx.clara_score = result.clara_score or 100.0
                if hasattr(result, "quality_issues"):
                    ctx.clara_issues = result.quality_issues or []
        except Exception as exc:
            logger.error("Response generation failed: %s", exc)
            if not ctx.response_text:
                ctx.response_text = self._get_template_response(ctx)

        ctx.generation_time_ms = (time.time() - gen_start) * 1000

    # ── Stage 10: CLARA Quality Gate ──────────────────────────

    async def _stage_clara_quality(self, ctx: PipelineContext) -> None:
        """Run 5-stage CLARA quality check on the response."""
        gate = self._get_clara_gate()
        if not gate or not ctx.response_text:
            return

        try:
            result = await gate.evaluate(
                ctx.response_text,
                ctx.query,
                context=ctx.extracted_signals or {},
                brand_config=None,
                strictness=None,
            )
            if result:
                if hasattr(result, "passed"):
                    ctx.clara_passed = result.passed
                if hasattr(result, "score"):
                    ctx.clara_score = result.score or 100.0
                if hasattr(result, "issues"):
                    ctx.clara_issues = result.issues or []
                if hasattr(result, "suggestions_applied"):
                    ctx.clara_suggestions_applied = result.suggestions_applied or False
                if hasattr(result, "response"):
                    # CLARA may have improved the response
                    improved = result.response
                    if improved and improved != ctx.response_text:
                        ctx.response_text = improved
                        ctx.clara_suggestions_applied = True
        except Exception as exc:
            logger.error("CLARA quality gate failed: %s", exc)

    # ── Stage 11: Output Guardrails ───────────────────────────

    def _stage_guardrails(self, ctx: PipelineContext) -> None:
        """Run guardrails check on the generated response."""
        engine = self._get_guardrails_engine()
        if not engine or not ctx.response_text:
            return

        try:
            report = engine.run_full_check(
                query=ctx.query,
                response=ctx.response_text,
                confidence=ctx.confidence_score,
                company_id=ctx.company_id,
                variant_type=ctx.variant_type,
            )
            if report:
                if hasattr(report, "passed"):
                    ctx.guardrails_passed = report.passed
                if hasattr(report, "passed") and not report.passed:
                    ctx.guardrails_blocked = True
                    if hasattr(report, "severity"):
                        ctx.guardrails_severity = report.severity or "high"
                if hasattr(report, "to_dict"):
                    ctx.guardrails_report = report.to_dict()
        except Exception as exc:
            logger.error("Guardrails check failed: %s", exc)

    # ── Stage 12: Confidence Scoring ──────────────────────────

    def _stage_confidence_scoring(self, ctx: PipelineContext) -> None:
        """Calculate calibrated confidence score."""
        engine = self._get_confidence_engine()
        if not engine or not ctx.response_text:
            ctx.confidence_score = 50.0  # Neutral default
            return

        try:
            result = engine.score_response(
                query=ctx.query,
                response=ctx.response_text,
                variant_type=ctx.variant_type,
            )
            if result:
                if hasattr(result, "overall_score"):
                    ctx.confidence_score = result.overall_score or 0.0
                if hasattr(result, "threshold"):
                    ctx.confidence_threshold = result.threshold or 75.0
                if hasattr(result, "auto_action"):
                    ctx.confidence_auto_action = result.auto_action or False

            # Determine auto-action based on variant thresholds
            thresholds = {"mini_parwa": 95, "parwa": 85, "parwa_high": 75}
            threshold = thresholds.get(ctx.variant_type, 75)
            ctx.confidence_auto_action = ctx.confidence_score >= threshold
            ctx.confidence_threshold = float(threshold)
        except Exception as exc:
            logger.error("Confidence scoring failed: %s", exc)
            ctx.confidence_score = 50.0

    # ── Stage 13: Brand Voice ─────────────────────────────────

    def _stage_brand_voice(self, ctx: PipelineContext) -> None:
        """Apply brand voice settings to the final response."""
        if not ctx.response_text or not ctx.company_id:
            return

        try:
            from app.services.jarvis_service import jarvis_merge_with_brand_voice as _merge_bv
            result = _merge_bv(ctx.company_id, ctx.response_text)
            if result and isinstance(result, dict):
                merged = result.get("merged_response") or result.get("response")
                if merged and merged != ctx.response_text:
                    ctx.response_text = merged
                    ctx.brand_voice_applied = True
        except Exception as exc:
            logger.debug("Brand voice merge failed: %s", exc)

    # ── Result Building ───────────────────────────────────────

    def _build_result(self, ctx: PipelineContext, start_time: float) -> PipelineResult:
        """Build the final PipelineResult from PipelineContext."""
        elapsed_ms = (time.time() - start_time) * 1000
        ctx.pipeline_time_ms = elapsed_ms

        return PipelineResult(
            response=ctx.final_response or ctx.response_text or ctx.edge_case_message or "",
            confidence_score=ctx.confidence_score,
            auto_action=ctx.confidence_auto_action and ctx.guardrails_passed and ctx.clara_passed,
            intent_type=ctx.intent_type,
            frustration_score=ctx.frustration_score,
            sentiment_score=ctx.sentiment_score,
            urgency_level=ctx.urgency_level,
            technique_used=ctx.selected_technique,
            model_used=ctx.selected_model,
            rag_context_used=ctx.rag_context_used,
            citations=ctx.rag_citations,
            is_edge_case=ctx.is_edge_case,
            injection_blocked=ctx.injection_blocked,
            guardrails_blocked=ctx.guardrails_blocked,
            clara_passed=ctx.clara_passed,
            pipeline_time_ms=elapsed_ms,
            stages_completed=ctx.stages_completed,
            stages_failed=ctx.stages_failed,
            metadata={
                "selected_provider": ctx.selected_provider,
                "selected_tier": ctx.selected_tier,
                "technique_tier": ctx.technique_tier,
                "technique_fallback": ctx.technique_fallback,
                "intent_confidence": ctx.intent_confidence,
                "secondary_intents": ctx.secondary_intents,
                "emotion": ctx.emotion,
                "tone_recommendation": ctx.tone_recommendation,
                "customer_tier": ctx.customer_tier,
                "clara_score": ctx.clara_score,
                "clara_issues": ctx.clara_issues,
                "guardrails_severity": ctx.guardrails_severity,
                "confidence_threshold": ctx.confidence_threshold,
                "rag_chunks_count": len(ctx.rag_chunks),
                "tokens_used": ctx.tokens_used,
                "generation_time_ms": ctx.generation_time_ms,
                "injection_severity": ctx.injection_severity,
                "injection_matches": ctx.injection_matches,
                "brand_voice_applied": ctx.brand_voice_applied,
                "edge_case_action": ctx.edge_case_action,
                "error": ctx.error,
            },
        )

    # ── Fallback Responses ────────────────────────────────────

    def _get_safe_fallback_response(self, ctx: PipelineContext) -> str:
        """Generate a safe fallback when guardrails block the response."""
        responses = {
            "high": "I understand your concern. Let me connect you with a team member who can better assist you with this.",
            "critical": "For your security, I'm transferring this to a specialized team member. Please hold.",
        }
        severity = ctx.guardrails_severity or "none"
        return responses.get(severity, "I appreciate your patience. A team member will follow up with you shortly on this matter.")

    def _get_template_response(self, ctx: PipelineContext) -> str:
        """Generate a template-based response when AI generation fails."""
        templates = {
            "refund": "Thank you for reaching out about your refund. I'd be happy to help. Could you please provide your order number so I can look into this for you?",
            "technical": "I'm sorry to hear you're experiencing a technical issue. Could you describe what's happening in more detail? This will help me provide the most accurate assistance.",
            "billing": "I understand you have a billing question. Let me help you with that. Could you share any relevant details about the charge or invoice?",
            "complaint": "I'm truly sorry for the inconvenience. Your feedback is important to us. Could you tell me more about what happened so we can make things right?",
            "feature_request": "That's a great suggestion! I'll make sure your feedback is recorded. Is there anything specific you'd like this feature to accomplish?",
            "general": "Thank you for reaching out! I'm here to help. Could you provide a bit more detail about what you need assistance with?",
        }
        return templates.get(ctx.intent_type, templates["general"])


# ── Convenience Function ─────────────────────────────────────────


async def process_ai_message(
    query: str,
    company_id: str,
    conversation_id: str,
    variant_type: str = "parwa",
    customer_id: Optional[str] = None,
    conversation_history: Optional[List[dict]] = None,
    customer_metadata: Optional[dict] = None,
    language: str = "en",
    ticket_id: Optional[str] = None,
) -> PipelineResult:
    """Process a customer message through the full AI pipeline.

    Convenience wrapper around AIPipeline.process().

    Args:
        query: Customer's message text.
        company_id: Tenant identifier (BC-001).
        conversation_id: Conversation/session identifier.
        variant_type: PARWA variant (mini_parwa/parwa/parwa_high).
        customer_id: Optional customer identifier.
        conversation_history: Previous messages for context.
        customer_metadata: Customer profile data.
        language: Message language (default: en).
        ticket_id: Optional ticket for draft co-pilot mode.

    Returns:
        PipelineResult with response and full metadata.
    """
    pipeline = AIPipeline()
    ctx = PipelineContext(
        query=query,
        company_id=company_id,
        conversation_id=conversation_id,
        variant_type=variant_type,
        customer_id=customer_id,
        conversation_history=conversation_history,
        customer_metadata=customer_metadata,
        language=language,
        ticket_id=ticket_id,
    )
    return await pipeline.process(ctx)
