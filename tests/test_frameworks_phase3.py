"""Unit tests for Phase 3 techniques: RAG (CLARA, HyDE, Multi-Query, Step-Back)
and Quality (Reflexion, Self-Consistency, CRP, Least-to-Most).

Tests cover:
  - Each technique's think() method in MOCK_MODE
  - TechniqueResult output validation
  - Complexity-based activation logic
  - Category and name verification
  - Edge cases: empty state, missing fields, bad types
  - FrameworkBrain integration with Phase 3 techniques
"""

import pytest

from parwa.frameworks.base import TechniqueCategory, TechniqueResult
from parwa.frameworks.registry import get_registry, reset_registry
from parwa.frameworks.brain import FrameworkBrain


# ─── CLARA Technique Tests ────────────────────────────────────────────────────

class TestClaraTechnique:

    def setup_method(self):
        reset_registry()

    @pytest.mark.asyncio
    async def test_clara_produces_result(self):
        from parwa.frameworks.rag.clara import ClaraTechnique
        technique = ClaraTechnique()
        result = await technique.think(
            "Find refund policy",
            {"intent": "refund_request", "kb_results": [], "faq_match": None},
        )
        assert isinstance(result, TechniqueResult)
        assert result.output != ""
        assert len(result.chain) > 0
        assert "clara" in result.frameworks_used
        assert result.confidence > 0

    @pytest.mark.asyncio
    async def test_clara_high_confidence_with_data(self):
        from parwa.frameworks.rag.clara import ClaraTechnique
        technique = ClaraTechnique()
        result = await technique.think(
            "Find refund policy",
            {
                "intent": "refund_request",
                "kb_results": [{"content": "Refund policy doc", "relevance_score": 0.9}],
                "faq_match": {"content": "Refund FAQ", "relevance_score": 0.8},
            },
        )
        assert result.confidence > 0.7
        assert result.metadata["clarification_needed"] is False

    @pytest.mark.asyncio
    async def test_clara_requests_clarification_without_data(self):
        from parwa.frameworks.rag.clara import ClaraTechnique
        technique = ClaraTechnique()
        result = await technique.think(
            "Unclear request",
            {"intent": "general_inquiry", "kb_results": [], "faq_match": None},
        )
        assert result.metadata["clarification_needed"] is True
        assert result.confidence < 0.7

    @pytest.mark.asyncio
    async def test_clara_name_and_category(self):
        from parwa.frameworks.rag.clara import ClaraTechnique
        technique = ClaraTechnique()
        assert technique.name == "clara"
        assert technique.category == TechniqueCategory.RAG

    @pytest.mark.asyncio
    async def test_clara_applicable_nodes(self):
        from parwa.frameworks.rag.clara import ClaraTechnique
        technique = ClaraTechnique()
        nodes = technique.applicable_nodes
        assert "KB_RETRIEVER" in nodes
        assert "FAQ_MATCHER" in nodes
        assert "CONTEXT_MANAGER" in nodes

    @pytest.mark.asyncio
    async def test_clara_requires_medium_complexity(self):
        from parwa.frameworks.rag.clara import ClaraTechnique
        technique = ClaraTechnique()
        assert technique.can_apply("KB_RETRIEVER", "simple") is False
        assert technique.can_apply("KB_RETRIEVER", "medium") is True
        assert technique.can_apply("KB_RETRIEVER", "complex") is True

    @pytest.mark.asyncio
    async def test_clara_token_cost(self):
        from parwa.frameworks.rag.clara import ClaraTechnique
        technique = ClaraTechnique()
        assert technique.token_cost_estimate > 0
        assert result.token_estimate == technique.token_cost_estimate if (result := await technique.think("test", {"intent": "test"})) else True


# ─── HyDE Technique Tests ─────────────────────────────────────────────────────

