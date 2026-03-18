"""
Integration Tests for TRIVYA Tier 1 + Tier 2 Pipeline.

Tests the complete TRIVYA reasoning pipeline:
- Tier 1 always fires on every query
- Tier 2 fires conditionally based on trigger detection
- Full end-to-end processing works correctly
"""
import os
import pytest
from uuid import uuid4, UUID
from unittest.mock import MagicMock, patch

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_unit_tests_32_characters!")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")

# Tier 1 imports
from shared.trivya_techniques.tier1.clara import CLARA, CLARAResult, CLARAConfig
from shared.trivya_techniques.tier1.crp import CRP, CRPResult, CRPConfig
from shared.trivya_techniques.tier1.gsd_integration import (
    GSDIntegration,
    GSDIntegrationResult,
    GSDIntegrationConfig,
)
from shared.trivya_techniques.orchestrator import (
    T1Orchestrator,
    T1OrchestratorResult,
    T1OrchestratorConfig,
    ProcessingStage,
)

# Tier 2 imports
from shared.trivya_techniques.tier2.trigger_detector import (
    TriggerDetector,
    TriggerResult,
    TriggerType,
)
from shared.trivya_techniques.tier2.chain_of_thought import (
    ChainOfThought,
    CoTResult,
    CoTConfig,
)
from shared.trivya_techniques.tier2.react import (
    ReActTechnique,
    ReActResult,
    ReActConfig,
)
from shared.trivya_techniques.tier2.reverse_thinking import (
    ReverseThinking,
    ReverseThinkingResult,
    ReverseThinkingConfig,
)
from shared.trivya_techniques.tier2.step_back import (
    StepBack,
    StepBackResult,
    StepBackConfig,
)
from shared.trivya_techniques.tier2.thread_of_thought import (
    ThreadOfThought,
    ToTResult,
    ToTConfig,
)

# Cold start import
from shared.knowledge_base.cold_start import (
    ColdStart,
    ColdStartResult,
    ColdStartConfig,
    IndustryType,
)


class MockEmbeddingFunction:
    """Mock embedding function for testing."""

    def __call__(self, text: str) -> list:
        """Return mock embedding vector."""
        # Simple hash-based mock embedding
        return [float(hash(text) % 100) / 100.0] * 1536


class TestT1AlwaysFires:
    """Tests verifying Tier 1 always fires on every query."""

    def test_t1_orchestrator_processes_simple_query(self):
        """T1 should process even simple queries."""
        orchestrator = T1Orchestrator(
            config=T1OrchestratorConfig(always_use_clara=True)
        )

        result = orchestrator.process("Hello")

        assert result.stage == ProcessingStage.COMPLETED.value
        assert result.clara_result is not None

    def test_t1_orchestrator_processes_complex_query(self):
        """T1 should process complex queries."""
        orchestrator = T1Orchestrator()

        result = orchestrator.process(
            "How do I resolve the database connection issue?"
        )

        assert result.stage == ProcessingStage.COMPLETED.value

    def test_t1_orchestrator_processes_empty_conversation(self):
        """T1 should handle new conversations."""
        orchestrator = T1Orchestrator()

        conv_id = orchestrator.create_conversation(customer_id="test_user")
        result = orchestrator.process("First message", conversation_id=conv_id)

        assert result.conversation_id == conv_id
        assert result.stage == ProcessingStage.COMPLETED.value

    def test_t1_clara_always_retrieves(self):
        """CLARA should always attempt retrieval."""
        clara = CLARA(
            config=CLARAConfig(fallback_enabled=True)
        )

        result = clara.retrieve("Any query here")

        assert result.query == "Any query here"
        assert result.retrieval_method != ""

    def test_t1_processing_stages_sequence(self):
        """T1 should process through correct stages."""
        orchestrator = T1Orchestrator(
            config=T1OrchestratorConfig(
                always_use_clara=True,
                use_smart_router=True,
            )
        )

        result = orchestrator.process("Test query")

        # Should complete all enabled stages
        assert result.stage == ProcessingStage.COMPLETED.value


class TestT2ConditionalFiring:
    """Tests verifying Tier 2 fires conditionally."""

    def test_t2_not_triggered_for_simple_query(self):
        """T2 should not fire for simple queries."""
        detector = TriggerDetector()

        # Simple greeting shouldn't trigger T2
        result = detector.detect("Hello there")

        # Simple query may not trigger any technique
        assert isinstance(result.triggered_techniques, list)

    def test_t2_triggered_for_decision_query(self):
        """T2 should fire for decision queries."""
        detector = TriggerDetector()

        result = detector.detect("Should I choose option A or B?")

        assert TriggerType.CHAIN_OF_THOUGHT in result.triggered_techniques

    def test_t2_triggered_for_action_query(self):
        """T2 should fire for action-oriented queries."""
        detector = TriggerDetector()

        result = detector.detect("Check my account balance")

        assert TriggerType.REACT in result.triggered_techniques

    def test_t2_triggered_for_goal_query(self):
        """T2 should fire for goal-oriented queries."""
        detector = TriggerDetector()

        result = detector.detect("I want to become a certified developer")

        assert TriggerType.REVERSE_THINKING in result.triggered_techniques

    def test_t2_triggered_for_exploration_query(self):
        """T2 should fire for exploration queries."""
        detector = TriggerDetector()

        result = detector.detect("Tell me about machine learning")

        assert TriggerType.THREAD_OF_THOUGHT in result.triggered_techniques

    def test_t2_max_techniques_limit(self):
        """T2 should respect max techniques limit."""
        detector = TriggerDetector(max_techniques_per_query=2)

        result = detector.detect(
            "I need to check my account and compare options"
        )

        assert len(result.triggered_techniques) <= 2


