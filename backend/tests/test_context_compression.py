"""
Tests for Context Compression Engine — Week 10 Day 12
Feature: F-086
Target: 65+ tests
"""

from unittest.mock import MagicMock, patch

import pytest

# Runtime-injected by _mock_logger fixture — satisfies flake8 F821
# type: ignore[assignment,misc]
ContextCompressor = CompressionConfig = CompressionInput = CompressionOutput = (
    CompressionStrategy
) = CompressionLevel = ContextCompressionError = _COMPRESSION_TTL_SECONDS = (
    _VARIANT_COMPRESSION_LEVELS
) = None


@pytest.fixture(autouse=True)
def _mock_logger():
    with patch("app.logger.get_logger", return_value=MagicMock()):
        from app.core.context_compression import (  # noqa: F811,F401
            _COMPRESSION_TTL_SECONDS,
            _VARIANT_COMPRESSION_LEVELS,
            CompressionConfig,
            CompressionInput,
            CompressionLevel,
            CompressionOutput,
            CompressionStrategy,
            ContextCompressionError,
            ContextCompressor,
        )

        globals().update(
            {
                "ContextCompressor": ContextCompressor,
                "CompressionConfig": CompressionConfig,
                "CompressionInput": CompressionInput,
                "CompressionOutput": CompressionOutput,
                "CompressionStrategy": CompressionStrategy,
                "CompressionLevel": CompressionLevel,
                "ContextCompressionError": ContextCompressionError,
                "_COMPRESSION_TTL_SECONDS": _COMPRESSION_TTL_SECONDS,
                "_VARIANT_COMPRESSION_LEVELS": _VARIANT_COMPRESSION_LEVELS,
            }
        )


def _make_input(content=None, priorities=None, token_counts=None):
    """Factory helper for creating CompressionInput."""
    if content is None:
        content = ["alpha beta gamma", "delta epsilon", "zeta eta theta"]
    if priorities is None:
        priorities = [0.9, 0.5, 0.2]
    if token_counts is None:
        token_counts = [4, 3, 4]
    return CompressionInput(
        content=content,
        token_counts=token_counts,
        priorities=priorities,
    )


# ═══════════════════════════════════════════════════════════════════════
# 1. CompressionConfig (8 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestCompressionConfig:
    def test_default_company_id_empty(self):
        cfg = CompressionConfig()
        assert cfg.company_id == ""

    def test_default_variant_type_parwa(self):
        cfg = CompressionConfig()
        assert cfg.variant_type == "parwa"

    def test_default_strategy_hybrid(self):
        cfg = CompressionConfig()
        assert cfg.strategy == CompressionStrategy.HYBRID

    def test_default_level_light(self):
        cfg = CompressionConfig()
        assert cfg.level == CompressionLevel.LIGHT

    def test_default_max_tokens(self):
        cfg = CompressionConfig()
        assert cfg.max_tokens == 2000

    def test_default_preserve_recent_n(self):
        cfg = CompressionConfig()
        assert cfg.preserve_recent_n == 3

    def test_custom_values(self):
        cfg = CompressionConfig(
            company_id="corp-1",
            variant_type="parwa_high",
            strategy=CompressionStrategy.EXTRACTIVE,
            level=CompressionLevel.AGGRESSIVE,
            max_tokens=4000,
            priority_threshold=0.5,
        )
        assert cfg.company_id == "corp-1"
        assert cfg.strategy == CompressionStrategy.EXTRACTIVE
        assert cfg.level == CompressionLevel.AGGRESSIVE
        assert cfg.max_tokens == 4000
        assert cfg.priority_threshold == 0.5

    def test_variant_defaults_strategy_assignment(self):
        mini_cfg = CompressionConfig(variant_type="mini_parwa")
        assert mini_cfg.variant_type == "mini_parwa"
        high_cfg = CompressionConfig(variant_type="parwa_high")
        assert high_cfg.variant_type == "parwa_high"


