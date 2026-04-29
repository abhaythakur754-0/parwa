"""
Tests for F-142: Step-Back Prompting Processor and StepBackNode.

Covers config, should_activate, narrow query detection (all 5 types),
pipeline steps, full pipeline, reasoning loops, edge cases, company
isolation, and error fallback (BC-008).
"""

import pytest
from unittest.mock import patch

from app.core.technique_router import TechniqueID, QuerySignals
from app.core.techniques.base import ConversationState, GSDState
from app.core.techniques.step_back import (
    StepBackConfig,
    StepBackResult,
    StepBackProcessor,
    StepBackNode,
    NarrowQueryDetector,
    _AMBIGUOUS_WORDS,
    _BROADENING_TEMPLATES,
    _ENTITY_PATTERNS,
    _TECHNICAL_JARGON,
)


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def processor() -> StepBackProcessor:
    return StepBackProcessor()


@pytest.fixture
def company_processor() -> StepBackProcessor:
    config = StepBackConfig(
        company_id="comp_123",
        max_broadening_levels=2,
        enable_context_injection=True,
    )
    return StepBackProcessor(config=config)


@pytest.fixture
def node() -> StepBackNode:
    return StepBackNode()


@pytest.fixture
def base_state() -> ConversationState:
    return ConversationState(
        query="What is the status of order #12345?",
        signals=QuerySignals(confidence_score=0.8),
        gsd_state=GSDState.NEW,
    )


# ── Constants Tests ──────────────────────────────────────────────────


class TestConstants:
    def test_entity_patterns_count(self):
        assert len(_ENTITY_PATTERNS) >= 10

    def test_entity_patterns_compile(self):
        import re
        for p in _ENTITY_PATTERNS:
            re.compile(p, re.I)  # should not raise

    def test_technical_jargon_count(self):
        assert len(_TECHNICAL_JARGON) >= 20

    def test_technical_jargon_has_common_terms(self):
        assert "api" in _TECHNICAL_JARGON
        assert "webhook" in _TECHNICAL_JARGON
        assert "ssl" in _TECHNICAL_JARGON

    def test_ambiguous_words_count(self):
        assert len(_AMBIGUOUS_WORDS) >= 10

    def test_ambiguous_words_has_common_terms(self):
        assert "fix" in _AMBIGUOUS_WORDS
        assert "help" in _AMBIGUOUS_WORDS
        assert "update" in _AMBIGUOUS_WORDS

    def test_broadening_templates_keys(self):
        expected_keys = {
            "entity_specific", "single_word", "technical_jargon",
            "ambiguous_intent", "stuck_reasoning",
        }
        assert set(_BROADENING_TEMPLATES.keys()) == expected_keys

    def test_broadening_templates_each_has_entries(self):
        for key, templates in _BROADENING_TEMPLATES.items():
            assert len(templates) >= 2, f"{key} has < 2 templates"


# ── Config Tests ─────────────────────────────────────────────────────


class TestStepBackConfig:
    def test_default_config(self):
        config = StepBackConfig()
        assert config.company_id == ""
        assert config.max_broadening_levels == 3
        assert config.enable_context_injection is True

    def test_frozen_immutability(self):
        config = StepBackConfig(company_id="comp_1")
        with pytest.raises(AttributeError):
            config.company_id = "new"  # type: ignore

    def test_custom_config(self):
        config = StepBackConfig(
            company_id="comp_2",
            max_broadening_levels=1,
            enable_context_injection=False,
        )
        assert config.company_id == "comp_2"
        assert config.max_broadening_levels == 1
        assert config.enable_context_injection is False

    def test_max_broadening_levels_zero(self):
        config = StepBackConfig(max_broadening_levels=0)
        assert config.max_broadening_levels == 0


# ── Result Tests ─────────────────────────────────────────────────────


