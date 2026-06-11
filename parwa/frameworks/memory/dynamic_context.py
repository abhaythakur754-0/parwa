"""Dynamic Context — Dynamically adjust context window based on complexity and budget.

How it works:
  1. Determines the available context window for the current LLM call
  2. Adjusts context size based on ticket complexity (simple=small, complex=large)
  3. Respects variant budget constraints (Mini gets smaller windows)
  4. Prioritizes which context to keep when window is limited

What hallucination it catches:
  "Context overflow" — when too much context is crammed into a small window,
  the LLM loses track and hallucinates. Dynamic Context ensures the right
  amount of context is provided, prioritizing the most relevant information.

Activation:
  - Simple complexity and above (always active — every call benefits)
  - Used in all nodes for smart context management
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.frameworks.base import BaseTechnique, TechniqueCategory, TechniqueResult

logger = logging.getLogger("parwa.frameworks.dynamic_context")

# Context window sizes by complexity and variant (in approximate tokens)
_CONTEXT_WINDOWS = {
    "mini": {"simple": 2000, "medium": 4000, "complex": 6000, "critical": 8000},
    "parwa": {"simple": 4000, "medium": 8000, "complex": 12000, "critical": 16000},
    "high": {"simple": 8000, "medium": 16000, "complex": 24000, "critical": 32000},
}


class DynamicContextTechnique(BaseTechnique):
    """Dynamic Context: Adjust context window based on complexity and variant budget.

    Determines the optimal context window size and prioritizes which
    context to keep when the window is limited. Prevents context
    overflow that leads to hallucination.
    """

    _min_complexity = "simple"

    @property
    def name(self) -> str:
        return "dynamic_context"

    @property
    def category(self) -> TechniqueCategory:
        return TechniqueCategory.MEMORY

    @property
    def applicable_nodes(self) -> list[str]:
        return [
            "REASONING_ENGINE",
            "CONTEXT_MANAGER",
            "RESPONSE_FORMATTER",
            "KB_RETRIEVER",
        ]

    @property
    def token_cost_estimate(self) -> int:
        return 50  # Very low — just context planning, no LLM call

    async def think(
        self,
        prompt: str,
        state: dict[str, Any],
        *,
        ticket_id: str = "",
        variant: str = "parwa",
    ) -> TechniqueResult:
        """Execute Dynamic Context: plan context window allocation.

        Determines the optimal context window size and which
        pieces of context to prioritize.
        """
        complexity = state.get("complexity", "simple")
        if not isinstance(complexity, str):
            complexity = "simple"

        # Get the context window size
        window = self._get_context_window(variant, complexity)

        # Calculate current context usage
        current_usage = self._estimate_context_usage(state)

        # Determine priority order for context
        priorities = self._prioritize_context(state, window, current_usage)

        chain = [
            f"DynamicContext: Window={window} tokens (variant={variant}, complexity={complexity})",
            f"DynamicContext: Current usage≈{current_usage} tokens",
            f"DynamicContext: Priority order: {', '.join(priorities[:5])}",
        ]

        # Determine if context needs trimming
        needs_trimming = current_usage > window
        if needs_trimming:
            chain.append(f"DynamicContext: TRIMMING needed ({current_usage} > {window})")
            output = f"DynamicContext: Context trimmed from {current_usage} to {window} tokens. Priority: {', '.join(priorities[:3])}"
            confidence = 0.70
        else:
            chain.append(f"DynamicContext: No trimming needed ({current_usage} <= {window})")
            output = f"DynamicContext: Context fits in window ({current_usage}/{window} tokens)"
            confidence = 0.90

        return TechniqueResult(
            output=output,
            chain=chain,
            confidence=confidence,
            frameworks_used=["dynamic_context"],
            metadata={
                "window_size": window,
                "current_usage": current_usage,
                "needs_trimming": needs_trimming,
                "priority_order": priorities,
                "complexity": complexity,
                "variant": variant,
            },
            token_estimate=self.token_cost_estimate,
        )

    def _get_context_window(self, variant: str, complexity: str) -> int:
        """Get the context window size for variant + complexity."""
        variant_key = variant if variant in _CONTEXT_WINDOWS else "parwa"
        windows = _CONTEXT_WINDOWS[variant_key]
        return windows.get(complexity, windows["simple"])

    def _estimate_context_usage(self, state: dict[str, Any]) -> int:
        """Estimate current context token usage from state."""
        total = 0
        for key, value in state.items():
            if isinstance(value, str):
                total += len(value) // 4  # Rough: 4 chars per token
            elif isinstance(value, list):
                for item in value:
                    total += len(str(item)) // 4
            elif isinstance(value, dict):
                total += len(str(value)) // 4
        return total

    def _prioritize_context(self, state: dict[str, Any], window: int, usage: int) -> list[str]:
        """Determine which context fields to keep when trimming.

        Priority order (highest first):
        1. raw_message (the customer's actual words)
        2. reasoning_conclusion (the main reasoning output)
        3. intent + sentiment (routing context)
        4. kb_results (evidence)
        5. integration_data (CRM facts)
        6. Everything else
        """
        priorities = [
            "raw_message",
            "reasoning_conclusion",
            "intent",
            "sentiment",
            "kb_results",
            "integration_data",
            "faq_match",
            "reasoning_chain",
            "context_history",
            "action_plans",
        ]

        # Add any remaining state keys
        for key in state:
            if key not in priorities and not key.startswith("_"):
                priorities.append(key)

        return priorities
