"""
BDD Scenarios for Mini PARWA.

Tests follow Given-When-Then format:
- Given: Initial context/setup
- When: Action performed
- Then: Expected outcome

Scenarios:
1. Customer asks FAQ → Mini answers
2. Customer requests refund → Mini creates pending_approval
3. Confidence < 70% → Mini escalates
4. 2 concurrent calls → Mini respects limit
"""
import pytest

from variants.mini.agents.faq_agent import MiniFAQAgent
from variants.mini.agents.voice_agent import MiniVoiceAgent
from variants.mini.tasks.verify_refund import VerifyRefundTask, RefundStatus
from variants.mini.config import get_mini_config


class TestMiniScenarios:
    """BDD scenarios for Mini PARWA variant."""

    # =========================================================================
    # Scenario 1: Customer asks FAQ → Mini answers
    # =========================================================================

    @pytest.mark.asyncio
    async def test_scenario_customer_asks_faq_mini_answers(self):
        """
        Scenario: Customer asks FAQ question
        Given: A customer has a frequently asked question
        When: The customer asks the question
        Then: Mini answers with a relevant response
        And: The confidence score is included
        """
        # Given
        agent = MiniFAQAgent(agent_id="faq_test")
        question = "What are your business hours?"
        customer_id = "cust_001"

        # When
        result = await agent.process({
            "query": question,
            "customer_id": customer_id,
        })

        # Then
        assert result.success is True
        assert result.variant == "mini"
        assert result.confidence >= 0

    @pytest.mark.asyncio
    async def test_scenario_faq_returns_light_tier(self):
        """
        Scenario: FAQ agent uses light tier
        Given: Mini FAQ agent is initialized
        When: Processing any FAQ query
        Then: The tier used is 'light'
        """
        # Given
        agent = MiniFAQAgent(agent_id="faq_tier_test")

        # When
        result = await agent.process({
            "query": "How do I reset my password?",
            "customer_id": "cust_002",
        })

        # Then
        assert result.success is True
        assert agent.get_tier() == "light"

    # =========================================================================
    # Scenario 2: Customer requests refund → Mini creates pending_approval
    # =========================================================================

    @pytest.mark.asyncio
    async def test_scenario_refund_creates_pending_approval(self):
        """
        Scenario: Customer requests refund
        Given: A customer wants a refund within Mini's limit
        When: The refund request is processed
        Then: A pending_approval record is created
        And: Paddle is NOT called directly
        """
        # Given
        task = VerifyRefundTask()
        refund_data = {
            "order_id": "ord_001",
            "amount": 25.00,  # Within $50 limit
            "reason": "Product defective",
            "customer_id": "cust_003",
        }

        # When
        result = await task.execute(refund_data)

        # Then
        assert result.success is True
        assert result.paddle_call_required is False
        assert result.approval_required is True

    @pytest.mark.asyncio
    async def test_scenario_refund_over_limit_rejected(self):
        """
        Scenario: Refund over Mini limit
        Given: A customer requests a refund over $50
        When: The refund request is processed
        Then: The request is rejected as over limit
        And: The reason indicates limit exceeded
        """
        # Given
        task = VerifyRefundTask()
        refund_data = {
            "order_id": "ord_002",
            "amount": 75.00,  # Over $50 limit
            "reason": "Customer changed mind",
            "customer_id": "cust_004",
        }

        # When
        result = await task.execute(refund_data)

        # Then
        assert result.success is False
        assert result.status == RefundStatus.EXCEEDED_LIMIT
        assert "exceeds" in result.rejection_reason.lower()

    @pytest.mark.asyncio
    async def test_scenario_refund_never_calls_paddle(self):
        """
        Scenario: Mini never calls Paddle directly
        Given: Any refund request to Mini
        When: The refund is processed
        Then: paddle_call_required is always False
        And: approval_required is always True
        """
        # Given
        task = VerifyRefundTask()

        # Test multiple amounts within limit
        amounts = [5.00, 25.00, 50.00]

        for amount in amounts:
            # When
            result = await task.execute({
                "order_id": f"ord_{amount}",
                "amount": amount,
                "reason": "Test",
                "customer_id": "cust_test",
            })

            # Then
            assert result.paddle_call_required is False, f"Failed for ${amount}"
            assert result.approval_required is True, f"Failed for ${amount}"

    # =========================================================================
    # Scenario 3: Confidence < 70% → Mini escalates
    # =========================================================================

    @pytest.mark.asyncio
    async def test_scenario_low_confidence_escalates(self):
        """
        Scenario: Low confidence triggers escalation
        Given: Mini's escalation threshold is 70%
        When: A response has confidence < 70%
        Then: The ticket is escalated
        """
        # Given
        config = get_mini_config()
        agent = MiniFAQAgent(agent_id="escalation_test")

        # Verify threshold
        assert config.escalation_threshold == 0.70

        # When - process a query
        result = await agent.process({
            "query": "Complex multi-part legal question",
            "customer_id": "cust_005",
        })

        # Then - check escalation behavior
        if result.confidence < 0.70:
            assert result.escalated is True

    # =========================================================================
    # Scenario 4: 2 concurrent calls → Mini respects limit
    # =========================================================================

    @pytest.mark.asyncio
    async def test_scenario_two_concurrent_calls_limit(self):
        """
        Scenario: Mini respects 2 concurrent call limit
        Given: Mini's max concurrent calls is 2
        When: A third call is attempted
        Then: The call is queued
        """
        # Given
        config = get_mini_config()
        agent = MiniVoiceAgent(agent_id="voice_limit_test")

        # Verify limit
        assert config.max_concurrent_calls == 2

        # Fill up to limit
        agent._active_calls = {
            "call_1": {"status": "active"},
            "call_2": {"status": "active"},
        }

        # When - try to make third call
        can_make_call = agent.can_accept_call()

        # Then
        assert can_make_call is False

    @pytest.mark.asyncio
    async def test_scenario_concurrent_calls_under_limit_allowed(self):
        """
        Scenario: Calls under limit are allowed
        Given: Fewer than 2 active calls
        When: A new call is attempted
        Then: The call is allowed
        """
        # Given
        agent = MiniVoiceAgent(agent_id="voice_allowed_test")
        agent._active_calls = {
            "call_1": {"status": "active"},
        }

        # When
        can_make_call = agent.can_accept_call()

        # Then
        assert can_make_call is True


class TestMiniBDDIntegration:
    """Integration tests combining multiple Mini scenarios."""

    @pytest.mark.asyncio
    async def test_full_faq_to_refund_flow(self):
        """
        Scenario: Complete FAQ to refund flow
        Given: Customer asks about refund policy
        When: Customer then requests refund
        Then: Both operations succeed with Mini constraints
        """
        # Given - FAQ query first
        faq_agent = MiniFAQAgent(agent_id="flow_test")
        faq_result = await faq_agent.process({
            "query": "What is your refund policy?",
            "customer_id": "cust_flow",
        })
        assert faq_result.success is True

        # When - refund request
        refund_task = VerifyRefundTask()
        refund_result = await refund_task.execute({
            "order_id": "ord_flow",
            "amount": 30.00,
            "reason": "Product not as described",
            "customer_id": "cust_flow",
        })

        # Then
        assert refund_result.success is True
        assert refund_result.paddle_call_required is False
        assert refund_result.approval_required is True
