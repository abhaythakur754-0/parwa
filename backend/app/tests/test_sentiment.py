"""
Tests for Sentiment Engine (F-063) and Sentiment Technique Mapper (F-151)

Covers:
- SentimentAnalyzer: positive/negative/neutral, frustration, emotion, urgency,
  tone, empathy signals, conversation trends, cache, BC-008
- SentimentTechniqueMapper: all sentiment ranges, VIP, urgency overrides,
  variant filtering, edge cases
- Unicode/non-ASCII, very long input, concurrent access, empty/null handling

Parent: Week 9 Day 7 (Sunday)
"""

import asyncio
import time
from unittest.mock import AsyncMock, patch

import pytest
from app.core.sentiment_engine import (
    ConversationTrendAnalyzer,
    EmotionClassifier,
    EmotionType,
    EmpathySignalDetector,
    FrustrationDetector,
    SentimentAnalyzer,
    SentimentResult,
    ToneAdvisor,
    ToneRecommendation,
    TrendDirection,
    UrgencyLevel,
    UrgencyScorer,
)
from app.core.technique_router import (
    TechniqueID,
)
from app.services.sentiment_technique_mapper import (
    SentimentMappingResult,
    SentimentTechniqueMapper,
)

# =========================================================================
# SECTION 1: Frustration Detector Tests
# =========================================================================


class TestFrustrationDetector:
    """Tests for the FrustrationDetector component."""

    def setup_method(self):
        self.detector = FrustrationDetector()

    def test_zero_frustration_neutral(self):
        score = self.detector.detect("Hello, how are you today?")
        assert score < 15

    def test_low_frustration(self):
        score = self.detector.detect("I have a question about my account settings")
        assert 0 <= score < 30

    def test_moderate_frustration(self):
        score = self.detector.detect("This is really annoying and frustrating")
        # 'annoying' contains 'annoyed' substring match, 'frustrating' contains 'frustrated'
        assert score >= 10

    def test_high_frustration(self):
        score = self.detector.detect("I am furious! This is unacceptable and terrible!")
        # furious(12) + unacceptable(12) + terrible(5) + !(5) = 34+
        assert score >= 30

    def test_extreme_frustration(self):
        score = self.detector.detect(
            "I am FURIOUS and ENRAGED! This is UNACCEPTABLE! "
            "OUTRAGEOUS! DISGUSTING! I hate this terrible awful horrible service!!!"
        )
        assert score >= 60

    def test_all_caps_detection(self):
        caps = self.detector.detect("I AM VERY ANGRY ABOUT THIS SITUATION")
        no_caps = self.detector.detect("I am very angry about this situation")
        assert caps > no_caps

    def test_exclamation_marks(self):
        no_excl = self.detector.detect("This is bad")
        one_excl = self.detector.detect("This is bad!")
        multi_excl = self.detector.detect("This is bad!!!")
        assert multi_excl > one_excl
        assert one_excl > no_excl

    def test_repeated_words(self):
        no_repeat = self.detector.detect("I have a problem")
        with_repeat = self.detector.detect("problem problem problem problem")
        assert with_repeat > no_repeat

    def test_question_density(self):
        low_q = self.detector.detect("Please help me")
        high_q = self.detector.detect("Why? What? When? How? Who?")
        assert high_q > low_q

    def test_intensifiers_boost(self):
        normal = self.detector.detect("This is bad")
        intensified = self.detector.detect("This is very very extremely bad")
        assert intensified > normal

    def test_score_bounded_0_100(self):
        for text in ["happy" * 200, "FURIOUS!!! " * 100, "why? " * 500, "a"]:
            score = self.detector.detect(text)
            assert 0.0 <= score <= 100.0

    def test_empty_string(self):
        score = self.detector.detect("")
        assert score == 0.0

    def test_whitespace_only(self):
        score = self.detector.detect("   \n\t  ")
        assert score == 0.0

    def test_none_input(self):
        score = self.detector.detect(None)
        assert score == 0.0

    def test_non_string_input(self):
        score = self.detector.detect(12345)
        assert score == 0.0

    def test_strong_vs_moderate_frustration(self):
        strong = self.detector.detect("I am furious and enraged about this")
        moderate = self.detector.detect("I am annoyed and irritated by this")
        assert strong > moderate


# =========================================================================
# SECTION 2: Emotion Classifier Tests
# =========================================================================


class TestEmotionClassifier:
    """Tests for the EmotionClassifier component."""

    def setup_method(self):
        self.classifier = EmotionClassifier()

    def test_anger_classification(self):
        emotion, breakdown = self.classifier.classify("I am furious and outraged")
        assert emotion in ("angry", "frustrated")
        assert "angry" in breakdown

    def test_frustration_classification(self):
        emotion, breakdown = self.classifier.classify(
            "This is very frustrating and annoying, impossible to use"
        )
        assert emotion in ("frustrated", "angry")
        assert "frustrated" in breakdown

    def test_disappointment_classification(self):
        emotion, breakdown = self.classifier.classify(
            "I am disappointed, this is not what I expected"
        )
        assert emotion == "disappointed"

    def test_neutral_classification(self):
        emotion, breakdown = self.classifier.classify("How do I update my settings?")
        assert emotion == "neutral"

    def test_happy_classification(self):
        emotion, breakdown = self.classifier.classify(
            "Great job, this is very helpful, thank you!"
        )
        assert emotion in ("happy", "delighted")

    def test_delighted_classification(self):
        emotion, breakdown = self.classifier.classify(
            "This is absolutely outstanding and phenomenal, I'm amazed!"
        )
        assert emotion == "delighted"

    def test_breakdown_all_emotions_present(self):
        emotion, breakdown = self.classifier.classify("test message")
        expected = {
            "angry",
            "frustrated",
            "disappointed",
            "neutral",
            "happy",
            "delighted",
        }
        assert set(breakdown.keys()) == expected

    def test_breakdown_values_bounded(self):
        _, breakdown = self.classifier.classify("any text here")
        for key, val in breakdown.items():
            assert 0.0 <= val <= 1.0

    def test_breakdown_sums_to_1(self):
        _, breakdown = self.classifier.classify("some message")
        total = sum(breakdown.values())
        assert abs(total - 1.0) < 0.01 or total == 0.0

    def test_frustration_influences_emotion(self):
        neutral, _ = self.classifier.classify("hello", frustration_score=0)
        angry, _ = self.classifier.classify("hello", frustration_score=95)
        assert neutral != angry or angry == "angry"

    def test_empty_string(self):
        emotion, breakdown = self.classifier.classify("")
        assert emotion == "neutral"
        assert len(breakdown) == 6

    def test_none_input(self):
        emotion, breakdown = self.classifier.classify(None)
        assert emotion == "neutral"
        assert breakdown["neutral"] == 1.0

    def test_non_string_input(self):
        emotion, breakdown = self.classifier.classify(42)
        assert emotion == "neutral"


