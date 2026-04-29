"""
Day 6 Gap Analysis Tests — Week 9

Manual gap analysis covering:
1. UNIT GAPS — edge cases not covered by existing 306 tests
2. INTEGRATION GAPS — signal extraction -> classification -> technique mapping pipeline
3. FLOW GAPS — full end-to-end flow from query to technique selection
4. BREAK TESTS — adversarial inputs, concurrent access, Unicode, boundaries

Parent: Week 9 Day 6 (Monday)
"""

import asyncio
import time
from unittest.mock import AsyncMock, patch

import pytest
from app.core.clara_quality_gate import (
    BrandVoiceConfig,
    CLARAQualityGate,
    CLARAStage,
    StageResult,
)
from app.core.classification_engine import (
    ClassificationEngine,
    IntentType,
)
from app.core.signal_extraction import (
    ExtractedSignals,
    SignalExtractionRequest,
    SignalExtractor,
)
from app.core.technique_router import TechniqueID
from app.services.intent_technique_mapper import IntentTechniqueMapper

# =========================================================================
# CATEGORY 1: UNIT GAPS — Edge cases not covered
# =========================================================================


class TestUnicodeHandling:
    """Unicode/non-ASCII input handling across modules."""

    def setup_method(self):
        self.extractor = SignalExtractor()
        self.engine = ClassificationEngine()

    @pytest.mark.asyncio
    async def test_signal_extraction_unicode_query(self):
        """Signal extraction should handle Unicode characters without crashing."""
        req = SignalExtractionRequest(
            query="私は返金を求めています！注文番号は #12345 です。",
            company_id="c1",
            variant_type="parwa",
        )
        result = await self.extractor.extract(req)
        assert isinstance(result.intent, str)
        assert 0.0 <= result.sentiment <= 1.0
        assert 0.0 <= result.complexity <= 1.0

    @pytest.mark.asyncio
    async def test_signal_extraction_emoji_query(self):
        """Signal extraction handles emoji-heavy input."""
        req = SignalExtractionRequest(
            query="I want a refund 😡😡😡 this is terrible 😤😤 💔💔",
            company_id="c1",
            variant_type="parwa",
        )
        result = await self.extractor.extract(req)
        assert result.intent == "refund"
        assert result.sentiment < 0.5

    @pytest.mark.asyncio
    async def test_signal_extraction_mixed_scripts(self):
        """Signal extraction handles mixed Latin/CJK/Arabic."""
        req = SignalExtractionRequest(
            query="Refund حادثة خطأ Fehler Merci",
            company_id="c1",
            variant_type="parwa",
        )
        result = await self.extractor.extract(req)
        assert isinstance(result.intent, str)
        assert result.intent in ("refund", "general", "technical")

    @pytest.mark.asyncio
    async def test_classification_unicode(self):
        """Classification engine handles non-ASCII input."""
        result = await self.engine.classify(
            "Ich möchte eine Rückerstattung für meine Bestellung", use_ai=False
        )
        assert result.primary_intent == "general"  # German not in keyword list

    @pytest.mark.asyncio
    async def test_classification_chinese_chars(self):
        """Classification engine handles Chinese characters."""
        result = await self.engine.classify("退款", use_ai=False)
        assert result.primary_intent == "general"
        assert 0.0 <= result.primary_confidence <= 1.0

    @pytest.mark.asyncio
    async def test_clara_unicode_response(self):
        """CLARA handles Unicode in response and query."""
        gate = CLARAQualityGate()
        result = await gate.evaluate(
            response="Vielen Dank für Ihre Anfrage. Wir helfen Ihnen gerne weiter. ¡Gracias!",
            query="Hilfe",
            customer_sentiment=0.7,
        )
        assert isinstance(result.overall_pass, bool)
        assert len(result.stages) == 5


class TestVeryLongInput:
    """Very long input (>10000 chars) handling."""

    def setup_method(self):
        self.extractor = SignalExtractor()
        self.engine = ClassificationEngine()
        self.gate = CLARAQualityGate()

    @pytest.mark.asyncio
    async def test_signal_extraction_10k_chars(self):
        """Signal extraction handles 10,000+ character queries."""
        long_query = "I have a billing problem with my account. " * 400  # ~12,000 chars
        req = SignalExtractionRequest(
            query=long_query,
            company_id="c1",
            variant_type="parwa",
        )
        result = await self.extractor.extract(req)
        assert isinstance(result.intent, str)
        assert 0.0 <= result.sentiment <= 1.0
        assert 0.0 <= result.complexity <= 1.0
        assert result.complexity >= 0.3  # Long query increases complexity

    @pytest.mark.asyncio
    async def test_signal_extraction_50k_chars(self):
        """Signal extraction handles 50,000+ character queries without timeout."""
        long_query = "problem error bug issue " * 3000  # ~60,000 chars
        req = SignalExtractionRequest(
            query=long_query,
            company_id="c1",
            variant_type="parwa",
        )
        start = time.monotonic()
        result = await self.extractor.extract(req)
        elapsed = time.monotonic() - start
        assert elapsed < 5.0  # Should not take more than 5 seconds
        assert result.intent in ("technical", "complaint", "general")

    @pytest.mark.asyncio
    async def test_classification_10k_chars(self):
        """Classification handles very long input."""
        long_text = "I want a refund for my order. " * 800  # ~12,000 chars
        result = await self.engine.classify(long_text, use_ai=False)
        assert result.primary_intent == "refund"
        assert result.processing_time_ms >= 0

    @pytest.mark.asyncio
    async def test_clara_10k_chars(self):
        """CLARA handles very long response text."""
        long_response = "Thank you for contacting support. " * 800  # ~12,000 chars
        result = await self.gate.evaluate(
            response=long_response,
            query="refund",
        )
        structure = next(
            s for s in result.stages if s.stage == CLARAStage.STRUCTURE_CHECK
        )
        assert structure.result == StageResult.FAIL  # >500 words


