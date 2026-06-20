"""
PARWA Activity Log Service - Timeline/Activity Tracking (Day 27)

Implements MF04: Activity log/timeline for every ticket change.
Implements BL08: Audit trail for tickets.

Tracks all ticket events:
- Status changes
- Priority changes
- Category changes
- Assignments
- Tag changes
- SLA events
- Messages added
- Internal notes
- Attachments
- Merges

BC-001: All queries are tenant-isolated via company_id.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, desc, or_
from sqlalchemy.orm import Session

from database.models.tickets import (
    Ticket,
    TicketStatusChange,
    TicketAssignment,
    TicketMessage,
    TicketInternalNote,
    TicketAttachment,
    TicketMerge,
    BulkActionLog,
    SLATimer,
)


class ActivityLogService:
    """Activity log and timeline management for tickets."""

    # Activity types
    ACTIVITY_STATUS_CHANGE = "status_change"
    ACTIVITY_PRIORITY_CHANGE = "priority_change"
    ACTIVITY_CATEGORY_CHANGE = "category_change"
    ACTIVITY_ASSIGNED = "assigned"
    ACTIVITY_UNASSIGNED = "unassigned"
    ACTIVITY_TAG_ADDED = "tag_added"
    ACTIVITY_TAG_REMOVED = "tag_removed"
    ACTIVITY_SLA_WARNING = "sla_warning"
    ACTIVITY_SLA_BREACHED = "sla_breached"
    ACTIVITY_REOPENED = "reopened"
    ACTIVITY_FROZEN = "frozen"
    ACTIVITY_THAWED = "thawed"
    ACTIVITY_MERGED = "merged"
    ACTIVITY_UNMERGED = "unmerged"
    ACTIVITY_MESSAGE_ADDED = "message_added"
    ACTIVITY_NOTE_ADDED = "note_added"
    ACTIVITY_ATTACHMENT_UPLOADED = "attachment_uploaded"
    ACTIVITY_CREATED = "created"
    ACTIVITY_CLOSED = "closed"
    ACTIVITY_ESCALATED = "escalated"
    ACTIVITY_SPAM_FLAGGED = "spam_flagged"

    def __init__(self, db: Session, company_id: str):
        self.db = db
        self.company_id = company_id

    # ── ACTIVITY RECORDING ────────────────────────────────────────────────

    def record_activity(
        self,
        ticket_id: str,
        activity_type: str,
        actor_id: Optional[str] = None,
        actor_type: str = "human",
        old_value: Optional[str] = None,
        new_value: Optional[str] = None,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Record an activity event.

        This creates an activity log entry. For status changes, also creates
        TicketStatusChange record for database tracking.

        Args:
            ticket_id: Ticket ID
            activity_type: Type of activity
            actor_id: ID of user/agent who performed action
            actor_type: Type of actor (human, ai, system)
            old_value: Previous value (if applicable)
            new_value: New value (if applicable)
            reason: Reason for change
            metadata: Additional metadata

        Returns:
            Activity record dict
        """
        now = datetime.now(timezone.utc)

        activity = {
            "id": str(uuid.uuid4()),
            "ticket_id": ticket_id,
            "company_id": self.company_id,
            "activity_type": activity_type,
            "actor_id": actor_id,
            "actor_type": actor_type,
            "old_value": old_value,
            "new_value": new_value,
            "reason": reason,
            "metadata": metadata or {},
            "created_at": now.isoformat(),
        }

        # For status changes, also create DB record
        if activity_type == self.ACTIVITY_STATUS_CHANGE:
            status_change = TicketStatusChange(
                id=activity["id"],
                ticket_id=ticket_id,
                company_id=self.company_id,
                from_status=old_value,
                to_status=new_value,
                changed_by=actor_id,
                reason=reason,
                created_at=now,
            )
            self.db.add(status_change)
            self.db.commit()

        return activity

    # ── TIMELINE RETRIEVAL ────────────────────────────────────────────────

    def get_timeline(
        self,
        ticket_id: str,
        include_messages: bool = True,
        include_notes: bool = True,
        include_internal: bool = False,
        activity_types: Optional[List[str]] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Get activity timeline for a ticket.

        Combines data from multiple sources:
        - TicketStatusChange (status changes)
        - TicketAssignment (assignments)
        - TicketMessage (messages)
        - TicketInternalNote (notes)
        - TicketAttachment (attachments)
        - TicketMerge (merges)

        Args:
            ticket_id: Ticket ID
            include_messages: Include message events
            include_notes: Include internal note events
            include_internal: Include internal-only activities
            activity_types: Filter by activity types
            page: Page number (1-based)
            page_size: Items per page

        Returns:
            Tuple of (timeline events, total count)
        """
        events = []

        # Get status changes
        status_changes = self.db.query(TicketStatusChange).filter(
            TicketStatusChange.ticket_id == ticket_id,
            TicketStatusChange.company_id == self.company_id,
        ).all()

        for sc in status_changes:
            events.append({
                "id": sc.id,
                "type": self.ACTIVITY_STATUS_CHANGE,
                "timestamp": sc.created_at,
                "actor_id": sc.changed_by,
                "actor_type": "human",
                "old_value": sc.from_status,
                "new_value": sc.to_status,
                "reason": sc.reason,
            })

        # Get assignments
        assignments = self.db.query(TicketAssignment).filter(
            TicketAssignment.ticket_id == ticket_id,
            TicketAssignment.company_id == self.company_id,
        ).all()

        for a in assignments:
            events.append({
                "id": a.id,
                "type": self.ACTIVITY_ASSIGNED,
                "timestamp": a.assigned_at,
                "actor_id": a.assignee_id,
                "actor_type": a.assignee_type,
                "new_value": a.assignee_id,
                "reason": a.reason,
                "metadata": {"score": float(a.score) if a.score else None},
            })

        # Get messages
        if include_messages:
            messages = self.db.query(TicketMessage).filter(
                TicketMessage.ticket_id == ticket_id,
                TicketMessage.company_id == self.company_id,
            ).all()

            for m in messages:
                # Skip internal messages unless requested
                if m.is_internal and not include_internal:
                    continue

                events.append({
                    "id": m.id,
                    "type": self.ACTIVITY_MESSAGE_ADDED,
                    "timestamp": m.created_at,
                    "actor_id": None,  # Would need to track sender
                    "actor_type": m.role,
                    "metadata": {
                        "channel": m.channel,
                        "is_internal": m.is_internal,
                        "is_redacted": m.is_redacted,
                        "ai_confidence": float(m.ai_confidence) if m.ai_confidence else None,
                    },
                })

        # Get internal notes
        if include_notes:
            notes = self.db.query(TicketInternalNote).filter(
                TicketInternalNote.ticket_id == ticket_id,
                TicketInternalNote.company_id == self.company_id,
            ).all()

            for n in notes:
                events.append({
                    "id": n.id,
                    "type": self.ACTIVITY_NOTE_ADDED,
                    "timestamp": n.created_at,
                    "actor_id": n.author_id,
                    "actor_type": "human",
                    "metadata": {
                        "is_pinned": n.is_pinned,
                    },
                })

        # Get attachments
        attachments = self.db.query(TicketAttachment).filter(
            TicketAttachment.ticket_id == ticket_id,
            TicketAttachment.company_id == self.company_id,
        ).all()

        for a in attachments:
            events.append({
                "id": a.id,
                "type": self.ACTIVITY_ATTACHMENT_UPLOADED,
                "timestamp": a.created_at,
                "actor_id": a.uploaded_by,
                "actor_type": "human",
                "metadata": {
                    "filename": a.filename,
                    "file_size": a.file_size,
                    "mime_type": a.mime_type,
                },
            })

        # Get merges
        merges = self.db.query(TicketMerge).filter(
            or_(
                TicketMerge.primary_ticket_id == ticket_id,
                TicketMerge.merged_ticket_ids.contains(f'"{ticket_id}"'),
            ),
            TicketMerge.company_id == self.company_id,
        ).all()

        for m in merges:
            events.append({
                "id": m.id,
                "type": self.ACTIVITY_MERGED if not m.undone else self.ACTIVITY_UNMERGED,
                "timestamp": m.created_at,
                "actor_id": m.merged_by,
                "actor_type": "human",
                "reason": m.reason,
                "metadata": {
                    "primary_ticket_id": m.primary_ticket_id,
                    "merged_ticket_ids": json.loads(m.merged_ticket_ids or "[]"),
                    "undone": m.undone,
                },
            })

        # Sort by timestamp (newest first)
        events.sort(key=lambda x: x["timestamp"], reverse=True)

        # Filter by activity types
        if activity_types:
            events = [e for e in events if e["type"] in activity_types]

        total = len(events)

        # Paginate
        offset = (page - 1) * page_size
        paginated = events[offset:offset + page_size]

        return paginated, total

    # ── AGGREGATE STATISTICS ──────────────────────────────────────────────

    def get_activity_summary(
        self,
        ticket_id: str,
    ) -> Dict[str, Any]:
        """Get activity summary for a ticket.

        Args:
            ticket_id: Ticket ID

        Returns:
            Summary dict with counts and key events
        """
        timeline, total = self.get_timeline(
            ticket_id,
            include_messages=True,
            include_notes=True,
            include_internal=True,
            page_size=1000,  # Get all for summary
        )

        # Count by type
        type_counts = {}
        for event in timeline:
            event_type = event["type"]
            type_counts[event_type] = type_counts.get(event_type, 0) + 1

        # Find key events
        first_response = None
        first_assignment = None
        resolution = None

        for event in reversed(timeline):  # Oldest first
            if event["type"] == self.ACTIVITY_MESSAGE_ADDED:
                if event.get("metadata", {}).get("actor_type") in ["agent", "ai"]:
                    if not first_response:
                        first_response = event["timestamp"]

            if event["type"] == self.ACTIVITY_ASSIGNED:
                if not first_assignment:
                    first_assignment = event["timestamp"]

            if event["type"] == self.ACTIVITY_STATUS_CHANGE:
                if event.get("new_value") == "resolved":
                    if not resolution:
                        resolution = event["timestamp"]

        return {
            "total_activities": total,
            "activity_counts": type_counts,
            "first_response_at": first_response.isoformat() if first_response else None,
            "first_assignment_at": first_assignment.isoformat() if first_assignment else None,
            "resolved_at": resolution.isoformat() if resolution else None,
            "message_count": type_counts.get(self.ACTIVITY_MESSAGE_ADDED, 0),
            "note_count": type_counts.get(self.ACTIVITY_NOTE_ADDED, 0),
            "status_change_count": type_counts.get(self.ACTIVITY_STATUS_CHANGE, 0),
        }

    # ── HELPER METHODS FOR RECORDING ─────────────────────────────────────

    def record_status_change(
        self,
        ticket_id: str,
        from_status: str,
        to_status: str,
        actor_id: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Helper to record status change."""
        return self.record_activity(
            ticket_id=ticket_id,
            activity_type=self.ACTIVITY_STATUS_CHANGE,
            actor_id=actor_id,
            old_value=from_status,
            new_value=to_status,
            reason=reason,
        )

    def record_assignment(
        self,
        ticket_id: str,
        assignee_id: str,
        assignee_type: str,
        actor_id: Optional[str] = None,
        reason: Optional[str] = None,
        score: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Helper to record assignment."""
        return self.record_activity(
            ticket_id=ticket_id,
            activity_type=self.ACTIVITY_ASSIGNED,
            actor_id=actor_id,
            actor_type=assignee_type,
            new_value=assignee_id,
            reason=reason,
            metadata={"score": score},
        )

    def record_tag_change(
        self,
        ticket_id: str,
        tag: str,
        added: bool,
        actor_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Helper to record tag change."""
        return self.record_activity(
            ticket_id=ticket_id,
            activity_type=self.ACTIVITY_TAG_ADDED if added else self.ACTIVITY_TAG_REMOVED,
            actor_id=actor_id,
            new_value=tag if added else None,
            old_value=tag if not added else None,
        )

    def record_message(
        self,
        ticket_id: str,
        message_id: str,
        role: str,
        channel: str,
        is_internal: bool = False,
    ) -> Dict[str, Any]:
        """Helper to record message added."""
        return self.record_activity(
            ticket_id=ticket_id,
            activity_type=self.ACTIVITY_MESSAGE_ADDED,
            actor_type=role,
            metadata={
                "message_id": message_id,
                "channel": channel,
                "is_internal": is_internal,
            },
        )

    def record_note(
        self,
        ticket_id: str,
        note_id: str,
        author_id: str,
        is_pinned: bool = False,
    ) -> Dict[str, Any]:
        """Helper to record internal note."""
        return self.record_activity(
            ticket_id=ticket_id,
            activity_type=self.ACTIVITY_NOTE_ADDED,
            actor_id=author_id,
            metadata={
                "note_id": note_id,
                "is_pinned": is_pinned,
            },
        )

    def record_attachment(
        self,
        ticket_id: str,
        attachment_id: str,
        filename: str,
        file_size: int,
        actor_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Helper to record attachment upload."""
        return self.record_activity(
            ticket_id=ticket_id,
            activity_type=self.ACTIVITY_ATTACHMENT_UPLOADED,
            actor_id=actor_id,
            metadata={
                "attachment_id": attachment_id,
                "filename": filename,
                "file_size": file_size,
            },
        )

    def record_sla_event(
        self,
        ticket_id: str,
        event_type: str,  # sla_warning or sla_breached
        time_remaining: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Helper to record SLA event."""
        return self.record_activity(
            ticket_id=ticket_id,
            activity_type=event_type,
            actor_type="system",
            metadata={
                "time_remaining_seconds": time_remaining,
            },
        )