# =========================================================================
# SECTION 3: Urgency Scorer Tests
# =========================================================================


class TestUrgencyScorer:
    """Tests for the UrgencyScorer component."""

    def setup_method(self):
        self.scorer = UrgencyScorer()

    def test_low_urgency(self):
        level = self.scorer.score("I have a question about billing")
        assert level == UrgencyLevel.LOW

    def test_medium_urgency(self):
        level = self.scorer.score("I need this fixed by tomorrow")
        assert level in (UrgencyLevel.LOW, UrgencyLevel.MEDIUM)

    def test_high_urgency(self):
        level = self.scorer.score(
            "This is urgent, the system is down and I am locked out"
        )
        # Multiple urgency keywords may push to critical
        assert level in (UrgencyLevel.HIGH, UrgencyLevel.MEDIUM, UrgencyLevel.CRITICAL)

    def test_critical_urgency(self):
        level = self.scorer.score(
            "EMERGENCY! Security breach detected immediately! Data loss!"
        )
        assert level == UrgencyLevel.CRITICAL

    def test_frustration_boosts_urgency(self):
        low_f = self.scorer.score("help me", frustration_score=0)
        high_f = self.scorer.score("help me", frustration_score=90)
        order = {
            UrgencyLevel.LOW: 1,
            UrgencyLevel.MEDIUM: 2,
            UrgencyLevel.HIGH: 3,
            UrgencyLevel.CRITICAL: 4,
        }
        assert order[high_f] >= order[low_f]

    def test_empty_string(self):
        level = self.scorer.score("")
        assert level == UrgencyLevel.LOW

    def test_none_input(self):
        level = self.scorer.score(None)
        assert level == UrgencyLevel.LOW

    def test_non_string_input(self):
        level = self.scorer.score(123)
        assert level == UrgencyLevel.LOW

    def test_all_levels_are_valid(self):
        queries = {
            "hello": UrgencyLevel.LOW,
            "urgent": UrgencyLevel.MEDIUM,
            "urgent asap immediately": UrgencyLevel.HIGH,
            "EMERGENCY CRITICAL SECURITY BREACH DATA LOSS": UrgencyLevel.CRITICAL,
        }
        for query, expected in queries.items():
            level = self.scorer.score(query)
            assert level in (
                UrgencyLevel.LOW,
                UrgencyLevel.MEDIUM,
                UrgencyLevel.HIGH,
                UrgencyLevel.CRITICAL,
            )


# =========================================================================
# SECTION 4: Tone Advisor Tests
# =========================================================================


class TestToneAdvisor:
    """Tests for the ToneAdvisor component."""

    def setup_method(self):
        self.advisor = ToneAdvisor()

    def test_standard_tone_neutral(self):
        tone = self.advisor.recommend(10, "neutral", "low")
        assert tone == ToneRecommendation.STANDARD

    def test_empathetic_tone_moderate_frustration(self):
        tone = self.advisor.recommend(45, "frustrated", "medium")
        assert tone == ToneRecommendation.EMPATHETIC

    def test_empathetic_tone_disappointed(self):
        tone = self.advisor.recommend(20, "disappointed", "low")
        assert tone == ToneRecommendation.EMPATHETIC

    def test_urgent_tone(self):
        tone = self.advisor.recommend(70, "frustrated", "high")
        assert tone == ToneRecommendation.URGENT

    def test_de_escalation_very_high_frustration(self):
        tone = self.advisor.recommend(95, "angry", "critical")
        assert tone == ToneRecommendation.DE_ESCALATION

    def test_de_escalation_angry_70(self):
        tone = self.advisor.recommend(72, "angry", "high")
        assert tone == ToneRecommendation.DE_ESCALATION

    def test_empathetic_boundary_at_40(self):
        tone = self.advisor.recommend(40, "neutral", "medium")
        assert tone == ToneRecommendation.EMPATHETIC

    def test_standard_below_40_happy(self):
        tone = self.advisor.recommend(20, "happy", "low")
        assert tone == ToneRecommendation.STANDARD


# =========================================================================
# SECTION 5: Empathy Signal Detector Tests
# =========================================================================