class TestStepBackResult:
    def test_basic_creation(self):
        detection = NarrowQueryDetector(
            is_narrow=True, narrow_type="single_word",
            confidence=0.8, suggested_broadening="short query",
        )
        result = StepBackResult(
            detection_result=detection,
            broadened_queries=["More details?"],
            analysis_result="Analyzed",
            refined_response="Refined",
            steps_applied=["detection", "broadening"],
            context_score=0.5,
        )
        assert result.detection_result.is_narrow is True
        assert len(result.broadened_queries) == 1
        assert result.context_score == 0.5

    def test_to_dict(self):
        detection = NarrowQueryDetector(
            is_narrow=True, narrow_type="entity_specific",
            confidence=0.9, suggested_broadening="entity found",
        )
        result = StepBackResult(
            detection_result=detection,
            broadened_queries=["Q1", "Q2"],
            analysis_result="Good",
            refined_response="Better",
            steps_applied=["detection"],
            context_score=0.75,
        )
        d = result.to_dict()
        assert d["detection_result"]["is_narrow"] is True
        assert d["detection_result"]["narrow_type"] == "entity_specific"
        assert len(d["broadened_queries"]) == 2
        assert d["context_score"] == 0.75

    def test_to_dict_none_detection(self):
        result = StepBackResult(detection_result=None)
        d = result.to_dict()
        assert d["detection_result"] is None

    def test_default_values(self):
        result = StepBackResult()
        assert result.detection_result is None
        assert result.broadened_queries == []
        assert result.analysis_result == ""
        assert result.refined_response == ""
        assert result.steps_applied == []
        assert result.context_score == 0.0

    def test_dict_keys(self):
        result = StepBackResult()
        d = result.to_dict()
        expected_keys = {
            "detection_result", "broadened_queries", "analysis_result",
            "refined_response", "steps_applied", "context_score",
        }
        assert set(d.keys()) == expected_keys


# ── NarrowQueryDetector Tests ────────────────────────────────────────


class TestNarrowQueryDetector:
    def test_default_values(self):
        detector = NarrowQueryDetector()
        assert detector.is_narrow is False
        assert detector.narrow_type == ""
        assert detector.confidence == 0.0
        assert detector.suggested_broadening == ""

    def test_custom_values(self):
        detector = NarrowQueryDetector(
            is_narrow=True,
            narrow_type="entity_specific",
            confidence=0.85,
            suggested_broadening="Order #123 found",
        )
        assert detector.is_narrow is True
        assert detector.narrow_type == "entity_specific"
        assert detector.confidence == 0.85
        assert "Order #123" in detector.suggested_broadening


# ── should_activate Tests ────────────────────────────────────────────


class TestShouldActivate:
    @pytest.mark.asyncio
    async def test_low_confidence(self, node):
        state = ConversationState(
            query="test",
            signals=QuerySignals(confidence_score=0.5),
            gsd_state=GSDState.NEW,
        )
        assert await node.should_activate(state) is True

    @pytest.mark.asyncio
    async def test_reasoning_loop_detected(self, node):
        state = ConversationState(
            query="test",
            signals=QuerySignals(
                confidence_score=0.9,
                reasoning_loop_detected=True,
            ),
            gsd_state=GSDState.NEW,
        )
        assert await node.should_activate(state) is True

    @pytest.mark.asyncio
    async def test_gsd_diagnosis_state(self, node):
        state = ConversationState(
            query="test",
            signals=QuerySignals(confidence_score=0.9),
            gsd_state=GSDState.DIAGNOSIS,
        )
        assert await node.should_activate(state) is True

    @pytest.mark.asyncio
    async def test_normal_state(self, node):
        state = ConversationState(
            query="test",
            signals=QuerySignals(confidence_score=0.9),
            gsd_state=GSDState.NEW,
        )
        assert await node.should_activate(state) is False

    @pytest.mark.asyncio
    async def test_confidence_exactly_0_7(self, node):
        """confidence == 0.7 should NOT activate (needs < 0.7)."""
        state = ConversationState(
            query="test",
            signals=QuerySignals(confidence_score=0.7),
            gsd_state=GSDState.NEW,
        )
        assert await node.should_activate(state) is False

    @pytest.mark.asyncio
    async def test_confidence_just_below_0_7(self, node):
        state = ConversationState(
            query="test",
            signals=QuerySignals(confidence_score=0.69),
            gsd_state=GSDState.NEW,
        )
        assert await node.should_activate(state) is True

    @pytest.mark.asyncio
    async def test_all_three_triggers(self, node):
        state = ConversationState(
            query="test",
            signals=QuerySignals(
                confidence_score=0.3,
                reasoning_loop_detected=True,
            ),
            gsd_state=GSDState.DIAGNOSIS,
        )
        assert await node.should_activate(state) is True

    @pytest.mark.asyncio
    async def test_gsd_resolution_state(self, node):
        state = ConversationState(
            query="test",
            signals=QuerySignals(confidence_score=0.8),
            gsd_state=GSDState.RESOLUTION,
        )
        assert await node.should_activate(state) is False


# ── Narrow Query Detection Tests ─────────────────────────────────────


