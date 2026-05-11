"""Week 10.5 Integration Tests — Day 20

Comprehensive integration test suite verifying all 14 AI techniques work
correctly with variant gating, tier distribution, module imports, node
activation, and BC-008 never-crash compliance.

Variant gating:
  - Mini PARWA  → Tier 1 only  (CLARA, CRP, GSD)
  - PARWA       → Tier 1 + Tier 2
  - PARWA High  → Tier 1 + Tier 2 + Tier 3

Run:
  cd /home/z/my-project/parwa && PYTHONPATH=backend python -m pytest \
    tests/unit/test_week10_5_integration.py -v --tb=short
"""

import pytest

from backend.app.core.technique_router import (
    TechniqueID,
    TechniqueTier,
    TECHNIQUE_REGISTRY,
    TechniqueRouter,
    QuerySignals,
)
from backend.app.core.techniques.base import (
    ConversationState,
    GSDState,
)

# ─────────────────────────────────────────────────────────────────────
# Mapping of TechniqueID → (module_path, NodeClassName)
# CLARA and GSD are special: CLARA is quality gate (F-057),
# GSD is state machine (F-053). Neither has a technique Node class.
# ─────────────────────────────────────────────────────────────────────

TECHNIQUE_MODULE_MAP = {
    TechniqueID.CRP: ("backend.app.core.techniques.stub_nodes", "CRPNode"),
    TechniqueID.CLARA: ("backend.app.core.technique_router", None),  # quality gate, no Node
    TechniqueID.GSD: ("backend.app.core.techniques.base", None),  # state machine, no Node
    TechniqueID.CHAIN_OF_THOUGHT: (
        "backend.app.core.techniques.chain_of_thought", "ChainOfThoughtNode"
    ),
    TechniqueID.REVERSE_THINKING: (
        "backend.app.core.techniques.reverse_thinking", "ReverseThinkingNode"
    ),
    TechniqueID.REACT: ("backend.app.core.techniques.react", "ReActNode"),
    TechniqueID.STEP_BACK: ("backend.app.core.techniques.step_back", "StepBackNode"),
    TechniqueID.THREAD_OF_THOUGHT: (
        "backend.app.core.techniques.thread_of_thought", "ThreadOfThoughtNode"
    ),
    TechniqueID.GST: ("backend.app.core.techniques.gst", "GSTNode"),
    TechniqueID.UNIVERSE_OF_THOUGHTS: (
        "backend.app.core.techniques.universe_of_thoughts", "UniverseOfThoughtsNode"
    ),
    TechniqueID.TREE_OF_THOUGHTS: (
        "backend.app.core.techniques.tree_of_thoughts", "TreeOfThoughtsNode"
    ),
    TechniqueID.SELF_CONSISTENCY: (
        "backend.app.core.techniques.self_consistency", "SelfConsistencyNode"
    ),
    TechniqueID.REFLEXION: ("backend.app.core.techniques.reflexion", "ReflexionNode"),
    TechniqueID.LEAST_TO_MOST: (
        "backend.app.core.techniques.least_to_most", "LeastToMostNode"
    ),
}

# Techniques that have dedicated Node classes (12 of 14)
TECHNIQUES_WITH_NODES = {
    tid: (mod, cls)
    for tid, (mod, cls) in TECHNIQUE_MODULE_MAP.items()
    if cls is not None
}

# Signal configurations that should cause each technique to activate
ACTIVATION_SIGNALS = {
    TechniqueID.CRP: {},  # Always active
    TechniqueID.CHAIN_OF_THOUGHT: {"query_complexity": 0.6},
    TechniqueID.REVERSE_THINKING: {"confidence_score": 0.4},
    TechniqueID.REACT: {"external_data_required": True},
    TechniqueID.STEP_BACK: {"confidence_score": 0.4},
    TechniqueID.THREAD_OF_THOUGHT: {"turn_count": 8},
    TechniqueID.GST: {"is_strategic_decision": True},
    TechniqueID.UNIVERSE_OF_THOUGHTS: {"customer_tier": "vip"},
    TechniqueID.TREE_OF_THOUGHTS: {"resolution_path_count": 5},
    TechniqueID.SELF_CONSISTENCY: {"monetary_value": 200.0},
    TechniqueID.REFLEXION: {"previous_response_status": "rejected"},
    TechniqueID.LEAST_TO_MOST: {"query_complexity": 0.9},
}


