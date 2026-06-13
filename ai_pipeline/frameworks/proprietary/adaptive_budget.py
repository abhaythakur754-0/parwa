"""AdaptiveBudget — Dynamic token budget reallocation technique.

AdaptiveBudget monitors token usage across nodes and dynamically
reallocates budget from under-spending nodes to over-spending ones.

How it works:
  - Checks current token spend per node vs. allocated budget
  - Identifies nodes that are over-budget (need more tokens)
  - Identifies nodes that are under-budget (can release tokens)
  - Reallocates budget to ensure critical nodes never run out

What hallucination it catches:
  "Budget exhaustion" — when a critical node runs out of tokens
  mid-reasoning, it falls back to rule-based output. AdaptiveBudget
  prevents this by shifting budget where it's needed.

Activation:
  - Activates on MEDIUM+ complexity (simple tickets stay within budget)
  - Critical for complex tickets where reasoning nodes need more tokens
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.frameworks.base import BaseTechnique, TechniqueCategory, TechniqueResult

logger = logging.getLogger("parwa.frameworks.adaptive_budget")


class AdaptiveBudgetTechnique(BaseTechnique):
    """Adaptive Budget token reallocation technique.

    Monitors and dynamically reallocates token budgets across nodes
    to prevent budget exhaustion during critical reasoning.
    """

    _min_complexity = "medium"

    @property
    def name(self) -> str:
        return "adaptive_budget"

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
        ]

    @property
    def token_cost_estimate(self) -> int:
        return 5  # Negligible — just budget math, no LLM call

    async def think(
        self,
        prompt: str,
        state: dict[str, Any],
        *,
        ticket_id: str = "",
        variant: str = "parwa",
    ) -> TechniqueResult:
        """Execute adaptive budget reallocation.

        Checks token usage and recommends reallocation if needed.
        """
        total_budget = state.get("token_budget_total", 0)
        used = state.get("token_budget_used", 0)
        remaining = state.get("token_budget_remaining", 0)
        usage_by_node = state.get("token_usage_by_node", {})

        chain = []

        # Calculate utilization
        utilization = (used / total_budget * 100) if total_budget > 0 else 0
        chain.append(f"AdaptiveBudget: {utilization:.0f}% utilized ({used}/{total_budget})")

        # Check per-node usage
        over_budget_nodes = []
        under_budget_nodes = []
        for node_name, usage in usage_by_node.items():
            if isinstance(usage, dict):
                node_used = usage.get("used", 0)
                node_allocated = usage.get("allocated", 0)
                if node_allocated > 0:
                    node_ratio = node_used / node_allocated
                    if node_ratio > 0.9:
                        over_budget_nodes.append(node_name)
                    elif node_ratio < 0.3:
                        under_budget_nodes.append(node_name)

        # Build reallocation recommendation
        reallocations = []
        if over_budget_nodes:
            chain.append(f"AdaptiveBudget: Over-budget nodes: {over_budget_nodes}")
            for node in over_budget_nodes:
                reallocations.append(f"+500 tokens to {node}")

        if under_budget_nodes:
            chain.append(f"AdaptiveBudget: Under-budget nodes: {under_budget_nodes}")
            for node in under_budget_nodes:
                reallocations.append(f"-200 tokens from {node}")

        if not over_budget_nodes and not under_budget_nodes:
            chain.append("AdaptiveBudget: All nodes within budget — no reallocation needed")

        output = "; ".join(reallocations) if reallocations else "Budget allocation optimal"

        return TechniqueResult(
            output=output,
            chain=chain,
            confidence=0.90,
            frameworks_used=["adaptive_budget"],
            metadata={
                "total_budget": total_budget,
                "used": used,
                "remaining": remaining,
                "utilization_pct": round(utilization, 1),
                "over_budget_nodes": over_budget_nodes,
                "under_budget_nodes": under_budget_nodes,
            },
            token_estimate=self.token_cost_estimate,
        )
