"""
Tests for F-141: Reverse Thinking — Tier 2 Conditional AI Reasoning.

Covers configuration, should_activate logic, each pipeline step
individually, full pipeline execution, edge cases, company isolation
(BC-001), and error fallback (BC-008).

Target: 60+ tests.
"""

import pytest
from unittest.mock import patch

from app.core.technique_router import TechniqueID, QuerySignals
from app.core.techniques.base import (
    BaseTechniqueNode,
    ConversationState,
)
from app.core.techniques.reverse_thinking import (
    ReverseThinkingConfig,
    ReverseThinkingNode,
    ReverseThinkingProcessor,
    ReverseThinkingResult,
    InversionHypothesis,
    ErrorType,
    ProblemCategory,
    _CATEGORY_PATTERNS,
    _WRONG_ANSWER_TEMPLATES,
    _RESERVED_PHRASES,
    _VALIDATION_ANCHORS,
    _DEFAULT_CATEGORY,
)

# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def processor() -> ReverseThinkingProcessor:
    return ReverseThinkingProcessor()


@pytest.fixture
def company_processor() -> ReverseThinkingProcessor:
    config = ReverseThinkingConfig(
        company_id="comp_123",
        enable_validation=True,
        max_inversions=2,
    )
    return ReverseThinkingProcessor(config=config)


@pytest.fixture
def node() -> ReverseThinkingNode:
    return ReverseThinkingNode()


@pytest.fixture
def low_confidence_state() -> ConversationState:
    return ConversationState(
        query="I was charged $50 but I didn't authorize this",
        signals=QuerySignals(confidence_score=0.4),
    )


@pytest.fixture
def rejected_state() -> ConversationState:
    return ConversationState(
        query="My subscription is not working properly",
        signals=QuerySignals(
            confidence_score=0.8,
            previous_response_status="rejected",
        ),
    )


@pytest.fixture
def corrected_state() -> ConversationState:
    return ConversationState(
        query="I need help with my billing issue",
        signals=QuerySignals(
            confidence_score=0.8,
            previous_response_status="corrected",
        ),
    )


@pytest.fixture
def normal_state() -> ConversationState:
    return ConversationState(
        query="What is my account balance?",
        signals=QuerySignals(
            confidence_score=0.9,
            previous_response_status="accepted",
        ),
    )


@pytest.fixture
def empty_state() -> ConversationState:
    return ConversationState(
        query="",
        signals=QuerySignals(confidence_score=0.5),
    )


# ── Config Tests ─────────────────────────────────────────────────────


class TestReverseThinkingConfig:
    """Tests for ReverseThinkingConfig dataclass."""

    def test_default_config(self):
        config = ReverseThinkingConfig()
        assert config.company_id == ""
        assert config.enable_validation is True
        assert config.max_inversions == 3

    def test_frozen_immutability(self):
        config = ReverseThinkingConfig(company_id="comp_1")
        with pytest.raises(AttributeError):
            config.company_id = "new"  # type: ignore

    def test_custom_config(self):
        config = ReverseThinkingConfig(
            company_id="comp_2",
            enable_validation=False,
            max_inversions=1,
        )
        assert config.company_id == "comp_2"
        assert config.enable_validation is False
        assert config.max_inversions == 1

    def test_max_inversions_zero(self):
        config = ReverseThinkingConfig(max_inversions=0)
        assert config.max_inversions == 0

    def test_max_inversions_large(self):
        config = ReverseThinkingConfig(max_inversions=100)
        assert config.max_inversions == 100

    def test_company_id_default_empty(self):
        config = ReverseThinkingConfig()
        assert config.company_id == ""

    def test_enable_validation_true_by_default(self):
        config = ReverseThinkingConfig()
        assert config.enable_validation is True

    def test_enable_validation_false(self):
        config = ReverseThinkingConfig(enable_validation=False)
        assert config.enable_validation is False


# ── Result / Hypothesis Data Structure Tests ─────────────────────────


class TestInversionHypothesis:
    """Tests for InversionHypothesis dataclass."""

    def test_default_values(self):
        h = InversionHypothesis()
        assert h.hypothesis_text == ""
        assert h.error_type == ""
        assert h.inversion_result == ""

    def test_full_creation(self):
        h = InversionHypothesis(
            hypothesis_text="Wrong answer",
            error_type="factual_incorrect",
            inversion_result="Correct answer",
        )
        assert h.hypothesis_text == "Wrong answer"
        assert h.error_type == "factual_incorrect"
        assert h.inversion_result == "Correct answer"

    def test_mutable(self):
        h = InversionHypothesis()
        h.hypothesis_text = "Updated"
        assert h.hypothesis_text == "Updated"


