"""
AI-Powered Multi-Label Intent Classification Engine (F-062)

Classifies ticket text into primary + secondary intents using:
1. Smart Router AI classification (parwa/high_parwa variants)
2. Keyword-based fallback (always available, all variants)

Supports 12 intent types (6 core + 6 extended from technique_router).

GAP FIX:
- W9-GAP-008 (HIGH): Handles empty/whitespace-only input gracefully

Parent: Week 9 Day 6 (Monday)
"""

from __future__ import annotations

import time
import re
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from app.logger import get_logger

logger = get_logger("classification_engine")


class IntentType(str, Enum):
    """All supported intent types for classification."""

    # Core 6 (from ClassificationService)
    REFUND = "refund"
    TECHNICAL = "technical"
    BILLING = "billing"
    COMPLAINT = "complaint"
    FEATURE_REQUEST = "feature_request"
    GENERAL = "general"

    # Extended 6 (from technique_router trigger rules R13-R23)
    CANCELLATION = "cancellation"
    SHIPPING = "shipping"
    INQUIRY = "inquiry"
    ESCALATION = "escalation"
    ACCOUNT = "account"
    FEEDBACK = "feedback"


# Map IntentType → ClassificationService.IntentCategory for compatibility
INTENT_TO_CATEGORY_MAP: Dict[str, str] = {
    IntentType.REFUND.value: "refund",
    IntentType.TECHNICAL.value: "technical",
    IntentType.BILLING.value: "billing",
    IntentType.COMPLAINT.value: "complaint",
    IntentType.FEATURE_REQUEST.value: "feature_request",
    IntentType.GENERAL.value: "general",
    IntentType.CANCELLATION.value: "general",
    IntentType.SHIPPING.value: "technical",
    IntentType.INQUIRY.value: "general",
    IntentType.ESCALATION.value: "complaint",
    IntentType.ACCOUNT.value: "general",
    IntentType.FEEDBACK.value: "general",
}


@dataclass
class IntentResult:
    """Output of intent classification."""

    primary_intent: str  # IntentType value
    primary_confidence: float  # 0.0-1.0
    # [(intent, confidence), ...] max 3
    secondary_intents: List[Tuple[str, float]]
    all_scores: Dict[str, float]  # intent -> confidence for all types
    classification_method: str  # "keyword", "ai", "fallback"
    processing_time_ms: float
    model_used: Optional[str] = None


# ── Keyword Patterns (enhanced) ──────────────────────────────────────

INTENT_PATTERNS: Dict[str, Dict[str, Any]] = {
    IntentType.REFUND.value: {
        "keywords": [
            "refund",
            "money back",
            "return",
            "reimburse",
            "credit back",
            "chargeback",
            "cancel order",
            "get my money",
            "want my money back",
            "refund policy",
            "refundable",
            "non-refundable",
        ],
        "weight": 1.0,
    },
    IntentType.TECHNICAL.value: {
        "keywords": [
            "error",
            "bug",
            "not working",
            "broken",
            "crash",
            "issue",
            "problem",
            "doesn't work",
            "failed",
            "glitch",
            "not loading",
            "slow",
            "connection",
            "timeout",
            "offline",
            "down",
            "500 error",
            "404",
            "exception",
            "stack trace",
        ],
        "weight": 1.0,
    },
    IntentType.BILLING.value: {
        "keywords": [
            "bill",
            "invoice",
            "charge",
            "payment",
            "subscription",
            "price",
            "cost",
            "fee",
            "overcharge",
            "duplicate charge",
            "unauthorized charge",
            "subscription cancel",
            "renewal",
            "billing",
            "receipt",
            "transaction",
        ],
        "weight": 1.0,
    },
    IntentType.COMPLAINT.value: {
        "keywords": [
            "complaint",
            "unhappy",
            "disappointed",
            "frustrated",
            "angry",
            "terrible",
            "awful",
            "worst",
            "horrible",
            "unacceptable",
            "speak to manager",
            "escalate",
            "report",
            "formal complaint",
            "outrageous",
            "appalling",
            "disgusting",
        ],
        "weight": 1.2,  # weighted higher for sensitivity
    },
    IntentType.FEATURE_REQUEST.value: {
        "keywords": [
            "feature",
            "suggestion",
            "would be great",
            "wish you had",
            "please add",
            "would like to see",
            "enhancement",
            "improve",
            "new functionality",
            "missing feature",
            "roadmap",
            "can you add",
            "it would be nice",
        ],
        "weight": 1.0,
    },
    IntentType.GENERAL.value: {
        "keywords": [],
        "weight": 0.3,  # low weight — only matches when nothing else does
    },
    IntentType.CANCELLATION.value: {
        "keywords": [
            "cancel subscription",
            "unsubscribe",
            "stop service",
            "terminate",
            "close account",
            "end subscription",
            "deactivate",
            "cancel my plan",
            "i want to cancel",
            "please cancel",
            "cancel right now",
            "cancel immediately",
            "cancel my subscription",
            "cancel my",
            "cancel",
        ],
        "weight": 1.0,
    },
    IntentType.SHIPPING.value: {
        "keywords": [
            "ship",
            "shipping",
            "deliver",
            "delivery",
            "track",
            "package",
            "order status",
            "courier",
            "transit",
            "parcel",
            "tracking number",
            "estimated delivery",
            "shipping address",
            "lost package",
        ],
        "weight": 1.0,
    },
    IntentType.INQUIRY.value: {
        "keywords": [
            "question",
            "how do i",
            "what is",
            "can you explain",
            "information",
            "documentation",
            "help me understand",
            "guide",
            "wondering",
            "curious",
            "tell me about",
            "i'd like to know",
        ],
        "weight": 0.8,
    },
    IntentType.ESCALATION.value: {
        "keywords": [
            "escalate",
            "manager",
            "supervisor",
            "senior",
            "higher up",
            "speak to someone",
            "not resolved",
            "still waiting",
            "unacceptable",
            "take this further",
            "next level",
        ],
        "weight": 1.1,
    },
    IntentType.ACCOUNT.value: {
        "keywords": [
            "account",
            "profile",
            "login",
            "password reset",
            "reset password",
            "reset my password",
            "verify",
            "mfa",
            "two-factor",
            "email change",
            "username",
            "settings",
            "update account",
            "delete account",
            "deactivate account",
            "password",
        ],
        "weight": 1.0,
    },
    IntentType.FEEDBACK.value: {
        "keywords": [
            "feedback",
            "suggestion",
            "opinion",
            "thought",
            "experience",
            "rating",
            "review",
            "love your product",
            "keep up",
            "suggestion box",
            "improve",
            "great job",
            "amazing",
            "keep it up",
        ],
        "weight": 0.9,
    },
}


