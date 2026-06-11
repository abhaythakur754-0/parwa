"""Token Tracker — Track actual token usage per node, per ticket, per variant.

Records every LLM call's token usage and provides aggregation
for cost analysis and budget optimization.

Thread-safe and async-safe for concurrent ticket processing.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("parwa.turboquant.tracker")


@dataclass
class TokenUsage:
    """Record of token usage for a single LLM call."""
    ticket_id: str
    node_name: str
    variant: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    model: str = "gpt-4o-mini"
    timestamp: float = 0.0
    latency_ms: float = 0.0

    def __post_init__(self) -> None:
        if self.timestamp == 0.0:
            self.timestamp = time.monotonic()
        if self.total_tokens == 0:
            self.total_tokens = self.prompt_tokens + self.completion_tokens

    def estimated_cost(self) -> float:
        """Estimate cost in USD based on model pricing.

        GPT-4o-mini pricing (as of 2025):
        - Input: $0.15 per 1M tokens
        - Output: $0.60 per 1M tokens
        """
        MODEL_PRICING = {
            "gpt-4o-mini": (0.15 / 1_000_000, 0.60 / 1_000_000),
            "gpt-4o": (2.50 / 1_000_000, 10.00 / 1_000_000),
            "gpt-3.5-turbo": (0.50 / 1_000_000, 1.50 / 1_000_000),
        }
        input_price, output_price = MODEL_PRICING.get(
            self.model, MODEL_PRICING["gpt-4o-mini"]
        )
        return (self.prompt_tokens * input_price) + (self.completion_tokens * output_price)


class TokenTracker:
    """Thread-safe tracker for LLM token usage across all tickets.

    Records every LLM call and provides aggregation for:
    - Per-node token usage
    - Per-variant token usage and cost
    - Per-ticket token usage
    - Overall system efficiency metrics
    """

    def __init__(self, max_records: int = 10000) -> None:
        """Initialize the token tracker.

        Args:
            max_records: Maximum number of records to keep (FIFO eviction).
        """
        self._records: list[TokenUsage] = []
        self._lock = threading.Lock()
        self._max_records = max_records

    def record(
        self,
        ticket_id: str,
        node_name: str,
        variant: str,
        prompt_tokens: int,
        completion_tokens: int,
        model: str = "gpt-4o-mini",
        latency_ms: float = 0.0,
    ) -> TokenUsage:
        """Record a token usage event.

        Args:
            ticket_id: The ticket being processed.
            node_name: The node that made the LLM call.
            variant: The PARWA variant.
            prompt_tokens: Number of input tokens.
            completion_tokens: Number of output tokens.
            model: The LLM model used.
            latency_ms: LLM call latency in milliseconds.

        Returns:
            The recorded TokenUsage object.
        """
        usage = TokenUsage(
            ticket_id=ticket_id,
            node_name=node_name,
            variant=variant,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            model=model,
            latency_ms=latency_ms,
        )

        with self._lock:
            self._records.append(usage)
            # FIFO eviction if over max
            if len(self._records) > self._max_records:
                self._records = self._records[-self._max_records:]

        logger.debug(
            "token_tracker: ticket=%s node=%s tokens=%d (p=%d c=%d) model=%s",
            ticket_id, node_name, usage.total_tokens,
            prompt_tokens, completion_tokens, model,
        )

        return usage

    def get_ticket_usage(self, ticket_id: str) -> list[TokenUsage]:
        """Get all token usage records for a specific ticket."""
        with self._lock:
            return [r for r in self._records if r.ticket_id == ticket_id]

    def get_node_usage(self, node_name: str) -> list[TokenUsage]:
        """Get all token usage records for a specific node."""
        with self._lock:
            return [r for r in self._records if r.node_name == node_name]

    def get_variant_usage(self, variant: str) -> list[TokenUsage]:
        """Get all token usage records for a specific variant."""
        with self._lock:
            return [r for r in self._records if r.variant == variant]

    def get_total_tokens(self, variant: str | None = None) -> int:
        """Get total tokens used, optionally filtered by variant."""
        with self._lock:
            records = self._records
            if variant:
                records = [r for r in records if r.variant == variant]
            return sum(r.total_tokens for r in records)

    def get_total_cost(self, variant: str | None = None) -> float:
        """Get total estimated cost in USD, optionally filtered by variant."""
        with self._lock:
            records = self._records
            if variant:
                records = [r for r in records if r.variant == variant]
            return sum(r.estimated_cost() for r in records)

    def get_node_summary(self) -> dict[str, dict[str, Any]]:
        """Get token usage summary per node.

        Returns:
            Dict mapping node_name → {total_tokens, avg_tokens, call_count, total_cost}.
        """
        with self._lock:
            summary: dict[str, dict[str, Any]] = {}
            for r in self._records:
                if r.node_name not in summary:
                    summary[r.node_name] = {
                        "total_tokens": 0,
                        "total_prompt": 0,
                        "total_completion": 0,
                        "call_count": 0,
                        "total_cost": 0.0,
                    }
                s = summary[r.node_name]
                s["total_tokens"] += r.total_tokens
                s["total_prompt"] += r.prompt_tokens
                s["total_completion"] += r.completion_tokens
                s["call_count"] += 1
                s["total_cost"] += r.estimated_cost()

            # Add averages
            for s in summary.values():
                if s["call_count"] > 0:
                    s["avg_tokens"] = s["total_tokens"] / s["call_count"]
                else:
                    s["avg_tokens"] = 0

            return summary

    def get_variant_summary(self) -> dict[str, dict[str, Any]]:
        """Get token usage summary per variant.

        Returns:
            Dict mapping variant → {total_tokens, total_cost, ticket_count, avg_per_ticket}.
        """
        with self._lock:
            summary: dict[str, dict[str, Any]] = {}
            for r in self._records:
                if r.variant not in summary:
                    summary[r.variant] = {
                        "total_tokens": 0,
                        "total_cost": 0.0,
                        "ticket_ids": set(),
                    }
                s = summary[r.variant]
                s["total_tokens"] += r.total_tokens
                s["total_cost"] += r.estimated_cost()
                s["ticket_ids"].add(r.ticket_id)

            # Convert sets to counts and add averages
            for s in summary.values():
                ticket_count = len(s["ticket_ids"])
                s["ticket_count"] = ticket_count
                s["avg_per_ticket"] = s["total_tokens"] / ticket_count if ticket_count > 0 else 0
                del s["ticket_ids"]  # Remove set, not serializable

            return summary

    def clear(self) -> None:
        """Clear all tracked records."""
        with self._lock:
            self._records.clear()

    @property
    def record_count(self) -> int:
        """Number of tracked records."""
        with self._lock:
            return len(self._records)


# ─── Global Singleton ──────────────────────────────────────────────────────────────

_tracker: TokenTracker | None = None


def get_token_tracker() -> TokenTracker:
    """Get or create the global token tracker singleton."""
    global _tracker
    if _tracker is None:
        _tracker = TokenTracker()
    return _tracker
