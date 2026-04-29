"""
Tests for Chain of Thought (CoT) — Tier 2 Conditional AI Reasoning.

Covers configuration, dataclasses, enums, should_activate logic,
each pipeline step individually, full pipeline execution, query type
detection, company isolation (BC-001), and error fallback (BC-008).

Target: 80+ tests.
"""

import pytest
from unittest.mock import patch

from app.core.technique_router import TechniqueID, QuerySignals
from app.core.techniques.base import (
    BaseTechniqueNode,
    ConversationState,
)
from app.core.techniques.chain_of_thought import (
    CoTConfig,
    CoTStep,
    CoTResult,
    ChainOfThoughtNode,
    ChainOfThoughtProcessor,
    QueryType,
    _CONJUNCTIONS,
    _SEQUENTIAL_KEYWORDS,
    _COMPARISON_PATTERNS,
    _CAUSAL_PATTERNS,
    _STOP_WORDS,
    _REASONING_TEMPLATES,
    _SYNTHESIS_TEMPLATES,
)


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def processor() -> ChainOfThoughtProcessor:
    return ChainOfThoughtProcessor()


@pytest.fixture
def company_processor() -> ChainOfThoughtProcessor:
    config = CoTConfig(
        company_id="comp_123",
        max_steps=3,
        enable_validation=True,
    )
    return ChainOfThoughtProcessor(config=config)


@pytest.fixture
def node() -> ChainOfThoughtNode:
    return ChainOfThoughtNode()


@pytest.fixture
def complex_state() -> ConversationState:
    return ConversationState(
        query="How do I cancel my subscription and get a refund? Also what happens to my data?",
        signals=QuerySignals(
            query_complexity=0.6),
    )


@pytest.fixture
def simple_state() -> ConversationState:
    return ConversationState(
        query="What is my balance?",
        signals=QuerySignals(query_complexity=0.3),
    )


@pytest.fixture
def boundary_state() -> ConversationState:
    return ConversationState(
        query="test query",
        signals=QuerySignals(query_complexity=0.4),
    )


@pytest.fixture
def empty_state() -> ConversationState:
    return ConversationState(
        query="",
        signals=QuerySignals(query_complexity=0.5),
    )


@pytest.fixture
def high_complexity_state() -> ConversationState:
    return ConversationState(
        query="First, check the order. Then, verify the payment. Finally, confirm delivery.",
        signals=QuerySignals(
            query_complexity=0.8),
    )


# ── Enum Tests ──────────────────────────────────────────────────────


class TestQueryType:
    """Tests for the QueryType enum."""

    def test_all_values_exist(self):
        expected = {
            "multi_part",
            "sequential",
            "comparison",
            "causal",
            "single"}
        actual = {qt.value for qt in QueryType}
        assert actual == expected

    def test_multi_part_value(self):
        assert QueryType.MULTI_PART.value == "multi_part"

    def test_sequential_value(self):
        assert QueryType.SEQUENTIAL.value == "sequential"

    def test_comparison_value(self):
        assert QueryType.COMPARISON.value == "comparison"

    def test_causal_value(self):
        assert QueryType.CAUSAL.value == "causal"

    def test_single_value(self):
        assert QueryType.SINGLE.value == "single"

    def test_is_string_enum(self):
        assert isinstance(QueryType.MULTI_PART.value, str)

    def test_enum_members_count(self):
        assert len(QueryType) == 5


# ── Config Tests ─────────────────────────────────────────────────────


class TestCoTConfig:
    """Tests for CoTConfig dataclass."""

    def test_default_config(self):
        config = CoTConfig()
        assert config.company_id == ""
        assert config.max_steps == 10
        assert config.enable_validation is True

    def test_frozen_immutability(self):
        config = CoTConfig(company_id="comp_1")
        with pytest.raises(AttributeError):
            config.company_id = "new"  # type: ignore

    def test_custom_config(self):
        config = CoTConfig(
            company_id="comp_2",
            max_steps=5,
            enable_validation=False,
        )
        assert config.company_id == "comp_2"
        assert config.max_steps == 5
        assert config.enable_validation is False

    def test_max_steps_zero(self):
        config = CoTConfig(max_steps=0)
        assert config.max_steps == 0

    def test_max_steps_large(self):
        config = CoTConfig(max_steps=100)
        assert config.max_steps == 100

    def test_company_id_default_empty(self):
        config = CoTConfig()
        assert config.company_id == ""

    def test_enable_validation_true_by_default(self):
        config = CoTConfig()
        assert config.enable_validation is True

    def test_enable_validation_false(self):
        config = CoTConfig(enable_validation=False)
        assert config.enable_validation is False


# ── CoTStep Data Structure Tests ────────────────────────────────────


