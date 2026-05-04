"""
Signal Extraction Layer (SG-13)

Extracts 10 real-time signals from each ticket query:
1. Intent — keyword-based classification
2. Sentiment — lexicon-based 0.0-1.0 score
3. Complexity — multi-factor 0.0-1.0 score
4. Monetary Value — multi-currency extraction (W9-GAP-017)
5. Customer Tier — from metadata
6. Turn Count — conversation turn count
7. Previous Response Status — accepted/rejected/corrected/none
8. Reasoning Loop Detection — repeated similar queries
9. Resolution Path Count — estimated resolution approaches
10. Query Breadth — multi-topic detection 0.0-1.0

GAP FIXES:
- W9-GAP-007 (HIGH): Cache key includes variant_type for isolation
- W9-GAP-017 (MEDIUM): Multi-currency support ($ £ € ¥ ₹ USD EUR GBP INR)

Parent: Week 9 Day 6 (Monday)
"""

from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

from app.logger import get_logger

logger = get_logger("signal_extraction")

# ── Currency Conversion Rates to USD (W9-GAP-017) ────────────────────

CURRENCY_TO_USD: Dict[str, float] = {
    "USD": 1.0, "$": 1.0,
    "EUR": 1.09, "€": 1.09,
    "GBP": 1.27, "£": 1.27,
    "INR": 0.012, "₹": 0.012,
    "JPY": 0.0067, "¥": 0.0067,
}

# Multi-currency regex (W9-GAP-017): matches $500, £1,200.50, €99, ₹50000, 500 USD, etc.
MONETARY_REGEX = re.compile(
    r"(?:(?:\$|£|€|¥|₹)\s?\d{1,3}(?:,\d{3})*(?:\.\d{2})?)"
    r"|(?:\d{1,3}(?:,\d{3})*(?:\.\d{2})?\s*(?:USD|EUR|GBP|INR|JPY))",
    re.IGNORECASE,
)

# ── Sentiment Lexicon ────────────────────────────────────────────────

NEGATIVE_WORDS = {
    "angry", "annoyed", "bad", "broken", "cancel", "complaint", "damage",
    "defective", "delay", "disappointed", "error", "fail", "fault", "frustrated",
    "hate", "horrible", "impossible", "intolerable", "irritated", "issue",
    "mad", "neglect", "never", "nothing", "outage", "pathetic", "poor",
    "problem", "refund", "reject", "ridiculous", "rude", "slow", "terrible",
    "unacceptable", "unfair", "unhappy", "unhelpful", "useless", "worst",
    "wrong", "awful", "scam", "cheat", "lies", "deceived", "fraud",
    "garbage", "waste", "sucks", "trash", "disgusting", "horrendous",
    "abysmal", "atrocious", "appalling", "dreadful", "miserable", "painful",
    "infuriating", "outrageous", "unbearable", "excruciating", "disastrous",
    "catastrophic", "devastating", "ruined", "destroyed", "corrupted",
}

POSITIVE_WORDS = {
    "awesome", "brilliant", "excellent", "fantastic", "good", "great",
    "happy", "helpful", "love", "perfect", "pleased", "quick", "satisfied",
    "superb", "thank", "thanks", "wonderful", "amazing", "impressed",
    "outstanding", "phenomenal", "remarkable", "stellar", "magnificent",
    "splendid", "terrific", "marvelous", "exceptional", "delightful",
    "grateful", "appreciate", "efficient", "reliable", "professional",
    "friendly", "polite", "responsive", "smooth", "seamless", "easy",
}

# ── Topic Clusters for Breadth Detection ─────────────────────────────

TOPIC_CLUSTERS = {
    "billing": {"refund", "bill", "invoice", "charge", "payment", "subscription",
                "price", "cost", "fee", "money", "credit", "debit", "overcharge",
                "discount", "coupon", "plan", "upgrade", "cancel", "renewal"},
    "technical": {"error", "bug", "crash", "not working", "broken", "glitch",
                  "slow", "timeout", "offline", "down", "loading", "connection",
                  "install", "update", "configure", "sync", "login", "password",
                  "api", "integration", "database", "server", "code", "deploy"},
    "shipping": {"ship", "deliver", "track", "package", "order", "courier",
                 "address", "delivery", "dispatch", "transit", "logistics",
                 "parcel", "box", "warehouse", "express", "overnight"},
    "account": {"account", "profile", "settings", "email", "username",
                "password", "verify", "mfa", "login", "signup", "register",
                " deactivate", "delete account", "privacy", "security"},
    "product": {"feature", "suggestion", "improve", "wish", "request",
                "enhancement", " roadmap", "missing", "add", "functionality",
                "capability", "option", "setting", "customization"},
    "support": {"help", "support", "agent", "representative", "manager",
                "escalate", "priority", "urgent", "ticket", "chat", "call",
                "contact", "reach", "response", "follow up", "status"},
    "content": {"documentation", "guide", "tutorial", "article", "faq",
                "knowledge", "base", "instructions", "how to", "explain",
                "understand", "learn", "training", "video", "resource"},
}

