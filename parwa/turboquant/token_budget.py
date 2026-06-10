"""Token Budget System — Per-node token budget allocation with variant awareness.

Every node gets a base token budget. The variant determines the multiplier:
- Mini: 0.5x (cost-sensitive, uses prompt compression aggressively)
- PARWA: 1.0x (balanced)
- High: 2.0x (accuracy-focused, generous budgets)

TurboQuant never sacrifices accuracy — it optimizes token EFFICIENCY.
If a node needs more tokens for accuracy, it gets them.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("parwa.turboquant.budget")

# ─── Variant Token Multipliers ─────────────────────────────────────────────────────
# Mini = cost-sensitive (0.5x), PARWA = balanced (1.0x), High = accuracy-first (2.0x)
# These multipliers scale the BASE budget for each node.
VARIANT_TOKEN_MULTIPLIERS: dict[str, float] = {
    "mini": 0.5,
    "parwa": 1.0,
    "high": 2.0,
}

# ─── Node Budget Definitions ───────────────────────────────────────────────────────
# Base budgets (in tokens) for each of the 22 nodes.
# These are the "PARWA variant" budgets — Mini gets 0.5x, High gets 2.0x.
# Nodes that call LLM get higher budgets; rule-based nodes get minimal budgets.

NODE_BASE_BUDGETS: dict[str, int] = {
    # Router Agent nodes
    "ingest": 50,                # No LLM, just validation
    "intent_classifier": 300,    # LLM classification
    "sentiment_analyzer": 250,   # LLM sentiment
    "escalation_decision": 200,  # LLM escalation check

    # Knowledge Agent nodes
    "faq_matcher": 300,          # LLM FAQ matching
    "kb_retriever": 150,         # Rule-based + embedding lookup
    "context_manager": 50,       # No LLM, just data management
    "integration_lookup": 50,    # No LLM, API calls only

    # Reasoning Agent nodes
    "reasoning_engine": 800,     # LLM chain of thought — THE brain
    "reverse_thinker": 400,      # LLM validation
    "tree_of_thoughts": 600,     # LLM multi-path exploration
    "strategy_planner": 400,     # LLM strategy creation

    # Action Agent nodes
    "action_planner": 300,       # LLM action planning
    "action_executor": 50,       # No LLM, permission check only
    "action_verifier": 50,       # No LLM, verification logic

    # Proactive Agent nodes
    "proactive_checker": 200,    # LLM proactive insights
    "prediction_engine": 200,    # LLM predictions
    "feedback_loop": 50,         # No LLM, feedback signal generation

    # Compliance Agent nodes
    "pii_compliance_guard": 50,  # No LLM, regex-based
    "audit_logger": 50,          # No LLM, logging only
    "quality_scorer": 200,       # LLM quality scoring
    "response_formatter": 500,   # LLM response crafting
}

# ─── Per-Ticket Total Budgets ───────────────────────────────────────────────────────
# Maximum total tokens per ticket for each variant.
# This is the safety cap — a single ticket cannot exceed this.
TICKET_TOTAL_BUDGETS: dict[str, int] = {
    "mini": 2000,    # ~$0.003 per ticket (gpt-4o-mini)
    "parwa": 4000,   # ~$0.006 per ticket
    "high": 8000,    # ~$0.012 per ticket (accuracy first)
}


@dataclass
class NodeBudget:
    """Token budget for a single node execution."""
    node_name: str
    base_budget: int
    variant: str
    multiplier: float
    allocated: int
    used: int = 0
    remaining: int = 0

    def __post_init__(self) -> None:
        self.remaining = self.allocated - self.used

    def can_spend(self, tokens: int) -> bool:
        """Check if we have budget for the given number of tokens."""
        return tokens <= self.remaining

    def spend(self, tokens: int) -> None:
        """Record token usage against this budget."""
        self.used += tokens
        self.remaining = self.allocated - self.used

    def utilization(self) -> float:
        """Return budget utilization as a percentage (0-100)."""
        if self.allocated == 0:
            return 0.0
        return min(100.0, (self.used / self.allocated) * 100)


@dataclass
class TokenBudget:
    """Complete token budget for a ticket across all nodes.

    Tracks per-node budgets and total ticket budget.
    Supports adaptive reallocation from unused to needy nodes.
    """
    variant: str
    ticket_total: int
    node_budgets: dict[str, NodeBudget] = field(default_factory=dict)
    total_used: int = 0

    def __post_init__(self) -> None:
        if not self.node_budgets:
            self._allocate_node_budgets()

    def _allocate_node_budgets(self) -> None:
        """Allocate token budgets to all 22 nodes based on variant multiplier."""
        multiplier = VARIANT_TOKEN_MULTIPLIERS.get(self.variant, 1.0)

        for node_name, base_budget in NODE_BASE_BUDGETS.items():
            allocated = int(base_budget * multiplier)
            self.node_budgets[node_name] = NodeBudget(
                node_name=node_name,
                base_budget=base_budget,
                variant=self.variant,
                multiplier=multiplier,
                allocated=allocated,
            )

    def get_node_budget(self, node_name: str) -> NodeBudget:
        """Get the budget for a specific node."""
        if node_name not in self.node_budgets:
            # Unknown node — give it a small default budget
            multiplier = VARIANT_TOKEN_MULTIPLIERS.get(self.variant, 1.0)
            self.node_budgets[node_name] = NodeBudget(
                node_name=node_name,
                base_budget=100,
                variant=self.variant,
                multiplier=multiplier,
                allocated=int(100 * multiplier),
            )
        return self.node_budgets[node_name]

    def spend_tokens(self, node_name: str, tokens: int) -> bool:
        """Record token usage for a node. Returns True if within budget."""
        budget = self.get_node_budget(node_name)
        budget.spend(tokens)
        self.total_used += tokens

        if budget.used > budget.allocated:
            logger.warning(
                "token_budget: node=%s over_budget used=%d allocated=%d variant=%s",
                node_name, budget.used, budget.allocated, self.variant,
            )
            return False
        return True

    def remaining_total(self) -> int:
        """Total remaining tokens across all nodes."""
        return self.ticket_total - self.total_used

    def utilization(self) -> float:
        """Overall budget utilization as a percentage."""
        if self.ticket_total == 0:
            return 0.0
        return min(100.0, (self.total_used / self.ticket_total) * 100)

    def reallocate(self, from_node: str, to_node: str, tokens: int) -> bool:
        """Move unused tokens from one node to another (adaptive budgeting).

        Args:
            from_node: Node giving up tokens.
            to_node: Node receiving tokens.
            tokens: Number of tokens to reallocate.

        Returns:
            True if reallocation succeeded.
        """
        from_budget = self.get_node_budget(from_node)
        to_budget = self.get_node_budget(to_node)

        available = from_budget.remaining
        if available < tokens:
            logger.debug(
                "reallocate: insufficient remaining in %s (have=%d, need=%d)",
                from_node, available, tokens,
            )
            return False

        from_budget.allocated -= tokens
        from_budget.remaining = from_budget.allocated - from_budget.used
        to_budget.allocated += tokens
        to_budget.remaining = to_budget.allocated - to_budget.used

        logger.info(
            "reallocate: %d tokens from %s → %s (variant=%s)",
            tokens, from_node, to_node, self.variant,
        )
        return True


def get_node_budget(node_name: str, variant: str = "parwa") -> NodeBudget:
    """Get the token budget for a specific node and variant.

    Args:
        node_name: The node name (e.g. "reasoning_engine").
        variant: The PARWA variant (mini, parwa, high).

    Returns:
        A NodeBudget instance with allocated tokens.
    """
    base = NODE_BASE_BUDGETS.get(node_name, 100)
    multiplier = VARIANT_TOKEN_MULTIPLIERS.get(variant, 1.0)
    allocated = int(base * multiplier)

    return NodeBudget(
        node_name=node_name,
        base_budget=base,
        variant=variant,
        multiplier=multiplier,
        allocated=allocated,
    )


def get_ticket_budget(variant: str = "parwa") -> TokenBudget:
    """Create a complete token budget for a ticket.

    Args:
        variant: The PARWA variant (mini, parwa, high).

    Returns:
        A TokenBudget with all 22 node budgets allocated.
    """
    total = TICKET_TOTAL_BUDGETS.get(variant, 4000)
    return TokenBudget(variant=variant, ticket_total=total)
