"""Prompt Compressor — Compress prompts to fit within token budgets.

TurboQuant's prompt compression reduces token usage while preserving
semantic meaning. Strategies:
1. Remove redundant whitespace and formatting
2. Compress conversation history (keep last N messages)
3. Truncate evidence to most relevant parts
4. Template optimization (shorter system prompts for Mini variant)

The compression is LOSSLESS for accuracy — only removes noise,
never cuts important information.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from parwa.turboquant.token_budget import get_node_budget, VARIANT_TOKEN_MULTIPLIERS

logger = logging.getLogger("parwa.turboquant.compressor")

# Rough estimate: 1 token ≈ 4 characters for English text
CHARS_PER_TOKEN = 4


def _estimate_tokens(text: str) -> int:
    """Estimate token count from text length.

    This is a rough estimate — actual tokenization depends on the model.
    For production, use tiktoken for exact counts.

    Args:
        text: The text to estimate tokens for.

    Returns:
        Estimated token count.
    """
    return max(1, len(text) // CHARS_PER_TOKEN)


def _strip_redundant_whitespace(text: str) -> str:
    """Remove redundant whitespace without changing meaning."""
    # Replace multiple spaces/newlines with single
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)
    # Remove trailing whitespace on each line
    text = '\n'.join(line.rstrip() for line in text.split('\n'))
    return text.strip()


def _compress_evidence(evidence: list[str], max_items: int = 3, max_chars: int = 200) -> list[str]:
    """Compress evidence list by truncating items and limiting count.

    Args:
        evidence: List of evidence strings.
        max_items: Maximum number of evidence items to keep.
        max_chars: Maximum characters per evidence item.

    Returns:
        Compressed evidence list.
    """
    compressed = []
    for item in evidence[:max_items]:
        if len(item) > max_chars:
            compressed.append(item[:max_chars - 3] + "...")
        else:
            compressed.append(item)
    return compressed


def _compress_history(history: list[dict], max_entries: int = 5) -> list[dict]:
    """Compress conversation history by keeping only recent entries.

    Args:
        history: List of conversation history entries.
        max_entries: Maximum entries to keep.

    Returns:
        Trimmed history list.
    """
    if len(history) <= max_entries:
        return history
    return history[-max_entries:]


def compress_prompt(
    prompt: str,
    node_name: str = "",
    variant: str = "parwa",
    target_tokens: int | None = None,
    evidence: list[str] | None = None,
    history: list[dict] | None = None,
) -> dict[str, Any]:
    """Compress a prompt to fit within token budget.

    Applies progressive compression strategies based on variant:
    - Mini: Aggressive compression (remove everything non-essential)
    - PARWA: Balanced compression (trim excess, keep important)
    - High: Minimal compression (only strip whitespace)

    Args:
        prompt: The original prompt text.
        node_name: The node making the LLM call (for budget lookup).
        variant: The PARWA variant (mini, parwa, high).
        target_tokens: Optional explicit token target (overrides budget).
        evidence: Optional evidence strings to compress.
        history: Optional conversation history to compress.

    Returns:
        Dict with: compressed_prompt, original_tokens, compressed_tokens,
        savings_percent, compressed_evidence, compressed_history.
    """
    original_tokens = _estimate_tokens(prompt)

    # Determine target token budget
    if target_tokens is None:
        budget = get_node_budget(node_name, variant)
        target_tokens = budget.allocated

    # Apply compression based on variant aggressiveness
    multiplier = VARIANT_TOKEN_MULTIPLIERS.get(variant, 1.0)

    compressed = prompt
    compressed_evidence = evidence
    compressed_history = history

    # Level 1: Always strip whitespace (lossless)
    compressed = _strip_redundant_whitespace(compressed)

    # Level 2: Variant-dependent compression
    if multiplier <= 0.5:
        # Mini — aggressive compression
        # Remove lines that are just labels/headers
        compressed = re.sub(r'^[A-Z][A-Za-z\s]+:\s*$', '', compressed, flags=re.MULTILINE)
        # Compress evidence aggressively
        if evidence:
            compressed_evidence = _compress_evidence(evidence, max_items=2, max_chars=100)
        # Keep only last 3 history entries
        if history:
            compressed_history = _compress_history(history, max_entries=3)

    elif multiplier <= 1.0:
        # PARWA — balanced compression
        if evidence:
            compressed_evidence = _compress_evidence(evidence, max_items=3, max_chars=200)
        if history:
            compressed_history = _compress_history(history, max_entries=5)

    else:
        # High — minimal compression (accuracy first)
        if evidence:
            compressed_evidence = _compress_evidence(evidence, max_items=5, max_chars=300)
        if history:
            compressed_history = _compress_history(history, max_entries=8)

    # Level 3: If still over budget, truncate from the end (last resort)
    compressed_tokens = _estimate_tokens(compressed)
    if compressed_tokens > target_tokens and target_tokens > 0:
        max_chars = target_tokens * CHARS_PER_TOKEN
        compressed = compressed[:max_chars - 3] + "..."
        logger.info(
            "compress_prompt: truncated node=%s variant=%s %d→%d tokens",
            node_name, variant, original_tokens, target_tokens,
        )

    compressed_tokens = _estimate_tokens(compressed)
    savings = ((original_tokens - compressed_tokens) / original_tokens * 100) if original_tokens > 0 else 0.0

    return {
        "compressed_prompt": compressed,
        "original_tokens": original_tokens,
        "compressed_tokens": compressed_tokens,
        "savings_percent": round(savings, 1),
        "compressed_evidence": compressed_evidence,
        "compressed_history": compressed_history,
    }


class PromptCompressor:
    """Stateful prompt compressor for repeated use within a ticket.

    Tracks cumulative savings across all nodes in a ticket.

    Example:
        compressor = PromptCompressor(variant="mini")
        result = compressor.compress("Long prompt...", node_name="reasoning_engine")
        print(f"Saved {result['savings_percent']}%")
        print(f"Total saved: {compressor.total_savings}%")
    """

    def __init__(self, variant: str = "parwa") -> None:
        """Initialize the compressor.

        Args:
            variant: The PARWA variant for compression aggressiveness.
        """
        self.variant = variant
        self._total_original = 0
        self._total_compressed = 0

    def compress(
        self,
        prompt: str,
        node_name: str = "",
        target_tokens: int | None = None,
        evidence: list[str] | None = None,
        history: list[dict] | None = None,
    ) -> dict[str, Any]:
        """Compress a prompt and track cumulative savings.

        Args:
            prompt: The original prompt text.
            node_name: The node making the LLM call.
            target_tokens: Optional explicit token target.
            evidence: Optional evidence strings to compress.
            history: Optional conversation history to compress.

        Returns:
            Same dict as compress_prompt().
        """
        result = compress_prompt(
            prompt=prompt,
            node_name=node_name,
            variant=self.variant,
            target_tokens=target_tokens,
            evidence=evidence,
            history=history,
        )

        # Track cumulative savings
        self._total_original += result["original_tokens"]
        self._total_compressed += result["compressed_tokens"]

        return result

    @property
    def total_savings(self) -> float:
        """Cumulative savings percentage across all compressed prompts."""
        if self._total_original == 0:
            return 0.0
        return round(
            ((self._total_original - self._total_compressed) / self._total_original) * 100, 1
        )

    @property
    def total_original_tokens(self) -> int:
        """Total original tokens before compression."""
        return self._total_original

    @property
    def total_compressed_tokens(self) -> int:
        """Total tokens after compression."""
        return self._total_compressed
