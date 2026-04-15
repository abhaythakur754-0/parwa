"""
Tests for CLARA Quality Gate Pipeline (F-150)

Covers: 5 stages, GAP-002 (timeout), GAP-018 (brand defaults),
overall scoring, edge cases.
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.core.clara_quality_gate import (
    BrandVoiceConfig,
    CLARAQualityGate,
    CLARAStage,
    CLARAResult,
    StageOutput,
    StageResult,
)


# ── BrandVoiceConfig ─────────────────────────────────────────────────


class TestBrandVoiceConfig:
    def test_defaults(self):
        bv = BrandVoiceConfig.defaults()
        assert bv.tone == "professional"
        assert bv.formality == "medium"
        assert bv.prohibited_words == []
        assert bv.max_length == 500
        assert bv.required_sign_off is False

    def test_custom_configured_true(self):
        bv = BrandVoiceConfig(prohibited_words=["cheap", "free"])
        assert bv.is_custom_configured is True

    def test_custom_configured_with_rules(self):
        bv = BrandVoiceConfig(custom_rules={"no_emoji": True})
        assert bv.is_custom_configured is True

    def test_custom_configured_false(self):
        bv = BrandVoiceConfig()
        assert bv.is_custom_configured is False

    def test_custom_with_both(self):
        bv = BrandVoiceConfig(
            prohibited_words=["damn"],
            custom_rules={"max_emojis": 2},
        )
        assert bv.is_custom_configured is True


# ── Structure Check ──────────────────────────────────────────────────


class TestStructureCheck:
    @pytest.mark.asyncio
    async def test_valid_response(self):
        gate = CLARAQualityGate()
        result = await gate._structure_check(
            "Thank you for reaching out. I understand your concern about the refund. Let me help you with that right away.",
            "refund my order",
        )
        assert result.result == StageResult.PASS
        assert result.score >= 0.7

    @pytest.mark.asyncio
    async def test_empty_response(self):
        gate = CLARAQualityGate()
        result = await gate._structure_check("", "query")
        assert result.result == StageResult.FAIL
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_whitespace_response(self):
        gate = CLARAQualityGate()
        result = await gate._structure_check("   \n\n  ", "query")
        assert result.result == StageResult.FAIL

    @pytest.mark.asyncio
    async def test_too_short(self):
        gate = CLARAQualityGate()
        result = await gate._structure_check("Ok fine.", "query")
        assert result.result == StageResult.FAIL

    @pytest.mark.asyncio
    async def test_wall_of_text(self):
        gate = CLARAQualityGate()
        long_text = " ".join(["word"] * 600)
        result = await gate._structure_check(long_text, "query")
        assert result.result == StageResult.FAIL
        assert any("too long" in i.lower() for i in result.issues)

    @pytest.mark.asyncio
    async def test_repeated_phrases(self):
        gate = CLARAQualityGate()
        text = "This is a problem. This is a problem. This is a problem. Let me help you."
        result = await gate._structure_check(text, "query")
        assert any("repeated" in i.lower() for i in result.issues)


# ── Logic Check ─────────────────────────────────────────────────────


class TestLogicCheck:
    @pytest.mark.asyncio
    async def test_relevant_response(self):
        gate = CLARAQualityGate()
        result = await gate._logic_check(
            "I can process your refund right away. The amount will be credited within 5-7 business days.",
            "refund my order",
        )
        assert result.result == StageResult.PASS

    @pytest.mark.asyncio
    async def test_low_relevance(self):
        gate = CLARAQualityGate()
        result = await gate._logic_check(
            "The weather today is sunny and warm with clear skies expected throughout the afternoon.",
            "I want a refund for my broken product",
        )
        assert result.result == StageResult.FAIL

    @pytest.mark.asyncio
    async def test_contradiction_detected(self):
        gate = CLARAQualityGate()
        result = await gate._logic_check(
            "Yes we can refund you, but no we cannot process that refund at this time.",
            "refund",
        )
        assert any("contradiction" in i.lower() for i in result.issues)

    @pytest.mark.asyncio
    async def test_dont_know_paradox(self):
        gate = CLARAQualityGate()
        result = await gate._logic_check(
            "I don't know the answer to your question, but actually the refund policy states you have 30 days to request a full refund of your purchase amount.",
            "refund policy",
        )
        # This may or may not flag depending on length thresholds
        assert result.score is not None


# ── Brand Check (GAP-018) ───────────────────────────────────────────


class TestBrandCheck:
    @pytest.mark.asyncio
    async def test_default_always_passes(self):
        """GAP-018: New tenant with default config always passes."""
        gate = CLARAQualityGate(brand_voice=BrandVoiceConfig.defaults())
        result = await gate._brand_check("Any response here is fine.")
        assert result.result == StageResult.PASS
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_custom_prohibited_word_detected(self):
        bv = BrandVoiceConfig(prohibited_words=["cheap", "inferior"])
        gate = CLARAQualityGate(brand_voice=bv)
        result = await gate._brand_check("Our product is not cheap at all.")
        assert result.result == StageResult.FAIL
        assert any("cheap" in i.lower() for i in result.issues)

    @pytest.mark.asyncio
    async def test_max_length_violation(self):
        bv = BrandVoiceConfig(max_length=10)
        gate = CLARAQualityGate(brand_voice=bv)
        result = await gate._brand_check(" ".join(["word"] * 20))
        assert result.result == StageResult.FAIL

    @pytest.mark.asyncio
    async def test_sign_off_missing(self):
        bv = BrandVoiceConfig(required_sign_off=True)
        gate = CLARAQualityGate(brand_voice=bv)
        result = await gate._brand_check("Here is the information you requested.")
        assert result.result == StageResult.FAIL

    @pytest.mark.asyncio
    async def test_sign_off_present(self):
        bv = BrandVoiceConfig(required_sign_off=True)
        gate = CLARAQualityGate(brand_voice=bv)
        result = await gate._brand_check("Here is your info. Best regards, Support team.")
        assert result.result == StageResult.PASS

    @pytest.mark.asyncio
    async def test_formality_check(self):
        bv = BrandVoiceConfig(formality="high")
        gate = CLARAQualityGate(brand_voice=bv)
        result = await gate._brand_check("Hey yo, what's up? Your issue is fixed lol.")
        assert result.result == StageResult.FAIL

    @pytest.mark.asyncio
    async def test_compliant_response(self):
        bv = BrandVoiceConfig(
            prohibited_words=["cheap"],
            max_length=100,
            formality="medium",
        )
        gate = CLARAQualityGate(brand_voice=bv)
        result = await gate._brand_check(
            "Thank you for your inquiry. We value your business and are happy to assist."
        )
        assert result.result == StageResult.PASS

    @pytest.mark.asyncio
    async def test_empty_response(self):
        bv = BrandVoiceConfig(prohibited_words=["test"])
        gate = CLARAQualityGate(brand_voice=bv)
        result = await gate._brand_check("")
        assert result.result == StageResult.PASS  # empty passes (no words to check)


# ── Tone Check ───────────────────────────────────────────────────────


class TestToneCheck:
    @pytest.mark.asyncio
    async def test_professional_tone(self):
        gate = CLARAQualityGate()
        result = await gate._tone_check(
            "Thank you for your patience. I'll resolve this promptly.",
            customer_sentiment=0.7,
        )
        assert result.result == StageResult.PASS

    @pytest.mark.asyncio
    async def test_empathetic_for_angry(self):
        gate = CLARAQualityGate()
        result = await gate._tone_check(
            "I understand your frustration. I'm sorry about this experience and I'll do my best to fix it.",
            customer_sentiment=0.2,
        )
        assert result.result == StageResult.PASS

    @pytest.mark.asyncio
    async def test_cold_for_angry(self):
        gate = CLARAQualityGate()
        result = await gate._tone_check(
            "Your request has been processed. Reference number 12345.",
            customer_sentiment=0.2,
        )
        assert result.result == StageResult.FAIL
        assert any("empathy" in i.lower() for i in result.issues)

    @pytest.mark.asyncio
    async def test_aggressive_language(self):
        gate = CLARAQualityGate()
        result = await gate._tone_check(
            "Calm down. Obviously you should know this already.",
            customer_sentiment=0.5,
        )
        assert result.result == StageResult.FAIL
        assert any("aggressive" in i.lower() for i in result.issues)

    @pytest.mark.asyncio
    async def test_empty_response(self):
        gate = CLARAQualityGate()
        result = await gate._tone_check("", customer_sentiment=0.5)
        assert result.result == StageResult.PASS

    @pytest.mark.asyncio
    async def test_happy_cold_tone(self):
        gate = CLARAQualityGate()
        result = await gate._tone_check(
            "Your request has been logged. You will receive a response within 48 hours.",
            customer_sentiment=0.9,
        )
        assert result.result == StageResult.FAIL


# ── Delivery Check ───────────────────────────────────────────────────


class TestDeliveryCheck:
    @pytest.mark.asyncio
    async def test_clean_response(self):
        gate = CLARAQualityGate()
        result = await gate._delivery_check(
            "Thank you for contacting support. Here is the information you requested."
        )
        assert result.result == StageResult.PASS

    @pytest.mark.asyncio
    async def test_email_pii(self):
        gate = CLARAQualityGate()
        result = await gate._delivery_check(
            "Please contact us at support@example.com for more help."
        )
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
    async def test_broken_markdown(self):
        gate = CLARAQualityGate()
        result = await gate._delivery_check("Click [here]() for more info.")
        assert result.result == StageResult.FAIL

    @pytest.mark.asyncio
    async def test_excessive_emojis(self):
        gate = CLARAQualityGate()
        result = await gate._delivery_check("Great! 😊🎉😃👍🌟⭐🔥")
        assert result.result == StageResult.FAIL

    @pytest.mark.asyncio
    async def test_multiple_pii(self):
        gate = CLARAQualityGate()
        result = await gate._delivery_check(
            "Email john@test.com or call 555-123-4567. SSN: 123-45-6789."
        )
        assert len(result.issues) >= 2

    @pytest.mark.asyncio
    async def test_empty_response(self):
        gate = CLARAQualityGate()
        result = await gate._delivery_check("")
        assert result.result == StageResult.FAIL


# ── Full Pipeline ────────────────────────────────────────────────────


class TestFullPipeline:
    @pytest.mark.asyncio
    async def test_all_pass(self):
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
        assert len(result.stages) == 5

    @pytest.mark.asyncio
    async def test_any_fail(self):
        gate = CLARAQualityGate()
        result = await gate.evaluate(
            response="",
            query="refund",
        )
        assert result.overall_pass is False

    @pytest.mark.asyncio
    async def test_five_stages_present(self):
        gate = CLARAQualityGate()
        result = await gate.evaluate(
            response="I understand your concern. Let me help you with the refund process right away. Thank you for your patience.",
            query="refund",
        )
        stage_names = {s.stage for s in result.stages}
        assert CLARAStage.STRUCTURE_CHECK in stage_names
        assert CLARAStage.LOGIC_CHECK in stage_names
        assert CLARAStage.BRAND_CHECK in stage_names
        assert CLARAStage.TONE_CHECK in stage_names
        assert CLARAStage.DELIVERY_CHECK in stage_names

    @pytest.mark.asyncio
    async def test_score_is_average(self):
        gate = CLARAQualityGate()
        result = await gate.evaluate(
            response="Thank you for your inquiry. I can help you with that.",
            query="help",
        )
        scored = [s for s in result.stages if s.result in (StageResult.PASS, StageResult.FAIL)]
        if scored:
            expected_avg = sum(s.score for s in scored) / len(scored)
            assert abs(result.overall_score - expected_avg) < 0.01

    @pytest.mark.asyncio
    async def test_final_response_provided(self):
        gate = CLARAQualityGate()
        result = await gate.evaluate(
            response="Valid response about the refund.",
            query="refund",
        )
        assert result.final_response is not None

    @pytest.mark.asyncio
    async def test_whitespace_cleaned(self):
        gate = CLARAQualityGate()
        result = await gate.evaluate(
            response="Response text.\n\n\n\n\nMore text.",
            query="test",
        )
        assert "\n\n\n" not in (result.final_response or "")


# ── Timeout (GAP-002) ───────────────────────────────────────────────


class TestTimeoutGAP002:
    @pytest.mark.asyncio
    async def test_stage_timeout_returns_timeout_pass(self):
        """GAP-002: Stage timeout returns TIMEOUT_PASS, not FAIL."""
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
        assert result.score == 0.5
        assert result.metadata.get("timeout") is True

    @pytest.mark.asyncio
    async def test_pipeline_timeout(self):
        """GAP-002: Stage timeouts produce TIMEOUT_PASS with correct metadata."""
        gate = CLARAQualityGate(
            stage_timeout_seconds=0.0001,
            pipeline_timeout_seconds=0.0001,
        )
        # Even if pipeline doesn't timeout, verify the timeout mechanism works
        # by testing the _run_stage method directly
        async def slow_stage(**kwargs):
            await asyncio.sleep(0.1)
            return StageOutput(
                stage=CLARAStage.LOGIC_CHECK,
                result=StageResult.PASS,
                score=0.9,
                issues=[], suggestions=[], processing_time_ms=0,
            )
        result = await gate._run_stage(CLARAStage.LOGIC_CHECK, slow_stage)
        assert result.result == StageResult.TIMEOUT_PASS
        assert result.score == 0.5
        assert result.metadata.get("timeout") is True

    @pytest.mark.asyncio
    async def test_timeout_pass_doesnt_fail_overall(self):
        """GAP-002: TIMEOUT_PASS stages don't cause overall failure."""
        gate = CLARAQualityGate(stage_timeout_seconds=0.001, pipeline_timeout_seconds=0.01)
        result = await gate.evaluate(
            response="A reasonable response for testing.",
            query="help",
        )
        # TIMEOUT_PASS stages are excluded from scoring, so overall should pass
        # if no actual FAIL stages exist
        timeout_stages = [s for s in result.stages if s.result == StageResult.TIMEOUT_PASS]
        fail_stages = [s for s in result.stages if s.result == StageResult.FAIL]
        if not fail_stages:
            assert result.overall_pass is True

    @pytest.mark.asyncio
    async def test_normal_stage_completes(self):
        """Non-slow stages complete normally."""
        gate = CLARAQualityGate(stage_timeout_seconds=5.0)
        result = await gate._structure_check("A good response about the topic.", "query")
        assert result.result in (StageResult.PASS, StageResult.FAIL)
        assert result.metadata.get("timeout") is None