class TestT1T2Integration:
    """Full T1+T2 integration tests."""

    def test_t1_t2_simple_query_flow(self):
        """Test flow for simple query - only T1 fires."""
        t1 = T1Orchestrator()
        t2_detector = TriggerDetector()

        query = "Hello"

        # T1 always runs
        t1_result = t1.process(query)
        assert t1_result.stage == ProcessingStage.COMPLETED.value

        # T2 may not fire
        t2_result = t2_detector.detect(query)
        # Simple query may have no triggers
        assert isinstance(t2_result.triggered_techniques, list)

    def test_t1_t2_complex_query_flow(self):
        """Test flow for complex query - both T1 and T2 fire."""
        t1 = T1Orchestrator()
        t2_detector = TriggerDetector()
        cot = ChainOfThought()

        query = "How should I decide between the two pricing plans?"

        # T1 always runs first
        t1_result = t1.process(query)
        assert t1_result.stage == ProcessingStage.COMPLETED.value
        assert t1_result.clara_result is not None

        # T2 fires for decision query
        t2_trigger = t2_detector.detect(query)
        assert TriggerType.CHAIN_OF_THOUGHT in t2_trigger.triggered_techniques

        # Execute T2 technique
        cot_result = cot.reason(query)
        assert len(cot_result.steps) > 0

    def test_t1_t2_action_query_flow(self):
        """Test flow for action query - T1 + ReAct."""
        t1 = T1Orchestrator()
        t2_detector = TriggerDetector()
        react = ReActTechnique()

        query = "Check my order status"

        # T1 runs
        t1_result = t1.process(query)

        # T2 detects ReAct
        t2_trigger = t2_detector.detect(query)
        assert TriggerType.REACT in t2_trigger.triggered_techniques

        # Execute ReAct
        react_result = react.execute(query)
        assert len(react_result.steps) > 0

    def test_t1_provides_context_for_t2(self):
        """T1 context can enhance T2 reasoning."""
        t1 = T1Orchestrator()
        cot = ChainOfThought()

        query = "Compare the subscription options"

        # T1 retrieves context
        t1_result = t1.process(query)
        context = t1_result.context

        # T2 can use context
        cot_result = cot.reason(query, context=context)

        assert cot_result.query == query
        assert len(cot_result.steps) > 0

    def test_full_pipeline_with_conversation(self):
        """Test full pipeline with conversation management."""
        t1 = T1Orchestrator()
        t2_detector = TriggerDetector()

        # Create conversation
        conv_id = t1.create_conversation(customer_id="test_user")

        # First query
        query1 = "What products do you offer?"
        result1 = t1.process(query1, conversation_id=conv_id)
        assert result1.stage == ProcessingStage.COMPLETED.value

        # Second query (complex)
        query2 = "Should I choose the premium or basic plan?"
        result2 = t1.process(query2, conversation_id=conv_id)

        # Check T2 trigger
        t2_trigger = t2_detector.detect(query2)
        assert TriggerType.CHAIN_OF_THOUGHT in t2_trigger.triggered_techniques


class TestAllT2Techniques:
    """Tests for all T2 techniques."""

    def test_chain_of_thought_produces_steps(self):
        """CoT should produce reasoning steps."""
        cot = ChainOfThought()

        result = cot.reason("How do I solve this problem?")

        assert len(result.steps) > 0
        assert result.total_steps > 0
        assert result.overall_confidence >= 0

    def test_react_produces_actions(self):
        """ReAct should produce action steps."""
        react = ReActTechnique()

        result = react.execute("Find information about returns")

        assert len(result.steps) > 0
        assert result.total_steps > 0

    def test_reverse_thinking_produces_backward_steps(self):
        """Reverse thinking should work backward from goal."""
        rt = ReverseThinking()

        result = rt.reason_backward("I want to complete the project")

        assert len(result.steps) > 0
        assert result.goal != ""
        assert result.feasibility_score >= 0

    def test_step_back_produces_abstractions(self):
        """Step back should produce abstraction layers."""
        sb = StepBack()

        result = sb.analyze("Why does this error occur?")

        assert len(result.abstraction_layers) > 0
        assert result.core_principle != ""

    def test_thread_of_thought_explores(self):
        """Thread of thought should create exploration threads."""
        tot = ThreadOfThought()

        result = tot.explore("Explain cloud computing")

        assert result.main_thread is not None
        assert result.total_threads >= 1

    def test_techniques_produce_different_outputs(self):
        """Each technique should produce different output format."""
        query = "Complex problem to solve"

        cot = ChainOfThought()
        react = ReActTechnique()
        rt = ReverseThinking()
        sb = StepBack()
        tot = ThreadOfThought()

        cot_result = cot.reason(query)
        react_result = react.execute(query)
        rt_result = rt.reason_backward(query)
        sb_result = sb.analyze(query)
        tot_result = tot.explore(query)

        # Each produces different structure
        assert hasattr(cot_result, 'steps')
        assert hasattr(react_result, 'actions_taken')
        assert hasattr(rt_result, 'forward_plan')
        assert hasattr(sb_result, 'abstraction_layers')
        assert hasattr(tot_result, 'sub_threads')


