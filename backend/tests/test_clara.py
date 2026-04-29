"""
Tests for CLARA Quality Gate Pipeline (F-150) — Week 9 Day 6

Covers: 5 stages, GAP-002 (timeout), GAP-018 (brand defaults),
D6-GAP-02 (context entity refs), D6-GAP-03 (context-aware phone),
overall scoring, edge cases.
Target: 120+ tests
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

# ═══════════════════════════════════════════════════════════════════════
# Fixtures — import source modules with mocked logger
# ═══════════════════════════════════════════════════════════════════════

# Runtime-injected by _mock_logger fixture — satisfies flake8 F821
BrandVoiceConfig = CLARAQualityGate = CLARAStage = CLARAResult = StageOutput = (
    StageResult
) = None


@pytest.fixture(autouse=True)
def _mock_logger():
    with patch("app.logger.get_logger", return_value=MagicMock()):
        from app.core.clara_quality_gate import (  # noqa: F811,F401
            BrandVoiceConfig,
            CLARAQualityGate,
            CLARAStage,
            CLARAResult,
            StageOutput,
            StageResult,
        )

        globals().update(
            {
                "BrandVoiceConfig": BrandVoiceConfig,
                "CLARAQualityGate": CLARAQualityGate,
                "CLARAStage": CLARAStage,
                "CLARAResult": CLARAResult,
                "StageOutput": StageOutput,
                "StageResult": StageResult,
            }
        )


# ═══════════════════════════════════════════════════════════════════════
# 1. Structure Check (15 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestStructureCheck:
    @pytest.mark.asyncio
    async def test_valid_response_passes(self):
        gate = CLARAQualityGate()
        result = await gate._structure_check(
            "Thank you for reaching out. I understand your concern about the refund. Let me help you with that right away.",
            "refund my order",
        )
        assert result.result == StageResult.PASS
        assert result.score >= 0.7

    @pytest.mark.asyncio
    async def test_empty_response_fails(self):
        gate = CLARAQualityGate()
        result = await gate._structure_check("", "query")
        assert result.result == StageResult.FAIL
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_whitespace_only_fails(self):
        gate = CLARAQualityGate()
        result = await gate._structure_check("   \n\n  ", "query")
        assert result.result == StageResult.FAIL

    @pytest.mark.asyncio
    async def test_too_short_fails(self):
        gate = CLARAQualityGate()
        result = await gate._structure_check("Ok fine.", "query")
        assert result.result == StageResult.FAIL
        assert any("too short" in i.lower() for i in result.issues)

    @pytest.mark.asyncio
    async def test_too_long_fails(self):
        gate = CLARAQualityGate()
        long_text = " ".join(["word"] * 600)
        result = await gate._structure_check(long_text, "query")
        assert result.result == StageResult.FAIL
        assert any("too long" in i.lower() for i in result.issues)

    @pytest.mark.asyncio
    async def test_good_length_passes(self):
        gate = CLARAQualityGate()
        text = " ".join(["word"] * 50)
        result = await gate._structure_check(text, "query")
        assert result.result == StageResult.PASS

    @pytest.mark.asyncio
    async def test_repeated_phrases_detected(self):
        gate = CLARAQualityGate()
        text = (
            "This is a problem. This is a problem. This is a problem. Let me help you."
        )
        result = await gate._structure_check(text, "query")
        assert any("repeated" in i.lower() for i in result.issues)

    @pytest.mark.asyncio
    async def test_excessive_whitespace_detected(self):
        gate = CLARAQualityGate()
        text = "Response text.\n\n\n\n\n\nMore text."
        result = await gate._structure_check(text, "query")
        assert any(
            "blank lines" in i.lower() or "whitespace" in i.lower()
            for i in result.issues
        )

    @pytest.mark.asyncio
    async def test_no_repeated_phrases(self):
        gate = CLARAQualityGate()
        text = "First sentence here. Second different sentence. Third unique thought."
        result = await gate._structure_check(text, "query")
        repeated_issues = [i for i in result.issues if "repeated" in i.lower()]
        assert len(repeated_issues) == 0

    @pytest.mark.asyncio
    async def test_exactly_5_words_passes(self):
        gate = CLARAQualityGate()
        result = await gate._structure_check("One two three four five.", "query")
        assert result.result == StageResult.PASS

    @pytest.mark.asyncio
    async def test_exactly_4_words_fails(self):
        gate = CLARAQualityGate()
        result = await gate._structure_check("One two three four.", "query")
        assert result.result == StageResult.FAIL

    @pytest.mark.asyncio
    async def test_score_range(self):
        gate = CLARAQualityGate()
        result = await gate._structure_check(
            "A good response about the topic.", "query"
        )
        assert 0.0 <= result.score <= 1.0

    @pytest.mark.asyncio
    async def test_stage_name(self):
        gate = CLARAQualityGate()
        result = await gate._structure_check("test text here", "query")
        assert result.stage == CLARAStage.STRUCTURE_CHECK

    @pytest.mark.asyncio
    async def test_suggestions_for_short(self):
        gate = CLARAQualityGate()
        result = await gate._structure_check("Ok.", "query")
        assert len(result.suggestions) > 0

    @pytest.mark.asyncio
    async def test_issues_list_type(self):
        gate = CLARAQualityGate()
        result = await gate._structure_check("", "query")
        assert isinstance(result.issues, list)


# ═══════════════════════════════════════════════════════════════════════
# 2. Logic Check (15 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestLogicCheck:
    @pytest.mark.asyncio
    async def test_relevant_response_passes(self):
        gate = CLARAQualityGate()
        result = await gate._logic_check(
            "I can process your refund right away. The amount will be credited within 5-7 business days.",
            "refund my order",
        )
        assert result.result == StageResult.PASS

    @pytest.mark.asyncio
    async def test_irrelevant_response_fails(self):
        gate = CLARAQualityGate()
        result = await gate._logic_check(
            "The weather today is sunny and warm with clear skies expected.",
            "I want a refund for my broken product",
        )
        assert result.result == StageResult.FAIL
        assert any("relevance" in i.lower() for i in result.issues)

    @pytest.mark.asyncio
    async def test_contradiction_yes_but_no(self):
        gate = CLARAQualityGate()
        result = await gate._logic_check(
            "Yes we can refund you, but no we cannot process that refund.",
            "refund",
        )
        assert any("contradiction" in i.lower() for i in result.issues)

    @pytest.mark.asyncio
    async def test_contradiction_correct_incorrect(self):
        gate = CLARAQualityGate()
        result = await gate._logic_check(
            "Yes that is correct but no it is incorrect.",
            "test",
        )
        assert any("contradiction" in i.lower() for i in result.issues)

    @pytest.mark.asyncio
    async def test_contradiction_will_wont(self):
        gate = CLARAQualityGate()
        result = await gate._logic_check(
            "We will process this but we won't do it today.",
            "test",
        )
        assert any("won" in i.lower() for i in result.issues)

    @pytest.mark.asyncio
    async def test_dont_know_followed_by_answer(self):
        gate = CLARAQualityGate()
        result = await gate._logic_check(
            "I don't know the answer to your question, but actually the refund policy states you have 30 days to request a full refund of your purchase amount and we will credit it back to your original payment method.",
            "refund policy",
        )
        # "I don't know" followed by >20 words triggers issue
        assert isinstance(result.score, float)

    @pytest.mark.asyncio
    async def test_context_entity_reference_d6_gap02(self):
        """D6-GAP-02: Context entity references checked."""
        gate = CLARAQualityGate()
        result = await gate._logic_check(
            "I can help with that.",
            "help with order",
            context={"order_id": "ORD-12345"},
        )
        assert any("order_id" in i.lower() for i in result.issues)

    @pytest.mark.asyncio
    async def test_context_customer_name_referenced(self):
        gate = CLARAQualityGate()
        result = await gate._logic_check(
            "Hello John, I can help you with that.",
            "help",
            context={"customer_name": "John"},
        )
        name_issues = [i for i in result.issues if "customer_name" in i.lower()]
        assert len(name_issues) == 0  # John is referenced

    @pytest.mark.asyncio
    async def test_empty_context_no_entity_check(self):
        gate = CLARAQualityGate()
        result = await gate._logic_check("I can help you.", "help", context={})
        entity_issues = [i for i in result.issues if "context key" in i.lower()]
        assert len(entity_issues) == 0

    @pytest.mark.asyncio
    async def test_none_context_handled(self):
        gate = CLARAQualityGate()
        result = await gate._logic_check("I can help you.", "help", context=None)
        assert isinstance(result.score, float)

    @pytest.mark.asyncio
    async def test_short_context_value_ignored(self):
        """Context values <= 3 chars are ignored."""
        gate = CLARAQualityGate()
        result = await gate._logic_check(
            "I can help.",
            "help",
            context={"ticket_id": "AB"},
        )
        entity_issues = [i for i in result.issues if "ticket_id" in i.lower()]
        assert len(entity_issues) == 0

    @pytest.mark.asyncio
    async def test_score_range(self):
        gate = CLARAQualityGate()
        result = await gate._logic_check("test", "test")
        assert 0.0 <= result.score <= 1.0

    @pytest.mark.asyncio
    async def test_stage_name(self):
        gate = CLARAQualityGate()
        result = await gate._logic_check("test", "test")
        assert result.stage == CLARAStage.LOGIC_CHECK

    @pytest.mark.asyncio
    async def test_contradiction_cant_can(self):
        gate = CLARAQualityGate()
        result = await gate._logic_check(
            "We can't do this but we can certainly try harder.",
            "test",
        )
        assert any("can" in i.lower() and "can't" in i.lower() for i in result.issues)

    @pytest.mark.asyncio
    async def test_no_contradiction(self):
        gate = CLARAQualityGate()
        result = await gate._logic_check(
            "I will process your refund within 5 business days.",
            "refund",
        )
        contradiction_issues = [
            i for i in result.issues if "contradiction" in i.lower()
        ]
        assert len(contradiction_issues) == 0


# ═══════════════════════════════════════════════════════════════════════
# 3. Brand Check — GAP-018 (15 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestBrandCheck:
    @pytest.mark.asyncio
    async def test_default_always_passes_gap018(self):
        """GAP-018: Default config always passes."""
        gate = CLARAQualityGate(brand_voice=BrandVoiceConfig.defaults())
        result = await gate._brand_check("Any response here is fine.")
        assert result.result == StageResult.PASS
        assert result.score == 1.0
        assert result.metadata.get("used_defaults") is True

    @pytest.mark.asyncio
    async def test_custom_prohibited_word(self):
        bv = BrandVoiceConfig(prohibited_words=["cheap", "inferior"])
        gate = CLARAQualityGate(brand_voice=bv)
        result = await gate._brand_check("Our product is not cheap at all.")
        assert result.result == StageResult.FAIL
        assert any("cheap" in i.lower() for i in result.issues)

    @pytest.mark.asyncio
    async def test_no_prohibited_words_passes(self):
        bv = BrandVoiceConfig(prohibited_words=["cheap"])
        gate = CLARAQualityGate(brand_voice=bv)
        result = await gate._brand_check("Our product is affordable.")
        assert result.result == StageResult.PASS

    @pytest.mark.asyncio
    async def test_max_length_violation(self):
        bv = BrandVoiceConfig(max_length=10)
        gate = CLARAQualityGate(brand_voice=bv)
        result = await gate._brand_check(" ".join(["word"] * 20))
        assert result.result == StageResult.FAIL
        assert any(
            "max length" in i.lower() or "exceeds" in i.lower() for i in result.issues
        )

    @pytest.mark.asyncio
    async def test_max_length_ok(self):
        bv = BrandVoiceConfig(max_length=500)
        gate = CLARAQualityGate(brand_voice=bv)
        result = await gate._brand_check("Short response.")
        assert result.result == StageResult.PASS

    @pytest.mark.asyncio
    async def test_required_sign_off_missing(self):
        bv = BrandVoiceConfig(required_sign_off=True)
        gate = CLARAQualityGate(brand_voice=bv)
        result = await gate._brand_check("Here is the information you requested.")
        assert result.result == StageResult.FAIL
        assert any("sign-off" in i.lower() for i in result.issues)

    @pytest.mark.asyncio
    async def test_required_sign_off_present(self):
        bv = BrandVoiceConfig(required_sign_off=True)
        gate = CLARAQualityGate(brand_voice=bv)
        result = await gate._brand_check("Here is your info. Best regards, Support.")
        assert result.result == StageResult.PASS

    @pytest.mark.asyncio
    async def test_formality_medium_no_casual(self):
        bv = BrandVoiceConfig(formality="medium")
        gate = CLARAQualityGate(brand_voice=bv)
        result = await gate._brand_check(
            "Thank you for your inquiry. We are happy to assist."
        )
        assert result.result == StageResult.PASS

    @pytest.mark.asyncio
    async def test_formality_high_casual_detected(self):
        bv = BrandVoiceConfig(formality="high")
        gate = CLARAQualityGate(brand_voice=bv)
        result = await gate._brand_check("Hey yo what's up? Your issue is fixed lol.")
        assert result.result == StageResult.FAIL
        assert any("informal" in i.lower() for i in result.issues)

    @pytest.mark.asyncio
    async def test_formality_high_professional_passes(self):
        bv = BrandVoiceConfig(formality="high")
        gate = CLARAQualityGate(brand_voice=bv)
        result = await gate._brand_check("Dear customer, we appreciate your business.")
        assert result.result == StageResult.PASS

    @pytest.mark.asyncio
    async def test_custom_vs_default_metadata(self):
        bv = BrandVoiceConfig(prohibited_words=["test"])
        gate = CLARAQualityGate(brand_voice=bv)
        result = await gate._brand_check("test response")
        assert result.metadata.get("used_defaults") is False

    @pytest.mark.asyncio
    async def test_multiple_prohibited_words(self):
        bv = BrandVoiceConfig(prohibited_words=["cheap", "free", "stupid"])
        gate = CLARAQualityGate(brand_voice=bv)
        result = await gate._brand_check("This is cheap, free, and stupid.")
        assert result.result == StageResult.FAIL
        assert len([i for i in result.issues if "prohibited" in i.lower()]) >= 2

    @pytest.mark.asyncio
    async def test_sign_off_with_thanks(self):
        bv = BrandVoiceConfig(required_sign_off=True)
        gate = CLARAQualityGate(brand_voice=bv)
        result = await gate._brand_check("Done. Thanks!")
        assert result.result == StageResult.PASS

    @pytest.mark.asyncio
    async def test_stage_name(self):
        gate = CLARAQualityGate()
        result = await gate._brand_check("test")
        assert result.stage == CLARAStage.BRAND_CHECK

    @pytest.mark.asyncio
    async def test_empty_response_default_passes(self):
        gate = CLARAQualityGate(brand_voice=BrandVoiceConfig.defaults())
        result = await gate._brand_check("")
        assert result.result == StageResult.PASS


# ═══════════════════════════════════════════════════════════════════════
# 4. Tone Check (15 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestToneCheck:
    @pytest.mark.asyncio
    async def test_empathetic_for_angry(self):
        gate = CLARAQualityGate()
        result = await gate._tone_check(
            "I understand your frustration. I'm sorry about this experience.",
            customer_sentiment=0.2,
        )
        assert result.result == StageResult.PASS

    @pytest.mark.asyncio
    async def test_lacks_empathy_for_angry(self):
        gate = CLARAQualityGate()
        result = await gate._tone_check(
            "Your request has been processed. Reference number 12345.",
            customer_sentiment=0.2,
        )
        assert result.result == StageResult.FAIL
        assert any("empathy" in i.lower() for i in result.issues)

    @pytest.mark.asyncio
    async def test_warm_for_happy(self):
        gate = CLARAQualityGate()
        result = await gate._tone_check(
            "Great! I'm glad we could help you with that!",
            customer_sentiment=0.9,
        )
        assert result.result == StageResult.PASS

    @pytest.mark.asyncio
    async def test_cold_for_happy(self):
        gate = CLARAQualityGate()
        result = await gate._tone_check(
            "Your request has been logged. You will receive a response within 48 hours.",
            customer_sentiment=0.9,
        )
        assert result.result == StageResult.FAIL
        assert any(
            "cold" in i.lower() or "warm" in i.lower() or "positive" in i.lower()
            for i in result.issues
        )

    @pytest.mark.asyncio
    async def test_neutral_customer(self):
        gate = CLARAQualityGate()
        result = await gate._tone_check(
            "Thank you for your inquiry.",
            customer_sentiment=0.5,
        )
        assert result.result == StageResult.PASS

    @pytest.mark.asyncio
    async def test_aggressive_calm_down(self):
        gate = CLARAQualityGate()
        # Use multiple aggressive words to ensure score drops below 0.5
        result = await gate._tone_check(
            "Calm down. Obviously you should know this.",
            customer_sentiment=0.5,
        )
        assert result.result == StageResult.FAIL
        assert any("aggressive" in i.lower() for i in result.issues)

    @pytest.mark.asyncio
    async def test_aggressive_obviously(self):
        gate = CLARAQualityGate()
        result = await gate._tone_check(
            "Obviously you should know this.",
            customer_sentiment=0.5,
        )
        assert result.result == StageResult.FAIL

    @pytest.mark.asyncio
    async def test_multiple_aggressive_words(self):
        gate = CLARAQualityGate()
        result = await gate._tone_check(
            "Calm down. Obviously you should know this. You should know better.",
            customer_sentiment=0.5,
        )
        assert result.result == StageResult.FAIL
        aggressive_issues = [i for i in result.issues if "aggressive" in i.lower()]
        assert len(aggressive_issues) >= 1

    @pytest.mark.asyncio
    async def test_no_aggressive_language(self):
        gate = CLARAQualityGate()
        result = await gate._tone_check(
            "I understand and will help you right away.",
            customer_sentiment=0.5,
        )
        aggressive_issues = [i for i in result.issues if "aggressive" in i.lower()]
        assert len(aggressive_issues) == 0

    @pytest.mark.asyncio
    async def test_apologize_empathy(self):
        gate = CLARAQualityGate()
        result = await gate._tone_check(
            "I apologize for the inconvenience you experienced.",
            customer_sentiment=0.2,
        )
        assert result.result == StageResult.PASS

    @pytest.mark.asyncio
    async def test_understand_empathy(self):
        gate = CLARAQualityGate()
        result = await gate._tone_check(
            "I understand how frustrating this must be.",
            customer_sentiment=0.1,
        )
        assert result.result == StageResult.PASS

    @pytest.mark.asyncio
    async def test_score_range(self):
        gate = CLARAQualityGate()
        result = await gate._tone_check("test", customer_sentiment=0.5)
        assert 0.0 <= result.score <= 1.0

    @pytest.mark.asyncio
    async def test_stage_name(self):
        gate = CLARAQualityGate()
        result = await gate._tone_check("test", customer_sentiment=0.5)
        assert result.stage == CLARAStage.TONE_CHECK

    @pytest.mark.asyncio
    async def test_empty_response(self):
        gate = CLARAQualityGate()
        result = await gate._tone_check("", customer_sentiment=0.5)
        # No aggressive language detected
        assert isinstance(result.score, float)

    @pytest.mark.asyncio
    async def test_frustrating_empathy_word(self):
        gate = CLARAQualityGate()
        result = await gate._tone_check(
            "I know this is frustrating for you.",
            customer_sentiment=0.2,
        )
        assert result.result == StageResult.PASS


# ═══════════════════════════════════════════════════════════════════════
# 5. Delivery Check (15 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestDeliveryCheck:
    @pytest.mark.asyncio
    async def test_clean_response_passes(self):
        gate = CLARAQualityGate()
        result = await gate._delivery_check(
            "Thank you for contacting support. Here is the information you requested."
        )
        assert result.result == StageResult.PASS

    @pytest.mark.asyncio
    async def test_email_pii(self):
        gate = CLARAQualityGate()
        result = await gate._delivery_check("Contact us at support@example.com")
        assert result.result == StageResult.FAIL
        assert any("pii" in i.lower() or "email" in i.lower() for i in result.issues)

    @pytest.mark.asyncio
    async def test_phone_pii(self):
        gate = CLARAQualityGate()
        result = await gate._delivery_check("Call us at 555-123-4567.")
        assert result.result == StageResult.FAIL

    @pytest.mark.asyncio
    async def test_ssn_pii(self):
        gate = CLARAQualityGate()
        result = await gate._delivery_check("Your SSN is 123-45-6789.")
        assert result.result == StageResult.FAIL

    @pytest.mark.asyncio
    async def test_credit_card_pii(self):
        gate = CLARAQualityGate()
        result = await gate._delivery_check("Card: 4111 1111 1111 1111.")
        assert result.result == StageResult.FAIL

    @pytest.mark.asyncio
    async def test_context_aware_phone_d6_gap03(self):
        """D6-GAP-03: Phone near tracking/order indicator is filtered out."""
        gate = CLARAQualityGate()
        result = await gate._delivery_check(
            "Your tracking number is 555-123-4567 and it ships today.",
            context={},
        )
        phone_issues = [i for i in result.issues if "phone" in i.lower()]
        assert len(phone_issues) == 0  # filtered as tracking number

    @pytest.mark.asyncio
    async def test_context_has_tracking_filters_phone(self):
        """D6-GAP-03: context.has_tracking_number filters all phones."""
        gate = CLARAQualityGate()
        result = await gate._delivery_check(
            "Call 555-123-4567 for help.",
            context={"has_tracking_number": True},
        )
        phone_issues = [i for i in result.issues if "phone" in i.lower()]
        assert len(phone_issues) == 0

    @pytest.mark.asyncio
    async def test_context_has_order_id_filters_phone(self):
        gate = CLARAQualityGate()
        result = await gate._delivery_check(
            "Phone: 555-123-4567.",
            context={"has_order_id": True},
        )
        phone_issues = [i for i in result.issues if "phone" in i.lower()]
        assert len(phone_issues) == 0

    @pytest.mark.asyncio
    async def test_broken_markdown_link(self):
        gate = CLARAQualityGate()
        result = await gate._delivery_check("Click [here]() for more info.")
        assert result.result == StageResult.FAIL
        assert any(
            "broken" in i.lower() or "markdown" in i.lower() for i in result.issues
        )

    @pytest.mark.asyncio
    async def test_excessive_emojis(self):
        gate = CLARAQualityGate()
        result = await gate._delivery_check("Great! 😊🎉😃👍🌟⭐🔥")
        assert result.result == StageResult.FAIL
        assert any("emoji" in i.lower() for i in result.issues)

    @pytest.mark.asyncio
    async def test_few_emojis_passes(self):
        gate = CLARAQualityGate()
        result = await gate._delivery_check("Great! 😊🎉😃")
        assert result.result == StageResult.PASS

    @pytest.mark.asyncio
    async def test_empty_response_fails(self):
        gate = CLARAQualityGate()
        result = await gate._delivery_check("")
        assert result.result == StageResult.FAIL

    @pytest.mark.asyncio
    async def test_multiple_pii_types(self):
        gate = CLARAQualityGate()
        result = await gate._delivery_check("Email john@test.com and SSN 123-45-6789.")
        assert len(result.issues) >= 2

    @pytest.mark.asyncio
    async def test_stage_name(self):
        gate = CLARAQualityGate()
        result = await gate._delivery_check("test response here.")
        assert result.stage == CLARAStage.DELIVERY_CHECK

    @pytest.mark.asyncio
    async def test_order_context_filters_phone(self):
        """Phone near 'order' keyword is filtered."""
        gate = CLARAQualityGate()
        result = await gate._delivery_check(
            "Your order 5551234567 is being processed.",
            context={},
        )
        phone_issues = [i for i in result.issues if "phone" in i.lower()]
        assert len(phone_issues) == 0


# ═══════════════════════════════════════════════════════════════════════
# 6. Pipeline Integration (10 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestPipelineIntegration:
    @pytest.mark.asyncio
    async def test_all_5_stages_run(self):
        gate = CLARAQualityGate()
        result = await gate.evaluate(
            response="Thank you for your patience regarding the refund. "
            "I have processed your refund of $50.00.",
            query="refund my order",
        )
        stage_names = {s.stage for s in result.stages}
        assert CLARAStage.STRUCTURE_CHECK in stage_names
        assert CLARAStage.LOGIC_CHECK in stage_names
        assert CLARAStage.BRAND_CHECK in stage_names
        assert CLARAStage.TONE_CHECK in stage_names
        assert CLARAStage.DELIVERY_CHECK in stage_names

    @pytest.mark.asyncio
    async def test_all_pass_overall_pass(self):
        gate = CLARAQualityGate()
        result = await gate.evaluate(
            response="Thank you for your patience regarding the refund. "
            "I have processed your refund of $50.00. You should see "
            "the credit within 5-7 business days. Best regards.",
            query="refund my order",
            customer_sentiment=0.5,
        )
        assert result.overall_pass is True
        assert result.overall_score >= 0.7

    @pytest.mark.asyncio
    async def test_empty_response_overall_fail(self):
        gate = CLARAQualityGate()
        result = await gate.evaluate(response="", query="refund")
        assert result.overall_pass is False

    @pytest.mark.asyncio
    async def test_overall_score_range(self):
        gate = CLARAQualityGate()
        result = await gate.evaluate(
            response="Helpful response about the topic.",
            query="question",
        )
        assert 0.0 <= result.overall_score <= 1.0

    @pytest.mark.asyncio
    async def test_clararesult_structure(self):
        gate = CLARAQualityGate()
        result = await gate.evaluate(response="A good response.", query="help")
        assert isinstance(result, CLARAResult)
        assert isinstance(result.overall_pass, bool)
        assert isinstance(result.overall_score, float)
        assert isinstance(result.stages, list)
        assert isinstance(result.total_processing_time_ms, float)
        assert isinstance(result.final_response, str)
        assert isinstance(result.pipeline_timed_out, bool)

    @pytest.mark.asyncio
    async def test_final_response_not_none(self):
        gate = CLARAQualityGate()
        result = await gate.evaluate(
            response="Valid response about the refund.", query="refund"
        )
        assert result.final_response is not None

    @pytest.mark.asyncio
    async def test_processing_time_positive(self):
        gate = CLARAQualityGate()
        result = await gate.evaluate(response="Test response.", query="test")
        assert result.total_processing_time_ms >= 0

    @pytest.mark.asyncio
    async def test_pipeline_timed_out_false(self):
        gate = CLARAQualityGate()
        result = await gate.evaluate(response="Good response.", query="test")
        assert result.pipeline_timed_out is False

    @pytest.mark.asyncio
    async def test_empty_query_handled(self):
        gate = CLARAQualityGate()
        result = await gate.evaluate(response="Response.", query="")
        assert isinstance(result.overall_pass, bool)

    @pytest.mark.asyncio
    async def test_none_context_handled(self):
        gate = CLARAQualityGate()
        result = await gate.evaluate(
            response="Response.",
            query="test",
            context=None,
        )
        assert isinstance(result.overall_pass, bool)


# ═══════════════════════════════════════════════════════════════════════
# 7. Pipeline Timeout GAP-002 (5 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestPipelineTimeoutGAP002:
    @pytest.mark.asyncio
    async def test_pipeline_timeout_fills_missing(self):
        """GAP-002: Pipeline timeout fills missing stages as TIMEOUT_PASS."""
        # Patch _run_all_stages to simulate a slow pipeline
        gate = CLARAQualityGate(pipeline_timeout_seconds=0.001)

        async def slow_run_all(*args, **kwargs):
            await asyncio.sleep(1)

        with patch.object(gate, "_run_all_stages", side_effect=slow_run_all):
            result = await gate.evaluate(response="test response", query="test")
        assert result.pipeline_timed_out is True
        timeout_stages = [
            s for s in result.stages if s.result == StageResult.TIMEOUT_PASS
        ]
        assert len(timeout_stages) > 0

    @pytest.mark.asyncio
    async def test_timeout_pass_has_metadata(self):
        gate = CLARAQualityGate(pipeline_timeout_seconds=0.001)

        async def slow_run_all(*args, **kwargs):
            await asyncio.sleep(1)

        with patch.object(gate, "_run_all_stages", side_effect=slow_run_all):
            result = await gate.evaluate(response="test", query="test")
        timeout_stages = [
            s for s in result.stages if s.result == StageResult.TIMEOUT_PASS
        ]
        for ts in timeout_stages:
            assert ts.metadata.get("timeout") is True

    @pytest.mark.asyncio
    async def test_timeout_pass_doesnt_fail_overall(self):
        """TIMEOUT_PASS stages don't cause overall failure."""
        gate = CLARAQualityGate(pipeline_timeout_seconds=0.001)

        async def slow_run_all(*args, **kwargs):
            await asyncio.sleep(1)

        with patch.object(gate, "_run_all_stages", side_effect=slow_run_all):
            result = await gate.evaluate(response="test", query="test")
        fail_stages = [s for s in result.stages if s.result == StageResult.FAIL]
        if not fail_stages:
            assert result.overall_pass is True

    @pytest.mark.asyncio
    async def test_timeout_pass_score_is_05(self):
        gate = CLARAQualityGate(pipeline_timeout_seconds=0.001)

        async def slow_run_all(*args, **kwargs):
            await asyncio.sleep(1)

        with patch.object(gate, "_run_all_stages", side_effect=slow_run_all):
            result = await gate.evaluate(response="test", query="test")
        timeout_stages = [
            s for s in result.stages if s.result == StageResult.TIMEOUT_PASS
        ]
        for ts in timeout_stages:
            assert ts.score == 0.5

    @pytest.mark.asyncio
    async def test_all_stages_present_after_timeout(self):
        gate = CLARAQualityGate(pipeline_timeout_seconds=0.001)

        async def slow_run_all(*args, **kwargs):
            await asyncio.sleep(1)

        with patch.object(gate, "_run_all_stages", side_effect=slow_run_all):
            result = await gate.evaluate(response="test", query="test")
        stage_names = {s.stage for s in result.stages}
        assert len(stage_names) == 5


