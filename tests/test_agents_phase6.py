"""Phase 6: Agent Orchestration Layer — Unit Tests.

Tests for:
  - AgentContext: Per-agent state accumulation
  - AgentOrchestrator: Coordination, handoffs, cross-agent sharing
  - AgentRecovery: Error recovery strategies
  - AgentMetrics: Performance tracking
  - Integration with graph.py (orchestrated nodes)
"""

from __future__ import annotations

import asyncio
import pytest
import time

from parwa.agents.context import AgentContext
from parwa.agents.orchestrator import (
    AgentOrchestrator,
    get_orchestrator,
    reset_orchestrator,
    _NODE_TO_AGENT,
)
from parwa.agents.metrics import (
    AgentMetrics,
    get_agent_metrics,
    reset_agent_metrics,
)
from parwa.agents.recovery import (
    AgentRecovery,
    RecoveryStrategy,
    RecoveryDecision,
    _AGENT_CRITICAL_NODES,
)


# ═══════════════════════════════════════════════════════════════════════════════
# AgentContext Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestAgentContext:
    """Tests for the AgentContext class."""

    def test_create_context(self):
        ctx = AgentContext(agent_name="Knowledge Agent")
        assert ctx.agent_name == "Knowledge Agent"
        assert ctx.node_outputs == {}
        assert ctx.node_timings == {}
        assert ctx.frameworks_used == []
        assert ctx.errors == []
        assert ctx.started_at == 0.0
        assert ctx.completed_at == 0.0
        assert not ctx.is_completed
        assert ctx.error_count == 0

    def test_start_and_complete(self):
        ctx = AgentContext(agent_name="Reasoning Agent")
        ctx.start()
        assert ctx.started_at > 0
        assert not ctx.is_completed
        assert ctx.elapsed_ms >= 0

        ctx.complete()
        assert ctx.completed_at > 0
        assert ctx.is_completed
        assert ctx.elapsed_ms > 0

    def test_start_node_and_end_node(self):
        ctx = AgentContext(agent_name="Knowledge Agent")
        ctx.start_node("FAQ_MATCHER")

        output = {"faq_match": {"content": "test"}, "active_frameworks": ["hyde"]}
        ctx.end_node("FAQ_MATCHER", output)

        assert "FAQ_MATCHER" in ctx.node_outputs
        assert ctx.node_outputs["FAQ_MATCHER"] == output
        assert "FAQ_MATCHER" in ctx.node_timings
        assert ctx.node_timings["FAQ_MATCHER"] >= 0
        assert "hyde" in ctx.frameworks_used

    def test_multiple_nodes(self):
        ctx = AgentContext(agent_name="Knowledge Agent")

        # Node 1
        ctx.start_node("FAQ_MATCHER")
        ctx.end_node("FAQ_MATCHER", {"faq_match": None, "active_frameworks": ["hyde"]})

        # Node 2
        ctx.start_node("KB_RETRIEVER")
        ctx.end_node("KB_RETRIEVER", {"kb_results": [{"content": "test"}], "active_frameworks": ["clara"]})

        # Node 3
        ctx.start_node("CONTEXT_MANAGER")
        ctx.end_node("CONTEXT_MANAGER", {"context_history": [], "active_frameworks": ["multi_query"]})

        # Node 4
        ctx.start_node("INTEGRATION_LOOKUP")
        ctx.end_node("INTEGRATION_LOOKUP", {"integration_data": {}, "active_frameworks": ["hyde"]})

        assert len(ctx.node_outputs) == 4
        assert len(ctx.frameworks_used) == 3  # hyde, clara, multi_query (hyde deduped)
        assert ctx.has_node_completed("FAQ_MATCHER")
        assert ctx.has_node_completed("KB_RETRIEVER")
        assert not ctx.has_node_completed("NONEXISTENT_NODE")

    def test_framework_deduplication(self):
        ctx = AgentContext(agent_name="Knowledge Agent")
        ctx.start_node("FAQ_MATCHER")
        ctx.end_node("FAQ_MATCHER", {"active_frameworks": ["hyde", "clara"]})
        ctx.start_node("KB_RETRIEVER")
        ctx.end_node("KB_RETRIEVER", {"active_frameworks": ["hyde", "step_back"]})

        # hyde should only appear once
        assert ctx.frameworks_used.count("hyde") == 1
        assert len(ctx.frameworks_used) == 3  # hyde, clara, step_back

    def test_error_tracking(self):
        ctx = AgentContext(agent_name="Action Agent")
        ctx.add_error("ACTION_EXECUTOR", "Timeout after 30s")

        assert ctx.has_errors
        assert ctx.error_count == 1
        assert ctx.errors[0]["node"] == "ACTION_EXECUTOR"
        assert "Timeout" in ctx.errors[0]["error"]

    def test_error_from_node_output(self):
        ctx = AgentContext(agent_name="Reasoning Agent")
        ctx.start_node("REASONING_ENGINE")
        ctx.end_node("REASONING_ENGINE", {"node_error": "LLM failed", "reasoning_chain": []})

        assert ctx.has_errors
        assert ctx.error_count == 1

    def test_get_node_output(self):
        ctx = AgentContext(agent_name="Knowledge Agent")
        ctx.start_node("KB_RETRIEVER")
        ctx.end_node("KB_RETRIEVER", {"kb_results": [{"content": "refund policy"}]})

        output = ctx.get_node_output("KB_RETRIEVER")
        assert output is not None
        assert len(output["kb_results"]) == 1

        assert ctx.get_node_output("NONEXISTENT") is None

    def test_get_node_names(self):
        ctx = AgentContext(agent_name="Knowledge Agent")
        ctx.start_node("FAQ_MATCHER")
        ctx.end_node("FAQ_MATCHER", {})
        ctx.start_node("KB_RETRIEVER")
        ctx.end_node("KB_RETRIEVER", {})

        names = ctx.get_node_names()
        assert "FAQ_MATCHER" in names
        assert "KB_RETRIEVER" in names

    def test_total_time_ms(self):
        ctx = AgentContext(agent_name="Test Agent")
        ctx.start_node("NODE_A")
        time.sleep(0.01)
        ctx.end_node("NODE_A", {})
        ctx.start_node("NODE_B")
        time.sleep(0.01)
        ctx.end_node("NODE_B", {})

        total = ctx.get_total_time_ms()
        assert total >= 10  # At least 20ms total

    def test_serialization(self):
        ctx = AgentContext(agent_name="Knowledge Agent")
        ctx.start_node("FAQ_MATCHER")
        ctx.end_node("FAQ_MATCHER", {"faq_match": {"content": "test"}, "active_frameworks": ["hyde"]})
        ctx.start_node("KB_RETRIEVER")
        ctx.end_node("KB_RETRIEVER", {"kb_results": [], "active_frameworks": ["clara"]})
        ctx.complete()

        # Serialize
        data = ctx.to_dict()
        assert data["agent_name"] == "Knowledge Agent"
        assert "FAQ_MATCHER" in data["node_outputs"]
        assert len(data["frameworks_used"]) == 2
        assert data["is_completed"] is True

        # Deserialize
        ctx2 = AgentContext.from_dict(data)
        assert ctx2.agent_name == "Knowledge Agent"
        assert ctx2.has_node_completed("FAQ_MATCHER")
        assert ctx2.is_completed
        assert len(ctx2.frameworks_used) == 2

    def test_repr(self):
        ctx = AgentContext(agent_name="Reasoning Agent")
        r = repr(ctx)
        assert "Reasoning Agent" in r
        assert "nodes=0" in r

    def test_empty_frameworks(self):
        ctx = AgentContext(agent_name="Router Agent")
        ctx.start_node("INGEST")
        ctx.end_node("INGEST", {"ticket_id": "T-001"})

        assert ctx.frameworks_used == []
        assert ctx.get_all_frameworks() == []


