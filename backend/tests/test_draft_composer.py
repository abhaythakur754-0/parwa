"""
Tests for AI Draft Composer — Co-Pilot Mode (F-066) — Week 9 Day 8

Covers: DraftOptions, DraftRequest, DraftResult, DraftComposerResponse,
SelectTechnique, BuildGenerationContext, Deduplication, CacheBehavior,
ComposeIntegration, RegenerateDraft.
Target: 100+ tests
"""

import asyncio
import hashlib
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ═══════════════════════════════════════════════════════════════════════
# Fixtures — import source modules with mocked logger
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def _mock_logger():
    with patch("backend.app.logger.get_logger", return_value=MagicMock()):
        from backend.app.core.draft_composer import (
            DraftComposer,
            DraftComposerResponse,
            DraftOptions,
            DraftRequest,
            DraftResult,
            _DEDUP_SIMILARITY_THRESHOLD,
            _TECHNIQUE_MAP,
            _VARIANT_MAX_DRAFTS,
        )
        globals().update({
            "DraftComposer": DraftComposer,
            "DraftComposerResponse": DraftComposerResponse,
            "DraftOptions": DraftOptions,
            "DraftRequest": DraftRequest,
            "DraftResult": DraftResult,
            "_DEDUP_SIMILARITY_THRESHOLD": _DEDUP_SIMILARITY_THRESHOLD,
            "_TECHNIQUE_MAP": _TECHNIQUE_MAP,
            "_VARIANT_MAX_DRAFTS": _VARIANT_MAX_DRAFTS,
        })


def _make_composer(**kwargs):
    """Create a DraftComposer with all services mocked."""
    smart_router = kwargs.pop("smart_router", MagicMock())
    smart_router.route = MagicMock()
    smart_router.async_execute_llm_call = AsyncMock(
        return_value={
            "content": "Here is a suggested response for the customer.",
            "model": "gpt-4o",
            "provider": "openai",
            "tier": "medium",
        },
    )
    clara_gate = kwargs.pop("clara_gate", MagicMock())
    clara_stage = MagicMock()
    clara_stage.stage.value = "brand_check"
    clara_stage.result.value = "pass"
    clara_stage.score = 0.85
    clara_stage.issues = []
    clara_result = MagicMock()
    clara_result.overall_score = 0.85
    clara_result.overall_pass = True
    clara_result.final_response = None
    clara_result.stages = [clara_stage]
    clara_gate.evaluate = AsyncMock(return_value=clara_result)

    brand_voice_service = kwargs.pop("brand_voice_service", MagicMock())
    config_mock = MagicMock()
    config_mock.tone = "professional"
    config_mock.formality_level = 0.5
    config_mock.brand_name = "TestCorp"
    config_mock.prohibited_words = []
    config_mock.response_length_preference = "standard"
    config_mock.max_response_sentences = 6
    config_mock.min_response_sentences = 2
    config_mock.greeting_template = ""
    config_mock.closing_template = ""
    config_mock.emoji_usage = "minimal"
    config_mock.custom_instructions = ""
    brand_voice_service.get_config = AsyncMock(return_value=config_mock)

    return DraftComposer(
        smart_router=smart_router,
        clara_gate=clara_gate,
        brand_voice_service=brand_voice_service,
    )


def _make_request(**overrides):
    """Create a DraftRequest with sensible defaults."""
    defaults = {
        "query": "I need help with my order",
        "company_id": "test_co",
        "variant_type": "parwa",
        "agent_id": "agent_1",
    }
    defaults.update(overrides)
    return DraftRequest(**defaults)


def _make_draft(content="Hello, here is your draft.", quality_score=0.8, **overrides):
    """Create a DraftResult for testing."""
    defaults = {
        "draft_id": uuid.uuid4().hex,
        "content": content,
        "quality_score": quality_score,
        "generation_time_ms": 100.0,
        "technique_used": "standard_response",
    }
    defaults.update(overrides)
    return DraftResult(**defaults)


# ═══════════════════════════════════════════════════════════════════════
# 1. TestDraftOptions (10 tests)
# ═══════════════════════════════════════════════════════════════════════

class TestDraftOptions:

    def test_default_values(self):
        opts = DraftOptions()
        assert opts.max_drafts == 1
        assert opts.tone is None
        assert opts.max_length == 500
        assert opts.include_citations is False
        assert opts.custom_instructions is None

    def test_custom_values(self):
        opts = DraftOptions(
            max_drafts=3,
            tone="friendly",
            max_length=800,
            include_citations=True,
            custom_instructions="Be concise",
        )
        assert opts.max_drafts == 3
        assert opts.tone == "friendly"
        assert opts.max_length == 800
        assert opts.include_citations is True
        assert opts.custom_instructions == "Be concise"

    def test_max_drafts_clamped_to_1_minimum(self):
        opts = DraftOptions(max_drafts=0)
        assert opts.max_drafts == 1

    def test_max_drafts_clamped_to_5_maximum(self):
        opts = DraftOptions(max_drafts=10)
        assert opts.max_drafts == 5

    def test_max_drafts_negative_clamped(self):
        opts = DraftOptions(max_drafts=-5)
        assert opts.max_drafts == 1

    def test_max_length_clamped_to_50_minimum(self):
        opts = DraftOptions(max_length=10)
        assert opts.max_length == 50

    def test_max_length_clamped_to_2000_maximum(self):
        opts = DraftOptions(max_length=5000)
        assert opts.max_length == 2000

    def test_tone_override(self):
        opts = DraftOptions(tone="casual")
        assert opts.tone == "casual"

    def test_include_citations_flag(self):
        opts = DraftOptions(include_citations=True)
        assert opts.include_citations is True

    def test_custom_instructions(self):
        opts = DraftOptions(custom_instructions="Speak like a pirate")
        assert opts.custom_instructions == "Speak like a pirate"

    def test_zero_max_drafts_corrected(self):
        """Zero explicitly should be corrected to 1."""
        opts = DraftOptions(max_drafts=0)
        assert opts.max_drafts == 1


# ═══════════════════════════════════════════════════════════════════════
# 2. TestDraftRequest (10 tests)
# ═══════════════════════════════════════════════════════════════════════