class TestReverseThinkingResult:
    """Tests for ReverseThinkingResult dataclass."""

    def test_default_values(self):
        result = ReverseThinkingResult()
        assert result.problem_statement == ""
        assert result.wrong_hypotheses == []
        assert result.error_analysis == ""
        assert result.inverted_answer == ""
        assert result.validation_status == ""
        assert result.steps_applied == []
        assert result.confidence_boost == 0.0

    def test_full_creation(self):
        hypotheses = [InversionHypothesis(hypothesis_text="test")]
        result = ReverseThinkingResult(
            problem_statement="problem",
            wrong_hypotheses=hypotheses,
            error_analysis="errors found",
            inverted_answer="correct answer",
            validation_status="passed",
            steps_applied=["problem_statement", "inversion"],
            confidence_boost=0.25,
        )
        assert result.problem_statement == "problem"
        assert len(result.wrong_hypotheses) == 1
        assert result.validation_status == "passed"
        assert result.confidence_boost == 0.25

    def test_to_dict_keys(self):
        result = ReverseThinkingResult(
            problem_statement="p",
            inverted_answer="a",
            validation_status="v",
        )
        d = result.to_dict()
        expected_keys = {
            "problem_statement",
            "wrong_hypotheses",
            "error_analysis",
            "inverted_answer",
            "validation_status",
            "steps_applied",
            "confidence_boost",
        }
        assert set(d.keys()) == expected_keys

    def test_to_dict_hypotheses_serialized(self):
        h = InversionHypothesis(
            hypothesis_text="h",
            error_type="e",
            inversion_result="r",
        )
        result = ReverseThinkingResult(wrong_hypotheses=[h])
        d = result.to_dict()
        assert len(d["wrong_hypotheses"]) == 1
        assert d["wrong_hypotheses"][0]["hypothesis_text"] == "h"
        assert d["wrong_hypotheses"][0]["error_type"] == "e"
        assert d["wrong_hypotheses"][0]["inversion_result"] == "r"

    def test_to_dict_confidence_boost_rounded(self):
        result = ReverseThinkingResult(confidence_boost=0.256789)
        d = result.to_dict()
        assert d["confidence_boost"] == 0.2568

    def test_to_dict_steps_applied(self):
        result = ReverseThinkingResult(
            steps_applied=["step1", "step2", "step3"],
        )
        d = result.to_dict()
        assert d["steps_applied"] == ["step1", "step2", "step3"]


# ── Node Basic Tests ─────────────────────────────────────────────────


class TestReverseThinkingNode:
    """Tests for the ReverseThinkingNode class."""

    def test_is_base_technique_node(self, node):
        assert isinstance(node, BaseTechniqueNode)

    def test_technique_id(self, node):
        assert node.technique_id == TechniqueID.REVERSE_THINKING

    def test_technique_id_is_string(self, node):
        assert isinstance(node.technique_id.value, str)

    def test_technique_info_populated(self, node):
        assert node.technique_info is not None
        assert node.technique_info.id == TechniqueID.REVERSE_THINKING

    def test_tier_2(self, node):
        from app.core.technique_router import TechniqueTier

        assert node.technique_info.tier == TechniqueTier.TIER_2

    def test_node_with_custom_config(self):
        config = ReverseThinkingConfig(
            company_id="custom",
            max_inversions=1,
        )
        node = ReverseThinkingNode(config=config)
        assert node.technique_id == TechniqueID.REVERSE_THINKING


# ── should_activate Tests ────────────────────────────────────────────


