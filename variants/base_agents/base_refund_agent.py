"""
PARWA Base Refund Agent.

Abstract base class for refund-handling agents.
CRITICAL: Implements the refund gate - Stripe/Paddle must NEVER be called
without a pending_approval record in the database.
"""
from abc import abstractmethod
from typing import Dict, Any, Optional, List
from uuid import UUID
from enum import Enum

from variants.base_agents.base_agent import (
    BaseAgent,
    AgentResponse,
)
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class RefundRecommendation(str, Enum):
    """Refund recommendation values."""
    APPROVE = "APPROVE"
    REVIEW = "REVIEW"
    DENY = "DENY"


class BaseRefundAgent(BaseAgent):
    """
    Base class for refund-handling agents.

    CRITICAL: This agent implements the refund gate. All refund requests
    must create a pending_approval record before any payment processor
    interaction. Direct Stripe/Paddle calls without approval are FORBIDDEN.
    """

    def __init__(
        self,
        agent_id: str,
        config: Optional[Dict[str, Any]] = None,
        company_id: Optional[UUID] = None
    ) -> None:
        """Initialize refund agent."""
        super().__init__(agent_id, config, company_id)
        self._pending_approvals: Dict[str, Dict[str, Any]] = {}

    async def verify_refund_eligibility(
        self,
        order_id: str
    ) -> Dict[str, Any]:
        """
        Verify if an order is eligible for refund.

        Args:
            order_id: Unique order identifier

        Returns:
            Dict with eligibility status and details
        """
        self.log_action("refund_verify_eligibility", {"order_id": order_id})
        return {
            "order_id": order_id,
            "eligible": True,
            "reason": "Order found and within refund window",
        }

    async def create_pending_approval(
        self,
        refund_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a pending approval record for refund.

        CRITICAL: This method ONLY creates a pending_approval record.
        It does NOT and MUST NOT call Stripe/Paddle directly.

        Args:
            refund_data: Dict with refund details

        Returns:
            Dict with approval_id and status
        """
        order_id = refund_data.get("order_id", "unknown")
        amount = refund_data.get("amount", 0)
        approval_id = f"approval_{order_id}"

        self.log_action("refund_create_pending_approval", {
            "order_id": order_id,
            "amount": amount,
            "approval_id": approval_id,
        })

        # Create pending approval record
        self._pending_approvals[approval_id] = {
            "approval_id": approval_id,
            "order_id": order_id,
            "amount": amount,
            "status": "pending",
            "created_at": None,
            # CRITICAL: No payment processor call here
            "payment_processor_called": False,
        }

        return {
            "approval_id": approval_id,
            "status": "pending",
            "order_id": order_id,
            "amount": amount,
            "message": "Pending approval created. Awaiting human review.",
            "payment_processor_called": False,
        }

    async def check_approval_status(self, approval_id: str) -> str:
        """
        Check the status of a pending approval.

        Args:
            approval_id: Unique approval identifier

        Returns:
            Status string: "pending", "approved", "denied"
        """
        self.log_action("refund_check_approval", {"approval_id": approval_id})
        if approval_id in self._pending_approvals:
            return self._pending_approvals[approval_id].get("status", "pending")
        return "not_found"

    def get_refund_recommendation(
        self,
        refund_data: Dict[str, Any]
    ) -> str:
        """
        Get a refund recommendation based on the data.

        Args:
            refund_data: Dict with refund request details

        Returns:
            RefundRecommendation value
        """
        amount = refund_data.get("amount", 0)
        has_fraud_indicators = refund_data.get("fraud_indicators", False)
        is_first_refund = refund_data.get("is_first_refund", True)

        if has_fraud_indicators:
            return RefundRecommendation.DENY.value

        if amount > self._get_review_threshold():
            return RefundRecommendation.REVIEW.value

        if is_first_refund and amount <= self._get_auto_approve_threshold():
            return RefundRecommendation.APPROVE.value

        return RefundRecommendation.REVIEW.value

    def _get_auto_approve_threshold(self) -> float:
        """Get the threshold for auto-approve recommendations."""
        return self._config.model_dump().get("auto_approve_threshold", 25.0)

    def _get_review_threshold(self) -> float:
        """Get the threshold for manual review."""
        return self._config.model_dump().get("review_threshold", 100.0)

    async def process(
        self,
        input_data: Dict[str, Any]
    ) -> AgentResponse:
        """
        Process a refund request.

        CRITICAL: This creates pending_approval and NEVER calls
        Stripe/Paddle directly.

        Args:
            input_data: Must contain 'order_id'

        Returns:
            AgentResponse with refund recommendation
        """
        order_id = input_data.get("order_id")
        if not order_id:
            return AgentResponse(
                success=False,
                message="Missing required field: order_id",
                variant=self.get_variant(),
                tier_used=self.get_tier(),
            )

        self.log_action("refund_process", {"order_id": order_id})

        # Verify eligibility
        eligibility = await self.verify_refund_eligibility(order_id)

        if not eligibility.get("eligible"):
            return AgentResponse(
                success=False,
                message="Order not eligible for refund",
                data={"eligibility": eligibility},
                variant=self.get_variant(),
                tier_used=self.get_tier(),
            )

        # Get refund recommendation
        recommendation = self.get_refund_recommendation(input_data)

        # CRITICAL: Create pending approval (NEVER calls Stripe/Paddle)
        pending_approval = await self.create_pending_approval(input_data)

        confidence = 0.85 if recommendation == RefundRecommendation.APPROVE.value else 0.75
        escalated = self.should_escalate(confidence, input_data)

        return AgentResponse(
            success=True,
            message="Refund request processed - pending approval created",
            data={
                "recommendation": recommendation,
                "pending_approval": pending_approval,
                "eligibility": eligibility,
            },
            confidence=confidence,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
            escalated=escalated,
        )

    @abstractmethod
    def get_tier(self) -> str:
        """Return the processing tier for this agent."""
        pass

    @abstractmethod
    def get_variant(self) -> str:
        """Return the PARWA variant for this agent."""
        pass
