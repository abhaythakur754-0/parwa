"""Technique priority configurations for each subgraph.

Each subgraph has a different set of technique priorities because
different reasoning strategies work best for different domains:

  Refund: Policy-first reasoning (CoT > Reverse > ReAct)
  Tech:   Diagnostic reasoning (ReAct > CoT > ToT)
  Billing: Verification reasoning (CoT > Self-Consistency > Reverse)
  General: Simple reasoning (CoT > Least-to-Most)

These configs override the default priority sorting in FrameworkBrain
when a subgraph is active, ensuring domain-appropriate techniques
fire first and get the output slot.
"""

from __future__ import annotations

from typing import Any


# ─── Technique Priority Configs ───────────────────────────────────────────────

SUBGRAPH_TECHNIQUE_PRIORITIES: dict[str, dict[str, list[str]]] = {
    "refund": {
        # For refund tickets, policy reasoning is king
        # CoT for step-by-step policy check
        # Reverse Thinking for "what if this refund is wrong?"
        # ReAct for looking up customer history
        # SmartRouter for intelligent model selection
        # ZeroShotValidator for policy compliance verification
        "REASONING_ENGINE": ["chain_of_thought", "reverse_thinking", "react", "smart_router", "zero_shot_validator"],
        "KB_RETRIEVER": ["hyde", "multi_query", "step_back"],
        "ACTION_PLANNER": ["chain_of_thought", "least_to_most"],
        "QUALITY_SCORER": ["self_consistency", "reflexion"],
    },
    "tech": {
        # For tech tickets, diagnostic reasoning dominates
        # ReAct for step-by-step troubleshooting
        # ToT for complex multi-path diagnostics
        # CoT as baseline for simple issues
        # UoT for uncertainty-driven deep analysis
        # GSD for Get Stuff Done action-oriented resolution
        # ZeroShotValidator for verifying fix correctness
        "REASONING_ENGINE": ["react", "chain_of_thought", "tree_of_thoughts", "uncertainty_of_thought", "gsd", "zero_shot_validator"],
        "KB_RETRIEVER": ["multi_query", "step_back", "hyde"],
        "ACTION_PLANNER": ["react", "chain_of_thought", "gsd"],
        "QUALITY_SCORER": ["reflexion", "crp", "zero_shot_validator"],
    },
    "billing": {
        # For billing tickets, verification is critical
        # CoT for charge verification step-by-step
        # Self-Consistency for "does this charge match the plan?"
        # Reverse for "what if this charge is incorrect?"
        # SmartRouter for intelligent model selection
        # ZeroShotValidator for charge compliance
        "REASONING_ENGINE": ["chain_of_thought", "self_consistency", "reverse_thinking", "smart_router", "zero_shot_validator"],
        "KB_RETRIEVER": ["hyde", "multi_query", "step_back"],
        "ACTION_PLANNER": ["chain_of_thought", "least_to_most"],
        "QUALITY_SCORER": ["self_consistency", "reflexion", "zero_shot_validator"],
    },
    "general": {
        # For general tickets, keep it effective
        # CoT for straightforward reasoning
        # Least-to-Most for multi-part questions
        # GSD for action-oriented resolution
        "REASONING_ENGINE": ["chain_of_thought", "least_to_most", "gsd"],
        "KB_RETRIEVER": ["hyde", "multi_query"],
        "ACTION_PLANNER": ["chain_of_thought", "gsd"],
        "QUALITY_SCORER": ["reflexion"],
    },
}


# ─── Technique Activation Caps by Subgraph ────────────────────────────────────

SUBGRAPH_TECHNIQUE_CAPS: dict[str, dict[str, int]] = {
    "refund": {
        "simple": 3,     # Was 1 — refund tickets need policy verification even when simple
        "medium": 4,     # Was 2 — medium refund needs full policy stack
        "complex": 5,    # Was 3 — complex refund with disputes needs everything
        "critical": 6,   # Was 4 — fraud/legal refund gets all techniques
    },
    "tech": {
        "simple": 3,     # Was 2 — even simple tech needs ReAct + CoT + verification
        "medium": 4,     # Was 3 — medium tech needs full diagnostic stack
        "complex": 5,    # Was 4 — complex tech gets deep multi-path analysis
        "critical": 6,   # Was 4 — critical tech gets everything
    },
    "billing": {
        "simple": 3,     # Was 1 — billing always needs verification
        "medium": 4,     # Was 2 — medium billing needs charge + plan verification
        "complex": 5,    # Was 3 — complex billing disputes need full stack
        "critical": 6,   # Was 4 — critical billing (legal/high-value) gets everything
    },
    "general": {
        "simple": 2,     # Was 1 — even simple general gets CoT + 1 more
        "medium": 3,     # Was 1 — medium general needs proper reasoning
        "complex": 4,    # Was 2 — complex general needs multi-technique
        "critical": 5,   # Was 3 — critical general (complaints/escalations) needs more
    },
}


# ─── Subgraph-Specific KB Search Boosting ─────────────────────────────────────

SUBGRAPH_KB_BOOSTS: dict[str, dict[str, float]] = {
    "refund": {
        "refund_policy": 0.4,
        "return_policy": 0.3,
        "cancellation": 0.2,
        "subscription": 0.1,
    },
    "tech": {
        "troubleshooting": 0.4,
        "integration_guide": 0.3,
        "api_docs": 0.2,
        "known_issues": 0.3,
    },
    "billing": {
        "pricing": 0.4,
        "invoice": 0.3,
        "payment": 0.3,
        "subscription": 0.2,
    },
    "general": {
        "faq": 0.3,
        "how_to": 0.2,
        "policy": 0.1,
    },
}


def get_subgraph_techniques(subgraph: str, node: str) -> list[str]:
    """Get the ordered technique list for a subgraph + node combination.

    Args:
        subgraph: The subgraph name (refund/tech/billing/general).
        node: The node name (e.g. REASONING_ENGINE).

    Returns:
        Ordered list of technique names, highest-priority first.
    """
    return SUBGRAPH_TECHNIQUE_PRIORITIES.get(subgraph, {}).get(node, [])


def get_subgraph_cap(subgraph: str, complexity: str) -> int:
    """Get the maximum techniques to run for a subgraph + complexity.

    Args:
        subgraph: The subgraph name.
        complexity: The ticket complexity level.

    Returns:
        Maximum number of techniques to activate.
    """
    return SUBGRAPH_TECHNIQUE_CAPS.get(subgraph, {}).get(complexity, 2)


def get_subgraph_kb_boosts(subgraph: str) -> dict[str, float]:
    """Get KB search term boosting weights for a subgraph.

    Args:
        subgraph: The subgraph name.

    Returns:
        Dict of search terms to boost weights.
    """
    return SUBGRAPH_KB_BOOSTS.get(subgraph, {})
