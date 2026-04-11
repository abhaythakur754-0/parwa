"""Tests for Technique Nodes (base interface + stub nodes).

Covers: BaseTechniqueNode interface, should_activate logic for all
12 technique stubs, ConversationState, GSDState, token budget checks.
"""

import pytest
from backend.app.core.techniques.base import (
    BaseTechniqueNode,
    ConversationState,
    GSDState,
)
from backend.app.core.techniques.stub_nodes import (
    CRPNode,
    ReverseThinkingNodePlaceholder,
    StepBackNodePlaceholder,
    ChainOfThoughtNodePlaceholder,
    ReActNodePlaceholder,
    ThreadOfThoughtNodePlaceholder,
    GSTNodePlaceholder,
    UniverseOfThoughtsNodePlaceholder,
    TreeOfThoughtsNodePlaceholder,
    SelfConsistencyNodePlaceholder,
    ReflexionNodePlaceholder,
    LeastToMostNodePlaceholder,
    TECHNIQUE_NODES,
)

# Aliases for cleaner test names
ReverseThinkingNode = ReverseThinkingNodePlaceholder
StepBackNode = StepBackNodePlaceholder
ChainOfThoughtNode = ChainOfThoughtNodePlaceholder
ReActNode = ReActNodePlaceholder
ThreadOfThoughtNode = ThreadOfThoughtNodePlaceholder
GSTNode = GSTNodePlaceholder
UniverseOfThoughtsNode = UniverseOfThoughtsNodePlaceholder
TreeOfThoughtsNode = TreeOfThoughtsNodePlaceholder
SelfConsistencyNode = SelfConsistencyNodePlaceholder
ReflexionNode = ReflexionNodePlaceholder
LeastToMostNode = LeastToMostNodePlaceholder
from backend.app.core.technique_router import (
    TechniqueID,
    TechniqueTier,
    QuerySignals,
)


class TestGSDState:
    def test_all_states_defined(self):
        expected = {
            "new", "greeting", "diagnosis", "resolution",
            "follow_up", "closed", "escalate", "human_handoff",
        }
        actual = {s.value for s in GSDState}
        assert actual == expected

    def test_default_state_is_new(self):
        state = GSDState.NEW
        assert state.value == "new"


class TestConversationState:
    def test_default_state(self):
        state = ConversationState()
        assert state.query == ""
        assert state.gsd_state == GSDState.NEW
        assert state.token_usage == 0
        assert state.technique_results == {}
        assert state.response_parts == []
        assert state.reasoning_thread == []

    def test_custom_state(self):
        signals = QuerySignals(query_complexity=0.8, confidence_score=0.3)
        state = ConversationState(
            query="test query",
            signals=signals,
            ticket_id="ticket-1",
            company_id="company-1",
        )
        assert state.query == "test query"
        assert state.signals.query_complexity == 0.8
        assert state.ticket_id == "ticket-1"

    def test_gsd_history_tracks(self):
        state = ConversationState()
        state.gsd_history.append(GSDState.GREETING)
        state.gsd_history.append(GSDState.DIAGNOSIS)
        assert len(state.gsd_history) == 2

    def test_technique_results_storable(self):
        state = ConversationState()
        state.technique_results["cot"] = {"status": "success"}
        assert "cot" in state.technique_results


class TestNodeRegistry:
    def test_all_12_nodes_registered(self):
        assert len(TECHNIQUE_NODES) == 12

    def test_all_nodes_are_base_technique_nodes(self):
        for tid, node in TECHNIQUE_NODES.items():
            assert isinstance(node, BaseTechniqueNode)

    def test_tier_1_nodes_present(self):
        assert TechniqueID.CRP in TECHNIQUE_NODES
        # GSD is handled by the state machine (F-053), not a technique node
        # CLARA is the quality gate (F-057), not a technique node
        # Only CRP has a dedicated T1 technique node

    def test_tier_2_nodes_present(self):
        assert TechniqueID.CHAIN_OF_THOUGHT in TECHNIQUE_NODES
        assert TechniqueID.REVERSE_THINKING in TECHNIQUE_NODES
        assert TechniqueID.REACT in TECHNIQUE_NODES
        assert TechniqueID.STEP_BACK in TECHNIQUE_NODES
        assert TechniqueID.THREAD_OF_THOUGHT in TECHNIQUE_NODES

    def test_tier_3_nodes_present(self):
        assert TechniqueID.GST in TECHNIQUE_NODES
        assert TechniqueID.UNIVERSE_OF_THOUGHTS in TECHNIQUE_NODES
        assert TechniqueID.TREE_OF_THOUGHTS in TECHNIQUE_NODES
        assert TechniqueID.SELF_CONSISTENCY in TECHNIQUE_NODES
        assert TechniqueID.REFLEXION in TECHNIQUE_NODES
        assert TechniqueID.LEAST_TO_MOST in TECHNIQUE_NODES


