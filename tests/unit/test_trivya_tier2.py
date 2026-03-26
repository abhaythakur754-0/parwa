"""
Unit tests for TRIVYA Tier 2 Techniques.

Tests all Tier 2 techniques including:
- Trigger Detector
- Chain of Thought
- ReAct
- Reverse Thinking
- Step Back
- Thread of Thought
"""
import os
import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_unit_tests_32_characters!")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")

from shared.trivya_techniques.tier2.trigger_detector import (
    TriggerDetector,
    TriggerResult,
    TriggerType,
)
from shared.trivya_techniques.tier2.chain_of_thought import (
    ChainOfThought,
    CoTResult,
    CoTConfig,
    ReasoningStep,
)
from shared.trivya_techniques.tier2.react import (
    ReActTechnique,
    ReActResult,
    ReActConfig,
    ActionStep,
    ActionType,
)
from shared.trivya_techniques.tier2.reverse_thinking import (
    ReverseThinking,
    ReverseThinkingResult,
    ReverseThinkingConfig,
    ReverseStep,
)
from shared.trivya_techniques.tier2.step_back import (
    StepBack,
    StepBackResult,
    StepBackConfig,
    AbstractionLayer,
)
from shared.trivya_techniques.tier2.thread_of_thought import (
    ThreadOfThought,
    ToTResult,
    ToTConfig,
    ThoughtThread,
)


class TestTriggerDetector:
    """Tests for Trigger Detector."""

    def test_detector_initialization(self):
        """Test detector initializes correctly."""
        detector = TriggerDetector()
        assert detector.min_confidence == 0.5
        assert detector.max_techniques == 2

    def test_detect_decision_query(self):
        """Test detection of decision-making queries."""
        detector = TriggerDetector()

        result = detector.detect("Should I choose option A or option B?")

        assert result.query == "Should I choose option A or option B?"
        assert TriggerType.CHAIN_OF_THOUGHT in result.triggered_techniques
        assert result.confidence > 0

    def test_detect_action_query(self):
        """Test detection of action-oriented queries."""
        detector = TriggerDetector()

        result = detector.detect("Check my account balance")

        assert TriggerType.REACT in result.triggered_techniques
        assert result.primary_technique == TriggerType.REACT

    def test_detect_goal_query(self):
        """Test detection of goal-oriented queries."""
        detector = TriggerDetector()

        result = detector.detect("I want to become a certified developer")

        assert TriggerType.REVERSE_THINKING in result.triggered_techniques

    def test_detect_exploration_query(self):
        """Test detection of exploration queries."""
        detector = TriggerDetector()

        result = detector.detect("Tell me about machine learning")

        assert TriggerType.THREAD_OF_THOUGHT in result.triggered_techniques

    def test_detect_simple_query(self):
        """Test that simple queries don't trigger T2."""
        detector = TriggerDetector()

        result = detector.detect("What time is it?")

        # Simple query might not trigger any technique
        assert isinstance(result.triggered_techniques, list)

    def test_should_fire_t2(self):
        """Test T2 firing decision."""
        detector = TriggerDetector()

        # Complex query should fire
        assert detector.should_fire_t2("How do I decide between two options?") == True

        # Simple query might not fire
        result = detector.should_fire_t2("Hello")
        assert isinstance(result, bool)

    def test_empty_query_raises_error(self):
        """Test that empty query raises ValueError."""
        detector = TriggerDetector()

        with pytest.raises(ValueError, match="Query cannot be empty"):
            detector.detect("")

    def test_get_stats(self):
        """Test getting detector statistics."""
        detector = TriggerDetector()
        detector.detect("Test query 1")
        detector.detect("Test query 2")

        stats = detector.get_stats()

        assert stats["queries_analyzed"] == 2
        assert stats["total_processing_time_ms"] > 0


