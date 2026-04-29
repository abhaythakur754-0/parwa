"""
PARWA Ticket Event Emitters (Day 34)

Socket.io event emitters for ticket-related events.
Integrates with the existing event system in backend/app/core/events.py.

Events implemented:
- ticket:created, ticket:updated, ticket:status_changed
- ticket:assigned, ticket:message_added, ticket:note_added
- ticket:resolved, ticket:reopened, ticket:closed
- ticket:escalated, ticket:sla_warning, ticket:sla_breached
- ticket:collision, ticket:merged, ticket:incident_created, ticket:incident_resolved

Each event:
- Emits to room `tenant_{company_id}`
- Includes ticket_id, actor_id, and relevant data
- Uses the existing EventRegistry for validation

BC-001: All events are tenant-scoped.
BC-005: Events validated against registry.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.events import (
    EventCategory,
    EventRegistry,
    EventType,
    TicketEventPayload,
    get_event_registry,
)
from app.core.event_emitter import emit_ticket_event
from app.logger import get_logger

logger = get_logger("ticket_events")


# ── Ticket Event Types ───────────────────────────────────────────────────────

TICKET_EVENT_TYPES = {
    # Core ticket lifecycle events
    "ticket:created": "New ticket created",
    "ticket:updated": "Ticket properties updated",
    "ticket:status_changed": "Ticket status changed",
    "ticket:assigned": "Ticket assigned to agent",
    "ticket:message_added": "New message added to ticket",
    "ticket:note_added": "Internal note added to ticket",
    "ticket:resolved": "Ticket marked as resolved",
    "ticket:reopened": "Ticket reopened",
    "ticket:closed": "Ticket closed",
    # SLA and escalation events
    "ticket:escalated": "Ticket escalated to higher tier",
    "ticket:sla_warning": "SLA approaching breach threshold",
    "ticket:sla_breached": "SLA breached",
    # Special events
    "ticket:collision": "Multiple users viewing/editing ticket",
    "ticket:merged": "Ticket merged into another",
    "ticket:incident_created": "Incident created from ticket",
    "ticket:incident_resolved": "Incident resolved",
}


def register_ticket_events(registry: Optional[EventRegistry] = None) -> None:
    """Register all ticket event types with the event registry.

    This extends the core event registry with additional ticket-specific events.

    Args:
        registry: EventRegistry instance. Uses singleton if None.
    """
    reg = registry or get_event_registry()

    for event_type, description in TICKET_EVENT_TYPES.items():
        # Skip if already registered
        if reg.get(event_type) is not None:
            continue

        reg.register(
            EventType(
                type_str=event_type,
                category=EventCategory.TICKET,
                payload_schema=TicketEventPayload,
                description=description,
                rate_limit_per_sec=100,
                max_payload_bytes=10240,
            )
        )

    logger.info(
        "ticket_events_registered",
        extra={"event_count": len(TICKET_EVENT_TYPES)},
    )


# ── Event Emission Functions ─────────────────────────────────────────────────


async def emit_ticket_created(
    company_id: str,
    ticket_id: str,
    actor_id: str,
    ticket_data: Dict[str, Any],
    correlation_id: Optional[str] = None,
) -> bool:
    """Emit ticket:created event.

    Args:
        company_id: Tenant identifier
        ticket_id: The created ticket ID
        actor_id: User or system that created the ticket
        ticket_data: Ticket details (subject, priority, category, etc.)
        correlation_id: Optional correlation ID for tracing

    Returns:
        True if emitted successfully
    """
    payload = {
        "ticket_id": ticket_id,
        "company_id": company_id,
        "status": ticket_data.get("status"),
        "priority": ticket_data.get("priority"),
        "category": ticket_data.get("category"),
        "channel": ticket_data.get("channel"),
        "customer_id": ticket_data.get("customer_id"),
        "extra": {
            "subject": ticket_data.get("subject"),
            "actor_id": actor_id,
            "created_at": ticket_data.get(
                "created_at", datetime.now(timezone.utc).isoformat()
            ),
        },
    }

    return await emit_ticket_event(
        company_id=company_id,
        event_type="ticket:created",
        payload=payload,
        correlation_id=correlation_id,
    )


async def emit_ticket_updated(
    company_id: str,
    ticket_id: str,
    actor_id: str,
    changes: Dict[str, Any],
    correlation_id: Optional[str] = None,
) -> bool:
    """Emit ticket:updated event.

    Args:
        company_id: Tenant identifier
        ticket_id: The updated ticket ID
        actor_id: User or system that updated the ticket
        changes: Dict of field -> (old_value, new_value)
        correlation_id: Optional correlation ID for tracing

    Returns:
        True if emitted successfully
    """
    payload = {
        "ticket_id": ticket_id,
        "company_id": company_id,
        "extra": {
            "actor_id": actor_id,
            "changes": changes,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    }

    return await emit_ticket_event(
        company_id=company_id,
        event_type="ticket:updated",
        payload=payload,
        correlation_id=correlation_id,
    )


async def emit_ticket_status_changed(
    company_id: str,
    ticket_id: str,
    actor_id: str,
    from_status: str,
    to_status: str,
    reason: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> bool:
    """Emit ticket:status_changed event.

    Args:
        company_id: Tenant identifier
        ticket_id: The ticket ID
        actor_id: User or system that changed the status
        from_status: Previous status
        to_status: New status
        reason: Optional reason for status change
        correlation_id: Optional correlation ID for tracing

    Returns:
        True if emitted successfully
    """
    payload = {
        "ticket_id": ticket_id,
        "company_id": company_id,
        "status": to_status,
        "extra": {
            "actor_id": actor_id,
            "from_status": from_status,
            "to_status": to_status,
            "reason": reason,
            "changed_at": datetime.now(timezone.utc).isoformat(),
        },
    }

    return await emit_ticket_event(
        company_id=company_id,
        event_type="ticket:status_changed",
        payload=payload,
        correlation_id=correlation_id,
    )


async def emit_ticket_assigned(
    company_id: str,
    ticket_id: str,
    actor_id: str,
    assignee_id: Optional[str],
    previous_assignee_id: Optional[str] = None,
    assignment_type: str = "human",
    correlation_id: Optional[str] = None,
) -> bool:
    """Emit ticket:assigned event.

    Args:
        company_id: Tenant identifier
        ticket_id: The ticket ID
        actor_id: User or system that performed assignment
        assignee_id: New assignee ID (None if unassigned)
        previous_assignee_id: Previous assignee ID
        assignment_type: Type of assignment (human, ai, system)
        correlation_id: Optional correlation ID for tracing

    Returns:
        True if emitted successfully
    """
    payload = {
        "ticket_id": ticket_id,
        "company_id": company_id,
        "assignee_id": assignee_id,
        "extra": {
            "actor_id": actor_id,
            "previous_assignee_id": previous_assignee_id,
            "assignment_type": assignment_type,
            "assigned_at": datetime.now(timezone.utc).isoformat(),
        },
    }

    return await emit_ticket_event(
        company_id=company_id,
        event_type="ticket:assigned",
        payload=payload,
        correlation_id=correlation_id,
    )


async def emit_ticket_message_added(
    company_id: str,
    ticket_id: str,
    actor_id: str,
    message_id: str,
    message_role: str,
    content_preview: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> bool:
    """Emit ticket:message_added event.

    Args:
        company_id: Tenant identifier
        ticket_id: The ticket ID
        actor_id: User or system that added the message
        message_id: The new message ID
        message_role: Role of message sender (customer, agent, system, ai)
        content_preview: Optional preview of message content
        correlation_id: Optional correlation ID for tracing

    Returns:
        True if emitted successfully
    """
    payload = {
        "ticket_id": ticket_id,
        "company_id": company_id,
        "extra": {
            "actor_id": actor_id,
            "message_id": message_id,
            "message_role": message_role,
            "content_preview": content_preview[:100] if content_preview else None,
            "added_at": datetime.now(timezone.utc).isoformat(),
        },
    }

    return await emit_ticket_event(
        company_id=company_id,
        event_type="ticket:message_added",
        payload=payload,
        correlation_id=correlation_id,
    )


async def emit_ticket_note_added(
    company_id: str,
    ticket_id: str,
    actor_id: str,
    note_id: str,
    correlation_id: Optional[str] = None,
) -> bool:
    """Emit ticket:note_added event.

    Args:
        company_id: Tenant identifier
        ticket_id: The ticket ID
        actor_id: User that added the note
        note_id: The new note ID
        correlation_id: Optional correlation ID for tracing

    Returns:
        True if emitted successfully
    """
    payload = {
        "ticket_id": ticket_id,
        "company_id": company_id,
        "extra": {
            "actor_id": actor_id,
            "note_id": note_id,
            "added_at": datetime.now(timezone.utc).isoformat(),
        },
    }

    return await emit_ticket_event(
        company_id=company_id,
        event_type="ticket:note_added",
        payload=payload,
        correlation_id=correlation_id,
    )


async def emit_ticket_resolved(
    company_id: str,
    ticket_id: str,
    actor_id: str,
    resolution_time_minutes: Optional[float] = None,
    correlation_id: Optional[str] = None,
) -> bool:
    """Emit ticket:resolved event.

    Args:
        company_id: Tenant identifier
        ticket_id: The ticket ID
        actor_id: User or system that resolved the ticket
        resolution_time_minutes: Time to resolution in minutes
        correlation_id: Optional correlation ID for tracing

    Returns:
        True if emitted successfully
    """
    payload = {
        "ticket_id": ticket_id,
        "company_id": company_id,
        "status": "resolved",
        "extra": {
            "actor_id": actor_id,
            "resolution_time_minutes": resolution_time_minutes,
            "resolved_at": datetime.now(timezone.utc).isoformat(),
        },
    }

    return await emit_ticket_event(
        company_id=company_id,
        event_type="ticket:resolved",
        payload=payload,
        correlation_id=correlation_id,
    )


async def emit_ticket_reopened(
    company_id: str,
    ticket_id: str,
    actor_id: str,
    reopen_reason: Optional[str] = None,
    reopen_count: Optional[int] = None,
    correlation_id: Optional[str] = None,
) -> bool:
    """Emit ticket:reopened event.

    Args:
        company_id: Tenant identifier
        ticket_id: The ticket ID
        actor_id: User or system that reopened the ticket
        reopen_reason: Reason for reopening
        reopen_count: Number of times ticket has been reopened
        correlation_id: Optional correlation ID for tracing

    Returns:
        True if emitted successfully
    """
    payload = {
        "ticket_id": ticket_id,
        "company_id": company_id,
        "status": "reopened",
        "extra": {
            "actor_id": actor_id,
            "reopen_reason": reopen_reason,
            "reopen_count": reopen_count,
            "reopened_at": datetime.now(timezone.utc).isoformat(),
        },
    }

    return await emit_ticket_event(
        company_id=company_id,
        event_type="ticket:reopened",
        payload=payload,
        correlation_id=correlation_id,
    )


async def emit_ticket_closed(
    company_id: str,
    ticket_id: str,
    actor_id: str,
    closure_reason: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> bool:
    """Emit ticket:closed event.

    Args:
        company_id: Tenant identifier
        ticket_id: The ticket ID
        actor_id: User or system that closed the ticket
        closure_reason: Reason for closing
        correlation_id: Optional correlation ID for tracing

    Returns:
        True if emitted successfully
    """
    payload = {
        "ticket_id": ticket_id,
        "company_id": company_id,
        "status": "closed",
        "extra": {
            "actor_id": actor_id,
            "closure_reason": closure_reason,
            "closed_at": datetime.now(timezone.utc).isoformat(),
        },
    }

    return await emit_ticket_event(
        company_id=company_id,
        event_type="ticket:closed",
        payload=payload,
        correlation_id=correlation_id,
    )


async def emit_ticket_escalated(
    company_id: str,
    ticket_id: str,
    actor_id: str,
    from_level: int,
    to_level: int,
    escalation_reason: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> bool:
    """Emit ticket:escalated event.

    Args:
        company_id: Tenant identifier
        ticket_id: The ticket ID
        actor_id: User or system that escalated the ticket
        from_level: Previous escalation level (1=L1, 2=L2, 3=L3)
        to_level: New escalation level
        escalation_reason: Reason for escalation
        correlation_id: Optional correlation ID for tracing

    Returns:
        True if emitted successfully
    """
    payload = {
        "ticket_id": ticket_id,
        "company_id": company_id,
        "extra": {
            "actor_id": actor_id,
            "from_level": from_level,
            "to_level": to_level,
            "escalation_reason": escalation_reason,
            "escalated_at": datetime.now(timezone.utc).isoformat(),
        },
    }

    return await emit_ticket_event(
        company_id=company_id,
        event_type="ticket:escalated",
        payload=payload,
        correlation_id=correlation_id,
    )


async def emit_sla_warning(
    company_id: str,
    ticket_id: str,
    percentage_elapsed: float,
    minutes_remaining: float,
    sla_type: str = "resolution",
    correlation_id: Optional[str] = None,
) -> bool:
    """Emit ticket:sla_warning event (PS17: SLA approaching).

    Args:
        company_id: Tenant identifier
        ticket_id: The ticket ID
        percentage_elapsed: Percentage of SLA time elapsed (0-1)
        minutes_remaining: Minutes until SLA breach
        sla_type: Type of SLA (first_response, resolution)
        correlation_id: Optional correlation ID for tracing

    Returns:
        True if emitted successfully
    """
    payload = {
        "ticket_id": ticket_id,
        "company_id": company_id,
        "extra": {
            "percentage_elapsed": round(percentage_elapsed * 100, 1),
            "minutes_remaining": round(minutes_remaining, 1),
            "sla_type": sla_type,
            "warning_at": datetime.now(timezone.utc).isoformat(),
        },
    }

    return await emit_ticket_event(
        company_id=company_id,
        event_type="ticket:sla_warning",
        payload=payload,
        correlation_id=correlation_id,
    )


async def emit_sla_breach(
    company_id: str,
    ticket_id: str,
    breach_type: str = "resolution",
    minutes_overdue: Optional[float] = None,
    correlation_id: Optional[str] = None,
) -> bool:
    """Emit ticket:sla_breached event (PS11: SLA breach).

    Args:
        company_id: Tenant identifier
        ticket_id: The ticket ID
        breach_type: Type of SLA breach (first_response, resolution)
        minutes_overdue: Minutes past SLA deadline
        correlation_id: Optional correlation ID for tracing

    Returns:
        True if emitted successfully
    """
    payload = {
        "ticket_id": ticket_id,
        "company_id": company_id,
        "extra": {
            "breach_type": breach_type,
            "minutes_overdue": round(minutes_overdue, 1) if minutes_overdue else None,
            "breached_at": datetime.now(timezone.utc).isoformat(),
        },
    }

    return await emit_ticket_event(
        company_id=company_id,
        event_type="ticket:sla_breached",
        payload=payload,
        correlation_id=correlation_id,
    )


async def emit_ticket_collision(
    company_id: str,
    ticket_id: str,
    current_viewers: List[Dict[str, Any]],
    action: str = "viewing",
    correlation_id: Optional[str] = None,
) -> bool:
    """Emit ticket:collision event (MF11: Concurrent editing detection).

    Args:
        company_id: Tenant identifier
        ticket_id: The ticket ID
        current_viewers: List of users currently viewing/editing
        action: Action type (viewing, editing)
        correlation_id: Optional correlation ID for tracing

    Returns:
        True if emitted successfully
    """
    payload = {
        "ticket_id": ticket_id,
        "company_id": company_id,
        "extra": {
            "current_viewers": current_viewers,
            "action": action,
            "collision_at": datetime.now(timezone.utc).isoformat(),
        },
    }

    return await emit_ticket_event(
        company_id=company_id,
        event_type="ticket:collision",
        payload=payload,
        correlation_id=correlation_id,
    )


async def emit_ticket_merged(
    company_id: str,
    primary_ticket_id: str,
    merged_ticket_ids: List[str],
    actor_id: str,
    merge_reason: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> bool:
    """Emit ticket:merged event.

    Args:
        company_id: Tenant identifier
        primary_ticket_id: The ticket that absorbed others
        merged_ticket_ids: List of merged ticket IDs
        actor_id: User who performed the merge
        merge_reason: Reason for merging
        correlation_id: Optional correlation ID for tracing

    Returns:
        True if emitted successfully
    """
    payload = {
        "ticket_id": primary_ticket_id,
        "company_id": company_id,
        "extra": {
            "actor_id": actor_id,
            "merged_ticket_ids": merged_ticket_ids,
            "merge_reason": merge_reason,
            "merged_at": datetime.now(timezone.utc).isoformat(),
        },
    }

    return await emit_ticket_event(
        company_id=company_id,
        event_type="ticket:merged",
        payload=payload,
        correlation_id=correlation_id,
    )


async def emit_incident_created(
    company_id: str,
    ticket_id: str,
    incident_id: str,
    actor_id: str,
    incident_type: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> bool:
    """Emit ticket:incident_created event.

    Args:
        company_id: Tenant identifier
        ticket_id: The source ticket ID
        incident_id: The created incident ID
        actor_id: User or system that created the incident
        incident_type: Type of incident
        correlation_id: Optional correlation ID for tracing

    Returns:
        True if emitted successfully
    """
    payload = {
        "ticket_id": ticket_id,
        "company_id": company_id,
        "extra": {
            "actor_id": actor_id,
            "incident_id": incident_id,
            "incident_type": incident_type,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    }

    return await emit_ticket_event(
        company_id=company_id,
        event_type="ticket:incident_created",
        payload=payload,
        correlation_id=correlation_id,
    )


async def emit_incident_resolved(
    company_id: str,
    ticket_id: str,
    incident_id: str,
    actor_id: str,
    resolution_summary: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> bool:
    """Emit ticket:incident_resolved event.

    Args:
        company_id: Tenant identifier
        ticket_id: The related ticket ID
        incident_id: The resolved incident ID
        actor_id: User or system that resolved the incident
        resolution_summary: Summary of resolution
        correlation_id: Optional correlation ID for tracing

    Returns:
        True if emitted successfully
    """
    payload = {
        "ticket_id": ticket_id,
        "company_id": company_id,
        "extra": {
            "actor_id": actor_id,
            "incident_id": incident_id,
            "resolution_summary": resolution_summary,
            "resolved_at": datetime.now(timezone.utc).isoformat(),
        },
    }

    return await emit_ticket_event(
        company_id=company_id,
        event_type="ticket:incident_resolved",
        payload=payload,
        correlation_id=correlation_id,
    )


# ── Auto-register on module import ───────────────────────────────────────────

try:
    register_ticket_events()
except Exception as e:
    logger.warning(
        "ticket_events_registration_failed",
        extra={"error": str(e)},
    )