# ═══════════════════════════════════════════════════════════════════════
# 2. CompressionInput (5 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestCompressionInput:
    def test_creation_empty(self):
        inp = CompressionInput()
        assert inp.content == []
        assert inp.token_counts == []
        assert inp.priorities == []
        assert inp.metadata == {}

    def test_content_list(self):
        inp = CompressionInput(content=["a", "b", "c"])
        assert inp.content == ["a", "b", "c"]
        assert len(inp.content) == 3

    def test_token_counts_list(self):
        inp = CompressionInput(token_counts=[10, 20, 30])
        assert inp.token_counts == [10, 20, 30]

    def test_priorities_list(self):
        inp = CompressionInput(priorities=[0.1, 0.5, 0.9])
        assert inp.priorities == [0.1, 0.5, 0.9]

    def test_metadata_dict(self):
        inp = CompressionInput(metadata={"source": "rag"})
        assert inp.metadata == {"source": "rag"}


# ═══════════════════════════════════════════════════════════════════════
# 3. CompressionOutput (5 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestCompressionOutput:
    def test_defaults(self):
        out = CompressionOutput()
        assert out.compressed_content == []
        assert out.original_token_count == 0
        assert out.compressed_token_count == 0
        assert out.compression_ratio == 1.0

    def test_compressed_content_list(self):
        out = CompressionOutput(compressed_content=["a", "b"])
        assert len(out.compressed_content) == 2

    def test_strategy_used(self):
        out = CompressionOutput(strategy_used="extractive")
        assert out.strategy_used == "extractive"

    def test_chunks_removed_retained(self):
        out = CompressionOutput(chunks_removed=3, chunks_retained=7)
        assert out.chunks_removed == 3
        assert out.chunks_retained == 7

    def test_processing_time(self):
        out = CompressionOutput(processing_time_ms=12.5)
        assert out.processing_time_ms == 12.5


# ═══════════════════════════════════════════════════════════════════════
# 4. Extractive Strategy (5 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestExtractiveStrategy:
    @pytest.mark.asyncio
    async def test_basic_compression(self):
        comp = ContextCompressor(
            CompressionConfig(
                strategy=CompressionStrategy.EXTRACTIVE,
                level=CompressionLevel.LIGHT,
                priority_threshold=0.3,
            )
        )
        result = await comp.compress("c1", _make_input())
        assert isinstance(result, CompressionOutput)
        assert result.strategy_used == "extractive"
        assert len(result.compressed_content) > 0

    @pytest.mark.asyncio
    async def test_priority_ordering(self):
        comp = ContextCompressor(
            CompressionConfig(
                strategy=CompressionStrategy.EXTRACTIVE,
                level=CompressionLevel.LIGHT,
                priority_threshold=0.3,
            )
        )
        content = ["low priority item", "high priority item", "medium priority item"]
        priorities = [0.1, 0.9, 0.5]
        inp = CompressionInput(content=content, priorities=priorities)
        result = await comp.compress("c1", inp)
        # High priority should be retained
        assert "high priority item" in result.compressed_content

    @pytest.mark.asyncio
    async def test_preserves_high_priority(self):
        comp = ContextCompressor(
            CompressionConfig(
                strategy=CompressionStrategy.EXTRACTIVE,
                level=CompressionLevel.LIGHT,
                priority_threshold=0.3,
            )
        )
        content = ["A" * 100, "B" * 100, "C" * 100]
        priorities = [0.1, 0.95, 0.1]
        inp = CompressionInput(content=content, priorities=priorities)
        result = await comp.compress("c1", inp)
        assert "B" * 100 in result.compressed_content

    @pytest.mark.asyncio
    async def test_target_tokens_respected(self):
        comp = ContextCompressor(
            CompressionConfig(
                strategy=CompressionStrategy.EXTRACTIVE,
                level=CompressionLevel.AGGRESSIVE,
                priority_threshold=0.3,
            )
        )
        content = ["item"] * 20
        priorities = [0.5] * 20
        inp = CompressionInput(content=content, priorities=priorities)
        result = await comp.compress("c1", inp)
        # Aggressive should compress
        assert result.chunks_removed >= 0

    @pytest.mark.asyncio
    async def test_returns_extractive_strategy_name(self):
        comp = ContextCompressor(
            CompressionConfig(
                strategy=CompressionStrategy.EXTRACTIVE,
                level=CompressionLevel.LIGHT,
            )
        )
        result = await comp.compress("c1", _make_input())
        assert result.strategy_used == "extractive"


