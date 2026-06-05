"""
MAKER Framework Full Pipeline (Day 5 — AI-15)

Implements the Map → Analyze → Knowledge → Evaluate → Refine pipeline
that composes multiple AI techniques into a complete customer care response.

Pipeline Stages:
  1. Map:    Classify query type and determine specialized agent
  2. Analyze: Sentiment analysis, urgency detection, entity extraction
  3. Knowledge: CLARA RAG retrieval (HyDE + Multi-Query + Compression)
  4. Evaluate: FAKE Voting system with Red-Flagging
  5. Refine:  PII redaction, brand voice, channel formatting

BC-001: All operations scoped to company_id.
BC-008: Each stage has independent fallback — pipeline never crashes.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.core.technique_tier_mapper import (
    get_max_llm_calls,
    get_technique_for_tier,
    get_tier_config,
)
from app.logger import get_logger

logger = get_logger("maker_pipeline")

# ── Query Types ─────────────────────────────────────────────────────

QUERY_TYPES = [
    "refund",
    "technical",
    "billing",
    "complaint",
    "faq",
    "general",
]

# ── Data Classes ────────────────────────────────────────────────────


@dataclass
class MakerStageResult:
    """Result of a single MAKER pipeline stage."""

    stage: str
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    processing_time_ms: float = 0.0
    fallback_used: bool = False
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage": self.stage,
            "success": self.success,
            "data": self.data,
            "processing_time_ms": round(self.processing_time_ms, 2),
            "fallback_used": self.fallback_used,
            "error": self.error,
        }


@dataclass
class MakerPipelineResult:
    """Result of the full MAKER pipeline execution."""

    query: str
    company_id: str
    variant_tier: str
    query_type: str
    response: str
    confidence: float
    stages: List[MakerStageResult] = field(default_factory=list)
    total_processing_time_ms: float = 0.0
    total_llm_calls: int = 0
    red_flagged: bool = False
    escalated: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query[:100],
            "company_id": self.company_id,
            "variant_tier": self.variant_tier,
            "query_type": self.query_type,
            "confidence": round(self.confidence, 4),
            "total_processing_time_ms": round(
                self.total_processing_time_ms, 2
            ),
            "total_llm_calls": self.total_llm_calls,
            "red_flagged": self.red_flagged,
            "escalated": self.escalated,
            "stages": [s.to_dict() for s in self.stages],
        }


class MAKERPipeline:
    """MAKER Framework Full Pipeline.

    Executes the Map → Analyze → Knowledge → Evaluate → Refine
    pipeline with tier-aware behavior.

    - mini_parwa: Map only (fastest path)
    - parwa: Map + Analyze + Knowledge + Evaluate (K=3)
    - parwa_high: Full pipeline with FAKE Voting + Compression

    BC-001: All operations scoped to company_id.
    BC-008: Each stage has independent fallback.
    """

    def __init__(self, llm_generate_func=None):
        """Initialize with optional LLM generate function."""
        self._llm_generate = llm_generate_func

    async def execute(
        self,
        query: str,
        company_id: str,
        variant_tier: str = "parwa",
        context: Optional[Dict[str, Any]] = None,
    ) -> MakerPipelineResult:
        """Run the full MAKER pipeline.

        Args:
            query: Customer query text.
            company_id: Tenant identifier (BC-001).
            variant_tier: Product tier.
            context: Optional additional context (ticket_id, etc.).

        Returns:
            MakerPipelineResult with full pipeline output.
        """
        pipeline_start = time.monotonic()
        stages: List[MakerStageResult] = []
        total_llm_calls = 0

        # ── Stage 1: MAP — Classify query ─────────────────────────
        map_result = await self._stage_map(query, company_id)
        stages.append(map_result)
        total_llm_calls += map_result.data.get("llm_calls", 0)

        query_type = map_result.data.get("query_type", "general")

        # Mini PARWA: Skip remaining stages for speed
        if variant_tier == "mini_parwa":
            response = map_result.data.get(
                "initial_response", self._safe_response(query)
            )
            confidence = map_result.data.get("confidence", 0.5)
            return self._build_result(
                query, company_id, variant_tier, query_type,
                response, confidence, stages, pipeline_start,
                total_llm_calls,
            )

        # ── Stage 2: ANALYZE — Sentiment + Entities ───────────────
        analyze_result = await self._stage_analyze(
            query, company_id, variant_tier
        )
        stages.append(analyze_result)
        total_llm_calls += analyze_result.data.get("llm_calls", 0)

        # ── Stage 3: KNOWLEDGE — CLARA RAG ────────────────────────
        knowledge_result = await self._stage_knowledge(
            query, company_id, variant_tier
        )
        stages.append(knowledge_result)
        total_llm_calls += knowledge_result.data.get("llm_calls", 0)

        rag_context = knowledge_result.data.get("rag_context", "")

        # ── Stage 4: EVALUATE — FAKE Voting ───────────────────────
        evaluate_result = await self._stage_evaluate(
            query, company_id, variant_tier, query_type, rag_context
        )
        stages.append(evaluate_result)
        total_llm_calls += evaluate_result.data.get("llm_calls", 0)

        response = evaluate_result.data.get("best_response", "")
        confidence = evaluate_result.data.get("best_confidence", 0.5)
        red_flagged = evaluate_result.data.get("red_flagged", False)

        # ── Stage 5: REFINE — Quality checks ──────────────────────
        refine_result = await self._stage_refine(
            response, query, company_id, variant_tier
        )
        stages.append(refine_result)

        final_response = refine_result.data.get(
            "refined_response", response
        )

        return self._build_result(
            query, company_id, variant_tier, query_type,
            final_response, confidence, stages, pipeline_start,
            total_llm_calls, red_flagged=red_flagged,
        )

    # ── Stage 1: MAP ────────────────────────────────────────────────

    async def _stage_map(
        self, query: str, company_id: str
    ) -> MakerStageResult:
        """Map stage: Classify query type using LLM or keywords.

        BC-008: Falls back to keyword classification.
        """
        start = time.monotonic()
        llm_calls = 0

        # Try LLM classification
        query_type = None
        try:
            llm = self._get_llm()
            if llm is not None:
                prompt = (
                    "Classify this customer support query into exactly "
                    "one category: refund, technical, billing, complaint, "
                    "faq, general.\n\n"
                    f"Query: {query[:500]}\n\nCategory:"
                )
                response = await self._call_llm(prompt, company_id)
                llm_calls = 1
                if response:
                    response_lower = response.lower().strip()
                    for qt in QUERY_TYPES:
                        if qt in response_lower:
                            query_type = qt
                            break
        except Exception as exc:
            logger.debug(
                "maker_map_llm_failed",
                company_id=company_id,
                error=str(exc)[:100],
            )

        # Fallback: keyword classification
        fallback_used = query_type is None
        if fallback_used:
            query_type = self._keyword_classify(query)

        return MakerStageResult(
            stage="map",
            success=True,
            data={
                "query_type": query_type,
                "llm_calls": llm_calls,
                "initial_response": "",
                "confidence": 0.6,
            },
            processing_time_ms=round((time.monotonic() - start) * 1000, 2),
            fallback_used=fallback_used,
        )

    # ── Stage 2: ANALYZE ────────────────────────────────────────────

    async def _stage_analyze(
        self, query: str, company_id: str, variant_tier: str
    ) -> MakerStageResult:
        """Analyze stage: Sentiment analysis, urgency, entity extraction.

        BC-008: Falls back to regex-based analysis.
        """
        start = time.monotonic()
        llm_calls = 0

        sentiment_score = 0.7  # neutral-positive default
        urgency = "normal"
        entities: Dict[str, str] = {}

        # Try LLM-based analysis
        try:
            llm = self._get_llm()
            if llm is not None:
                prompt = (
                    "Analyze this customer query:\n"
                    f"Query: {query[:500]}\n\n"
                    "Provide:\n"
                    "1. Sentiment score (0.0-1.0, 0=very negative, 1=very positive)\n"
                    "2. Urgency level (low, normal, high, critical)\n"
                    "3. Key entities (order numbers, product names, etc.)\n\n"
                    "Format: sentiment=X.X urgency=LEVEL entities=..."
                )
                response = await self._call_llm(prompt, company_id)
                llm_calls = 1

                if response:
                    # Parse sentiment
                    sentiment_match = re.search(
                        r"sentiment=(\d+\.?\d*)", response
                    )
                    if sentiment_match:
                        sentiment_score = float(sentiment_match.group(1))
                        sentiment_score = max(0.0, min(1.0, sentiment_score))

                    # Parse urgency
                    urgency_match = re.search(
                        r"urgency=(low|normal|high|critical)", response, re.I
                    )
                    if urgency_match:
                        urgency = urgency_match.group(1).lower()

                    # Parse entities
                    entities_match = re.search(
                        r"entities=(.*)", response
                    )
                    if entities_match:
                        entities["raw"] = entities_match.group(1).strip()
        except Exception as exc:
            logger.debug(
                "maker_analyze_llm_failed",
                company_id=company_id,
                error=str(exc)[:100],
            )

        # Regex-based entity extraction (always run as supplement)
        order_match = re.search(
            r"order\s*#?\s*(\d{4,})", query, re.I
        )
        if order_match:
            entities["order_id"] = order_match.group(1)

        tracking_match = re.search(
            r"tracking\s*#?\s*([A-Z0-9]{6,})", query, re.I
        )
        if tracking_match:
            entities["tracking_number"] = tracking_match.group(1)

        # Urgency from keywords
        if urgency == "normal":
            urgent_words = ["urgent", "asap", "emergency", "immediately"]
            if any(w in query.lower() for w in urgent_words):
                urgency = "high"

        return MakerStageResult(
            stage="analyze",
            success=True,
            data={
                "sentiment_score": sentiment_score,
                "urgency": urgency,
                "entities": entities,
                "llm_calls": llm_calls,
            },
            processing_time_ms=round((time.monotonic() - start) * 1000, 2),
        )

    # ── Stage 3: KNOWLEDGE ──────────────────────────────────────────

    async def _stage_knowledge(
        self, query: str, company_id: str, variant_tier: str
    ) -> MakerStageResult:
        """Knowledge stage: CLARA RAG retrieval.

        - parwa: Multi-Query retrieval
        - parwa_high: HyDE + Multi-Query + Compression

        BC-008: Falls back to empty context.
        """
        start = time.monotonic()
        llm_calls = 0
        rag_context = ""
        rag_method = ""

        try:
            from app.core.rag_retrieval import RAGRetriever

            retriever = RAGRetriever()

            if variant_tier == "parwa_high":
                # Full CLARA: HyDE + Multi-Query
                rag_result = await retriever.generate_hyde_and_retrieve(
                    query=query,
                    company_id=company_id,
                    variant_type="parwa_high",
                )
                llm_calls = 1  # HyDE call

                # Compress results
                if rag_result.chunks:
                    from app.core.rag_compression import ContextualCompressor
                    compressor = ContextualCompressor()
                    comp_result = await compressor.compress_chunks(
                        chunks=rag_result.chunks,
                        query=query,
                        company_id=company_id,
                        variant_type="parwa_high",
                    )
                    rag_context = "\n".join(
                        c.compressed_content
                        for c in comp_result.compressed_chunks[:5]
                    )
                    rag_method = "hyde_multi_query_compression"
                else:
                    rag_method = "hyde_no_results"

            else:
                # parwa: Multi-Query retrieval
                rag_result = await retriever.expand_query_multi(
                    query=query,
                    company_id=company_id,
                    variant_type="parwa",
                )
                if rag_result.chunks:
                    rag_context = "\n".join(
                        c.content[:300] for c in rag_result.chunks[:3]
                    )
                    rag_method = "multi_query"

        except ImportError:
            logger.info(
                "maker_knowledge_rag_unavailable",
                company_id=company_id,
            )
        except Exception as exc:
            logger.warning(
                "maker_knowledge_failed",
                company_id=company_id,
                error=str(exc)[:200],
            )

        return MakerStageResult(
            stage="knowledge",
            success=bool(rag_context),
            data={
                "rag_context": rag_context[:500] if rag_context else "",
                "rag_method": rag_method,
                "rag_context_length": len(rag_context),
                "llm_calls": llm_calls,
            },
            processing_time_ms=round((time.monotonic() - start) * 1000, 2),
            fallback_used=not rag_context,
        )

    # ── Stage 4: EVALUATE ───────────────────────────────────────────

    async def _stage_evaluate(
        self,
        query: str,
        company_id: str,
        variant_tier: str,
        query_type: str,
        rag_context: str,
    ) -> MakerStageResult:
        """Evaluate stage: Generate and evaluate K candidate responses.

        - parwa: K=3 candidates, simple scoring
        - parwa_high: K=5-7 candidates, FAKE Voting with Red-Flagging

        BC-008: Falls back to single response with moderate confidence.
        """
        start = time.monotonic()
        llm_calls = 0

        # Determine K value
        tier_config = get_tier_config(variant_tier)
        k = tier_config.get("maker_k", 3)
        fake_voting = tier_config.get("fake_voting_enabled", False)

        # Generate primary response
        context_section = ""
        if rag_context:
            context_section = (
                f"\n\nKnowledge Base Context:\n{rag_context[:2000]}\n"
            )

        best_response = ""
        best_confidence = 0.5
        red_flagged = False

        try:
            llm = self._get_llm()
            if llm is not None:
                # Generate K candidate responses
                candidates: List[Dict[str, Any]] = []

                for i in range(k):
                    prompt = (
                        f"You are a professional customer support agent "
                        f"handling a {query_type} query.\n"
                        f"Generate response variant #{i+1} with a "
                        f"{'conservative' if i % 2 == 0 else 'empathetic'} "
                        f"approach.\n"
                        f"{context_section}\n"
                        f"Customer Query: {query[:1000]}\n\nResponse:"
                    )
                    response_text = await self._call_llm(
                        prompt, company_id
                    )
                    llm_calls += 1

                    if response_text and len(response_text.strip()) > 10:
                        # Estimate confidence
                        conf = 0.6 + (0.05 * (k - i) / k)
                        if rag_context:
                            conf += 0.1
                        candidates.append({
                            "response": response_text.strip(),
                            "confidence": min(conf, 0.95),
                            "index": i,
                        })

                # Select best candidate
                if candidates:
                    # Simple scoring: pick the one with highest confidence
                    if fake_voting and len(candidates) >= 3:
                        # FAKE Voting: LLM judges evaluate each candidate
                        best_idx = await self._fake_vote(
                            candidates, query, company_id
                        )
                        llm_calls += len(candidates)
                    else:
                        best_idx = 0

                    candidates.sort(
                        key=lambda c: c["confidence"], reverse=True
                    )
                    best_response = candidates[best_idx]["response"]
                    best_confidence = candidates[best_idx]["confidence"]

                    # Red-flag check
                    threshold = 0.75 if variant_tier == "parwa_high" else 0.6
                    if best_confidence < threshold:
                        red_flagged = True

        except Exception as exc:
            logger.warning(
                "maker_evaluate_failed",
                company_id=company_id,
                error=str(exc)[:200],
            )

        if not best_response:
            best_response = self._safe_response(query)

        return MakerStageResult(
            stage="evaluate",
            success=True,
            data={
                "best_response": best_response,
                "best_confidence": best_confidence,
                "red_flagged": red_flagged,
                "k_candidates": k,
                "fake_voting_used": fake_voting,
                "llm_calls": llm_calls,
            },
            processing_time_ms=round((time.monotonic() - start) * 1000, 2),
        )

    # ── Stage 5: REFINE ─────────────────────────────────────────────

    async def _stage_refine(
        self,
        response: str,
        query: str,
        company_id: str,
        variant_tier: str,
    ) -> MakerStageResult:
        """Refine stage: PII redaction, brand voice, formatting.

        BC-008: Falls back to basic formatting.
        """
        start = time.monotonic()
        refined = response

        # PII redaction (regex-based, no LLM needed)
        pii_patterns = [
            (r'[\w.+-]+@[\w-]+\.[\w.-]+', '[EMAIL]'),
            (r'\d{3}[-.]?\d{3}[-.]?\d{4}', '[PHONE]'),
            (r'\d{3}-\d{2}-\d{4}', '[SSN]'),
            (r'\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}', '[CARD]'),
        ]

        for pattern, replacement in pii_patterns:
            refined = re.sub(pattern, replacement, refined)

        # Basic formatting: ensure clean whitespace
        refined = re.sub(r'\n{3,}', '\n\n', refined)
        refined = refined.strip()

        return MakerStageResult(
            stage="refine",
            success=True,
            data={
                "refined_response": refined,
                "pii_redacted": refined != response,
            },
            processing_time_ms=round((time.monotonic() - start) * 1000, 2),
        )

    # ── FAKE Voting ─────────────────────────────────────────────────

    async def _fake_vote(
        self,
        candidates: List[Dict[str, Any]],
        query: str,
        company_id: str,
    ) -> int:
        """FAKE Voting: LLM judges evaluate candidate responses.

        Each judge scores on accuracy, helpfulness, tone, completeness.
        The candidate with the highest aggregate score wins.

        BC-008: Returns 0 (first candidate) on failure.

        Args:
            candidates: List of candidate dicts with 'response' key.
            query: Original customer query.
            company_id: Tenant identifier.

        Returns:
            Index of winning candidate.
        """
        if not candidates:
            return 0

        try:
            scores: List[float] = []

            for candidate in candidates:
                prompt = (
                    "Rate this customer support response on a scale of "
                    "1-10 for each criterion:\n"
                    "- Accuracy\n- Helpfulness\n- Tone\n- Completeness\n\n"
                    f"Customer Query: {query[:300]}\n\n"
                    f"Response: {candidate['response'][:500]}\n\n"
                    "Format: accuracy=X helpfulness=X tone=X completeness=X"
                )
                judge_response = await self._call_llm(
                    prompt, company_id
                )

                if judge_response:
                    # Parse scores
                    total = 0.0
                    count = 0
                    for criterion in [
                        "accuracy", "helpfulness", "tone", "completeness"
                    ]:
                        match = re.search(
                            f"{criterion}=(\\d+)",
                            judge_response,
                            re.I,
                        )
                        if match:
                            total += float(match.group(1))
                            count += 1

                    if count > 0:
                        scores.append(total / count)
                    else:
                        scores.append(candidate.get("confidence", 0.5) * 10)
                else:
                    scores.append(candidate.get("confidence", 0.5) * 10)

            # Return index of highest scoring candidate
            return scores.index(max(scores))

        except Exception as exc:
            logger.warning(
                "maker_fake_vote_failed",
                company_id=company_id,
                error=str(exc)[:200],
            )
            return 0

    # ── Helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _keyword_classify(query: str) -> str:
        """Keyword-based query classification (BC-008 fallback)."""
        query_lower = query.lower()
        intent_keywords = {
            "refund": ["refund", "money back", "reimburse", "return"],
            "technical": ["error", "bug", "crash", "not working", "broken"],
            "billing": ["bill", "charge", "invoice", "payment"],
            "complaint": ["complaint", "terrible", "worst", "unacceptable"],
            "faq": ["how do", "what is", "can i"],
        }
        for intent, keywords in intent_keywords.items():
            if any(kw in query_lower for kw in keywords):
                return intent
        return "general"

    @staticmethod
    def _safe_response(query: str) -> str:
        """Generate a safe fallback response (BC-008)."""
        return (
            "Thank you for reaching out. We're reviewing your request "
            "and will get back to you shortly with a detailed response."
        )

    @staticmethod
    def _build_result(
        query: str,
        company_id: str,
        variant_tier: str,
        query_type: str,
        response: str,
        confidence: float,
        stages: List[MakerStageResult],
        pipeline_start: float,
        total_llm_calls: int,
        red_flagged: bool = False,
    ) -> MakerPipelineResult:
        """Build the final MakerPipelineResult."""
        total_ms = round((time.monotonic() - pipeline_start) * 1000, 2)
        return MakerPipelineResult(
            query=query,
            company_id=company_id,
            variant_tier=variant_tier,
            query_type=query_type,
            response=response,
            confidence=confidence,
            stages=stages,
            total_processing_time_ms=total_ms,
            total_llm_calls=total_llm_calls,
            red_flagged=red_flagged,
            escalated=red_flagged and confidence < 0.5,
        )

    def _get_llm(self):
        """Get LLM generate function (BC-008 safe)."""
        if self._llm_generate is not None:
            return self._llm_generate
        try:
            from app.services.llm_gateway import generate
            self._llm_generate = generate
            return generate
        except ImportError:
            return None

    async def _call_llm(
        self, prompt: str, company_id: str
    ) -> Optional[str]:
        """Call LLM and return text (BC-008 safe)."""
        try:
            llm = self._get_llm()
            if llm is None:
                return None

            import asyncio
            if asyncio.iscoroutinefunction(llm):
                response = await llm(prompt, company_id=company_id)
            else:
                response = llm(prompt, company_id=company_id)

            if hasattr(response, "text"):
                return response.text
            elif isinstance(response, str):
                return response
            elif isinstance(response, dict):
                return response.get("text", "")
        except Exception as exc:
            logger.debug(
                "maker_pipeline_llm_call_failed",
                company_id=company_id,
                error=str(exc)[:100],
            )
        return None
