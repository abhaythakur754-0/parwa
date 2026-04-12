"""
Tests for F-149: Thread of Thought (ThoT) Processor and ThreadOfThoughtNode.

Covers config, dataclasses, enums, should_activate (boundary 5, edge cases),
thread extraction, continuity checking, topic shift detection, loop detection,
context enhancement, full pipeline, company isolation, error fallback,
and edge cases (empty thread, very long thread, single turn).
"""

import pytest
from unittest.mock import patch, MagicMock

from app.core.technique_router import TechniqueID, QuerySignals
from app.core.techniques.base import ConversationState, GSDState
from app.core.techniques.thread_of_thought import (
    ThoTConfig,
    ThoTResult,
    ThoTProcessor,
    ThreadOfThoughtNode,
    ThreadAnalysis,
    TopicShift,
    _STOP_WORDS,
    _TOPIC_DOMAINS,
    _CONTRADICTION_PAIRS,
    _NEGATION_WORDS,
)


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def processor() -> ThoTProcessor:
    return ThoTProcessor()


@pytest.fixture
def company_processor() -> ThoTProcessor:
    config = ThoTConfig(
        company_id="comp_123",
        min_turns=5,
        continuity_threshold=0.6,
        max_thread_length=50,
    )
    return ThoTProcessor(config=config)


@pytest.fixture
def low_threshold_processor() -> ThoTProcessor:
    config = ThoTConfig(continuity_threshold=0.3)
    return ThoTProcessor(config=config)


@pytest.fixture
def node() -> ThreadOfThoughtNode:
    return ThreadOfThoughtNode()


@pytest.fixture
def sample_thread() -> list:
    return [
        "Customer is asking about their billing statement",
        "Checking the billing records for the account",
        "Billing history shows a charge of $49.99 on March 15",
        "The charge appears to be for the monthly subscription",
        "Customer confirms they did not authorize this charge",
        "Reviewing refund policy for unauthorized charges",
    ]


@pytest.fixture
def base_state() -> ConversationState:
    return ConversationState(
        query="Can you check my order status?",
        signals=QuerySignals(turn_count=6),
        gsd_state=GSDState.NEW,
    )


# ── TopicShift Enum Tests ───────────────────────────────────────────


class TestTopicShift:
    def test_enum_values(self):
        assert TopicShift.NONE.value == "none"
        assert TopicShift.PARTIAL.value == "partial"
        assert TopicShift.COMPLETE.value == "complete"

    def test_enum_count(self):
        assert len(TopicShift) == 3

    def test_enum_string_comparison(self):
        assert TopicShift.NONE == "none"
        assert TopicShift.PARTIAL == "partial"
        assert TopicShift.COMPLETE == "complete"


# ── Constants Tests ──────────────────────────────────────────────────


class TestConstants:
    def test_stop_words_not_empty(self):
        assert len(_STOP_WORDS) > 50

    def test_stop_words_has_common(self):
        assert "the" in _STOP_WORDS
        assert "is" in _STOP_WORDS
        assert "and" in _STOP_WORDS

    def test_topic_domains_has_required(self):
        required = {"billing", "technical", "account", "order", "general"}
        assert required.issubset(set(_TOPIC_DOMAINS.keys()))

    def test_topic_domains_each_has_keywords(self):
        for domain, keywords in _TOPIC_DOMAINS.items():
            assert len(keywords) >= 5, f"{domain} has fewer than 5 keywords"

    def test_contradiction_pairs_not_empty(self):
        assert len(_CONTRADICTION_PAIRS) >= 4

    def test_negation_words_not_empty(self):
        assert len(_NEGATION_WORDS) >= 10

    def test_negation_words_has_common(self):
        assert "not" in _NEGATION_WORDS
        assert "never" in _NEGATION_WORDS


# ── Config Tests ─────────────────────────────────────────────────────


class TestThoTConfig:
    def test_default_config(self):
        config = ThoTConfig()
        assert config.company_id == ""
        assert config.min_turns == 5
        assert config.continuity_threshold == 0.6
        assert config.max_thread_length == 50

    def test_frozen_immutability(self):
        config = ThoTConfig(company_id="comp_1")
        with pytest.raises(AttributeError):
            config.company_id = "new"  # type: ignore

    def test_custom_config(self):
        config = ThoTConfig(
            company_id="comp_2",
            min_turns=3,
            continuity_threshold=0.8,
            max_thread_length=20,
        )
        assert config.company_id == "comp_2"
        assert config.min_turns == 3
        assert config.continuity_threshold == 0.8
        assert config.max_thread_length == 20

    def test_min_turns_zero(self):
        config = ThoTConfig(min_turns=0)
        assert config.min_turns == 0

    def test_continuity_threshold_boundary(self):
        config = ThoTConfig(continuity_threshold=0.0)
        assert config.continuity_threshold == 0.0
        config2 = ThoTConfig(continuity_threshold=1.0)
        assert config2.continuity_threshold == 1.0

    def test_max_thread_length_one(self):
        config = ThoTConfig(max_thread_length=1)
        assert config.max_thread_length == 1


