"""
PARWA Internal Note Service - Internal Notes Management (Day 27)

Implements internal note CRUD operations for ticket collaboration:
- Create, read, update, delete internal notes
- Pin/unpin notes for visibility
- Author-only edit/delete permissions

BC-001: All queries are tenant-isolated via company_id.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, desc
from sqlalchemy.orm import Session

from app.exceptions import (
    NotFoundError,
    AuthorizationError,
    ValidationError,
)
from database.models.tickets import (
    Ticket,
    TicketInternalNote,
)


class InternalNoteService:
    """Internal note management for tickets."""

    # Max note length
    MAX_NOTE_LENGTH = 50000  # 50KB

    # Max pinned notes per ticket
    MAX_PINNED_NOTES = 5

    def __init__(self, db: Session, company_id: str):
        self.db = db
        self.company_id = company_id

    # ── CREATE ─────────────────────────────────────────────────────────────

    def create_note(
        self,
        ticket_id: str,
        author_id: str,
        content: str,
        is_pinned: bool = False,
    ) -> TicketInternalNote:
        """Create an internal note on a ticket.

        Args:
            ticket_id: Ticket ID
            author_id: ID of the author (user)
            content: Note content
            is_pinned: Whether to pin the note

        Returns:
            Created TicketInternalNote object

        Raises:
            NotFoundError: If ticket not found
            ValidationError: If validation fails
        """
        # Validate ticket exists
        ticket = self._validate_ticket(ticket_id)

        # Validate content
        if not content or not content.strip():
            raise ValidationError("Note content cannot be empty")

        if len(content) > self.MAX_NOTE_LENGTH:
            raise ValidationError(
                f"Note too long. Max {self.MAX_NOTE_LENGTH} characters."
            )

        # Check pinned limit
        if is_pinned:
            pinned_count = self.db.query(TicketInternalNote).filter(
                TicketInternalNote.ticket_id == ticket_id,
                TicketInternalNote.company_id == self.company_id,
                TicketInternalNote.is_pinned == True,
            ).count()

            if pinned_count >= self.MAX_PINNED_NOTES:
                raise ValidationError(
                    f"Maximum {self.MAX_PINNED_NOTES} pinned notes per ticket"
                )

        # Create note
        note = TicketInternalNote(
            id=str(uuid.uuid4()),
            ticket_id=ticket_id,
            company_id=self.company_id,
            author_id=author_id,
            content=content,
            is_pinned=is_pinned,
            created_at=datetime.now(timezone.utc),
        )

        self.db.add(note)

        # Update ticket's updated_at
        ticket.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(note)

        return note

    # ── READ ───────────────────────────────────────────────────────────────

    def get_note(self, ticket_id: str, note_id: str) -> TicketInternalNote:
        """Get a single note by ID.

        Args:
            ticket_id: Ticket ID
            note_id: Note ID

        Returns:
            TicketInternalNote object

        Raises:
            NotFoundError: If note not found
        """
        note = self.db.query(TicketInternalNote).filter(
            TicketInternalNote.id == note_id,
            TicketInternalNote.ticket_id == ticket_id,
            TicketInternalNote.company_id == self.company_id,
        ).first()

        if not note:
            raise NotFoundError(f"Note {note_id} not found")

        return note

    def list_notes(
        self,
        ticket_id: str,
        pinned_only: bool = False,
        page: int = 1,
        page_size: int = 50,
        order: str = "desc",
    ) -> Tuple[List[TicketInternalNote], int]:
        """List internal notes for a ticket.

        Args:
            ticket_id: Ticket ID
            pinned_only: Only return pinned notes
            page: Page number (1-based)
            page_size: Items per page
            order: Sort order (asc/desc)

        Returns:
            Tuple of (notes list, total count)
        """
        query = self.db.query(TicketInternalNote).filter(
            TicketInternalNote.ticket_id == ticket_id,
            TicketInternalNote.company_id == self.company_id,
        )

        # Filter pinned
        if pinned_only:
            query = query.filter(TicketInternalNote.is_pinned == True)

        # Count total
        total = query.count()

        # Sort (pinned first, then by created_at)
        if order == "asc":
            query = query.order_by(
                TicketInternalNote.is_pinned.desc(),
                TicketInternalNote.created_at
            )
        else:
            query = query.order_by(
                TicketInternalNote.is_pinned.desc(),
                desc(TicketInternalNote.created_at)
            )

        # Paginate
        offset = (page - 1) * page_size
        notes = query.offset(offset).limit(page_size).all()

        return notes, total

    # ── UPDATE ─────────────────────────────────────────────────────────────

    def update_note(
        self,
        ticket_id: str,
        note_id: str,
        content: Optional[str] = None,
        user_id: Optional[str] = None,
        force: bool = False,
    ) -> TicketInternalNote:
        """Update a note.

        Only the author can edit their own notes (unless force=True for admins).

        Args:
            ticket_id: Ticket ID
            note_id: Note ID
            content: New content
            user_id: ID of user making edit (for authorization)
            force: Skip author check (for admins)

        Returns:
            Updated TicketInternalNote object

        Raises:
            NotFoundError: If note not found
            AuthorizationError: If user is not the author
            ValidationError: If validation fails
        """
        note = self.get_note(ticket_id, note_id)

        # Check authorization
        if not force and user_id and note.author_id != user_id:
            raise AuthorizationError("Only the author can edit this note")

        # Validate content
        if content is not None:
            if not content.strip():
                raise ValidationError("Note content cannot be empty")

            if len(content) > self.MAX_NOTE_LENGTH:
                raise ValidationError(
                    f"Note too long. Max {self.MAX_NOTE_LENGTH} characters."
                )

            note.content = content

        self.db.commit()
        self.db.refresh(note)

        return note

    # ── DELETE ─────────────────────────────────────────────────────────────

    def delete_note(
        self,
        ticket_id: str,
        note_id: str,
        user_id: Optional[str] = None,
        force: bool = False,
    ) -> bool:
        """Delete a note.

        Only the author can delete their own notes (unless force=True for admins).

        Args:
            ticket_id: Ticket ID
            note_id: Note ID
            user_id: ID of user deleting (for authorization)
            force: Skip author check (for admins)

        Returns:
            True if deleted successfully

        Raises:
            NotFoundError: If note not found
            AuthorizationError: If user is not the author
        """
        note = self.get_note(ticket_id, note_id)

        # Check authorization
        if not force and user_id and note.author_id != user_id:
            raise AuthorizationError("Only the author can delete this note")

        self.db.delete(note)
        self.db.commit()

        return True

    # ── PIN MANAGEMENT ─────────────────────────────────────────────────────

    def pin_note(
        self,
        ticket_id: str,
        note_id: str,
        user_id: Optional[str] = None,
    ) -> TicketInternalNote:
        """Pin a note.

        Pinned notes appear at the top of the notes list.

        Args:
            ticket_id: Ticket ID
            note_id: Note ID
            user_id: ID of user pinning

        Returns:
            Updated TicketInternalNote object

        Raises:
            NotFoundError: If note not found
            ValidationError: If pinned limit reached
        """
        note = self.get_note(ticket_id, note_id)

        if note.is_pinned:
            return note  # Already pinned

        # Check pinned limit
        pinned_count = self.db.query(TicketInternalNote).filter(
            TicketInternalNote.ticket_id == ticket_id,
            TicketInternalNote.company_id == self.company_id,
            TicketInternalNote.is_pinned == True,
        ).count()

        if pinned_count >= self.MAX_PINNED_NOTES:
            raise ValidationError(
                f"Maximum {self.MAX_PINNED_NOTES} pinned notes per ticket. "
                "Unpin another note first."
            )

        note.is_pinned = True
        self.db.commit()
        self.db.refresh(note)

        return note

    def unpin_note(
        self,
        ticket_id: str,
        note_id: str,
        user_id: Optional[str] = None,
    ) -> TicketInternalNote:
        """Unpin a note.

        Args:
            ticket_id: Ticket ID
            note_id: Note ID
            user_id: ID of user unpinning

        Returns:
            Updated TicketInternalNote object

        Raises:
            NotFoundError: If note not found
        """
        note = self.get_note(ticket_id, note_id)

        note.is_pinned = False
        self.db.commit()
        self.db.refresh(note)

        return note

    def toggle_pin(
        self,
        ticket_id: str,
        note_id: str,
        user_id: Optional[str] = None,
    ) -> TicketInternalNote:
        """Toggle pin status of a note.

        Args:
            ticket_id: Ticket ID
            note_id: Note ID
            user_id: ID of user toggling

        Returns:
            Updated TicketInternalNote object

        Raises:
            NotFoundError: If note not found
            ValidationError: If trying to pin but limit reached
        """
        note = self.get_note(ticket_id, note_id)

        if note.is_pinned:
            return self.unpin_note(ticket_id, note_id, user_id)
        else:
            return self.pin_note(ticket_id, note_id, user_id)

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

    # ── BULK OPERATIONS ────────────────────────────────────────────────────

    def get_pinned_notes(
        self,
        ticket_id: str,
    ) -> List[TicketInternalNote]:
        """Get all pinned notes for a ticket.

        Args:
            ticket_id: Ticket ID

        Returns:
            List of pinned TicketInternalNote objects
        """
        return self.db.query(TicketInternalNote).filter(
            TicketInternalNote.ticket_id == ticket_id,
            TicketInternalNote.company_id == self.company_id,
            TicketInternalNote.is_pinned == True,
        ).order_by(TicketInternalNote.created_at).all()

    def clear_all_pins(
        self,
        ticket_id: str,
    ) -> int:
        """Clear all pinned notes for a ticket.

        Args:
            ticket_id: Ticket ID

        Returns:
            Number of notes unpinned
        """
        result = self.db.query(TicketInternalNote).filter(
            TicketInternalNote.ticket_id == ticket_id,
            TicketInternalNote.company_id == self.company_id,
            TicketInternalNote.is_pinned == True,
        ).update({"is_pinned": False})

        self.db.commit()

        return result