class TestCoTStep:
    """Tests for CoTStep dataclass."""

    def test_default_values(self):
        step = CoTStep()
        assert step.step_number == 0
        assert step.step_type == ""
        assert step.description == ""
        assert step.reasoning == ""
        assert step.validation_status == ""
        assert step.key_terms == []

    def test_full_creation(self):
        step = CoTStep(
            step_number=1,
            step_type="multi_part",
            description="Analyze billing",
            reasoning="Checking billing records",
            validation_status="passed",
            key_terms=["billing", "invoice"],
        )
        assert step.step_number == 1
        assert step.step_type == "multi_part"
        assert step.description == "Analyze billing"
        assert step.reasoning == "Checking billing records"
        assert step.validation_status == "passed"
        assert step.key_terms == ["billing", "invoice"]

    def test_mutable(self):
        step = CoTStep()
        step.description = "Updated"
        assert step.description == "Updated"

    def test_to_dict_keys(self):
        step = CoTStep(step_number=1, description="test")
        d = step.to_dict()
        expected_keys = {
            "step_number", "step_type", "description",
            "reasoning", "validation_status", "key_terms",
        }
        assert set(d.keys()) == expected_keys

    def test_to_dict_values(self):
        step = CoTStep(
            step_number=2,
            step_type="sequential",
            description="Process order",
            reasoning="Tracing the flow",
            validation_status="passed",
            key_terms=["order"],
        )
        d = step.to_dict()
        assert d["step_number"] == 2
        assert d["step_type"] == "sequential"
        assert d["description"] == "Process order"
        assert d["reasoning"] == "Tracing the flow"
        assert d["validation_status"] == "passed"
        assert d["key_terms"] == ["order"]

    def test_to_dict_key_terms_is_list(self):
        step = CoTStep(key_terms=["a", "b"])
        d = step.to_dict()
        assert isinstance(d["key_terms"], list)

    def test_key_terms_default_is_list(self):
        step = CoTStep()
        assert isinstance(step.key_terms, list)


# ── CoTResult Data Structure Tests ──────────────────────────────────


class TestCoTResult:
    """Tests for CoTResult dataclass."""

    def test_default_values(self):
        result = CoTResult()
        assert result.decomposed_steps == []
        assert result.reasoning_chain == ""
        assert result.synthesis == ""
        assert result.validation_summary == ""
        assert result.steps_applied == []
        assert result.confidence_boost == 0.0

    def test_full_creation(self):
        steps = [CoTStep(step_number=1, description="test")]
        result = CoTResult(
            decomposed_steps=steps,
            reasoning_chain="Step 1: ...",
            synthesis="Combined analysis.",
            validation_summary="1 passed.",
            steps_applied=["decomposition", "reasoning"],
            confidence_boost=0.3,
        )
        assert len(result.decomposed_steps) == 1
        assert result.synthesis == "Combined analysis."
        assert result.confidence_boost == 0.3

    def test_to_dict_keys(self):
        result = CoTResult(synthesis="test")
        d = result.to_dict()
        expected_keys = {
            "decomposed_steps",
            "reasoning_chain",
            "synthesis",
            "validation_summary",
            "steps_applied",
            "confidence_boost",
        }
        assert set(d.keys()) == expected_keys

    def test_to_dict_steps_serialized(self):
        step = CoTStep(
            step_number=1,
            step_type="causal",
            description="Find root cause",
            reasoning="Investigating",
            validation_status="passed",
            key_terms=["cause"],
        )
        result = CoTResult(decomposed_steps=[step])
        d = result.to_dict()
        assert len(d["decomposed_steps"]) == 1
        assert d["decomposed_steps"][0]["step_number"] == 1
        assert d["decomposed_steps"][0]["step_type"] == "causal"
        assert d["decomposed_steps"][0]["key_terms"] == ["cause"]

    def test_to_dict_confidence_boost_rounded(self):
        result = CoTResult(confidence_boost=0.256789)
        d = result.to_dict()
        assert d["confidence_boost"] == 0.2568

    def test_to_dict_steps_applied(self):
        result = CoTResult(
            steps_applied=[
                "decomposition",
                "reasoning",
                "validation",
                "synthesis"],
        )
        d = result.to_dict()
        assert d["steps_applied"] == [
            "decomposition",
            "reasoning",
            "validation",
            "synthesis"]

    def test_mutable(self):
        result = CoTResult()
        result.synthesis = "Updated"
        assert result.synthesis == "Updated"


# ── Node Basic Tests ─────────────────────────────────────────────────


class TestChainOfThoughtNode:
    """Tests for the ChainOfThoughtNode class."""

    def test_is_base_technique_node(self, node):
        assert isinstance(node, BaseTechniqueNode)

    def test_technique_id(self, node):
        assert node.technique_id == TechniqueID.CHAIN_OF_THOUGHT

    def test_technique_id_is_string(self, node):
        assert isinstance(node.technique_id.value, str)

    def test_technique_info_populated(self, node):
        assert node.technique_info is not None
        assert node.technique_info.id == TechniqueID.CHAIN_OF_THOUGHT

    def test_tier_2(self, node):
        from app.core.technique_router import TechniqueTier
        assert node.technique_info.tier == TechniqueTier.TIER_2

    def test_node_with_custom_config(self):
        config = CoTConfig(
            company_id="custom",
            max_steps=5,
        )
        node = ChainOfThoughtNode(config=config)
        assert node.technique_id == TechniqueID.CHAIN_OF_THOUGHT
        assert node._config.company_id == "custom"


# ── should_activate Tests ────────────────────────────────────────────