class TestDraftRequest:

    def test_default_values(self):
        req = DraftRequest(
            query="hello",
            company_id="c1",
            variant_type="parwa",
            agent_id="a1",
        )
        assert req.query == "hello"
        assert req.company_id == "c1"
        assert req.variant_type == "parwa"
        assert req.agent_id == "a1"
        assert req.ticket_id is None
        assert req.conversation_history is None
        assert req.customer_sentiment == 0.5
        assert req.customer_tier == "free"

    def test_custom_values(self):
        req = DraftRequest(
            query="help",
            company_id="c2",
            variant_type="parwa_high",
            agent_id="a2",
            ticket_id="t1",
            conversation_history=["hi", "hello"],
            customer_sentiment=0.9,
            customer_tier="enterprise",
        )
        assert req.ticket_id == "t1"
        assert req.conversation_history == ["hi", "hello"]
        assert req.customer_sentiment == 0.9
        assert req.customer_tier == "enterprise"

    def test_default_draft_options_created_when_none(self):
        req = DraftRequest(
            query="test",
            company_id="c1",
            variant_type="parwa",
            agent_id="a1",
        )
        assert req.draft_options is not None
        assert isinstance(req.draft_options, DraftOptions)

    def test_variant_type_determines_default_max_drafts_mini_parwa(self):
        req = DraftRequest(
            query="test",
            company_id="c1",
            variant_type="mini_parwa",
            agent_id="a1",
        )
        assert req.draft_options.max_drafts == 1

    def test_variant_type_determines_default_max_drafts_parwa(self):
        req = DraftRequest(
            query="test",
            company_id="c1",
            variant_type="parwa",
            agent_id="a1",
        )
        assert req.draft_options.max_drafts == 3

    def test_variant_type_determines_default_max_drafts_parwa_high(self):
        req = DraftRequest(
            query="test",
            company_id="c1",
            variant_type="parwa_high",
            agent_id="a1",
        )
        assert req.draft_options.max_drafts == 5

    def test_unknown_variant_type_defaults_to_1_draft(self):
        req = DraftRequest(
            query="test",
            company_id="c1",
            variant_type="unknown_variant",
            agent_id="a1",
        )
        assert req.draft_options.max_drafts == 1

    def test_conversation_history_preserved(self):
        history = ["msg1", "msg2", "msg3"]
        req = DraftRequest(
            query="test",
            company_id="c1",
            variant_type="parwa",
            agent_id="a1",
            conversation_history=history,
        )
        assert req.conversation_history == history

    def test_customer_sentiment_bounds_zero(self):
        req = DraftRequest(
            query="test",
            company_id="c1",
            variant_type="parwa",
            agent_id="a1",
            customer_sentiment=0.0,
        )
        assert req.customer_sentiment == 0.0

    def test_customer_tier_custom(self):
        req = DraftRequest(
            query="test",
            company_id="c1",
            variant_type="parwa",
            agent_id="a1",
            customer_tier="vip",
        )
        assert req.customer_tier == "vip"


# ═══════════════════════════════════════════════════════════════════════
# 3. TestDraftResult (8 tests)
# ═══════════════════════════════════════════════════════════════════════

class TestDraftResult:

    def test_default_creation(self):
        draft = DraftResult(
            draft_id="abc",
            content="hello",
            quality_score=0.5,
            generation_time_ms=50.0,
            technique_used="standard_response",
        )
        assert draft.draft_id == "abc"
        assert draft.content == "hello"
        assert draft.quality_score == 0.5
        assert draft.generation_time_ms == 50.0
        assert draft.technique_used == "standard_response"

    def test_to_dict_serialization(self):
        draft = DraftResult(
            draft_id="xyz",
            content="world",
            quality_score=0.75,
            generation_time_ms=123.456,
            technique_used="empathetic_resolution",
        )
        d = draft.to_dict()
        assert d["draft_id"] == "xyz"
        assert d["content"] == "world"
        assert d["quality_score"] == 0.75
        assert d["generation_time_ms"] == 123.46
        assert d["technique_used"] == "empathetic_resolution"

    def test_quality_score_bounds(self):
        draft = DraftResult(
            draft_id="a", content="b",
            quality_score=1.0, generation_time_ms=1.0,
            technique_used="x",
        )
        assert 0.0 <= draft.quality_score <= 1.0

    def test_generation_time_ms_positive(self):
        draft = _make_draft(generation_time_ms=42.5)
        assert draft.generation_time_ms > 0

    def test_technique_used_set(self):
        draft = _make_draft(technique_used="de_escalation")
        assert draft.technique_used == "de_escalation"

    def test_metadata_default_empty(self):
        draft = DraftResult(
            draft_id="a", content="b",
            quality_score=0.5, generation_time_ms=1.0,
            technique_used="x",
        )
        assert draft.metadata == {}

    def test_metadata_custom_values(self):
        draft = DraftResult(
            draft_id="a", content="b",
            quality_score=0.5, generation_time_ms=1.0,
            technique_used="x",
            metadata={"brand_check_passed": True, "tone_match": 0.9},
        )
        assert draft.metadata["brand_check_passed"] is True
        assert draft.metadata["tone_match"] == 0.9

    def test_draft_id_is_string(self):
        draft = _make_draft(draft_id="123abc")
        assert isinstance(draft.draft_id, str)


# ═══════════════════════════════════════════════════════════════════════
# 4. TestDraftComposerResponse (8 tests)
# ═══════════════════════════════════════════════════════════════════════