# ═══════════════════════════════════════════════════════════════════
# 1. TestTechniqueRegistryCompleteness
# ═══════════════════════════════════════════════════════════════════


class TestTechniqueRegistryCompleteness:
    """Verify TECHNIQUE_REGISTRY is complete and well-formed."""

    def test_all_14_techniques_registered(self):
        """TECHNIQUE_REGISTRY must have exactly 14 entries."""
        assert len(TECHNIQUE_REGISTRY) == 14, (
            f"Expected 14 techniques, got {len(TECHNIQUE_REGISTRY)}"
        )

        expected_ids = {tid for tid in TechniqueID}
        registered_ids = set(TECHNIQUE_REGISTRY.keys())
        assert expected_ids == registered_ids, (
            f"Registry mismatch. Missing: {expected_ids - registered_ids}, "
            f"Extra: {registered_ids - expected_ids}"
        )

    def test_all_techniques_have_valid_tier(self):
        """Each technique must have tier_1, tier_2, or tier_3."""
        valid_tiers = {TechniqueTier.TIER_1, TechniqueTier.TIER_2, TechniqueTier.TIER_3}
        for tid, info in TECHNIQUE_REGISTRY.items():
            assert info.tier in valid_tiers, (
                f"{tid.value} has invalid tier: {info.tier}"
            )

    def test_all_techniques_have_description(self):
        """No technique should have an empty description."""
        for tid, info in TECHNIQUE_REGISTRY.items():
            assert info.description and info.description.strip(), (
                f"{tid.value} has empty description"
            )

    def test_all_techniques_have_positive_time_budget(self):
        """Every technique must have time_budget_ms > 0."""
        for tid, info in TECHNIQUE_REGISTRY.items():
            assert info.time_budget_ms > 0, (
                f"{tid.value} has time_budget_ms={info.time_budget_ms}"
            )

    def test_all_techniques_have_positive_estimated_tokens(self):
        """Every technique must have estimated_tokens > 0."""
        for tid, info in TECHNIQUE_REGISTRY.items():
            assert info.estimated_tokens > 0, (
                f"{tid.value} has estimated_tokens={info.estimated_tokens}"
            )


# ═══════════════════════════════════════════════════════════════════
# 2. TestTierDistribution
# ═══════════════════════════════════════════════════════════════════


