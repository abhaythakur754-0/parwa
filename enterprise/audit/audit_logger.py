# Audit Logger - Week 49 Builder 1
# Core audit logging engine for enterprise compliance

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import uuid
import json


class AuditEventType(Enum):
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    LOGOUT = "logout"
    EXPORT = "export"
    IMPORT = "import"
    ACCESS = "access"
    PERMISSION_CHANGE = "permission_change"
    CONFIG_CHANGE = "config_change"
    SECURITY_EVENT = "security_event"


class AuditSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AuditStatus(Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"


@dataclass
class AuditEvent:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    user_id: str = ""
    event_type: AuditEventType = AuditEventType.READ
    severity: AuditSeverity = AuditSeverity.LOW
    status: AuditStatus = AuditStatus.SUCCESS
    resource_type: str = ""
    resource_id: str = ""
    action: str = ""
    description: str = ""
    old_values: Dict[str, Any] = field(default_factory=dict)
    new_values: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    session_id: Optional[str] = None
    correlation_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class AuditConfig:
    enabled: bool = True
    log_payloads: bool = True
    log_ip_addresses: bool = True
    retention_days: int = 365
    encrypt_sensitive: bool = True
    sensitive_fields: List[str] = field(default_factory=lambda: [
        "password", "token", "secret", "api_key", "credit_card"
    ])


class AuditLogger:
    """Core audit logging engine for enterprise compliance"""

    def __init__(self, config: Optional[AuditConfig] = None):
        self.config = config or AuditConfig()
        self._events: List[AuditEvent] = []
        self._hooks: List[Any] = []
        self._metrics = {
            "total_events": 0,
            "by_type": {},
            "by_severity": {},
            "by_status": {}
        }

    def log(
        self,
        tenant_id: str,
        user_id: str,
        event_type: AuditEventType,
        resource_type: str,
        resource_id: str,
        action: str,
        description: str = "",
        severity: AuditSeverity = AuditSeverity.LOW,
        status: AuditStatus = AuditStatus.SUCCESS,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> AuditEvent:
        """Log an audit event"""
        if not self.config.enabled:
            return None

        # Sanitize sensitive fields
        if self.config.encrypt_sensitive:
            old_values = self._sanitize(old_values or {})
            new_values = self._sanitize(new_values or {})

        event = AuditEvent(
            tenant_id=tenant_id,
            user_id=user_id,
            event_type=event_type,
            severity=severity,
            status=status,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            description=description,
            old_values=old_values,
            new_values=new_values,
            metadata=metadata or {},
            ip_address=ip_address if self.config.log_ip_addresses else None,
            user_agent=user_agent,
            session_id=session_id,
            correlation_id=correlation_id
        )

        self._events.append(event)
        self._update_metrics(event)
        self._trigger_hooks(event)

        return event

    def _sanitize(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize sensitive fields"""
        result = {}
        for key, value in data.items():
            if key.lower() in [f.lower() for f in self.config.sensitive_fields]:
                result[key] = "***REDACTED***"
            elif isinstance(value, dict):
                result[key] = self._sanitize(value)
            else:
                result[key] = value
        return result

    def _update_metrics(self, event: AuditEvent) -> None:
        """Update aggregate metrics"""
        self._metrics["total_events"] += 1

        # By type
        type_key = event.event_type.value
        self._metrics["by_type"][type_key] = self._metrics["by_type"].get(type_key, 0) + 1

        # By severity
        sev_key = event.severity.value
        self._metrics["by_severity"][sev_key] = self._metrics["by_severity"].get(sev_key, 0) + 1

        # By status
        status_key = event.status.value
        self._metrics["by_status"][status_key] = self._metrics["by_status"].get(status_key, 0) + 1

    def _trigger_hooks(self, event: AuditEvent) -> None:
        """Trigger registered hooks for event processing"""
        for hook in self._hooks:
            try:
                hook(event)
            except Exception:
                pass

    def register_hook(self, hook: Any) -> None:
        """Register a hook for audit event processing"""
        self._hooks.append(hook)

    def log_create(
        self,
        tenant_id: str,
        user_id: str,
        resource_type: str,
        resource_id: str,
        new_values: Dict[str, Any],
        **kwargs
    ) -> AuditEvent:
        """Log a create event"""
        return self.log(
            tenant_id=tenant_id,
            user_id=user_id,
            event_type=AuditEventType.CREATE,
            resource_type=resource_type,
            resource_id=resource_id,
            action="create",
            new_values=new_values,
            **kwargs
        )

    def log_update(
        self,
        tenant_id: str,
        user_id: str,
        resource_type: str,
        resource_id: str,
        old_values: Dict[str, Any],
        new_values: Dict[str, Any],
        **kwargs
    ) -> AuditEvent:
        """Log an update event"""
        return self.log(
            tenant_id=tenant_id,
            user_id=user_id,
            event_type=AuditEventType.UPDATE,
            resource_type=resource_type,
            resource_id=resource_id,
            action="update",
            old_values=old_values,
            new_values=new_values,
            **kwargs
        )

    def log_delete(
        self,
        tenant_id: str,
        user_id: str,
        resource_type: str,
        resource_id: str,
        old_values: Dict[str, Any],
        **kwargs
    ) -> AuditEvent:
        """Log a delete event"""
        return self.log(
            tenant_id=tenant_id,
            user_id=user_id,
            event_type=AuditEventType.DELETE,
            resource_type=resource_type,
            resource_id=resource_id,
            action="delete",
            old_values=old_values,
            **kwargs
        )

    def log_read(
        self,
        tenant_id: str,
        user_id: str,
        resource_type: str,
        resource_id: str,
        **kwargs
    ) -> AuditEvent:
        """Log a read event"""
        return self.log(
            tenant_id=tenant_id,
            user_id=user_id,
            event_type=AuditEventType.READ,
            resource_type=resource_type,
            resource_id=resource_id,
            action="read",
            **kwargs
        )

    def log_login(
        self,
        tenant_id: str,
        user_id: str,
        ip_address: str,
        success: bool = True,
        **kwargs
    ) -> AuditEvent:
        """Log a login event"""
        return self.log(
            tenant_id=tenant_id,
            user_id=user_id,
            event_type=AuditEventType.LOGIN,
            resource_type="session",
            resource_id=user_id,
            action="login",
            status=AuditStatus.SUCCESS if success else AuditStatus.FAILURE,
            ip_address=ip_address,
            severity=AuditSeverity.MEDIUM,
            **kwargs
        )

    def log_security_event(
        self,
        tenant_id: str,
        user_id: str,
        description: str,
        severity: AuditSeverity = AuditSeverity.HIGH,
        **kwargs
    ) -> AuditEvent:
        """Log a security event"""
        return self.log(
            tenant_id=tenant_id,
            user_id=user_id,
            event_type=AuditEventType.SECURITY_EVENT,
            resource_type="security",
            resource_id=str(uuid.uuid4()),
            action="security_event",
            description=description,
            severity=severity,
            **kwargs
        )

    def get_event(self, event_id: str) -> Optional[AuditEvent]:
        """Get an event by ID"""
        for event in self._events:
            if event.id == event_id:
                return event
        return None

    def get_events_by_tenant(
        self,
        tenant_id: str,
        limit: int = 100
    ) -> List[AuditEvent]:
        """Get events for a tenant"""
        events = [e for e in self._events if e.tenant_id == tenant_id]
        return events[-limit:]

    def get_events_by_user(
        self,
        user_id: str,
        limit: int = 100
    ) -> List[AuditEvent]:
        """Get events for a user"""
        events = [e for e in self._events if e.user_id == user_id]
        return events[-limit:]

    def get_events_by_resource(
        self,
        resource_type: str,
        resource_id: str
    ) -> List[AuditEvent]:
        """Get events for a resource"""
        return [
            e for e in self._events
            if e.resource_type == resource_type and e.resource_id == resource_id
        ]

    def get_events_by_correlation(
        self,
        correlation_id: str
    ) -> List[AuditEvent]:
        """Get events by correlation ID"""
        return [e for e in self._events if e.correlation_id == correlation_id]

    def get_metrics(self) -> Dict[str, Any]:
        """Get audit metrics"""
        return {
            **self._metrics,
            "total_events_stored": len(self._events)
        }

    def export_events(
        self,
        tenant_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Export events for compliance reporting"""
        events = [e for e in self._events if e.tenant_id == tenant_id]

        if start_time:
            events = [e for e in events if e.timestamp >= start_time]
        if end_time:
            events = [e for e in events if e.timestamp <= end_time]

        return [
            {
                "id": e.id,
                "tenant_id": e.tenant_id,
                "timestamp": e.timestamp.isoformat(),
                "user_id": e.user_id,
                "event_type": e.event_type.value,
                "severity": e.severity.value,
                "status": e.status.value,
                "resource_type": e.resource_type,
                "resource_id": e.resource_id,
                "action": e.action,
                "description": e.description,
                "ip_address": e.ip_address,
                "metadata": e.metadata
            }
            for e in events
        ]

    def cleanup_old_events(self, days: Optional[int] = None) -> int:
        """Remove events older than retention period"""
        from datetime import timedelta
        retention_days = days or self.config.retention_days
        cutoff = datetime.utcnow() - timedelta(days=retention_days)

        initial_count = len(self._events)
        self._events = [e for e in self._events if e.timestamp >= cutoff]

        return initial_count - len(self._events)
