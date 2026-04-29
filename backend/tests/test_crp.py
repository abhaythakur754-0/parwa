"""
Tests for F-140: Concise Response Protocol (CRP) Processor.

Covers filler elimination, compression, redundancy removal,
token budget enforcement, full pipeline, and edge cases.
"""

from unittest.mock import patch

import pytest
from app.core.techniques.crp import (
    _COMPRESSION_RULES,
    _RESERVED_PHRASES,
    DEFAULT_FILLERS,
    CRPConfig,
    CRPProcessor,
    CRPResult,
)

# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def processor() -> CRPProcessor:
    return CRPProcessor()


@pytest.fixture
def company_processor() -> CRPProcessor:
    config = CRPConfig(
        company_id="comp_123",
        custom_fillers=(r"Thanks for choosing us!?\s*",),
    )
    return CRPProcessor(config=config)


# ── Constants Tests ──────────────────────────────────────────────────


class TestConstants:
    def test_default_filler_count(self):
        assert len(DEFAULT_FILLERS) >= 20

    def test_has_opening_fillers(self):
        assert any("happy to help" in f for f in DEFAULT_FILLERS)

    def test_has_closing_fillers(self):
        assert any("hesitate" in f for f in DEFAULT_FILLERS)

    def test_has_transition_fillers(self):
        assert any("look into" in f for f in DEFAULT_FILLERS)

    def test_compression_rules_count(self):
        assert len(_COMPRESSION_RULES) >= 20

    def test_compression_rules_compile(self):
        for pattern, _ in _COMPRESSION_RULES:
            assert pattern.pattern, f"Pattern {pattern} has no source"


# ── Config Tests ─────────────────────────────────────────────────────


class TestCRPConfig:
    def test_default_config(self):
        config = CRPConfig()
        assert config.company_id == ""
        assert config.custom_fillers == ()
        assert config.enable_compression is True
        assert config.enable_redundancy_removal is True
        assert config.keep_empathy is False

    def test_frozen_immutability(self):
        config = CRPConfig(company_id="comp_1")
        with pytest.raises(AttributeError):
            config.company_id = "new"  # type: ignore

    def test_custom_config(self):
        config = CRPConfig(
            company_id="comp_2",
            custom_fillers=(r"Test filler",),
            min_token_budget=50,
        )
        assert config.company_id == "comp_2"
        assert len(config.custom_fillers) == 1
        assert config.min_token_budget == 50

    def test_disabled_features(self):
        config = CRPConfig(
            enable_compression=False,
            enable_redundancy_removal=False,
        )
        assert config.enable_compression is False
        assert config.enable_redundancy_removal is False


# ── Result Tests ─────────────────────────────────────────────────────


class TestCRPResult:
    def test_basic_creation(self):
        result = CRPResult(
            processed_text="Hello world",
            original_tokens=10,
            processed_tokens=5,
            reduction_pct=50.0,
            steps_applied=["filler_elimination"],
        )
        assert result.processed_text == "Hello world"
        assert result.reduction_pct == 50.0

    def test_to_dict(self):
        result = CRPResult(
            processed_text="Hi",
            original_tokens=10,
            processed_tokens=2,
            reduction_pct=80.0,
            steps_applied=["compression"],
        )
        d = result.to_dict()
        assert d["processed_text"] == "Hi"
        assert d["original_tokens"] == 10
        assert d["reduction_pct"] == 80.0
        assert "compression" in d["steps_applied"]

    def test_default_values(self):
        result = CRPResult()
        assert result.processed_text == ""
        assert result.original_tokens == 0
        assert result.steps_applied == []

    def test_dict_keys(self):
        result = CRPResult(processed_text="x")
        d = result.to_dict()
        expected_keys = {
            "processed_text",
            "original_tokens",
            "processed_tokens",
            "reduction_pct",
            "steps_applied",
        }
        assert set(d.keys()) == expected_keys


# ── Token Estimation ─────────────────────────────────────────────────


class TestEstimateTokens:
    def test_empty(self):
        assert CRPProcessor.estimate_tokens("") == 0

    def test_whitespace(self):
        # max(1, ...) ensures minimum 1 even for whitespace
        assert CRPProcessor.estimate_tokens("   ") == 1

    def test_short_text(self):
        assert CRPProcessor.estimate_tokens("Hello") == 1

    def test_longer_text(self):
        text = "a" * 40
        assert CRPProcessor.estimate_tokens(text) == 10

    def test_monotonic(self):
        t1 = CRPProcessor.estimate_tokens("Hello world")
        t2 = CRPProcessor.estimate_tokens("Hello world! More text here.")
        assert t2 >= t1