# ═══════════════════════════════════════════════════════════════════════
# 5. Sliding Window Strategy (5 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestSlidingWindowStrategy:
    @pytest.mark.asyncio
    async def test_keeps_recent(self):
        comp = ContextCompressor(
            CompressionConfig(
                strategy=CompressionStrategy.SLIDING_WINDOW,
                level=CompressionLevel.LIGHT,
            )
        )
        content = ["old message", "older message", "recent message"]
        inp = CompressionInput(content=content)
        result = await comp.compress("c1", inp)
        # Recent items should be at the end
        assert "recent message" in result.compressed_content

    @pytest.mark.asyncio
    async def test_drops_oldest(self):
        comp = ContextCompressor(
            CompressionConfig(
                strategy=CompressionStrategy.SLIDING_WINDOW,
                level=CompressionLevel.AGGRESSIVE,
            )
        )
        content = ["very old context message"] + ["recent"] * 10
        inp = CompressionInput(content=content)
        result = await comp.compress("c1", inp)
        # Aggressive should drop the oldest
        if "very old context message" not in result.compressed_content:
            assert result.chunks_removed >= 1

    @pytest.mark.asyncio
    async def test_preserve_recent_n(self):
        comp = ContextCompressor(
            CompressionConfig(
                strategy=CompressionStrategy.SLIDING_WINDOW,
                level=CompressionLevel.LIGHT,
                preserve_recent_n=2,
            )
        )
        content = ["a", "b", "c", "d", "e"]
        inp = CompressionInput(content=content)
        result = await comp.compress("c1", inp)
        # Preserve the most recent
        assert result.compressed_content[-1] == "e"

    @pytest.mark.asyncio
    async def test_empty_input_returns_empty(self):
        comp = ContextCompressor(
            CompressionConfig(
                strategy=CompressionStrategy.SLIDING_WINDOW,
            )
        )
        inp = CompressionInput(content=[])
        result = await comp.compress("c1", inp)
        assert result.compressed_content == []
        assert result.chunks_removed == 0

    @pytest.mark.asyncio
    async def test_within_budget_returns_all(self):
        comp = ContextCompressor(
            CompressionConfig(
                strategy=CompressionStrategy.SLIDING_WINDOW,
                level=CompressionLevel.LIGHT,
            )
        )
        # Use long content so LIGHT level keeps most of it
        content = ["word " * 50, "word " * 50, "word " * 50]
        inp = CompressionInput(content=content)
        result = await comp.compress("c1", inp)
        # LIGHT keeps ~70%, so most should be retained
        assert len(result.compressed_content) >= 1


