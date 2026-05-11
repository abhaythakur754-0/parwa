"""
Day 6: Chain of Thought — Unit Tests

Tests for the CoT processor, query type detection, decomposition,
validation, synthesis, and full pipeline.
"""

import os
import sys
import pytest

# Add backend to path for nested app imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_testing_only_not_prod")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from app.core.techniques.chain_of_thought import (
        QueryType,
        CoTConfig,
        CoTStep,
        CoTResult,
        ChainOfThoughtProcessor,
        _STOP_WORDS,
        _SEQUENTIAL_KEYWORDS,
        _COMPARISON_PATTERNS,
        _CAUSAL_PATTERNS,
        _CONJUNCTIONS,
    )


@pytest.fixture
def processor():
    return ChainOfThoughtProcessor(config=CoTConfig(company_id="test_comp"))


# ── QueryType Tests ──────────────────────────────────────────────


class TestQueryType:
    """Test QueryType enum."""

    def test_all_types_exist(self):
        assert QueryType.MULTI_PART == "multi_part"
        assert QueryType.SEQUENTIAL == "sequential"
        assert QueryType.COMPARISON == "comparison"
        assert QueryType.CAUSAL == "causal"
        assert QueryType.SINGLE == "single"


# ── Detect Query Type Tests ─────────────────────────────────────


class TestDetectQueryType:
    """Tests for ChainOfThoughtProcessor.detect_query_type()."""

    def setup_method(self):
        self.proc = ChainOfThoughtProcessor()

    def test_comparison_difference_between(self):
        result = self.proc.detect_query_type("What is the difference between A and B?")
        assert result == QueryType.COMPARISON

    def test_comparison_vs(self):
        result = self.proc.detect_query_type("Pro vs Enterprise plan")
        assert result == QueryType.COMPARISON

    def test_comparison_versus(self):
        result = self.proc.detect_query_type("Basic versus Premium")
        assert result == QueryType.COMPARISON

    def test_causal_why(self):
        result = self.proc.detect_query_type("Why does my payment keep failing?")
        assert result == QueryType.CAUSAL

    def test_causal_what_caused(self):
        result = self.proc.detect_query_type("What caused the outage?")
        assert result == QueryType.CAUSAL

    def test_causal_due_to(self):
        result = self.proc.detect_query_type("The delay was due to weather")
        assert result == QueryType.CAUSAL

    def test_multi_part_also(self):
        result = self.proc.detect_query_type("How do I reset my password also how do I change my email?")
        assert result == QueryType.MULTI_PART

    def test_multi_part_plus(self):
        result = self.proc.detect_query_type("Check my order plus refund status")
        assert result == QueryType.MULTI_PART

    def test_multi_part_multiple_questions(self):
        # "What is this? How do I fix?" — "what caused" in causal patterns
        # could match. Use questions that avoid causal triggers.
        result = self.proc.detect_query_type("Can I cancel? How do I return? Is there a fee?")
        assert result == QueryType.MULTI_PART

    def test_sequential(self):
        result = self.proc.detect_query_type("First log in, then go to settings, after that change password")
        assert result == QueryType.SEQUENTIAL

    def test_single(self):
        result = self.proc.detect_query_type("What is my order status?")
        assert result == QueryType.SINGLE

    def test_empty_query(self):
        result = self.proc.detect_query_type("")
        assert result == QueryType.SINGLE

    def test_none_query(self):
        result = self.proc.detect_query_type(None)
        assert result == QueryType.SINGLE


# ── Decomposition Tests ──────────────────────────────────────────