class TestHyDETechnique:

    def setup_method(self):
        reset_registry()

    @pytest.mark.asyncio
    async def test_hyde_produces_result(self):
        from parwa.frameworks.rag.hyde import HyDETechnique
        technique = HyDETechnique()
        result = await technique.think(
            "I was charged twice",
            {"intent": "refund_request", "raw_message": "I was charged twice"},
        )
        assert isinstance(result, TechniqueResult)
        assert result.output != ""
        assert "hyde" in result.frameworks_used
        assert result.metadata["hypothetical_document"] != ""

    @pytest.mark.asyncio
    async def test_hyde_generates_hypothetical_document(self):
        from parwa.frameworks.rag.hyde import HyDETechnique
        technique = HyDETechnique()
        result = await technique.think(
            "I was charged twice",
            {"intent": "refund_request", "raw_message": "I was charged twice"},
        )
        hypo_doc = result.metadata["hypothetical_document"]
        assert len(hypo_doc) > 20  # Should be a meaningful document

    @pytest.mark.asyncio
    async def test_hyde_name_and_category(self):
        from parwa.frameworks.rag.hyde import HyDETechnique
        technique = HyDETechnique()
        assert technique.name == "hyde"
        assert technique.category == TechniqueCategory.RAG

    @pytest.mark.asyncio
    async def test_hyde_applicable_nodes(self):
        from parwa.frameworks.rag.hyde import HyDETechnique
        technique = HyDETechnique()
        nodes = technique.applicable_nodes
        assert "KB_RETRIEVER" in nodes
        assert "FAQ_MATCHER" in nodes

    @pytest.mark.asyncio
    async def test_hyde_activates_on_simple(self):
        from parwa.frameworks.rag.hyde import HyDETechnique
        technique = HyDETechnique()
        assert technique.can_apply("KB_RETRIEVER", "simple") is True

    @pytest.mark.asyncio
    async def test_hyde_different_intents(self):
        from parwa.frameworks.rag.hyde import HyDETechnique
        technique = HyDETechnique()
        for intent in ["refund_request", "order_status", "cancellation", "billing_issue"]:
            result = await technique.think(
                f"Help with {intent}",
                {"intent": intent, "raw_message": f"Help with {intent}"},
            )
            assert result.output != ""
            assert result.confidence > 0


# ─── Multi-Query Technique Tests ──────────────────────────────────────────────

class TestMultiQueryTechnique:

    def setup_method(self):
        reset_registry()

    @pytest.mark.asyncio
    async def test_multi_query_produces_result(self):
        from parwa.frameworks.rag.multi_query import MultiQueryTechnique
        technique = MultiQueryTechnique()
        result = await technique.think(
            "I was charged twice",
            {"intent": "refund_request", "raw_message": "I was charged twice"},
        )
        assert isinstance(result, TechniqueResult)
        assert "multi_query" in result.frameworks_used
        assert result.metadata["query_count"] > 0

    @pytest.mark.asyncio
    async def test_multi_query_generates_multiple_queries(self):
        from parwa.frameworks.rag.multi_query import MultiQueryTechnique
        technique = MultiQueryTechnique()
        result = await technique.think(
            "I was charged twice",
            {"intent": "refund_request", "raw_message": "I was charged twice"},
        )
        queries = result.metadata["queries"]
        assert len(queries) >= 2

    @pytest.mark.asyncio
    async def test_multi_query_name_and_category(self):
        from parwa.frameworks.rag.multi_query import MultiQueryTechnique
        technique = MultiQueryTechnique()
        assert technique.name == "multi_query"
        assert technique.category == TechniqueCategory.RAG

    @pytest.mark.asyncio
    async def test_multi_query_requires_medium(self):
        from parwa.frameworks.rag.multi_query import MultiQueryTechnique
        technique = MultiQueryTechnique()
        assert technique.can_apply("KB_RETRIEVER", "simple") is False
        assert technique.can_apply("KB_RETRIEVER", "medium") is True

    @pytest.mark.asyncio
    async def test_multi_query_applicable_nodes(self):
        from parwa.frameworks.rag.multi_query import MultiQueryTechnique
        technique = MultiQueryTechnique()
        nodes = technique.applicable_nodes
        assert "KB_RETRIEVER" in nodes
        assert "FAQ_MATCHER" in nodes
        assert "CONTEXT_MANAGER" in nodes


# ─── Step-Back Technique Tests ────────────────────────────────────────────────