class TestCRPNode:
    """F-140: CRP — Tier 1 always-active."""

    @pytest.fixture
    def node(self):
        return CRPNode()

    @pytest.mark.asyncio
    async def test_always_activates(self, node):
        state = ConversationState()
        assert await node.should_activate(state) is True

    @pytest.mark.asyncio
    async def test_activates_even_with_minimal_signals(self, node):
        state = ConversationState(query="")
        assert await node.should_activate(state) is True

    @pytest.mark.asyncio
    async def test_execute_returns_state(self, node):
        state = ConversationState(query="Hello")
        result = await node.execute(state)
        assert isinstance(result, ConversationState)
        assert "crp" in result.technique_results

    @pytest.mark.asyncio
    async def test_execute_records_stub(self, node):
        state = ConversationState(query="Hello")
        await node.execute(state)
        assert state.technique_results["crp"]["status"] == "stub"

    def test_technique_id(self, node):
        assert node.technique_id == TechniqueID.CRP

    def test_is_tier_1(self, node):
        assert node.technique_info.tier == TechniqueTier.TIER_1


class TestReverseThinkingNode:
    """F-141: Reverse Thinking — Tier 2 conditional."""

    @pytest.fixture
    def node(self):
        return ReverseThinkingNode()

    @pytest.mark.asyncio
    async def test_activates_on_low_confidence(self, node):
        signals = QuerySignals(confidence_score=0.4)
        state = ConversationState(signals=signals)
        assert await node.should_activate(state) is True

    @pytest.mark.asyncio
    async def test_activates_on_rejected_response(self, node):
        signals = QuerySignals(previous_response_status="rejected")
        state = ConversationState(signals=signals)
        assert await node.should_activate(state) is True

    @pytest.mark.asyncio
    async def test_does_not_activate_on_high_confidence(self, node):
        signals = QuerySignals(confidence_score=0.9)
        state = ConversationState(signals=signals)
        assert await node.should_activate(state) is False

    @pytest.mark.asyncio
    async def test_execute_records_stub(self, node):
        state = ConversationState()
        await node.execute(state)
        assert "reverse_thinking" in state.technique_results

    def test_technique_id(self, node):
        assert node.technique_id == TechniqueID.REVERSE_THINKING


class TestStepBackNode:
    """F-142: Step-Back — Tier 2 conditional."""

    @pytest.fixture
    def node(self):
        return StepBackNode()

    @pytest.mark.asyncio
    async def test_activates_on_low_confidence(self, node):
        signals = QuerySignals(confidence_score=0.4)
        state = ConversationState(signals=signals)
        assert await node.should_activate(state) is True

    @pytest.mark.asyncio
    async def test_activates_on_reasoning_loop(self, node):
        signals = QuerySignals(reasoning_loop_detected=True)
        state = ConversationState(signals=signals)
        assert await node.should_activate(state) is True

    @pytest.mark.asyncio
    async def test_activates_on_diagnosis_state(self, node):
        state = ConversationState(gsd_state=GSDState.DIAGNOSIS)
        assert await node.should_activate(state) is True

    @pytest.mark.asyncio
    async def test_does_not_activate_on_normal_state(self, node):
        state = ConversationState(
            signals=QuerySignals(confidence_score=0.9),
            gsd_state=GSDState.RESOLUTION,
        )
        assert await node.should_activate(state) is False

    @pytest.mark.asyncio
    async def test_execute_records_stub(self, node):
        state = ConversationState()
        await node.execute(state)
        assert "step_back" in state.technique_results

    def test_technique_id(self, node):
        assert node.technique_id == TechniqueID.STEP_BACK


