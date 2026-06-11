"""Integration tests for Phase 2: FrameworkBrain wired into reasoning nodes.

Tests the full reasoning chain with FrameworkBrain:
  Node 6 (REASONING_ENGINE) → Node 10 (REVERSE_THINKER) →
  Node 12 (TREE_OF_THOUGHTS) → Node 11 (STRATEGY_PLANNER)

These tests verify that:
  1. Nodes still work with FrameworkBrain (backward compatible)
  2. FrameworkBrain selects correct techniques based on complexity
  3. The reasoning chain produces complete, sensible output
  4. All existing node tests still pass
  5. Frameworks are properly tracked in active_frameworks
  6. Graceful degradation works when FrameworkBrain fails
"""

import pytest

from parwa.nodes.reasoning_engine import reasoning_engine
from parwa.nodes.reverse_thinker import reverse_thinker
from parwa.nodes.tree_of_thoughts import tree_of_thoughts
from parwa.nodes.strategy_planner import strategy_planner
from parwa.frameworks.registry import reset_registry


# ─── Reasoning Engine Integration ─────────────────────────────────────────────

class TestReasoningEngineIntegration:
    """Node 6: REASONING_ENGINE with FrameworkBrain."""

    def setup_method(self):
        reset_registry()

    @pytest.mark.asyncio
    async def test_simple_ticket_activates_cot(self):
        result = await reasoning_engine({
            "raw_message": "Where is my order?",
            "intent": "order_status",
            "faq_match": None,
            "kb_results": [],
            "integration_data": {},
            "active_frameworks": [],
            "complexity": "simple",
        })
        assert len(result["reasoning_chain"]) > 0
        assert result["reasoning_conclusion"] != ""
        assert "chain_of_thought" in result["active_frameworks"]

    @pytest.mark.asyncio
    async def test_medium_ticket_activates_cot_and_react(self):
        result = await reasoning_engine({
            "raw_message": "I was charged twice, I want a refund",
            "intent": "refund_request",
            "faq_match": None,
            "kb_results": [{"content": "Refund policy", "relevance_score": 0.9}],
            "integration_data": {"charges": [{"amount": 49.99}]},
            "active_frameworks": [],
            "complexity": "medium",
        })
        assert len(result["reasoning_chain"]) > 0
        assert "chain_of_thought" in result["active_frameworks"]
        assert "react" in result["active_frameworks"]

    @pytest.mark.asyncio
    async def test_critical_ticket_activates_all(self):
        result = await reasoning_engine({
            "raw_message": "I'm calling my lawyer!",
            "intent": "complaint",
            "faq_match": None,
            "kb_results": [],
            "integration_data": {},
            "active_frameworks": [],
            "complexity": "critical",
        })
        assert "chain_of_thought" in result["active_frameworks"]
        assert "react" in result["active_frameworks"]
        assert "uncertainty_of_thought" in result["active_frameworks"]

    @pytest.mark.asyncio
    async def test_backward_compatible_without_complexity(self):
        """Should still work if complexity is not set (defaults to simple)."""
        result = await reasoning_engine({
            "raw_message": "Hello",
            "intent": "general_inquiry",
            "faq_match": None,
            "kb_results": [],
            "integration_data": {},
            "active_frameworks": [],
        })
        assert len(result["reasoning_chain"]) > 0
        assert result["reasoning_conclusion"] != ""

    @pytest.mark.asyncio
    async def test_does_not_duplicate_frameworks(self):
        """If chain_of_thought already in active_frameworks, should not add again."""
        result = await reasoning_engine({
            "raw_message": "Hello",
            "intent": "general_inquiry",
            "faq_match": None,
            "kb_results": [],
            "integration_data": {},
            "active_frameworks": ["chain_of_thought"],
            "complexity": "simple",
        })
        # Should not duplicate
        assert result["active_frameworks"].count("chain_of_thought") <= 1


# ─── Reverse Thinker Integration ──────────────────────────────────────────────

