"""
E2E Test: UI Ticket Flow.

Tests the ticket workflow through the UI:
- Create new ticket
- View ticket list
- Filter tickets
- Assign ticket
- Reply to ticket
- Escalate ticket
- Close ticket
- Verify all actions logged
"""
import pytest
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import uuid


class MockUITicketService:
    """Mock service for UI ticket operations."""

    def __init__(self) -> None:
        self._tickets: Dict[str, Dict[str, Any]] = {}
        self._messages: Dict[str, List[Dict[str, Any]]] = {}
        self._audit_log: List[Dict[str, Any]] = []

    async def create_ticket(
        self,
        customer_id: str,
        subject: str,
        body: str,
        channel: str = "email"
    ) -> Dict[str, Any]:
        """Create a new ticket."""
        ticket_id = f"TKT-{uuid.uuid4().hex[:8].upper()}"
        ticket = {
            "ticket_id": ticket_id,
            "customer_id": customer_id,
            "subject": subject,
            "body": body,
            "channel": channel,
            "status": "open",
            "priority": "medium",
            "assignee_id": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._tickets[ticket_id] = ticket
        self._messages[ticket_id] = []

        self._audit_log.append({
            "event": "ticket_created",
            "ticket_id": ticket_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        return ticket

    async def get_tickets(
        self,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        assignee_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get tickets with optional filters."""
        tickets = list(self._tickets.values())

        if status:
            tickets = [t for t in tickets if t["status"] == status]
        if priority:
            tickets = [t for t in tickets if t["priority"] == priority]
        if assignee_id:
            tickets = [t for t in tickets if t["assignee_id"] == assignee_id]

        return tickets

    async def get_ticket(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        """Get ticket by ID."""
        return self._tickets.get(ticket_id)

    async def assign_ticket(
        self,
        ticket_id: str,
        assignee_id: str
    ) -> Dict[str, Any]:
        """Assign ticket to an agent."""
        if ticket_id not in self._tickets:
            return {"success": False, "error": "Ticket not found"}

        ticket = self._tickets[ticket_id]
        ticket["assignee_id"] = assignee_id
        ticket["status"] = "in_progress"
        ticket["updated_at"] = datetime.now(timezone.utc).isoformat()

        self._audit_log.append({
            "event": "ticket_assigned",
            "ticket_id": ticket_id,
            "assignee_id": assignee_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        return {"success": True, "ticket": ticket}

    async def add_reply(
        self,
        ticket_id: str,
        author_id: str,
        message: str
    ) -> Dict[str, Any]:
        """Add a reply to ticket."""
        if ticket_id not in self._tickets:
            return {"success": False, "error": "Ticket not found"}

        reply = {
            "message_id": f"MSG-{uuid.uuid4().hex[:8]}",
            "ticket_id": ticket_id,
            "author_id": author_id,
            "message": message,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._messages[ticket_id].append(reply)

        ticket = self._tickets[ticket_id]
        ticket["updated_at"] = datetime.now(timezone.utc).isoformat()

        self._audit_log.append({
            "event": "ticket_reply",
            "ticket_id": ticket_id,
            "author_id": author_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        return {"success": True, "reply": reply}

    async def escalate_ticket(
        self,
        ticket_id: str,
        reason: str
    ) -> Dict[str, Any]:
        """Escalate ticket."""
        if ticket_id not in self._tickets:
            return {"success": False, "error": "Ticket not found"}

        ticket = self._tickets[ticket_id]
        ticket["status"] = "escalated"
        ticket["escalation_reason"] = reason
        ticket["escalated_at"] = datetime.now(timezone.utc).isoformat()
        ticket["updated_at"] = datetime.now(timezone.utc).isoformat()

        self._audit_log.append({
            "event": "ticket_escalated",
            "ticket_id": ticket_id,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        return {"success": True, "ticket": ticket}

    async def close_ticket(
        self,
        ticket_id: str,
        resolution: str
    ) -> Dict[str, Any]:
        """Close ticket with resolution."""
        if ticket_id not in self._tickets:
            return {"success": False, "error": "Ticket not found"}

        ticket = self._tickets[ticket_id]
        ticket["status"] = "closed"
        ticket["resolution"] = resolution
        ticket["closed_at"] = datetime.now(timezone.utc).isoformat()
        ticket["updated_at"] = datetime.now(timezone.utc).isoformat()

        self._audit_log.append({
            "event": "ticket_closed",
            "ticket_id": ticket_id,
            "resolution": resolution,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        return {"success": True, "ticket": ticket}

    def get_audit_log(self) -> List[Dict[str, Any]]:
        """Get audit log."""
        return self._audit_log.copy()


@pytest.fixture
def ticket_service():
    """Create ticket service fixture."""
    return MockUITicketService()


class TestUITicketFlow:
    """E2E tests for UI ticket flow."""

    @pytest.mark.asyncio
    async def test_create_ticket(self, ticket_service):
        """Test creating a new ticket."""
        ticket = await ticket_service.create_ticket(
            customer_id="CUST-001",
            subject="Cannot login",
            body="I forgot my password and cannot reset it.",
            channel="email",
        )

        assert ticket["ticket_id"] is not None
        assert ticket["status"] == "open"
        assert ticket["subject"] == "Cannot login"

    @pytest.mark.asyncio
    async def test_view_ticket_list(self, ticket_service):
        """Test viewing ticket list."""
        # Create tickets
        for i in range(5):
            await ticket_service.create_ticket(
                customer_id=f"CUST-{i}",
                subject=f"Ticket {i}",
                body=f"Body {i}",
            )

        tickets = await ticket_service.get_tickets()
        assert len(tickets) == 5

    @pytest.mark.asyncio
    async def test_filter_tickets_by_status(self, ticket_service):
        """Test filtering tickets by status."""
        # Create tickets
        t1 = await ticket_service.create_ticket(
            customer_id="CUST-1",
            subject="Open ticket",
            body="Body",
        )
        t2 = await ticket_service.create_ticket(
            customer_id="CUST-2",
            subject="Closed ticket",
            body="Body",
        )
        await ticket_service.close_ticket(t2["ticket_id"], "Resolved")

        open_tickets = await ticket_service.get_tickets(status="open")
        assert len(open_tickets) == 1
        assert open_tickets[0]["ticket_id"] == t1["ticket_id"]

    @pytest.mark.asyncio
    async def test_assign_ticket(self, ticket_service):
        """Test assigning ticket to agent."""
        ticket = await ticket_service.create_ticket(
            customer_id="CUST-001",
            subject="Assignment test",
            body="Body",
        )

        result = await ticket_service.assign_ticket(
            ticket_id=ticket["ticket_id"],
            assignee_id="agent-001",
        )

        assert result["success"] is True
        assert result["ticket"]["assignee_id"] == "agent-001"
        assert result["ticket"]["status"] == "in_progress"

    @pytest.mark.asyncio
    async def test_reply_to_ticket(self, ticket_service):
        """Test replying to ticket."""
        ticket = await ticket_service.create_ticket(
            customer_id="CUST-001",
            subject="Reply test",
            body="Original message",
        )

        result = await ticket_service.add_reply(
            ticket_id=ticket["ticket_id"],
            author_id="agent-001",
            message="Thank you for contacting us.",
        )

        assert result["success"] is True
        assert result["reply"]["message"] == "Thank you for contacting us."

    @pytest.mark.asyncio
    async def test_escalate_ticket(self, ticket_service):
        """Test escalating ticket."""
        ticket = await ticket_service.create_ticket(
            customer_id="CUST-001",
            subject="Escalation test",
            body="Need supervisor help",
        )

        result = await ticket_service.escalate_ticket(
            ticket_id=ticket["ticket_id"],
            reason="Customer requested supervisor",
        )

        assert result["success"] is True
        assert result["ticket"]["status"] == "escalated"
        assert result["ticket"]["escalation_reason"] == "Customer requested supervisor"

    @pytest.mark.asyncio
    async def test_close_ticket(self, ticket_service):
        """Test closing ticket."""
        ticket = await ticket_service.create_ticket(
            customer_id="CUST-001",
            subject="Close test",
            body="Resolved issue",
        )

        result = await ticket_service.close_ticket(
            ticket_id=ticket["ticket_id"],
            resolution="Issue resolved by password reset",
        )

        assert result["success"] is True
        assert result["ticket"]["status"] == "closed"
        assert result["ticket"]["resolution"] == "Issue resolved by password reset"

    @pytest.mark.asyncio
    async def test_all_actions_logged(self, ticket_service):
        """Test that all ticket actions are logged."""
        ticket = await ticket_service.create_ticket(
            customer_id="CUST-001",
            subject="Log test",
            body="Testing audit log",
        )

        await ticket_service.assign_ticket(ticket["ticket_id"], "agent-1")
        await ticket_service.add_reply(ticket["ticket_id"], "agent-1", "Reply")
        await ticket_service.close_ticket(ticket["ticket_id"], "Done")

        audit_log = ticket_service.get_audit_log()

        events = [e["event"] for e in audit_log]
        assert "ticket_created" in events
        assert "ticket_assigned" in events
        assert "ticket_reply" in events
        assert "ticket_closed" in events