class KeywordClassifier:
    """Enhanced keyword-based multi-label intent classifier."""

    MIN_TEXT_LENGTH = 3

    def classify(self, text: str) -> IntentResult:
        """Classify text into primary + secondary intents using keywords."""
        start = time.monotonic()
        text_lower = text.lower()

        # Score each intent
        scores: Dict[str, float] = {}
        for intent, config in INTENT_PATTERNS.items():
            weight = config.get("weight", 1.0)
            keywords = config.get("keywords", [])
            if not keywords:
                # General: give tiny base score (won't dominate after
                # normalization)
                scores[intent] = 0.01
                continue

            raw_score = sum(len(kw.split()) for kw in keywords if kw in text_lower)
            scores[intent] = raw_score * weight

        # Ensure general has a small presence if nothing else matched
        max_non_general = max(
            (v for k, v in scores.items() if k != IntentType.GENERAL.value),
            default=0,
        )
        if max_non_general == 0:
            scores[IntentType.GENERAL.value] = max(
                scores[IntentType.GENERAL.value],
                0.1,
            )

        # Normalize scores
        total = sum(scores.values())
        if total > 0:
            scores = {k: round(v / total, 4) for k, v in scores.items()}
        else:
            scores = {intent: 0.0 for intent in IntentType}

        # Determine primary intent
        primary_intent = max(scores, key=scores.get)
        primary_confidence = scores[primary_intent]

        # Cap at 0.95 (reserve 1.0 for human corrections)
        primary_confidence = min(primary_confidence, 0.95)

        # General intent: confidence ceiling (it's a catch-all)
        if primary_intent == IntentType.GENERAL.value:
            primary_confidence = min(primary_confidence, 0.5)

        # Determine secondary intents (up to 3, exclude primary)
        secondary = sorted(
            [(k, v) for k, v in scores.items() if k != primary_intent and v > 0.05],
            key=lambda x: x[1],
            reverse=True,
        )[:3]

        elapsed = round((time.monotonic() - start) * 1000, 2)

        return IntentResult(
            primary_intent=primary_intent,
            primary_confidence=primary_confidence,
            secondary_intents=secondary,
            all_scores=scores,
            classification_method="keyword",
            processing_time_ms=elapsed,
        )


