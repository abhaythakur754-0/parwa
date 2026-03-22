"""
PARWA Mini Refund Agent.

Mini PARWA's refund agent handles refund requests with a $50 limit.
CRITICAL: This agent NEVER calls Paddle directly. It creates
pending_approval records for human review.
"""
from typing import Dict, Any, Optional
from uuid import UUID

from variants.base_agents.base_refund_agent import (
    BaseRefundAgent,
    AgentResponse,
    RefundRecommendation,
)
from variants.mini.config import MiniConfig, get_mini_config
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class MiniRefundAgent(BaseRefundAgent):
    """
    Mini PARWA Refund Agent.

    Handles refund requests with the following characteristics:
    - Maximum refund amount: $50 (Mini limit)
    - Always routes to 'light' tier
    - Creates pending_approval for ALL refunds (NEVER calls Paddle)
    - Escalates refunds over $50 limit
    - Escalation threshold: 70% confidence

    CRITICAL: This agent implements the Paddle refund gate.
    Paddle must NEVER be called without pending_approval.
    """

    # Mini can only recommend refunds up to $50
    MINI_REFUND_LIMIT = 50.0

    def __init__(
        self,
        agent_id: str,
        config: Optional[Dict[str, Any]] = None,
        company_id: Optional[UUID] = None,
        mini_config: Optional[MiniConfig] = None,
    ) -> None:
        """
        Initialize Mini Refund Agent.

        Args:
            agent_id: Unique identifier for this agent
            config: Agent configuration dictionary
            company_id: UUID of the company
            mini_config: Optional MiniConfig instance
        """
        super().__init__(agent_id, config, company_id)
        self._mini_config = mini_config or get_mini_config()

    def get_tier(self) -> str:
        """Get the AI tier for this agent. Mini always uses 'light'."""
        return "light"

    def get_variant(self) -> str:
        """Get the PARWA variant for this agent."""
        return "mini"

    def validate_refund_amount(self, amount: float) -> bool:
        """
        Check if amount is within Mini's $50 limit.

        Args:
            amount: Refund amount in USD

        Returns:
            True if amount <= $50
        """
        return amount <= self.MINI_REFUND_LIMIT

    async def process(self, input_data: Dict[str, Any]) -> AgentResponse:
        """
        Process a refund request.

        CRITICAL: This method NEVER calls Paddle directly.
        It creates pending_approval records for human review.

        Args:
            input_data: Must contain 'order_id' and 'amount'

        Returns:
            AgentResponse with refund processing result
        """
        order_id = input_data.get("order_id")
        amount = input_data.get("amount", 0)

        if not order_id:
            return AgentResponse(
                success=False,
                message="Missing required field: order_id",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        # Validate amount
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            return AgentResponse(
                success=False,
                message="Invalid amount value",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        self.log_action("mini_refund_process", {
            "order_id": order_id,
            "amount": amount,
            "limit": self.MINI_REFUND_LIMIT,
            "tier": self.get_tier(),
        })

        # Check if amount exceeds Mini limit
        if amount > self.MINI_REFUND_LIMIT:
            self.log_action("mini_refund_escalate_over_limit", {
                "order_id": order_id,
                "amount": amount,
                "limit": self.MINI_REFUND_LIMIT,
            })
            return AgentResponse(
                success=True,
                message=f"Refund amount ${amount:.2f} exceeds Mini limit of ${self.MINI_REFUND_LIMIT:.2f}. Escalated for human review.",
                data={
                    "refund_amount": amount,
                    "mini_limit": self.MINI_REFUND_LIMIT,
                    "exceeds_limit": True,
                    "requires_escalation": True,
                },
                confidence=0.0,
                tier_used=self.get_tier(),
                variant=self.get_variant(),
                escalated=True,
            )

        # Verify eligibility
        eligibility = await self.verify_refund_eligibility(order_id)

        if not eligibility.get("eligible"):
            return AgentResponse(
                success=False,
                message="Order not eligible for refund",
                data={"eligibility": eligibility},
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        # Get refund recommendation
        recommendation = self.get_refund_recommendation(input_data)

        # CRITICAL: Create pending approval (NEVER calls Paddle)
        pending_approval = await self.create_pending_approval({
            "order_id": order_id,
            "amount": amount,
            "recommendation": recommendation,
            "variant": self.get_variant(),
        })

        # Calculate confidence
        confidence = self._calculate_refund_confidence(
            amount, recommendation, input_data
        )

        # Check escalation
        escalated = self.should_escalate(confidence, input_data)

        # Determine message based on recommendation
        if recommendation == RefundRecommendation.APPROVE.value:
            message = f"Refund of ${amount:.2f} recommended for approval. Pending review created."
        elif recommendation == RefundRecommendation.DENY.value:
            message = "Refund denied due to fraud indicators. Pending review created."
        else:
            message = f"Refund of ${amount:.2f} requires manual review. Pending review created."

        return AgentResponse(
            success=True,
            message=message,
            data={
                "recommendation": recommendation,
                "pending_approval": pending_approval,
                "eligibility": eligibility,
                "refund_amount": amount,
                "mini_limit": self.MINI_REFUND_LIMIT,
                # CRITICAL: Verify Paddle was NOT called
                "payment_processor_called": False,
            },
            confidence=confidence,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
            escalated=escalated,
        )

    async def create_pending_approval(
        self,
        refund_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a pending approval record for refund.

        CRITICAL: This method ONLY creates a pending_approval record.
        It does NOT and MUST NOT call Paddle directly.

        Args:
            refund_data: Dict with refund details including:
                - order_id: Order identifier
                - amount: Refund amount
                - recommendation: APPROVE/REVIEW/DENY

        Returns:
            Dict with approval_id and status
        """
        order_id = refund_data.get("order_id", "unknown")
        amount = refund_data.get("amount", 0)
        recommendation = refund_data.get("recommendation", "REVIEW")

        # Call parent implementation
        result = await super().create_pending_approval(refund_data)

        # Add Mini-specific fields
        result["mini_limit"] = self.MINI_REFUND_LIMIT
        result["within_limit"] = amount <= self.MINI_REFUND_LIMIT
        result["recommendation"] = recommendation
        result["variant"] = self.get_variant()

        self.log_action("mini_pending_approval_created", {
            "approval_id": result["approval_id"],
            "order_id": order_id,
            "amount": amount,
            "within_limit": result["within_limit"],
            # CRITICAL: Explicitly log no Paddle call
            "paddle_called": False,
        })

        return result

    def get_refund_recommendation(
        self,
        refund_data: Dict[str, Any]
    ) -> str:
        """
        Get a refund recommendation based on the data.

        Mini-specific logic:
        - Amounts over $50 -> REVIEW (should be escalated anyway)
        - Fraud indicators -> DENY
        - First refund under $25 -> APPROVE
        - Everything else -> REVIEW

        Args:
            refund_data: Dict with refund request details

        Returns:
            RefundRecommendation value
        """
        amount = refund_data.get("amount", 0)
        has_fraud_indicators = refund_data.get("fraud_indicators", False)
        is_first_refund = refund_data.get("is_first_refund", True)

        # Fraud always denied
        if has_fraud_indicators:
            return RefundRecommendation.DENY.value

        # Amounts over Mini limit require review
        if amount > self.MINI_REFUND_LIMIT:
            return RefundRecommendation.REVIEW.value

        # Small first refunds can be approved
        if is_first_refund and amount <= 25.0:
            return RefundRecommendation.APPROVE.value

        # Everything else needs review
        return RefundRecommendation.REVIEW.value

    def _calculate_refund_confidence(
        self,
        amount: float,
        recommendation: str,
        input_data: Dict[str, Any]
    ) -> float:
        """Calculate confidence for refund processing."""
        confidence = 0.7  # Base confidence

        # Higher confidence for smaller amounts
        if amount <= 25.0:
            confidence += 0.15
        elif amount <= 50.0:
            confidence += 0.05

        # Higher confidence for clean history
        if input_data.get("is_first_refund", True):
            confidence += 0.1

        # Lower confidence if suspicious
        if input_data.get("fraud_indicators", False):
            confidence -= 0.3

        # Adjust based on recommendation
        if recommendation == RefundRecommendation.APPROVE.value:
            confidence += 0.05
        elif recommendation == RefundRecommendation.DENY.value:
            confidence -= 0.1

        return max(0.0, min(1.0, confidence))

    def should_escalate(
        self,
        confidence: float,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Determine if escalation is needed.

        Uses Mini config's escalation threshold (default 70%).

        Args:
            confidence: Confidence score (0.0-1.0)
            context: Optional additional context

        Returns:
            True if confidence < escalation threshold
        """
        context = context or {}

        # Check amount escalation
        amount = context.get("amount", 0)
        if amount > self.MINI_REFUND_LIMIT:
            return True

        # Check confidence threshold
        return confidence < self._mini_config.escalation_threshold

    def get_refund_stats(self) -> Dict[str, Any]:
        """Get refund agent statistics."""
        return {
            "total_pending": len(self._pending_approvals),
            "mini_limit": self.MINI_REFUND_LIMIT,
            "variant": self.get_variant(),
            "tier": self.get_tier(),
            "escalation_threshold": self._mini_config.escalation_threshold,
        }