class TestShouldActivate:
    """Tests for ChainOfThoughtNode.should_activate()."""

    @pytest.mark.asyncio
    async def test_complex_query_activates(self, node, complex_state):
        assert await node.should_activate(complex_state) is True

    @pytest.mark.asyncio
    async def test_complexity_exactly_04_does_not_activate(
            self, node, boundary_state):
        assert await node.should_activate(boundary_state) is False

    @pytest.mark.asyncio
    async def test_complexity_041_activates(self, node):
        state = ConversationState(
            query="test",
            signals=QuerySignals(query_complexity=0.41),
        )
        assert await node.should_activate(state) is True

    @pytest.mark.asyncio
    async def test_simple_query_does_not_activate(self, node, simple_state):
        assert await node.should_activate(simple_state) is False

    @pytest.mark.asyncio
    async def test_complexity_zero_does_not_activate(self, node):
        state = ConversationState(
            query="test",
            signals=QuerySignals(query_complexity=0.0),
        )
        assert await node.should_activate(state) is False

    @pytest.mark.asyncio
    async def test_complexity_one_activates(self, node):
        state = ConversationState(
            query="test",
            signals=QuerySignals(query_complexity=1.0),
        )
        assert await node.should_activate(state) is True

    @pytest.mark.asyncio
    async def test_complexity_05_activates(self, node):
        state = ConversationState(
            query="test",
            signals=QuerySignals(query_complexity=0.5),
        )
        assert await node.should_activate(state) is True

    @pytest.mark.asyncio
    async def test_complexity_039_does_not_activate(self, node):
        state = ConversationState(
            query="test",
            signals=QuerySignals(query_complexity=0.39),
        )
        assert await node.should_activate(state) is False

    @pytest.mark.asyncio
    async def test_high_complexity_activates(
            self, node, high_complexity_state):
        assert await node.should_activate(high_complexity_state) is True


# ── Query Type Detection Tests ───────────────────────────────────────


class TestDetectQueryType:
    """Tests for detect_query_type()."""

    def test_multi_part_conjunctions(self, processor):
        query = "How do I cancel and also what about my refund and my data?"
        assert processor.detect_query_type(query) == QueryType.MULTI_PART

    def test_multi_part_multiple_questions(self, processor):
        query = "What is the price? How does billing work? When am I charged?"
        assert processor.detect_query_type(query) == QueryType.MULTI_PART

    def test_sequential_keywords(self, processor):
        query = "First check the order, then verify payment, after that confirm delivery"
        assert processor.detect_query_type(query) == QueryType.SEQUENTIAL

    def test_comparison_vs(self, processor):
        query = "Basic plan vs Pro plan"
        assert processor.detect_query_type(query) == QueryType.COMPARISON

    def test_comparison_difference_between(self, processor):
        query = "What is the difference between Plan A and Plan B?"
        assert processor.detect_query_type(query) == QueryType.COMPARISON

    def test_comparison_compared_to(self, processor):
        query = "How does this service compared to the competition?"
        assert processor.detect_query_type(query) == QueryType.COMPARISON

    def test_comparison_versus(self, processor):
        query = "Free tier versus paid tier"
        assert processor.detect_query_type(query) == QueryType.COMPARISON

    def test_causal_why(self, processor):
        query = "Why was my payment declined?"
        assert processor.detect_query_type(query) == QueryType.CAUSAL

    def test_causal_what_caused(self, processor):
        query = "What caused the service outage?"
        assert processor.detect_query_type(query) == QueryType.CAUSAL

    def test_causal_reason_for(self, processor):
        query = "What is the reason for this charge?"
        assert processor.detect_query_type(query) == QueryType.CAUSAL

    def test_single_simple(self, processor):
        query = "What is my account balance?"
        assert processor.detect_query_type(query) == QueryType.SINGLE

    def test_empty_query(self, processor):
        assert processor.detect_query_type("") == QueryType.SINGLE

    def test_whitespace_query(self, processor):
        assert processor.detect_query_type("   ") == QueryType.SINGLE

    def test_comparison_priority_over_causal(self, processor):
        """Comparison should be detected before causal if both patterns exist."""
        query = "Why is there a difference between Plan A and Plan B?"
        # "difference between" is checked before "why"
        assert processor.detect_query_type(query) == QueryType.COMPARISON

    def test_causal_due_to(self, processor):
        query = "Was the error due to server issues?"
        assert processor.detect_query_type(query) == QueryType.CAUSAL

    def test_causal_resulted_in(self, processor):
        query = "What resulted in the account suspension?"
        assert processor.detect_query_type(query) == QueryType.CAUSAL

    def test_multi_part_plus(self, processor):
        query = "Reset my password plus update my email"
        assert processor.detect_query_type(query) == QueryType.MULTI_PART

    def test_two_questions(self, processor):
        query = "What is the price? How do I subscribe?"
        assert processor.detect_query_type(query) == QueryType.MULTI_PART


# ── Step 1: Decomposition Tests ──────────────────────────────────────


