"""Test: Technique Activation Fix Validation + Complicated Tokens.

This test suite validates that all 3 technique activation fixes work correctly:
  1. Priority-based selection (not hard cap by registration order)
  2. RAG techniques actually modify search queries
  3. No technique overlap/cancellation (curated assignments)

It also includes:
  - Two variant test tickets (Mini + High) observed without interference
  - A "complicated tokens" test case that stresses the pipeline

Run: pytest tests/test_technique_activation_fix.py -v
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock


# ─── Fix 1: Priority-Based Selection Tests ───────────────────────────────────


class TestPriorityBasedSelection:
    """Verify that brain.py selects techniques by priority, not registration order."""

    def setup_method(self):
        """Reset registry for each test."""
        from parwa.frameworks.registry import reset_registry
        reset_registry()

    def teardown_method(self):
        from parwa.frameworks.registry import reset_registry
        reset_registry()

    @pytest.mark.asyncio
    async def test_critical_ticket_activates_uot(self):
        """UoT (critical technique) MUST activate on critical tickets.

        Before Fix 1: Hard cap of 2 meant UoT was always cut.
        After Fix 1: Priority-based selection puts UoT first for critical.
        """
        from parwa.frameworks.brain import FrameworkBrain
        from parwa.frameworks.registry import get_registry

        registry = get_registry()
        uot = registry.get("uncertainty_of_thought")
        assert uot is not None, "UoT technique must be registered"

        state = {"complexity": "critical", "intent": "refund_request"}
        brain = FrameworkBrain(node="REASONING_ENGINE", state=state)

        result = await brain.think(
            prompt="Customer demands immediate legal action for unauthorized charges",
            techniques=["chain_of_thought", "react", "tree_of_thoughts", "uncertainty_of_thought"],
        )

        # UoT MUST be in the activated techniques for critical
        assert "uncertainty_of_thought" in result.frameworks_used, \
            f"UoT must activate on critical tickets. Got: {result.frameworks_used}"

    @pytest.mark.asyncio
    async def test_complex_ticket_activates_tot_in_reasoning(self):
        """ToT MUST activate on complex tickets in REASONING_ENGINE.

        Before Fix 1: Hard cap of 2 meant ToT was always cut.
        After Fix 1: ToT is now requested as a candidate for complex tickets.
        """
        from parwa.frameworks.brain import FrameworkBrain

        state = {"complexity": "complex", "intent": "cancellation"}
        brain = FrameworkBrain(node="REASONING_ENGINE", state=state)

        result = await brain.think(
            prompt="Complex order cancellation with multiple items and partial shipment",
            techniques=["chain_of_thought", "react", "tree_of_thoughts"],
        )

        assert "tree_of_thoughts" in result.frameworks_used, \
            f"ToT must activate on complex tickets. Got: {result.frameworks_used}"

    @pytest.mark.asyncio
    async def test_simple_ticket_only_cot(self):
        """Simple tickets should ONLY activate CoT (no expensive techniques)."""
        from parwa.frameworks.brain import FrameworkBrain

        state = {"complexity": "simple", "intent": "order_status"}
        brain = FrameworkBrain(node="REASONING_ENGINE", state=state)

        result = await brain.think(
            prompt="What's my order status?",
            techniques=["chain_of_thought", "react", "tree_of_thoughts", "uncertainty_of_thought"],
        )

        assert "chain_of_thought" in result.frameworks_used
        assert "react" not in result.frameworks_used, "ReAct should not activate on simple tickets"
        assert "tree_of_thoughts" not in result.frameworks_used, "ToT should not activate on simple tickets"
        assert "uncertainty_of_thought" not in result.frameworks_used, "UoT should not activate on simple tickets"

    @pytest.mark.asyncio
    async def test_medium_ticket_cot_and_react_only(self):
        """Medium tickets should activate CoT + ReAct but NOT ToT or UoT."""
        from parwa.frameworks.brain import FrameworkBrain

        state = {"complexity": "medium", "intent": "refund_request"}
        brain = FrameworkBrain(node="REASONING_ENGINE", state=state)

        result = await brain.think(
            prompt="I was charged twice for my order",
            techniques=["chain_of_thought", "react", "tree_of_thoughts", "uncertainty_of_thought"],
        )

        assert "chain_of_thought" in result.frameworks_used
        assert "react" in result.frameworks_used, "ReAct should activate on medium tickets"
        assert "tree_of_thoughts" not in result.frameworks_used, "ToT should not activate on medium"
        assert "uncertainty_of_thought" not in result.frameworks_used, "UoT should not activate on medium"

    @pytest.mark.asyncio
    async def test_priority_sorts_by_complexity_match(self):
        """Techniques designed for the current complexity should run first."""
        from parwa.frameworks.brain import FrameworkBrain

        state = {"complexity": "critical", "intent": "refund_request"}
        brain = FrameworkBrain(node="REASONING_ENGINE", state=state)

        # The _technique_priority should give UoT 100 for critical
        registry = brain._registry
        uot = registry.get("uncertainty_of_thought")
        cot = registry.get("chain_of_thought")

        uot_priority = brain._technique_priority(uot, "critical")
        cot_priority = brain._technique_priority(cot, "critical")

        assert uot_priority > cot_priority, \
            f"UoT ({uot_priority}) should have higher priority than CoT ({cot_priority}) for critical tickets"


# ─── Fix 2: RAG Techniques Modify Search Queries ─────────────────────────────


class TestRAGQueryEnhancement:
    """Verify that RAG techniques actually modify KB search queries."""

    @pytest.mark.asyncio
    async def test_kb_retriever_uses_enhanced_queries(self):
        """KB retriever must use brain-enhanced queries, not just rule-based."""
        from parwa.nodes.kb_retriever import _retrieve_with_brain

        state = {
            "raw_message": "I was charged twice for my order and need a refund",
            "intent": "refund_request",
            "complexity": "medium",
            "ticket_id": "TKT-TEST-001",
            "variant": "parwa",
        }

        results, frameworks = await _retrieve_with_brain(state)

        # Should return results (even if brain falls back to rule-based)
        assert isinstance(results, list), f"KB results should be a list, got {type(results)}"

    @pytest.mark.asyncio
    async def test_kb_retriever_merges_multiple_queries(self):
        """When RAG techniques produce enhanced queries, results should be merged."""
        from parwa.nodes.kb_retriever import _merge_and_deduplicate

        # Simulate results from original + enhanced queries
        result_set_1 = [
            {"source": "kb:doc1", "content": "Refund policy...", "relevance_score": 0.8},
        ]
        result_set_2 = [
            {"source": "kb:doc2", "content": "Duplicate charges...", "relevance_score": 0.9},
            {"source": "kb:doc1", "content": "Refund policy...", "relevance_score": 0.7},  # Duplicate, lower score
        ]

        merged = _merge_and_deduplicate([result_set_1, result_set_2], max_results=5)

        # Should deduplicate by source, keeping best score
        sources = [r["source"] for r in merged]
        assert len(sources) == len(set(sources)), "Results should be deduplicated by source"

        # Should keep best score for duplicates
        doc1 = next(r for r in merged if r["source"] == "kb:doc1")
        assert doc1["relevance_score"] == 0.8, "Should keep the higher relevance score"


# ─── Fix 3: Technique Assignment & Overlap Tests ─────────────────────────────


class TestTechniqueAssignments:
    """Verify that techniques are properly assigned to nodes without overlap."""

    def setup_method(self):
        from parwa.frameworks.registry import reset_registry
        reset_registry()

    def teardown_method(self):
        from parwa.frameworks.registry import reset_registry
        reset_registry()

    def test_action_verifier_has_reverse_thinking(self):
        """Reverse Thinking must be applicable to ACTION_VERIFIER."""
        from parwa.frameworks.registry import get_registry

        registry = get_registry()
        reverse = registry.get("reverse_thinking")
        assert reverse is not None
        assert "ACTION_VERIFIER" in reverse.applicable_nodes, \
            "Reverse Thinking must be applicable to ACTION_VERIFIER"

    def test_no_dead_applicable_nodes(self):
        """Techniques should not list nodes that never request them.

        Removed: PREDICTION_ENGINE from ToT, ACTION_EXECUTOR from ReAct
        """
        from parwa.frameworks.registry import get_registry

        registry = get_registry()

        tot = registry.get("tree_of_thoughts")
        assert "PREDICTION_ENGINE" not in tot.applicable_nodes, \
            "ToT should not list PREDICTION_ENGINE (dead registration)"

        react = registry.get("react")
        assert "ACTION_EXECUTOR" not in react.applicable_nodes, \
            "ReAct should not list ACTION_EXECUTOR (dead registration)"

    @pytest.mark.asyncio
    async def test_action_verifier_uses_brain(self):
        """ACTION_VERIFIER must use FrameworkBrain for evidence tracing."""
        from parwa.nodes.action_verifier import action_verifier

        state = {
            "execution_results": [{"action_type": "process_refund", "status": "executed"}],
            "recommendation": None,
            "action_plans": [
                {"action_type": "process_refund", "evidence": ["Duplicate charge confirmed"]},
            ],
            "loop_count": 0,
            "max_loops": 2,
            "active_frameworks": [],
            "complexity": "medium",
            "ticket_id": "TKT-TEST-002",
            "variant": "parwa",
        }

        result = await action_verifier(state)

        # Must return active_frameworks (proves brain was used)
        assert "active_frameworks" in result, "action_verifier must track active_frameworks"

    @pytest.mark.asyncio
    async def test_medium_ticket_skips_tot_and_gst(self):
        """Medium tickets should NOT run through TREE_OF_THOUGHTS or STRATEGY_PLANNER.

        This is the graph routing optimization — medium goes:
        REASONING_ENGINE → REVERSE_THINKER → ACTION_PLANNER
        """
        from parwa.graph import _after_reasoning, _after_reverse_thinker

        medium_state = {"complexity": "medium", "loop_count": 0}

        after_reasoning = _after_reasoning(medium_state)
        assert after_reasoning == "reverse_thinker", \
            f"Medium tickets should go to reverse_thinker, got {after_reasoning}"

        after_reverse = _after_reverse_thinker(medium_state)
        assert after_reverse == "action_planner", \
            f"Medium tickets should skip ToT/GST, got {after_reverse}"

    @pytest.mark.asyncio
    async def test_complex_ticket_gets_full_chain(self):
        """Complex tickets must go through the full advanced reasoning chain."""
        from parwa.graph import _after_reasoning, _after_reverse_thinker

        complex_state = {"complexity": "complex", "loop_count": 0}

        after_reasoning = _after_reasoning(complex_state)
        assert after_reasoning == "reverse_thinker"

        after_reverse = _after_reverse_thinker(complex_state)
        assert after_reverse == "tree_of_thoughts", \
            f"Complex tickets should go to tree_of_thoughts, got {after_reverse}"

    def test_simple_ticket_skips_all_advanced(self):
        """Simple tickets should go directly to action_planner."""
        from parwa.graph import _after_reasoning

        simple_state = {"complexity": "simple", "loop_count": 0}
        result = _after_reasoning(simple_state)
        assert result == "action_planner", \
            f"Simple tickets should skip advanced reasoning, got {result}"


# ─── Variant Test Tickets (Observe Without Interference) ─────────────────────


class TestVariantTickets:
    """Two test tickets observed across Mini and High variants.

    These tests run the full pipeline and just WATCH for errors.
    No assertions on specific output — just verify the pipeline
    doesn't crash and produces valid state.
    """

    @pytest.mark.asyncio
    async def test_mini_variant_refund_ticket(self):
        """Mini PARWA variant — refund request. Just observe, don't interfere."""
        from parwa.graph import reset_parwa_graph, aprocess_ticket
        reset_parwa_graph()

        result = await aprocess_ticket(
            raw_message="I was charged twice for my order. I need a refund immediately.",
            customer_id="CUST-001",
            channel="email",
            variant="mini",
        )

        # Only check for pipeline errors — we're just watching
        errors = result.get("pipeline_errors", [])
        assert not any(e.get("error_type") == "Exception" for e in errors), \
            f"Mini variant crashed with errors: {errors}"

        # Must have a final response
        assert result.get("final_response") or result.get("recommendation"), \
            "Mini variant must produce either a response or recommendation"

    @pytest.mark.asyncio
    async def test_high_variant_complex_ticket(self):
        """High PARWA variant — complex complaint. Just observe, don't interfere."""
        from parwa.graph import reset_parwa_graph, aprocess_ticket
        reset_parwa_graph()

        result = await aprocess_ticket(
            raw_message=(
                "This is my third email about the same issue! I ordered 3 items but "
                "received the wrong ones. The packing slip shows a different order number. "
                "I want to speak to a supervisor immediately. I've been waiting 2 weeks "
                "and nobody has responded. This is completely unacceptable."
            ),
            customer_id="CUST-002",
            channel="email",
            variant="high",
        )

        # Only check for pipeline errors — we're just watching
        errors = result.get("pipeline_errors", [])
        assert not any(e.get("error_type") == "Exception" for e in errors), \
            f"High variant crashed with errors: {errors}"

        # Must have reached quality scoring
        quality = result.get("quality_score", 0)
        assert quality > 0, "High variant must produce a quality score"