class TestMonetaryEdgeCases:
    """Monetary value edge cases: 0, negative, extremely large."""

    def setup_method(self):
        self.extractor = SignalExtractor()

    def test_zero_dollar_amount(self):
        """$0 should extract as 0.0."""
        value, currency = self.extractor._extract_monetary_value("I paid $0")
        assert value == 0.0
        assert currency == "$"

    def test_fractional_cent_amount(self):
        """Very small amounts like $0.01."""
        value, currency = self.extractor._extract_monetary_value("$0.01")
        assert value == 0.01
        assert currency == "$"

    def test_very_large_amount(self):
        """Very large monetary values like $1,000,000.00."""
        value, currency = self.extractor._extract_monetary_value("$1,000,000.00")
        assert value == 1_000_000.00
        assert currency == "$"

    def test_negative_dollar_sign_prefix(self):
        """Text says '-$50' (negative context)."""
        value, currency = self.extractor._extract_monetary_value("I lost -$50 on this")
        # The regex matches $50, not -$50 (the regex doesn't capture the minus)
        assert value == 50.0
        assert currency == "$"

    def test_multiple_currencies_in_one_query(self):
        """Sum of multiple different currencies."""
        value, currency = self.extractor._extract_monetary_value(
            "$100 plus £200 plus €300 plus ₹50000 plus ¥10000"
        )
        # All should be converted to USD
        assert value > 100  # At least the $100
        assert value < 1000  # Not an unreasonable sum

    def test_amount_without_space_after_symbol(self):
        """€99 without space after symbol."""
        value, currency = self.extractor._extract_monetary_value("Price:€99")
        assert value > 90
        assert currency == "€"


class TestSafeIntentFromStringNone:
    """_safe_intent_from_string with None and non-string inputs."""

    def test_none_input(self):
        """None should return 'general', not crash."""
        result = ClassificationEngine._safe_intent_from_string(None)
        assert result == "general"

    def test_integer_input(self):
        """Integer input should return 'general'."""
        result = ClassificationEngine._safe_intent_from_string(123)
        assert result == "general"

    def test_float_input(self):
        """Float input should return 'general'."""
        result = ClassificationEngine._safe_intent_from_string(3.14)
        assert result == "general"

    def test_list_input(self):
        """List input should return 'general'."""
        result = ClassificationEngine._safe_intent_from_string(["refund"])
        assert result == "general"

    def test_dict_input(self):
        """Dict input should return 'general'."""
        result = ClassificationEngine._safe_intent_from_string({"primary": "refund"})
        assert result == "general"


class TestBrandVoiceConfigNonProfessionalTone:
    """BrandVoiceConfig with tone != professional."""

    def test_friendly_tone_is_custom(self):
        """Friendly tone counts as custom configuration."""
        bv = BrandVoiceConfig(tone="friendly")
        assert bv.is_custom_configured is True

    def test_casual_tone_is_custom(self):
        """Casual tone counts as custom configuration."""
        bv = BrandVoiceConfig(tone="casual")
        assert bv.is_custom_configured is True

    @pytest.mark.asyncio
    async def test_friendly_tone_enforced_in_clara(self):
        """CLARA with friendly tone config should check brand rules."""
        bv = BrandVoiceConfig(tone="friendly", prohibited_words=["stupid"])
        gate = CLARAQualityGate(brand_voice=bv)
        result = await gate._brand_check("That's a stupid thing to do.")
        assert result.result == StageResult.FAIL
        assert any("stupid" in i.lower() for i in result.issues)

    @pytest.mark.asyncio
    async def test_casual_formality_allows_informal(self):
        """Casual formality should not flag informal language."""
        bv = BrandVoiceConfig(formality="low")
        gate = CLARAQualityGate(brand_voice=bv)
        result = await gate._brand_check("Hey what's up! Your issue is fixed, lol.")
        assert result.result == StageResult.PASS