class TestStepBackTechnique:

    def setup_method(self):
        reset_registry()

    @pytest.mark.asyncio
    async def test_step_back_produces_result(self):
        from parwa.frameworks.rag.step_back import StepBackTechnique
        technique = StepBackTechnique()
        result = await technique.think(
            "I was charged twice",
            {"intent": "refund_request", "raw_message": "I was charged twice"},
        )
        assert isinstance(result, TechniqueResult)
        assert "step_back" in result.frameworks_used
        assert result.metadata["broader_concept"] != ""

    @pytest.mark.asyncio
    async def test_step_back_identifies_broader_concept(self):
        from parwa.frameworks.rag.step_back import StepBackTechnique
        technique = StepBackTechnique()
        result = await technique.think(
            "Duplicate charge",
            {"intent": "refund_request", "raw_message": "I was charged twice"},
        )
        concept = result.metadata["broader_concept"]
        assert len(concept) > 10  # Should be a meaningful concept

    @pytest.mark.asyncio
    async def test_step_back_name_and_category(self):
        from parwa.frameworks.rag.step_back import StepBackTechnique
        technique = StepBackTechnique()
        assert technique.name == "step_back"
        assert technique.category == TechniqueCategory.RAG

    @pytest.mark.asyncio
    async def test_step_back_requires_medium(self):
        from parwa.frameworks.rag.step_back import StepBackTechnique
        technique = StepBackTechnique()
        assert technique.can_apply("KB_RETRIEVER", "simple") is False
        assert technique.can_apply("KB_RETRIEVER", "medium") is True

    @pytest.mark.asyncio
    async def test_step_back_applicable_nodes(self):
        from parwa.frameworks.rag.step_back import StepBackTechnique
        technique = StepBackTechnique()
        nodes = technique.applicable_nodes
        assert "KB_RETRIEVER" in nodes
        assert "FAQ_MATCHER" in nodes
        assert "REASONING_ENGINE" in nodes


# ─── Reflexion Technique Tests ────────────────────────────────────────────────

class TestReflexionTechnique:

    def setup_method(self):
        reset_registry()

    @pytest.mark.asyncio
    async def test_reflexion_produces_result(self):
        from parwa.frameworks.quality.reflexion import ReflexionTechnique
        technique = ReflexionTechnique()
        result = await technique.think(
            "Review this conclusion",
            {
                "intent": "refund_request",
                "reasoning_conclusion": "Customer is eligible for refund",
                "verification_passed": True,
            },
        )
        assert isinstance(result, TechniqueResult)
        assert "reflexion" in result.frameworks_used
        assert result.confidence > 0

    @pytest.mark.asyncio
    async def test_reflexion_finds_issues_without_conclusion(self):
        from parwa.frameworks.quality.reflexion import ReflexionTechnique
        technique = ReflexionTechnique()
        result = await technique.think(
            "Review this",
            {
                "intent": "refund_request",
                "reasoning_conclusion": "",
                "verification_passed": False,
            },
        )
        assert result.metadata["issues_found"] > 0
        assert result.confidence < 0.8

    @pytest.mark.asyncio
    async def test_reflexion_passes_with_good_conclusion(self):
        from parwa.frameworks.quality.reflexion import ReflexionTechnique
        technique = ReflexionTechnique()
        result = await technique.think(
            "Review this",
            {
                "intent": "refund_request",
                "reasoning_conclusion": "Customer is eligible for a full refund",
                "verification_passed": True,
            },
        )
        assert result.confidence > 0.8

    @pytest.mark.asyncio
    async def test_reflexion_name_and_category(self):
        from parwa.frameworks.quality.reflexion import ReflexionTechnique
        technique = ReflexionTechnique()
        assert technique.name == "reflexion"
        assert technique.category == TechniqueCategory.QUALITY

    @pytest.mark.asyncio
    async def test_reflexion_requires_medium(self):
        from parwa.frameworks.quality.reflexion import ReflexionTechnique
        technique = ReflexionTechnique()
        assert technique.can_apply("QUALITY_SCORER", "simple") is False
        assert technique.can_apply("QUALITY_SCORER", "medium") is True

    @pytest.mark.asyncio
    async def test_reflexion_applicable_nodes(self):
        from parwa.frameworks.quality.reflexion import ReflexionTechnique
        technique = ReflexionTechnique()
        nodes = technique.applicable_nodes
        assert "QUALITY_SCORER" in nodes
        assert "RESPONSE_FORMATTER" in nodes
        assert "REASONING_ENGINE" in nodes