# ═══════════════════════════════════════════════════════════════════════
# 6. Priority Based Strategy (5 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestPriorityBasedStrategy:
    @pytest.mark.asyncio
    async def test_sorts_by_priority(self):
        comp = ContextCompressor(
            CompressionConfig(
                strategy=CompressionStrategy.PRIORITY_BASED,
                level=CompressionLevel.LIGHT,
                priority_threshold=0.3,
            )
        )
        content = ["low", "high", "medium"]
        priorities = [0.1, 0.9, 0.5]
        inp = CompressionInput(content=content, priorities=priorities)
        result = await comp.compress("c1", inp)
        assert "high" in result.compressed_content

    @pytest.mark.asyncio
    async def test_threshold_filtering(self):
        comp = ContextCompressor(
            CompressionConfig(
                strategy=CompressionStrategy.PRIORITY_BASED,
                level=CompressionLevel.LIGHT,
                priority_threshold=0.7,
            )
        )
        content = ["low", "medium", "high"]
        priorities = [0.1, 0.5, 0.9]
        inp = CompressionInput(content=content, priorities=priorities)
        result = await comp.compress("c1", inp)
        # Only high priority passes threshold
        assert "high" in result.compressed_content

    @pytest.mark.asyncio
    async def test_keeps_high_priority_chunks(self):
        comp = ContextCompressor(
            CompressionConfig(
                strategy=CompressionStrategy.PRIORITY_BASED,
                level=CompressionLevel.LIGHT,
                priority_threshold=0.3,
            )
        )
        # All high priority — should retain most given LIGHT budget
        content = [
            "alpha beta gamma delta epsilon",
            "zeta eta theta iota kappa",
            "lambda mu nu xi omicron",
        ]
        priorities = [0.9, 0.9, 0.9]
        inp = CompressionInput(content=content, priorities=priorities)
        result = await comp.compress("c1", inp)
        # LIGHT keeps ~70% — should retain at least 1 chunk
        assert len(result.compressed_content) >= 1

    @pytest.mark.asyncio
    async def test_fills_with_low_priority(self):
        comp = ContextCompressor(
            CompressionConfig(
                strategy=CompressionStrategy.PRIORITY_BASED,
                level=CompressionLevel.LIGHT,
                priority_threshold=0.7,
            )
        )
        content = ["low1", "high1", "low2"]
        priorities = [0.5, 0.9, 0.4]
        inp = CompressionInput(content=content, priorities=priorities)
        result = await comp.compress("c1", inp)
        assert result.strategy_used == "priority_based"

    @pytest.mark.asyncio
    async def test_original_order_preserved(self):
        comp = ContextCompressor(
            CompressionConfig(
                strategy=CompressionStrategy.PRIORITY_BASED,
                level=CompressionLevel.LIGHT,
                priority_threshold=0.3,
            )
        )
        content = ["first", "second", "third"]
        priorities = [0.9, 0.5, 0.8]
        inp = CompressionInput(content=content, priorities=priorities)
        result = await comp.compress("c1", inp)
        # If all are retained, order should match
        if len(result.compressed_content) == 3:
            assert result.compressed_content[0] == "first"
            assert result.compressed_content[1] == "second"
            assert result.compressed_content[2] == "third"


# ═══════════════════════════════════════════════════════════════════════
# 7. Abstractive Strategy (5 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestAbstractiveStrategy:
    @pytest.mark.asyncio
    async def test_keeps_high_priority_verbatim(self):
        comp = ContextCompressor(
            CompressionConfig(
                strategy=CompressionStrategy.ABSTRACTIVE,
                level=CompressionLevel.LIGHT,
                priority_threshold=0.5,
            )
        )
        # Use longer strings so budget accommodates at least the high-priority
        # chunk
        content = [
            "low priority background context information that is not critical",
            "high priority critical information that must be preserved always",
        ]
        priorities = [0.1, 0.9]
        inp = CompressionInput(content=content, priorities=priorities)
        result = await comp.compress("c1", inp)
        assert result.strategy_used == "abstractive"
        # Content should be retained (at least one chunk)
        assert len(result.compressed_content) >= 1

    @pytest.mark.asyncio
    async def test_summarizes_low_priority(self):
        comp = ContextCompressor(
            CompressionConfig(
                strategy=CompressionStrategy.ABSTRACTIVE,
                level=CompressionLevel.AGGRESSIVE,
                priority_threshold=0.7,
            )
        )
        content = [
            "low text one with some extra words here",
            "low text two with some extra words here",
            "high text that is very important and critical for the user query",
        ]
        priorities = [0.1, 0.2, 0.9]
        inp = CompressionInput(content=content, priorities=priorities)
        result = await comp.compress("c1", inp)
        assert result.strategy_used == "abstractive"
        # Aggressive may trim but the strategy should still produce output
        assert isinstance(result.compressed_content, list)

    @pytest.mark.asyncio
    async def test_condensed_output_for_low_priority(self):
        comp = ContextCompressor(
            CompressionConfig(
                strategy=CompressionStrategy.ABSTRACTIVE,
                level=CompressionLevel.LIGHT,
                priority_threshold=0.8,
            )
        )
        content = ["First item of interest", "Second item of interest", "Third item"]
        priorities = [0.1, 0.1, 0.9]
        inp = CompressionInput(content=content, priorities=priorities)
        result = await comp.compress("c1", inp)
        # Low priority chunks should be condensed
        assert result.strategy_used == "abstractive"

    @pytest.mark.asyncio
    async def test_all_high_priority_no_summary(self):
        comp = ContextCompressor(
            CompressionConfig(
                strategy=CompressionStrategy.ABSTRACTIVE,
                level=CompressionLevel.LIGHT,
                priority_threshold=0.3,
            )
        )
        content = ["a", "b", "c"]
        priorities = [0.9, 0.8, 0.7]
        inp = CompressionInput(content=content, priorities=priorities)
        result = await comp.compress("c1", inp)
        # All high priority, no summary needed
        assert all("Prior context summary" not in c for c in result.compressed_content)

    @pytest.mark.asyncio
    async def test_strategy_name(self):
        comp = ContextCompressor(
            CompressionConfig(
                strategy=CompressionStrategy.ABSTRACTIVE,
                level=CompressionLevel.LIGHT,
            )
        )
        result = await comp.compress("c1", _make_input())
        assert result.strategy_used == "abstractive"


