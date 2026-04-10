"""
PARWA Message Service - Ticket Conversation Management (Day 27)

Implements F-047: Ticket conversation/message operations with:
- Message CRUD with thread ordering
- Edit within time window (5 minutes)
- Role-based visibility (customer vs internal)
- PII redaction integration (BL07)

BC-001: All queries are tenant-isolated via company_id.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, desc, func, or_
from sqlalchemy.orm import Session

from app.exceptions import (
    NotFoundError,
    AuthorizationError,
    ValidationError,
)
from database.models.tickets import (
    Ticket,
    TicketMessage,
    TicketAttachment,
    TicketStatus,
)


class MessageService:
    """Message/Conversation management for tickets."""

    # Edit window in minutes
    EDIT_WINDOW_MINUTES = 5

    # Max message length
    MAX_MESSAGE_LENGTH = 100000  # 100KB

    # Valid roles
    VALID_ROLES = ["customer", "agent", "system", "ai"]

    def __init__(self, db: Session, company_id: str):
        self.db = db
        self.company_id = company_id

    # ── CREATE ─────────────────────────────────────────────────────────────

    def create_message(
        self,
        ticket_id: str,
        role: str,
        content: str,
        channel: str,
        is_internal: bool = False,
        metadata_json: Optional[Dict[str, Any]] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        user_id: Optional[str] = None,
        ai_confidence: Optional[float] = None,
        variant_version: Optional[str] = None,
    ) -> TicketMessage:
        """Create a new message on a ticket.

        Args:
            ticket_id: Ticket ID
            role: Message role (customer, agent, system, ai)
            content: Message content
            channel: Communication channel
            is_internal: Whether this is an internal note
            metadata_json: Additional metadata
            attachments: List of attachment metadata
            user_id: ID of user creating message
            ai_confidence: AI confidence score (for AI messages)
            variant_version: AI variant version (for AI messages)

        Returns:
            Created TicketMessage object

        Raises:
            NotFoundError: If ticket not found
            ValidationError: If validation fails
        """
        # Validate ticket exists
        ticket = self._validate_ticket(ticket_id)

        # Validate role
        if role not in self.VALID_ROLES:
            raise ValidationError(f"Invalid role: {role}. Must be one of {self.VALID_ROLES}")

        # Validate content length
        if len(content) > self.MAX_MESSAGE_LENGTH:
            raise ValidationError(
                f"Message too long. Max {self.MAX_MESSAGE_LENGTH} characters."
            )

        # Check if ticket is frozen
        if ticket.frozen:
            raise ValidationError("Cannot add messages to a frozen ticket")

        # Create message
        message = TicketMessage(
            id=str(uuid.uuid4()),
            ticket_id=ticket_id,
            company_id=self.company_id,
            role=role,
            content=content,
            channel=channel,
            is_internal=is_internal,
            metadata_json=json.dumps(metadata_json or {}),
            ai_confidence=ai_confidence,
            variant_version=variant_version,
            created_at=datetime.utcnow(),
        )

        self.db.add(message)

        # Update ticket's updated_at timestamp
        ticket.updated_at = datetime.utcnow()

        # If first response, update ticket's first_response_at
        if not ticket.first_response_at and role in ["agent", "ai"]:
            ticket.first_response_at = datetime.utcnow()

        # Handle attachments
        if attachments:
            for att in attachments:
                attachment = TicketAttachment(
                    id=str(uuid.uuid4()),
                    ticket_id=ticket_id,
                    company_id=self.company_id,
                    filename=att.get("filename"),
                    file_url=att.get("file_url"),
                    file_size=att.get("file_size"),
                    mime_type=att.get("mime_type"),
                    uploaded_by=user_id,
                    created_at=datetime.utcnow(),
                )
                self.db.add(attachment)

        self.db.commit()
        self.db.refresh(message)

        return message

    # ── READ ───────────────────────────────────────────────────────────────

    def get_message(self, ticket_id: str, message_id: str) -> TicketMessage:
        """Get a single message by ID.

        Args:
            ticket_id: Ticket ID
            message_id: Message ID

        Returns:
            TicketMessage object

        Raises:
            NotFoundError: If message not found
        """
        message = self.db.query(TicketMessage).filter(
            TicketMessage.id == message_id,
            TicketMessage.ticket_id == ticket_id,
            TicketMessage.company_id == self.company_id,
        ).first()

        if not message:
            raise NotFoundError(f"Message {message_id} not found")

        return message

    def list_messages(
        self,
        ticket_id: str,
        include_internal: bool = False,
        role: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
        order: str = "asc",
    ) -> Tuple[List[TicketMessage], int]:
        """List messages for a ticket.

        Args:
            ticket_id: Ticket ID
            include_internal: Include internal notes
            role: Filter by role
            page: Page number (1-based)
            page_size: Items per page
            order: Sort order (asc/desc)

        Returns:
            Tuple of (messages list, total count)
        """
        query = self.db.query(TicketMessage).filter(
            TicketMessage.ticket_id == ticket_id,
            TicketMessage.company_id == self.company_id,
        )

        # Filter internal notes
        if not include_internal:
            query = query.filter(TicketMessage.is_internal == False)

        # Filter by role
        if role:
            query = query.filter(TicketMessage.role == role)

        # Count total
        total = query.count()

        # Sort (chronological by default)
        if order == "desc":
            query = query.order_by(desc(TicketMessage.created_at))
        else:
            query = query.order_by(TicketMessage.created_at)

        # Paginate
        offset = (page - 1) * page_size
        messages = query.offset(offset).limit(page_size).all()

        return messages, total

    # ── UPDATE ─────────────────────────────────────────────────────────────

    def update_message(
        self,
        ticket_id: str,
        message_id: str,
        content: Optional[str] = None,
        metadata_json: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        force: bool = False,
    ) -> TicketMessage:
        """Update a message.

        Edit window: Only editable within 5 minutes of creation.
        Only the original author can edit (enforced at API level).

        Args:
            ticket_id: Ticket ID
            message_id: Message ID
            content: New content
            metadata_json: New metadata
            user_id: ID of user making edit
            force: Skip edit window check (for admins)

        Returns:
            Updated TicketMessage object

        Raises:
            NotFoundError: If message not found
            ValidationError: If edit window expired
        """
        message = self.get_message(ticket_id, message_id)

        # Check edit window
        if not force:
            edit_deadline = message.created_at + timedelta(
                minutes=self.EDIT_WINDOW_MINUTES
            )
            if datetime.utcnow() > edit_deadline:
                raise ValidationError(
                    f"Message can only be edited within {self.EDIT_WINDOW_MINUTES} minutes"
                )

        # Validate content length
        if content and len(content) > self.MAX_MESSAGE_LENGTH:
            raise ValidationError(
                f"Message too long. Max {self.MAX_MESSAGE_LENGTH} characters."
            )

        # Update fields
        if content is not None:
            message.content = content

        if metadata_json is not None:
            # Merge with existing metadata
            existing = json.loads(message.metadata_json or "{}")
            existing.update(metadata_json)
            message.metadata_json = json.dumps(existing)

        self.db.commit()
        self.db.refresh(message)

        return message

    # ── DELETE ─────────────────────────────────────────────────────────────

    def delete_message(
        self,
        ticket_id: str,
        message_id: str,
        user_id: Optional[str] = None,
        hard: bool = False,
    ) -> bool:
        """Delete a message (soft delete by default).

        Soft delete replaces content with "[DELETED]" but preserves metadata.

        Args:
            ticket_id: Ticket ID
            message_id: Message ID
            user_id: ID of user deleting
            hard: If True, permanently delete

        Returns:
            True if deleted successfully

        Raises:
            NotFoundError: If message not found
        """
        message = self.get_message(ticket_id, message_id)

        if hard:
            self.db.delete(message)
        else:
            # Soft delete: replace content, mark in metadata
            message.content = "[DELETED]"
            metadata = json.loads(message.metadata_json or "{}")
            metadata["deleted"] = True
            metadata["deleted_at"] = datetime.utcnow().isoformat()
            metadata["deleted_by"] = user_id
            message.metadata_json = json.dumps(metadata)

        self.db.commit()

        return True

    # ── REDACTION ─────────────────────────────────────────────────────────

    def redact_message(
        self,
        ticket_id: str,
        message_id: str,
        reason: str,
        user_id: Optional[str] = None,
    ) -> TicketMessage:
        """Redact a message (GDPR/PS12).

        Replaces content with "[REDACTED]" and marks as redacted.

        Args:
            ticket_id: Ticket ID
            message_id: Message ID
            reason: Reason for redaction
            user_id: ID of user redacting

        Returns:
            Updated TicketMessage object

        Raises:
            NotFoundError: If message not found
        """
        message = self.get_message(ticket_id, message_id)

        message.content = "[REDACTED]"
        message.is_redacted = True

        metadata = json.loads(message.metadata_json or "{}")
        metadata["redacted"] = True
        metadata["redacted_at"] = datetime.utcnow().isoformat()
        metadata["redacted_by"] = user_id
        metadata["redaction_reason"] = reason
        message.metadata_json = json.dumps(metadata)

        self.db.commit()
        self.db.refresh(message)

        return message

    # ── ATTACHMENTS ───────────────────────────────────────────────────────

    def get_attachments(
        self,
        ticket_id: str,
    ) -> List[TicketAttachment]:
        """Get all attachments for a ticket.

        Args:
            ticket_id: Ticket ID

        Returns:
            List of TicketAttachment objects
        """
        return self.db.query(TicketAttachment).filter(
            TicketAttachment.ticket_id == ticket_id,
            TicketAttachment.company_id == self.company_id,
        ).order_by(TicketAttachment.created_at).all()

    # ── PRIVATE HELPERS ────────────────────────────────────────────────────

    def _validate_ticket(self, ticket_id: str) -> Ticket:
        """Validate ticket exists and belongs to company.

        Args:
            ticket_id: Ticket ID

        Returns:
            Ticket object

        Raises:
            NotFoundError: If ticket not found
        """
        ticket = self.db.query(Ticket).filter(
            Ticket.id == ticket_id,
            Ticket.company_id == self.company_id,
        ).first()

        if not ticket:
            raise NotFoundError(f"Ticket {ticket_id} not found")

        return ticket