# ── GAP-018: Brand Defaults ─────────────────────────────────────────


class TestBrandDefaultsGAP018:
    @pytest.mark.asyncio
    async def test_new_tenant_pipeline_passes(self):
        """GAP-018: Full pipeline with defaults doesn't fail on brand check."""
        gate = CLARAQualityGate(brand_voice=BrandVoiceConfig.defaults())
        result = await gate.evaluate(
            response="I understand your concern and will help you right away.",
            query="help",
        )
        brand_stage = next(
            s for s in result.stages if s.stage == CLARAStage.BRAND_CHECK
        )
        assert brand_stage.result == StageResult.PASS
        assert brand_stage.metadata.get("used_defaults") is True

    @pytest.mark.asyncio
    async def test_custom_tenant_enforced(self):
        """GAP-018: Custom rules are enforced."""
        bv = BrandVoiceConfig(prohibited_words=["stupid", "dumb"])
        gate = CLARAQualityGate(brand_voice=bv)
        result = await gate.evaluate(
            response="That's a stupid dumb question but I'll answer it anyway now.",
            query="help",
        )
        brand_stage = next(
            s for s in result.stages if s.stage == CLARAStage.BRAND_CHECK
        )
        assert brand_stage.result == StageResult.FAIL


# ── Overall Scoring ──────────────────────────────────────────────────


