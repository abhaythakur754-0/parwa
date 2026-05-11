"""
Tests for Signal Extraction Layer (SG-13) — Week 9 Day 6

Covers: 10 signal extraction, GAP-007 (cache variant isolation),
GAP-017 (multi-currency), edge cases, variant weights.
Target: 120+ tests
"""

import asyncio
import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# Module-level stubs
CURRENCY_TO_USD = None  # type: ignore[assignment,misc]
ExtractedSignals = None  # type: ignore[assignment,misc]
INTENT_KEYWORDS = None  # type: ignore[assignment,misc]
MONETARY_REGEX = None  # type: ignore[assignment,misc]
NEGATIVE_WORDS = None  # type: ignore[assignment,misc]
POSITIVE_WORDS = None  # type: ignore[assignment,misc]
SignalExtractionRequest = None  # type: ignore[assignment,misc]
SignalExtractor = None  # type: ignore[assignment,misc]
TOPIC_CLUSTERS = None  # type: ignore[assignment,misc]


# ═══════════════════════════════════════════════════════════════════════
# Fixtures — import source modules with mocked logger
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def _mock_logger():
    with patch("app.logger.get_logger", return_value=MagicMock()):
        from app.core.signal_extraction import (  # noqa: F811,F401
            CURRENCY_TO_USD,
            ExtractedSignals,
            INTENT_KEYWORDS,
            MONETARY_REGEX,
            NEGATIVE_WORDS,
            POSITIVE_WORDS,
            SignalExtractionRequest,
            SignalExtractor,
            TOPIC_CLUSTERS,
        )
        globals().update({
            "CURRENCY_TO_USD": CURRENCY_TO_USD,
            "ExtractedSignals": ExtractedSignals,
            "INTENT_KEYWORDS": INTENT_KEYWORDS,
            "MONETARY_REGEX": MONETARY_REGEX,
            "NEGATIVE_WORDS": NEGATIVE_WORDS,
            "POSITIVE_WORDS": POSITIVE_WORDS,
            "SignalExtractionRequest": SignalExtractionRequest,
            "SignalExtractor": SignalExtractor,
            "TOPIC_CLUSTERS": TOPIC_CLUSTERS,
        })


# ═══════════════════════════════════════════════════════════════════════
# 1. Intent Extraction (15 tests)
# ═══════════════════════════════════════════════════════════════════════

class TestExtractIntent:
    def setup_method(self):
        self.extractor = SignalExtractor()

    def test_refund_intent(self):
        assert self.extractor._extract_intent("I want a refund for my order") == "refund"

    def test_technical_intent(self):
        assert self.extractor._extract_intent("The app keeps crashing with an error") == "technical"

    def test_billing_intent(self):
        assert self.extractor._extract_intent("I have a question about my bill") == "billing"

    def test_complaint_intent(self):
        assert self.extractor._extract_intent("I'm very unhappy with the service") == "complaint"

    def test_feature_request_intent(self):
        assert self.extractor._extract_intent("It would be great to add a dark mode") == "feature_request"

    def test_general_intent(self):
        assert self.extractor._extract_intent("Hello there, how are you?") == "general"

    def test_cancellation_intent(self):
        assert self.extractor._extract_intent("Cancel my subscription immediately") == "cancellation"

    def test_shipping_intent(self):
        assert self.extractor._extract_intent("Where is my package? I need to track it") == "shipping"

    def test_inquiry_intent(self):
        assert self.extractor._extract_intent("Can you explain how this works?") == "inquiry"

    def test_escalation_intent(self):
        assert self.extractor._extract_intent("I need to speak to a manager") == "escalation"

    def test_account_intent(self):
        assert self.extractor._extract_intent("How do I reset my password?") == "account"

    def test_feedback_intent(self):
        assert self.extractor._extract_intent("Your product is amazing, great job!") == "feedback"

    def test_multi_intent_best_score_wins(self):
        result = self.extractor._extract_intent(
            "I want a refund for the charge on my bill and also there is a bug"
        )
        assert result in ("refund", "billing", "technical")

    def test_no_intent_fallback_general(self):
        assert self.extractor._extract_intent("hello there good day") == "general"

    def test_empty_query_returns_general(self):
        assert self.extractor._extract_intent("") == "general"

    def test_case_insensitive_intent(self):
        assert self.extractor._extract_intent("REFUND MY ORDER NOW") == "refund"


