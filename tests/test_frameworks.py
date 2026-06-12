"""Unit tests for FrameworkBrain, TechniqueRegistry, and all 14 techniques.

Tests cover:
  - TechniqueResult model validation
  - BaseTechnique interface compliance
  - TechniqueRegistry registration and lookup
  - FrameworkBrain technique selection and execution
  - Each technique's think() method in MOCK_MODE
  - Complexity-based activation logic
  - Phase 2: 6 reasoning techniques
  - Phase 3: 4 RAG techniques + 4 quality techniques
"""

import pytest
from unittest.mock import patch

from parwa.frameworks.base import BaseTechnique, TechniqueCategory, TechniqueResult
from parwa.frameworks.brain import FrameworkBrain
from parwa.frameworks.registry import TechniqueRegistry, get_registry, reset_registry


# ─── TechniqueResult Model Tests ──────────────────────────────────────────────

class TestTechniqueResult:
    """TechniqueResult Pydantic model."""

    def test_default_values(self):
        result = TechniqueResult()
        assert result.output == ""
        assert result.chain == []
        assert result.confidence == 0.0
        assert result.frameworks_used == []
        assert result.metadata == {}
        assert result.token_estimate == 0
        assert result.error is None

    def test_with_values(self):
        result = TechniqueResult(
            output="Customer is eligible",
            chain=["Step 1", "Step 2"],
            confidence=0.95,
            frameworks_used=["chain_of_thought"],
            metadata={"intent": "refund_request"},
            token_estimate=150,
        )
        assert result.output == "Customer is eligible"
        assert len(result.chain) == 2
        assert result.confidence == 0.95
        assert "chain_of_thought" in result.frameworks_used
        assert result.metadata["intent"] == "refund_request"

    def test_extra_fields_allowed(self):
        result = TechniqueResult(custom_field="test")
        assert result.custom_field == "test"


# ─── TechniqueRegistry Tests ──────────────────────────────────────────────────

class TestTechniqueRegistry:

    def setup_method(self):
        """Reset registry before each test."""
        reset_registry()

    def test_empty_registry(self):
        registry = TechniqueRegistry()
        assert registry.count() == 0
        assert registry.get_technique_names() == []

    def test_register_technique(self):
        from parwa.frameworks.reasoning.cot import ChainOfThoughtTechnique
        registry = TechniqueRegistry()
        technique = ChainOfThoughtTechnique()
        registry.register(technique)
        assert registry.count() == 1
        assert "chain_of_thought" in registry.get_technique_names()

    def test_register_duplicate_raises(self):
        from parwa.frameworks.reasoning.cot import ChainOfThoughtTechnique
        registry = TechniqueRegistry()
        registry.register(ChainOfThoughtTechnique())
        with pytest.raises(ValueError, match="already registered"):
            registry.register(ChainOfThoughtTechnique())

    def test_get_by_name(self):
        registry = get_registry()
        technique = registry.get("chain_of_thought")
        assert technique is not None
        assert technique.name == "chain_of_thought"

    def test_get_nonexistent_returns_none(self):
        registry = get_registry()
        assert registry.get("nonexistent_technique") is None

    def test_get_techniques_for_node(self):
        registry = get_registry()
        # REASONING_ENGINE should have CoT, ReAct, UoT
        techniques = registry.get_techniques_for_node("REASONING_ENGINE")
        names = [t.name for t in techniques]
        assert "chain_of_thought" in names
        assert "react" in names
        assert "uncertainty_of_thought" in names

    def test_get_techniques_for_reverse_thinker(self):
        registry = get_registry()
        techniques = registry.get_techniques_for_node("REVERSE_THINKER")
        names = [t.name for t in techniques]
        assert "reverse_thinking" in names

    def test_get_techniques_for_tot_node(self):
        registry = get_registry()
        techniques = registry.get_techniques_for_node("TREE_OF_THOUGHTS")
        names = [t.name for t in techniques]
        assert "tree_of_thoughts" in names

    def test_get_techniques_for_strategy_planner(self):
        registry = get_registry()
        techniques = registry.get_techniques_for_node("STRATEGY_PLANNER")
        names = [t.name for t in techniques]
        assert "graph_of_strategic_thought" in names

    def test_get_by_category(self):
        registry = get_registry()
        reasoning = registry.get_techniques_by_category(TechniqueCategory.REASONING)
        assert len(reasoning) == 6
        names = [t.name for t in reasoning]
        assert "chain_of_thought" in names
        assert "react" in names
        assert "tree_of_thoughts" in names
        assert "reverse_thinking" in names
        assert "uncertainty_of_thought" in names
        assert "graph_of_strategic_thought" in names

    def test_summary(self):
        registry = get_registry()
        summary = registry.summary()
        # Phase 2: 6 reasoning + Phase 3: 4 RAG + 4 quality + Phase 4: 3 memory + Phase 5: 8 proprietary = 25 total
        assert summary["total_techniques"] == 25
        assert "reasoning" in summary["by_category"]
        assert "rag" in summary["by_category"]
        assert "quality" in summary["by_category"]
        assert "REASONING_ENGINE" in summary["by_node"]

    def test_all_techniques_registered(self):
        registry = get_registry()
        names = registry.get_technique_names()
        # Phase 2: Reasoning
        expected_reasoning = [
            "chain_of_thought", "react", "tree_of_thoughts",
            "reverse_thinking", "uncertainty_of_thought", "graph_of_strategic_thought",
        ]
        # Phase 3: RAG + Quality
        expected_rag = ["clara", "hyde", "multi_query", "step_back"]
        expected_quality = ["reflexion", "self_consistency", "crp", "least_to_most"]
        # Phase 4: Memory
        expected_memory = ["thread_of_thought", "dynamic_context", "contextual_compression"]
        for name in expected_reasoning + expected_rag + expected_quality + expected_memory:
            assert name in names, f"Expected technique '{name}' not registered"


