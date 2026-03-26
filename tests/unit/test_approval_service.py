"""
Unit tests for Approval Service.

CRITICAL TESTS:
- pending_approval created
- Paddle NOT called before approval
- Paddle called EXACTLY once after approval
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from backend.services.approval_service import (
    ApprovalService,
    ApprovalStatus,
    ApprovalType,
    ApprovalRecord,
)


@pytest.fixture
def mock_db():
    """Mock database session."""
    return AsyncMock()


@pytest.fixture
def mock_paddle_client():
    """Mock Paddle client."""
    client = AsyncMock()
    client.process_refund = AsyncMock(return_value={
        "transaction_id": "txn_test_123",
        "status": "processed",
    })
    return client


@pytest.fixture
def approval_service(mock_db, mock_paddle_client):
    """Create approval service instance."""
    company_id = uuid4()
    service = ApprovalService(mock_db, company_id, mock_paddle_client)
    return service


class TestApprovalServiceCreatePending:
    """Tests for create_pending_approval method."""

    @pytest.mark.asyncio
    async def test_create_pending_approval_success(self, approval_service):
        """Test successful creation of pending approval."""
        result = await approval_service.create_pending_approval(
            ticket_id="ticket-123",
            amount=50.0,
            approval_type=ApprovalType.REFUND,
            created_by="user-1",
        )

        assert result["status"] == ApprovalStatus.PENDING.value
        assert result["ticket_id"] == "ticket-123"
        assert result["amount"] == 50.0
        assert result["paddle_called"] is False  # CRITICAL

    @pytest.mark.asyncio
    async def test_create_pending_approval_generates_unique_id(self, approval_service):
        """Test that each approval gets a unique ID."""
        result1 = await approval_service.create_pending_approval(
            ticket_id="ticket-1",
            amount=10.0,
        )
        result2 = await approval_service.create_pending_approval(
            ticket_id="ticket-2",
            amount=20.0,
        )

        assert result1["approval_id"] != result2["approval_id"]

    @pytest.mark.asyncio
    async def test_create_pending_approval_sets_expiry(self, approval_service):
        """Test that approval has expiry time."""
        result = await approval_service.create_pending_approval(
            ticket_id="ticket-123",
            amount=50.0,
        )

        assert "expires_at" in result
        expires_at = datetime.fromisoformat(result["expires_at"].replace("Z", "+00:00"))
        assert expires_at > datetime.now(timezone.utc)


class TestApprovalServiceApprove:
    """Tests for approve method - CRITICAL."""

    @pytest.mark.asyncio
    async def test_approve_calls_paddle_exactly_once(self, approval_service, mock_paddle_client):
        """CRITICAL: Paddle called EXACTLY once after approval."""
        # Create pending approval
        pending = await approval_service.create_pending_approval(
            ticket_id="ticket-123",
            amount=50.0,
            metadata={"transaction_id": "txn_original"},
        )
        approval_id = pending["approval_id"]

        # Verify Paddle not called yet
        assert approval_service._paddle_called.get(approval_id) is False

        # Approve
        result = await approval_service.approve(
            approval_id=approval_id,
            approver_id="manager-1",
        )

        # CRITICAL: Verify Paddle called exactly once
        assert result["success"] is True
        assert result["paddle_called"] is True
        assert mock_paddle_client.process_refund.call_count == 1

    @pytest.mark.asyncio
    async def test_approve_blocks_duplicate_paddle_calls(self, approval_service, mock_paddle_client):
        """CRITICAL: Block duplicate Paddle calls."""
        # Create and approve
        pending = await approval_service.create_pending_approval(
            ticket_id="ticket-123",
            amount=50.0,
        )
        approval_id = pending["approval_id"]

        # First approval
        result1 = await approval_service.approve(approval_id, "manager-1")
        assert result1["success"] is True

        # Try to approve again (should fail)
        result2 = await approval_service.approve(approval_id, "manager-2")
        assert result2["success"] is False
        assert "already" in result2.get("error", "").lower() or "blocked" in result2.get("error", "").lower()

        # Verify Paddle still only called once
        assert mock_paddle_client.process_refund.call_count == 1

    @pytest.mark.asyncio
    async def test_approve_nonexistent_approval_fails(self, approval_service):
        """Test approving non-existent approval fails."""
        result = await approval_service.approve(
            approval_id="nonexistent-id",
            approver_id="manager-1",
        )

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_approve_sets_approved_status(self, approval_service):
        """Test that approval status is updated."""
        pending = await approval_service.create_pending_approval(
            ticket_id="ticket-123",
            amount=50.0,
        )
        approval_id = pending["approval_id"]

        result = await approval_service.approve(approval_id, "manager-1")

        assert result["status"] == ApprovalStatus.APPROVED.value
        assert result["approved_by"] == "manager-1"


class TestApprovalServiceReject:
    """Tests for reject method."""

    @pytest.mark.asyncio
    async def test_reject_does_not_call_paddle(self, approval_service, mock_paddle_client):
        """CRITICAL: Paddle NOT called when rejecting."""
        pending = await approval_service.create_pending_approval(
            ticket_id="ticket-123",
            amount=50.0,
        )
        approval_id = pending["approval_id"]

        result = await approval_service.reject(
            approval_id=approval_id,
            reason="Customer not eligible",
            rejected_by="manager-1",
        )

        assert result["success"] is True
        assert result["paddle_called"] is False
        assert mock_paddle_client.process_refund.call_count == 0

    @pytest.mark.asyncio
    async def test_reject_sets_status(self, approval_service):
        """Test that reject sets proper status."""
        pending = await approval_service.create_pending_approval(
            ticket_id="ticket-123",
            amount=50.0,
        )
        approval_id = pending["approval_id"]

        result = await approval_service.reject(
            approval_id=approval_id,
            reason="Invalid request",
        )

        assert result["status"] == ApprovalStatus.REJECTED.value


class TestApprovalServiceGetStatus:
    """Tests for get_approval_status method."""

    @pytest.mark.asyncio
    async def test_get_status_returns_correct_info(self, approval_service):
        """Test that status retrieval works."""
        pending = await approval_service.create_pending_approval(
            ticket_id="ticket-123",
            amount=50.0,
        )
        approval_id = pending["approval_id"]

        status = await approval_service.get_approval_status(approval_id)

        assert status["success"] is True
        assert status["status"] == ApprovalStatus.PENDING.value
        assert status["amount"] == 50.0


class TestApprovalServiceValidateAmount:
    """Tests for validate_refund_amount method."""

    @pytest.mark.asyncio
    async def test_validate_amount_within_limit(self, approval_service):
        """Test amount within tier limit."""
        result = await approval_service.validate_refund_amount(
            amount=40.0,
            tier="mini",
        )

        assert result["is_valid"] is True
        assert result["max_allowed"] == 50.0

    @pytest.mark.asyncio
    async def test_validate_amount_exceeds_limit(self, approval_service):
        """Test amount exceeding tier limit."""
        result = await approval_service.validate_refund_amount(
            amount=100.0,
            tier="mini",
        )

        assert result["is_valid"] is False
        assert result["exceeds_limit"] is True

    @pytest.mark.asyncio
    async def test_validate_amount_parwa_high_tier(self, approval_service):
        """Test amount for PARWA High tier."""
        result = await approval_service.validate_refund_amount(
            amount=1500.0,
            tier="parwa_high",
        )

        assert result["is_valid"] is True
        assert result["max_allowed"] == 2000.0


class TestApprovalServiceCancel:
    """Tests for cancel_approval method."""

    @pytest.mark.asyncio
    async def test_cancel_pending_approval(self, approval_service):
        """Test cancelling a pending approval."""
        pending = await approval_service.create_pending_approval(
            ticket_id="ticket-123",
            amount=50.0,
        )
        approval_id = pending["approval_id"]

        result = await approval_service.cancel_approval(approval_id, "user-1")

        assert result["success"] is True
        assert result["status"] == ApprovalStatus.CANCELLED.value

    @pytest.mark.asyncio
    async def test_cancel_approved_approval_fails(self, approval_service):
        """Test that approved approvals cannot be cancelled."""
        pending = await approval_service.create_pending_approval(
            ticket_id="ticket-123",
            amount=50.0,
        )
        approval_id = pending["approval_id"]

        # Approve first
        await approval_service.approve(approval_id, "manager-1")

        # Try to cancel
        result = await approval_service.cancel_approval(approval_id, "user-1")

        assert result["success"] is False
