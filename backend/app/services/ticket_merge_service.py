"""
PARWA Ticket Merge Service

Handles merging and unmerging of tickets.
- Merge multiple tickets into a primary ticket
- Transfer messages from merged tickets to primary
- Track merge history
- Undo merge (unmerge) capability

Day 29 - F-051 implementation.
PS26: Unmerge preserves message history.
"""

import json
import secrets
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from database.models.tickets import (
    Ticket,
    TicketMessage,
    TicketMerge,
    TicketStatus,
    TicketAttachment,
    TicketInternalNote,
)


class TicketMergeError(Exception):
    """Base exception for merge operations."""


class TicketNotFoundError(TicketMergeError):
    """Raised when a ticket is not found."""


class TicketAlreadyMergedError(TicketMergeError):
    """Raised when a ticket is already merged."""


class MergeAlreadyUndoneError(TicketMergeError):
    """Raised when trying to undo an already undone merge."""


class CrossTenantMergeError(TicketMergeError):
    """Raised when trying to merge tickets from different companies."""


class TicketMergeService:
    """Service for merging and unmerging tickets."""

    def __init__(self, db: Session):
        self.db = db

    def merge_tickets(
        self,
        company_id: str,
        primary_ticket_id: str,
        merged_ticket_ids: List[str],
        merged_by: str,
        reason: Optional[str] = None,
    ) -> Tuple[TicketMerge, Ticket]:
        """
        Merge multiple tickets into a primary ticket.

        The primary ticket retains all messages from merged tickets.
        Merged tickets get status 'closed' with merge reference.

        Args:
            company_id: Company performing the merge
            primary_ticket_id: ID of the primary (surviving) ticket
            merged_ticket_ids: IDs of tickets to merge
            merged_by: User ID performing the merge
            reason: Optional reason for the merge

        Returns:
            Tuple of (TicketMerge record, updated primary ticket)
        """
        # Validate primary ticket exists and belongs to company
        primary_ticket = (
            self.db.query(Ticket)
            .filter(
                Ticket.id == primary_ticket_id,
                Ticket.company_id == company_id,
            )
            .first()
        )

        if not primary_ticket:
            raise TicketNotFoundError(f"Primary ticket {primary_ticket_id} not found")

        # Validate all merged tickets
        tickets_to_merge = []
        for ticket_id in merged_ticket_ids:
            ticket = (
                self.db.query(Ticket)
                .filter(
                    Ticket.id == ticket_id,
                    Ticket.company_id == company_id,
                )
                .first()
            )

            if not ticket:
                raise TicketNotFoundError(f"Ticket {ticket_id} not found")

            if ticket.company_id != company_id:
                raise CrossTenantMergeError(
                    f"Ticket {ticket_id} belongs to different company"
                )

            # Check if already merged
            existing_merge = (
                self.db.query(TicketMerge)
                .filter(
                    TicketMerge.primary_ticket_id == ticket.id,
                    TicketMerge.undone is False,  # noqa: E712
                )
                .first()
            )

            if existing_merge:
                raise TicketAlreadyMergedError(f"Ticket {ticket_id} is already merged")

            # Check if this ticket is a primary of another merge
            as_primary_merge = (
                self.db.query(TicketMerge)
                .filter(
                    TicketMerge.primary_ticket_id == ticket.id,
                    TicketMerge.undone is False,  # noqa: E712
                )
                .first()
            )

            if as_primary_merge:
                raise TicketAlreadyMergedError(
                    f"Ticket {ticket_id} is a primary of another merge"
                )

            tickets_to_merge.append(ticket)

        # Generate undo token
        undo_token = secrets.token_urlsafe(32)

        # Create merge record
        merge_record = TicketMerge(
            primary_ticket_id=primary_ticket_id,
            merged_ticket_ids=json.dumps(merged_ticket_ids),
            merged_by=merged_by,
            company_id=company_id,
            reason=reason,
            undo_token=undo_token,
            undone=False,
        )
        self.db.add(merge_record)
        self.db.flush()

        # Transfer messages from merged tickets to primary
        for ticket in tickets_to_merge:
            self._transfer_messages(primary_ticket, ticket)
            self._transfer_attachments(primary_ticket, ticket)
            self._transfer_internal_notes(primary_ticket, ticket)

            # Mark merged ticket as closed
            ticket.status = TicketStatus.closed.value
            ticket.closed_at = datetime.now(timezone.utc)
            ticket.updated_at = datetime.now(timezone.utc)

        # Update primary ticket
        primary_ticket.updated_at = datetime.now(timezone.utc)

        self.db.commit()

        return merge_record, primary_ticket

    def _transfer_messages(
        self,
        primary_ticket: Ticket,
        merged_ticket: Ticket,
    ) -> None:
        """Transfer messages from merged ticket to primary ticket."""
        messages = (
            self.db.query(TicketMessage)
            .filter(
                TicketMessage.ticket_id == merged_ticket.id,
            )
            .all()
        )

        for message in messages:
            # Create a copy of the message linked to primary ticket
            # Keep original for unmerge capability
            new_message = TicketMessage(
                ticket_id=primary_ticket.id,
                company_id=primary_ticket.company_id,
                role=message.role,
                content=message.content,
                channel=message.channel,
                metadata_json=json.dumps(
                    {
                        "original_ticket_id": merged_ticket.id,
                        "original_message_id": message.id,
                        "merged_at": datetime.now(timezone.utc).isoformat(),
                    }
                ),
                is_internal=message.is_internal,
                is_redacted=message.is_redacted,
                ai_confidence=message.ai_confidence,
                variant_version=message.variant_version,
                classification=message.classification,
            )
            self.db.add(new_message)

    def _transfer_attachments(
        self,
        primary_ticket: Ticket,
        merged_ticket: Ticket,
    ) -> None:
        """Transfer attachments from merged ticket to primary ticket."""
        attachments = (
            self.db.query(TicketAttachment)
            .filter(
                TicketAttachment.ticket_id == merged_ticket.id,
            )
            .all()
        )

        for attachment in attachments:
            # Create reference to attachment from primary ticket
            # The actual file remains the same
            new_attachment = TicketAttachment(
                ticket_id=primary_ticket.id,
                company_id=primary_ticket.company_id,
                filename=attachment.filename,
                file_url=attachment.file_url,
                file_size=attachment.file_size,
                mime_type=attachment.mime_type,
                uploaded_by=attachment.uploaded_by,
            )
            self.db.add(new_attachment)

    def _transfer_internal_notes(
        self,
        primary_ticket: Ticket,
        merged_ticket: Ticket,
    ) -> None:
        """Transfer internal notes from merged ticket to primary ticket."""
        notes = (
            self.db.query(TicketInternalNote)
            .filter(
                TicketInternalNote.ticket_id == merged_ticket.id,
            )
            .all()
        )

        for note in notes:
            new_note = TicketInternalNote(
                ticket_id=primary_ticket.id,
                company_id=primary_ticket.company_id,
                author_id=note.author_id,
                content=note.content,
                is_pinned=note.is_pinned,
            )
            self.db.add(new_note)

    def unmerge_tickets(
        self,
        company_id: str,
        merge_id: str,
    ) -> Tuple[TicketMerge, List[Ticket]]:
        """
        Unmerge previously merged tickets (PS26).

        Restores the merged tickets to their original state.
        Messages transferred to primary are not removed (kept for audit).

        Args:
            company_id: Company that performed the merge
            merge_id: ID of the merge operation to undo

        Returns:
            Tuple of (updated merge record, list of restored tickets)
        """
        merge_record = (
            self.db.query(TicketMerge)
            .filter(
                TicketMerge.id == merge_id,
                TicketMerge.company_id == company_id,
            )
            .first()
        )

        if not merge_record:
            raise TicketNotFoundError(f"Merge record {merge_id} not found")

        if merge_record.undone:
            raise MergeAlreadyUndoneError("Merge has already been undone")

        # Get the merged ticket IDs
        merged_ticket_ids = json.loads(merge_record.merged_ticket_ids)

        # Restore merged tickets
        restored_tickets = []
        for ticket_id in merged_ticket_ids:
            ticket = (
                self.db.query(Ticket)
                .filter(
                    Ticket.id == ticket_id,
                    Ticket.company_id == company_id,
                )
                .first()
            )

            if ticket:
                # Reopen the ticket
                ticket.status = TicketStatus.reopened.value
                ticket.closed_at = None
                ticket.reopen_count = (ticket.reopen_count or 0) + 1
                ticket.updated_at = datetime.now(timezone.utc)
                restored_tickets.append(ticket)

        # Mark merge as undone
        merge_record.undone = True
        self.db.commit()

        return merge_record, restored_tickets

    def get_merge_history(
        self,
        company_id: str,
        ticket_id: str,
    ) -> List[TicketMerge]:
        """
        Get merge history for a ticket.

        Returns both merges where ticket is primary and where it was merged.
        """
        # Merges where this ticket is the primary
        as_primary = (
            self.db.query(TicketMerge)
            .filter(
                TicketMerge.primary_ticket_id == ticket_id,
                TicketMerge.company_id == company_id,
            )
            .all()
        )

        # Merges where this ticket was merged (need to search JSON)
        # This is a simplified approach - in production, use a proper JSON
        # query
        all_merges = (
            self.db.query(TicketMerge)
            .filter(
                TicketMerge.company_id == company_id,
            )
            .all()
        )

        as_merged = []
        for merge in all_merges:
            merged_ids = json.loads(merge.merged_ticket_ids)
            if ticket_id in merged_ids:
                as_merged.append(merge)

        return as_primary + as_merged

    def get_merge_by_token(
        self,
        company_id: str,
        undo_token: str,
    ) -> Optional[TicketMerge]:
        """Get a merge record by undo token."""
        return (
            self.db.query(TicketMerge)
            .filter(
                TicketMerge.company_id == company_id,
                TicketMerge.undo_token == undo_token,
            )
            .first()
        )

    def get_merge_by_id(
        self,
        company_id: str,
        merge_id: str,
    ) -> Optional[TicketMerge]:
        """Get a merge record by ID."""
        return (
            self.db.query(TicketMerge)
            .filter(
                TicketMerge.id == merge_id,
                TicketMerge.company_id == company_id,
            )
            .first()
        )

    def can_merge_tickets(
        self,
        company_id: str,
        ticket_ids: List[str],
    ) -> Tuple[bool, List[str]]:
        """
        Check if tickets can be merged.

        Returns:
            Tuple of (can_merge, list of reasons if not)
        """
        reasons = []

        # Check all tickets exist and belong to company
        for ticket_id in ticket_ids:
            ticket = (
                self.db.query(Ticket)
                .filter(
                    Ticket.id == ticket_id,
                    Ticket.company_id == company_id,
                )
                .first()
            )

            if not ticket:
                reasons.append(f"Ticket {ticket_id} not found")
                continue

            # Check if already merged
            existing_merge = (
                self.db.query(TicketMerge)
                .filter(
                    TicketMerge.merged_ticket_ids.contains(f'"{ticket_id}"'),
                    TicketMerge.undone is False,  # noqa: E712
                )
                .first()
            )

            if existing_merge:
                reasons.append(f"Ticket {ticket_id} is already part of a merge")

        return len(reasons) == 0, reasons