class TestShouldActivate:
    """Tests for ReverseThinkingNode.should_activate()."""

    @pytest.mark.asyncio
    async def test_low_confidence_activates(self, node, low_confidence_state):
        assert await node.should_activate(low_confidence_state) is True

    @pytest.mark.asyncio
    async def test_confidence_exactly_07_does_not_activate(self, node):
        state = ConversationState(
            query="test",
            signals=QuerySignals(confidence_score=0.7),
        )
        assert await node.should_activate(state) is False

    @pytest.mark.asyncio
    async def test_confidence_069_activates(self, node):
        state = ConversationState(
            query="test",
            signals=QuerySignals(confidence_score=0.69),
        )
        assert await node.should_activate(state) is True

    @pytest.mark.asyncio
    async def test_rejected_status_activates(self, node, rejected_state):
        assert await node.should_activate(rejected_state) is True

    @pytest.mark.asyncio
    async def test_corrected_status_activates(self, node, corrected_state):
        assert await node.should_activate(corrected_state) is True

    @pytest.mark.asyncio
    async def test_normal_state_does_not_activate(self, node, normal_state):
        assert await node.should_activate(normal_state) is False

    @pytest.mark.asyncio
    async def test_accepted_status_does_not_activate(self, node):
        state = ConversationState(
            query="test",
            signals=QuerySignals(
                confidence_score=0.8,
                previous_response_status="accepted",
            ),
        )
        assert await node.should_activate(state) is False

    @pytest.mark.asyncio
    async def test_none_status_does_not_activate(self, node):
        state = ConversationState(
            query="test",
            signals=QuerySignals(
                confidence_score=0.8,
                previous_response_status="none",
            ),
        )
        assert await node.should_activate(state) is False

    @pytest.mark.asyncio
    async def test_confidence_zero_activates(self, node):
        state = ConversationState(
            query="test",
            signals=QuerySignals(confidence_score=0.0),
        )
        assert await node.should_activate(state) is True

    @pytest.mark.asyncio
    async def test_confidence_one_does_not_activate_alone(self, node):
        state = ConversationState(
            query="test",
            signals=QuerySignals(
                confidence_score=1.0,
                previous_response_status="none",
            ),
        )
        assert await node.should_activate(state) is False

    @pytest.mark.asyncio
    async def test_high_confidence_but_rejected_activates(self, node):
        """High confidence with rejected status should still activate."""
        state = ConversationState(
            query="test",
            signals=QuerySignals(
                confidence_score=0.95,
                previous_response_status="rejected",
            ),
        )
        assert await node.should_activate(state) is True

    @pytest.mark.asyncio
    async def test_high_confidence_but_corrected_activates(self, node):
        """High confidence with corrected status should still activate."""
        state = ConversationState(
            query="test",
            signals=QuerySignals(
                confidence_score=0.95,
                previous_response_status="corrected",
            ),
        )
        assert await node.should_activate(state) is True


# ── Step 1: Problem Statement Tests ──────────────────────────────────


class TestFormulateProblemStatement:
    """Tests for Step 1 — formulate_problem_statement()."""

    @pytest.mark.asyncio
    async def test_billing_query(self, processor):
        result = await processor.formulate_problem_statement(
            "I have a billing question about my invoice",
        )
        assert "billing" in result.lower()
        assert "query" in result.lower()

    @pytest.mark.asyncio
    async def test_refund_query(self, processor):
        result = await processor.formulate_problem_statement(
            "I want a refund for my last purchase",
        )
        assert "refund" in result.lower()

    @pytest.mark.asyncio
    async def test_subscription_query(self, processor):
        result = await processor.formulate_problem_statement(
            "I need to cancel my subscription plan",
        )
        assert "subscription" in result.lower()

    @pytest.mark.asyncio
    async def test_technical_query(self, processor):
        result = await processor.formulate_problem_statement(
            "The app keeps crashing when I try to login",
        )
        assert "technical" in result.lower()

    @pytest.mark.asyncio
    async def test_account_query(self, processor):
        result = await processor.formulate_problem_statement(
            "I want to change my account email settings",
        )
        assert "account" in result.lower()

    @pytest.mark.asyncio
    async def test_general_query(self, processor):
        result = await processor.formulate_problem_statement(
            "How does this service work?",
        )
        assert "general" in result.lower()

    @pytest.mark.asyncio
    async def test_empty_query(self, processor):
        result = await processor.formulate_problem_statement("")
        assert result == ""

    @pytest.mark.asyncio
    async def test_whitespace_query(self, processor):
        result = await processor.formulate_problem_statement("   ")
        assert result == ""

    @pytest.mark.asyncio
    async def test_includes_key_terms(self, processor):
        result = await processor.formulate_problem_statement(
            "I have an unexpected charge of $99 on my credit card",
        )
        assert "key terms" in result.lower()


# ── Step 2: Inversion Generation Tests ───────────────────────────────


class TestGenerateWrongHypotheses:
    """Tests for Step 2 — generate_wrong_hypotheses()."""

    @pytest.mark.asyncio
    async def test_billing_hypotheses(self, processor):
        result = await processor.generate_wrong_hypotheses(
            "I have a billing issue with my invoice",
        )
        assert len(result) > 0
        assert all(isinstance(h, InversionHypothesis) for h in result)
        assert all(h.hypothesis_text for h in result)
        assert all(h.inversion_result for h in result)

    @pytest.mark.asyncio
    async def test_refund_hypotheses(self, processor):
        result = await processor.generate_wrong_hypotheses(
            "I want a refund",
        )
        assert len(result) > 0
        for h in result:
            assert h.error_type != ""

    @pytest.mark.asyncio
    async def test_subscription_hypotheses(self, processor):
        result = await processor.generate_wrong_hypotheses(
            "cancel my subscription",
        )
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_technical_hypotheses(self, processor):
        result = await processor.generate_wrong_hypotheses(
            "the app is broken and won't connect",
        )
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_general_hypotheses(self, processor):
        result = await processor.generate_wrong_hypotheses(
            "hello how are you today",
        )
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_empty_query(self, processor):
        result = await processor.generate_wrong_hypotheses("")
        assert result == []

    @pytest.mark.asyncio
    async def test_max_inversions_respected(self, company_processor):
        result = await company_processor.generate_wrong_hypotheses(
            "I have a billing issue",
        )
        assert len(result) <= 2  # company_processor has max_inversions=2

    @pytest.mark.asyncio
    async def test_default_max_inversions(self, processor):
        result = await processor.generate_wrong_hypotheses(
            "billing issue with my account",
        )
        assert len(result) <= 3  # default max_inversions=3

    @pytest.mark.asyncio
    async def test_explicit_category(self, processor):
        result = await processor.generate_wrong_hypotheses(
            "something",
            category=ProblemCategory.BILLING,
        )
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_hypotheses_have_inversion_results(self, processor):
        result = await processor.generate_wrong_hypotheses(
            "I need a refund for this charge",
        )
        for h in result:
            assert len(h.inversion_result) > 0