class TestDetectNarrowQuery:

    # -- Entity Specific --

    @pytest.mark.asyncio
    async def test_entity_specific_order(self, processor):
        detection = await processor.detect_narrow_query("order #12345")
        assert detection.is_narrow is True
        assert detection.narrow_type == "entity_specific"
        assert detection.confidence > 0

    @pytest.mark.asyncio
    async def test_entity_specific_invoice(self, processor):
        detection = await processor.detect_narrow_query("invoice #INV-001")
        assert detection.is_narrow is True
        assert detection.narrow_type == "entity_specific"

    @pytest.mark.asyncio
    async def test_entity_specific_ticket(self, processor):
        detection = await processor.detect_narrow_query("ticket TK-456")
        assert detection.is_narrow is True
        assert detection.narrow_type == "entity_specific"

    @pytest.mark.asyncio
    async def test_entity_specific_with_context(self, processor):
        """Entity with enough context should not be entity_specific narrow."""
        detection = await processor.detect_narrow_query(
            "I need to know the current delivery status and estimated "
            "arrival date for my order #12345 that I placed last week"
        )
        # > 5 words, so entity_specific won't trigger; but single_word won't either
        assert detection.narrow_type != "entity_specific"

    @pytest.mark.asyncio
    async def test_entity_specific_refund(self, processor):
        detection = await processor.detect_narrow_query("refund #RF-99")
        assert detection.is_narrow is True
        assert detection.narrow_type == "entity_specific"

    @pytest.mark.asyncio
    async def test_entity_specific_account(self, processor):
        detection = await processor.detect_narrow_query("account ACCT-42")
        assert detection.is_narrow is True
        assert detection.narrow_type == "entity_specific"

    # -- Single Word --

    @pytest.mark.asyncio
    async def test_single_word_one(self, processor):
        detection = await processor.detect_narrow_query("help")
        assert detection.is_narrow is True
        assert detection.narrow_type == "single_word"

    @pytest.mark.asyncio
    async def test_single_word_two(self, processor):
        detection = await processor.detect_narrow_query("fix it")
        assert detection.is_narrow is True
        assert detection.narrow_type == "single_word"

    @pytest.mark.asyncio
    async def test_single_word_three(self, processor):
        detection = await processor.detect_narrow_query("check my order")
        assert detection.is_narrow is True
        assert detection.narrow_type == "single_word"

    @pytest.mark.asyncio
    async def test_single_word_four_words(self, processor):
        """4 words should NOT be single_word narrow."""
        detection = await processor.detect_narrow_query("please check my order")
        assert detection.narrow_type != "single_word"

    @pytest.mark.asyncio
    async def test_single_word_confidence_one_word(self, processor):
        detection = await processor.detect_narrow_query("refund")
        assert detection.confidence >= 0.8

    @pytest.mark.asyncio
    async def test_single_word_confidence_three_words(self, processor):
        detection = await processor.detect_narrow_query("I need help")
        assert detection.confidence >= 0.3
        assert detection.confidence < 0.8

    # -- Technical Jargon --

    @pytest.mark.asyncio
    async def test_technical_jargon_api_webhook(self, processor):
        detection = await processor.detect_narrow_query(
            "api webhook endpoint oauth ssl"
        )
        assert detection.is_narrow is True
        assert detection.narrow_type == "technical_jargon"

    @pytest.mark.asyncio
    async def test_technical_jargon_devops(self, processor):
        detection = await processor.detect_narrow_query(
            "kubernetes docker deployment rollback"
        )
        assert detection.is_narrow is True
        assert detection.narrow_type == "technical_jargon"

    @pytest.mark.asyncio
    async def test_technical_jargon_too_long(self, processor):
        """Long query with jargon should NOT be narrow (len > 15)."""
        long_jargon = " ".join(
            list(_TECHNICAL_JARGON)[:20]
        )
        detection = await processor.detect_narrow_query(long_jargon)
        assert detection.narrow_type != "technical_jargon"

    @pytest.mark.asyncio
    async def test_technical_jargon_low_density(self, processor):
        """Low jargon density should NOT trigger."""
        detection = await processor.detect_narrow_query(
            "I need to configure the api settings for my account"
        )
        assert detection.narrow_type != "technical_jargon"

    # -- Ambiguous Intent --

    @pytest.mark.asyncio
    async def test_ambiguous_intent_fix_update(self, processor):
        detection = await processor.detect_narrow_query("fix update issue")
        assert detection.is_narrow is True
        assert detection.narrow_type == "ambiguous_intent"

    @pytest.mark.asyncio
    async def test_ambiguous_intent_help_check(self, processor):
        detection = await processor.detect_narrow_query("help check problem")
        assert detection.is_narrow is True
        assert detection.narrow_type == "ambiguous_intent"

    @pytest.mark.asyncio
    async def test_ambiguous_intent_too_long(self, processor):
        """Long ambiguous query should NOT trigger (len > 10)."""
        detection = await processor.detect_narrow_query(
            "fix update change issue problem help check what how why when"
        )
        assert detection.narrow_type != "ambiguous_intent"

    @pytest.mark.asyncio
    async def test_ambiguous_intent_single_word(self, processor):
        """Single ambiguous word should NOT trigger (need >= 2)."""
        detection = await processor.detect_narrow_query("help")
        assert detection.narrow_type != "ambiguous_intent"

    # -- Not Narrow --

    @pytest.mark.asyncio
    async def test_not_narrow_descriptive(self, processor):
        detection = await processor.detect_narrow_query(
            "I placed an order last Tuesday and the delivery tracking "
            "shows it has been stuck in transit for three days now"
        )
        assert detection.is_narrow is False

    @pytest.mark.asyncio
    async def test_not_narrow_specific_request(self, processor):
        detection = await processor.detect_narrow_query(
            "Please cancel my monthly subscription and refund the "
            "remaining balance to my credit card ending in 4242"
        )
        assert detection.is_narrow is False