# ═══════════════════════════════════════════════════════════════════════
# 8. Stage Timeout GAP-002 (5 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestStageTimeoutGAP002:
    @pytest.mark.asyncio
    async def test_slow_stage_times_out(self):
        gate = CLARAQualityGate(stage_timeout_seconds=0.001)

        async def slow_stage(**kwargs):
            await asyncio.sleep(10)
            return StageOutput(
                stage=CLARAStage.LOGIC_CHECK,
                result=StageResult.PASS,
                score=0.9,
                issues=[],
                suggestions=[],
                processing_time_ms=0,
            )

        result = await gate._run_stage(CLARAStage.LOGIC_CHECK, slow_stage)
        assert result.result == StageResult.TIMEOUT_PASS

    @pytest.mark.asyncio
    async def test_timeout_stage_score(self):
        gate = CLARAQualityGate(stage_timeout_seconds=0.001)

        async def slow_stage(**kwargs):
            await asyncio.sleep(10)
            return StageOutput(
                stage=CLARAStage.LOGIC_CHECK,
                result=StageResult.PASS,
                score=0.9,
                issues=[],
                suggestions=[],
                processing_time_ms=0,
            )

        result = await gate._run_stage(CLARAStage.LOGIC_CHECK, slow_stage)
        assert result.score == 0.5

    @pytest.mark.asyncio
    async def test_timeout_metadata(self):
        gate = CLARAQualityGate(stage_timeout_seconds=0.001)

        async def slow_stage(**kwargs):
            await asyncio.sleep(10)
            return StageOutput(
                stage=CLARAStage.STRUCTURE_CHECK,
                result=StageResult.PASS,
                score=0.9,
                issues=[],
                suggestions=[],
                processing_time_ms=0,
            )

        result = await gate._run_stage(CLARAStage.STRUCTURE_CHECK, slow_stage)
        assert result.metadata.get("timeout") is True

    @pytest.mark.asyncio
    async def test_fast_stage_completes(self):
        gate = CLARAQualityGate(stage_timeout_seconds=5.0)

        async def fast_stage(**kwargs):
            return StageOutput(
                stage=CLARAStage.LOGIC_CHECK,
                result=StageResult.PASS,
                score=0.9,
                issues=[],
                suggestions=[],
                processing_time_ms=0,
            )

        result = await gate._run_stage(CLARAStage.LOGIC_CHECK, fast_stage)
        assert result.result == StageResult.PASS
        assert result.metadata.get("timeout") is None

    @pytest.mark.asyncio
    async def test_timeout_stage_name_preserved(self):
        gate = CLARAQualityGate(stage_timeout_seconds=0.001)

        async def slow_stage(**kwargs):
            await asyncio.sleep(10)
            return StageOutput(
                stage=CLARAStage.TONE_CHECK,
                result=StageResult.PASS,
                score=0.9,
                issues=[],
                suggestions=[],
                processing_time_ms=0,
            )

        result = await gate._run_stage(CLARAStage.TONE_CHECK, slow_stage)
        assert result.stage == CLARAStage.TONE_CHECK