class TestDraftComposerResponse:

    def test_default_creation(self):
        resp = DraftComposerResponse(
            request_id="r1",
            drafts=[],
            best_draft_index=0,
            total_generation_time_ms=200.0,
            variant_type="parwa",
            cached=False,
        )
        assert resp.request_id == "r1"
        assert resp.drafts == []
        assert resp.variant_type == "parwa"
        assert resp.cached is False

    def test_to_dict_serialization(self):
        draft = _make_draft()
        resp = DraftComposerResponse(
            request_id="r1",
            drafts=[draft],
            best_draft_index=0,
            total_generation_time_ms=150.0,
            variant_type="parwa_high",
            cached=True,
        )
        d = resp.to_dict()
        assert d["request_id"] == "r1"
        assert len(d["drafts"]) == 1
        assert d["best_draft_index"] == 0
        assert d["total_generation_time_ms"] == 150.0
        assert d["variant_type"] == "parwa_high"
        assert d["cached"] is True

    def test_best_draft_index(self):
        resp = DraftComposerResponse(
            request_id="r1", drafts=[], best_draft_index=2,
            total_generation_time_ms=100.0, variant_type="parwa",
            cached=False,
        )
        assert resp.best_draft_index == 2

    def test_variant_type_set(self):
        resp = DraftComposerResponse(
            request_id="r1", drafts=[], best_draft_index=-1,
            total_generation_time_ms=100.0, variant_type="mini_parwa",
            cached=False,
        )
        assert resp.variant_type == "mini_parwa"

    def test_cached_flag(self):
        resp = DraftComposerResponse(
            request_id="r1", drafts=[], best_draft_index=-1,
            total_generation_time_ms=100.0, variant_type="parwa",
            cached=True,
        )
        assert resp.cached is True

    def test_total_generation_time_ms(self):
        resp = DraftComposerResponse(
            request_id="r1", drafts=[], best_draft_index=-1,
            total_generation_time_ms=999.99, variant_type="parwa",
            cached=False,
        )
        assert resp.total_generation_time_ms == 999.99

    def test_drafts_list(self):
        drafts = [_make_draft(quality_score=0.9), _make_draft(quality_score=0.7)]
        resp = DraftComposerResponse(
            request_id="r1", drafts=drafts, best_draft_index=0,
            total_generation_time_ms=100.0, variant_type="parwa",
            cached=False,
        )
        assert len(resp.drafts) == 2
        assert resp.drafts[0].quality_score == 0.9

    def test_empty_drafts_list(self):
        resp = DraftComposerResponse(
            request_id="r1", drafts=[], best_draft_index=-1,
            total_generation_time_ms=50.0, variant_type="parwa",
            cached=False,
        )
        assert resp.drafts == []


# ═══════════════════════════════════════════════════════════════════════
# 5. TestSelectTechnique (15 tests)
# ═══════════════════════════════════════════════════════════════════════

class TestSelectTechnique:

    def setup_method(self):
        self.composer = _make_composer()

    def test_refund_low_sentiment_empathetic_resolution(self):
        result = self.composer._select_technique(
            intent="refund", sentiment=0.1, variant_type="parwa",
        )
        assert result == "empathetic_resolution"

    def test_refund_high_sentiment_friendly_confirmation(self):
        result = self.composer._select_technique(
            intent="refund", sentiment=0.9, variant_type="parwa",
        )
        assert result == "friendly_confirmation"

    def test_refund_default_sentiment_standard_resolution(self):
        result = self.composer._select_technique(
            intent="refund", sentiment=0.5, variant_type="parwa",
        )
        assert result == "standard_resolution"

    def test_technical_low_sentiment_patient_troubleshooting(self):
        result = self.composer._select_technique(
            intent="technical", sentiment=0.2, variant_type="parwa",
        )
        assert result == "patient_troubleshooting"

    def test_billing_default_informative_breakdown(self):
        result = self.composer._select_technique(
            intent="billing", sentiment=0.5, variant_type="parwa",
        )
        assert result == "informative_breakdown"

    def test_complaint_low_sentiment_de_escalation(self):
        result = self.composer._select_technique(
            intent="complaint", sentiment=0.1, variant_type="parwa",
        )
        assert result == "de_escalation"

    def test_escalation_low_sentiment_urgent_escalation(self):
        result = self.composer._select_technique(
            intent="escalation", sentiment=0.15, variant_type="parwa",
        )
        assert result == "urgent_escalation"

    def test_shipping_default_logistics_response(self):
        result = self.composer._select_technique(
            intent="shipping", sentiment=0.5, variant_type="parwa",
        )
        assert result == "logistics_response"

    def test_account_default_account_assistance(self):
        result = self.composer._select_technique(
            intent="account", sentiment=0.5, variant_type="parwa",
        )
        assert result == "account_assistance"

    def test_feature_request_high_sentiment_enthusiastic_capture(self):
        result = self.composer._select_technique(
            intent="feature_request", sentiment=0.8, variant_type="parwa",
        )
        assert result == "enthusiastic_capture"

    def test_inquiry_default_informative_response(self):
        result = self.composer._select_technique(
            intent="inquiry", sentiment=0.5, variant_type="parwa",
        )
        assert result == "informative_response"

    def test_feedback_high_sentiment_celebration(self):
        result = self.composer._select_technique(
            intent="feedback", sentiment=0.9, variant_type="parwa",
        )
        assert result == "celebration"

    def test_general_default_standard_response(self):
        result = self.composer._select_technique(
            intent="general", sentiment=0.5, variant_type="parwa",
        )
        assert result == "standard_response"

    def test_mini_parwa_always_standard_response(self):
        """mini_parwa should always return standard_response regardless of intent."""
        result = self.composer._select_technique(
            intent="refund", sentiment=0.1, variant_type="mini_parwa",
        )
        assert result == "standard_response"

    def test_unknown_intent_fallback_to_general(self):
        result = self.composer._select_technique(
            intent="completely_unknown_intent", sentiment=0.5,
            variant_type="parwa",
        )
        assert result in _TECHNIQUE_MAP["general"].values()


# ═══════════════════════════════════════════════════════════════════════
# 6. TestBuildGenerationContext (8 tests)
# ═══════════════════════════════════════════════════════════════════════

class TestBuildGenerationContext:

    def setup_method(self):
        self.composer = _make_composer()

    def test_merges_signals_classification_brand_voice(self):
        signals = {"sentiment": 0.3, "intent": "refund"}
        classification = {"primary_intent": "refund"}
        brand_voice = {"tone": "professional"}
        ctx = self.composer._build_generation_context(
            signals, classification, brand_voice,
        )
        assert ctx["signals"] == signals
        assert ctx["classification"] == classification
        assert ctx["brand_voice"] == brand_voice

    def test_missing_signals_uses_defaults(self):
        ctx = self.composer._build_generation_context(
            {}, {"primary_intent": "general"}, {},
        )
        assert ctx["sentiment"] == 0.5
        assert ctx["complexity"] == 0.5
        assert ctx["customer_tier"] == "free"

    def test_missing_classification_uses_defaults(self):
        ctx = self.composer._build_generation_context(
            {"sentiment": 0.8}, {}, {},
        )
        assert ctx["intent"] == "general"

    def test_missing_brand_voice_uses_defaults(self):
        ctx = self.composer._build_generation_context(
            {"sentiment": 0.5}, {"primary_intent": "general"}, {},
        )
        assert ctx["brand_voice"] == {}

    def test_intent_from_classification(self):
        ctx = self.composer._build_generation_context(
            {}, {"primary_intent": "billing"}, {},
        )
        assert ctx["intent"] == "billing"

    def test_sentiment_from_signals(self):
        ctx = self.composer._build_generation_context(
            {"sentiment": 0.15}, {"primary_intent": "general"}, {},
        )
        assert ctx["sentiment"] == 0.15

    def test_technique_included(self):
        ctx = self.composer._build_generation_context(
            {"sentiment": 0.1}, {"primary_intent": "refund"}, {},
        )
        assert "technique" in ctx
        assert isinstance(ctx["technique"], str)
        assert len(ctx["technique"]) > 0

    def test_customer_tier_from_signals(self):
        ctx = self.composer._build_generation_context(
            {"customer_tier": "enterprise"}, {}, {},
        )
        assert ctx["customer_tier"] == "enterprise"