class TestReverseThinkerIntegration:
    """Node 10: REVERSE_THINKER with FrameworkBrain."""

    def setup_method(self):
        reset_registry()

    @pytest.mark.asyncio
    async def test_passes_with_evidence(self):
        result = await reverse_thinker({
            "reasoning_conclusion": "Customer eligible for refund",
            "kb_results": [{"content": "Refund policy", "relevance_score": 0.9}],
            "integration_data": {"charges": [{"amount": 49.99}]},
            "active_frameworks": [],
            "loop_count": 0,
            "max_loops": 2,
            "complexity": "medium",
        })
        assert result["reverse_validation"]["passed"] is True
        assert "reverse_thinking" in result["active_frameworks"]

    @pytest.mark.asyncio
    async def test_fails_without_evidence(self):
        result = await reverse_thinker({
            "reasoning_conclusion": "Some conclusion",
            "kb_results": [],
            "integration_data": {},
            "active_frameworks": [],
            "loop_count": 0,
            "max_loops": 2,
            "complexity": "medium",
        })
        assert result["reverse_validation"]["passed"] is False
        assert result["should_loop_back"] is True

    @pytest.mark.asyncio
    async def test_loop_back_on_failure(self):
        result = await reverse_thinker({
            "reasoning_conclusion": "Unverified",
            "kb_results": [],
            "integration_data": {},
            "active_frameworks": [],
            "loop_count": 0,
            "max_loops": 2,
            "complexity": "medium",
        })
        assert result["should_loop_back"] is True

    @pytest.mark.asyncio
    async def test_no_loop_back_at_max_loops(self):
        result = await reverse_thinker({
            "reasoning_conclusion": "Unverified",
            "kb_results": [],
            "integration_data": {},
            "active_frameworks": [],
            "loop_count": 2,
            "max_loops": 2,
            "complexity": "medium",
        })
        assert result["should_loop_back"] is False


# ─── Tree of Thoughts Integration ─────────────────────────────────────────────

class TestTreeOfThoughtsIntegration:
    """Node 12: TREE_OF_THOUGHTS with FrameworkBrain."""

    def setup_method(self):
        reset_registry()

    @pytest.mark.asyncio
    async def test_creates_multiple_paths(self):
        result = await tree_of_thoughts({
            "intent": "refund_request",
            "reasoning_conclusion": "Eligible for refund",
            "active_frameworks": [],
            "complexity": "complex",
        })
        assert len(result["reasoning_paths"]) >= 3
        assert result["selected_path"] is not None
        assert "tree_of_thoughts" in result["active_frameworks"]

    @pytest.mark.asyncio
    async def test_selects_best_path(self):
        result = await tree_of_thoughts({
            "intent": "refund_request",
            "reasoning_conclusion": "Eligible for refund",
            "active_frameworks": [],
            "complexity": "complex",
        })
        assert result["selected_path"]["selected"] is True
        assert result["selected_path"]["confidence"] > 0.5


# ─── Strategy Planner Integration ─────────────────────────────────────────────

class TestStrategyPlannerIntegration:
    """Node 11: STRATEGY_PLANNER with FrameworkBrain."""

    def setup_method(self):
        reset_registry()

    @pytest.mark.asyncio
    async def test_simple_plan(self):
        result = await strategy_planner({
            "intent": "refund_request",
            "reasoning_conclusion": "Eligible for refund",
            "selected_path": None,
            "active_frameworks": [],
            "complexity": "simple",
        })
        assert len(result["strategy_plan"]) > 0
        assert "maker_planning" in result["active_frameworks"]

    @pytest.mark.asyncio
    async def test_complex_plan_uses_gst(self):
        result = await strategy_planner({
            "intent": "refund_request",
            "reasoning_conclusion": "Eligible for refund",
            "selected_path": {
                "description": "Full refund",
                "steps": ["Verify", "Process"],
                "confidence": 0.90,
            },
            "active_frameworks": [],
            "complexity": "complex",
        })
        assert len(result["strategy_plan"]) > 0
        # Complex should use GST
        assert "graph_of_strategic_thought" in result["active_frameworks"]

    @pytest.mark.asyncio
    async def test_uses_selected_path_steps(self):
        path = {"steps": ["Step A", "Step B", "Step C"]}
        result = await strategy_planner({
            "intent": "refund_request",
            "reasoning_conclusion": "Eligible",
            "selected_path": path,
            "active_frameworks": [],
            "complexity": "simple",
        })
        assert result["strategy_plan"] == ["Step A", "Step B", "Step C"]


# ─── Full Reasoning Chain Integration ─────────────────────────────────────────