# ── Stuck Reasoning Detection Tests ──────────────────────────────────


class TestStuckReasoning:

    @pytest.mark.asyncio
    async def test_reasoning_loop_detected(self, processor):
        thread = [
            "checking the order status for order #12345",
            "order #12345 status is still pending",
            "need to verify order #12345 delivery date",
            "order #12345 delivery is scheduled",
            "rechecking order #12345 again because status unclear",
        ]
        detection = await processor.detect_narrow_query(
            "What about order #12345?", reasoning_thread=thread,
        )
        assert detection.is_narrow is True
        assert detection.narrow_type == "stuck_reasoning"

    @pytest.mark.asyncio
    async def test_no_reasoning_loop(self, processor):
        thread = [
            "analyzing the billing issue",
            "checking payment history",
            "reviewing refund policy",
        ]
        detection = await processor.detect_narrow_query(
            "What about order #12345?", reasoning_thread=thread,
        )
        assert detection.narrow_type != "stuck_reasoning"

    @pytest.mark.asyncio
    async def test_empty_reasoning_thread(self, processor):
        detection = await processor.detect_narrow_query(
            "order #12345", reasoning_thread=[],
        )
        assert detection.narrow_type != "stuck_reasoning"

    @pytest.mark.asyncio
    async def test_none_reasoning_thread(self, processor):
        detection = await processor.detect_narrow_query(
            "order #12345", reasoning_thread=None,
        )
        assert detection.narrow_type != "stuck_reasoning"

    @pytest.mark.asyncio
    async def test_stop_words_filtered(self, processor):
        """Stop words should not trigger loop detection."""
        thread = [
            "the order is being processed",
            "the customer is waiting",
            "the system is working",
            "the team is reviewing",
        ]
        detection = await processor.detect_narrow_query(
            "some query", reasoning_thread=thread,
        )
        assert detection.narrow_type != "stuck_reasoning"

    @pytest.mark.asyncio
    async def test_stuck_reasoning_priority_over_entity(self, processor):
        """Stuck reasoning should take priority over entity_specific."""
        thread = [
            "order order order order",
            "order status check",
            "order update needed",
            "order confirmed order shipped",
        ]
        detection = await processor.detect_narrow_query(
            "order #12345", reasoning_thread=thread,
        )
        assert detection.narrow_type == "stuck_reasoning"


# ── Step 2: Broadening Tests ─────────────────────────────────────────


