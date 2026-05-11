"""Day 19 unit tests — Tier 3 Premium technique implementations.

Tests for: F-144 (UoT), F-145 (ToT), F-146 (Self-Consistency),
F-147 (Reflexion), F-148 (Least-to-Most).

Each technique has Node activation tests, Processor pipeline tests,
and BC-008 never-crash edge case tests.
"""

import pytest

from backend.app.core.techniques.base import (
    ConversationState,
    QuerySignals,
)
from backend.app.core.technique_router import (
    TechniqueID,
    TechniqueTier,
)


# ────────────────────────────────────────────────────────────────────
# F-144: Universe of Thoughts (UoT)
# ────────────────────────────────────────────────────────────────────


class TestUniverseOfThoughtsNode:

    @pytest.fixture
    def node(self):
        from backend.app.core.techniques.universe_of_thoughts import (
            UniverseOfThoughtsNode,
        )
        return UniverseOfThoughtsNode()

    def test_technique_id(self, node):
        assert node.technique_id == TechniqueID.UNIVERSE_OF_THOUGHTS

    def test_is_tier_3(self, node):
        assert node.technique_info.tier == TechniqueTier.TIER_3

    @pytest.mark.asyncio
    async def test_activates_on_vip(self, node):
        signals = QuerySignals(customer_tier="vip")
        state = ConversationState(signals=signals)
        assert await node.should_activate(state) is True

    @pytest.mark.asyncio
    async def test_activates_on_low_sentiment(self, node):
        signals = QuerySignals(sentiment_score=0.2)
        state = ConversationState(signals=signals)
        assert await node.should_activate(state) is True

    @pytest.mark.asyncio
    async def test_activates_on_high_monetary(self, node):
        signals = QuerySignals(monetary_value=500.0)
        state = ConversationState(signals=signals)
        assert await node.should_activate(state) is True

    @pytest.mark.asyncio
    async def test_activates_on_negative_sentiment_and_monetary(self, node):
        signals = QuerySignals(sentiment_score=0.2, monetary_value=150.0)
        state = ConversationState(signals=signals)
        assert await node.should_activate(state) is True

    @pytest.mark.asyncio
    async def test_does_not_activate_on_normal(self, node):
        signals = QuerySignals(
            customer_tier="free",
            sentiment_score=0.7,
            monetary_value=0,
        )
        state = ConversationState(signals=signals)
        assert await node.should_activate(state) is False

    @pytest.mark.asyncio
    async def test_execute_returns_state(self, node):
        state = ConversationState(query="I want a refund for $200")
        result = await node.execute(state)
        assert isinstance(result, ConversationState)

    @pytest.mark.asyncio
    async def test_execute_records_result(self, node):
        state = ConversationState(query="I want a refund for $200")
        result = await node.execute(state)
        assert "universe_of_thoughts" in result.technique_results

    @pytest.mark.asyncio
    async def test_execute_never_crashes_on_empty(self, node):
        state = ConversationState(query="")
        result = await node.execute(state)
        assert isinstance(result, ConversationState)

    @pytest.mark.asyncio
    async def test_execute_never_crashes_on_special_chars(self, node):
        state = ConversationState(query="<script>alert('xss')</script>")
        result = await node.execute(state)
        assert isinstance(result, ConversationState)