# ── Intent Keywords ──────────────────────────────────────────────────

INTENT_KEYWORDS = {
    "refund": ["refund", "money back", "return", "reimburse", "credit back",
               "chargeback", "cancel order", "get my money"],
    "technical": ["error", "bug", "not working", "broken", "crash", "issue",
                  "doesn't work", "failed", "glitch", "not loading", "slow",
                  "connection", "timeout", "offline", "down"],
    "billing": ["bill", "invoice", "charge", "payment", "subscription",
                "price", "cost", "fee", "overcharge", "duplicate charge",
                "unauthorized charge", "renewal"],
    "complaint": ["complaint", "unhappy", "disappointed", "frustrated", "angry",
                  "terrible", "awful", "worst", "horrible", "unacceptable",
                  "speak to manager", "escalate", "formal complaint"],
    "feature_request": ["feature", "suggestion", "would be great", "wish",
                        "please add", "would like", "enhancement", "improve",
                        "new functionality", "missing feature"],
    "general": [],
    "cancellation": ["cancel subscription", "unsubscribe", "stop service", "terminate",
                     "close account", "end subscription", "deactivate", "cancel my",
                     "cancel immediately", "cancel right now"],
    "shipping": ["ship", "deliver", "track", "package", "delivery", "order status",
                 "courier", "transit", "parcel", "address"],
    "inquiry": ["question", "how do i", "what is", "can you explain", "information",
                "help me understand", "guide", "wondering", "curious"],
    "escalation": ["escalate", "manager", "supervisor", "senior", "higher up",
                   "speak to someone", "not resolved", "still waiting"],
    "account": ["account", "profile", "login", "password", "reset password",
                "reset my password", "verify", "mfa", "email change",
                "username", "settings", "deactivate"],
    "feedback": ["feedback", "suggestion", "opinion", "thought", "experience",
                 "rating", "review", "improve", "better", "amazing", "great job",
                 "keep it up", "love your"],
}

# ── Data Classes ──────────────────────────────────────────────────────


@dataclass
class SignalExtractionRequest:
    """Input for signal extraction."""

    query: str
    company_id: str
    variant_type: str = "parwa"  # mini_parwa, parwa, parwa_high
    customer_tier: str = "free"
    turn_count: int = 0
    previous_response_status: str = "none"
    conversation_history: Optional[List[str]] = None
    customer_metadata: Optional[Dict[str, Any]] = None


@dataclass
class ExtractedSignals:
    """Output of signal extraction — 10 signals."""

    intent: str
    sentiment: float  # 0.0-1.0
    complexity: float  # 0.0-1.0
    monetary_value: float  # USD equivalent
    monetary_currency: Optional[str]
    customer_tier: str
    turn_count: int
    previous_response_status: str
    reasoning_loop_detected: bool
    resolution_path_count: int
    query_breadth: float  # 0.0-1.0
    extraction_version: str = "1.0"
    cached: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "intent": self.intent,
            "sentiment": round(self.sentiment, 4),
            "complexity": round(self.complexity, 4),
            "monetary_value": round(self.monetary_value, 2),
            "monetary_currency": self.monetary_currency,
            "customer_tier": self.customer_tier,
            "turn_count": self.turn_count,
            "previous_response_status": self.previous_response_status,
            "reasoning_loop_detected": self.reasoning_loop_detected,
            "resolution_path_count": self.resolution_path_count,
            "query_breadth": round(self.query_breadth, 4),
            "extraction_version": self.extraction_version,
            "cached": self.cached,
        }


# ── Signal Extractor ─────────────────────────────────────────────────