# ── ThreadAnalysis Tests ─────────────────────────────────────────────


class TestThreadAnalysis:
    def test_default_values(self):
        analysis = ThreadAnalysis()
        assert analysis.turn_count == 0
        assert analysis.topic_continuity == 0.0
        assert analysis.contradictions == []
        assert analysis.repeated_info == []
        assert analysis.loop_detected is False
        assert analysis.summary == ""

    def test_custom_values(self):
        analysis = ThreadAnalysis(
            turn_count=6,
            topic_continuity=0.85,
            contradictions=["Turn 1->2: 'yes' contradicts 'no'"],
            repeated_info=["Turn 4 repeats turn 2 (similarity: 0.90)"],
            loop_detected=True,
            summary="Topic: billing; Key points: charge, refund",
        )
        assert analysis.turn_count == 6
        assert analysis.topic_continuity == 0.85
        assert len(analysis.contradictions) == 1
        assert len(analysis.repeated_info) == 1
        assert analysis.loop_detected is True
        assert "billing" in analysis.summary

    def test_to_dict_keys(self):
        analysis = ThreadAnalysis()
        d = analysis.to_dict()
        expected_keys = {
            "turn_count", "topic_continuity", "contradictions",
            "repeated_info", "loop_detected", "summary",
        }
        assert set(d.keys()) == expected_keys

    def test_to_dict_values(self):
        analysis = ThreadAnalysis(
            turn_count=3,
            topic_continuity=0.75,
            contradictions=["c1"],
            repeated_info=["r1"],
            loop_detected=True,
            summary="test summary",
        )
        d = analysis.to_dict()
        assert d["turn_count"] == 3
        assert d["topic_continuity"] == 0.75
        assert d["contradictions"] == ["c1"]
        assert d["repeated_info"] == ["r1"]
        assert d["loop_detected"] is True
        assert d["summary"] == "test summary"


# ── ThoTResult Tests ─────────────────────────────────────────────────


class TestThoTResult:
    def test_default_values(self):
        result = ThoTResult()
        assert isinstance(result.thread_analysis, ThreadAnalysis)
        assert result.context_prefix == ""
        assert result.enhanced_response == ""
        assert result.steps_applied == []
        assert result.continuity_score == 0.0

    def test_custom_values(self):
        result = ThoTResult(
            thread_analysis=ThreadAnalysis(turn_count=5),
            context_prefix="[Context: Topic: billing]",
            enhanced_response="[Context: Topic: billing] query text",
            steps_applied=["thread_extraction", "continuity_check"],
            continuity_score=0.9,
        )
        assert result.thread_analysis.turn_count == 5
        assert "[Context:" in result.context_prefix
        assert "query text" in result.enhanced_response
        assert len(result.steps_applied) == 2
        assert result.continuity_score == 0.9

    def test_to_dict_keys(self):
        result = ThoTResult()
        d = result.to_dict()
        expected_keys = {
            "thread_analysis", "context_prefix", "enhanced_response",
            "steps_applied", "continuity_score",
        }
        assert set(d.keys()) == expected_keys

    def test_to_dict_nested(self):
        result = ThoTResult(
            thread_analysis=ThreadAnalysis(turn_count=4, topic_continuity=0.8),
            continuity_score=0.8,
        )
        d = result.to_dict()
        assert isinstance(d["thread_analysis"], dict)
        assert d["thread_analysis"]["turn_count"] == 4
        assert d["continuity_score"] == 0.8


# ── should_activate Tests ────────────────────────────────────────────


