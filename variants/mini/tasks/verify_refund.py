"""
PARWA Mini Verify Refund Task.

Task for verifying refund requests using the Mini Refund agent.
CRITICAL: NEVER executes refund without approval - only verifies.

Payment Processor: Paddle (Merchant of Record)
"""
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum

from variants.mini.agents.refund_agent import MiniRefundAgent
from variants.mini.config import MiniConfig, get_mini_config
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class RefundStatus(Enum):
    """Refund verification status."""
    ELIGIBLE = "eligible"  # Can be processed
    PENDING_APPROVAL = "pending_approval"  # Needs human approval
    NOT_ELIGIBLE = "not_eligible"  # Cannot be refunded
    EXCEEDED_LIMIT = "exceeded_limit"  # Over Mini $50 limit
    ALREADY_REFUNDED = "already_refunded"


@dataclass
class RefundTaskResult:
    """Result from verify refund task."""
    success: bool
    refund_id: Optional[str] = None
    status: RefundStatus = RefundStatus.PENDING_APPROVAL
    amount: Decimal = Decimal("0.00")
    currency: str = "USD"
    confidence: float = 0.0
    reason: Optional[str] = None
    paddle_call_required: bool = False  # Always FALSE for Mini - only verification
    approval_required: bool = True  # ALWAYS TRUE - Mini never auto-executes
    estimated_processing_days: int = 5
    rejection_reason: Optional[str] = None


class VerifyRefundTask:
    """
    Task for verifying refund requests.

    Uses MiniRefundAgent to:
    1. Verify refund eligibility
    2. Check amount limits ($50 max for Mini)
    3. Create pending_approval record
    4. NEVER execute refund without approval

    CRITICAL RULES:
    - Mini variant: $50 refund limit
    - NEVER call Paddle without pending_approval
    - All refunds require human approval in Mini

    Example:
        task = VerifyRefundTask()
        result = await task.execute({
            "order_id": "ord_123",
            "amount": 25.00,
            "reason": "Product defective",
            "customer_id": "cust_456"
        })
    """

    # Mini variant refund limit
    MAX_REFUND_AMOUNT = Decimal("50.00")

    # Refund eligibility time window (days)
    REFUND_WINDOW_DAYS = 30

    def __init__(
        self,
        mini_config: Optional[MiniConfig] = None,
        agent_id: str = "mini_refund_task"
    ) -> None:
        """
        Initialize verify refund task.

        Args:
            mini_config: Mini configuration
            agent_id: Agent identifier
        """
        self._config = mini_config or get_mini_config()
        self._agent = MiniRefundAgent(
            agent_id=agent_id,
            mini_config=self._config
        )

    async def execute(self, input_data: Dict[str, Any]) -> RefundTaskResult:
        """
        Execute the verify refund task.

        Args:
            input_data: Must contain:
                - order_id: Order identifier
                - amount: Refund amount
                - reason: Refund reason
                - customer_id: Customer identifier
                - currency: Optional currency (default USD)

        Returns:
            RefundTaskResult with verification status

        CRITICAL: This task NEVER executes the refund.
        It only verifies and creates pending_approval.
        """
        order_id = input_data.get("order_id", "")
        amount = Decimal(str(input_data.get("amount", 0)))
        reason = input_data.get("reason", "")
        customer_id = input_data.get("customer_id", "")
        currency = input_data.get("currency", "USD")

        logger.info({
            "event": "refund_verify_task_started",
            "order_id": order_id,
            "amount": str(amount),
            "currency": currency,
            "customer_id": customer_id,
        })

        # Generate refund ID
        refund_id = f"ref_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{order_id}"

        # Check amount limit (CRITICAL for Mini)
        if amount > self.MAX_REFUND_AMOUNT:
            logger.warning({
                "event": "refund_limit_exceeded",
                "amount": str(amount),
                "limit": str(self.MAX_REFUND_AMOUNT),
                "variant": "mini",
            })
            return RefundTaskResult(
                success=False,
                refund_id=refund_id,
                status=RefundStatus.EXCEEDED_LIMIT,
                amount=amount,
                currency=currency,
                rejection_reason=f"Amount ${amount} exceeds Mini limit of ${self.MAX_REFUND_AMOUNT}. Escalate to PARWA or PARWA High.",
                paddle_call_required=False,  # NEVER call Paddle
                approval_required=True,
            )

        # Process through Mini Refund agent
        response = await self._agent.process({
            "refund_id": refund_id,
            "order_id": order_id,
            "amount": float(amount),
            "reason": reason,
            "customer_id": customer_id,
            "currency": currency
        })

        # Build result
        result = RefundTaskResult(
            success=response.success,
            refund_id=refund_id,
            amount=amount,
            currency=currency,
            confidence=response.confidence,
            paddle_call_required=False,  # NEVER TRUE for Mini
            approval_required=True,  # ALWAYS TRUE for Mini
        )

        if response.success:
            data = response.data or {}
            status_str = data.get("status", "pending_approval")

            try:
                result.status = RefundStatus(status_str)
            except ValueError:
                result.status = RefundStatus.PENDING_APPROVAL

            result.reason = data.get("reason")

            # Log CRITICAL: Paddle NOT called
            logger.info({
                "event": "refund_verification_complete",
                "refund_id": refund_id,
                "status": result.status.value,
                "paddle_called": False,  # CRITICAL: Always False for verification
                "approval_required": True,  # CRITICAL: Always True for Mini
            })
        else:
            result.status = RefundStatus.NOT_ELIGIBLE
            result.rejection_reason = response.message

        return result

    def check_limit(self, amount: Decimal) -> bool:
        """
        Check if amount is within Mini limit.

        Args:
            amount: Refund amount

        Returns:
            True if within limit
        """
        return amount <= self.MAX_REFUND_AMOUNT

    def get_max_refund(self) -> Decimal:
        """Get maximum refund amount for Mini."""
        return self.MAX_REFUND_AMOUNT

    def get_task_name(self) -> str:
        """Get task name."""
        return "verify_refund"

    def get_variant(self) -> str:
        """Get variant name."""
        return "mini"

    def get_tier(self) -> str:
        """Get tier used."""
        return "light"