# ── Filler Elimination ───────────────────────────────────────────────


class TestFillerElimination:
    @pytest.mark.asyncio
    async def test_happy_to_help(self, processor):
        text = "I'd be happy to help you with that. Your refund is approved."
        result = await processor.eliminate_fillers(text)
        assert "happy to help" not in result.lower()
        assert "refund" in result
        assert "approved" in result

    @pytest.mark.asyncio
    async def test_certainly_assist(self, processor):
        text = "Certainly, I can assist. Here is your order status."
        result = await processor.eliminate_fillers(text)
        assert "certainly" not in result.lower()

    @pytest.mark.asyncio
    async def test_opening_filler(self, processor):
        text = "Of course! I'd be glad to help with your question."
        result = await processor.eliminate_fillers(text)
        assert "of course" not in result.lower()

    @pytest.mark.asyncio
    async def test_closing_filler(self, processor):
        text = "Your order has shipped. Please don't hesitate to reach out."
        result = await processor.eliminate_fillers(text)
        assert "don't hesitate" not in result.lower()

    @pytest.mark.asyncio
    async def test_multiple_fillers(self, processor):
        text = (
            "Great question! Let me look into that for you. "
            "Your subscription ends on March 15. "
            "Let me know if there's anything else."
        )
        result = await processor.eliminate_fillers(text)
        assert "great question" not in result.lower()
        assert "look into that" not in result.lower()
        assert "subscription" in result
        assert "March 15" in result

    @pytest.mark.asyncio
    async def test_no_fillers(self, processor):
        text = "Your refund of $50 has been processed."
        result = await processor.eliminate_fillers(text)
        assert result == text

    @pytest.mark.asyncio
    async def test_empty_string(self, processor):
        result = await processor.eliminate_fillers("")
        assert result == ""

    @pytest.mark.asyncio
    async def test_whitespace_only(self, processor):
        result = await processor.eliminate_fillers("   ")
        assert result == ""

    @pytest.mark.asyncio
    async def test_content_preserved(self, processor):
        text = "I'd be happy to help you with that. Your refund amount is $49.99 for order #12345."
        result = await processor.eliminate_fillers(text)
        assert "$49.99" in result
        assert "#12345" in result
        assert "refund" in result

    @pytest.mark.asyncio
    async def test_custom_filler(self, company_processor):
        text = "Thanks for choosing us! Here is your invoice."
        result = await company_processor.eliminate_fillers(text)
        assert "Thanks for choosing us" not in result
        assert "invoice" in result


# ── Compression ─────────────────────────────────────────────────────


class TestCompression:
    @pytest.mark.asyncio
    async def test_in_order_to(self, processor):
        text = "In order to process your refund, we need your account ID."
        result = await processor.compress_response(text)
        assert "In order to" not in result
        assert "To process" in result

    @pytest.mark.asyncio
    async def test_at_this_point(self, processor):
        text = "At this point in time, your subscription is active."
        result = await processor.compress_response(text)
        assert "At this point in time" not in result
        assert "Currently" in result

    @pytest.mark.asyncio
    async def test_multiple_compressions(self, processor):
        text = "In addition, a number of users have requested this feature. Furthermore, prior to the update, there were bugs."
        result = await processor.compress_response(text)
        assert "In addition" not in result
        assert "Furthermore" not in result
        assert "prior to" not in result

    @pytest.mark.asyncio
    async def test_disabled(self):
        config = CRPConfig(enable_compression=False)
        proc = CRPProcessor(config=config)
        text = "In order to help you, I need more info."
        result = await proc.compress_response(text)
        assert "In order to" in result

    @pytest.mark.asyncio
    async def test_empty(self, processor):
        result = await processor.compress_response("")
        assert result == ""

    @pytest.mark.asyncio
    async def test_no_compression_needed(self, processor):
        text = "Your order has shipped."
        result = await processor.compress_response(text)
        # May or may not change, but content preserved
        assert "shipped" in result


# ── Redundancy Removal ───────────────────────────────────────────────