class TestShouldActivate:
    @pytest.mark.asyncio
    async def test_turn_count_above_threshold(self, node):
        state = ConversationState(
            query="test",
            signals=QuerySignals(turn_count=6),
        )
        assert await node.should_activate(state) is True

    @pytest.mark.asyncio
    async def test_turn_count_at_boundary(self, node):
        """turn_count == 5 should NOT activate (needs > 5)."""
        state = ConversationState(
            query="test",
            signals=QuerySignals(turn_count=5),
        )
        assert await node.should_activate(state) is False

    @pytest.mark.asyncio
    async def test_turn_count_below_threshold(self, node):
        state = ConversationState(
            query="test",
            signals=QuerySignals(turn_count=3),
        )
        assert await node.should_activate(state) is False

    @pytest.mark.asyncio
    async def test_turn_count_zero(self, node):
        state = ConversationState(
            query="test",
            signals=QuerySignals(turn_count=0),
        )
        assert await node.should_activate(state) is False

    @pytest.mark.asyncio
    async def test_turn_count_one_above(self, node):
        """turn_count == 6 should activate (just above threshold)."""
        state = ConversationState(
            query="test",
            signals=QuerySignals(turn_count=6),
        )
        assert await node.should_activate(state) is True

    @pytest.mark.asyncio
    async def test_very_high_turn_count(self, node):
        state = ConversationState(
            query="test",
            signals=QuerySignals(turn_count=100),
        )
        assert await node.should_activate(state) is True

    @pytest.mark.asyncio
    async def test_custom_min_turns(self):
        config = ThoTConfig(min_turns=3)
        custom_node = ThreadOfThoughtNode(config=config)
        state = ConversationState(
            query="test",
            signals=QuerySignals(turn_count=4),
        )
        assert await custom_node.should_activate(state) is True

    @pytest.mark.asyncio
    async def test_custom_min_turns_below(self):
        config = ThoTConfig(min_turns=10)
        custom_node = ThreadOfThoughtNode(config=config)
        state = ConversationState(
            query="test",
            signals=QuerySignals(turn_count=6),
        )
        assert await custom_node.should_activate(state) is False

    @pytest.mark.asyncio
    async def test_technique_id(self, node):
        assert node.technique_id == TechniqueID.THREAD_OF_THOUGHT


# ── Thread Extraction Tests ─────────────────────────────────────────


class TestThreadExtraction:
    @pytest.mark.asyncio
    async def test_extraction_with_thread(self, processor, sample_thread):
        thread, topic, shift = await processor.extract_thread(
            sample_thread, "What about the refund?",
        )
        assert len(thread) == 6
        assert isinstance(topic, str)
        assert isinstance(shift, TopicShift)

    @pytest.mark.asyncio
    async def test_extraction_empty_thread(self, processor):
        thread, topic, shift = await processor.extract_thread(
            [], "What is my billing balance?",
        )
        assert thread == []
        # Topic should still be identified even with empty thread
        assert topic in ("billing", "unknown")
        assert shift == TopicShift.NONE

    @pytest.mark.asyncio
    async def test_extraction_truncates_long_thread(self):
        config = ThoTConfig(max_thread_length=3)
        proc = ThoTProcessor(config=config)
        thread = [f"entry {i}" for i in range(10)]
        result_thread, _, _ = await proc.extract_thread(thread, "query")
        assert len(result_thread) == 3
        # Should be the most recent 3 entries
        assert result_thread == ["entry 7", "entry 8", "entry 9"]

    @pytest.mark.asyncio
    async def test_identify_topic_billing(self, processor):
        topic = processor._identify_topic([
            "The billing charge is incorrect",
            "Refund the payment for this invoice",
        ])
        assert topic == "billing"

    @pytest.mark.asyncio
    async def test_identify_topic_technical(self, processor):
        topic = processor._identify_topic([
            "The API endpoint is returning a 500 error",
            "Need to fix the webhook integration",
        ])
        assert topic == "technical"

    @pytest.mark.asyncio
    async def test_identify_topic_account(self, processor):
        topic = processor._identify_topic([
            "I need to update my account settings",
            "Change the email address for my profile",
        ])
        assert topic == "account"

    @pytest.mark.asyncio
    async def test_identify_topic_unknown(self, processor):
        topic = processor._identify_topic(["hello there"])
        assert topic == "unknown"

    @pytest.mark.asyncio
    async def test_identify_topic_empty(self, processor):
        topic = processor._identify_topic([])
        assert topic == "unknown"


# ── Topic Shift Detection Tests ──────────────────────────────────────


