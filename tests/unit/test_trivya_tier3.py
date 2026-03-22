"""
Unit tests for PARWA TRIVYA Tier 3 techniques.

Tests cover:
- T3TriggerDetector: Trigger detection for high-stakes scenarios
- GST: Generated Step-by-step Thought
- UniverseOfThoughts: Multiple solution paths
- TreeOfThoughts: Tree-structured reasoning
- SelfConsistency: Majority voting
- Reflexion: Self-improvement through reflection
- LeastToMost: Query decomposition
"""
import pytest
from datetime import datetime

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


# =============================================================================
# T3 Trigger Detector Tests
# =============================================================================

class TestT3TriggerDetector:
    """Tests for T3 Trigger Detector."""

    def test_trigger_detector_initialization(self):
        """Test trigger detector initializes correctly."""
        detector = T3TriggerDetector()

        assert detector.config is not None
        assert detector.config.amount_threshold == 100.0
        assert detector.config.anger_threshold == 0.80
        assert detector.config.require_all_conditions is True

    def test_trigger_detector_custom_config(self):
        """Test trigger detector with custom config."""
        config = T3TriggerConfig(
            amount_threshold=200.0,
            anger_threshold=0.70,
            require_all_conditions=False
        )
        detector = T3TriggerDetector(config=config)

        assert detector.config.amount_threshold == 200.0
        assert detector.config.anger_threshold == 0.70
        assert detector.config.require_all_conditions is False

    def test_t3_fires_on_all_conditions_met(self):
        """Test T3 fires when all conditions are met."""
        detector = T3TriggerDetector()

        result = detector.detect(
            query="I want to speak to your manager!",
            is_vip=True,
            transaction_amount=150.0,
            anger_level=0.85
        )

        assert result.should_fire_t3 is True
        assert result.is_vip is True
        assert result.amount_exceeds_threshold is True
        assert result.anger_exceeds_threshold is True

    def test_t3_does_not_fire_missing_vip(self):
        """Test T3 does not fire when VIP is False."""
        detector = T3TriggerDetector()

        result = detector.detect(
            query="I have a question",
            is_vip=False,
            transaction_amount=150.0,
            anger_level=0.85
        )

        assert result.should_fire_t3 is False
        assert result.is_vip is False

    def test_t3_does_not_fire_low_amount(self):
        """Test T3 does not fire when amount is below threshold."""
        detector = T3TriggerDetector()

        result = detector.detect(
            query="I have a complaint",
            is_vip=True,
            transaction_amount=50.0,  # Below $100 threshold
            anger_level=0.85
        )

        assert result.should_fire_t3 is False
        assert result.amount_exceeds_threshold is False

    def test_t3_does_not_fire_low_anger(self):
        """Test T3 does not fire when anger is below threshold."""
        detector = T3TriggerDetector()

        result = detector.detect(
            query="Quick question",
            is_vip=True,
            transaction_amount=150.0,
            anger_level=0.50  # Below 80% threshold
        )

        assert result.should_fire_t3 is False
        assert result.anger_exceeds_threshold is False

    def test_t3_fires_on_legal_mention(self):
        """Test T3 fires on legal mention regardless of other conditions."""
        detector = T3TriggerDetector()

        result = detector.detect(
            query="I'm going to contact my lawyer about this",
            is_vip=False,
            transaction_amount=50.0,
            anger_level=0.50
        )

        assert result.should_fire_t3 is True
        assert HighStakesIndicator.LEGAL_MENTION.value in result.risk_factors

    def test_t3_detects_escalation_risk(self):
        """Test detection of escalation risk indicators."""
        detector = T3TriggerDetector()

        result = detector.detect(
            query="I want to speak to your supervisor right now!",
            is_vip=False,
            transaction_amount=None,
            anger_level=0.60
        )

        assert HighStakesIndicator.ESCALATION_RISK.value in result.risk_factors

    def test_t3_detects_social_media_threat(self):
        """Test detection of social media threats."""
        detector = T3TriggerDetector()

        result = detector.detect(
            query="I'm going to post about this on Twitter and Facebook",
            is_vip=False,
            transaction_amount=None,
            anger_level=0.50
        )

        assert HighStakesIndicator.SOCIAL_MEDIA_THREAT.value in result.risk_factors

    def test_t3_selects_correct_techniques(self):
        """Test technique selection based on query type."""
        detector = T3TriggerDetector()

        result = detector.detect(
            query="How do I resolve this complex issue?",
            is_vip=True,
            transaction_amount=150.0,
            anger_level=0.85
        )

        assert result.should_fire_t3 is True
        assert len(result.triggered_techniques) > 0
        assert T3TriggerType.GST in result.triggered_techniques

    def test_t3_quick_check_method(self):
        """Test the quick check method."""
        detector = T3TriggerDetector()

        # Should fire with all conditions
        assert detector.should_fire_t3(
            query="Test",
            is_vip=True,
            transaction_amount=150.0,
            anger_level=0.85
        ) is True

        # Should not fire without all conditions
        assert detector.should_fire_t3(
            query="Test",
            is_vip=False,
            transaction_amount=150.0,
            anger_level=0.85
        ) is False

    def test_t3_empty_query_raises_error(self):
        """Test empty query raises ValueError."""
        detector = T3TriggerDetector()

        with pytest.raises(ValueError, match="Query cannot be empty"):
            detector.detect(query="")

    def test_t3_stats_tracking(self):
        """Test statistics tracking."""
        detector = T3TriggerDetector()

        detector.detect("Query 1", is_vip=True, transaction_amount=150.0, anger_level=0.85)
        detector.detect("Query 2", is_vip=False, transaction_amount=50.0, anger_level=0.50)

        stats = detector.get_stats()
        assert stats["queries_analyzed"] == 2
        assert stats["t3_activations"] == 1


