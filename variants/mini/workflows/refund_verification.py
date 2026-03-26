"""
PARWA Mini Refund Verification Workflow.

Handles refund request verification and approval creation.
CRITICAL: This workflow NEVER calls Paddle directly.
It creates pending_approval records for human review.
"""
from typing import Dict, Any, Optional
from variants.mini.tools.order_lookup import OrderLookupTool
from variants.mini.tools.refund_verification_tools import RefundVerificationTool
from variants.mini.tools.ticket_create import TicketCreateTool
from variants.mini.workflows.escalation import EscalationWorkflow
from variants.mini.config import MiniConfig, get_mini_config
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class RefundVerificationWorkflow:
    """
    Workflow for verifying and processing refund requests.

    CRITICAL: This workflow creates pending_approval records
    and NEVER calls Paddle directly. All refunds require
    human approval before processing.

    Steps:
    1. Verify order eligibility
    2. Check amount against Mini limit
    3. Create pending approval
    4. Return recommendation
    """

    def __init__(
        self,
        mini_config: Optional[MiniConfig] = None
    ) -> None:
        """
        Initialize refund verification workflow.

        Args:
            mini_config: Mini configuration
        """
        self._config = mini_config or get_mini_config()
        self._order_tool = OrderLookupTool()
        self._refund_tool = RefundVerificationTool()
        self._ticket_tool = TicketCreateTool()
        self._escalation_workflow = EscalationWorkflow(mini_config)

    async def execute(self, refund_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the refund verification workflow.

        CRITICAL: This creates pending_approval and NEVER
        calls Paddle directly.

        Args:
            refund_data: Dict with:
                - order_id: Order identifier
                - amount: Refund amount
                - reason: Refund reason
                - customer_id: Customer identifier
                - customer_email: Customer email

        Returns:
            Dict with workflow result
        """
        order_id = refund_data.get("order_id")
        amount = refund_data.get("amount", 0)
        reason = refund_data.get("reason", "Customer request")
        customer_id = refund_data.get("customer_id")
        customer_email = refund_data.get("customer_email")

        logger.info({
            "event": "refund_verification_workflow_started",
            "order_id": order_id,
            "amount": amount,
            "customer_id": customer_id,
        })

        # Step 1: Verify order eligibility
        eligibility = await self._refund_tool.verify_eligibility(order_id)

        if not eligibility.get("eligible"):
            return {
                "status": "not_eligible",
                "order_id": order_id,
                "reason": eligibility.get("reason"),
                "message": f"Order {order_id} is not eligible for refund. {eligibility.get('reason')}",
            }

        # Step 2: Validate amount against Mini limit
        amount_validation = self._refund_tool.validate_refund_amount(amount)

        if not amount_validation.get("valid"):
            return {
                "status": "invalid_amount",
                "order_id": order_id,
                "errors": amount_validation.get("error"),
                "message": "Invalid refund amount.",
            }

        # Step 3: Create pending approval (CRITICAL: never calls Paddle)
        approval_request = await self._refund_tool.create_approval_request({
            "order_id": order_id,
            "amount": amount,
            "reason": reason,
            "customer_id": customer_id,
            "customer_email": customer_email,
            "within_mini_limit": amount_validation.get("within_mini_limit", True),
        })

        # Step 4: Get recommendation
        recommendation = approval_request.get("recommendation", "REVIEW")

        # Step 5: Check if needs escalation
        needs_escalation = (
            not amount_validation.get("within_mini_limit", True) or
            recommendation == "DENY"
        )

        # Log CRITICAL verification that Paddle was NOT called
        logger.info({
            "event": "refund_approval_created",
            "approval_id": approval_request.get("approval_id"),
            "order_id": order_id,
            "amount": amount,
            "recommendation": recommendation,
            "within_limit": amount_validation.get("within_mini_limit"),
            # CRITICAL: Explicitly log no processor call
            "paddle_called": False,
            "payment_processor_called": False,
        })

        return {
            "status": "pending_approval",
            "approval_id": approval_request.get("approval_id"),
            "order_id": order_id,
            "amount": amount,
            "recommendation": recommendation,
            "within_mini_limit": amount_validation.get("within_mini_limit", True),
            "mini_limit": self._refund_tool.MINI_REFUND_LIMIT,
            "escalated": needs_escalation,
            # CRITICAL: Confirm no processor call
            "payment_processor_called": False,
            "message": self._format_message(recommendation, amount, needs_escalation),
        }

    async def execute_with_ticket(
        self,
        refund_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute refund verification and create a ticket.

        Args:
            refund_data: Refund request data

        Returns:
            Dict with workflow result including ticket ID
        """
        # Execute refund verification
        result = await self.execute(refund_data)

        # Create ticket for the refund request
        ticket_result = await self._ticket_tool.create(
            subject=f"Refund Request - {refund_data.get('order_id')}",
            description=f"""
Refund request for order {refund_data.get('order_id')}.
Amount: ${refund_data.get('amount')}
Reason: {refund_data.get('reason', 'Customer request')}
            """.strip(),
            priority="normal",
            customer_id=refund_data.get("customer_id"),
            customer_email=refund_data.get("customer_email"),
            metadata={
                "refund_approval_id": result.get("approval_id"),
                "refund_amount": refund_data.get("amount"),
                "refund_recommendation": result.get("recommendation"),
            },
        )

        result["ticket_id"] = ticket_result.get("ticket_id")

        return result

    async def check_status(self, approval_id: str) -> Dict[str, Any]:
        """
        Check the status of a refund approval.

        Args:
            approval_id: Approval identifier

        Returns:
            Dict with approval status
        """
        status = await self._refund_tool.check_approval_status(approval_id)

        if not status:
            return {
                "status": "not_found",
                "approval_id": approval_id,
                "message": "Approval request not found.",
            }

        return status

    async def escalate_over_limit(
        self,
        refund_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Escalate a refund that's over Mini limit.

        Args:
            refund_data: Refund request data

        Returns:
            Dict with escalation result
        """
        result = await self.execute(refund_data)

        if result.get("escalated"):
            # Trigger escalation workflow
            escalation_result = await self._escalation_workflow.execute({
                "ticket_id": result.get("approval_id"),
                "reason": "refund_over_limit",
                "confidence": 0.0,
                "customer_id": refund_data.get("customer_id"),
                "customer_email": refund_data.get("customer_email"),
            })
            result["escalation"] = escalation_result

        return result

    def _format_message(
        self,
        recommendation: str,
        amount: float,
        needs_escalation: bool
    ) -> str:
        """
        Format response message.

        Args:
            recommendation: Refund recommendation
            amount: Refund amount
            needs_escalation: Whether escalated

        Returns:
            Formatted message
        """
        if needs_escalation and amount > self._refund_tool.MINI_REFUND_LIMIT:
            return f"Refund request for ${amount:.2f} exceeds Mini limit of ${self._refund_tool.MINI_REFUND_LIMIT:.2f}. A human agent will review your request."

        if recommendation == "APPROVE":
            return f"Refund request for ${amount:.2f} has been submitted for approval. You will receive a confirmation shortly."

        if recommendation == "DENY":
            return "Your refund request requires additional review. A human agent will contact you."

        return f"Refund request for ${amount:.2f} has been submitted and is pending review."

    def get_workflow_name(self) -> str:
        """Get workflow name."""
        return "RefundVerificationWorkflow"

    def get_variant(self) -> str:
        """Get variant name."""
        return "mini"