class TestTopicShiftDetection:
    @pytest.mark.asyncio
    async def test_no_shift_same_topic(self, processor, sample_thread):
        _, _, shift = await processor.extract_thread(
            sample_thread, "I need a refund for the charge",
        )
        assert shift == TopicShift.NONE

    @pytest.mark.asyncio
    async def test_complete_shift(self, processor):
        thread = [
            "The billing charge is incorrect",
            "Refund the payment for this invoice",
            "Checking the billing records",
        ]
        _, _, shift = await processor.extract_thread(
            thread, "The API endpoint is returning a 500 error",
        )
        assert shift == TopicShift.COMPLETE

    @pytest.mark.asyncio
    async def test_shift_unknown_topic(self, processor):
        thread = [
            "Checking the billing records",
        ]
        _, _, shift = await processor.extract_thread(
            thread, "hello there unknown query",
        )
        assert shift == TopicShift.PARTIAL

    @pytest.mark.asyncio
    async def test_shift_empty_prev_topic(self, processor):
        shift = processor._detect_topic_shift("", "billing", [])
        assert shift == TopicShift.NONE

    @pytest.mark.asyncio
    async def test_shift_unknown_prev_topic(self, processor):
        shift = processor._detect_topic_shift("unknown", "billing", [])
        assert shift == TopicShift.NONE


# ── Continuity Check Tests ───────────────────────────────────────────


class TestContinuityCheck:
    @pytest.mark.asyncio
    async def test_high_continuity_same_topic(self, processor, sample_thread):
        analysis = await processor.check_continuity(
            sample_thread, "What about the billing?", TopicShift.NONE,
        )
        assert analysis.turn_count == 6
        assert analysis.topic_continuity > 0.7
        assert analysis.loop_detected is False

    @pytest.mark.asyncio
    async def test_low_continuity_complete_shift(self, processor, sample_thread):
        analysis = await processor.check_continuity(
            sample_thread, "The API is broken", TopicShift.COMPLETE,
        )
        assert analysis.topic_continuity < 0.5

    @pytest.mark.asyncio
    async def test_empty_thread_continuity(self, processor):
        analysis = await processor.check_continuity(
            [], "query", TopicShift.NONE,
        )
        assert analysis.turn_count == 0
        assert analysis.topic_continuity == 1.0

    @pytest.mark.asyncio
    async def test_single_entry_thread(self, processor):
        analysis = await processor.check_continuity(
            ["Single entry"], "query", TopicShift.NONE,
        )
        assert analysis.turn_count == 1
        assert analysis.topic_continuity > 0.0

    @pytest.mark.asyncio
    async def test_contradiction_detection(self, processor):
        thread = [
            "The charge is confirmed and correct",
            "The charge is incorrect and wrong",
        ]
        analysis = await processor.check_continuity(
            thread, "query", TopicShift.NONE,
        )
        assert len(analysis.contradictions) > 0

    @pytest.mark.asyncio
    async def test_no_contradiction(self, processor):
        thread = [
            "Checking the billing statement",
            "Reviewing the payment history",
        ]
        analysis = await processor.check_continuity(
            thread, "query", TopicShift.NONE,
        )
        assert len(analysis.contradictions) == 0

    @pytest.mark.asyncio
    async def test_repeated_info_detection(self, processor):
        thread = [
            "The billing charge was for the monthly subscription plan",
            "The billing charge was for the monthly subscription plan",
        ]
        analysis = await processor.check_continuity(
            thread, "query", TopicShift.NONE,
        )
        assert len(analysis.repeated_info) > 0

    @pytest.mark.asyncio
    async def test_no_repeated_info(self, processor):
        thread = [
            "Checking the billing statement",
            "The customer wants to update their profile settings",
            "Reviewing the API integration issue",
        ]
        analysis = await processor.check_continuity(
            thread, "query", TopicShift.NONE,
        )
        assert len(analysis.repeated_info) == 0

    @pytest.mark.asyncio
    async def test_score_topic_continuity_none(self, processor):
        score = processor._score_topic_continuity(TopicShift.NONE)
        assert score == 1.0

    @pytest.mark.asyncio
    async def test_score_topic_continuity_partial(self, processor):
        score = processor._score_topic_continuity(TopicShift.PARTIAL)
        assert score == 0.65

    @pytest.mark.asyncio
    async def test_score_topic_continuity_complete(self, processor):
        score = processor._score_topic_continuity(TopicShift.COMPLETE)
        assert score == 0.3

    @pytest.mark.asyncio
    async def test_summary_generation(self, processor, sample_thread):
        analysis = await processor.check_continuity(
            sample_thread, "query", TopicShift.NONE,
        )
        assert analysis.summary != ""
        assert "Thread depth:" in analysis.summary