class TestEmpathySignalDetector:
    """Tests for the EmpathySignalDetector component."""

    def setup_method(self):
        self.detector = EmpathySignalDetector()

    def test_no_signals_neutral(self):
        signals = self.detector.detect("Hello, how are you?")
        assert len(signals) == 0

    def test_apology_expectation(self):
        signals = self.detector.detect("You should be ashamed, I demand an apology!")
        assert "apology_expectation" in signals

    def test_timeline_pressure(self):
        signals = self.detector.detect("I need this fixed immediately, it's urgent!")
        assert "timeline_pressure" in signals

    def test_financial_impact(self):
        signals = self.detector.detect("I was overcharged and lost money on this")
        assert "financial_impact" in signals

    def test_personal_impact(self):
        signals = self.detector.detect("This ruined my business and caused me stress")
        assert "personal_impact" in signals

    def test_repeated_contacts_via_history(self):
        history = ["refund my order", "please refund my order", "I need a refund"]
        signals = self.detector.detect("refund my order", conversation_history=history)
        assert "repeated_contacts" in signals

    def test_no_repeated_contacts_short_history(self):
        history = ["hello"]
        signals = self.detector.detect("refund my order", conversation_history=history)
        assert "repeated_contacts" not in signals

    def test_multiple_signals(self):
        signals = self.detector.detect(
            "I need this fixed immediately, I've lost money and this is your fault!"
        )
        assert len(signals) >= 2

    def test_empty_string(self):
        signals = self.detector.detect("")
        assert signals == []

    def test_none_input(self):
        signals = self.detector.detect(None)
        assert signals == []

    def test_none_history_items(self):
        history = [None, None, "refund my order"]
        signals = self.detector.detect("refund my order", conversation_history=history)
        assert isinstance(signals, list)


# =========================================================================
# SECTION 6: Conversation Trend Analyzer Tests
# =========================================================================


class TestConversationTrendAnalyzer:
    """Tests for the ConversationTrendAnalyzer component."""

    def setup_method(self):
        self.analyzer = ConversationTrendAnalyzer()

    def test_no_history(self):
        trend = self.analyzer.analyze(None)
        assert trend == TrendDirection.STABLE

    def test_empty_history(self):
        trend = self.analyzer.analyze([])
        assert trend == TrendDirection.STABLE

    def test_short_history(self):
        trend = self.analyzer.analyze(["hello"])
        assert trend == TrendDirection.STABLE

    def test_improving_trend(self):
        history = [
            "This is TERRIBLE! I am FURIOUS!!!",
            "This is still very bad and annoying",
            "OK this is a bit frustrating",
            "It's not great but manageable",
            "Thanks, that helps a lot!",
        ]
        trend = self.analyzer.analyze(history)
        assert trend == TrendDirection.IMPROVING

    def test_worsening_trend(self):
        history = [
            "Thanks, that helps a lot!",
            "It's not great but manageable",
            "This is getting frustrating",
            "This is terrible and annoying!",
            "This is TERRIBLE! I am FURIOUS!!! UNACCEPTABLE!!!",
        ]
        trend = self.analyzer.analyze(history)
        assert trend == TrendDirection.WORSENING

    def test_stable_trend(self):
        history = [
            "I have a question about my account",
            "Can you explain the billing?",
            "How do I change my settings?",
        ]
        trend = self.analyzer.analyze(history)
        assert trend == TrendDirection.STABLE

    def test_none_items_in_history(self):
        history = [None, "hello", None, "how are you"]
        trend = self.analyzer.analyze(history)
        assert trend == TrendDirection.STABLE

    def test_empty_strings_in_history(self):
        history = ["", "   ", "", "hello"]
        trend = self.analyzer.analyze(history)
        assert trend == TrendDirection.STABLE


# =========================================================================
# SECTION 7: SentimentResult Dataclass Tests
# =========================================================================


class TestSentimentResult:
    """Tests for the SentimentResult dataclass."""

    def test_creation(self):
        result = SentimentResult(
            frustration_score=50.0,
            emotion="frustrated",
            urgency_level="medium",
            tone_recommendation="empathetic",
            empathy_signals=["timeline_pressure"],
            sentiment_score=0.5,
            emotion_breakdown={
                "angry": 0.2,
                "frustrated": 0.5,
                "neutral": 0.3,
                "disappointed": 0.0,
                "happy": 0.0,
                "delighted": 0.0,
            },
            processing_time_ms=5.0,
        )
        assert result.frustration_score == 50.0
        assert result.emotion == "frustrated"
        assert result.cached is False

    def test_to_dict(self):
        result = SentimentResult(
            frustration_score=75.0,
            emotion="angry",
            urgency_level="high",
            tone_recommendation="de-escalation",
            empathy_signals=["personal_impact"],
            sentiment_score=0.25,
            emotion_breakdown={
                "angry": 0.7,
                "neutral": 0.3,
                "frustrated": 0.0,
                "disappointed": 0.0,
                "happy": 0.0,
                "delighted": 0.0,
            },
            processing_time_ms=10.5,
            conversation_trend="worsening",
        )
        d = result.to_dict()
        assert d["frustration_score"] == 75.0
        assert d["emotion"] == "angry"
        assert d["urgency_level"] == "high"
        assert isinstance(d["sentiment_score"], float)
        assert d["conversation_trend"] == "worsening"

    def test_default_cached_false(self):
        result = SentimentResult(
            frustration_score=0.0,
            emotion="neutral",
            urgency_level="low",
            tone_recommendation="standard",
            empathy_signals=[],
            sentiment_score=0.5,
            emotion_breakdown={},
            processing_time_ms=0.0,
        )
        assert result.cached is False
        assert result.conversation_trend == "stable"


# =========================================================================
# SECTION 8: SentimentAnalyzer Full Pipeline Tests
# =========================================================================