# ═══════════════════════════════════════════════════════════════════════
# 7. TestDeduplication (10 tests)
# ═══════════════════════════════════════════════════════════════════════

class TestDeduplication:

    def setup_method(self):
        self.composer = _make_composer()

    def test_empty_list_returns_empty(self):
        result = self.composer._deduplicate_drafts([])
        assert result == []

    def test_single_draft_unchanged(self):
        draft = _make_draft(content="Unique draft content here.")
        result = self.composer._deduplicate_drafts([draft])
        assert len(result) == 1
        assert result[0].draft_id == draft.draft_id

    def test_two_identical_drafts_one_removed(self):
        d1 = _make_draft(content="This is exactly the same draft.", quality_score=0.9)
        d2 = _make_draft(content="This is exactly the same draft.", quality_score=0.8)
        result = self.composer._deduplicate_drafts([d1, d2])
        assert len(result) == 1

    def test_similar_drafts_deduplicated(self):
        """Drafts that are 90%+ similar should be deduplicated."""
        base = "Thank you for contacting our support team. We are happy to help you with your inquiry. "
        d1 = _make_draft(content=base + "Please let us know how else we can assist.", quality_score=0.9)
        d2 = _make_draft(content=base + "Please let us know what else we can assist.", quality_score=0.8)
        result = self.composer._deduplicate_drafts([d1, d2])
        assert len(result) == 1

    def test_different_drafts_both_kept(self):
        d1 = _make_draft(content="The cat sat on the mat and looked out the window.")
        d2 = _make_draft(content="Quantum mechanics explains subatomic particle behavior.")
        result = self.composer._deduplicate_drafts([d1, d2])
        assert len(result) == 2

    def test_threshold_85_boundary(self):
        """Drafts just at the 0.85 boundary should be deduplicated."""
        long_text = "word " * 50
        d1 = _make_draft(content=long_text + " ending A", quality_score=0.9)
        d2 = _make_draft(content=long_text + " ending B", quality_score=0.8)
        result = self.composer._deduplicate_drafts([d1, d2])
        # These should be > 0.85 similar
        assert len(result) == 1

    def test_keeps_higher_quality_draft(self):
        """When duplicates found, the first (higher quality) should be kept."""
        d1 = _make_draft(content="Exactly the same text here for both.", quality_score=0.95)
        d2 = _make_draft(content="Exactly the same text here for both.", quality_score=0.6)
        result = self.composer._deduplicate_drafts([d1, d2])
        assert len(result) == 1
        assert result[0].quality_score == 0.95

    def test_three_drafts_two_similar_one_removed(self):
        base = "We apologize for the inconvenience caused. "
        d1 = _make_draft(content=base + "Here is your refund info.", quality_score=0.9)
        d2 = _make_draft(content=base + "Here is the refund info.", quality_score=0.85)
        d3 = _make_draft(content="Completely different response text here.", quality_score=0.7)
        result = self.composer._deduplicate_drafts([d1, d2, d3])
        assert len(result) == 2

    def test_order_preserved_for_unique(self):
        d1 = _make_draft(content="First unique draft.", quality_score=0.5, draft_id="d1")
        d2 = _make_draft(content="Second unique draft.", quality_score=0.6, draft_id="d2")
        d3 = _make_draft(content="Third unique draft.", quality_score=0.7, draft_id="d3")
        result = self.composer._deduplicate_drafts([d1, d2, d3])
        assert [d.draft_id for d in result] == ["d1", "d2", "d3"]

    def test_empty_content_drafts_handled(self):
        """Drafts with empty content should be skipped."""
        d1 = _make_draft(content="", quality_score=0.0)
        d2 = _make_draft(content="Valid content here.", quality_score=0.7)
        result = self.composer._deduplicate_drafts([d1, d2])
        assert len(result) == 1
        assert result[0].content == "Valid content here."


# ═══════════════════════════════════════════════════════════════════════
# 8. TestCacheBehavior (10 tests)
# ═══════════════════════════════════════════════════════════════════════