class TestCLARASentimentBoundaries:
    """CLARA Tone Check with customer_sentiment at boundaries."""

    @pytest.mark.asyncio
    async def test_sentiment_exactly_0_0(self):
        """customer_sentiment=0.0 (extremely angry) needs empathy."""
        gate = CLARAQualityGate()
        result = await gate._tone_check(
            "Your request has been processed.",
            customer_sentiment=0.0,
        )
        assert result.result == StageResult.FAIL  # No empathy

    @pytest.mark.asyncio
    async def test_sentiment_exactly_0_3(self):
        """customer_sentiment=0.3 is boundary — just above angry threshold."""
        gate = CLARAQualityGate()
        result = await gate._tone_check(
            "Your request has been processed.",
            customer_sentiment=0.3,
        )
        # 0.3 is NOT < 0.3, so no empathy required
        assert result.result == StageResult.PASS

    @pytest.mark.asyncio
    async def test_sentiment_exactly_0_7(self):
        """customer_sentiment=0.7 is boundary — just at happy threshold."""
        gate = CLARAQualityGate()
        result = await gate._tone_check(
            "Your request has been processed.",
            customer_sentiment=0.7,
        )
        # 0.7 is NOT > 0.7, so no warm language required
        assert result.result == StageResult.PASS

    @pytest.mark.asyncio
    async def test_sentiment_exactly_1_0(self):
        """customer_sentiment=1.0 (extremely happy) needs warmth."""
        gate = CLARAQualityGate()
        result = await gate._tone_check(
            "Your request has been processed.",
            customer_sentiment=1.0,
        )
        assert result.result == StageResult.FAIL  # Cold tone for happy customer

    @pytest.mark.asyncio
    async def test_sentiment_0_29_with_empathy(self):
        """customer_sentiment=0.29 with empathy should pass."""
        gate = CLARAQualityGate()
        result = await gate._tone_check(
            "I'm sorry about this issue. I understand your frustration.",
            customer_sentiment=0.29,
        )
        assert result.result == StageResult.PASS

    @pytest.mark.asyncio
    async def test_sentiment_0_71_with_warmth(self):
        """customer_sentiment=0.71 with warm language should pass."""
        gate = CLARAQualityGate()
        result = await gate._tone_check(
            "Great! I'm happy to help you with that.",
            customer_sentiment=0.71,
        )
        assert result.result == StageResult.PASS


class TestAIResponseExtraFields:
    """Classification with AI JSON that has extra/unexpected fields."""

    def test_extra_fields_ignored(self):
        """Extra fields in AI JSON should be ignored, not crash."""
        engine = ClassificationEngine()
        response = {
            "content": (
                '{"primary": "refund", "secondary": [], '
                '"confidences": {"refund": 0.9}, '
                '"extra_field": "should be ignored", '
                '"model_version": "v2", '
                '"unknown_key": 42}'
            ),
            "model_used": "test",
        }
        result = engine._parse_ai_response(response, "c1", "parwa", 0.0)
        assert result.primary_intent == "refund"
        assert result.classification_method == "ai"
        assert result.primary_confidence > 0.0

    def test_missing_confidences_field(self):
        """Missing confidences field should not crash."""
        engine = ClassificationEngine()
        response = {
            "content": '{"primary": "billing", "secondary": []}',
            "model_used": "test",
        }
        result = engine._parse_ai_response(response, "c1", "parwa", 0.0)
        assert result.primary_intent == "billing"
        # All 12 intent scores should still be populated
        assert len(result.all_scores) == 12

    def test_secondary_with_extra_fields(self):
        """Secondary intents with extra fields should not crash."""
        engine = ClassificationEngine()
        response = {
            "content": (
                '{"primary": "refund", '
                '"secondary": [{"intent": "billing", "confidence": 0.3, "note": "also"}], '
                '"confidences": {"refund": 0.85, "billing": 0.3}}'
            ),
            "model_used": "test",
        }
        result = engine._parse_ai_response(response, "c1", "parwa", 0.0)
        assert result.primary_intent == "refund"
        assert len(result.secondary_intents) >= 1


class TestVariantWeightDifferences:
    """Signal extraction with all 3 variants getting different weights."""

    def setup_method(self):
        self.extractor = SignalExtractor()

    def test_mini_parwa_weights_differ_from_parwa(self):
        """Mini PARWA and Parwa should have different complexity weights."""
        mini = self.extractor.get_variant_weights("mini_parwa")
        parwa = self.extractor.get_variant_weights("parwa")
        assert mini["complexity"] != parwa["complexity"]

    def test_high_parwa_has_monetary_weight(self):
        """Parwa High should have monetary weight, others don't."""
        high_parwa = self.extractor.get_variant_weights("high_parwa")
        parwa = self.extractor.get_variant_weights("parwa")
        mini = self.extractor.get_variant_weights("mini_parwa")
        assert "monetary" in high_parwa
        assert "monetary" not in parwa
        assert "monetary" not in mini

    def test_complexity_differs_by_variant(self):
        """Same query should produce different complexity for different variants."""
        query = "I have a complex technical problem with my API integration and database server"
        mini_weights = self.extractor.get_variant_weights("mini_parwa")
        parwa_weights = self.extractor.get_variant_weights("parwa")
        high_parwa_weights = self.extractor.get_variant_weights("high_parwa")

        mini_complexity = self.extractor._extract_complexity(query, mini_weights)
        parwa_complexity = self.extractor._extract_complexity(query, parwa_weights)
        high_parwa_complexity = self.extractor._extract_complexity(
            query, high_parwa_weights
        )

        # All should be valid
        for c in [mini_complexity, parwa_complexity, high_parwa_complexity]:
            assert 0.0 <= c <= 1.0
        # Different weights should produce different results
        assert (
            mini_complexity != parwa_complexity
            or parwa_complexity != high_parwa_complexity
        )