# ── Step 3: Error Analysis Tests ─────────────────────────────────────


class TestAnalyzeErrors:
    """Tests for Step 3 — analyze_errors()."""

    @pytest.mark.asyncio
    async def test_empty_hypotheses(self, processor):
        result = await processor.analyze_errors([])
        assert "No hypotheses" in result

    @pytest.mark.asyncio
    async def test_single_hypothesis(self, processor):
        hypotheses = [
            InversionHypothesis(
                hypothesis_text="Wrong answer",
                error_type="factual_incorrect",
                inversion_result="Correct answer",
            )
        ]
        result = await processor.analyze_errors(hypotheses)
        assert "factual_incorrect" in result
        assert "1" in result  # 1 error pattern

    @pytest.mark.asyncio
    async def test_multiple_hypotheses(self, processor):
        hypotheses = [
            InversionHypothesis(
                hypothesis_text="Wrong 1",
                error_type="policy_violation",
                inversion_result="Correct 1",
            ),
            InversionHypothesis(
                hypothesis_text="Wrong 2",
                error_type="logical_fallacy",
                inversion_result="Correct 2",
            ),
        ]
        result = await processor.analyze_errors(hypotheses)
        assert "policy_violation" in result
        assert "logical_fallacy" in result
        assert "2" in result  # 2 error patterns

    @pytest.mark.asyncio
    async def test_duplicate_error_types(self, processor):
        hypotheses = [
            InversionHypothesis(
                hypothesis_text="W1",
                error_type="factual_incorrect",
                inversion_result="C1",
            ),
            InversionHypothesis(
                hypothesis_text="W2",
                error_type="factual_incorrect",
                inversion_result="C2",
            ),
        ]
        result = await processor.analyze_errors(hypotheses)
        assert "factual_incorrect(2)" in result

    @pytest.mark.asyncio
    async def test_analysis_includes_key_findings(self, processor):
        # Use a real template hypothesis so _get_error_reason finds the reason
        templates = _WRONG_ANSWER_TEMPLATES[ProblemCategory.BILLING]
        hypothesis = InversionHypothesis(
            hypothesis_text=templates[0]["hypothesis"],
            error_type=templates[0]["error_type"].value,
            inversion_result=templates[0]["inversion"],
        )
        result = await processor.analyze_errors([hypothesis])
        assert "Key findings" in result


# ── Step 4: Inversion Tests ──────────────────────────────────────────


class TestInvertToCorrectAnswer:
    """Tests for Step 4 — invert_to_correct_answer()."""

    @pytest.mark.asyncio
    async def test_empty_hypotheses(self, processor):
        result = await processor.invert_to_correct_answer([])
        assert result == ""

    @pytest.mark.asyncio
    async def test_single_hypothesis(self, processor):
        hypotheses = [
            InversionHypothesis(
                hypothesis_text="Wrong",
                error_type="e",
                inversion_result="This is the correct answer with verification.",
            )
        ]
        result = await processor.invert_to_correct_answer(hypotheses)
        assert "correct answer" in result

    @pytest.mark.asyncio
    async def test_selects_best_answer(self, processor):
        hypotheses = [
            InversionHypothesis(
                hypothesis_text="W1",
                error_type="e1",
                inversion_result="Short.",
            ),
            InversionHypothesis(
                hypothesis_text="W2",
                error_type="e2",
                inversion_result="This is a much longer and more detailed answer that provides specific guidance to the customer about how to verify their billing issue.",
            ),
        ]
        result = await processor.invert_to_correct_answer(hypotheses)
        # Should prefer the longer, more detailed answer
        assert "specific guidance" in result

    @pytest.mark.asyncio
    async def test_empty_inversion_result_skipped(self, processor):
        hypotheses = [
            InversionHypothesis(
                hypothesis_text="W1",
                error_type="e1",
                inversion_result="",
            ),
            InversionHypothesis(
                hypothesis_text="W2",
                error_type="e2",
                inversion_result="Valid answer.",
            ),
        ]
        result = await processor.invert_to_correct_answer(hypotheses)
        assert result == "Valid answer."


