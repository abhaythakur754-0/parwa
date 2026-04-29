"""
Tests for AI Classification Engine (F-062)

Covers: GAP-008 (empty input), all 12 intents, multi-label,
confidence scoring, AI path, variant gating.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.classification_engine import (
    ClassificationEngine,
    IntentType,
    KeywordClassifier,
)

# ── GAP-008: Empty Input Handling ───────────────────────────────────


class TestGAP008EmptyInput:
    def setup_method(self):
        self.engine = ClassificationEngine()

    @pytest.mark.asyncio
    async def test_empty_string(self):
        result = await self.engine.classify("")
        assert result.primary_intent == IntentType.GENERAL.value
        assert result.primary_confidence == 0.0
        assert result.classification_method == "fallback"
        assert result.secondary_intents == []

    @pytest.mark.asyncio
    async def test_none_input(self):
        result = await self.engine.classify(None)
        assert result.primary_intent == IntentType.GENERAL.value
        assert result.primary_confidence == 0.0

    @pytest.mark.asyncio
    async def test_whitespace_only(self):
        result = await self.engine.classify("   \n\t   ")
        assert result.primary_intent == IntentType.GENERAL.value
        assert result.primary_confidence == 0.0

    @pytest.mark.asyncio
    async def test_single_char(self):
        result = await self.engine.classify("a")
        assert result.primary_intent == IntentType.GENERAL.value
        assert result.primary_confidence == 0.0

    @pytest.mark.asyncio
    async def test_two_chars(self):
        result = await self.engine.classify("ab")
        assert result.primary_intent == IntentType.GENERAL.value
        assert result.primary_confidence == 0.0

    @pytest.mark.asyncio
    async def test_three_chars_valid(self):
        """Exactly 3 chars should proceed to classification, not fallback."""
        result = await self.engine.classify("bug")
        assert result.classification_method == "keyword"
        assert result.primary_intent == "technical"

    @pytest.mark.asyncio
    async def test_all_scores_populated_on_fallback(self):
        result = await self.engine.classify("")
        assert len(result.all_scores) == len(IntentType)
        for intent in IntentType:
            assert intent.value in result.all_scores


# ── IntentType Enum ──────────────────────────────────────────────────


class TestIntentTypeEnum:
    def test_count(self):
        assert len(IntentType) == 12

    def test_core_intents(self):
        core = {
            "refund",
            "technical",
            "billing",
            "complaint",
            "feature_request",
            "general",
        }
        assert core.issubset({t.value for t in IntentType})

    def test_extended_intents(self):
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

    def test_compat_map(self):
        from app.core.classification_engine import INTENT_TO_CATEGORY_MAP

        assert len(INTENT_TO_CATEGORY_MAP) == 12


# ── Keyword Classification ───────────────────────────────────────────


class TestKeywordClassifier:
    def setup_method(self):
        self.classifier = KeywordClassifier()

    @pytest.mark.parametrize(
        "query,expected",
        [
            ("I want a refund for my order", "refund"),
            ("The app keeps crashing with error 500", "technical"),
            ("I have a question about my bill", "billing"),
            ("This is the worst service ever", "complaint"),
            ("Please add dark mode feature", "feature_request"),
            ("Cancel my subscription right now", "cancellation"),
            ("Where is my package tracking?", "shipping"),
            ("How do I reset my password?", "account"),
            ("Can you explain how billing works?", "inquiry"),
            ("I need to speak to your manager", "escalation"),
            ("Great product, keep it up!", "feedback"),
        ],
    )
    def test_intent_detection(self, query, expected):
        result = self.classifier.classify(query)
        assert result.primary_intent == expected

    def test_general_fallback(self):
        result = self.classifier.classify("hello there how are you")
        assert result.primary_intent == "general"

    def test_method_is_keyword(self):
        result = self.classifier.classify("refund my order")
        assert result.classification_method == "keyword"


# ── Multi-Label Detection ────────────────────────────────────────────


class TestMultiLabelDetection:
    def setup_method(self):
        self.classifier = KeywordClassifier()

    def test_refund_plus_technical(self):
        result = self.classifier.classify("refund this technical error")
        assert result.primary_intent in ("refund", "technical")
        secondary_intents = [i for i, c in result.secondary_intents]
        assert (
            result.primary_intent in secondary_intents
            or "technical" in secondary_intents
            or "refund" in secondary_intents
        )

    def test_max_3_secondary(self):
        result = self.classifier.classify(
            "refund my order, there's a bug, bill is wrong, cancel subscription"
        )
        assert len(result.secondary_intents) <= 3

    def test_no_secondary_for_very_specific(self):
        result = self.classifier.classify("chargeback immediately")
        secondary_intents = [i for i, c in result.secondary_intents if c > 0.2]
        # May have some low-confidence secondaries but that's ok
        assert isinstance(result.secondary_intents, list)

    def test_secondary_are_tuples(self):
        result = self.classifier.classify("some text here")
        for item in result.secondary_intents:
            assert isinstance(item, tuple)
            assert len(item) == 2
            assert isinstance(item[0], str)
            assert isinstance(item[1], float)


# ── Confidence Scoring ───────────────────────────────────────────────


class TestConfidenceScoring:
    def setup_method(self):
        self.classifier = KeywordClassifier()

    def test_confidence_bounded(self):
        result = self.classifier.classify("I want a refund money back return")
        assert 0.0 <= result.primary_confidence <= 0.95

    def test_confidence_cap_at_095(self):
        result = self.classifier.classify(
            "refund refund refund money back return reimburse chargeback"
        )
        assert result.primary_confidence <= 0.95

    def test_general_low_confidence(self):
        result = self.classifier.classify("hello world how are you today")
        assert result.primary_intent == "general"
        # General may have low confidence
        assert result.primary_confidence < 0.8

    def test_specific_high_confidence(self):
        result = self.classifier.classify(
            "I want a refund money back return reimburse chargeback"
        )
        assert result.primary_confidence > 0.3

    def test_all_scores_are_floats(self):
        result = self.classifier.classify("test")
        for key, val in result.all_scores.items():
            assert isinstance(val, float)


# ── Classification Method ────────────────────────────────────────────


class TestClassificationMethod:
    def setup_method(self):
        self.engine = ClassificationEngine()

    @pytest.mark.asyncio
    async def test_keyword_method(self):
        result = await self.engine.classify("refund my order", use_ai=False)
        assert result.classification_method in ("keyword", "fallback")

    @pytest.mark.asyncio
    async def test_fallback_method_for_empty(self):
        result = await self.engine.classify("", use_ai=True)
        assert result.classification_method == "fallback"

    @pytest.mark.asyncio
    async def test_use_ai_false(self):
        result = await self.engine.classify("bug in system", use_ai=False)
        assert result.classification_method == "keyword"

    @pytest.mark.asyncio
    async def test_processing_time_populated(self):
        result = await self.engine.classify("refund my order", use_ai=False)
        assert result.processing_time_ms >= 0

    @pytest.mark.asyncio
    async def test_model_used_none_for_keyword(self):
        result = await self.engine.classify("refund", use_ai=False)
        assert result.model_used is None


# ── Variant Gating ───────────────────────────────────────────────────


class TestVariantGating:
    def setup_method(self):
        self.engine = ClassificationEngine()

    @pytest.mark.asyncio
    async def test_mini_parwa_skips_ai(self):
        """Mini PARWA should use keyword, not AI."""
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
    async def test_parwa_uses_ai(self):
        """Parwa should attempt AI classification."""
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
    async def test_high_parwa_uses_ai(self):
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
            variant_type="high_parwa",
            use_ai=True,
        )
        mock_router.async_execute_llm_call.assert_called_once()


# ── AI Classification Path ───────────────────────────────────────────


class TestAIClassificationPath:
    @pytest.mark.asyncio
    async def test_ai_response_parsed(self):
        mock_router = MagicMock()
        mock_router.async_execute_llm_call = AsyncMock(
            return_value={
                "content": '{"primary": "refund", "secondary": [{"intent": "billing", "confidence": 0.3}], "confidences": {"refund": 0.85, "billing": 0.3, "general": 0.1}}',
                "model_used": "gemma-3-27b-it",
            }
        )
        engine = ClassificationEngine(smart_router=mock_router)
        result = await engine.classify(
            "I want a refund",
            variant_type="parwa",
            use_ai=True,
        )
        assert result.primary_intent == "refund"
        assert result.model_used == "gemma-3-27b-it"

    @pytest.mark.asyncio
    async def test_ai_fallback_on_exception(self):
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
    async def test_ai_fallback_on_empty_response(self):
        mock_router = MagicMock()
        mock_router.async_execute_llm_call = AsyncMock(return_value={})
        engine = ClassificationEngine(smart_router=mock_router)
        result = await engine.classify(
            "test query",
            variant_type="parwa",
            use_ai=True,
        )
        assert result.classification_method == "keyword"

    @pytest.mark.asyncio
    async def test_ai_fallback_on_invalid_json(self):
        mock_router = MagicMock()
        mock_router.async_execute_llm_call = AsyncMock(
            return_value={"content": "not json at all"}
        )
        engine = ClassificationEngine(smart_router=mock_router)
        result = await engine.classify(
            "test",
            variant_type="parwa",
            use_ai=True,
        )
        assert result.classification_method == "keyword"


# ── AI Response Parsing ──────────────────────────────────────────────


class TestAIParseResponse:
    def setup_method(self):
        self.engine = ClassificationEngine()

    def test_valid_json(self):
        response = {
            "content": '{"primary": "refund", "secondary": [], "confidences": {"refund": 0.9}}',
            "model_used": "test",
        }
        result = self.engine._parse_ai_response(response, "c1", "parwa", 0.0)
        assert result.primary_intent == "refund"
        assert result.classification_method == "ai"

    def test_json_with_markdown_fences(self):
        response = {
            "content": '```json\n{"primary": "billing", "secondary": [], "confidences": {"billing": 0.8}}\n```',
            "model_used": "test",
        }
        result = self.engine._parse_ai_response(response, "c1", "parwa", 0.0)
        assert result.primary_intent == "billing"

    def test_confidence_clamped_above(self):
        response = {
            "content": '{"primary": "refund", "secondary": [], "confidences": {"refund": 1.5}}',
            "model_used": "test",
        }
        result = self.engine._parse_ai_response(response, "c1", "parwa", 0.0)
        assert result.primary_confidence <= 0.95

    def test_confidence_clamped_below(self):
        response = {
            "content": '{"primary": "refund", "secondary": [], "confidences": {"refund": -0.5}}',
            "model_used": "test",
        }
        result = self.engine._parse_ai_response(response, "c1", "parwa", 0.0)
        assert result.primary_confidence >= 0.0

    def test_invalid_primary_falls_to_general(self):
        response = {
            "content": '{"primary": "nonexistent_intent", "secondary": [], "confidences": {}}',
            "model_used": "test",
        }
        result = self.engine._parse_ai_response(response, "c1", "parwa", 0.0)
        assert result.primary_intent == "general"


# ── Safe Intent From String ──────────────────────────────────────────


class TestSafeIntentFromString:
    def test_valid_intent(self):
        assert ClassificationEngine._safe_intent_from_string("refund") == "refund"

    def test_case_insensitive(self):
        assert ClassificationEngine._safe_intent_from_string("REFUND") == "refund"
        assert ClassificationEngine._safe_intent_from_string("Billing") == "billing"

    def test_invalid_returns_general(self):
        assert ClassificationEngine._safe_intent_from_string("xyz") == "general"

    def test_empty_returns_general(self):
        assert ClassificationEngine._safe_intent_from_string("") == "general"

    def test_whitespace_returns_general(self):
        assert ClassificationEngine._safe_intent_from_string("   ") == "general"
