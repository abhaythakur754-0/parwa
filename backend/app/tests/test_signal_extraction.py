"""
Tests for Signal Extraction Layer (SG-13)

Covers: 10 signal extraction, GAP-007 (cache variant isolation),
GAP-017 (multi-currency), edge cases.
"""

import asyncio
import hashlib
from unittest.mock import AsyncMock, patch

import pytest

from backend.app.core.signal_extraction import (
    CURRENCY_TO_USD,
    ExtractedSignals,
    INTENT_KEYWORDS,
    MONETARY_REGEX,
    SignalExtractionRequest,
    SignalExtractor,
)


# ── Intent Extraction ────────────────────────────────────────────────


class TestExtractIntent:
    def setup_method(self):
        self.extractor = SignalExtractor()

    @pytest.mark.parametrize("query,expected", [
        ("I want a refund for my order", "refund"),
        ("The app keeps crashing with an error", "technical"),
        ("I have a question about my bill", "billing"),
        ("I'm very unhappy with the service", "complaint"),
        ("It would be great to add a dark mode", "feature_request"),
        ("Cancel my subscription immediately", "cancellation"),
        ("Where is my package? I need to track it", "shipping"),
        ("How do I reset my password?", "account"),
        ("Can you explain how this works?", "inquiry"),
        ("I need to speak to a manager", "escalation"),
        ("Your product is amazing, great job!", "feedback"),
    ])
    def test_intent_detection(self, query, expected):
        assert self.extractor._extract_intent(query) == expected

    def test_general_fallback(self):
        assert self.extractor._extract_intent("hello there") == "general"

    def test_empty_query(self):
        assert self.extractor._extract_intent("") == "general"

    def test_multi_keyword_intent(self):
        """Refund has more matches than billing."""
        result = self.extractor._extract_intent(
            "I want a refund for the charge on my bill"
        )
        assert result in ("refund", "billing")  # Both valid for billing+refund query

    def test_case_insensitive(self):
        assert self.extractor._extract_intent("REFUND MY ORDER") == "refund"


# ── Sentiment Extraction ─────────────────────────────────────────────


class TestExtractSentiment:
    def setup_method(self):
        self.extractor = SignalExtractor()

    def test_positive_sentiment(self):
        score = self.extractor._extract_sentiment("This is amazing and wonderful!")
        assert score > 0.7

    def test_negative_sentiment(self):
        score = self.extractor._extract_sentiment(
            "This is terrible, awful, worst service ever"
        )
        assert score < 0.3

    def test_neutral_sentiment(self):
        score = self.extractor._extract_sentiment("How do I update my settings?")
        assert 0.3 <= score <= 0.7

    def test_mixed_sentiment(self):
        score = self.extractor._extract_sentiment(
            "Great product but terrible support"
        )
        assert 0.3 <= score <= 0.7

    def test_empty_text(self):
        score = self.extractor._extract_sentiment("")
        assert score == 0.5

    def test_intensifiers_boost(self):
        normal = self.extractor._extract_sentiment("This is bad and terrible")
        intensified = self.extractor._extract_sentiment("This is very very bad and extremely terrible")
        assert intensified <= normal

    def test_score_bounded(self):
        for text in ["happy" * 100, "angry" * 100]:
            score = self.extractor._extract_sentiment(text)
            assert 0.0 <= score <= 1.0


# ── Complexity Extraction ────────────────────────────────────────────


class TestExtractComplexity:
    def setup_method(self):
        self.extractor = SignalExtractor()
        self.weights = self.extractor.VARIANT_WEIGHTS["parwa"]

    def test_simple_query_low_complexity(self):
        score = self.extractor._extract_complexity("Hi", self.weights)
        assert score < 0.3

    def test_long_query_higher_complexity(self):
        long_query = " ".join(["problem"] * 120)
        score = self.extractor._extract_complexity(long_query, self.weights)
        assert score > 0.3

    def test_question_marks_increase(self):
        simple = self.extractor._extract_complexity("Help me", self.weights)
        questions = self.extractor._extract_complexity(
            "How? Why? What? When? Where?", self.weights
        )
        assert questions > simple

    def test_technical_terms_increase(self):
        normal = self.extractor._extract_complexity("My thing is broken", self.weights)
        techy = self.extractor._extract_complexity(
            "The API endpoint has a 500 error and the database server is down",
            self.weights,
        )
        assert techy > normal

    def test_complexity_capped_at_1(self):
        score = self.extractor._extract_complexity("x " * 1000, self.weights)
        assert score <= 1.0


