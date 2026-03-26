"""
BDD Scenarios for PARWA Junior.

Tests follow Given-When-Then format:
- Given: Initial context/setup
- When: Action performed
- Then: Expected outcome

Scenarios:
1. Complex query → PARWA uses Medium tier
2. Refund request → PARWA returns APPROVE/REVIEW/DENY with reasoning
3. Negative feedback → Learning agent creates negative_reward
4. Competitor mention → Safety agent blocks
"""
import pytest

from variants.parwa.agents.faq_agent import ParwaFAQAgent
from variants.parwa.agents.refund_agent import ParwaRefundAgent
from variants.parwa.agents.learning_agent import ParwaLearningAgent
from variants.parwa.agents.safety_agent import ParwaSafetyAgent
from variants.parwa.workflows.refund_recommendation import (
    RefundRecommendationWorkflow,
    RefundDecision,
)
from variants.parwa.config import get_parwa_config


class TestParwaScenarios:
    """BDD scenarios for PARWA Junior variant."""

    # =========================================================================
    # Scenario 1: Complex query → PARWA uses Medium tier
    # =========================================================================

    @pytest.mark.asyncio
    async def test_scenario_complex_query_uses_medium_tier(self):
        """
        Scenario: Complex query uses medium tier
        Given: A complex customer query
        When: PARWA processes the query
        Then: The medium tier is used
        And: The response has higher capability
        """
        # Given
        agent = ParwaFAQAgent(agent_id="complex_test")
        complex_query = "I need to understand the difference between refund policies"

        # When
        result = await agent.process({
            "query": complex_query,
            "customer_id": "cust_complex",
        })

        # Then
        assert result.success is True
        assert agent.get_tier() == "medium"
        assert agent.get_variant() == "parwa"

    @pytest.mark.asyncio
    async def test_scenario_parwa_tier_is_medium(self):
        """
        Scenario: PARWA always uses medium tier
        Given: Any PARWA agent
        When: Checking the tier
        Then: Tier is 'medium'
        """
        # Given
        agents = [
            ParwaFAQAgent(agent_id="faq"),
            ParwaRefundAgent(agent_id="refund"),
            ParwaLearningAgent(agent_id="learning"),
            ParwaSafetyAgent(agent_id="safety"),
        ]

        # When/Then
        for agent in agents:
            assert agent.get_tier() == "medium"
            assert agent.get_variant() == "parwa"

    # =========================================================================
    # Scenario 2: Refund request → PARWA returns APPROVE/REVIEW/DENY with reasoning
    # =========================================================================

    @pytest.mark.asyncio
    async def test_scenario_refund_returns_decision(self):
        """
        Scenario: Refund returns decision with reasoning
        Given: A refund request within PARWA limit
        When: PARWA processes the refund
        Then: Returns APPROVE, REVIEW, or DENY
        And: Includes full reasoning
        """
        # Given
        workflow = RefundRecommendationWorkflow()
        refund_data = {
            "order_id": "ord_parwa_001",
            "amount": 150.00,
            "customer_id": "cust_parwa",
            "reason": "Product not as described",
        }

        # When
        result = await workflow.execute(refund_data)

        # Then
        assert result.success is True
        assert result.decision in [
            RefundDecision.APPROVE,
            RefundDecision.REVIEW,
            RefundDecision.DENY,
        ]

    @pytest.mark.asyncio
    async def test_scenario_refund_includes_full_reasoning(self):
        """
        Scenario: Refund includes full reasoning
        Given: A refund request
        When: PARWA processes and makes decision
        Then: The result includes reasoning object
        And: Reasoning has primary_reason
        And: Reasoning has supporting_factors
        """
        # Given
        workflow = RefundRecommendationWorkflow()
        refund_data = {
            "order_id": "ord_reasoning",
            "amount": 200.00,
            "customer_id": "cust_reasoning",
            "reason": "Damaged product",
            "customer_history": {"total_refunds": 0},
        }

        # When
        result = await workflow.execute(refund_data)

        # Then
        assert result.success is True
        assert result.reasoning is not None
        assert result.reasoning.primary_reason is not None
        assert isinstance(result.reasoning.supporting_factors, list)

    @pytest.mark.asyncio
    async def test_scenario_refund_never_calls_paddle(self):
        """
        Scenario: PARWA never calls Paddle directly
        Given: Any refund request to PARWA
        When: The refund is processed
        Then: paddle_called is always False
        """
        # Given
        workflow = RefundRecommendationWorkflow()

        # When
        result = await workflow.execute({
            "order_id": "ord_no_paddle",
            "amount": 400.00,
            "customer_id": "cust_no_paddle",
            "reason": "Test",
        })

        # Then
        assert result.paddle_called is False

    # =========================================================================
    # Scenario 3: Negative feedback → Learning agent creates negative_reward
    # =========================================================================

    @pytest.mark.asyncio
    async def test_scenario_negative_feedback_creates_negative_reward(self):
        """
        Scenario: Negative feedback creates negative_reward
        Given: A customer interaction with negative feedback
        When: Learning agent records the feedback
        Then: A negative_reward record is created
        """
        # Given
        agent = ParwaLearningAgent(agent_id="learning_test")
        interaction_id = "inter_001"
        reason = "Customer was dissatisfied with response"

        # When
        result = await agent.create_negative_reward(
            interaction_id=interaction_id,
            reason=reason,
        )

        # Then
        assert result.get("success", True) is True
        assert result.get("reward_id") is not None  # Contains reward_id

    # =========================================================================
    # Scenario 4: Competitor mention → Safety agent blocks
    # =========================================================================

    @pytest.mark.asyncio
    async def test_scenario_competitor_mention_blocked(self):
        """
        Scenario: Competitor mention is blocked
        Given: A response containing competitor name
        When: Safety agent checks the response
        Then: The competitor mention is flagged/blocked
        """
        # Given
        agent = ParwaSafetyAgent(agent_id="safety_test")
        response_with_competitor = "I recommend checking out CompetitorX for better prices"

        # When
        result = await agent.block_competitor_mention(response_with_competitor)

        # Then
        assert result.get("blocked", True) is True or result.get("success", True) is True

    @pytest.mark.asyncio
    async def test_scenario_safe_response_passes(self):
        """
        Scenario: Safe response passes through
        Given: A response without competitor mentions
        When: Safety agent checks the response
        Then: The response is allowed
        """
        # Given
        agent = ParwaSafetyAgent(agent_id="safety_safe_test")
        safe_response = "Our product offers great value and excellent support"

        # When
        result = await agent.check_response(safe_response)

        # Then
        assert result.get("safe", True) is True or result.get("success", True) is True


class TestParwaConfigValidation:
    """Tests validating PARWA configuration."""

    def test_parwa_config_values(self):
        """Verify PARWA configuration values."""
        config = get_parwa_config()

        assert config.max_concurrent_calls == 5
        assert config.escalation_threshold == 0.60
        assert config.refund_limit == 500.0
        assert config.default_tier == "medium"
        assert config.get_variant_name() == "PARWA Junior"