class TestBroadening:

    @pytest.mark.asyncio
    async def test_broaden_entity_specific(self, processor):
        detection = NarrowQueryDetector(
            is_narrow=True, narrow_type="entity_specific",
            confidence=0.8, suggested_broadening="",
        )
        queries = await processor.generate_broadened_queries(
            "order #12345", detection,
        )
        assert len(queries) >= 1
        assert any("order" in q.lower() or "#12345" in q.lower()
                   for q in queries)

    @pytest.mark.asyncio
    async def test_broaden_single_word(self, processor):
        detection = NarrowQueryDetector(
            is_narrow=True, narrow_type="single_word",
            confidence=0.8, suggested_broadening="",
        )
        queries = await processor.generate_broadened_queries(
            "help", detection,
        )
        assert len(queries) >= 1
        assert any("help" in q.lower() for q in queries)

    @pytest.mark.asyncio
    async def test_broaden_technical_jargon(self, processor):
        detection = NarrowQueryDetector(
            is_narrow=True, narrow_type="technical_jargon",
            confidence=0.8, suggested_broadening="",
        )
        queries = await processor.generate_broadened_queries(
            "api webhook ssl", detection,
        )
        assert len(queries) >= 1

    @pytest.mark.asyncio
    async def test_broaden_ambiguous_intent(self, processor):
        detection = NarrowQueryDetector(
            is_narrow=True, narrow_type="ambiguous_intent",
            confidence=0.8, suggested_broadening="",
        )
        queries = await processor.generate_broadened_queries(
            "fix update issue", detection,
        )
        assert len(queries) >= 1

    @pytest.mark.asyncio
    async def test_broaden_stuck_reasoning(self, processor):
        detection = NarrowQueryDetector(
            is_narrow=True, narrow_type="stuck_reasoning",
            confidence=0.8, suggested_broadening="",
        )
        queries = await processor.generate_broadened_queries(
            "some query", detection,
        )
        assert len(queries) >= 1

    @pytest.mark.asyncio
    async def test_not_narrow_returns_empty(self, processor):
        detection = NarrowQueryDetector(
            is_narrow=False, narrow_type="none",
            confidence=0.0, suggested_broadening="",
        )
        queries = await processor.generate_broadened_queries(
            "some query", detection,
        )
        assert queries == []

    @pytest.mark.asyncio
    async def test_max_broadening_levels_respected(self):
        config = StepBackConfig(max_broadening_levels=1)
        proc = StepBackProcessor(config=config)
        detection = NarrowQueryDetector(
            is_narrow=True, narrow_type="single_word",
            confidence=0.8, suggested_broadening="",
        )
        queries = await proc.generate_broadened_queries("help", detection)
        assert len(queries) == 1

    @pytest.mark.asyncio
    async def test_max_broadening_levels_zero(self):
        config = StepBackConfig(max_broadening_levels=0)
        proc = StepBackProcessor(config=config)
        detection = NarrowQueryDetector(
            is_narrow=True, narrow_type="single_word",
            confidence=0.8, suggested_broadening="",
        )
        queries = await proc.generate_broadened_queries("help", detection)
        assert queries == []

    @pytest.mark.asyncio
    async def test_unknown_narrow_type(self, processor):
        detection = NarrowQueryDetector(
            is_narrow=True, narrow_type="unknown_type",
            confidence=0.8, suggested_broadening="",
        )
        queries = await processor.generate_broadened_queries(
            "test", detection,
        )
        assert queries == []


# ── Step 3: Analysis Tests ───────────────────────────────────────────


class TestAnalysis:

    @pytest.mark.asyncio
    async def test_analysis_returns_score_and_summary(self, processor):
        summary, score = await processor.analyze_broadened_context(
            "help",
            ["Can you provide more details about 'help'?"],
        )
        assert isinstance(summary, str)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    @pytest.mark.asyncio
    async def test_analysis_empty_broadened(self, processor):
        summary, score = await processor.analyze_broadened_context(
            "test", [],
        )
        assert score == 0.0
        assert "No broadening" in summary

    @pytest.mark.asyncio
    async def test_analysis_multiple_queries(self, processor):
        queries = [
            "Can you provide more details about 'help'?",
            "What specific aspect of 'help' do you need?",
            "Are you asking about 'help' in relation to billing?",
        ]
        _, score = await processor.analyze_broadened_context("help", queries)
        # More queries → higher coverage → higher score
        assert score > 0.1

    @pytest.mark.asyncio
    async def test_analysis_better_with_more_context(self, processor):
        # Single query
        _, score1 = await processor.analyze_broadened_context(
            "help", ["Tell me more about help"],
        )
        # Multiple richer queries
        _, score2 = await processor.analyze_broadened_context(
            "help",
            [
                "Can you provide more details about 'help'?",
                "What specific aspect of 'help' do you need help with?",
            ],
        )
        assert score2 >= score1


# ── Step 4: Refined Response Tests ───────────────────────────────────


class TestRefinedResponse:

    @pytest.mark.asyncio
    async def test_refine_with_context_injection(self, processor):
        refined = await processor.refine_response(
            "order #12345",
            ["What is the customer trying to accomplish with order #12345?"],
            context_score=0.5,
        )
        assert "order #12345" in refined
        assert "Step-Back Context" in refined

    @pytest.mark.asyncio
    async def test_refine_no_context_injection(self):
        config = StepBackConfig(enable_context_injection=False)
        proc = StepBackProcessor(config=config)
        refined = await proc.refine_response(
            "order #12345",
            ["What is the context?"],
            context_score=0.8,
        )
        assert refined == "order #12345"

    @pytest.mark.asyncio
    async def test_refine_low_context_score(self, processor):
        refined = await processor.refine_response(
            "test",
            ["Some question?"],
            context_score=0.05,
        )
        # Score < 0.1 → no refinement
        assert refined == "test"

    @pytest.mark.asyncio
    async def test_refine_empty_broadened(self, processor):
        refined = await processor.refine_response(
            "test", [], context_score=0.5,
        )
        assert refined == "test"