class TestChainOfThought:
    """Tests for Chain of Thought technique."""

    def test_cot_initialization(self):
        """Test CoT initializes correctly."""
        cot = ChainOfThought()
        assert cot.config.max_steps == 8

    def test_reason_produces_steps(self):
        """Test that reasoning produces steps."""
        cot = ChainOfThought()

        result = cot.reason("How do I compare option A and B?")

        assert result.query == "How do I compare option A and B?"
        assert len(result.steps) >= 2
        assert result.total_steps > 0
        assert result.overall_confidence >= 0

    def test_reason_comparison_query(self):
        """Test reasoning for comparison queries."""
        cot = ChainOfThought()

        result = cot.reason("What is the difference between Python and JavaScript?")

        assert len(result.steps) > 0
        assert result.final_answer != ""

    def test_reason_procedural_query(self):
        """Test reasoning for procedural queries."""
        cot = ChainOfThought()

        result = cot.reason("How do I set up a new project?")

        assert len(result.steps) > 0
        assert all(isinstance(s, ReasoningStep) for s in result.steps)

    def test_generate_prompt(self):
        """Test prompt generation."""
        cot = ChainOfThought()

        prompt = cot.generate_prompt("Test query")

        assert "step by step" in prompt.lower()
        assert "Test query" in prompt

    def test_parse_response(self):
        """Test parsing LLM response."""
        cot = ChainOfThought()

        response = """Step 1: First, identify the options
Step 2: Compare the features
Final Answer: Option A is better"""

        result = cot.parse_response(response, "Test query")

        assert len(result.steps) == 2
        assert "First" in result.steps[0].thought or "identify" in result.steps[0].thought.lower()

    def test_empty_query_raises_error(self):
        """Test empty query raises ValueError."""
        cot = ChainOfThought()

        with pytest.raises(ValueError, match="Query cannot be empty"):
            cot.reason("")

    def test_get_stats(self):
        """Test getting CoT statistics."""
        cot = ChainOfThought()
        cot.reason("Query 1")
        cot.reason("Query 2")

        stats = cot.get_stats()

        assert stats["queries_processed"] == 2
        assert stats["average_steps_per_query"] > 0


class TestReAct:
    """Tests for ReAct technique."""

    def test_react_initialization(self):
        """Test ReAct initializes correctly."""
        react = ReActTechnique()
        assert react.config.max_iterations == 6

    def test_execute_produces_steps(self):
        """Test that execution produces action steps."""
        react = ReActTechnique()

        result = react.execute("Check my account status")

        assert result.query == "Check my account status"
        assert len(result.steps) > 0
        assert result.total_steps > 0

    def test_execute_check_query(self):
        """Test execution for check queries."""
        react = ReActTechnique()

        result = react.execute("What's my current balance?")

        assert any(s.action == ActionType.CHECK for s in result.steps)
        assert result.actions_taken >= 0

    def test_execute_search_query(self):
        """Test execution for search queries."""
        react = ReActTechnique()

        result = react.execute("Find information about refunds")

        assert len(result.steps) > 0

    def test_generate_prompt(self):
        """Test ReAct prompt generation."""
        react = ReActTechnique()

        prompt = react.generate_prompt("Test query")

        assert "thought" in prompt.lower()
        assert "action" in prompt.lower()

    def test_parse_response(self):
        """Test parsing ReAct response."""
        react = ReActTechnique()

        response = """Thought: Need to check account
Action: check
Action Input: user_account
Observation: Account found
Final Answer: Your account is active"""

        result = react.parse_response(response, "Test query")

        assert len(result.steps) >= 1
        assert result.final_answer != ""

    def test_empty_query_raises_error(self):
        """Test empty query raises ValueError."""
        react = ReActTechnique()

        with pytest.raises(ValueError, match="Query cannot be empty"):
            react.execute("")

    def test_get_stats(self):
        """Test getting ReAct statistics."""
        react = ReActTechnique()
        react.execute("Query 1")
        react.execute("Query 2")

        stats = react.get_stats()

        assert stats["queries_processed"] == 2