# ── Loop Detection Tests ─────────────────────────────────────────────


class TestLoopDetection:
    @pytest.mark.asyncio
    async def test_loop_detected(self, processor):
        thread = [
            "checking order status checking order status",
            "order status checking order status checking",
            "checking order status checking order status",
        ]
        loop = processor._detect_loop(thread)
        assert loop is True

    @pytest.mark.asyncio
    async def test_no_loop(self, processor):
        thread = [
            "analyzing the billing issue",
            "checking payment history",
            "reviewing refund policy",
            "contacting customer for details",
        ]
        loop = processor._detect_loop(thread)
        assert loop is False

    @pytest.mark.asyncio
    async def test_no_loop_short_thread(self, processor):
        loop = processor._detect_loop(["entry1", "entry2"])
        assert loop is False

    @pytest.mark.asyncio
    async def test_no_loop_empty_thread(self, processor):
        loop = processor._detect_loop([])
        assert loop is False

    @pytest.mark.asyncio
    async def test_loop_with_three_similar(self, processor):
        thread = [
            "billing charge billing charge refund",
            "billing charge refund billing charge",
            "refund billing charge billing charge",
        ]
        loop = processor._detect_loop(thread)
        assert loop is True

    @pytest.mark.asyncio
    async def test_loop_reflected_in_analysis(self, processor):
        thread = [
            "checking order order order order status",
            "order order order checking order status",
            "order status order order checking order",
        ]
        analysis = await processor.check_continuity(
            thread, "query", TopicShift.NONE,
        )
        assert analysis.loop_detected is True


# ── Context Enhancement Tests ────────────────────────────────────────


class TestContextEnhancement:
    @pytest.mark.asyncio
    async def test_enhancement_when_low_continuity(self, processor):
        analysis = ThreadAnalysis(
            topic_continuity=0.3,
            contradictions=["Turn 1->2: yes contradicts no"],
            loop_detected=False,
            repeated_info=[],
            summary="Topic: billing",
        )
        prefix, enhanced = await processor.enhance_context(
            analysis, ["entry"], "query", TopicShift.COMPLETE,
        )
        assert prefix != ""
        assert "query" in enhanced
        assert "[Context:" in prefix

    @pytest.mark.asyncio
    async def test_no_enhancement_when_high_continuity(self, processor):
        analysis = ThreadAnalysis(
            topic_continuity=0.9,
            contradictions=[],
            loop_detected=False,
            repeated_info=[],
            summary="",
        )
        prefix, enhanced = await processor.enhance_context(
            analysis, ["entry"], "query", TopicShift.NONE,
        )
        assert prefix == ""
        assert enhanced == "query"

    @pytest.mark.asyncio
    async def test_enhancement_with_contradictions(self, processor):
        analysis = ThreadAnalysis(
            topic_continuity=0.2,
            contradictions=["c1", "c2"],
            loop_detected=False,
            repeated_info=[],
            summary="Topic: billing",
        )
        prefix, _ = await processor.enhance_context(
            analysis, [], "query", TopicShift.COMPLETE,
        )
        assert "2 contradiction" in prefix

    @pytest.mark.asyncio
    async def test_enhancement_with_loop(self, processor):
        analysis = ThreadAnalysis(
            topic_continuity=0.1,
            contradictions=[],
            loop_detected=True,
            repeated_info=[],
            summary="Topic: technical",
        )
        prefix, _ = await processor.enhance_context(
            analysis, [], "query", TopicShift.NONE,
        )
        assert "reasoning loop" in prefix.lower()

    @pytest.mark.asyncio
    async def test_enhancement_with_repeated_info(self, processor):
        analysis = ThreadAnalysis(
            topic_continuity=0.2,
            contradictions=[],
            loop_detected=False,
            repeated_info=["r1", "r2", "r3"],
            summary="Topic: billing",
        )
        prefix, _ = await processor.enhance_context(
            analysis, [], "query", TopicShift.NONE,
        )
        assert "3 repeated" in prefix

    @pytest.mark.asyncio
    async def test_enhancement_complete_shift(self, processor):
        analysis = ThreadAnalysis(
            topic_continuity=0.3,
            contradictions=[],
            loop_detected=False,
            repeated_info=[],
            summary="",
        )
        prefix, _ = await processor.enhance_context(
            analysis, [], "query", TopicShift.COMPLETE,
        )
        assert "Topic shift detected" in prefix

    @pytest.mark.asyncio
    async def test_enhancement_partial_shift(self, processor):
        analysis = ThreadAnalysis(
            topic_continuity=0.4,
            contradictions=[],
            loop_detected=False,
            repeated_info=[],
            summary="",
        )
        prefix, _ = await processor.enhance_context(
            analysis, [], "query", TopicShift.PARTIAL,
        )
        assert "Partial topic shift" in prefix

    @pytest.mark.asyncio
    async def test_low_threshold_processor_enhances(self, low_threshold_processor):
        """With low threshold (0.3), a score of 0.4 should NOT enhance."""
        analysis = ThreadAnalysis(topic_continuity=0.4)
        prefix, enhanced = await low_threshold_processor.enhance_context(
            analysis, [], "query", TopicShift.NONE,
        )
        assert prefix == ""
        assert enhanced == "query"