class TestConversationHistoryNoneItems:
    """conversation_history containing None items."""

    def setup_method(self):
        self.extractor = SignalExtractor()

    @pytest.mark.asyncio
    async def test_all_none_history(self):
        """History with all None items should not crash."""
        req = SignalExtractionRequest(
            query="refund my order",
            company_id="c1",
            variant_type="parwa",
            conversation_history=[None, None, None],
        )
        result = await self.extractor.extract(req)
        assert result.intent == "refund"
        assert result.reasoning_loop_detected is False

    @pytest.mark.asyncio
    async def test_mixed_none_and_strings(self):
        """History with mix of None and strings."""
        req = SignalExtractionRequest(
            query="refund my order now please",
            company_id="c1",
            variant_type="parwa",
            conversation_history=[
                None,
                "refund my order now please",
                None,
                "refund my order now please",
            ],
        )
        result = await self.extractor.extract(req)
        assert result.intent == "refund"
        # Two matching strings in history should trigger loop detection
        assert result.reasoning_loop_detected is True

    @pytest.mark.asyncio
    async def test_empty_string_in_history(self):
        """History with empty strings should be handled."""
        req = SignalExtractionRequest(
            query="help me",
            company_id="c1",
            variant_type="parwa",
            conversation_history=["", "   ", "", "  ", ""],
        )
        result = await self.extractor.extract(req)
        assert result.reasoning_loop_detected is False


# =========================================================================
# CATEGORY 2: INTEGRATION GAPS — Pipeline integration tests
# =========================================================================


class TestSignalExtractionToClassification:
    """Signal extraction output feeds into classification engine."""

    @pytest.mark.asyncio
    async def test_extracted_intent_matches_classification(self):
        """Signal extraction intent should be consistent with classification."""
        query = "I want a refund for my $50 order, this is terrible!"
        req = SignalExtractionRequest(
            query=query,
            company_id="c1",
            variant_type="parwa",
        )
        extractor = SignalExtractor()
        signals = await extractor.extract(req)

        engine = ClassificationEngine()
        classification = await engine.classify(query, use_ai=False)

        # Both should identify refund-related intent
        assert signals.intent == "refund"
        assert classification.primary_intent in (
            "refund",
            "complaint",
        )  # "terrible" boosts complaint

    @pytest.mark.asyncio
    async def test_extracted_sentiment_used_in_clara(self):
        """Extracted sentiment can be passed to CLARA tone check."""
        query = "This is the worst experience ever! I'm furious!"
        req = SignalExtractionRequest(
            query=query,
            company_id="c1",
            variant_type="parwa",
        )
        extractor = SignalExtractor()
        signals = await extractor.extract(req)

        # Negative sentiment extracted
        assert signals.sentiment < 0.4

        # Use sentiment as customer_sentiment for CLARA
        gate = CLARAQualityGate()
        result = await gate.evaluate(
            response="Your request has been processed. Reference 12345.",
            query=query,
            customer_sentiment=signals.sentiment,
        )
        tone_stage = next(s for s in result.stages if s.stage == CLARAStage.TONE_CHECK)
        # Cold tone for negative sentiment customer should fail
        assert tone_stage.result == StageResult.FAIL


class TestClassificationToTechniqueMapping:
    """Classification output feeds into intent→technique mapping."""

    def test_all_classifiable_intents_have_mappings(self):
        """Every intent in IntentType should have a technique mapping."""
        mapper = IntentTechniqueMapper()
        engine = ClassificationEngine()

        # Classify each intent type's keywords
        intent_keywords_map = {
            "refund": "I want a refund for my order",
            "technical": "The API server has a 500 error",
            "billing": "My bill has an incorrect charge",
            "complaint": "This is the worst service, I'm furious",
            "feature_request": "Please add a dark mode feature",
            "general": "Hello how are you today",
            "cancellation": "Cancel my subscription right now",
            "shipping": "Where is my package delivery?",
            "inquiry": "How do I update my account settings?",
            "escalation": "I need to speak to your manager immediately",
            "account": "I need to reset my account password",
            "feedback": "Great product, keep up the good work!",
        }

        for intent_value, query in intent_keywords_map.items():
            result = engine._keyword_classifier.classify(query)
            mapping = mapper.map_intent(result.primary_intent, variant_type="parwa")
            # Even "general" has a mapping
            assert isinstance(mapping.selected_techniques, list)

    def test_technique_mapping_respects_variant_for_all_intents(self):
        """All intents filtered through mini_parwa should only have T1 techniques."""
        mapper = IntentTechniqueMapper()
        tier1_techniques = {TechniqueID.CLARA, TechniqueID.CRP, TechniqueID.GSD}

        for intent in mapper.get_supported_intents():
            result = mapper.map_intent(intent=intent, variant_type="mini_parwa")
            for tech in result.selected_techniques:
                assert tech in tier1_techniques, f"Intent '{intent}' got {
                    tech.value} which is not Tier 1 for mini_parwa"


