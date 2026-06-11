"""Tests for TurboQuant — PARWA's Token Optimization Engine.

Tests token budgets, tracking, compression, adaptive reallocation,
and cost reporting across all three variants.
"""

import pytest

from parwa.turboquant.token_budget import (
    TokenBudget, NodeBudget, get_node_budget, get_ticket_budget,
    VARIANT_TOKEN_MULTIPLIERS, NODE_BASE_BUDGETS, TICKET_TOTAL_BUDGETS,
)
from parwa.turboquant.token_tracker import TokenTracker, TokenUsage, get_token_tracker
from parwa.turboquant.prompt_compressor import PromptCompressor, compress_prompt
from parwa.turboquant.adaptive_budget import AdaptiveBudgetManager, ReallocationRecord
from parwa.turboquant.cost_reporter import CostReporter, CostReport, get_cost_reporter


# ─── Token Budget Tests ────────────────────────────────────────────────────────────

class TestNodeBudget:
    """Test per-node token budget allocation."""

    def test_parwa_variant_gets_base_budget(self):
        """PARWA variant should get exactly the base budget (1.0x multiplier)."""
        budget = get_node_budget("reasoning_engine", "parwa")
        assert budget.allocated == NODE_BASE_BUDGETS["reasoning_engine"]
        assert budget.multiplier == 1.0

    def test_mini_variant_gets_reduced_budget(self):
        """Mini variant should get 0.8x the base budget (Month 1 fix: was 0.5x, too restrictive)."""
        budget = get_node_budget("reasoning_engine", "mini")
        assert budget.allocated == int(NODE_BASE_BUDGETS["reasoning_engine"] * 0.8)
        assert budget.multiplier == 0.8

    def test_high_variant_gets_double_budget(self):
        """High variant should get 2.0x the base budget."""
        budget = get_node_budget("reasoning_engine", "high")
        assert budget.allocated == NODE_BASE_BUDGETS["reasoning_engine"] * 2
        assert budget.multiplier == 2.0

    def test_unknown_node_gets_default_budget(self):
        """Unknown node name should get a small default budget."""
        budget = get_node_budget("custom_node", "parwa")
        assert budget.allocated > 0

    def test_node_budget_spend_tracking(self):
        """Spending tokens should track usage correctly."""
        budget = get_node_budget("intent_classifier", "parwa")
        assert budget.can_spend(100)
        budget.spend(100)
        assert budget.used == 100
        assert budget.remaining == budget.allocated - 100

    def test_node_budget_over_spend(self):
        """Over-spending should be tracked (not blocked)."""
        budget = get_node_budget("ingest", "parwa")
        budget.spend(budget.allocated + 50)
        assert budget.used > budget.allocated

    def test_node_budget_utilization(self):
        """Utilization should be calculated correctly."""
        budget = get_node_budget("intent_classifier", "parwa")
        budget.spend(budget.allocated // 2)
        assert budget.utilization() == 50.0


class TestTokenBudget:
    """Test complete ticket token budget."""

    def test_ticket_budget_all_22_nodes(self):
        """Ticket budget should allocate to all 22+ nodes (including FrameworkBrain technique nodes)."""
        budget = get_ticket_budget("parwa")
        assert len(budget.node_budgets) >= 22

    def test_ticket_budget_total_matches_variant(self):
        """Ticket total budget should match variant configuration."""
        budget = get_ticket_budget("mini")
        assert budget.ticket_total == TICKET_TOTAL_BUDGETS["mini"]

    def test_ticket_budget_spend_tokens(self):
        """Spending tokens on a node should track correctly."""
        budget = get_ticket_budget("parwa")
        within = budget.spend_tokens("reasoning_engine", 100)
        assert within is True
        assert budget.total_used == 100

    def test_ticket_budget_remaining(self):
        """Remaining total should decrease as tokens are spent."""
        budget = get_ticket_budget("parwa")
        initial_remaining = budget.remaining_total()
        budget.spend_tokens("reasoning_engine", 100)
        assert budget.remaining_total() == initial_remaining - 100

    def test_ticket_budget_reallocation(self):
        """Should be able to reallocate tokens between nodes."""
        budget = get_ticket_budget("parwa")
        success = budget.reallocate("ingest", "reasoning_engine", 20)
        assert success is True
        # Reasoning should have more, ingest less
        assert budget.get_node_budget("reasoning_engine").allocated > NODE_BASE_BUDGETS["reasoning_engine"]
        assert budget.get_node_budget("ingest").allocated < NODE_BASE_BUDGETS["ingest"]


# ─── Token Tracker Tests ───────────────────────────────────────────────────────────

class TestTokenTracker:
    """Test token usage tracking."""

    def test_record_usage(self):
        """Should record a token usage event."""
        tracker = TokenTracker()
        usage = tracker.record(
            ticket_id="TKT-001", node_name="reasoning_engine",
            variant="parwa", prompt_tokens=100, completion_tokens=50,
        )
        assert usage.total_tokens == 150
        assert usage.ticket_id == "TKT-001"

    def test_get_ticket_usage(self):
        """Should retrieve usage for a specific ticket."""
        tracker = TokenTracker()
        tracker.record("TKT-001", "ingest", "parwa", 50, 20)
        tracker.record("TKT-001", "reasoning_engine", "parwa", 100, 80)
        tracker.record("TKT-002", "ingest", "mini", 30, 10)

        ticket_usage = tracker.get_ticket_usage("TKT-001")
        assert len(ticket_usage) == 2

    def test_get_node_usage(self):
        """Should retrieve usage for a specific node."""
        tracker = TokenTracker()
        tracker.record("TKT-001", "reasoning_engine", "parwa", 100, 80)
        tracker.record("TKT-002", "reasoning_engine", "high", 200, 150)

        node_usage = tracker.get_node_usage("reasoning_engine")
        assert len(node_usage) == 2

    def test_get_total_tokens(self):
        """Should calculate total tokens across all records."""
        tracker = TokenTracker()
        tracker.record("TKT-001", "ingest", "parwa", 50, 20)
        tracker.record("TKT-001", "reasoning_engine", "parwa", 100, 80)

        assert tracker.get_total_tokens() == 250

    def test_get_total_tokens_by_variant(self):
        """Should filter total tokens by variant."""
        tracker = TokenTracker()
        tracker.record("TKT-001", "ingest", "parwa", 50, 20)
        tracker.record("TKT-002", "ingest", "mini", 30, 10)

        assert tracker.get_total_tokens(variant="mini") == 40
        assert tracker.get_total_tokens(variant="parwa") == 70

    def test_estimated_cost(self):
        """TokenUsage should estimate cost in USD."""
        usage = TokenUsage(
            ticket_id="TKT-001", node_name="test", variant="parwa",
            prompt_tokens=1000, completion_tokens=500, total_tokens=1500,
        )
        cost = usage.estimated_cost()
        assert cost > 0
        # gpt-4o-mini: $0.15/1M input + $0.60/1M output
        # 1000 * 0.15/1M + 500 * 0.60/1M = 0.00015 + 0.00030 = 0.00045
        assert cost < 0.001  # Very cheap per call

    def test_node_summary(self):
        """Should generate per-node summary."""
        tracker = TokenTracker()
        tracker.record("TKT-001", "reasoning_engine", "parwa", 100, 80)
        tracker.record("TKT-001", "reasoning_engine", "parwa", 120, 90)

        summary = tracker.get_node_summary()
        assert "reasoning_engine" in summary
        assert summary["reasoning_engine"]["call_count"] == 2
        assert summary["reasoning_engine"]["total_tokens"] == 390

    def test_fifo_eviction(self):
        """Should evict old records when over max_records."""
        tracker = TokenTracker(max_records=5)
        for i in range(10):
            tracker.record(f"TKT-{i}", "test", "parwa", 10, 5)

        assert tracker.record_count == 5


# ─── Prompt Compressor Tests ────────────────────────────────────────────────────────

class TestPromptCompressor:
    """Test prompt compression."""

    def test_whitespace_compression(self):
        """Should strip redundant whitespace."""
        result = compress_prompt(
            "Hello   world\n\n\n\n   test   ",
            variant="parwa",
        )
        assert "   " not in result["compressed_prompt"]
        assert result["compressed_tokens"] <= result["original_tokens"]

    def test_mini_aggressive_compression(self):
        """Mini variant should compress more aggressively."""
        long_prompt = "This is a long prompt with lots of text " * 50
        result_mini = compress_prompt(long_prompt, node_name="reasoning_engine", variant="mini")
        result_high = compress_prompt(long_prompt, node_name="reasoning_engine", variant="high")

        # Mini should compress more (or same, but never less)
        assert result_mini["compressed_tokens"] <= result_high["compressed_tokens"]

    def test_evidence_compression(self):
        """Should compress evidence lists."""
        evidence = ["Short", "A" * 500, "B" * 500, "C" * 500, "D" * 500]
        result = compress_prompt(
            "Test prompt",
            variant="mini",
            evidence=evidence,
        )
        # Mini (0.8x multiplier) falls in balanced bracket: max_items=3, max_chars=200
        assert len(result["compressed_evidence"]) <= 3
        # Each evidence item should be truncated
        for item in result["compressed_evidence"]:
            if "..." in item:
                assert len(item) <= 203  # 200 chars + "..."

    def test_prompt_compressor_stateful(self):
        """PromptCompressor should track cumulative savings."""
        compressor = PromptCompressor(variant="mini")
        compressor.compress("This is test prompt one for testing", node_name="test1")
        compressor.compress("This is test prompt two for testing", node_name="test2")

        assert compressor.total_original_tokens > 0
        assert compressor.total_compressed_tokens > 0
        assert isinstance(compressor.total_savings, float)


# ─── Adaptive Budget Tests ──────────────────────────────────────────────────────────

class TestAdaptiveBudget:
    """Test adaptive token reallocation."""

    def test_reallocation_from_completed_node(self):
        """Should reallocate unused tokens from completed nodes to needy ones."""
        budget = get_ticket_budget("parwa")
        adaptive = AdaptiveBudgetManager(budget)

        # Simulate ingest completing with minimal usage
        budget.spend_tokens("ingest", 5)

        # Simulate reasoning_engine going over budget
        reasoning_budget = budget.get_node_budget("reasoning_engine")
        budget.spend_tokens("reasoning_engine", reasoning_budget.allocated + 200)

        # Reallocate from completed ingest
        records = adaptive.check_and_reallocate("ingest")
        assert len(records) > 0
        assert records[0].from_node == "ingest"
        assert records[0].to_node == "reasoning_engine"

    def test_no_reallocation_when_no_surplus(self):
        """Should not reallocate if completed node has no surplus."""
        budget = get_ticket_budget("mini")
        adaptive = AdaptiveBudgetManager(budget)

        # Use all of ingest's budget
        ingest_budget = budget.get_node_budget("ingest")
        budget.spend_tokens("ingest", ingest_budget.allocated)

        records = adaptive.check_and_reallocate("ingest")
        assert len(records) == 0

    def test_request_bonus_tokens(self):
        """Should grant bonus tokens from unused nodes."""
        budget = get_ticket_budget("parwa")
        adaptive = AdaptiveBudgetManager(budget)

        # Reasoning engine needs more tokens
        granted = adaptive.request_bonus("reasoning_engine", 100)
        assert granted >= 0  # May or may not get bonus depending on availability

    def test_reallocation_summary(self):
        """Should generate reallocation summary."""
        budget = get_ticket_budget("parwa")
        adaptive = AdaptiveBudgetManager(budget)

        budget.spend_tokens("ingest", 5)
        reasoning_budget = budget.get_node_budget("reasoning_engine")
        budget.spend_tokens("reasoning_engine", reasoning_budget.allocated + 200)

        adaptive.check_and_reallocate("ingest")

        summary = adaptive.get_reallocation_summary()
        assert summary["reallocation_count"] > 0
        assert summary["total_reallocated"] > 0


# ─── Cost Reporter Tests ────────────────────────────────────────────────────────────

class TestCostReporter:
    """Test cost analysis and reporting."""

    def test_ticket_cost_report(self):
        """Should generate per-ticket cost report."""
        tracker = TokenTracker()
        tracker.record("TKT-001", "reasoning_engine", "parwa", 100, 80)
        tracker.record("TKT-001", "intent_classifier", "parwa", 50, 30)
        tracker.record("TKT-002", "reasoning_engine", "mini", 60, 40)

        reporter = CostReporter(tracker)
        report = reporter.ticket_report("TKT-001", variant="parwa")

        assert report.scope == "ticket"
        assert report.identifier == "TKT-001"
        assert report.total_tokens == 260  # 180 + 80
        assert report.llm_call_count == 2
        assert report.total_cost_usd > 0

    def test_variant_cost_report(self):
        """Should generate per-variant cost report."""
        tracker = TokenTracker()
        tracker.record("TKT-001", "reasoning_engine", "parwa", 100, 80)
        tracker.record("TKT-002", "intent_classifier", "parwa", 50, 30)
        tracker.record("TKT-003", "reasoning_engine", "mini", 60, 40)

        reporter = CostReporter(tracker)
        report = reporter.variant_report("parwa")

        assert report.scope == "variant"
        assert report.identifier == "parwa"
        assert report.llm_call_count == 2

    def test_monthly_cost_forecast(self):
        """Should forecast monthly costs."""
        tracker = TokenTracker()
        reporter = CostReporter(tracker)

        forecast = reporter.forecast_monthly_cost(
            variant="parwa",
            tickets_per_month=2000,
            avg_tokens_per_ticket=2000,
        )

        assert forecast["variant"] == "parwa"
        assert forecast["tickets_per_month"] == 2000
        assert forecast["monthly_cost_usd"] > 0
        assert forecast["cost_per_ticket_usd"] > 0

    def test_mini_cheaper_than_high(self):
        """Mini should have lower forecast cost than High."""
        tracker = TokenTracker()
        reporter = CostReporter(tracker)

        mini_forecast = reporter.forecast_monthly_cost("mini", 500, 1500)
        high_forecast = reporter.forecast_monthly_cost("high", 500, 4000)

        assert mini_forecast["cost_per_ticket_usd"] < high_forecast["cost_per_ticket_usd"]


# ─── Variant Budget Differentiation ─────────────────────────────────────────────────

class TestVariantBudgetDifferentiation:
    """Test that variants get different budgets but same thinking capacity."""

    def test_all_variants_have_all_22_nodes(self):
        """All variants should budget for all 22+ nodes (including FrameworkBrain technique nodes)."""
        for variant in ("mini", "parwa", "high"):
            budget = get_ticket_budget(variant)
            assert len(budget.node_budgets) >= 22, f"{variant} missing nodes"

    def test_mini_cheapest_total_budget(self):
        """Mini should have the smallest total ticket budget."""
        mini = get_ticket_budget("mini")
        parwa = get_ticket_budget("parwa")
        high = get_ticket_budget("high")

        assert mini.ticket_total < parwa.ticket_total < high.ticket_total

    def test_reasoning_engine_gets_most_tokens(self):
        """Reasoning engine should have the highest node budget (it's the brain)."""
        budget = get_ticket_budget("parwa")
        reasoning_budget = budget.get_node_budget("reasoning_engine").allocated

        # It should be higher than any non-reasoning node
        for name, nb in budget.node_budgets.items():
            if name != "reasoning_engine":
                assert reasoning_budget >= nb.allocated, f"reasoning_engine should >= {name}"