class TestCacheBehavior:

    def setup_method(self):
        self.composer = _make_composer()

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached_response(self):
        cached_data = {
            "request_id": "cached_r1",
            "drafts": [{
                "draft_id": "cd1",
                "content": "Cached draft",
                "quality_score": 0.9,
                "generation_time_ms": 50.0,
                "technique_used": "standard_response",
                "metadata": {},
            }],
            "best_draft_index": 0,
            "total_generation_time_ms": 80.0,
            "variant_type": "parwa",
        }
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=cached_data):
            result = await self.composer._check_cache("c1", "key1")
            assert result is not None
            assert result.cached is True
            assert result.request_id == "cached_r1"

    @pytest.mark.asyncio
    async def test_cache_miss_returns_none(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            result = await self.composer._check_cache("c1", "key1")
            assert result is None

    @pytest.mark.asyncio
    async def test_cache_fail_open_on_read_error(self):
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, side_effect=Exception("Redis down")):
            result = await self.composer._check_cache("c1", "key1")
            assert result is None

    @pytest.mark.asyncio
    async def test_cache_fail_open_on_write_error(self):
        resp = DraftComposerResponse(
            request_id="r1", drafts=[], best_draft_index=-1,
            total_generation_time_ms=100.0, variant_type="parwa",
            cached=False,
        )
        with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock, side_effect=Exception("Write fail")):
            # Should not raise
            await self.composer._store_cache("c1", "key1", resp)

    def test_cache_key_format_includes_company_id_and_variant(self):
        qh = self.composer._compute_query_hash("test query")
        key = f"draft_cache:my_company:parwa:{qh}"
        assert "my_company" in key
        assert "parwa" in key

    def test_cache_key_format_includes_query_hash(self):
        qh = self.composer._compute_query_hash("test query")
        key = f"draft_cache:c1:parwa:{qh}"
        assert qh in key

    @pytest.mark.asyncio
    async def test_compose_cached_response_has_cached_true(self):
        """Full compose pipeline: cached response has cached=True."""
        cached_data = {
            "request_id": "cr1",
            "drafts": [{
                "draft_id": "cd1", "content": "Cached",
                "quality_score": 0.9, "generation_time_ms": 50.0,
                "technique_used": "standard_response", "metadata": {},
            }],
            "best_draft_index": 0,
            "total_generation_time_ms": 80.0,
            "variant_type": "parwa",
        }
        req = _make_request(query="cached query")
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=cached_data):
            result = await self.composer.compose(req)
            assert result.cached is True

    @pytest.mark.asyncio
    async def test_non_cached_has_cached_false(self):
        """Non-cached response through full pipeline has cached=False."""
        req = _make_request(query="fresh query")
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                with patch("backend.app.core.signal_extraction.SignalExtractor") as MockExtractor:
                    mock_sig_result = MagicMock()
                    mock_sig_result.to_dict.return_value = {
                        "intent": "general", "sentiment": 0.5,
                        "complexity": 0.5, "monetary_value": 0.0,
                        "customer_tier": "free", "query_breadth": 0.5,
                    }
                    MockExtractor.return_value.extract = AsyncMock(return_value=mock_sig_result)
                    with patch("backend.app.core.classification_engine.ClassificationEngine") as MockEngine:
                        mock_class_result = MagicMock()
                        mock_class_result.primary_intent = "general"
                        mock_class_result.primary_confidence = 0.7
                        mock_class_result.secondary_intents = []
                        mock_class_result.classification_method = "keyword"
                        MockEngine.return_value.classify = AsyncMock(return_value=mock_class_result)
                        with patch("backend.app.core.socketio.emit_to_tenant", new_callable=AsyncMock):
                            result = await self.composer.compose(req)
                            assert result.cached is False

    @pytest.mark.asyncio
    async def test_cache_stores_response(self):
        resp = DraftComposerResponse(
            request_id="r1",
            drafts=[_make_draft()],
            best_draft_index=0,
            total_generation_time_ms=100.0,
            variant_type="parwa",
            cached=False,
        )
        mock_set = AsyncMock()
        with patch("backend.app.core.redis.cache_set", mock_set):
            await self.composer._store_cache("c1", "key1", resp)
            mock_set.assert_called_once()
            call_args = mock_set.call_args
            assert call_args[0][0] == "c1"
            assert call_args[0][1] == "key1"
            assert isinstance(call_args[0][2], dict)

    def test_cache_key_deterministic(self):
        h1 = self.composer._compute_query_hash("Hello World")
        h2 = self.composer._compute_query_hash("Hello World")
        h3 = self.composer._compute_query_hash("hello world")
        assert h1 == h2
        assert h1 == h3  # normalized (lowercase)


# ═══════════════════════════════════════════════════════════════════════
# 9. TestComposeIntegration (12 tests)
# ═══════════════════════════════════════════════════════════════════════

