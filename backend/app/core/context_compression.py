"""
F-086: Context Compression Engine (Week 10 Day 12)

Compresses RAG context and conversation history for LLM calls,
respecting per-variant token budgets. Five compression strategies:

  - extractive:      Select most relevant sentences
  - abstractive:     Generate compressed summary
  - hybrid:          Extractive + abstractive combined
  - sliding_window:  Keep most recent N messages
  - priority_based:  Keep high-priority content only

Per-variant compression levels:
  - mini_parwa (L1): NONE   — no compression
  - parwa      (L2): LIGHT  — ~30% reduction target
  - parwa_high (L3): AGGRESSIVE — ~50% reduction target

BC-001: All public methods take company_id as the first parameter.
BC-008: Every public method is wrapped in try/except; never crashes.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from app.logger import get_logger

logger = get_logger("context_compression")


# ══════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════

_COMPRESSION_TTL_SECONDS: int = 300
_DEFAULT_SLIDING_WINDOW_SIZE: int = 5
_PRIORITY_WEIGHT_RECENT: float = 0.3
_PRIORITY_WEIGHT_SIGNAL: float = 0.4
_PRIORITY_WEIGHT_ENTITY: float = 0.3


# ══════════════════════════════════════════════════════════════════
# ENUMS
# ══════════════════════════════════════════════════════════════════


class CompressionStrategy(str, Enum):
    """Available compression algorithms."""
    EXTRACTIVE = "extractive"
    ABSTRACTIVE = "abstractive"
    HYBRID = "hybrid"
    SLIDING_WINDOW = "sliding_window"
    PRIORITY_BASED = "priority_based"


class CompressionLevel(str, Enum):
    """Per-variant compression aggressiveness."""
    NONE = "none"
    LIGHT = "light"
    AGGRESSIVE = "aggressive"


# Maps variant type to default compression level
_VARIANT_COMPRESSION_LEVELS: Dict[str, CompressionLevel] = {
    "mini_parwa": CompressionLevel.NONE,
    "parwa": CompressionLevel.LIGHT,
    "parwa_high": CompressionLevel.AGGRESSIVE,
}


# ══════════════════════════════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════════════════════════════


@dataclass
class CompressionInput:
    """Input data for a compression operation."""
    content: List[str] = field(default_factory=list)
    token_counts: List[int] = field(default_factory=list)
    priorities: List[float] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CompressionOutput:
    """Result of a compression operation."""
    compressed_content: List[str] = field(default_factory=list)
    original_token_count: int = 0
    compressed_token_count: int = 0
    compression_ratio: float = 1.0
    strategy_used: str = ""
    chunks_removed: int = 0
    chunks_retained: int = 0
    processing_time_ms: float = 0.0


@dataclass
class CompressionConfig:
    """Configuration for the ContextCompressor."""
    company_id: str = ""
    variant_type: str = "parwa"
    strategy: CompressionStrategy = CompressionStrategy.HYBRID
    level: CompressionLevel = CompressionLevel.LIGHT
    max_tokens: int = 2000
    preserve_recent_n: int = 3
    min_compression_ratio: float = 0.3
    priority_threshold: float = 0.3


# ══════════════════════════════════════════════════════════════════
# EXCEPTION
# ══════════════════════════════════════════════════════════════════


class ContextCompressionError(Exception):
    """Raised when context compression fails critically.

    Inherits from Exception for BC-008 graceful degradation.
    """

    def __init__(
        self,
        message: str = "Context compression failed",
        company_id: str = "",
    ) -> None:
        self.message = message
        self.company_id = company_id
        super().__init__(self.message)


# ══════════════════════════════════════════════════════════════════
# CONTEXT COMPRESSOR
# ══════════════════════════════════════════════════════════════════


class ContextCompressor:
    """F-086: Context Compression Engine.

    Compresses RAG context and conversation history to fit within
    LLM token budgets. Supports five strategies with per-variant
    compression levels.

    BC-001: company_id first parameter on public methods.
    BC-008: Never crash — graceful degradation.
    """

    def __init__(
        self, config: Optional[CompressionConfig] = None,
    ) -> None:
        self._config = config or CompressionConfig()
        self._stats: Dict[str, Dict[str, Any]] = {}

        logger.info(
            "context_compressor_initialized",
            variant_type=self._config.variant_type,
            strategy=self._config.strategy.value,
            level=self._config.level.value,
            company_id=self._config.company_id,
        )

    # ── Public API ─────────────────────────────────────────────

    async def compress(
        self,
        company_id: str,
        input_data: CompressionInput,
    ) -> CompressionOutput:
        """Compress context for a given company.

        Args:
            company_id: Tenant company ID (BC-001).
            input_data: Content chunks with token counts and
                priorities.

        Returns:
            CompressionOutput with compressed content and stats.
        """
        start_time = time.monotonic()

        try:
            # Validate inputs
            if not input_data.content:
                logger.info(
                    "compress_empty_input",
                    company_id=company_id,
                )
                return CompressionOutput(
                    compressed_content=[],
                    original_token_count=0,
                    compressed_token_count=0,
                    compression_ratio=1.0,
                    strategy_used=self._config.strategy.value,
                    chunks_removed=0,
                    chunks_retained=0,
                    processing_time_ms=0.0,
                )

            # Sync token counts if not provided
            token_counts = input_data.token_counts
            if not token_counts or len(token_counts) != len(
                input_data.content,
            ):
                token_counts = [
                    self._estimate_tokens(c)
                    for c in input_data.content
                ]

            # Sync priorities if not provided
            priorities = input_data.priorities
            if not priorities or len(priorities) != len(
                input_data.content,
            ):
                priorities = [0.5] * len(input_data.content)

            original_tokens = sum(token_counts)
            level = self._config.level

            # NONE level: no compression needed
            if level == CompressionLevel.NONE:
                elapsed_ms = (time.monotonic() - start_time) * 1000
                return CompressionOutput(
                    compressed_content=list(input_data.content),
                    original_token_count=original_tokens,
                    compressed_token_count=original_tokens,
                    compression_ratio=1.0,
                    strategy_used="none",
                    chunks_removed=0,
                    chunks_retained=len(input_data.content),
                    processing_time_ms=round(elapsed_ms, 2),
                )

            # Calculate target tokens based on compression level
            target_reduction = self._get_reduction_target(level)
            target_tokens = int(original_tokens * target_reduction)
            target_tokens = max(
                target_tokens,
                int(
                    original_tokens
                    * self._config.min_compression_ratio
                ),
            )

            # Select strategy
            strategy = self._config.strategy
            if strategy == CompressionStrategy.SLIDING_WINDOW:
                output = self._apply_sliding_window(
                    input_data, target_tokens,
                )
            elif strategy == CompressionStrategy.PRIORITY_BASED:
                output = self._apply_priority_based(
                    input_data, target_tokens,
                )
            elif strategy == CompressionStrategy.EXTRACTIVE:
                output = self._apply_extractive(
                    input_data, target_tokens,
                )
            elif strategy == CompressionStrategy.ABSTRACTIVE:
                output = self._apply_abstractive(
                    input_data, target_tokens,
                )
            else:
                output = self._apply_hybrid(
                    input_data, target_tokens,
                )

            # Recalculate compression ratio
            compressed_tokens = sum(
                self._estimate_tokens(c)
                for c in output.compressed_content
            )
            if original_tokens > 0:
                output.compression_ratio = round(
                    compressed_tokens / original_tokens, 4,
                )
            output.original_token_count = original_tokens
            output.compressed_token_count = compressed_tokens
            output.processing_time_ms = round(
                (time.monotonic() - start_time) * 1000, 2,
            )

            # Update stats
            self._update_stats(
                company_id, output,
            )

            logger.info(
                "compress_completed",
                company_id=company_id,
                strategy=output.strategy_used,
                original_tokens=original_tokens,
                compressed_tokens=compressed_tokens,
                ratio=output.compression_ratio,
                chunks_removed=output.chunks_removed,
                duration_ms=output.processing_time_ms,
            )

            return output

        except Exception as exc:
            # BC-008: Graceful degradation — return original
            logger.warning(
                "compress_failed_fallback",
                error=str(exc),
                company_id=company_id,
            )
            elapsed_ms = (time.monotonic() - start_time) * 1000
            original_tokens = sum(
                self._estimate_tokens(c)
                for c in input_data.content
            )
            return CompressionOutput(
                compressed_content=list(input_data.content),
                original_token_count=original_tokens,
                compressed_token_count=original_tokens,
                compression_ratio=1.0,
                strategy_used="fallback",
                chunks_removed=0,
                chunks_retained=len(input_data.content),
                processing_time_ms=round(elapsed_ms, 2),
            )

    # ── Compression Strategies ─────────────────────────────────

    def _apply_extractive(
        self,
        input_data: CompressionInput,
        target_tokens: int,
    ) -> CompressionOutput:
        """Select top-priority chunks until target reached.

        Sorts chunks by priority (descending) and keeps the
        highest-priority ones that fit within the token budget.
        Recent messages are always preserved per config.
        """
        content = input_data.content
        priorities = input_data.priorities or [0.5] * len(content)

        n = len(content)
        preserve_n = min(self._config.preserve_recent_n, n)

        # Always preserve the most recent N chunks
        recent_indices = set(range(n - preserve_n, n))
        candidate_indices = [i for i in range(n - preserve_n)]
        candidate_priorities = [(priorities[i], i) for i in candidate_indices]

        # Sort by priority descending
        candidate_priorities.sort(key=lambda x: x[0], reverse=True)

        selected_indices = set(recent_indices)
        running_tokens = sum(
            self._estimate_tokens(content[i])
            for i in recent_indices
        )

        for priority, idx in candidate_priorities:
            if running_tokens >= target_tokens:
                break
            chunk_tokens = self._estimate_tokens(content[idx])
            running_tokens += chunk_tokens
            selected_indices.add(idx)

        # Preserve original order
        ordered = sorted(selected_indices)
        result_content = [content[i] for i in ordered]

        return CompressionOutput(
            compressed_content=result_content,
            strategy_used="extractive",
            chunks_removed=n - len(result_content),
            chunks_retained=len(result_content),
        )

    def _apply_sliding_window(
        self,
        input_data: CompressionInput,
        target_tokens: int,
    ) -> CompressionOutput:
        """Keep most recent chunks within budget.

        Iterates from the end of the content list backwards,
        keeping chunks until the token budget is filled.
        """
        content = input_data.content
        n = len(content)

        selected: List[str] = []
        running_tokens = 0

        for i in range(n - 1, -1, -1):
            chunk_tokens = self._estimate_tokens(content[i])
            if running_tokens + chunk_tokens > target_tokens:
                break
            selected.append(content[i])
            running_tokens += chunk_tokens

        # Reverse to restore chronological order
        selected.reverse()

        return CompressionOutput(
            compressed_content=selected,
            strategy_used="sliding_window",
            chunks_removed=n - len(selected),
            chunks_retained=len(selected),
        )

    def _apply_priority_based(
        self,
        input_data: CompressionInput,
        target_tokens: int,
    ) -> CompressionOutput:
        """Sort by priority, keep high-priority content.

        Chunks below the priority threshold are dropped first.
        Remaining chunks are kept in original order if they
        fit within the token budget.
        """
        content = input_data.content
        priorities = input_data.priorities or [0.5] * len(content)

        threshold = self._config.priority_threshold
        n = len(content)

        # Pair index + priority, filter by threshold
        indexed = [(i, priorities[i]) for i in range(n)]
        high_priority = [
            (i, p) for i, p in indexed if p >= threshold
        ]
        low_priority = [
            (i, p) for i, p in indexed if p < threshold
        ]

        # Sort high priority by priority descending
        high_priority.sort(key=lambda x: x[1], reverse=True)

        selected_indices: List[int] = []
        running_tokens = 0

        for idx, _pri in high_priority:
            chunk_tokens = self._estimate_tokens(content[idx])
            if running_tokens + chunk_tokens > target_tokens:
                break
            selected_indices.append(idx)
            running_tokens += chunk_tokens

        # Fill remaining budget with low-priority chunks
        remaining = target_tokens - running_tokens
        low_priority.sort(key=lambda x: x[1], reverse=True)
        for idx, _pri in low_priority:
            chunk_tokens = self._estimate_tokens(content[idx])
            if chunk_tokens > remaining:
                break
            selected_indices.append(idx)
            remaining -= chunk_tokens
            running_tokens += chunk_tokens

        # Preserve order
        selected_indices.sort()
        result_content = [content[i] for i in selected_indices]

        return CompressionOutput(
            compressed_content=result_content,
            strategy_used="priority_based",
            chunks_removed=n - len(result_content),
            chunks_retained=len(result_content),
        )

    def _apply_abstractive(
        self,
        input_data: CompressionInput,
        target_tokens: int,
    ) -> CompressionOutput:
        """Summarize low-priority chunks, keep high-priority as-is.

        High-priority chunks (>= threshold) are kept verbatim.
        Low-priority chunks are condensed into a single summary
        chunk using a rule-based approach.
        """
        content = input_data.content
        priorities = input_data.priorities or [0.5] * len(content)
        threshold = self._config.priority_threshold

        high_priority_chunks: List[str] = []
        low_priority_chunks: List[str] = []

        for i, chunk in enumerate(content):
            pri = priorities[i] if i < len(priorities) else 0.5
            if pri >= threshold:
                high_priority_chunks.append(chunk)
            else:
                low_priority_chunks.append(chunk)

        # Rule-based condensation of low-priority chunks
        if low_priority_chunks:
            summary = self._condense_chunks(low_priority_chunks)
        else:
            summary = ""

        result_content = list(high_priority_chunks)
        if summary:
            result_content.append(f"[Earlier context: {summary}]")

        # Trim if still over budget
        result_tokens = sum(
            self._estimate_tokens(c) for c in result_content
        )
        if result_tokens > target_tokens:
            result_content = self._trim_to_budget(
                result_content, target_tokens,
            )

        return CompressionOutput(
            compressed_content=result_content,
            strategy_used="abstractive",
            chunks_removed=len(content) - len(result_content),
            chunks_retained=len(result_content),
        )

    def _apply_hybrid(
        self,
        input_data: CompressionInput,
        target_tokens: int,
    ) -> CompressionOutput:
        """Extractive for high-priority + abstractive for low-priority.

        High-priority chunks are selected by extractive method.
        Low-priority chunks are condensed into a summary.
        """
        content = input_data.content
        priorities = input_data.priorities or [0.5] * len(content)
        threshold = self._config.priority_threshold

        # Split into high and low priority
        high_indices: List[int] = []
        low_chunks: List[str] = []
        for i in range(len(content)):
            pri = priorities[i] if i < len(priorities) else 0.5
            if pri >= threshold:
                high_indices.append(i)
            else:
                low_chunks.append(content[i])

        # Sort high-priority by priority descending
        high_with_pri = [
            (i, priorities[i]) for i in high_indices
        ]
        high_with_pri.sort(key=lambda x: x[1], reverse=True)

        # Budget allocation: 70% for high-priority, 30% for summary
        high_budget = int(target_tokens * 0.7)
        summary_budget = target_tokens - high_budget

        # Select high-priority chunks within budget
        selected_high: List[Tuple[int, float]] = []
        running_tokens = 0
        for idx, pri in high_with_pri:
            chunk_tokens = self._estimate_tokens(content[idx])
            if running_tokens + chunk_tokens > high_budget:
                break
            selected_high.append((idx, pri))
            running_tokens += chunk_tokens

        # Restore original order for high-priority
        selected_high.sort(key=lambda x: x[0])
        high_content = [content[idx] for idx, _ in selected_high]

        # Condense low-priority chunks
        summary_text = ""
        if low_chunks and summary_budget > 20:
            condensed = self._condense_chunks(low_chunks)
            condensed_tokens = self._estimate_tokens(condensed)
            if condensed_tokens <= summary_budget:
                summary_text = condensed
            else:
                # Truncate summary to fit
                max_chars = summary_budget * 4
                summary_text = condensed[:max_chars] + "..."

        result_content = list(high_content)
        if summary_text:
            result_content.append(
                f"[Prior context summary: {summary_text}]",
            )

        return CompressionOutput(
            compressed_content=result_content,
            strategy_used="hybrid",
            chunks_removed=len(content) - len(result_content),
            chunks_retained=len(result_content),
        )

    # ── Helpers ────────────────────────────────────────────────

    def _estimate_tokens(self, text: str) -> int:
        """Simple token estimation: approximately 4 chars per token."""
        if not text:
            return 0
        return max(1, len(text) // 4)

    def _get_reduction_target(
        self, level: CompressionLevel,
    ) -> float:
        """Get the target ratio (compressed/original) for a level.

        LIGHT: ~70% (30% reduction)
        AGGRESSIVE: ~50% (50% reduction)
        """
        if level == CompressionLevel.LIGHT:
            return 0.7
        if level == CompressionLevel.AGGRESSIVE:
            return 0.5
        return 1.0  # NONE

    def _condense_chunks(self, chunks: List[str]) -> str:
        """Rule-based condensation of multiple chunks into one.

        Takes first sentence from each chunk, limited to 200 chars.
        """
        if not chunks:
            return ""

        sentences: List[str] = []
        for chunk in chunks:
            # Take first sentence (up to first period)
            first_sentence = chunk.split(".")[0].strip()
            if len(first_sentence) > 200:
                first_sentence = first_sentence[:197] + "..."
            if first_sentence:
                sentences.append(first_sentence)

        if not sentences:
            return ""

        if len(sentences) <= 3:
            return " ".join(sentences)

        return (
            "; ".join(sentences[:3])
            + f" (and {len(sentences) - 3} more items)"
        )

    def _trim_to_budget(
        self, chunks: List[str], target_tokens: int,
    ) -> List[str]:
        """Trim chunk list to fit within token budget.

        Keeps chunks from the end (most recent) and drops from
        the front.
        """
        running = 0
        result: List[str] = []
        for chunk in reversed(chunks):
            tokens = self._estimate_tokens(chunk)
            if running + tokens > target_tokens:
                break
            result.append(chunk)
            running += tokens
        result.reverse()
        return result

    def _update_stats(
        self, company_id: str, output: CompressionOutput,
    ) -> None:
        """Update cumulative compression statistics."""
        if company_id not in self._stats:
            self._stats[company_id] = {
                "total_compressions": 0,
                "total_original_tokens": 0,
                "total_compressed_tokens": 0,
                "total_chunks_removed": 0,
                "avg_compression_ratio": 0.0,
            }
        stats = self._stats[company_id]
        stats["total_compressions"] += 1
        stats["total_original_tokens"] += (
            output.original_token_count
        )
        stats["total_compressed_tokens"] += (
            output.compressed_token_count
        )
        stats["total_chunks_removed"] += output.chunks_removed
        n = stats["total_compressions"]
        stats["avg_compression_ratio"] = round(
            (
                stats["avg_compression_ratio"] * (n - 1)
                + output.compression_ratio
            ) / n,
            4,
        )

    # ── Query Methods ──────────────────────────────────────────

    def get_compression_stats(
        self, company_id: str = "",
    ) -> Dict[str, Any]:
        """Return cumulative compression statistics."""
        try:
            return dict(
                self._stats.get(company_id, {
                    "total_compressions": 0,
                    "total_original_tokens": 0,
                    "total_compressed_tokens": 0,
                    "total_chunks_removed": 0,
                    "avg_compression_ratio": 0.0,
                }),
            )
        except Exception as exc:
            logger.warning(
                "get_compression_stats_failed",
                error=str(exc),
                company_id=company_id,
            )
            return {
                "total_compressions": 0,
                "error": str(exc),
            }

    @staticmethod
    def get_level_for_variant(
        variant_type: str,
    ) -> CompressionLevel:
        """Get the default compression level for a variant.

        mini_parwa -> NONE
        parwa      -> LIGHT
        parwa_high -> AGGRESSIVE
        """
        return _VARIANT_COMPRESSION_LEVELS.get(
            variant_type, CompressionLevel.LIGHT,
        )

    def get_config(self) -> CompressionConfig:
        """Return the current compressor configuration."""
        return self._config

    def reset(self) -> None:
        """Reset all internal state. For testing."""
        try:
            self._stats.clear()
            logger.info("context_compressor_reset")
        except Exception as exc:
            logger.warning(
                "compressor_reset_failed",
                error=str(exc),
            )