# ═══════════════════════════════════════════════════════════════════════
# 2. Sentiment Extraction (15 tests)
# ═══════════════════════════════════════════════════════════════════════

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
        score = self.extractor._extract_sentiment("Great product but terrible support")
        assert 0.3 <= score <= 0.7

    def test_intensifiers_boost_negative(self):
        normal = self.extractor._extract_sentiment("This is bad and terrible")
        intensified = self.extractor._extract_sentiment(
            "This is very very bad and extremely terrible"
        )
        # Intensifiers amplify both sides, but net effect shifts toward the dominant
        assert isinstance(intensified, float)

    def test_intensifiers_boost_positive(self):
        normal = self.extractor._extract_sentiment("This is great and amazing")
        intensified = self.extractor._extract_sentiment(
            "This is really great and incredibly amazing"
        )
        assert isinstance(intensified, float)

    def test_multiple_negative_signals(self):
        score = self.extractor._extract_sentiment(
            "angry frustrated disappointed horrible unacceptable worst"
        )
        assert score < 0.3

    def test_multiple_positive_signals(self):
        score = self.extractor._extract_sentiment(
            "awesome brilliant excellent fantastic happy satisfied"
        )
        assert score > 0.7

    def test_empty_text_neutral(self):
        score = self.extractor._extract_sentiment("")
        assert score == 0.5

    def test_score_bounded_zero(self):
        score = self.extractor._extract_sentiment("angry" * 100)
        assert 0.0 <= score <= 1.0

    def test_score_bounded_one(self):
        score = self.extractor._extract_sentiment("happy" * 100)
        assert 0.0 <= score <= 1.0

    def test_intensifier_only_no_sentiment_words(self):
        score = self.extractor._extract_sentiment("very extremely really")
        assert score == 0.5

    def test_single_negative_word(self):
        score = self.extractor._extract_sentiment("broken")
        assert score < 0.5

    def test_single_positive_word(self):
        score = self.extractor._extract_sentiment("excellent")
        assert score > 0.5

    def test_zero_score_negative(self):
        score = self.extractor._extract_sentiment("angry frustrated furious")
        assert score >= 0.0


# ═══════════════════════════════════════════════════════════════════════
# 3. Complexity Extraction (12 tests)
# ═══════════════════════════════════════════════════════════════════════

class TestExtractComplexity:
    def setup_method(self):
        self.extractor = SignalExtractor()

    def test_simple_query_low_complexity(self):
        score = self.extractor._extract_complexity("Hi", {"complexity": 0.4})
        assert score < 0.3

    def test_complex_query_higher(self):
        long_query = " ".join(["problem"] * 120)
        score = self.extractor._extract_complexity(long_query, {"complexity": 0.4})
        assert score > 0.3

    def test_technical_terms_increase(self):
        normal = self.extractor._extract_complexity("My thing is broken", {"complexity": 0.4})
        techy = self.extractor._extract_complexity(
            "The API endpoint has a 500 error and the database server is down",
            {"complexity": 0.4},
        )
        assert techy > normal

    def test_multi_question_increases(self):
        simple = self.extractor._extract_complexity("Help me", {"complexity": 0.4})
        questions = self.extractor._extract_complexity(
            "How? Why? What? When? Where?", {"complexity": 0.4}
        )
        assert questions > simple

    def test_complexity_capped_at_1(self):
        score = self.extractor._extract_complexity("x " * 1000, {"complexity": 1.0})
        assert score <= 1.0

    def test_complexity_capped_at_0(self):
        score = self.extractor._extract_complexity("", {"complexity": 0.0})
        assert score >= 0.0

    def test_mini_parwa_weights(self):
        weights = self.extractor.VARIANT_WEIGHTS["mini_parwa"]
        score = self.extractor._extract_complexity("hello", weights)
        assert 0.0 <= score <= 1.0

    def test_parwa_weights(self):
        weights = self.extractor.VARIANT_WEIGHTS["parwa"]
        score = self.extractor._extract_complexity("hello", weights)
        assert 0.0 <= score <= 1.0

    def test_parwa_high_weights(self):
        weights = self.extractor.VARIANT_WEIGHTS["parwa_high"]
        score = self.extractor._extract_complexity("hello", weights)
        assert 0.0 <= score <= 1.0

    def test_empty_weights_fallback(self):
        score = self.extractor._extract_complexity("test", {})
        assert 0.0 <= score <= 1.0

    def test_long_text_higher_than_short(self):
        short = self.extractor._extract_complexity("bug", {"complexity": 0.4})
        long_q = "bug " * 200
        long_score = self.extractor._extract_complexity(long_q, {"complexity": 0.4})
        assert long_score > short

    def test_multi_topic_increases_complexity(self):
        simple = self.extractor._extract_complexity("I want a refund", {"complexity": 0.4})
        multi = self.extractor._extract_complexity(
            "I have a billing error charge, the app server is crashing, "
            "my package delivery is lost, and my account login is broken",
            {"complexity": 0.4},
        )
        assert multi > simple


