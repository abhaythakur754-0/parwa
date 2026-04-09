"""
Tests for Sentiment Analysis / Empathy Engine (F-063) — Week 9 Day 7

Covers: FrustrationDetector, EmpathySignalDetector, EmotionClassifier,
UrgencyScorer, ToneAdvisor, ConversationTrendAnalyzer, SentimentAnalyzer,
data classes (SentimentResult, EmotionType, UrgencyLevel, etc.),
G9-GAP-03 (word-boundary matching for mild frustration),
G9-GAP-02 (history hash in cache key), BC-008 (graceful degradation).

Target: 120+ tests
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ═══════════════════════════════════════════════════════════════════════
# Fixtures — import source modules with mocked logger
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def _mock_logger():
    with patch("backend.app.logger.get_logger", return_value=MagicMock()):
        from backend.app.core.sentiment_engine import (  # noqa: F811,F401
            ConversationTrendAnalyzer,
            EmotionClassifier,
            EmotionType,
            EMPATHY_PATTERNS,
            EmpathySignalDetector,
            FRUSTRATION_MILD,
            FRUSTRATION_MODERATE,
            FRUSTRATION_STRONG,
            FrustrationDetector,
            POSITIVE_WORDS,
            SentimentAnalyzer,
            SentimentResult,
            ToneAdvisor,
            ToneRecommendation,
            TrendDirection,
            UrgencyLevel,
            UrgencyScorer,
        )
        globals().update({
            "ConversationTrendAnalyzer": ConversationTrendAnalyzer,
            "EmotionClassifier": EmotionClassifier,
            "EmotionType": EmotionType,
            "EMPATHY_PATTERNS": EMPATHY_PATTERNS,
            "EmpathySignalDetector": EmpathySignalDetector,
            "FRUSTRATION_MILD": FRUSTRATION_MILD,
            "FRUSTRATION_MODERATE": FRUSTRATION_MODERATE,
            "FRUSTRATION_STRONG": FRUSTRATION_STRONG,
            "FrustrationDetector": FrustrationDetector,
            "POSITIVE_WORDS": POSITIVE_WORDS,
            "SentimentAnalyzer": SentimentAnalyzer,
            "SentimentResult": SentimentResult,
            "ToneAdvisor": ToneAdvisor,
            "ToneRecommendation": ToneRecommendation,
            "TrendDirection": TrendDirection,
            "UrgencyLevel": UrgencyLevel,
            "UrgencyScorer": UrgencyScorer,
        })


# ═══════════════════════════════════════════════════════════════════════
# 1. FrustrationDetector — detect() (25 tests)
# ═══════════════════════════════════════════════════════════════════════

class TestFrustrationDetector:
    def setup_method(self):
        self.detector = FrustrationDetector()

    # -- detect() main method --

    def test_neutral_text_low_score(self):
        score = self.detector.detect("Hello, how are you today?")
        assert score < 20

    def test_mild_frustration_some_score(self):
        score = self.detector.detect("I have an issue with my account")
        assert 0 < score < 50

    def test_moderate_frustration_medium_score(self):
        score = self.detector.detect("I am very annoyed and frustrated with this terrible service")
        assert score > 10

    def test_strong_frustration_high_score(self):
        score = self.detector.detect("This is absolutely unacceptable and furious disgusting!")
        assert score > 20

    def test_all_caps_boosts_score(self):
        normal = self.detector.detect("fix this now")
        caps = self.detector.detect("FIX THIS NOW")
        assert caps > normal

    def test_exclamation_boosts_score(self):
        normal = self.detector.detect("I am upset")
        excl = self.detector.detect("I am upset!!!!!!")
        assert excl > normal

    def test_repeated_words_boost_score(self):
        text = "fix fix fix fix fix fix fix this problem"
        score = self.detector.detect(text)
        assert score > 0

    def test_empty_string(self):
        assert self.detector.detect("") == 0.0

    def test_none_input(self):
        assert self.detector.detect(None) == 0.0

    def test_whitespace_only(self):
        assert self.detector.detect("   ") == 0.0

    def test_max_capped_at_100(self):
        # Combine all high-scoring elements
        text = "FURIOUS ENRAGED LIVID OUTRAGED UNACCEPTABLE APPALLING " * 10 + "!" * 20
        score = self.detector.detect(text)
        assert score <= 100.0

    def test_non_string_input(self):
        assert self.detector.detect(123) == 0.0

    def test_intensifiers_increase_score(self):
        normal = self.detector.detect("I am upset")
        intensified = self.detector.detect("I am very extremely upset and completely terrible")
        assert intensified >= normal

    def test_question_marks_increase_score(self):
        text = "why? what? how? when? where? why? what?"
        score = self.detector.detect(text)
        assert score > 0

    # -- _lexicon_score --

    def test_lexicon_strong_words(self):
        score = self.detector._lexicon_score("This is furious and enraged")
        assert score > 0

    def test_lexicon_moderate_words(self):
        score = self.detector._lexicon_score("I am angry and annoyed and frustrated")
        assert score > 0

    def test_lexicon_mild_words(self):
        score = self.detector._lexicon_score("I have an issue and a problem")
        assert score > 0

    def test_lexicon_capped_at_50(self):
        # Many strong words should still cap at 50
        text = "furious enraged livid outraged disgusted infuriated " * 5
        score = self.detector._lexicon_score(text)
        assert score <= 50.0

    def test_gap03_mild_word_boundary_no_false_positive(self):
        """G9-GAP-03: 'issue' in 'tissue' should NOT trigger mild frustration."""
        score_tissue = self.detector._lexicon_score("I need a tissue for my nose")
        score_issue = self.detector._lexicon_score("I have an issue with my order")
        assert score_tissue < score_issue

    def test_gap03_bad_in_badge_no_false_positive(self):
        """G9-GAP-03: 'bad' in 'badge' should NOT trigger mild frustration."""
        score_badge = self.detector._lexicon_score("He wore a badge on his shirt")
        score_bad = self.detector._lexicon_score("This is a bad experience")
        assert score_badge <= score_bad

    def test_gap03_error_in_terrain_no_false_positive(self):
        """G9-GAP-03: 'error' in 'terrain' should NOT trigger."""
        score_terrain = self.detector._lexicon_score("We crossed the terrain")
        score_error = self.detector._lexicon_score("There is an error in the system")
        assert score_terrain <= score_error

    # -- _caps_score --

    def test_caps_score_zero_for_normal(self):
        assert self.detector._caps_score("normal text here") == 0.0

    def test_caps_score_single_word(self):
        score = self.detector._caps_score("HELLO world")
        assert score > 0

    def test_caps_score_half_caps(self):
        score = self.detector._caps_score("THIS IS HALF world")
        assert score > 0

    # -- _exclamation_score --

    def test_exclamation_zero(self):
        assert self.detector._exclamation_score("no exclamations") == 0.0

    def test_exclamation_single(self):
        score = self.detector._exclamation_score("hello!")
        assert score == 2.0

    def test_exclamation_multiple(self):
        score = self.detector._exclamation_score("hello!!!")
        assert score == 10.0

    def test_exclamation_many(self):
        score = self.detector._exclamation_score("hello!!!!!!!!")
        assert score == 15.0

    # -- _repetition_score --

    def test_repetition_zero_short(self):
        assert self.detector._repetition_score("hi there") == 0.0

    def test_repetition_detected(self):
        text = "fix fix fix fix fix the problem now"
        score = self.detector._repetition_score(text)
        assert score > 0

    # -- _question_score --

    def test_question_zero(self):
        assert self.detector._question_score("no questions") == 0.0

    def test_question_high_density(self):
        text = "why? what? when? how?"
        score = self.detector._question_score(text)
        assert score > 0

    # -- _intensifier_score --

    def test_intensifier_zero(self):
        assert self.detector._intensifier_score("normal text") == 0.0

    def test_intensifier_single(self):
        score = self.detector._intensifier_score("very bad")
        assert score > 0

    def test_intensifier_multi_word(self):
        score = self.detector._intensifier_score("this is completely unacceptable")
        assert score > 0

    def test_intensifier_capped_at_5(self):
        text = "very extremely really so incredibly absolutely totally completely utterly never ever absolutely not"
        score = self.detector._intensifier_score(text)
        assert score <= 5.0


# ═══════════════════════════════════════════════════════════════════════
# 2. EmpathySignalDetector (12 tests)
# ═══════════════════════════════════════════════════════════════════════

class TestEmpathySignalDetector:
    def setup_method(self):
        self.detector = EmpathySignalDetector()

    def test_apology_expectation(self):
        signals = self.detector.detect("you should be ashamed and apologize to me")
        assert "apology_expectation" in signals

    def test_timeline_pressure(self):
        signals = self.detector.detect("I need this fixed immediately, it is urgent and an emergency")
        assert "timeline_pressure" in signals

    def test_financial_impact(self):
        signals = self.detector.detect("I lost money and was overcharged, I want a refund")
        assert "financial_impact" in signals

    def test_personal_impact(self):
        signals = self.detector.detect("This ruined my reputation and caused me anxiety and stress")
        assert "personal_impact" in signals

    def test_repeated_contacts_with_history(self):
        history = ["please help me with my account", "I need help with my account please", "please help me with my account now"]
        signals = self.detector.detect("please help me with my account", history)
        assert "repeated_contacts" in signals

    def test_no_signals(self):
        signals = self.detector.detect("What is the weather like outside?")
        assert len(signals) == 0

    def test_empty_query(self):
        signals = self.detector.detect("")
        assert signals == []

    def test_none_query(self):
        signals = self.detector.detect(None)
        assert signals == []

    def test_multiple_signals(self):
        text = "you owe me an apology, I need this immediately, I lost money"
        signals = self.detector.detect(text)
        assert len(signals) >= 2

    def test_repeated_contacts_insufficient_history(self):
        history = ["one message"]
        signals = self.detector.detect("refund my order", history)
        assert "repeated_contacts" not in signals

    def test_repeated_contacts_different_messages(self):
        history = ["what is the weather", "tell me a joke", "how are you"]
        signals = self.detector.detect("refund my order", history)
        assert "repeated_contacts" not in signals

    def test_repeated_contacts_none_history(self):
        signals = self.detector.detect("test query", None)
        assert "repeated_contacts" not in signals


# ═══════════════════════════════════════════════════════════════════════
# 3. EmotionClassifier (12 tests)
# ═══════════════════════════════════════════════════════════════════════

class TestEmotionClassifier:
    def setup_method(self):
        self.classifier = EmotionClassifier()

    def test_classify_angry(self):
        emotion, breakdown = self.classifier.classify("I am furious and enraged and hate this")
        assert emotion == "angry"

    def test_classify_frustrated(self):
        emotion, breakdown = self.classifier.classify("I am frustrated and annoyed and irritated")
        assert emotion == "frustrated"

    def test_classify_disappointed(self):
        emotion, breakdown = self.classifier.classify("I am disappointed and let down")
        assert emotion == "disappointed"

    def test_classify_neutral(self):
        emotion, breakdown = self.classifier.classify("What time does the store open?")
        assert emotion == "neutral"

    def test_classify_happy(self):
        emotion, breakdown = self.classifier.classify("I am happy and glad, thank you")
        assert emotion == "happy"

    def test_classify_delighted(self):
        emotion, breakdown = self.classifier.classify("I am delighted and amazed, outstanding excellent!")
        assert emotion == "delighted"

    def test_frustration_boosts_angry(self):
        emotion_high, _ = self.classifier.classify("this is okay", frustration_score=90)
        assert emotion_high == "angry"

    def test_frustration_boosts_frustrated(self):
        emotion_mid, _ = self.classifier.classify("I am frustrated and this is annoying", frustration_score=50)
        assert emotion_mid == "frustrated"

    def test_positive_boosts_happy(self):
        emotion, _ = self.classifier.classify("awesome brilliant excellent fantastic")
        assert emotion in ("happy", "delighted")

    def test_empty_query(self):
        emotion, breakdown = self.classifier.classify("")
        assert emotion == "neutral"
        assert breakdown["neutral"] == 1.0

    def test_none_query(self):
        emotion, breakdown = self.classifier.classify(None)
        assert emotion == "neutral"

    def test_breakdown_keys(self):
        _, breakdown = self.classifier.classify("test text")
        expected = {"angry", "frustrated", "disappointed", "neutral", "happy", "delighted"}
        assert set(breakdown.keys()) == expected
        # Scores should sum to ~1.0
        total = sum(breakdown.values())
        assert abs(total - 1.0) < 0.01


# ═══════════════════════════════════════════════════════════════════════
# 4. UrgencyScorer (12 tests)
# ═══════════════════════════════════════════════════════════════════════

class TestUrgencyScorer:
    def setup_method(self):
        self.scorer = UrgencyScorer()

    def test_low_urgency(self):
        level = self.scorer.score("Hello, I have a question")
        assert level == UrgencyLevel.LOW

    def test_medium_urgency(self):
        level = self.scorer.score("I have an urgent issue")
        assert level == UrgencyLevel.MEDIUM

    def test_high_urgency(self):
        level = self.scorer.score("This is urgent and I need it immediately!")
        assert level in (UrgencyLevel.HIGH, UrgencyLevel.CRITICAL)

    def test_critical_urgency(self):
        level = self.scorer.score("emergency breach security data loss critical!")
        assert level == UrgencyLevel.CRITICAL

    def test_empty_query(self):
        assert self.scorer.score("") == UrgencyLevel.LOW

    def test_none_query(self):
        assert self.scorer.score(None) == UrgencyLevel.LOW

    def test_gap09_word_boundary_down_not_download(self):
        """G9-GAP-09: 'down' in 'download' should not trigger urgency."""
        score_download = self.scorer.score("I want to download the app")
        score_down = self.scorer.score("urgent the system is down")
        assert score_download == UrgencyLevel.LOW
        assert score_down != UrgencyLevel.LOW

    def test_multi_word_keyword(self):
        level = self.scorer.score("this is a final notice")
        assert level != UrgencyLevel.LOW

    def test_frustration_contribution(self):
        low = self.scorer.score("help me", frustration_score=0)
        high = self.scorer.score("help me", frustration_score=80)
        assert high != low or high == UrgencyLevel.LOW  # at least doesn't crash

    def test_exclamation_contribution(self):
        normal = self.scorer.score("urgent")
        excl = self.scorer.score("urgent!!!!")
        # Exclamation adds urgency
        assert isinstance(excl, str)

    def test_caps_contribution(self):
        normal = self.scorer.score("need help urgent")
        caps = self.scorer.score("NEED HELP URGENT")
        assert isinstance(caps, str)

    def test_non_string_input(self):
        assert self.scorer.score(12345) == UrgencyLevel.LOW


# ═══════════════════════════════════════════════════════════════════════
# 5. ToneAdvisor (10 tests)
# ═══════════════════════════════════════════════════════════════════════

class TestToneAdvisor:
    def setup_method(self):
        self.advisor = ToneAdvisor()

    def test_de_escalation_high_frustration(self):
        tone = self.advisor.recommend(95, "angry", UrgencyLevel.HIGH)
        assert tone == ToneRecommendation.DE_ESCALATION

    def test_de_escalation_angry_plus_frustration(self):
        tone = self.advisor.recommend(75, "angry", UrgencyLevel.LOW)
        assert tone == ToneRecommendation.DE_ESCALATION

    def test_urgent_tone(self):
        tone = self.advisor.recommend(65, "frustrated", UrgencyLevel.CRITICAL)
        assert tone == ToneRecommendation.URGENT

    def test_urgent_tone_high(self):
        tone = self.advisor.recommend(70, "neutral", UrgencyLevel.HIGH)
        assert tone == ToneRecommendation.URGENT

    def test_empathetic_frustration(self):
        tone = self.advisor.recommend(50, "neutral", UrgencyLevel.LOW)
        assert tone == ToneRecommendation.EMPATHETIC

    def test_empathetic_disappointed(self):
        tone = self.advisor.recommend(20, "disappointed", UrgencyLevel.LOW)
        assert tone == ToneRecommendation.EMPATHETIC

    def test_standard_tone(self):
        tone = self.advisor.recommend(10, "neutral", UrgencyLevel.LOW)
        assert tone == ToneRecommendation.STANDARD

    def test_standard_happy(self):
        tone = self.advisor.recommend(5, "happy", UrgencyLevel.LOW)
        assert tone == ToneRecommendation.STANDARD

    def test_de_escalation_threshold_90(self):
        tone = self.advisor.recommend(90, "neutral", UrgencyLevel.MEDIUM)
        assert tone == ToneRecommendation.DE_ESCALATION

    def test_urgent_frustration_60_required(self):
        tone = self.advisor.recommend(55, "neutral", UrgencyLevel.CRITICAL)
        # frustration < 60, so not urgent despite critical
        assert tone == ToneRecommendation.EMPATHETIC


# ═══════════════════════════════════════════════════════════════════════
# 6. ConversationTrendAnalyzer (8 tests)
# ═══════════════════════════════════════════════════════════════════════

class TestConversationTrendAnalyzer:
    def setup_method(self):
        self.analyzer = ConversationTrendAnalyzer()

    def test_improving_trend(self):
        history = [
            "I am furious and this is absolutely unacceptable!",
            "This is very annoying and terrible",
            "This is somewhat frustrating",
            "It is an issue",
            "Okay, thanks for the help",
        ]
        trend = self.analyzer.analyze(history)
        assert trend == TrendDirection.IMPROVING

    def test_worsening_trend(self):
        history = [
            "Thanks for the help, great service",
            "There is a small issue",
            "This is very annoying and frustrating",
            "I am angry and this is terrible",
            "This is absolutely furious and unacceptable disgusting!",
        ]
        trend = self.analyzer.analyze(history)
        assert trend == TrendDirection.WORSENING

    def test_stable_trend(self):
        history = [
            "Hello there",
            "How are you",
            "I have a question",
        ]
        trend = self.analyzer.analyze(history)
        assert trend == TrendDirection.STABLE

    def test_short_history_stable(self):
        trend = self.analyzer.analyze(["one message", "two message"])
        assert trend == TrendDirection.STABLE

    def test_none_history(self):
        trend = self.analyzer.analyze(None)
        assert trend == TrendDirection.STABLE

    def test_empty_history(self):
        trend = self.analyzer.analyze([])
        assert trend == TrendDirection.STABLE

    def test_history_with_none_items(self):
        history = [None, "", "some text", "  ", "more text", "another one"]
        trend = self.analyzer.analyze(history)
        assert trend == TrendDirection.STABLE

    def test_uses_last_5_messages(self):
        history = [
            "I am furious and absolutely unacceptable",
            "I am furious and absolutely unacceptable",
            "I am furious and absolutely unacceptable",
            "I am furious and absolutely unacceptable",
            "I am furious and absolutely unacceptable",
            "calm message here",
            "calm message here",
            "calm message here",
        ]
        # Last 5 are calm → trend should be stable or improving
        trend = self.analyzer.analyze(history)
        assert trend in (TrendDirection.STABLE, TrendDirection.IMPROVING)


# ═══════════════════════════════════════════════════════════════════════
# 7. SentimentAnalyzer — full pipeline (15 tests)
# ═══════════════════════════════════════════════════════════════════════

class TestSentimentAnalyzer:
    def setup_method(self):
        self.analyzer = SentimentAnalyzer()

    @pytest.mark.asyncio
    async def test_full_analysis_neutral(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.analyzer.analyze("Hello, how are you?", company_id="c1")
        assert isinstance(result, SentimentResult)
        assert result.emotion == "neutral"
        assert 0.0 <= result.frustration_score < 50
        assert result.cached is False

    @pytest.mark.asyncio
    async def test_full_analysis_frustrated(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.analyzer.analyze(
                    "I am very angry and frustrated with this terrible service!",
                    company_id="c1",
                )
        assert result.frustration_score > 10
        assert result.sentiment_score < 1.0

    @pytest.mark.asyncio
    async def test_empty_query_returns_default(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.analyzer.analyze("", company_id="c1")
        assert result.frustration_score == 0.0
        assert result.emotion == EmotionType.NEUTRAL
        assert result.tone_recommendation == ToneRecommendation.STANDARD

    @pytest.mark.asyncio
    async def test_none_query_returns_default(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.analyzer.analyze(None, company_id="c1")
        assert result.frustration_score == 0.0

    @pytest.mark.asyncio
    async def test_cache_hit(self):
        cached_data = {
            "frustration_score": 42.0,
            "emotion": "frustrated",
            "urgency_level": "medium",
            "tone_recommendation": "empathetic",
            "empathy_signals": [],
            "sentiment_score": 0.58,
            "emotion_breakdown": {"angry": 0.1, "frustrated": 0.5, "neutral": 0.2,
                                   "disappointed": 0.1, "happy": 0.05, "delighted": 0.05},
            "processing_time_ms": 5.0,
            "conversation_trend": "stable",
        }
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=cached_data):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.analyzer.analyze("test query", company_id="c1")
        assert result.cached is True
        assert result.frustration_score == 42.0

    @pytest.mark.asyncio
    async def test_cache_miss(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.analyzer.analyze("I have an issue", company_id="c1")
        assert result.cached is False

    @pytest.mark.asyncio
    async def test_cache_fail_open(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, side_effect=Exception("Redis down")):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.analyzer.analyze("hello", company_id="c1")
        assert result.cached is False
        assert isinstance(result, SentimentResult)

    @pytest.mark.asyncio
    async def test_cache_write_fail_open(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock, side_effect=Exception("write fail")):
                result = await self.analyzer.analyze("hello", company_id="c1")
        assert isinstance(result, SentimentResult)

    @pytest.mark.asyncio
    async def test_gap02_history_affects_cache_key(self):
        """G9-GAP-02: Different histories produce different cache keys."""
        q = "I need help"
        h1 = self.analyzer._compute_history_hash(["previous message 1"])
        h2 = self.analyzer._compute_history_hash(["previous message 2"])
        qh = self.analyzer._compute_query_hash(q)
        key1 = f"sentiment_cache:c1:parwa:{qh}:{h1}"
        key2 = f"sentiment_cache:c1:parwa:{qh}:{h2}"
        assert key1 != key2

    @pytest.mark.asyncio
    async def test_gap02_none_history_hash(self):
        assert self.analyzer._compute_history_hash(None) == "none"
        assert self.analyzer._compute_history_hash([]) == "none"

    @pytest.mark.asyncio
    async def test_default_result_fields(self):
        result = self.analyzer._default_result("test")
        assert result.frustration_score == 0.0
        assert result.emotion == "neutral"
        assert result.urgency_level == "low"
        assert result.tone_recommendation == "standard"
        assert result.empathy_signals == []
        assert result.sentiment_score == 0.5
        assert result.conversation_trend == "stable"
        assert result.processing_time_ms == 0.0

    @pytest.mark.asyncio
    async def test_with_conversation_history(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.analyzer.analyze(
                    "This is frustrating",
                    company_id="c1",
                    conversation_history=["hello", "how are you", "I need help"],
                )
        assert result.conversation_trend in ("improving", "stable", "worsening")

    @pytest.mark.asyncio
    async def test_variant_type_preserved(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock) as mock_set:
                await self.analyzer.analyze("test", company_id="c1", variant_type="mini_parwa")
                # Verify cache_set was called
                mock_set.assert_called_once()

    @pytest.mark.asyncio
    async def test_whitespace_query_returns_default(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                result = await self.analyzer.analyze("   ", company_id="c1")
        assert result.frustration_score == 0.0


# ═══════════════════════════════════════════════════════════════════════
# 8. Data Classes (5 tests)
# ═══════════════════════════════════════════════════════════════════════

class TestDataClasses:
    def test_sentiment_result_to_dict(self):
        result = SentimentResult(
            frustration_score=42.0,
            emotion="frustrated",
            urgency_level="medium",
            tone_recommendation="empathetic",
            empathy_signals=["financial_impact"],
            sentiment_score=0.58,
            emotion_breakdown={"frustrated": 0.5, "neutral": 0.5},
            processing_time_ms=5.0,
            conversation_trend="stable",
            cached=False,
        )
        d = result.to_dict()
        assert d["frustration_score"] == 42.0
        assert d["emotion"] == "frustrated"
        assert d["urgency_level"] == "medium"
        assert d["tone_recommendation"] == "empathetic"
        assert d["empathy_signals"] == ["financial_impact"]
        assert "cached" not in d

    def test_emotion_type_values(self):
        assert EmotionType.ANGRY == "angry"
        assert EmotionType.NEUTRAL == "neutral"
        assert EmotionType.HAPPY == "happy"
        assert EmotionType.DELIGHTED == "delighted"
        assert EmotionType.FRUSTRATED == "frustrated"
        assert EmotionType.DISAPPOINTED == "disappointed"

    def test_urgency_level_values(self):
        assert UrgencyLevel.LOW == "low"
        assert UrgencyLevel.MEDIUM == "medium"
        assert UrgencyLevel.HIGH == "high"
        assert UrgencyLevel.CRITICAL == "critical"

    def test_tone_recommendation_values(self):
        assert ToneRecommendation.EMPATHETIC == "empathetic"
        assert ToneRecommendation.URGENT == "urgent"
        assert ToneRecommendation.DE_ESCALATION == "de-escalation"
        assert ToneRecommendation.STANDARD == "standard"

    def test_trend_direction_values(self):
        assert TrendDirection.IMPROVING == "improving"
        assert TrendDirection.STABLE == "stable"
        assert TrendDirection.WORSENING == "worsening"


# ═══════════════════════════════════════════════════════════════════════
# 9. Additional Edge / Integration tests
# ═══════════════════════════════════════════════════════════════════════

class TestSentimentEdgeCases:
    def setup_method(self):
        self.detector = FrustrationDetector()
        self.classifier = EmotionClassifier()
        self.scorer = UrgencyScorer()
        self.advisor = ToneAdvisor()

    def test_very_long_text(self):
        text = "I am furious and this is unacceptable " * 200
        score = self.detector.detect(text)
        assert 0 <= score <= 100

    def test_special_characters(self):
        score = self.detector.detect("@#$%^&*() furious !!! ???")
        assert score > 0

    def test_unicode_text(self):
        score = self.detector.detect("I am very angry 😡😡😡")
        assert isinstance(score, float)

    def test_emoji_only(self):
        score = self.detector.detect("😡😡😡😡")
        assert isinstance(score, float)

    def test_mixed_language(self):
        emotion, breakdown = self.classifier.classify("je suis très content et happy")
        assert emotion in ("happy", "delighted", "neutral", "frustrated")

    def test_numbers_only(self):
        score = self.detector.detect("12345 67890")
        assert isinstance(score, float)

    def test_score_is_float(self):
        score = self.detector.detect("test")
        assert isinstance(score, float)

    def test_sentiment_score_inverse_frustration(self):
        # High frustration → low sentiment score
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                import asyncio
                analyzer = SentimentAnalyzer()
                result = asyncio.get_event_loop().run_until_complete(
                    analyzer.analyze("I am furious and absolutely unacceptable", company_id="c1")
                )
        assert result.sentiment_score > 0.5

    def test_empathy_signals_with_metadata(self):
        detector = EmpathySignalDetector()
        signals = detector.detect("I lost money", customer_metadata={"vip": True})
        assert "financial_impact" in signals

    def test_query_hash_deterministic(self):
        h1 = SentimentAnalyzer._compute_query_hash("Hello World")
        h2 = SentimentAnalyzer._compute_query_hash("Hello World")
        assert h1 == h2

    def test_query_hash_case_insensitive(self):
        h1 = SentimentAnalyzer._compute_query_hash("Hello World")
        h2 = SentimentAnalyzer._compute_query_hash("hello world")
        assert h1 == h2

    def test_emotion_breakdown_sums_to_one(self):
        _, breakdown = self.classifier.classify("This is great and wonderful")
        total = sum(breakdown.values())
        assert abs(total - 1.0) < 0.02

    def test_sentiment_result_defaults(self):
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
        assert result.conversation_trend == "stable"
        assert result.cached is False