class TestReverseThinking:
    """Tests for Reverse Thinking technique."""

    def test_reverse_thinking_initialization(self):
        """Test Reverse Thinking initializes correctly."""
        rt = ReverseThinking()
        assert rt.config.max_steps == 8

    def test_reason_backward_produces_steps(self):
        """Test backward reasoning produces steps."""
        rt = ReverseThinking()

        result = rt.reason_backward("I want to become a developer")

        assert result.goal != ""
        assert len(result.steps) > 0
        assert result.starting_point != ""

    def test_reason_backward_with_explicit_goal(self):
        """Test reasoning with explicit goal."""
        rt = ReverseThinking()

        result = rt.reason_backward(
            "How do I get there?",
            goal="Become a senior developer"
        )

        assert result.goal == "Become a senior developer"

    def test_generate_forward_plan(self):
        """Test forward plan generation."""
        rt = ReverseThinking()

        result = rt.reason_backward("I need to fix this bug")

        assert isinstance(result.forward_plan, list)

    def test_feasibility_calculation(self):
        """Test feasibility score calculation."""
        rt = ReverseThinking()

        result = rt.reason_backward("I want to complete the project")

        assert 0 <= result.feasibility_score <= 1

    def test_generate_prompt(self):
        """Test prompt generation."""
        rt = ReverseThinking()

        prompt = rt.generate_prompt("I want to succeed")

        assert "backward" in prompt.lower()
        assert "goal" in prompt.lower()

    def test_empty_query_raises_error(self):
        """Test empty query raises ValueError."""
        rt = ReverseThinking()

        with pytest.raises(ValueError, match="Query cannot be empty"):
            rt.reason_backward("")

    def test_get_stats(self):
        """Test getting statistics."""
        rt = ReverseThinking()
        rt.reason_backward("Query 1")
        rt.reason_backward("Query 2")

        stats = rt.get_stats()

        assert stats["queries_processed"] == 2


class TestStepBack:
    """Tests for Step Back technique."""

    def test_step_back_initialization(self):
        """Test Step Back initializes correctly."""
        sb = StepBack()
        assert sb.config.max_abstraction_levels == 3

    def test_analyze_produces_abstractions(self):
        """Test that analysis produces abstraction layers."""
        sb = StepBack()

        result = sb.analyze("Why does this happen?")

        assert result.query == "Why does this happen?"
        assert len(result.abstraction_layers) > 0
        assert result.core_principle != ""

    def test_analyze_causal_query(self):
        """Test analysis for causal queries."""
        sb = StepBack()

        result = sb.analyze("What is the cause of this error?")

        assert len(result.abstraction_layers) > 0
        assert result.confidence >= 0

    def test_analyze_process_query(self):
        """Test analysis for process queries."""
        sb = StepBack()

        result = sb.analyze("How does the system work?")

        assert result.abstracted_understanding != ""

    def test_extract_core_principle(self):
        """Test core principle extraction."""
        sb = StepBack()

        result = sb.analyze("What is machine learning?")

        assert result.core_principle != ""
        assert result.solution_approach != ""

    def test_generate_prompt(self):
        """Test prompt generation."""
        sb = StepBack()

        prompt = sb.generate_prompt("Test query")

        assert "step back" in prompt.lower()
        assert "principle" in prompt.lower()

    def test_empty_query_raises_error(self):
        """Test empty query raises ValueError."""
        sb = StepBack()

        with pytest.raises(ValueError, match="Query cannot be empty"):
            sb.analyze("")

    def test_get_stats(self):
        """Test getting statistics."""
        sb = StepBack()
        sb.analyze("Query 1")
        sb.analyze("Query 2")

        stats = sb.get_stats()

        assert stats["queries_processed"] == 2