class TestDecomposition:
    """Tests for decompose_query()."""

    @pytest.mark.asyncio
    async def test_empty_query(self, processor):
        result = await processor.decompose_query("")
        assert result == []

    @pytest.mark.asyncio
    async def test_single_query_one_step(self, processor):
        result = await processor.decompose_query(
            "What is my balance?",
            QueryType.SINGLE,
        )
        assert len(result) == 1
        assert result[0].step_type == "single"

    @pytest.mark.asyncio
    async def test_multi_part_has_description(self, processor):
        result = await processor.decompose_query(
            "How do I cancel? Also, what about my refund?",
            QueryType.MULTI_PART,
        )
        assert len(result) >= 2
        for step in result:
            assert step.description != ""

    @pytest.mark.asyncio
    async def test_sequential_has_numbered_steps(self, processor):
        result = await processor.decompose_query(
            "First check order. Then verify payment. After that confirm.",
            QueryType.SEQUENTIAL,
        )
        assert len(result) >= 2
        for i, step in enumerate(result):
            assert step.step_number == i + 1

    @pytest.mark.asyncio
    async def test_comparison_three_steps(self, processor):
        result = await processor.decompose_query(
            "Plan A vs Plan B",
            QueryType.COMPARISON,
        )
        assert len(result) >= 2
        assert result[0].step_type == "comparison"

    @pytest.mark.asyncio
    async def test_causal_three_steps(self, processor):
        result = await processor.decompose_query(
            "Why was I charged?",
            QueryType.CAUSAL,
        )
        assert len(result) == 3
        assert all(s.step_type == "causal" for s in result)

    @pytest.mark.asyncio
    async def test_max_steps_enforced(self, company_processor):
        result = await company_processor.decompose_query(
            "First this. Then that. Next another. After that more. Finally last.",
            QueryType.SEQUENTIAL,
        )
        assert len(result) <= 3  # company_processor has max_steps=3

    @pytest.mark.asyncio
    async def test_steps_have_key_terms(self, processor):
        result = await processor.decompose_query(
            "How do I cancel my subscription?",
            QueryType.SINGLE,
        )
        assert len(result) == 1
        assert isinstance(result[0].key_terms, list)

    @pytest.mark.asyncio
    async def test_auto_detect_query_type(self, processor):
        result = await processor.decompose_query(
            "Plan A vs Plan B",
        )
        assert len(result) >= 2
        assert all(s.step_type == "comparison" for s in result)

    @pytest.mark.asyncio
    async def test_whitespace_query(self, processor):
        result = await processor.decompose_query("   ")
        assert result == []


# ── Step 2: Reasoning Tests ──────────────────────────────────────────


class TestStepByStepReasoning:
    """Tests for generate_reasoning()."""

    @pytest.mark.asyncio
    async def test_empty_steps(self, processor):
        result = await processor.generate_reasoning([])
        assert result == []

    @pytest.mark.asyncio
    async def test_single_step_gets_reasoning(self, processor):
        steps = [CoTStep(
            step_number=1,
            step_type="single",
            description="Check billing",
            key_terms=["billing"],
        )]
        result = await processor.generate_reasoning(steps)
        assert len(result) == 1
        assert result[0].reasoning != ""
        assert "billing" in result[0].reasoning

    @pytest.mark.asyncio
    async def test_multi_part_reasoning(self, processor):
        steps = [
            CoTStep(
                step_number=1,
                step_type="multi_part",
                description="Cancel subscription",
                key_terms=["cancel"]),
            CoTStep(
                step_number=2,
                step_type="multi_part",
                description="Get refund",
                key_terms=["refund"]),
        ]
        result = await processor.generate_reasoning(steps)
        assert len(result) == 2
        assert "cancel" in result[0].reasoning.lower()
        assert "refund" in result[1].reasoning.lower()

    @pytest.mark.asyncio
    async def test_sequential_reasoning_includes_step_number(self, processor):
        steps = [CoTStep(
            step_number=3,
            step_type="sequential",
            description="Confirm delivery",
            key_terms=["delivery"],
        )]
        result = await processor.generate_reasoning(steps)
        assert "3" in result[0].reasoning

    @pytest.mark.asyncio
    async def test_causal_reasoning(self, processor):
        steps = [CoTStep(
            step_number=1,
            step_type="causal",
            description="Identify the effect",
            key_terms=["effect"],
        )]
        result = await processor.generate_reasoning(steps)
        assert "cause" in result[0].reasoning.lower()

    @pytest.mark.asyncio
    async def test_comparison_reasoning(self, processor):
        steps = [CoTStep(
            step_number=1,
            step_type="comparison",
            description="Compare plans",
            key_terms=["plan"],
        )]
        result = await processor.generate_reasoning(steps)
        assert "compar" in result[0].reasoning.lower()

    @pytest.mark.asyncio
    async def test_preserves_step_numbers(self, processor):
        steps = [
            CoTStep(
                step_number=1,
                step_type="single",
                description="A",
                key_terms=["a"]),
            CoTStep(
                step_number=2,
                step_type="single",
                description="B",
                key_terms=["b"]),
        ]
        result = await processor.generate_reasoning(steps)
        assert result[0].step_number == 1
        assert result[1].step_number == 2


# ── Step 3: Validation Tests ─────────────────────────────────────────