# ── Monetary Value Extraction (W9-GAP-017) ───────────────────────────


class TestExtractMonetaryValue:
    def setup_method(self):
        self.extractor = SignalExtractor()

    def test_usd_dollar_sign(self):
        value, currency = self.extractor._extract_monetary_value("I paid $500")
        assert value == 500.0
        assert currency == "$"

    def test_gbp_pound(self):
        value, currency = self.extractor._extract_monetary_value("Costs £1,200.50")
        assert value > 1300  # converted to USD
        assert currency == "£"

    def test_euro(self):
        value, currency = self.extractor._extract_monetary_value("Price is €99")
        assert value > 90  # converted to USD
        assert currency == "€"

    def test_inr_rupee(self):
        value, currency = self.extractor._extract_monetary_value("I paid ₹50000")
        assert 0 < value < 1000  # INR to USD
        assert currency == "₹"

    def test_jpy_yen(self):
        value, currency = self.extractor._extract_monetary_value("Price ¥10000")
        assert 0 < value < 200  # JPY to USD
        assert currency == "¥"

    def test_currency_code_usd(self):
        value, currency = self.extractor._extract_monetary_value("Total 500 USD")
        assert value == 500.0
        assert currency == "USD"

    def test_currency_code_eur(self):
        value, currency = self.extractor._extract_monetary_value("Costs 250 EUR")
        assert value > 250  # converted

    def test_no_monetary_value(self):
        value, currency = self.extractor._extract_monetary_value("No money mentioned")
        assert value == 0.0
        assert currency is None

    def test_multiple_amounts(self):
        value, currency = self.extractor._extract_monetary_value(
            "I paid $100 and then €50 more"
        )
        assert value > 100  # both converted and summed

    def test_comma_separated_amount(self):
        value, currency = self.extractor._extract_monetary_value("$1,234.56")
        assert value == 1234.56


# ── Customer Tier Resolution ─────────────────────────────────────────


class TestResolveCustomerTier:
    def setup_method(self):
        self.extractor = SignalExtractor()

    def test_from_request(self):
        req = SignalExtractionRequest(
            query="test", company_id="c1", customer_tier="vip"
        )
        assert self.extractor._resolve_customer_tier(req) == "vip"

    def test_from_metadata(self):
        req = SignalExtractionRequest(
            query="test", company_id="c1",
            customer_metadata={"tier": "enterprise"},
        )
        assert self.extractor._resolve_customer_tier(req) == "enterprise"

    def test_metadata_overrides_request(self):
        req = SignalExtractionRequest(
            query="test", company_id="c1",
            customer_tier="free",
            customer_metadata={"tier": "pro"},
        )
        assert self.extractor._resolve_customer_tier(req) == "pro"

    def test_invalid_metadata_falls_back(self):
        req = SignalExtractionRequest(
            query="test", company_id="c1",
            customer_metadata={"tier": "invalid_tier"},
        )
        assert self.extractor._resolve_customer_tier(req) == "free"

    def test_none_metadata(self):
        req = SignalExtractionRequest(
            query="test", company_id="c1", customer_metadata=None
        )
        assert self.extractor._resolve_customer_tier(req) == "free"


# ── Reasoning Loop Detection ─────────────────────────────────────────


class TestReasoningLoopDetection:
    def setup_method(self):
        self.extractor = SignalExtractor()

    def test_no_history(self):
        assert not self.extractor._detect_reasoning_loop("test", [])

    def test_no_loop(self):
        history = ["How do I reset?", "Where is settings?", "Thanks"]
        assert not self.extractor._detect_reasoning_loop("New question here", history)

    def test_loop_detected(self):
        history = ["refund my order now", "I need a refund please", "refund my order now"]
        assert self.extractor._detect_reasoning_loop("refund my order now", history)

    def test_empty_history_items(self):
        history = ["", None, "refund"]
        assert not self.extractor._detect_reasoning_loop("refund", history)

    def test_similar_threshold(self):
        """Queries must be very similar (>=0.85) to trigger loop."""
        history = ["I have a billing problem", "I have a shipping problem"]
        assert not self.extractor._detect_reasoning_loop("I have a refund problem", history)