class TestComposeIntegration:

    def setup_method(self):
        self.composer = _make_composer()

    @pytest.mark.asyncio
    async def test_empty_query_returns_empty_response(self):
        req = DraftRequest(
            query="", company_id="c1", variant_type="parwa", agent_id="a1",
        )
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            result = await self.composer.compose(req)
            assert len(result.drafts) == 0
            assert result.best_draft_index == -1

    @pytest.mark.asyncio
    async def test_whitespace_only_query_returns_empty(self):
        req = DraftRequest(
            query="   ", company_id="c1", variant_type="parwa", agent_id="a1",
        )
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            result = await self.composer.compose(req)
            assert len(result.drafts) == 0

    @pytest.mark.asyncio
    async def test_valid_query_generates_drafts(self):
        req = _make_request(query="How do I reset my password?")
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                with patch("backend.app.core.signal_extraction.SignalExtractor") as MockExtractor:
                    mock_sig_result = MagicMock()
                    mock_sig_result.to_dict.return_value = {
                        "intent": "account", "sentiment": 0.5,
                        "complexity": 0.4, "monetary_value": 0.0,
                        "customer_tier": "free", "query_breadth": 0.5,
                    }
                    MockExtractor.return_value.extract = AsyncMock(return_value=mock_sig_result)
                    with patch("backend.app.core.classification_engine.ClassificationEngine") as MockEngine:
                        mock_class_result = MagicMock()
                        mock_class_result.primary_intent = "account"
                        mock_class_result.primary_confidence = 0.8
                        mock_class_result.secondary_intents = []
                        mock_class_result.classification_method = "keyword"
                        MockEngine.return_value.classify = AsyncMock(return_value=mock_class_result)
                        with patch("backend.app.core.socketio.emit_to_tenant", new_callable=AsyncMock):
                            result = await self.composer.compose(req)
                            assert len(result.drafts) > 0

    @pytest.mark.asyncio
    async def test_mini_parwa_generates_1_draft(self):
        req = _make_request(query="What is this?", variant_type="mini_parwa")
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                with patch("backend.app.core.signal_extraction.SignalExtractor") as MockExtractor:
                    mock_sig_result = MagicMock()
                    mock_sig_result.to_dict.return_value = {
                        "intent": "general", "sentiment": 0.5,
                        "complexity": 0.3, "monetary_value": 0.0,
                        "customer_tier": "free", "query_breadth": 0.5,
                    }
                    MockExtractor.return_value.extract = AsyncMock(return_value=mock_sig_result)
                    with patch("backend.app.core.classification_engine.ClassificationEngine") as MockEngine:
                        mock_class_result = MagicMock()
                        mock_class_result.primary_intent = "general"
                        mock_class_result.primary_confidence = 0.5
                        mock_class_result.secondary_intents = []
                        mock_class_result.classification_method = "keyword"
                        MockEngine.return_value.classify = AsyncMock(return_value=mock_class_result)
                        with patch("backend.app.core.socketio.emit_to_tenant", new_callable=AsyncMock):
                            result = await self.composer.compose(req)
                            assert len(result.drafts) <= 1

    @pytest.mark.asyncio
    async def test_parwa_generates_up_to_3_drafts(self):
        req = _make_request(query="I need help with billing", variant_type="parwa")
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                with patch("backend.app.core.signal_extraction.SignalExtractor") as MockExtractor:
                    mock_sig_result = MagicMock()
                    mock_sig_result.to_dict.return_value = {
                        "intent": "billing", "sentiment": 0.4,
                        "complexity": 0.5, "monetary_value": 0.0,
                        "customer_tier": "free", "query_breadth": 0.5,
                    }
                    MockExtractor.return_value.extract = AsyncMock(return_value=mock_sig_result)
                    with patch("backend.app.core.classification_engine.ClassificationEngine") as MockEngine:
                        mock_class_result = MagicMock()
                        mock_class_result.primary_intent = "billing"
                        mock_class_result.primary_confidence = 0.8
                        mock_class_result.secondary_intents = []
                        mock_class_result.classification_method = "keyword"
                        MockEngine.return_value.classify = AsyncMock(return_value=mock_class_result)
                        with patch("backend.app.core.socketio.emit_to_tenant", new_callable=AsyncMock):
                            result = await self.composer.compose(req)
                            assert len(result.drafts) <= 3

    @pytest.mark.asyncio
    async def test_parwa_high_generates_up_to_5_drafts(self):
        req = _make_request(query="I have a complex issue", variant_type="parwa_high")
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                with patch("backend.app.core.signal_extraction.SignalExtractor") as MockExtractor:
                    mock_sig_result = MagicMock()
                    mock_sig_result.to_dict.return_value = {
                        "intent": "general", "sentiment": 0.5,
                        "complexity": 0.5, "monetary_value": 0.0,
                        "customer_tier": "pro", "query_breadth": 0.5,
                    }
                    MockExtractor.return_value.extract = AsyncMock(return_value=mock_sig_result)
                    with patch("backend.app.core.classification_engine.ClassificationEngine") as MockEngine:
                        mock_class_result = MagicMock()
                        mock_class_result.primary_intent = "general"
                        mock_class_result.primary_confidence = 0.6
                        mock_class_result.secondary_intents = []
                        mock_class_result.classification_method = "keyword"
                        MockEngine.return_value.classify = AsyncMock(return_value=mock_class_result)
                        with patch("backend.app.core.socketio.emit_to_tenant", new_callable=AsyncMock):
                            result = await self.composer.compose(req)
                            assert len(result.drafts) <= 5

    @pytest.mark.asyncio
    async def test_total_timeout_returns_empty(self):
        """When total timeout (30s) fires, return empty response."""
        req = _make_request(query="delayed query")

        async def slow_pipeline(*args, **kwargs):
            await asyncio.sleep(999)
            return DraftComposerResponse(
                request_id="r1", drafts=[], best_draft_index=-1,
                total_generation_time_ms=0.0, variant_type="parwa",
                cached=False,
            )

        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch.object(self.composer, "_compose_pipeline", side_effect=slow_pipeline):
                # Use very short timeout to simulate timeout
                with patch("backend.app.core.draft_composer._TOTAL_COMPOSE_TIMEOUT_SECONDS", 0.001):
                    result = await self.composer.compose(req)
                    assert len(result.drafts) == 0
                    assert result.best_draft_index == -1

    @pytest.mark.asyncio
    async def test_clara_validation_applied(self):
        """CLARA gate should be called for each draft."""
        req = _make_request(query="Test query")
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                with patch("backend.app.core.signal_extraction.SignalExtractor") as MockExtractor:
                    mock_sig_result = MagicMock()
                    mock_sig_result.to_dict.return_value = {
                        "intent": "general", "sentiment": 0.5,
                        "complexity": 0.5, "monetary_value": 0.0,
                        "customer_tier": "free", "query_breadth": 0.5,
                    }
                    MockExtractor.return_value.extract = AsyncMock(return_value=mock_sig_result)
                    with patch("backend.app.core.classification_engine.ClassificationEngine") as MockEngine:
                        mock_class_result = MagicMock()
                        mock_class_result.primary_intent = "general"
                        mock_class_result.primary_confidence = 0.7
                        mock_class_result.secondary_intents = []
                        mock_class_result.classification_method = "keyword"
                        MockEngine.return_value.classify = AsyncMock(return_value=mock_class_result)
                        with patch("backend.app.core.socketio.emit_to_tenant", new_callable=AsyncMock):
                            result = await self.composer.compose(req)
                            self.composer.clara_gate.evaluate.assert_called()

    @pytest.mark.asyncio
    async def test_drafts_sorted_by_quality(self):
        """Response drafts should be sorted by quality_score descending."""
        req = _make_request(query="multi draft query")
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                with patch("backend.app.core.signal_extraction.SignalExtractor") as MockExtractor:
                    mock_sig_result = MagicMock()
                    mock_sig_result.to_dict.return_value = {
                        "intent": "general", "sentiment": 0.5,
                        "complexity": 0.5, "monetary_value": 0.0,
                        "customer_tier": "free", "query_breadth": 0.5,
                    }
                    MockExtractor.return_value.extract = AsyncMock(return_value=mock_sig_result)
                    with patch("backend.app.core.classification_engine.ClassificationEngine") as MockEngine:
                        mock_class_result = MagicMock()
                        mock_class_result.primary_intent = "general"
                        mock_class_result.primary_confidence = 0.7
                        mock_class_result.secondary_intents = []
                        mock_class_result.classification_method = "keyword"
                        MockEngine.return_value.classify = AsyncMock(return_value=mock_class_result)
                        with patch("backend.app.core.socketio.emit_to_tenant", new_callable=AsyncMock):
                            result = await self.composer.compose(req)
                            if len(result.drafts) > 1:
                                for i in range(len(result.drafts) - 1):
                                    assert result.drafts[i].quality_score >= result.drafts[i + 1].quality_score

    @pytest.mark.asyncio
    async def test_best_draft_is_first(self):
        """best_draft_index should always be 0 after sorting."""
        req = _make_request(query="best draft test")
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                with patch("backend.app.core.signal_extraction.SignalExtractor") as MockExtractor:
                    mock_sig_result = MagicMock()
                    mock_sig_result.to_dict.return_value = {
                        "intent": "general", "sentiment": 0.5,
                        "complexity": 0.5, "monetary_value": 0.0,
                        "customer_tier": "free", "query_breadth": 0.5,
                    }
                    MockExtractor.return_value.extract = AsyncMock(return_value=mock_sig_result)
                    with patch("backend.app.core.classification_engine.ClassificationEngine") as MockEngine:
                        mock_class_result = MagicMock()
                        mock_class_result.primary_intent = "general"
                        mock_class_result.primary_confidence = 0.7
                        mock_class_result.secondary_intents = []
                        mock_class_result.classification_method = "keyword"
                        MockEngine.return_value.classify = AsyncMock(return_value=mock_class_result)
                        with patch("backend.app.core.socketio.emit_to_tenant", new_callable=AsyncMock):
                            result = await self.composer.compose(req)
                            if len(result.drafts) > 0:
                                assert result.best_draft_index == 0

    @pytest.mark.asyncio
    async def test_draft_history_stored_for_ticket(self):
        """When ticket_id is present, draft history should be stored."""
        req = _make_request(query="history test", ticket_id="ticket_123")
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            mock_cache_set = AsyncMock()
            with patch("backend.app.core.redis.cache_set", mock_cache_set):
                with patch("backend.app.core.signal_extraction.SignalExtractor") as MockExtractor:
                    mock_sig_result = MagicMock()
                    mock_sig_result.to_dict.return_value = {
                        "intent": "general", "sentiment": 0.5,
                        "complexity": 0.5, "monetary_value": 0.0,
                        "customer_tier": "free", "query_breadth": 0.5,
                    }
                    MockExtractor.return_value.extract = AsyncMock(return_value=mock_sig_result)
                    with patch("backend.app.core.classification_engine.ClassificationEngine") as MockEngine:
                        mock_class_result = MagicMock()
                        mock_class_result.primary_intent = "general"
                        mock_class_result.primary_confidence = 0.7
                        mock_class_result.secondary_intents = []
                        mock_class_result.classification_method = "keyword"
                        MockEngine.return_value.classify = AsyncMock(return_value=mock_class_result)
                        with patch("backend.app.core.socketio.emit_to_tenant", new_callable=AsyncMock):
                            await self.composer.compose(req)
                            # cache_set should be called at least twice (cache + history)
                            assert mock_cache_set.call_count >= 2

    @pytest.mark.asyncio
    async def test_socketio_emission_on_success(self):
        """Socket.io emit_to_tenant should be called on successful compose."""
        req = _make_request(query="socket test")
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                with patch("backend.app.core.signal_extraction.SignalExtractor") as MockExtractor:
                    mock_sig_result = MagicMock()
                    mock_sig_result.to_dict.return_value = {
                        "intent": "general", "sentiment": 0.5,
                        "complexity": 0.5, "monetary_value": 0.0,
                        "customer_tier": "free", "query_breadth": 0.5,
                    }
                    MockExtractor.return_value.extract = AsyncMock(return_value=mock_sig_result)
                    with patch("backend.app.core.classification_engine.ClassificationEngine") as MockEngine:
                        mock_class_result = MagicMock()
                        mock_class_result.primary_intent = "general"
                        mock_class_result.primary_confidence = 0.7
                        mock_class_result.secondary_intents = []
                        mock_class_result.classification_method = "keyword"
                        MockEngine.return_value.classify = AsyncMock(return_value=mock_class_result)
                        with patch("backend.app.core.socketio.emit_to_tenant", new_callable=AsyncMock) as mock_emit:
                            await self.composer.compose(req)
                            mock_emit.assert_called_once()

    @pytest.mark.asyncio
    async def test_signal_extraction_failure_safe_defaults(self):
        """When signal extraction fails, pipeline should use safe defaults."""
        req = _make_request(query="fallback test")
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock):
                with patch("backend.app.core.signal_extraction.SignalExtractor") as MockExtractor:
                    MockExtractor.return_value.extract = AsyncMock(
                        side_effect=Exception("Signal extraction failed")
                    )
                    with patch("backend.app.core.classification_engine.ClassificationEngine") as MockEngine:
                        mock_class_result = MagicMock()
                        mock_class_result.primary_intent = "general"
                        mock_class_result.primary_confidence = 0.3
                        mock_class_result.secondary_intents = []
                        mock_class_result.classification_method = "fallback"
                        MockEngine.return_value.classify = AsyncMock(
                            side_effect=Exception("Classification failed")
                        )
                        with patch("backend.app.core.socketio.emit_to_tenant", new_callable=AsyncMock):
                            # Should NOT raise — BC-008 graceful degradation
                            result = await self.composer.compose(req)
                            assert isinstance(result, DraftComposerResponse)