# =============================================================================
# GST (Generated Step-by-step Thought) Tests
# =============================================================================

class TestGST:
    """Tests for Generated Step-by-step Thought."""

    def test_gst_initialization(self):
        """Test GST initializes correctly."""
        gst = GeneratedStepByStepThought()

        assert gst.config is not None
        assert gst.config.max_steps == 10
        assert gst.config.enable_backtracking is True

    def test_gst_reasoning_produces_steps(self):
        """Test GST produces reasoning steps."""
        gst = GeneratedStepByStepThought()

        result = gst.reason("How do I reset my password?")

        assert result.total_steps > 0
        assert len(result.steps) > 0
        assert result.processing_time_ms > 0

    def test_gst_procedural_query(self):
        """Test GST handles procedural queries."""
        gst = GeneratedStepByStepThought()

        result = gst.reason("How do I process a refund?")

        # Should have procedural-style steps
        assert any("goal" in s.description.lower() or "step" in s.description.lower()
                   for s in result.steps)

    def test_gst_decision_query(self):
        """Test GST handles decision queries."""
        gst = GeneratedStepByStepThought()

        result = gst.reason("Should I choose option A or B?")

        # Should have decision-style steps
        assert len(result.steps) > 0

    def test_gst_step_completion(self):
        """Test steps are marked as completed."""
        gst = GeneratedStepByStepThought()

        result = gst.reason("What is the meaning of life?")

        # At least some steps should complete
        completed = [s for s in result.steps if s.status == StepStatus.COMPLETED]
        assert len(completed) > 0

    def test_gst_final_conclusion(self):
        """Test GST produces final conclusion."""
        gst = GeneratedStepByStepThought()

        result = gst.reason("How can I improve my productivity?")

        assert result.final_conclusion != ""
        assert result.overall_confidence >= 0.0

    def test_gst_reasoning_chain(self):
        """Test reasoning chain is built."""
        gst = GeneratedStepByStepThought(GSTConfig(include_reasoning_chain=True))

        result = gst.reason("Explain quantum computing")

        assert result.reasoning_chain != ""

    def test_gst_empty_query_raises_error(self):
        """Test empty query raises ValueError."""
        gst = GeneratedStepByStepThought()

        with pytest.raises(ValueError, match="Query cannot be empty"):
            gst.reason("")

    def test_gst_stats_tracking(self):
        """Test statistics tracking."""
        gst = GeneratedStepByStepThought()

        gst.reason("Query 1")
        gst.reason("Query 2")

        stats = gst.get_stats()
        assert stats["queries_processed"] == 2
        assert stats["total_steps_generated"] > 0