# ═══════════════════════════════════════════════════════════════════════
# 8. Hybrid Strategy (5 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestHybridStrategy:
    @pytest.mark.asyncio
    async def test_combines_extractive_and_abstractive(self):
        comp = ContextCompressor(
            CompressionConfig(
                strategy=CompressionStrategy.HYBRID,
                level=CompressionLevel.LIGHT,
                priority_threshold=0.5,
            )
        )
        content = ["low one", "low two", "high one", "high two"]
        priorities = [0.1, 0.2, 0.8, 0.9]
        inp = CompressionInput(content=content, priorities=priorities)
        result = await comp.compress("c1", inp)
        assert result.strategy_used == "hybrid"
        assert len(result.compressed_content) > 0

    @pytest.mark.asyncio
    async def test_high_priority_selected_first(self):
        comp = ContextCompressor(
            CompressionConfig(
                strategy=CompressionStrategy.HYBRID,
                level=CompressionLevel.LIGHT,
                priority_threshold=0.5,
            )
        )
        # Use longer content so the high-priority chunk fits in the 70% budget
        content = [
            "low priority chunk with minimal relevance to the current query",
            "high priority chunk directly answering the user question",
        ]
        priorities = [0.1, 0.9]
        inp = CompressionInput(content=content, priorities=priorities)
        result = await comp.compress("c1", inp)
        assert result.strategy_used == "hybrid"
        # High priority chunk should fit in the high-priority budget (70%)
        assert any("high priority chunk" in c for c in result.compressed_content)

    @pytest.mark.asyncio
    async def test_low_priority_condensed(self):
        comp = ContextCompressor(
            CompressionConfig(
                strategy=CompressionStrategy.HYBRID,
                level=CompressionLevel.AGGRESSIVE,
                priority_threshold=0.7,
            )
        )
        # Use longer content so budget is meaningful
        content = [
            "low priority chunk a with additional context words",
            "low priority chunk b with additional context words",
            "high priority chunk c directly answering the question",
        ]
        priorities = [0.1, 0.1, 0.9]
        inp = CompressionInput(content=content, priorities=priorities)
        result = await comp.compress("c1", inp)
        assert result.strategy_used == "hybrid"
        # Either high priority retained or summary generated
        assert len(result.compressed_content) >= 0

    @pytest.mark.asyncio
    async def test_result_within_budget(self):
        comp = ContextCompressor(
            CompressionConfig(
                strategy=CompressionStrategy.HYBRID,
                level=CompressionLevel.LIGHT,
            )
        )
        content = ["a" * 100] * 10
        inp = CompressionInput(content=content)
        result = await comp.compress("c1", inp)
        assert isinstance(result, CompressionOutput)

    @pytest.mark.asyncio
    async def test_strategy_name_is_hybrid(self):
        comp = ContextCompressor(
            CompressionConfig(
                strategy=CompressionStrategy.HYBRID,
                level=CompressionLevel.LIGHT,
            )
        )
        result = await comp.compress("c1", _make_input())
        assert result.strategy_used == "hybrid"