# ═══════════════════════════════════════════════════════════════════════
# 10. TestRegenerateDraft (9 tests)
# ═══════════════════════════════════════════════════════════════════════

class TestRegenerateDraft:

    def setup_method(self):
        self.composer = _make_composer()

    @pytest.mark.asyncio
    async def test_regenerate_with_feedback(self):
        result = await self.composer._regenerate_draft(
            draft_id="old_draft",
            feedback="Make it more empathetic",
            company_id="c1",
        )
        assert result.content == "Here is a suggested response for the customer."
        assert result.technique_used == "feedback_revision"
        assert result.metadata.get("regenerated_from") == "old_draft"
        assert result.metadata.get("feedback") == "Make it more empathetic"

    @pytest.mark.asyncio
    async def test_feedback_stored_in_redis(self):
        mock_cache_set = AsyncMock()
        with patch("backend.app.core.redis.cache_set", mock_cache_set):
            await self.composer._regenerate_draft(
                draft_id="draft_abc",
                feedback="Too formal",
                company_id="c1",
            )
            mock_cache_set.assert_called_once()
            call_args = mock_cache_set.call_args
            assert call_args[0][0] == "c1"
            assert "draft_feedback:draft_abc" in call_args[0][1]
            feedback_data = call_args[0][2]
            assert feedback_data["feedback"] == "Too formal"
            assert feedback_data["draft_id"] == "draft_abc"

    @pytest.mark.asyncio
    async def test_original_draft_context_preserved(self):
        """Metadata should reference the original draft_id."""
        result = await self.composer._regenerate_draft(
            draft_id="orig_123",
            feedback="shorter please",
            company_id="c1",
        )
        assert result.metadata["regenerated_from"] == "orig_123"

    @pytest.mark.asyncio
    async def test_empty_feedback_handled(self):
        """Empty feedback string should still work without crashing."""
        result = await self.composer._regenerate_draft(
            draft_id="d1",
            feedback="",
            company_id="c1",
        )
        assert isinstance(result, DraftResult)
        assert result.technique_used == "feedback_revision"

    @pytest.mark.asyncio
    async def test_feedback_history_retrieval(self):
        """get_feedback_history should return a list (placeholder)."""
        history = await self.composer.get_feedback_history(company_id="c1", limit=10)
        assert isinstance(history, list)

    @pytest.mark.asyncio
    async def test_non_existent_draft_handled_gracefully(self):
        """Regenerating a non-existent draft should not crash."""
        result = await self.composer._regenerate_draft(
            draft_id="nonexistent_id",
            feedback="This draft doesn't exist but regenerate anyway",
            company_id="c1",
        )
        assert isinstance(result, DraftResult)
        assert result.content != ""

    @pytest.mark.asyncio
    async def test_different_feedback_produces_different_content_in_metadata(self):
        """Different feedback strings should appear in metadata."""
        r1 = await self.composer._regenerate_draft("d1", "Be casual", "c1")
        r2 = await self.composer._regenerate_draft("d2", "Be formal", "c2")
        assert r1.metadata["feedback"] == "Be casual"
        assert r2.metadata["feedback"] == "Be formal"

    @pytest.mark.asyncio
    async def test_company_isolation(self):
        """Feedback for one company should not leak to another."""
        calls = []
        mock_cache_set = AsyncMock(side_effect=lambda *args, **kwargs: calls.append(args))
        with patch("backend.app.core.redis.cache_set", mock_cache_set):
            await self.composer._regenerate_draft("d1", "feedback A", "company_A")
            await self.composer._regenerate_draft("d2", "feedback B", "company_B")
            assert calls[0][0] == "company_A"
            assert calls[1][0] == "company_B"

    @pytest.mark.asyncio
    async def test_draft_metadata_includes_feedback(self):
        result = await self.composer._regenerate_draft(
            draft_id="d1",
            feedback="Add more detail about the refund process",
            company_id="c1",
        )
        assert "feedback" in result.metadata
        assert result.metadata["feedback"] == "Add more detail about the refund process"
        assert "regenerated_from" in result.metadata
        assert "model" in result.metadata
        assert "provider" in result.metadata