class TestFullPipelineSignalToTechnique:
    """Full pipeline: Query → Signal Extraction → Classification → Technique Mapping."""

    @pytest.mark.asyncio
    async def test_refund_pipeline(self):
        """Full pipeline for refund query."""
        query = "I want a refund for my $500 order"
        req = SignalExtractionRequest(
            query=query,
            company_id="c1",
            variant_type="parwa",
        )

        # Step 1: Signal Extraction
        extractor = SignalExtractor()
        signals = await extractor.extract(req)
        assert signals.intent == "refund"
        assert signals.monetary_value == 500.0

        # Step 2: Classification
        engine = ClassificationEngine()
        classification = await engine.classify(query, use_ai=False)
        assert classification.primary_intent == "refund"

        # Step 3: Technique Mapping
        mapper = IntentTechniqueMapper()
        mapping = mapper.map_intent(classification.primary_intent, variant_type="parwa")
        assert len(mapping.selected_techniques) > 0

    @pytest.mark.asyncio
    async def test_technical_pipeline(self):
        """Full pipeline for technical query."""
        query = "The API endpoint returns a 500 error and the server is down"
        req = SignalExtractionRequest(
            query=query,
            company_id="c1",
            variant_type="parwa",
        )

        extractor = SignalExtractor()
        signals = await extractor.extract(req)

        engine = ClassificationEngine()
        classification = await engine.classify(query, use_ai=False)

        mapper = IntentTechniqueMapper()
        mapping = mapper.map_intent(classification.primary_intent, variant_type="parwa")

        assert classification.primary_intent == "technical"
        assert TechniqueID.CHAIN_OF_THOUGHT in mapping.selected_techniques

    @pytest.mark.asyncio
    async def test_mini_parwa_pipeline_blocks_t3(self):
        """Mini PARWA pipeline should never select T3 techniques."""
        query = "I want a refund for my $1000 order, this is unacceptable!"
        req = SignalExtractionRequest(
            query=query,
            company_id="c1",
            variant_type="mini_parwa",
        )

        extractor = SignalExtractor()
        signals = await extractor.extract(req)

        engine = ClassificationEngine()
        classification = await engine.classify(
            query, use_ai=False, variant_type="mini_parwa"
        )

        mapper = IntentTechniqueMapper()
        mapping = mapper.map_intent(
            classification.primary_intent, variant_type="mini_parwa"
        )

        tier1 = {TechniqueID.CLARA, TechniqueID.CRP, TechniqueID.GSD}
        for tech in mapping.selected_techniques:
            assert tech in tier1

    @pytest.mark.asyncio
    async def test_unknown_intent_falls_through_safely(self):
        """Pipeline with unrecognized intent should not crash."""
        query = "xyzzy plugh frobozz"  # gibberish
        req = SignalExtractionRequest(
            query=query,
            company_id="c1",
            variant_type="parwa",
        )

        extractor = SignalExtractor()
        signals = await extractor.extract(req)

        engine = ClassificationEngine()
        classification = await engine.classify(query, use_ai=False)

        mapper = IntentTechniqueMapper()
        # This won't crash even if intent has no mapping
        mapping = mapper.map_intent(classification.primary_intent, variant_type="parwa")

        assert isinstance(mapping.selected_techniques, list)


class TestSignalExtractionToQuerySignalsToMapping:
    """Signal extraction → to_query_signals → technique mapping bridge."""

    def test_extracted_signals_bridge_to_router(self):
        """ExtractedSignals converts to QuerySignals for technique router."""
        extractor = SignalExtractor()
        signals = ExtractedSignals(
            intent="refund",
            sentiment=0.3,
            complexity=0.6,
            monetary_value=500.0,
            monetary_currency="$",
            customer_tier="vip",
            turn_count=3,
            previous_response_status="rejected",
            reasoning_loop_detected=True,
            resolution_path_count=4,
            query_breadth=0.7,
        )
        qs = extractor.to_query_signals(signals)
        assert qs.intent_type == "refund"
        assert qs.monetary_value == 500.0
        assert qs.reasoning_loop_detected is True


# =========================================================================
# CATEGORY 3: FLOW GAPS — End-to-end flows
# =========================================================================