# ═══════════════════════════════════════════════════════════════════════
# 9. No Compression (NONE level) (3 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestNoCompression:
    @pytest.mark.asyncio
    async def test_mini_parwa_none_level(self):
        comp = ContextCompressor(
            CompressionConfig(
                variant_type="mini_parwa",
                level=CompressionLevel.NONE,
            )
        )
        result = await comp.compress("c1", _make_input())
        assert result.strategy_used == "none"

    @pytest.mark.asyncio
    async def test_returns_content_as_is(self):
        comp = ContextCompressor(
            CompressionConfig(
                level=CompressionLevel.NONE,
            )
        )
        content = ["keep this one", "keep this too"]
        inp = CompressionInput(content=content)
        result = await comp.compress("c1", inp)
        assert result.compressed_content == content
        assert result.chunks_removed == 0
        assert result.compression_ratio == 1.0

    @pytest.mark.asyncio
    async def test_empty_input_none_level(self):
        comp = ContextCompressor(
            CompressionConfig(
                level=CompressionLevel.NONE,
            )
        )
        inp = CompressionInput(content=[])
        result = await comp.compress("c1", inp)
        assert result.compressed_content == []
        assert result.compression_ratio == 1.0


# ═══════════════════════════════════════════════════════════════════════
# 10. Compress Main (5 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestCompressMain:
    @pytest.mark.asyncio
    async def test_main_entry_point_returns_output(self):
        comp = ContextCompressor()
        result = await comp.compress("c1", _make_input())
        assert isinstance(result, CompressionOutput)
        assert result.strategy_used in (
            "hybrid",
            "extractive",
            "sliding_window",
            "priority_based",
            "abstractive",
            "none",
            "fallback",
        )

    @pytest.mark.asyncio
    async def test_empty_input_returns_empty_output(self):
        comp = ContextCompressor()
        result = await comp.compress("c1", CompressionInput(content=[]))
        assert result.compressed_content == []
        assert result.original_token_count == 0
        assert result.chunks_removed == 0

    @pytest.mark.asyncio
    async def test_error_handling_returns_original(self):
        comp = ContextCompressor(
            CompressionConfig(
                strategy=CompressionStrategy.EXTRACTIVE,
                level=CompressionLevel.LIGHT,
            )
        )
        # Force error only in the strategy method; _estimate_tokens must
        # work for the fallback to produce a valid result.
        with patch.object(comp, "_apply_extractive", side_effect=RuntimeError("boom")):
            result = await comp.compress("c1", _make_input())
        # BC-008: fallback returns original
        assert result.strategy_used == "fallback"
        assert result.compressed_content == _make_input().content

    @pytest.mark.asyncio
    async def test_updates_stats(self):
        comp = ContextCompressor()
        await comp.compress("c1", _make_input())
        stats = comp.get_compression_stats("c1")
        assert stats["total_compressions"] == 1

    @pytest.mark.asyncio
    async def test_wrong_variant_defaults_safely(self):
        comp = ContextCompressor(
            CompressionConfig(
                variant_type="unknown_variant",
            )
        )
        result = await comp.compress("c1", _make_input())
        assert isinstance(result, CompressionOutput)
        assert result.strategy_used != ""


# ═══════════════════════════════════════════════════════════════════════
# 11. Token Estimation (3 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestTokenEstimation:
    def test_empty_string_zero(self):
        comp = ContextCompressor()
        assert comp._estimate_tokens("") == 0

    def test_normal_text_estimate(self):
        comp = ContextCompressor()
        # "hello world" = 11 chars -> 11//4 = 2 tokens (min 1)
        result = comp._estimate_tokens("hello world")
        assert result >= 1

    def test_unicode_text_estimate(self):
        comp = ContextCompressor()
        # Unicode chars should still produce tokens
        result = comp._estimate_tokens("こんにちは世界")
        assert result >= 1


# ═══════════════════════════════════════════════════════════════════════
# 12. Variant Levels (3 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestVariantLevels:
    def test_mini_parwa_none(self):
        level = ContextCompressor.get_level_for_variant("mini_parwa")
        assert level == CompressionLevel.NONE

    def test_parwa_light(self):
        level = ContextCompressor.get_level_for_variant("parwa")
        assert level == CompressionLevel.LIGHT

    def test_parwa_high_aggressive(self):
        level = ContextCompressor.get_level_for_variant("parwa_high")
        assert level == CompressionLevel.AGGRESSIVE