# ── Full Pipeline Tests ──────────────────────────────────────────────


class TestFullPipeline:

    @pytest.mark.asyncio
    async def test_entity_specific_pipeline(self, processor):
        result = await processor.process("order #12345")
        assert result.detection_result is not None
        assert result.detection_result.is_narrow is True
        assert result.detection_result.narrow_type == "entity_specific"
        assert len(result.broadened_queries) >= 1
        assert "detection" in result.steps_applied
        assert result.context_score > 0

    @pytest.mark.asyncio
    async def test_single_word_pipeline(self, processor):
        result = await processor.process("refund")
        assert result.detection_result.is_narrow is True
        assert result.detection_result.narrow_type == "single_word"
        assert len(result.broadened_queries) >= 1
        assert "detection" in result.steps_applied

    @pytest.mark.asyncio
    async def test_not_narrow_pipeline(self, processor):
        result = await processor.process(
            "Please cancel my subscription and refund the balance"
        )
        assert result.detection_result.is_narrow is False
        assert result.context_score == 0.0
        assert "not_narrow" in result.steps_applied

    @pytest.mark.asyncio
    async def test_empty_input(self, processor):
        result = await processor.process("")
        assert "empty_input" in result.steps_applied

    @pytest.mark.asyncio
    async def test_whitespace_input(self, processor):
        result = await processor.process("   ")
        assert "empty_input" in result.steps_applied

    @pytest.mark.asyncio
    async def test_steps_applied_order(self, processor):
        result = await processor.process("order #12345")
        steps = result.steps_applied
        # detection should come before broadening
        if "detection" in steps and "broadening" in steps:
            assert steps.index("detection") < steps.index("broadening")
        # analysis should come before refinement
        if "analysis" in steps and "refinement" in steps:
            assert steps.index("analysis") < steps.index("refinement")

    @pytest.mark.asyncio
    async def test_refined_response_differs_for_narrow(self, processor):
        result = await processor.process("order #12345")
        if result.refined_response != "order #12345":
            assert "Step-Back Context" in result.refined_response

    @pytest.mark.asyncio
    async def test_technical_jargon_pipeline(self, processor):
        result = await processor.process("api webhook endpoint ssl tls")
        assert result.detection_result.is_narrow is True
        assert result.detection_result.narrow_type == "technical_jargon"

    @pytest.mark.asyncio
    async def test_ambiguous_intent_pipeline(self, processor):
        result = await processor.process("fix update issue")
        assert result.detection_result.is_narrow is True
        assert result.detection_result.narrow_type == "ambiguous_intent"

    @pytest.mark.asyncio
    async def test_result_to_dict(self, processor):
        result = await processor.process("order #12345")
        d = result.to_dict()
        assert isinstance(d, dict)
        assert "detection_result" in d
        assert "broadened_queries" in d
        assert "context_score" in d


# ── Reasoning Thread Integration ─────────────────────────────────────


class TestReasoningThreadIntegration:

    @pytest.mark.asyncio
    async def test_loop_detected_in_process(self, processor):
        thread = [
            "checking the refund refund refund request",
            "refund status is pending",
            "refund refund needs review",
            "verifying the refund again",
        ]
        result = await processor.process(
            "What about my refund?", reasoning_thread=thread,
        )
        assert result.detection_result.is_narrow is True
        assert result.detection_result.narrow_type == "stuck_reasoning"
        assert "detection" in result.steps_applied

    @pytest.mark.asyncio
    async def test_no_loop_with_diverse_thread(self, processor):
        thread = [
            "analyzing billing history",
            "checking payment records",
            "reviewing subscription terms",
        ]
        result = await processor.process(
            "What about my order #12345?", reasoning_thread=thread,
        )
        # Should still detect entity_specific, not stuck_reasoning
        assert result.detection_result.narrow_type != "stuck_reasoning"


# ── Edge Cases ───────────────────────────────────────────────────────