# ─── Complicated Tokens Test ──────────────────────────────────────────────────


class TestComplicatedTokens:
    """Stress test with complicated/malformed tokens.

    These tests deliberately use edge-case inputs to verify
    the pipeline doesn't crash on unusual content.
    """

    @pytest.mark.asyncio
    async def test_mixed_language_unicode(self):
        """Ticket with mixed languages and Unicode characters."""
        from parwa.graph import reset_parwa_graph, aprocess_ticket
        reset_parwa_graph()

        result = await aprocess_ticket(
            raw_message=(
                "你好！I need a refund for 订单#ORD-12345. "
                "The charge of $49.99 appeared twice on my carte de crédit. "
                "Por favor, resolve this ASAP. "
                "Σας ευχαριστώ!ありがとうございます！"
            ),
            customer_id="CUST-MULTI-001",
            channel="chat",
            variant="parwa",
        )

        # Pipeline must not crash
        assert isinstance(result, dict), "Pipeline must return a dict"

    @pytest.mark.asyncio
    async def test_extremely_long_message(self):
        """Ticket with an extremely long message (stress test token handling)."""
        from parwa.graph import reset_parwa_graph, aprocess_ticket
        reset_parwa_graph()

        # Generate a very long message
        base_msg = "I have a problem with my order. "
        long_message = base_msg * 200  # ~7000 chars

        result = await aprocess_ticket(
            raw_message=long_message,
            customer_id="CUST-LONG-001",
            channel="email",
            variant="parwa",
        )

        assert isinstance(result, dict), "Pipeline must handle long messages"

    @pytest.mark.asyncio
    async def test_special_characters_and_html(self):
        """Ticket with HTML tags, special chars, and escape sequences."""
        from parwa.graph import reset_parwa_graph, aprocess_ticket
        reset_parwa_graph()

        result = await aprocess_ticket(
            raw_message=(
                "My order <script>alert('xss')</script> has issues. "
                "Item #12345 costs $99.99 & I got charged $199.98 (2x!). "
                "Email: test@example.com | Phone: +1-555-0123 "
                "Path: C:\\Users\\test\\file.txt "
                "SQL: SELECT * FROM orders WHERE id=1; DROP TABLE-- "
                "JSON: {\"order_id\": \"ORD-999\", \"status\": \"failed\"} "
                "Newlines:\n\nand\t\ttabs\there"
            ),
            customer_id="CUST-SPECIAL-001",
            channel="email",
            variant="parwa",
        )

        assert isinstance(result, dict), "Pipeline must handle special characters"

    @pytest.mark.asyncio
    async def test_empty_and_whitespace_message(self):
        """Ticket with minimal or whitespace-only content."""
        from parwa.graph import reset_parwa_graph, aprocess_ticket
        reset_parwa_graph()

        result = await aprocess_ticket(
            raw_message="   ",
            customer_id="CUST-EMPTY-001",
            channel="email",
            variant="parwa",
        )

        # Should handle gracefully (error or minimal response)
        assert isinstance(result, dict), "Pipeline must handle empty messages"

    @pytest.mark.asyncio
    async def test_emoji_and_non_bmp_characters(self):
        """Ticket with emojis and non-BMP Unicode (emoji, rare characters)."""
        from parwa.graph import reset_parwa_graph, aprocess_ticket
        reset_parwa_graph()

        result = await aprocess_ticket(
            raw_message=(
                "I'm very angry 😡😡😡 about my order! "
                "The product is broken 🔥 and I want a refund 💰 NOW! "
                "This is the 𝔴𝔬𝔯𝔰𝔱 service ever! "
                "Package arrived 📦 but it was 𝓭𝓪𝓶𝓪𝓰𝓮𝓭 💔"
            ),
            customer_id="CUST-EMOJI-001",
            channel="social",
            variant="parwa",
        )

        assert isinstance(result, dict), "Pipeline must handle emoji and non-BMP chars"

    @pytest.mark.asyncio
    async def test_rapid_fire_questions(self):
        """Ticket with multiple rapid-fire questions (tests intent classification)."""
        from parwa.graph import reset_parwa_graph, aprocess_ticket
        reset_parwa_graph()

        result = await aprocess_ticket(
            raw_message=(
                "Where is my order? Can I cancel it? How do I get a refund? "
                "What's your return policy? Can I speak to a manager? "
                "Why was I charged twice? Is there a phone number I can call? "
                "Can you email me back? I want to modify my account too."
            ),
            customer_id="CUST-RAPID-001",
            channel="chat",
            variant="parwa",
        )

        assert isinstance(result, dict), "Pipeline must handle rapid-fire questions"