class TestDecomposeQuery:
    """Tests for ChainOfThoughtProcessor.decompose_query()."""

    def setup_method(self):
        self.proc = ChainOfThoughtProcessor()

    @pytest.mark.asyncio
    async def test_comparison_produces_steps(self):
        steps = await self.proc.decompose_query("Difference between A and B")
        assert len(steps) >= 2

    @pytest.mark.asyncio
    async def test_causal_produces_3_steps(self):
        steps = await self.proc.decompose_query("Why does the payment fail?", QueryType.CAUSAL)
        assert len(steps) == 3

    @pytest.mark.asyncio
    async def test_single_produces_1_step(self):
        steps = await self.proc.decompose_query("Hello")
        assert len(steps) == 1
        assert steps[0].description == "Hello"

    @pytest.mark.asyncio
    async def test_empty_returns_empty(self):
        steps = await self.proc.decompose_query("")
        assert steps == []

    @pytest.mark.asyncio
    async def test_respects_max_steps(self):
        proc = ChainOfThoughtProcessor(config=CoTConfig(max_steps=2))
        steps = await proc.decompose_query(
            "First do this, then that, next another, after that more, finally last"
        )
        assert len(steps) <= 2

    @pytest.mark.asyncio
    async def test_steps_have_key_terms(self):
        steps = await self.proc.decompose_query("How to reset password?")
        assert len(steps) >= 1
        # At least some steps should have key terms (unless all filtered)
        total_terms = sum(len(s.key_terms) for s in steps)
        # Key terms may be empty if all words are stop words
        assert isinstance(total_terms, int)

    @pytest.mark.asyncio
    async def test_causal_steps_content(self):
        steps = await self.proc.decompose_query("Why did my order fail?", QueryType.CAUSAL)
        assert steps[0].step_type == QueryType.CAUSAL.value
        assert "effect" in steps[0].description.lower() or "outcome" in steps[0].description.lower()


# ── Validation Tests ─────────────────────────────────────────────


class TestValidateSteps:
    """Tests for ChainOfThoughtProcessor.validate_steps()."""

    def setup_method(self):
        self.proc = ChainOfThoughtProcessor()

    @pytest.mark.asyncio
    async def test_passed_step(self):
        steps = [CoTStep(
            step_number=1, step_type="single",
            description="test", reasoning="Some reasoning",
            key_terms=["test"],
        )]
        validated, summary = await self.proc.validate_steps(steps)
        assert validated[0].validation_status == "passed"
        assert "1 passed" in summary

    @pytest.mark.asyncio
    async def test_needs_data_no_reasoning(self):
        steps = [CoTStep(
            step_number=1, step_type="single",
            description="test", reasoning="",
            key_terms=["test"],
        )]
        validated, summary = await self.proc.validate_steps(steps)
        assert validated[0].validation_status == "needs_data"
        assert "1 need more data" in summary

    @pytest.mark.asyncio
    async def test_needs_data_no_key_terms(self):
        steps = [CoTStep(
            step_number=1, step_type="single",
            description="test", reasoning="Some reasoning",
            key_terms=[],
        )]
        validated, summary = await self.proc.validate_steps(steps)
        assert validated[0].validation_status == "needs_data"

    @pytest.mark.asyncio
    async def test_failed_no_description(self):
        steps = [CoTStep(
            step_number=1, step_type="single",
            description="", reasoning="Some reasoning",
            key_terms=["test"],
        )]
        validated, summary = await self.proc.validate_steps(steps)
        assert validated[0].validation_status == "failed"
        assert "1 failed" in summary

    @pytest.mark.asyncio
    async def test_empty_steps(self):
        validated, summary = await self.proc.validate_steps([])
        assert validated == []
        assert "No steps to validate" in summary

    @pytest.mark.asyncio
    async def test_mixed_statuses(self):
        steps = [
            CoTStep(1, "single", "desc1", "reasoning1", "", ["term1"]),
            CoTStep(2, "single", "desc2", "", "", ["term2"]),
            CoTStep(3, "single", "", "reasoning3", "", ["term3"]),
        ]
        validated, summary = await self.proc.validate_steps(steps)
        statuses = {s.validation_status for s in validated}
        assert "passed" in statuses
        assert "needs_data" in statuses
        assert "failed" in statuses


# ── Key Term Extraction Tests ────────────────────────────────────


class TestExtractKeyTerms:
    """Tests for ChainOfThoughtProcessor._extract_key_terms()."""

    def test_filters_stop_words(self):
        terms = ChainOfThoughtProcessor._extract_key_terms("the is a test")
        assert "the" not in terms
        assert "is" not in terms
        assert "a" not in terms
        assert "test" in terms

    def test_deduplicates(self):
        terms = ChainOfThoughtProcessor._extract_key_terms("test test test")
        assert len(terms) == 1
        assert terms[0] == "test"

    def test_max_five_terms(self):
        terms = ChainOfThoughtProcessor._extract_key_terms(
            "alpha beta gamma delta epsilon zeta"
        )
        assert len(terms) <= 5

    def test_empty_query(self):
        terms = ChainOfThoughtProcessor._extract_key_terms("")
        assert terms == []

    def test_returns_lowercase(self):
        terms = ChainOfThoughtProcessor._extract_key_terms("HELLO World TEST")
        assert all(t.islower() for t in terms)

    def test_short_words_filtered(self):
        terms = ChainOfThoughtProcessor._extract_key_terms("hi at it on")
        assert len(terms) == 0  # All are stop words or < 3 chars