# ─── Self-Consistency Technique Tests ─────────────────────────────────────────

class TestSelfConsistencyTechnique:

    def setup_method(self):
        reset_registry()

    @pytest.mark.asyncio
    async def test_self_consistency_produces_result(self):
        from parwa.frameworks.quality.self_consistency import SelfConsistencyTechnique
        technique = SelfConsistencyTechnique()
        result = await technique.think(
            "Check consistency",
            {"intent": "refund_request", "reasoning_conclusion": "Eligible for refund"},
        )
        assert isinstance(result, TechniqueResult)
        assert "self_consistency" in result.frameworks_used

    @pytest.mark.asyncio
    async def test_self_consistency_mock_majority_agrees(self):
        from parwa.frameworks.quality.self_consistency import SelfConsistencyTechnique
        technique = SelfConsistencyTechnique()
        result = await technique.think(
            "Check",
            {"intent": "refund_request", "reasoning_conclusion": "Eligible"},
        )
        # In mock mode, all 3 agree → majority
        assert result.metadata["agreement_count"] >= 2
        assert result.confidence > 0.8

    @pytest.mark.asyncio
    async def test_self_consistency_name_and_category(self):
        from parwa.frameworks.quality.self_consistency import SelfConsistencyTechnique
        technique = SelfConsistencyTechnique()
        assert technique.name == "self_consistency"
        assert technique.category == TechniqueCategory.QUALITY

    @pytest.mark.asyncio
    async def test_self_consistency_requires_complex(self):
        from parwa.frameworks.quality.self_consistency import SelfConsistencyTechnique
        technique = SelfConsistencyTechnique()
        assert technique.can_apply("QUALITY_SCORER", "simple") is False
        assert technique.can_apply("QUALITY_SCORER", "medium") is False
        assert technique.can_apply("QUALITY_SCORER", "complex") is True
        assert technique.can_apply("QUALITY_SCORER", "critical") is True

    @pytest.mark.asyncio
    async def test_self_consistency_applicable_nodes(self):
        from parwa.frameworks.quality.self_consistency import SelfConsistencyTechnique
        technique = SelfConsistencyTechnique()
        nodes = technique.applicable_nodes
        assert "QUALITY_SCORER" in nodes
        assert "REASONING_ENGINE" in nodes

    @pytest.mark.asyncio
    async def test_self_consistency_num_samples_metadata(self):
        from parwa.frameworks.quality.self_consistency import SelfConsistencyTechnique
        technique = SelfConsistencyTechnique()
        result = await technique.think(
            "Test",
            {"intent": "refund_request", "reasoning_conclusion": "Test"},
        )
        assert result.metadata["num_samples"] >= 3


# ─── CRP (Constrained Response) Technique Tests ───────────────────────────────

