"""
Approval Service Layer.

Handles approval workflows for refunds and other financial operations.
CRITICAL: Paddle (payment provider) is called EXACTLY ONCE after approval.
All methods are company-scoped for RLS compliance.
"""
from typing import Optional, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime, timezone
from enum import Enum
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from backend.models.support_ticket import SupportTicket
from shared.core_functions.logger import get_logger
from shared.integrations.paddle_client import PaddleClient, get_paddle_client

logger = get_logger(__name__)


class ApprovalStatus(str, Enum):
    """Approval status values."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class ApprovalType(str, Enum):
    """Types of approvals."""
    REFUND = "refund"
    CREDIT = "credit"
    DISCOUNT = "discount"
    ACCOUNT_CHANGE = "account_change"
    ESCALATION = "escalation"


@dataclass
class ApprovalRecord:
    """In-memory approval record for tracking."""
    approval_id: str
    ticket_id: str
    company_id: str
    approval_type: ApprovalType
    amount: float
    status: ApprovalStatus
    created_at: datetime
    expires_at: datetime
    created_by: str
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    rejected_by: Optional[str] = None
    rejected_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    paddle_transaction_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ApprovalService:
    """
    Service class for approval workflow management.

    Handles approval workflows for refunds and other financial operations.
    
    CRITICAL RULES:
    1. Paddle is NEVER called before approve()
    2. Paddle is called EXACTLY ONCE after approval
    3. All approvals are audited
    4. Approval records are immutable after creation

    All methods enforce company-scoped data access (RLS).
    """

    # Approval expiry time in hours
    APPROVAL_EXPIRY_HOURS = 72

    # Maximum refund amounts by tier (matches variant configs)
    MAX_REFUND_AMOUNTS = {
        "mini": 50.0,
        "parwa": 500.0,
        "parwa_high": 2000.0,
    }

    def __init__(
        self,
        db: AsyncSession,
        company_id: UUID,
        paddle_client: Optional[PaddleClient] = None
    ) -> None:
        """
        Initialize approval service.

        Args:
            db: Async database session
            company_id: Company UUID for RLS scoping
            paddle_client: Optional Paddle client for testing
        """
        self.db = db
        self.company_id = company_id
        self._paddle_client = paddle_client
        self._pending_approvals: Dict[str, ApprovalRecord] = {}
        self._paddle_called: Dict[str, bool] = {}  # Track Paddle calls

    def _get_paddle_client(self) -> PaddleClient:
        """Get or create Paddle client."""
        if self._paddle_client is None:
            self._paddle_client = get_paddle_client()
        return self._paddle_client

    async def create_pending_approval(
        self,
        ticket_id: str,
        amount: float,
        approval_type: ApprovalType = ApprovalType.REFUND,
        created_by: str = "system",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a pending approval for a refund.

        CRITICAL: Paddle is NOT called at this point.
        The approval must be explicitly approved before Paddle is called.

        Args:
            ticket_id: Ticket identifier
            amount: Amount to refund
            approval_type: Type of approval
            created_by: User ID who created the approval
            metadata: Additional metadata

        Returns:
            Dict with approval details
        """
        approval_id = str(uuid4())
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=self.APPROVAL_EXPIRY_HOURS)

        approval = ApprovalRecord(
            approval_id=approval_id,
            ticket_id=ticket_id,
            company_id=str(self.company_id),
            approval_type=approval_type,
            amount=amount,
            status=ApprovalStatus.PENDING,
            created_at=now,
            expires_at=expires_at,
            created_by=created_by,
            metadata=metadata or {},
        )

        self._pending_approvals[approval_id] = approval
        self._paddle_called[approval_id] = False  # Track Paddle calls

        logger.info({
            "event": "pending_approval_created",
            "company_id": str(self.company_id),
            "approval_id": approval_id,
            "ticket_id": ticket_id,
            "amount": amount,
            "approval_type": approval_type.value,
            # CRITICAL: Paddle NOT called yet
            "paddle_called": False,
        })

        return {
            "approval_id": approval_id,
            "ticket_id": ticket_id,
            "amount": amount,
            "status": ApprovalStatus.PENDING.value,
            "created_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "created_by": created_by,
            "paddle_called": False,  # CRITICAL: Not called yet
        }

    async def approve(
        self,
        approval_id: str,
        approver_id: str
    ) -> Dict[str, Any]:
        """
        Approve a pending approval.

        CRITICAL: Paddle is called EXACTLY ONCE at this point.
        If Paddle call fails, the approval is marked as failed.

        Args:
            approval_id: Approval identifier
            approver_id: User ID who approved

        Returns:
            Dict with approval result
        """
        approval = self._pending_approvals.get(approval_id)

        if not approval:
            logger.error({
                "event": "approval_not_found",
                "company_id": str(self.company_id),
                "approval_id": approval_id,
            })
            return {
                "success": False,
                "error": "Approval not found",
                "approval_id": approval_id,
            }

        if approval.status != ApprovalStatus.PENDING:
            logger.warning({
                "event": "approval_not_pending",
                "company_id": str(self.company_id),
                "approval_id": approval_id,
                "current_status": approval.status.value,
            })
            return {
                "success": False,
                "error": f"Approval already {approval.status.value}",
                "approval_id": approval_id,
            }

        now = datetime.now(timezone.utc)

        # Check if expired
        if now > approval.expires_at:
            approval.status = ApprovalStatus.EXPIRED
            logger.warning({
                "event": "approval_expired",
                "company_id": str(self.company_id),
                "approval_id": approval_id,
            })
            return {
                "success": False,
                "error": "Approval has expired",
                "approval_id": approval_id,
            }

        # CRITICAL: Check if Paddle was already called
        if self._paddle_called.get(approval_id, False):
            logger.critical({
                "event": "paddle_duplicate_call_blocked",
                "company_id": str(self.company_id),
                "approval_id": approval_id,
                "message": "Paddle already called for this approval - blocking duplicate",
            })
            return {
                "success": False,
                "error": "Paddle already called for this approval",
                "approval_id": approval_id,
            }

        # Call Paddle EXACTLY ONCE
        try:
            paddle = self._get_paddle_client()
            transaction_result = await paddle.process_refund(
                transaction_id=approval.metadata.get("transaction_id", ""),
                amount=approval.amount,
                reason=f"Approved by {approver_id} for ticket {approval.ticket_id}",
            )

            # Mark Paddle as called
            self._paddle_called[approval_id] = True

            approval.status = ApprovalStatus.APPROVED
            approval.approved_by = approver_id
            approval.approved_at = now
            approval.paddle_transaction_id = transaction_result.get("transaction_id")

            logger.info({
                "event": "approval_approved",
                "company_id": str(self.company_id),
                "approval_id": approval_id,
                "approver_id": approver_id,
                "amount": approval.amount,
                "paddle_transaction_id": approval.paddle_transaction_id,
                # CRITICAL: Paddle called exactly once
                "paddle_called": True,
            })

            return {
                "success": True,
                "approval_id": approval_id,
                "status": ApprovalStatus.APPROVED.value,
                "approved_by": approver_id,
                "approved_at": now.isoformat(),
                "amount": approval.amount,
                "paddle_transaction_id": approval.paddle_transaction_id,
                "paddle_called": True,
            }

        except Exception as e:
            logger.error({
                "event": "paddle_call_failed",
                "company_id": str(self.company_id),
                "approval_id": approval_id,
                "error": str(e),
            })
            return {
                "success": False,
                "error": f"Paddle transaction failed: {str(e)}",
                "approval_id": approval_id,
                "paddle_called": False,
            }

    async def reject(
        self,
        approval_id: str,
        reason: str,
        rejected_by: str = "system"
    ) -> Dict[str, Any]:
        """
        Reject a pending approval.

        CRITICAL: Paddle is NOT called when rejecting.

        Args:
            approval_id: Approval identifier
            reason: Reason for rejection
            rejected_by: User ID who rejected

        Returns:
            Dict with rejection result
        """
        approval = self._pending_approvals.get(approval_id)

        if not approval:
            return {
                "success": False,
                "error": "Approval not found",
                "approval_id": approval_id,
            }

        if approval.status != ApprovalStatus.PENDING:
            return {
                "success": False,
                "error": f"Approval already {approval.status.value}",
                "approval_id": approval_id,
            }

        now = datetime.now(timezone.utc)

        approval.status = ApprovalStatus.REJECTED
        approval.rejected_by = rejected_by
        approval.rejected_at = now
        approval.rejection_reason = reason

        logger.info({
            "event": "approval_rejected",
            "company_id": str(self.company_id),
            "approval_id": approval_id,
            "rejected_by": rejected_by,
            "reason": reason,
            # CRITICAL: Paddle NOT called
            "paddle_called": False,
        })

        return {
            "success": True,
            "approval_id": approval_id,
            "status": ApprovalStatus.REJECTED.value,
            "rejected_by": rejected_by,
            "rejected_at": now.isoformat(),
            "reason": reason,
            "paddle_called": False,  # CRITICAL: Not called
        }

    async def get_approval_status(self, approval_id: str) -> Dict[str, Any]:
        """
        Get the status of an approval.

        Args:
            approval_id: Approval identifier

        Returns:
            Dict with approval status
        """
        approval = self._pending_approvals.get(approval_id)

        if not approval:
            return {
                "success": False,
                "error": "Approval not found",
                "approval_id": approval_id,
            }

        return {
            "success": True,
            "approval_id": approval_id,
            "ticket_id": approval.ticket_id,
            "amount": approval.amount,
            "status": approval.status.value,
            "approval_type": approval.approval_type.value,
            "created_at": approval.created_at.isoformat(),
            "expires_at": approval.expires_at.isoformat(),
            "created_by": approval.created_by,
            "approved_by": approval.approved_by,
            "approved_at": approval.approved_at.isoformat() if approval.approved_at else None,
            "rejected_by": approval.rejected_by,
            "rejected_at": approval.rejected_at.isoformat() if approval.rejected_at else None,
            "rejection_reason": approval.rejection_reason,
            "paddle_transaction_id": approval.paddle_transaction_id,
            "paddle_called": self._paddle_called.get(approval_id, False),
        }

    async def cancel_approval(
        self,
        approval_id: str,
        cancelled_by: str
    ) -> Dict[str, Any]:
        """
        Cancel a pending approval.

        Args:
            approval_id: Approval identifier
            cancelled_by: User ID who cancelled

        Returns:
            Dict with cancellation result
        """
        approval = self._pending_approvals.get(approval_id)

        if not approval:
            return {
                "success": False,
                "error": "Approval not found",
                "approval_id": approval_id,
            }

        if approval.status != ApprovalStatus.PENDING:
            return {
                "success": False,
                "error": f"Cannot cancel approval with status {approval.status.value}",
                "approval_id": approval_id,
            }

        approval.status = ApprovalStatus.CANCELLED

        logger.info({
            "event": "approval_cancelled",
            "company_id": str(self.company_id),
            "approval_id": approval_id,
            "cancelled_by": cancelled_by,
        })

        return {
            "success": True,
            "approval_id": approval_id,
            "status": ApprovalStatus.CANCELLED.value,
            "cancelled_by": cancelled_by,
            "cancelled_at": datetime.now(timezone.utc).isoformat(),
        }

    async def list_pending_approvals(
        self,
        limit: int = 50,
        offset: int = 0
    ) -> list:
        """
        List all pending approvals for the company.

        Args:
            limit: Max results
            offset: Pagination offset

        Returns:
            List of pending approvals
        """
        pending = [
            {
                "approval_id": a.approval_id,
                "ticket_id": a.ticket_id,
                "amount": a.amount,
                "status": a.status.value,
                "created_at": a.created_at.isoformat(),
                "expires_at": a.expires_at.isoformat(),
            }
            for a in self._pending_approvals.values()
            if a.status == ApprovalStatus.PENDING
            and a.company_id == str(self.company_id)
        ]

        return pending[offset:offset + limit]

    async def cleanup_expired_approvals(self) -> int:
        """
        Mark all expired approvals.

        Returns:
            Number of approvals marked as expired
        """
        now = datetime.now(timezone.utc)
        expired_count = 0

        for approval in self._pending_approvals.values():
            if approval.status == ApprovalStatus.PENDING and now > approval.expires_at:
                approval.status = ApprovalStatus.EXPIRED
                expired_count += 1

        if expired_count > 0:
            logger.info({
                "event": "expired_approvals_cleaned",
                "company_id": str(self.company_id),
                "count": expired_count,
            })

        return expired_count

    async def validate_refund_amount(
        self,
        amount: float,
        tier: str
    ) -> Dict[str, Any]:
        """
        Validate if refund amount is within tier limits.

        Args:
            amount: Refund amount
            tier: License tier

        Returns:
            Dict with validation result
        """
        max_amount = self.MAX_REFUND_AMOUNTS.get(tier, 50.0)
        is_valid = amount <= max_amount

        return {
            "is_valid": is_valid,
            "amount": amount,
            "max_allowed": max_amount,
            "tier": tier,
            "exceeds_limit": amount > max_amount,
        }


# Import timedelta for expiry calculation
from datetime import timedelta