class TestTierDistribution:
    """Verify tier counts and token budget ordering."""

    def test_tier_1_count(self):
        """At least 1 Tier 1 technique (CRP is always Tier 1)."""
        t1 = [
            info for info in TECHNIQUE_REGISTRY.values()
            if info.tier == TechniqueTier.TIER_1
        ]
        assert len(t1) >= 1
        # Verify CRP specifically is Tier 1
        assert TECHNIQUE_REGISTRY[TechniqueID.CRP].tier == TechniqueTier.TIER_1

    def test_tier_2_count(self):
        """At least 3 Tier 2 techniques."""
        t2 = [
            info for info in TECHNIQUE_REGISTRY.values()
            if info.tier == TechniqueTier.TIER_2
        ]
        assert len(t2) >= 3

    def test_tier_3_count(self):
        """At least 5 Tier 3 techniques."""
        t3 = [
            info for info in TECHNIQUE_REGISTRY.values()
            if info.tier == TechniqueTier.TIER_3
        ]
        assert len(t3) >= 5

    def test_t1_tokens_are_lowest(self):
        """Tier 1 avg tokens < Tier 2 avg tokens < Tier 3 avg tokens."""
        t1_tokens = [
            info.estimated_tokens
            for info in TECHNIQUE_REGISTRY.values()
            if info.tier == TechniqueTier.TIER_1
        ]
        t2_tokens = [
            info.estimated_tokens
            for info in TECHNIQUE_REGISTRY.values()
            if info.tier == TechniqueTier.TIER_2
        ]
        t3_tokens = [
            info.estimated_tokens
            for info in TECHNIQUE_REGISTRY.values()
            if info.tier == TechniqueTier.TIER_3
        ]
        assert len(t1_tokens) > 0
        assert len(t2_tokens) > 0
        assert len(t3_tokens) > 0

        avg_t1 = sum(t1_tokens) / len(t1_tokens)
        avg_t2 = sum(t2_tokens) / len(t2_tokens)
        avg_t3 = sum(t3_tokens) / len(t3_tokens)

        assert avg_t1 < avg_t2, (
            f"T1 avg ({avg_t1:.1f}) should be < T2 avg ({avg_t2:.1f})"
        )
        assert avg_t2 < avg_t3, (
            f"T2 avg ({avg_t2:.1f}) should be < T3 avg ({avg_t3:.1f})"
        )

    def test_t3_tokens_are_highest(self):
        """Tier 3 techniques have highest token budgets."""
        t1_max = max(
            info.estimated_tokens
            for info in TECHNIQUE_REGISTRY.values()
            if info.tier == TechniqueTier.TIER_1
        )
        t2_max = max(
            info.estimated_tokens
            for info in TECHNIQUE_REGISTRY.values()
            if info.tier == TechniqueTier.TIER_2
        )
        t3_min = min(
            info.estimated_tokens
            for info in TECHNIQUE_REGISTRY.values()
            if info.tier == TechniqueTier.TIER_3
        )
        assert t3_min >= t2_max, (
            f"T3 min ({t3_min}) should be >= T2 max ({t2_max})"
        )


# ═══════════════════════════════════════════════════════════════════
# 3. TestVariantGating
# ═══════════════════════════════════════════════════════════════════


class TestVariantGating:
    """Verify variant gating for Mini PARWA / PARWA / PARWA High."""

    def test_mini_parwa_gets_only_tier_1(self):
        """Mini PARWA (free plan) gets only Tier 1 techniques."""
        available = TechniqueRouter.get_available_techniques_for_plan("free")
        t1_only = {
            tid for tid, info in TECHNIQUE_REGISTRY.items()
            if info.tier == TechniqueTier.TIER_1
        }
        assert available == t1_only
        # Should have exactly Tier 1 count
        t1_count = sum(
            1 for info in TECHNIQUE_REGISTRY.values()
            if info.tier == TechniqueTier.TIER_1
        )
        assert len(available) == t1_count

    def test_parwa_gets_t1_and_t2(self):
        """PARWA (pro plan) gets Tier 1 + Tier 2 techniques."""
        available = TechniqueRouter.get_available_techniques_for_plan("pro")
        t1_t2 = {
            tid for tid, info in TECHNIQUE_REGISTRY.items()
            if info.tier in (TechniqueTier.TIER_1, TechniqueTier.TIER_2)
        }
        assert available == t1_t2

    def test_parwa_high_gets_all(self):
        """PARWA High (enterprise/vip) gets all techniques."""
        available = TechniqueRouter.get_available_techniques_for_plan("enterprise")
        total = len(TECHNIQUE_REGISTRY)
        assert len(available) == total
        assert available == set(TECHNIQUE_REGISTRY.keys())

    def test_no_tier_0_exists(self):
        """No technique should have tier_0 or an invalid tier."""
        for tid, info in TECHNIQUE_REGISTRY.items():
            assert info.tier in {
                TechniqueTier.TIER_1, TechniqueTier.TIER_2, TechniqueTier.TIER_3,
            }, f"{tid.value} has unexpected tier: {info.tier}"


# ═══════════════════════════════════════════════════════════════════
# 4. TestAllTechniquesImportable
# ═══════════════════════════════════════════════════════════════════