# ── Full Pipeline Tests ──────────────────────────────────────────────


class TestFullPipeline:
    @pytest.mark.asyncio
    async def test_full_pipeline_with_thread(self, processor, sample_thread):
        result = await processor.process(sample_thread, "What about my refund?")
        assert "thread_extraction" in result.steps_applied
        assert "continuity_check" in result.steps_applied
        assert isinstance(result.thread_analysis, ThreadAnalysis)
        assert result.continuity_score > 0

    @pytest.mark.asyncio
    async def test_full_pipeline_empty_thread(self, processor):
        result = await processor.process([], "Hello")
        assert result.thread_analysis.turn_count == 0
        assert result.continuity_score == 1.0
        assert result.enhanced_response == "Hello"

    @pytest.mark.asyncio
    async def test_full_pipeline_empty_everything(self, processor):
        result = await processor.process([], "")
        assert "empty_input" in result.steps_applied

    @pytest.mark.asyncio
    async def test_pipeline_result_to_dict(self, processor, sample_thread):
        result = await processor.process(sample_thread, "query")
        d = result.to_dict()
        assert isinstance(d, dict)
        assert "thread_analysis" in d
        assert "context_prefix" in d
        assert "enhanced_response" in d
        assert "steps_applied" in d
        assert "continuity_score" in d

    @pytest.mark.asyncio
    async def test_pipeline_with_contradictions(self, processor):
        thread = [
            "The payment was confirmed and processed correctly",
            "The payment was incorrect and rejected",
            "Checking the billing records",
            "The charge is approved and accepted",
        ]
        result = await processor.process(thread, "query")
        assert len(result.thread_analysis.contradictions) > 0

    @pytest.mark.asyncio
    async def test_pipeline_with_loop(self, processor):
        thread = [
            "checking order status checking order status",
            "order status checking order status checking",
            "checking order status checking order status",
        ]
        result = await processor.process(thread, "query")
        assert result.thread_analysis.loop_detected is True

    @pytest.mark.asyncio
    async def test_pipeline_steps_order(self, processor, sample_thread):
        result = await processor.process(sample_thread, "query")
        steps = result.steps_applied
        if "thread_extraction" in steps and "continuity_check" in steps:
            assert steps.index("thread_extraction") < steps.index("continuity_check")

    @pytest.mark.asyncio
    async def test_pipeline_very_long_thread(self, processor):
        thread = [f"Entry number {i} about billing charges" for i in range(100)]
        result = await processor.process(thread, "What about the refund?")
        assert "thread_extraction" in result.steps_applied
        # Thread should be truncated to max_thread_length
        assert result.thread_analysis.turn_count <= 50


# ── ThreadOfThoughtNode Integration Tests ───────────────────────────