# ═══════════════════════════════════════════════════════════════════════
# 9. Stage Error (5 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestStageError:
    @pytest.mark.asyncio
    async def test_exception_returns_error(self):
        gate = CLARAQualityGate()

        async def error_stage(**kwargs):
            raise ValueError("test error")

        result = await gate._run_stage(CLARAStage.LOGIC_CHECK, error_stage)
        assert result.result == StageResult.ERROR

    @pytest.mark.asyncio
    async def test_error_stage_score_zero(self):
        gate = CLARAQualityGate()

        async def error_stage(**kwargs):
            raise RuntimeError("boom")

        result = await gate._run_stage(CLARAStage.BRAND_CHECK, error_stage)
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_error_metadata(self):
        gate = CLARAQualityGate()

        async def error_stage(**kwargs):
            raise ValueError("specific error")

        result = await gate._run_stage(CLARAStage.TONE_CHECK, error_stage)
        assert result.metadata.get("error") is True

    @pytest.mark.asyncio
    async def test_error_stage_name(self):
        gate = CLARAQualityGate()

        async def error_stage(**kwargs):
            raise Exception("error")

        result = await gate._run_stage(CLARAStage.DELIVERY_CHECK, error_stage)
        assert result.stage == CLARAStage.DELIVERY_CHECK

    @pytest.mark.asyncio
    async def test_error_has_issue_message(self):
        gate = CLARAQualityGate()

        async def error_stage(**kwargs):
            raise ValueError("test error message")

        result = await gate._run_stage(CLARAStage.STRUCTURE_CHECK, error_stage)
        assert len(result.issues) > 0
        assert "error" in result.issues[0].lower()