class TestChainOfThoughtNode:
    @pytest.fixture
    def node(self):
        return ChainOfThoughtNode()

    @pytest.mark.asyncio
    async def test_activates_on_high_complexity(self, node):
        signals = QuerySignals(query_complexity=0.6)
        state = ConversationState(signals=signals)
        assert await node.should_activate(state) is True

    @pytest.mark.asyncio
    async def test_does_not_activate_on_low_complexity(self, node):
        signals = QuerySignals(query_complexity=0.2)
        state = ConversationState(signals=signals)
        assert await node.should_activate(state) is False

    def test_technique_id(self, node):
        assert node.technique_id == TechniqueID.CHAIN_OF_THOUGHT


class TestReActNode:
    @pytest.fixture
    def node(self):
        return ReActNode()

    @pytest.mark.asyncio
    async def test_activates_on_external_data(self, node):
        signals = QuerySignals(external_data_required=True)
        state = ConversationState(signals=signals)
        assert await node.should_activate(state) is True

    @pytest.mark.asyncio
    async def test_does_not_activate_without_external_data(self, node):
        signals = QuerySignals(external_data_required=False)
        state = ConversationState(signals=signals)
        assert await node.should_activate(state) is False

    def test_technique_id(self, node):
        assert node.technique_id == TechniqueID.REACT


class TestThreadOfThoughtNode:
    @pytest.fixture
    def node(self):
        return ThreadOfThoughtNode()

    @pytest.mark.asyncio
    async def test_activates_on_many_turns(self, node):
        signals = QuerySignals(turn_count=8)
        state = ConversationState(signals=signals)
        assert await node.should_activate(state) is True

    @pytest.mark.asyncio
    async def test_does_not_activate_on_few_turns(self, node):
        signals = QuerySignals(turn_count=3)
        state = ConversationState(signals=signals)
        assert await node.should_activate(state) is False

    def test_technique_id(self, node):
        assert node.technique_id == TechniqueID.THREAD_OF_THOUGHT


class TestGSTNode:
    @pytest.fixture
    def node(self):
        return GSTNode()

    @pytest.mark.asyncio
    async def test_activates_on_strategic_decision(self, node):
        signals = QuerySignals(is_strategic_decision=True)
        state = ConversationState(signals=signals)
        assert await node.should_activate(state) is True

    @pytest.mark.asyncio
    async def test_does_not_activate_on_normal_query(self, node):
        signals = QuerySignals(is_strategic_decision=False)
        state = ConversationState(signals=signals)
        assert await node.should_activate(state) is False

    def test_technique_id(self, node):
        assert node.technique_id == TechniqueID.GST
    def test_is_tier_3(self, node):
        assert node.technique_info.tier == TechniqueTier.TIER_3


class TestUniverseOfThoughtsNode:
    @pytest.fixture
    def node(self):
        return UniverseOfThoughtsNode()

    @pytest.mark.asyncio
    async def test_activates_on_vip(self, node):
        signals = QuerySignals(customer_tier="vip")
        state = ConversationState(signals=signals)
        assert await node.should_activate(state) is True

    @pytest.mark.asyncio
    async def test_activates_on_low_sentiment(self, node):
        signals = QuerySignals(sentiment_score=0.1)
        state = ConversationState(signals=signals)
        assert await node.should_activate(state) is True

    @pytest.mark.asyncio
    async def test_activates_on_high_monetary(self, node):
        signals = QuerySignals(monetary_value=500.0)
        state = ConversationState(signals=signals)
        assert await node.should_activate(state) is True

    @pytest.mark.asyncio
    async def test_does_not_activate_on_normal(self, node):
        signals = QuerySignals(customer_tier="free", sentiment_score=0.7, monetary_value=0)
        state = ConversationState(signals=signals)
        assert await node.should_activate(state) is False

    def test_technique_id(self, node):
        assert node.technique_id == TechniqueID.UNIVERSE_OF_THOUGHTS


