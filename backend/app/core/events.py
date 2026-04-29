"""
PARWA Event Type Registry (BC-005)

Defines all event types used in the PARWA real-time system.
Every event has:
- A registered type string (e.g., "ticket:new")
- A Pydantic payload schema for validation
- A category (ticket, ai, approval, notification, system)
- Rate limit configuration
"""

import json
from enum import Enum
from typing import Any, Dict, Optional, Type

from pydantic import BaseModel, Field

# ── Event Categories ──────────────────────────────────────


class EventCategory(str, Enum):
    """Category of a PARWA real-time event."""

    TICKET = "ticket"
    AI = "ai"
    APPROVAL = "approval"
    NOTIFICATION = "notification"
    SYSTEM = "system"
    SHADOW = "shadow"


# ── Event Payload Schemas ────────────────────────────────


class TicketEventPayload(BaseModel):
    """Schema for ticket-scoped events."""

    ticket_id: str
    company_id: str
    status: Optional[str] = None
    assignee_id: Optional[str] = None
    priority: Optional[str] = None
    channel: Optional[str] = None
    message: Optional[str] = None
    customer_id: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None


class AIEventPayload(BaseModel):
    """Schema for AI-scoped events."""

    ticket_id: str
    company_id: str
    confidence: Optional[float] = Field(default=None, ge=0, le=100)
    intent: Optional[str] = None
    sentiment: Optional[float] = Field(default=None, ge=-1, le=1)
    draft_text: Optional[str] = None
    model_tier: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None


class ApprovalEventPayload(BaseModel):
    """Schema for approval-scoped events."""

    approval_id: str
    company_id: str
    action_type: Optional[str] = None
    status: Optional[str] = None
    approver_id: Optional[str] = None
    ticket_ids: Optional[list] = None
    reason: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None


class NotificationEventPayload(BaseModel):
    """Schema for notification-scoped events."""

    company_id: str
    user_id: Optional[str] = None
    notification_type: Optional[str] = None
    title: Optional[str] = None
    message: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None


class SystemEventPayload(BaseModel):
    """Schema for system-scoped events. company_id is optional."""

    company_id: Optional[str] = None
    subsystem: Optional[str] = None
    status: Optional[str] = None
    message: Optional[str] = None
    metric_value: Optional[float] = None
    extra: Optional[Dict[str, Any]] = None


class ShadowModeEventPayload(BaseModel):
    """Schema for shadow mode events."""

    company_id: str
    mode: Optional[str] = None
    previous_mode: Optional[str] = None
    action_type: Optional[str] = None
    risk_score: Optional[float] = None
    shadow_log_id: Optional[str] = None
    manager_id: Optional[str] = None
    decision: Optional[str] = None
    set_via: Optional[str] = None
    reason: Optional[str] = None
    pending_count: Optional[int] = None
    extra: Optional[Dict[str, Any]] = None


# ── Event Type Definition ────────────────────────────────