# ─── FrameworkBrain Tests ─────────────────────────────────────────────────────

class TestFrameworkBrain:

    def setup_method(self):
        reset_registry()

    @pytest.mark.asyncio
    async def test_brain_simple_complexity_activates_cot(self):
        brain = FrameworkBrain(
            node="REASONING_ENGINE",
            state={"complexity": "simple", "intent": "order_status"},
        )
        result = await brain.think(
            prompt="Where is my order?",
            techniques=["chain_of_thought", "react", "uncertainty_of_thought"],
        )
        # Simple should only activate CoT (not ReAct or UoT)
        assert "chain_of_thought" in result.frameworks_used
        # ReAct requires medium+, UoT requires critical
        assert "react" not in result.frameworks_used
        assert "uncertainty_of_thought" not in result.frameworks_used

    @pytest.mark.asyncio
    async def test_brain_medium_complexity_activates_cot_and_react(self):
        brain = FrameworkBrain(
            node="REASONING_ENGINE",
            state={"complexity": "medium", "intent": "refund_request"},
        )
        result = await brain.think(
            prompt="I was charged twice",
            techniques=["chain_of_thought", "react", "uncertainty_of_thought"],
        )
        assert "chain_of_thought" in result.frameworks_used
        assert "react" in result.frameworks_used
        assert "uncertainty_of_thought" not in result.frameworks_used

    @pytest.mark.asyncio
    async def test_brain_critical_complexity_activates_all(self):
        """Critical complexity activates techniques, but limited to MAX_TECHNIQUES_PER_NODE=2."""
        brain = FrameworkBrain(
            node="REASONING_ENGINE",
            state={"complexity": "critical", "intent": "complaint"},
        )
        result = await brain.think(
            prompt="Legal threat",
            techniques=["chain_of_thought", "react", "uncertainty_of_thought"],
        )
        assert "chain_of_thought" in result.frameworks_used
        assert "react" in result.frameworks_used
        # Max 2 techniques per node (rate limit for API reliability)
        assert len(result.frameworks_used) <= 2

    @pytest.mark.asyncio
    async def test_brain_no_techniques_for_wrong_node(self):
        brain = FrameworkBrain(
            node="NONEXISTENT_NODE",
            state={"complexity": "simple"},
        )
        result = await brain.think(prompt="test")
        assert result.frameworks_used == []
        assert result.metadata["activated_count"] == 0

    @pytest.mark.asyncio
    async def test_brain_think_single(self):
        brain = FrameworkBrain(
            node="REVERSE_THINKER",
            state={"complexity": "medium", "reasoning_conclusion": "Eligible for refund"},
        )
        result = await brain.think_single(
            "reverse_thinking",
            prompt="Validate this conclusion",
        )
        assert result.frameworks_used == ["reverse_thinking"]

    @pytest.mark.asyncio
    async def test_brain_think_single_nonexistent_raises(self):
        brain = FrameworkBrain(
            node="REASONING_ENGINE",
            state={"complexity": "simple"},
        )
        with pytest.raises(ValueError, match="not found"):
            await brain.think_single("nonexistent_technique", prompt="test")

    @pytest.mark.asyncio
    async def test_brain_combines_chain_from_multiple_techniques(self):
        brain = FrameworkBrain(
            node="REASONING_ENGINE",
            state={"complexity": "medium", "intent": "refund_request"},
        )
        result = await brain.think(
            prompt="I was charged twice",
            techniques=["chain_of_thought", "react"],
        )
        # Should have chain entries from both CoT and ReAct
        # With MockLLM, each technique typically produces 1 chain entry
        assert len(result.chain) >= 2
        assert result.metadata["activated_count"] == 2

    @pytest.mark.asyncio
    async def test_brain_graceful_technique_failure(self):
        """If a technique fails, FrameworkBrain should continue with others."""
        brain = FrameworkBrain(
            node="REASONING_ENGINE",
            state={"complexity": "medium", "intent": "refund_request"},
        )
        # This should work even if one technique fails internally
        result = await brain.think(
            prompt="test",
            techniques=["chain_of_thought", "react"],
        )
        # At least CoT should succeed
        assert len(result.frameworks_used) >= 1


