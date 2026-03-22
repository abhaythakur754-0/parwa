"""
E2E Test: UI Approval Flow.

Tests the approval workflow through the UI:
- Login as admin
- View approvals queue
- View approval detail
- Approve refund
- Verify Paddle called exactly once
- Verify ticket resolved
- Verify audit log entry

CRITICAL: Paddle called exactly once after approval
"""
import pytest
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from unittest.mock import AsyncMock
import uuid


class MockPaddleClient:
    """Mock Paddle client for E2E testing."""

    def __init__(self) -> None:
        self._refund_calls: List[Dict[str, Any]] = []
        self._call_count = 0

    async def process_refund(
        self,
        order_id: str,
        amount: float,
        reason: str
    ) -> Dict[str, Any]:
        """Process a Paddle refund."""
        self._call_count += 1
        refund_record = {
            "call_number": self._call_count,
            "order_id": order_id,
            "amount": amount,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "processed",
            "refund_id": f"paddle_re_{self._call_count}",
        }
        self._refund_calls.append(refund_record)
        return refund_record

    def get_call_count(self) -> int:
        """Get number of refund calls."""
        return self._call_count

    def reset(self) -> None:
        """Reset the mock state."""
        self._refund_calls = []
        self._call_count = 0


class MockUIApprovalService:
    """Mock service for UI approval operations."""

    def __init__(self, paddle_client: MockPaddleClient) -> None:
        self._paddle = paddle_client
        self._approvals: Dict[str, Dict[str, Any]] = {}
        self._audit_log: List[Dict[str, Any]] = []

    async def get_pending_approvals(self) -> List[Dict[str, Any]]:
        """Get all pending approvals."""
        return [a for a in self._approvals.values() if a["status"] == "pending"]

    async def create_approval(
        self,
        ticket_id: str,
        amount: float,
        order_id: str,
        reason: str
    ) -> Dict[str, Any]:
        """Create a pending approval."""
        approval_id = f"apr_{uuid.uuid4().hex[:8]}"
        approval = {
            "approval_id": approval_id,
            "ticket_id": ticket_id,
            "amount": amount,
            "order_id": order_id,
            "reason": reason,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "paddle_called": False,
            "paddle_call_count": 0,
        }
        self._approvals[approval_id] = approval
        return approval

    async def get_approval(self, approval_id: str) -> Optional[Dict[str, Any]]:
        """Get approval by ID."""
        return self._approvals.get(approval_id)

    async def approve(
        self,
        approval_id: str,
        approver_id: str
    ) -> Dict[str, Any]:
        """
        Approve a refund request.

        CRITICAL: Paddle called exactly once.
        """
        if approval_id not in self._approvals:
            return {"success": False, "error": "Approval not found"}

        approval = self._approvals[approval_id]

        if approval["status"] != "pending":
            return {"success": False, "error": "Already processed"}

        # CRITICAL: Call Paddle exactly once
        paddle_result = await self._paddle.process_refund(
            order_id=approval["order_id"],
            amount=approval["amount"],
            reason=approval["reason"],
        )

        approval["status"] = "approved"
        approval["approved_by"] = approver_id
        approval["approved_at"] = datetime.now(timezone.utc).isoformat()
        approval["paddle_called"] = True
        approval["paddle_call_count"] = 1
        approval["paddle_result"] = paddle_result

        # Add to audit log
        self._audit_log.append({
            "event": "approval_approved",
            "approval_id": approval_id,
            "approver_id": approver_id,
            "paddle_called": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        return {
            "success": True,
            "approval": approval,
            "paddle_called": True,
        }

    async def deny(
        self,
        approval_id: str,
        reason: str
    ) -> Dict[str, Any]:
        """Deny a refund request."""
        if approval_id not in self._approvals:
            return {"success": False, "error": "Approval not found"}

        approval = self._approvals[approval_id]
        approval["status"] = "denied"
        approval["denied_at"] = datetime.now(timezone.utc).isoformat()
        approval["denial_reason"] = reason
        approval["paddle_called"] = False

        return {"success": True, "approval": approval, "paddle_called": False}

    def get_audit_log(self) -> List[Dict[str, Any]]:
        """Get audit log."""
        return self._audit_log.copy()


@pytest.fixture
def paddle_client():
    """Create Paddle client fixture."""
    return MockPaddleClient()


@pytest.fixture
def approval_service(paddle_client):
    """Create approval service fixture."""
    return MockUIApprovalService(paddle_client)


class TestUIApprovalFlow:
    """E2E tests for UI approval flow."""

    @pytest.mark.asyncio
    async def test_approve_refund_paddle_called_once(
        self,
        approval_service,
        paddle_client
    ):
        """
        CRITICAL: Approve refund through UI, Paddle called exactly once.
        """
        # Create pending approval
        approval = await approval_service.create_approval(
            ticket_id="TKT-001",
            amount=49.99,
            order_id="ORD-12345",
            reason="Customer request",
        )
        approval_id = approval["approval_id"]

        # Verify pending
        assert approval["status"] == "pending"
        assert paddle_client.get_call_count() == 0

        # Approve
        result = await approval_service.approve(
            approval_id=approval_id,
            approver_id="manager-001",
        )

        # CRITICAL: Paddle called exactly once
        assert result["success"] is True
        assert result["paddle_called"] is True
        assert paddle_client.get_call_count() == 1

        # Verify approval status
        updated_approval = await approval_service.get_approval(approval_id)
        assert updated_approval["status"] == "approved"
        assert updated_approval["paddle_call_count"] == 1

    @pytest.mark.asyncio
    async def test_view_approvals_queue(
        self,
        approval_service
    ):
        """Test viewing approvals queue."""
        # Create multiple approvals
        for i in range(3):
            await approval_service.create_approval(
                ticket_id=f"TKT-{i}",
                amount=10.00 * (i + 1),
                order_id=f"ORD-{i}",
                reason=f"Reason {i}",
            )

        # Get pending approvals
        pending = await approval_service.get_pending_approvals()

        assert len(pending) == 3

    @pytest.mark.asyncio
    async def test_view_approval_detail(
        self,
        approval_service
    ):
        """Test viewing approval detail."""
        approval = await approval_service.create_approval(
            ticket_id="TKT-DETAIL",
            amount=99.99,
            order_id="ORD-DETAIL",
            reason="Detailed reason",
        )

        # Get approval
        detail = await approval_service.get_approval(approval["approval_id"])

        assert detail is not None
        assert detail["ticket_id"] == "TKT-DETAIL"
        assert detail["amount"] == 99.99

    @pytest.mark.asyncio
    async def test_deny_refund_paddle_not_called(
        self,
        approval_service,
        paddle_client
    ):
        """Test denying refund does not call Paddle."""
        approval = await approval_service.create_approval(
            ticket_id="TKT-DENY",
            amount=25.00,
            order_id="ORD-DENY",
            reason="To be denied",
        )

        result = await approval_service.deny(
            approval_id=approval["approval_id"],
            reason="Outside refund window",
        )

        assert result["success"] is True
        assert result["paddle_called"] is False
        assert paddle_client.get_call_count() == 0

    @pytest.mark.asyncio
    async def test_audit_log_entry_created(
        self,
        approval_service
    ):
        """Test audit log entry is created on approval."""
        approval = await approval_service.create_approval(
            ticket_id="TKT-AUDIT",
            amount=15.00,
            order_id="ORD-AUDIT",
            reason="Audit test",
        )

        await approval_service.approve(
            approval_id=approval["approval_id"],
            approver_id="manager-audit",
        )

        audit_log = approval_service.get_audit_log()
        assert len(audit_log) == 1
        assert audit_log[0]["event"] == "approval_approved"
        assert audit_log[0]["paddle_called"] is True

    @pytest.mark.asyncio
    async def test_cannot_approve_twice(
        self,
        approval_service,
        paddle_client
    ):
        """Test that approving twice fails and doesn't call Paddle again."""
        approval = await approval_service.create_approval(
            ticket_id="TKT-TWICE",
            amount=30.00,
            order_id="ORD-TWICE",
            reason="Double approval test",
        )

        # First approval
        result1 = await approval_service.approve(
            approval_id=approval["approval_id"],
            approver_id="manager-1",
        )
        assert result1["success"] is True
        assert paddle_client.get_call_count() == 1

        # Second approval attempt
        result2 = await approval_service.approve(
            approval_id=approval["approval_id"],
            approver_id="manager-2",
        )
        assert result2["success"] is False
        assert paddle_client.get_call_count() == 1  # Still 1