class SignalExtractor:
    """Extracts 10 real-time signals from ticket queries (SG-13).

    GAP-007: Cache key includes variant_type for cross-variant isolation.
    GAP-017: Multi-currency monetary value extraction.
    """

    # Per-variant configurable weights
    VARIANT_WEIGHTS: Dict[str, Dict[str, float]] = {
        "mini_parwa": {"complexity": 0.3, "intent": 0.5, "sentiment": 0.2},
        "parwa": {"complexity": 0.4, "intent": 0.3, "sentiment": 0.3},
        "parwa_high": {"complexity": 0.3, "intent": 0.3, "sentiment": 0.2, "monetary": 0.2},
    }

    CACHE_TTL_SECONDS = 60

    def __init__(self):
        pass

    async def extract(self, request: SignalExtractionRequest) -> ExtractedSignals:
        """Extract all 10 signals from a query.

        GAP-007 FIX: Cache key format is
        ``signal_cache:{company_id}:{variant_type}:{query_hash}`` so different
        variants never share cached signal results.
        """
        # Compute query hash for caching
        query_hash = self._compute_query_hash(request.query)
        cache_key = f"signal_cache:{request.company_id}:{request.variant_type}:{query_hash}"

        # Check cache (fail-open — never crash on Redis errors)
        try:
            from app.core.redis import cache_get, cache_set
            cached = await cache_get(request.company_id, cache_key)
            if cached is not None and isinstance(cached, dict):
                logger.debug("signal_cache_hit", key=cache_key)
                result = ExtractedSignals(
                    intent=cached["intent"],
                    sentiment=cached["sentiment"],
                    complexity=cached["complexity"],
                    monetary_value=cached["monetary_value"],
                    monetary_currency=cached.get("monetary_currency"),
                    customer_tier=cached["customer_tier"],
                    turn_count=cached["turn_count"],
                    previous_response_status=cached["previous_response_status"],
                    reasoning_loop_detected=cached["reasoning_loop_detected"],
                    resolution_path_count=cached["resolution_path_count"],
                    query_breadth=cached["query_breadth"],
                    cached=True,
                )
                return result
        except Exception as exc:
            logger.warning("signal_cache_read_error", error=str(exc))

        # Extract all signals
        start_time = time.monotonic()

        intent = self._extract_intent(request.query)
        sentiment = self._extract_sentiment(request.query)
        weights = self.VARIANT_WEIGHTS.get(request.variant_type, self.VARIANT_WEIGHTS["parwa"])
        complexity = self._extract_complexity(request.query, weights)
        monetary_value, monetary_currency = self._extract_monetary_value(request.query)
        customer_tier = self._resolve_customer_tier(request)
        reasoning_loop = self._detect_reasoning_loop(
            request.query, request.conversation_history or [],
        )
        resolution_paths = self._count_resolution_paths(request.query, intent)
        query_breadth = self._calculate_query_breadth(request.query)

        result = ExtractedSignals(
            intent=intent,
            sentiment=sentiment,
            complexity=complexity,
            monetary_value=monetary_value,
            monetary_currency=monetary_currency,
            customer_tier=customer_tier,
            turn_count=request.turn_count,
            previous_response_status=request.previous_response_status,
            reasoning_loop_detected=reasoning_loop,
            resolution_path_count=resolution_paths,
            query_breadth=query_breadth,
        )

        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
        logger.info(
            "signal_extraction_complete",
            company_id=request.company_id,
            variant_type=request.variant_type,
            intent=intent,
            sentiment=round(sentiment, 2),
            complexity=round(complexity, 2),
            monetary_value=monetary_value,
            elapsed_ms=elapsed_ms,
        )

        # Store in cache (GAP-007: key already includes variant_type)
        try:
            from app.core.redis import cache_set
            await cache_set(
                request.company_id, cache_key,
                result.to_dict(), ttl_seconds=self.CACHE_TTL_SECONDS,
            )
        except Exception as exc:
            logger.warning("signal_cache_write_error", error=str(exc))

        return result

    # ── Signal 1: Intent ─────────────────────────────────────────────

    def _extract_intent(self, query: str) -> str:
        """Classify intent from query using keyword matching."""
        query_lower = query.lower()
        best_intent = "general"
        best_score = 0

        for intent, keywords in INTENT_KEYWORDS.items():
            if intent == "general":
                continue
            # Score by keyword length (longer = more specific = better match)
            score = sum(len(kw.split()) for kw in keywords if kw in query_lower)
            if score > best_score:
                best_score = score
                best_intent = intent

        return best_intent

    # ── Signal 2: Sentiment ──────────────────────────────────────────

    def _extract_sentiment(self, query: str) -> float:
        """Calculate sentiment score using lexicon-based approach.

        Returns 0.0 (very negative) to 1.0 (very positive).
        """
        query_lower = query.lower()
        words = re.findall(r"\b\w+\b", query_lower)

        if not words:
            return 0.5  # neutral for empty

        neg_count = sum(1 for w in words if w in NEGATIVE_WORDS)
        pos_count = sum(1 for w in words if w in POSITIVE_WORDS)

        # Intensifiers boost effect
        intensifiers = {"very", "extremely", "really", "so", "incredibly",
                        "absolutely", "totally", "completely", "utterly"}
        intensifier_count = sum(1 for w in words if w in intensifiers)

        neg_score = neg_count * (1.0 + 0.3 * intensifier_count)
        pos_score = pos_count * (1.0 + 0.2 * intensifier_count)

        total = neg_score + pos_score
        if total == 0:
            return 0.5  # neutral

        # Score: 0.0 (all negative) to 1.0 (all positive)
        score = pos_score / total
        return max(0.0, min(1.0, score))

    # ── Signal 3: Complexity ─────────────────────────────────────────

    def _extract_complexity(self, query: str, weights: Dict[str, float]) -> float:
        """Multi-factor complexity scoring (0.0-1.0).

        Factors:
        - Query length (longer = more complex)
        - Question count (more questions = more complex)
        - Technical term density
        - Multi-topic detection
        """
        words = re.findall(r"\b\w+\b", query)
        word_count = len(words)

        # Length factor: 0 at <10 words, 1.0 at >100 words
        length_factor = min(1.0, word_count / 100.0)

        # Question factor: each ? adds complexity
        question_marks = query.count("?")
        question_words = sum(1 for w in words if w in {"how", "why", "what", "when", "where", "which"})
        question_factor = min(1.0, (question_marks + question_words * 0.5) / 5.0)

        # Technical density
        technical_words = sum(
            1 for w in words
            if w in {"api", "database", "server", "integration", "configuration",
                     "deployment", "endpoint", "webhook", "authentication",
                     "ssl", "tls", "dns", "http", "https", "json", "xml",
                     "docker", "kubernetes", "lambda", "function", "script"}
        )
        tech_factor = min(1.0, technical_words / 5.0) if words else 0.0

        # Multi-topic factor (uses query_breadth internally)
        breadth = self._calculate_query_breadth(query)
        topic_factor = breadth * 0.5  # scale down

        # Weighted combination
        complexity = (
            length_factor * weights.get("complexity", 0.4)
            + question_factor * 0.25
            + tech_factor * 0.15
            + topic_factor * 0.20
        )

        return round(max(0.0, min(1.0, complexity)), 4)

    # ── Signal 4: Monetary Value (W9-GAP-017) ────────────────────────

    def _extract_monetary_value(self, query: str) -> Tuple[float, Optional[str]]:
        """Extract monetary value with multi-currency support.

        W9-GAP-017 FIX: Supports $ £ € ¥ ₹ and USD/EUR/GBP/INR/JPY codes.
        Converts all to USD equivalent.
        """
        matches = MONETARY_REGEX.findall(query)
        if not matches:
            return 0.0, None

        total_usd = 0.0
        detected_currency = None

        for match in matches:
            match_stripped = match.strip()
            # Determine currency from match
            currency = None
            for symbol, rate in CURRENCY_TO_USD.items():
                if symbol in match_stripped and symbol.isalpha() and len(symbol) == 3:
                    currency = symbol
                    break
                if symbol in match_stripped and not symbol.isalpha():
                    currency = symbol
                    break

            if currency is None:
                # Try to detect from match pattern
                if match_stripped.upper().endswith("USD"):
                    currency = "USD"
                elif match_stripped.upper().endswith("EUR"):
                    currency = "EUR"
                elif match_stripped.upper().endswith("GBP"):
                    currency = "GBP"
                elif match_stripped.upper().endswith("INR"):
                    currency = "INR"
                elif match_stripped.upper().endswith("JPY"):
                    currency = "JPY"
                else:
                    currency = "$"

            # Extract numeric value
            num_str = re.sub(r"[^0-9.]", "", match_stripped)
            try:
                value = float(num_str)
                rate = CURRENCY_TO_USD.get(currency, 1.0)
                total_usd += value * rate
                detected_currency = currency
            except (ValueError, TypeError):
                continue

        return round(total_usd, 2), detected_currency

    # ── Signal 5: Customer Tier ──────────────────────────────────────

    def _resolve_customer_tier(self, request: SignalExtractionRequest) -> str:
        """Resolve customer tier from metadata or request default."""
        if request.customer_metadata and "tier" in request.customer_metadata:
            tier = request.customer_metadata["tier"].lower()
            if tier in ("free", "pro", "enterprise", "vip"):
                return tier
        return request.customer_tier

    # ── Signal 8: Reasoning Loop Detection ───────────────────────────

    def _detect_reasoning_loop(
        self, query: str, history: List[str],
    ) -> bool:
        """Detect repeated similar queries indicating a reasoning loop.

        Uses SequenceMatcher with 0.85 threshold to detect paraphrased
        repetitions.
        """
        if not history:
            return False

        query_normalized = query.lower().strip()
        # Check last 5 messages for similarity
        recent = history[-5:]

        similar_count = 0
        for past_msg in recent:
            if not past_msg or not past_msg.strip():
                continue
            past_normalized = past_msg.lower().strip()
            ratio = SequenceMatcher(None, query_normalized, past_normalized).ratio()
            if ratio >= 0.85:
                similar_count += 1

        # If 2+ recent messages are similar, it's a loop
        return similar_count >= 2

    # ── Signal 9: Resolution Path Count ──────────────────────────────

    def _count_resolution_paths(self, query: str, intent: str) -> int:
        """Estimate resolution paths based on intent and query content.

        More complex queries have more possible resolution approaches.
        """
        base_paths = {
            "general": 1, "inquiry": 1, "feedback": 1,
            "account": 2, "shipping": 2,
            "technical": 3, "billing": 3, "feature_request": 2,
            "refund": 3, "cancellation": 3,
            "complaint": 4, "escalation": 4,
        }

        paths = base_paths.get(intent, 2)

        # Boost for multi-currency / high monetary value
        if self._extract_monetary_value(query)[0] > 100:
            paths += 1

        # Boost for multi-topic queries
        breadth = self._calculate_query_breadth(query)
        if breadth > 0.5:
            paths += 1

        return min(paths, 5)  # cap at 5

    # ── Signal 10: Query Breadth ─────────────────────────────────────

    def _calculate_query_breadth(self, query: str) -> float:
        """Detect how many distinct topics are covered (0.0-1.0).

        1.0 = single focused topic, lower = multiple topics.
        Returns the inverse: 1.0 = many topics, 0.5 = single topic.
        """
        query_lower = query.lower()
        words = set(re.findall(r"\b\w+\b", query_lower))

        if not words:
            return 0.0

        active_topics = 0
        for topic_name, topic_words in TOPIC_CLUSTERS.items():
            overlap = len(words & topic_words)
            if overlap >= 2:
                active_topics += 1

        if active_topics <= 1:
            return 0.5  # single topic (focused)
        elif active_topics == 2:
            return 0.7
        elif active_topics == 3:
            return 0.85
        else:
            return 1.0  # very broad

    # ── Utility Methods ──────────────────────────────────────────────

    @staticmethod
    def _compute_query_hash(query: str) -> str:
        """Compute deterministic SHA-256 hash for cache key."""
        normalized = query.lower().strip()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]

    def to_query_signals(self, extracted: ExtractedSignals) -> Any:
        """Convert ExtractedSignals → technique_router.QuerySignals.

        This bridges Signal Extraction → Technique Router.
        """
        from app.core.technique_router import QuerySignals

        return QuerySignals(
            query_complexity=extracted.complexity,
            sentiment_score=extracted.sentiment,
            customer_tier=extracted.customer_tier,
            monetary_value=extracted.monetary_value,
            turn_count=extracted.turn_count,
            intent_type=extracted.intent,
            previous_response_status=extracted.previous_response_status,
            reasoning_loop_detected=extracted.reasoning_loop_detected,
            resolution_path_count=extracted.resolution_path_count,
            external_data_required=extracted.intent in ("technical", "shipping", "account"),
        )

    def get_variant_weights(self, variant_type: str) -> Dict[str, float]:
        """Get configurable weights for a variant type."""
        return dict(self.VARIANT_WEIGHTS.get(variant_type, self.VARIANT_WEIGHTS["parwa"]))
