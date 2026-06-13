"""Cost Reporter — Per-ticket and per-variant cost analysis.

Provides cost reporting and analysis for the PARWA platform:
- Per-ticket cost breakdown by node
- Per-variant cost aggregation
- Cost forecasting based on volume
- Efficiency metrics (cost per resolution, cost per ticket)

This is what makes PARWA's pricing work — know exactly what each
ticket costs so variants can be priced profitably.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from parwa.turboquant.token_tracker import TokenTracker, TokenUsage, get_token_tracker
from parwa.turboquant.token_budget import TICKET_TOTAL_BUDGETS

logger = logging.getLogger("parwa.turboquant.cost")

# ─── Model Pricing (USD per 1M tokens) ─────────────────────────────────────────────
MODEL_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
}


@dataclass
class CostReport:
    """Cost analysis report for a ticket or variant."""
    scope: str  # "ticket", "variant", "system"
    identifier: str  # ticket_id or variant name
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_cost_usd: float = 0.0
    node_breakdown: dict[str, dict[str, Any]] = field(default_factory=dict)
    llm_call_count: int = 0
    avg_cost_per_call: float = 0.0
    budget_utilization: float = 0.0  # percent

    def __post_init__(self) -> None:
        if self.llm_call_count > 0:
            self.avg_cost_per_call = self.total_cost_usd / self.llm_call_count


class CostReporter:
    """Generate cost reports from the token tracker.

    Usage:
        reporter = CostReporter()
        ticket_report = reporter.ticket_report("TKT-ABC123")
        variant_report = reporter.variant_report("mini")
        system_report = reporter.system_report()
    """

    def __init__(self, tracker: TokenTracker | None = None) -> None:
        """Initialize the cost reporter.

        Args:
            tracker: Token tracker instance (uses global if None).
        """
        self.tracker = tracker or get_token_tracker()

    def _calculate_cost(self, usage: TokenUsage) -> float:
        """Calculate cost for a single token usage record."""
        pricing = MODEL_PRICING.get(usage.model, MODEL_PRICING["gpt-4o-mini"])
        input_cost = (usage.prompt_tokens / 1_000_000) * pricing["input"]
        output_cost = (usage.completion_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost

    def ticket_report(self, ticket_id: str, variant: str = "parwa") -> CostReport:
        """Generate a cost report for a single ticket.

        Args:
            ticket_id: The ticket ID to report on.
            variant: The variant for budget comparison.

        Returns:
            CostReport with per-node breakdown.
        """
        records = self.tracker.get_ticket_usage(ticket_id)

        report = CostReport(
            scope="ticket",
            identifier=ticket_id,
        )

        for r in records:
            cost = self._calculate_cost(r)
            report.total_tokens += r.total_tokens
            report.prompt_tokens += r.prompt_tokens
            report.completion_tokens += r.completion_tokens
            report.total_cost_usd += cost
            report.llm_call_count += 1

            # Per-node breakdown
            if r.node_name not in report.node_breakdown:
                report.node_breakdown[r.node_name] = {
                    "tokens": 0,
                    "cost_usd": 0.0,
                    "calls": 0,
                }
            nb = report.node_breakdown[r.node_name]
            nb["tokens"] += r.total_tokens
            nb["cost_usd"] += cost
            nb["calls"] += 1

        # Budget utilization
        budget = TICKET_TOTAL_BUDGETS.get(variant, 4000)
        report.budget_utilization = (report.total_tokens / budget * 100) if budget > 0 else 0.0

        if report.llm_call_count > 0:
            report.avg_cost_per_call = report.total_cost_usd / report.llm_call_count

        return report

    def variant_report(self, variant: str) -> CostReport:
        """Generate a cost report for a variant.

        Args:
            variant: The variant to report on.

        Returns:
            CostReport with aggregated variant data.
        """
        records = self.tracker.get_variant_usage(variant)

        report = CostReport(
            scope="variant",
            identifier=variant,
        )

        ticket_ids = set()

        for r in records:
            cost = self._calculate_cost(r)
            report.total_tokens += r.total_tokens
            report.prompt_tokens += r.prompt_tokens
            report.completion_tokens += r.completion_tokens
            report.total_cost_usd += cost
            report.llm_call_count += 1
            ticket_ids.add(r.ticket_id)

            # Per-node breakdown
            if r.node_name not in report.node_breakdown:
                report.node_breakdown[r.node_name] = {
                    "tokens": 0,
                    "cost_usd": 0.0,
                    "calls": 0,
                }
            nb = report.node_breakdown[r.node_name]
            nb["tokens"] += r.total_tokens
            nb["cost_usd"] += cost
            nb["calls"] += 1

        if report.llm_call_count > 0:
            report.avg_cost_per_call = report.total_cost_usd / report.llm_call_count

        # Add ticket count to breakdown
        report.node_breakdown["__meta"] = {
            "ticket_count": len(ticket_ids),
            "avg_tokens_per_ticket": report.total_tokens / len(ticket_ids) if ticket_ids else 0,
            "avg_cost_per_ticket": report.total_cost_usd / len(ticket_ids) if ticket_ids else 0,
        }

        return report

    def system_report(self) -> CostReport:
        """Generate a system-wide cost report across all variants.

        Returns:
            CostReport with system-wide aggregation.
        """
        report = CostReport(
            scope="system",
            identifier="all",
        )

        node_summary = self.tracker.get_node_summary()
        variant_summary = self.tracker.get_variant_summary()

        for node_name, stats in node_summary.items():
            report.total_tokens += stats["total_tokens"]
            report.prompt_tokens += stats["total_prompt"]
            report.completion_tokens += stats["total_completion"]
            report.total_cost_usd += stats["total_cost"]
            report.llm_call_count += stats["call_count"]

            report.node_breakdown[node_name] = {
                "tokens": stats["total_tokens"],
                "cost_usd": stats["total_cost"],
                "calls": stats["call_count"],
                "avg_tokens": stats.get("avg_tokens", 0),
            }

        if report.llm_call_count > 0:
            report.avg_cost_per_call = report.total_cost_usd / report.llm_call_count

        # Add variant breakdown
        report.node_breakdown["__variant_summary"] = variant_summary

        return report

    def forecast_monthly_cost(
        self,
        variant: str,
        tickets_per_month: int,
        avg_tokens_per_ticket: int | None = None,
    ) -> dict[str, Any]:
        """Forecast monthly cost for a variant.

        Args:
            variant: The variant to forecast.
            tickets_per_month: Expected tickets per month.
            avg_tokens_per_ticket: Override for average tokens per ticket.

        Returns:
            Dict with projected costs and metrics.
        """
        # Get actual average from tracker, or use budget as estimate
        if avg_tokens_per_ticket is None:
            variant_records = self.tracker.get_variant_usage(variant)
            if variant_records:
                ticket_ids = set(r.ticket_id for r in variant_records)
                total_tokens = sum(r.total_tokens for r in variant_records)
                avg_tokens_per_ticket = total_tokens / len(ticket_ids) if ticket_ids else 2000
            else:
                avg_tokens_per_ticket = TICKET_TOTAL_BUDGETS.get(variant, 4000) * 0.6

        # Estimate cost using gpt-4o-mini pricing
        pricing = MODEL_PRICING["gpt-4o-mini"]
        # Assume 70% input, 30% output split
        input_tokens = int(avg_tokens_per_ticket * 0.7)
        output_tokens = int(avg_tokens_per_ticket * 0.3)
        cost_per_ticket = (
            (input_tokens / 1_000_000) * pricing["input"] +
            (output_tokens / 1_000_000) * pricing["output"]
        )

        monthly_cost = cost_per_ticket * tickets_per_month

        return {
            "variant": variant,
            "tickets_per_month": tickets_per_month,
            "avg_tokens_per_ticket": int(avg_tokens_per_ticket),
            "cost_per_ticket_usd": round(cost_per_ticket, 6),
            "monthly_cost_usd": round(monthly_cost, 2),
            "model": "gpt-4o-mini",
            "input_output_split": "70/30",
        }


# ─── Global Singleton ──────────────────────────────────────────────────────────────

_reporter: CostReporter | None = None


def get_cost_reporter() -> CostReporter:
    """Get or create the global cost reporter singleton."""
    global _reporter
    if _reporter is None:
        _reporter = CostReporter()
    return _reporter