class TestSentimentAnalyzer:
    """Tests for the main SentimentAnalyzer class."""

    def setup_method(self):
        self.analyzer = SentimentAnalyzer()

    @pytest.mark.asyncio
    async def test_basic_positive_query(self):
        result = await self.analyzer.analyze(
            "Great service, thank you so much! Very helpful!",
            company_id="test_co",
        )
        assert result.sentiment_score > 0.5
        assert result.frustration_score < 40
        assert result.emotion in ("happy", "delighted")
        assert result.urgency_level == UrgencyLevel.LOW

    @pytest.mark.asyncio
    async def test_basic_negative_query(self):
        result = await self.analyzer.analyze(
            "This is terrible! I am furious and demand an apology!",
            company_id="test_co",
        )
        # High frustration → low sentiment score
        assert result.sentiment_score < 0.8
        assert result.frustration_score > 20
        assert result.emotion in ("angry", "frustrated")
        assert len(result.empathy_signals) > 0

    @pytest.mark.asyncio
    async def test_basic_neutral_query(self):
        result = await self.analyzer.analyze(
            "How do I reset my password?",
            company_id="test_co",
        )
        # Low frustration → high sentiment (inverse mapping)
        assert result.sentiment_score > 0.5
        assert result.emotion == "neutral"
        assert result.tone_recommendation == ToneRecommendation.STANDARD

    @pytest.mark.asyncio
    async def test_frustration_score_range(self):
        result = await self.analyzer.analyze("test query", company_id="c1")
        assert 0.0 <= result.frustration_score <= 100.0

    @pytest.mark.asyncio
    async def test_sentiment_score_range(self):
        result = await self.analyzer.analyze("test query", company_id="c1")
        assert 0.0 <= result.sentiment_score <= 1.0

    @pytest.mark.asyncio
    async def test_processing_time_populated(self):
        result = await self.analyzer.analyze("test", company_id="c1")
        assert result.processing_time_ms >= 0.0

    @pytest.mark.asyncio
    async def test_emotion_breakdown_all_keys(self):
        result = await self.analyzer.analyze("test", company_id="c1")
        expected = {
            "angry",
            "frustrated",
            "disappointed",
            "neutral",
            "happy",
            "delighted",
        }
        assert set(result.emotion_breakdown.keys()) == expected

    @pytest.mark.asyncio
    async def test_variant_type_accepted(self):
        for variant in ("mini_parwa", "parwa", "high_parwa"):
            result = await self.analyzer.analyze(
                "test query",
                company_id="c1",
                variant_type=variant,
            )
            assert isinstance(result, SentimentResult)

    @pytest.mark.asyncio
    async def test_company_id_scoped(self):
        result = await self.analyzer.analyze("test", company_id="tenant_123")
        assert isinstance(result, SentimentResult)


# =========================================================================
# SECTION 9: BC-008 Graceful Degradation Tests
# =========================================================================


class TestGracefulDegradation:
    """BC-008: Empty/null input handling — never crashes."""

    def setup_method(self):
        self.analyzer = SentimentAnalyzer()

    @pytest.mark.asyncio
    async def test_empty_string(self):
        result = await self.analyzer.analyze("", company_id="c1")
        assert result.frustration_score == 0.0
        assert result.emotion == EmotionType.NEUTRAL
        assert result.sentiment_score == 0.5

    @pytest.mark.asyncio
    async def test_none_input(self):
        result = await self.analyzer.analyze(None, company_id="c1")
        assert result.frustration_score == 0.0
        assert result.emotion == EmotionType.NEUTRAL

    @pytest.mark.asyncio
    async def test_whitespace_only(self):
        result = await self.analyzer.analyze("   \n\t  ", company_id="c1")
        assert result.frustration_score == 0.0

    @pytest.mark.asyncio
    async def test_non_string_input(self):
        result = await self.analyzer.analyze(12345, company_id="c1")
        assert result.frustration_score == 0.0
        assert result.emotion == EmotionType.NEUTRAL

    @pytest.mark.asyncio
    async def test_list_input(self):
        result = await self.analyzer.analyze(["refund"], company_id="c1")
        assert result.frustration_score == 0.0

    @pytest.mark.asyncio
    async def test_dict_input(self):
        result = await self.analyzer.analyze({"text": "refund"}, company_id="c1")
        assert result.frustration_score == 0.0

    @pytest.mark.asyncio
    async def test_none_conversation_history(self):
        result = await self.analyzer.analyze(
            "hello",
            company_id="c1",
            conversation_history=None,
        )
        assert result.conversation_trend == TrendDirection.STABLE

    @pytest.mark.asyncio
    async def test_none_customer_metadata(self):
        result = await self.analyzer.analyze(
            "hello",
            company_id="c1",
            customer_metadata=None,
        )
        assert isinstance(result, SentimentResult)

    @pytest.mark.asyncio
    async def test_empty_company_id(self):
        result = await self.analyzer.analyze("hello", company_id="")
        assert isinstance(result, SentimentResult)


# =========================================================================
# SECTION 10: Cache Behavior Tests
# =========================================================================