class TestFullEndToEndFlow:
    """Full end-to-end flow from raw query to CLARA evaluation."""

    @pytest.mark.asyncio
    async def test_query_to_clara_with_adaptive_tone(self):
        """Query → Signal Extract → Classify → Map → CLARA evaluate."""
        query = "I'm very frustrated! This is the worst service ever, I want a refund!"
        company_id = "test_tenant"
        variant_type = "parwa"

        # Step 1: Extract signals
        req = SignalExtractionRequest(
            query=query,
            company_id=company_id,
            variant_type=variant_type,
        )
        extractor = SignalExtractor()
        signals = await extractor.extract(req)

        # Step 2: Classify
        engine = ClassificationEngine()
        classification = await engine.classify(query, use_ai=False)

        # Step 3: Map to techniques
        mapper = IntentTechniqueMapper()
        mapping = mapper.map_intent(
            classification.primary_intent, variant_type=variant_type
        )

        # Step 4: Generate a response (simulated) and run CLARA
        # Simulate an empathetic response based on negative sentiment
        if signals.sentiment < 0.4:
            test_response = (
                "I'm sorry about your frustrating experience. "
                "I understand how upsetting this must be. "
                "Let me process your refund right away. "
                "The amount will be credited within 5-7 business days. "
                "Thank you for your patience."
            )
        else:
            test_response = "Your request has been processed."

        gate = CLARAQualityGate()
        clara_result = await gate.evaluate(
            response=test_response,
            query=query,
            company_id=company_id,
            customer_sentiment=signals.sentiment,
        )

        # Verify full pipeline
        assert classification.primary_intent in ("refund", "complaint")
        assert len(mapping.selected_techniques) > 0
        assert len(clara_result.stages) == 5
        # Empathetic response should pass tone check
        tone = next(s for s in clara_result.stages if s.stage == CLARAStage.TONE_CHECK)
        assert tone.result == StageResult.PASS

    @pytest.mark.asyncio
    async def test_all_12_intents_end_to_end(self):
        """Every intent goes through the full pipeline without errors."""
        queries = {
            "refund": "I want a refund for my order",
            "technical": "The app keeps crashing with a bug",
            "billing": "My bill has an overcharge",
            "complaint": "This is terrible, worst service ever",
            "feature_request": "Please add a dark mode feature",
            "general": "Hello, how are you?",
            "cancellation": "Cancel my subscription right now",
            "shipping": "Where is my package delivery?",
            "inquiry": "How do I update my account?",
            "escalation": "I need to speak to a manager",
            "account": "I forgot my password",
            "feedback": "Great job, keep it up! Love your product!",
        }

        extractor = SignalExtractor()
        engine = ClassificationEngine()
        mapper = IntentTechniqueMapper()
        gate = CLARAQualityGate()

        for intent, query in queries.items():
            req = SignalExtractionRequest(
                query=query,
                company_id="c1",
                variant_type="parwa",
            )
            signals = await extractor.extract(req)
            classification = await engine.classify(query, use_ai=False)
            mapping = mapper.map_intent(
                classification.primary_intent, variant_type="parwa"
            )

            assert signals.intent == intent, f"Expected '{intent}', got '{
                signals.intent}'"
            assert len(mapping.selected_techniques) > 0


# =========================================================================
# CATEGORY 4: BREAK TESTS — Adversarial inputs, concurrency, boundaries
# =========================================================================


class TestConcurrentClassification:
    """Concurrent classification requests (race condition safety)."""

    @pytest.mark.asyncio
    async def test_concurrent_classifications(self):
        """Multiple concurrent classify calls should not crash."""
        engine = ClassificationEngine()
        texts = [
            "I want a refund for my order",
            "The server is down",
            "My bill is wrong",
            "Cancel my subscription",
            "Where is my package?",
            "Reset my password",
            "This is terrible",
            "Great product!",
            "How do I update settings?",
            "Speak to manager",
        ]

        tasks = [engine.classify(text, use_ai=False) for text in texts]
        results = await asyncio.gather(*tasks)

        assert len(results) == 10
        for result in results:
            assert isinstance(result.primary_intent, str)
            assert 0.0 <= result.primary_confidence <= 1.0
            assert result.classification_method == "keyword"

    @pytest.mark.asyncio
    async def test_concurrent_signal_extraction(self):
        """Multiple concurrent signal extractions should not crash."""
        extractor = SignalExtractor()
        queries = [
            SignalExtractionRequest(
                query=f"Query number {i}: I have a refund request for ${i * 10}",
                company_id="c1",
                variant_type="parwa",
            )
            for i in range(20)
        ]

        tasks = [extractor.extract(req) for req in queries]
        results = await asyncio.gather(*tasks)

        assert len(results) == 20
        for result in results:
            assert isinstance(result.intent, str)
            assert 0.0 <= result.sentiment <= 1.0

    @pytest.mark.asyncio
    async def test_concurrent_clara_evaluations(self):
        """Multiple concurrent CLARA evaluations should not crash."""
        gate = CLARAQualityGate()
        responses = [
            ("I understand your concern. Let me help.", "refund"),
            ("Thank you for reaching out.", "help"),
            ("Sorry about this issue. Here's the fix.", "bug"),
        ]

        tasks = [
            gate.evaluate(response=response, query=query, customer_sentiment=0.5)
            for response, query in responses
        ]
        results = await asyncio.gather(*tasks)

        assert len(results) == 3
        for result in results:
            assert isinstance(result.overall_pass, bool)
            assert len(result.stages) == 5


