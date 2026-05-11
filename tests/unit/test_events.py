"""
Tests for PARWA Event Type Registry (Day 19)

Tests:
- All 22 event types registered
- Payload validation per category
- Unknown event type rejection
- Invalid payload rejection
- Category filtering
- Duplicate registration prevention
- Registry reset for testing
"""

import pytest

from backend.app.core.events import (
    AIEventPayload,
    ApprovalEventPayload,
    EventCategory,
    EventRegistry,
    EventType,
    NotificationEventPayload,
    SystemEventPayload,
    TicketEventPayload,
    get_event_registry,
    reset_event_registry,
)


@pytest.fixture(autouse=True)
def _reset_registry():
    """Reset singleton before each test."""
    reset_event_registry()
    yield
    reset_event_registry()


class TestEventRegistryCore:
    """Test core registry functionality."""

    def test_all_22_events_registered(self):
        """All 22 core event types are registered."""
        reg = get_event_registry()
        assert len(reg.all_types()) == 22

    def test_ticket_events_count(self):
        """6 ticket events registered."""
        reg = get_event_registry()
        ticket = reg.get_events_by_category(EventCategory.TICKET)
        assert len(ticket) == 6

    def test_ai_events_count(self):
        """4 AI events registered."""
        reg = get_event_registry()
        ai = reg.get_events_by_category(EventCategory.AI)
        assert len(ai) == 4

    def test_approval_events_count(self):
        """5 approval events registered."""
        reg = get_event_registry()
        approval = reg.get_events_by_category(EventCategory.APPROVAL)
        assert len(approval) == 5

    def test_notification_events_count(self):
        """3 notification events registered."""
        reg = get_event_registry()
        notif = reg.get_events_by_category(EventCategory.NOTIFICATION)
        assert len(notif) == 3

    def test_system_events_count(self):
        """4 system events registered."""
        reg = get_event_registry()
        system = reg.get_events_by_category(EventCategory.SYSTEM)
        assert len(system) == 4

    def test_ticket_new_registered(self):
        """ticket:new is registered."""
        reg = get_event_registry()
        assert reg.get("ticket:new") is not None

    def test_ai_draft_ready_registered(self):
        """ai:draft_ready is registered."""
        reg = get_event_registry()
        assert reg.get("ai:draft_ready") is not None

    def test_approval_pending_registered(self):
        """approval:pending is registered."""
        reg = get_event_registry()
        assert reg.get("approval:pending") is not None

    def test_notification_new_registered(self):
        """notification:new is registered."""
        reg = get_event_registry()
        assert reg.get("notification:new") is not None

    def test_system_health_registered(self):
        """system:health is registered."""
        reg = get_event_registry()
        assert reg.get("system:health") is not None


class TestEventRegistryUnknown:
    """Test unknown event type handling."""

    def test_unknown_type_returns_none(self):
        """get() returns None for unknown event type."""
        reg = get_event_registry()
        assert reg.get("unknown:event") is None

    def test_validate_unknown_raises(self):
        """validate() raises ValueError for unknown event type."""
        reg = get_event_registry()
        with pytest.raises(ValueError, match="Unknown event type"):
            reg.validate("unknown:event", {})


class TestEventRegistryDuplicate:
    """Test duplicate registration prevention."""

    def test_duplicate_registration_raises(self):
        """Registering same event type twice raises ValueError."""
        reg = EventRegistry()
        et = EventType(
            type_str="test:dup",
            category=EventCategory.SYSTEM,
            payload_schema=SystemEventPayload,
            description="test",
        )
        reg.register(et)
        with pytest.raises(ValueError, match="already registered"):
            reg.register(et)


class TestEventRegistryReset:
    """Test registry reset functionality."""

    def test_reset_creates_fresh_registry(self):
        """reset_event_registry creates a fresh 22-event registry."""
        reg = get_event_registry()
        original_count = len(reg.all_types())
        reset_event_registry()
        reg2 = get_event_registry()
        assert len(reg2.all_types()) == original_count
        assert len(reg2.all_types()) == 22


class TestTicketPayloadValidation:
    """Test ticket event payload validation."""

    def test_valid_minimal_payload(self):
        """Minimal ticket payload validates with required fields."""
        reg = get_event_registry()
        result = reg.validate("ticket:new", {
            "ticket_id": "t-123",
            "company_id": "acme",
        })
        assert result["ticket_id"] == "t-123"
        assert result["company_id"] == "acme"

    def test_full_payload(self):
        """Full ticket payload validates correctly."""
        reg = get_event_registry()
        result = reg.validate("ticket:assigned", {
            "ticket_id": "t-123",
            "company_id": "acme",
            "status": "assigned",
            "assignee_id": "u-456",
            "priority": "high",
            "channel": "email",
            "message": "Hello",
            "customer_id": "c-789",
        })
        assert result["assignee_id"] == "u-456"
        assert result["channel"] == "email"

    def test_missing_ticket_id_raises(self):
        """Missing ticket_id raises validation error."""
        reg = get_event_registry()
        with pytest.raises(Exception):
            reg.validate("ticket:new", {"company_id": "acme"})

    def test_extra_fields_allowed(self):
        """Extra fields in payload are ignored (Pydantic strict=False)."""
        reg = get_event_registry()
        result = reg.validate("ticket:new", {
            "ticket_id": "t-123",
            "company_id": "acme",
            "extra": {"custom_field": "value"},
        })
        assert result["ticket_id"] == "t-123"