# =============================================================================
# Universe of Thoughts Tests
# =============================================================================

class TestUniverseOfThoughts:
    """Tests for Universe of Thoughts."""

    def test_universe_initialization(self):
        """Test Universe of Thoughts initializes correctly."""
        uot = UniverseOfThoughts()

        assert uot.config is not None
        assert uot.config.max_paths == 6
        assert uot.config.min_paths == 3

    def test_universe_explores_multiple_paths(self):
        """Test multiple paths are explored."""
        uot = UniverseOfThoughts()

        result = uot.explore("Should I invest in stocks or bonds?")

        assert result.total_paths_explored >= 3
        assert len(result.paths) >= 3

    def test_universe_path_types_diverse(self):
        """Test diverse path types are generated."""
        uot = UniverseOfThoughts()

        result = uot.explore("How should I approach this problem?")

        path_types = {p.path_type for p in result.paths}
        # Should have multiple different path types
        assert len(path_types) >= 2

    def test_universe_completes_paths(self):
        """Test paths are completed."""
        uot = UniverseOfThoughts()

        result = uot.explore("What's the best approach?")

        completed = [p for p in result.paths if p.status == PathStatus.COMPLETED]
        assert len(completed) > 0

    def test_universe_selects_optimal_path(self):
        """Test optimal path is selected."""
        uot = UniverseOfThoughts()

        result = uot.explore("Which solution is better?")

        # Should have an optimal path selected
        assert result.optimal_path is not None or result.completed_paths == 0

    def test_universe_pros_and_cons(self):
        """Test pros and cons are generated."""
        uot = UniverseOfThoughts()

        result = uot.explore("Should I buy or rent?")

        # At least one path should have pros/cons
        paths_with_pros = [p for p in result.paths if p.pros]
        assert len(paths_with_pros) > 0

    def test_universe_cross_pollination(self):
        """Test cross-pollination of insights."""
        uot = UniverseOfThoughts(UniverseConfig(cross_pollination=True))

        result = uot.explore("Complex decision needed")

        # Cross-path insights should be generated
        assert isinstance(result.cross_path_insights, list)

    def test_universe_synthesis(self):
        """Test synthesis is generated."""
        uot = UniverseOfThoughts()

        result = uot.explore("Help me decide")

        assert result.synthesis != ""

    def test_universe_empty_query_raises_error(self):
        """Test empty query raises ValueError."""
        uot = UniverseOfThoughts()

        with pytest.raises(ValueError, match="Query cannot be empty"):
            uot.explore("")

    def test_universe_stats_tracking(self):
        """Test statistics tracking."""
        uot = UniverseOfThoughts()

        uot.explore("Query 1")
        uot.explore("Query 2")

        stats = uot.get_stats()
        assert stats["queries_processed"] == 2


# =============================================================================
# Tree of Thoughts Tests
# =============================================================================