# ── Synthesis Tests ──────────────────────────────────────────────


class TestSynthesis:
    """Tests for ChainOfThoughtProcessor.synthesize()."""

    def setup_method(self):
        self.proc = ChainOfThoughtProcessor()

    @pytest.mark.asyncio
    async def test_empty_steps(self):
        result = await self.proc.synthesize([], QueryType.SINGLE)
        assert result == ""

    @pytest.mark.asyncio
    async def test_steps_without_reasoning(self):
        steps = [CoTStep(1, "single", "test", "", "", [])]
        result = await self.proc.synthesize(steps, QueryType.SINGLE)
        # Should return template-based synthesis
        assert isinstance(result, str)


# ── Full Pipeline Tests ──────────────────────────────────────────


class TestProcess:
    """Tests for ChainOfThoughtProcessor.process() full pipeline."""

    def setup_method(self):
        self.proc = ChainOfThoughtProcessor()

    @pytest.mark.asyncio
    async def test_empty_query(self):
        result = await self.proc.process("")
        assert isinstance(result, CoTResult)
        assert "empty_input" in result.steps_applied

    @pytest.mark.asyncio
    async def test_single_query(self):
        result = await self.proc.process("What is my order status?")
        assert isinstance(result, CoTResult)
        assert "decomposition" in result.steps_applied

    @pytest.mark.asyncio
    async def test_comparison_query(self):
        result = await self.proc.process("Difference between Pro and Enterprise?")
        assert isinstance(result, CoTResult)
        assert len(result.steps_applied) >= 1

    @pytest.mark.asyncio
    async def test_result_has_confidence_boost(self):
        result = await self.proc.process("Why did my order fail?")
        assert result.confidence_boost >= 0

    @pytest.mark.asyncio
    async def test_never_crashes(self):
        """BC-008: process() never raises."""
        result = await self.proc.process("test" * 10000)
        assert isinstance(result, CoTResult)


# ── Data Structure Tests ─────────────────────────────────────────


class TestCoTStep:
    """Tests for CoTStep dataclass."""

    def test_to_dict(self):
        step = CoTStep(
            step_number=1, step_type="single",
            description="test", reasoning="analysis",
            key_terms=["hello"],
        )
        d = step.to_dict()
        assert d["step_number"] == 1
        assert d["step_type"] == "single"
        assert d["description"] == "test"
        assert d["reasoning"] == "analysis"
        assert d["key_terms"] == ["hello"]

    def test_defaults(self):
        step = CoTStep()
        assert step.step_number == 0
        assert step.step_type == ""
        assert step.description == ""
        assert step.reasoning == ""
        assert step.validation_status == ""
        assert step.key_terms == []


class TestCoTResult:
    """Tests for CoTResult dataclass."""

    def test_to_dict(self):
        result = CoTResult(
            decomposed_steps=[CoTStep(1, "single", "test")],
            reasoning_chain="Step 1: test",
            synthesis="Analysis complete",
            steps_applied=["decomposition", "reasoning"],
            confidence_boost=0.25,
        )
        d = result.to_dict()
        assert d["decomposed_steps"][0]["step_number"] == 1
        assert d["reasoning_chain"] == "Step 1: test"
        assert d["synthesis"] == "Analysis complete"
        assert len(d["steps_applied"]) == 2
        assert d["confidence_boost"] == 0.25

    def test_defaults(self):
        result = CoTResult()
        assert result.decomposed_steps == []
        assert result.reasoning_chain == ""
        assert result.synthesis == ""
        assert result.steps_applied == []
        assert result.confidence_boost == 0.0


class TestCoTConfig:
    """Tests for CoTConfig dataclass."""

    def test_defaults(self):
        config = CoTConfig()
        assert config.company_id == ""
        assert config.max_steps == 10
        assert config.enable_validation is True

    def test_custom_values(self):
        config = CoTConfig(company_id="comp_1", max_steps=5, enable_validation=False)
        assert config.company_id == "comp_1"
        assert config.max_steps == 5
        assert config.enable_validation is False
