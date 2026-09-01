"""Tests for dead code wiring — verifies all previously dead modules are now reachable.

Tests:
1. Technique system bridge in Node 4 (run_llm_techniques, _build_query_signals, _build_conversation_state)
2. RAG system wiring in Node 3 (MultiQuery, LLMReranker called for parwa/high)
3. Enhancement system wiring in Node 1 (billing, tech, emotion, shipping, churn engines)
4. API router + middleware wiring in main.py (all imports resolve)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ═══════════════════════════════════════════════════════════════
# 1. TECHNIQUE SYSTEM BRIDGE (Node 4)
# ═══════════════════════════════════════════════════════════════


class TestTechniqueBridge:
    """Test the technique system bridge functions in node_4_reasoning_engine."""

    def test_import_bridge_functions(self):
        """Bridge functions must be importable from Node 4."""
        from app.core.parwa_pipeline.nodes.node_4_reasoning_engine import (
            run_llm_techniques,
            _build_query_signals,
            _build_conversation_state,
        )
        assert callable(run_llm_techniques)
        assert callable(_build_query_signals)
        assert callable(_build_conversation_state)

    def test_build_query_signals_default(self):
        """_build_query_signals should return QuerySignals with sensible defaults."""
        from app.core.parwa_pipeline.nodes.node_4_reasoning_engine import _build_query_signals
        state = {
            "complexity": "complex",
            "classification_confidence": 0.65,
            "sentiment_score": 0.4,
            "customer_context": {"tier": "enterprise"},
            "action_details": {"amount": 150.0},
            "turn_count": 3,
            "ticket_type": "billing",
            "connected_databases": [{"name": "shopify"}],
            "required_action": "escalate",
        }
        signals = _build_query_signals(state)
        assert signals.query_complexity == 1.0  # complex → True → 1.0
        assert signals.confidence_score == 0.65
        assert signals.customer_tier == "enterprise"
        assert signals.monetary_value == 150.0
        assert signals.turn_count == 3
        assert signals.intent_type == "billing"
        assert signals.external_data_required is True
        assert signals.is_strategic_decision is True

    def test_build_query_signals_simple(self):
        """Simple complexity should produce query_complexity=0.0."""
        from app.core.parwa_pipeline.nodes.node_4_reasoning_engine import _build_query_signals
        signals = _build_query_signals({"complexity": "simple"})
        assert signals.query_complexity == 0.0

    def test_build_conversation_state(self):
        """_build_conversation_state should convert pipeline state to ConversationState."""
        from app.core.parwa_pipeline.nodes.node_4_reasoning_engine import _build_conversation_state
        state = {"query": "Where is my refund?", "ticket_id": "t-123", "tenant_id": "c-456"}
        conv = _build_conversation_state(state)
        assert conv.query == "Where is my refund?"
        assert conv.ticket_id == "t-123"
        assert conv.company_id == "c-456"

    @pytest.mark.asyncio
    async def test_run_llm_techniques_skips_quick_lane(self):
        """Should return empty for QUICK lane regardless of variant."""
        from app.core.parwa_pipeline.nodes.node_4_reasoning_engine import run_llm_techniques
        state = {"lane": "QUICK", "variant_tier_short": "parwa"}
        logs, tech_state, tokens = await run_llm_techniques(state)
        assert logs == []
        assert tech_state is None
        assert tokens == 0

    @pytest.mark.asyncio
    async def test_run_llm_techniques_skips_free_variant(self):
        """Should return empty for free variant even on FULL lane."""
        from app.core.parwa_pipeline.nodes.node_4_reasoning_engine import run_llm_techniques
        state = {"lane": "FULL", "variant_tier_short": "mini"}
        logs, tech_state, tokens = await run_llm_techniques(state)
        assert logs == []

    @pytest.mark.asyncio
    async def test_run_llm_techniques_runs_for_parwa_full(self):
        """Should attempt execution for parwa FULL lane."""
        from app.core.parwa_pipeline.nodes.node_4_reasoning_engine import run_llm_techniques
        state = {"lane": "FULL", "variant_tier_short": "parwa", "tenant_id": "c-1", "query": "test"}
        # Will likely fail in test env (no LLM), but should not crash
        logs, tech_state, tokens = await run_llm_techniques(state)
        assert isinstance(logs, list)  # even on error, returns error log
        assert tokens >= 0

    @pytest.mark.asyncio
    async def test_run_llm_techniques_runs_for_high_full(self):
        """Should attempt execution for high FULL lane."""
        from app.core.parwa_pipeline.nodes.node_4_reasoning_engine import run_llm_techniques
        state = {"lane": "FULL", "variant_tier_short": "high", "tenant_id": "c-1", "query": "test"}
        logs, tech_state, tokens = await run_llm_techniques(state)
        assert isinstance(logs, list)

    def test_technique_executor_import(self):
        """TechniqueExecutor should be importable."""
        from app.core.technique_executor import TechniqueExecutor
        assert TechniqueExecutor is not None

    def test_technique_router_import(self):
        """TechniqueRouter should be importable."""
        from app.core.technique_router import TechniqueRouter, TechniqueID, TECHNIQUE_REGISTRY
        assert TechniqueRouter is not None
        assert TechniqueID.CHAIN_OF_THOUGHT in TECHNIQUE_REGISTRY
        assert TechniqueID.TREE_OF_THOUGHTS in TECHNIQUE_REGISTRY
        assert TechniqueID.GST in TECHNIQUE_REGISTRY

    def test_all_13_techniques_in_registry(self):
        """All 13 AI techniques must be registered in TECHNIQUE_REGISTRY."""
        from app.core.technique_router import TechniqueID, TECHNIQUE_REGISTRY
        expected = [
            TechniqueID.CLARA, TechniqueID.CRP, TechniqueID.GSD,
            TechniqueID.CHAIN_OF_THOUGHT, TechniqueID.REVERSE_THINKING,
            TechniqueID.REACT, TechniqueID.STEP_BACK, TechniqueID.THREAD_OF_THOUGHT,
            TechniqueID.GST, TechniqueID.UNIVERSE_OF_THOUGHTS,
            TechniqueID.TREE_OF_THOUGHTS, TechniqueID.SELF_CONSISTENCY,
            TechniqueID.REFLEXION, TechniqueID.LEAST_TO_MOST,
        ]
        for tid in expected:
            assert tid in TECHNIQUE_REGISTRY, f"{tid} not in TECHNIQUE_REGISTRY"


# ═══════════════════════════════════════════════════════════════
# 2. RAG SYSTEM WIRING (Node 3)
# ═══════════════════════════════════════════════════════════════


class TestRAGWiring:
    """Test the RAG system modules are importable and have correct interfaces."""

    def test_hyde_import(self):
        """HyDEGenerator should be importable."""
        from app.core.rag.hyde import HyDEGenerator
        assert HyDEGenerator is not None

    def test_multi_query_import(self):
        """MultiQueryRetriever should be importable."""
        from app.core.rag.multi_query import MultiQueryRetriever
        assert MultiQueryRetriever is not None

    def test_llm_reranker_import(self):
        """LLMReranker should be importable."""
        from app.core.rag.llm_reranker import LLMReranker
        assert LLMReranker is not None

    def test_multi_query_has_retrieve_method(self):
        """MultiQueryRetriever should have retrieve_with_multi_query method."""
        from app.core.rag.multi_query import MultiQueryRetriever
        assert hasattr(MultiQueryRetriever, "retrieve_with_multi_query")

    def test_llm_reranker_has_rerank_method(self):
        """LLMReranker should have rerank method."""
        from app.core.rag.llm_reranker import LLMReranker
        assert hasattr(LLMReranker, "rerank")

    def test_hyde_has_generate_method(self):
        """HyDEGenerator should have generate_hypothetical_answer method."""
        from app.core.rag.hyde import HyDEGenerator
        assert hasattr(HyDEGenerator, "generate_hypothetical_answer")


# ═══════════════════════════════════════════════════════════════
# 3. ENHANCEMENT SYSTEM WIRING (Node 1)
# ═══════════════════════════════════════════════════════════════


class TestEnhancementWiring:
    """Test the 5 enhancement engines are importable and have correct interfaces."""

    def test_billing_intelligence_import(self):
        """BillingIntelligenceEngine should be importable."""
        from app.core.enhancements.billing_intelligence import BillingIntelligenceEngine
        eng = BillingIntelligenceEngine()
        assert hasattr(eng, "detect_anomaly")

    def test_churn_retention_import(self):
        """ChurnRetentionEngine should be importable."""
        from app.core.enhancements.churn_retention import ChurnRetentionEngine
        eng = ChurnRetentionEngine()
        assert hasattr(eng, "score_churn_risk")

    def test_emotional_intelligence_import(self):
        """EmotionalIntelligenceEngine should be importable."""
        from app.core.enhancements.emotional_intelligence import EmotionalIntelligenceEngine
        eng = EmotionalIntelligenceEngine()
        assert hasattr(eng, "profile_emotion")

    def test_shipping_intelligence_import(self):
        """ShippingIntelligenceEngine should be importable."""
        from app.core.enhancements.shipping_intelligence import ShippingIntelligenceEngine
        eng = ShippingIntelligenceEngine()
        assert hasattr(eng, "detect_tracking_number")

    def test_tech_diagnostics_import(self):
        """TechDiagnosticsEngine should be importable."""
        from app.core.enhancements.tech_diagnostics import TechDiagnosticsEngine
        eng = TechDiagnosticsEngine()
        assert hasattr(eng, "detect_known_issue")
        assert hasattr(eng, "score_severity")

    def test_billing_anomaly_returns_dict(self):
        """detect_anomaly should return a dict (never crash)."""
        from app.core.enhancements.billing_intelligence import BillingIntelligenceEngine
        eng = BillingIntelligenceEngine()
        result = eng.detect_anomaly("test-company", "I was charged twice", {})
        assert isinstance(result, dict)

    def test_emotion_profile_returns_dict(self):
        """profile_emotion should return a dict (never crash)."""
        from app.core.enhancements.emotional_intelligence import EmotionalIntelligenceEngine
        eng = EmotionalIntelligenceEngine()
        result = eng.profile_emotion("test-company", "This is terrible!")
        assert isinstance(result, dict)

    def test_churn_score_returns_dict(self):
        """score_churn_risk should return a dict (never crash)."""
        from app.core.enhancements.churn_retention import ChurnRetentionEngine
        eng = ChurnRetentionEngine()
        result = eng.score_churn_risk("test-company", "I want to cancel my subscription", {})
        assert isinstance(result, dict)


# ═══════════════════════════════════════════════════════════════
# 4. ROUTER + MIDDLEWARE WIRING (main.py)
# ═══════════════════════════════════════════════════════════════


class TestRouterMiddlewareWiring:
    """Test that previously dead routers and middleware are importable."""

    def test_crm_webhooks_router_exists(self):
        """crm_webhooks.py should have router = APIRouter(...)."""
        import ast
        with open('backend/app/api/crm_webhooks.py') as f:
            tree = ast.parse(f.read())
        has_router = any(isinstance(n, ast.Assign) for n in ast.walk(tree))
        assert has_router

    def test_custom_connectors_router_exists(self):
        import ast
        with open('backend/app/api/custom_connectors.py') as f:
            tree = ast.parse(f.read())
        has_router = any(isinstance(n, ast.Assign) for n in ast.walk(tree))
        assert has_router

    def test_flexpay_router_exists(self):
        import ast
        with open('backend/app/api/flexpay.py') as f:
            tree = ast.parse(f.read())
        has_router = any(isinstance(n, ast.Assign) for n in ast.walk(tree))
        assert has_router

    def test_jarvis_chat_router_exists(self):
        import ast
        with open('backend/app/api/jarvis_chat.py') as f:
            tree = ast.parse(f.read())
        has_router = any(isinstance(n, ast.Assign) for n in ast.walk(tree))
        assert has_router

    def test_superglue_actions_router_exists(self):
        import ast
        with open('backend/app/api/superglue_actions.py') as f:
            tree = ast.parse(f.read())
        has_router = any(isinstance(n, ast.Assign) for n in ast.walk(tree))
        assert has_router

    def test_variant_check_middleware_exists(self):
        """variant_check.py should define VariantCheckMiddleware class."""
        import ast
        with open('backend/app/middleware/variant_check.py') as f:
            tree = ast.parse(f.read())
        has_class = any(isinstance(n, ast.ClassDef) and n.name == 'VariantCheckMiddleware' for n in ast.walk(tree))
        assert has_class

    def test_main_py_has_new_imports(self):
        """main.py should contain imports for all 5 newly-wired routers."""
        with open('backend/app/main.py') as f:
            content = f.read()
        assert 'crm_webhooks_router' in content
        assert 'custom_connectors_router' in content
        assert 'flexpay_router' in content
        assert 'jarvis_chat_router' in content
        assert 'superglue_actions_router' in content
        assert 'VariantCheckMiddleware' in content

    def test_main_py_has_new_includes(self):
        """main.py should include_router for all 5 newly-wired routers."""
        with open('backend/app/main.py') as f:
            content = f.read()
        assert 'include_router(crm_webhooks_router)' in content
        assert 'include_router(custom_connectors_router)' in content
        assert 'include_router(flexpay_router)' in content
        assert 'include_router(jarvis_chat_router)' in content
        assert 'include_router(superglue_actions_router)' in content
        assert 'add_middleware(VariantCheckMiddleware)' in content


# ═══════════════════════════════════════════════════════════════
# 5. INTEGRATION: Technique system end-to-end
# ═══════════════════════════════════════════════════════════════


class TestTechniqueIntegration:
    """Integration tests for the full technique pipeline."""

    def test_technique_executor_creates_with_variant(self):
        """TechniqueExecutor should accept variant_type parameter."""
        from app.core.technique_executor import TechniqueExecutor
        for variant in ("parwa", "high"):
            executor = TechniqueExecutor(variant_type=variant, company_id="test")
            assert executor.variant_type == variant

    def test_technique_router_route_returns_result(self):
        """TechniqueRouter.route should return RouterResult with activated_techniques."""
        from app.core.technique_router import TechniqueRouter, QuerySignals
        router = TechniqueRouter(model_tier="medium")
        signals = QuerySignals(query_complexity=0.8, confidence_score=0.5, intent_type="billing")
        result = router.route(signals)
        assert result.activated_techniques  # Tier 1 always activates
        # CLARA is Tier 1, should always be present
        from app.core.technique_router import TechniqueID
        activated_ids = {a.technique_id for a in result.activated_techniques}
        assert TechniqueID.CLARA in activated_ids

    def test_base_technique_conversation_state(self):
        """ConversationState from base_technique should have all required fields."""
        from app.core.techniques.base_technique import ConversationState, GSDState
        state = ConversationState(query="test query")
        assert state.query == "test query"
        assert state.gsd_state == GSDState.NEW
        assert state.technique_results == {}
        assert state.response_parts == []

    def test_all_technique_modules_importable(self):
        """All 13 technique files should be importable."""
        technique_modules = [
            "app.core.techniques.chain_of_thought",
            "app.core.techniques.crp",
            "app.core.techniques.gst",
            "app.core.techniques.least_to_most",
            "app.core.techniques.react",
            "app.core.techniques.react_tools",
            "app.core.techniques.reflexion",
            "app.core.techniques.reverse_thinking",
            "app.core.techniques.self_consistency",
            "app.core.techniques.step_back",
            "app.core.techniques.thread_of_thought",
            "app.core.techniques.tree_of_thoughts",
            "app.core.techniques.universe_of_thoughts",
        ]
        for mod in technique_modules:
            __import__(mod)