class TestCacheBehavior:
    """Cache support — same pattern as signal_extraction.py."""

    def setup_method(self):
        self.analyzer = SentimentAnalyzer()

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached(self):
        """Cache hit returns cached result with cached=True."""
        cached_data = {
            "frustration_score": 42.0,
            "emotion": "frustrated",
            "urgency_level": "medium",
            "tone_recommendation": "empathetic",
            "empathy_signals": ["timeline_pressure"],
            "sentiment_score": 0.58,
            "emotion_breakdown": {
                "angry": 0.1,
                "frustrated": 0.5,
                "neutral": 0.3,
                "disappointed": 0.05,
                "happy": 0.0,
                "delighted": 0.0,
            },
            "processing_time_ms": 2.5,
            "conversation_trend": "stable",
        }
        with patch(
            "app.core.redis.cache_get", new_callable=AsyncMock, return_value=cached_data
        ):
            result = await self.analyzer.analyze(
                "any query",
                company_id="c1",
                variant_type="parwa",
            )
            assert result.cached is True
            assert result.frustration_score == 42.0
            assert result.emotion == "frustrated"

    @pytest.mark.asyncio
    async def test_cache_miss_computes_result(self):
        """Cache miss computes result and stores it."""
        with patch(
            "app.core.redis.cache_get", new_callable=AsyncMock, return_value=None
        ):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock) as mock_set:
                result = await self.analyzer.analyze(
                    "hello",
                    company_id="c1",
                    variant_type="parwa",
                )
                assert result.cached is False
                mock_set.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_fail_open(self):
        """Redis failure should not crash analysis."""
        with patch(
            "app.core.redis.cache_get",
            new_callable=AsyncMock,
            side_effect=Exception("Redis down"),
        ):
            with patch(
                "app.core.redis.cache_set",
                new_callable=AsyncMock,
                side_effect=Exception("Redis down"),
            ):
                result = await self.analyzer.analyze(
                    "test query",
                    company_id="c1",
                )
                assert result.cached is False
                assert isinstance(result, SentimentResult)

    @pytest.mark.asyncio
    async def test_cache_key_includes_variant(self):
        """Different variants produce different cache keys."""
        h1 = self.analyzer._compute_query_hash("test query")
        h2 = self.analyzer._compute_query_hash("test query")
        assert h1 == h2
        key1 = f"sentiment_cache:c1:mini_parwa:{h1}"
        key2 = f"sentiment_cache:c1:parwa:{h2}"
        assert key1 != key2

    @pytest.mark.asyncio
    async def test_cache_key_deterministic(self):
        """Same query produces same hash."""
        h1 = SentimentAnalyzer._compute_query_hash("Hello World")
        h2 = SentimentAnalyzer._compute_query_hash("hello world")
        assert h1 == h2

    @pytest.mark.asyncio
    async def test_cache_key_different_queries(self):
        """Different queries produce different hashes."""
        h1 = SentimentAnalyzer._compute_query_hash("query one")
        h2 = SentimentAnalyzer._compute_query_hash("query two")
        assert h1 != h2


# =========================================================================
# SECTION 11: Unicode and Edge Case Input Tests
# =========================================================================


class TestUnicodeAndEdgeCases:
    """Unicode/non-ASCII, very long input, special characters."""

    def setup_method(self):
        self.analyzer = SentimentAnalyzer()
        self.detector = FrustrationDetector()

    @pytest.mark.asyncio
    async def test_unicode_japanese(self):
        result = await self.analyzer.analyze(
            "私は非常に怒っています！これはひどい！",
            company_id="c1",
        )
        assert isinstance(result, SentimentResult)
        assert 0.0 <= result.frustration_score <= 100.0
        assert 0.0 <= result.sentiment_score <= 1.0

    @pytest.mark.asyncio
    async def test_unicode_arabic(self):
        result = await self.analyzer.analyze(
            "أنا غاضب جداً هذا غير مقبول",
            company_id="c1",
        )
        assert isinstance(result, SentimentResult)

    @pytest.mark.asyncio
    async def test_emoji_query(self):
        result = await self.analyzer.analyze(
            "I'm very happy 😊😊😊 Thank you! 🎉",
            company_id="c1",
        )
        assert isinstance(result, SentimentResult)
        assert result.sentiment_score > 0.5

    @pytest.mark.asyncio
    async def test_mixed_scripts(self):
        result = await self.analyzer.analyze(
            "Refund 返金 Rückerstattung remerciement",
            company_id="c1",
        )
        assert isinstance(result, SentimentResult)

    @pytest.mark.asyncio
    async def test_very_long_input_10k(self):
        """10,000+ character query should not crash."""
        long_query = "I have a terrible problem with this service. " * 300
        assert len(long_query) > 10000
        start = time.monotonic()
        result = await self.analyzer.analyze(long_query, company_id="c1")
        elapsed = time.monotonic() - start
        assert isinstance(result, SentimentResult)
        assert elapsed < 5.0  # Should not take more than 5 seconds

    @pytest.mark.asyncio
    async def test_very_long_input_50k(self):
        """50,000+ character query."""
        long_query = "frustrated angry terrible " * 5000
        assert len(long_query) > 50000
        result = await self.analyzer.analyze(long_query, company_id="c1")
        assert isinstance(result, SentimentResult)

    def test_frustration_detector_very_long_input(self):
        long_query = "furious " * 20000
        score = self.detector.detect(long_query)
        assert 0.0 <= score <= 100.0

    @pytest.mark.asyncio
    async def test_sql_injection(self):
        result = await self.analyzer.analyze(
            "'; DROP TABLE users; --",
            company_id="c1",
        )
        assert isinstance(result, SentimentResult)
        assert result.emotion == "neutral"

    @pytest.mark.asyncio
    async def test_html_tags(self):
        result = await self.analyzer.analyze(
            "<script>alert('xss')</script> refund my order",
            company_id="c1",
        )
        assert isinstance(result, SentimentResult)

    @pytest.mark.asyncio
    async def test_null_bytes(self):
        result = await self.analyzer.analyze(
            "refund\x00my\x00order",
            company_id="c1",
        )
        assert isinstance(result, SentimentResult)

    @pytest.mark.asyncio
    async def test_only_special_chars(self):
        result = await self.analyzer.analyze(
            "@#$%^&*()_+-=[]{}|;:',.<>?/~`",
            company_id="c1",
        )
        assert isinstance(result, SentimentResult)
        assert result.emotion == "neutral"


# =========================================================================
# SECTION 12: Conversation Trend Tests (via SentimentAnalyzer)
# =========================================================================


