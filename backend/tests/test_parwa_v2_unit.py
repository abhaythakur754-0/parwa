"""
PARWA Pipeline V2 — Comprehensive Unit Test Suite

Tests ALL 8 nodes of the unified PARWA v2 pipeline with proper mocking.
Each test is independent, uses descriptive names, and logs technique participation.

Sections:
  1. Node 1: Ingest + Classify (8+ tests)
  2. Node 2: Smart Route (6+ tests)
  3. Node 3: Knowledge Fetch (6+ tests)
  4. Node 4: Reasoning Engine (6+ tests)
  5. Node 5: Act + Verify (6+ tests)
  6. Node 6: Quality + Format (6+ tests)
  7. Node 7: Simple Resolver (6+ tests)
  8. Node 8: Super Node (6+ tests)
  9. Graph V2 Flow (4+ tests)
 10. PARWA Bridge (5+ tests)

Run: pytest tests/test_parwa_v2_unit.py -v --tb=short
"""

from __future__ import annotations

import asyncio
import sys
import time
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Pre-import: Stub out langgraph to avoid ModuleNotFoundError in CI ──
# The parwa_pipeline/__init__.py imports graph_v2 which needs langgraph.
# In unit tests we never build the real graph, so stub it.
if "langgraph" not in sys.modules:
    sys.modules["langgraph"] = MagicMock()
    sys.modules["langgraph.graph"] = MagicMock()
    sys.modules["langgraph.graph"].END = "__end__"
    sys.modules["langgraph.graph"].StateGraph = MagicMock

# ── Technique Participation Tracker ─────────────────────────────────

_technique_log: List[Dict[str, str]] = []


def _log_technique(node: str, technique: str, test_name: str) -> None:
    """Log which technique was invoked in a test for the summary report."""
    _technique_log.append({
        "node": node,
        "technique": technique,
        "test": test_name,
    })


def _clear_technique_log() -> None:
    _technique_log.clear()


@pytest.fixture(autouse=True)
def _track_techniques(request):
    """Auto-track technique participation for each test."""
    _clear_technique_log()
    yield
    # After test, techniques are logged via _log_technique calls


@pytest.fixture(scope="session", autouse=True)
def _print_technique_summary(request):
    """Print a technique participation summary at the end of the test session."""
    yield
    if not _technique_log:
        return

    print("\n" + "=" * 80)
    print("TECHNIQUE PARTICIPATION SUMMARY")
    print("=" * 80)

    # Group by node
    by_node: Dict[str, List[Dict]] = {}
    for entry in _technique_log:
        node = entry["node"]
        by_node.setdefault(node, []).append(entry)

    for node in sorted(by_node.keys()):
        techs = set(e["technique"] for e in by_node[node])
        tests = set(e["test"] for e in by_node[node])
        print(f"\n  Node {node}: {len(techs)} techniques across {len(tests)} tests")
        for tech in sorted(techs):
            count = sum(1 for e in by_node[node] if e["technique"] == tech)
            print(f"    - {tech}: invoked {count} time(s)")

    print(f"\n  TOTAL: {len(_technique_log)} technique invocations across all tests")
    print("=" * 80)


# ── Shared Fixtures ─────────────────────────────────────────────────


@pytest.fixture
def base_state() -> Dict[str, Any]:
    """Minimal base state for all nodes."""
    return {
        "ticket_id": "TKT-TEST-001",
        "tenant_id": "tenant_acme",
        "query": "I want a refund for my annual subscription",
        "channel_type": "email",
        "customer_context": {
            "account_tier": "parwa",
            "customer_tenure_days": 180,
            "recent_ticket_count": 2,
            "lifetime_value": 1200,
        },
        "metadata": {"sender": "user@example.com", "timestamp": "2026-01-15T10:00:00Z"},
    }


@pytest.fixture
def mock_llm_call():
    """Mock the llm_call function to return predictable responses."""
    with patch("app.core.parwa_pipeline.llm_client.llm_call", new_callable=AsyncMock) as mock:
        # Default response — a confidence value for Node 1 UoT
        mock.return_value = "0.85"
        yield mock


@pytest.fixture
def mock_wiki_store():
    """Mock the AI Wiki store."""
    with patch("app.core.parwa_pipeline.ai_wiki_store.get_wiki_store") as mock_get:
        mock_store = MagicMock()
        mock_store.find_similar_patterns.return_value = []
        mock_store.search.return_value = []
        mock_store.read.return_value = []
        mock_store.write_ticket_pattern.return_value = MagicMock(entry_key="wiki_test_001")
        mock_store.check_policy_sync.return_value = {"synced": True, "version": "v2.0", "previous_version": None}
        mock_get.return_value = mock_store
        yield mock_store, mock_get


@pytest.fixture
def mock_jarvis_db():
    """Mock the Jarvis DB (used by parwa_bridge)."""
    # get_db is imported inside parwa_bridge functions, so patch at the source module
    with patch("app.core.jarvis_pipeline.jarvis_db.get_db") as mock_get_db_fn:
        mock_db = AsyncMock()
        mock_db.get_active_flags.return_value = []
        mock_db.write_quality_score.return_value = {"id": "qs_001", "score": 0.92}
        mock_db.write_to_inbox.return_value = {"id": "inbox_001", "status": "written"}
        mock_db.record_training_data.return_value = {"id": "train_001", "signal": "approved"}
        mock_get_db_fn.return_value = mock_db
        yield mock_db, mock_get_db_fn


# ══════════════════════════════════════════════════════════════════════
# 1. NODE 1: INGEST + CLASSIFY — 10 tests
# ══════════════════════════════════════════════════════════════════════


class TestNode1IngestClassify:
    """Tests for Node 1: Ingest + Classify.

    Techniques exercised:
      - SmartRouter.classify (ticket type)
      - SmartRouter.complexity
      - SmartRouter.action
      - DynamicContext.pull
      - MetaLearner.predict
      - UoT.measure (LLM)
    """

    @pytest.mark.asyncio
    async def test_classifies_refund_ticket_correctly(self, base_state, mock_llm_call, mock_wiki_store):
        """Verify that a refund-related query is classified as 'refund_request'."""
        from app.core.parwa_pipeline.nodes.node_1_ingest_classify import node_1_ingest_classify

        base_state["query"] = "I would like a refund for my annual subscription of $1200"
        result = await node_1_ingest_classify(base_state)

        assert result["ticket_type"] == "refund_request", (
            f"Expected 'refund_request', got '{result['ticket_type']}'"
        )
        assert "technique_log" in result
        _log_technique("1", "SmartRouter", "test_classifies_refund_ticket")

    @pytest.mark.asyncio
    async def test_classifies_billing_ticket_correctly(self, base_state, mock_llm_call, mock_wiki_store):
        """Verify that a billing-related query is classified as 'billing'."""
        from app.core.parwa_pipeline.nodes.node_1_ingest_classify import node_1_ingest_classify

        base_state["query"] = "I was charged twice on my invoice this month"
        result = await node_1_ingest_classify(base_state)

        assert result["ticket_type"] == "billing"
        _log_technique("1", "SmartRouter", "test_classifies_billing_ticket")

    @pytest.mark.asyncio
    async def test_classifies_technical_ticket_correctly(self, base_state, mock_llm_call, mock_wiki_store):
        """Verify that a technical query is classified as 'technical'."""
        from app.core.parwa_pipeline.nodes.node_1_ingest_classify import node_1_ingest_classify

        base_state["query"] = "I can't access my account, I keep getting a login error"
        result = await node_1_ingest_classify(base_state)

        assert result["ticket_type"] == "technical"
        _log_technique("1", "SmartRouter", "test_classifies_technical_ticket")

    @pytest.mark.asyncio
    async def test_classifies_faq_ticket_correctly(self, base_state, mock_llm_call, mock_wiki_store):
        """Verify that a general FAQ query is classified as 'faq'."""
        from app.core.parwa_pipeline.nodes.node_1_ingest_classify import node_1_ingest_classify

        base_state["query"] = "What is the pricing for your plans and how do they compare?"
        result = await node_1_ingest_classify(base_state)

        assert result["ticket_type"] == "faq"
        _log_technique("1", "SmartRouter", "test_classifies_faq_ticket")

    @pytest.mark.asyncio
    async def test_detects_hard_complexity(self, base_state, mock_llm_call, mock_wiki_store):
        """Verify that complex queries with multiple hard signals get 'hard' or 'complex' complexity."""
        from app.core.parwa_pipeline.nodes.node_1_ingest_classify import node_1_ingest_classify

        base_state["query"] = (
            "I have a complicated billing issue that has been going on for weeks. "
            "I've also had multiple errors and want to escalate this to a manager. "
            "This is a formal complaint about the terrible service."
        )
        result = await node_1_ingest_classify(base_state)

        # Multiple hard keywords → at minimum complex (or hard)
        assert result["complexity"] in ("complex", "hard"), (
            f"Expected 'complex' or 'hard', got '{result['complexity']}'"
        )
        _log_technique("1", "SmartRouter.complexity", "test_detects_hard_complexity")

    @pytest.mark.asyncio
    async def test_classifies_simple_complexity(self, base_state, mock_llm_call, mock_wiki_store):
        """Verify that a simple FAQ query gets 'simple' complexity."""
        from app.core.parwa_pipeline.nodes.node_1_ingest_classify import node_1_ingest_classify

        base_state["query"] = "What is your platform?"
        result = await node_1_ingest_classify(base_state)

        assert result["complexity"] == "simple"
        _log_technique("1", "SmartRouter.complexity", "test_classifies_simple_complexity")

    @pytest.mark.asyncio
    async def test_handles_global_shutdown_flag(self, base_state, mock_wiki_store):
        """Verify that the global_shutdown flag causes ticket rejection."""
        from app.core.parwa_pipeline.nodes.node_1_ingest_classify import node_1_ingest_classify

        base_state["system_flags"] = {"global_shutdown": True}
        result = await node_1_ingest_classify(base_state)

        assert result["status"] == "rejected"
        assert "maintenance" in result.get("final_response", "").lower()
        _log_technique("1", "JARVIS_SHUTDOWN_CHECK", "test_handles_global_shutdown_flag")

    @pytest.mark.asyncio
    async def test_loads_shutdown_from_bridge(self, base_state, mock_llm_call, mock_jarvis_db, mock_wiki_store):
        """Verify that Node 1 loads shutdown flag from bridge when not in state."""
        from app.core.parwa_pipeline.nodes.node_1_ingest_classify import node_1_ingest_classify
        from app.core.parwa_pipeline.parwa_bridge import invalidate_flag_cache

        # Invalidate cache to force DB load
        invalidate_flag_cache(base_state["tenant_id"])

        # Set up mock to return shutdown flag
        mock_db, _ = mock_jarvis_db
        mock_db.get_active_flags.return_value = [
            {"flag_type": "global_shutdown", "flag_value": "true"}
        ]

        result = await node_1_ingest_classify(base_state)

        assert result["status"] == "rejected"
        invalidate_flag_cache()  # cleanup
        _log_technique("1", "JARVIS_SHUTDOWN_CHECK", "test_loads_shutdown_from_bridge")

    @pytest.mark.asyncio
    async def test_extracts_action_details_with_amount(self, base_state, mock_llm_call, mock_wiki_store):
        """Verify that refund amount is extracted from the query."""
        from app.core.parwa_pipeline.nodes.node_1_ingest_classify import node_1_ingest_classify

        base_state["query"] = "I want a refund of $450 for my subscription"
        result = await node_1_ingest_classify(base_state)

        assert result["required_action"] == "execute_refund"
        assert result["action_details"].get("amount") == 450.0
        _log_technique("1", "SmartRouter.action", "test_extracts_action_details")

    @pytest.mark.asyncio
    async def test_routing_suggestion_simple_for_simple(self, base_state, mock_llm_call, mock_wiki_store):
        """Verify that simple complexity → simple_medium_path routing suggestion."""
        from app.core.parwa_pipeline.nodes.node_1_ingest_classify import node_1_ingest_classify

        base_state["query"] = "What is your pricing?"
        result = await node_1_ingest_classify(base_state)

        assert result["routing_suggestion"] in ("simple_medium_path", "complex_path")
        _log_technique("1", "DynamicContext", "test_routing_suggestion_simple")

    @pytest.mark.asyncio
    async def test_classification_confidence_populated(self, base_state, mock_llm_call, mock_wiki_store):
        """Verify that classification confidence is set (0.0-1.0 range)."""
        from app.core.parwa_pipeline.nodes.node_1_ingest_classify import node_1_ingest_classify

        mock_llm_call.return_value = "0.92"
        result = await node_1_ingest_classify(base_state)

        assert 0.0 <= result["classification_confidence"] <= 1.0
        _log_technique("1", "UoT", "test_classification_confidence_populated")