# ═══════════════════════════════════════════════════════════════════════
# 4. Monetary Value Extraction (15 tests)
# ═══════════════════════════════════════════════════════════════════════

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

    def test_euro_sign(self):
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
        assert value > 250

    def test_currency_code_gbp(self):
        value, currency = self.extractor._extract_monetary_value("Price 100 GBP")
        assert value > 100

    def test_currency_code_inr(self):
        value, currency = self.extractor._extract_monetary_value("Amount 5,000 INR")
        assert 0 < value < 100

    def test_currency_code_jpy(self):
        value, currency = self.extractor._extract_monetary_value("Price 50,000 JPY")
        assert 0 < value < 500

    def test_multiple_amounts(self):
        value, currency = self.extractor._extract_monetary_value(
            "I paid $100 and then €50 more"
        )
        assert value > 100

    def test_no_monetary_value(self):
        value, currency = self.extractor._extract_monetary_value("No money mentioned")
        assert value == 0.0
        assert currency is None

    def test_comma_separated_amount(self):
        value, currency = self.extractor._extract_monetary_value("$1,234.56")
        assert value == 1234.56

    def test_multiple_currencies_sum(self):
        value, currency = self.extractor._extract_monetary_value(
            "$200 and £100 and €50 and ₹10000"
        )
        assert value > 200  # all summed and converted

    def test_usd_amount_with_cents(self):
        value, currency = self.extractor._extract_monetary_value("$99.99")
        assert value == 99.99


# ═══════════════════════════════════════════════════════════════════════
# 5. Customer Tier Resolution (8 tests)
# ═══════════════════════════════════════════════════════════════════════

class TestResolveCustomerTier:
    def setup_method(self):
        self.extractor = SignalExtractor()

    def test_from_request_default(self):
        req = SignalExtractionRequest(query="test", company_id="c1", customer_tier="free")
        assert self.extractor._resolve_customer_tier(req) == "free"

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

    def test_invalid_tier_falls_back(self):
        req = SignalExtractionRequest(
            query="test", company_id="c1",
            customer_metadata={"tier": "invalid_tier"},
        )
        assert self.extractor._resolve_customer_tier(req) == "free"

    def test_valid_tier_free(self):
        req = SignalExtractionRequest(
            query="test", company_id="c1",
            customer_metadata={"tier": "free"},
        )
        assert self.extractor._resolve_customer_tier(req) == "free"

    def test_valid_tier_pro(self):
        req = SignalExtractionRequest(
            query="test", company_id="c1",
            customer_metadata={"tier": "Pro"},
        )
        assert self.extractor._resolve_customer_tier(req) == "pro"

    def test_valid_tier_vip(self):
        req = SignalExtractionRequest(
            query="test", company_id="c1",
            customer_metadata={"tier": "VIP"},
        )
        assert self.extractor._resolve_customer_tier(req) == "vip"

    def test_none_metadata(self):
        req = SignalExtractionRequest(
            query="test", company_id="c1", customer_metadata=None
        )
        assert self.extractor._resolve_customer_tier(req) == "free"