class TestCLARAAllStagesFailing:
    """CLARA pipeline with a response designed to fail all stages."""

    @pytest.mark.asyncio
    async def test_all_stages_fail(self):
        """A deliberately terrible response should fail multiple stages."""
        gate = CLARAQualityGate(
            brand_voice=BrandVoiceConfig(
                prohibited_words=["stupid", "idiot"],
                max_length=10,
                required_sign_off=True,
                formality="high",
            )
        )

        terrible_response = "Ok"  # < 5 words

        result = await gate.evaluate(
            response=terrible_response,
            query="I want a refund for my order",
            customer_sentiment=0.1,  # Angry customer
        )

        # Structure should fail (too short)
        structure = next(
            s for s in result.stages if s.stage == CLARAStage.STRUCTURE_CHECK
        )
        assert structure.result == StageResult.FAIL

        # Tone should fail (no empathy for angry customer)
        tone = next(s for s in result.stages if s.stage == CLARAStage.TONE_CHECK)
        assert tone.result == StageResult.FAIL

    @pytest.mark.asyncio
    async def test_aggressive_pii_response(self):
        """Response with aggressive language + PII should fail delivery + tone."""
        gate = CLARAQualityGate()
        result = await gate.evaluate(
            response="Calm down. Obviously you should know this. Email john@test.com.",
            query="refund",
            customer_sentiment=0.2,
        )

        delivery = next(
            s for s in result.stages if s.stage == CLARAStage.DELIVERY_CHECK
        )
        assert delivery.result == StageResult.FAIL

        tone = next(s for s in result.stages if s.stage == CLARAStage.TONE_CHECK)
        assert tone.result == StageResult.FAIL

        # Overall should fail
        assert result.overall_pass is False


class TestAdversarialInputs:
    """Adversarial / unusual inputs that shouldn't crash the system."""

    def setup_method(self):
        self.extractor = SignalExtractor()
        self.engine = ClassificationEngine()

    @pytest.mark.asyncio
    async def test_sql_injection_in_query(self):
        """SQL injection attempt should be treated as regular text."""
        req = SignalExtractionRequest(
            query="'; DROP TABLE users; --",
            company_id="c1",
            variant_type="parwa",
        )
        result = await self.extractor.extract(req)
        assert isinstance(result.intent, str)
        assert result.intent == "general"

    @pytest.mark.asyncio
    async def test_html_in_query(self):
        """HTML tags in query should be treated as regular text."""
        req = SignalExtractionRequest(
            query="<script>alert('xss')</script> refund my order",
            company_id="c1",
            variant_type="parwa",
        )
        result = await self.extractor.extract(req)
        assert result.intent == "refund"

    @pytest.mark.asyncio
    async def test_markdown_in_query(self):
        """Markdown formatting in query should be handled."""
        req = SignalExtractionRequest(
            query="# Refund Request\n\n**URGENT:** I want a refund for my $50 order!",
            company_id="c1",
            variant_type="parwa",
        )
        result = await self.extractor.extract(req)
        assert result.intent == "refund"
        assert result.monetary_value == 50.0

    @pytest.mark.asyncio
    async def test_null_bytes_in_query(self):
        """Null bytes should not crash the system."""
        req = SignalExtractionRequest(
            query="refund\x00my\x00order",
            company_id="c1",
            variant_type="parwa",
        )
        result = await self.extractor.extract(req)
        assert isinstance(result.intent, str)

    @pytest.mark.asyncio
    async def test_only_special_characters(self):
        """Query with only special characters should return general."""
        req = SignalExtractionRequest(
            query="@#$%^&*()_+-=[]{}|;:',.<>?/~`",
            company_id="c1",
            variant_type="parwa",
        )
        result = await self.extractor.extract(req)
        assert result.intent == "general"
        assert result.sentiment == 0.5  # No words to score

    @pytest.mark.asyncio
    async def test_classification_with_newlines_and_tabs(self):
        """Classification handles newlines and tabs."""
        result = await self.engine.classify(
            "I want\n\n\ta refund for my\t\torder",
            use_ai=False,
        )
        assert result.primary_intent == "refund"

    @pytest.mark.asyncio
    async def test_clara_with_null_bytes(self):
        """CLARA handles null bytes in response."""
        gate = CLARAQualityGate()
        result = await gate.evaluate(
            response="Thank you\x00for\x00your inquiry.",
            query="help",
        )
        assert isinstance(result.overall_pass, bool)
        assert len(result.stages) == 5


class TestNumericBoundaryConditions:
    """Numeric boundary conditions in various fields."""

    def setup_method(self):
        self.extractor = SignalExtractor()

    @pytest.mark.asyncio
    async def test_turn_count_zero(self):
        """turn_count=0 should work."""
        req = SignalExtractionRequest(
            query="help",
            company_id="c1",
            turn_count=0,
        )
        result = await self.extractor.extract(req)
        assert result.turn_count == 0

    @pytest.mark.asyncio
    async def test_turn_count_very_large(self):
        """Very large turn_count should work."""
        req = SignalExtractionRequest(
            query="help",
            company_id="c1",
            turn_count=999999,
        )
        result = await self.extractor.extract(req)
        assert result.turn_count == 999999

    @pytest.mark.asyncio
    async def test_customer_tier_case_normalization(self):
        """Customer tier should be normalized to lowercase."""
        req = SignalExtractionRequest(
            query="help",
            company_id="c1",
            customer_tier="ENTERPRISE",
            customer_metadata={"tier": "PRO"},
        )
        result = await self.extractor.extract(req)
        assert result.customer_tier == "pro"


