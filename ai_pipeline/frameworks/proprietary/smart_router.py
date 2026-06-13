"""Smart Router — Model selection technique based on node + complexity + variant.

Smart Router is woven into the LLM call path. As a technique, it provides
intelligence about WHICH model to use for a given reasoning task.

How it works as a technique:
  - Analyzes the node name, complexity, and variant
  - Selects the optimal LLM model (gpt-4o-mini, gpt-4o, o1-preview)
  - Mini variant always uses cheap model (cost optimization)
  - Critical complexity uses the best model (accuracy priority)
  - Node-specific overrides take priority (e.g., INGEST always cheap)

What hallucination it catches:
  "Overkill reasoning" — using a powerful model for a simple task wastes
  tokens and can over-complicate. Smart Router ensures the right model
  for the right task.

Activation:
  - Activates on MEDIUM+ complexity (simple tasks don't need routing)
  - Always activates for variant-aware model selection
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.frameworks.base import BaseTechnique, TechniqueCategory, TechniqueResult

logger = logging.getLogger("parwa.frameworks.smart_router")


class SmartRouterTechnique(BaseTechnique):
    """Smart Router model selection technique.

    Selects the optimal LLM model based on node name, complexity,
    and variant. Ensures cost-efficiency for simple tasks and
    accuracy for critical ones.
    """

    _min_complexity = "medium"  # Simple tasks don't need routing

    @property
    def name(self) -> str:
        return "smart_router"

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
            "ACTION_PLANNER",
            "PREDICTION_ENGINE",
            "QUALITY_SCORER",
            "RESPONSE_FORMATTER",
            "KB_RETRIEVER",
            "CONTEXT_MANAGER",
        ]

    @property
    def token_cost_estimate(self) -> int:
        return 5  # Negligible — just model selection logic, no LLM call

    async def think(
        self,
        prompt: str,
        state: dict[str, Any],
        *,
        ticket_id: str = "",
        variant: str = "parwa",
    ) -> TechniqueResult:
        """Execute Smart Router model selection.

        Returns a TechniqueResult with the selected model and rationale.
        """
        from parwa.utils.llm import smart_route_model

        node_name = state.get("_current_node", "UNKNOWN")
        complexity = state.get("complexity", "simple")

        selected_model = smart_route_model(
            node_name, complexity=complexity, variant=variant
        )

        # Build rationale
        rationale = f"Node={node_name}, Complexity={complexity}, Variant={variant}"
        if variant == "mini":
            rationale += " → gpt-4o-mini (mini cost optimization)"
        elif selected_model == "o1-preview":
            rationale += " → o1-preview (critical reasoning)"
        elif selected_model == "gpt-4o":
            rationale += " → gpt-4o (balanced capability)"
        else:
            rationale += f" → {selected_model} (cost efficiency)"

        return TechniqueResult(
            output=f"Selected model: {selected_model}",
            chain=[f"SmartRouter: {rationale}"],
            confidence=0.95,
            frameworks_used=["smart_router"],
            metadata={
                "selected_model": selected_model,
                "node_name": node_name,
                "complexity": complexity,
                "variant": variant,
            },
            token_estimate=self.token_cost_estimate,
        )