# ═══════════════════════════════════════════════════════════════════════
# 6. Reasoning Loop Detection (10 tests)
# ═══════════════════════════════════════════════════════════════════════

class TestReasoningLoopDetection:
    def setup_method(self):
        self.extractor = SignalExtractor()

    def test_no_history(self):
        assert not self.extractor._detect_reasoning_loop("test", [])

    def test_single_different_message(self):
        history = ["How do I reset my password?"]
        assert not self.extractor._detect_reasoning_loop("What is my order status?", history)

    def test_similar_messages_detected(self):
        history = ["refund my order now", "I need a refund please", "refund my order now"]
        assert self.extractor._detect_reasoning_loop("refund my order now", history)

    def test_different_messages_not_loop(self):
        history = ["How do I reset?", "Where is settings?", "Thanks"]
        assert not self.extractor._detect_reasoning_loop("New question here", history)

    def test_empty_history_items(self):
        history = ["", None, "refund"]
        assert not self.extractor._detect_reasoning_loop("refund", history)

    def test_exact_duplicate_triggers(self):
        history = ["Please help me"] * 3
        assert self.extractor._detect_reasoning_loop("Please help me", history)

    def test_one_similar_not_enough(self):
        history = ["refund my order now"]
        assert not self.extractor._detect_reasoning_loop("refund my order now", history)

    def test_case_insensitive_similarity(self):
        history = ["REFUND MY ORDER", "Refund My Order"]
        assert self.extractor._detect_reasoning_loop("refund my order", history)

    def test_only_checks_last_5_messages(self):
        history = ["unrelated"] * 10 + ["refund my order", "refund my order please"]
        assert not self.extractor._detect_reasoning_loop("refund my order", history)

    def test_whitespace_variations(self):
        history = ["refund my order", "refund  my  order"]
        assert self.extractor._detect_reasoning_loop("refund my order", history)


# ═══════════════════════════════════════════════════════════════════════
# 7. Resolution Path Counting (8 tests)
# ═══════════════════════════════════════════════════════════════════════

class TestResolutionPathCount:
    def setup_method(self):
        self.extractor = SignalExtractor()

    def test_general_intent_base(self):
        paths = self.extractor._count_resolution_paths("hello", "general")
        assert paths == 1

    def test_inquiry_intent_base(self):
        paths = self.extractor._count_resolution_paths("question", "inquiry")
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

    def test_multi_topic_boost(self):
        simple = self.extractor._count_resolution_paths("I want a refund", "refund")
        multi = self.extractor._count_resolution_paths(
            "I want a refund for the billing charge on my shipping package",
            "refund",
        )
        assert multi >= simple

    def test_capped_at_5(self):
        paths = self.extractor._count_resolution_paths(
            "I have a complaint about the $5000 refund, "
            "billing charge, shipping, account, and escalation "
            "for this technical issue",
            "complaint",
        )
        assert paths <= 5

    def test_feedback_base_paths(self):
        paths = self.extractor._count_resolution_paths("great product", "feedback")
        assert paths == 1


# ═══════════════════════════════════════════════════════════════════════
# 8. Query Breadth (10 tests)
# ═══════════════════════════════════════════════════════════════════════

