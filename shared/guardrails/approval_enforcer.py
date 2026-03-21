"""
PARWA Approval Enforcer.

Enforces approval gates for sensitive actions including:
- Refunds and financial transactions
- Account modifications
- Data exports and deletions

CRITICAL: This enforcer NEVER allows direct execution of sensitive
actions. It only creates pending_approval records that require
human or system approval before execution.
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from enum import Enum
import uuid
import hashlib

from pydantic import BaseModel, Field, ConfigDict

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class ApprovalStatus(str, Enum):
    """Status of an approval request."""
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class ApprovalAction(str, Enum):
    """Actions that require approval."""
    REFUND = "refund"
    REFUND_PARTIAL = "refund_partial"
    REFUND_FULL = "refund_full"
    ACCOUNT_DELETE = "account_delete"
    DATA_EXPORT = "data_export"
    SUBSCRIPTION_CANCEL = "subscription_cancel"
    SUBSCRIPTION_DOWNGRADE = "subscription_downgrade"
    CREDIT_ISSUE = "credit_issue"
    DISCOUNT_APPLY = "discount_apply"
    PRICE_OVERRIDE = "price_override"
    TICKET_ESCALATE = "ticket_escalate"
    VIP_STATUS_CHANGE = "vip_status_change"


class ApprovalRequest(BaseModel):
    """Approval request model."""
    approval_id: str
    action: ApprovalAction
    status: ApprovalStatus = ApprovalStatus.PENDING
    context: Dict[str, Any] = Field(default_factory=dict)
    amount: Optional[float] = None
    requested_by: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    denial_reason: Optional[str] = None
    bypass_attempts: int = Field(default=0)
    audit_trail: List[Dict[str, Any]] = Field(default_factory=list)

    model_config = ConfigDict(use_enum_values=True)


class ApprovalConfig(BaseModel):
    """Configuration for approval enforcer."""
    # Amount thresholds requiring approval
    refund_approval_threshold: float = Field(default=50.0)
    credit_approval_threshold: float = Field(default=25.0)
    discount_approval_threshold: float = Field(default=20.0)

    # Approval expiry time (hours)
    approval_expiry_hours: int = Field(default=24)

    # Auto-approve settings (NOT for refunds - always require approval)
    auto_approve_vip_credits: bool = Field(default=False)
    auto_approve_small_refunds: bool = Field(default=False)  # NEVER TRUE for safety

    # Bypass prevention
    max_bypass_attempts: int = Field(default=3)
    bypass_lockout_hours: int = Field(default=24)

    model_config = ConfigDict()


# Approval requirements by action
APPROVAL_REQUIREMENTS: Dict[str, Dict[str, Any]] = {
    ApprovalAction.REFUND.value: {
        "requires_approval": True,
        "never_auto_approve": True,
        "min_approver_level": "agent",
        "notification_required": True,
    },
    ApprovalAction.REFUND_PARTIAL.value: {
        "requires_approval": True,
        "never_auto_approve": True,
        "min_approver_level": "agent",
        "notification_required": True,
    },
    ApprovalAction.REFUND_FULL.value: {
        "requires_approval": True,
        "never_auto_approve": True,
        "min_approver_level": "team_lead",
        "notification_required": True,
    },
    ApprovalAction.ACCOUNT_DELETE.value: {
        "requires_approval": True,
        "never_auto_approve": False,
        "min_approver_level": "manager",
        "notification_required": True,
    },
    ApprovalAction.DATA_EXPORT.value: {
        "requires_approval": True,
        "never_auto_approve": False,
        "min_approver_level": "agent",
        "notification_required": False,
    },
    ApprovalAction.CREDIT_ISSUE.value: {
        "requires_approval": True,
        "never_auto_approve": False,
        "min_approver_level": "agent",
        "notification_required": True,
    },
    ApprovalAction.PRICE_OVERRIDE.value: {
        "requires_approval": True,
        "never_auto_approve": False,
        "min_approver_level": "manager",
        "notification_required": True,
    },
}


class ApprovalEnforcer:
    """
    Approval Gate Enforcer for PARWA.

    CRITICAL: This class NEVER executes sensitive actions directly.
    It ONLY creates pending_approval records that must be approved
    through a separate approval workflow.

    The enforcer:
    - Checks if actions require approval
    - Creates pending approval requests
    - Verifies approval status before action execution
    - Blocks and logs bypass attempts
    - Maintains audit trail of all approval operations

    Example:
        enforcer = ApprovalEnforcer()

        # Check if approval needed
        if enforcer.check_approval_required("refund", amount=100.0):
            # Create pending approval (NOT execute refund)
            approval = enforcer.create_pending_approval(
                "refund",
                {"order_id": "123", "amount": 100.0}
            )
            # Return approval_id for later verification
            return {"status": "pending_approval", "approval_id": approval["approval_id"]}
    """

    def __init__(
        self,
        config: Optional[ApprovalConfig] = None
    ) -> None:
        """
        Initialize Approval Enforcer.

        Args:
            config: Optional configuration override
        """
        self.config = config or ApprovalConfig()
        self._pending_approvals: Dict[str, ApprovalRequest] = {}
        self._bypass_attempts: Dict[str, List[datetime]] = {}
        self._audit_log: List[Dict[str, Any]] = []

        # Stats
        self._approvals_created = 0
        self._approvals_approved = 0
        self._approvals_denied = 0
        self._bypass_attempts_blocked = 0

        logger.info({
            "event": "approval_enforcer_initialized",
            "refund_threshold": self.config.refund_approval_threshold,
            "expiry_hours": self.config.approval_expiry_hours,
        })

    def check_approval_required(
        self,
        action: str,
        amount: Optional[float] = None
    ) -> bool:
        """
        Check if an action requires approval.

        Args:
            action: Action to check
            amount: Optional amount for threshold checks

        Returns:
            True if approval is required
        """
        # Get action requirements
        requirements = APPROVAL_REQUIREMENTS.get(action, {})

        if not requirements.get("requires_approval", False):
            return False

        # For refunds, ALWAYS require approval (safety rule)
        if action in [
            ApprovalAction.REFUND.value,
            ApprovalAction.REFUND_PARTIAL.value,
            ApprovalAction.REFUND_FULL.value
        ]:
            return True

        # Check amount thresholds
        if amount is not None:
            if action == ApprovalAction.CREDIT_ISSUE.value:
                return amount >= self.config.credit_approval_threshold
            if action == ApprovalAction.DISCOUNT_APPLY.value:
                return amount >= self.config.discount_approval_threshold

        return True

    def create_pending_approval(
        self,
        action: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a pending approval request.

        CRITICAL: This does NOT execute the action. It only creates
        a pending_approval record that must be approved separately.

        Args:
            action: Action requiring approval
            context: Context for the approval (order_id, amount, etc.)

        Returns:
            Dict with approval_id and status
        """
        # Generate approval ID
        approval_id = self._generate_approval_id(action, context)

        # Calculate expiry
        expires_at = datetime.now() + timedelta(hours=self.config.approval_expiry_hours)

        # Extract amount if present
        amount = context.get("amount")

        # Create approval request
        request = ApprovalRequest(
            approval_id=approval_id,
            action=ApprovalAction(action),
            status=ApprovalStatus.PENDING,
            context=context,
            amount=amount,
            requested_by=context.get("requested_by"),
            expires_at=expires_at,
            audit_trail=[{
                "event": "created",
                "timestamp": datetime.now().isoformat(),
                "action": action,
                "context_keys": list(context.keys()),
            }]
        )

        self._pending_approvals[approval_id] = request
        self._approvals_created += 1

        # Add to audit log
        self._log_audit("approval_created", {
            "approval_id": approval_id,
            "action": action,
            "amount": amount,
        })

        logger.info({
            "event": "pending_approval_created",
            "approval_id": approval_id,
            "action": action,
            "amount": amount,
            "expires_at": expires_at.isoformat(),
        })

        return {
            "approval_id": approval_id,
            "status": ApprovalStatus.PENDING.value,
            "action": action,
            "amount": amount,
            "expires_at": expires_at.isoformat(),
            "message": f"Approval required for {action}. Approval ID: {approval_id}",
        }

    def verify_approval(
        self,
        approval_id: str
    ) -> Dict[str, Any]:
        """
        Verify the status of an approval request.

        Args:
            approval_id: Approval ID to verify

        Returns:
            Dict with approval status and details
        """
        request = self._pending_approvals.get(approval_id)

        if not request:
            return {
                "valid": False,
                "status": "not_found",
                "message": f"Approval {approval_id} not found",
            }

        # Check if expired
        if request.expires_at and datetime.now() > request.expires_at:
            request.status = ApprovalStatus.EXPIRED
            return {
                "valid": False,
                "status": ApprovalStatus.EXPIRED.value,
                "message": "Approval has expired",
                "approval_id": approval_id,
            }

        return {
            "valid": request.status == ApprovalStatus.APPROVED or request.status == ApprovalStatus.APPROVED.value,
            "status": request.status.value if hasattr(request.status, 'value') else request.status,
            "approval_id": approval_id,
            "action": request.action.value if hasattr(request.action, 'value') else request.action,
            "amount": request.amount,
            "approved_by": request.approved_by,
            "approved_at": request.approved_at.isoformat() if request.approved_at else None,
        }

    def block_bypass_attempt(
        self,
        action: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Block and log a bypass attempt.

        Called when someone tries to execute a sensitive action
        without proper approval.

        Args:
            action: Action attempted
            context: Context of the attempt

        Returns:
            Dict with blocked status
        """
        # Track bypass attempts by source
        source = context.get("source", "unknown")
        if source not in self._bypass_attempts:
            self._bypass_attempts[source] = []

        self._bypass_attempts[source].append(datetime.now())
        self._bypass_attempts_blocked += 1

        # Check for lockout
        recent_attempts = [
            t for t in self._bypass_attempts[source]
            if datetime.now() - t < timedelta(hours=self.config.bypass_lockout_hours)
        ]

        locked = len(recent_attempts) >= self.config.max_bypass_attempts

        # Log the bypass attempt
        self._log_audit("bypass_blocked", {
            "action": action,
            "source": source,
            "attempt_count": len(recent_attempts),
            "locked": locked,
        })

        logger.warning({
            "event": "bypass_attempt_blocked",
            "action": action,
            "source": source,
            "attempt_count": len(recent_attempts),
            "locked": locked,
        })

        return {
            "blocked": True,
            "action": action,
            "reason": "Action requires approval - bypass not allowed",
            "attempt_count": len(recent_attempts),
            "locked": locked,
            "message": (
                f"Bypass attempt blocked. {len(recent_attempts)} attempts recorded. "
                f"{'Account locked for approval requests.' if locked else ''}"
            ),
        }

    def get_approval_status(
        self,
        approval_id: str
    ) -> str:
        """
        Get the status of an approval.

        Args:
            approval_id: Approval ID to check

        Returns:
            Status string: pending/approved/denied/expired/cancelled/not_found
        """
        request = self._pending_approvals.get(approval_id)

        if not request:
            return "not_found"

        return request.status.value if hasattr(request.status, 'value') else request.status

    def approve(
        self,
        approval_id: str,
        approver: str
    ) -> Dict[str, Any]:
        """
        Approve a pending request.

        This is called by the approval workflow, NOT by the action executor.

        Args:
            approval_id: Approval ID to approve
            approver: Who approved it

        Returns:
            Dict with approval status
        """
        request = self._pending_approvals.get(approval_id)

        if not request:
            return {
                "success": False,
                "message": f"Approval {approval_id} not found",
            }

        if request.status != ApprovalStatus.PENDING:
            return {
                "success": False,
                "message": f"Approval already {request.status.value}",
            }

        # Update status
        request.status = ApprovalStatus.APPROVED
        request.approved_by = approver
        request.approved_at = datetime.now()
        request.audit_trail.append({
            "event": "approved",
            "timestamp": datetime.now().isoformat(),
            "approver": approver,
        })

        self._approvals_approved += 1

        self._log_audit("approval_approved", {
            "approval_id": approval_id,
            "approver": approver,
        })

        logger.info({
            "event": "approval_approved",
            "approval_id": approval_id,
            "approver": approver,
        })

        return {
            "success": True,
            "status": ApprovalStatus.APPROVED.value,
            "approval_id": approval_id,
            "approved_by": approver,
            "approved_at": request.approved_at.isoformat(),
        }

    def deny(
        self,
        approval_id: str,
        reason: str,
        denier: str
    ) -> Dict[str, Any]:
        """
        Deny a pending request.

        Args:
            approval_id: Approval ID to deny
            reason: Reason for denial
            denier: Who denied it

        Returns:
            Dict with denial status
        """
        request = self._pending_approvals.get(approval_id)

        if not request:
            return {
                "success": False,
                "message": f"Approval {approval_id} not found",
            }

        if request.status != ApprovalStatus.PENDING:
            return {
                "success": False,
                "message": f"Approval already {request.status.value}",
            }

        # Update status
        request.status = ApprovalStatus.DENIED
        request.denial_reason = reason
        request.audit_trail.append({
            "event": "denied",
            "timestamp": datetime.now().isoformat(),
            "reason": reason,
            "denier": denier,
        })

        self._approvals_denied += 1

        logger.info({
            "event": "approval_denied",
            "approval_id": approval_id,
            "reason": reason,
            "denier": denier,
        })

        return {
            "success": True,
            "status": ApprovalStatus.DENIED.value,
            "approval_id": approval_id,
            "reason": reason,
        }

    def get_stats(self) -> Dict[str, Any]:
        """
        Get enforcer statistics.

        Returns:
            Dict with stats
        """
        return {
            "approvals_created": self._approvals_created,
            "approvals_approved": self._approvals_approved,
            "approvals_denied": self._approvals_denied,
            "approval_rate": (
                self._approvals_approved / self._approvals_created
                if self._approvals_created > 0 else 0
            ),
            "bypass_attempts_blocked": self._bypass_attempts_blocked,
            "pending_count": sum(
                1 for r in self._pending_approvals.values()
                if r.status == ApprovalStatus.PENDING
            ),
        }

    def _generate_approval_id(
        self,
        action: str,
        context: Dict[str, Any]
    ) -> str:
        """Generate unique approval ID."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        hash_input = f"{action}:{timestamp}:{context.get('order_id', '')}"
        short_hash = hashlib.md5(hash_input.encode()).hexdigest()[:8]
        return f"APR-{action.upper()[:4]}-{short_hash}"

    def _log_audit(self, event: str, data: Dict[str, Any]) -> None:
        """Log to audit trail."""
        self._audit_log.append({
            "timestamp": datetime.now().isoformat(),
            "event": event,
            **data,
        })


def get_approval_enforcer() -> ApprovalEnforcer:
    """
    Get an ApprovalEnforcer instance.

    Returns:
        ApprovalEnforcer instance
    """
    return ApprovalEnforcer()