class TestRedundancyRemoval:
    @pytest.mark.asyncio
    async def test_duplicate_removal(self, processor):
        text = (
            "Your refund has been approved and credited. "
            "The refund has been approved and credited to your account. "
            "You will receive it in 3-5 days."
        )
        result = await processor.remove_redundancy(text)
        # One of the two near-duplicate sentences should be removed
        assert result.count("approved and credited") <= 1

    @pytest.mark.asyncio
    async def test_distinct_preserved(self, processor):
        text = (
            "Your order has been shipped. "
            "The tracking number is TRK-123. "
            "You will receive it by Friday."
        )
        result = await processor.remove_redundancy(text)
        assert "shipped" in result
        assert "tracking" in result
        assert "Friday" in result

    @pytest.mark.asyncio
    async def test_disabled(self):
        config = CRPConfig(enable_redundancy_removal=False)
        proc = CRPProcessor(config=config)
        text = "Refund approved. The refund is approved."
        result = await proc.remove_redundancy(text)
        assert result.count("approved") == 2


# ── Token Budget Enforcement ─────────────────────────────────────────


class TestTokenBudgetEnforcement:
    @pytest.mark.asyncio
    async def test_within_budget(self, processor):
        text = "Your refund is processed."
        result = await processor.enforce_token_budget(text, max_tokens=1000)
        assert result == text

    @pytest.mark.asyncio
    async def test_truncation(self, processor):
        long_text = (
            "This is a sentence about your order. "
            "Another sentence about the refund. "
            "More details about your subscription. "
            "Final note about the billing."
        )
        result = await processor.enforce_token_budget(long_text, max_tokens=10)
        tokens = CRPProcessor.estimate_tokens(result)
        assert tokens <= 25  # min_token_budget=20 floor + slack for sentence boundary

    @pytest.mark.asyncio
    async def test_zero_budget(self, processor):
        text = "Hello world."
        result = await processor.enforce_token_budget(text, max_tokens=0)
        # min_token_budget = 20, so should still get something
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_empty(self, processor):
        result = await processor.enforce_token_budget("", max_tokens=100)
        assert result == ""

    @pytest.mark.asyncio
    async def test_exact_budget(self, processor):
        text = "Hello world."
        tokens = CRPProcessor.estimate_tokens(text)
        result = await processor.enforce_token_budget(text, max_tokens=tokens + 5)
        assert result == text


# ── Full Pipeline ─────────────────────────────────────────────────────


class TestFullPipeline:
    @pytest.mark.asyncio
    async def test_verbose_input(self, processor):
        text = (
            "I'd be happy to help you with that! "
            "In order to process your refund, we need your account details. "
            "Your refund has been processed. The refund was processed successfully. "
            "Please don't hesitate to reach out if you need anything else."
        )
        result = await processor.process(text, complexity=0.5)
        assert result.original_tokens > 0
        assert result.processed_tokens <= result.original_tokens
        assert result.processed_text != text

    @pytest.mark.asyncio
    async def test_already_concise(self, processor):
        text = "Refund approved. $50 credited to your account."
        result = await processor.process(text)
        assert "Refund" in result.processed_text
        assert "$50" in result.processed_text

    @pytest.mark.asyncio
    async def test_empty_input(self, processor):
        result = await processor.process("")
        assert result.processed_text == ""
        assert result.original_tokens == 0

    @pytest.mark.asyncio
    async def test_whitespace_input(self, processor):
        result = await processor.process("   ")
        assert result.processed_text.strip() == ""

    @pytest.mark.asyncio
    async def test_steps_applied(self, processor):
        text = (
            "I'd be happy to help you with that. "
            "In order to check your order, please provide the ID."
        )
        result = await processor.process(text)
        assert len(result.steps_applied) >= 1

    @pytest.mark.asyncio
    async def test_complexity_scaling(self, processor):
        verbose = (
            "I'd be happy to help. In order to resolve your billing issue, "
            "I will need to look at your account. Your account shows a charge of $100. "
            "Please don't hesitate to contact us for more help."
        )
        result_low = await processor.process(verbose, complexity=0.1)
        result_high = await processor.process(verbose, complexity=0.9)
        # High complexity should preserve more tokens
        assert result_low.processed_tokens <= result_high.processed_tokens

    @pytest.mark.asyncio
    async def test_key_facts_preserved(self, processor):
        text = (
            "I'd be happy to help you with that. "
            "Your refund of $49.99 for order ORD-12345 has been processed. "
            "Please feel free to reach out."
        )
        result = await processor.process(text)
        assert "$49.99" in result.processed_text
        assert "ORD-12345" in result.processed_text

    @pytest.mark.asyncio
    async def test_max_tokens_override(self, processor):
        text = "Hello world. This is extra text that should be removed."
        result = await processor.process(text, max_tokens=5)
        tokens = CRPProcessor.estimate_tokens(result.processed_text)
        assert tokens <= 15  # slack for min_token_budget

    @pytest.mark.asyncio
    async def test_reduction_percentage(self, processor):
        verbose = (
            "I'd be happy to help you with that. "
            "I'd love to help. Certainly I can assist. "
            "Of course! Let me look into that for you. "
            "Your order status is shipped."
        )
        result = await processor.process(verbose)
        assert result.reduction_pct > 0

    @pytest.mark.asyncio
    async def test_result_to_dict(self, processor):
        result = await processor.process("Hello world.")
        d = result.to_dict()
        assert isinstance(d, dict)
        assert "processed_text" in d