class EventType:
    """Represents a registered event type with schema and metadata."""

    def __init__(
        self,
        type_str: str,
        category: EventCategory,
        payload_schema: Type[BaseModel],
        description: str,
        rate_limit_per_sec: int = 100,
        max_payload_bytes: int = 10240,
    ):
        self.type_str = type_str
        self.category = category
        self.payload_schema = payload_schema
        self.description = description
        self.rate_limit_per_sec = rate_limit_per_sec
        self.max_payload_bytes = max_payload_bytes

    def validate_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Validate payload against schema. Returns cleaned payload."""
        return self.payload_schema(**payload).model_dump(exclude_none=True)

    def check_payload_size(self, payload: Dict[str, Any]) -> int:
        """Return approximate byte size of payload when JSON-serialized."""
        return len(json.dumps(payload, default=str).encode("utf-8"))

    def __repr__(self) -> str:
        return f"EventType({self.type_str!r}, " f"category={self.category.value!r})"


# ── Event Registry ────────────────────────────────────────


class EventRegistry:
    """Registry of all event types. Singleton via get_event_registry()."""

    def __init__(self):
        self._events: Dict[str, EventType] = {}
        self._register_core_events()

    def register(self, event_type: EventType) -> None:
        """Register a new event type. Raises ValueError if duplicate."""
        if event_type.type_str in self._events:
            raise ValueError(f"Event type '{event_type.type_str}' already registered")
        self._events[event_type.type_str] = event_type

    def get(self, type_str: str) -> Optional[EventType]:
        """Get event type by string, or None if not found."""
        return self._events.get(type_str)

    def validate(self, type_str: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Validate event type and payload. Returns cleaned payload."""
        et = self._events.get(type_str)
        if et is None:
            raise ValueError(f"Unknown event type: '{type_str}'")
        return et.validate_payload(payload)

    def get_events_by_category(self, category: EventCategory) -> list:
        """Get all event types in a category."""
        return [et for et in self._events.values() if et.category == category]

    def all_types(self) -> list:
        """Get all registered event types."""
        return list(self._events.values())

    def all_type_strings(self) -> list:
        """Get all registered event type strings."""
        return list(self._events.keys())

    def _register_core_events(self) -> None:
        """Register all core PARWA event types (22 events)."""
        # ── Ticket Events (6) ──
        for type_str, desc in [
            ("ticket:new", "New ticket created"),
            ("ticket:assigned", "Ticket assigned to agent"),
            ("ticket:updated", "Ticket status/priority changed"),
            ("ticket:resolved", "Ticket marked as resolved"),
            ("ticket:escalated", "Ticket escalated"),
            ("ticket:message_new", "New message added to ticket"),
        ]:
            self.register(
                EventType(
                    type_str=type_str,
                    category=EventCategory.TICKET,
                    payload_schema=TicketEventPayload,
                    description=desc,
                )
            )

        # ── AI Events (4) ──
        for type_str, desc in [
            ("ai:draft_ready", "AI draft response generated"),
            ("ai:response_sent", "AI auto-response sent"),
            ("ai:confidence_low", "Confidence dropped below threshold"),
            ("ai:classification", "Ticket classified by AI"),
        ]:
            self.register(
                EventType(
                    type_str=type_str,
                    category=EventCategory.AI,
                    payload_schema=AIEventPayload,
                    description=desc,
                )
            )

        # ── Approval Events (5) ──
        for type_str, desc in [
            ("approval:pending", "New approval queued"),
            ("approval:approved", "Action approved"),
            ("approval:rejected", "Action rejected"),
            ("approval:timeout", "Approval timed out (72h)"),
            ("approval:batch", "Batch approval completed"),
        ]:
            self.register(
                EventType(
                    type_str=type_str,
                    category=EventCategory.APPROVAL,
                    payload_schema=ApprovalEventPayload,
                    description=desc,
                )
            )

        # ── Notification Events (3) ──
        for type_str, desc in [
            ("notification:new", "New notification for user"),
            ("notification:read", "User read notification"),
            ("notification:bulk", "Bulk notification (team-wide)"),
        ]:
            self.register(
                EventType(
                    type_str=type_str,
                    category=EventCategory.NOTIFICATION,
                    payload_schema=NotificationEventPayload,
                    description=desc,
                )
            )

        # ── System Events (4) ──
        for type_str, desc in [
            ("system:health", "Subsystem health status change"),
            ("system:queue_depth", "Queue depth warning"),
            ("system:error", "Critical error occurred"),
            ("system:maintenance", "Maintenance mode toggle"),
        ]:
            self.register(
                EventType(
                    type_str=type_str,
                    category=EventCategory.SYSTEM,
                    payload_schema=SystemEventPayload,
                    description=desc,
                )
            )

        # ── Shadow Mode Events (6) ──
        for type_str, desc in [
            (
                "shadow:mode_changed",
                "System shadow mode changed (shadow/supervised/graduated)",
            ),
            ("shadow:action_pending", "New shadow action awaiting approval"),
            ("shadow:action_resolved", "Shadow action approved or rejected"),
            ("shadow:action_undone", "Auto-approved action was undone"),
            ("shadow:preference_changed", "Per-category shadow preference updated"),
            ("shadow:stats_updated", "Shadow mode statistics refreshed"),
        ]:
            self.register(
                EventType(
                    type_str=type_str,
                    category=EventCategory.SHADOW,
                    payload_schema=ShadowModeEventPayload,
                    description=desc,
                )
            )


# ── Singleton ─────────────────────────────────────────────

_registry_instance: Optional[EventRegistry] = None


def get_event_registry() -> EventRegistry:
    """Get the singleton EventRegistry instance."""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = EventRegistry()
    return _registry_instance


def reset_event_registry() -> None:
    """Reset the registry singleton (for testing only)."""
    global _registry_instance
    _registry_instance = EventRegistry()