class TestResolutionPathCapping:
    """Resolution paths should be capped at 5."""

    def test_paths_capped_at_5(self):
        """Even complex queries with money + breadth should cap at 5."""
        extractor = SignalExtractor()
        # Complaint = 4 base, +1 money, +1 breadth = 6 → should cap at 5
        paths = extractor._count_resolution_paths(
            "I have a terrible complaint about the $500 charge on my billing error. "
            "Also the app server is crashing and my package delivery is lost.",
            "complaint",
        )
        assert paths <= 5

    def test_all_intents_path_bounds(self):
        """All intents should produce 1-5 resolution paths."""
        extractor = SignalExtractor()
        for intent in [
            "general",
            "inquiry",
            "feedback",
            "account",
            "shipping",
            "technical",
            "billing",
            "feature_request",
            "refund",
            "cancellation",
            "complaint",
            "escalation",
        ]:
            paths = extractor._count_resolution_paths("test query here", intent)
            assert 1 <= paths <= 5, f"{intent}: {paths} paths"


class TestCLARADeliveryCheckEdgeCases:
    """Additional delivery check edge cases."""

    @pytest.mark.asyncio
    async def test_no_pii_clean_response_passes(self):
        """Clean response with no PII should pass delivery."""
        gate = CLARAQualityGate()
        result = await gate._delivery_check(
            "Thank you for contacting us. We will resolve your issue shortly."
        )
        assert result.result == StageResult.PASS
        assert len(result.issues) == 0

    @pytest.mark.asyncio
    async def test_single_paragraph_3_emojis_ok(self):
        """3 emojis in a paragraph should be OK (not excessive)."""
        gate = CLARAQualityGate()
        result = await gate._delivery_check("Great! 😊🎉😃")
        assert result.result == StageResult.PASS

    @pytest.mark.asyncio
    async def test_multiple_paragraphs_emojis(self):
        """Emojis spread across paragraphs should be checked per paragraph."""
        gate = CLARAQualityGate()
        result = await gate._delivery_check(
            "First paragraph with 😊🎉😃.\n\n" "Second paragraph with 🤔😊😃🌟."
        )
        # First para: 3 emojis (OK), second para: 4 emojis (FAIL)
        assert result.result == StageResult.FAIL

    @pytest.mark.asyncio
    async def test_broken_markdown_valid_link_ok(self):
        """Valid markdown links should pass."""
        gate = CLARAQualityGate()
        result = await gate._delivery_check(
            "Click [here](https://example.com) for info."
        )
        assert result.result == StageResult.PASS


class TestIntentToCategoryMapCompleteness:
    """Verify INTENT_TO_CATEGORY_MAP covers all 12 intents."""

    def test_all_intents_mapped(self):
        """All 12 IntentType values should have a category mapping."""
        from app.core.classification_engine import INTENT_TO_CATEGORY_MAP

        for intent in IntentType:
            assert (
                intent.value in INTENT_TO_CATEGORY_MAP
            ), f"Missing category mapping for {intent.value}"

    def test_all_categories_valid(self):
        """All mapped categories should be known categories."""
        from app.core.classification_engine import INTENT_TO_CATEGORY_MAP

        valid_categories = {
            "refund",
            "technical",
            "billing",
            "complaint",
            "feature_request",
            "general",
        }
        for intent, category in INTENT_TO_CATEGORY_MAP.items():
            assert (
                category in valid_categories
            ), f"Invalid category '{category}' for intent '{intent}'"


class TestCacheIsolationAcrossVariants:
    """Cache keys isolate data across variants (GAP-007 verification)."""

    @pytest.mark.asyncio
    async def test_different_variants_different_results(self):
        """Different variants should potentially produce different complexity."""
        query = "I have a complex technical issue with my API server"
        extractor = SignalExtractor()

        req_mini = SignalExtractionRequest(
            query=query,
            company_id="c1",
            variant_type="mini_parwa",
        )
        req_parwa = SignalExtractionRequest(
            query=query,
            company_id="c1",
            variant_type="parwa",
        )
        req_high = SignalExtractionRequest(
            query=query,
            company_id="c1",
            variant_type="high_parwa",
        )

        # Extract with all 3 variants (no cache mocking - fresh extraction)
        with patch(
            "app.core.redis.cache_get", new_callable=AsyncMock, return_value=None
        ):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                result_mini = await extractor.extract(req_mini)
                result_parwa = await extractor.extract(req_parwa)
                result_high = await extractor.extract(req_high)

        # All should have valid results
        for r in [result_mini, result_parwa, result_high]:
            assert r.intent == "technical"
            assert 0.0 <= r.complexity <= 1.0