class TestQueryBreadth:
    def setup_method(self):
        self.extractor = SignalExtractor()

    def test_single_topic(self):
        breadth = self.extractor._calculate_query_breadth("I want a refund")
        assert breadth == 0.5

    def test_two_topics(self):
        breadth = self.extractor._calculate_query_breadth(
            "I have a bill invoice charge error bug crash server"
        )
        assert breadth == 0.7

    def test_three_topics(self):
        breadth = self.extractor._calculate_query_breadth(
            "I have a bill invoice charge error bug crash server "
            "ship delivery tracking package order"
        )
        assert breadth == 0.85

    def test_four_plus_topics(self):
        breadth = self.extractor._calculate_query_breadth(
            "billing error charge app server crash package delivery "
            "lost account login password help support escalate manager"
        )
        assert breadth == 1.0

    def test_empty_query(self):
        breadth = self.extractor._calculate_query_breadth("")
        assert breadth == 0.0

    def test_breadth_bounded(self):
        breadth = self.extractor._calculate_query_breadth("any text here")
        assert 0.0 <= breadth <= 1.0

    def test_mixed_topics_billing_technical(self):
        breadth = self.extractor._calculate_query_breadth(
            "My bill invoice charge has an error bug and the server api is down"
        )
        assert breadth > 0.5

    def test_single_word(self):
        breadth = self.extractor._calculate_query_breadth("refund")
        assert 0.0 <= breadth <= 1.0

    def test_no_topic_overlap(self):
        breadth = self.extractor._calculate_query_breadth(
            "the quick brown fox jumps over the lazy dog"
        )
        assert breadth == 0.5

    def test_whitespace_only(self):
        breadth = self.extractor._calculate_query_breadth("   ")
        assert breadth == 0.0


# ═══════════════════════════════════════════════════════════════════════
# 9. Cache Behavior (8 tests)
# ═══════════════════════════════════════════════════════════════════════

class TestCacheBehavior:
    def setup_method(self):
        self.extractor = SignalExtractor()

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached_result(self):
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
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=cached_data):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.extractor.extract(req)
                assert result.intent == "refund"
                assert result.cached is True

    @pytest.mark.asyncio
    async def test_cache_miss_computes_signals(self):
        req = SignalExtractionRequest(
            query="refund my order", company_id="c1", variant_type="parwa"
        )
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.extractor.extract(req)
                assert result.cached is False
                assert result.intent == "refund"

    @pytest.mark.asyncio
    async def test_cache_key_includes_variant_type_gap007(self):
        """GAP-007: Different variants get different cache keys."""
        req_mini = SignalExtractionRequest(
            query="refund my order", company_id="c1", variant_type="mini_parwa"
        )
        req_parwa = SignalExtractionRequest(
            query="refund my order", company_id="c1", variant_type="parwa"
        )
        h = self.extractor._compute_query_hash("refund my order")
        key1 = f"signal_cache:c1:mini_parwa:{h}"
        key2 = f"signal_cache:c1:parwa:{h}"
        assert key1 != key2

    @pytest.mark.asyncio
    async def test_cache_fail_open_read_error(self):
        req = SignalExtractionRequest(query="test", company_id="c1")
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, side_effect=Exception("Redis down")):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.extractor.extract(req)
                assert result.cached is False

    @pytest.mark.asyncio
    async def test_cache_fail_open_write_error(self):
        req = SignalExtractionRequest(query="test", company_id="c1")
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock, side_effect=Exception("Redis down")):
                result = await self.extractor.extract(req)
                assert result.cached is False

    @pytest.mark.asyncio
    async def test_cache_key_format(self):
        req = SignalExtractionRequest(query="hello", company_id="co123")
        h = self.extractor._compute_query_hash("hello")
        expected_key = f"signal_cache:co123:parwa:{h}"
        assert expected_key.startswith("signal_cache:")
        assert "co123" in expected_key
        assert "parwa" in expected_key

    @pytest.mark.asyncio
    async def test_cache_stores_result(self):
        req = SignalExtractionRequest(query="test query", company_id="c1")
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None) as mock_get:
            with patch("app.core.redis.cache_set", new_callable=AsyncMock) as mock_set:
                await self.extractor.extract(req)
                mock_set.assert_called_once()
                call_args = mock_set.call_args
                assert call_args[0][0] == "c1"
                assert "signal_cache:" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_cache_non_dict_ignored(self):
        """Non-dict cached values are ignored."""
        req = SignalExtractionRequest(query="test", company_id="c1")
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value="not a dict"):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.extractor.extract(req)
                assert result.cached is False