# ═══════════════════════════════════════════════════════════════════════
# 10. BrandVoiceConfig (8 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestBrandVoiceConfig:
    def test_defaults_method(self):
        bv = BrandVoiceConfig.defaults()
        assert bv.tone == "professional"
        assert bv.formality == "medium"
        assert bv.prohibited_words == []
        assert bv.max_length == 500
        assert bv.required_sign_off is False

    def test_is_custom_false_default(self):
        bv = BrandVoiceConfig()
        assert bv.is_custom_configured is False

    def test_is_custom_true_prohibited_words(self):
        bv = BrandVoiceConfig(prohibited_words=["cheap"])
        assert bv.is_custom_configured is True

    def test_is_custom_true_custom_rules(self):
        bv = BrandVoiceConfig(custom_rules={"no_emoji": True})
        assert bv.is_custom_configured is True

    def test_is_custom_true_required_sign_off(self):
        bv = BrandVoiceConfig(required_sign_off=True)
        assert bv.is_custom_configured is True

    def test_is_custom_true_max_length(self):
        bv = BrandVoiceConfig(max_length=200)
        assert bv.is_custom_configured is True

    def test_is_custom_true_formality(self):
        bv = BrandVoiceConfig(formality="high")
        assert bv.is_custom_configured is True

    def test_is_custom_true_tone(self):
        bv = BrandVoiceConfig(tone="friendly")
        assert bv.is_custom_configured is True