class TestConstrainedResponseTechnique:

    def setup_method(self):
        reset_registry()

    @pytest.mark.asyncio
    async def test_crp_produces_result(self):
        from parwa.frameworks.quality.crp import ConstrainedResponseTechnique
        technique = ConstrainedResponseTechnique()
        result = await technique.think(
            "Generate quality score",
            {"intent": "refund_request", "reasoning_conclusion": "Eligible"},
        )
        assert isinstance(result, TechniqueResult)
        assert "crp" in result.frameworks_used

    @pytest.mark.asyncio
    async def test_crp_uses_schema(self):
        from parwa.frameworks.quality.crp import ConstrainedResponseTechnique
        technique = ConstrainedResponseTechnique()
        result = await technique.think(
            "Score quality",
            {"intent": "refund_request", "reasoning_conclusion": "Test"},
        )
        assert result.metadata["schema_used"] != ""

    @pytest.mark.asyncio
    async def test_crp_name_and_category(self):
        from parwa.frameworks.quality.crp import ConstrainedResponseTechnique
        technique = ConstrainedResponseTechnique()
        assert technique.name == "crp"
        assert technique.category == TechniqueCategory.QUALITY

    @pytest.mark.asyncio
    async def test_crp_activates_on_simple(self):
        from parwa.frameworks.quality.crp import ConstrainedResponseTechnique
        technique = ConstrainedResponseTechnique()
        assert technique.can_apply("QUALITY_SCORER", "simple") is True

    @pytest.mark.asyncio
    async def test_crp_applicable_nodes(self):
        from parwa.frameworks.quality.crp import ConstrainedResponseTechnique
        technique = ConstrainedResponseTechnique()
        nodes = technique.applicable_nodes
        assert "QUALITY_SCORER" in nodes
        assert "RESPONSE_FORMATTER" in nodes
        assert "REASONING_ENGINE" in nodes
        assert "ACTION_PLANNER" in nodes

    @pytest.mark.asyncio
    async def test_crp_quality_scorer_schema(self):
        from parwa.frameworks.quality.crp import ConstrainedResponseTechnique
        technique = ConstrainedResponseTechnique()
        result = await technique.think(
            "Score quality",
            {"intent": "refund_request", "reasoning_conclusion": "Eligible", "quality_score": 85},
        )
        # Should infer QUALITY_SCORER schema
        assert result.metadata["node_hint"] == "QUALITY_SCORER"


# ─── Least-to-Most Technique Tests ───────────────────────────────────────────

class TestLeastToMostTechnique:

    def setup_method(self):
        reset_registry()

    @pytest.mark.asyncio
    async def test_least_to_most_produces_result(self):
        from parwa.frameworks.quality.least_to_most import LeastToMostTechnique
        technique = LeastToMostTechnique()
        result = await technique.think(
            "Solve refund problem",
            {"intent": "refund_request", "reasoning_conclusion": "Eligible"},
        )
        assert isinstance(result, TechniqueResult)
        assert "least_to_most" in result.frameworks_used

    @pytest.mark.asyncio
    async def test_least_to_most_decomposes_problem(self):
        from parwa.frameworks.quality.least_to_most import LeastToMostTechnique
        technique = LeastToMostTechnique()
        result = await technique.think(
            "Solve refund problem",
            {"intent": "refund_request", "reasoning_conclusion": "Eligible"},
        )
        sub_problems = result.metadata["sub_problems"]
        assert len(sub_problems) >= 2
        assert result.metadata["sub_problem_count"] >= 2

    @pytest.mark.asyncio
    async def test_least_to_most_name_and_category(self):
        from parwa.frameworks.quality.least_to_most import LeastToMostTechnique
        technique = LeastToMostTechnique()
        assert technique.name == "least_to_most"
        assert technique.category == TechniqueCategory.QUALITY

    @pytest.mark.asyncio
    async def test_least_to_most_requires_complex(self):
        from parwa.frameworks.quality.least_to_most import LeastToMostTechnique
        technique = LeastToMostTechnique()
        assert technique.can_apply("REASONING_ENGINE", "simple") is False
        assert technique.can_apply("REASONING_ENGINE", "medium") is False
        assert technique.can_apply("REASONING_ENGINE", "complex") is True

    @pytest.mark.asyncio
    async def test_least_to_most_applicable_nodes(self):
        from parwa.frameworks.quality.least_to_most import LeastToMostTechnique
        technique = LeastToMostTechnique()
        nodes = technique.applicable_nodes
        assert "REASONING_ENGINE" in nodes
        assert "ACTION_PLANNER" in nodes
        assert "QUALITY_SCORER" in nodes
        assert "STRATEGY_PLANNER" in nodes

    @pytest.mark.asyncio
    async def test_least_to_most_different_intents(self):
        from parwa.frameworks.quality.least_to_most import LeastToMostTechnique
        technique = LeastToMostTechnique()
        for intent in ["refund_request", "order_status", "cancellation", "billing_issue"]:
            result = await technique.think(
                f"Solve {intent}",
                {"intent": intent, "reasoning_conclusion": "Test"},
            )
            assert len(result.metadata["sub_problems"]) >= 2


# ─── FrameworkBrain + Phase 3 Techniques Integration ─────────────────────────