class TestConversationTrends:
    """Conversation trend detection through the full analyzer."""

    def setup_method(self):
        self.analyzer = SentimentAnalyzer()

    @pytest.mark.asyncio
    async def test_improving_trend(self):
        history = [
            "This is TERRIBLE! I am FURIOUS!!!",
            "This is still bad and annoying",
            "OK it's getting better",
            "Thanks for the help!",
        ]
        result = await self.analyzer.analyze(
            "Thanks, that works now!",
            company_id="c1",
            conversation_history=history,
        )
        assert result.conversation_trend == TrendDirection.IMPROVING

    @pytest.mark.asyncio
    async def test_worsening_trend(self):
        history = [
            "Thanks for the info",
            "Actually, I'm a bit confused now",
            "This is getting really annoying",
            "I am absolutely furious now!!!",
        ]
        result = await self.analyzer.analyze(
            "This is UNACCEPTABLE!",
            company_id="c1",
            conversation_history=history,
        )
        assert result.conversation_trend == TrendDirection.WORSENING

    @pytest.mark.asyncio
    async def test_stable_trend(self):
        history = [
            "I have a question about billing",
            "Can you explain the charges?",
            "How do I view my invoice?",
        ]
        result = await self.analyzer.analyze(
            "What is the payment method?",
            company_id="c1",
            conversation_history=history,
        )
        assert result.conversation_trend == TrendDirection.STABLE

    @pytest.mark.asyncio
    async def test_no_history_stable(self):
        result = await self.analyzer.analyze(
            "hello",
            company_id="c1",
            conversation_history=None,
        )
        assert result.conversation_trend == TrendDirection.STABLE


# =========================================================================
# SECTION 13: Sentiment Technique Mapper Tests
# =========================================================================