class TestAllTechniquesImportable:
    """Verify all technique modules can be imported and have the
    required interface (technique_id, should_activate, execute)."""

    @pytest.mark.parametrize("tid,module_path,node_class_name", [
        (tid, mod, cls)
        for tid, (mod, cls) in TECHNIQUE_MODULE_MAP.items()
    ], ids=[tid.value for tid in TECHNIQUE_MODULE_MAP])
    def test_module_importable(self, tid, module_path, node_class_name):
        """Each technique's module must be importable."""
        __import__(module_path)

    def test_all_node_classes_have_required_interface(self):
        """Each technique with a Node class must have technique_id,
        should_activate, and execute."""
        for tid, (module_path, node_class_name) in TECHNIQUES_WITH_NODES.items():
            module = __import__(module_path, fromlist=[node_class_name])
            node_class = getattr(module, node_class_name)
            node = node_class()

            # technique_id is a property
            assert hasattr(node, "technique_id"), (
                f"{tid.value} node missing technique_id property"
            )
            assert node.technique_id == tid, (
                f"{tid.value} node.technique_id is {node.technique_id}, "
                f"expected {tid}"
            )

            # should_activate is an async method
            assert hasattr(node, "should_activate"), (
                f"{tid.value} node missing should_activate method"
            )
            assert callable(node.should_activate), (
                f"{tid.value} should_activate is not callable"
            )

            # execute is an async method
            assert hasattr(node, "execute"), (
                f"{tid.value} node missing execute method"
            )
            assert callable(node.execute), (
                f"{tid.value} execute is not callable"
            )


# ═══════════════════════════════════════════════════════════════════
# 5. TestAllTechniquesNodeActivation
# ═══════════════════════════════════════════════════════════════════


class TestAllTechniquesNodeActivation:
    """Verify should_activate works for all technique nodes,
    returns a bool, and doesn't crash."""

    @pytest.fixture
    def _nodes(self):
        """Instantiate all technique nodes once."""
        nodes = {}
        for tid, (module_path, node_class_name) in TECHNIQUES_WITH_NODES.items():
            module = __import__(module_path, fromlist=[node_class_name])
            node_class = getattr(module, node_class_name)
            nodes[tid] = node_class()
        return nodes

    @pytest.mark.asyncio
    async def test_all_nodes_activate_returns_bool(self, _nodes):
        """should_activate must return bool for all nodes."""
        for tid, node in _nodes.items():
            # Use appropriate signals for each technique
            if tid in ACTIVATION_SIGNALS:
                signals = QuerySignals(**ACTIVATION_SIGNALS[tid])
            else:
                signals = QuerySignals()
            state = ConversationState(signals=signals)
            result = await node.should_activate(state)
            assert isinstance(result, bool), (
                f"{tid.value}.should_activate() returned {type(result).__name__}, "
                f"expected bool"
            )

    @pytest.mark.asyncio
    async def test_crp_always_activates(self, _nodes):
        """CRP (Tier 1) must always activate, even on empty state."""
        node = _nodes[TechniqueID.CRP]
        state = ConversationState()
        assert await node.should_activate(state) is True

    @pytest.mark.asyncio
    async def test_tier_2_techniques_activate_on_appropriate_signals(self, _nodes):
        """Tier 2 techniques should activate on their trigger signals."""
        t2_tests = {
            TechniqueID.CHAIN_OF_THOUGHT: QuerySignals(query_complexity=0.6),
            TechniqueID.REVERSE_THINKING: QuerySignals(confidence_score=0.4),
            TechniqueID.REACT: QuerySignals(external_data_required=True),
            TechniqueID.STEP_BACK: QuerySignals(confidence_score=0.4),
            TechniqueID.THREAD_OF_THOUGHT: QuerySignals(turn_count=8),
        }
        for tid, signals in t2_tests.items():
            if tid in _nodes:
                node = _nodes[tid]
                state = ConversationState(signals=signals)
                assert await node.should_activate(state) is True, (
                    f"{tid.value} should activate on {vars(signals)}"
                )

    @pytest.mark.asyncio
    async def test_tier_3_techniques_activate_on_appropriate_signals(self, _nodes):
        """Tier 3 techniques should activate on their trigger signals."""
        t3_tests = {
            TechniqueID.GST: QuerySignals(is_strategic_decision=True),
            TechniqueID.UNIVERSE_OF_THOUGHTS: QuerySignals(customer_tier="vip"),
            TechniqueID.TREE_OF_THOUGHTS: QuerySignals(resolution_path_count=5),
            TechniqueID.SELF_CONSISTENCY: QuerySignals(monetary_value=200.0),
            TechniqueID.REFLEXION: QuerySignals(previous_response_status="rejected"),
            TechniqueID.LEAST_TO_MOST: QuerySignals(query_complexity=0.9),
        }
        for tid, signals in t3_tests.items():
            if tid in _nodes:
                node = _nodes[tid]
                state = ConversationState(signals=signals)
                assert await node.should_activate(state) is True, (
                    f"{tid.value} should activate on {vars(signals)}"
                )

    @pytest.mark.asyncio
    async def test_all_nodes_handle_empty_state(self, _nodes):
        """All nodes must handle empty ConversationState without crashing."""
        empty_state = ConversationState()
        for tid, node in _nodes.items():
            result = await node.should_activate(empty_state)
            assert isinstance(result, bool), (
                f"{tid.value}.should_activate() crashed on empty state"
            )