# ── Company Isolation ────────────────────────────────────────────────


class TestCompanyIsolation:
    @pytest.mark.asyncio
    async def test_custom_filler_applied(self, company_processor):
        text = "Thanks for choosing us! Your account is verified."
        result = await company_processor.eliminate_fillers(text)
        assert "Thanks for choosing us" not in result

    @pytest.mark.asyncio
    async def test_default_filler_still_works(self, company_processor):
        text = "I'd be happy to help you with that. Order confirmed."
        result = await company_processor.eliminate_fillers(text)
        assert "happy to help" not in result.lower()

    @pytest.mark.asyncio
    async def test_two_companies_independent(self):
        config1 = CRPConfig(company_id="A", custom_fillers=(r"Custom phrase A",))
        config2 = CRPConfig(company_id="B", custom_fillers=(r"Custom phrase B",))
        p1 = CRPProcessor(config=config1)
        p2 = CRPProcessor(config=config2)

        text = "Custom phrase A. Your refund is approved."
        r1 = await p1.eliminate_fillers(text)
        assert "Custom phrase A" not in r1

        r2 = await p2.eliminate_fillers(text)
        assert "Custom phrase A" in r2  # not a filler for company B

    @pytest.mark.asyncio
    async def test_config_defaults_not_shared(self):
        p1 = CRPProcessor()
        p2 = CRPProcessor(CRPConfig(company_id="X"))
        assert p1.config.company_id == ""
        assert p2.config.company_id == "X"


# ── Sentence Helpers ────────────────────────────────────────────────


class TestSentenceHelpers:
    def test_split_sentences(self):
        text = "Hello world. How are you? I am fine!"
        result = CRPProcessor._split_sentences(text)
        assert len(result) == 3
        assert result[0] == "Hello world."
        assert result[2] == "I am fine!"

    def test_split_empty(self):
        assert CRPProcessor._split_sentences("") == []

    def test_split_single(self):
        result = CRPProcessor._split_sentences("One sentence.")
        assert len(result) == 1

    def test_join_sentences(self):
        sentences = ["First.", "Second.", "Third."]
        result = CRPProcessor._join_sentences(sentences)
        assert result == "First. Second. Third."


# ── Redundancy Detection ─────────────────────────────────────────────


class TestIsRedundant:
    def test_identical(self):
        words = {"the", "refund", "is", "processed"}
        prev = [words]
        assert CRPProcessor._is_redundant(words, prev)

    def test_different(self):
        words = {"order", "shipped", "fedex"}
        prev = [{"the", "refund", "is", "processed"}]
        assert not CRPProcessor._is_redundant(words, prev)

    def test_partially_overlapping(self):
        words = {"the", "refund", "is", "confirmed"}
        prev = [{"the", "refund", "is", "processed"}]
        # 3/5 overlap = 0.6 similarity < 0.7 threshold
        assert not CRPProcessor._is_redundant(words, prev)

    def test_empty_input(self):
        assert CRPProcessor._is_redundant(set(), [])

    def test_empty_previous(self):
        assert not CRPProcessor._is_redundant({"hello"}, [])


# ── Budget Calculation ───────────────────────────────────────────────


class TestBudgetCalculation:
    def test_low_complexity(self):
        budget = CRPProcessor._calculate_budget(100, 0.1)
        assert budget == 60  # 60% of 100

    def test_medium_complexity(self):
        budget = CRPProcessor._calculate_budget(100, 0.5)
        assert budget == 80  # 80% of 100

    def test_high_complexity(self):
        budget = CRPProcessor._calculate_budget(100, 0.9)
        assert budget == 95  # 95% of 100

    def test_minimum_floor(self):
        budget = CRPProcessor._calculate_budget(10, 0.1)
        assert budget >= 20  # minimum 20 tokens

    def test_clamping(self):
        budget = CRPProcessor._calculate_budget(5, 0.1)
        assert budget == 20  # min floor