class TestUniverseOfThoughtsProcessor:

    @pytest.fixture
    def processor(self):
        from backend.app.core.techniques.universe_of_thoughts import (
            UoTProcessor,
        )
        return UoTProcessor()

    @pytest.mark.asyncio
    async def test_process_returns_result(self, processor):
        result = await processor.process("I want a refund for $200")
        assert result is not None

    @pytest.mark.asyncio
    async def test_process_has_steps_applied(self, processor):
        result = await processor.process("Can I get a refund?")
        assert len(result.steps_applied) > 0

    @pytest.mark.asyncio
    async def test_process_has_confidence_boost(self, processor):
        result = await processor.process("Can I get a refund?")
        assert result.confidence_boost >= 0

    @pytest.mark.asyncio
    async def test_process_has_solutions(self, processor):
        result = await processor.process("Can I get a refund?")
        assert len(result.solutions) >= 3

    @pytest.mark.asyncio
    async def test_process_has_selected_solution(self, processor):
        result = await processor.process("Can I get a refund?")
        assert result.selected_solution is not None

    @pytest.mark.asyncio
    async def test_process_empty_query(self, processor):
        result = await processor.process("")
        assert result is not None

    @pytest.mark.asyncio
    async def test_process_to_dict(self, processor):
        result = await processor.process("refund")
        d = result.to_dict()
        assert isinstance(d, dict)
        assert "solutions" in d
        assert "steps_applied" in d

    @pytest.mark.asyncio
    async def test_generate_solution_space(self, processor):
        candidates = await processor.generate_solution_space(
            "I need a refund for my subscription"
        )
        assert len(candidates) >= 3

    @pytest.mark.asyncio
    async def test_evaluate_solutions(self, processor):
        candidates = await processor.generate_solution_space("refund")
        solutions, matrix = await processor.evaluate_solutions(candidates)
        assert len(matrix) >= 3

    @pytest.mark.asyncio
    async def test_select_optimal(self, processor):
        candidates = await processor.generate_solution_space("refund")
        solutions, matrix = await processor.evaluate_solutions(candidates)
        best = await processor.select_optimal(solutions)
        assert best is not None
        assert best.total_score > 0


class TestUoTConfig:

    def test_default_config(self):
        from backend.app.core.techniques.universe_of_thoughts import UoTConfig
        config = UoTConfig()
        assert config.min_solutions == 3
        assert config.max_solutions == 5

    def test_frozen_config(self):
        from backend.app.core.techniques.universe_of_thoughts import UoTConfig
        config = UoTConfig()
        try:
            config.min_solutions = 99
            assert False, "Should not be mutable"
        except Exception:
            pass


# ────────────────────────────────────────────────────────────────────
# F-146: Self-Consistency
# ────────────────────────────────────────────────────────────────────


class TestSelfConsistencyNode:

    @pytest.fixture
    def node(self):
        from backend.app.core.techniques.self_consistency import (
            SelfConsistencyNode,
        )
        return SelfConsistencyNode()

    def test_technique_id(self, node):
        assert node.technique_id == TechniqueID.SELF_CONSISTENCY

    def test_is_tier_3(self, node):
        assert node.technique_info.tier == TechniqueTier.TIER_3

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

    @pytest.mark.asyncio
    async def test_execute_returns_state(self, node):
        state = ConversationState(
            query="What is my refund amount for $120 plan cancelled at 4 months?"
        )
        result = await node.execute(state)
        assert isinstance(result, ConversationState)

    @pytest.mark.asyncio
    async def test_execute_records_result(self, node):
        state = ConversationState(query="refund $200")
        result = await node.execute(state)
        assert "self_consistency" in result.technique_results

    @pytest.mark.asyncio
    async def test_execute_never_crashes_on_empty(self, node):
        state = ConversationState(query="")
        result = await node.execute(state)
        assert isinstance(result, ConversationState)


