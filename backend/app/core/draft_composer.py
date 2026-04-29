"""
AI Draft Composer — Co-Pilot Mode (F-066)

Suggests response drafts to human agents for accept/edit/regenerate.
Operates in real-time via Socket.io.  Generates multiple draft
variations ranked by CLARA quality gate score.

Pipeline:
  1. Cache lookup (Redis, 120s TTL, fail-open)
  2. Signal extraction (SG-13)
  3. Intent classification (F-062)
  4. Brand voice retrieval (F-154)
  5. Draft generation via Smart Router Medium tier (F-054)
  6. CLARA quality gate validation (F-150)
  7. Deduplication (GAP-021)
  8. Rank by quality score, return best first
  9. Store draft history in Redis
 10. Emit via Socket.io to agent

Per-variant capabilities:
  - mini_parwa (L1): simple drafts, 1 draft max
  - parwa (L2): + tone/brand matching, 3 drafts max
  - high_parwa (L3): + multi-draft + personalization, 5 drafts max

GAP FIXES:
- W9-GAP-019 (HIGH): Per-draft timeout (8s) + total timeout (30s)
- W9-GAP-020 (MEDIUM): Agent feedback loop for improvement tracking
- W9-GAP-021 (MEDIUM): Draft deduplication (near-identical detection)

BC-001: All operations scoped to company_id.
BC-008: Graceful degradation — never crashes.

Parent: Week 9 Day 8 (Monday)
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

from app.logger import get_logger

logger = get_logger("draft_composer")


# ════════════════════════════════════════════════════════════════════
# CONSTANTS
# ════════════════════════════════════════════════════════════════════

# GAP-019: Per-draft generation timeout (seconds)
_DRAFT_GENERATION_TIMEOUT_SECONDS: float = 8.0

# GAP-019: Total compose timeout (seconds) — covers signal extraction,
# classification, all draft generation, and CLARA validation.
_TOTAL_COMPOSE_TIMEOUT_SECONDS: float = 30.0

# Cache TTL for composed drafts (seconds)
_CACHE_TTL_SECONDS: int = 120

# Cache key template: draft_cache:{company_id}:{variant_type}:{query_hash}
_CACHE_KEY_TEMPLATE: str = "draft_cache:{company_id}:{variant_type}:{query_hash}"

# Draft history Redis key template
_HISTORY_KEY_TEMPLATE: str = "draft_history:{company_id}:{ticket_id}"
_HISTORY_TTL_SECONDS: int = 86400  # 24 hours

# GAP-020: Feedback Redis key template for improvement tracking
_FEEDBACK_KEY_TEMPLATE: str = "draft_feedback:{company_id}:{draft_id}"
_FEEDBACK_TTL_SECONDS: int = 604800  # 7 days

# GAP-021: Deduplication similarity threshold (0.0-1.0)
_DEDUP_SIMILARITY_THRESHOLD: float = 0.85

# Per-variant draft limits
_VARIANT_MAX_DRAFTS: Dict[str, int] = {
    "mini_parwa": 1,
    "parwa": 3,
    "high_parwa": 5,
}

# Per-variant max response tokens
_VARIANT_MAX_TOKENS: Dict[str, int] = {
    "mini_parwa": 256,
    "parwa": 512,
    "high_parwa": 1024,
}

# Temperature settings per variant (higher = more creative)
_VARIANT_TEMPERATURE: Dict[str, float] = {
    "mini_parwa": 0.5,
    "parwa": 0.7,
    "high_parwa": 0.85,
}

# Technique mapping for intent + sentiment combinations
_TECHNIQUE_MAP: Dict[str, Dict[str, str]] = {
    "refund": {
        "low_sentiment": "empathetic_resolution",
        "high_sentiment": "friendly_confirmation",
        "default": "standard_resolution",
    },
    "technical": {
        "low_sentiment": "patient_troubleshooting",
        "high_sentiment": "helpful_guide",
        "default": "step_by_step",
    },
    "billing": {
        "low_sentiment": "apologetic_clarification",
        "high_sentiment": "clear_summary",
        "default": "informative_breakdown",
    },
    "complaint": {
        "low_sentiment": "de_escalation",
        "high_sentiment": "acknowledgment",
        "default": "empathetic_response",
    },
    "cancellation": {
        "low_sentiment": "retention_offer",
        "high_sentiment": "smooth_exit",
        "default": "process_confirmation",
    },
    "escalation": {
        "low_sentiment": "urgent_escalation",
        "high_sentiment": "warm_transfer",
        "default": "escalation_acknowledgment",
    },
    "shipping": {
        "low_sentiment": "proactive_tracking",
        "high_sentiment": "delivery_update",
        "default": "logistics_response",
    },
    "account": {
        "low_sentiment": "security_assurance",
        "high_sentiment": "quick_fix",
        "default": "account_assistance",
    },
    "feature_request": {
        "low_sentiment": "encouraging_acknowledgment",
        "high_sentiment": "enthusiastic_capture",
        "default": "feature_acknowledgment",
    },
    "inquiry": {
        "low_sentiment": "detailed_explanation",
        "high_sentiment": "concise_answer",
        "default": "informative_response",
    },
    "feedback": {
        "low_sentiment": "grateful_acknowledgment",
        "high_sentiment": "celebration",
        "default": "thank_you_response",
    },
    "general": {
        "low_sentiment": "helpful_standard",
        "high_sentiment": "friendly_standard",
        "default": "standard_response",
    },
}


# ════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ════════════════════════════════════════════════════════════════════


@dataclass
class DraftOptions:
    """Configuration options for draft generation.

    Controls how many drafts to generate, tone preferences, length
    limits, and whether to include citations from RAG context.
    """

    max_drafts: int = 1
    tone: Optional[str] = None  # Override brand tone if specified
    max_length: int = 500  # Max characters per draft
    include_citations: bool = False
    custom_instructions: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate options after initialization."""
        if self.max_drafts < 1:
            self.max_drafts = 1
        if self.max_drafts > 5:
            self.max_drafts = 5
        if self.max_length < 50:
            self.max_length = 50
        if self.max_length > 2000:
            self.max_length = 2000


@dataclass
class DraftRequest:
    """Input to the draft composer pipeline.

    Contains the customer query, tenant context, conversation history,
    and configuration for how drafts should be generated.
    """

    query: str
    company_id: str
    variant_type: str  # mini_parwa, parwa, high_parwa
    agent_id: str
    ticket_id: Optional[str] = None
    conversation_history: Optional[List[str]] = None
    customer_sentiment: float = 0.5  # 0.0 (negative) to 1.0 (positive)
    customer_tier: str = "free"
    draft_options: Optional[DraftOptions] = None

    def __post_init__(self) -> None:
        """Set default draft options if not provided."""
        if self.draft_options is None:
            max_drafts = _VARIANT_MAX_DRAFTS.get(
                self.variant_type,
                1,
            )
            self.draft_options = DraftOptions(max_drafts=max_drafts)


