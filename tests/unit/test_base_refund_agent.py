"""
Unit tests for PARWA Base Refund Agent.

CRITICAL: These tests verify the refund gate is enforced.
Paddle must NEVER be called without pending_approval.
"""
import pytest
from uuid import uuid4

from variants.base_agents.base_refund_agent import (
    BaseRefundAgent,
    RefundRecommendation,
)
from variants.base_agents.base_agent import AgentResponse


class TestableRefundAgent(BaseRefundAgent):
    """Concrete refund agent for testing."""

    def get_tier(self) -> str:
        return "light"

    def get_variant(self) -> str:
        return "mini"


@pytest.fixture
def company_id():
    return uuid4()


@pytest.fixture
def refund_agent(company_id):
    return TestableRefundAgent("test_refund_agent", {}, company_id)


class TestRefundEligibility:
    """Tests for refund eligibility verification."""

    @pytest.mark.asyncio
    async def test_verify_eligibility_returns_result(self, refund_agent):
        """Test eligibility check returns a result."""
        result = await refund_agent.verify_refund_eligibility("ORD-12345")

        assert "order_id" in result
        assert "eligible" in result

    @pytest.mark.asyncio
    async def test_verify_eligibility_logs_action(self, refund_agent):
        """Test eligibility check is logged."""
        await refund_agent.verify_refund_eligibility("ORD-12345")

        logs = refund_agent.get_action_log()
        assert any("refund_verify" in log.get("action", "") for log in logs)


class TestPendingApproval:
    """Tests for pending approval creation."""

    @pytest.mark.asyncio
    async def test_create_pending_approval_success(self, refund_agent):
        """Test creating pending approval."""
        result = await refund_agent.create_pending_approval({
            "order_id": "ORD-12345",
            "amount": 25.00,
        })

        assert "approval_id" in result
        assert result["status"] == "pending"

    @pytest.mark.asyncio
    async def test_pending_approval_includes_message(self, refund_agent):
        """Test approval includes awaiting review message."""
        result = await refund_agent.create_pending_approval({
            "order_id": "ORD-12345",
            "amount": 25.00,
        })

        assert "message" in result
        assert "pending" in result["message"].lower()


class TestRefundGate:
    """CRITICAL: Tests verifying the refund gate is enforced."""

    @pytest.mark.asyncio
    async def test_payment_processor_not_called(self, refund_agent):
        """CRITICAL: Payment processor must NOT be called when creating approval."""
        result = await refund_agent.create_pending_approval({
            "order_id": "ORD-12345",
            "amount": 25.00,
        })

        # CRITICAL: Verify payment processor was NOT called
        assert result.get("payment_processor_called") is False

    @pytest.mark.asyncio
    async def test_pending_approval_status(self, refund_agent):
        """Test created approval has pending status."""
        result = await refund_agent.create_pending_approval({
            "order_id": "ORD-12345",
            "amount": 25.00,
        })

        approval_id = result["approval_id"]
        status = await refund_agent.check_approval_status(approval_id)

        assert status == "pending"

    @pytest.mark.asyncio
    async def test_process_creates_pending_not_executed(self, refund_agent):
        """Test process() creates pending approval, doesn't execute refund."""
        response = await refund_agent.process({
            "order_id": "ORD-12345",
            "amount": 30.00,
        })

        assert response.success is True
        # Check pending approval was created, not executed
        pending = response.data.get("pending_approval", {})
        assert pending.get("payment_processor_called") is False

    @pytest.mark.asyncio
    async def test_no_direct_paddle_calls(self, refund_agent):
        """CRITICAL: Verify no direct Paddle calls in process()."""
        response = await refund_agent.process({
            "order_id": "ORD-12345",
            "amount": 50.00,
        })

        # Verify the refund gate is enforced
        assert response.data.get("pending_approval", {}).get("payment_processor_called") is False


class TestRefundRecommendation:
    """Tests for refund recommendation logic."""

    def test_recommendation_approve_normal_request(self, refund_agent):
        """Test approve recommendation for normal request."""
        recommendation = refund_agent.get_refund_recommendation({
            "amount": 25.00,
            "is_first_refund": True,
            "fraud_indicators": False,
        })

        assert recommendation == RefundRecommendation.APPROVE.value

    def test_recommendation_deny_fraud_indicator(self, refund_agent):
        """Test deny recommendation for fraud indicators."""
        recommendation = refund_agent.get_refund_recommendation({
            "amount": 25.00,
            "fraud_indicators": True,
        })

        assert recommendation == RefundRecommendation.DENY.value

    def test_recommendation_review_high_value(self, refund_agent):
        """Test review recommendation for high value."""
        recommendation = refund_agent.get_refund_recommendation({
            "amount": 200.00,
            "is_first_refund": True,
            "fraud_indicators": False,
        })

        assert recommendation == RefundRecommendation.REVIEW.value


class TestRefundProcess:
    """Tests for the process() method."""

    @pytest.mark.asyncio
    async def test_process_success(self, refund_agent):
        """Test successful refund processing."""
        response = await refund_agent.process({
            "order_id": "ORD-12345",
            "amount": 25.00,
        })

        assert response.success is True
        assert "recommendation" in response.data
        assert "pending_approval" in response.data

    @pytest.mark.asyncio
    async def test_process_missing_order_id(self, refund_agent):
        """Test process with missing order_id."""
        response = await refund_agent.process({
            "amount": 25.00,
        })

        assert response.success is False

    @pytest.mark.asyncio
    async def test_process_returns_confidence(self, refund_agent):
        """Test process returns confidence score."""
        response = await refund_agent.process({
            "order_id": "ORD-12345",
            "amount": 25.00,
        })

        assert response.confidence >= 0.0
        assert response.confidence <= 1.0


class TestApprovalStatus:
    """Tests for approval status checking."""

    @pytest.mark.asyncio
    async def test_check_status_pending(self, refund_agent):
        """Test checking status of pending approval."""
        result = await refund_agent.create_pending_approval({
            "order_id": "ORD-12345",
            "amount": 25.00,
        })
        approval_id = result["approval_id"]

        status = await refund_agent.check_approval_status(approval_id)

        assert status == "pending"

    @pytest.mark.asyncio
    async def test_check_status_not_found(self, refund_agent):
        """Test checking status of non-existent approval."""
        status = await refund_agent.check_approval_status("nonexistent")

        assert status == "not_found"


class TestRefundAgentInheritance:
    """Tests for refund agent inheritance."""

    def test_inherits_from_base_agent(self, refund_agent):
        """Test refund agent inherits from BaseAgent."""
        from variants.base_agents.base_agent import BaseAgent
        assert isinstance(refund_agent, BaseAgent)

    def test_has_get_tier(self, refund_agent):
        """Test refund agent has get_tier method."""
        assert refund_agent.get_tier() == "light"

    def test_has_get_variant(self, refund_agent):
        """Test refund agent has get_variant method."""
        assert refund_agent.get_variant() == "mini"
