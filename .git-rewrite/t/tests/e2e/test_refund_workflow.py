"""
E2E Test: Refund Workflow.

Tests the complete refund workflow with CRITICAL verification:
- Stripe called EXACTLY once after approval
- Stripe NEVER called before approval
- Audit trail hash chain validates
- Refund gate is enforced

Steps:
1. Create ticket
2. Request refund
3. Pending approval
4. Approve
5. Stripe call (EXACTLY once)
"""
import pytest
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from unittest.mock import AsyncMock, MagicMock
import hashlib
import uuid
import json

from tests.e2e import E2ETestHelper, MockStripeClient


class RefundWorkflowState:
    """Tracks the state of a refund workflow."""

    def __init__(self) -> None:
        """Initialize workflow state."""
        self.ticket_id: Optional[str] = None
        self.approval_id: Optional[str] = None
        self.amount: float = 0.0
        self.status: str = "created"
        self.stripe_calls: int = 0
        self.audit_trail: List[Dict[str, Any]] = []
        self.approval_timestamp: Optional[datetime] = None


class MockRefundWorkflowService:
    """Mock service for refund workflow testing."""

    # Hash chain for audit trail
    GENESIS_HASH = "0" * 64

    def __init__(self, stripe_client: MockStripeClient) -> None:
        """
        Initialize mock refund workflow service.

        Args:
            stripe_client: Mock Stripe client for tracking calls
        """
        self._stripe = stripe_client
        self._tickets: Dict[str, Dict[str, Any]] = {}
        self._approvals: Dict[str, Dict[str, Any]] = {}
        self._audit_entries: Dict[str, List[Dict[str, Any]]] = {}
        self._workflow_states: Dict[str, RefundWorkflowState] = {}

    async def create_ticket(
        self,
        company_id: str,
        customer_id: str,
        subject: str,
        description: str
    ) -> Dict[str, Any]:
        """
        Create a support ticket.

        Args:
            company_id: Company ID
            customer_id: Customer ID
            subject: Ticket subject
            description: Ticket description

        Returns:
            Created ticket
        """
        ticket_id = f"TKT-{uuid.uuid4().hex[:8].upper()}"

        ticket = {
            "ticket_id": ticket_id,
            "company_id": company_id,
            "customer_id": customer_id,
            "subject": subject,
            "description": description,
            "status": "open",
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        self._tickets[ticket_id] = ticket
        self._audit_entries[ticket_id] = []

        # Add audit entry
        await self._add_audit_entry(
            ticket_id=ticket_id,
            event="ticket_created",
            data={"customer_id": customer_id}
        )

        return ticket

    async def request_refund(
        self,
        ticket_id: str,
        amount: float,
        transaction_id: str,
        reason: str
    ) -> Dict[str, Any]:
        """
        Request a refund for a ticket.

        CRITICAL: This should NOT call Stripe.

        Args:
            ticket_id: Ticket ID
            amount: Refund amount
            transaction_id: Original transaction ID
            reason: Refund reason

        Returns:
            Refund request result with approval ID
        """
        if ticket_id not in self._tickets:
            return {"success": False, "error": "Ticket not found"}

        approval_id = f"APR-{uuid.uuid4().hex[:8].upper()}"

        approval = {
            "approval_id": approval_id,
            "ticket_id": ticket_id,
            "amount": amount,
            "transaction_id": transaction_id,
            "reason": reason,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "stripe_called": False,  # CRITICAL: Not called yet
            "stripe_call_count": 0
        }

        self._approvals[approval_id] = approval

        # Track workflow state
        state = RefundWorkflowState()
        state.ticket_id = ticket_id
        state.approval_id = approval_id
        state.amount = amount
        state.status = "pending_approval"
        self._workflow_states[ticket_id] = state

        # Add audit entry
        await self._add_audit_entry(
            ticket_id=ticket_id,
            event="refund_requested",
            data={
                "approval_id": approval_id,
                "amount": amount,
                "stripe_called": False  # CRITICAL
            }
        )

        return {
            "success": True,
            "approval_id": approval_id,
            "ticket_id": ticket_id,
            "amount": amount,
            "status": "pending_approval",
            "stripe_called": False  # CRITICAL: Not called yet
        }

    async def approve_refund(
        self,
        approval_id: str,
        approver_id: str
    ) -> Dict[str, Any]:
        """
        Approve a refund request.

        CRITICAL: Stripe should be called EXACTLY once here.

        Args:
            approval_id: Approval ID
            approver_id: Approver ID

        Returns:
            Approval result
        """
        if approval_id not in self._approvals:
            return {"success": False, "error": "Approval not found"}

        approval = self._approvals[approval_id]
        ticket_id = approval["ticket_id"]

        # Check if already processed
        if approval["status"] == "approved":
            return {
                "success": False,
                "error": "Already approved",
                "stripe_already_called": True
            }

        # Update approval status
        approval["status"] = "approved"
        approval["approved_by"] = approver_id
        approval["approved_at"] = datetime.now(timezone.utc).isoformat()

        # CRITICAL: Call Stripe EXACTLY once
        stripe_result = await self._stripe.process_refund(
            amount=approval["amount"],
            transaction_id=approval["transaction_id"],
            reason=approval["reason"]
        )

        # CRITICAL: Mark Stripe as called
        approval["stripe_called"] = True
        approval["stripe_call_count"] = approval.get("stripe_call_count", 0) + 1
        approval["stripe_result"] = stripe_result

        # Update workflow state
        if ticket_id in self._workflow_states:
            state = self._workflow_states[ticket_id]
            state.status = "approved"
            state.stripe_calls = approval["stripe_call_count"]
            state.approval_timestamp = datetime.now(timezone.utc)

        # Add audit entry
        await self._add_audit_entry(
            ticket_id=ticket_id,
            event="refund_approved",
            data={
                "approval_id": approval_id,
                "approver_id": approver_id,
                "stripe_called": True,  # CRITICAL: Called now
                "stripe_call_count": approval["stripe_call_count"]
            }
        )

        return {
            "success": True,
            "approval_id": approval_id,
            "ticket_id": ticket_id,
            "status": "approved",
            "stripe_called": True,
            "stripe_result": stripe_result
        }

    async def reject_refund(
        self,
        approval_id: str,
        reason: str
    ) -> Dict[str, Any]:
        """
        Reject a refund request.

        CRITICAL: Stripe should NOT be called for rejection.

        Args:
            approval_id: Approval ID
            reason: Rejection reason

        Returns:
            Rejection result
        """
        if approval_id not in self._approvals:
            return {"success": False, "error": "Approval not found"}

        approval = self._approvals[approval_id]
        ticket_id = approval["ticket_id"]

        approval["status"] = "rejected"
        approval["rejected_at"] = datetime.now(timezone.utc).isoformat()
        approval["rejection_reason"] = reason
        approval["stripe_called"] = False  # CRITICAL: Not called

        # Add audit entry
        await self._add_audit_entry(
            ticket_id=ticket_id,
            event="refund_rejected",
            data={
                "approval_id": approval_id,
                "reason": reason,
                "stripe_called": False  # CRITICAL
            }
        )

        return {
            "success": True,
            "approval_id": approval_id,
            "status": "rejected",
            "stripe_called": False  # CRITICAL: Not called
        }

    async def get_approval_status(
        self,
        approval_id: str
    ) -> Dict[str, Any]:
        """
        Get approval status.

        Args:
            approval_id: Approval ID

        Returns:
            Approval status
        """
        if approval_id not in self._approvals:
            return {"success": False, "error": "Approval not found"}

        approval = self._approvals[approval_id]
        return {
            "success": True,
            "approval_id": approval_id,
            "ticket_id": approval["ticket_id"],
            "status": approval["status"],
            "amount": approval["amount"],
            "stripe_called": approval.get("stripe_called", False),
            "stripe_call_count": approval.get("stripe_call_count", 0)
        }

    async def get_audit_trail(
        self,
        ticket_id: str
    ) -> Dict[str, Any]:
        """
        Get audit trail for a ticket.

        Args:
            ticket_id: Ticket ID

        Returns:
            Audit trail with hash chain
        """
        if ticket_id not in self._audit_entries:
            return {"success": False, "error": "Ticket not found"}

        entries = self._audit_entries[ticket_id]
        return {
            "success": True,
            "ticket_id": ticket_id,
            "entries": entries,
            "valid": self._validate_hash_chain(entries)
        }

    def get_stripe_call_count(self) -> int:
        """
        Get total number of Stripe calls.

        Returns:
            Number of Stripe refund calls
        """
        return self._stripe.get_call_count()

    async def _add_audit_entry(
        self,
        ticket_id: str,
        event: str,
        data: Dict[str, Any]
    ) -> None:
        """
        Add an entry to the audit trail.

        Args:
            ticket_id: Ticket ID
            event: Event type
            data: Event data
        """
        entries = self._audit_entries.get(ticket_id, [])
        prev_hash = entries[-1]["hash"] if entries else self.GENESIS_HASH

        entry = {
            "event": event,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "prev_hash": prev_hash
        }

        # Calculate hash
        entry_json = json.dumps(entry, sort_keys=True)
        entry["hash"] = hashlib.sha256(entry_json.encode()).hexdigest()

        entries.append(entry)
        self._audit_entries[ticket_id] = entries

    def _validate_hash_chain(self, entries: List[Dict[str, Any]]) -> bool:
        """
        Validate the hash chain of audit entries.

        Args:
            entries: List of audit entries

        Returns:
            True if hash chain is valid
        """
        if not entries:
            return True

        # Check genesis
        if entries[0]["prev_hash"] != self.GENESIS_HASH:
            return False

        # Validate chain
        for i in range(1, len(entries)):
            if entries[i]["prev_hash"] != entries[i - 1]["hash"]:
                return False

        return True


@pytest.fixture
def stripe_client():
    """Create mock Stripe client fixture."""
    return MockStripeClient()


@pytest.fixture
def refund_service(stripe_client):
    """Create refund workflow service fixture."""
    return MockRefundWorkflowService(stripe_client)


class TestE2ERefundWorkflow:
    """E2E tests for refund workflow with CRITICAL Stripe verification."""

    @pytest.mark.asyncio
    async def test_complete_refund_workflow_stripe_called_once(
        self,
        refund_service,
        stripe_client
    ):
        """
        CRITICAL: Test complete refund workflow.

        Steps:
        1. Create ticket
        2. Request refund (Stripe NOT called)
        3. Approve refund (Stripe called EXACTLY once)
        4. Verify audit trail
        """
        # Step 1: Create ticket
        ticket = await refund_service.create_ticket(
            company_id="company-123",
            customer_id="customer-456",
            subject="Defective product",
            description="Product arrived damaged"
        )

        assert ticket["status"] == "open"
        assert ticket["ticket_id"] is not None
        ticket_id = ticket["ticket_id"]

        # Step 2: Request refund - CRITICAL: Stripe NOT called
        refund_request = await refund_service.request_refund(
            ticket_id=ticket_id,
            amount=99.99,
            transaction_id="txn_original_123",
            reason="Product defective"
        )

        assert refund_request["success"] is True
        assert refund_request["status"] == "pending_approval"
        assert refund_request["stripe_called"] is False, \
            "CRITICAL: Stripe should NOT be called on refund request"

        # Verify Stripe has NOT been called
        assert stripe_client.get_call_count() == 0, \
            "CRITICAL: Stripe call count should be 0 before approval"

        approval_id = refund_request["approval_id"]

        # Step 3: Approve refund - CRITICAL: Stripe called EXACTLY once
        approval = await refund_service.approve_refund(
            approval_id=approval_id,
            approver_id="manager-001"
        )

        assert approval["success"] is True
        assert approval["status"] == "approved"
        assert approval["stripe_called"] is True, \
            "CRITICAL: Stripe should be called on approval"

        # CRITICAL: Verify Stripe called EXACTLY once
        assert stripe_client.get_call_count() == 1, \
            f"CRITICAL: Stripe should be called EXACTLY once, got {stripe_client.get_call_count()}"

        # Step 4: Verify audit trail
        audit = await refund_service.get_audit_trail(ticket_id)

        assert audit["success"] is True
        assert audit["valid"] is True, "Audit trail hash chain should be valid"

        # Verify events in audit trail
        events = [e["event"] for e in audit["entries"]]
        assert "ticket_created" in events
        assert "refund_requested" in events
        assert "refund_approved" in events

    @pytest.mark.asyncio
    async def test_stripe_not_called_before_approval(
        self,
        refund_service,
        stripe_client
    ):
        """CRITICAL: Stripe must NOT be called before approval."""
        # Create ticket
        ticket = await refund_service.create_ticket(
            company_id="company-123",
            customer_id="customer-456",
            subject="Wrong item",
            description="Received wrong item"
        )

        # Request refund
        refund_request = await refund_service.request_refund(
            ticket_id=ticket["ticket_id"],
            amount=50.00,
            transaction_id="txn_wrong_item",
            reason="Wrong item shipped"
        )

        # CRITICAL: Verify Stripe NOT called
        assert refund_request["stripe_called"] is False
        assert stripe_client.get_call_count() == 0

        # Check approval status
        status = await refund_service.get_approval_status(
            refund_request["approval_id"]
        )

        assert status["stripe_called"] is False
        assert status["stripe_call_count"] == 0

    @pytest.mark.asyncio
    async def test_stripe_called_exactly_once_after_approval(
        self,
        refund_service,
        stripe_client
    ):
        """CRITICAL: Stripe must be called EXACTLY once after approval."""
        # Setup
        ticket = await refund_service.create_ticket(
            company_id="company-123",
            customer_id="customer-456",
            subject="Duplicate charge",
            description="Charged twice"
        )

        refund_request = await refund_service.request_refund(
            ticket_id=ticket["ticket_id"],
            amount=25.00,
            transaction_id="txn_duplicate",
            reason="Duplicate charge"
        )

        # Before approval
        assert stripe_client.get_call_count() == 0

        # Approve
        await refund_service.approve_refund(
            approval_id=refund_request["approval_id"],
            approver_id="manager-001"
        )

        # CRITICAL: Exactly 1 call
        assert stripe_client.get_call_count() == 1

        # Try to approve again (should fail)
        result = await refund_service.approve_refund(
            approval_id=refund_request["approval_id"],
            approver_id="manager-002"
        )

        assert result["success"] is False

        # CRITICAL: Still exactly 1 call
        assert stripe_client.get_call_count() == 1, \
            "CRITICAL: Duplicate approval should not trigger another Stripe call"

    @pytest.mark.asyncio
    async def test_stripe_not_called_on_rejection(
        self,
        refund_service,
        stripe_client
    ):
        """CRITICAL: Stripe must NOT be called when refund is rejected."""
        # Setup
        ticket = await refund_service.create_ticket(
            company_id="company-123",
            customer_id="customer-456",
            subject="Refund request",
            description="Customer wants refund"
        )

        refund_request = await refund_service.request_refund(
            ticket_id=ticket["ticket_id"],
            amount=100.00,
            transaction_id="txn_reject_test",
            reason="Customer request"
        )

        # Before rejection
        assert stripe_client.get_call_count() == 0

        # Reject
        result = await refund_service.reject_refund(
            approval_id=refund_request["approval_id"],
            reason="Outside refund window"
        )

        assert result["success"] is True
        assert result["stripe_called"] is False

        # CRITICAL: No Stripe calls
        assert stripe_client.get_call_count() == 0

    @pytest.mark.asyncio
    async def test_audit_trail_hash_chain_validates(
        self,
        refund_service
    ):
        """Test that audit trail hash chain validates correctly."""
        # Create and process refund
        ticket = await refund_service.create_ticket(
            company_id="company-123",
            customer_id="customer-456",
            subject="Test audit",
            description="Testing audit trail"
        )

        refund_request = await refund_service.request_refund(
            ticket_id=ticket["ticket_id"],
            amount=10.00,
            transaction_id="txn_audit_test",
            reason="Audit test"
        )

        await refund_service.approve_refund(
            approval_id=refund_request["approval_id"],
            approver_id="manager-001"
        )

        # Get audit trail
        audit = await refund_service.get_audit_trail(ticket["ticket_id"])

        # Verify chain
        assert audit["valid"] is True
        assert len(audit["entries"]) >= 3  # Created, requested, approved

        # Verify each entry has required fields
        for entry in audit["entries"]:
            assert "event" in entry
            assert "hash" in entry
            assert "prev_hash" in entry
            assert "timestamp" in entry

    @pytest.mark.asyncio
    async def test_multiple_refunds_independent_stripe_calls(
        self,
        refund_service,
        stripe_client
    ):
        """Test multiple refunds trigger independent Stripe calls."""
        refund_ids = []

        # Create and approve 3 refunds
        for i in range(3):
            ticket = await refund_service.create_ticket(
                company_id="company-123",
                customer_id=f"customer-{i}",
                subject=f"Refund {i}",
                description="Test"
            )

            refund_request = await refund_service.request_refund(
                ticket_id=ticket["ticket_id"],
                amount=10.00 * (i + 1),
                transaction_id=f"txn_multi_{i}",
                reason="Test"
            )

            await refund_service.approve_refund(
                approval_id=refund_request["approval_id"],
                approver_id="manager-001"
            )

            refund_ids.append(refund_request["approval_id"])

        # CRITICAL: Each refund should have exactly 1 Stripe call
        assert stripe_client.get_call_count() == 3

        # Each approval status should show 1 call
        for approval_id in refund_ids:
            status = await refund_service.get_approval_status(approval_id)
            assert status["stripe_call_count"] == 1


class TestE2ERefundWorkflowEdgeCases:
    """E2E tests for refund workflow edge cases."""

    @pytest.mark.asyncio
    async def test_approval_not_found(self, refund_service):
        """Test handling of non-existent approval."""
        result = await refund_service.approve_refund(
            approval_id="nonexistent-id",
            approver_id="manager-001"
        )

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_rejection_not_found(self, refund_service):
        """Test handling of non-existent rejection."""
        result = await refund_service.reject_refund(
            approval_id="nonexistent-id",
            reason="Test"
        )

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_audit_trail_not_found(self, refund_service):
        """Test handling of non-existent audit trail."""
        result = await refund_service.get_audit_trail("nonexistent-ticket")

        assert result["success"] is False