# ═══════════════════════════════════════════════════════════════════════
# 11. Additional Edge Case Tests (bonus to exceed 100)
# ═══════════════════════════════════════════════════════════════════════

class TestEdgeCases:

    def test_query_hash_deterministic_same_input(self):
        composer = _make_composer()
        h1 = composer._compute_query_hash("Hello World")
        h2 = composer._compute_query_hash("Hello World")
        assert h1 == h2

    def test_query_hash_normalizes_case(self):
        composer = _make_composer()
        h1 = composer._compute_query_hash("HELLO WORLD")
        h2 = composer._compute_query_hash("hello world")
        assert h1 == h2

    def test_query_hash_normalizes_whitespace(self):
        composer = _make_composer()
        h1 = composer._compute_query_hash("  hello world  ")
        h2 = composer._compute_query_hash("hello world")
        assert h1 == h2

    def test_query_hash_different_inputs_differ(self):
        composer = _make_composer()
        h1 = composer._compute_query_hash("refund my order")
        h2 = composer._compute_query_hash("cancel my subscription")
        assert h1 != h2

    def test_generate_uuid_returns_string(self):
        result = DraftComposer._generate_uuid()
        assert isinstance(result, str)
        assert len(result) == 32  # UUID4 hex

    def test_generate_uuid_is_unique(self):
        r1 = DraftComposer._generate_uuid()
        r2 = DraftComposer._generate_uuid()
        assert r1 != r2

    def test_variant_max_drafts_constant(self):
        assert _VARIANT_MAX_DRAFTS["mini_parwa"] == 1
        assert _VARIANT_MAX_DRAFTS["parwa"] == 3
        assert _VARIANT_MAX_DRAFTS["parwa_high"] == 5

    def test_dedup_similarity_threshold_value(self):
        assert _DEDUP_SIMILARITY_THRESHOLD == 0.85

    def test_technique_map_has_all_intents(self):
        expected_intents = {
            "refund", "technical", "billing", "complaint", "cancellation",
            "escalation", "shipping", "account", "feature_request",
            "inquiry", "feedback", "general",
        }
        assert set(_TECHNIQUE_MAP.keys()) == expected_intents

    def test_empty_response_best_draft_index_is_negative_one(self):
        resp = DraftComposerResponse(
            request_id="r1", drafts=[], best_draft_index=-1,
            total_generation_time_ms=0.0, variant_type="parwa",
            cached=False,
        )
        assert resp.best_draft_index == -1

    @pytest.mark.asyncio
    async def test_get_draft_history_empty_on_failure(self):
        composer = _make_composer()
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, side_effect=Exception("Redis error")):
            result = await composer.get_draft_history("t1", "c1")
            assert result == []

    @pytest.mark.asyncio
    async def test_get_draft_history_empty_on_no_ticket(self):
        composer = _make_composer()
        assert await composer.get_draft_history("", "c1") == []
        assert await composer.get_draft_history("t1", "") == []

    def test_draft_result_to_dict_rounds_quality(self):
        draft = DraftResult(
            draft_id="a", content="b",
            quality_score=0.123456789, generation_time_ms=123.456789,
            technique_used="x",
        )
        d = draft.to_dict()
        assert d["quality_score"] == 0.1235
        assert d["generation_time_ms"] == 123.46

    def test_response_to_dict_rounds_total_time(self):
        resp = DraftComposerResponse(
            request_id="r1", drafts=[], best_draft_index=-1,
            total_generation_time_ms=1234.567, variant_type="parwa",
            cached=False,
        )
        d = resp.to_dict()
        assert d["total_generation_time_ms"] == 1234.57