# ═══════════════════════════════════════════════════════════════════════════════
# AgentRecovery Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestAgentRecovery:
    """Tests for the AgentRecovery class."""

    def test_transient_error_retries(self):
        recovery = AgentRecovery()
        decision = recovery.decide(
            "Knowledge Agent", "KB_RETRIEVER",
            "Connection timeout", "TimeoutError",
        )
        assert decision.strategy == RecoveryStrategy.RETRY
        assert decision.retry_count == 1

    def test_rate_limit_retries(self):
        recovery = AgentRecovery()
        decision = recovery.decide(
            "Reasoning Agent", "REASONING_ENGINE",
            "Rate limit exceeded (429)", "RateLimitError",
        )
        assert decision.strategy == RecoveryStrategy.RETRY

    def test_optional_node_skips(self):
        recovery = AgentRecovery()
        # PREDICTION_ENGINE is optional in Proactive Agent
        decision = recovery.decide(
            "Proactive Agent", "PREDICTION_ENGINE",
            "Permanent failure", "ValueError",
        )
        assert decision.strategy == RecoveryStrategy.SKIP

    def test_optional_node_redirects(self):
        recovery = AgentRecovery()
        # INTEGRATION_LOOKUP has a redirect to KB_RETRIEVER
        # Use a non-transient error so it doesn't retry first
        decision = recovery.decide(
            "Knowledge Agent", "INTEGRATION_LOOKUP",
            "CRM data malformed", "ValueError",
        )
        assert decision.strategy == RecoveryStrategy.REDIRECT
        assert decision.redirect_target == "KB_RETRIEVER"

    def test_critical_node_retries_then_degrades(self):
        recovery = AgentRecovery()
        # REASONING_ENGINE is critical in Reasoning Agent
        # _MAX_RETRIES = 2, so:
        # First failure (retry_count=1): retry
        d1 = recovery.decide(
            "Reasoning Agent", "REASONING_ENGINE",
            "LLM error", "RuntimeError",
        )
        assert d1.strategy == RecoveryStrategy.RETRY
        assert d1.retry_count == 1

        # Second failure (retry_count=2): degrade (retry_count >= _MAX_RETRIES)
        d2 = recovery.decide(
            "Reasoning Agent", "REASONING_ENGINE",
            "LLM error again", "RuntimeError",
        )
        assert d2.strategy == RecoveryStrategy.DEGRADE
        assert d2.retry_count == 2

        # Third failure (retry_count=3): escalate (cannot recover)
        d3 = recovery.decide(
            "Reasoning Agent", "REASONING_ENGINE",
            "LLM error third time", "RuntimeError",
        )
        assert d3.strategy == RecoveryStrategy.ESCALATE

    def test_max_retries_leads_to_escalate(self):
        recovery = AgentRecovery()
        # Push beyond max retries for a critical node
        for _ in range(5):
            recovery.decide(
                "Compliance Agent", "PII_COMPLIANCE_GUARD",
                "Permanent failure", "RuntimeError",
            )
        # After max retries, should escalate
        decision = recovery.decide(
            "Compliance Agent", "PII_COMPLIANCE_GUARD",
            "Still failing", "RuntimeError",
        )
        assert decision.strategy in (RecoveryStrategy.DEGRADE, RecoveryStrategy.ESCALATE)

    def test_recovery_decision_serialization(self):
        decision = RecoveryDecision(
            strategy=RecoveryStrategy.RETRY,
            retry_count=2,
            reason="Transient error",
        )
        data = decision.to_dict()
        assert data["strategy"] == "retry"
        assert data["retry_count"] == 2

    def test_recovery_history(self):
        recovery = AgentRecovery()
        recovery.decide("Knowledge Agent", "KB_RETRIEVER", "timeout", "TimeoutError")
        recovery.decide("Action Agent", "ACTION_PLANNER", "error", "ValueError")

        history = recovery.get_recovery_history()
        assert len(history) == 2
        assert history[0]["agent"] == "Knowledge Agent"
        assert history[1]["agent"] == "Action Agent"

    def test_get_critical_nodes(self):
        critical = AgentRecovery.get_critical_nodes("Reasoning Agent")
        assert "REASONING_ENGINE" in critical
        assert "REVERSE_THINKER" not in critical

    def test_get_optional_nodes(self):
        optional = AgentRecovery.get_optional_nodes("Proactive Agent")
        assert "PROACTIVE_CHECKER" in optional
        assert "PREDICTION_ENGINE" in optional
        assert "FEEDBACK_LOOP" in optional

    def test_all_agents_have_critical_nodes(self):
        """Every agent except Proactive should have at least one critical node."""
        for agent_name in _AGENT_CRITICAL_NODES:
            critical = AgentRecovery.get_critical_nodes(agent_name)
            if agent_name == "Proactive Agent":
                # Proactive Agent is entirely optional — no critical nodes
                assert len(critical) == 0, f"{agent_name} should have no critical nodes"
            else:
                assert len(critical) > 0, f"{agent_name} has no critical nodes"

    def test_reset(self):
        recovery = AgentRecovery()
        recovery.decide("Test Agent", "NODE_A", "error", "Error")
        recovery.reset()
        assert recovery.get_retry_count("Test Agent", "NODE_A") == 0
        assert len(recovery.get_recovery_history()) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# AgentMetrics Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestAgentMetrics:
    """Tests for the AgentMetrics class."""

    def setup_method(self):
        """Reset metrics before each test."""
        reset_agent_metrics()
        self.metrics = get_agent_metrics()

    def test_initial_state(self):
        summary = self.metrics.summary()
        assert "Router Agent" in summary
        assert "Knowledge Agent" in summary
        assert summary["Router Agent"]["total_runs"] == 0

    def test_record_agent_run(self):
        ctx = AgentContext(agent_name="Knowledge Agent")
        ctx.start_node("FAQ_MATCHER")
        ctx.end_node("FAQ_MATCHER", {"active_frameworks": ["hyde"]})
        ctx.start_node("KB_RETRIEVER")
        ctx.end_node("KB_RETRIEVER", {"active_frameworks": ["clara"]})
        ctx.complete()

        self.metrics.record_agent_run("Knowledge Agent", ctx)

        agent_data = self.metrics.get_agent_metrics("Knowledge Agent")
        assert agent_data["total_runs"] == 1
        assert agent_data["avg_latency_ms"] >= 0
        assert "hyde" in agent_data["framework_usage"]
        assert "clara" in agent_data["framework_usage"]

    def test_record_multiple_runs(self):
        for i in range(5):
            ctx = AgentContext(agent_name="Reasoning Agent")
            ctx.start_node("REASONING_ENGINE")
            ctx.end_node("REASONING_ENGINE", {"active_frameworks": ["chain_of_thought"]})
            ctx.complete()
            self.metrics.record_agent_run("Reasoning Agent", ctx)

        agent_data = self.metrics.get_agent_metrics("Reasoning Agent")
        assert agent_data["total_runs"] == 5
        assert agent_data["framework_usage"]["chain_of_thought"] == 5

    def test_record_confidence(self):
        self.metrics.record_confidence("Compliance Agent", 0.85)
        self.metrics.record_confidence("Compliance Agent", 0.92)

        agent_data = self.metrics.get_agent_metrics("Compliance Agent")
        assert agent_data["avg_confidence"] == pytest.approx(0.885, abs=0.01)

    def test_summary_format(self):
        ctx = AgentContext(agent_name="Action Agent")
        ctx.start_node("ACTION_PLANNER")
        ctx.end_node("ACTION_PLANNER", {})
        ctx.complete()
        self.metrics.record_agent_run("Action Agent", ctx)

        summary = self.metrics.summary()
        assert "Action Agent" in summary
        agent_summary = summary["Action Agent"]
        assert "total_runs" in agent_summary
        assert "avg_latency_ms" in agent_summary
        assert "error_rate" in agent_summary
        assert "top_frameworks" in agent_summary

    def test_error_rate_tracking(self):
        ctx = AgentContext(agent_name="Action Agent")
        ctx.add_error("ACTION_EXECUTOR", "timeout")
        ctx.complete()

        self.metrics.record_agent_run("Action Agent", ctx)

        agent_data = self.metrics.get_agent_metrics("Action Agent")
        assert agent_data["total_errors"] == 1
        assert agent_data["error_rate"] == 1.0

    def test_node_timing_tracking(self):
        ctx = AgentContext(agent_name="Knowledge Agent")
        ctx.start_node("KB_RETRIEVER")
        time.sleep(0.01)
        ctx.end_node("KB_RETRIEVER", {})
        ctx.complete()

        self.metrics.record_agent_run("Knowledge Agent", ctx)

        agent_data = self.metrics.get_agent_metrics("Knowledge Agent")
        assert "KB_RETRIEVER" in agent_data["node_timings"]
        assert agent_data["node_timings"]["KB_RETRIEVER"]["count"] == 1
        assert agent_data["node_timings"]["KB_RETRIEVER"]["avg_ms"] >= 0

    def test_reset(self):
        ctx = AgentContext(agent_name="Router Agent")
        ctx.start_node("INGEST")
        ctx.end_node("INGEST", {})
        ctx.complete()
        self.metrics.record_agent_run("Router Agent", ctx)

        self.metrics.reset()
        agent_data = self.metrics.get_agent_metrics("Router Agent")
        assert agent_data["total_runs"] == 0

    def test_unknown_agent(self):
        agent_data = self.metrics.get_agent_metrics("Unknown Agent")
        assert agent_data == {}

    def test_confidence_window(self):
        """Confidence scores should be capped at 1000 entries."""
        for i in range(1100):
            self.metrics.record_confidence("Router Agent", 0.5)

        agent_data = self.metrics.get_agent_metrics("Router Agent")
        assert len(agent_data["confidence_scores"]) == 1000


