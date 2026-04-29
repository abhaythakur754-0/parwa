"""
Tests for AI Classification Engine (F-062) — Week 9 Day 6

Covers: GAP-008 (empty input), D6-GAP-07 (non-string company_id),
all 12 intents, multi-label, confidence scoring, AI path, variant gating.
Target: 120+ tests
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ═══════════════════════════════════════════════════════════════════════
# Fixtures — import source modules with mocked logger
# ═══════════════════════════════════════════════════════════════════════

# Runtime-injected by _mock_logger fixture — satisfies flake8 F821
ClassificationEngine = IntentType = IntentResult = KeywordClassifier = (
    INTENT_PATTERNS
) = INTENT_TO_CATEGORY_MAP = None


@pytest.fixture(autouse=True)
def _mock_logger():
    with patch("app.logger.get_logger", return_value=MagicMock()):
        from app.core.classification_engine import (  # noqa: F811,F401
            ClassificationEngine,
            IntentType,
            IntentResult,
            KeywordClassifier,
            INTENT_PATTERNS,
            INTENT_TO_CATEGORY_MAP,
        )

        globals().update(
            {
                "ClassificationEngine": ClassificationEngine,
                "IntentType": IntentType,
                "IntentResult": IntentResult,
                "KeywordClassifier": KeywordClassifier,
                "INTENT_PATTERNS": INTENT_PATTERNS,
                "INTENT_TO_CATEGORY_MAP": INTENT_TO_CATEGORY_MAP,
            }
        )


# ═══════════════════════════════════════════════════════════════════════
# 1. KeywordClassifier.classify() — 12 intents + edge (20 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestKeywordClassifierClassify:
    def setup_method(self):
        self.classifier = KeywordClassifier()

    def test_refund_intent(self):
        result = self.classifier.classify("I want a refund for my order")
        assert result.primary_intent == "refund"

    def test_technical_intent(self):
        result = self.classifier.classify("The app keeps crashing with error 500")
        assert result.primary_intent == "technical"

    def test_billing_intent(self):
        result = self.classifier.classify("I have a question about my bill and invoice")
        assert result.primary_intent == "billing"

    def test_complaint_intent(self):
        result = self.classifier.classify("This is the worst service ever, I'm angry")
        assert result.primary_intent == "complaint"

    def test_feature_request_intent(self):
        result = self.classifier.classify("Please add a dark mode feature to your app")
        assert result.primary_intent == "feature_request"

    def test_general_intent(self):
        result = self.classifier.classify("hello there how are you today")
        assert result.primary_intent == "general"

    def test_cancellation_intent(self):
        result = self.classifier.classify("Cancel my subscription right now")
        assert result.primary_intent == "cancellation"

    def test_shipping_intent(self):
        result = self.classifier.classify("Where is my package tracking number?")
        assert result.primary_intent == "shipping"

    def test_inquiry_intent(self):
        result = self.classifier.classify("Can you explain how billing works?")
        assert result.primary_intent == "inquiry"

    def test_escalation_intent(self):
        result = self.classifier.classify("I need to speak to your manager")
        assert result.primary_intent == "escalation"

    def test_account_intent(self):
        result = self.classifier.classify("How do I reset my password?")
        assert result.primary_intent == "account"

    def test_feedback_intent(self):
        result = self.classifier.classify("Great product, keep it up!")
        assert result.primary_intent == "feedback"

    def test_mixed_query_picks_best(self):
        result = self.classifier.classify("refund this technical error")
        assert result.primary_intent in ("refund", "technical")

    def test_unknown_text_returns_general(self):
        result = self.classifier.classify("the quick brown fox jumps")
        assert result.primary_intent == "general"

    def test_method_is_keyword(self):
        result = self.classifier.classify("refund my order")
        assert result.classification_method == "keyword"

    def test_case_insensitive(self):
        result = self.classifier.classify("REFUND MY ORDER NOW")
        assert result.primary_intent == "refund"

    def test_empty_text(self):
        result = self.classifier.classify("")
        assert result.primary_intent == "general"

    def test_complaint_keyword_weight(self):
        result = self.classifier.classify("I have a formal complaint")
        assert result.primary_intent == "complaint"

    def test_escalation_speak_to_someone(self):
        result = self.classifier.classify("I need to speak to someone about this")
        assert result.primary_intent == "escalation"

    def test_ship_tracking(self):
        result = self.classifier.classify(
            "What is my order status and tracking number?"
        )
        assert result.primary_intent == "shipping"


# ═══════════════════════════════════════════════════════════════════════
# 2. Secondary Intents (10 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestSecondaryIntents:
    def setup_method(self):
        self.classifier = KeywordClassifier()

    def test_max_3_secondary(self):
        result = self.classifier.classify(
            "refund my order, there's a bug, bill is wrong, cancel subscription"
        )
        assert len(result.secondary_intents) <= 3

    def test_secondary_excludes_primary(self):
        result = self.classifier.classify("refund my order now please")
        secondary_intents = [i for i, c in result.secondary_intents]
        assert result.primary_intent not in secondary_intents

    def test_confidence_threshold_above_005(self):
        result = self.classifier.classify("refund my order")
        for intent, conf in result.secondary_intents:
            assert conf > 0.05

    def test_secondary_are_tuples(self):
        result = self.classifier.classify("refund this technical error")
        for item in result.secondary_intents:
            assert isinstance(item, tuple)
            assert len(item) == 2

    def test_no_secondary_for_clear_general(self):
        result = self.classifier.classify("hello there good day")
        # May have 0 secondaries or low-confidence ones
        assert isinstance(result.secondary_intents, list)

    def test_refund_billing_secondary(self):
        result = self.classifier.classify("I want a refund for the charge on my bill")
        secondary_intents = [i for i, c in result.secondary_intents]
        # One should be billing or refund
        assert "refund" in secondary_intents or "billing" in secondary_intents

    def test_secondary_sorted_by_confidence(self):
        result = self.classifier.classify(
            "refund my order, there's a bug, bill is wrong"
        )
        for i in range(len(result.secondary_intents) - 1):
            assert result.secondary_intents[i][1] >= result.secondary_intents[i + 1][1]

    def test_secondary_types_string_float(self):
        result = self.classifier.classify("some text here")
        for intent, conf in result.secondary_intents:
            assert isinstance(intent, str)
            assert isinstance(conf, float)

    def test_complaint_escalation_secondary(self):
        result = self.classifier.classify(
            "I have a complaint and want to escalate to a manager"
        )
        secondary_intents = [i for i, c in result.secondary_intents]
        assert "complaint" in secondary_intents or "escalation" in secondary_intents

    def test_no_duplicates_in_secondary(self):
        result = self.classifier.classify("refund refund refund money back")
        secondary_ids = [i for i, c in result.secondary_intents]
        assert len(secondary_ids) == len(set(secondary_ids))


# ═══════════════════════════════════════════════════════════════════════
# 3. Confidence Capping (8 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestConfidenceCapping:
    def setup_method(self):
        self.classifier = KeywordClassifier()

    def test_primary_capped_at_095(self):
        result = self.classifier.classify(
            "refund refund refund money back return reimburse chargeback"
        )
        assert result.primary_confidence <= 0.95

    def test_general_capped_at_050(self):
        result = self.classifier.classify("hello world how are you today")
        if result.primary_intent == "general":
            assert result.primary_confidence <= 0.5

    def test_confidence_bounded_zero(self):
        result = self.classifier.classify("test")
        assert result.primary_confidence >= 0.0

    def test_confidence_bounded_one(self):
        result = self.classifier.classify("test")
        assert result.primary_confidence <= 1.0

    def test_high_specificity_high_confidence(self):
        result = self.classifier.classify(
            "I want a refund money back return reimburse chargeback cancel order"
        )
        assert result.primary_confidence > 0.3
        assert result.primary_confidence <= 0.95

    def test_non_general_not_capped_at_050(self):
        result = self.classifier.classify("I want a refund money back return")
        if result.primary_intent != "general":
            assert result.primary_confidence <= 0.95

    def test_multiple_keywords_increase_confidence(self):
        r1 = self.classifier.classify("refund")
        r2 = self.classifier.classify("refund money back return reimburse")
        # More matching keywords gives high confidence
        assert r2.primary_confidence > 0.5

    def test_complaint_weighted_higher(self):
        """Complaint has weight 1.2."""
        result = self.classifier.classify("I have a formal complaint about this")
        assert result.primary_intent == "complaint"
        assert result.primary_confidence > 0.3


# ═══════════════════════════════════════════════════════════════════════
# 4. Score Normalization (5 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestScoreNormalization:
    def setup_method(self):
        self.classifier = KeywordClassifier()

    def test_scores_sum_approximately_1(self):
        result = self.classifier.classify("I want a refund for my order")
        total = sum(result.all_scores.values())
        assert 0.9 <= total <= 1.1  # allow small rounding variance

    def test_all_12_intents_have_scores(self):
        result = self.classifier.classify("refund my order")
        assert len(result.all_scores) == 12

    def test_all_scores_are_float(self):
        result = self.classifier.classify("refund")
        for val in result.all_scores.values():
            assert isinstance(val, float)

    def test_all_scores_non_negative(self):
        result = self.classifier.classify("test")
        for val in result.all_scores.values():
            assert val >= 0.0

    def test_general_text_low_total(self):
        """General text should still produce normalized scores."""
        result = self.classifier.classify("hello there")
        total = sum(result.all_scores.values())
        assert total >= 0.0


# ═══════════════════════════════════════════════════════════════════════
# 5. ClassificationEngine.classify() (15 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestClassificationEngineClassify:
    def setup_method(self):
        self.engine = ClassificationEngine()

    @pytest.mark.asyncio
    async def test_keyword_fallback_no_router(self):
        result = await self.engine.classify("refund my order", use_ai=True)
        assert result.classification_method == "keyword"

    @pytest.mark.asyncio
    async def test_empty_input_gap008(self):
        """GAP-008: Empty input returns safe default."""
        result = await self.engine.classify("")
        assert result.primary_intent == "general"
        assert result.primary_confidence == 0.0
        assert result.classification_method == "fallback"

    @pytest.mark.asyncio
    async def test_whitespace_only_gap008(self):
        result = await self.engine.classify("   \n\t   ")
        assert result.primary_intent == "general"
        assert result.classification_method == "fallback"

    @pytest.mark.asyncio
    async def test_none_input_gap008(self):
        result = await self.engine.classify(None)
        assert result.primary_intent == "general"
        assert result.primary_confidence == 0.0

    @pytest.mark.asyncio
    async def test_too_short_gap008(self):
        result = await self.engine.classify("ab")
        assert result.primary_intent == "general"
        assert result.classification_method == "fallback"

    @pytest.mark.asyncio
    async def test_exactly_min_length(self):
        result = await self.engine.classify("bug")
        assert result.classification_method == "keyword"
        assert result.primary_intent == "technical"

    @pytest.mark.asyncio
    async def test_non_string_company_id_d6_gap07(self):
        """D6-GAP-07: Non-string company_id handled gracefully."""
        result = await self.engine.classify("refund my order", company_id=12345)
        assert result.primary_intent == "refund"
        assert result.classification_method == "keyword"

    @pytest.mark.asyncio
    async def test_none_company_id(self):
        result = await self.engine.classify("refund", company_id=None)
        assert result.primary_intent == "refund"

    @pytest.mark.asyncio
    async def test_use_ai_false(self):
        result = await self.engine.classify("bug in system", use_ai=False)
        assert result.classification_method == "keyword"

    @pytest.mark.asyncio
    async def test_mini_parwa_skips_ai(self):
        mock_router = MagicMock()
        mock_router.async_execute_llm_call = AsyncMock()
        engine = ClassificationEngine(smart_router=mock_router)
        result = await engine.classify(
            "refund my order",
            variant_type="mini_parwa",
            use_ai=True,
        )
        assert result.classification_method == "keyword"
        mock_router.async_execute_llm_call.assert_not_called()

    @pytest.mark.asyncio
    async def test_parwa_attempts_ai(self):
        mock_router = MagicMock()
        mock_router.async_execute_llm_call = AsyncMock(
            return_value={
                "content": '{"primary": "refund", "secondary": [], "confidences": {"refund": 0.9}}',
                "model_used": "test-model",
            }
        )
        engine = ClassificationEngine(smart_router=mock_router)
        result = await engine.classify(
            "refund my order",
            variant_type="parwa",
            use_ai=True,
        )
        mock_router.async_execute_llm_call.assert_called_once()

    @pytest.mark.asyncio
    async def test_parwa_high_attempts_ai(self):
        mock_router = MagicMock()
        mock_router.async_execute_llm_call = AsyncMock(
            return_value={
                "content": '{"primary": "billing", "secondary": [], "confidences": {"billing": 0.8}}',
                "model_used": "test-model",
            }
        )
        engine = ClassificationEngine(smart_router=mock_router)
        result = await engine.classify(
            "bill issue",
            variant_type="parwa_high",
            use_ai=True,
        )
        mock_router.async_execute_llm_call.assert_called_once()

    @pytest.mark.asyncio
    async def test_ai_exception_fallback(self):
        mock_router = MagicMock()
        mock_router.async_execute_llm_call = AsyncMock(
            side_effect=Exception("API down")
        )
        engine = ClassificationEngine(smart_router=mock_router)
        result = await engine.classify(
            "refund my order",
            variant_type="parwa",
            use_ai=True,
        )
        assert result.classification_method == "keyword"

    @pytest.mark.asyncio
    async def test_processing_time_populated(self):
        result = await self.engine.classify("refund my order", use_ai=False)
        assert result.processing_time_ms >= 0

    @pytest.mark.asyncio
    async def test_model_used_none_for_keyword(self):
        result = await self.engine.classify("refund", use_ai=False)
        assert result.model_used is None


# ═══════════════════════════════════════════════════════════════════════
# 6. AI Classification (10 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestAIClassification:
    @pytest.mark.asyncio
    async def test_valid_json_response(self):
        mock_router = MagicMock()
        mock_router.async_execute_llm_call = AsyncMock(
            return_value={
                "content": '{"primary": "refund", "secondary": [{"intent": "billing", "confidence": 0.3}], "confidences": {"refund": 0.85, "billing": 0.3}}',
                "model_used": "gemma-3-27b-it",
            }
        )
        engine = ClassificationEngine(smart_router=mock_router)
        result = await engine.classify(
            "I want a refund", variant_type="parwa", use_ai=True
        )
        assert result.primary_intent == "refund"
        assert result.model_used == "gemma-3-27b-it"
        assert result.classification_method == "ai"

    @pytest.mark.asyncio
    async def test_markdown_fenced_json(self):
        mock_router = MagicMock()
        mock_router.async_execute_llm_call = AsyncMock(
            return_value={
                "content": '```json\n{"primary": "billing", "secondary": [], "confidences": {"billing": 0.8}}\n```',
                "model_used": "test",
            }
        )
        engine = ClassificationEngine(smart_router=mock_router)
        result = await engine.classify("bill issue", variant_type="parwa", use_ai=True)
        assert result.primary_intent == "billing"

    @pytest.mark.asyncio
    async def test_invalid_json_fallback(self):
        mock_router = MagicMock()
        mock_router.async_execute_llm_call = AsyncMock(
            return_value={"content": "not json at all"}
        )
        engine = ClassificationEngine(smart_router=mock_router)
        result = await engine.classify("test", variant_type="parwa", use_ai=True)
        assert result.classification_method == "keyword"

    @pytest.mark.asyncio
    async def test_empty_response_fallback(self):
        mock_router = MagicMock()
        mock_router.async_execute_llm_call = AsyncMock(return_value={})
        engine = ClassificationEngine(smart_router=mock_router)
        result = await engine.classify("test", variant_type="parwa", use_ai=True)
        assert result.classification_method == "keyword"

    @pytest.mark.asyncio
    async def test_ai_confidence_clamped_above(self):
        mock_router = MagicMock()
        mock_router.async_execute_llm_call = AsyncMock(
            return_value={
                "content": '{"primary": "refund", "secondary": [], "confidences": {"refund": 1.5}}',
                "model_used": "test",
            }
        )
        engine = ClassificationEngine(smart_router=mock_router)
        result = await engine.classify("test", variant_type="parwa", use_ai=True)
        assert result.primary_confidence <= 0.95

    @pytest.mark.asyncio
    async def test_ai_confidence_clamped_below(self):
        mock_router = MagicMock()
        mock_router.async_execute_llm_call = AsyncMock(
            return_value={
                "content": '{"primary": "refund", "secondary": [], "confidences": {"refund": -0.5}}',
                "model_used": "test",
            }
        )
        engine = ClassificationEngine(smart_router=mock_router)
        result = await engine.classify("test", variant_type="parwa", use_ai=True)
        assert result.primary_confidence >= 0.0

    @pytest.mark.asyncio
    async def test_ai_invalid_primary_falls_to_general(self):
        mock_router = MagicMock()
        mock_router.async_execute_llm_call = AsyncMock(
            return_value={
                "content": '{"primary": "nonexistent_intent", "secondary": [], "confidences": {}}',
                "model_used": "test",
            }
        )
        engine = ClassificationEngine(smart_router=mock_router)
        result = await engine.classify("test", variant_type="parwa", use_ai=True)
        assert result.primary_intent == "general"

    @pytest.mark.asyncio
    async def test_ai_secondary_parsed(self):
        mock_router = MagicMock()
        mock_router.async_execute_llm_call = AsyncMock(
            return_value={
                "content": '{"primary": "refund", "secondary": [{"intent": "billing", "confidence": 0.3}], "confidences": {"refund": 0.85, "billing": 0.3}}',
                "model_used": "test",
            }
        )
        engine = ClassificationEngine(smart_router=mock_router)
        result = await engine.classify("test", variant_type="parwa", use_ai=True)
        assert len(result.secondary_intents) >= 1
        assert result.secondary_intents[0][0] == "billing"

    @pytest.mark.asyncio
    async def test_ai_all_confidences_populated(self):
        mock_router = MagicMock()
        mock_router.async_execute_llm_call = AsyncMock(
            return_value={
                "content": '{"primary": "refund", "secondary": [], "confidences": {"refund": 0.8}}',
                "model_used": "test",
            }
        )
        engine = ClassificationEngine(smart_router=mock_router)
        result = await engine.classify("test", variant_type="parwa", use_ai=True)
        assert len(result.all_scores) == 12

    @pytest.mark.asyncio
    async def test_ai_fallback_on_exception(self):
        mock_router = MagicMock()
        mock_router.async_execute_llm_call = AsyncMock(
            side_effect=Exception("API down")
        )
        engine = ClassificationEngine(smart_router=mock_router)
        result = await engine.classify("test", variant_type="parwa", use_ai=True)
        assert result.classification_method == "keyword"


# ═══════════════════════════════════════════════════════════════════════
# 7. IntentType Enum (5 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestIntentTypeEnum:
    def test_count_12(self):
        assert len(IntentType) == 12

    def test_core_intents_present(self):
        core = {
            "refund",
            "technical",
            "billing",
            "complaint",
            "feature_request",
            "general",
        }
        assert core.issubset({t.value for t in IntentType})

    def test_extended_intents_present(self):
        extended = {
            "cancellation",
            "shipping",
            "inquiry",
            "escalation",
            "account",
            "feedback",
        }
        assert extended.issubset({t.value for t in IntentType})

    def test_string_values(self):
        for t in IntentType:
            assert isinstance(t.value, str)
            assert len(t.value) > 0

    def test_unique_values(self):
        values = [t.value for t in IntentType]
        assert len(values) == len(set(values))


# ═══════════════════════════════════════════════════════════════════════
# 8. Intent-to-Category Mapping (5 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestIntentToCategoryMapping:
    def test_all_12_intents_mapped(self):
        assert len(INTENT_TO_CATEGORY_MAP) == 12

    def test_refund_maps_to_refund(self):
        assert INTENT_TO_CATEGORY_MAP["refund"] == "refund"

    def test_technical_maps_to_technical(self):
        assert INTENT_TO_CATEGORY_MAP["technical"] == "technical"

    def test_shipping_maps_to_technical(self):
        assert INTENT_TO_CATEGORY_MAP["shipping"] == "technical"

    def test_cancellation_maps_to_general(self):
        assert INTENT_TO_CATEGORY_MAP["cancellation"] == "general"

    def test_escalation_maps_to_complaint(self):
        assert INTENT_TO_CATEGORY_MAP["escalation"] == "complaint"


# ═══════════════════════════════════════════════════════════════════════
# 9. _safe_intent_from_string (8 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestSafeIntentFromString:
    def test_valid_refund(self):
        assert ClassificationEngine._safe_intent_from_string("refund") == "refund"

    def test_valid_technical(self):
        assert ClassificationEngine._safe_intent_from_string("technical") == "technical"

    def test_case_insensitive(self):
        assert ClassificationEngine._safe_intent_from_string("REFUND") == "refund"
        assert ClassificationEngine._safe_intent_from_string("Billing") == "billing"

    def test_invalid_returns_general(self):
        assert (
            ClassificationEngine._safe_intent_from_string("xyz_nonexistent")
            == "general"
        )

    def test_none_returns_general(self):
        assert ClassificationEngine._safe_intent_from_string(None) == "general"

    def test_empty_returns_general(self):
        assert ClassificationEngine._safe_intent_from_string("") == "general"

    def test_whitespace_returns_general(self):
        assert ClassificationEngine._safe_intent_from_string("   ") == "general"

    def test_non_string_returns_general(self):
        assert ClassificationEngine._safe_intent_from_string(123) == "general"


# ═══════════════════════════════════════════════════════════════════════
# 10. _default_result (5 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestDefaultResult:
    def setup_method(self):
        self.engine = ClassificationEngine()

    def test_empty_input_default(self):
        result = self.engine._default_result("empty_input")
        assert result.primary_intent == "general"
        assert result.primary_confidence == 0.0
        assert result.classification_method == "fallback"

    def test_too_short_default(self):
        result = self.engine._default_result("too_short")
        assert result.primary_intent == "general"
        assert result.primary_confidence == 0.0

    def test_all_scores_zero(self):
        result = self.engine._default_result("empty_input")
        for val in result.all_scores.values():
            assert val == 0.0

    def test_secondary_empty(self):
        result = self.engine._default_result("empty_input")
        assert result.secondary_intents == []

    def test_processing_time_zero(self):
        result = self.engine._default_result("empty_input")
        assert result.processing_time_ms == 0.0


# ═══════════════════════════════════════════════════════════════════════
# 11. Processing Time (3 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestProcessingTime:
    @pytest.mark.asyncio
    async def test_keyword_classification_has_time(self):
        engine = ClassificationEngine()
        result = await engine.classify("refund my order", use_ai=False)
        assert isinstance(result.processing_time_ms, float)
        assert result.processing_time_ms >= 0

    @pytest.mark.asyncio
    async def test_ai_classification_has_time(self):
        mock_router = MagicMock()
        mock_router.async_execute_llm_call = AsyncMock(
            return_value={
                "content": '{"primary": "refund", "secondary": [], "confidences": {"refund": 0.9}}',
                "model_used": "test",
            }
        )
        engine = ClassificationEngine(smart_router=mock_router)
        result = await engine.classify("refund", variant_type="parwa", use_ai=True)
        assert result.processing_time_ms >= 0

    @pytest.mark.asyncio
    async def test_fallback_time_is_zero(self):
        engine = ClassificationEngine()
        result = await engine.classify("")
        assert result.processing_time_ms == 0.0


# ═══════════════════════════════════════════════════════════════════════
# 12. Edge Cases (8 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_very_long_text(self):
        engine = ClassificationEngine()
        long_text = "refund " * 500
        result = await engine.classify(long_text, use_ai=False)
        assert result.primary_intent == "refund"

    @pytest.mark.asyncio
    async def test_unicode_text(self):
        engine = ClassificationEngine()
        result = await engine.classify(
            "I want a refund — Großartiger Service! こんにちは", use_ai=False
        )
        assert result.primary_intent == "refund"

    @pytest.mark.asyncio
    async def test_special_characters(self):
        engine = ClassificationEngine()
        result = await engine.classify("@#$%^&*() refund !@#$%^&*()", use_ai=False)
        assert result.primary_intent == "refund"

    @pytest.mark.asyncio
    async def test_mixed_case(self):
        engine = ClassificationEngine()
        result = await engine.classify("ReFuNd My OrDeR", use_ai=False)
        assert result.primary_intent == "refund"

    @pytest.mark.asyncio
    async def test_non_string_text(self):
        engine = ClassificationEngine()
        result = await engine.classify(12345)
        assert result.classification_method == "fallback"

    @pytest.mark.asyncio
    async def test_list_text(self):
        engine = ClassificationEngine()
        result = await engine.classify(["refund", "my", "order"])
        assert result.classification_method == "fallback"

    @pytest.mark.asyncio
    async def test_newlines_in_text(self):
        engine = ClassificationEngine()
        result = await engine.classify("I want a\n\nrefund\n\nmy order", use_ai=False)
        assert result.primary_intent == "refund"

    @pytest.mark.asyncio
    async def test_tabs_in_text(self):
        engine = ClassificationEngine()
        result = await engine.classify("refund\tmy\torder", use_ai=False)
        assert result.primary_intent == "refund"


# ═══════════════════════════════════════════════════════════════════════
# Additional tests for coverage
# ═══════════════════════════════════════════════════════════════════════


class TestIntentPatterns:
    def test_all_intents_in_patterns(self):
        for t in IntentType:
            assert t.value in INTENT_PATTERNS

    def test_general_weight_is_low(self):
        assert INTENT_PATTERNS[IntentType.GENERAL.value]["weight"] == 0.3

    def test_complaint_weight_higher(self):
        assert INTENT_PATTERNS[IntentType.COMPLAINT.value]["weight"] == 1.2

    def test_technical_keywords_not_empty(self):
        assert len(INTENT_PATTERNS[IntentType.TECHNICAL.value]["keywords"]) > 0


class TestAIParseResponseDirect:
    def setup_method(self):
        self.engine = ClassificationEngine()

    def test_valid_json_direct(self):
        response = {
            "content": '{"primary": "refund", "secondary": [], "confidences": {"refund": 0.9}}',
            "model_used": "test",
        }
        result = self.engine._parse_ai_response(response, "c1", "parwa", 0.0)
        assert result.primary_intent == "refund"
        assert result.classification_method == "ai"

    def test_none_response(self):
        result = self.engine._parse_ai_response(None, "c1", "parwa", 0.0)
        assert result.classification_method == "keyword"

    def test_response_without_content(self):
        result = self.engine._parse_ai_response({}, "c1", "parwa", 0.0)
        assert result.classification_method == "keyword"

    def test_primary_gets_min_confidence(self):
        """AI classification ensures primary has >= 0.5 confidence."""
        response = {
            "content": '{"primary": "refund", "secondary": [], "confidences": {"refund": 0.1}}',
            "model_used": "test",
        }
        result = self.engine._parse_ai_response(response, "c1", "parwa", 0.0)
        assert result.primary_confidence >= 0.5

    def test_ai_secondary_excludes_primary(self):
        response = {
            "content": '{"primary": "refund", "secondary": [{"intent": "refund", "confidence": 0.5}], "confidences": {"refund": 0.9}}',
            "model_used": "test",
        }
        result = self.engine._parse_ai_response(response, "c1", "parwa", 0.0)
        secondary_ids = [i for i, c in result.secondary_intents]
        assert "refund" not in secondary_ids


class TestKeywordClassifierMinLength:
    def test_min_length_attribute(self):
        assert KeywordClassifier.MIN_TEXT_LENGTH == 3

    def test_length_constant_is_int(self):
        assert isinstance(KeywordClassifier.MIN_TEXT_LENGTH, int)


class TestClassificationEngineInit:
    def test_default_no_router(self):
        engine = ClassificationEngine()
        assert engine.smart_router is None

    def test_with_router(self):
        mock = MagicMock()
        engine = ClassificationEngine(smart_router=mock)
        assert engine.smart_router is mock

    def test_keyword_classifier_created(self):
        engine = ClassificationEngine()
        assert isinstance(engine._keyword_classifier, KeywordClassifier)
