"""ThoT (Thread of Thought) — Maintains a continuous reasoning thread across nodes.

How it works:
  1. Accumulates reasoning outputs from each node into a "thought thread"
  2. Each node can read the thread to understand what previous nodes concluded
  3. The thread is compressed as it grows (keeps key conclusions, drops details)
  4. Prevents each node from starting from scratch — builds on prior reasoning

What hallucination it catches:
  "Context loss between nodes" — without ThoT, each node only sees state
  fields, not the reasoning that produced them. ThoT carries the reasoning
  context forward, preventing nodes from contradicting earlier conclusions.

Activation:
  - Medium complexity and above (simple tickets don't need cross-node threading)
  - Used in FEEDBACK_LOOP to maintain learning across tickets
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.frameworks.base import BaseTechnique, TechniqueCategory, TechniqueResult

logger = logging.getLogger("parwa.frameworks.thot")


class ThreadOfThoughtTechnique(BaseTechnique):
    """Thread of Thought: Maintains continuous reasoning across nodes.

    Accumulates reasoning outputs into a thread that carries context
    forward. Each node reads the thread to understand prior conclusions,
    preventing context loss and contradiction.
    """

    _min_complexity = "medium"

    @property
    def name(self) -> str:
        return "thread_of_thought"

    @property
    def category(self) -> TechniqueCategory:
        return TechniqueCategory.MEMORY

    @property
    def applicable_nodes(self) -> list[str]:
        return [
            "FEEDBACK_LOOP",
            "REASONING_ENGINE",
            "QUALITY_SCORER",
            "RESPONSE_FORMATTER",
        ]

    @property
    def token_cost_estimate(self) -> int:
        return 150  # Moderate — thread management

    async def think(
        self,
        prompt: str,
        state: dict[str, Any],
        *,
        ticket_id: str = "",
        variant: str = "parwa",
    ) -> TechniqueResult:
        """Execute Thread of Thought: build and maintain reasoning thread.

        Reads prior reasoning conclusions from state and weaves them
        into a continuous thread that the next node can reference.
        """
        reasoning_chain = state.get("reasoning_chain", [])
        reasoning_conclusion = state.get("reasoning_conclusion", "")
        reverse_validation = state.get("reverse_validation", {})
        quality_score = state.get("quality_score", 0.0)
        feedback_signal = state.get("feedback_signal", {})

        # Build the thought thread from state
        thread = self._build_thread(
            reasoning_chain, reasoning_conclusion,
            reverse_validation, quality_score, feedback_signal,
        )

        # Compress thread if too long
        if len(thread) > 10:
            thread = self._compress_thread(thread)

        chain = [f"ThoT: Maintaining reasoning thread ({len(thread)} entries)"]
        for entry in thread[-3:]:  # Show last 3 entries
            chain.append(f"  → {entry}")

        output = f"ThoT: Reasoning thread has {len(thread)} entries. Latest: {thread[-1] if thread else 'empty'}"

        confidence = 0.80
        if reasoning_conclusion:
            confidence = 0.88
        if reverse_validation.get("passed", False):
            confidence = 0.92

        return TechniqueResult(
            output=output,
            chain=chain,
            confidence=confidence,
            frameworks_used=["thread_of_thought"],
            metadata={
                "thread_length": len(thread),
                "thread_entries": thread,
                "has_conclusion": bool(reasoning_conclusion),
                "validated": reverse_validation.get("passed", False),
            },
            token_estimate=self.token_cost_estimate,
        )

    def _build_thread(
        self,
        reasoning_chain: list[str],
        reasoning_conclusion: str,
        reverse_validation: dict[str, Any],
        quality_score: float,
        feedback_signal: dict[str, Any],
    ) -> list[str]:
        """Build a thought thread from current state."""
        thread = []

        # Add reasoning steps
        if isinstance(reasoning_chain, list):
            for step in reasoning_chain[:5]:  # Keep first 5 steps
                if isinstance(step, str) and len(step) > 5:
                    thread.append(step)

        # Add conclusion
        if reasoning_conclusion:
            thread.append(f"Conclusion: {reasoning_conclusion}")

        # Add validation status
        if isinstance(reverse_validation, dict):
            passed = reverse_validation.get("passed", False)
            thread.append(f"Reverse validation: {'PASSED' if passed else 'FAILED'}")

        # Add quality assessment
        if quality_score > 0:
            thread.append(f"Quality score: {quality_score:.1f}")

        # Add feedback signal
        if isinstance(feedback_signal, dict) and feedback_signal:
            resolved = feedback_signal.get("resolved", False)
            thread.append(f"Feedback: {'resolved' if resolved else 'unresolved'}")

        return thread if thread else ["No prior reasoning thread"]

    def _compress_thread(self, thread: list[str]) -> list[str]:
        """Compress a long thread by keeping key entries."""
        # Keep first entry (context), last 3 entries (recent), and any PASSED/FAILED entries
        compressed = []
        if thread:
            compressed.append(thread[0])  # Context
        for entry in thread[1:]:
            if "PASSED" in entry or "FAILED" in entry or "Conclusion:" in entry:
                compressed.append(entry)
        # Always keep the last 3 entries
        for entry in thread[-3:]:
            if entry not in compressed:
                compressed.append(entry)

        return compressed
