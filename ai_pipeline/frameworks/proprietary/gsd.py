"""GSD (Global State Decompression) — State compression technique.

GSD is NOT a node — it's woven into the pipeline as a compression layer.
As a technique, it provides state-aware compression that reduces state-passing
token cost from ~12,000 tokens to ~180 tokens (~98% reduction).

How it works as a technique:
  - Compresses the full state into a compact representation
  - Keeps critical fields intact, summarizes verbose fields
  - Other techniques can use compressed state for cheaper processing
  - Decompresses on demand when full state is needed

What hallucination it catches:
  "State bloat" — when the state grows so large that the LLM loses
  focus on what matters. GSD forces focus on critical fields.

Activation:
  - Activates on ALL complexity levels (state compression is always useful)
  - Runs automatically before every node in the real pipeline
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.frameworks.base import BaseTechnique, TechniqueCategory, TechniqueResult

logger = logging.getLogger("parwa.frameworks.gsd")


class GSDTechnique(BaseTechnique):
    """Global State Decompression technique.

    Compresses ticket state for efficient passing between nodes.
    Reduces state from ~12,000 tokens to ~180 tokens by keeping
    critical fields intact and summarizing verbose ones.
    """

    _min_complexity = "simple"  # Always useful

    @property
    def name(self) -> str:
        return "gsd"

    @property
    def category(self) -> TechniqueCategory:
        return TechniqueCategory.PROPRIETARY

    @property
    def applicable_nodes(self) -> list[str]:
        return [
            "REASONING_ENGINE",
            "ACTION_PLANNER",
            "QUALITY_SCORER",
            "RESPONSE_FORMATTER",
            "CONTEXT_MANAGER",
        ]

    @property
    def token_cost_estimate(self) -> int:
        return 10  # Very cheap — just state manipulation, no LLM call

    async def think(
        self,
        prompt: str,
        state: dict[str, Any],
        *,
        ticket_id: str = "",
        variant: str = "parwa",
    ) -> TechniqueResult:
        """Execute GSD compression on the state.

        Returns a TechniqueResult with the compressed state summary
        as the output, and compression metadata.
        """
        from parwa.gsd import compress_state, get_compression_ratio

        compressed = compress_state(state)
        ratio = get_compression_ratio(state)

        original_size = len(str(state))
        compressed_size = len(str(compressed))

        # Build a summary of what was compressed
        summary_parts = []
        if compressed.get("_gsd_compressed"):
            original_keys = compressed.get("_gsd_original_keys", [])
            summary_parts.append(f"Compressed {len(original_keys)} fields")
            summary_parts.append(f"Size: {original_size}→{compressed_size} chars")
            summary_parts.append(f"Ratio: {ratio:.1%}")

        output = ". ".join(summary_parts) if summary_parts else "State compression complete"

        return TechniqueResult(
            output=output,
            chain=[f"GSD: {original_size}→{compressed_size} chars ({ratio:.1%})"],
            confidence=0.99,  # Compression is deterministic
            frameworks_used=["gsd"],
            metadata={
                "original_size": original_size,
                "compressed_size": compressed_size,
                "compression_ratio": ratio,
                "fields_compressed": len(compressed.get("_gsd_original_keys", [])),
            },
            token_estimate=self.token_cost_estimate,
        )