class TestFrameworkBrainPhase3:

    def setup_method(self):
        reset_registry()

    @pytest.mark.asyncio
    async def test_brain_with_rag_techniques_kb_retriever(self):
        brain = FrameworkBrain(
            node="KB_RETRIEVER",
            state={"complexity": "medium", "intent": "refund_request", "raw_message": "I was charged twice"},
        )
        result = await brain.think(
            prompt="I was charged twice",
            techniques=["clara", "hyde", "multi_query", "step_back"],
        )
        # Medium complexity should activate all RAG techniques
        assert len(result.frameworks_used) >= 2

    @pytest.mark.asyncio
    async def test_brain_with_quality_techniques(self):
        brain = FrameworkBrain(
            node="QUALITY_SCORER",
            state={
                "complexity": "complex",
                "intent": "refund_request",
                "reasoning_conclusion": "Eligible",
                "verification_passed": True,
            },
        )
        result = await brain.think(
            prompt="Score this response",
            techniques=["reflexion", "self_consistency", "crp", "least_to_most"],
        )
        assert len(result.frameworks_used) >= 2

    @pytest.mark.asyncio
    async def test_brain_rag_simple_only_activates_hyde(self):
        brain = FrameworkBrain(
            node="KB_RETRIEVER",
            state={"complexity": "simple", "intent": "order_status", "raw_message": "Where is my order?"},
        )
        result = await brain.think(
            prompt="Where is my order?",
            techniques=["clara", "hyde", "multi_query", "step_back"],
        )
        # Simple should only activate HyDE (min_complexity=simple)
        assert "hyde" in result.frameworks_used
        # CLARA, Multi-Query, Step-Back require medium+
        assert "clara" not in result.frameworks_used
        assert "multi_query" not in result.frameworks_used
        assert "step_back" not in result.frameworks_used

    @pytest.mark.asyncio
    async def test_brain_quality_complex_activates_all(self):
        brain = FrameworkBrain(
            node="QUALITY_SCORER",
            state={
                "complexity": "complex",
                "intent": "refund_request",
                "reasoning_conclusion": "Eligible",
                "verification_passed": True,
            },
        )
        result = await brain.think(
            prompt="Score",
            techniques=["reflexion", "self_consistency", "crp", "least_to_most"],
        )
        # Complex should activate: reflexion (medium+), self_consistency (complex+),
        # crp (simple+), least_to_most (complex+)
        assert "reflexion" in result.frameworks_used
        assert "crp" in result.frameworks_used
        assert "self_consistency" in result.frameworks_used
        assert "least_to_most" in result.frameworks_used

    @pytest.mark.asyncio
    async def test_brain_registry_has_all_phase3_techniques(self):
        registry = get_registry()
        # RAG techniques
        assert registry.get("clara") is not None
        assert registry.get("hyde") is not None
        assert registry.get("multi_query") is not None
        assert registry.get("step_back") is not None
        # Quality techniques
        assert registry.get("reflexion") is not None
        assert registry.get("self_consistency") is not None
        assert registry.get("crp") is not None
        assert registry.get("least_to_most") is not None
        # Total: 6 reasoning + 4 RAG + 4 quality + 3 memory = 17
        assert registry.count() == 20

    @pytest.mark.asyncio
    async def test_brain_kb_retriever_techniques_from_registry(self):
        registry = get_registry()
        kb_techniques = registry.get_technique_names_for_node("KB_RETRIEVER")
        # Should include: chain_of_thought, clara, hyde, multi_query, step_back
        assert "chain_of_thought" in kb_techniques
        assert "clara" in kb_techniques
        assert "hyde" in kb_techniques
        assert "multi_query" in kb_techniques
        assert "step_back" in kb_techniques

    @pytest.mark.asyncio
    async def test_brain_quality_scorer_techniques_from_registry(self):
        registry = get_registry()
        qs_techniques = registry.get_technique_names_for_node("QUALITY_SCORER")
        # Should include: chain_of_thought, react, reflexion, self_consistency, crp, least_to_most
        assert "chain_of_thought" in qs_techniques
        assert "react" in qs_techniques
        assert "reflexion" in qs_techniques
        assert "self_consistency" in qs_techniques
        assert "crp" in qs_techniques
        assert "least_to_most" in qs_techniques