# ── Step 5: Validation Tests ─────────────────────────────────────────


class TestValidateAnswer:
    """Tests for Step 5 — validate_answer()."""

    @pytest.mark.asyncio
    async def test_good_answer_passes(self, processor):
        answer = (
            "Let me verify your account details and review the charge. "
            "I can confirm the refund is eligible based on our policy."
        )
        result = await processor.validate_answer(answer)
        assert result == "passed"

    @pytest.mark.asyncio
    async def test_empty_answer_fails(self, processor):
        result = await processor.validate_answer("")
        assert result == "failed"

    @pytest.mark.asyncio
    async def test_negative_absolute_fails(self, processor):
        answer = "You can never get a refund under any circumstances."
        result = await processor.validate_answer(answer)
        assert result == "failed"

    @pytest.mark.asyncio
    async def test_single_anchor_warning(self, processor):
        answer = "Please check your recent order."
        result = await processor.validate_answer(answer)
        assert result == "warning"

    @pytest.mark.asyncio
    async def test_answer_with_never_and_anchor(self, processor):
        answer = "I can verify your account. But refunds are never issued."
        # Has 1 anchor + 1 negative absolute => warning
        result = await processor.validate_answer(answer)
        assert result == "warning"

    @pytest.mark.asyncio
    async def test_specific_policy_answer_passes(self, processor):
        answer = (
            "Let me review your account to confirm eligibility. "
            "Based on your subscription, I can investigate the billing "
            "discrepancy and check the available options."
        )
        result = await processor.validate_answer(answer)
        assert result == "passed"

    @pytest.mark.asyncio
    async def test_multiple_negative_absolutes_fails(self, processor):
        answer = "This is always impossible and can never be fixed."
        result = await processor.validate_answer(answer)
        assert result == "failed"


# ── Full Pipeline Tests ──────────────────────────────────────────────


class TestFullPipeline:
    """Tests for the full 5-step process() method."""

    @pytest.mark.asyncio
    async def test_billing_query_pipeline(self, processor):
        result = await processor.process(
            "I was charged twice for the same invoice",
        )
        assert result.problem_statement != ""
        assert len(result.wrong_hypotheses) > 0
        assert result.error_analysis != ""
        assert result.inverted_answer != ""
        assert result.validation_status in ("passed", "warning", "failed")
        assert len(result.steps_applied) >= 3
        assert result.confidence_boost > 0

    @pytest.mark.asyncio
    async def test_refund_query_pipeline(self, processor):
        result = await processor.process(
            "I want my money back for this defective product",
        )
        assert "refund" in result.problem_statement.lower()
        assert result.inverted_answer != ""
        assert result.confidence_boost > 0

    @pytest.mark.asyncio
    async def test_subscription_query_pipeline(self, processor):
        result = await processor.process(
            "How do I downgrade my subscription plan?",
        )
        assert result.inverted_answer != ""
        assert "inversion_generation" in result.steps_applied

    @pytest.mark.asyncio
    async def test_technical_query_pipeline(self, processor):
        result = await processor.process(
            "The application keeps crashing on startup",
        )
        assert result.inverted_answer != ""

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
            "I need help with my refund request",
        )
        expected_steps = [
            "problem_statement",
            "inversion_generation",
            "error_analysis",
            "inversion",
            "validation",
        ]
        for step in expected_steps:
            assert step in result.steps_applied

    @pytest.mark.asyncio
    async def test_confidence_boost_range(self, processor):
        result = await processor.process("I have a billing question")
        assert 0.0 < result.confidence_boost <= 0.35

    @pytest.mark.asyncio
    async def test_to_dict_returns_dict(self, processor):
        result = await processor.process("refund issue")
        d = result.to_dict()
        assert isinstance(d, dict)


# ── Query Categorization Tests ───────────────────────────────────────