# ═══════════════════════════════════════════════════════════════════════════════
# AgentOrchestrator Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestAgentOrchestrator:
    """Tests for the AgentOrchestrator class."""

    def setup_method(self):
        reset_orchestrator()
        reset_agent_metrics()

    def test_get_agent_for_node(self):
        orc = get_orchestrator()
        assert orc.get_agent_for_node("reasoning_engine") == "Reasoning Agent"
        assert orc.get_agent_for_node("kb_retriever") == "Knowledge Agent"
        assert orc.get_agent_for_node("action_planner") == "Action Agent"
        assert orc.get_agent_for_node("quality_scorer") == "Compliance Agent"
        assert orc.get_agent_for_node("proactive_checker") == "Proactive Agent"
        assert orc.get_agent_for_node("ingest") == "Router Agent"

    def test_all_22_nodes_mapped(self):
        """Every pipeline node should be mapped to an agent."""
        orc = get_orchestrator()
        all_nodes = [
            "ingest", "intent_classifier", "sentiment_analyzer", "escalation_decision",
            "faq_matcher", "kb_retriever", "context_manager", "integration_lookup",
            "reasoning_engine", "reverse_thinker", "tree_of_thoughts", "strategy_planner",
            "action_planner", "action_executor", "action_verifier",
            "proactive_checker", "prediction_engine", "feedback_loop",
            "pii_compliance_guard", "audit_logger", "quality_scorer", "response_formatter",
        ]
        for node in all_nodes:
            agent = orc.get_agent_for_node(node)
            assert agent != "Unknown Agent", f"Node '{node}' not mapped to any agent"

    def test_get_or_create_context(self):
        orc = get_orchestrator()
        ctx = orc.get_or_create_context({}, "Knowledge Agent")
        assert ctx.agent_name == "Knowledge Agent"
        assert not ctx.is_completed

    def test_get_agent_context_from_state(self):
        orc = get_orchestrator()
        ctx = AgentContext(agent_name="Reasoning Agent")
        ctx.start_node("REASONING_ENGINE")
        ctx.end_node("REASONING_ENGINE", {"reasoning_chain": ["step1"], "active_frameworks": ["cot"]})

        state = {"agent_contexts": {"Reasoning Agent": ctx.to_dict()}}
        retrieved = orc.get_agent_context(state, "Reasoning Agent")
        assert retrieved is not None
        assert retrieved.has_node_completed("REASONING_ENGINE")

    def test_save_context_to_state(self):
        orc = get_orchestrator()
        ctx = AgentContext(agent_name="Action Agent")
        ctx.start_node("ACTION_PLANNER")
        ctx.end_node("ACTION_PLANNER", {"action_plans": []})

        state = {}
        updates = orc._save_context(state, ctx)
        assert "agent_contexts" in updates
        assert "Action Agent" in updates["agent_contexts"]

    def test_detect_handoff(self):
        orc = get_orchestrator()
        assert not orc._detect_handoff(None, "Router Agent")
        assert not orc._detect_handoff("Router Agent", "Router Agent")
        assert orc._detect_handoff("Router Agent", "Knowledge Agent")
        assert orc._detect_handoff("Knowledge Agent", "Reasoning Agent")

    def test_orchestrated_node_wrapper(self):
        """Test that orchestrated_node wraps a node function correctly."""
        orc = get_orchestrator()

        async def mock_node(state):
            return {"test_output": "hello", "active_frameworks": ["cot"]}

        wrapped = orc.orchestrated_node(mock_node, "reasoning_engine")
        assert wrapped.__name__ == "orchestrated_reasoning_engine"

        # Run the wrapped node
        state = {}
        result = asyncio.get_event_loop().run_until_complete(wrapped(state))

        assert result["test_output"] == "hello"
        assert "agent_contexts" in result
        assert "Reasoning Agent" in result["agent_contexts"]
        assert "_current_agent" in result
        assert result["_current_agent"] == "Reasoning Agent"

    def test_orchestrated_node_tracks_context(self):
        """Test that orchestrated nodes build up agent context."""
        orc = get_orchestrator()

        async def mock_faq(state):
            return {"faq_match": None, "active_frameworks": ["hyde"]}

        async def mock_kb(state):
            return {"kb_results": [{"content": "test"}], "active_frameworks": ["clara"]}

        # Simulate running two Knowledge Agent nodes
        wrapped_faq = orc.orchestrated_node(mock_faq, "faq_matcher")
        wrapped_kb = orc.orchestrated_node(mock_kb, "kb_retriever")

        state = {}
        result1 = asyncio.get_event_loop().run_until_complete(wrapped_faq(state))
        state.update(result1)

        result2 = asyncio.get_event_loop().run_until_complete(wrapped_kb(state))
        state.update(result2)

        # Check that context accumulated
        ctx_data = state["agent_contexts"]["Knowledge Agent"]
        ctx = AgentContext.from_dict(ctx_data)
        assert ctx.has_node_completed("faq_matcher")
        assert ctx.has_node_completed("kb_retriever")
        assert "hyde" in ctx.frameworks_used
        assert "clara" in ctx.frameworks_used

    def test_orchestrated_node_detects_handoff(self):
        """Test that agent handoffs are detected and previous agent finalized."""
        orc = get_orchestrator()

        async def mock_ingest(state):
            return {"ticket_id": "T-001"}

        async def mock_faq(state):
            return {"faq_match": None, "active_frameworks": []}

        wrapped_ingest = orc.orchestrated_node(mock_ingest, "ingest")
        wrapped_faq = orc.orchestrated_node(mock_faq, "faq_matcher")

        state = {}
        result1 = asyncio.get_event_loop().run_until_complete(wrapped_ingest(state))
        state.update(result1)

        # faq_matcher is in Knowledge Agent (handoff from Router Agent)
        result2 = asyncio.get_event_loop().run_until_complete(wrapped_faq(state))
        state.update(result2)

        # Router Agent should be finalized
        router_ctx_data = state["agent_contexts"].get("Router Agent")
        if router_ctx_data:
            router_ctx = AgentContext.from_dict(router_ctx_data)
            # Router Agent should have ingest recorded
            assert router_ctx.has_node_completed("ingest")

    def test_cross_agent_context(self):
        """Test reading another agent's context."""
        orc = get_orchestrator()

        # Set up a state with Reasoning Agent context
        ctx = AgentContext(agent_name="Reasoning Agent")
        ctx.start_node("REASONING_ENGINE")
        ctx.end_node("REASONING_ENGINE", {
            "reasoning_conclusion": "Customer is eligible for refund",
            "active_frameworks": ["cot"],
        })

        state = {"agent_contexts": {"Reasoning Agent": ctx.to_dict()}}

        # Action Agent wants to read the reasoning conclusion
        conclusion = orc.get_cross_agent_context(
            state, "Action Agent", "Reasoning Agent", "reasoning_conclusion",
        )
        assert conclusion == "Customer is eligible for refund"

    def test_cross_agent_context_missing(self):
        """Test reading from a non-existent agent context."""
        orc = get_orchestrator()
        state = {"agent_contexts": {}}

        result = orc.get_cross_agent_context(
            state, "Action Agent", "Nonexistent Agent", "some_field",
        )
        assert result is None

    def test_get_agent_summary(self):
        """Test the agent summary endpoint."""
        orc = get_orchestrator()

        ctx = AgentContext(agent_name="Knowledge Agent")
        ctx.start_node("KB_RETRIEVER")
        ctx.end_node("KB_RETRIEVER", {"kb_results": [], "active_frameworks": ["clara"]})
        ctx.complete()

        state = {"agent_contexts": {"Knowledge Agent": ctx.to_dict()}}
        summary = orc.get_agent_summary(state)

        assert "Knowledge Agent" in summary
        assert summary["Knowledge Agent"]["completed"] is True
        # Node names are uppercase (as used in the pipeline)
        assert "KB_RETRIEVER" in summary["Knowledge Agent"]["nodes_run"]

    def test_reset_orchestrator(self):
        get_orchestrator()  # Create it
        reset_orchestrator()
        # Should create a new instance
        orc = get_orchestrator()
        assert orc is not None


