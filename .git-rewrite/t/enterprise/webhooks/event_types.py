# Event Types - Week 47 Builder 2
# Event type definitions and registry

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from enum import Enum
from datetime import datetime
import uuid


class EventCategory(Enum):
    SYSTEM = "system"
    USER = "user"
    BILLING = "billing"
    NOTIFICATION = "notification"
    INTEGRATION = "integration"
    SECURITY = "security"
    AUDIT = "audit"
    CUSTOM = "custom"


class EventSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class EventTypeDefinition:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    category: EventCategory = EventCategory.CUSTOM
    severity: EventSeverity = EventSeverity.LOW
    description: str = ""
    schema: Dict[str, Any] = field(default_factory=dict)
    required_fields: List[str] = field(default_factory=list)
    optional_fields: List[str] = field(default_factory=list)
    topics: List[str] = field(default_factory=list)
    retention_days: int = 30
    created_at: datetime = field(default_factory=datetime.utcnow)


class EventTypeRegistry:
    """Registry for event type definitions"""

    def __init__(self):
        self._types: Dict[str, EventTypeDefinition] = {}
        self._by_category: Dict[EventCategory, Set[str]] = {
            cat: set() for cat in EventCategory
        }
        self._initialized = False

    def initialize_defaults(self) -> None:
        """Initialize with default event types"""
        if self._initialized:
            return

        defaults = [
            # System events
            EventTypeDefinition(
                name="system.startup",
                category=EventCategory.SYSTEM,
                severity=EventSeverity.LOW,
                description="System startup event",
                schema={"version": "string", "timestamp": "datetime"},
                required_fields=["version"],
                topics=["system"]
            ),
            EventTypeDefinition(
                name="system.shutdown",
                category=EventCategory.SYSTEM,
                severity=EventSeverity.MEDIUM,
                description="System shutdown event",
                schema={"reason": "string", "timestamp": "datetime"},
                required_fields=["reason"],
                topics=["system"]
            ),
            EventTypeDefinition(
                name="system.error",
                category=EventCategory.SYSTEM,
                severity=EventSeverity.HIGH,
                description="System error event",
                schema={"error_code": "string", "message": "string", "stack_trace": "string"},
                required_fields=["error_code", "message"],
                topics=["system", "alerts"]
            ),

            # User events
            EventTypeDefinition(
                name="user.created",
                category=EventCategory.USER,
                severity=EventSeverity.LOW,
                description="New user created",
                schema={"user_id": "string", "email": "string", "tenant_id": "string"},
                required_fields=["user_id", "email"],
                topics=["users", "audit"]
            ),
            EventTypeDefinition(
                name="user.updated",
                category=EventCategory.USER,
                severity=EventSeverity.LOW,
                description="User profile updated",
                schema={"user_id": "string", "changes": "dict"},
                required_fields=["user_id"],
                topics=["users", "audit"]
            ),
            EventTypeDefinition(
                name="user.deleted",
                category=EventCategory.USER,
                severity=EventSeverity.MEDIUM,
                description="User deleted",
                schema={"user_id": "string", "deleted_by": "string"},
                required_fields=["user_id"],
                topics=["users", "audit"]
            ),
            EventTypeDefinition(
                name="user.login",
                category=EventCategory.USER,
                severity=EventSeverity.LOW,
                description="User login event",
                schema={"user_id": "string", "ip_address": "string", "user_agent": "string"},
                required_fields=["user_id"],
                topics=["users", "security"]
            ),
            EventTypeDefinition(
                name="user.logout",
                category=EventCategory.USER,
                severity=EventSeverity.LOW,
                description="User logout event",
                schema={"user_id": "string", "session_duration": "int"},
                required_fields=["user_id"],
                topics=["users"]
            ),

            # Billing events
            EventTypeDefinition(
                name="billing.invoice_created",
                category=EventCategory.BILLING,
                severity=EventSeverity.LOW,
                description="Invoice created",
                schema={"invoice_id": "string", "amount": "float", "tenant_id": "string"},
                required_fields=["invoice_id", "amount"],
                topics=["billing", "invoices"]
            ),
            EventTypeDefinition(
                name="billing.payment_received",
                category=EventCategory.BILLING,
                severity=EventSeverity.LOW,
                description="Payment received",
                schema={"payment_id": "string", "amount": "float", "invoice_id": "string"},
                required_fields=["payment_id", "amount"],
                topics=["billing", "payments"]
            ),
            EventTypeDefinition(
                name="billing.payment_failed",
                category=EventCategory.BILLING,
                severity=EventSeverity.HIGH,
                description="Payment failed",
                schema={"payment_id": "string", "reason": "string", "retry_count": "int"},
                required_fields=["payment_id", "reason"],
                topics=["billing", "payments", "alerts"]
            ),
            EventTypeDefinition(
                name="billing.subscription_changed",
                category=EventCategory.BILLING,
                severity=EventSeverity.MEDIUM,
                description="Subscription plan changed",
                schema={"tenant_id": "string", "old_plan": "string", "new_plan": "string"},
                required_fields=["tenant_id", "new_plan"],
                topics=["billing", "subscriptions"]
            ),

            # Notification events
            EventTypeDefinition(
                name="notification.sent",
                category=EventCategory.NOTIFICATION,
                severity=EventSeverity.LOW,
                description="Notification sent",
                schema={"notification_id": "string", "channel": "string", "recipient": "string"},
                required_fields=["notification_id", "channel"],
                topics=["notifications"]
            ),
            EventTypeDefinition(
                name="notification.delivered",
                category=EventCategory.NOTIFICATION,
                severity=EventSeverity.LOW,
                description="Notification delivered",
                schema={"notification_id": "string", "delivered_at": "datetime"},
                required_fields=["notification_id"],
                topics=["notifications"]
            ),
            EventTypeDefinition(
                name="notification.failed",
                category=EventCategory.NOTIFICATION,
                severity=EventSeverity.MEDIUM,
                description="Notification delivery failed",
                schema={"notification_id": "string", "error": "string"},
                required_fields=["notification_id", "error"],
                topics=["notifications", "alerts"]
            ),

            # Security events
            EventTypeDefinition(
                name="security.login_failed",
                category=EventCategory.SECURITY,
                severity=EventSeverity.MEDIUM,
                description="Failed login attempt",
                schema={"email": "string", "ip_address": "string", "reason": "string"},
                required_fields=["email", "reason"],
                topics=["security", "alerts"]
            ),
            EventTypeDefinition(
                name="security.suspicious_activity",
                category=EventCategory.SECURITY,
                severity=EventSeverity.HIGH,
                description="Suspicious activity detected",
                schema={"user_id": "string", "activity_type": "string", "details": "dict"},
                required_fields=["activity_type"],
                topics=["security", "alerts"]
            ),
            EventTypeDefinition(
                name="security.api_key_rotated",
                category=EventCategory.SECURITY,
                severity=EventSeverity.MEDIUM,
                description="API key rotated",
                schema={"tenant_id": "string", "key_id": "string", "rotated_by": "string"},
                required_fields=["tenant_id", "key_id"],
                topics=["security", "audit"]
            ),

            # Integration events
            EventTypeDefinition(
                name="integration.connected",
                category=EventCategory.INTEGRATION,
                severity=EventSeverity.LOW,
                description="Integration connected",
                schema={"integration_id": "string", "type": "string", "tenant_id": "string"},
                required_fields=["integration_id", "type"],
                topics=["integrations"]
            ),
            EventTypeDefinition(
                name="integration.disconnected",
                category=EventCategory.INTEGRATION,
                severity=EventSeverity.MEDIUM,
                description="Integration disconnected",
                schema={"integration_id": "string", "reason": "string"},
                required_fields=["integration_id"],
                topics=["integrations", "alerts"]
            ),
            EventTypeDefinition(
                name="integration.sync_completed",
                category=EventCategory.INTEGRATION,
                severity=EventSeverity.LOW,
                description="Integration sync completed",
                schema={"integration_id": "string", "records_synced": "int", "duration_ms": "int"},
                required_fields=["integration_id"],
                topics=["integrations"]
            ),
            EventTypeDefinition(
                name="integration.sync_failed",
                category=EventCategory.INTEGRATION,
                severity=EventSeverity.HIGH,
                description="Integration sync failed",
                schema={"integration_id": "string", "error": "string"},
                required_fields=["integration_id", "error"],
                topics=["integrations", "alerts"]
            ),
        ]

        for event_type in defaults:
            self._types[event_type.name] = event_type
            self._by_category[event_type.category].add(event_type.name)

        self._initialized = True

    def register(self, definition: EventTypeDefinition) -> None:
        """Register a new event type"""
        self._types[definition.name] = definition
        self._by_category[definition.category].add(definition.name)

    def unregister(self, name: str) -> bool:
        """Unregister an event type"""
        if name not in self._types:
            return False
        definition = self._types[name]
        self._by_category[definition.category].discard(name)
        del self._types[name]
        return True

    def get(self, name: str) -> Optional[EventTypeDefinition]:
        """Get event type by name"""
        return self._types.get(name)

    def get_by_category(self, category: EventCategory) -> List[EventTypeDefinition]:
        """Get all event types in a category"""
        return [self._types[name] for name in self._by_category[category]]

    def get_all(self) -> List[EventTypeDefinition]:
        """Get all registered event types"""
        return list(self._types.values())

    def exists(self, name: str) -> bool:
        """Check if event type exists"""
        return name in self._types

    def validate_event(
        self,
        event_type: str,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate event payload against type definition"""
        definition = self._types.get(event_type)
        if not definition:
            return {"valid": False, "errors": [f"Unknown event type: {event_type}"]}

        errors = []
        for field in definition.required_fields:
            if field not in payload:
                errors.append(f"Missing required field: {field}")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "definition": definition
        }

    def get_topics_for_event(self, event_type: str) -> List[str]:
        """Get topics for an event type"""
        definition = self._types.get(event_type)
        return definition.topics if definition else []

    def get_severity(self, event_type: str) -> EventSeverity:
        """Get severity for an event type"""
        definition = self._types.get(event_type)
        return definition.severity if definition else EventSeverity.LOW

    def get_category(self, event_type: str) -> EventCategory:
        """Get category for an event type"""
        definition = self._types.get(event_type)
        return definition.category if definition else EventCategory.CUSTOM


# Global registry instance
event_type_registry = EventTypeRegistry()