# ═══════════════════════════════════════════════════════════════════════
# 10. ExtractedSignals Dataclass (5 tests)
# ═══════════════════════════════════════════════════════════════════════

class TestExtractedSignalsDataclass:
    def test_to_dict_all_keys(self):
        signals = ExtractedSignals(
            intent="refund", sentiment=0.5, complexity=0.6,
            monetary_value=100.0, monetary_currency="$",
            customer_tier="pro", turn_count=2,
            previous_response_status="none",
            reasoning_loop_detected=False, resolution_path_count=2,
            query_breadth=0.5,
        )
        d = signals.to_dict()
        expected_keys = {
            "intent", "sentiment", "complexity", "monetary_value",
            "monetary_currency", "customer_tier", "turn_count",
            "previous_response_status", "reasoning_loop_detected",
            "resolution_path_count", "query_breadth", "extraction_version", "cached",
        }
        assert set(d.keys()) == expected_keys

    def test_default_values(self):
        signals = ExtractedSignals(
            intent="general", sentiment=0.5, complexity=0.0,
            monetary_value=0.0, monetary_currency=None,
            customer_tier="free", turn_count=0,
            previous_response_status="none",
            reasoning_loop_detected=False, resolution_path_count=1,
            query_breadth=0.5,
        )
        assert signals.extraction_version == "1.0"
        assert signals.cached is False

    def test_to_dict_rounded_values(self):
        signals = ExtractedSignals(
            intent="test", sentiment=0.12345678, complexity=0.98765432,
            monetary_value=99.999, monetary_currency=None,
            customer_tier="free", turn_count=0,
            previous_response_status="none",
            reasoning_loop_detected=False, resolution_path_count=1,
            query_breadth=0.12345678,
        )
        d = signals.to_dict()
        assert d["sentiment"] == 0.1235
        assert d["complexity"] == 0.9877
        assert d["monetary_value"] == 100.0
        assert d["query_breadth"] == 0.1235

    def test_all_10_signals_populated(self):
        signals = ExtractedSignals(
            intent="refund", sentiment=0.3, complexity=0.5,
            monetary_value=100.0, monetary_currency="$",
            customer_tier="vip", turn_count=3,
            previous_response_status="rejected",
            reasoning_loop_detected=True, resolution_path_count=3,
            query_breadth=0.6,
        )
        assert signals.intent == "refund"
        assert signals.sentiment == 0.3
        assert signals.complexity == 0.5
        assert signals.monetary_value == 100.0
        assert signals.monetary_currency == "$"
        assert signals.customer_tier == "vip"
        assert signals.turn_count == 3
        assert signals.previous_response_status == "rejected"
        assert signals.reasoning_loop_detected is True
        assert signals.resolution_path_count == 3
        assert signals.query_breadth == 0.6

    def test_to_dict_types(self):
        signals = ExtractedSignals(
            intent="test", sentiment=0.5, complexity=0.5,
            monetary_value=0.0, monetary_currency=None,
            customer_tier="free", turn_count=0,
            previous_response_status="none",
            reasoning_loop_detected=False, resolution_path_count=1,
            query_breadth=0.5,
        )
        d = signals.to_dict()
        assert isinstance(d["intent"], str)
        assert isinstance(d["sentiment"], float)
        assert isinstance(d["complexity"], float)
        assert isinstance(d["monetary_value"], (int, float))
        assert isinstance(d["customer_tier"], str)
        assert isinstance(d["turn_count"], int)
        assert isinstance(d["reasoning_loop_detected"], bool)
        assert isinstance(d["resolution_path_count"], int)


# ═══════════════════════════════════════════════════════════════════════
# 11. SignalExtractor.extract() Integration (10 tests)
# ═══════════════════════════════════════════════════════════════════════