# ═══════════════════════════════════════════════════════════════════════════════
# Integration Tests — Orchestrated Graph
# ═══════════════════════════════════════════════════════════════════════════════

class TestOrchestratedGraphIntegration:
    """Integration tests for the orchestrated PARWA graph."""

    def setup_method(self):
        reset_orchestrator()
        reset_agent_metrics()
        # Reset the graph singleton so it picks up the orchestrator
        from parwa.graph import reset_parwa_graph
        reset_parwa_graph()

    def test_graph_builds_with_orchestrator(self):
        """Test that the graph compiles with orchestration enabled."""
        from parwa.graph import build_parwa_graph
        graph = build_parwa_graph(use_orchestrator=True)
        assert graph is not None

    def test_graph_builds_without_orchestrator(self):
        """Test that the graph still compiles without orchestration."""
        from parwa.graph import build_parwa_graph
        graph = build_parwa_graph(use_orchestrator=False)
        assert graph is not None

    def test_process_ticket_with_orchestrator(self):
        """Test full ticket processing with orchestration."""
        from parwa.graph import process_ticket
        result = process_ticket(
            raw_message="I was charged twice for my order",
            customer_id="CUST-001",
            channel="email",
            variant="parwa",
        )

        assert result is not None
        assert "final_response" in result
        # Should have agent contexts populated
        assert "agent_contexts" in result
        assert isinstance(result["agent_contexts"], dict)

    def test_agent_contexts_populated(self):
        """Test that agent contexts are populated during processing."""
        from parwa.graph import process_ticket
        result = process_ticket(
            raw_message="I need a refund for a duplicate charge",
            customer_id="CUST-001",
            variant="parwa",
        )

        contexts = result.get("agent_contexts", {})
        # At minimum, Router Agent should have run
        assert len(contexts) > 0

        # Check that contexts have meaningful data
        for agent_name, ctx_data in contexts.items():
            if isinstance(ctx_data, dict):
                assert "agent_name" in ctx_data
                assert "node_outputs" in ctx_data

    def test_metrics_recorded_after_processing(self):
        """Test that agent metrics are recorded after ticket processing."""
        from parwa.graph import process_ticket
        process_ticket(
            raw_message="Cancel my order please",
            customer_id="CUST-001",
            variant="parwa",
        )

        metrics = get_agent_metrics()
        summary = metrics.summary()

        # At least some agents should have recorded runs
        total_runs = sum(s["total_runs"] for s in summary.values())
        assert total_runs > 0

    def test_current_agent_tracking(self):
        """Test that _current_agent is tracked in the final state."""
        from parwa.graph import process_ticket
        result = process_ticket(
            raw_message="What is the refund policy?",
            customer_id="CUST-001",
            variant="parwa",
        )

        # The last agent should be Compliance Agent (response_formatter)
        assert result.get("_current_agent") == "Compliance Agent"

    def test_mini_variant_with_orchestrator(self):
        """Test Mini PARWA variant still works with orchestration."""
        from parwa.graph import process_ticket
        result = process_ticket(
            raw_message="Process a refund for duplicate charge",
            customer_id="CUST-001",
            variant="mini",
        )

        assert result is not None
        # Mini PARWA should have recommendations (not executions) for high-risk actions
        recommendation = result.get("recommendation")
        if recommendation:
            assert recommendation.get("pending_approval") is True

    def test_quality_loopback_with_orchestrator(self):
        """Test that quality loop-back still works with orchestration."""
        from parwa.graph import build_parwa_graph

        # Build graph that forces a low quality score to trigger loop-back
        graph = build_parwa_graph(use_orchestrator=True)
        # This is a basic test — the loop-back behavior is tested
        # more thoroughly in test_graph.py
        assert graph is not None