class TestTreeOfThoughtsNode:
    @pytest.fixture
    def node(self):
        return TreeOfThoughtsNode()

    @pytest.mark.asyncio
    async def test_activates_on_multi_path(self, node):
        signals = QuerySignals(resolution_path_count=5)
        state = ConversationState(signals=signals)
        assert await node.should_activate(state) is True

    @pytest.mark.asyncio
    async def test_does_not_activate_on_single_path(self, node):
        signals = QuerySignals(resolution_path_count=1)
        state = ConversationState(signals=signals)
        assert await node.should_activate(state) is False

    def test_technique_id(self, node):
        assert node.technique_id == TechniqueID.TREE_OF_THOUGHTS


class TestSelfConsistencyNode:
    @pytest.fixture
    def node(self):
        return SelfConsistencyNode()

    @pytest.mark.asyncio
    async def test_activates_on_high_monetary(self, node):
        signals = QuerySignals(monetary_value=200.0)
        state = ConversationState(signals=signals)
        assert await node.should_activate(state) is True

    @pytest.mark.asyncio
    async def test_activates_on_billing_intent(self, node):
        signals = QuerySignals(intent_type="billing")
        state = ConversationState(signals=signals)
        assert await node.should_activate(state) is True

    @pytest.mark.asyncio
    async def test_does_not_activate_on_general(self, node):
        signals = QuerySignals(intent_type="general", monetary_value=0)
        state = ConversationState(signals=signals)
        assert await node.should_activate(state) is False

    def test_technique_id(self, node):
        assert node.technique_id == TechniqueID.SELF_CONSISTENCY


class TestReflexionNode:
    @pytest.fixture
    def node(self):
        return ReflexionNode()

    @pytest.mark.asyncio
    async def test_activates_on_rejected(self, node):
        signals = QuerySignals(previous_response_status="rejected")
        state = ConversationState(signals=signals)
        assert await node.should_activate(state) is True

    @pytest.mark.asyncio
    async def test_activates_on_vip(self, node):
        signals = QuerySignals(customer_tier="vip")
        state = ConversationState(signals=signals)
        assert await node.should_activate(state) is True

    @pytest.mark.asyncio
    async def test_does_not_activate_on_normal(self, node):
        signals = QuerySignals(previous_response_status="accepted", customer_tier="free")
        state = ConversationState(signals=signals)
        assert await node.should_activate(state) is False

    def test_technique_id(self, node):
        assert node.technique_id == TechniqueID.REFLEXION


class TestLeastToMostNode:
    @pytest.fixture
    def node(self):
        return LeastToMostNode()

    @pytest.mark.asyncio
    async def test_activates_on_high_complexity(self, node):
        signals = QuerySignals(query_complexity=0.9)
        state = ConversationState(signals=signals)
        assert await node.should_activate(state) is True

    @pytest.mark.asyncio
    async def test_does_not_activate_on_low_complexity(self, node):
        signals = QuerySignals(query_complexity=0.3)
        state = ConversationState(signals=signals)
        assert await node.should_activate(state) is False

    def test_technique_id(self, node):
        assert node.technique_id == TechniqueID.LEAST_TO_MOST


class TestTokenBudgetCheck:
    """Verify token budget checking on nodes."""

    @pytest.mark.asyncio
    async def test_budget_ok_when_usage_low(self):
        node = ChainOfThoughtNode()
        state = ConversationState(
            token_usage=0,
            technique_token_budget=1500,
        )
        assert node.check_token_budget(state) is True

    @pytest.mark.asyncio
    async def test_budget_exceeded_when_usage_high(self):
        node = ChainOfThoughtNode()
        state = ConversationState(
            token_usage=1200,
            technique_token_budget=1500,
        )
        # CoT needs ~350 tokens, 1200+350 > 1500
        assert node.check_token_budget(state) is False

    @pytest.mark.asyncio
    async def test_record_result_updates_usage(self):
        node = CRPNode()
        state = ConversationState(token_usage=0)
        node.record_result(state, {"compressed": True})
        assert state.token_usage > 0

    @pytest.mark.asyncio
    async def test_record_skip(self):
        node = CRPNode()
        state = ConversationState(token_usage=0)
        node.record_skip(state, reason="test_skip")
        assert state.technique_results["crp"]["status"] == "skipped_budget"