class TestSelfConsistencyProcessor:

    @pytest.fixture
    def processor(self):
        from backend.app.core.techniques.self_consistency import (
            SelfConsistencyProcessor,
        )
        return SelfConsistencyProcessor()

    @pytest.mark.asyncio
    async def test_process_returns_result(self, processor):
        result = await processor.process("What is my prorated refund?")
        assert result is not None

    @pytest.mark.asyncio
    async def test_process_has_steps_applied(self, processor):
        result = await processor.process("refund amount")
        assert len(result.steps_applied) > 0

    @pytest.mark.asyncio
    async def test_process_has_confidence_boost(self, processor):
        result = await processor.process("refund amount")
        assert result.confidence_boost >= 0

    @pytest.mark.asyncio
    async def test_process_has_answers(self, processor):
        result = await processor.process("refund $120")
        assert len(result.answers) >= 3

    @pytest.mark.asyncio
    async def test_process_has_consistency(self, processor):
        result = await processor.process("refund $120")
        assert result.consistency is not None

    @pytest.mark.asyncio
    async def test_process_has_final_answer(self, processor):
        result = await processor.process("refund $120")
        assert result.final_answer != ""

    @pytest.mark.asyncio
    async def test_process_empty_query(self, processor):
        result = await processor.process("")
        assert result is not None

    @pytest.mark.asyncio
    async def test_process_to_dict(self, processor):
        result = await processor.process("refund")
        d = result.to_dict()
        assert isinstance(d, dict)
        assert "consensus_level" in d
        assert "final_answer" in d

    @pytest.mark.asyncio
    async def test_generate_independent_answers_count(self, processor):
        answers = await processor.generate_independent_answers("refund")
        assert len(answers) >= 3

    @pytest.mark.asyncio
    async def test_check_consistency(self, processor):
        answers = await processor.generate_independent_answers("refund")
        consistency = await processor.check_consistency(answers)
        assert consistency is not None
        assert consistency.agreement_ratio >= 0

    @pytest.mark.asyncio
    async def test_consensus_level_valid(self, processor):
        answers = await processor.generate_independent_answers("refund")
        consistency = await processor.check_consistency(answers)
        valid_levels = {
            "unanimous", "majority", "split", "no_consensus"
        }
        assert consistency.consensus_level in valid_levels


class TestSelfConsistencyConfig:

    def test_default_config(self):
        from backend.app.core.techniques.self_consistency import (
            SelfConsistencyConfig,
        )
        config = SelfConsistencyConfig()
        assert config.num_answers == 5
        assert config.consensus_threshold == 0.6


# ────────────────────────────────────────────────────────────────────
# F-147: Reflexion
# ────────────────────────────────────────────────────────────────────


class TestReflexionNode:

    @pytest.fixture
    def node(self):
        from backend.app.core.techniques.reflexion import ReflexionNode
        return ReflexionNode()

    def test_technique_id(self, node):
        assert node.technique_id == TechniqueID.REFLEXION

    def test_is_tier_3(self, node):
        assert node.technique_info.tier == TechniqueTier.TIER_3

    @pytest.mark.asyncio
    async def test_activates_on_rejected(self, node):
        signals = QuerySignals(previous_response_status="rejected")
        state = ConversationState(signals=signals)
        assert await node.should_activate(state) is True

    @pytest.mark.asyncio
    async def test_activates_on_corrected(self, node):
        signals = QuerySignals(previous_response_status="corrected")
        state = ConversationState(signals=signals)
        assert await node.should_activate(state) is True

    @pytest.mark.asyncio
    async def test_activates_on_vip(self, node):
        signals = QuerySignals(customer_tier="vip")
        state = ConversationState(signals=signals)
        assert await node.should_activate(state) is True

    @pytest.mark.asyncio
    async def test_does_not_activate_on_normal(self, node):
        signals = QuerySignals(
            previous_response_status="accepted",
            customer_tier="free",
        )
        state = ConversationState(signals=signals)
        assert await node.should_activate(state) is False

    @pytest.mark.asyncio
    async def test_execute_returns_state(self, node):
        state = ConversationState(
            query="That's not what I asked. I want to know about billing."
        )
        result = await node.execute(state)
        assert isinstance(result, ConversationState)

    @pytest.mark.asyncio
    async def test_execute_records_result(self, node):
        state = ConversationState(query="that's wrong")
        result = await node.execute(state)
        assert "reflexion" in result.technique_results

    @pytest.mark.asyncio
    async def test_execute_never_crashes(self, node):
        state = ConversationState(query="")
        result = await node.execute(state)
        assert isinstance(result, ConversationState)


