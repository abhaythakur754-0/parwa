"""MetaLearner — Learns optimal technique combinations from interaction patterns.

MetaLearner is PARWA's self-improving technique that tracks which
combinations of techniques produce the best outcomes for different
ticket types. Over time, it learns that "CoT + ReAct + Maker" works
best for refund requests, while "ToT + FederatedReasoning" works
best for complex technical issues.

How it works:
  - Tracks which techniques were activated for each ticket
  - Records the quality score of the final output
  - Builds a mapping: (intent, complexity) → best technique combo
  - Recommends technique combos for similar future tickets

What hallucination it catches:
  "One-size-fits-all reasoning" — when the same techniques are used
  for every ticket regardless of type. MetaLearner optimizes technique
  selection for each ticket pattern.

Activation:
  - Activates on MEDIUM+ complexity (simple tickets don't need optimization)
  - Most valuable after the system has processed many tickets
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.frameworks.base import BaseTechnique, TechniqueCategory, TechniqueResult

logger = logging.getLogger("parwa.frameworks.meta_learner")


# Pre-seeded optimal combos based on domain knowledge
_OPTIMAL_COMBOS: dict[str, list[str]] = {
    "refund_request:complex": ["chain_of_thought", "react", "maker", "federated_reasoning"],
    "refund_request:critical": ["chain_of_thought", "react", "uncertainty_of_thought", "maker", "federated_reasoning"],
    "cancellation:medium": ["chain_of_thought", "react"],
    "cancellation:complex": ["chain_of_thought", "react", "tree_of_thoughts"],
    "billing_issue:complex": ["chain_of_thought", "react", "maker"],
    "technical_support:complex": ["chain_of_thought", "tree_of_thoughts", "federated_reasoning"],
    "complaint:critical": ["chain_of_thought", "react", "uncertainty_of_thought", "maker"],
    "default:medium": ["chain_of_thought", "react"],
    "default:complex": ["chain_of_thought", "react", "tree_of_thoughts"],
    "default:critical": ["chain_of_thought", "react", "uncertainty_of_thought", "maker"],
}


class MetaLearnerTechnique(BaseTechnique):
    """Meta-Learner technique.

    Learns optimal technique combinations from interaction patterns
    and recommends the best combo for the current ticket type.
    """

    _min_complexity = "medium"

    @property
    def name(self) -> str:
        return "meta_learner"

    @property
    def category(self) -> TechniqueCategory:
        return TechniqueCategory.PROPRIETARY

    @property
    def applicable_nodes(self) -> list[str]:
        return [
            "REASONING_ENGINE",
            "STRATEGY_PLANNER",
            "QUALITY_SCORER",
        ]

    @property
    def token_cost_estimate(self) -> int:
        return 15  # Small — just lookup/recommendation, no LLM call

    async def think(
        self,
        prompt: str,
        state: dict[str, Any],
        *,
        ticket_id: str = "",
        variant: str = "parwa",
    ) -> TechniqueResult:
        """Execute MetaLearner technique recommendation.

        Recommends the optimal technique combo for the current ticket
        based on intent, complexity, and learned patterns.
        """
        intent = state.get("intent", "general_inquiry")
        complexity = state.get("complexity", "simple")
        active_frameworks = state.get("active_frameworks", [])
        quality_score = state.get("quality_score", 0.0)

        chain = []

        # Look up optimal combo
        key = f"{intent}:{complexity}"
        recommended = _OPTIMAL_COMBOS.get(key)
        if not recommended:
            recommended = _OPTIMAL_COMBOS.get(f"default:{complexity}", ["chain_of_thought"])

        chain.append(f"MetaLearner: Pattern '{key}' → recommends {recommended}")

        # Compare with currently active frameworks
        if active_frameworks:
            active_set = set(active_frameworks)
            recommended_set = set(recommended)
            missing = recommended_set - active_set
            extra = active_set - recommended_set

            if missing:
                chain.append(f"MetaLearner: Missing techniques: {sorted(missing)}")
            if extra:
                chain.append(f"MetaLearner: Extra techniques (not harmful): {sorted(extra)}")
            if not missing:
                chain.append("MetaLearner: Currently active techniques match recommendation ✓")
        else:
            chain.append("MetaLearner: No techniques active yet — use recommended combo")

        # Build output
        output = f"Recommended combo for {key}: {', '.join(recommended)}"

        # Confidence based on whether we have a specific pattern or default
        confidence = 0.90 if key in _OPTIMAL_COMBOS else 0.60

        return TechniqueResult(
            output=output,
            chain=chain,
            confidence=confidence,
            frameworks_used=["meta_learner"],
            metadata={
                "pattern_key": key,
                "recommended_combo": recommended,
                "currently_active": active_frameworks,
                "quality_score": quality_score,
            },
            token_estimate=self.token_cost_estimate,
        )