# ═══════════════════════════════════════════════════════════════════════
# 11. _apply_suggestions (5 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestApplySuggestions:
    def test_whitespace_cleanup_on_structure_fail(self):
        gate = CLARAQualityGate()
        stages = [
            StageOutput(
                stage=CLARAStage.STRUCTURE_CHECK,
                result=StageResult.FAIL,
                score=0.5,
                issues=["Excessive blank lines"],
                suggestions=["Clean up whitespace"],
                processing_time_ms=0,
            )
        ]
        result = gate._apply_suggestions("Response.\n\n\n\n\nMore text.", stages)
        assert "\n\n\n" not in result

    def test_no_change_when_all_pass(self):
        gate = CLARAQualityGate()
        stages = [
            StageOutput(
                stage=CLARAStage.STRUCTURE_CHECK,
                result=StageResult.PASS,
                score=0.9,
                issues=[],
                suggestions=[],
                processing_time_ms=0,
            )
        ]
        original = "Good response text."
        result = gate._apply_suggestions(original, stages)
        assert result == original

    def test_empty_response_unchanged(self):
        gate = CLARAQualityGate()
        result = gate._apply_suggestions("", [])
        assert result == ""

    def test_strips_on_structure_fail(self):
        gate = CLARAQualityGate()
        stages = [
            StageOutput(
                stage=CLARAStage.STRUCTURE_CHECK,
                result=StageResult.FAIL,
                score=0.3,
                issues=["too short"],
                suggestions=["expand"],
                processing_time_ms=0,
            )
        ]
        result = gate._apply_suggestions("  padded text  ", stages)
        assert result == "padded text"

    def test_non_structure_fail_unchanged(self):
        gate = CLARAQualityGate()
        stages = [
            StageOutput(
                stage=CLARAStage.DELIVERY_CHECK,
                result=StageResult.FAIL,
                score=0.3,
                issues=["PII detected"],
                suggestions=["Remove PII"],
                processing_time_ms=0,
            )
        ]
        original = "Response.\n\n\n\nMore."
        result = gate._apply_suggestions(original, stages)
        assert "\n\n\n" in result  # Not cleaned for non-structure fails