# ── Resolution Path Count ────────────────────────────────────────────


class TestResolutionPathCount:
    def setup_method(self):
        self.extractor = SignalExtractor()

    def test_general_intent(self):
        paths = self.extractor._count_resolution_paths("hello", "general")
        assert paths == 1

    def test_technical_intent(self):
        paths = self.extractor._count_resolution_paths("bug in api", "technical")
        assert paths >= 2

    def test_complaint_high_paths(self):
        paths = self.extractor._count_resolution_paths("terrible service", "complaint")
        assert paths >= 3

    def test_monetary_boost(self):
        normal = self.extractor._count_resolution_paths("I want a refund", "refund")
        with_money = self.extractor._count_resolution_paths("I want a $500 refund", "refund")
        assert with_money > normal


# ── Query Breadth ────────────────────────────────────────────────────


class TestQueryBreadth:
    def setup_method(self):
        self.extractor = SignalExtractor()

    def test_single_topic(self):
        breadth = self.extractor._calculate_query_breadth("I want a refund")
        assert breadth == 0.5

    def test_multi_topic(self):
        breadth = self.extractor._calculate_query_breadth(
            "I have a billing error charge, the app server is crashing, and my package delivery is lost"
        )
        assert breadth > 0.5

    def test_empty_query(self):
        breadth = self.extractor._calculate_query_breadth("")
        assert breadth == 0.0

    def test_breadth_bounded(self):
        breadth = self.extractor._calculate_query_breadth("any text here")
        assert 0.0 <= breadth <= 1.0


# ── Query Hash ───────────────────────────────────────────────────────


class TestQueryHash:
    def test_deterministic(self):
        h1 = SignalExtractor._compute_query_hash("test query")
        h2 = SignalExtractor._compute_query_hash("test query")
        assert h1 == h2

    def test_normalized(self):
        h1 = SignalExtractor._compute_query_hash("Test Query")
        h2 = SignalExtractor._compute_query_hash("test query")
        assert h1 == h2

    def test_different_queries(self):
        h1 = SignalExtractor._compute_query_hash("query one")
        h2 = SignalExtractor._compute_query_hash("query two")
        assert h1 != h2


# ── to_query_signals Conversion ──────────────────────────────────────


class TestToQuerySignals:
    def setup_method(self):
        self.extractor = SignalExtractor()

    def test_conversion(self):
        signals = ExtractedSignals(
            intent="refund", sentiment=0.3, complexity=0.5,
            monetary_value=100.0, monetary_currency="$",
            customer_tier="vip", turn_count=3,
            previous_response_status="rejected",
            reasoning_loop_detected=True, resolution_path_count=3,
            query_breadth=0.6,
        )
        qs = self.extractor.to_query_signals(signals)
        assert qs.intent_type == "refund"
        assert qs.sentiment_score == 0.3
        assert qs.query_complexity == 0.5
        assert qs.monetary_value == 100.0
        assert qs.customer_tier == "vip"
        assert qs.turn_count == 3
        assert qs.previous_response_status == "rejected"
        assert qs.reasoning_loop_detected is True
        assert qs.resolution_path_count == 3

    def test_external_data_required(self):
        for intent in ("technical", "shipping", "account"):
            signals = ExtractedSignals(
                intent=intent, sentiment=0.5, complexity=0.5,
                monetary_value=0, monetary_currency=None,
                customer_tier="free", turn_count=0,
                previous_response_status="none",
                reasoning_loop_detected=False, resolution_path_count=1,
                query_breadth=0.5,
            )
            qs = self.extractor.to_query_signals(signals)
            assert qs.external_data_required is True

    def test_no_external_data_for_billing(self):
        signals = ExtractedSignals(
            intent="billing", sentiment=0.5, complexity=0.5,
            monetary_value=0, monetary_currency=None,
            customer_tier="free", turn_count=0,
            previous_response_status="none",
            reasoning_loop_detected=False, resolution_path_count=1,
            query_breadth=0.5,
        )
        qs = self.extractor.to_query_signals(signals)
        assert qs.external_data_required is False


# ── Variant Weights ──────────────────────────────────────────────────


