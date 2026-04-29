"""
CLARA Quality Gate Pipeline (F-150)

5-stage quality gate that every AI response must pass before delivery:
1. Structure Check — validates format (greeting, body, length)
2. Logic Check — validates factual consistency, query relevance
3. Brand Check — validates brand voice compliance
4. Tone Check — validates tone matches customer sentiment
5. Delivery Check — final validation (PII, formatting)

GAP FIXES:
- W9-GAP-002 (CRITICAL): Per-stage timeout (3s) + pipeline timeout (15s)
- W9-GAP-018 (MEDIUM): Default brand voice for new tenants

Parent: Week 9 Day 6 (Monday)
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from app.logger import get_logger

logger = get_logger("clara_quality_gate")


class CLARAStage(str, Enum):
    STRUCTURE_CHECK = "structure_check"
    LOGIC_CHECK = "logic_check"
    BRAND_CHECK = "brand_check"
    TONE_CHECK = "tone_check"
    DELIVERY_CHECK = "delivery_check"


class StageResult(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    TIMEOUT_PASS = "timeout_pass"
    ERROR = "error"


@dataclass
class StageOutput:
    stage: CLARAStage
    result: StageResult
    score: float  # 0.0-1.0
    issues: List[str]
    suggestions: List[str]
    processing_time_ms: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BrandVoiceConfig:
    """Brand voice configuration for CLARA Brand Check.

    GAP-018: Sensible defaults for new tenants without brand voice setup.
    Only fails Brand Check if tenant has explicitly configured custom rules.
    """

    tone: str = "professional"  # professional/friendly/casual
    formality: str = "medium"  # low/medium/high
    prohibited_words: List[str] = field(default_factory=list)
    max_length: int = 500
    required_sign_off: bool = False
    custom_rules: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def defaults(cls) -> "BrandVoiceConfig":
        """GAP-018: Sensible defaults for new tenants."""
        return cls()

    @property
    def is_custom_configured(self) -> bool:
        """True if tenant has explicitly configured custom brand rules.

        Considers: prohibited_words, custom_rules, non-default formality,
        non-default max_length, required_sign_off, non-default tone.
        """
        if self.prohibited_words or self.custom_rules:
            return True
        if self.required_sign_off:
            return True
        if self.max_length != 500:
            return True
        if self.formality != "medium":
            return True
        if self.tone != "professional":
            return True
        return False


@dataclass
class CLARAResult:
    overall_pass: bool
    overall_score: float  # 0.0-1.0
    stages: List[StageOutput]
    total_processing_time_ms: float
    final_response: Optional[str]
    pipeline_timed_out: bool = False


class CLARAQualityGate:
    """5-Stage CLARA Quality Gate Pipeline (F-150).

    Stages run sequentially. Each has configurable timeout (GAP-002).
    Brand Check has defaults for new tenants (GAP-018).
    """

    DEFAULT_STAGE_TIMEOUT = 3.0  # seconds
    DEFAULT_PIPELINE_TIMEOUT = 15.0  # seconds

    def __init__(
        self,
        smart_router=None,
        brand_voice: Optional[BrandVoiceConfig] = None,
        stage_timeout_seconds: float = DEFAULT_STAGE_TIMEOUT,
        pipeline_timeout_seconds: float = DEFAULT_PIPELINE_TIMEOUT,
    ):
        self.smart_router = smart_router
        self.brand_voice = brand_voice or BrandVoiceConfig.defaults()
        self.stage_timeout = stage_timeout_seconds
        self.pipeline_timeout = pipeline_timeout_seconds

    async def evaluate(
        self,
        response: str,
        query: str,
        company_id: str = "",
        customer_sentiment: float = 0.7,
        context: Optional[Dict] = None,
    ) -> CLARAResult:
        """Run full 5-stage CLARA pipeline.

        GAP-002: Pipeline-level timeout wraps all stages.
        """
        pipeline_start = time.monotonic()
        stages: List[StageOutput] = []

        stage_funcs = [
            (CLARAStage.STRUCTURE_CHECK, self._structure_check),
            (CLARAStage.LOGIC_CHECK, self._logic_check),
            (CLARAStage.BRAND_CHECK, self._brand_check),
            (CLARAStage.TONE_CHECK, self._tone_check),
            (CLARAStage.DELIVERY_CHECK, self._delivery_check),
        ]

        pipeline_timed_out = False

        try:
            # GAP-002: Wrap entire pipeline in timeout
            await asyncio.wait_for(
                self._run_all_stages(
                    stage_funcs,
                    stages,
                    response,
                    query,
                    customer_sentiment,
                    context,
                    company_id,
                ),
                timeout=self.pipeline_timeout,
            )
        except asyncio.TimeoutError:
            pipeline_timed_out = True
            logger.warning(
                "clara_pipeline_timeout",
                company_id=company_id,
                timeout=self.pipeline_timeout,
            )
            # Add missing stages as timeout_pass
            completed_stages = {s.stage for s in stages}
            for stage_enum, _ in stage_funcs:
                if stage_enum not in completed_stages:
                    stages.append(
                        StageOutput(
                            stage=stage_enum,
                            result=StageResult.TIMEOUT_PASS,
                            score=0.5,
                            issues=[f"{stage_enum.value} timed out (pipeline)"],
                            suggestions=[],
                            processing_time_ms=self.pipeline_timeout * 1000,
                            metadata={"timeout": True},
                        )
                    )

        # Calculate overall score and pass/fail
        scored_stages = [
            s for s in stages if s.result in (StageResult.PASS, StageResult.FAIL)
        ]
        timeout_stages = [s for s in stages if s.result == StageResult.TIMEOUT_PASS]

        if scored_stages:
            overall_score = sum(s.score for s in scored_stages) / len(scored_stages)
        elif timeout_stages:
            overall_score = 0.5
        else:
            overall_score = 0.0

        # FAIL only if a scored stage fails (TIMEOUT_PASS doesn't fail)
        has_failure = any(s.result == StageResult.FAIL for s in scored_stages)
        overall_pass = not has_failure

        total_ms = round((time.monotonic() - pipeline_start) * 1000, 2)

        # Build final response (clean up based on stage suggestions)
        final_response = self._apply_suggestions(response, stages)

        return CLARAResult(
            overall_pass=overall_pass,
            overall_score=round(overall_score, 4),
            stages=stages,
            total_processing_time_ms=total_ms,
            final_response=final_response,
            pipeline_timed_out=pipeline_timed_out,
        )

    async def _run_all_stages(
        self,
        stage_funcs: List,
        stages: List[StageOutput],
        response: str,
        query: str,
        customer_sentiment: float,
        context: Optional[Dict],
        company_id: str,
    ) -> None:
        """Run all stages sequentially with per-stage timeout."""
        for stage_enum, stage_func in stage_funcs:
            output = await self._run_stage(
                stage_enum,
                stage_func,
                response=response,
                query=query,
                customer_sentiment=customer_sentiment,
                context=context,
                company_id=company_id,
            )
            stages.append(output)

    async def _run_stage(
        self,
        stage: CLARAStage,
        stage_func: Any,
        **kwargs,
    ) -> StageOutput:
        """Run a single stage with timeout (GAP-002 FIX)."""
        start = time.monotonic()
        try:
            output = await asyncio.wait_for(
                stage_func(**kwargs),
                timeout=self.stage_timeout,
            )
            output.processing_time_ms = round(
                (time.monotonic() - start) * 1000,
                2,
            )
            return output
        except asyncio.TimeoutError:
            logger.warning(
                "clara_stage_timeout",
                stage=stage.value,
                timeout=self.stage_timeout,
            )
            return StageOutput(
                stage=stage,
                result=StageResult.TIMEOUT_PASS,
                score=0.5,
                issues=[f"{stage.value} timed out"],
                suggestions=[],
                processing_time_ms=round(self.stage_timeout * 1000, 2),
                metadata={"timeout": True},
            )
        except Exception as exc:
            logger.error(
                "clara_stage_error",
                stage=stage.value,
                error=str(exc),
            )
            return StageOutput(
                stage=stage,
                result=StageResult.ERROR,
                score=0.0,
                issues=[f"{stage.value} error: {str(exc)}"],
                suggestions=[],
                processing_time_ms=round((time.monotonic() - start) * 1000, 2),
                metadata={"error": True},
            )

    # ── Stage 1: Structure Check ─────────────────────────────────────

    async def _structure_check(
        self,
        response: str,
        query: str,
        **kwargs,
    ) -> StageOutput:
        """Validate response structure."""
        issues: List[str] = []
        suggestions: List[str] = []

        if not response or not response.strip():
            return StageOutput(
                stage=CLARAStage.STRUCTURE_CHECK,
                result=StageResult.FAIL,
                score=0.0,
                issues=["Response is empty"],
                suggestions=["Generate a non-empty response"],
                processing_time_ms=0,
            )

        stripped = response.strip()
        words = stripped.split()

        # Too short (< 5 words)
        if len(words) < 5:
            issues.append("Response too short (< 5 words)")
            suggestions.append("Expand response to at least 5 words")
            score = 0.3
        # Wall of text (> 500 words)
        elif len(words) > 500:
            issues.append("Response too long (> 500 words)")
            suggestions.append("Condense response to under 500 words")
            score = 0.4
        else:
            score = 0.9

        # Check for repeated phrases
        sentences = re.split(r"[.!?]+", stripped)
        seen_sentences: Dict[str, int] = {}
        for sentence in sentences:
            s_norm = sentence.strip().lower()
            if s_norm and len(s_norm) > 10:
                seen_sentences[s_norm] = seen_sentences.get(s_norm, 0) + 1

        repeated = [s for s, c in seen_sentences.items() if c > 1]
        if repeated:
            issues.append(f"Repeated phrases detected: {len(repeated)}")
            score -= 0.2

        # Check for excessive whitespace
        if len(re.findall(r"\n\n\n+", stripped)):
            issues.append("Excessive blank lines")
            score -= 0.1

        score = max(0.0, min(1.0, score))
        result = StageResult.PASS if score >= 0.7 else StageResult.FAIL

        return StageOutput(
            stage=CLARAStage.STRUCTURE_CHECK,
            result=result,
            score=round(score, 4),
            issues=issues,
            suggestions=suggestions,
            processing_time_ms=0,
        )

    # ── Stage 2: Logic Check ────────────────────────────────────────

    async def _logic_check(
        self,
        response: str,
        query: str,
        **kwargs,
    ) -> StageOutput:
        """Validate logical consistency.

        D6-GAP-02 FIX: Uses context dict for additional data like
        ticket_id, customer_name, order_details to validate relevance.
        """
        issues: List[str] = []
        suggestions: List[str] = []
        response_lower = response.lower()
        query_lower = query.lower()
        context = kwargs.get("context") or {}

        # Check query relevance: keyword overlap
        query_words = set(re.findall(r"\b\w{3,}\b", query_lower))
        response_words = set(re.findall(r"\b\w{3,}\b", response_lower))

        if query_words and response_words:
            overlap = len(query_words & response_words)
            relevance = overlap / min(len(query_words), 20)
            if relevance < 0.1:
                issues.append("Low relevance to original query")
                suggestions.append("Ensure response addresses the query topic")
                score = 0.3
            else:
                score = 0.7 + relevance * 0.3
        else:
            score = 0.7

        # D6-GAP-02: Check if context-provided entities appear in response
        if context:
            for ctx_key, ctx_val in context.items():
                if not ctx_val or not isinstance(ctx_val, str):
                    continue
                ctx_val_lower = ctx_val.lower()
                # If context has order_id, ticket_id, etc., check they appear
                if ctx_key in ("order_id", "ticket_id", "customer_name"):
                    if ctx_val_lower not in response_lower and len(ctx_val) > 3:
                        issues.append(
                            f"Context key '{ctx_key}' value not referenced in response"
                        )
                        score -= 0.05

        # Check for contradictions
        contradiction_patterns = [
            (r"yes.*but\s+no", "Yes followed by No (contradiction)"),
            (r"correct.*incorrect", "Correct followed by Incorrect"),
            (r"will.*won't\b", "Will followed by won't"),
            (r"can't.*can\b", "Can't followed by can"),
        ]
        for pattern, desc in contradiction_patterns:
            if re.search(pattern, response_lower):
                issues.append(desc)
                score -= 0.2

        # Check "I don't know" followed by detailed answer
        if re.search(r"(?:i don'?t know|i'?m not sure|uncertain)", response_lower):
            # If response is long after "I don't know", that's odd
            after_unknown = re.split(
                r"i don'?t know|i'?m not sure|uncertain",
                response_lower,
                maxsplit=1,
            )
            if len(after_unknown) > 1 and len(after_unknown[1].split()) > 20:
                issues.append('"I don\'t know" followed by detailed answer')
                score -= 0.1

        score = max(0.0, min(1.0, score))
        result = StageResult.PASS if score >= 0.7 else StageResult.FAIL

        return StageOutput(
            stage=CLARAStage.LOGIC_CHECK,
            result=result,
            score=round(score, 4),
            issues=issues,
            suggestions=suggestions,
            processing_time_ms=0,
        )

    # ── Stage 3: Brand Check (GAP-018) ──────────────────────────────

    async def _brand_check(
        self,
        response: str,
        **kwargs,
    ) -> StageOutput:
        """Validate brand voice compliance.

        GAP-018 FIX: If brand voice is NOT custom configured, use defaults
        and always PASS (new tenant has no rules to violate).
        """
        issues: List[str] = []
        suggestions: List[str] = []
        score = 1.0

        # GAP-018: If no custom brand rules, always pass
        if not self.brand_voice.is_custom_configured:
            return StageOutput(
                stage=CLARAStage.BRAND_CHECK,
                result=StageResult.PASS,
                score=1.0,
                issues=[],
                suggestions=[],
                processing_time_ms=0,
                metadata={"used_defaults": True},
            )

        response_lower = response.lower()

        # Check prohibited words
        for word in self.brand_voice.prohibited_words:
            word_lower = word.lower()
            # Normalize: remove non-alphanumeric for comparison
            response_normalized = re.sub(r"[^a-z0-9\s]", "", response_lower)
            word_normalized = re.sub(r"[^a-z0-9\s]", "", word_lower)
            if word_normalized in response_normalized:
                issues.append(f"Prohibited word used: '{word}'")
                score -= 0.3  # significant deduction

        # Check max length
        word_count = len(response.split())
        if word_count > self.brand_voice.max_length:
            issues.append(
                "Response exceeds max length "
                f"({word_count}/{self.brand_voice.max_length} words)"
            )
            suggestions.append(f"Shorten response to under {
                    self.brand_voice.max_length} words")
            score -= 0.25

        # Check required sign-off
        if self.brand_voice.required_sign_off:
            sign_offs = [
                "best regards",
                "sincerely",
                "thanks",
                "thank you",
                "regards",
                "cheers",
                "warmly",
            ]
            if not any(so in response_lower for so in sign_offs):
                issues.append("Missing required sign-off")
                suggestions.append("Add a sign-off to the response")
                score -= 0.25

        # Check formality level
        formality = self.brand_voice.formality.lower()
        casual_words = [
            r"\bhey\b",
            r"\byo\b",
            r"\bsup\b",
            r"\bgonna\b",
            r"\bwanna\b",
            r"\blol\b",
            r"\bbtw\b",
            r"\bbrb\b",
        ]
        if formality in ("medium", "high"):
            found_casual = [
                w.strip(r"\b") for w in casual_words if re.search(w, response_lower)
            ]
            if found_casual:
                issues.append(
                    f"Informal language for {formality} formality: {found_casual}"
                )
                score -= 0.3

        score = max(0.0, min(1.0, score))
        result = StageResult.PASS if score >= 0.8 else StageResult.FAIL

        return StageOutput(
            stage=CLARAStage.BRAND_CHECK,
            result=result,
            score=round(score, 4),
            issues=issues,
            suggestions=suggestions,
            processing_time_ms=0,
            metadata={"used_defaults": False},
        )

    # ── Stage 4: Tone Check ─────────────────────────────────────────

    async def _tone_check(
        self,
        response: str,
        customer_sentiment: float = 0.7,
        **kwargs,
    ) -> StageOutput:
        """Validate tone matches customer sentiment."""
        issues: List[str] = []
        suggestions: List[str] = []
        response_lower = response.lower()
        score = 0.8  # base score

        # Angry customer (sentiment < 0.3) → need empathetic tone
        if customer_sentiment < 0.3:
            empathy_words = [
                "sorry",
                "apologize",
                "understand",
                "frustrating",
                "inconvenience",
                "unfortunate",
                "appreciate your patience",
            ]
            has_empathy = any(w in response_lower for w in empathy_words)
            if not has_empathy:
                issues.append("Customer is frustrated but response lacks empathy")
                suggestions.append("Add empathetic language for frustrated customer")
                score -= 0.35
            else:
                score = 0.95

        # Happy customer (sentiment > 0.7) → match positive tone
        elif customer_sentiment > 0.7:
            positive_words = ["great", "glad", "happy", "pleased", "wonderful"]
            has_positive = any(w in response_lower for w in positive_words)
            if not has_positive:
                issues.append("Customer is happy but response is cold/formal")
                suggestions.append("Add warm, positive language to match customer mood")
                score -= 0.35

        # Check for aggressive language (never OK) — per-word deduction
        aggressive_words = ["calm down", "obviously", "clearly", "you should know"]
        found_aggressive = [w for w in aggressive_words if w in response_lower]
        if found_aggressive:
            issues.append(f"Aggressive language detected: {found_aggressive}")
            score -= 0.3 * len(found_aggressive)

        score = max(0.0, min(1.0, score))
        result = StageResult.PASS if score >= 0.5 else StageResult.FAIL

        return StageOutput(
            stage=CLARAStage.TONE_CHECK,
            result=result,
            score=round(score, 4),
            issues=issues,
            suggestions=suggestions,
            processing_time_ms=0,
        )

    # ── Stage 5: Delivery Check ─────────────────────────────────────

    async def _delivery_check(self, response: str, **kwargs) -> StageOutput:
        """Final delivery validation: PII, formatting, etc.

        D6-GAP-03 FIX: Context-aware PII detection — reduces false positives
        for order/tracking numbers that look like phone numbers.
        """
        issues: List[str] = []
        suggestions: List[str] = []
        score = 1.0
        context = kwargs.get("context") or {}

        if not response or not response.strip():
            return StageOutput(
                stage=CLARAStage.DELIVERY_CHECK,
                result=StageResult.FAIL,
                score=0.0,
                issues=["Empty response at delivery"],
                suggestions=["Generate response before delivery"],
                processing_time_ms=0,
            )

        # PII Detection
        pii_patterns = [
            (r"[\w.+-]+@[\w-]+\.[\w.-]+", "email address"),
            # D6-GAP-03: Use context-aware phone detection
            (r"\d{3}[-.]?\d{3}[-.]?\d{4}", "phone number"),
            (r"\d{3}-\d{2}-\d{4}", "SSN"),
            (r"\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}", "credit card"),
        ]
        for pattern, pii_type in pii_patterns:
            matches = re.findall(pattern, response)
            if not matches:
                continue
            # D6-GAP-03: Context-aware filtering for phone numbers
            if pii_type == "phone number":
                filtered_matches = self._filter_phone_false_positives(
                    matches, response, context
                )
                if filtered_matches:
                    issues.append(f"PII detected: {pii_type}")
                    suggestions.append(f"Remove {pii_type} from response")
                    score -= 0.25
            else:
                issues.append(f"PII detected: {pii_type}")
                suggestions.append(f"Remove {pii_type} from response")
                score -= 0.25

        # Broken markdown links
        broken_links = re.findall(r"\[[^\]]*\]\(\s*\)", response)
        if broken_links:
            issues.append(f"Broken markdown links: {len(broken_links)}")
            score -= 0.3

        # Excessive emojis (more than 3 per paragraph)
        paragraphs = response.split("\n\n")
        for i, para in enumerate(paragraphs):
            if not para.strip():
                continue
            emoji_count = len(
                re.findall(
                    r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF"
                    r"\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF"
                    r"\U00002702-\U000027B0\U0000FE00-\U0000FE0F"
                    r"\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F"
                    r"\U0001FA70-\U0001FAFF\U00002600-\U000026FF"
                    r"\U00002700-\U000027BF]",
                    para,
                )
            )
            if emoji_count > 3:
                issues.append(f"Excessive emojis in paragraph {
                        i + 1}: {emoji_count}")
                score -= 0.3

        score = max(0.0, min(1.0, score))
        result = StageResult.PASS if score >= 0.8 else StageResult.FAIL

        return StageOutput(
            stage=CLARAStage.DELIVERY_CHECK,
            result=result,
            score=round(score, 4),
            issues=issues,
            suggestions=suggestions,
            processing_time_ms=0,
        )

    # ── Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _filter_phone_false_positives(
        matches: List[str], response: str, context: Dict[str, Any]
    ) -> List[str]:
        """D6-GAP-03: Filter out false positive phone number matches.

        Removes matches that are actually order IDs, tracking numbers,
        or other non-phone-number patterns based on context.
        """
        filtered = []
        response_lower = response.lower()
        tracking_indicators = [
            "tracking",
            "order",
            "invoice",
            "receipt",
            "confirmation",
            "reference",
            "ticket",
            "case",
            "shipment",
            "parcel",
        ]
        for match in matches:
            # Check if the match appears near a tracking/order indicator
            match_pos = response_lower.find(match)
            if match_pos > 0:
                preceding = response_lower[max(0, match_pos - 30) : match_pos]
                following = response_lower[
                    match_pos + len(match) : match_pos + len(match) + 30
                ]
                surrounding = preceding + " " + following
                if any(indicator in surrounding for indicator in tracking_indicators):
                    continue  # Likely an order/tracking number, not a phone
            # Check if context explicitly marks this as a tracking/order number
            if context.get("has_tracking_number") or context.get("has_order_id"):
                continue
            filtered.append(match)
        return filtered

    def _apply_suggestions(self, response: str, stages: List[StageOutput]) -> str:
        """Apply basic fixes based on stage suggestions."""
        if not response:
            return response

        result = response
        for stage in stages:
            if stage.result == StageResult.FAIL:
                # Clean up whitespace issues from structure check
                if stage.stage == CLARAStage.STRUCTURE_CHECK:
                    result = re.sub(r"\n\n\n+", "\n\n", result)
                    result = result.strip()

        return result
