"""
PARWA Mini Ticket Create Tool.

Provides ticket creation functionality for Mini PARWA agents.
"""
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import uuid
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class TicketCreateTool:
    """
    Tool for creating support tickets.

    Provides:
    - Create new tickets
    - Validate ticket data
    - Generate ticket IDs
    """

    VALID_PRIORITIES = ["low", "normal", "high", "urgent"]
    VALID_STATUSES = ["open", "in_progress", "waiting", "resolved", "closed"]

    def __init__(self) -> None:
        """Initialize ticket create tool."""
        self._tickets: Dict[str, Dict[str, Any]] = {}

    async def create(
        self,
        subject: str,
        description: str,
        priority: str = "normal",
        customer_id: Optional[str] = None,
        customer_email: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new support ticket.

        Args:
            subject: Ticket subject
            description: Ticket description
            priority: Priority level (low, normal, high, urgent)
            customer_id: Customer identifier
            customer_email: Customer email
            metadata: Additional metadata

        Returns:
            Created ticket data
        """
        # Generate ticket ID
        ticket_id = f"TKT-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc).isoformat()

        # Normalize priority
        priority_lower = priority.lower()
        if priority_lower not in self.VALID_PRIORITIES:
            priority_lower = "normal"

        ticket = {
            "ticket_id": ticket_id,
            "subject": subject,
            "description": description,
            "priority": priority_lower,
            "status": "open",
            "customer_id": customer_id,
            "customer_email": customer_email,
            "created_at": now,
            "updated_at": now,
            "comments": [],
            "metadata": metadata or {},
        }

        self._tickets[ticket_id] = ticket

        logger.info({
            "event": "ticket_created",
            "ticket_id": ticket_id,
            "priority": priority_lower,
            "customer_id": customer_id,
        })

        return ticket

    async def get(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        """
        Get ticket by ID.

        Args:
            ticket_id: Ticket identifier

        Returns:
            Ticket data or None if not found
        """
        return self._tickets.get(ticket_id)

    async def update(
        self,
        ticket_id: str,
        updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Update a ticket.

        Args:
            ticket_id: Ticket identifier
            updates: Fields to update

        Returns:
            Updated ticket or None if not found
        """
        ticket = self._tickets.get(ticket_id)
        if not ticket:
            return None

        # Allowed fields to update
        allowed_fields = ["subject", "description", "priority", "status", "metadata"]

        for field in allowed_fields:
            if field in updates:
                if field == "priority" and updates[field].lower() not in self.VALID_PRIORITIES:
                    continue
                if field == "status" and updates[field].lower() not in self.VALID_STATUSES:
                    continue
                ticket[field] = updates[field]

        ticket["updated_at"] = datetime.now(timezone.utc).isoformat()

        logger.info({
            "event": "ticket_updated",
            "ticket_id": ticket_id,
            "updated_fields": list(updates.keys()),
        })

        return ticket

    async def add_comment(
        self,
        ticket_id: str,
        comment: str,
        author: str
    ) -> Optional[Dict[str, Any]]:
        """
        Add a comment to a ticket.

        Args:
            ticket_id: Ticket identifier
            comment: Comment text
            author: Comment author

        Returns:
            Updated ticket or None if not found
        """
        ticket = self._tickets.get(ticket_id)
        if not ticket:
            return None

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
            "ticket_id": ticket_id,
            "author": author,
        })

        return ticket

    def validate_ticket_data(
        self,
        subject: str,
        description: str,
        priority: str = "normal"
    ) -> Dict[str, Any]:
        """
        Validate ticket data before creation.

        Args:
            subject: Ticket subject
            description: Ticket description
            priority: Priority level

        Returns:
            Dict with valid status and any errors
        """
        errors = []

        if not subject or len(subject.strip()) < 3:
            errors.append("Subject must be at least 3 characters")

        if not description or len(description.strip()) < 10:
            errors.append("Description must be at least 10 characters")

        if priority.lower() not in self.VALID_PRIORITIES:
            errors.append(f"Priority must be one of: {', '.join(self.VALID_PRIORITIES)}")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
        }

    def get_ticket_count(self) -> int:
        """Get total ticket count."""
        return len(self._tickets)

    def get_tickets_by_status(self) -> Dict[str, int]:
        """Get ticket counts by status."""
        counts = {}
        for ticket in self._tickets.values():
            status = ticket.get("status", "open")
            counts[status] = counts.get(status, 0) + 1
        return counts