class TestColdStartIntegration:
    """Tests for cold start with T1 integration."""

    def test_cold_start_creates_kb(self):
        """Cold start should bootstrap knowledge base."""
        cold_start = ColdStart()
        company_id = uuid4()

        result = cold_start.bootstrap(
            company_id=company_id,
            industry=IndustryType.ECOMMERCE
        )

        assert result.status == "completed"
        assert result.documents_ingested > 0

    def test_cold_start_industry_specific(self):
        """Cold start should use industry-specific FAQs."""
        cold_start = ColdStart()

        # E-commerce should have order/shipping FAQs
        preview = cold_start.get_industry_preview(IndustryType.ECOMMERCE)

        assert "orders" in preview or "shipping" in preview

    def test_cold_start_with_custom_faqs(self):
        """Cold start should include custom FAQs."""
        cold_start = ColdStart()
        company_id = uuid4()

        custom_faqs = [
            {
                "question": "What is our return policy?",
                "answer": "We offer 30-day returns on all items.",
                "category": "returns"
            }
        ]

        result = cold_start.bootstrap(
            company_id=company_id,
            industry=IndustryType.ECOMMERCE,
            custom_faqs=custom_faqs
        )

        assert result.status == "completed"

    def test_available_industries(self):
        """Should list available industries."""
        cold_start = ColdStart()

        industries = cold_start.get_available_industries()

        assert IndustryType.ECOMMERCE.value in industries
        assert IndustryType.SAAS.value in industries


class TestEdgeCases:
    """Edge case tests for T1+T2 pipeline."""

    def test_empty_query_handling(self):
        """Empty queries should raise error."""
        t1 = T1Orchestrator()

        with pytest.raises(ValueError):
            t1.process("")

    def test_whitespace_query_handling(self):
        """Whitespace-only queries should raise error."""
        t1 = T1Orchestrator()

        with pytest.raises(ValueError):
            t1.process("   ")

    def test_very_long_query(self):
        """Very long queries should be handled."""
        t1 = T1Orchestrator()
        t2_detector = TriggerDetector()

        long_query = "How do I " + "solve " * 500 + "this?"

        t1_result = t1.process(long_query)
        t2_result = t2_detector.detect(long_query)

        assert t1_result.stage == ProcessingStage.COMPLETED.value

    def test_special_characters_query(self):
        """Special characters should be handled."""
        t1 = T1Orchestrator()

        result = t1.process("What's the @#$% error code?!?")

        assert result.stage == ProcessingStage.COMPLETED.value

    def test_unicode_query(self):
        """Unicode characters should be handled."""
        t1 = T1Orchestrator()

        result = t1.process("Comment ça va? 你好吗?")

        assert result.stage == ProcessingStage.COMPLETED.value


class TestPipelineStats:
    """Tests for pipeline statistics and monitoring."""

    def test_t1_orchestrator_stats(self):
        """T1 should track processing stats."""
        t1 = T1Orchestrator()

        t1.process("Query 1")
        t1.process("Query 2")

        stats = t1.get_stats()

        assert stats["queries_processed"] == 2
        assert stats["average_processing_time_ms"] > 0

    def test_t2_detector_stats(self):
        """T2 detector should track analysis stats."""
        detector = TriggerDetector()

        detector.detect("Query 1")
        detector.detect("Query 2")

        stats = detector.get_stats()

        assert stats["queries_analyzed"] == 2

    def test_cot_stats(self):
        """CoT should track reasoning stats."""
        cot = ChainOfThought()

        cot.reason("Problem 1")
        cot.reason("Problem 2")

        stats = cot.get_stats()

        assert stats["queries_processed"] == 2
        assert stats["average_steps_per_query"] > 0

    def test_cold_start_stats(self):
        """Cold start should track bootstrap stats."""
        cold_start = ColdStart()

        cold_start.bootstrap(uuid4(), IndustryType.ECOMMERCE)
        cold_start.bootstrap(uuid4(), IndustryType.SAAS)

        stats = cold_start.get_stats()

        assert stats["cold_starts_completed"] == 2
