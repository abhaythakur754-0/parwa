"""
PARWA Audit Service

Writes audit trail entries to the audit_trail table.
Every significant action (create, update, delete, login, etc.)
must be logged through this service.

Audit trail fields (from database/models/integration.py):
- id: UUID primary key
- company_id: Tenant ID (BC-001)
- actor_id: Who performed the action (user ID or system)
- actor_type: Type of actor (user, system, api_key)
- action: What was done (create, update, delete, login, etc.)
- resource_type: What was affected (ticket, user, subscription, etc.)
- resource_id: ID of the affected resource
- old_value: Previous value (for updates)
- new_value: New value (for creates/updates)
- ip_address: Client IP address
- user_agent: Client user agent string
- created_at: Timestamp
"""

import enum
import uuid
from datetime import datetime, timezone
from typing import Optional


class ActorType(str, enum.Enum):
    """Types of actors that can perform audited actions."""

    USER = "user"
    SYSTEM = "system"
    API_KEY = "api_key"


class AuditAction(str, enum.Enum):
    """Standard audit action types."""

    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"
    APPROVE = "approve"
    REJECT = "reject"
    EXPORT = "export"
    SETTINGS_CHANGE = "settings_change"
    PERMISSION_CHANGE = "permission_change"
    API_KEY_CREATE = "api_key_create"
    API_KEY_ROTATE = "api_key_rotate"
    API_KEY_REVOKE = "api_key_revoke"
    WEBHOOK_DELIVERED = "webhook_delivered"
    WEBHOOK_FAILED = "webhook_failed"


VALID_ACTOR_TYPES = {t.value for t in ActorType}


def validate_actor_type(actor_type: str) -> str:
    """Validate that actor_type is a known value.

    Args:
        actor_type: String to validate.

    Returns:
        Validated actor_type string.

    Raises:
        ValueError: If actor_type is not a valid ActorType.
    """
    if not actor_type or actor_type not in VALID_ACTOR_TYPES:
        raise ValueError(
            f"Invalid actor_type '{actor_type}'. "
            f"Must be one of: {', '.join(sorted(VALID_ACTOR_TYPES))}"
        )
    return actor_type


class AuditEntry:
    """Represents a single audit trail entry.

    This is the data structure for creating audit entries.
    The actual database write happens through the audit_service functions.
    """

    def __init__(
        self,
        company_id: str,
        actor_id: Optional[str] = None,
        actor_type: str = ActorType.SYSTEM.value,
        action: str = "unknown",
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        old_value: Optional[str] = None,
        new_value: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        # Validate company_id first (BC-001 — multi-tenant isolation)
        if not company_id or not isinstance(company_id, str):
            raise ValueError(
                "company_id is required and must be a "
                "non-empty string (BC-001)"
            )
        if len(company_id) > 128:
            raise ValueError("company_id must not exceed 128 characters")
        validate_actor_type(actor_type)
        self.id = str(uuid.uuid4())
        self.company_id = company_id
        self.actor_id = actor_id
        self.actor_type = actor_type
        self.action = action
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.old_value = old_value
        self.new_value = new_value
        self.ip_address = ip_address
        self.user_agent = user_agent
        self.created_at = datetime.now(timezone.utc)

    def to_dict(self) -> dict:
        """Convert to dictionary (for JSON serialization or DB insert)."""
        return {
            "id": self.id,
            "company_id": self.company_id,
            "actor_id": self.actor_id,
            "actor_type": self.actor_type,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "created_at": self.created_at,
        }


def create_audit_entry(
    company_id: str,
    actor_id: Optional[str] = None,
    actor_type: str = ActorType.SYSTEM.value,
    action: str = "unknown",
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    old_value: Optional[str] = None,
    new_value: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> AuditEntry:
    """Create an audit trail entry.

    This is the primary interface for creating audit entries.
    The entry is returned as an AuditEntry object that can be
    serialized to dict for database insertion.

    Args:
        company_id: Tenant ID (BC-001 — required for multi-tenant isolation).
        actor_id: ID of the user/system/api_key performing the action.
        actor_type: Type of actor (user, system, api_key).
        action: What action was performed.
        resource_type: Type of resource affected.
        resource_id: ID of the specific resource.
        old_value: Previous value (for updates).
        new_value: New value (for creates/updates).
        ip_address: Client IP address.
        user_agent: Client user agent.

    Returns:
        AuditEntry object ready for serialization.

    Raises:
        ValueError: If company_id is missing or actor_type is invalid.
    """
    if not company_id:
        raise ValueError("company_id is required for audit entries (BC-001)")

    return AuditEntry(
        company_id=company_id,
        actor_id=actor_id,
        actor_type=actor_type,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        old_value=old_value,
        new_value=new_value,
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_audit(
    company_id: str,
    actor_id: Optional[str] = None,
    actor_type: str = ActorType.SYSTEM.value,
    action: str = "unknown",
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    old_value: Optional[str] = None,
    new_value: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> dict:
    """Create and return audit entry as dict (for direct DB insertion).

    Convenience function that creates an AuditEntry and converts to dict.
    Use this when you need to pass the entry directly to a database session.

    Args:
        Same as create_audit_entry().

    Returns:
        Dictionary with all audit fields.
    """
    entry = create_audit_entry(
        company_id=company_id,
        actor_id=actor_id,
        actor_type=actor_type,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        old_value=old_value,
        new_value=new_value,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return entry.to_dict()