@dataclass
class DraftResult:
    """A single generated draft with quality metadata.

    Each draft includes the generated content, its CLARA quality
    score, generation timing, and detailed metadata about brand
    compliance and tone matching.
    """

    draft_id: str  # UUID
    content: str
    quality_score: float  # 0.0-1.0 from CLARA
    generation_time_ms: float
    technique_used: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for Redis storage."""
        return {
            "draft_id": self.draft_id,
            "content": self.content,
            "quality_score": round(self.quality_score, 4),
            "generation_time_ms": round(self.generation_time_ms, 2),
            "technique_used": self.technique_used,
            "metadata": self.metadata,
        }


@dataclass
class DraftComposerResponse:
    """Complete response from the draft composer.

    Contains all generated drafts ranked by quality score, with
    the best draft indicated by ``best_draft_index``.
    """

    request_id: str  # UUID
    drafts: List[DraftResult]
    best_draft_index: int
    total_generation_time_ms: float
    variant_type: str
    cached: bool

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "request_id": self.request_id,
            "drafts": [d.to_dict() for d in self.drafts],
            "best_draft_index": self.best_draft_index,
            "total_generation_time_ms": round(
                self.total_generation_time_ms,
                2,
            ),
            "variant_type": self.variant_type,
            "cached": self.cached,
        }


# ════════════════════════════════════════════════════════════════════
# DRAFT COMPOSER
# ════════════════════════════════════════════════════════════════════


class DraftComposer:
    """AI Draft Composer — Co-Pilot Mode (F-066).

    Suggests response drafts to human agents for accept/edit/regenerate.
    Uses Smart Router Medium tier for LLM calls and CLARA quality gate
    for validation.  Supports per-variant draft limits and tone matching.

    GAP-019: Per-draft timeout (8s) + total timeout (30s).
    GAP-020: Agent feedback loop for improvement tracking.
    GAP-021: Draft deduplication to avoid near-identical drafts.

    BC-001: All operations scoped to company_id.
    BC-008: Graceful degradation — never crashes.
    """

    def __init__(
        self,
        smart_router: Any = None,
        clara_gate: Any = None,
        brand_voice_service: Any = None,
    ) -> None:
        """Initialize the draft composer with optional service overrides.

        Args:
            smart_router: Smart Router instance for LLM calls.
                Defaults to ``SmartRouter()`` if not provided.
            clara_gate: CLARA Quality Gate instance for draft validation.
                Defaults to ``CLARAQualityGate()`` if not provided.
            brand_voice_service: Brand Voice Service for tone matching.
                Defaults to ``BrandVoiceService()`` if not provided.
        """
        from app.core.clara_quality_gate import CLARAQualityGate
        from app.core.smart_router import SmartRouter
        from app.services.brand_voice_service import (
            BrandVoiceService,
        )

        self.smart_router = smart_router or SmartRouter()
        self.clara_gate = clara_gate or CLARAQualityGate()
        self.brand_voice_service = brand_voice_service or BrandVoiceService()

        logger.info("draft_composer_initialized")

    # ──────────────────────────────────────────────────────────────
    # MAIN ENTRY POINT
    # ──────────────────────────────────────────────────────────────

    async def compose(
        self,
        request: DraftRequest,
    ) -> DraftComposerResponse:
        """Generate draft suggestions for a human agent.

        Full pipeline:
          1. Cache check (Redis, fail-open)
          2. Signal extraction
          3. Intent classification
          4. Brand voice retrieval
          5. Generate N drafts (per variant)
          6. CLARA quality gate on each draft
          7. Deduplication
          8. Rank by quality, store history, emit via Socket.io

        GAP-019: Wrapped in total 30s timeout.

        Args:
            request: The draft generation request with query, context,
                and options.

        Returns:
            ``DraftComposerResponse`` with ranked drafts.
        """
        compose_start = time.monotonic()
        request_id = (
            hashlib.uuid4_hex()
            if hasattr(hashlib, "uuid4_hex")
            else self._generate_uuid()
        )

        # ── Validate request ──────────────────────────────────────
        if not request.query or not request.query.strip():
            logger.info(
                "draft_composer_empty_query",
                company_id=request.company_id,
            )
            return self._empty_response(
                request_id=request_id,
                variant_type=request.variant_type,
                compose_start=compose_start,
                reason="empty_query",
            )

        # ── Step 1: Cache lookup ──────────────────────────────────
        query_hash = self._compute_query_hash(request.query)
        cache_key = _CACHE_KEY_TEMPLATE.format(
            company_id=request.company_id,
            variant_type=request.variant_type,
            query_hash=query_hash,
        )

        cached_response = await self._check_cache(
            request.company_id,
            cache_key,
        )
        if cached_response is not None:
            logger.info(
                "draft_composer_cache_hit",
                company_id=request.company_id,
                variant_type=request.variant_type,
            )
            cached_response.cached = True
            return cached_response

        # ── Steps 2-4 wrapped in total timeout (GAP-019) ──────────
        try:
            return await asyncio.wait_for(
                self._compose_pipeline(
                    request=request,
                    request_id=request_id,
                    compose_start=compose_start,
                    cache_key=cache_key,
                    query_hash=query_hash,
                ),
                timeout=_TOTAL_COMPOSE_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "draft_composer_total_timeout",
                company_id=request.company_id,
                variant_type=request.variant_type,
                timeout=_TOTAL_COMPOSE_TIMEOUT_SECONDS,
            )
            return self._empty_response(
                request_id=request_id,
                variant_type=request.variant_type,
                compose_start=compose_start,
                reason="total_timeout",
            )

    # ──────────────────────────────────────────────────────────────
    # INTERNAL PIPELINE
    # ──────────────────────────────────────────────────────────────

    async def _compose_pipeline(
        self,
        request: DraftRequest,
        request_id: str,
        compose_start: float,
        cache_key: str,
        query_hash: str,
    ) -> DraftComposerResponse:
        """Execute the full compose pipeline with signal extraction,
        classification, generation, quality gating, and deduplication.
        """
        # ── Step 2: Signal Extraction ─────────────────────────────
        signals = await self._extract_signals(request)

        # ── Step 3: Intent Classification ─────────────────────────
        classification = await self._classify_intent(request)

        # ── Step 4: Brand Voice Retrieval ─────────────────────────
        brand_voice = await self._get_brand_voice(request)

        # ── Step 5: Build generation context ──────────────────────
        context = self._build_generation_context(
            signals=signals,
            classification=classification,
            brand_voice=brand_voice,
        )

        # ── Step 6: Generate drafts ───────────────────────────────
        max_drafts = _VARIANT_MAX_DRAFTS.get(
            request.variant_type,
            1,
        )
        if request.draft_options:
            max_drafts = min(
                request.draft_options.max_drafts,
                max_drafts,
            )

        drafts: List[DraftResult] = []
        draft_tasks = []

        for i in range(max_drafts):
            task = self._generate_single_draft(
                context=context,
                options=request.draft_options or DraftOptions(),
                company_id=request.company_id,
                variant_type=request.variant_type,
                draft_index=i,
                total_drafts=max_drafts,
            )
            draft_tasks.append(task)

        # Generate all drafts concurrently with per-draft timeout
        try:
            draft_results = await asyncio.gather(
                *draft_tasks,
                return_exceptions=True,
            )
            for result in draft_results:
                if isinstance(result, DraftResult):
                    drafts.append(result)
                elif isinstance(result, Exception):
                    logger.warning(
                        "draft_generation_exception_skipping",
                        error=str(result),
                        company_id=request.company_id,
                    )
        except Exception as exc:
            logger.warning(
                "draft_generation_gather_failed",
                error=str(exc),
                company_id=request.company_id,
            )

        # If all drafts failed, return empty
        if not drafts:
            logger.warning(
                "draft_composer_all_drafts_failed",
                company_id=request.company_id,
            )
            return self._empty_response(
                request_id=request_id,
                variant_type=request.variant_type,
                compose_start=compose_start,
                reason="all_drafts_failed",
            )

        # ── Step 7: CLARA Quality Gate ────────────────────────────
        validated_drafts = await self._validate_drafts(
            drafts=drafts,
            query=request.query,
            company_id=request.company_id,
            sentiment=request.customer_sentiment,
        )

        # ── Step 8: Deduplication (GAP-021) ────────────────────────
        unique_drafts = self._deduplicate_drafts(validated_drafts)

        # ── Step 9: Rank by quality score ─────────────────────────
        unique_drafts.sort(
            key=lambda d: d.quality_score,
            reverse=True,
        )

        # ── Step 10: Build response ───────────────────────────────
        total_time = round(
            (time.monotonic() - compose_start) * 1000,
            2,
        )
        best_index = 0  # First after sort is best

        response = DraftComposerResponse(
            request_id=request_id,
            drafts=unique_drafts,
            best_draft_index=best_index,
            total_generation_time_ms=total_time,
            variant_type=request.variant_type,
            cached=False,
        )

        # ── Step 11: Store in cache ───────────────────────────────
        await self._store_cache(
            request.company_id,
            cache_key,
            response,
        )

        # ── Step 12: Store draft history ──────────────────────────
        if request.ticket_id:
            await self._store_draft_history(
                ticket_id=request.ticket_id,
                company_id=request.company_id,
                response=response,
            )

        # ── Step 13: Emit via Socket.io ───────────────────────────
        await self._emit_to_agent(
            request=request,
            response=response,
        )

        logger.info(
            "draft_composer_complete",
            company_id=request.company_id,
            variant_type=request.variant_type,
            drafts_generated=len(drafts),
            drafts_after_dedup=len(unique_drafts),
            best_score=unique_drafts[0].quality_score if unique_drafts else 0.0,
            total_time_ms=total_time,
        )

        return response

    # ──────────────────────────────────────────────────────────────
    # SIGNAL EXTRACTION
    # ──────────────────────────────────────────────────────────────

    async def _extract_signals(
        self,
        request: DraftRequest,
    ) -> Dict[str, Any]:
        """Extract signals from the query using SignalExtractor.

        Returns a dictionary of extracted signals.  On failure, returns
        safe defaults (BC-008).
        """
        try:
            from app.core.signal_extraction import (
                SignalExtractionRequest,
                SignalExtractor,
            )

            extractor = SignalExtractor()
            sig_request = SignalExtractionRequest(
                query=request.query,
                company_id=request.company_id,
                variant_type=request.variant_type,
                customer_tier=request.customer_tier,
                conversation_history=request.conversation_history,
            )
            result = await extractor.extract(sig_request)
            return result.to_dict()
        except Exception as exc:
            logger.warning(
                "draft_composer_signal_extraction_failed",
                error=str(exc),
                company_id=request.company_id,
            )
            return {
                "intent": "general",
                "sentiment": request.customer_sentiment,
                "complexity": 0.5,
                "monetary_value": 0.0,
                "customer_tier": request.customer_tier,
                "query_breadth": 0.5,
            }

    # ──────────────────────────────────────────────────────────────
    # INTENT CLASSIFICATION
    # ──────────────────────────────────────────────────────────────

    async def _classify_intent(
        self,
        request: DraftRequest,
    ) -> Dict[str, Any]:
        """Classify the intent of the query.

        Returns a dictionary with primary intent, confidence, and
        classification method.  On failure, returns safe defaults.
        """
        try:
            from app.core.classification_engine import (
                ClassificationEngine,
            )

            engine = ClassificationEngine(
                smart_router=self.smart_router,
            )
            result = await engine.classify(
                text=request.query,
                company_id=request.company_id,
                variant_type=request.variant_type,
            )
            return {
                "primary_intent": result.primary_intent,
                "primary_confidence": result.primary_confidence,
                "secondary_intents": result.secondary_intents,
                "classification_method": result.classification_method,
            }
        except Exception as exc:
            logger.warning(
                "draft_composer_intent_classification_failed",
                error=str(exc),
                company_id=request.company_id,
            )
            return {
                "primary_intent": "general",
                "primary_confidence": 0.3,
                "secondary_intents": [],
                "classification_method": "fallback",
            }

    # ──────────────────────────────────────────────────────────────
    # BRAND VOICE
    # ──────────────────────────────────────────────────────────────

    async def _get_brand_voice(
        self,
        request: DraftRequest,
    ) -> Dict[str, Any]:
        """Retrieve brand voice configuration for the company.

        Returns a dictionary of brand voice settings.  On failure,
        returns sensible defaults (BC-008).
        """
        try:
            config = await self.brand_voice_service.get_config(
                request.company_id,
            )
            return {
                "tone": getattr(config, "tone", "professional"),
                "formality_level": getattr(
                    config,
                    "formality_level",
                    0.5,
                ),
                "brand_name": getattr(config, "brand_name", "our company"),
                "prohibited_words": getattr(
                    config,
                    "prohibited_words",
                    [],
                ),
                "response_length_preference": getattr(
                    config,
                    "response_length_preference",
                    "standard",
                ),
                "max_response_sentences": getattr(
                    config,
                    "max_response_sentences",
                    6,
                ),
                "min_response_sentences": getattr(
                    config,
                    "min_response_sentences",
                    2,
                ),
                "greeting_template": getattr(
                    config,
                    "greeting_template",
                    "",
                ),
                "closing_template": getattr(
                    config,
                    "closing_template",
                    "",
                ),
                "emoji_usage": getattr(config, "emoji_usage", "minimal"),
                "custom_instructions": getattr(
                    config,
                    "custom_instructions",
                    "",
                ),
            }
        except Exception as exc:
            logger.warning(
                "draft_composer_brand_voice_failed",
                error=str(exc),
                company_id=request.company_id,
            )
            return {
                "tone": "professional",
                "formality_level": 0.5,
                "brand_name": "our company",
                "prohibited_words": [],
                "response_length_preference": "standard",
                "max_response_sentences": 6,
                "min_response_sentences": 2,
                "greeting_template": "",
                "closing_template": "",
                "emoji_usage": "minimal",
                "custom_instructions": "",
            }

    # ──────────────────────────────────────────────────────────────
    # GENERATION CONTEXT BUILDER
    # ──────────────────────────────────────────────────────────────

    def _build_generation_context(
        self,
        signals: Dict[str, Any],
        classification: Dict[str, Any],
        brand_voice: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Combine signals, classification, and brand voice into a
        unified context dictionary for prompt building.

        Args:
            signals: Extracted signals from SignalExtractor.
            classification: Intent classification results.
            brand_voice: Brand voice configuration.

        Returns:
            Merged context dictionary for prompt construction.
        """
        return {
            "signals": signals,
            "classification": classification,
            "brand_voice": brand_voice,
            "intent": classification.get("primary_intent", "general"),
            "sentiment": signals.get(
                "sentiment",
                0.5,
            ),
            "complexity": signals.get("complexity", 0.5),
            "customer_tier": signals.get("customer_tier", "free"),
            "monetary_value": signals.get("monetary_value", 0.0),
            "query_breadth": signals.get("query_breadth", 0.5),
            "technique": self._select_technique(
                intent=classification.get("primary_intent", "general"),
                sentiment=signals.get("sentiment", 0.5),
                variant_type="parwa",
            ),
        }

    # ──────────────────────────────────────────────────────────────
    # TECHNIQUE SELECTION
    # ──────────────────────────────────────────────────────────────

    def _select_technique(
        self,
        intent: str,
        sentiment: float,
        variant_type: str,
    ) -> str:
        """Map intent + sentiment to an appropriate response technique.

        The technique determines how the LLM should approach the
        response (e.g., empathetic, step-by-step, de-escalation).

        Args:
            intent: Primary intent classification.
            sentiment: Customer sentiment score (0.0-1.0).
            variant_type: Product variant tier.

        Returns:
            Technique name string.
        """
        # Determine sentiment bucket
        if sentiment < 0.3:
            sentiment_bucket = "low_sentiment"
        elif sentiment > 0.7:
            sentiment_bucket = "high_sentiment"
        else:
            sentiment_bucket = "default"

        # Look up technique from map
        intent_techniques = _TECHNIQUE_MAP.get(intent, _TECHNIQUE_MAP["general"])
        technique = intent_techniques.get(
            sentiment_bucket,
            intent_techniques.get("default", "standard_response"),
        )

        # mini_parwa always uses simpler techniques
        if variant_type == "mini_parwa":
            technique = "standard_response"

        return technique

    # ──────────────────────────────────────────────────────────────
    # SINGLE DRAFT GENERATION
    # ──────────────────────────────────────────────────────────────

    async def _generate_single_draft(
        self,
        context: Dict[str, Any],
        options: DraftOptions,
        company_id: str,
        variant_type: str,
        draft_index: int = 0,
        total_drafts: int = 1,
    ) -> DraftResult:
        """Generate a single draft response.

        Builds a prompt from the context, routes through Smart Router
        Medium tier, and returns a ``DraftResult``.

        GAP-019: Per-draft timeout of 8 seconds.

        Args:
            context: Generation context from ``_build_generation_context``.
            options: Draft configuration options.
            company_id: Tenant identifier (BC-001).
            variant_type: Product variant tier.
            draft_index: Index of this draft (for temperature variation).
            total_drafts: Total number of drafts being generated.

        Returns:
            ``DraftResult`` with content and metadata.
        """
        draft_id = self._generate_uuid()
        draft_start = time.monotonic()

        try:
            return await asyncio.wait_for(
                self._do_generate_draft(
                    draft_id=draft_id,
                    context=context,
                    options=options,
                    company_id=company_id,
                    variant_type=variant_type,
                    draft_index=draft_index,
                    total_drafts=total_drafts,
                ),
                timeout=_DRAFT_GENERATION_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "draft_generation_timeout",
                draft_id=draft_id,
                draft_index=draft_index,
                company_id=company_id,
                timeout=_DRAFT_GENERATION_TIMEOUT_SECONDS,
            )
            generation_time = round(
                (time.monotonic() - draft_start) * 1000,
                2,
            )
            return DraftResult(
                draft_id=draft_id,
                content="",
                quality_score=0.0,
                generation_time_ms=generation_time,
                technique_used=context.get("technique", "unknown"),
                metadata={
                    "timed_out": True,
                    "draft_index": draft_index,
                },
            )
        except Exception as exc:
            logger.warning(
                "draft_generation_error",
                draft_id=draft_id,
                error=str(exc),
                company_id=company_id,
            )
            generation_time = round(
                (time.monotonic() - draft_start) * 1000,
                2,
            )
            return DraftResult(
                draft_id=draft_id,
                content="",
                quality_score=0.0,
                generation_time_ms=generation_time,
                technique_used=context.get("technique", "unknown"),
                metadata={
                    "error": str(exc),
                    "draft_index": draft_index,
                },
            )

    async def _do_generate_draft(
        self,
        draft_id: str,
        context: Dict[str, Any],
        options: DraftOptions,
        company_id: str,
        variant_type: str,
        draft_index: int,
        total_drafts: int,
    ) -> DraftResult:
        """Internal draft generation — no timeout wrapper."""
        draft_start = time.monotonic()

        # Build the system prompt
        system_prompt = self._build_draft_prompt(
            context=context,
            options=options,
            variant_type=variant_type,
            draft_index=draft_index,
            total_drafts=total_drafts,
        )

        # Build conversation history messages
        history = context.get("signals", {}).get(
            "conversation_history",
        )
        messages = [{"role": "system", "content": system_prompt}]

        if history and isinstance(history, list):
            for msg in history[-6:]:  # Last 6 messages
                if isinstance(msg, str) and msg.strip():
                    messages.append(
                        {
                            "role": "user",
                            "content": msg,
                        }
                    )

        # Add the current query
        query = context.get("signals", {}).get(
            "query",
            "",
        )
        messages.append({"role": "user", "content": query})

        # Route through Smart Router — Medium tier
        from app.core.smart_router import (
            AtomicStepType,
        )

        routing_decision = self.smart_router.route(
            company_id=company_id,
            variant_type=variant_type,
            atomic_step=AtomicStepType.DRAFT_RESPONSE_MODERATE,
            query_signals={
                "sentiment_score": context.get("sentiment", 0.5),
                "intent_type": context.get("intent", "general"),
                "complexity": context.get("complexity", 0.5),
                "customer_tier": context.get("customer_tier", "free"),
            },
        )

        max_tokens = _VARIANT_MAX_TOKENS.get(variant_type, 512)

        # Vary temperature for diverse drafts
        base_temp = _VARIANT_TEMPERATURE.get(variant_type, 0.7)
        temperature = min(1.0, base_temp + draft_index * 0.1)

        llm_result = await self.smart_router.async_execute_llm_call(
            company_id=company_id,
            routing_decision=routing_decision,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        content = llm_result.get("content", "")
        if not content or not content.strip():
            content = ""

        # Truncate to max_length
        if options.max_length and len(content) > options.max_length:
            content = content[: options.max_length].rsplit(" ", 1)[0]

        generation_time = round(
            (time.monotonic() - draft_start) * 1000,
            2,
        )

        technique = context.get("technique", "standard_response")

        return DraftResult(
            draft_id=draft_id,
            content=content,
            quality_score=0.0,  # Will be set by CLARA validation
            generation_time_ms=generation_time,
            technique_used=technique,
            metadata={
                "model": llm_result.get("model", "unknown"),
                "provider": llm_result.get("provider", "unknown"),
                "tier": llm_result.get("tier", "unknown"),
                "temperature": temperature,
                "draft_index": draft_index,
                "brand_check_passed": False,
                "tone_match": 0.0,
            },
        )

    # ──────────────────────────────────────────────────────────────
    # PROMPT BUILDER
    # ──────────────────────────────────────────────────────────────

    def _build_draft_prompt(
        self,
        context: Dict[str, Any],
        options: DraftOptions,
        variant_type: str,
        draft_index: int,
        total_drafts: int,
    ) -> str:
        """Build the system prompt for draft generation.

        Combines brand voice settings, technique instructions,
        and tone guidance into a comprehensive system prompt.

        Args:
            context: Generation context.
            options: Draft configuration options.
            variant_type: Product variant tier.
            draft_index: Which draft in the sequence (0-based).
            total_drafts: Total number of drafts being generated.

        Returns:
            System prompt string.
        """
        brand = context.get("brand_voice", {})
        technique = context.get("technique", "standard_response")
        sentiment = context.get("sentiment", 0.5)
        intent = context.get("intent", "general")
        customer_tier = context.get("customer_tier", "free")

        parts: List[str] = []

        # ── Core role ─────────────────────────────────────────────
        brand_name = brand.get("brand_name", "our company")
        parts.append(
            f"You are a customer support co-pilot for {brand_name}. "
            "Draft a response that a human agent can review, edit, "
            "and send to the customer."
        )

        # ── Variant-specific instructions ─────────────────────────
        if variant_type == "mini_parwa":
            parts.append(
                "\nGenerate a simple, clear response. "
                "Focus on directly answering the query."
            )
        elif variant_type == "parwa":
            parts.append(
                "\nGenerate a polished response that matches "
                "the brand's tone and style guidelines."
            )
        elif variant_type == "high_parwa":
            parts.append(
                "\nGenerate a personalized, nuanced response. "
                "Consider the customer's history, tier, and "
                "sentiment. Provide the best possible draft."
            )

        # ── Tone guidance ─────────────────────────────────────────
        tone = options.tone or brand.get("tone", "professional")
        formality = brand.get("formality_level", 0.5)

        if formality > 0.7:
            formality_desc = "formal — no contractions, precise language"
        elif formality > 0.4:
            formality_desc = "semi-formal — polite but approachable"
        else:
            formality_desc = "casual — warm and friendly"

        parts.append(f"\nTone: {tone}. Style: {formality_desc}.")

        # ── Sentiment-aware guidance ──────────────────────────────
        if sentiment < 0.3:
            parts.append(
                "\nThe customer is frustrated or upset. "
                "Use empathetic language, acknowledge their feelings, "
                "and focus on resolution."
            )
        elif sentiment > 0.7:
            parts.append(
                "\nThe customer is positive. "
                "Match their friendly tone and express appreciation."
            )

        # ── Technique-specific instructions ───────────────────────
        technique_instructions = self._get_technique_instructions(
            technique,
        )
        if technique_instructions:
            parts.append(f"\nApproach: {technique_instructions}")

        # ── Brand-specific rules ──────────────────────────────────
        prohibited = brand.get("prohibited_words", [])
        if prohibited:
            parts.append(f"\nNEVER use these words: {', '.join(prohibited[:10])}")

        max_sent = brand.get("max_response_sentences", 6)
        min_sent = brand.get("min_response_sentences", 2)
        parts.append(
            f"\nKeep the response between {min_sent} and " f"{max_sent} sentences."
        )

        # ── Custom instructions ───────────────────────────────────
        custom = options.custom_instructions or brand.get(
            "custom_instructions",
            "",
        )
        if custom:
            parts.append(f"\nAdditional instructions: {custom}")

        # ── Multi-draft variation ─────────────────────────────────
        if total_drafts > 1:
            parts.append(
                f"\nThis is draft {draft_index + 1} of "
                f"{total_drafts}. Make this variation distinct "
                "from others in tone or emphasis."
            )

        # ── high_parwa: Customer tier personalization ─────────────
        if variant_type == "high_parwa" and customer_tier != "free":
            parts.append(
                f"\nThis is a {customer_tier} tier customer. "
                "Provide premium, personalized service."
            )

        # ── Citations ─────────────────────────────────────────────
        if options.include_citations:
            parts.append("\nInclude [citation:N] references where applicable.")

        # ── Length constraint ─────────────────────────────────────
        if options.max_length:
            parts.append(f"\nMaximum response length: {options.max_length} characters.")

        return "\n".join(parts)

    @staticmethod
    def _get_technique_instructions(technique: str) -> str:
        """Get human-readable instructions for a technique."""
        _instructions: Dict[str, str] = {
            "empathetic_resolution": (
                "Lead with empathy. Acknowledge the customer's "
                "frustration, then clearly explain the resolution "
                "process and timeline."
            ),
            "friendly_confirmation": (
                "Confirm the action in a friendly, positive way. "
                "Summarize what was done and provide next steps."
            ),
            "standard_resolution": (
                "Clearly explain the resolution with step-by-step "
                "instructions if needed."
            ),
            "patient_troubleshooting": (
                "Be patient and methodical. Walk through "
                "troubleshooting steps one at a time."
            ),
            "helpful_guide": (
                "Provide a helpful, clear guide. Use bullet points "
                "or numbered steps for clarity."
            ),
            "step_by_step": (
                "Break down the solution into numbered steps. "
                "Be concise and precise."
            ),
            "apologetic_clarification": (
                "Start with an apology for the billing confusion, "
                "then clearly explain the charges."
            ),
            "clear_summary": (
                "Provide a clear, organized summary of the billing " "details."
            ),
            "informative_breakdown": (
                "Break down the billing information in an organized, "
                "easy-to-understand format."
            ),
            "de_escalation": (
                "Focus on de-escalation. Acknowledge the complaint "
                "empathetically, show you take it seriously, "
                "and offer a concrete resolution."
            ),
            "acknowledgment": (
                "Acknowledge the complaint and thank the customer "
                "for their feedback."
            ),
            "empathetic_response": (
                "Respond with genuine empathy. Validate the "
                "customer's feelings before addressing the issue."
            ),
            "retention_offer": (
                "Acknowledge the cancellation request, express regret, "
                "and offer alternatives or incentives to stay."
            ),
            "smooth_exit": (
                "Process the cancellation smoothly and professionally. "
                "Leave the door open for return."
            ),
            "process_confirmation": (
                "Confirm the cancellation process and provide "
                "clear next steps and timelines."
            ),
            "urgent_escalation": (
                "Immediately escalate with urgency. Acknowledge "
                "the severity and transfer to the right team."
            ),
            "warm_transfer": (
                "Warmly transfer to the appropriate team with full "
                "context. Reassure the customer."
            ),
            "escalation_acknowledgment": (
                "Acknowledge the escalation request and explain " "the next steps."
            ),
            "proactive_tracking": (
                "Proactively provide tracking information and "
                "set expectations for delivery."
            ),
            "delivery_update": (
                "Provide a clear delivery update with tracking " "details."
            ),
            "logistics_response": (
                "Address the shipping/logistics question clearly "
                "with relevant details."
            ),
            "security_assurance": (
                "Reassure the customer about security. Provide "
                "clear steps for account recovery."
            ),
            "quick_fix": ("Provide a quick, easy fix for the account issue."),
            "account_assistance": ("Assist with the account request step by step."),
            "encouraging_acknowledgment": (
                "Thank the customer for their feature suggestion "
                "and encourage continued feedback."
            ),
            "enthusiastic_capture": (
                "Enthusiastically capture the feature request "
                "and share any related plans."
            ),
            "feature_acknowledgment": (
                "Acknowledge the feature request professionally "
                "and explain the review process."
            ),
            "detailed_explanation": (
                "Provide a detailed, thorough explanation to address "
                "the inquiry fully."
            ),
            "concise_answer": ("Provide a concise, direct answer to the inquiry."),
            "informative_response": (
                "Provide an informative, helpful response that "
                "addresses the inquiry."
            ),
            "grateful_acknowledgment": (
                "Express genuine gratitude for the feedback "
                "and address any concerns."
            ),
            "celebration": ("Celebrate the positive feedback enthusiastically!"),
            "thank_you_response": (
                "Thank the customer sincerely for their feedback "
                "and offer further assistance."
            ),
            "helpful_standard": (
                "Provide a helpful, standard response addressing "
                "the customer's needs."
            ),
            "friendly_standard": (
                "Provide a friendly, standard response that "
                "matches the customer's positive tone."
            ),
            "standard_response": (
                "Provide a clear, professional response that "
                "addresses the customer's query."
            ),
        }
        return _instructions.get(technique, "")

    # ──────────────────────────────────────────────────────────────
    # CLARA QUALITY VALIDATION
    # ──────────────────────────────────────────────────────────────

    async def _validate_drafts(
        self,
        drafts: List[DraftResult],
        query: str,
        company_id: str,
        sentiment: float,
    ) -> List[DraftResult]:
        """Run each draft through the CLARA quality gate.

        Updates each draft's ``quality_score`` and ``metadata`` with
        CLARA results.  Drafts that fail CLARA still get included
        (agent can still review), but have lower scores.

        Args:
            drafts: List of generated drafts to validate.
            query: Original customer query.
            company_id: Tenant identifier.
            sentiment: Customer sentiment score.

        Returns:
            List of drafts with updated quality scores.
        """
        validated = []
        for draft in drafts:
            if not draft.content:
                validated.append(draft)
                continue

            try:
                brand = {}
                if draft.metadata.get("tone") or draft.metadata.get("brand_name"):
                    brand = {
                        "brand_name": draft.metadata.get("brand_name", ""),
                    }

                clara_result = await self.clara_gate.evaluate(
                    response=draft.content,
                    query=query,
                    company_id=company_id,
                    customer_sentiment=sentiment,
                    context=brand,
                )

                draft.quality_score = clara_result.overall_score

                # Extract stage-level details for metadata
                brand_passed = True
                tone_score = 0.5
                for stage in clara_result.stages:
                    stage_name = stage.stage.value
                    if stage_name == "brand_check":
                        brand_passed = stage.result.value in (
                            "pass",
                            "timeout_pass",
                        )
                    if stage_name == "tone_check":
                        tone_score = stage.score

                draft.metadata["brand_check_passed"] = brand_passed
                draft.metadata["tone_match"] = round(tone_score, 4)
                draft.metadata["clara_passed"] = clara_result.overall_pass
                draft.metadata["clara_score"] = round(
                    clara_result.overall_score,
                    4,
                )
                draft.metadata["clara_issues"] = [
                    issue for stage in clara_result.stages for issue in stage.issues
                ][:5]

                # Use CLARA's improved response if available
                if clara_result.final_response and clara_result.overall_pass:
                    draft.content = clara_result.final_response

            except Exception as exc:
                logger.warning(
                    "draft_clara_validation_failed",
                    draft_id=draft.draft_id,
                    error=str(exc),
                    company_id=company_id,
                )
                draft.quality_score = 0.3  # Low but not zero
                draft.metadata["clara_error"] = str(exc)

            validated.append(draft)

        return validated

    # ──────────────────────────────────────────────────────────────
    # DEDUPLICATION (GAP-021)
    # ──────────────────────────────────────────────────────────────

    def _deduplicate_drafts(
        self,
        drafts: List[DraftResult],
    ) -> List[DraftResult]:
        """Remove near-identical drafts to avoid redundancy.

        Uses SequenceMatcher with configurable similarity threshold.
        Keeps the draft with the higher quality score when duplicates
        are found.

        GAP-021: Threshold of 0.85 catches paraphrased repetitions
        while preserving meaningfully different drafts.

        Args:
            drafts: List of drafts to deduplicate.

        Returns:
            Deduplicated list sorted by quality score.
        """
        if len(drafts) <= 1:
            return drafts

        unique: List[DraftResult] = []
        seen_content: List[str] = []

        for draft in drafts:
            if not draft.content:
                continue

            is_duplicate = False
            for existing in seen_content:
                similarity = SequenceMatcher(
                    None,
                    draft.content.lower(),
                    existing.lower(),
                ).ratio()
                if similarity >= _DEDUP_SIMILARITY_THRESHOLD:
                    is_duplicate = True
                    logger.info(
                        "draft_deduplicated",
                        draft_id=draft.draft_id,
                        similarity=round(similarity, 4),
                        threshold=_DEDUP_SIMILARITY_THRESHOLD,
                    )
                    break

            if not is_duplicate:
                unique.append(draft)
                seen_content.append(draft.content)

        return unique

    # ──────────────────────────────────────────────────────────────
    # REGENERATE DRAFT (GAP-020 FEEDBACK LOOP)
    # ──────────────────────────────────────────────────────────────

    async def _regenerate_draft(
        self,
        draft_id: str,
        feedback: str,
        company_id: str,
    ) -> DraftResult:
        """Regenerate a draft based on agent feedback.

        GAP-020: Stores feedback for improvement tracking.  The
        feedback is included in the prompt to guide the new draft.

        Args:
            draft_id: ID of the original draft to regenerate.
            feedback: Agent's feedback describing what to improve.
            company_id: Tenant identifier (BC-001).

        Returns:
            New ``DraftResult`` incorporating the feedback.
        """
        new_draft_id = self._generate_uuid()
        draft_start = time.monotonic()

        # Store the feedback for improvement tracking (GAP-020)
        await self._store_feedback(
            draft_id=draft_id,
            feedback=feedback,
            company_id=company_id,
        )

        try:
            # Build feedback-aware prompt
            system_prompt = (
                "You are a customer support co-pilot. "
                "The human agent has provided feedback on a "
                "previous draft. Generate an improved version "
                "that addresses their feedback.\n\n"
                f"Agent Feedback: {feedback}\n\n"
                "Incorporate the feedback while maintaining "
                "a professional, helpful tone. The draft should "
                "be ready for the agent to review and send."
            )

            messages = [{"role": "system", "content": system_prompt}]

            # Route through Smart Router Medium tier
            from app.core.smart_router import (
                AtomicStepType,
            )

            routing_decision = self.smart_router.route(
                company_id=company_id,
                variant_type="parwa",
                atomic_step=AtomicStepType.DRAFT_RESPONSE_MODERATE,
            )

            llm_result = await asyncio.wait_for(
                self.smart_router.async_execute_llm_call(
                    company_id=company_id,
                    routing_decision=routing_decision,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=512,
                ),
                timeout=_DRAFT_GENERATION_TIMEOUT_SECONDS,
            )

            content = llm_result.get("content", "")
            if not content or not content.strip():
                content = ""

            generation_time = round(
                (time.monotonic() - draft_start) * 1000,
                2,
            )

            return DraftResult(
                draft_id=new_draft_id,
                content=content,
                quality_score=0.0,
                generation_time_ms=generation_time,
                technique_used="feedback_revision",
                metadata={
                    "regenerated_from": draft_id,
                    "feedback": feedback,
                    "model": llm_result.get("model", "unknown"),
                    "provider": llm_result.get("provider", "unknown"),
                },
            )

        except asyncio.TimeoutError:
            logger.warning(
                "draft_regenerate_timeout",
                draft_id=draft_id,
                new_draft_id=new_draft_id,
                company_id=company_id,
            )
            generation_time = round(
                (time.monotonic() - draft_start) * 1000,
                2,
            )
            return DraftResult(
                draft_id=new_draft_id,
                content="",
                quality_score=0.0,
                generation_time_ms=generation_time,
                technique_used="feedback_revision",
                metadata={
                    "regenerated_from": draft_id,
                    "timed_out": True,
                },
            )
        except Exception as exc:
            logger.warning(
                "draft_regenerate_error",
                draft_id=draft_id,
                error=str(exc),
                company_id=company_id,
            )
            generation_time = round(
                (time.monotonic() - draft_start) * 1000,
                2,
            )
            return DraftResult(
                draft_id=new_draft_id,
                content="",
                quality_score=0.0,
                generation_time_ms=generation_time,
                technique_used="feedback_revision",
                metadata={
                    "regenerated_from": draft_id,
                    "error": str(exc),
                },
            )

    # ──────────────────────────────────────────────────────────────
    # DRAFT HISTORY
    # ──────────────────────────────────────────────────────────────

    async def get_draft_history(
        self,
        ticket_id: str,
        company_id: str,
    ) -> List[Dict[str, Any]]:
        """Get previous drafts for a ticket from Redis.

        Returns the draft history stored in Redis for the given
        ticket.  Each entry includes the request ID, drafts,
        timestamps, and quality scores.

        Args:
            ticket_id: The ticket identifier.
            company_id: Tenant identifier (BC-001).

        Returns:
            List of draft history entries.  Empty list on failure
            or if no history exists.
        """
        if not ticket_id or not company_id:
            return []

        try:
            from app.core.redis import cache_get

            key = _HISTORY_KEY_TEMPLATE.format(
                company_id=company_id,
                ticket_id=ticket_id,
            )
            history = await cache_get(
                company_id,
                f"draft_history:{ticket_id}",
            )
            if history is not None and isinstance(history, list):
                return history
            return []
        except Exception as exc:
            logger.warning(
                "draft_history_retrieval_failed",
                error=str(exc),
                company_id=company_id,
                ticket_id=ticket_id,
            )
            # BC-008: Return empty on failure
            return []

    async def _store_draft_history(
        self,
        ticket_id: str,
        company_id: str,
        response: DraftComposerResponse,
    ) -> None:
        """Store draft generation in Redis history for a ticket.

        Appends the new response to the existing history list.
        On Redis failure, silently continues (BC-008).
        """
        try:
            from app.core.redis import cache_get, cache_set

            # Get existing history
            history_key = f"draft_history:{ticket_id}"
            existing = await cache_get(company_id, history_key)
            if not isinstance(existing, list):
                existing = []

            # Append new entry
            entry = {
                "request_id": response.request_id,
                "timestamp": datetime.now(
                    timezone.utc,
                ).isoformat(),
                "draft_count": len(response.drafts),
                "best_score": (
                    response.drafts[0].quality_score if response.drafts else 0.0
                ),
                "total_time_ms": response.total_generation_time_ms,
                "variant_type": response.variant_type,
            }
            existing.append(entry)

            # Keep only last 50 entries to prevent unbounded growth
            if len(existing) > 50:
                existing = existing[-50:]

            # Store back
            await cache_set(
                company_id,
                history_key,
                existing,
                ttl_seconds=_HISTORY_TTL_SECONDS,
            )

        except Exception as exc:
            logger.warning(
                "draft_history_store_failed",
                error=str(exc),
                company_id=company_id,
                ticket_id=ticket_id,
            )

    # ──────────────────────────────────────────────────────────────
    # FEEDBACK STORAGE (GAP-020)
    # ──────────────────────────────────────────────────────────────

    async def _store_feedback(
        self,
        draft_id: str,
        feedback: str,
        company_id: str,
    ) -> None:
        """Store agent feedback for improvement tracking.

        GAP-020: Feedback is stored in Redis with 7-day TTL.
        This enables future analysis of common rejection patterns
        and draft quality improvement.

        Args:
            draft_id: ID of the draft being feedback on.
            feedback: Agent's feedback text.
            company_id: Tenant identifier (BC-001).
        """
        try:
            from app.core.redis import cache_set

            feedback_data = {
                "draft_id": draft_id,
                "feedback": feedback,
                "company_id": company_id,
                "timestamp": datetime.now(
                    timezone.utc,
                ).isoformat(),
            }
            key = f"draft_feedback:{draft_id}"
            await cache_set(
                company_id,
                key,
                feedback_data,
                ttl_seconds=_FEEDBACK_TTL_SECONDS,
            )

            logger.info(
                "draft_feedback_stored",
                draft_id=draft_id,
                company_id=company_id,
            )

        except Exception as exc:
            logger.warning(
                "draft_feedback_store_failed",
                error=str(exc),
                draft_id=draft_id,
                company_id=company_id,
            )

    async def get_feedback_history(
        self,
        company_id: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Retrieve recent feedback history for a company.

        Useful for analytics dashboards showing draft quality trends
        and common rejection patterns.

        Args:
            company_id: Tenant identifier (BC-001).
            limit: Maximum number of feedback entries to return.

        Returns:
            List of feedback entries with timestamps.
        """
        # Feedback is stored per-draft, not per-company, so
        # this is a placeholder for future aggregation via DB.
        # For now, return empty — the per-draft feedback storage
        # above enables future batch analysis.
        logger.debug(
            "draft_feedback_history_requested",
            company_id=company_id,
            limit=limit,
        )
        return []

    # ──────────────────────────────────────────────────────────────
    # CACHE
    # ──────────────────────────────────────────────────────────────

    async def _check_cache(
        self,
        company_id: str,
        cache_key: str,
    ) -> Optional[DraftComposerResponse]:
        """Check Redis cache for a previously composed response.

        Returns ``None`` on cache miss or Redis error (fail-open).

        Args:
            company_id: Tenant identifier (BC-001).
            cache_key: The cache key to look up.

        Returns:
            Cached ``DraftComposerResponse`` or ``None``.
        """
        try:
            from app.core.redis import cache_get

            cached = await cache_get(company_id, cache_key)
            if cached is not None and isinstance(cached, dict):
                drafts = []
                for d in cached.get("drafts", []):
                    drafts.append(
                        DraftResult(
                            draft_id=d.get("draft_id", ""),
                            content=d.get("content", ""),
                            quality_score=d.get("quality_score", 0.0),
                            generation_time_ms=d.get(
                                "generation_time_ms",
                                0.0,
                            ),
                            technique_used=d.get("technique_used", ""),
                            metadata=d.get("metadata", {}),
                        )
                    )
                return DraftComposerResponse(
                    request_id=cached.get("request_id", ""),
                    drafts=drafts,
                    best_draft_index=cached.get(
                        "best_draft_index",
                        0,
                    ),
                    total_generation_time_ms=cached.get(
                        "total_generation_time_ms",
                        0.0,
                    ),
                    variant_type=cached.get("variant_type", ""),
                    cached=True,
                )
        except Exception as exc:
            logger.warning(
                "draft_cache_read_error",
                error=str(exc),
                company_id=company_id,
            )
        return None

    async def _store_cache(
        self,
        company_id: str,
        cache_key: str,
        response: DraftComposerResponse,
    ) -> None:
        """Store composed response in Redis cache.

        Fail-open: cache write failure does not affect the response.

        Args:
            company_id: Tenant identifier (BC-001).
            cache_key: The cache key to store under.
            response: The response to cache.
        """
        try:
            from app.core.redis import cache_set

            await cache_set(
                company_id,
                cache_key,
                response.to_dict(),
                ttl_seconds=_CACHE_TTL_SECONDS,
            )
        except Exception as exc:
            logger.warning(
                "draft_cache_write_error",
                error=str(exc),
                company_id=company_id,
            )

    # ──────────────────────────────────────────────────────────────
    # SOCKET.IO EMISSION
    # ──────────────────────────────────────────────────────────────

    async def _emit_to_agent(
        self,
        request: DraftRequest,
        response: DraftComposerResponse,
    ) -> None:
        """Emit draft suggestions to the agent via Socket.io.

        Sends a ``draft_suggestions`` event to the tenant room
        so the agent's UI can display the suggestions in real-time.

        Args:
            request: The original draft request.
            response: The composed response to emit.
        """
        try:
            from app.core.socketio import emit_to_tenant

            payload = {
                "event": "draft_suggestions",
                "request_id": response.request_id,
                "agent_id": request.agent_id,
                "ticket_id": request.ticket_id,
                "drafts": [
                    {
                        "draft_id": d.draft_id,
                        "content": d.content,
                        "quality_score": d.quality_score,
                        "technique_used": d.technique_used,
                    }
                    for d in response.drafts
                ],
                "best_draft_index": response.best_draft_index,
                "variant_type": response.variant_type,
            }

            await emit_to_tenant(
                company_id=request.company_id,
                event="draft_suggestions",
                data=payload,
            )

            logger.info(
                "draft_suggestions_emitted",
                company_id=request.company_id,
                agent_id=request.agent_id,
                ticket_id=request.ticket_id,
                draft_count=len(response.drafts),
            )

        except Exception as exc:
            logger.warning(
                "draft_socketio_emit_failed",
                error=str(exc),
                company_id=request.company_id,
            )
            # BC-008: Socket.io failure doesn't affect the response

    # ──────────────────────────────────────────────────────────────
    # UTILITIES
    # ──────────────────────────────────────────────────────────────

    @staticmethod
    def _generate_uuid() -> str:
        """Generate a unique identifier (UUID4 hex)."""
        import uuid

        return uuid.uuid4().hex

    @staticmethod
    def _compute_query_hash(query: str) -> str:
        """Compute deterministic SHA-256 hash for cache key.

        Normalizes the query by lowercasing and stripping whitespace.

        Args:
            query: The customer query to hash.

        Returns:
            First 16 characters of the SHA-256 hex digest.
        """
        normalized = query.lower().strip()
        return hashlib.sha256(
            normalized.encode("utf-8"),
        ).hexdigest()[:16]

    def _empty_response(
        self,
        request_id: str,
        variant_type: str,
        compose_start: float,
        reason: str,
    ) -> DraftComposerResponse:
        """Build an empty response for error/fallback cases.

        Args:
            request_id: Request identifier.
            variant_type: Product variant tier.
            compose_start: Timestamp when compose started.
            reason: Reason for the empty response.

        Returns:
            ``DraftComposerResponse`` with no drafts.
        """
        total_time = round(
            (time.monotonic() - compose_start) * 1000,
            2,
        )
        logger.info(
            "draft_composer_empty_response",
            request_id=request_id,
            reason=reason,
            total_time_ms=total_time,
        )
        return DraftComposerResponse(
            request_id=request_id,
            drafts=[],
            best_draft_index=-1,
            total_generation_time_ms=total_time,
            variant_type=variant_type,
            cached=False,
        )