# ── Performance Targets ─────────────────────────────────────────────


class TestPerformance:
    @pytest.mark.asyncio
    async def test_reduction_target(self, processor):
        verbose = (
            "I'd be happy to help you with that. "
            "Certainly I can assist. "
            "Of course, I'd be glad to look into that for you. "
            "Let me know if there's anything else. "
            "Your order has been shipped via FedEx."
        )
        result = await processor.process(verbose)
        assert result.reduction_pct >= 10  # at least some reduction

    @pytest.mark.asyncio
    async def test_key_fact_preservation(self, processor):
        text = (
            "I'd be happy to help you with that. "
            "Your refund of $99.99 for invoice INV-001 has been processed. "
            "Please don't hesitate to reach out."
        )
        result = await processor.process(text)
        assert "$99.99" in result.processed_text
        assert "INV-001" in result.processed_text


# ── Gap Tests: Invalid Regex Handling ────────────────────────────────


class TestInvalidRegexPatterns:
    """Invalid regex patterns should be silently skipped (BC-008)."""

    def test_invalid_custom_filler_regex_skipped(self):
        """Invalid custom filler regex should not crash; should log warning."""
        config = CRPConfig(
            company_id="test",
            custom_fillers=(r"[invalid",),  # Unclosed bracket
        )
        processor = CRPProcessor(config=config)
        # Should have compiled DEFAULT_FILLERS (invalid one skipped)
        assert len(processor._filler_patterns) == len(DEFAULT_FILLERS)

    def test_invalid_custom_compression_regex_skipped(self):
        """Invalid custom compression regex should not crash."""
        config = CRPConfig(
            company_id="test",
            custom_compressions=((r"(?P<name", "replacement"),),  # Invalid
        )
        processor = CRPProcessor(config=config)
        # Should have all default compression rules
        assert len(processor._compression_rules) == len(_COMPRESSION_RULES)

    def test_multiple_invalid_fillers(self):
        """Multiple invalid fillers should all be skipped."""
        config = CRPConfig(
            company_id="test",
            custom_fillers=(r"[invalid1", r"[invalid2", r"valid.*pattern"),
        )
        processor = CRPProcessor(config=config)
        assert len(processor._filler_patterns) == len(DEFAULT_FILLERS) + 1


# ── Gap Tests: keep_empathy ──────────────────────────────────────────


class TestKeepEmpathy:
    """keep_empathy should suppress empathy filler removal for upset customers."""

    def test_keep_empathy_excludes_empathy_patterns(self):
        """When keep_empathy=True, empathy patterns should be excluded."""
        config = CRPConfig(keep_empathy=True)
        processor = CRPProcessor(config=config)
        normal_processor = CRPProcessor()
        # keep_empathy processor should have fewer patterns
        assert len(processor._filler_patterns) < len(normal_processor._filler_patterns)

    @pytest.mark.asyncio
    async def test_keep_empathy_preserves_empathy_phrases(self):
        """When keep_empathy=True, empathy phrases should NOT be removed."""
        config = CRPConfig(keep_empathy=True)
        processor = CRPProcessor(config=config)
        text = "I understand how frustrating this can be. Your refund is processed."
        result = await processor.eliminate_fillers(text)
        assert "understand" in result.lower() or "frustrating" in result.lower()

    @pytest.mark.asyncio
    async def test_keep_empathy_false_removes_empathy(self):
        """When keep_empathy=False (default), empathy phrases SHOULD be removed."""
        processor = CRPProcessor()
        text = "I completely understand how frustrating this must be. Your refund is processed."
        result = await processor.eliminate_fillers(text)
        assert "refund" in result
        # Empathy phrase should be removed
        assert result != text


# ── Gap Tests: Reserved Phrases ──────────────────────────────────────


class TestReservedPhrases:
    """Reserved phrases should be identifiable via _is_reserved."""

    def test_reserved_refund(self):
        assert CRPProcessor._is_reserved("refund") is True

    def test_reserved_payment(self):
        assert CRPProcessor._is_reserved("payment") is True

    def test_reserved_case_insensitive(self):
        assert CRPProcessor._is_reserved("REFUND") is True
        assert CRPProcessor._is_reserved("Refund") is True

    def test_non_reserved_word(self):
        assert CRPProcessor._is_reserved("hello") is False

    def test_non_reserved_empty(self):
        assert CRPProcessor._is_reserved("") is False

    def test_reserved_constant_has_values(self):
        """_RESERVED_PHRASES should contain critical business terms."""
        assert "refund" in _RESERVED_PHRASES
        assert "payment" in _RESERVED_PHRASES
        assert "invoice" in _RESERVED_PHRASES