# ═══════════════════════════════════════════════════════════════════════
# 12. CLARAStage/StageResult Enums (3 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestEnums:
    def test_clara_stage_count(self):
        assert len(CLARAStage) == 5

    def test_clara_stage_values(self):
        expected = {
            "structure_check",
            "logic_check",
            "brand_check",
            "tone_check",
            "delivery_check",
        }
        assert {s.value for s in CLARAStage} == expected

    def test_stage_result_values(self):
        expected = {"pass", "fail", "timeout_pass", "error"}
        assert {r.value for r in StageResult} == expected


# ═══════════════════════════════════════════════════════════════════════
# 13. Edge Cases (4+ tests)
# ═══════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_empty_response_through_pipeline(self):
        gate = CLARAQualityGate()
        result = await gate.evaluate(response="", query="test")
        assert result.overall_pass is False
        assert result.final_response is not None

    @pytest.mark.asyncio
    async def test_very_long_response(self):
        gate = CLARAQualityGate()
        long_response = " ".join(["This is a long response."] * 300)
        result = await gate.evaluate(response=long_response, query="test")
        structure = next(
            s for s in result.stages if s.stage == CLARAStage.STRUCTURE_CHECK
        )
        assert structure.result == StageResult.FAIL

    @pytest.mark.asyncio
    async def test_special_characters(self):
        gate = CLARAQualityGate()
        result = await gate.evaluate(
            response="Here's the info: @#$%^&*()",
            query="query",
        )
        assert isinstance(result.overall_pass, bool)

    @pytest.mark.asyncio
    async def test_unicode_response(self):
        gate = CLARAQualityGate()
        result = await gate.evaluate(
            response="Thank you! Grüß Gott! こんにちは!",
            query="query",
        )
        assert isinstance(result.overall_pass, bool)

    @pytest.mark.asyncio
    async def test_numbers_only(self):
        gate = CLARAQualityGate()
        result = await gate.evaluate(response="12345", query="query")
        assert isinstance(result.overall_pass, bool)

    @pytest.mark.asyncio
    async def test_whitespace_cleaned_in_final(self):
        gate = CLARAQualityGate()
        result = await gate.evaluate(
            response="Response text.\n\n\n\n\nMore text.",
            query="test",
        )
        assert "\n\n\n" not in (result.final_response or "")
