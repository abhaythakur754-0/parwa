"""
PARWA Junior Refund Agent.

PARWA Junior's refund agent handles refund requests with $500 limit.
CRITICAL: This agent returns APPROVE/REVIEW/DENY with full reasoning.
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
from variants.parwa.config import ParwaConfig, get_parwa_config
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class ParwaRefundAgent(BaseRefundAgent):
    """
    PARWA Junior Refund Agent.

    Handles refund requests with the following characteristics:
    - Maximum refund amount: $500 (PARWA limit)
    - Routes to 'medium' tier for sophisticated analysis
    - Returns APPROVE/REVIEW/DENY with FULL REASONING
    - Creates pending_approval for ALL refunds (NEVER calls Paddle)
    - Escalates refunds over $500 limit
    - Escalation threshold: 60% confidence

    CRITICAL: This agent implements the Paddle refund gate.
    Paddle must NEVER be called without pending_approval.
    """

    # PARWA Junior can recommend refunds up to $500
    PARWA_REFUND_LIMIT = 500.0

    def __init__(
        self,
        agent_id: str,
        config: Optional[Dict[str, Any]] = None,
        company_id: Optional[UUID] = None,
        parwa_config: Optional[ParwaConfig] = None,
    ) -> None:
        """
        Initialize PARWA Junior Refund Agent.

        Args:
            agent_id: Unique identifier for this agent
            config: Agent configuration dictionary
            company_id: UUID of the company
            parwa_config: Optional ParwaConfig instance
        """
        # Set parwa_config BEFORE calling super().__init__ because
        # the parent's __init__ calls get_tier() which needs this attribute
        self._parwa_config = parwa_config or get_parwa_config()
        super().__init__(agent_id, config, company_id)

    def get_tier(self) -> str:
        """Get the AI tier for this agent. PARWA uses 'medium'."""
        return self._parwa_config.default_tier

    def get_variant(self) -> str:
        """Get the PARWA variant for this agent."""
        return "parwa"

    def validate_refund_amount(self, amount: float) -> bool:
        """
        Check if amount is within PARWA's $500 limit.

        Args:
            amount: Refund amount in USD

        Returns:
            True if amount <= $500
        """
        return amount <= self.PARWA_REFUND_LIMIT

    async def process(self, input_data: Dict[str, Any]) -> AgentResponse:
        """
        Process a refund request.

        CRITICAL: This method NEVER calls Paddle directly.
        It creates pending_approval records for human review.
        Returns APPROVE/REVIEW/DENY with FULL REASONING.

        Args:
            input_data: Must contain 'order_id' and 'amount'

        Returns:
            AgentResponse with refund processing result including:
            - recommendation: APPROVE/REVIEW/DENY
            - reasoning: Full explanation for the recommendation
            - confidence: Confidence score
            - pending_approval: Approval record details
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

        self.log_action("parwa_refund_process", {
            "order_id": order_id,
            "amount": amount,
            "limit": self.PARWA_REFUND_LIMIT,
            "tier": self.get_tier(),
        })

        # Check if amount exceeds PARWA limit
        if amount > self.PARWA_REFUND_LIMIT:
            self.log_action("parwa_refund_escalate_over_limit", {
                "order_id": order_id,
                "amount": amount,
                "limit": self.PARWA_REFUND_LIMIT,
            })
            return AgentResponse(
                success=True,
                message=f"Refund amount ${amount:.2f} exceeds PARWA limit of ${self.PARWA_REFUND_LIMIT:.2f}. Escalated for human review.",
                data={
                    "refund_amount": amount,
                    "parwa_limit": self.PARWA_REFUND_LIMIT,
                    "exceeds_limit": True,
                    "requires_escalation": True,
                    "recommendation": RefundRecommendation.REVIEW.value,
                    "reasoning": f"Amount ${amount:.2f} exceeds PARWA Junior limit of ${self.PARWA_REFUND_LIMIT:.2f}. Requires PARWA High or manual review.",
                },
                confidence=0.0,
                tier_used=self.get_tier(),
                variant=self.get_variant(),
                escalated=True,
            )

        # Verify eligibility
        eligibility = await self.verify_refund_eligibility(order_id)

        if not eligibility.get("eligible"):
            reasoning = self._generate_denial_reasoning(eligibility, input_data)
            return AgentResponse(
                success=False,
                message="Order not eligible for refund",
                data={
                    "eligibility": eligibility,
                    "recommendation": RefundRecommendation.DENY.value,
                    "reasoning": reasoning,
                },
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        # Get refund recommendation with reasoning
        recommendation_data = self.get_refund_recommendation(input_data)
        recommendation = recommendation_data["recommendation"]
        reasoning = recommendation_data["reasoning"]

        # CRITICAL: Create pending approval (NEVER calls Paddle)
        pending_approval = await self.create_pending_approval({
            "order_id": order_id,
            "amount": amount,
            "recommendation": recommendation,
            "reasoning": reasoning,
            "variant": self.get_variant(),
        })

        # Calculate confidence
        confidence = self._calculate_refund_confidence(
            amount, recommendation, input_data
        )

        # Check escalation based on PARWA threshold (60%)
        escalated = self.should_escalate(confidence, input_data)

        # Determine message based on recommendation
        if recommendation == RefundRecommendation.APPROVE.value:
            message = f"Refund of ${amount:.2f} recommended for APPROVAL. {reasoning}"
        elif recommendation == RefundRecommendation.DENY.value:
            message = f"Refund DENIED. {reasoning}"
        else:
            message = f"Refund of ${amount:.2f} requires MANUAL REVIEW. {reasoning}"

        return AgentResponse(
            success=True,
            message=message,
            data={
                "recommendation": recommendation,
                "reasoning": reasoning,
                "pending_approval": pending_approval,
                "eligibility": eligibility,
                "refund_amount": amount,
                "parwa_limit": self.PARWA_REFUND_LIMIT,
                # CRITICAL: Verify Paddle was NOT called
                "payment_processor_called": False,
            },
            confidence=confidence,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
            escalated=escalated,
        )

    def get_refund_recommendation(
        self,
        refund_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Get a refund recommendation with FULL REASONING.

        PARWA Junior-specific logic:
        - Amounts over $500 -> REVIEW (should be escalated anyway)
        - Fraud indicators -> DENY with reasoning
        - First refund under $100 -> APPROVE with reasoning
        - Amounts $100-$500 -> REVIEW with reasoning
        - Everything else -> REVIEW with context

        Args:
            refund_data: Dict with refund request details

        Returns:
            Dict with:
            - recommendation: APPROVE/REVIEW/DENY
            - reasoning: Full explanation for the recommendation
            - confidence: Confidence score
        """
        amount = refund_data.get("amount", 0)
        has_fraud_indicators = refund_data.get("fraud_indicators", False)
        is_first_refund = refund_data.get("is_first_refund", True)
        customer_history = refund_data.get("customer_history", "normal")
        order_age_days = refund_data.get("order_age_days", 0)

        reasoning_parts = []
        confidence = 0.7

        # Fraud check - always denied with detailed reasoning
        if has_fraud_indicators:
            reasoning_parts.append("Fraud indicators detected in request.")
            reasoning_parts.append("Transaction flagged for security review.")
            if refund_data.get("fraud_details"):
                reasoning_parts.append(f"Details: {refund_data['fraud_details']}")
            return {
                "recommendation": RefundRecommendation.DENY.value,
                "reasoning": " ".join(reasoning_parts),
                "confidence": 0.9,
            }

        # Amount over limit
        if amount > self.PARWA_REFUND_LIMIT:
            reasoning_parts.append(
                f"Amount ${amount:.2f} exceeds PARWA Junior limit of ${self.PARWA_REFUND_LIMIT:.2f}."
            )
            reasoning_parts.append("Requires escalation to PARWA High or human review.")
            return {
                "recommendation": RefundRecommendation.REVIEW.value,
                "reasoning": " ".join(reasoning_parts),
                "confidence": 0.5,
            }

        # Order age check
        if order_age_days > 30:
            reasoning_parts.append(
                f"Order is {order_age_days} days old, exceeding 30-day refund window."
            )
            reasoning_parts.append("Requires manager approval for policy exception.")
            return {
                "recommendation": RefundRecommendation.REVIEW.value,
                "reasoning": " ".join(reasoning_parts),
                "confidence": 0.6,
            }

        # First refund, small amount - auto-approve territory
        if is_first_refund and amount <= 100.0:
            reasoning_parts.append("First-time refund request from customer.")
            reasoning_parts.append(f"Amount ${amount:.2f} within auto-approve threshold ($100).")
            reasoning_parts.append("Customer has no prior refund history.")
            reasoning_parts.append("Recommendation: Approve pending human verification.")
            confidence = 0.85
            return {
                "recommendation": RefundRecommendation.APPROVE.value,
                "reasoning": " ".join(reasoning_parts),
                "confidence": confidence,
            }

        # First refund, medium amount
        if is_first_refund and amount <= 250.0:
            reasoning_parts.append("First-time refund request from customer.")
            reasoning_parts.append(f"Amount ${amount:.2f} requires verification.")
            reasoning_parts.append("No prior refund history found.")
            reasoning_parts.append("Recommendation: Review and approve if order verified.")
            confidence = 0.75
            return {
                "recommendation": RefundRecommendation.REVIEW.value,
                "reasoning": " ".join(reasoning_parts),
                "confidence": confidence,
            }

        # High-value refund
        if amount > 250.0:
            reasoning_parts.append(f"High-value refund request: ${amount:.2f}.")
            reasoning_parts.append("Requires detailed verification and approval.")
            if customer_history == "vip":
                reasoning_parts.append("VIP customer - prioritize review.")
                confidence = 0.7
            else:
                reasoning_parts.append("Standard review process required.")
                confidence = 0.65
            return {
                "recommendation": RefundRecommendation.REVIEW.value,
                "reasoning": " ".join(reasoning_parts),
                "confidence": confidence,
            }

        # Default case - review
        reasoning_parts.append(f"Refund request for ${amount:.2f}.")
        reasoning_parts.append("Requires standard review process.")
        if not is_first_refund:
            reasoning_parts.append("Note: Customer has prior refund history.")
            confidence = 0.6
        else:
            confidence = 0.7

        return {
            "recommendation": RefundRecommendation.REVIEW.value,
            "reasoning": " ".join(reasoning_parts),
            "confidence": confidence,
        }

    def _generate_denial_reasoning(
        self,
        eligibility: Dict[str, Any],
        refund_data: Dict[str, Any]
    ) -> str:
        """Generate reasoning for denial."""
        reason = eligibility.get("reason", "Unknown reason")
        order_id = refund_data.get("order_id", "unknown")

        reasoning_parts = [
            f"Refund request for order {order_id} DENIED.",
            f"Reason: {reason}.",
        ]

        if "refund window" in reason.lower():
            reasoning_parts.append(
                "The order has exceeded the 30-day refund policy window."
            )
        elif "already refunded" in reason.lower():
            reasoning_parts.append(
                "This order has already been processed for a refund."
            )
        elif "not found" in reason.lower():
            reasoning_parts.append(
                "The order could not be located in our system."
            )

        reasoning_parts.append("No pending approval will be created for this denial.")

        return " ".join(reasoning_parts)

    def _calculate_refund_confidence(
        self,
        amount: float,
        recommendation: str,
        input_data: Dict[str, Any]
    ) -> float:
        """Calculate confidence for refund processing."""
        confidence = 0.65  # Base confidence for PARWA

        # Higher confidence for smaller amounts
        if amount <= 100.0:
            confidence += 0.15
        elif amount <= 250.0:
            confidence += 0.08
        elif amount <= 500.0:
            confidence += 0.02

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
            confidence -= 0.05

        # Lower confidence for high-value refunds
        if amount > 300.0:
            confidence -= 0.05

        return max(0.0, min(1.0, confidence))

    def should_escalate(
        self,
        confidence: float,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Determine if escalation is needed.

        Uses PARWA config's escalation threshold (default 60%).

        Args:
            confidence: Confidence score (0.0-1.0)
            context: Optional additional context

        Returns:
            True if confidence < escalation threshold
        """
        context = context or {}

        # Check amount escalation
        amount = context.get("amount", 0)
        if amount > self.PARWA_REFUND_LIMIT:
            return True

        # Check confidence threshold (60% for PARWA)
        return confidence < self._parwa_config.escalation_threshold

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
                - reasoning: Full reasoning for recommendation

        Returns:
            Dict with approval_id and status
        """
        order_id = refund_data.get("order_id", "unknown")
        amount = refund_data.get("amount", 0)
        recommendation = refund_data.get("recommendation", "REVIEW")
        reasoning = refund_data.get("reasoning", "")

        # Call parent implementation
        result = await super().create_pending_approval(refund_data)

        # Add PARWA-specific fields
        result["parwa_limit"] = self.PARWA_REFUND_LIMIT
        result["within_limit"] = amount <= self.PARWA_REFUND_LIMIT
        result["recommendation"] = recommendation
        result["reasoning"] = reasoning
        result["variant"] = self.get_variant()
        result["tier"] = self.get_tier()

        self.log_action("parwa_pending_approval_created", {
            "approval_id": result["approval_id"],
            "order_id": order_id,
            "amount": amount,
            "recommendation": recommendation,
            "within_limit": result["within_limit"],
            # CRITICAL: Explicitly log no Paddle call
            "paddle_called": False,
        })

        return result

    def get_refund_stats(self) -> Dict[str, Any]:
        """Get refund agent statistics."""
        return {
            "total_pending": len(self._pending_approvals),
            "parwa_limit": self.PARWA_REFUND_LIMIT,
            "variant": self.get_variant(),
            "tier": self.get_tier(),
            "escalation_threshold": self._parwa_config.escalation_threshold,
        }