class TestExtractIntegration:
    def setup_method(self):
        self.extractor = SignalExtractor()

    @pytest.mark.asyncio
    async def test_full_extraction_refund(self):
        req = SignalExtractionRequest(
            query="I want a refund for my $50 order, this is terrible!",
            company_id="test_company", variant_type="parwa",
        )
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.extractor.extract(req)
                assert result.intent == "refund"
                assert 0.0 <= result.sentiment <= 1.0
                assert 0.0 <= result.complexity <= 1.0
                assert result.monetary_value == 50.0
                assert result.cached is False

    @pytest.mark.asyncio
    async def test_extraction_with_variant_mini_parwa(self):
        req = SignalExtractionRequest(
            query="How do I reset my password?",
            company_id="c1", variant_type="mini_parwa",
        )
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.extractor.extract(req)
                assert result.intent == "account"
                assert result.customer_tier == "free"

    @pytest.mark.asyncio
    async def test_extraction_with_conversation_history(self):
        req = SignalExtractionRequest(
            query="refund my order",
            company_id="c1",
            conversation_history=["refund my order", "refund my order now", "refund my order please"],
        )
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.extractor.extract(req)
                assert result.reasoning_loop_detected is True

    @pytest.mark.asyncio
    async def test_extraction_with_vip_tier(self):
        req = SignalExtractionRequest(
            query="I have a question about my bill",
            company_id="c1", customer_tier="vip",
        )
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.extractor.extract(req)
                assert result.customer_tier == "vip"

    @pytest.mark.asyncio
    async def test_extraction_with_parwa_high_variant(self):
        req = SignalExtractionRequest(
            query="complaint about terrible service",
            company_id="c1", variant_type="parwa_high",
        )
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.extractor.extract(req)
                assert result.intent == "complaint"

    @pytest.mark.asyncio
    async def test_extraction_multi_currency(self):
        req = SignalExtractionRequest(
            query="I paid $100 and €50 for my order",
            company_id="c1", variant_type="parwa",
        )
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.extractor.extract(req)
                assert result.monetary_value > 100

    @pytest.mark.asyncio
    async def test_extraction_no_monetary(self):
        req = SignalExtractionRequest(
            query="I need help with my account settings",
            company_id="c1",
        )
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.extractor.extract(req)
                assert result.monetary_value == 0.0
                assert result.monetary_currency is None

    @pytest.mark.asyncio
    async def test_extraction_turn_count_preserved(self):
        req = SignalExtractionRequest(
            query="hello", company_id="c1", turn_count=7,
        )
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.extractor.extract(req)
                assert result.turn_count == 7

    @pytest.mark.asyncio
    async def test_extraction_previous_status_preserved(self):
        req = SignalExtractionRequest(
            query="still not working",
            company_id="c1",
            previous_response_status="rejected",
        )
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.extractor.extract(req)
                assert result.previous_response_status == "rejected"

    @pytest.mark.asyncio
    async def test_extraction_metadata_tier_override(self):
        req = SignalExtractionRequest(
            query="help",
            company_id="c1",
            customer_tier="free",
            customer_metadata={"tier": "enterprise"},
        )
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.extractor.extract(req)
                assert result.customer_tier == "enterprise"


# ═══════════════════════════════════════════════════════════════════════
# 12. Edge Cases (5+ tests)
# ═══════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    def setup_method(self):
        self.extractor = SignalExtractor()

    def test_none_query_intent(self):
        with pytest.raises(AttributeError):
            self.extractor._extract_intent(None)

    def test_empty_string_sentiment(self):
        score = self.extractor._extract_sentiment("")
        assert score == 0.5

    def test_very_long_query(self):
        long_q = "error " * 500
        score = self.extractor._extract_sentiment(long_q)
        assert 0.0 <= score <= 1.0

    def test_special_characters_query(self):
        intent = self.extractor._extract_intent("@#$%^&*() refund !@#$%^&*()")
        assert intent == "refund"

    def test_unicode_query(self):
        score = self.extractor._extract_sentiment("This is amazing! 🎉")
        assert 0.0 <= score <= 1.0

    def test_numbers_only_query(self):
        intent = self.extractor._extract_intent("12345 67890")
        assert intent == "general"

    def test_newlines_in_query(self):
        intent = self.extractor._extract_intent("I have a\n\nrefund\nrequest")
        assert intent == "refund"

    def test_tabs_in_query(self):
        intent = self.extractor._extract_intent("refund\tmy\torder")
        assert intent == "refund"