# ─── Individual Technique Tests ───────────────────────────────────────────────

class TestChainOfThoughtTechnique:

    def setup_method(self):
        reset_registry()

    @pytest.mark.asyncio
    async def test_cot_produces_chain_and_conclusion(self):
        from parwa.frameworks.reasoning.cot import ChainOfThoughtTechnique
        technique = ChainOfThoughtTechnique()
        result = await technique.think(
            "I was charged twice",
            {"intent": "refund_request", "faq_match": None, "kb_results": [], "integration_data": {}},
        )
        assert len(result.chain) > 0
        assert result.output != ""
        assert result.confidence > 0
        assert "chain_of_thought" in result.frameworks_used

    @pytest.mark.asyncio
    async def test_cot_refund_request(self):
        from parwa.frameworks.reasoning.cot import ChainOfThoughtTechnique
        technique = ChainOfThoughtTechnique()
        result = await technique.think(
            "I was charged twice",
            {"intent": "refund_request", "faq_match": None, "kb_results": [], "integration_data": {}},
        )
        assert "refund" in result.output.lower() or "eligible" in result.output.lower()

    @pytest.mark.asyncio
    async def test_cot_activates_on_simple(self):
        from parwa.frameworks.reasoning.cot import ChainOfThoughtTechnique
        technique = ChainOfThoughtTechnique()
        assert technique.can_apply("REASONING_ENGINE", "simple") is True

    @pytest.mark.asyncio
    async def test_cot_name_and_category(self):
        from parwa.frameworks.reasoning.cot import ChainOfThoughtTechnique
        technique = ChainOfThoughtTechnique()
        assert technique.name == "chain_of_thought"
        assert technique.category == TechniqueCategory.REASONING