class TestAIPayloadValidation:
    """Test AI event payload validation."""

    def test_valid_ai_payload(self):
        """Valid AI payload with confidence."""
        reg = get_event_registry()
        result = reg.validate("ai:classification", {
            "ticket_id": "t-123",
            "company_id": "acme",
            "confidence": 85.5,
            "intent": "refund",
            "sentiment": -0.3,
            "model_tier": "light",
        })
        assert result["confidence"] == 85.5
        assert result["intent"] == "refund"

    def test_confidence_above_100_raises(self):
        """Confidence > 100 raises validation error."""
        reg = get_event_registry()
        with pytest.raises(Exception):
            reg.validate("ai:classification", {
                "ticket_id": "t-1",
                "company_id": "acme",
                "confidence": 101,
            })

    def test_sentiment_below_minus1_raises(self):
        """Sentiment < -1 raises validation error."""
        reg = get_event_registry()
        with pytest.raises(Exception):
            reg.validate("ai:classification", {
                "ticket_id": "t-1",
                "company_id": "acme",
                "sentiment": -2,
            })


class TestApprovalPayloadValidation:
    """Test approval event payload validation."""

    def test_valid_approval_payload(self):
        """Valid approval payload validates."""
        reg = get_event_registry()
        result = reg.validate("approval:pending", {
            "approval_id": "a-123",
            "company_id": "acme",
            "action_type": "refund",
            "ticket_ids": ["t-1", "t-2"],
        })
        assert result["approval_id"] == "a-123"

    def test_missing_approval_id_raises(self):
        """Missing approval_id raises validation error."""
        reg = get_event_registry()
        with pytest.raises(Exception):
            reg.validate("approval:approved", {"company_id": "acme"})


class TestNotificationPayloadValidation:
    """Test notification event payload validation."""

    def test_valid_notification_payload(self):
        """Valid notification payload validates."""
        reg = get_event_registry()
        result = reg.validate("notification:new", {
            "company_id": "acme",
            "user_id": "u-123",
            "title": "New ticket",
            "message": "Ticket t-1 was created",
        })
        assert result["title"] == "New ticket"

    def test_notification_minimal(self):
        """Minimal notification with only company_id."""
        reg = get_event_registry()
        result = reg.validate("notification:new", {
            "company_id": "acme",
        })
        assert result["company_id"] == "acme"


class TestSystemPayloadValidation:
    """Test system event payload validation."""

    def test_system_event_without_company_id(self):
        """System events can omit company_id (global events)."""
        reg = get_event_registry()
        result = reg.validate("system:health", {
            "subsystem": "redis",
            "status": "healthy",
        })
        assert result["subsystem"] == "redis"

    def test_system_event_with_company_id(self):
        """System events can include company_id."""
        reg = get_event_registry()
        result = reg.validate("system:error", {
            "company_id": "acme",
            "subsystem": "celery",
            "message": "Worker crashed",
            "metric_value": 42.0,
        })
        assert result["company_id"] == "acme"


class TestEventTypeConfig:
    """Test EventType configuration."""

    def test_default_max_payload_bytes(self):
        """Default max payload is 10KB."""
        et = EventType(
            type_str="test",
            category=EventCategory.SYSTEM,
            payload_schema=SystemEventPayload,
            description="test",
        )
        assert et.max_payload_bytes == 10240

    def test_custom_max_payload_bytes(self):
        """Custom max payload can be set."""
        et = EventType(
            type_str="test",
            category=EventCategory.SYSTEM,
            payload_schema=SystemEventPayload,
            description="test",
            max_payload_bytes=512,
        )
        assert et.max_payload_bytes == 512

    def test_default_rate_limit(self):
        """Default rate limit is 100 per second."""
        et = EventType(
            type_str="test",
            category=EventCategory.SYSTEM,
            payload_schema=SystemEventPayload,
            description="test",
        )
        assert et.rate_limit_per_sec == 100

    def test_check_payload_size(self):
        """check_payload_size returns byte estimate."""
        et = EventType(
            type_str="test",
            category=EventCategory.SYSTEM,
            payload_schema=SystemEventPayload,
            description="test",
        )
        size = et.check_payload_size({"key": "value"})
        assert size > 0

    def test_repr(self):
        """EventType repr is informative."""
        et = EventType(
            type_str="ticket:new",
            category=EventCategory.TICKET,
            payload_schema=TicketEventPayload,
            description="test",
        )
        assert "ticket:new" in repr(et)
        assert "ticket" in repr(et)


class TestAllTypeStrings:
    """Test all_type_strings returns all registered type strings."""

    def test_returns_22_strings(self):
        """all_type_strings returns exactly 22 type strings."""
        reg = get_event_registry()
        strings = reg.all_type_strings()
        assert len(strings) == 22
        assert "ticket:new" in strings
        assert "system:maintenance" in strings