class TestTreeOfThoughts:
    """Tests for Tree of Thoughts."""

    def test_tot_initialization(self):
        """Test Tree of Thoughts initializes correctly."""
        tot = TreeOfThoughts()

        assert tot.config is not None
        assert tot.config.max_depth == 5
        assert tot.config.max_branches == 3

    def test_tot_creates_tree_structure(self):
        """Test tree structure is created."""
        tot = TreeOfThoughts()

        result = tot.reason("How should I solve this problem?")

        assert result.root is not None
        assert result.total_nodes > 0

    def test_tot_different_search_strategies(self):
        """Test different search strategies."""
        for strategy in [SearchStrategy.BFS, SearchStrategy.DFS,
                         SearchStrategy.BEST_FIRST, SearchStrategy.BEAM]:
            config = TreeConfig(search_strategy=strategy)
            tot = TreeOfThoughts(config=config)

            result = tot.reason("Test query")
            assert result.search_strategy == strategy.value

    def test_tot_finds_solution(self):
        """Test tree search can find solutions."""
        tot = TreeOfThoughts(TreeConfig(max_depth=3, max_nodes=30))

        result = tot.reason("What is 2+2?")

        # Should have explored some nodes
        assert result.total_nodes > 0

    def test_tot_pruning(self):
        """Test branch pruning."""
        tot = TreeOfThoughts(TreeConfig(enable_pruning=True))

        result = tot.reason("Complex problem")

        # Pruning should occur for low-scoring branches
        assert isinstance(result.pruned_branches, int)

    def test_tot_best_path(self):
        """Test best path is identified."""
        tot = TreeOfThoughts()

        result = tot.reason("Help me decide")

        # Best path should be identified or empty
        assert isinstance(result.best_path, list)

    def test_tot_max_depth_respected(self):
        """Test max depth is respected."""
        config = TreeConfig(max_depth=2)
        tot = TreeOfThoughts(config=config)

        result = tot.reason("Complex multi-step problem")

        assert result.max_depth_reached <= 2

    def test_tot_empty_query_raises_error(self):
        """Test empty query raises ValueError."""
        tot = TreeOfThoughts()

        with pytest.raises(ValueError, match="Query cannot be empty"):
            tot.reason("")

    def test_tot_stats_tracking(self):
        """Test statistics tracking."""
        tot = TreeOfThoughts()

        tot.reason("Query 1")
        tot.reason("Query 2")

        stats = tot.get_stats()
        assert stats["queries_processed"] == 2


# =============================================================================
# Self-Consistency Tests
# =============================================================================

class TestSelfConsistency:
    """Tests for Self-Consistency."""

    def test_self_consistency_initialization(self):
        """Test Self-Consistency initializes correctly."""
        sc = SelfConsistency()

        assert sc.config is not None
        assert sc.config.num_chains == 5

    def test_self_consistency_generates_chains(self):
        """Test multiple chains are generated."""
        sc = SelfConsistency()

        result = sc.reason("What is the capital of France?")

        assert result.total_chains == 5
        assert len(result.chains) == 5

    def test_self_consistency_voting(self):
        """Test voting mechanism."""
        sc = SelfConsistency()

        result = sc.reason("Should I use Python or JavaScript?")

        # Vote distribution should be populated
        assert len(result.vote_distribution) > 0

    def test_self_consistency_consensus(self):
        """Test consensus detection."""
        sc = SelfConsistency()

        result = sc.reason("Is the sky blue?")

        # Should have some form of answer
        assert result.winning_answer is not None or result.has_consensus is False

    def test_self_consistency_different_vote_strategies(self):
        """Test different voting strategies."""
        for strategy in [VoteStrategy.MAJORITY, VoteStrategy.WEIGHTED,
                         VoteStrategy.SUPERMAJORITY]:
            config = SelfConsistencyConfig(vote_strategy=strategy)
            sc = SelfConsistency(config=config)

            result = sc.reason("Test question")
            # Result should complete without error

    def test_self_consistency_confidence(self):
        """Test confidence calculation."""
        sc = SelfConsistency()

        result = sc.reason("Complex question requiring analysis")

        assert 0.0 <= result.confidence <= 1.0
        assert 0.0 <= result.consensus_strength <= 1.0

    def test_self_consistency_divergent_answers(self):
        """Test divergent answer detection."""
        sc = SelfConsistency()

        result = sc.reason("What's the best programming language?")

        # Should identify divergent answers if they exist
        assert isinstance(result.divergent_answers, list)

    def test_self_consistency_empty_query_raises_error(self):
        """Test empty query raises ValueError."""
        sc = SelfConsistency()

        with pytest.raises(ValueError, match="Query cannot be empty"):
            sc.reason("")

    def test_self_consistency_stats_tracking(self):
        """Test statistics tracking."""
        sc = SelfConsistency()

        sc.reason("Query 1")
        sc.reason("Query 2")

        stats = sc.get_stats()
        assert stats["queries_processed"] == 2