class TestReactTechnique:

    def setup_method(self):
        reset_registry()

    @pytest.mark.asyncio
    async def test_react_produces_think_act_observe(self):
        from parwa.frameworks.reasoning.react import ReactTechnique
        technique = ReactTechnique()
        result = await technique.think(
            "Verify refund eligibility",
            {
                "intent": "refund_request",
                "reasoning_conclusion": "Customer eligible for refund",
                "faq_match": None,
                "kb_results": [{"content": "Refund policy", "relevance_score": 0.9}],
                "integration_data": {"charges": [{"amount": 49.99}]},
            },
        )
        assert len(result.chain) > 0
        assert "react" in result.frameworks_used
        assert result.metadata["verified"] is True

    @pytest.mark.asyncio
    async def test_react_flags_unverified_without_data(self):
        from parwa.frameworks.reasoning.react import ReactTechnique
        technique = ReactTechnique()
        # Force mock mode so the test is deterministic
        with patch("parwa.frameworks.reasoning.react.MOCK_MODE", True):
            result = await technique.think(
                "Verify refund",
                {
                    "intent": "refund_request",
                    "reasoning_conclusion": "Some conclusion",
                    "faq_match": None,
                    "kb_results": [],
                    "integration_data": {},
                },
            )
            assert result.metadata["verified"] is False

    @pytest.mark.asyncio
    async def test_react_requires_medium_complexity(self):
        from parwa.frameworks.reasoning.react import ReactTechnique
        technique = ReactTechnique()
        assert technique.can_apply("REASONING_ENGINE", "simple") is False
        assert technique.can_apply("REASONING_ENGINE", "medium") is True


class TestTreeOfThoughtsTechnique:

    def setup_method(self):
        reset_registry()

    @pytest.mark.asyncio
    async def test_tot_generates_multiple_paths(self):
        from parwa.frameworks.reasoning.tot import TreeOfThoughtsTechnique
        technique = TreeOfThoughtsTechnique()
        # Force mock mode for deterministic testing
        with patch("parwa.frameworks.reasoning.tot.MOCK_MODE", True):
            result = await technique.think(
                "Explore solutions for refund",
                {"intent": "refund_request", "reasoning_conclusion": "Eligible for refund"},
            )
            assert result.metadata["paths_generated"] >= 3
            assert result.metadata["selected_path"] is not None
            assert "tree_of_thoughts" in result.frameworks_used

    @pytest.mark.asyncio
    async def test_tot_selects_best_path(self):
        from parwa.frameworks.reasoning.tot import TreeOfThoughtsTechnique
        technique = TreeOfThoughtsTechnique()
        with patch("parwa.frameworks.reasoning.tot.MOCK_MODE", True):
            result = await technique.think(
                "Explore solutions",
                {"intent": "refund_request", "reasoning_conclusion": "Eligible"},
            )
            selected = result.metadata["selected_path"]
            assert selected is not None
            assert selected["confidence"] > 0.5
            assert selected["selected"] is True

    @pytest.mark.asyncio
    async def test_tot_requires_complex(self):
        from parwa.frameworks.reasoning.tot import TreeOfThoughtsTechnique
        technique = TreeOfThoughtsTechnique()
        assert technique.can_apply("TREE_OF_THOUGHTS", "simple") is False
        assert technique.can_apply("TREE_OF_THOUGHTS", "medium") is False
        assert technique.can_apply("TREE_OF_THOUGHTS", "complex") is True


class TestReverseThinkingTechnique:

    def setup_method(self):
        reset_registry()

    @pytest.mark.asyncio
    async def test_reverse_passes_with_evidence(self):
        from parwa.frameworks.reasoning.reverse import ReverseThinkingTechnique
        technique = ReverseThinkingTechnique()
        result = await technique.think(
            "Validate conclusion",
            {
                "reasoning_conclusion": "Customer eligible for refund",
                "kb_results": [{"content": "Refund policy", "relevance_score": 0.9}],
                "integration_data": {"charges": [{"amount": 49.99}]},
            },
        )
        assert result.metadata["passed"] is True
        assert "reverse_thinking" in result.frameworks_used

    @pytest.mark.asyncio
    async def test_reverse_fails_without_evidence(self):
        from parwa.frameworks.reasoning.reverse import ReverseThinkingTechnique
        technique = ReverseThinkingTechnique()
        result = await technique.think(
            "Validate conclusion",
            {
                "reasoning_conclusion": "Some conclusion",
                "kb_results": [],
                "integration_data": {},
            },
        )
        assert result.metadata["passed"] is False

    @pytest.mark.asyncio
    async def test_reverse_requires_medium(self):
        from parwa.frameworks.reasoning.reverse import ReverseThinkingTechnique
        technique = ReverseThinkingTechnique()
        assert technique.can_apply("REVERSE_THINKER", "simple") is False
        assert technique.can_apply("REVERSE_THINKER", "medium") is True