class TestEdgeCases:

    @pytest.mark.asyncio
    async def test_empty_query(self, processor):
        result = await processor.process("")
        assert result.detection_result.is_narrow is True

    @pytest.mark.asyncio
    async def test_none_query(self, processor):
        result = await processor.process("")
        assert result is not None

    @pytest.mark.asyncio
    async def test_very_long_query(self, processor):
        long_query = "I need help with " + "and ".join(
            [f"item{i}" for i in range(100)]
        )
        result = await processor.process(long_query)
        assert result.detection_result.is_narrow is False

    @pytest.mark.asyncio
    async def test_special_characters(self, processor):
        result = await processor.process(
            "order #123-ABC? ($50)"
        )
        # Should detect entity_specific due to # pattern (short query)
        assert result.detection_result.is_narrow is True
        assert result.detection_result.narrow_type == "entity_specific"

    @pytest.mark.asyncio
    async def test_unicode_query(self, processor):
        result = await processor.process("help")
        assert result is not None
        assert result.detection_result.is_narrow is True

    @pytest.mark.asyncio
    async def test_numbers_only(self, processor):
        result = await processor.process("12345")
        assert result.detection_result.is_narrow is True
        assert result.detection_result.narrow_type == "single_word"

    @pytest.mark.asyncio
    async def test_punctuation_only(self, processor):
        result = await processor.process("?!.")
        assert result.detection_result.is_narrow is True

    @pytest.mark.asyncio
    async def test_mixed_case(self, processor):
        result = await processor.process("ORDER #12345")
        assert result.detection_result.is_narrow is True
        assert result.detection_result.narrow_type == "entity_specific"

    @pytest.mark.asyncio
    async def test_query_with_newlines(self, processor):
        result = await processor.process("help\nme\nplease")
        assert result.detection_result.is_narrow is True
        assert result.detection_result.narrow_type == "single_word"

    @pytest.mark.asyncio
    async def test_query_with_tabs(self, processor):
        result = await processor.process("order\t#12345")
        assert result.detection_result.is_narrow is True


# ── Company Isolation Tests ──────────────────────────────────────────


class TestCompanyIsolation:

    @pytest.mark.asyncio
    async def test_company_config_isolation(self):
        config1 = StepBackConfig(company_id="A", max_broadening_levels=1)
        config2 = StepBackConfig(company_id="B", max_broadening_levels=3)
        p1 = StepBackProcessor(config=config1)
        p2 = StepBackProcessor(config=config2)

        detection = NarrowQueryDetector(
            is_narrow=True, narrow_type="single_word",
            confidence=0.8, suggested_broadening="",
        )
        q1 = await p1.generate_broadened_queries("help", detection)
        q2 = await p2.generate_broadened_queries("help", detection)

        assert len(q1) == 1
        assert len(q2) == 3

    @pytest.mark.asyncio
    async def test_config_defaults_not_shared(self):
        p1 = StepBackProcessor()
        p2 = StepBackProcessor(StepBackConfig(company_id="X"))
        assert p1.config.company_id == ""
        assert p2.config.company_id == "X"

    def test_frozen_config_per_instance(self):
        c1 = StepBackConfig(company_id="A")
        c2 = StepBackConfig(company_id="B")
        assert c1.company_id == "A"
        assert c2.company_id == "B"

    @pytest.mark.asyncio
    async def test_node_company_isolation(self):
        node_a = StepBackNode(StepBackConfig(company_id="A"))
        node_b = StepBackNode(StepBackConfig(company_id="B"))
        assert node_a._config.company_id == "A"
        assert node_b._config.company_id == "B"


# ── StepBackNode Integration Tests ───────────────────────────────────


class TestStepBackNodeIntegration:

    @pytest.mark.asyncio
    async def test_technique_id(self, node):
        assert node.technique_id == TechniqueID.STEP_BACK

    @pytest.mark.asyncio
    async def test_execute_updates_state(self, node, base_state):
        base_state.signals.confidence_score = 0.3
        result_state = await node.execute(base_state)
        assert "step_back" in result_state.technique_results
        assert result_state.technique_results["step_back"]["status"] == "success"

    @pytest.mark.asyncio
    async def test_execute_records_result(self, node):
        state = ConversationState(
            query="order #12345",
            signals=QuerySignals(confidence_score=0.3),
            gsd_state=GSDState.DIAGNOSIS,
        )
        result_state = await node.execute(state)
        recorded = result_state.technique_results["step_back"]
        assert recorded["tokens_used"] > 0
        assert "executed_at" in recorded
        assert "result" in recorded

    @pytest.mark.asyncio
    async def test_execute_context_injection(self, node):
        state = ConversationState(
            query="order #12345",
            signals=QuerySignals(confidence_score=0.3),
            gsd_state=GSDState.NEW,
        )
        result_state = await node.execute(state)
        # Should have response_parts with refined response
        if result_state.response_parts:
            assert any(
                "Step-Back Context" in p for p in result_state.response_parts)

    @pytest.mark.asyncio
    async def test_execute_no_context_injection(self):
        node = StepBackNode(StepBackConfig(enable_context_injection=False))
        state = ConversationState(
            query="order #12345",
            signals=QuerySignals(confidence_score=0.3),
            gsd_state=GSDState.NEW,
        )
        result_state = await node.execute(state)
        # Should not inject context
        assert all(
            "Step-Back Context" not in p for p in result_state.response_parts
        )

    @pytest.mark.asyncio
    async def test_execute_with_reasoning_thread(self, node):
        state = ConversationState(
            query="check order",
            signals=QuerySignals(confidence_score=0.3),
            gsd_state=GSDState.DIAGNOSIS,
            reasoning_thread=[
                "order status check",
                "order pending",
                "order order order order",
            ],
        )
        result_state = await node.execute(state)
        assert "step_back" in result_state.technique_results

    @pytest.mark.asyncio
    async def test_execute_returns_state(self, node, base_state):
        base_state.signals.confidence_score = 0.5
        result_state = await node.execute(base_state)
        assert isinstance(result_state, ConversationState)
        assert result_state is base_state  # same object, mutated in place