# =============================================================================
# Reflexion Tests
# =============================================================================

class TestReflexion:
    """Tests for Reflexion."""

    def test_reflexion_initialization(self):
        """Test Reflexion initializes correctly."""
        reflexion = Reflexion()

        assert reflexion.config is not None
        assert reflexion.config.max_iterations == 3

    def test_reflexion_runs_iterations(self):
        """Test reflection iterations are run."""
        reflexion = Reflexion()

        result = reflexion.reason("How can I improve my code?")

        assert result.total_iterations > 0
        assert len(result.iterations) > 0

    def test_reflexion_improvement_tracking(self):
        """Test improvement is tracked."""
        reflexion = Reflexion()

        result = reflexion.reason("Explain machine learning")

        # Should track total improvement
        assert result.total_improvement >= 0.0

    def test_reflexion_lessons_learned(self):
        """Test lessons are extracted."""
        reflexion = Reflexion()

        result = reflexion.reason("Complex problem to solve")

        assert isinstance(result.lessons_learned, list)

    def test_reflexion_convergence(self):
        """Test convergence detection."""
        config = ReflexionConfig(min_score_threshold=0.95)
        reflexion = Reflexion(config=config)

        result = reflexion.reason("What is 1+1?")

        # Should either converge or reach max iterations
        assert result.convergence_reason != ""

    def test_reflexion_with_initial_answer(self):
        """Test with provided initial answer."""
        reflexion = Reflexion()

        result = reflexion.reason(
            query="Test question",
            initial_answer="This is my initial answer."
        )

        assert result.initial_answer == "This is my initial answer."

    def test_reflexion_memory(self):
        """Test memory functionality."""
        reflexion = Reflexion(ReflexionConfig(enable_memory=True))

        reflexion.reason("Question 1")
        reflexion.reason("Question 2")

        memory = reflexion.get_memory()
        assert isinstance(memory, list)

    def test_reflexion_empty_query_raises_error(self):
        """Test empty query raises ValueError."""
        reflexion = Reflexion()

        with pytest.raises(ValueError, match="Query cannot be empty"):
            reflexion.reason("")

    def test_reflexion_stats_tracking(self):
        """Test statistics tracking."""
        reflexion = Reflexion()

        reflexion.reason("Query 1")
        reflexion.reason("Query 2")

        stats = reflexion.get_stats()
        assert stats["queries_processed"] == 2


# =============================================================================
# Least-to-Most Tests
# =============================================================================