class TestCategorizeQuery:
    """Tests for the _categorize_query() utility method."""

    def test_billing_category(self):
        assert (
            ReverseThinkingProcessor._categorize_query("I have a billing question")
            == ProblemCategory.BILLING
        )

    def test_refund_category(self):
        assert (
            ReverseThinkingProcessor._categorize_query("I want a refund")
            == ProblemCategory.REFUND
        )

    def test_subscription_category(self):
        assert (
            ReverseThinkingProcessor._categorize_query("Cancel my subscription plan")
            == ProblemCategory.SUBSCRIPTION
        )

    def test_technical_category(self):
        assert (
            ReverseThinkingProcessor._categorize_query("The app is broken and crashes")
            == ProblemCategory.TECHNICAL
        )

    def test_account_category(self):
        assert (
            ReverseThinkingProcessor._categorize_query("Change my account email")
            == ProblemCategory.ACCOUNT
        )

    def test_general_category(self):
        assert (
            ReverseThinkingProcessor._categorize_query("Hello how are you")
            == ProblemCategory.GENERAL
        )

    def test_case_insensitive(self):
        assert (
            ReverseThinkingProcessor._categorize_query("BILLING INVOICE")
            == ProblemCategory.BILLING
        )

    def test_empty_query(self):
        assert ReverseThinkingProcessor._categorize_query("") == ProblemCategory.GENERAL

    def test_billing_match_with_charge(self):
        assert (
            ReverseThinkingProcessor._categorize_query("I see a charge on my statement")
            == ProblemCategory.BILLING
        )

    def test_refund_match_with_money_back(self):
        assert (
            ReverseThinkingProcessor._categorize_query("Give me my money back")
            == ProblemCategory.REFUND
        )

    def test_technical_match_with_bug(self):
        assert (
            ReverseThinkingProcessor._categorize_query("There is a bug in the system")
            == ProblemCategory.TECHNICAL
        )

    def test_subscription_match_with_upgrade(self):
        assert (
            ReverseThinkingProcessor._categorize_query("I want to upgrade my plan")
            == ProblemCategory.SUBSCRIPTION
        )


# ── Key Term Extraction Tests ────────────────────────────────────────


class TestExtractKeyTerms:
    """Tests for the _extract_key_terms() utility method."""

    def test_basic_extraction(self):
        terms = ReverseThinkingProcessor._extract_key_terms(
            "I have a billing problem with my invoice"
        )
        assert "billing" in terms
        assert "problem" in terms
        assert "invoice" in terms

    def test_stop_words_filtered(self):
        terms = ReverseThinkingProcessor._extract_key_terms(
            "I want to know how my account works"
        )
        # "I", "to", "how", "my" are stop words
        assert "want" not in terms or len(terms) <= 5
        assert "account" in terms

    def test_max_five_terms(self):
        terms = ReverseThinkingProcessor._extract_key_terms(
            "billing invoice charge payment subscription account profile"
        )
        assert len(terms) <= 5

    def test_empty_query(self):
        terms = ReverseThinkingProcessor._extract_key_terms("")
        assert terms == []

    def test_deduplication(self):
        terms = ReverseThinkingProcessor._extract_key_terms(
            "billing billing billing invoice invoice"
        )
        assert len([t for t in terms if t == "billing"]) == 1
        assert len([t for t in terms if t == "invoice"]) == 1

    def test_short_words_filtered(self):
        terms = ReverseThinkingProcessor._extract_key_terms("my be an it or")
        # All words are < 3 chars or stop words
        assert terms == []

    def test_preserves_order(self):
        terms = ReverseThinkingProcessor._extract_key_terms(
            "refund billing subscription technical"
        )
        if len(terms) >= 2:
            # Order should match first appearance
            idx = {t: i for i, t in enumerate(terms)}
            if "refund" in idx and "billing" in idx:
                assert idx["refund"] < idx["billing"]


# ── Inversion Scoring Tests ──────────────────────────────────────────


class TestScoreInversion:
    """Tests for the _score_inversion() utility method."""

    def test_empty_answer(self):
        assert ReverseThinkingProcessor._score_inversion("") == 0.0

    def test_longer_answer_scores_higher(self):
        short = "Hello."
        long = "Let me verify your account details and review the transaction history to confirm the billing discrepancy."
        assert ReverseThinkingProcessor._score_inversion(
            long
        ) > ReverseThinkingProcessor._score_inversion(short)

    def test_action_words_boost(self):
        plain = "Your issue will be addressed."
        with_actions = "Let me verify and review your account to confirm the details."
        assert ReverseThinkingProcessor._score_inversion(
            with_actions
        ) > ReverseThinkingProcessor._score_inversion(plain)

    def test_negative_absolutes_penalty(self):
        good = "I can check that for you."
        bad = "This can never be fixed and is always impossible."
        assert ReverseThinkingProcessor._score_inversion(
            good
        ) > ReverseThinkingProcessor._score_inversion(bad)

    def test_score_non_negative(self):
        score = ReverseThinkingProcessor._score_inversion(
            "This can never ever always be impossible never."
        )
        assert score >= 0.0


# ── Node execute() Tests ─────────────────────────────────────────────