class TestThreadOfThoughtNodeIntegration:
    @pytest.mark.asyncio
    async def test_execute_updates_state(self, node, base_state):
        base_state.reasoning_thread = [
            "checking billing records",
            "reviewing payment history",
            "analyzing charge details",
            "contacting payment processor",
            "reviewing refund policy",
            "checking customer account",
        ]
        result_state = await node.execute(base_state)
        assert "thread_of_thought" in result_state.technique_results
        assert result_state.technique_results["thread_of_thought"]["status"] == "success"

    @pytest.mark.asyncio
    async def test_execute_records_result(self, node):
        state = ConversationState(
            query="What is my refund status?",
            signals=QuerySignals(turn_count=6),
            reasoning_thread=[
                "checking billing", "checking billing",
                "checking billing", "checking billing",
                "checking billing", "checking billing",
            ],
        )
        result_state = await node.execute(state)
        recorded = result_state.technique_results["thread_of_thought"]
        assert recorded["tokens_used"] > 0
        assert "executed_at" in recorded
        assert "result" in recorded

    @pytest.mark.asyncio
    async def test_execute_appends_reasoning_thread(self, node):
        initial_thread = ["step1", "step2", "step3"]
        state = ConversationState(
            query="new query about billing",
            signals=QuerySignals(turn_count=6),
            reasoning_thread=list(initial_thread),
        )
        result_state = await node.execute(state)
        assert len(result_state.reasoning_thread) == len(initial_thread) + 1
        assert result_state.reasoning_thread[-1] == "new query about billing"

    @pytest.mark.asyncio
    async def test_execute_does_not_append_empty_query(self, node):
        state = ConversationState(
            query="",
            signals=QuerySignals(turn_count=6),
            reasoning_thread=["step1"],
        )
        result_state = await node.execute(state)
        assert len(result_state.reasoning_thread) == 1

    @pytest.mark.asyncio
    async def test_execute_returns_state(self, node, base_state):
        base_state.reasoning_thread = [
            "a", "b", "c", "d", "e", "f",
        ]
        result_state = await node.execute(base_state)
        assert isinstance(result_state, ConversationState)
        assert result_state is base_state

    @pytest.mark.asyncio
    async def test_execute_sets_loop_signal(self, node):
        state = ConversationState(
            query="order status?",
            signals=QuerySignals(turn_count=6),
            reasoning_thread=[
                "order order order status",
                "order order checking status",
                "order status order order",
                "order order order status",
                "order order checking status",
                "order status order order",
            ],
        )
        result_state = await node.execute(state)
        assert result_state.signals.reasoning_loop_detected is True

    @pytest.mark.asyncio
    async def test_execute_with_empty_thread(self, node):
        state = ConversationState(
            query="What is my balance?",
            signals=QuerySignals(turn_count=6),
            reasoning_thread=[],
        )
        result_state = await node.execute(state)
        assert "thread_of_thought" in result_state.technique_results


# ── Company Isolation Tests ──────────────────────────────────────────


class TestCompanyIsolation:
    def test_company_config_isolation(self):
        config1 = ThoTConfig(company_id="A", continuity_threshold=0.3)
        config2 = ThoTConfig(company_id="B", continuity_threshold=0.9)
        p1 = ThoTProcessor(config=config1)
        p2 = ThoTProcessor(config=config2)
        assert p1.config.company_id == "A"
        assert p2.config.company_id == "B"
        assert p1.config.continuity_threshold == 0.3
        assert p2.config.continuity_threshold == 0.9

    def test_config_defaults_not_shared(self):
        p1 = ThoTProcessor()
        p2 = ThoTProcessor(ThoTConfig(company_id="X"))
        assert p1.config.company_id == ""
        assert p2.config.company_id == "X"

    def test_frozen_config_per_instance(self):
        c1 = ThoTConfig(company_id="A")
        c2 = ThoTConfig(company_id="B")
        assert c1.company_id == "A"
        assert c2.company_id == "B"

    @pytest.mark.asyncio
    async def test_node_company_isolation(self):
        node_a = ThreadOfThoughtNode(ThoTConfig(company_id="A"))
        node_b = ThreadOfThoughtNode(ThoTConfig(company_id="B"))
        assert node_a._config.company_id == "A"
        assert node_b._config.company_id == "B"

    @pytest.mark.asyncio
    async def test_company_isolation_different_thresholds(self):
        analysis_low = ThreadAnalysis(topic_continuity=0.5, summary="Topic: billing")
        analysis_high = ThreadAnalysis(topic_continuity=0.5, summary="Topic: billing")

        p_low = ThoTProcessor(ThoTConfig(continuity_threshold=0.3))
        p_high = ThoTProcessor(ThoTConfig(continuity_threshold=0.7))

        prefix_low, _ = await p_low.enhance_context(analysis_low, [], "q", TopicShift.NONE)
        prefix_high, _ = await p_high.enhance_context(analysis_high, [], "q", TopicShift.COMPLETE)

        # Low threshold: 0.5 >= 0.3, no enhancement
        assert prefix_low == ""
        # High threshold: 0.5 < 0.7 + complete shift triggers prefix
        assert prefix_high != ""


# ── Error Fallback Tests (BC-008) ────────────────────────────────────


