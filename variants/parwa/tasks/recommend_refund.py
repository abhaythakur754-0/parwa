"""
PARWA Junior Recommend Refund Task.

Task for generating refund recommendations with APPROVE/REVIEW/DENY reasoning.
CRITICAL: This task NEVER executes refunds - only provides recommendations.

PARWA Junior Features:
- Refund limit: $500
- Returns APPROVE/REVIEW/DENY with full reasoning
- Uses Medium AI tier for analysis
- Creates pending_approval records
"""
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum

from variants.parwa.config import ParwaConfig, get_parwa_config
from variants.parwa.workflows.refund_recommendation import (
    RefundRecommendationWorkflow,
    RefundDecision,
    RefundReasoning,
)
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class RefundRecommendationStatus(Enum):
    """Status of refund recommendation."""
    GENERATED = "generated"
    PENDING_APPROVAL = "pending_approval"
    OVER_LIMIT = "over_limit"
    NOT_ELIGIBLE = "not_eligible"
    ERROR = "error"


@dataclass
class RefundRecommendationResult:
    """Result from recommend refund task."""
    success: bool
    recommendation_id: Optional[str] = None
    decision: RefundDecision = RefundDecision.REVIEW
    reasoning: Optional[RefundReasoning] = None
    status: RefundRecommendationStatus = RefundRecommendationStatus.GENERATED
    amount: Decimal = Decimal("0.00")
    within_parwa_limit: bool = True
    confidence: float = 0.0
    approval_id: Optional[str] = None
    paddle_called: bool = False  # CRITICAL: Always False
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class RecommendRefundTask:
    """
    Task for generating refund recommendations with full reasoning.

    This task uses the RefundRecommendationWorkflow to analyze refund
    requests and provide APPROVE/REVIEW/DENY recommendations with
    detailed reasoning.

    CRITICAL: This task NEVER executes refunds or calls Paddle directly.
    It only generates recommendations and creates pending_approval records.

    Example:
        task = RecommendRefundTask()
        result = await task.execute({
            "order_id": "ord_123",
            "amount": 150.00,
            "customer_id": "cust_456",
            "reason": "Product not as described"
        })
        # result.decision = RefundDecision.REVIEW
        # result.reasoning.primary_reason = "Amount requires verification..."
    """

    # PARWA Junior refund limits
    PARWA_REFUND_LIMIT = Decimal("500.00")

    def __init__(
        self,
        parwa_config: Optional[ParwaConfig] = None,
        workflow: Optional[RefundRecommendationWorkflow] = None,
    ) -> None:
        """
        Initialize recommend refund task.

        Args:
            parwa_config: PARWA Junior configuration
            workflow: Optional workflow instance
        """
        self._config = parwa_config or get_parwa_config()
        self._workflow = workflow or RefundRecommendationWorkflow(parwa_config)

    async def execute(self, input_data: Dict[str, Any]) -> RefundRecommendationResult:
        """
        Execute the refund recommendation task.

        Args:
            input_data: Dict with:
                - order_id: Order identifier
                - amount: Refund amount
                - reason: Refund reason
                - customer_id: Customer identifier
                - customer_email: Customer email (optional)
                - customer_history: Customer history data (optional)
                - order_age_days: Order age in days (optional)

        Returns:
            RefundRecommendationResult with recommendation

        CRITICAL: This task NEVER executes the refund.
        It only generates recommendations.
        """
        order_id = input_data.get("order_id", "")
        amount = Decimal(str(input_data.get("amount", 0)))

        recommendation_id = f"rec_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{order_id}"

        logger.info({
            "event": "recommend_refund_task_started",
            "recommendation_id": recommendation_id,
            "order_id": order_id,
            "amount": str(amount),
        })

        try:
            # Use workflow to generate recommendation
            workflow_result = await self._workflow.execute(input_data)

            # Build result
            result = RefundRecommendationResult(
                success=workflow_result.success,
                recommendation_id=recommendation_id,
                decision=workflow_result.decision,
                reasoning=workflow_result.reasoning,
                amount=workflow_result.amount,
                within_parwa_limit=workflow_result.within_parwa_limit,
                confidence=workflow_result.reasoning.confidence if workflow_result.reasoning else 0.0,
                approval_id=workflow_result.approval_id,
                paddle_called=False,  # CRITICAL: Always False
                message=workflow_result.message,
                metadata={
                    "variant": "parwa",
                    "tier": "medium",
                    "workflow_status": workflow_result.status.value,
                    **workflow_result.metadata,
                },
            )

            # Determine status
            if not workflow_result.within_parwa_limit:
                result.status = RefundRecommendationStatus.OVER_LIMIT
            elif workflow_result.decision == RefundDecision.DENY:
                result.status = RefundRecommendationStatus.NOT_ELIGIBLE
            elif workflow_result.approval_id:
                result.status = RefundRecommendationStatus.PENDING_APPROVAL
            else:
                result.status = RefundRecommendationStatus.GENERATED

            logger.info({
                "event": "recommend_refund_task_complete",
                "recommendation_id": recommendation_id,
                "decision": result.decision.value,
                "status": result.status.value,
                "confidence": result.confidence,
                # CRITICAL: Log no processor call
                "paddle_called": False,
            })

            return result

        except Exception as e:
            logger.error({
                "event": "recommend_refund_task_error",
                "recommendation_id": recommendation_id,
                "error": str(e),
            })
            return RefundRecommendationResult(
                success=False,
                recommendation_id=recommendation_id,
                status=RefundRecommendationStatus.ERROR,
                amount=amount,
                message=f"Error generating recommendation: {str(e)}",
                metadata={"error": str(e)},
            )

    def get_parwa_limit(self) -> Decimal:
        """Get PARWA Junior refund limit."""
        return self.PARWA_REFUND_LIMIT

    def get_task_name(self) -> str:
        """Get task name."""
        return "recommend_refund"

    def get_variant(self) -> str:
        """Get variant name."""
        return "parwa"

    def get_tier(self) -> str:
        """Get tier used."""
        return "medium"