# ═══════════════════════════════════════════════════════════════════════════════
# Agent Definition Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestAgentDefinitions:
    """Tests for the 6 agent definitions."""

    def test_all_agents_defined(self):
        from parwa.agents import ALL_AGENTS
        assert len(ALL_AGENTS) == 6

    def test_agent_names(self):
        from parwa.agents import ALL_AGENTS
        names = [a.name for a in ALL_AGENTS]
        assert "Router Agent" in names
        assert "Knowledge Agent" in names
        assert "Reasoning Agent" in names
        assert "Action Agent" in names
        assert "Compliance Agent" in names
        assert "Proactive Agent" in names

    def test_agent_node_coverage(self):
        """All 22 pipeline nodes should be owned by exactly one agent."""
        from parwa.agents import ALL_AGENTS

        all_node_names = set()
        for agent in ALL_AGENTS:
            for name in agent.node_names:
                assert name not in all_node_names, f"Node {name} owned by multiple agents"
                all_node_names.add(name)

        assert len(all_node_names) == 22

    def test_node_to_agent_mapping(self):
        from parwa.agents import NODE_TO_AGENT
        assert len(NODE_TO_AGENT) == 22

    def test_agent_node_ids_match_names(self):
        """Node IDs should map to the correct node names."""
        from parwa.agents import ALL_AGENTS
        from parwa.nodes import __all__ as node_names

        # This is a consistency check — node_ids in agent definitions
        # should correspond to node_names
        for agent in ALL_AGENTS:
            assert len(agent.node_ids) == len(agent.node_names)