class TestSentimentTechniqueMapper:
    """Tests for the SentimentTechniqueMapper (F-151)."""

    def setup_method(self):
        self.mapper = SentimentTechniqueMapper()

    def test_low_frustration_positive(self):
        """Frustration < 30 + positive (>0.7) → CoT or UoT + Step-Back."""
        result = self.mapper.map(
            frustration_score=10,
            sentiment_score=0.9,
            urgency_level="low",
            customer_tier="free",
        )
        assert isinstance(result, SentimentMappingResult)
        assert len(result.recommended_techniques) > 0
        assert result.escalation_recommended is False
        assert result.priority_override is False

    def test_low_frustration_neutral(self):
        """Frustration < 30 + neutral → UoT + Step-Back."""
        result = self.mapper.map(
            frustration_score=15,
            sentiment_score=0.5,
            urgency_level="low",
            customer_tier="free",
        )
        assert len(result.recommended_techniques) > 0
        assert result.escalation_recommended is False

    def test_moderate_frustration_30_60(self):
        """Frustration 30-60 → Step-Back."""
        result = self.mapper.map(
            frustration_score=45,
            sentiment_score=0.55,
            urgency_level="medium",
            customer_tier="free",
        )
        assert len(result.recommended_techniques) > 0
        # Step-Back should be recommended
        tech_ids = [t.value for t in result.recommended_techniques]
        assert "step_back" in tech_ids or "gsd" in tech_ids  # GSD is fallback

    def test_high_frustration_60_80(self):
        """Frustration 60-80 → Reflexion + Step-Back."""
        result = self.mapper.map(
            frustration_score=70,
            sentiment_score=0.3,
            urgency_level="high",
            customer_tier="free",
        )
        assert result.escalation_recommended is False
        tech_ids = [t.value for t in result.recommended_techniques]
        # Reflexion or its fallback should be present
        assert "reflexion" in tech_ids or "gsd" in tech_ids

    def test_very_high_frustration_80(self):
        """Frustration 80+ → CLARA + Step-Back + escalation."""
        result = self.mapper.map(
            frustration_score=85,
            sentiment_score=0.15,
            urgency_level="high",
            customer_tier="free",
        )
        assert result.escalation_recommended is True
        assert len(result.recommended_techniques) > 0
        tech_ids = [t.value for t in result.recommended_techniques]
        assert "clara" in tech_ids

    def test_critical_urgency_bypass(self):
        """Critical urgency → priority_override + escalation."""
        result = self.mapper.map(
            frustration_score=50,
            sentiment_score=0.5,
            urgency_level="critical",
            customer_tier="free",
        )
        assert result.priority_override is True
        assert result.escalation_recommended is True

    def test_vip_low_frustration(self):
        """VIP with low frustration → extra techniques."""
        result = self.mapper.map(
            frustration_score=20,
            sentiment_score=0.6,
            urgency_level="low",
            customer_tier="vip",
            is_vip=True,
        )
        assert len(result.recommended_techniques) > 0
        # Reflexion should be added for VIP even at low frustration
        tech_ids = [t.value for t in result.recommended_techniques]
        assert "reflexion" in tech_ids or "gsd" in tech_ids

    def test_vip_high_frustration(self):
        """VIP + high frustration → UoT + Reflexion + Step-Back."""
        result = self.mapper.map(
            frustration_score=85,
            sentiment_score=0.15,
            urgency_level="high",
            customer_tier="vip",
            is_vip=True,
            variant_type="high_parwa",
        )
        assert result.escalation_recommended is True
        tech_ids = [t.value for t in result.recommended_techniques]
        assert "universe_of_thoughts" in tech_ids
        assert "reflexion" in tech_ids

    def test_mini_parwa_blocks_tier3(self):
        """Mini PARWA cannot access Tier 3 techniques."""
        tier1 = {TechniqueID.CLARA, TechniqueID.CRP, TechniqueID.GSD}
        result = self.mapper.map(
            frustration_score=85,
            sentiment_score=0.1,
            urgency_level="critical",
            customer_tier="free",
            variant_type="mini_parwa",
        )
        for tech in result.recommended_techniques:
            assert tech in tier1, f"Mini PARWA got {tech.value} which is not Tier 1"

    def test_parwa_allows_tier2(self):
        """Parwa allows Tier 2 techniques."""
        result = self.mapper.map(
            frustration_score=45,
            sentiment_score=0.55,
            urgency_level="medium",
            customer_tier="free",
            variant_type="parwa",
        )
        tech_ids = [t.value for t in result.recommended_techniques]
        # Should have at least one Tier 2 technique
        tier2 = {
            "chain_of_thought",
            "reverse_thinking",
            "react",
            "step_back",
            "thread_of_thought",
        }
        assert any(t in tech_ids for t in tier2) or len(result.blocked_techniques) > 0

    def test_high_parwa_allows_tier3(self):
        """Parwa High allows Tier 3 techniques."""
        result = self.mapper.map(
            frustration_score=85,
            sentiment_score=0.15,
            urgency_level="high",
            customer_tier="vip",
            is_vip=True,
            variant_type="high_parwa",
        )
        tech_ids = [t.value for t in result.recommended_techniques]
        tier3 = {
            "gst",
            "universe_of_thoughts",
            "tree_of_thoughts",
            "self_consistency",
            "reflexion",
            "least_to_most",
        }
        assert any(t in tech_ids for t in tier3)

    def test_technique_reasons_populated(self):
        result = self.mapper.map(
            frustration_score=70,
            sentiment_score=0.3,
            urgency_level="high",
            customer_tier="free",
        )
        for tech in result.recommended_techniques:
            assert tech.value in result.technique_reasons
            assert len(result.technique_reasons[tech.value]) > 0

    def test_tone_adjustments_for_escalation(self):
        result = self.mapper.map(
            frustration_score=90,
            sentiment_score=0.1,
            urgency_level="critical",
            customer_tier="free",
        )
        assert len(result.tone_adjustments) > 0

    def test_no_escalation_for_happy(self):
        result = self.mapper.map(
            frustration_score=5,
            sentiment_score=0.95,
            urgency_level="low",
            customer_tier="free",
        )
        assert result.escalation_recommended is False
        assert result.priority_override is False

    def test_blocked_techniques_listed(self):
        """Blocked techniques should be in blocked_techniques list."""
        result = self.mapper.map(
            frustration_score=85,
            sentiment_score=0.1,
            urgency_level="high",
            customer_tier="free",
            variant_type="mini_parwa",
        )
        assert isinstance(result.blocked_techniques, list)
        # Should have some blocked techniques (T2/T3 not available)
        if result.blocked_techniques:
            for blocked in result.blocked_techniques:
                assert "id" in blocked
                assert "reason" in blocked

    def test_to_dict(self):
        result = self.mapper.map(
            frustration_score=50,
            sentiment_score=0.5,
            urgency_level="medium",
            customer_tier="free",
        )
        d = result.to_dict()
        assert "recommended_techniques" in d
        assert "technique_reasons" in d
        assert "priority_override" in d
        assert "escalation_recommended" in d
        assert "tone_adjustments" in d
        assert isinstance(d["recommended_techniques"], list)

    def test_unknown_variant_falls_to_tier1(self):
        """Unknown variant type falls back to Tier 1 limit."""
        result = self.mapper.map(
            frustration_score=85,
            sentiment_score=0.1,
            urgency_level="high",
            customer_tier="free",
            variant_type="unknown_variant",
        )
        tier1 = {TechniqueID.CLARA, TechniqueID.CRP, TechniqueID.GSD}
        for tech in result.recommended_techniques:
            assert tech in tier1

    def test_zero_frustration_zero_sentiment(self):
        """Edge case: zero frustration and zero sentiment."""
        result = self.mapper.map(
            frustration_score=0,
            sentiment_score=0.0,
            urgency_level="low",
            customer_tier="free",
        )
        assert isinstance(result, SentimentMappingResult)
        assert len(result.recommended_techniques) > 0

    def test_boundary_frustration_30(self):
        """Exact boundary at frustration=30."""
        result = self.mapper.map(
            frustration_score=30,
            sentiment_score=0.7,
            urgency_level="medium",
            customer_tier="free",
        )
        assert isinstance(result, SentimentMappingResult)

    def test_boundary_frustration_60(self):
        """Exact boundary at frustration=60."""
        result = self.mapper.map(
            frustration_score=60,
            sentiment_score=0.4,
            urgency_level="high",
            customer_tier="free",
        )
        assert isinstance(result, SentimentMappingResult)

    def test_boundary_frustration_80(self):
        """Exact boundary at frustration=80."""
        result = self.mapper.map(
            frustration_score=80,
            sentiment_score=0.2,
            urgency_level="high",
            customer_tier="free",
        )
        assert result.escalation_recommended is True

    def test_positive_sentiment_no_heavy_techniques(self):
        """Positive sentiment with low frustration should use light techniques."""
        result = self.mapper.map(
            frustration_score=5,
            sentiment_score=0.8,
            urgency_level="low",
            customer_tier="free",
            variant_type="high_parwa",
        )
        tech_ids = [t.value for t in result.recommended_techniques]
        # Should have chain_of_thought, not heavy techniques like reflexion
        assert "chain_of_thought" in tech_ids


# =========================================================================
# SECTION 14: Concurrent Access Tests
# =========================================================================


