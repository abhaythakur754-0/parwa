"""
Enterprise Support - Ticket Manager
Enterprise ticket management system
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum
import uuid


class TicketPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TicketStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WAITING = "waiting"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketCategory(str, Enum):
    TECHNICAL = "technical"
    BILLING = "billing"
    FEATURE = "feature"
    SECURITY = "security"
    OTHER = "other"


class EnterpriseTicket(BaseModel):
    """Enterprise support ticket"""
    ticket_id: str = Field(default_factory=lambda: f"tkt_{uuid.uuid4().hex[:8]}")
    client_id: str
    title: str
    description: str
    category: TicketCategory = TicketCategory.OTHER
    priority: TicketPriority = TicketPriority.MEDIUM
    status: TicketStatus = TicketStatus.OPEN
    assignee: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    due_date: Optional[datetime] = None
    tags: List[str] = Field(default_factory=list)
    attachments: List[str] = Field(default_factory=list)
    comments: List[Dict[str, Any]] = Field(default_factory=list)

    model_config = ConfigDict()


class TicketManager:
    """
    Manage enterprise support tickets.
    """

    def __init__(self):
        self.tickets: Dict[str, EnterpriseTicket] = {}

    def create_ticket(
        self,
        client_id: str,
        title: str,
        description: str,
        priority: TicketPriority = TicketPriority.MEDIUM,
        category: TicketCategory = TicketCategory.OTHER,
        tags: Optional[List[str]] = None
    ) -> EnterpriseTicket:
        """Create a new ticket"""
        ticket = EnterpriseTicket(
            client_id=client_id,
            title=title,
            description=description,
            priority=priority,
            category=category,
            tags=tags or []
        )

        # Set due date based on priority
        hours = {
            TicketPriority.CRITICAL: 4,
            TicketPriority.HIGH: 24,
            TicketPriority.MEDIUM: 72,
            TicketPriority.LOW: 168
        }
        ticket.due_date = datetime.utcnow() + timedelta(hours=hours[priority])

        self.tickets[ticket.ticket_id] = ticket
        return ticket

    def update_ticket(
        self,
        ticket_id: str,
        updates: Dict[str, Any]
    ) -> Optional[EnterpriseTicket]:
        """Update a ticket"""
        if ticket_id not in self.tickets:
            return None

        ticket = self.tickets[ticket_id]
        for key, value in updates.items():
            if hasattr(ticket, key):
                setattr(ticket, key, value)
        ticket.updated_at = datetime.utcnow()

        return ticket

    def assign_ticket(self, ticket_id: str, assignee: str) -> bool:
        """Assign ticket to someone"""
        if ticket_id not in self.tickets:
            return False

        ticket = self.tickets[ticket_id]
        ticket.assignee = assignee
        ticket.status = TicketStatus.IN_PROGRESS
        ticket.updated_at = datetime.utcnow()
        return True

    def resolve_ticket(self, ticket_id: str, resolution: str) -> bool:
        """Resolve a ticket"""
        if ticket_id not in self.tickets:
            return False

        ticket = self.tickets[ticket_id]
        ticket.status = TicketStatus.RESOLVED
        ticket.resolved_at = datetime.utcnow()
        ticket.updated_at = datetime.utcnow()
        ticket.comments.append({
            "content": resolution,
            "type": "resolution",
            "timestamp": datetime.utcnow().isoformat()
        })
        return True

    def add_comment(self, ticket_id: str, comment: str, author: str) -> bool:
        """Add comment to ticket"""
        if ticket_id not in self.tickets:
            return False

        self.tickets[ticket_id].comments.append({
            "content": comment,
            "author": author,
            "timestamp": datetime.utcnow().isoformat()
        })
        return True

    def get_client_tickets(self, client_id: str) -> List[EnterpriseTicket]:
        """Get all tickets for a client"""
        return [t for t in self.tickets.values() if t.client_id == client_id]

    def get_open_tickets(self) -> List[EnterpriseTicket]:
        """Get all open tickets"""
        return [t for t in self.tickets.values() if t.status == TicketStatus.OPEN]

    def get_overdue_tickets(self) -> List[EnterpriseTicket]:
        """Get overdue tickets"""
        now = datetime.utcnow()
        return [
            t for t in self.tickets.values()
            if t.due_date and t.due_date < now and t.status not in [TicketStatus.RESOLVED, TicketStatus.CLOSED]
        ]
