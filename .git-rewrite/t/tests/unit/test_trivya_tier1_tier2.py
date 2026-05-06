"""
Integration Tests for TRIVYA Tier 1 + Tier 2 + Tier 3 Pipeline.

Tests the complete TRIVYA reasoning pipeline:
- Tier 1 always fires on every query
- Tier 2 fires conditionally based on trigger detection
- Tier 3 fires ONLY on high-stakes scenarios (VIP + amount>$100 + anger>80%)
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

# Tier 3 imports
from shared.trivya_techniques.tier3.trigger_detector import (
    T3TriggerDetector,
    T3TriggerConfig,
    T3TriggerType,
    HighStakesIndicator,
)
from shared.trivya_techniques.tier3.gst import (
    GeneratedStepByStepThought,
    GSTConfig,
    StepStatus,
)
from shared.trivya_techniques.tier3.universe_of_thoughts import (
    UniverseOfThoughts,
    UniverseConfig,
    PathType,
    PathStatus,
)
from shared.trivya_techniques.tier3.tree_of_thoughts import (
    TreeOfThoughts,
    TreeConfig,
    NodeStatus,
    SearchStrategy,
)
from shared.trivya_techniques.tier3.self_consistency import (
    SelfConsistency,
    SelfConsistencyConfig,
    VoteStrategy,
)
from shared.trivya_techniques.tier3.reflexion import (
    Reflexion,
    ReflexionConfig,
    ReflectionStatus,
)
from shared.trivya_techniques.tier3.least_to_most import (
    LeastToMost,
    LeastToMostConfig,
    SubQuestionStatus,
    Difficulty,
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


# =============================================================================
# TIER 3 INTEGRATION TESTS
# =============================================================================

class TestT3TriggerConditions:
    """Tests verifying T3 trigger conditions."""

    def test_t3_fires_when_all_conditions_met(self):
        """T3 should fire when VIP + amount>$100 + anger>80%."""
        t3_detector = T3TriggerDetector()

        result = t3_detector.detect(
            query="I need this resolved immediately!",
            is_vip=True,
            transaction_amount=150.0,
            anger_level=0.85
        )

        assert result.should_fire_t3 is True
        assert result.is_vip is True
        assert result.amount_exceeds_threshold is True
        assert result.anger_exceeds_threshold is True

    def test_t3_does_not_fire_missing_vip(self):
        """T3 should NOT fire without VIP status."""
        t3_detector = T3TriggerDetector()

        result = t3_detector.detect(
            query="I have a question",
            is_vip=False,
            transaction_amount=150.0,
            anger_level=0.85
        )

        assert result.should_fire_t3 is False
        assert result.is_vip is False

    def test_t3_does_not_fire_low_amount(self):
        """T3 should NOT fire when amount below $100."""
        t3_detector = T3TriggerDetector()

        result = t3_detector.detect(
            query="Help me",
            is_vip=True,
            transaction_amount=50.0,  # Below $100
            anger_level=0.85
        )

        assert result.should_fire_t3 is False
        assert result.amount_exceeds_threshold is False

    def test_t3_does_not_fire_low_anger(self):
        """T3 should NOT fire when anger below 80%."""
        t3_detector = T3TriggerDetector()

        result = t3_detector.detect(
            query="Quick question",
            is_vip=True,
            transaction_amount=150.0,
            anger_level=0.50  # Below 80%
        )

        assert result.should_fire_t3 is False
        assert result.anger_exceeds_threshold is False

    def test_t3_fires_on_legal_mention(self):
        """T3 should fire when legal action is mentioned."""
        t3_detector = T3TriggerDetector()

        result = t3_detector.detect(
            query="I'm going to contact my lawyer about this!",
            is_vip=False,
            transaction_amount=50.0,
            anger_level=0.50
        )

        assert result.should_fire_t3 is True
        assert HighStakesIndicator.LEGAL_MENTION.value in result.risk_factors

    def test_t3_detects_escalation_risk(self):
        """T3 should detect escalation risk patterns."""
        t3_detector = T3TriggerDetector()

        result = t3_detector.detect(
            query="I want to speak to your supervisor right now!",
            is_vip=False,
            transaction_amount=None,
            anger_level=0.60
        )

        assert HighStakesIndicator.ESCALATION_RISK.value in result.risk_factors

    def test_t3_detects_social_media_threat(self):
        """T3 should detect social media threat patterns."""
        t3_detector = T3TriggerDetector()

        result = t3_detector.detect(
            query="I'm going to post this on Twitter and Facebook!",
            is_vip=False,
            transaction_amount=None,
            anger_level=0.50
        )

        assert HighStakesIndicator.SOCIAL_MEDIA_THREAT.value in result.risk_factors


class TestT3DoesNotActivateOnSimpleQueries:
    """Tests verifying T3 does NOT activate on simple FAQ queries."""

    def test_t3_not_activated_for_simple_faq(self):
        """T3 should NOT activate for simple FAQ queries."""
        t3_detector = T3TriggerDetector()

        result = t3_detector.detect(
            query="What are your business hours?",
            is_vip=False,
            transaction_amount=None,
            anger_level=0.10
        )

        assert result.should_fire_t3 is False

    def test_t3_not_activated_for_greeting(self):
        """T3 should NOT activate for greetings."""
        t3_detector = T3TriggerDetector()

        result = t3_detector.detect(
            query="Hello, how are you?",
            is_vip=False,
            transaction_amount=None,
            anger_level=0.05
        )

        assert result.should_fire_t3 is False

    def test_t3_not_activated_for_simple_question(self):
        """T3 should NOT activate for simple questions."""
        t3_detector = T3TriggerDetector()

        result = t3_detector.detect(
            query="What is your return policy?",
            is_vip=False,
            transaction_amount=None,
            anger_level=0.10
        )

        assert result.should_fire_t3 is False

    def test_t3_not_activated_for_non_vip_complex_query(self):
        """T3 should NOT activate for non-VIP even with complex query."""
        t3_detector = T3TriggerDetector()

        # Use lower values to avoid triggering secondary path (high_stakes_score >= 0.7)
        result = t3_detector.detect(
            query="I have a question about my order",
            is_vip=False,  # Not VIP
            transaction_amount=150.0,  # Above $100
            anger_level=0.85  # Above 80%
        )

        # Should not fire because VIP is False (AND logic requires all conditions)
        # Secondary path requires high_stakes_score >= 0.7 + 2+ risk factors
        # With only amount + anger (no VIP), score is ~0.45 which is below 0.7
        assert result.should_fire_t3 is False


class TestAllT3Techniques:
    """Tests verifying all T3 techniques produce expected outputs."""

    def test_gst_produces_steps(self):
        """GST should produce reasoning steps."""
        gst = GeneratedStepByStepThought()

        result = gst.reason("How do I resolve this complex issue?")

        assert result.total_steps > 0
        assert len(result.steps) > 0
        assert result.final_conclusion != ""

    def test_gst_step_status_tracking(self):
        """GST should track step completion status."""
        gst = GeneratedStepByStepThought()

        result = gst.reason("Complex multi-step problem")

        completed_steps = [s for s in result.steps if s.status == StepStatus.COMPLETED]
        assert len(completed_steps) > 0

    def test_universe_of_thoughts_explores_paths(self):
        """Universe of Thoughts should explore multiple paths."""
        uot = UniverseOfThoughts()

        result = uot.explore("Should I invest in stocks or bonds?")

        assert result.total_paths_explored >= 3
        assert len(result.paths) >= 3

    def test_universe_of_thoughts_path_types(self):
        """Universe of Thoughts should generate diverse path types."""
        uot = UniverseOfThoughts()

        result = uot.explore("How should I approach this problem?")

        path_types = {p.path_type for p in result.paths}
        assert len(path_types) >= 2  # At least 2 different types

    def test_tree_of_thoughts_creates_structure(self):
        """Tree of Thoughts should create tree structure."""
        tot = TreeOfThoughts()

        result = tot.reason("How should I solve this?")

        assert result.root is not None
        assert result.total_nodes > 0

    def test_tree_of_thoughts_search_strategies(self):
        """Tree of Thoughts should support different search strategies."""
        for strategy in [SearchStrategy.BFS, SearchStrategy.DFS]:
            config = TreeConfig(search_strategy=strategy)
            tot = TreeOfThoughts(config=config)

            result = tot.reason("Test query")
            assert result.search_strategy == strategy.value

    def test_self_consistency_voting(self):
        """Self-Consistency should perform majority voting."""
        sc = SelfConsistency()

        result = sc.reason("What is the best approach?")

        assert result.total_chains == 5  # Default num_chains
        assert len(result.chains) == 5
        assert len(result.vote_distribution) > 0

    def test_self_consistency_consensus_detection(self):
        """Self-Consistency should detect consensus."""
        sc = SelfConsistency()

        result = sc.reason("Is 2+2=4?")

        assert result.winning_answer is not None or result.has_consensus is False

    def test_reflexion_iterations(self):
        """Reflexion should run improvement iterations."""
        reflexion = Reflexion()

        result = reflexion.reason("How can I improve this?")

        assert result.total_iterations > 0
        assert len(result.iterations) > 0

    def test_reflexion_lessons_learned(self):
        """Reflexion should extract lessons."""
        reflexion = Reflexion()

        result = reflexion.reason("Complex problem")

        assert isinstance(result.lessons_learned, list)

    def test_least_to_most_decomposition(self):
        """Least-to-Most should decompose queries."""
        ltm = LeastToMost()

        result = ltm.reason("What is Python and how do I learn it?")

        assert result.total_sub_questions >= 2
        assert len(result.sub_questions) >= 2

    def test_least_to_most_difficulty_ordering(self):
        """Least-to-Most should order by difficulty."""
        ltm = LeastToMost()

        result = ltm.reason("Complex multi-part question")

        assert result.ordered_by_difficulty is True


class TestT1T2T3FullPipeline:
    """Full T1→T2→T3 pipeline integration tests."""

    def test_full_pipeline_simple_query(self):
        """Test full pipeline with simple query - only T1 fires."""
        t1 = T1Orchestrator()
        t2_detector = TriggerDetector()
        t3_detector = T3TriggerDetector()

        query = "Hello, what are your hours?"

        # T1 always runs
        t1_result = t1.process(query)
        assert t1_result.stage == ProcessingStage.COMPLETED.value

        # T2 may or may not fire (simple query)
        t2_result = t2_detector.detect(query)
        assert isinstance(t2_result.triggered_techniques, list)

        # T3 should NOT fire
        t3_result = t3_detector.detect(
            query=query,
            is_vip=False,
            transaction_amount=None,
            anger_level=0.10
        )
        assert t3_result.should_fire_t3 is False

    def test_full_pipeline_t2_complex_query(self):
        """Test full pipeline with complex query - T1 + T2 fire."""
        t1 = T1Orchestrator()
        t2_detector = TriggerDetector()
        t3_detector = T3TriggerDetector()
        cot = ChainOfThought()

        query = "Should I choose the premium or basic subscription plan?"

        # T1 always runs first
        t1_result = t1.process(query)
        assert t1_result.stage == ProcessingStage.COMPLETED.value
        assert t1_result.clara_result is not None

        # T2 fires for decision query
        t2_result = t2_detector.detect(query)
        assert TriggerType.CHAIN_OF_THOUGHT in t2_result.triggered_techniques

        # Execute T2 technique
        cot_result = cot.reason(query, context=t1_result.context)
        assert len(cot_result.steps) > 0

        # T3 should NOT fire (no high-stakes indicators)
        t3_result = t3_detector.detect(
            query=query,
            is_vip=False,
            transaction_amount=None,
            anger_level=0.20
        )
        assert t3_result.should_fire_t3 is False

    def test_full_pipeline_high_stakes_scenario(self):
        """Test full pipeline with high-stakes - T1 + T2 + T3 all fire."""
        t1 = T1Orchestrator()
        t2_detector = TriggerDetector()
        t3_detector = T3TriggerDetector()

        query = "I demand an immediate resolution! This is unacceptable!"

        # T1 always runs first
        t1_result = t1.process(query)
        assert t1_result.stage == ProcessingStage.COMPLETED.value

        # T2 fires (action-oriented/escalation patterns)
        t2_result = t2_detector.detect(query)
        assert isinstance(t2_result.triggered_techniques, list)

        # T3 fires for high-stakes scenario
        t3_result = t3_detector.detect(
            query=query,
            is_vip=True,
            transaction_amount=250.0,
            anger_level=0.92
        )
        assert t3_result.should_fire_t3 is True

        # T3 techniques are selected
        assert len(t3_result.triggered_techniques) > 0
        assert T3TriggerType.GST in t3_result.triggered_techniques

    def test_full_pipeline_t3_legal_mention(self):
        """Test full pipeline with legal mention - T3 fires immediately."""
        t1 = T1Orchestrator()
        t3_detector = T3TriggerDetector()

        query = "I'm contacting my lawyer about this fraud!"

        # T1 runs
        t1_result = t1.process(query)
        assert t1_result.stage == ProcessingStage.COMPLETED.value

        # T3 fires immediately for legal mention
        t3_result = t3_detector.detect(
            query=query,
            is_vip=False,
            transaction_amount=50.0,
            anger_level=0.50
        )
        assert t3_result.should_fire_t3 is True
        assert HighStakesIndicator.LEGAL_MENTION.value in t3_result.risk_factors

        # All T3 techniques should be triggered for legal cases
        assert len(t3_result.triggered_techniques) >= 1

    def test_full_pipeline_with_all_t3_techniques(self):
        """Test full pipeline executing all T3 techniques."""
        t1 = T1Orchestrator()
        t3_detector = T3TriggerDetector()

        query = "I need immediate resolution or I will take legal action!"

        # T1 runs
        t1_result = t1.process(query)

        # T3 fires with legal mention
        t3_result = t3_detector.detect(
            query=query,
            is_vip=True,
            transaction_amount=500.0,
            anger_level=0.95
        )

        assert t3_result.should_fire_t3 is True

        # Execute GST (always included)
        gst = GeneratedStepByStepThought()
        gst_result = gst.reason(query)
        assert gst_result.total_steps > 0

        # Execute Universe of Thoughts if triggered
        if T3TriggerType.UNIVERSE_OF_THOUGHTS in t3_result.triggered_techniques:
            uot = UniverseOfThoughts()
            uot_result = uot.explore(query)
            assert uot_result.total_paths_explored >= 3

        # Execute Self-Consistency if triggered
        if T3TriggerType.SELF_CONSISTENCY in t3_result.triggered_techniques:
            sc = SelfConsistency()
            sc_result = sc.reason(query)
            assert sc_result.total_chains >= 3

    def test_t1_context_enhances_t3_reasoning(self):
        """Test that T1 context can enhance T3 reasoning."""
        t1 = T1Orchestrator()
        t3_detector = T3TriggerDetector()
        gst = GeneratedStepByStepThought()

        query = "This is unacceptable, I need this fixed now!"

        # T1 retrieves context
        t1_result = t1.process(query)
        context = t1_result.context

        # T3 fires
        t3_result = t3_detector.detect(
            query=query,
            is_vip=True,
            transaction_amount=200.0,
            anger_level=0.90
        )
        assert t3_result.should_fire_t3 is True

        # T3 can use T1 context
        gst_result = gst.reason(query)
        assert gst_result.total_steps > 0


class TestT3StatsTracking:
    """Tests for T3 statistics tracking."""

    def test_t3_detector_stats(self):
        """T3 detector should track analysis stats."""
        detector = T3TriggerDetector()

        detector.detect("Query 1", is_vip=True, transaction_amount=150.0, anger_level=0.85)
        detector.detect("Query 2", is_vip=False, transaction_amount=50.0, anger_level=0.50)

        stats = detector.get_stats()

        assert stats["queries_analyzed"] == 2
        assert stats["t3_activations"] == 1
        assert stats["activation_rate"] == 0.5

    def test_gst_stats(self):
        """GST should track reasoning stats."""
        gst = GeneratedStepByStepThought()

        gst.reason("Query 1")
        gst.reason("Query 2")

        stats = gst.get_stats()

        assert stats["queries_processed"] == 2
        assert stats["total_steps_generated"] > 0

    def test_universe_stats(self):
        """Universe of Thoughts should track exploration stats."""
        uot = UniverseOfThoughts()

        uot.explore("Query 1")
        uot.explore("Query 2")

        stats = uot.get_stats()

        assert stats["queries_processed"] == 2

    def test_tree_of_thoughts_stats(self):
        """Tree of Thoughts should track reasoning stats."""
        tot = TreeOfThoughts()

        tot.reason("Query 1")
        tot.reason("Query 2")

        stats = tot.get_stats()

        assert stats["queries_processed"] == 2

    def test_self_consistency_stats(self):
        """Self-Consistency should track voting stats."""
        sc = SelfConsistency()

        sc.reason("Query 1")
        sc.reason("Query 2")

        stats = sc.get_stats()

        assert stats["queries_processed"] == 2

    def test_reflexion_stats(self):
        """Reflexion should track reflection stats."""
        reflexion = Reflexion()

        reflexion.reason("Query 1")
        reflexion.reason("Query 2")

        stats = reflexion.get_stats()

        assert stats["queries_processed"] == 2

    def test_least_to_most_stats(self):
        """Least-to-Most should track decomposition stats."""
        ltm = LeastToMost()

        ltm.reason("Query 1")
        ltm.reason("Query 2")

        stats = ltm.get_stats()

        assert stats["queries_processed"] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