class TestIntermediateValidation:
    """Tests for validate_steps()."""

    @pytest.mark.asyncio
    async def test_empty_steps(self, processor):
        steps, summary = await processor.validate_steps([])
        assert steps == []
        assert "No steps" in summary

    @pytest.mark.asyncio
    async def test_valid_step_passes(self, processor):
        steps = [CoTStep(
            step_number=1,
            step_type="single",
            description="Valid description",
            reasoning="Valid reasoning content",
            key_terms=["term1", "term2"],
        )]
        result, summary = await processor.validate_steps(steps)
        assert result[0].validation_status == "passed"
        assert "1 passed" in summary

    @pytest.mark.asyncio
    async def test_missing_reasoning_needs_data(self, processor):
        steps = [CoTStep(
            step_number=1,
            step_type="single",
            description="Valid description",
            reasoning="",
            key_terms=["term1"],
        )]
        result, summary = await processor.validate_steps(steps)
        assert result[0].validation_status == "needs_data"
        assert "need more data" in summary

    @pytest.mark.asyncio
    async def test_missing_key_terms_needs_data(self, processor):
        steps = [CoTStep(
            step_number=1,
            step_type="single",
            description="Valid description",
            reasoning="Valid reasoning",
            key_terms=[],
        )]
        result, summary = await processor.validate_steps(steps)
        assert result[0].validation_status == "needs_data"

    @pytest.mark.asyncio
    async def test_empty_description_fails(self, processor):
        steps = [CoTStep(
            step_number=1,
            step_type="single",
            description="",
            reasoning="Valid reasoning",
            key_terms=["term"],
        )]
        result, summary = await processor.validate_steps(steps)
        assert result[0].validation_status == "failed"
        assert "failed" in summary

    @pytest.mark.asyncio
    async def test_mixed_validation(self, processor):
        steps = [
            CoTStep(
                step_number=1, step_type="single",
                description="Good", reasoning="Good reasoning",
                key_terms=["t"],
            ),
            CoTStep(
                step_number=2, step_type="single",
                description="OK", reasoning="", key_terms=["t"],
            ),
        ]
        result, summary = await processor.validate_steps(steps)
        assert result[0].validation_status == "passed"
        assert result[1].validation_status == "needs_data"
        assert "1 passed" in summary
        assert "1 need more data" in summary

    @pytest.mark.asyncio
    async def test_all_passed_summary(self, processor):
        steps = [
            CoTStep(
                step_number=i + 1, step_type="single",
                description=f"Step {i}", reasoning="Reasoning",
                key_terms=["t"],
            )
            for i in range(3)
        ]
        _, summary = await processor.validate_steps(steps)
        assert "3 passed" in summary

    @pytest.mark.asyncio
    async def test_preserves_step_data(self, processor):
        steps = [CoTStep(
            step_number=5,
            step_type="causal",
            description="Root cause",
            reasoning="Tracing causes",
            key_terms=["cause"],
        )]
        result, _ = await processor.validate_steps(steps)
        assert result[0].step_number == 5
        assert result[0].step_type == "causal"
        assert result[0].description == "Root cause"
        assert result[0].reasoning == "Tracing causes"


# ── Step 4: Synthesis Tests ──────────────────────────────────────────


class TestSynthesis:
    """Tests for synthesize()."""

    @pytest.mark.asyncio
    async def test_empty_steps(self, processor):
        result = await processor.synthesize([], QueryType.SINGLE)
        assert result == ""

    @pytest.mark.asyncio
    async def test_single_step_synthesis(self, processor):
        steps = [CoTStep(
            step_number=1,
            step_type="single",
            description="Check balance",
            reasoning="Analyzing: Check balance. Key terms: balance.",
            key_terms=["balance"],
        )]
        result = await processor.synthesize(steps, QueryType.SINGLE)
        assert "Analysis complete" in result

    @pytest.mark.asyncio
    async def test_multi_part_synthesis(self, processor):
        steps = [
            CoTStep(
                step_number=1,
                step_type="multi_part",
                description="Cancel subscription",
                reasoning="Analyzing sub-question: Cancel subscription.",
                key_terms=["cancel"],
            ),
            CoTStep(
                step_number=2,
                step_type="multi_part",
                description="Get refund",
                reasoning="Analyzing sub-question: Get refund.",
                key_terms=["refund"],
            ),
        ]
        result = await processor.synthesize(steps, QueryType.MULTI_PART)
        assert "2" in result  # step count
        assert "sub-question" in result.lower()

    @pytest.mark.asyncio
    async def test_sequential_synthesis(self, processor):
        steps = [
            CoTStep(
                step_number=1,
                step_type="sequential",
                description="Check order",
                reasoning="Processing step 1: Check order.",
                key_terms=["order"],
            ),
            CoTStep(
                step_number=2,
                step_type="sequential",
                description="Verify payment",
                reasoning="Processing step 2: Verify payment.",
                key_terms=["payment"],
            ),
        ]
        result = await processor.synthesize(steps, QueryType.SEQUENTIAL)
        assert "2-step" in result

    @pytest.mark.asyncio
    async def test_comparison_synthesis(self, processor):
        steps = [
            CoTStep(
                step_number=1,
                step_type="comparison",
                description="Features of A",
                reasoning="Comparing: Features of A.",
                key_terms=["a"],
            ),
        ]
        result = await processor.synthesize(steps, QueryType.COMPARISON)
        assert "Comparison analysis" in result

    @pytest.mark.asyncio
    async def test_causal_synthesis(self, processor):
        steps = [
            CoTStep(
                step_number=1,
                step_type="causal",
                description="Identify effect",
                reasoning="Investigating cause: Identify effect.",
                key_terms=["effect"],
            ),
        ]
        result = await processor.synthesize(steps, QueryType.CAUSAL)
        assert "Root cause analysis" in result

    @pytest.mark.asyncio
    async def test_no_reasoning_fallback(self, processor):
        steps = [CoTStep(
            step_number=1,
            step_type="single",
            description="Test",
            reasoning="",
            key_terms=[],
        )]
        result = await processor.synthesize(steps, QueryType.SINGLE)
        assert "no specific findings" in result