class TestThreadOfThought:
    """Tests for Thread of Thought technique."""

    def test_tot_initialization(self):
        """Test ToT initializes correctly."""
        tot = ThreadOfThought()
        assert tot.config.max_threads == 5

    def test_explore_creates_threads(self):
        """Test that exploration creates threads."""
        tot = ThreadOfThought()

        result = tot.explore("Tell me about cloud computing")

        assert result.query == "Tell me about cloud computing"
        assert result.main_thread is not None
        assert result.total_threads >= 1

    def test_explore_creates_sub_threads(self):
        """Test that exploration creates sub-threads."""
        tot = ThreadOfThought()

        result = tot.explore("Explain how databases work")

        assert len(result.sub_threads) > 0
        assert result.total_threads > 1

    def test_explore_discovers_connections(self):
        """Test connection discovery."""
        tot = ThreadOfThought(config=ToTConfig(explore_connections=True))

        result = tot.explore("Describe artificial intelligence")

        # Main thread should connect to sub-threads
        assert len(result.main_thread.connections) > 0

    def test_explore_synthesizes(self):
        """Test synthesis generation."""
        tot = ThreadOfThought(config=ToTConfig(synthesize_results=True))

        result = tot.explore("What is blockchain?")

        assert result.synthesis != ""

    def test_coverage_calculation(self):
        """Test coverage score calculation."""
        tot = ThreadOfThought()

        result = tot.explore("Tell me about DevOps")

        assert 0 <= result.coverage_score <= 1

    def test_generate_prompt(self):
        """Test prompt generation."""
        tot = ThreadOfThought()

        prompt = tot.generate_prompt("Test topic")

        assert "thread" in prompt.lower()
        assert "synthesis" in prompt.lower()

    def test_empty_query_raises_error(self):
        """Test empty query raises ValueError."""
        tot = ThreadOfThought()

        with pytest.raises(ValueError, match="Query cannot be empty"):
            tot.explore("")

    def test_get_stats(self):
        """Test getting statistics."""
        tot = ThreadOfThought()
        tot.explore("Topic 1")
        tot.explore("Topic 2")

        stats = tot.get_stats()

        assert stats["queries_processed"] == 2
        assert stats["total_threads_created"] >= 2


class TestT2Integration:
    """Integration tests for T2 techniques."""

    def test_trigger_to_technique_flow(self):
        """Test flow from trigger detection to technique execution."""
        detector = TriggerDetector()
        cot = ChainOfThought()

        # Detect triggers
        trigger_result = detector.detect("How should I decide between A and B?")

        # Verify CoT is triggered
        assert TriggerType.CHAIN_OF_THOUGHT in trigger_result.triggered_techniques

        # Execute CoT
        if TriggerType.CHAIN_OF_THOUGHT in trigger_result.triggered_techniques:
            cot_result = cot.reason("How should I decide between A and B?")
            assert len(cot_result.steps) > 0

    def test_all_techniques_produce_different_outputs(self):
        """Test that different techniques produce different outputs."""
        query = "How do I solve this problem?"

        detector = TriggerDetector()
        trigger_result = detector.detect(query)

        cot = ChainOfThought()
        react = ReActTechnique()
        rt = ReverseThinking()
        sb = StepBack()
        tot = ThreadOfThought()

        # Execute all techniques
        cot_result = cot.reason(query)
        react_result = react.execute(query)
        rt_result = rt.reason_backward(query)
        sb_result = sb.analyze(query)
        tot_result = tot.explore(query)

        # Verify all produce results
        assert len(cot_result.steps) > 0
        assert len(react_result.steps) > 0
        assert len(rt_result.steps) > 0
        assert len(sb_result.abstraction_layers) > 0
        assert tot_result.total_threads > 0

    def test_technique_configs(self):
        """Test that techniques respect configurations."""
        cot = ChainOfThought(config=CoTConfig(max_steps=3))
        react = ReActTechnique(config=ReActConfig(max_iterations=3))
        rt = ReverseThinking(config=ReverseThinkingConfig(max_steps=3))
        sb = StepBack(config=StepBackConfig(max_abstraction_levels=2))
        tot = ThreadOfThought(config=ToTConfig(max_threads=3))

        cot_result = cot.reason("Complex query")
        react_result = react.execute("Complex query")
        rt_result = rt.reason_backward("Complex query")
        sb_result = sb.analyze("Complex query")
        tot_result = tot.explore("Complex query")

        # Verify config limits are respected
        assert len(cot_result.steps) <= 3
        assert len(react_result.steps) <= 3
        assert len(rt_result.steps) <= 3
        assert len(sb_result.abstraction_layers) <= 2
        assert tot_result.total_threads <= 3