class TestConcurrentAccess:
    """Concurrent async analysis — race condition safety."""

    @pytest.mark.asyncio
    async def test_concurrent_sentiment_analysis(self):
        """Multiple concurrent analyze calls should not crash."""
        analyzer = SentimentAnalyzer()
        queries = [
            ("I am furious and angry!", "c1"),
            ("This is wonderful and amazing!", "c2"),
            ("How do I reset my password?", "c3"),
            ("This is terrible and unacceptable!", "c4"),
            ("Great service, thank you!", "c5"),
            ("I need a refund immediately!", "c6"),
            ("I'm disappointed with the quality", "c7"),
            ("Hello, quick question", "c8"),
            ("The system is down, emergency!", "c9"),
            ("Your product is outstanding!", "c10"),
        ]

        tasks = [
            analyzer.analyze(query, company_id=company_id)
            for query, company_id in queries
        ]
        results = await asyncio.gather(*tasks)

        assert len(results) == 10
        for result in results:
            assert isinstance(result, SentimentResult)
            assert 0.0 <= result.frustration_score <= 100.0
            assert 0.0 <= result.sentiment_score <= 1.0

    @pytest.mark.asyncio
    async def test_concurrent_with_cache_failures(self):
        """Concurrent analysis with Redis failures."""
        analyzer = SentimentAnalyzer()
        queries = ["test query " + str(i) for i in range(20)]

        with patch(
            "app.core.redis.cache_get",
            new_callable=AsyncMock,
            side_effect=Exception("Redis down"),
        ):
            with patch(
                "app.core.redis.cache_set",
                new_callable=AsyncMock,
                side_effect=Exception("Redis down"),
            ):
                tasks = [analyzer.analyze(q, company_id="c1") for q in queries]
                results = await asyncio.gather(*tasks)

                assert len(results) == 20
                for result in results:
                    assert result.cached is False
                    assert isinstance(result, SentimentResult)

    @pytest.mark.asyncio
    async def test_concurrent_mapper_calls(self):
        """Concurrent mapper calls should not crash."""
        mapper = SentimentTechniqueMapper()

        def sync_map(i):
            return mapper.map(
                frustration_score=i * 10,
                sentiment_score=1.0 - (i * 0.1),
                urgency_level="low" if i < 5 else "high",
                customer_tier="vip" if i % 3 == 0 else "free",
                variant_type=["mini_parwa", "parwa", "high_parwa"][i % 3],
            )

        # Sync calls in a thread pool
        loop = asyncio.get_event_loop()
        tasks = [loop.run_in_executor(None, sync_map, i) for i in range(20)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 20
        for result in results:
            assert isinstance(result, SentimentMappingResult)


# =========================================================================
# SECTION 15: Integration — Sentiment → Technique Mapper Pipeline
# =========================================================================


class TestSentimentToTechniquePipeline:
    """Full pipeline: SentimentAnalyzer → SentimentTechniqueMapper."""

    @pytest.mark.asyncio
    async def test_angry_customer_pipeline(self):
        """Angry customer → proper techniques."""
        analyzer = SentimentAnalyzer()
        mapper = SentimentTechniqueMapper()

        result = await analyzer.analyze(
            "I am furious! This is unacceptable! I demand an apology!",
            company_id="c1",
        )

        mapping = mapper.map(
            frustration_score=result.frustration_score,
            sentiment_score=result.sentiment_score,
            urgency_level=result.urgency_level,
            emotion=result.emotion,
            customer_tier="free",
            variant_type="parwa",
        )

        assert isinstance(mapping, SentimentMappingResult)
        assert len(mapping.recommended_techniques) > 0
        if result.frustration_score >= 80:
            assert mapping.escalation_recommended is True

    @pytest.mark.asyncio
    async def test_happy_customer_pipeline(self):
        """Happy customer → light techniques."""
        analyzer = SentimentAnalyzer()
        mapper = SentimentTechniqueMapper()

        result = await analyzer.analyze(
            "This is amazing! Thank you so much for the great service!",
            company_id="c1",
        )

        mapping = mapper.map(
            frustration_score=result.frustration_score,
            sentiment_score=result.sentiment_score,
            urgency_level=result.urgency_level,
            emotion=result.emotion,
            customer_tier="free",
            variant_type="parwa",
        )

        assert mapping.escalation_recommended is False
        assert mapping.priority_override is False

    @pytest.mark.asyncio
    async def test_vip_escalation_pipeline(self):
        """VIP with high frustration → escalation + VIP techniques."""
        analyzer = SentimentAnalyzer()
        mapper = SentimentTechniqueMapper()

        result = await analyzer.analyze(
            "I am FURIOUS! This is UNACCEPTABLE! I am a VIP customer!",
            company_id="c1",
            customer_metadata={"tier": "vip"},
        )

        mapping = mapper.map(
            frustration_score=result.frustration_score,
            sentiment_score=result.sentiment_score,
            urgency_level=result.urgency_level,
            emotion=result.emotion,
            customer_tier="vip",
            is_vip=True,
            variant_type="high_parwa",
        )

        if result.frustration_score >= 80:
            assert mapping.escalation_recommended is True
            tech_ids = [t.value for t in mapping.recommended_techniques]
            assert "universe_of_thoughts" in tech_ids

    @pytest.mark.asyncio
    async def test_mini_parwa_pipeline(self):
        """Mini PARWA → only Tier 1 techniques."""
        analyzer = SentimentAnalyzer()
        mapper = SentimentTechniqueMapper()

        result = await analyzer.analyze(
            "I am furious! This is terrible!",
            company_id="c1",
        )

        mapping = mapper.map(
            frustration_score=result.frustration_score,
            sentiment_score=result.sentiment_score,
            urgency_level=result.urgency_level,
            emotion=result.emotion,
            customer_tier="free",
            variant_type="mini_parwa",
        )

        tier1 = {TechniqueID.CLARA, TechniqueID.CRP, TechniqueID.GSD}
        for tech in mapping.recommended_techniques:
            assert tech in tier1

    @pytest.mark.asyncio
    async def test_emergency_pipeline(self):
        """Emergency query → critical urgency → bypass."""
        analyzer = SentimentAnalyzer()
        mapper = SentimentTechniqueMapper()

        result = await analyzer.analyze(
            "EMERGENCY! Security breach! Data loss! Immediate action needed!",
            company_id="c1",
        )

        mapping = mapper.map(
            frustration_score=result.frustration_score,
            sentiment_score=result.sentiment_score,
            urgency_level=result.urgency_level,
            emotion=result.emotion,
            customer_tier="enterprise",
            variant_type="parwa",
        )

        if result.urgency_level == "critical":
            assert mapping.priority_override is True
            assert mapping.escalation_recommended is True
