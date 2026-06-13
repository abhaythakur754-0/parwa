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
# Mini = cost-sensitive but needs real LLM (0.8x), PARWA = balanced (1.0x), High = accuracy-first (2.0x)
# Month 1 fix: Increased Mini from 0.5x to 0.8x — it was too restrictive,
# causing most nodes to skip real LLM calls entirely
VARIANT_TOKEN_MULTIPLIERS: dict[str, float] = {
    "mini": 0.8,
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
    "intent_classifier": 3000,   # LLM classification (needs room for few-shot examples)
    "sentiment_analyzer": 2000,   # LLM sentiment
    "escalation_decision": 2000, # LLM escalation check

    # Knowledge Agent nodes
    "faq_matcher": 2000,         # LLM FAQ matching
    "kb_retriever": 2000,        # LLM + embedding lookup
    "context_manager": 50,       # No LLM, just data management
    "integration_lookup": 50,    # No LLM, API calls only

    # Reasoning Agent nodes
    "reasoning_engine": 5000,    # LLM chain of thought — THE brain (needs more tokens for real reasoning)
    "reverse_thinker": 3000,     # LLM validation
    "tree_of_thoughts": 4000,    # LLM multi-path exploration
    "strategy_planner": 3000,    # LLM strategy creation

    # Action Agent nodes
    "action_planner": 1500,      # LLM action planning
    "action_executor": 50,       # No LLM, permission check only
    "action_verifier": 50,       # No LLM, verification logic

    # Proactive Agent nodes
    "proactive_checker": 1500,   # LLM proactive insights
    "prediction_engine": 1500,   # LLM predictions
    "feedback_loop": 50,         # No LLM, feedback signal generation

    # Compliance Agent nodes
    "pii_compliance_guard": 50,  # No LLM, regex-based
    "audit_logger": 50,          # No LLM, logging only
    "quality_scorer": 2000,      # LLM quality scoring (needs room for honest scoring)
    "response_formatter": 3000,  # LLM response crafting (needs room for detailed responses)

    # FrameworkBrain technique nodes (used by brain.py for LLM technique calls)
    "frameworkbrain_cot": 2000,  # Chain of Thought
    "frameworkbrain_react": 2000,# ReAct Think-Act-Observe
    "frameworkbrain_tot": 2000,  # Tree of Thoughts
    "frameworkbrain_reverse": 2000, # Reverse Thinking
    "frameworkbrain_clara": 1500,# Confidence-driven retrieval
    "frameworkbrain_hyde": 1500, # Hypothetical Document Embedding
    "frameworkbrain_multi_query": 1500, # Multiple query variations
    "frameworkbrain_step_back": 1500,   # Step-back retrieval
    "frameworkbrain_reflexion": 1500,   # Self-reflective improvement
    "frameworkbrain_sc": 1500,   # Self-consistency
    "frameworkbrain_crp": 1500,  # Constrained Response
    "frameworkbrain_ltm": 1500,  # Least-to-Most
    "frameworkbrain_uot": 1500,  # Uncertainty of Thought
    "frameworkbrain_gst": 1500,  # Graph of Strategic Thought
    "frameworkbrain_thot": 1500, # Thread of Thought
    "frameworkbrain_dynamic_context": 1500, # Dynamic Context
    "frameworkbrain_contextual_compression": 1500, # Contextual Compression
    "frameworkbrain_gsd": 500,   # GSD technique (no LLM call)
    "frameworkbrain_smart_router": 500, # Smart Router (no LLM call)
    "frameworkbrain_maker": 1500, # MAKER technique
    "frameworkbrain_adaptive_budget": 500, # Adaptive Budget (no LLM call)
    "frameworkbrain_turbo_compress": 500, # TurboCompress (no LLM call)
    "frameworkbrain_federated_reasoning": 1500, # Federated Reasoning
    "frameworkbrain_zero_shot_validator": 1500, # Zero-Shot Validator
    "frameworkbrain_meta_learner": 1500, # Meta-Learner
}

# ─── Per-Ticket Total Budgets ───────────────────────────────────────────────────────
# Maximum total tokens per ticket for each variant.
# This is the safety cap — a single ticket cannot exceed this.
# Month 1 fix: Increased from 30K/60K/120K to accommodate real LLM calls
# across all 22 nodes. The old budgets were too tight for real AI processing.
TICKET_TOTAL_BUDGETS: dict[str, int] = {
    "mini": 60000,     # Cost-sensitive but enough for real LLM calls across all 22 nodes
    "parwa": 100000,   # Balanced — enough for all techniques with real tokens
    "high": 200000,    # Accuracy-first — generous budgets for production
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
        node_name: The node name (e.g. "reasoning_engine"). Case-insensitive.
        variant: The PARWA variant (mini, parwa, high).

    Returns:
        A NodeBudget instance with allocated tokens.
    """
    # Normalize to lowercase for consistent budget lookup
    node_name_normalized = node_name.lower() if node_name else node_name
    base = NODE_BASE_BUDGETS.get(node_name_normalized, 100)
    multiplier = VARIANT_TOKEN_MULTIPLIERS.get(variant, 1.0)
    allocated = int(base * multiplier)

    return NodeBudget(
        node_name=node_name_normalized,
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