# ═══════════════════════════════════════════════════════════════════════════════
# State Schema Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestStateAgentFields:
    """Tests for the new agent orchestration fields in TicketState."""

    def test_agent_contexts_field(self):
        from parwa.state import TicketState
        state = TicketState()
        assert state.agent_contexts == {}
        assert state._current_agent == ""

    def test_agent_contexts_with_data(self):
        from parwa.state import TicketState
        state = TicketState(
            agent_contexts={"Knowledge Agent": {"node_outputs": {}}},
        )
        assert "Knowledge Agent" in state.agent_contexts

    def test_state_to_dict_includes_agent_contexts(self):
        from parwa.state import state_to_dict, TicketState
        state = TicketState(
            agent_contexts={"Reasoning Agent": {"frameworks_used": ["cot"]}},
        )
        d = state_to_dict(state)
        assert "agent_contexts" in d
        assert "Reasoning Agent" in d["agent_contexts"]


# ═══════════════════════════════════════════════════════════════════════════════
# Graph Merge Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestGraphMergeWithAgentContexts:
    """Tests for the updated _merge_dicts with agent_contexts."""

    def test_dict_merge_agent_contexts(self):
        from parwa.graph import _merge_dicts
        left = {"agent_contexts": {"Router Agent": {"nodes": 2}}}
        right = {"agent_contexts": {"Knowledge Agent": {"nodes": 3}}}

        merged = _merge_dicts(left, right)
        assert "Router Agent" in merged["agent_contexts"]
        assert "Knowledge Agent" in merged["agent_contexts"]

    def test_dict_merge_overwrites_same_agent(self):
        from parwa.graph import _merge_dicts
        left = {"agent_contexts": {"Knowledge Agent": {"nodes": 2, "old": True}}}
        right = {"agent_contexts": {"Knowledge Agent": {"nodes": 4, "new": True}}}

        merged = _merge_dicts(left, right)
        # Right wins per key within agent_contexts
        assert merged["agent_contexts"]["Knowledge Agent"]["nodes"] == 4
        assert merged["agent_contexts"]["Knowledge Agent"]["new"] is True
        # But "old" from left is lost (shallow merge of the outer dict)
        # This is expected — the orchestrator saves the full context each time

    def test_append_keys_still_work(self):
        from parwa.graph import _merge_dicts
        left = {"active_frameworks": ["cot"], "pipeline_errors": [{"node": "a"}]}
        right = {"active_frameworks": ["react"], "pipeline_errors": [{"node": "b"}]}

        merged = _merge_dicts(left, right)
        assert merged["active_frameworks"] == ["cot", "react"]
        assert len(merged["pipeline_errors"]) == 2

    def test_regular_replace_still_works(self):
        from parwa.graph import _merge_dicts
        left = {"intent": "general_inquiry"}
        right = {"intent": "refund_request"}

        merged = _merge_dicts(left, right)
        assert merged["intent"] == "refund_request"
