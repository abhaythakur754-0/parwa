"""
PARWA Base Ticket Agent.

Abstract base class for ticket management agents. Provides common
functionality for ticket creation, updates, and status tracking.
"""
from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime, timezone
from enum import Enum
import uuid

from variants.base_agents.base_agent import (
    BaseAgent,
    AgentResponse,
)
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class TicketPriority(Enum):
    """Ticket priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class TicketStatus(Enum):
    """Ticket status values."""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WAITING = "waiting"
    RESOLVED = "resolved"
    CLOSED = "closed"


class BaseTicketAgent(BaseAgent):
    """
    Abstract base class for ticket management agents.

    Provides:
    - Ticket creation
    - Ticket updates
    - Status tracking
    - Comment management

    Subclasses must implement:
    - get_tier()
    - get_variant()
    - process()
    """

    def __init__(
        self,
        agent_id: str,
        config: Optional[Dict[str, Any]] = None,
        company_id: Optional[UUID] = None
    ) -> None:
        """
        Initialize Ticket agent.

        Args:
            agent_id: Unique identifier for this agent
            config: Optional configuration dictionary
            company_id: Company UUID for multi-tenancy
        """
        super().__init__(agent_id, config, company_id)
        self._tickets: Dict[str, Dict[str, Any]] = {}

    async def create_ticket(
        self,
        subject: str,
        description: str,
        priority: str = "normal",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new support ticket.

        Args:
            subject: Ticket subject
            description: Ticket description
            priority: Priority level (low, normal, high, urgent)
            metadata: Additional metadata

        Returns:
            Created ticket data
        """
        ticket_id = f"TKT-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc).isoformat()

        ticket = {
            "ticket_id": ticket_id,
            "subject": subject,
            "description": description,
            "priority": priority,
            "status": TicketStatus.OPEN.value,
            "created_at": now,
            "updated_at": now,
            "company_id": str(self._company_id) if self._company_id else None,
            "comments": [],
            "metadata": metadata or {},
        }

        self._tickets[ticket_id] = ticket

        logger.info({
            "event": "ticket_created",
            "agent_id": self._agent_id,
            "ticket_id": ticket_id,
            "priority": priority,
        })

        return ticket

    async def update_ticket(
        self,
        ticket_id: str,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update an existing ticket.

        Args:
            ticket_id: Ticket identifier
            updates: Fields to update

        Returns:
            Updated ticket data
        """
        ticket = self._tickets.get(ticket_id)

        if not ticket:
            return {
                "status": "error",
                "message": f"Ticket {ticket_id} not found",
            }

        # Update allowed fields
        updatable_fields = [
            "subject", "description", "priority", "status", "metadata"
        ]
        for field in updatable_fields:
            if field in updates:
                ticket[field] = updates[field]

        ticket["updated_at"] = datetime.now(timezone.utc).isoformat()

        logger.info({
            "event": "ticket_updated",
            "agent_id": self._agent_id,
            "ticket_id": ticket_id,
            "updated_fields": list(updates.keys()),
        })

        return ticket

    async def get_ticket(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a ticket by ID.

        Args:
            ticket_id: Ticket identifier

        Returns:
            Ticket data or None if not found
        """
        return self._tickets.get(ticket_id)

    async def add_comment(
        self,
        ticket_id: str,
        comment: str,
        author: str
    ) -> Dict[str, Any]:
        """
        Add a comment to a ticket.

        Args:
            ticket_id: Ticket identifier
            comment: Comment text
            author: Comment author

        Returns:
            Updated ticket data
        """
        ticket = self._tickets.get(ticket_id)

        if not ticket:
            return {
                "status": "error",
                "message": f"Ticket {ticket_id} not found",
            }

        comment_entry = {
            "comment_id": f"CMT-{uuid.uuid4().hex[:6].upper()}",
            "text": comment,
            "author": author,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        ticket["comments"].append(comment_entry)
        ticket["updated_at"] = datetime.now(timezone.utc).isoformat()

        logger.info({
            "event": "ticket_comment_added",
            "agent_id": self._agent_id,
            "ticket_id": ticket_id,
            "author": author,
        })

        return ticket

    async def search_tickets(
        self,
        query: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search tickets by criteria.

        Args:
            query: Search criteria

        Returns:
            List of matching tickets
        """
        query = query or {}
        results = []

        for ticket in self._tickets.values():
            match = True

            # Filter by status
            if "status" in query:
                match = match and ticket["status"] == query["status"]

            # Filter by priority
            if "priority" in query:
                match = match and ticket["priority"] == query["priority"]

            if match:
                results.append(ticket)

        return results

    def get_ticket_count(self) -> int:
        """Get total ticket count."""
        return len(self._tickets)

    def get_tickets_by_status(self) -> Dict[str, int]:
        """Get ticket counts by status."""
        counts = {}
        for ticket in self._tickets.values():
            status = ticket["status"]
            counts[status] = counts.get(status, 0) + 1
        return counts