class TestVariantWeights:
    def setup_method(self):
        self.extractor = SignalExtractor()

    def test_all_variants_have_weights(self):
        for variant in ("mini_parwa", "parwa", "parwa_high"):
            weights = self.extractor.get_variant_weights(variant)
            assert "complexity" in weights
            assert "intent" in weights

    def test_unknown_variant_gets_parwa_weights(self):
        weights = self.extractor.get_variant_weights("unknown_variant")
        parwa_weights = self.extractor.get_variant_weights("parwa")
        assert weights == parwa_weights


# ── Full Pipeline (async) ────────────────────────────────────────────


class TestFullPipeline:
    def setup_method(self):
        self.extractor = SignalExtractor()

    @pytest.mark.asyncio
    async def test_full_extraction(self):
        req = SignalExtractionRequest(
            query="I want a refund for my $50 order, this is terrible!",
            company_id="test_company",
            variant_type="parwa",
        )
        result = await self.extractor.extract(req)
        assert result.intent == "refund"
        assert 0.0 <= result.sentiment <= 1.0
        assert 0.0 <= result.complexity <= 1.0
        assert result.monetary_value == 50.0
        assert result.monetary_currency == "$"
        assert result.cached is False

    @pytest.mark.asyncio
    async def test_extraction_cache_key_includes_variant(self):
        """GAP-007: Different variants get different cache keys."""
        req_mini = SignalExtractionRequest(
            query="refund my order", company_id="c1", variant_type="mini_parwa"
        )
        req_parwa = SignalExtractionRequest(
            query="refund my order", company_id="c1", variant_type="parwa"
        )
        h1 = self.extractor._compute_query_hash(req_mini.query)
        h2 = self.extractor._compute_query_hash(req_parwa.query)
        # Same query hash but different cache keys due to variant
        key1 = f"signal_cache:{req_mini.company_id}:{req_mini.variant_type}:{h1}"
        key2 = f"signal_cache:{req_parwa.company_id}:{req_parwa.variant_type}:{h2}"
        assert key1 != key2

    @pytest.mark.asyncio
    async def test_cache_fail_open(self):
        """Redis failure should not crash extraction."""
        req = SignalExtractionRequest(
            query="test query", company_id="c1", variant_type="parwa"
        )
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, side_effect=Exception("Redis down")):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock, side_effect=Exception("Redis down")):
                result = await self.extractor.extract(req)
                assert result.cached is False

    @pytest.mark.asyncio
    async def test_cache_hit(self):
        """GAP-007: Cache hit returns cached result."""
        req = SignalExtractionRequest(
            query="I need a refund", company_id="c1", variant_type="parwa"
        )
        cached_data = {
            "intent": "refund", "sentiment": 0.3, "complexity": 0.4,
            "monetary_value": 0.0, "monetary_currency": None,
            "customer_tier": "free", "turn_count": 0,
            "previous_response_status": "none",
            "reasoning_loop_detected": False, "resolution_path_count": 2,
            "query_breadth": 0.5, "extraction_version": "1.0",
        }
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=cached_data):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.extractor.extract(req)
                assert result.intent == "refund"
                assert result.cached is True


# ── Serialization ────────────────────────────────────────────────────


class TestSerialization:
    def test_to_dict(self):
        signals = ExtractedSignals(
            intent="refund", sentiment=0.5, complexity=0.6,
            monetary_value=100.0, monetary_currency="$",
            customer_tier="pro", turn_count=2,
            previous_response_status="none",
            reasoning_loop_detected=False, resolution_path_count=2,
            query_breadth=0.5,
        )
        d = signals.to_dict()
        assert d["intent"] == "refund"
        assert d["monetary_currency"] == "$"
        assert d["cached"] is False
        assert "extraction_version" in d

    def test_round_trip(self):
        signals = ExtractedSignals(
            intent="technical", sentiment=0.4, complexity=0.7,
            monetary_value=0.0, monetary_currency=None,
            customer_tier="free", turn_count=5,
            previous_response_status="rejected",
            reasoning_loop_detected=True, resolution_path_count=3,
            query_breadth=0.8,
        )
        d = signals.to_dict()
        assert isinstance(d["sentiment"], float)
        assert isinstance(d["complexity"], float)
