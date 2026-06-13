"""FederatedReasoning — Combines conclusions from multiple reasoning paths.

FederatedReasoning is PARWA's technique for combining the outputs of
multiple reasoning techniques (CoT, ReAct, ToT, etc.) into a single
unified conclusion. Instead of just taking the last technique's output,
it weighs all outputs by confidence and consistency.

How it works:
  - Collects outputs from all activated reasoning techniques
  - Weighs each output by its confidence score
  - Identifies consensus (when multiple techniques agree)
  - Flags disagreement (when techniques disagree — needs human review)
  - Produces a unified conclusion with combined confidence

What hallucination it catches:
  "Single-path hallucination" — when one reasoning technique produces
  a confident but wrong answer. FederatedReasoning cross-validates
  across multiple paths.

Activation:
  - Activates on COMPLEX+ complexity (simple tickets only use CoT)
  - Most valuable when multiple reasoning paths are explored
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.frameworks.base import BaseTechnique, TechniqueCategory, TechniqueResult

logger = logging.getLogger("parwa.frameworks.federated_reasoning")


class FederatedReasoningTechnique(BaseTechnique):
    """Federated Reasoning technique.

    Combines conclusions from multiple reasoning techniques into
    a single unified conclusion, weighted by confidence and consistency.
    """

    _min_complexity = "complex"

    @property
    def name(self) -> str:
        return "federated_reasoning"

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
        return 30  # Small — just combining existing results

    async def think(
        self,
        prompt: str,
        state: dict[str, Any],
        *,
        ticket_id: str = "",
        variant: str = "parwa",
    ) -> TechniqueResult:
        """Execute federated reasoning — combine multiple reasoning paths.

        Examines all reasoning outputs in the state and produces
        a unified conclusion.
        """
        # Collect all reasoning outputs
        reasoning_conclusion = state.get("reasoning_conclusion", "")
        reverse_validation = state.get("reverse_validation", {})
        reasoning_paths = state.get("reasoning_paths", [])
        strategy_plan = state.get("strategy_plan", [])
        active_frameworks = state.get("active_frameworks", [])

        chain = []
        sources = []

        # Source 1: Direct reasoning conclusion
        if reasoning_conclusion:
            sources.append({
                "source": "reasoning_engine",
                "conclusion": reasoning_conclusion,
                "confidence": 0.80,
            })
            chain.append(f"Federated: Reasoning engine says: {reasoning_conclusion[:100]}")

        # Source 2: Reverse thinking validation
        if reverse_validation:
            validation_status = reverse_validation.get("validation", "unknown")
            if validation_status == "PASSED":
                sources.append({
                    "source": "reverse_thinker",
                    "conclusion": "Reverse validation passed",
                    "confidence": 0.90,
                })
                chain.append("Federated: Reverse thinking validates the conclusion")
            elif validation_status == "FAILED":
                sources.append({
                    "source": "reverse_thinker",
                    "conclusion": "Reverse validation FAILED",
                    "confidence": 0.30,
                })
                chain.append("Federated: Reverse thinking REJECTS the conclusion")

        # Source 3: Tree of Thoughts — selected path
        if reasoning_paths:
            selected = None
            for path in reasoning_paths:
                if isinstance(path, dict) and path.get("selected"):
                    selected = path
                    break
            if selected:
                sources.append({
                    "source": "tree_of_thoughts",
                    "conclusion": selected.get("description", ""),
                    "confidence": selected.get("confidence", 0.50),
                })
                chain.append(f"Federated: ToT selected path (conf={selected.get('confidence', 0):.2f})")

        # Source 4: Strategy plan
        if strategy_plan:
            sources.append({
                "source": "strategy_planner",
                "conclusion": strategy_plan[0] if strategy_plan else "",
                "confidence": 0.75,
            })
            chain.append(f"Federated: Strategy plan has {len(strategy_plan)} steps")

        # Compute federated conclusion
        if not sources:
            output = "No reasoning sources available for federation"
            confidence = 0.0
        elif len(sources) == 1:
            output = sources[0]["conclusion"]
            confidence = sources[0]["confidence"]
        else:
            # Weighted average confidence
            total_weight = sum(s["confidence"] for s in sources)
            confidence = total_weight / len(sources) if sources else 0.0

            # Check consensus
            conclusions = [s["conclusion"].lower() for s in sources]
            # Simple consensus: do any conclusions contradict?
            has_failure = any("fail" in c or "reject" in c for c in conclusions)
            has_success = any("pass" in c or "eligible" in c or "confirm" in c for c in conclusions)

            if has_failure and has_success:
                # Disagreement — lower confidence, flag for review
                confidence *= 0.5
                output = f"DISAGREEMENT detected among {len(sources)} reasoning paths. Primary conclusion: {reasoning_conclusion}"
                chain.append("Federated: WARNING — reasoning paths disagree")
            else:
                # Consensus — boost confidence
                confidence = min(0.98, confidence + 0.10)
                output = reasoning_conclusion or sources[0]["conclusion"]
                chain.append(f"Federated: Consensus among {len(sources)} reasoning paths")

        return TechniqueResult(
            output=output,
            chain=chain,
            confidence=confidence,
            frameworks_used=["federated_reasoning"],
            metadata={
                "source_count": len(sources),
                "sources": [s["source"] for s in sources],
                "consensus": not any("fail" in s["conclusion"].lower() and
                                    any("pass" in o["conclusion"].lower() for o in sources)
                                    for s in sources),
                "active_frameworks": active_frameworks,
            },
            token_estimate=self.token_cost_estimate,
        )