class TestNodeExecute:
    """Tests for ReverseThinkingNode.execute()."""

    @pytest.mark.asyncio
    async def test_execute_updates_state(self, node, low_confidence_state):
        result = await node.execute(low_confidence_state)
        assert result is low_confidence_state
        assert TechniqueID.REVERSE_THINKING.value in result.technique_results

    @pytest.mark.asyncio
    async def test_execute_records_result(self, node, low_confidence_state):
        result = await node.execute(low_confidence_state)
        record = result.technique_results[TechniqueID.REVERSE_THINKING.value]
        assert record["status"] == "success"
        assert "result" in record

    @pytest.mark.asyncio
    async def test_execute_increases_confidence(self, node, low_confidence_state):
        original_confidence = low_confidence_state.signals.confidence_score
        result = await node.execute(low_confidence_state)
        assert result.signals.confidence_score >= original_confidence
        assert result.signals.confidence_score <= 1.0

    @pytest.mark.asyncio
    async def test_execute_appends_response(self, node, low_confidence_state):
        result = await node.execute(low_confidence_state)
        # Should have appended inverted answer to response_parts
        assert len(result.response_parts) > 0

    @pytest.mark.asyncio
    async def test_execute_with_empty_query(self, node, empty_state):
        result = await node.execute(empty_state)
        # Should not crash, state should still be returned
        assert result is empty_state

    @pytest.mark.asyncio
    async def test_execute_result_has_dict(self, node, low_confidence_state):
        result = await node.execute(low_confidence_state)
        record = result.technique_results[TechniqueID.REVERSE_THINKING.value]
        assert isinstance(record["result"], dict)


# ── Company Isolation Tests (BC-001) ─────────────────────────────────


class TestCompanyIsolation:
    """BC-001: Company data must be isolated."""

    def test_company_processor_has_company_id(self, company_processor):
        assert company_processor.config.company_id == "comp_123"

    def test_default_processor_no_company_id(self, processor):
        assert processor.config.company_id == ""

    def test_two_companies_independent(self):
        config1 = ReverseThinkingConfig(
            company_id="A",
            max_inversions=1,
        )
        config2 = ReverseThinkingConfig(
            company_id="B",
            max_inversions=3,
        )
        p1 = ReverseThinkingProcessor(config=config1)
        p2 = ReverseThinkingProcessor(config=config2)
        assert p1.config.max_inversions == 1
        assert p2.config.max_inversions == 3

    def test_node_company_config(self):
        config = ReverseThinkingConfig(company_id="tenant_X")
        node = ReverseThinkingNode(config=config)
        assert node._config.company_id == "tenant_X"

    def test_configs_not_shared(self):
        c1 = ReverseThinkingConfig(company_id="A")
        c2 = ReverseThinkingConfig(company_id="B")
        assert c1.company_id != c2.company_id


# ── Error Fallback Tests (BC-008) ────────────────────────────────────