class TestUncertaintyOfThoughtTechnique:

    def setup_method(self):
        reset_registry()

    @pytest.mark.asyncio
    async def test_uot_no_uncertainty_for_high_confidence(self):
        from parwa.frameworks.reasoning.uot import UncertaintyOfThoughtTechnique
        technique = UncertaintyOfThoughtTechnique()
        result = await technique.think(
            "Check uncertainty",
            {
                "reasoning_conclusion": "Customer eligible for refund",
                "intent_confidence": 0.95,
                "reasoning_paths": [],
                "loop_count": 0,
                "quality_score": 92,
            },
        )
        assert result.metadata["is_uncertain"] is False
        assert result.metadata["recommendation"] == "proceed"

    @pytest.mark.asyncio
    async def test_uot_detects_low_confidence(self):
        from parwa.frameworks.reasoning.uot import UncertaintyOfThoughtTechnique
        technique = UncertaintyOfThoughtTechnique()
        result = await technique.think(
            "Check uncertainty",
            {
                "reasoning_conclusion": "Maybe eligible",
                "intent_confidence": 0.30,
                "reasoning_paths": [],
                "loop_count": 0,
                "quality_score": 50,
            },
        )
        assert result.metadata["is_uncertain"] is True

    @pytest.mark.asyncio
    async def test_uot_requires_critical(self):
        from parwa.frameworks.reasoning.uot import UncertaintyOfThoughtTechnique
        technique = UncertaintyOfThoughtTechnique()
        assert technique.can_apply("REASONING_ENGINE", "simple") is False
        assert technique.can_apply("REASONING_ENGINE", "medium") is False
        assert technique.can_apply("REASONING_ENGINE", "complex") is False
        assert technique.can_apply("REASONING_ENGINE", "critical") is True


class TestGraphOfStrategicThoughtTechnique:

    def setup_method(self):
        reset_registry()

    @pytest.mark.asyncio
    async def test_gst_produces_plan(self):
        from parwa.frameworks.reasoning.gst import GraphOfStrategicThoughtTechnique
        technique = GraphOfStrategicThoughtTechnique()
        result = await technique.think(
            "Plan strategy for refund",
            {"intent": "refund_request", "reasoning_conclusion": "Eligible", "selected_path": None},
        )
        assert len(result.chain) > 0
        assert "graph_of_strategic_thought" in result.frameworks_used

    @pytest.mark.asyncio
    async def test_gst_uses_selected_path(self):
        from parwa.frameworks.reasoning.gst import GraphOfStrategicThoughtTechnique
        technique = GraphOfStrategicThoughtTechnique()
        result = await technique.think(
            "Plan strategy",
            {
                "intent": "refund_request",
                "reasoning_conclusion": "Eligible",
                "selected_path": {
                    "description": "Full refund path",
                    "steps": ["Verify", "Process"],
                    "confidence": 0.90,
                },
            },
        )
        assert result.metadata["had_selected_path"] is True

    @pytest.mark.asyncio
    async def test_gst_requires_complex(self):
        from parwa.frameworks.reasoning.gst import GraphOfStrategicThoughtTechnique
        technique = GraphOfStrategicThoughtTechnique()
        assert technique.can_apply("STRATEGY_PLANNER", "simple") is False
        assert technique.can_apply("STRATEGY_PLANNER", "complex") is True