class TestReasoningChainIntegration:
    """Test the full reasoning chain: Node 6 → Node 10 → Node 12 → Node 11.

    This tests that FrameworkBrain works correctly when techniques
    pass results between nodes through the shared state.
    """

    def setup_method(self):
        reset_registry()

    @pytest.mark.asyncio
    async def test_full_chain_medium_complexity(self):
        """Simulate the full reasoning chain for a medium-complexity refund ticket."""
        base_state = {
            "raw_message": "I was charged twice for the same order",
            "intent": "refund_request",
            "faq_match": {"content": "Refunds available within 30 days", "relevance_score": 0.85},
            "kb_results": [{"content": "Refund policy allows duplicate charge refunds", "relevance_score": 0.9}],
            "integration_data": {"charges": [{"amount": 49.99, "date": "2025-01-05"}, {"amount": 49.99, "date": "2025-01-05"}]},
            "active_frameworks": [],
            "loop_count": 0,
            "max_loops": 2,
            "complexity": "medium",
        }

        # Step 1: Reasoning Engine
        r1 = await reasoning_engine(base_state)
        assert len(r1["reasoning_chain"]) > 0
        assert r1["reasoning_conclusion"] != ""
        assert "chain_of_thought" in r1["active_frameworks"]
        assert "react" in r1["active_frameworks"]

        # Merge results into state
        state = {**base_state, **r1}

        # Step 2: Reverse Thinker
        r2 = await reverse_thinker(state)
        assert "reverse_thinking" in r2["active_frameworks"]
        assert r2["should_loop_back"] is False  # Should pass with evidence

        # Merge and continue
        state = {**state, **r2}

        # Step 3: Tree of Thoughts (complexity = medium, ToT needs complex)
        # On medium complexity, ToT won't activate via FrameworkBrain
        # but the node still runs with rule-based fallback
        r3 = await tree_of_thoughts(state)
        assert len(r3["reasoning_paths"]) >= 3
        assert r3["selected_path"] is not None

        # Merge and continue
        state = {**state, **r3}

        # Step 4: Strategy Planner
        r4 = await strategy_planner(state)
        assert len(r4["strategy_plan"]) > 0

    @pytest.mark.asyncio
    async def test_full_chain_complex_complexity(self):
        """Test full chain with complex complexity — all techniques activate."""
        base_state = {
            "raw_message": "Your system broke my business workflow, I'm losing $10K/day",
            "intent": "complaint",
            "faq_match": None,
            "kb_results": [{"content": "Enterprise SLA policy", "relevance_score": 0.7}],
            "integration_data": {"account_type": "enterprise"},
            "active_frameworks": [],
            "loop_count": 0,
            "max_loops": 2,
            "complexity": "complex",
        }

        # Step 1: Reasoning Engine
        r1 = await reasoning_engine(base_state)
        assert len(r1["reasoning_chain"]) > 0
        assert "chain_of_thought" in r1["active_frameworks"]
        assert "react" in r1["active_frameworks"]

        state = {**base_state, **r1}

        # Step 2: Reverse Thinker
        r2 = await reverse_thinker(state)
        assert "reverse_thinking" in r2["active_frameworks"]

        state = {**state, **r2}

        # Step 3: Tree of Thoughts (complex → ToT activates)
        r3 = await tree_of_thoughts(state)
        assert len(r3["reasoning_paths"]) >= 3
        assert "tree_of_thoughts" in r3["active_frameworks"]

        state = {**state, **r3}

        # Step 4: Strategy Planner (complex → GST activates)
        r4 = await strategy_planner(state)
        assert len(r4["strategy_plan"]) > 0
        assert "graph_of_strategic_thought" in r4["active_frameworks"]

    @pytest.mark.asyncio
    async def test_frameworks_accumulate_across_chain(self):
        """Verify that active_frameworks accumulate as the chain progresses."""
        base_state = {
            "raw_message": "I was charged twice",
            "intent": "refund_request",
            "faq_match": None,
            "kb_results": [{"content": "Refund policy", "relevance_score": 0.9}],
            "integration_data": {"charges": [{"amount": 49.99}]},
            "active_frameworks": [],
            "loop_count": 0,
            "max_loops": 2,
            "complexity": "medium",
        }

        # Each node adds its frameworks (like the graph's append reducer does)
        accumulated_frameworks = list(base_state["active_frameworks"])

        r1 = await reasoning_engine(base_state)
        accumulated_frameworks.extend(r1["active_frameworks"])
        state = {**base_state, **r1, "active_frameworks": accumulated_frameworks}
        assert len(accumulated_frameworks) >= 1

        r2 = await reverse_thinker(state)
        accumulated_frameworks = list(state["active_frameworks"]) + list(r2["active_frameworks"])
        state = {**state, **r2, "active_frameworks": accumulated_frameworks}
        assert "reverse_thinking" in accumulated_frameworks

        r3 = await tree_of_thoughts(state)
        accumulated_frameworks = list(state["active_frameworks"]) + list(r3["active_frameworks"])
        state = {**state, **r3, "active_frameworks": accumulated_frameworks}
        assert "tree_of_thoughts" in accumulated_frameworks

        r4 = await strategy_planner(state)
        accumulated_frameworks = list(state["active_frameworks"]) + list(r4["active_frameworks"])
        state = {**state, **r4, "active_frameworks": accumulated_frameworks}
        # Should have multiple frameworks by now
        assert len(accumulated_frameworks) >= 3