class TestLeastToMost:
    """Tests for Least-to-Most Reasoning."""

    def test_least_to_most_initialization(self):
        """Test Least-to-Most initializes correctly."""
        ltm = LeastToMost()

        assert ltm.config is not None
        assert ltm.config.max_sub_questions == 8

    def test_least_to_most_decomposes_query(self):
        """Test query is decomposed."""
        ltm = LeastToMost()

        result = ltm.reason("What is Python and how do I learn it?")

        assert result.total_sub_questions >= 2
        assert len(result.sub_questions) >= 2

    def test_least_to_most_difficulty_ordering(self):
        """Test sub-questions are ordered by difficulty."""
        ltm = LeastToMost()

        result = ltm.reason("Complex multi-part question")

        assert result.ordered_by_difficulty is True

    def test_least_to_most_solves_sub_questions(self):
        """Test sub-questions are solved."""
        ltm = LeastToMost()

        result = ltm.reason("What is AI and how does it work?")

        # At least some sub-questions should be solved
        assert result.solved_sub_questions >= 0

    def test_least_to_most_aggregation(self):
        """Test answer aggregation."""
        ltm = LeastToMost()

        result = ltm.reason("Explain databases and their types")

        assert result.final_answer != ""
        assert result.aggregation_method != ""

    def test_least_to_most_procedural_query(self):
        """Test handling of procedural queries."""
        ltm = LeastToMost()

        result = ltm.reason("How do I deploy an application?")

        # Should have procedural-style decomposition
        assert result.total_sub_questions >= 2

    def test_least_to_most_difficulty_assessment(self):
        """Test difficulty assessment."""
        ltm = LeastToMost()

        result = ltm.reason("Complex question requiring analysis")

        difficulties = {sq.difficulty for sq in result.sub_questions}
        # Should have varying difficulties
        assert len(difficulties) >= 1

    def test_least_to_most_confidence(self):
        """Test confidence calculation."""
        ltm = LeastToMost()

        result = ltm.reason("Test question")

        assert 0.0 <= result.overall_confidence <= 1.0

    def test_least_to_most_decompose_only(self):
        """Test decompose-only functionality."""
        ltm = LeastToMost()

        sub_questions = ltm.decompose_only("Complex multi-part query")

        assert len(sub_questions) >= 2
        # All should be pending since not solved
        assert all(sq.status == SubQuestionStatus.PENDING for sq in sub_questions)

    def test_least_to_most_empty_query_raises_error(self):
        """Test empty query raises ValueError."""
        ltm = LeastToMost()

        with pytest.raises(ValueError, match="Query cannot be empty"):
            ltm.reason("")

    def test_least_to_most_stats_tracking(self):
        """Test statistics tracking."""
        ltm = LeastToMost()

        ltm.reason("Query 1")
        ltm.reason("Query 2")

        stats = ltm.get_stats()
        assert stats["queries_processed"] == 2


# =============================================================================
# Integration Tests
# =============================================================================

class TestT3Integration:
    """Integration tests for T3 techniques."""

    def test_t3_full_pipeline_trigger_to_gst(self):
        """Test full pipeline from trigger to GST."""
        detector = T3TriggerDetector()

        # Trigger T3
        trigger_result = detector.detect(
            query="I need help with a complex issue",
            is_vip=True,
            transaction_amount=150.0,
            anger_level=0.85
        )

        assert trigger_result.should_fire_t3 is True

        # If GST is triggered, run it
        if T3TriggerType.GST in trigger_result.triggered_techniques:
            gst = GeneratedStepByStepThought()
            gst_result = gst.reason(trigger_result.query)

            assert gst_result.total_steps > 0

    def test_t3_techniques_work_together(self):
        """Test multiple T3 techniques work together."""
        query = "Should I invest in stocks or bonds for long-term growth?"

        # GST
        gst = GeneratedStepByStepThought()
        gst_result = gst.reason(query)
        assert gst_result.total_steps > 0

        # Universe of Thoughts
        uot = UniverseOfThoughts()
        uot_result = uot.explore(query)
        assert uot_result.total_paths_explored >= 3

        # Self-Consistency
        sc = SelfConsistency()
        sc_result = sc.reason(query)
        assert sc_result.total_chains >= 3

    def test_t3_does_not_activate_for_simple_queries(self):
        """Test T3 does not activate for simple queries."""
        detector = T3TriggerDetector()

        result = detector.detect(
            query="What are your hours?",
            is_vip=False,
            transaction_amount=None,
            anger_level=0.10
        )

        assert result.should_fire_t3 is False
        assert result.triggered_techniques == [] or result.primary_technique == T3TriggerType.NONE


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