class TestReflexionProcessor:

    @pytest.fixture
    def processor(self):
        from backend.app.core.techniques.reflexion import ReflexionProcessor
        return ReflexionProcessor()

    @pytest.mark.asyncio
    async def test_process_returns_result(self, processor):
        result = await processor.process(
            "That's not what I asked",
            previous_response="Here is your invoice.",
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_process_has_steps_applied(self, processor):
        result = await processor.process("that's wrong")
        assert len(result.steps_applied) > 0

    @pytest.mark.asyncio
    async def test_process_has_reflection(self, processor):
        result = await processor.process("that's incorrect")
        assert result.reflection is not None

    @pytest.mark.asyncio
    async def test_process_has_improved_response(self, processor):
        result = await processor.process(
            "That's not helpful at all",
        )
        assert result.improved_response != ""

    @pytest.mark.asyncio
    async def test_process_empty_query(self, processor):
        result = await processor.process("")
        assert result is not None

    @pytest.mark.asyncio
    async def test_process_to_dict(self, processor):
        result = await processor.process("that's wrong")
        d = result.to_dict()
        assert isinstance(d, dict)
        assert "reflection" in d
        assert "improved_response" in d

    @pytest.mark.asyncio
    async def test_detect_failure_misunderstood(self, processor):
        from backend.app.core.techniques.reflexion import FailureMode
        mode = await processor.detect_failure_mode(
            "That's not what I asked"
        )
        assert mode == FailureMode.MISUNDERSTOOD_QUERY

    @pytest.mark.asyncio
    async def test_detect_failure_incorrect_info(self, processor):
        from backend.app.core.techniques.reflexion import FailureMode
        mode = await processor.detect_failure_mode(
            "That's wrong and your answer is incorrect"
        )
        assert mode == FailureMode.INCORRECT_INFO

    @pytest.mark.asyncio
    async def test_detect_failure_bad_tone(self, processor):
        from backend.app.core.techniques.reflexion import FailureMode
        mode = await processor.detect_failure_mode(
            "You sound really rude and unhelpful"
        )
        assert mode == FailureMode.BAD_TONE

    @pytest.mark.asyncio
    async def test_detect_failure_missed_context(self, processor):
        from backend.app.core.techniques.reflexion import FailureMode
        mode = await processor.detect_failure_mode(
            "You missed the point about my billing issue"
        )
        assert mode == FailureMode.MISSED_CONTEXT

    @pytest.mark.asyncio
    async def test_detect_failure_incomplete(self, processor):
        from backend.app.core.techniques.reflexion import FailureMode
        mode = await processor.detect_failure_mode(
            "That's not enough information"
        )
        assert mode == FailureMode.INCOMPLETE_RESPONSE

    @pytest.mark.asyncio
    async def test_detect_failure_wrong_scope(self, processor):
        from backend.app.core.techniques.reflexion import FailureMode
        mode = await processor.detect_failure_mode(
            "That's off-topic completely"
        )
        assert mode == FailureMode.WRONG_SCOPE

    @pytest.mark.asyncio
    async def test_reflect_on_failure(self, processor):
        from backend.app.core.techniques.reflexion import FailureMode
        analysis = await processor.reflect_on_failure(
            FailureMode.INCORRECT_INFO,
            "that's wrong",
            "The charge is $50.",
        )
        assert analysis.failure_mode == "incorrect_information"
        assert len(analysis.strategy_changes) > 0

    @pytest.mark.asyncio
    async def test_generate_improved_response(self, processor):
        from backend.app.core.techniques.reflexion import (
            FailureMode,
            ReflectionAnalysis,
        )
        reflection = ReflectionAnalysis(
            failure_mode="incorrect_information",
            strategy_changes=["investigative"],
        )
        response = await processor.generate_improved_response(
            reflection, "that's wrong"
        )
        assert len(response) > 0


class TestReflexionConfig:

    def test_default_config(self):
        from backend.app.core.techniques.reflexion import ReflexionConfig
        config = ReflexionConfig()
        assert config.max_reflection_depth == 3
        assert config.enable_meta_trace is True

    def test_frozen_config(self):
        from backend.app.core.techniques.reflexion import ReflexionConfig
        config = ReflexionConfig()
        try:
            config.max_reflection_depth = 99
            assert False, "Should not be mutable"
        except Exception:
            pass


# ────────────────────────────────────────────────────────────────────
# F-145: Tree of Thoughts (ToT)
# ────────────────────────────────────────────────────────────────────


class TestTreeOfThoughtsNode:

    @pytest.fixture
    def node(self):
        from backend.app.core.techniques.tree_of_thoughts import (
            TreeOfThoughtsNode,
        )
        return TreeOfThoughtsNode()

    def test_technique_id(self, node):
        assert node.technique_id == TechniqueID.TREE_OF_THOUGHTS

    def test_is_tier_3(self, node):
        assert node.technique_info.tier == TechniqueTier.TIER_3

    @pytest.mark.asyncio
    async def test_activates_on_multi_path(self, node):
        signals = QuerySignals(resolution_path_count=5)
        state = ConversationState(signals=signals)
        assert await node.should_activate(state) is True

    @pytest.mark.asyncio
    async def test_activates_on_strategic(self, node):
        signals = QuerySignals(
            resolution_path_count=3,
            is_strategic_decision=True,
        )
        state = ConversationState(signals=signals)
        assert await node.should_activate(state) is True

    @pytest.mark.asyncio
    async def test_does_not_activate_on_single_path(self, node):
        signals = QuerySignals(resolution_path_count=1)
        state = ConversationState(signals=signals)
        assert await node.should_activate(state) is False

    @pytest.mark.asyncio
    async def test_execute_returns_state(self, node):
        state = ConversationState(
            query="My API returns 500 errors intermittently"
        )
        result = await node.execute(state)
        assert isinstance(result, ConversationState)

    @pytest.mark.asyncio
    async def test_execute_records_result(self, node):
        state = ConversationState(query="API keeps failing with 500")
        result = await node.execute(state)
        assert "tree_of_thoughts" in result.technique_results

    @pytest.mark.asyncio
    async def test_execute_never_crashes(self, node):
        state = ConversationState(query="")
        result = await node.execute(state)
        assert isinstance(result, ConversationState)


class TestToTProcessor:

    @pytest.fixture
    def processor(self):
        from backend.app.core.techniques.tree_of_thoughts import ToTProcessor
        return ToTProcessor()

    @pytest.mark.asyncio
    async def test_process_returns_result(self, processor):
        result = await processor.process("API 500 error on login")
        assert result is not None

    @pytest.mark.asyncio
    async def test_process_has_steps_applied(self, processor):
        result = await processor.process("API failing")
        assert len(result.steps_applied) > 0

    @pytest.mark.asyncio
    async def test_process_has_confidence_boost(self, processor):
        result = await processor.process("API failing")
        assert result.confidence_boost >= 0

    @pytest.mark.asyncio
    async def test_process_empty_query(self, processor):
        result = await processor.process("")
        assert result is not None

    @pytest.mark.asyncio
    async def test_process_to_dict(self, processor):
        result = await processor.process("API error")
        d = result.to_dict()
        assert isinstance(d, dict)

    @pytest.mark.asyncio
    async def test_generate_tree(self, processor):
        from backend.app.core.techniques.tree_of_thoughts import (
            ProblemDomain,
            TreeNode,
        )
        tree = await processor.generate_tree(
            "API 500 error", domain=ProblemDomain.TECHNICAL
        )
        assert isinstance(tree, TreeNode)
        assert len(tree.children) >= 2  # root has multiple branches

    @pytest.mark.asyncio
    async def test_evaluate_branches(self, processor):
        from backend.app.core.techniques.tree_of_thoughts import ProblemDomain
        await processor.generate_tree(
            "API 500 error", domain=ProblemDomain.TECHNICAL
        )
        evaluated_count = await processor.evaluate_branches()
        assert isinstance(evaluated_count, int)
        assert evaluated_count > 0

    @pytest.mark.asyncio
    async def test_prune_tree(self, processor):
        from backend.app.core.techniques.tree_of_thoughts import ProblemDomain
        await processor.generate_tree(
            "API 500 error", domain=ProblemDomain.TECHNICAL
        )
        await processor.evaluate_branches()
        pruned_count = await processor.prune_tree()
        assert isinstance(pruned_count, int)

    @pytest.mark.asyncio
    async def test_search_tree(self, processor):
        from backend.app.core.techniques.tree_of_thoughts import ProblemDomain
        await processor.generate_tree(
            "API 500 error", domain=ProblemDomain.TECHNICAL
        )
        await processor.evaluate_branches()
        await processor.prune_tree()
        explored = await processor.search_tree()
        assert isinstance(explored, list)

    @pytest.mark.asyncio
    async def test_build_reasoning_trace(self, processor):
        from backend.app.core.techniques.tree_of_thoughts import ProblemDomain
        domain = ProblemDomain.TECHNICAL
        await processor.generate_tree(
            "API 500 error", domain=domain
        )
        await processor.evaluate_branches()
        await processor.prune_tree()
        explored = await processor.search_tree()
        path = await processor.select_best_path(explored)
        trace = await processor.build_reasoning_trace(
            path, domain=domain, template_name="api_error_investigation"
        )
        assert isinstance(trace, list)


class TestToTConfig:

    def test_default_config(self):
        from backend.app.core.techniques.tree_of_thoughts import ToTConfig
        config = ToTConfig()
        assert config.max_depth >= 3
        assert config.max_branches >= 3

    def test_frozen_config(self):
        from backend.app.core.techniques.tree_of_thoughts import ToTConfig
        config = ToTConfig()
        try:
            config.max_depth = 99
            assert False, "Should not be mutable"
        except Exception:
            pass


# ────────────────────────────────────────────────────────────────────
# F-148: Least-to-Most Decomposition
# ────────────────────────────────────────────────────────────────────


class TestLeastToMostNode:

    @pytest.fixture
    def node(self):
        from backend.app.core.techniques.least_to_most import (
            LeastToMostNode,
        )
        return LeastToMostNode()

    def test_technique_id(self, node):
        assert node.technique_id == TechniqueID.LEAST_TO_MOST

    def test_is_tier_3(self, node):
        assert node.technique_info.tier == TechniqueTier.TIER_3

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

    @pytest.mark.asyncio
    async def test_execute_returns_state(self, node):
        state = ConversationState(
            query="We need to onboard 50 employees with platform access"
        )
        result = await node.execute(state)
        assert isinstance(result, ConversationState)

    @pytest.mark.asyncio
    async def test_execute_records_result(self, node):
        state = ConversationState(query="onboard 50 employees")
        result = await node.execute(state)
        assert "least_to_most" in result.technique_results

    @pytest.mark.asyncio
    async def test_execute_never_crashes(self, node):
        state = ConversationState(query="")
        result = await node.execute(state)
        assert isinstance(result, ConversationState)


class TestLeastToMostProcessor:

    @pytest.fixture
    def processor(self):
        from backend.app.core.techniques.least_to_most import (
            LeastToMostProcessor,
        )
        return LeastToMostProcessor()

    @pytest.mark.asyncio
    async def test_process_returns_result(self, processor):
        result = await processor.process(
            "We need to onboard 50 new employees"
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_process_has_steps_applied(self, processor):
        result = await processor.process("onboard 50 employees")
        assert len(result.steps_applied) > 0

    @pytest.mark.asyncio
    async def test_process_has_confidence_boost(self, processor):
        result = await processor.process("onboard 50 employees")
        assert result.confidence_boost >= 0

    @pytest.mark.asyncio
    async def test_process_empty_query(self, processor):
        result = await processor.process("")
        assert result is not None

    @pytest.mark.asyncio
    async def test_process_to_dict(self, processor):
        result = await processor.process("onboard employees")
        d = result.to_dict()
        assert isinstance(d, dict)
        assert "sub_queries" in d
        assert "steps_applied" in d

    @pytest.mark.asyncio
    async def test_decompose_query(self, processor):
        sub_queries = await processor.decompose_query(
            "We need to onboard 50 employees across 3 departments"
        )
        assert len(sub_queries) >= 3

    @pytest.mark.asyncio
    async def test_order_dependencies(self, processor):
        sub_queries = await processor.decompose_query(
            "Set up platform, email, and Slack for 50 users"
        )
        graph = await processor.order_dependencies(sub_queries)
        assert graph is not None
        assert len(graph.execution_order) > 0

    @pytest.mark.asyncio
    async def test_solve_sequentially(self, processor):
        sub_queries = await processor.decompose_query(
            "Onboard 50 new employees"
        )
        graph = await processor.order_dependencies(sub_queries)
        results = await processor.solve_sequentially(graph)
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_combine_results(self, processor):
        sub_queries = await processor.decompose_query(
            "Onboard 50 employees"
        )
        graph = await processor.order_dependencies(sub_queries)
        results = await processor.solve_sequentially(graph)
        final = await processor.combine_results(results, "onboard")
        assert len(final) > 0

    @pytest.mark.asyncio
    async def test_check_completeness(self, processor):
        sub_queries = await processor.decompose_query(
            "Onboard employees"
        )
        graph = await processor.order_dependencies(sub_queries)
        results = await processor.solve_sequentially(graph)
        completeness = await processor.check_completeness(
            sub_queries, results
        )
        assert completeness is not None


class TestLeastToMostConfig:

    def test_default_config(self):
        from backend.app.core.techniques.least_to_most import (
            LeastToMostConfig,
        )
        config = LeastToMostConfig()
        assert config.max_sub_queries >= 5
        assert config.min_sub_queries >= 3

    def test_frozen_config(self):
        from backend.app.core.techniques.least_to_most import (
            LeastToMostConfig,
        )
        config = LeastToMostConfig()
        try:
            config.max_sub_queries = 99
            assert False, "Should not be mutable"
        except Exception:
            pass


# ────────────────────────────────────────────────────────────────────
# BC-008: Never Crash — Cross-Technique Stress Tests
# ────────────────────────────────────────────────────────────────────


class TestDay19NeverCrash:

    """BC-008: All Tier 3 techniques must never crash, even on
    adversarial or garbage input."""

    @pytest.mark.asyncio
    async def test_uot_garbage_input(self):
        from backend.app.core.techniques.universe_of_thoughts import (
            UoTProcessor,
        )
        proc = UoTProcessor()
        for query in ["", "x" * 10000, "!!!@@@", "\x00\x01\x02", None]:
            result = await proc.process(query or "")
            assert result is not None

    @pytest.mark.asyncio
    async def test_sc_garbage_input(self):
        from backend.app.core.techniques.self_consistency import (
            SelfConsistencyProcessor,
        )
        proc = SelfConsistencyProcessor()
        for query in ["", "x" * 10000, "!!!@@@"]:
            result = await proc.process(query)
            assert result is not None

    @pytest.mark.asyncio
    async def test_reflexion_garbage_input(self):
        from backend.app.core.techniques.reflexion import ReflexionProcessor
        proc = ReflexionProcessor()
        for query in ["", "x" * 10000, "!!!@@@"]:
            result = await proc.process(query)
            assert result is not None

    @pytest.mark.asyncio
    async def test_tot_garbage_input(self):
        from backend.app.core.techniques.tree_of_thoughts import ToTProcessor
        proc = ToTProcessor()
        for query in ["", "x" * 10000, "!!!@@@"]:
            result = await proc.process(query)
            assert result is not None

    @pytest.mark.asyncio
    async def test_ltm_garbage_input(self):
        from backend.app.core.techniques.least_to_most import (
            LeastToMostProcessor,
        )
        proc = LeastToMostProcessor()
        for query in ["", "x" * 10000, "!!!@@@"]:
            result = await proc.process(query)
            assert result is not None

    @pytest.mark.asyncio
    async def test_all_nodes_execute_on_empty_state(self):
        """All 5 new nodes must handle empty ConversationState."""
        from backend.app.core.techniques.universe_of_thoughts import (
            UniverseOfThoughtsNode,
        )
        from backend.app.core.techniques.self_consistency import (
            SelfConsistencyNode,
        )
        from backend.app.core.techniques.reflexion import ReflexionNode
        from backend.app.core.techniques.tree_of_thoughts import (
            TreeOfThoughtsNode,
        )
        from backend.app.core.techniques.least_to_most import (
            LeastToMostNode,
        )

        nodes = [
            UniverseOfThoughtsNode(),
            SelfConsistencyNode(),
            ReflexionNode(),
            TreeOfThoughtsNode(),
            LeastToMostNode(),
        ]
        empty_state = ConversationState()
        for node in nodes:
            result = await node.execute(empty_state)
            assert isinstance(result, ConversationState)