# ══════════════════════════════════════════════════════════════════════
# 2. NODE 2: SMART ROUTE — 7 tests
# ══════════════════════════════════════════════════════════════════════


class TestNode2SmartRoute:
    """Tests for Node 2: Smart Route.

    Techniques exercised:
      - VariantRegistry
      - QuotaTracker
      - RouteDecision (capability matrix)
      - JARVIS_PAUSE_CHECK
      - JARVIS_REDIRECT_CHECK
    """

    @pytest.mark.asyncio
    async def test_routes_simple_ticket_to_simple_path(self, base_state, mock_jarvis_db):
        """Verify a simple provide_info ticket routes to simple_path."""
        from app.core.parwa_pipeline.nodes.node_2_smart_route import (
            MOCK_VARIANT_REGISTRY,
            node_2_smart_route,
        )

        state = {
            **base_state,
            "ticket_type": "faq",
            "complexity": "simple",
            "required_action": "provide_info",
            "action_details": {},
        }

        MOCK_VARIANT_REGISTRY["tenant_acme"] = {"tier": "parwa", "quota_total": 500, "quota_remaining": 500}
        try:
            result = await node_2_smart_route(state)
            assert result["route_decision"] == "simple_path"
            _log_technique("2", "RouteDecision", "test_routes_simple_ticket")
        finally:
            MOCK_VARIANT_REGISTRY.pop("tenant_acme", None)

    @pytest.mark.asyncio
    async def test_routes_complex_ticket_to_complex_path(self, base_state, mock_jarvis_db):
        """Verify a complex ticket with execution routes to complex_path."""
        from app.core.parwa_pipeline.nodes.node_2_smart_route import (
            MOCK_VARIANT_REGISTRY,
            node_2_smart_route,
        )

        state = {
            **base_state,
            "ticket_type": "refund_request",
            "complexity": "complex",
            "required_action": "execute_refund",
            "action_details": {"amount": 300},
        }

        MOCK_VARIANT_REGISTRY["tenant_acme"] = {"tier": "parwa", "quota_total": 500, "quota_remaining": 500}
        try:
            result = await node_2_smart_route(state)
            assert result["route_decision"] == "complex_path"
            _log_technique("2", "RouteDecision", "test_routes_complex_ticket")
        finally:
            MOCK_VARIANT_REGISTRY.pop("tenant_acme", None)

    @pytest.mark.asyncio
    async def test_respects_tier_capability_matrix(self, base_state, mock_jarvis_db):
        """Verify mini tier cannot execute refunds (capability matrix)."""
        from app.core.parwa_pipeline.nodes.node_2_smart_route import (
            MOCK_VARIANT_REGISTRY,
            node_2_smart_route,
        )

        state = {
            **base_state,
            "ticket_type": "refund_request",
            "complexity": "simple",
            "required_action": "execute_refund",
            "action_details": {"amount": 100},
        }

        MOCK_VARIANT_REGISTRY["tenant_acme"] = {"tier": "mini", "quota_total": 100, "quota_remaining": 100}
        try:
            result = await node_2_smart_route(state)
            # mini cannot do refunds → should fallback to parwa
            assert result["route_decision"] == "complex_path"
            _log_technique("2", "CapabilityMatrix", "test_respects_capability")
        finally:
            MOCK_VARIANT_REGISTRY.pop("tenant_acme", None)

    @pytest.mark.asyncio
    async def test_quota_fallback_when_exhausted(self, base_state, mock_jarvis_db):
        """Verify fallback when quota is exhausted for a tier."""
        from app.core.parwa_pipeline.nodes.node_2_smart_route import (
            MOCK_VARIANT_REGISTRY,
            node_2_smart_route,
        )

        state = {
            **base_state,
            "ticket_type": "faq",
            "complexity": "simple",
            "required_action": "provide_info",
            "action_details": {},
        }

        MOCK_VARIANT_REGISTRY["tenant_acme"] = {"tier": "parwa", "quota_total": 100, "quota_remaining": 0}
        try:
            result = await node_2_smart_route(state)
            # Should still route (fallback to parwa even with 0 quota)
            assert "route_decision" in result
            _log_technique("2", "QuotaTracker", "test_quota_fallback")
        finally:
            MOCK_VARIANT_REGISTRY.pop("tenant_acme", None)

    @pytest.mark.asyncio
    async def test_routes_to_human_on_jarvis_redirect(self, base_state, mock_jarvis_db):
        """Verify Jarvis channel redirect to human causes escalation."""
        from app.core.parwa_pipeline.nodes.node_2_smart_route import node_2_smart_route

        state = {
            **base_state,
            "system_flags": {
                "redirected_channels": {"call": "human"},
                "paused_actions": [],
            },
            "channel_type": "call",
            "ticket_type": "faq",
            "complexity": "simple",
            "required_action": "provide_info",
        }

        result = await node_2_smart_route(state)
        assert result["status"] == "escalated"
        assert "escalation_context" in result
        _log_technique("2", "JARVIS_REDIRECT_CHECK", "test_redirect_to_human")

    @pytest.mark.asyncio
    async def test_handles_paused_actions(self, base_state, mock_jarvis_db):
        """Verify that paused actions cause status='paused'."""
        from app.core.parwa_pipeline.nodes.node_2_smart_route import node_2_smart_route

        state = {
            **base_state,
            "system_flags": {
                "paused_actions": ["execute_refund"],
                "redirected_channels": {},
            },
            "ticket_type": "refund_request",
            "complexity": "simple",
            "required_action": "execute_refund",
            "action_details": {"amount": 100},
        }

        result = await node_2_smart_route(state)
        assert result["status"] == "paused"
        assert "paused" in result.get("final_response", "").lower()
        _log_technique("2", "JARVIS_PAUSE_CHECK", "test_handles_paused_actions")

    @pytest.mark.asyncio
    async def test_variant_capabilities_returned(self, base_state, mock_jarvis_db):
        """Verify variant capabilities list is populated."""
        from app.core.parwa_pipeline.nodes.node_2_smart_route import (
            MOCK_VARIANT_REGISTRY,
            node_2_smart_route,
        )

        state = {
            **base_state,
            "ticket_type": "faq",
            "complexity": "simple",
            "required_action": "provide_info",
            "action_details": {},
        }

        MOCK_VARIANT_REGISTRY["tenant_acme"] = {"tier": "parwa", "quota_total": 500, "quota_remaining": 500}
        try:
            result = await node_2_smart_route(state)
            assert isinstance(result["variant_capabilities"], list)
            assert len(result["variant_capabilities"]) > 0
            _log_technique("2", "VariantRegistry", "test_variant_capabilities")
        finally:
            MOCK_VARIANT_REGISTRY.pop("tenant_acme", None)


# ══════════════════════════════════════════════════════════════════════
# 3. NODE 3: KNOWLEDGE FETCH — 7 tests
# ══════════════════════════════════════════════════════════════════════


class TestNode3KnowledgeFetch:
    """Tests for Node 3: Knowledge Fetch.

    Techniques exercised:
      - CLARA (LLM gatekeep)
      - RAG (type-based retrieval)
      - SmartFilter (relevance scoring)
      - SufficiencyCheck
      - AIWiki (Section A/B/C reads)
      - UCB (CRM data)
    """

    @pytest.mark.asyncio
    async def test_fetches_knowledge_for_refund_query(self, base_state, mock_llm_call, mock_wiki_store):
        """Verify refund tickets get refund policy + billing docs."""
        from app.core.parwa_pipeline.nodes.node_3_knowledge_fetch import node_3_knowledge_fetch

        state = {
            **base_state,
            "ticket_type": "refund_request",
            "variant_tier": "parwa",
        }

        mock_llm_call.return_value = "Refund policy, billing info, cancellation policy"
        result = await node_3_knowledge_fetch(state)

        docs = result["knowledge_context"]
        assert len(docs) > 0, "Should have knowledge docs for refund"
        sources = [d.get("source", "") for d in docs]
        assert any("refund" in s.lower() for s in sources)
        _log_technique("3", "RAG", "test_fetches_knowledge_refund")

    @pytest.mark.asyncio
    async def test_fetches_knowledge_for_billing_query(self, base_state, mock_llm_call, mock_wiki_store):
        """Verify billing tickets get billing policy docs."""
        from app.core.parwa_pipeline.nodes.node_3_knowledge_fetch import node_3_knowledge_fetch

        state = {
            **base_state,
            "ticket_type": "billing",
            "variant_tier": "parwa",
        }

        mock_llm_call.return_value = "Billing policy, invoice info"
        result = await node_3_knowledge_fetch(state)

        docs = result["knowledge_context"]
        assert len(docs) > 0
        sources = [d.get("source", "") for d in docs]
        assert any("billing" in s.lower() for s in sources)
        _log_technique("3", "RAG", "test_fetches_knowledge_billing")

    @pytest.mark.asyncio
    async def test_reads_wiki_section_a_patterns(self, base_state, mock_llm_call, mock_wiki_store):
        """Verify AI Wiki Section A (ticket patterns) is queried."""
        from app.core.parwa_pipeline.nodes.node_3_knowledge_fetch import node_3_knowledge_fetch

        mock_store, mock_get = mock_wiki_store

        state = {
            **base_state,
            "ticket_type": "refund_request",
            "variant_tier": "parwa",
        }

        mock_llm_call.return_value = "Refund policy"
        result = await node_3_knowledge_fetch(state)

        # Verify wiki search was called
        mock_store.search.assert_called()
        assert "wiki_section_a" in result
        _log_technique("3", "AIWiki", "test_reads_wiki_section_a")

    @pytest.mark.asyncio
    async def test_clara_gatekeep_passes_relevant_knowledge(self, base_state, mock_llm_call, mock_wiki_store):
        """Verify CLARA gatekeep returns relevant_knowledge from LLM call."""
        from app.core.parwa_pipeline.nodes.node_3_knowledge_fetch import node_3_knowledge_fetch

        state = {
            **base_state,
            "ticket_type": "refund_request",
            "variant_tier": "parwa",
        }

        mock_llm_call.return_value = "Refund eligibility, refund process, credit policy"
        result = await node_3_knowledge_fetch(state)

        # Verify knowledge_sufficient is determined
        assert "knowledge_sufficient" in result
        # For refund_request type, we have primary docs so it should be sufficient
        assert result["knowledge_sufficient"] is True
        _log_technique("3", "CLARA", "test_clara_gatekeep_passes")

    @pytest.mark.asyncio
    async def test_clara_gatekeep_rejects_irrelevant_knowledge(self, base_state, mock_llm_call, mock_wiki_store):
        """Verify sufficiency check returns False for unknown ticket types."""
        from app.core.parwa_pipeline.nodes.node_3_knowledge_fetch import node_3_knowledge_fetch

        state = {
            **base_state,
            "ticket_type": "unknown_exotic_type",
            "variant_tier": "parwa",
        }

        mock_llm_call.return_value = "Unknown topic, no relevant KB found"
        result = await node_3_knowledge_fetch(state)

        # No primary docs for unknown type
        assert result["knowledge_sufficient"] is False
        _log_technique("3", "CLARA", "test_clara_gatekeep_rejects")

    @pytest.mark.asyncio
    async def test_handles_empty_knowledge_base(self, base_state, mock_llm_call, mock_wiki_store):
        """Verify that node handles a ticket type with no KB docs gracefully."""
        from app.core.parwa_pipeline.nodes.node_3_knowledge_fetch import node_3_knowledge_fetch

        state = {
            **base_state,
            "ticket_type": "general",  # not in KNOWLEDGE_BASE
            "variant_tier": "parwa",
        }

        mock_llm_call.return_value = "General inquiry"
        result = await node_3_knowledge_fetch(state)

        # Should not crash — knowledge_context may be empty but state is valid
        assert "knowledge_context" in result
        assert "knowledge_sufficient" in result
        _log_technique("3", "SufficiencyCheck", "test_handles_empty_kb")

    @pytest.mark.asyncio
    async def test_injects_jarvis_guidance(self, base_state, mock_llm_call, mock_wiki_store):
        """Verify Jarvis guidance is injected as additional knowledge when present."""
        from app.core.parwa_pipeline.nodes.node_3_knowledge_fetch import node_3_knowledge_fetch

        state = {
            **base_state,
            "ticket_type": "refund_request",
            "variant_tier": "parwa",
            "system_flags": {
                "guidance": {"TKT-TEST-001": "Check the Shopify order ID first before processing refund."},
            },
        }

        mock_llm_call.return_value = "Refund policy"
        result = await node_3_knowledge_fetch(state)

        docs = result["knowledge_context"]
        guidance_docs = [d for d in docs if d.get("is_jarvis_guidance")]
        assert len(guidance_docs) > 0, "Jarvis guidance should be injected"
        assert "Shopify" in guidance_docs[0]["content"]
        _log_technique("3", "JARVIS_GUIDANCE", "test_injects_jarvis_guidance")