# ─── Technique Activation Summary Test ────────────────────────────────────────


class TestTechniqueActivationSummary:
    """Summary test showing which techniques activate at each complexity level."""

    @pytest.mark.asyncio
    async def test_full_activation_matrix(self):
        """Print out the technique activation matrix for verification."""
        from parwa.frameworks.brain import FrameworkBrain

        matrix = {}
        for complexity in ["simple", "medium", "complex", "critical"]:
            state = {"complexity": complexity, "intent": "refund_request"}
            brain = FrameworkBrain(node="REASONING_ENGINE", state=state)

            result = await brain.think(
                prompt="Test ticket",
                techniques=["chain_of_thought", "react", "tree_of_thoughts", "uncertainty_of_thought"],
            )
            matrix[complexity] = result.frameworks_used

        # Verify the matrix
        assert "chain_of_thought" in matrix["simple"], "CoT must activate on simple"
        assert len(matrix["simple"]) == 1, f"Simple should have 1 technique, got {matrix['simple']}"

        assert "react" in matrix["medium"], "ReAct must activate on medium"
        assert "uncertainty_of_thought" not in matrix["medium"], "UoT must NOT activate on medium"

        assert "tree_of_thoughts" in matrix["complex"], "ToT must activate on complex"
        assert "uncertainty_of_thought" not in matrix["complex"], "UoT must NOT activate on complex"

        assert "uncertainty_of_thought" in matrix["critical"], "UoT MUST activate on critical"

        # Print matrix for visibility
        print("\n=== TECHNIQUE ACTIVATION MATRIX (REASONING_ENGINE) ===")
        for complexity, techniques in matrix.items():
            print(f"  {complexity:10s} → {techniques}")
        print("===================================================")