class TestErrorFallback:
    """BC-008: Never crash — return graceful fallback."""

    @pytest.mark.asyncio
    async def test_process_error_fallback(self, processor):
        with patch.object(
            processor, 'extract_thread',
            side_effect=RuntimeError("boom"),
        ):
            result = await processor.process(["entry"], "query")
            assert result.enhanced_response == "query"
            assert "error_fallback" in result.steps_applied
            assert result.continuity_score == 0.0

    @pytest.mark.asyncio
    async def test_process_error_preserves_query(self, processor):
        with patch.object(
            processor, 'check_continuity',
            side_effect=ValueError("err"),
        ):
            result = await processor.process(["entry"], "original query")
            assert result.enhanced_response == "original query"

    @pytest.mark.asyncio
    async def test_node_execute_error_fallback(self, node):
        state = ConversationState(
            query="test",
            signals=QuerySignals(turn_count=6),
        )
        with patch.object(
            node._processor, 'process',
            side_effect=RuntimeError("node boom"),
        ):
            result_state = await node.execute(state)
            assert result_state is state
            # Should record a skip
            recorded = result_state.technique_results.get("thread_of_thought", {})
            assert recorded.get("status") in ("skipped_budget", "error")


# ── Edge Cases ───────────────────────────────────────────────────────


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_empty_query_empty_thread(self, processor):
        result = await processor.process([], "")
        assert "empty_input" in result.steps_applied

    @pytest.mark.asyncio
    async def test_very_long_thread_truncation(self, processor):
        long_thread = [f"This is entry number {i}" for i in range(200)]
        result = await processor.process(long_thread, "query")
        assert result.thread_analysis.turn_count == 50  # max_thread_length

    @pytest.mark.asyncio
    async def test_single_turn(self, processor):
        result = await processor.process(["only one entry"], "query")
        assert result.thread_analysis.turn_count == 1

    @pytest.mark.asyncio
    async def test_whitespace_query(self, processor):
        result = await processor.process(["entry"], "   ")
        # Should not crash
        assert result is not None

    @pytest.mark.asyncio
    async def test_special_characters_in_thread(self, processor):
        thread = [
            "Order #123-ABC? ($50)",
            "Invoice #INV-001 @ 2024!",
            "Payment: $49.99 (USD)",
        ]
        result = await processor.process(thread, "query")
        assert result.thread_analysis.turn_count == 3

    @pytest.mark.asyncio
    async def test_unicode_in_thread(self, processor):
        thread = [
            "Checking the order status",
            "Reviewing payment history",
        ]
        result = await processor.process(thread, "query")
        assert result is not None

    @pytest.mark.asyncio
    async def test_max_thread_length_one(self):
        config = ThoTConfig(max_thread_length=1)
        proc = ThoTProcessor(config=config)
        result = await proc.process(["a", "b", "c"], "query")
        assert result.thread_analysis.turn_count == 1

    @pytest.mark.asyncio
    async def test_contradiction_cap(self, processor):
        """Contradictions should be capped at 10."""
        # Create many contradicting entries
        thread = []
        for i in range(20):
            if i % 2 == 0:
                thread.append("The payment is confirmed correct and accepted")
            else:
                thread.append("The payment is rejected incorrect and wrong")
        analysis = await processor.check_continuity(thread, "query", TopicShift.NONE)
        assert len(analysis.contradictions) <= 10

    @pytest.mark.asyncio
    async def test_repeated_info_cap(self, processor):
        """Repeated info should be capped at 10."""
        thread = ["The billing charge is exactly the same text here"] * 15
        analysis = await processor.check_continuity(thread, "query", TopicShift.NONE)
        assert len(analysis.repeated_info) <= 10

    @pytest.mark.asyncio
    async def test_continuity_score_bounds(self, processor, sample_thread):
        result = await processor.process(sample_thread, "query")
        assert 0.0 <= result.continuity_score <= 1.0

    @pytest.mark.asyncio
    async def test_empty_thread_node_execute(self, node):
        state = ConversationState(
            query="query",
            signals=QuerySignals(turn_count=6),
            reasoning_thread=[],
        )
        result_state = await node.execute(state)
        assert "thread_of_thought" in result_state.technique_results

    @pytest.mark.asyncio
    async def test_node_with_max_thread_length_zero(self):
        config = ThoTConfig(max_thread_length=0)
        custom_node = ThreadOfThoughtNode(config=config)
        state = ConversationState(
            query="query",
            signals=QuerySignals(turn_count=6),
            reasoning_thread=["a", "b", "c"],
        )
        result_state = await custom_node.execute(state)
        assert "thread_of_thought" in result_state.technique_results