# ── Gap Tests: Callable Compression ──────────────────────────────────


class TestCallableCompression:
    """Ordinal compression with lambda replacement should work."""

    @pytest.mark.asyncio
    async def test_ordinal_list_compression(self, processor):
        """First, Second, Third should be numbered with period."""
        text = "First, check the account. Second, verify the charge. Third, process refund."
        result = await processor.compress_response(text)
        # The lambda strips trailing comma and adds period
        assert "First." in result
        assert "Second." in result
        assert "Third." in result


# ── Gap Tests: Error Fallback (BC-008) ──────────────────────────────


class TestErrorFallback:
    """BC-008: process() should return original text on exception."""

    @pytest.mark.asyncio
    async def test_process_returns_original_on_internal_error(self, processor):
        """Force an exception inside process() pipeline."""
        with patch.object(
            processor, "eliminate_fillers", side_effect=RuntimeError("boom")
        ):
            result = await processor.process("Hello world test text.")
            assert result.processed_text == "Hello world test text."
            assert "error_fallback" in result.steps_applied

    @pytest.mark.asyncio
    async def test_process_metrics_on_error(self, processor):
        """Error fallback should still report original token count."""
        with patch.object(
            processor, "compress_response", side_effect=ValueError("err")
        ):
            result = await processor.process("Some test text here.")
            assert result.original_tokens > 0
            assert result.processed_tokens == result.original_tokens
            assert result.reduction_pct == 0.0


# ── Gap Tests: _normalize Edge Cases ────────────────────────────────


class TestNormalize:
    """_normalize should handle edge cases."""

    def test_normalize_unicode(self):
        """Unicode characters should be handled by \\w regex."""
        result = CRPProcessor._normalize("Hello world")
        assert "hello" in result
        assert "world" in result

    def test_normalize_empty(self):
        assert CRPProcessor._normalize("") == set()

    def test_normalize_numbers(self):
        result = CRPProcessor._normalize("Order 12345 for $99.99")
        assert "order" in result
        assert "12345" in result
        assert "99" in result

    def test_normalize_punctuation_stripped(self):
        result = CRPProcessor._normalize("Hello, world! How are you?")
        assert "," not in result
        assert "!" not in result
        assert "hello" in result
        assert "world" in result


# ── Gap Tests: Boundary / Edge Cases ────────────────────────────────


class TestPipelineEdgeCases:
    """Additional edge cases for the full pipeline."""

    @pytest.mark.asyncio
    async def test_negative_complexity(self, processor):
        """Negative complexity should not crash."""
        result = await processor.process("Hello world.", complexity=-0.5)
        assert "Hello" in result.processed_text

    @pytest.mark.asyncio
    async def test_complexity_one(self, processor):
        """Complexity=1.0 should not crash."""
        text = "I'd be happy to help. Your order shipped."
        result = await processor.process(text, complexity=1.0)
        assert "shipped" in result.processed_text

    @pytest.mark.asyncio
    async def test_very_long_text(self, processor):
        """Very long text should be processed without crash."""
        text = ("I'd be happy to help. " * 100) + "Your refund is $50."
        result = await processor.process(text)
        assert "$50" in result.processed_text

    @pytest.mark.asyncio
    async def test_special_characters_in_input(self, processor):
        """Special characters should not crash the processor."""
        text = "Your refund of $49.99 (order #ABC-123) is processed."
        result = await processor.process(text)
        assert "$49.99" in result.processed_text
        assert "ABC-123" in result.processed_text

    @pytest.mark.asyncio
    async def test_only_fillers(self, processor):
        """Text that is entirely fillers should result in minimal output."""
        text = "I'd be happy to help you with that. Please don't hesitate to reach out."
        result = await processor.process(text)
        assert result.reduction_pct > 50

    @pytest.mark.asyncio
    async def test_custom_compression_applied(self):
        """Custom compression rules should be applied."""
        config = CRPConfig(
            custom_compressions=((r"\butilize\b", "use"),),
        )
        processor = CRPProcessor(config=config)
        text = "We utilize the latest technology."
        result = await processor.compress_response(text)
        assert "utilize" not in result
        assert "use" in result
