"""
PARWA Mini Refund Verification Tool.

Provides refund verification functionality for Mini PARWA agents.
CRITICAL: This tool creates pending_approval records and NEVER
processes refunds directly via Paddle.
"""
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import uuid
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class RefundVerificationTool:
    """
    Tool for verifying refund eligibility and creating approvals.

    CRITICAL: This tool NEVER calls Paddle directly. It only
    creates pending_approval records for human review.

    Provides:
    - Verify refund eligibility
    - Create approval requests
    - Get refund recommendations
    """

    MINI_REFUND_LIMIT = 50.0
    AUTO_APPROVE_THRESHOLD = 25.0

    def __init__(self) -> None:
        """Initialize refund verification tool."""
        self._approval_requests: Dict[str, Dict[str, Any]] = {}

    async def verify_eligibility(self, order_id: str) -> Dict[str, Any]:
        """
        Check if an order is eligible for refund.

        Args:
            order_id: Order identifier

        Returns:
            Dict with eligibility status and details
        """
        logger.info({
            "event": "refund_verify_eligibility",
            "order_id": order_id,
        })

        # Mock eligibility check
        # In production, this would check:
        # - Order exists
        # - Order not already refunded
        # - Order within refund window (30 days)
        # - Order belongs to requesting customer

        return {
            "order_id": order_id,
            "eligible": True,
            "reason": "Order is eligible for refund",
            "refund_window_days": 30,
            "verified_at": datetime.now(timezone.utc).isoformat(),
        }

    async def create_approval_request(
        self,
        refund_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a pending approval request for refund.

        CRITICAL: This method ONLY creates an approval request.
        It does NOT and MUST NOT call Paddle or any payment processor.

        Args:
            refund_data: Dict with refund details:
                - order_id: Order identifier
                - amount: Refund amount
                - reason: Refund reason
                - customer_id: Customer identifier

        Returns:
            Dict with approval request details
        """
        order_id = refund_data.get("order_id", "unknown")
        amount = refund_data.get("amount", 0)
        reason = refund_data.get("reason", "Customer request")

        # Generate approval ID
        approval_id = f"APR-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc).isoformat()

        # Get recommendation
        recommendation = self.get_recommendation(refund_data)

        # Check if within Mini limit
        within_limit = amount <= self.MINI_REFUND_LIMIT

        approval_request = {
            "approval_id": approval_id,
            "order_id": order_id,
            "amount": amount,
            "reason": reason,
            "recommendation": recommendation,
            "status": "pending",
            "within_mini_limit": within_limit,
            "mini_limit": self.MINI_REFUND_LIMIT,
            "created_at": now,
            "customer_id": refund_data.get("customer_id"),
            "customer_email": refund_data.get("customer_email"),
            # CRITICAL: No payment processor call
            "payment_processor_called": False,
            "processor": "paddle",  # Indicates Paddle would be used, but NOT called
            "approved_at": None,
            "approved_by": None,
        }

        self._approval_requests[approval_id] = approval_request

        logger.info({
            "event": "refund_approval_created",
            "approval_id": approval_id,
            "order_id": order_id,
            "amount": amount,
            "within_limit": within_limit,
            # CRITICAL: Explicitly log no processor call
            "paddle_called": False,
        })

        return approval_request

    def get_recommendation(self, refund_data: Dict[str, Any]) -> str:
        """
        Get refund recommendation based on data.

        Args:
            refund_data: Dict with refund details

        Returns:
            Recommendation: "APPROVE", "REVIEW", or "DENY"
        """
        amount = refund_data.get("amount", 0)
        has_fraud_indicators = refund_data.get("fraud_indicators", False)
        is_first_refund = refund_data.get("is_first_refund", True)
        order_age_days = refund_data.get("order_age_days", 0)

        # Fraud always denied
        if has_fraud_indicators:
            return "DENY"

        # Old orders need review
        if order_age_days > 14:
            return "REVIEW"

        # Over Mini limit needs review
        if amount > self.MINI_REFUND_LIMIT:
            return "REVIEW"

        # Small first refunds can be auto-approved for review
        if is_first_refund and amount <= self.AUTO_APPROVE_THRESHOLD:
            return "APPROVE"

        # Everything else needs review
        return "REVIEW"

    async def check_approval_status(self, approval_id: str) -> Optional[Dict[str, Any]]:
        """
        Check the status of an approval request.

        Args:
            approval_id: Approval identifier

        Returns:
            Approval request status or None if not found
        """
        request = self._approval_requests.get(approval_id)
        if not request:
            return None

        return {
            "approval_id": approval_id,
            "status": request.get("status"),
            "recommendation": request.get("recommendation"),
            "amount": request.get("amount"),
        }

    async def approve(
        self,
        approval_id: str,
        approved_by: str
    ) -> Dict[str, Any]:
        """
        Mark an approval as approved.

        Note: This does NOT process the refund. It only updates
        the approval status. The actual refund processing happens
        in a separate system.

        Args:
            approval_id: Approval identifier
            approved_by: Who approved it

        Returns:
            Updated approval request
        """
        request = self._approval_requests.get(approval_id)
        if not request:
            return {
                "success": False,
                "error": "Approval request not found",
            }

        request["status"] = "approved"
        request["approved_at"] = datetime.now(timezone.utc).isoformat()
        request["approved_by"] = approved_by

        logger.info({
            "event": "refund_approval_approved",
            "approval_id": approval_id,
            "approved_by": approved_by,
        })

        return {
            "success": True,
            "approval_id": approval_id,
            "status": "approved",
            # Still no direct processor call from this tool
            "message": "Approval granted. Refund processing pending.",
        }

    async def deny(
        self,
        approval_id: str,
        denied_by: str,
        reason: str
    ) -> Dict[str, Any]:
        """
        Mark an approval as denied.

        Args:
            approval_id: Approval identifier
            denied_by: Who denied it
            reason: Denial reason

        Returns:
            Updated approval request
        """
        request = self._approval_requests.get(approval_id)
        if not request:
            return {
                "success": False,
                "error": "Approval request not found",
            }

        request["status"] = "denied"
        request["denied_at"] = datetime.now(timezone.utc).isoformat()
        request["denied_by"] = denied_by
        request["denial_reason"] = reason

        logger.info({
            "event": "refund_approval_denied",
            "approval_id": approval_id,
            "denied_by": denied_by,
            "reason": reason,
        })

        return {
            "success": True,
            "approval_id": approval_id,
            "status": "denied",
        }

    def validate_refund_amount(self, amount: float) -> Dict[str, Any]:
        """
        Validate refund amount against Mini limits.

        Args:
            amount: Refund amount

        Returns:
            Dict with validation result
        """
        if amount <= 0:
            return {
                "valid": False,
                "error": "Amount must be greater than 0",
            }

        if amount > self.MINI_REFUND_LIMIT:
            return {
                "valid": True,
                "within_mini_limit": False,
                "mini_limit": self.MINI_REFUND_LIMIT,
                "message": f"Amount exceeds Mini limit of ${self.MINI_REFUND_LIMIT}. Will require escalation.",
            }

        return {
            "valid": True,
            "within_mini_limit": True,
            "mini_limit": self.MINI_REFUND_LIMIT,
        }

    def get_pending_count(self) -> int:
        """Get count of pending approval requests."""
        return sum(
            1 for r in self._approval_requests.values()
            if r.get("status") == "pending"
        )

    def get_approval_stats(self) -> Dict[str, int]:
        """Get approval statistics."""
        stats = {"pending": 0, "approved": 0, "denied": 0}
        for request in self._approval_requests.values():
            status = request.get("status", "pending")
            stats[status] = stats.get(status, 0) + 1
        return stats