class ClassificationEngine:
    """AI-Powered Multi-Label Intent Classifier (F-062).

    Uses Smart Router for AI classification with keyword-based fallback.
    Designed to work alongside existing ClassificationService.
    """

    def __init__(self, smart_router=None):
        self.smart_router = smart_router
        self._keyword_classifier = KeywordClassifier()

    async def classify(
        self,
        text: str,
        company_id: str = "",
        variant_type: str = "parwa",
        use_ai: bool = True,
    ) -> IntentResult:
        """Classify text into primary + secondary intents.

        GAP-008 FIX: Empty/whitespace → safe default.
        D6-GAP-07 FIX: Handle non-string company_id gracefully.
        """
        # D6-GAP-07: Normalize company_id to string
        if company_id is not None:
            company_id = str(company_id)
        else:
            company_id = ""

        # ── GAP-008: Input validation ────────────────────────────
        if not text or not isinstance(text, str):
            logger.info(
                "low_confidence_classification",
                reason="empty_input",
                company_id=company_id,
            )
            return self._default_result("empty_input")

        cleaned = text.strip()
        if len(cleaned) < self._keyword_classifier.MIN_TEXT_LENGTH:
            logger.info(
                "low_confidence_classification",
                reason="too_short",
                text_length=len(cleaned),
                company_id=company_id,
            )
            return self._default_result("too_short")

        # ── AI classification (parwa/high_parwa only) ────────────
        if use_ai and self.smart_router and variant_type in ("parwa", "high_parwa"):
            try:
                return await self._classify_with_ai(
                    cleaned,
                    company_id,
                    variant_type,
                )
            except Exception as exc:
                logger.warning(
                    "ai_classification_failed",
                    error=str(exc),
                    company_id=company_id,
                )

        # ── Fallback to keyword classification ────────────────────
        return self._keyword_classifier.classify(cleaned)

    async def _classify_with_ai(
        self,
        text: str,
        company_id: str,
        variant_type: str,
    ) -> IntentResult:
        """Use Smart Router for AI-powered classification."""
        start = time.monotonic()

        prompt = (
            "Classify this customer support message into intents.\n"
            'Return JSON: {"primary": "<intent>", "secondary": [{"intent": "<intent>", "confidence": <float>}], '
            '"confidences": {"<intent>": <float>, ...}}\n\n'
            f"Valid intents: {', '.join(t.value for t in IntentType)}\n\n"
            f"Message: {text[:500]}"
        )

        # Route through Smart Router light tier
        from app.core.smart_router import SmartRouter

        if not isinstance(self.smart_router, SmartRouter) and not hasattr(
            self.smart_router, "async_execute_llm_call"
        ):
            return self._keyword_classifier.classify(text)

        response = await self.smart_router.async_execute_llm_call(
            prompt=prompt,
            model_tier="light",
            step_type="intent_classification",
            company_id=company_id,
        )

        result = self._parse_ai_response(
            response,
            company_id,
            variant_type,
            start,
        )
        return result

    def _parse_ai_response(
        self,
        response: Dict[str, Any],
        company_id: str,
        variant_type: str,
        start_time: float,
    ) -> IntentResult:
        """Parse Smart Router response into IntentResult."""
        elapsed = round((time.monotonic() - start_time) * 1000, 2)

        if not response or "content" not in response:
            return self._keyword_classifier.classify("")

        content = response["content"]
        model_used = response.get("model_used", "unknown")

        # Extract JSON from response
        try:
            # Handle markdown fences
            json_match = re.search(r"```(?:json)?\s*(.*?)```", content, re.DOTALL)
            json_str = json_match.group(1) if json_match else content
            data = json.loads(json_str)
        except (json.JSONDecodeError, AttributeError):
            return self._keyword_classifier.classify("")

        # Validate primary intent
        primary = data.get("primary", "general")
        primary = self._safe_intent_from_string(primary)

        # Parse confidences
        confidences = data.get("confidences", {})
        all_scores: Dict[str, float] = {}
        for intent_type in IntentType:
            val = confidences.get(intent_type.value, 0.0)
            all_scores[intent_type.value] = max(0.0, min(1.0, float(val)))

        # Ensure primary has highest score
        all_scores[primary] = max(all_scores.get(primary, 0.5), 0.5)
        primary_confidence = all_scores[primary]
        primary_confidence = min(primary_confidence, 0.95)

        # Parse secondary
        secondary_raw = data.get("secondary", [])
        secondary: List[Tuple[str, float]] = []
        seen = {primary}
        for item in secondary_raw[:3]:
            intent = self._safe_intent_from_string(item.get("intent", ""))
            conf = max(0.0, min(1.0, float(item.get("confidence", 0.0))))
            if intent not in seen and conf > 0.05:
                secondary.append((intent, conf))
                seen.add(intent)

        return IntentResult(
            primary_intent=primary,
            primary_confidence=primary_confidence,
            secondary_intents=secondary,
            all_scores=all_scores,
            classification_method="ai",
            processing_time_ms=elapsed,
            model_used=model_used,
        )

    @staticmethod
    def _safe_intent_from_string(value: str) -> str:
        """Convert string to valid IntentType value.

        Handles None, non-string types, empty, and whitespace gracefully.
        """
        if not value or not isinstance(value, str):
            return IntentType.GENERAL.value
        value_lower = value.strip().lower()
        if not value_lower:
            return IntentType.GENERAL.value
        for intent in IntentType:
            if intent.value == value_lower:
                return intent.value
        return IntentType.GENERAL.value

    def _default_result(self, reason: str) -> IntentResult:
        """GAP-008: Return safe default for empty/invalid input."""
        return IntentResult(
            primary_intent=IntentType.GENERAL.value,
            primary_confidence=0.0,
            secondary_intents=[],
            all_scores={intent.value: 0.0 for intent in IntentType},
            classification_method="fallback",
            processing_time_ms=0.0,
        )