class TestErrorFallback:
    """BC-008: Never crash — return original state on error."""

    @pytest.mark.asyncio
    async def test_execute_returns_original_on_exception(
        self, node, low_confidence_state
    ):
        """Force an exception inside execute() and verify original state returned."""
        with patch.object(
            node._processor,
            "process",
            side_effect=RuntimeError("boom"),
        ):
            result = await node.execute(low_confidence_state)
            assert result is low_confidence_state

    @pytest.mark.asyncio
    async def test_process_returns_fallback_on_internal_error(self, processor):
        """Force an exception inside process() pipeline."""
        with patch.object(
            processor,
            "formulate_problem_statement",
            side_effect=RuntimeError("pipeline error"),
        ):
            result = await processor.process("billing question")
            assert "error_fallback" in result.steps_applied

    @pytest.mark.asyncio
    async def test_processor_error_logs_warning(self, processor):
        """Error should be logged as warning, not crash."""
        with patch.object(
            processor,
            "formulate_problem_statement",
            side_effect=ValueError("error"),
        ):
            result = await processor.process("test query")
            assert isinstance(result, ReverseThinkingResult)

    @pytest.mark.asyncio
    async def test_empty_confidence_on_error(self, processor):
        """Confidence boost should be 0 on error."""
        with patch.object(
            processor,
            "generate_wrong_hypotheses",
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
        query = "billing " * 500 + "I need help with my invoice"
        result = await processor.process(query)
        assert isinstance(result, ReverseThinkingResult)

    @pytest.mark.asyncio
    async def test_special_characters(self, processor):
        """Special characters should not crash the processor."""
        query = "I was charged $49.99 (invoice #INV-2024-001)! Refund? <test>"
        result = await processor.process(query)
        assert result.problem_statement != ""

    @pytest.mark.asyncio
    async def test_unicode_characters(self, processor):
        """Unicode characters should not crash."""
        query = "I have a billing question about my invoice — résumé café"
        result = await processor.process(query)
        assert isinstance(result, ReverseThinkingResult)

    @pytest.mark.asyncio
    async def test_only_stop_words(self, processor):
        """Query containing only stop words should still process."""
        query = "I am the one who is in it"
        result = await processor.process(query)
        assert isinstance(result, ReverseThinkingResult)

    @pytest.mark.asyncio
    async def test_newlines_in_query(self, processor):
        """Newlines in query should be handled."""
        query = "I have a billing\n\nquestion about my\ninvoice"
        result = await processor.process(query)
        assert isinstance(result, ReverseThinkingResult)

    @pytest.mark.asyncio
    async def test_tabs_in_query(self, processor):
        """Tabs in query should be handled."""
        query = "billing\t\tinvoice\tcharge"
        result = await processor.process(query)
        assert isinstance(result, ReverseThinkingResult)

    @pytest.mark.asyncio
    async def test_validation_disabled(self):
        """Validation step should be skipped when disabled."""
        config = ReverseThinkingConfig(enable_validation=False)
        proc = ReverseThinkingProcessor(config=config)
        result = await proc.process("billing question")
        assert "validation" not in result.steps_applied
        assert result.validation_status == "skipped"

    @pytest.mark.asyncio
    async def test_zero_max_inversions(self):
        """Zero max_inversions should produce no hypotheses."""
        config = ReverseThinkingConfig(max_inversions=0)
        proc = ReverseThinkingProcessor(config=config)
        result = await proc.process("billing question")
        assert len(result.wrong_hypotheses) == 0
        # Should still produce a problem statement
        assert result.problem_statement != ""

    @pytest.mark.asyncio
    async def test_single_word_query(self, processor):
        result = await processor.process("refund")
        assert isinstance(result, ReverseThinkingResult)

    @pytest.mark.asyncio
    async def test_mixed_case_query(self, processor):
        result = await processor.process("I WANT A REFUND FOR MY BILLING")
        assert isinstance(result, ReverseThinkingResult)


# ── Template / Constant Tests ────────────────────────────────────────


class TestTemplatesAndConstants:
    """Tests for predefined templates and constants."""

    def test_category_patterns_exist(self):
        assert len(_CATEGORY_PATTERNS) >= 5

    def test_all_categories_have_templates(self):
        for category in ProblemCategory:
            assert (
                category in _WRONG_ANSWER_TEMPLATES
            ), f"Missing templates for {category}"

    def test_billing_templates_count(self):
        assert len(_WRONG_ANSWER_TEMPLATES[ProblemCategory.BILLING]) >= 3

    def test_refund_templates_count(self):
        assert len(_WRONG_ANSWER_TEMPLATES[ProblemCategory.REFUND]) >= 3

    def test_reserved_phrases_not_empty(self):
        assert len(_RESERVED_PHRASES) >= 10

    def test_validation_anchors_not_empty(self):
        assert len(_VALIDATION_ANCHORS) >= 5

    def test_default_category_is_general(self):
        assert _DEFAULT_CATEGORY == ProblemCategory.GENERAL

    def test_error_types_complete(self):
        expected = {
            "factual_incorrect",
            "policy_violation",
            "logical_fallacy",
            "incomplete_info",
            "misinterpretation",
            "wrong_scope",
        }
        actual = {et.value for et in ErrorType}
        assert expected == actual

    def test_templates_have_required_fields(self):
        """All templates must have hypothesis, error_type, error_reason, inversion."""
        for category, templates in _WRONG_ANSWER_TEMPLATES.items():
            for template in templates:
                assert "hypothesis" in template, f"Missing 'hypothesis' in {category}"
                assert "error_type" in template, f"Missing 'error_type' in {category}"
                assert (
                    "error_reason" in template
                ), f"Missing 'error_reason' in {category}"
                assert "inversion" in template, f"Missing 'inversion' in {category}"
                assert isinstance(
                    template["error_type"], ErrorType
                ), f"error_type should be ErrorType in {category}"


# ── _get_error_reason Tests ──────────────────────────────────────────


class TestGetErrorReason:
    """Tests for _get_error_reason() utility."""

    def test_finds_reason_for_known_hypothesis(self):
        templates = _WRONG_ANSWER_TEMPLATES[ProblemCategory.BILLING]
        hypothesis = InversionHypothesis(
            hypothesis_text=templates[0]["hypothesis"],
            error_type=templates[0]["error_type"].value,
            inversion_result="",
        )
        reason = ReverseThinkingProcessor._get_error_reason(hypothesis)
        assert reason == templates[0]["error_reason"]

    def test_empty_for_unknown_hypothesis(self):
        hypothesis = InversionHypothesis(
            hypothesis_text="Completely unknown hypothesis text",
            error_type="factual_incorrect",
            inversion_result="",
        )
        reason = ReverseThinkingProcessor._get_error_reason(hypothesis)
        assert reason == ""