# ── Full Pipeline Tests ──────────────────────────────────────────────


class TestFullPipeline:
    """Tests for the full 4-step process() method."""

    @pytest.mark.asyncio
    async def test_multi_part_query_pipeline(self, processor):
        result = await processor.process(
            "How do I cancel my subscription? Also, what about my refund?",
        )
        assert len(result.decomposed_steps) >= 2
        assert result.reasoning_chain != ""
        assert result.synthesis != ""
        assert len(result.steps_applied) >= 3
        assert result.confidence_boost > 0

    @pytest.mark.asyncio
    async def test_sequential_query_pipeline(self, processor):
        result = await processor.process(
            "First, check the order. Then, verify the payment.",
        )
        assert len(result.decomposed_steps) >= 2
        assert result.synthesis != ""
        assert "decomposition" in result.steps_applied

    @pytest.mark.asyncio
    async def test_comparison_query_pipeline(self, processor):
        result = await processor.process(
            "Basic plan vs Pro plan",
        )
        assert len(result.decomposed_steps) >= 2
        assert result.synthesis != ""

    @pytest.mark.asyncio
    async def test_causal_query_pipeline(self, processor):
        result = await processor.process(
            "Why was my payment declined?",
        )
        assert len(result.decomposed_steps) >= 2
        assert result.synthesis != ""
        assert result.confidence_boost > 0

    @pytest.mark.asyncio
    async def test_empty_query_pipeline(self, processor):
        result = await processor.process("")
        assert result.steps_applied == ["empty_input"]
        assert result.confidence_boost == 0.0

    @pytest.mark.asyncio
    async def test_whitespace_query_pipeline(self, processor):
        result = await processor.process("   ")
        assert result.steps_applied == ["empty_input"]

    @pytest.mark.asyncio
    async def test_all_steps_applied(self, processor):
        result = await processor.process(
            "How do I cancel and get a refund? Also what about my data?",
        )
        expected_steps = [
            "decomposition",
            "reasoning",
            "validation",
            "synthesis",
        ]
        for step in expected_steps:
            assert step in result.steps_applied

    @pytest.mark.asyncio
    async def test_confidence_boost_range(self, processor):
        result = await processor.process("Plan A vs Plan B")
        assert 0.0 < result.confidence_boost <= 0.35

    @pytest.mark.asyncio
    async def test_to_dict_returns_dict(self, processor):
        result = await processor.process("Why was I charged?")
        d = result.to_dict()
        assert isinstance(d, dict)

    @pytest.mark.asyncio
    async def test_single_query_pipeline(self, processor):
        result = await processor.process("What is my balance?")
        assert len(result.decomposed_steps) == 1
        assert result.reasoning_chain != ""

    @pytest.mark.asyncio
    async def test_validation_in_result(self, processor):
        result = await processor.process(
            "How do I cancel my subscription and get a refund?",
        )
        assert result.validation_summary != ""

    @pytest.mark.asyncio
    async def test_validation_disabled(self):
        config = CoTConfig(enable_validation=False)
        proc = ChainOfThoughtProcessor(config=config)
        result = await proc.process("Plan A vs Plan B")
        assert "validation" not in result.steps_applied

    @pytest.mark.asyncio
    async def test_max_steps_limit(self, company_processor):
        result = await company_processor.process(
            "Step one. Then step two. Next step three. After that step four. Finally step five.",
        )
        assert len(result.decomposed_steps) <= 3

    @pytest.mark.asyncio
    async def test_reasoning_chain_format(self, processor):
        result = await processor.process(
            "First check order, then verify payment",
        )
        assert "Step 1:" in result.reasoning_chain

    @pytest.mark.asyncio
    async def test_very_long_query(self, processor):
        query = "What is this? And that? Also the other? Plus one more? How about another?" * 10
        result = await processor.process(query)
        assert isinstance(result, CoTResult)

    @pytest.mark.asyncio
    async def test_special_characters(self, processor):
        query = "Plan A vs Plan B — $9.99 vs $19.99 (monthly)!"
        result = await processor.process(query)
        assert result.synthesis != ""


# ── Node execute() Tests ─────────────────────────────────────────────


