"""Adaptive Budget Manager — Reallocate unused tokens across nodes.

When a simple ticket finishes early with unused tokens in knowledge/routing
nodes, TurboQuant can reallocate those tokens to the reasoning/action nodes
that need more room for complex thinking.

This is the KEY differentiator from static budgets — PARWA adapts
token allocation based on what each ticket actually needs.

Rules:
1. Only reallocate from COMPLETED nodes (don't steal from future nodes)
2. Never reduce a node below its minimum (base_budget * 0.25)
3. Only reallocate to nodes that are OVER their allocated budget
4. Track all reallocations for audit transparency
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from parwa.turboquant.token_budget import TokenBudget, get_ticket_budget

logger = logging.getLogger("parwa.turboquant.adaptive")


@dataclass
class ReallocationRecord:
    """Record of a token reallocation between nodes."""
    from_node: str
    to_node: str
    tokens: int
    reason: str
    variant: str


class AdaptiveBudgetManager:
    """Manages adaptive token budget reallocation within a ticket.

    Usage:
        budget = get_ticket_budget("parwa")
        adaptive = AdaptiveBudgetManager(budget)

        # After a node completes with unused tokens
        adaptive.check_and_reallocate(completed_node="faq_matcher")

        # When a node needs more tokens
        bonus = adaptive.request_bonus(node_name="reasoning_engine", needed=200)
    """

    def __init__(self, budget: TokenBudget) -> None:
        """Initialize with a ticket's token budget.

        Args:
            budget: The TokenBudget for the current ticket.
        """
        self.budget = budget
        self.reallocation_log: list[ReallocationRecord] = []

    def check_and_reallocate(self, completed_node: str) -> list[ReallocationRecord]:
        """After a node completes, reallocate its unused tokens to needy nodes.

        Scans all completed nodes for unused tokens and redistributes
        them to nodes that have exceeded their budget.

        Args:
            completed_node: The node that just finished processing.

        Returns:
            List of reallocation records (empty if none happened).
        """
    def check_and_reallocate(self, completed_node: str) -> list[ReallocationRecord]:
        """After a node completes, reallocate its unused tokens to needy nodes."""
        records = []
        completed_budget = self.budget.get_node_budget(completed_node)

        # How many unused tokens does this node have?
        unused = completed_budget.remaining
        if unused <= 0:
            return records

        # Keep a minimum for the completed node (25% of base)
        min_keep = int(completed_budget.base_budget * 0.25)
        available = max(0, unused - min_keep)

        if available <= 0:
            return records

        # Find nodes that are over budget (needy)
        needy_nodes = []
        for name, nb in self.budget.node_budgets.items():
            if nb.used > nb.allocated and name != completed_node:
                deficit = nb.used - nb.allocated
                needy_nodes.append((name, deficit))

        # Sort by deficit (most needy first)
        needy_nodes.sort(key=lambda x: x[1], reverse=True)

        # Distribute available tokens to needy nodes
        remaining = available
        for node_name, deficit in needy_nodes:
            if remaining <= 0:
                break

            give = min(remaining, deficit)
            success = self.budget.reallocate(completed_node, node_name, give)

            if success:
                record = ReallocationRecord(
                    from_node=completed_node,
                    to_node=node_name,
                    tokens=give,
                    reason=f"over_budget_by_{deficit}",
                    variant=self.budget.variant,
                )
                self.reallocation_log.append(record)
                records.append(record)
                remaining -= give

                logger.info(
                    "adaptive_budget: reallocated %d tokens %s→%s (deficit=%d)",
                    give, completed_node, node_name, deficit,
                )

        return records

    def request_bonus(self, node_name: str, needed: int) -> int:
        """Request bonus tokens for a node that needs more than its budget.

        Scans all nodes for surplus tokens and takes what's available.
        Only takes from nodes that haven't been used yet (still at 100% remaining).

        Args:
            node_name: The node requesting bonus tokens.
            needed: How many extra tokens are needed.

        Returns:
            Number of bonus tokens actually granted (may be less than requested).
        """
        granted = 0

        # Find nodes with surplus (unused tokens well above minimum)
        for name, nb in self.budget.node_budgets.items():
            if granted >= needed:
                break
            if name == node_name:
                continue

            # Only take from nodes that haven't run yet (full remaining)
            if nb.used > 0:
                continue

            # How much surplus does this node have? (above 50% of base)
            min_keep = int(nb.base_budget * 0.5)
            surplus = nb.allocated - min_keep

            if surplus <= 0:
                continue

            take = min(surplus, needed - granted)
            success = self.budget.reallocate(name, node_name, take)

            if success:
                record = ReallocationRecord(
                    from_node=name,
                    to_node=node_name,
                    tokens=take,
                    reason=f"bonus_request_{needed}",
                    variant=self.budget.variant,
                )
                self.reallocation_log.append(record)
                granted += take

                logger.debug(
                    "adaptive_budget: granted %d bonus tokens to %s from %s",
                    take, node_name, name,
                )

        if granted > 0:
            logger.info(
                "adaptive_budget: granted %d/%d bonus tokens to %s (variant=%s)",
                granted, needed, node_name, self.budget.variant,
            )

        return granted

    def get_reallocation_summary(self) -> dict[str, Any]:
        """Get a summary of all reallocations that happened.

        Returns:
            Dict with total_reallocated, reallocation_count, details.
        """
        total = sum(r.tokens for r in self.reallocation_log)
        return {
            "total_reallocated": total,
            "reallocation_count": len(self.reallocation_log),
            "variant": self.budget.variant,
            "details": [
                {
                    "from": r.from_node,
                    "to": r.to_node,
                    "tokens": r.tokens,
                    "reason": r.reason,
                }
                for r in self.reallocation_log
            ],
        }