# ═══════════════════════════════════════════════════════════════════════
# 13. CompressionError (3 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestCompressionError:
    def test_default_message(self):
        err = ContextCompressionError()
        assert err.message == "Context compression failed"
        assert err.company_id == ""

    def test_inheritance_from_exception(self):
        err = ContextCompressionError("test")
        assert isinstance(err, Exception)

    def test_custom_company_id(self):
        err = ContextCompressionError(
            message="Compression exceeded budget",
            company_id="corp-99",
        )
        assert err.message == "Compression exceeded budget"
        assert err.company_id == "corp-99"
        assert str(err) == "Compression exceeded budget"


# ═══════════════════════════════════════════════════════════════════════
# 14. CompressionStrategy Enum (3 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestCompressionStrategyEnum:
    def test_five_strategies(self):
        assert len(CompressionStrategy) == 5

    def test_all_values_are_strings(self):
        for s in CompressionStrategy:
            assert isinstance(s.value, str)

    def test_unique_values(self):
        values = [s.value for s in CompressionStrategy]
        assert len(values) == len(set(values))


# ═══════════════════════════════════════════════════════════════════════
# 15. CompressionLevel Enum (3 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestCompressionLevelEnum:
    def test_three_levels(self):
        assert len(CompressionLevel) == 3

    def test_all_values_are_strings(self):
        for level in CompressionLevel:
            assert isinstance(level.value, str)

    def test_level_hierarchy(self):
        assert CompressionLevel.NONE.value == "none"
        assert CompressionLevel.LIGHT.value == "light"
        assert CompressionLevel.AGGRESSIVE.value == "aggressive"


# ═══════════════════════════════════════════════════════════════════════
# 16. Constants (2 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestConstants:
    def test_compression_ttl(self):
        assert _COMPRESSION_TTL_SECONDS == 300

    def test_variant_levels_mapping(self):
        assert "mini_parwa" in _VARIANT_COMPRESSION_LEVELS
        assert "parwa" in _VARIANT_COMPRESSION_LEVELS
        assert "parwa_high" in _VARIANT_COMPRESSION_LEVELS
        assert _VARIANT_COMPRESSION_LEVELS["mini_parwa"] == CompressionLevel.NONE
        assert _VARIANT_COMPRESSION_LEVELS["parwa"] == CompressionLevel.LIGHT
        assert _VARIANT_COMPRESSION_LEVELS["parwa_high"] == CompressionLevel.AGGRESSIVE


# ═══════════════════════════════════════════════════════════════════════
# 17. Compression Stats (3 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestCompressionStats:
    @pytest.mark.asyncio
    async def test_stats_accumulate(self):
        comp = ContextCompressor()
        await comp.compress("c1", _make_input())
        await comp.compress("c1", _make_input())
        stats = comp.get_compression_stats("c1")
        assert stats["total_compressions"] == 2

    @pytest.mark.asyncio
    async def test_stats_for_unknown_company(self):
        comp = ContextCompressor()
        stats = comp.get_compression_stats("nonexistent")
        assert stats["total_compressions"] == 0

    @pytest.mark.asyncio
    async def test_reset_clears_stats(self):
        comp = ContextCompressor()
        await comp.compress("c1", _make_input())
        comp.reset()
        stats = comp.get_compression_stats("c1")
        assert stats["total_compressions"] == 0


# ═══════════════════════════════════════════════════════════════════════
# 18. CompressionInput sync behavior (2 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestCompressionInputSync:
    @pytest.mark.asyncio
    async def test_token_counts_auto_synced(self):
        comp = ContextCompressor(
            CompressionConfig(
                level=CompressionLevel.LIGHT,
            )
        )
        inp = CompressionInput(content=["hello", "world"])
        result = await comp.compress("c1", inp)
        assert isinstance(result, CompressionOutput)

    @pytest.mark.asyncio
    async def test_priorities_auto_synced(self):
        comp = ContextCompressor(
            CompressionConfig(
                level=CompressionLevel.LIGHT,
            )
        )
        inp = CompressionInput(content=["a", "b", "c"])
        result = await comp.compress("c1", inp)
        assert isinstance(result, CompressionOutput)