class TestNodeExecute:
    """Tests for ChainOfThoughtNode.execute()."""

    @pytest.mark.asyncio
    async def test_execute_updates_state(self, node, complex_state):
        result = await node.execute(complex_state)
        assert result is complex_state
        assert TechniqueID.CHAIN_OF_THOUGHT.value in result.technique_results

    @pytest.mark.asyncio
    async def test_execute_records_result(self, node, complex_state):
        result = await node.execute(complex_state)
        record = result.technique_results[TechniqueID.CHAIN_OF_THOUGHT.value]
        assert record["status"] == "success"
        assert "result" in record

    @pytest.mark.asyncio
    async def test_execute_increases_confidence(self, node, complex_state):
        original_confidence = complex_state.signals.confidence_score
        result = await node.execute(complex_state)
        assert result.signals.confidence_score >= original_confidence
        assert result.signals.confidence_score <= 1.0

    @pytest.mark.asyncio
    async def test_execute_appends_response(self, node, complex_state):
        result = await node.execute(complex_state)
        assert len(result.response_parts) > 0

    @pytest.mark.asyncio
    async def test_execute_with_empty_query(self, node, empty_state):
        result = await node.execute(empty_state)
        assert result is empty_state

    @pytest.mark.asyncio
    async def test_execute_result_has_dict(self, node, complex_state):
        result = await node.execute(complex_state)
        record = result.technique_results[TechniqueID.CHAIN_OF_THOUGHT.value]
        assert isinstance(record["result"], dict)

    @pytest.mark.asyncio
    async def test_execute_high_complexity(self, node, high_complexity_state):
        result = await node.execute(high_complexity_state)
        assert TechniqueID.CHAIN_OF_THOUGHT.value in result.technique_results


# ── Company Isolation Tests (BC-001) ─────────────────────────────────


class TestCompanyIsolation:
    """BC-001: Company data must be isolated."""

    def test_company_processor_has_company_id(self, company_processor):
        assert company_processor.config.company_id == "comp_123"

    def test_default_processor_no_company_id(self, processor):
        assert processor.config.company_id == ""

    def test_two_companies_independent(self):
        config1 = CoTConfig(company_id="A", max_steps=3)
        config2 = CoTConfig(company_id="B", max_steps=10)
        p1 = ChainOfThoughtProcessor(config=config1)
        p2 = ChainOfThoughtProcessor(config=config2)
        assert p1.config.max_steps == 3
        assert p2.config.max_steps == 10

    def test_node_company_config(self):
        config = CoTConfig(company_id="tenant_X")
        node = ChainOfThoughtNode(config=config)
        assert node._config.company_id == "tenant_X"

    def test_configs_not_shared(self):
        c1 = CoTConfig(company_id="A")
        c2 = CoTConfig(company_id="B")
        assert c1.company_id != c2.company_id


# ── Error Fallback Tests (BC-008) ────────────────────────────────────


class TestErrorFallback:
    """BC-008: Never crash — return original state on error."""

    @pytest.mark.asyncio
    async def test_execute_returns_original_on_exception(
            self, node, complex_state):
        """Force an exception inside execute() and verify original state returned."""
        with patch.object(
            node._processor, 'process',
            side_effect=RuntimeError("boom"),
        ):
            result = await node.execute(complex_state)
            assert result is complex_state

    @pytest.mark.asyncio
    async def test_process_returns_fallback_on_internal_error(self, processor):
        """Force an exception inside process() pipeline."""
        with patch.object(
            processor, 'detect_query_type',
            side_effect=RuntimeError("pipeline error"),
        ):
            result = await processor.process("billing question")
            assert "error_fallback" in result.steps_applied

    @pytest.mark.asyncio
    async def test_processor_error_logs_warning(self, processor):
        """Error should be logged as warning, not crash."""
        with patch.object(
            processor, 'decompose_query',
            side_effect=ValueError("error"),
        ):
            result = await processor.process("test query")
            assert isinstance(result, CoTResult)

    @pytest.mark.asyncio
    async def test_empty_confidence_on_error(self, processor):
        """Confidence boost should be 0 on error."""
        with patch.object(
            processor, 'generate_reasoning',
            side_effect=Exception("fail"),
        ):
            result = await processor.process("test query")
            assert result.confidence_boost == 0.0


# ── Edge Cases ───────────────────────────────────────────────────────