# ═══════════════════════════════════════════════════════════════════
# 6. TestAllTechniquesExecuteBC008
# ═══════════════════════════════════════════════════════════════════


class TestAllTechniquesExecuteBC008:
    """BC-008: All techniques must never crash on any input.
    Tests empty state, empty query, and special characters."""

    @pytest.fixture
    def _nodes(self):
        """Instantiate all technique nodes once."""
        nodes = {}
        for tid, (module_path, node_class_name) in TECHNIQUES_WITH_NODES.items():
            module = __import__(module_path, fromlist=[node_class_name])
            node_class = getattr(module, node_class_name)
            nodes[tid] = node_class()
        return nodes

    @pytest.mark.asyncio
    async def test_all_execute_on_empty_conversation_state(self, _nodes):
        """execute() on empty ConversationState() must return ConversationState."""
        for tid, node in _nodes.items():
            state = ConversationState()
            result = await node.execute(state)
            assert isinstance(result, ConversationState), (
                f"{tid.value}.execute() on empty state returned "
                f"{type(result).__name__}"
            )

    @pytest.mark.asyncio
    async def test_all_execute_on_empty_query(self, _nodes):
        """execute() with empty query must not crash."""
        for tid, node in _nodes.items():
            state = ConversationState(query="")
            result = await node.execute(state)
            assert isinstance(result, ConversationState), (
                f"{tid.value}.execute() on empty query returned "
                f"{type(result).__name__}"
            )

    @pytest.mark.asyncio
    async def test_all_execute_on_special_chars(self, _nodes):
        """execute() with special characters must not crash (BC-008)."""
        special_queries = [
            "<script>alert('xss')</script>",
            "'; DROP TABLE users; --",
            "\x00\x01\x02\x03",
            "日本語テスト ñoño café",
            "a" * 5000,
            "{{template_injection}}",
            "<img onerror=alert(1) src=x>",
        ]
        for tid, node in _nodes.items():
            for query in special_queries:
                state = ConversationState(query=query)
                result = await node.execute(state)
                assert isinstance(result, ConversationState), (
                    f"{tid.value}.execute() crashed on special char input: "
                    f"{repr(query[:50])}"
                )

    @pytest.mark.asyncio
    async def test_all_execute_records_result_in_state(self, _nodes):
        """After execute(), technique_results must contain the technique key."""
        for tid, node in _nodes.items():
            state = ConversationState(query="test query for integration")
            result = await node.execute(state)
            assert tid.value in result.technique_results, (
                f"{tid.value} not in technique_results after execute()"
            )