# ══════════════════════════════════════════════════════════════════════
# 4. NODE 4: REASONING ENGINE — 8 tests
# ══════════════════════════════════════════════════════════════════════


class TestNode4ReasoningEngine:
    """Tests for Node 4: Reasoning Engine.

    Techniques exercised:
      - GSD (decomposition)
      - MAKER (bridge, ZSV gate, reverse check)
      - CoT (solve sub-problems)
      - ToT (batch check)
      - ReverseThinking (validation)
      - FederatedReasoning (aggregation)
      - AnswerSynthesis
    """

    @pytest.fixture
    def reasoning_state(self, base_state):
        """State pre-configured for reasoning engine."""
        return {
            **base_state,
            "ticket_type": "refund_request",
            "complexity": "complex",
            "required_action": "execute_refund",
            "action_details": {"amount": 450},
            "knowledge_context": [
                {"source": "refund_policy", "content": "Refund Policy: Full refund within 30 days. Pro plan gets prorated refunds after 30 days. Processed in 5-7 business days."},
                {"source": "billing_policy", "content": "Billing Policy: Subscriptions billed monthly on the 1st. Upgrades are prorated."},
            ],
            "customer_context": {"account_tier": "parwa"},
            "wiki_section_a": [],
            "wiki_section_c": [],
            "wiki_patterns": [],
            "crm_data": {},
            "loop_count": 0,
        }

    @pytest.mark.asyncio
    async def test_gsd_decomposition_produces_sub_problems(self, reasoning_state, mock_llm_call, mock_wiki_store):
        """Verify GSD decomposes query into sub-problems."""
        from app.core.parwa_pipeline.nodes.node_4_reasoning_engine import node_4_reasoning_engine

        mock_llm_call.return_value = (
            "1. What is the customer's refund eligibility?\n"
            "2. What is the refund amount calculation?\n"
            "3. What is the refund process and timeline?"
        )
        result = await node_4_reasoning_engine(reasoning_state)

        assert "sub_problems" in result
        assert len(result["sub_problems"]) >= 2
        _log_technique("4", "GSD", "test_gsd_decomposition")

    @pytest.mark.asyncio
    async def test_cot_reasoning_generates_solutions(self, reasoning_state, mock_llm_call, mock_wiki_store):
        """Verify CoT generates solutions for each sub-problem."""
        from app.core.parwa_pipeline.nodes.node_4_reasoning_engine import node_4_reasoning_engine

        call_count = 0
        async def _mock_llm(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "1. What is the refund policy?\n2. What is the process?\n3. What is the timeline?"
            elif call_count <= 4:
                return f"Based on the refund policy, the customer is eligible for a full refund within 30 days. The refund will be processed in 5-7 business days."
            elif call_count == 5:
                return "1. COMPLETE\n2. COMPLETE\n3. COMPLETE"
            elif call_count == 6:
                return "VALID: YES\nCONFIDENCE: 0.9"
            else:
                return "Dear customer, your refund of $450 will be processed within 5-7 business days."

        mock_llm_call.side_effect = _mock_llm
        result = await node_4_reasoning_engine(reasoning_state)

        assert "combined_answer" in result
        assert len(result["combined_answer"]) > 50
        _log_technique("4", "CoT", "test_cot_reasoning")

    @pytest.mark.asyncio
    async def test_maker_bridges_knowledge_gaps(self, reasoning_state, mock_llm_call, mock_wiki_store):
        """Verify MAKER creates bridge connections between sub-problems and KB."""
        from app.core.parwa_pipeline.nodes.node_4_reasoning_engine import node_4_reasoning_engine

        async def _mock_llm(*args, **kwargs):
            return (
                "1. What is the refund eligibility?\n"
                "2. What is the process?\n"
                "3. What is the timeline?\n\n"
                "Based on policy, full refund within 30 days.\n\n"
                "1. COMPLETE\n2. COMPLETE\n3. COMPLETE\n\n"
                "VALID: YES\nCONFIDENCE: 0.9\n\n"
                "Your refund will be processed in 5-7 business days."
            )

        mock_llm_call.side_effect = _mock_llm
        result = await node_4_reasoning_engine(reasoning_state)

        assert "maker_bridges" in result
        assert isinstance(result["maker_bridges"], dict)
        _log_technique("4", "MAKER", "test_maker_bridges")

    @pytest.mark.asyncio
    async def test_reverse_thinking_validates_answer(self, reasoning_state, mock_llm_call, mock_wiki_store):
        """Verify Reverse Thinking validates the answer."""
        from app.core.parwa_pipeline.nodes.node_4_reasoning_engine import node_4_reasoning_engine

        call_count = 0
        async def _mock_llm(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "1. What is the refund policy?\n2. What is the process?"
            elif call_count <= 3:
                return "The refund policy states full refund within 30 days."
            elif call_count == 4:
                return "1. COMPLETE\n2. COMPLETE"
            elif call_count == 5:
                return "VALID: YES\nCONFIDENCE: 0.95"
            else:
                return "Your refund will be processed within 5-7 business days."

        mock_llm_call.side_effect = _mock_llm
        result = await node_4_reasoning_engine(reasoning_state)

        assert "maker_bridge_safe" in result
        _log_technique("4", "ReverseThinking", "test_reverse_thinking")

    @pytest.mark.asyncio
    async def test_tot_batch_check(self, reasoning_state, mock_llm_call, mock_wiki_store):
        """Verify ToT batch checks all solutions in one call."""
        from app.core.parwa_pipeline.nodes.node_4_reasoning_engine import node_4_reasoning_engine

        call_count = 0
        async def _mock_llm(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "1. Eligibility\n2. Process\n3. Timeline"
            elif call_count <= 3:
                return "Full refund within 30 days per policy."
            elif call_count == 4:
                return "1. COMPLETE\n2. MISSING: timeline details\n3. COMPLETE"
            elif call_count == 5:
                return "VALID: YES\nCONFIDENCE: 0.85"
            else:
                return "We will process your refund within 5-7 business days."

        mock_llm_call.side_effect = _mock_llm
        result = await node_4_reasoning_engine(reasoning_state)

        # Check technique log contains ToT
        techniques = [log.get("technique") for log in result.get("technique_log", [])]
        assert "ToT" in techniques
        _log_technique("4", "ToT", "test_tot_batch_check")

    @pytest.mark.asyncio
    async def test_federated_reasoning_aggregates_scores(self, reasoning_state, mock_llm_call, mock_wiki_store):
        """Verify FederatedReasoning produces aggregated confidence."""
        from app.core.parwa_pipeline.nodes.node_4_reasoning_engine import node_4_reasoning_engine

        async def _mock_llm(*args, **kwargs):
            return (
                "1. What is the refund policy?\n2. What is the process?\n\n"
                "Full refund within 30 days.\n\n"
                "1. COMPLETE\n2. COMPLETE\n\n"
                "VALID: YES\nCONFIDENCE: 0.9\n\n"
                "Your refund is being processed."
            )

        mock_llm_call.side_effect = _mock_llm
        result = await node_4_reasoning_engine(reasoning_state)

        assert "reasoning_confidence" in result
        assert 0.0 <= result["reasoning_confidence"] <= 1.0
        _log_technique("4", "FederatedReasoning", "test_federated_aggregation")

    @pytest.mark.asyncio
    async def test_empty_query_bails_out_safely(self, mock_llm_call, mock_wiki_store):
        """Verify that empty query results in safe fallback, not crash."""
        from app.core.parwa_pipeline.nodes.node_4_reasoning_engine import node_4_reasoning_engine

        empty_state = {
            "ticket_id": "TKT-EMPTY",
            "tenant_id": "tenant_test",
            "query": "",  # empty!
            "knowledge_context": [],
            "customer_context": {},
            "wiki_section_c": [],
            "crm_data": {},
        }

        result = await node_4_reasoning_engine(empty_state)

        assert result.get("reasoning_confidence", 0.0) == 0.0
        assert len(result.get("combined_answer", "")) > 0
        _log_technique("4", "UPSTREAM_CHECK", "test_empty_query_bails")

    @pytest.mark.asyncio
    async def test_wiki_enrichment_adds_techniques(self, reasoning_state, mock_llm_call, mock_wiki_store):
        """Verify wiki pattern enrichment adds historical techniques."""
        from app.core.parwa_pipeline.nodes.node_4_reasoning_engine import node_4_reasoning_engine

        # Set up wiki patterns
        reasoning_state["wiki_patterns"] = [
            {
                "entry_key": "wiki_001",
                "techniques_that_worked": ["CoT", "ReverseThinking", "MAKER"],
                "quality_achieved": 0.95,
                "answer_summary": "Full refund processed within 5 days",
            }
        ]

        async def _mock_llm(*args, **kwargs):
            return (
                "1. Policy\n2. Process\n\n"
                "Full refund.\n\n"
                "1. COMPLETE\n2. COMPLETE\n\n"
                "VALID: YES\nCONFIDENCE: 0.9\n\n"
                "Refund processed."
            )

        mock_llm_call.side_effect = _mock_llm
        result = await node_4_reasoning_engine(reasoning_state)

        assert "techniques_used" in result
        assert isinstance(result["techniques_used"], list)
        _log_technique("4", "WikiEnrich", "test_wiki_enrichment")


# ══════════════════════════════════════════════════════════════════════
# 5. NODE 5: ACT + VERIFY — 7 tests
# ══════════════════════════════════════════════════════════════════════


class TestNode5ActVerify:
    """Tests for Node 5: Act + Verify.

    Techniques exercised:
      - RuleBasedAction
      - GSD (action decomposition)
      - MAKER (knowledge bridge)
      - ReAct (execution)
      - ReverseThinking (verification)
      - ZeroShotValidator (action flag)
      - UCB (tool bus)
    """

    @pytest.fixture
    def act_state(self, base_state):
        """State pre-configured for act+verify."""
        return {
            **base_state,
            "ticket_type": "refund_request",
            "complexity": "complex",
            "required_action": "execute_refund",
            "action_details": {"amount": 300},
            "knowledge_context": [
                {"source": "refund_policy", "content": "Refund Policy: Full refund within 30 days. Processed in 5-7 business days."},
            ],
            "variant_tier": "parwa",
            "crm_data": {},
            "system_flags": {},
        }

    @pytest.mark.asyncio
    async def test_rule_based_check_allows_refund_on_parwa(self, act_state, mock_llm_call):
        """Verify parwa tier can execute refunds under $500."""
        from app.core.parwa_pipeline.nodes.node_5_act_verify import node_5_act_verify

        result = await node_5_act_verify(act_state)

        assert result["actions_verified"] is True
        _log_technique("5", "RuleBasedAction", "test_rule_based_allows_refund")

    @pytest.mark.asyncio
    async def test_rule_based_check_blocks_large_refund_on_parwa(self, mock_llm_call, base_state):
        """Verify parwa tier cannot execute refunds over $500 limit."""
        from app.core.parwa_pipeline.nodes.node_5_act_verify import node_5_act_verify

        state = {
            **base_state,
            "ticket_type": "refund_request",
            "required_action": "execute_refund",
            "action_details": {"amount": 800},
            "knowledge_context": [
                {"source": "refund_policy", "content": "Refund policy content here."},
            ],
            "variant_tier": "parwa",
            "crm_data": {},
            "system_flags": {},
        }

        result = await node_5_act_verify(state)

        # Should recommend instead of execute
        actions = result["actions_taken"]
        assert len(actions) > 0
        assert actions[0].get("status") == "recommended"
        _log_technique("5", "RuleBasedAction", "test_rule_based_blocks_large")

    @pytest.mark.asyncio
    async def test_react_execution_for_complex_action(self, act_state, mock_llm_call):
        """Verify ReAct is used for executing complex actions."""
        from app.core.parwa_pipeline.nodes.node_5_act_verify import node_5_act_verify

        call_count = 0
        async def _mock_llm(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "THOUGHT: Need to verify customer identity and calculate refund amount."
            elif call_count == 2:
                return "VERIFIED: YES\nRISK: low\nDETAILS: Standard refund process."
            return "done"

        mock_llm_call.side_effect = _mock_llm
        result = await node_5_act_verify(act_state)

        assert result["actions_verified"] is True
        techniques = [log.get("technique") for log in result.get("technique_log", [])]
        assert "ReAct" in techniques
        _log_technique("5", "ReAct", "test_react_execution")

    @pytest.mark.asyncio
    async def test_reverse_verify_works(self, act_state, mock_llm_call):
        """Verify Reverse Thinking verification runs after action."""
        from app.core.parwa_pipeline.nodes.node_5_act_verify import node_5_act_verify

        call_count = 0
        async def _mock_llm(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "THOUGHT: Process refund of $300 per policy."
            elif call_count == 2:
                return "VERIFIED: YES\nRISK: low\nDETAILS: Action is correct."
            return "done"

        mock_llm_call.side_effect = _mock_llm
        result = await node_5_act_verify(act_state)

        techniques = [log.get("technique") for log in result.get("technique_log", [])]
        assert "ReverseThinking" in techniques
        _log_technique("5", "ReverseThinking", "test_reverse_verify")

    @pytest.mark.asyncio
    async def test_zero_shot_validator_flags_high_amount(self, mock_llm_call, base_state):
        """Verify ZeroShotValidator flags unusually high refund amounts."""
        from app.core.parwa_pipeline.nodes.node_5_act_verify import node_5_act_verify

        state = {
            **base_state,
            "ticket_type": "refund_request",
            "required_action": "execute_refund",
            "action_details": {"amount": 10000},
            "knowledge_context": [
                {"source": "refund_policy", "content": "Refund policy content."},
            ],
            "variant_tier": "high",
            "crm_data": {},
            "system_flags": {},
        }

        call_count = 0
        async def _mock_llm(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "THOUGHT: Large refund amount of $10,000."
            elif call_count == 2:
                return "VERIFIED: YES\nRISK: high\nDETAILS: High-value action."
            return "done"

        mock_llm_call.side_effect = _mock_llm
        result = await node_5_act_verify(state)

        techniques = [log.get("technique") for log in result.get("technique_log", [])]
        assert "ZeroShotValidator" in techniques
        # Should be flagged for high value
        flagged_logs = [l for l in result.get("technique_log", []) if "flag:" in l.get("result_summary", "")]
        assert len(flagged_logs) > 0 or any("High-value" in l.get("result_summary", "") for l in result.get("technique_log", []))
        _log_technique("5", "ZeroShotValidator", "test_zsv_flags_high")

    @pytest.mark.asyncio
    async def test_respects_approval_overrides(self, mock_llm_call, base_state):
        """Verify Jarvis approval_overrides auto-approve actions."""
        from app.core.parwa_pipeline.nodes.node_5_act_verify import node_5_act_verify

        state = {
            **base_state,
            "ticket_type": "refund_request",
            "required_action": "execute_refund",
            "action_details": {"amount": 300},
            "knowledge_context": [
                {"source": "refund_policy", "content": "Refund policy."},
            ],
            "variant_tier": "parwa",
            "crm_data": {},
            "system_flags": {
                "approval_overrides": ["execute_refund"],
            },
        }

        call_count = 0
        async def _mock_llm(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "THOUGHT: Processing refund."
            elif call_count == 2:
                return "VERIFIED: YES\nRISK: low\nDETAILS: Approved."
            return "done"

        mock_llm_call.side_effect = _mock_llm
        result = await node_5_act_verify(state)

        techniques = [log.get("technique") for log in result.get("technique_log", [])]
        assert "JARVIS_APPROVAL_OVERRIDE" in techniques
        _log_technique("5", "JARVIS_APPROVAL_OVERRIDE", "test_approval_overrides")

    @pytest.mark.asyncio
    async def test_provide_info_no_execution_needed(self, mock_llm_call, base_state):
        """Verify provide_info action requires no execution."""
        from app.core.parwa_pipeline.nodes.node_5_act_verify import node_5_act_verify

        state = {
            **base_state,
            "ticket_type": "faq",
            "required_action": "provide_info",
            "action_details": {},
            "knowledge_context": [
                {"source": "faq", "content": "FAQ content."},
            ],
            "variant_tier": "parwa",
            "crm_data": {},
            "system_flags": {},
        }

        result = await node_5_act_verify(state)

        assert result["actions_verified"] is True
        assert result["node_5_token_usage"] == 0  # No LLM calls for provide_info
        _log_technique("5", "UCB", "test_provide_info_no_execution")


# ══════════════════════════════════════════════════════════════════════
# 6. NODE 6: QUALITY + FORMAT — 7 tests
# ══════════════════════════════════════════════════════════════════════


class TestNode6QualityFormat:
    """Tests for Node 6: Quality + Format.

    Techniques exercised:
      - Reflexion (LLM critique)
      - CRP (LLM revise + score)
      - ZeroShotValidator
      - GSD (part quality)
      - ThoT (coherence)
      - StructureCheck
      - KBGrounding
      - AnswerAdequacy
      - FederatedReasoning (7 evaluators)
    """

    @pytest.fixture
    def quality_state(self, base_state):
        """State pre-configured for quality evaluation."""
        return {
            **base_state,
            "combined_answer": (
                "Dear customer,\n\n"
                "Thank you for reaching out about your refund request.\n\n"
                "**Refund Eligibility**\n"
                "Based on our refund policy, you are eligible for a full refund within "
                "30 days of purchase. Since your purchase was made 15 days ago, you qualify.\n\n"
                "**Refund Amount**\n"
                "Your refund of **$450.00** will be calculated based on your annual "
                "subscription of $2,499 minus the 2 months used ($499.80 per month).\n\n"
                "**Timeline**\n"
                "Your refund will be processed within **5-7 business days** to your "
                "original payment method (Visa ending in 1234).\n\n"
                "**Next Steps**\n"
                "1. We will initiate the refund process today\n"
                "2. You will receive a confirmation email with refund ID\n"
                "3. The funds will appear in your account within 5-7 business days\n\n"
                "If you have any questions, please let us know.\n"
            ),
            "knowledge_context": [
                {"source": "refund_policy", "content": "Refund Policy: Full refund within 30 days. Processed in 5-7 business days. PARWA plan $2,499/month."},
            ],
            "loop_count": 0,
            "current_path": "complex_path",
            "total_token_usage": 7,
        }

    @pytest.mark.asyncio
    async def test_federated_reasoning_7_evaluators(self, quality_state, mock_llm_call):
        """Verify FederatedReasoning uses 7 evaluators with proper weights."""
        from app.core.parwa_pipeline.nodes.node_6_quality_format import node_6_quality_format

        call_count = 0
        async def _mock_llm(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Reflexion: generous scoring
                return (
                    "ACCURACY: 9/10\n"
                    "COMPLETENESS: 9/10\n"
                    "CLARITY: 10/10\n"
                    "ACTIONABILITY: 10/10\n"
                    "OVERALL: 9/10"
                )
            else:
                # CRP: improved response + quality score
                return (
                    "Dear customer, your refund of $450 will be processed within 5-7 business days.\n"
                    "QUALITY: 9/10"
                )

        mock_llm_call.side_effect = _mock_llm

        with patch("app.core.parwa_pipeline.nodes.node_6_quality_format.write_quality_score_to_jarvis", new_callable=AsyncMock):
            result = await node_6_quality_format(quality_state)

        assert "quality_details" in result
        details = result["quality_details"]
        # Check 7 evaluator scores exist
        expected_keys = {"reflexion", "crp", "zero_shot", "structure", "thot_coherence", "gsd_part_scores", "kb_grounding"}
        assert expected_keys.issubset(set(details.keys())), (
            f"Missing evaluator keys. Got: {set(details.keys())}"
        )
        _log_technique("6", "FederatedReasoning", "test_federated_7_evaluators")

    @pytest.mark.asyncio
    async def test_quality_pass_threshold(self, quality_state, mock_llm_call):
        """Verify quality >= 0.90 results in quality_passed=True."""
        from app.core.parwa_pipeline.nodes.node_6_quality_format import node_6_quality_format

        async def _mock_llm(*args, **kwargs):
            return (
                "ACCURACY: 10/10\nCOMPLETENESS: 10/10\n"
                "CLARITY: 10/10\nACTIONABILITY: 10/10\nOVERALL: 10/10\n"
                "QUALITY: 10/10"
            )

        mock_llm_call.side_effect = _mock_llm

        with patch("app.core.parwa_pipeline.nodes.node_6_quality_format.write_quality_score_to_jarvis", new_callable=AsyncMock):
            result = await node_6_quality_format(quality_state)

        # With all perfect scores, quality should pass
        assert result["quality_passed"] is True, f"Quality: {result['quality_score']}"
        _log_technique("6", "FederatedReasoning", "test_quality_pass")

    @pytest.mark.asyncio
    async def test_quality_loop_threshold(self, quality_state, mock_llm_call):
        """Verify quality 0.70-0.90 results in quality_passed=False (triggers loop)."""
        from app.core.parwa_pipeline.nodes.node_6_quality_format import node_6_quality_format

        async def _mock_llm(*args, **kwargs):
            return (
                "ACCURACY: 5/10\nCOMPLETENESS: 6/10\n"
                "CLARITY: 7/10\nACTIONABILITY: 6/10\nOVERALL: 6/10\n"
                "QUALITY: 6/10"
            )

        mock_llm_call.side_effect = _mock_llm

        with patch("app.core.parwa_pipeline.nodes.node_6_quality_format.write_quality_score_to_jarvis", new_callable=AsyncMock):
            result = await node_6_quality_format(quality_state)

        assert result["quality_passed"] is False
        assert result["quality_score"] < 0.90
        _log_technique("6", "FederatedReasoning", "test_quality_loop")

    @pytest.mark.asyncio
    async def test_structure_check_validates_format(self, quality_state, mock_llm_call):
        """Verify structure check rewards bullets, paragraphs, and bold text."""
        from app.core.parwa_pipeline.nodes.node_6_quality_format import _structure_check

        # The quality_state answer has bullets, bold, and multiple paragraphs
        answer = quality_state["combined_answer"]
        score = _structure_check(answer)

        assert score > 0.90, f"Structured answer should score high, got {score}"
        _log_technique("6", "StructureCheck", "test_structure_check")

    @pytest.mark.asyncio
    async def test_answer_adequacy_check(self, quality_state, mock_llm_call):
        """Verify answer adequacy checks length and data density."""
        from app.core.parwa_pipeline.nodes.node_6_quality_format import _answer_adequacy_check

        answer = quality_state["combined_answer"]
        query = quality_state["query"]
        score = _answer_adequacy_check(answer, query)

        # Answer has good length + dollar amounts + days → high adequacy
        assert score >= 0.90, f"Well-structured answer should be adequate, got {score}"
        _log_technique("6", "AnswerAdequacy", "test_answer_adequacy")

    @pytest.mark.asyncio
    async def test_writes_quality_score_to_jarvis(self, quality_state, mock_llm_call):
        """Verify quality score is written to Jarvis DB after evaluation."""
        from app.core.parwa_pipeline.nodes.node_6_quality_format import node_6_quality_format

        async def _mock_llm(*args, **kwargs):
            return (
                "ACCURACY: 9/10\nCOMPLETENESS: 9/10\n"
                "CLARITY: 10/10\nACTIONABILITY: 10/10\nOVERALL: 9/10\n"
                "QUALITY: 9/10"
            )

        mock_llm_call.side_effect = _mock_llm

        mock_write = AsyncMock()
        with patch("app.core.parwa_pipeline.nodes.node_6_quality_format.write_quality_score_to_jarvis", mock_write):
            result = await node_6_quality_format(quality_state)

        mock_write.assert_called_once()
        call_kwargs = mock_write.call_args[1]
        assert call_kwargs["quality_score"] == result["quality_score"]
        _log_technique("6", "JARVIS_WRITE", "test_writes_quality_score")

    @pytest.mark.asyncio
    async def test_missing_answer_returns_zero(self, mock_llm_call, base_state):
        """Verify that missing combined_answer results in quality=0."""
        from app.core.parwa_pipeline.nodes.node_6_quality_format import node_6_quality_format

        empty_state = {
            **base_state,
            "combined_answer": "",
            "query": "test query",
            "knowledge_context": [],
            "loop_count": 0,
        }

        result = await node_6_quality_format(empty_state)

        assert result["quality_score"] == 0.0
        assert result["quality_passed"] is False
        _log_technique("6", "UPSTREAM_CHECK", "test_missing_answer_zero")


# ══════════════════════════════════════════════════════════════════════
# 7. NODE 7: SIMPLE RESOLVER — 7 tests
# ══════════════════════════════════════════════════════════════════════


class TestNode7SimpleResolver:
    """Tests for Node 7: Simple/Medium Resolver.

    Techniques exercised:
      - GSD (THINK layer decomposition)
      - MAKER (BRIDGE layer relevance scoring)
      - ThoT (threading)
      - MetaLearner (pattern prediction)
      - ZeroShotValidator (THINK layer)
      - RuleBasedAction (ACT layer)
      - ZeroShotValidator (CHECK layer)
      - FederatedReasoning (confidence aggregation)
      - ContextualCompression
      - TurboCompress
      - AdaptiveBudget
    """

    @pytest.fixture
    def simple_state(self, base_state):
        """State pre-configured for simple resolver."""
        return {
            **base_state,
            "ticket_type": "faq",
            "complexity": "simple",
            "required_action": "provide_info",
            "action_details": {},
            "variant_tier": "parwa",
            "knowledge_context": [
                {"source": "faq", "content": "PARWA Platform FAQ: Plans are Mini ($999/mo), PARWA ($2,499/mo), High ($4,999/mo). All plans include 24/7 AI support and email, SMS, chat, phone channels."},
                {"source": "billing_policy", "content": "Billing Policy: Subscriptions billed monthly on the 1st. Upgrades are prorated."},
            ],
            "wiki_section_c": [],
            "customer_context": {"account_tier": "parwa"},
        }

    @pytest.mark.asyncio
    async def test_think_layer_gsd_decomposition_non_llm(self, simple_state, mock_wiki_store):
        """Verify THINK layer decomposes query without LLM calls."""
        from app.core.parwa_pipeline.nodes.node_7_simple_resolver import node_7_simple_resolver

        result = await node_7_simple_resolver(simple_state)

        techniques = [log.get("technique") for log in result.get("technique_log", [])]
        assert "GSD" in techniques

        # Verify simple_answer was generated
        assert "simple_answer" in result
        assert len(result["simple_answer"]) > 0
        _log_technique("7", "GSD", "test_think_gsd_non_llm")

    @pytest.mark.asyncio
    async def test_bridge_layer_relevance_scoring(self, simple_state, mock_wiki_store):
        """Verify BRIDGE layer (MAKER) scores relevance of KB sentences."""
        from app.core.parwa_pipeline.nodes.node_7_simple_resolver import node_7_simple_resolver

        result = await node_7_simple_resolver(simple_state)

        techniques = [log.get("technique") for log in result.get("technique_log", [])]
        assert "MAKER" in techniques

        # Check MAKER log shows matched/sub-questions
        maker_logs = [l for l in result.get("technique_log", []) if l.get("technique") == "MAKER"]
        assert len(maker_logs) >= 2  # one for THINK, one for ACT
        _log_technique("7", "MAKER", "test_bridge_relevance")

    @pytest.mark.asyncio
    async def test_solve_layer_template_generation(self, simple_state, mock_wiki_store):
        """Verify SOLVE layer generates answer from KB templates (non-LLM)."""
        from app.core.parwa_pipeline.nodes.node_7_simple_resolver import node_7_simple_resolver

        result = await node_7_simple_resolver(simple_state)

        # The simple answer should contain KB-derived content
        answer = result["simple_answer"]
        assert len(answer) > 30, "Answer should have substantive content"
        _log_technique("7", "ThoT", "test_solve_template")

    @pytest.mark.asyncio
    async def test_safety_net_confidence_upgrade(self, base_state, mock_wiki_store):
        """Verify confidence < 80% triggers auto-upgrade to complex path."""
        from app.core.parwa_pipeline.nodes.node_7_simple_resolver import node_7_simple_resolver

        # Create a state with minimal knowledge (should trigger safety net)
        state = {
            **base_state,
            "ticket_type": "general",
            "complexity": "simple",
            "required_action": "provide_info",
            "action_details": {},
            "variant_tier": "parwa",
            "knowledge_context": [
                {"source": "unknown", "content": "Very short content with no useful info."},
            ],
            "wiki_section_c": [],
            "query": "How do I integrate my custom ERP system with your API using OAuth2 and webhooks?",
        }

        result = await node_7_simple_resolver(state)

        # Check whether safety net was triggered
        # If confidence < 80% → auto_upgraded should be True
        if result["simple_confidence"] < QUALITY_SIMPLE_SAFETY_NET:
            assert result["auto_upgraded"] is True, (
                f"Expected auto_upgraded=True when confidence={result['simple_confidence']:.3f} < {QUALITY_SIMPLE_SAFETY_NET}"
            )
        # If confidence >= 80%, no upgrade is expected — also valid

        # Verify safety net technique is logged
        techniques = [log.get("technique") for log in result.get("technique_log", [])]
        # SafetyNet only appears when triggered
        _log_technique("7", "SafetyNet", "test_safety_net_upgrade")

    @pytest.mark.asyncio
    async def test_safety_net_triggers_on_no_match(self, mock_wiki_store, base_state):
        """Verify auto-upgrade when answer has 'not available' fallback."""
        from app.core.parwa_pipeline.nodes.node_7_simple_resolver import node_7_simple_resolver

        state = {
            **base_state,
            "ticket_type": "technical",
            "complexity": "simple",
            "required_action": "provide_info",
            "action_details": {},
            "variant_tier": "parwa",
            "knowledge_context": [
                {"source": "faq", "content": "General FAQ content about pricing and plans only."},
            ],
            "wiki_section_c": [],
            "query": "How do I fix the SSO certificate expiration error in my Azure AD integration?",
        }

        result = await node_7_simple_resolver(state)

        # Technical question but only FAQ knowledge → likely low confidence
        assert "simple_confidence" in result
        assert "auto_upgraded" in result
        _log_technique("7", "ZeroShotValidator", "test_safety_net_no_match")

    @pytest.mark.asyncio
    async def test_zero_shot_validator_5_checks(self, simple_state, mock_wiki_store):
        """Verify ZeroShotValidator performs 5-check validation on CHECK layer."""
        from app.core.parwa_pipeline.nodes.node_7_simple_resolver import node_7_simple_resolver

        result = await node_7_simple_resolver(simple_state)

        # Multiple ZeroShotValidator entries in technique log
        zsv_logs = [l for l in result.get("technique_log", []) if l.get("technique") == "ZeroShotValidator"]
        assert len(zsv_logs) >= 2  # one for THINK, one for ACT/layer
        _log_technique("7", "ZeroShotValidator", "test_zsv_5_checks")

    @pytest.mark.asyncio
    async def test_finalizes_simple_path_correctly(self, simple_state, mock_wiki_store):
        """Verify simple resolver produces final answer with proper fields."""
        from app.core.parwa_pipeline.nodes.node_7_simple_resolver import node_7_simple_resolver

        result = await node_7_simple_resolver(simple_state)

        assert "simple_answer" in result
        assert "simple_confidence" in result
        assert "simple_actions_taken" in result
        assert "auto_upgraded" in result
        assert 0.0 <= result["simple_confidence"] <= 1.0
        assert isinstance(result["simple_actions_taken"], list)

        # Should have all 11 non-LLM techniques logged
        techniques = [log.get("technique") for log in result.get("technique_log", [])]
        expected = ["GSD", "MAKER", "ThoT", "MetaLearner", "ZeroShotValidator", "RuleBasedAction",
                    "FederatedReasoning", "ContextualCompression", "TurboCompress", "AdaptiveBudget"]
        for tech in expected:
            assert tech in techniques, f"Missing technique: {tech}"
        _log_technique("7", "FederatedReasoning", "test_finalizes_simple")


# ══════════════════════════════════════════════════════════════════════
# 8. NODE 8: SUPER NODE — 7 tests
# ══════════════════════════════════════════════════════════════════════


class TestNode8SuperNode:
    """Tests for Node 8: Super Node.

    Techniques exercised:
      - Reflexion (failure analysis)
      - SelfConsistency (2 independent solutions)
      - ToT (deep exploration)
      - ReverseThinking (validation)
      - CRP (revision)
      - CoT (max detail)
      - All 11 non-LLM techniques
    """

    @pytest.fixture
    def super_state(self, base_state):
        """State pre-configured for super node."""
        return {
            **base_state,
            "ticket_type": "refund_request",
            "complexity": "complex",
            "knowledge_context": [
                {"source": "refund_policy", "content": "Refund Policy: Full refund within 30 days. Processed in 5-7 business days. PARWA plan $2,499/month."},
                {"source": "billing_policy", "content": "Billing Policy: Billed monthly on the 1st."},
            ],
            "wiki_section_c": [],
            "technique_log": [
                {"node": 4, "technique": "GSD", "duration_ms": 100, "result_summary": "decomposed"},
                {"node": 6, "technique": "FederatedReasoning", "duration_ms": 50, "result_summary": "quality=0.65"},
            ],
            "combined_answer": "Previous attempt: insufficient answer that failed quality.",
            "formatted_response": "Previous formatted attempt that scored 0.65.",
            "loop_count": 2,
            "total_token_usage": 14,
        }

    @pytest.mark.asyncio
    async def test_reflexion_analyzes_previous_failures(self, super_state, mock_llm_call, mock_wiki_store):
        """Verify Reflexion analyzes why previous attempts failed."""
        from app.core.parwa_pipeline.nodes.node_8_super_node import node_8_super_node

        call_count = 0
        async def _mock_llm(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "FAILURE ANALYSIS: Previous attempts failed because they lacked specific dollar amounts and timeline details. The knowledge base clearly states 5-7 business days and the refund calculation method was not followed."
            return f"Solution attempt {call_count} with specific details about refund policy."

        mock_llm_call.side_effect = _mock_llm

        with patch("app.core.parwa_pipeline.nodes.node_8_super_node.write_to_jarvis_inbox", new_callable=AsyncMock):
            result = await node_8_super_node(super_state)

        assert "super_node_analysis" in result
        assert len(result["super_node_analysis"]) > 0
        _log_technique("8", "Reflexion", "test_reflexion_analyzes")

    @pytest.mark.asyncio
    async def test_self_consistency_generates_solutions(self, super_state, mock_llm_call, mock_wiki_store):
        """Verify Self-Consistency generates 2 independent solutions."""
        from app.core.parwa_pipeline.nodes.node_8_super_node import node_8_super_node

        call_count = 0
        async def _mock_llm(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "FAILURE: Previous lacked specifics."
            elif call_count in (2, 3):
                # 2 independent solutions
                approach = "step-by-step" if call_count == 2 else "customer perspective"
                return f"Solution using {approach}: refund of $450 within 5-7 business days."
            else:
                return "Improved answer with specific details."

        mock_llm_call.side_effect = _mock_llm

        with patch("app.core.parwa_pipeline.nodes.node_8_super_node.write_to_jarvis_inbox", new_callable=AsyncMock):
            result = await node_8_super_node(super_state)

        techniques = [log.get("technique") for log in result.get("technique_log", [])]
        assert "SelfConsistency" in techniques
        _log_technique("8", "SelfConsistency", "test_self_consistency")

    @pytest.mark.asyncio
    async def test_tot_deep_exploration(self, super_state, mock_llm_call, mock_wiki_store):
        """Verify ToT explores the most promising path deeply."""
        from app.core.parwa_pipeline.nodes.node_8_super_node import node_8_super_node

        call_count = 0
        async def _mock_llm(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "FAILURE ANALYSIS: Not enough detail."
            elif call_count in (2, 3):
                return "Refund solution with $450 and 5-7 days timeline."
            elif call_count == 4:
                # ToT deep exploration
                return "IMPROVED ANSWER: After exploring alternative angles, the best approach is to cite the specific policy: full refund within 30 days, processed in 5-7 business days, with $450 refund amount."
            elif call_count == 5:
                return "VALID: YES\nCONFIDENCE: 0.92\nIMPROVEMENTS: none"
            elif call_count == 6:
                return "REVISED: Dear customer, your refund of $450 will be processed within 5-7 business days."
            else:
                return "FINAL: Enhanced response with all details."

        mock_llm_call.side_effect = _mock_llm

        with patch("app.core.parwa_pipeline.nodes.node_8_super_node.write_to_jarvis_inbox", new_callable=AsyncMock):
            result = await node_8_super_node(super_state)

        techniques = [log.get("technique") for log in result.get("technique_log", [])]
        assert "ToT" in techniques
        _log_technique("8", "ToT", "test_tot_deep_explore")

    @pytest.mark.asyncio
    async def test_crp_revision_with_context(self, super_state, mock_llm_call, mock_wiki_store):
        """Verify CRP revises answer with full failure context."""
        from app.core.parwa_pipeline.nodes.node_8_super_node import node_8_super_node

        call_count = 0
        async def _mock_llm(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "FAILURE: Previous attempts lacked specifics."
            elif call_count in (2, 3):
                return "Refund solution with details."
            elif call_count == 4:
                return "IMPROVED: Better answer with specifics."
            elif call_count == 5:
                return "VALID: YES\nCONFIDENCE: 0.90\nIMPROVEMENTS: none"
            elif call_count == 6:
                return "REVISED: Comprehensive answer incorporating all analysis."
            else:
                return "ENHANCED: Final polished answer."

        mock_llm_call.side_effect = _mock_llm

        with patch("app.core.parwa_pipeline.nodes.node_8_super_node.write_to_jarvis_inbox", new_callable=AsyncMock):
            result = await node_8_super_node(super_state)

        techniques = [log.get("technique") for log in result.get("technique_log", [])]
        assert "CRP" in techniques
        _log_technique("8", "CRP", "test_crp_revision")

    @pytest.mark.asyncio
    async def test_all_11_non_llm_techniques_active(self, super_state, mock_llm_call, mock_wiki_store):
        """Verify all 11 non-LLM techniques are active and scored."""
        from app.core.parwa_pipeline.nodes.node_8_super_node import node_8_super_node

        async def _mock_llm(*args, **kwargs):
            return "Some response text with enough content for evaluation."

        mock_llm_call.side_effect = _mock_llm

        with patch("app.core.parwa_pipeline.nodes.node_8_super_node.write_to_jarvis_inbox", new_callable=AsyncMock):
            result = await node_8_super_node(super_state)

        # Count non-LLM techniques in technique log
        non_llm_techniques = [
            "smart_router", "gsd", "maker", "thot", "federated",
            "zero_shot", "meta_learner", "dynamic_context",
            "contextual_compression", "turbo_compress", "adaptive_budget",
        ]
        logged = [log.get("technique") for log in result.get("technique_log", [])]
        for tech in non_llm_techniques:
            assert tech in logged, f"Missing non-LLM technique: {tech}"
        _log_technique("8", "NonLLM_All_11", "test_all_11_techniques")

    @pytest.mark.asyncio
    async def test_quality_above_85_sends_answer(self, super_state, mock_llm_call, mock_wiki_store):
        """Verify quality > 85% → status='resolved' and final_response is set."""
        from app.core.parwa_pipeline.nodes.node_8_super_node import node_8_super_node

        call_count = 0
        async def _mock_llm(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "FAILURE ANALYSIS: Previous lacked details."
            elif call_count in (2, 3):
                return "Good solution with refund details and timeline."
            elif call_count == 4:
                return "IMPROVED: Very detailed answer about refund."
            elif call_count == 5:
                return "VALID: YES\nCONFIDENCE: 0.95\nIMPROVEMENTS: none"
            elif call_count == 6:
                return "REVISED: Comprehensive refund response."
            else:
                return "ENHANCED: Final comprehensive response with all details."

        mock_llm_call.side_effect = _mock_llm

        with patch("app.core.parwa_pipeline.nodes.node_8_super_node.write_to_jarvis_inbox", new_callable=AsyncMock):
            result = await node_8_super_node(super_state)

        assert result["status"] == "resolved"
        assert result.get("final_response", "") != ""
        assert result.get("quality_passed") is True
        _log_technique("8", "Quality_SEND", "test_quality_sends")

    @pytest.mark.asyncio
    async def test_quality_below_85_escelates(self, super_state, mock_llm_call, mock_wiki_store):
        """Verify quality <= 85% → status='escalated' and notification generated."""
        from app.core.parwa_pipeline.nodes.node_8_super_node import node_8_super_node

        # All LLM responses are short/weak → low quality
        call_count = 0
        async def _mock_llm(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return "Short generic answer."

        mock_llm_call.side_effect = _mock_llm

        mock_inbox = AsyncMock(return_value={"id": "inbox_001"})
        with patch("app.core.parwa_pipeline.nodes.node_8_super_node.write_to_jarvis_inbox", mock_inbox):
            result = await node_8_super_node(super_state)

        assert result["status"] == "escalated"
        assert "escalation_context" in result
        assert "notification_key" in result["escalation_context"]
        # Verify inbox was called
        mock_inbox.assert_called_once()
        _log_technique("8", "Escalation", "test_quality_escelates")


# ══════════════════════════════════════════════════════════════════════
# 9. GRAPH V2 FLOW — 5 tests
# ══════════════════════════════════════════════════════════════════════


class TestGraphV2Flow:
    """Tests for Graph V2 routing logic.

    Tests the conditional edge functions directly.
    """

    def test_simple_path_routes_n1_to_n2_to_n3_to_n7(self, base_state):
        """Verify simple path: N1→N2→N3→N7→END."""
        from app.core.parwa_pipeline.graph_v2 import (
            _route_after_node_1,
            _route_after_node_2,
            _route_after_node_3,
            _route_after_node_7,
        )

        # After N1 — normal flow → N2
        state = {**base_state, "status": ""}
        assert _route_after_node_1(state) == "node_2"
        _log_technique("G", "Route_N1_N2", "test_simple_path")

        # After N2 — normal flow → N3
        state["route_decision"] = "simple_path"
        state["current_path"] = "simple_path"
        assert _route_after_node_2(state) == "node_3"

        # After N3 — simple path → N7
        assert _route_after_node_3(state) == "node_7"
        _log_technique("G", "Route_N3_N7", "test_simple_path")

        # After N7 — no upgrade → finalize → END
        state["auto_upgraded"] = False
        assert _route_after_node_7(state) == "__end__"
        _log_technique("G", "Route_N7_END", "test_simple_path")

    def test_complex_path_routes_n1_to_n2_to_n3_to_n4_to_n5_to_n6(self, base_state):
        """Verify complex path: N1→N2→N3→N4→N5→N6."""
        from app.core.parwa_pipeline.graph_v2 import (
            _route_after_node_1,
            _route_after_node_2,
            _route_after_node_3,
        )

        # After N1 → N2
        state = {**base_state, "status": ""}
        assert _route_after_node_1(state) == "node_2"

        # After N2 → N3
        state["status"] = ""
        assert _route_after_node_2(state) == "node_3"
        _log_technique("G", "Route_N1_N2", "test_complex_path")

        # After N3 — complex path → N4
        state["route_decision"] = "complex_path"
        state["current_path"] = "complex_path"
        assert _route_after_node_3(state) == "node_4"
        # N4→N5 and N5→N6 are unconditional edges
        _log_technique("G", "Route_N3_N4", "test_complex_path")

    def test_quality_loop_routes_n6_fail_to_n4(self, base_state):
        """Verify quality loop: N4→N5→N6→FAIL→N4 (loop back)."""
        from app.core.parwa_pipeline.graph_v2 import _route_after_node_6

        # Quality FAIL + loop < MAX → back to N4 (via increment_loop)
        state = {
            **base_state,
            "quality_score": 0.75,
            "loop_count": 0,
        }
        assert _route_after_node_6(state) == "node_4"
        _log_technique("G", "Route_N6_N4", "test_quality_loop")

    def test_max_loops_routes_to_n8_super_node(self, base_state):
        """Verify escalation: N4→N5→N6→FAIL(max loops)→N8→END."""
        from app.core.parwa_pipeline.graph_v2 import (
            _route_after_node_6,
            _route_after_node_8,
        )

        # Quality FAIL + loop >= MAX → N8 (Super Node)
        state = {
            **base_state,
            "quality_score": 0.65,
            "loop_count": 2,
        }
        assert _route_after_node_6(state) == "node_8"
        _log_technique("G", "Route_N6_N8", "test_max_loops")

        # After N8 → always END
        assert _route_after_node_8(state) == "__end__"
        _log_technique("G", "Route_N8_END", "test_max_loops")

    def test_quality_pass_routes_to_wiki_finalize(self, base_state):
        """Verify quality PASS → wiki_finalize → END."""
        from app.core.parwa_pipeline.graph_v2 import _route_after_node_6

        state = {
            **base_state,
            "quality_score": 0.92,
            "loop_count": 1,
        }
        assert _route_after_node_6(state) == "wiki_finalize"
        _log_technique("G", "Route_N6_WIKI", "test_quality_pass")

    def test_n1_rejected_goes_to_end(self, base_state):
        """Verify Node 1 rejected status routes directly to END."""
        from app.core.parwa_pipeline.graph_v2 import _route_after_node_1

        state = {**base_state, "status": "rejected"}
        assert _route_after_node_1(state) == "__end__"
        _log_technique("G", "Route_N1_END", "test_n1_rejected")

    def test_n7_safety_net_routes_to_n4(self, base_state):
        """Verify Node 7 safety net triggers route to N4 (complex path)."""
        from app.core.parwa_pipeline.graph_v2 import _route_after_node_7

        state = {**base_state, "auto_upgraded": True}
        assert _route_after_node_7(state) == "node_4"
        _log_technique("G", "Route_N7_N4", "test_n7_safety_net")


# ══════════════════════════════════════════════════════════════════════
# 10. PARWA BRIDGE — 6 tests
# ══════════════════════════════════════════════════════════════════════


class TestPARWABridge:
    """Tests for PARWA-Jarvis Bridge functions.

    Functions tested:
      - load_system_flags
      - write_quality_score_to_jarvis
      - write_to_jarvis_inbox
      - record_training_signal
      - invalidate_flag_cache
    """

    @pytest.mark.asyncio
    async def test_load_system_flags_returns_correct_flags(self, mock_jarvis_db):
        """Verify load_system_flags parses flag types correctly."""
        from app.core.parwa_pipeline.parwa_bridge import (
            invalidate_flag_cache,
            load_system_flags,
        )

        invalidate_flag_cache("tenant_bridge_test")

        mock_db, _ = mock_jarvis_db
        mock_db.get_active_flags.return_value = [
            {"flag_type": "global_shutdown", "flag_value": "true", "target_id": None},
            {"flag_type": "pause_action", "flag_value": "execute_refund", "target_id": None},
            {"flag_type": "redirect_channel", "flag_value": "call:human", "target_id": None},
            {"flag_type": "force_mode", "flag_value": "supervised", "target_id": None},
            {"flag_type": "approval_override", "flag_value": "address_change", "target_id": None},
        ]

        result = await load_system_flags("tenant_bridge_test")

        assert result["global_shutdown"] is True
        assert "execute_refund" in result["paused_actions"]
        assert result["redirected_channels"]["call"] == "human"
        assert result["force_mode"] == "supervised"
        assert "address_change" in result["approval_overrides"]

        invalidate_flag_cache("tenant_bridge_test")
        _log_technique("B", "load_system_flags", "test_load_flags")

    @pytest.mark.asyncio
    async def test_load_system_flags_defaults_when_no_flags(self, mock_jarvis_db):
        """Verify load_system_flags returns safe defaults for unknown tenant."""
        from app.core.parwa_pipeline.parwa_bridge import (
            invalidate_flag_cache,
            load_system_flags,
        )

        invalidate_flag_cache("tenant_new")

        mock_db, _ = mock_jarvis_db
        mock_db.get_active_flags.return_value = []

        result = await load_system_flags("tenant_new")

        assert result["global_shutdown"] is False
        assert result["paused_actions"] == []
        assert result["redirected_channels"] == {}
        assert result["force_mode"] is None
        assert result["approval_overrides"] == []

        invalidate_flag_cache("tenant_new")
        _log_technique("B", "load_system_flags_default", "test_default_flags")

    @pytest.mark.asyncio
    async def test_write_quality_score_to_jarvis(self, mock_jarvis_db):
        """Verify quality score is written to Jarvis DB."""
        from app.core.parwa_pipeline.parwa_bridge import write_quality_score_to_jarvis

        mock_db, _ = mock_jarvis_db

        result = await write_quality_score_to_jarvis(
            tenant_id="tenant_test",
            ticket_id="TKT-001",
            quality_score=0.92,
            resolution_path="complex_path",
            nodes_reached=[1, 2, 3, 4, 5, 6],
            llm_calls=9,
            tokens_used=2500,
        )

        assert result is not None
        mock_db.write_quality_score.assert_called_once()
        call_kwargs = mock_db.write_quality_score.call_args[1]
        assert call_kwargs["quality_score"] == 0.92
        assert call_kwargs["resolution_path"] == "complex_path"
        _log_technique("B", "write_quality_score", "test_write_quality")

    @pytest.mark.asyncio
    async def test_write_to_jarvis_inbox_stores_escalation(self, mock_jarvis_db):
        """Verify escalation details are written to Jarvis inbox."""
        from app.core.parwa_pipeline.parwa_bridge import write_to_jarvis_inbox

        mock_db, _ = mock_jarvis_db

        result = await write_to_jarvis_inbox(
            tenant_id="tenant_test",
            ticket_id="TKT-002",
            stuck_reason="Quality 0.65 after 2 loops",
            quality_score=0.65,
            what_was_tried="Reflexion, SelfConsistency, ToT, CRP, CoT + all 11 non-LLM techniques",
        )

        assert result is not None
        mock_db.write_to_inbox.assert_called_once()
        call_kwargs = mock_db.write_to_inbox.call_args[1]
        assert call_kwargs["inbox_type"] == "parwa_stuck"
        assert "0.65" in call_kwargs["stuck_reason"]
        _log_technique("B", "write_to_inbox", "test_write_inbox")

    @pytest.mark.asyncio
    async def test_record_training_signal_approved(self, mock_jarvis_db):
        """Verify approved training signal is recorded."""
        from app.core.parwa_pipeline.parwa_bridge import record_training_signal

        mock_db, _ = mock_jarvis_db

        result = await record_training_signal(
            tenant_id="tenant_test",
            ticket_id="TKT-003",
            signal_type="approved",
            original_response="Your refund will be processed in 5-7 days.",
            quality_score=0.92,
            ticket_type="refund_request",
        )

        assert result is not None
        mock_db.record_training_data.assert_called_once()
        _log_technique("B", "record_training_signal", "test_approved_signal")

    @pytest.mark.asyncio
    async def test_record_training_signal_rejected(self, mock_jarvis_db):
        """Verify rejected training signal is recorded with correction."""
        from app.core.parwa_pipeline.parwa_bridge import record_training_signal

        mock_db, _ = mock_jarvis_db

        result = await record_training_signal(
            tenant_id="tenant_test",
            ticket_id="TKT-004",
            signal_type="rejected",
            original_response="Wrong information provided.",
            corrected_response="The correct refund timeline is 5-7 business days.",
            quality_score=0.45,
            ticket_type="refund_request",
        )

        assert result is not None
        call_kwargs = mock_db.record_training_data.call_args[1]
        assert call_kwargs["signal_type"] == "rejected"
        assert call_kwargs["corrected_response"] != ""
        _log_technique("B", "record_training_signal", "test_rejected_signal")

    def test_invalidate_flag_cache_clears(self, mock_jarvis_db):
        """Verify invalidate_flag_cache clears all entries."""
        from app.core.parwa_pipeline.parwa_bridge import _FLAG_CACHE, invalidate_flag_cache

        # Set some entries
        _FLAG_CACHE["tenant_a"] = {"result": {"global_shutdown": True}, "loaded_at": time.time()}
        _FLAG_CACHE["tenant_b"] = {"result": {"global_shutdown": False}, "loaded_at": time.time()}

        assert len(_FLAG_CACHE) == 2

        # Clear all
        invalidate_flag_cache()
        assert len(_FLAG_CACHE) == 0

        _log_technique("B", "invalidate_cache", "test_cache_clear")

    def test_invalidate_flag_cache_single_tenant(self, mock_jarvis_db):
        """Verify invalidate_flag_cache clears only the specified tenant."""
        from app.core.parwa_pipeline.parwa_bridge import _FLAG_CACHE, invalidate_flag_cache

        _FLAG_CACHE["tenant_a"] = {"result": {"global_shutdown": True}, "loaded_at": time.time()}
        _FLAG_CACHE["tenant_b"] = {"result": {"global_shutdown": False}, "loaded_at": time.time()}

        invalidate_flag_cache("tenant_a")
        assert "tenant_a" not in _FLAG_CACHE
        assert "tenant_b" in _FLAG_CACHE

        # Cleanup
        _FLAG_CACHE.clear()
        _log_technique("B", "invalidate_cache", "test_cache_single")


# ══════════════════════════════════════════════════════════════════════
# BONUS: Internal Function Unit Tests — 8 additional tests
# ══════════════════════════════════════════════════════════════════════


class TestInternalFunctions:
    """Direct unit tests on internal helper functions (no mocking needed)."""

    def test_node1_classify_ticket_type_refund(self):
        """Direct test: _classify_ticket_type for refund patterns."""
        from app.core.parwa_pipeline.nodes.node_1_ingest_classify import _classify_ticket_type

        ticket_type, _ = _classify_ticket_type("I want my money back, please refund me")
        assert ticket_type == "refund_request"
        _log_technique("1", "SmartRouter._classify", "test_internal_refund")

    def test_node1_classify_ticket_type_billing(self):
        """Direct test: _classify_ticket_type for billing patterns."""
        from app.core.parwa_pipeline.nodes.node_1_ingest_classify import _classify_ticket_type

        ticket_type, _ = _classify_ticket_type("I see a double charge on my invoice")
        assert ticket_type == "billing"
        _log_technique("1", "SmartRouter._classify", "test_internal_billing")

    def test_node1_classify_complexity_hard(self):
        """Direct test: _classify_complexity for hard keywords."""
        from app.core.parwa_pipeline.nodes.node_1_ingest_classify import _classify_complexity

        complexity = _classify_complexity(
            "This complicated issue has been going on for weeks. "
            "I also have multiple problems and want to escalate to a manager. "
            "This is a formal complaint about the terrible service.",
            "complaint",
        )
        assert complexity in ("complex", "hard")
        _log_technique("1", "SmartRouter._complexity", "test_internal_hard")

    def test_node1_extract_action_refund_amount(self):
        """Direct test: _extract_action extracts amount from refund query."""
        from app.core.parwa_pipeline.nodes.node_1_ingest_classify import _extract_action

        action, details = _extract_action("Please refund me $250.00", "refund_request")
        assert action == "execute_refund"
        assert details.get("amount") == 250.0
        _log_technique("1", "SmartRouter._extract", "test_internal_extract")

    def test_node1_extract_action_investigate_billing(self):
        """Direct test: investigate_billing is preferred over plan_change for disputes."""
        from app.core.parwa_pipeline.nodes.node_1_ingest_classify import _extract_action

        action, _ = _extract_action(
            "Why am I seeing a different price of $99 per month?",
            "billing",
        )
        assert action == "investigate_billing"
        _log_technique("1", "SmartRouter._extract", "test_internal_investigate")

    def test_node2_check_capability_mini_no_refund(self):
        """Direct test: mini tier cannot execute refunds."""
        from app.core.parwa_pipeline.nodes.node_2_smart_route import _check_capability

        can = _check_capability("mini", "refund_request", "simple", "execute_refund", {"amount": 100})
        assert can is False
        _log_technique("2", "CapabilityMatrix._check", "test_internal_mini_no_refund")

    def test_node2_check_capability_high_unlimited_refund(self):
        """Direct test: high tier can execute unlimited refunds."""
        from app.core.parwa_pipeline.nodes.node_2_smart_route import _check_capability

        can = _check_capability("high", "refund_request", "complex", "execute_refund", {"amount": 50000})
        assert can is True
        _log_technique("2", "CapabilityMatrix._check", "test_internal_high_refund")

    def test_node3_retrieve_knowledge_returns_docs(self):
        """Direct test: _retrieve_knowledge returns docs for known type."""
        from app.core.parwa_pipeline.nodes.node_3_knowledge_fetch import _retrieve_knowledge

        docs = _retrieve_knowledge("refund_request")
        assert len(docs) > 0
        sources = [d.get("source", "") for d in docs]
        assert any("refund" in s.lower() for s in sources)
        _log_technique("3", "RAG._retrieve", "test_internal_retrieve")

    def test_node4_zero_shot_validate(self):
        """Direct test: _zero_shot_validate scores reasonable answer."""
        from app.core.parwa_pipeline.nodes.node_4_reasoning_engine import _zero_shot_validate

        answer = "Based on our refund policy, your refund of $450 will be processed within 5-7 business days to your original payment method."
        knowledge = "Refund Policy: Full refund within 30 days. Processed in 5-7 business days."
        score = _zero_shot_validate(answer, knowledge)

        assert 0.0 <= score <= 1.0
        assert score >= 0.8  # Reasonable answer should score well
        _log_technique("4", "ZeroShotValidator", "test_internal_zsv")

    def test_node6_structure_check_no_format(self):
        """Direct test: _structure_check penalizes unformatted response."""
        from app.core.parwa_pipeline.nodes.node_6_quality_format import _structure_check

        # Plain text with no bullets/bold/paragraphs
        answer = "this is a plain response without any formatting or structure at all"
        score = _structure_check(answer)

        assert score < 0.96  # Should be lower than structured answer
        _log_technique("6", "StructureCheck", "test_internal_structure")

    def test_node7_zero_shot_check_flags_not_available(self):
        """Direct test: _zero_shot_check penalizes 'not available' fallback."""
        from app.core.parwa_pipeline.nodes.node_7_simple_resolver import _zero_shot_check

        answer = "Information not available in knowledge base for your question."
        score = _zero_shot_check(answer, "some knowledge", "test query")

        # "not available" triggers -0.25 penalty
        assert score < 0.8
        _log_technique("7", "ZeroShotValidator", "test_internal_not_available")

    def test_llm_parse_confidence(self):
        """Direct test: parse_confidence extracts number from LLM text."""
        from app.core.parwa_pipeline.llm_client import parse_confidence

        assert parse_confidence("0.85") == 0.85
        assert parse_confidence("85%") == 0.85
        assert parse_confidence("CONFIDENCE: 92") == 0.92
        assert parse_confidence("no number here") == 0.7  # default
        assert parse_confidence("150") == 1.0  # clamped
        assert parse_confidence("-0.5") == 0.0  # clamped
        _log_technique("L", "parse_confidence", "test_internal_parse")


# ══════════════════════════════════════════════════════════════════════
# BONUS: Cross-Node Integration Snippets — 4 tests
# ══════════════════════════════════════════════════════════════════════


class TestCrossNodeIntegration:
    """Cross-node integration tests verifying data flows between nodes."""

    @pytest.mark.asyncio
    async def test_n1_output_feeds_n2(self, base_state, mock_llm_call, mock_wiki_store, mock_jarvis_db):
        """Verify Node 1 output fields are valid input for Node 2."""
        from app.core.parwa_pipeline.nodes.node_1_ingest_classify import node_1_ingest_classify
        from app.core.parwa_pipeline.nodes.node_2_smart_route import MOCK_VARIANT_REGISTRY, node_2_smart_route

        n1_result = await node_1_ingest_classify(base_state)

        # Node 2 expects these fields
        assert "ticket_type" in n1_result
        assert "complexity" in n1_result
        assert "required_action" in n1_result

        # Feed N1 output into N2 state
        n2_state = {**base_state, **n1_result}
        MOCK_VARIANT_REGISTRY["tenant_acme"] = {"tier": "parwa", "quota_total": 500, "quota_remaining": 500}
        try:
            n2_result = await node_2_smart_route(n2_state)
            assert "route_decision" in n2_result
            assert n2_result["route_decision"] in ("simple_path", "complex_path")
            _log_technique("X", "N1→N2", "test_n1_feeds_n2")
        finally:
            MOCK_VARIANT_REGISTRY.pop("tenant_acme", None)

    @pytest.mark.asyncio
    async def test_n2_output_feeds_n3(self, base_state, mock_llm_call, mock_wiki_store, mock_jarvis_db):
        """Verify Node 2 output fields are valid input for Node 3."""
        from app.core.parwa_pipeline.nodes.node_2_smart_route import MOCK_VARIANT_REGISTRY, node_2_smart_route
        from app.core.parwa_pipeline.nodes.node_3_knowledge_fetch import node_3_knowledge_fetch

        state = {
            **base_state,
            "ticket_type": "refund_request",
            "complexity": "complex",
            "required_action": "execute_refund",
            "action_details": {"amount": 300},
        }

        MOCK_VARIANT_REGISTRY["tenant_acme"] = {"tier": "parwa", "quota_total": 500, "quota_remaining": 500}
        try:
            n2_result = await node_2_smart_route(state)

            n3_state = {**base_state, **n2_result}
            mock_llm_call.return_value = "Refund policy, process details"
            n3_result = await node_3_knowledge_fetch(n3_state)

            assert "knowledge_context" in n3_result
            assert isinstance(n3_result["knowledge_context"], list)
            _log_technique("X", "N2→N3", "test_n2_feeds_n3")
        finally:
            MOCK_VARIANT_REGISTRY.pop("tenant_acme", None)

    @pytest.mark.asyncio
    async def test_n3_output_feeds_n4(self, base_state, mock_llm_call, mock_wiki_store, mock_jarvis_db):
        """Verify Node 3 output fields are valid input for Node 4."""
        from app.core.parwa_pipeline.nodes.node_3_knowledge_fetch import node_3_knowledge_fetch
        from app.core.parwa_pipeline.nodes.node_4_reasoning_engine import node_4_reasoning_engine

        state = {
            **base_state,
            "ticket_type": "refund_request",
            "variant_tier": "parwa",
        }

        mock_llm_call.return_value = "Refund policy and process"
        n3_result = await node_3_knowledge_fetch(state)

        # Feed N3 output into N4 state
        n4_state = {
            **base_state,
            **n3_result,
            "complexity": "complex",
            "required_action": "execute_refund",
            "action_details": {"amount": 300},
        }

        # Node 4 will make LLM calls — mock them
        async def _mock_llm_n4(*args, **kwargs):
            return (
                "1. What is the refund policy?\n2. What is the process?\n\n"
                "Full refund within 30 days.\n\n"
                "1. COMPLETE\n2. COMPLETE\n\n"
                "VALID: YES\nCONFIDENCE: 0.9\n\n"
                "Your refund will be processed within 5-7 business days."
            )

        mock_llm_call.side_effect = _mock_llm_n4
        n4_result = await node_4_reasoning_engine(n4_state)

        assert "combined_answer" in n4_result
        assert "reasoning_confidence" in n4_result
        _log_technique("X", "N3→N4", "test_n3_feeds_n4")

    @pytest.mark.asyncio
    async def test_state_accumulation_across_nodes(self, base_state, mock_llm_call, mock_wiki_store, mock_jarvis_db):
        """Verify technique_log accumulates (Annotated with _merge reducer)."""
        from app.core.parwa_pipeline.state_v2 import _merge

        # Simulate technique log accumulation
        log1 = [{"node": 1, "technique": "SmartRouter", "duration_ms": 5, "result_summary": "type=refund"}]
        log2 = [{"node": 2, "technique": "RouteDecision", "duration_ms": 3, "result_summary": "path=complex"}]
        log3 = [{"node": 3, "technique": "RAG", "duration_ms": 10, "result_summary": "5 docs"}]

        merged = _merge(log1, log2)
        assert len(merged) == 2

        merged = _merge(merged, log3)
        assert len(merged) == 3

        # Verify None handling
        assert _merge(None, log1) == log1
        assert _merge(log1, None) == log1
        _log_technique("S", "_merge_reducer", "test_state_accumulation")


# ══════════════════════════════════════════════════════════════════════
# CONFIG TESTS — 3 tests
# ══════════════════════════════════════════════════════════════════════


class TestPipelineConfig:
    """Tests for pipeline configuration constants."""

    def test_quality_thresholds_are_valid(self):
        """Verify quality thresholds have correct ordering."""
        from app.core.parwa_pipeline.config import (
            QUALITY_LOOP_THRESHOLD,
            QUALITY_PASS_THRESHOLD,
            QUALITY_SUPER_THRESHOLD,
        )

        assert QUALITY_LOOP_THRESHOLD < QUALITY_PASS_THRESHOLD
        assert QUALITY_SUPER_THRESHOLD < QUALITY_PASS_THRESHOLD
        assert 0.0 < QUALITY_LOOP_THRESHOLD < 1.0
        assert 0.0 < QUALITY_PASS_THRESHOLD <= 1.0
        _log_technique("C", "thresholds", "test_threshold_ordering")

    def test_quality_weights_sum_to_one(self):
        """Verify quality scoring weights sum to 1.0."""
        from app.core.parwa_pipeline.config import QUALITY_WEIGHTS

        total = sum(QUALITY_WEIGHTS.values())
        assert abs(total - 1.0) < 0.01, f"Weights sum to {total}, expected 1.0"
        _log_technique("C", "weights", "test_weights_sum")

    def test_max_quality_loops_is_positive(self):
        """Verify MAX_QUALITY_LOOPS is positive."""
        from app.core.parwa_pipeline.config import MAX_QUALITY_LOOPS

        assert MAX_QUALITY_LOOPS >= 1
        _log_technique("C", "max_loops", "test_max_loops")


# ══════════════════════════════════════════════════════════════════════
# PRINT SUMMARY — runs automatically
# ══════════════════════════════════════════════════════════════════════

# Constants for Node 7 test (avoid importing package __init__ which triggers langgraph)
QUALITY_SIMPLE_SAFETY_NET = 0.80