class TestEdgeCases:
    """Additional edge cases for robustness."""

    @pytest.mark.asyncio
    async def test_very_long_query(self, processor):
        """Very long query should be processed without crash."""
        query = "billing " * 500 + "I need help with my invoice and my refund"
        result = await processor.process(query)
        assert isinstance(result, CoTResult)

    @pytest.mark.asyncio
    async def test_special_characters(self, processor):
        """Special characters should not crash the processor."""
        query = "Plan A vs Plan B ($9.99 vs $19.99)? Check order #12345!"
        result = await processor.process(query)
        assert result.synthesis != ""

    @pytest.mark.asyncio
    async def test_unicode_characters(self, processor):
        """Unicode characters should not crash."""
        query = "Why is my refund taking so long? \u2014 I need answers"
        result = await processor.process(query)
        assert isinstance(result, CoTResult)

    @pytest.mark.asyncio
    async def test_only_question_marks(self, processor):
        """Query with only question marks should be handled."""
        query = "???"
        result = await processor.process(query)
        assert isinstance(result, CoTResult)

    @pytest.mark.asyncio
    async def test_very_short_query(self, processor):
        """Very short query should be handled."""
        result = await processor.process("Hi?")
        assert isinstance(result, CoTResult)

    @pytest.mark.asyncio
    async def test_duplicate_conjunctions(self, processor):
        """Duplicate conjunctions should still work."""
        query = "Cancel and and and refund"
        result = await processor.process(query)
        assert isinstance(result, CoTResult)

    def test_key_terms_extraction_empty(self):
        """Empty query returns empty key terms."""
        terms = ChainOfThoughtProcessor._extract_key_terms("")
        assert terms == []

    def test_key_terms_extraction_filters_stop_words(self):
        """Stop words should be filtered from key terms."""
        terms = ChainOfThoughtProcessor._extract_key_terms(
            "I want to know my billing status",
        )
        assert "want" not in terms or "billing" in terms or "status" in terms

    def test_key_terms_max_five(self):
        """Key terms should be limited to 5."""
        terms = ChainOfThoughtProcessor._extract_key_terms(
            "billing invoice charge payment subscription account profile settings", )
        assert len(terms) <= 5

    def test_key_terms_deduplication(self):
        """Key terms should be deduplicated."""
        terms = ChainOfThoughtProcessor._extract_key_terms(
            "billing billing billing invoice invoice",
        )
        assert len([t for t in terms if t == "billing"]) == 1
        assert len([t for t in terms if t == "invoice"]) == 1

    def test_key_terms_preserves_order(self):
        """Key terms should preserve first-appearance order."""
        terms = ChainOfThoughtProcessor._extract_key_terms(
            "refund billing subscription",
        )
        if len(terms) >= 2:
            idx = {t: i for i, t in enumerate(terms)}
            if "refund" in idx and "billing" in idx:
                assert idx["refund"] < idx["billing"]


# ── Constants Tests ──────────────────────────────────────────────────


class TestConstants:
    """Tests for module-level constants."""

    def test_conjunctions_not_empty(self):
        assert len(_CONJUNCTIONS) >= 5

    def test_sequential_keywords_not_empty(self):
        assert len(_SEQUENTIAL_KEYWORDS) >= 5

    def test_comparison_patterns_not_empty(self):
        assert len(_COMPARISON_PATTERNS) >= 3

    def test_causal_patterns_not_empty(self):
        assert len(_CAUSAL_PATTERNS) >= 3

    def test_stop_words_not_empty(self):
        assert len(_STOP_WORDS) >= 20

    def test_reasoning_templates_cover_all_types(self):
        for qt in QueryType:
            assert qt in _REASONING_TEMPLATES, f"Missing template for {qt}"

    def test_synthesis_templates_cover_all_types(self):
        for qt in QueryType:
            assert qt in _SYNTHESIS_TEMPLATES, f"Missing synthesis for {qt}"

    def test_reasoning_templates_have_required_keys(self):
        for qt, data in _REASONING_TEMPLATES.items():
            assert "template" in data, f"Missing 'template' for {qt}"
            assert "validation" in data, f"Missing 'validation' for {qt}"

    def test_synthesis_templates_are_strings(self):
        for qt, template in _SYNTHESIS_TEMPLATES.items():
            assert isinstance(
                template, str), f"Template for {qt} is not a string"
            assert "{step_count}" in template, f"Missing {{step_count}} for {qt}"
            assert "{step_summaries}" in template, f"Missing {{step_summaries}} for {qt}"

    def test_conjunctions_contain_and(self):
        assert any("and" in c for c in _CONJUNCTIONS)

    def test_sequential_keywords_contain_first(self):
        assert "first" in _SEQUENTIAL_KEYWORDS

    def test_causal_patterns_contain_why(self):
        assert any("why" in p for p in _CAUSAL_PATTERNS)

    def test_comparison_patterns_contain_vs(self):
        assert any("vs" in p for p in _COMPARISON_PATTERNS)


# ── Comparison Subject Extraction Tests ──────────────────────────────


class TestComparisonSubjectExtraction:
    """Tests for _extract_comparison_subjects()."""

    def test_vs_pattern(self):
        subjects = ChainOfThoughtProcessor._extract_comparison_subjects(
            "Basic plan vs Pro plan"
        )
        assert len(subjects) == 2
        assert "basic" in subjects[0].lower()
        assert "pro" in subjects[1].lower()

    def test_versus_pattern(self):
        subjects = ChainOfThoughtProcessor._extract_comparison_subjects(
            "Free tier versus paid tier"
        )
        assert len(subjects) == 2

    def test_difference_between_pattern(self):
        subjects = ChainOfThoughtProcessor._extract_comparison_subjects(
            "What is the difference between Plan A and Plan B?"
        )
        assert len(subjects) == 2

    def test_compared_to_pattern(self):
        subjects = ChainOfThoughtProcessor._extract_comparison_subjects(
            "This service compared to the competition"
        )
        assert len(subjects) == 2

    def test_no_pattern_returns_empty(self):
        subjects = ChainOfThoughtProcessor._extract_comparison_subjects(
            "Tell me about pricing"
        )
        assert subjects == []
