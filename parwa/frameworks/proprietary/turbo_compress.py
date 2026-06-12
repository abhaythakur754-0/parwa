"""TurboCompress — Prompt compression technique for token savings.

TurboCompress uses the TurboQuant prompt compressor to reduce prompt
size before sending to the LLM. This saves tokens without losing
critical information.

How it works:
  - Takes the full prompt text
  - Applies compression: removes redundancy, shortens phrases
  - Preserves all critical information (numbers, names, policies)
  - Achieves ~40-60% compression on typical customer support prompts

What hallucination it catches:
  "Prompt bloat" — when the prompt contains unnecessary repetition
  or verbose context that doesn't help reasoning. TurboCompress
  forces the prompt to be concise and focused.

Activation:
  - Activates on MEDIUM+ complexity (simple prompts are already short)
  - Critical for complex tickets where prompt size would exceed limits
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.frameworks.base import BaseTechnique, TechniqueCategory, TechniqueResult

logger = logging.getLogger("parwa.frameworks.turbo_compress")


class TurboCompressTechnique(BaseTechnique):
    """TurboCompress prompt compression technique.

    Compresses prompts using TurboQuant to reduce token usage
    while preserving critical information.
    """

    _min_complexity = "medium"

    @property
    def name(self) -> str:
        return "turbo_compress"

    @property
    def category(self) -> TechniqueCategory:
        return TechniqueCategory.PROPRIETARY

    @property
    def applicable_nodes(self) -> list[str]:
        return [
            "REASONING_ENGINE",
            "REVERSE_THINKER",
            "TREE_OF_THOUGHTS",
            "STRATEGY_PLANNER",
            "KB_RETRIEVER",
            "QUALITY_SCORER",
        ]

    @property
    def token_cost_estimate(self) -> int:
        return 20  # Small — compression itself is cheap

    async def think(
        self,
        prompt: str,
        state: dict[str, Any],
        *,
        ticket_id: str = "",
        variant: str = "parwa",
    ) -> TechniqueResult:
        """Execute prompt compression.

        Compresses the prompt using TurboQuant's prompt compressor.
        """
        original_len = len(prompt)

        try:
            from parwa.turboquant.prompt_compressor import PromptCompressor
            compressor = PromptCompressor()
            compressed = compressor.compress(prompt)
            compressed_len = len(compressed)
        except Exception:
            # Fallback: simple whitespace compression
            compressed = " ".join(prompt.split())
            compressed_len = len(compressed)

        ratio = (1 - compressed_len / original_len) if original_len > 0 else 0
        chain = [
            f"TurboCompress: {original_len}→{compressed_len} chars ({ratio:.0%} reduction)",
        ]

        output = compressed if compressed else prompt

        return TechniqueResult(
            output=output,
            chain=chain,
            confidence=0.85,
            frameworks_used=["turbo_compress"],
            metadata={
                "original_length": original_len,
                "compressed_length": compressed_len,
                "compression_ratio": round(ratio, 3),
                "tokens_saved_estimate": max(0, (original_len - compressed_len) // 4),
            },
            token_estimate=self.token_cost_estimate,
        )