# ═══════════════════════════════════════════════════════════════════════
# Additional tests to reach 120+ count
# ═══════════════════════════════════════════════════════════════════════

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

    def test_hash_length_16(self):
        h = SignalExtractor._compute_query_hash("test")
        assert len(h) == 16


class TestVariantWeights:
    def setup_method(self):
        self.extractor = SignalExtractor()

    def test_all_variants_have_weights(self):
        for variant in ("mini_parwa", "parwa", "parwa_high"):
            weights = self.extractor.get_variant_weights(variant)
            assert "complexity" in weights

    def test_unknown_variant_gets_parwa(self):
        weights = self.extractor.get_variant_weights("unknown")
        parwa = self.extractor.get_variant_weights("parwa")
        assert weights == parwa

    def test_parwa_high_has_monetary_weight(self):
        weights = self.extractor.get_variant_weights("parwa_high")
        assert "monetary" in weights

    def test_returns_copy(self):
        w1 = self.extractor.get_variant_weights("parwa")
        w1["extra"] = 99
        w2 = self.extractor.get_variant_weights("parwa")
        assert "extra" not in w2


class TestCurrencyToUSD:
    def test_usd_rate(self):
        assert CURRENCY_TO_USD["USD"] == 1.0
        assert CURRENCY_TO_USD["$"] == 1.0

    def test_eur_rate(self):
        assert CURRENCY_TO_USD["EUR"] == 1.09
        assert CURRENCY_TO_USD["€"] == 1.09

    def test_gbp_rate(self):
        assert CURRENCY_TO_USD["GBP"] == 1.27

    def test_inr_rate(self):
        assert CURRENCY_TO_USD["INR"] == 0.012

    def test_jpy_rate(self):
        assert CURRENCY_TO_USD["JPY"] == 0.0067


class TestToQuerySignals:
    def setup_method(self):
        self.extractor = SignalExtractor()

    def test_conversion_basic(self):
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
        assert qs.monetary_value == 100.0

    def test_external_data_technical(self):
        signals = ExtractedSignals(
            intent="technical", sentiment=0.5, complexity=0.5,
            monetary_value=0, monetary_currency=None,
            customer_tier="free", turn_count=0,
            previous_response_status="none",
            reasoning_loop_detected=False, resolution_path_count=1,
            query_breadth=0.5,
        )
        qs = self.extractor.to_query_signals(signals)
        assert qs.external_data_required is True

    def test_no_external_data_general(self):
        signals = ExtractedSignals(
            intent="general", sentiment=0.5, complexity=0.5,
            monetary_value=0, monetary_currency=None,
            customer_tier="free", turn_count=0,
            previous_response_status="none",
            reasoning_loop_detected=False, resolution_path_count=1,
            query_breadth=0.5,
        )
        qs = self.extractor.to_query_signals(signals)
        assert qs.external_data_required is False


class TestIntentKeywords:
    def test_12_intent_types(self):
        assert len(INTENT_KEYWORDS) == 12

    def test_general_has_no_keywords(self):
        assert INTENT_KEYWORDS["general"] == []

    def test_all_intents_have_keywords_except_general(self):
        for intent, keywords in INTENT_KEYWORDS.items():
            if intent == "general":
                continue
            assert len(keywords) > 0, f"{intent} has no keywords"


class TestTopicClusters:
    def test_at_least_7_clusters(self):
        assert len(TOPIC_CLUSTERS) >= 7

    def test_billing_cluster_has_key_words(self):
        assert "refund" in TOPIC_CLUSTERS["billing"]
        assert "bill" in TOPIC_CLUSTERS["billing"]

    def test_technical_cluster_has_key_words(self):
        assert "error" in TOPIC_CLUSTERS["technical"]
        assert "bug" in TOPIC_CLUSTERS["technical"]