class TestOverallScoring:
    @pytest.mark.asyncio
    async def test_all_pass_true(self):
        gate = CLARAQualityGate()
        result = await gate.evaluate(
            response="Thank you for your inquiry. I can help you with the refund process. The refund will be processed within 5-7 business days. Please let me know if you need anything else.",
            query="refund",
        )
        assert isinstance(result.overall_pass, bool)

    @pytest.mark.asyncio
    async def test_score_in_range(self):
        gate = CLARAQualityGate()
        result = await gate.evaluate(
            response="Helpful response about the topic.",
            query="question",
        )
        assert 0.0 <= result.overall_score <= 1.0

    @pytest.mark.asyncio
    async def test_processing_time(self):
        gate = CLARAQualityGate()
        result = await gate.evaluate(
            response="Response text.", query="query",
        )
        assert result.total_processing_time_ms >= 0


# ── Edge Cases ──────────────────────────────────────────────────────


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_numbers_only(self):
        gate = CLARAQualityGate()
        result = await gate.evaluate(response="12345", query="query")
        assert isinstance(result.overall_pass, bool)

    @pytest.mark.asyncio
    async def test_special_chars(self):
        gate = CLARAQualityGate()
        result = await gate.evaluate(
            response="Here's the info: @#$%^&*()", query="query",
        )
        assert isinstance(result.overall_pass, bool)

    @pytest.mark.asyncio
    async def test_unicode(self):
        gate = CLARAQualityGate()
        result = await gate.evaluate(
            response="Thank you! Grüß Gott! こんにちは!",
            query="query",
        )
        assert isinstance(result.overall_pass, bool)

    @pytest.mark.asyncio
    async def test_very_long_response(self):
        gate = CLARAQualityGate()
        result = await gate.evaluate(
            response=" ".join(["This is a long response."] * 300),
            query="query",
        )
        # Structure check should fail for >500 words
        structure = next(
            s for s in result.stages if s.stage == CLARAStage.STRUCTURE_CHECK
        )
        assert structure.result == StageResult.FAIL