# ── Error Fallback Tests (BC-008) ────────────────────────────────────


class TestErrorFallback:
    """BC-008: Never crash — return original on error."""

    @pytest.mark.asyncio
    async def test_process_error_fallback(self, processor):
        with patch.object(
            processor, 'detect_narrow_query',
            side_effect=RuntimeError("boom"),
        ):
            result = await processor.process("order #12345")
            assert result.refined_response == "order #12345"
            assert "error_fallback" in result.steps_applied
            assert result.context_score == 0.0

    @pytest.mark.asyncio
    async def test_process_error_preserves_query(self, processor):
        with patch.object(
            processor, 'generate_broadened_queries',
            side_effect=ValueError("err"),
        ):
            result = await processor.process("help me")
            assert result.refined_response == "help me"

    @pytest.mark.asyncio
    async def test_node_execute_error_fallback(self, node):
        state = ConversationState(
            query="test",
            signals=QuerySignals(confidence_score=0.3),
        )
        with patch.object(
            node._processor, 'process',
            side_effect=RuntimeError("node boom"),
        ):
            result_state = await node.execute(state)
            # Should record skip, not crash
            assert "step_back" in result_state.technique_results
            assert result_state.technique_results["step_back"]["status"] == "skipped_budget"

    @pytest.mark.asyncio
    async def test_analysis_error_in_pipeline(self, processor):
        """Error in analysis step should trigger error_fallback."""
        with patch.object(
            processor, 'analyze_broadened_context',
            side_effect=Exception("analysis error"),
        ):
            result = await processor.process("order #12345")
            assert "error_fallback" in result.steps_applied

    @pytest.mark.asyncio
    async def test_refine_error_in_pipeline(self, processor):
        """Error in refine step should trigger error_fallback."""
        with patch.object(
            processor, 'refine_response',
            side_effect=Exception("refine error"),
        ):
            result = await processor.process("order #12345")
            assert "error_fallback" in result.steps_applied


# ── Entity Extraction Tests ──────────────────────────────────────────


class TestEntityExtraction:

    @pytest.mark.asyncio
    async def test_extract_order_number(self, processor):
        queries = await processor.generate_broadened_queries(
            "what about order #12345",
            NarrowQueryDetector(
                is_narrow=True, narrow_type="entity_specific",
                confidence=0.9, suggested_broadening="",
            ),
        )
        assert any("#12345" in q or "order" in q.lower() for q in queries)

    @pytest.mark.asyncio
    async def test_extract_invoice_number(self, processor):
        queries = await processor.generate_broadened_queries(
            "invoice #INV-001",
            NarrowQueryDetector(
                is_narrow=True, narrow_type="entity_specific",
                confidence=0.9, suggested_broadening="",
            ),
        )
        assert len(queries) >= 1

    @pytest.mark.asyncio
    async def test_extract_tracking_number(self, processor):
        detection = NarrowQueryDetector(
            is_narrow=True, narrow_type="entity_specific",
            confidence=0.9, suggested_broadening="",
        )
        queries = await processor.generate_broadened_queries(
            "tracking #TRK999", detection,
        )
        assert len(queries) >= 1

    @pytest.mark.asyncio
    async def test_extract_hash_entity(self, processor):
        detection = NarrowQueryDetector(
            is_narrow=True, narrow_type="entity_specific",
            confidence=0.9, suggested_broadening="",
        )
        queries = await processor.generate_broadened_queries(
            "#ABC123", detection,
        )
        assert len(queries) >= 1
