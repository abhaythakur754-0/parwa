"""
Audit Trail Module

Provides comprehensive audit logging for multi-tenant environments.
Tracks all cross-tenant and sensitive operations.
"""

from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
import logging
import json
import hashlib

logger = logging.getLogger(__name__)


class AuditEventType(str, Enum):
    """Types of audit events"""
    DATA_ACCESS = "data_access"
    DATA_MODIFICATION = "data_modification"
    DATA_DELETION = "data_deletion"
    CONFIGURATION_CHANGE = "configuration_change"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    CROSS_TENANT_ACCESS = "cross_tenant_access"
    POLICY_VIOLATION = "policy_violation"
    SYSTEM_EVENT = "system_event"
    USER_ACTION = "user_action"
    INTEGRATION = "integration"
    EXPORT = "export"
    IMPORT = "import"


class AuditSeverity(str, Enum):
    """Severity levels for audit events"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """Represents an audit event"""
    event_id: str
    event_type: AuditEventType
    tenant_id: str
    user_id: Optional[str]
    action: str
    resource: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    severity: AuditSeverity = AuditSeverity.INFO
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    outcome: str = "success"  # success, failure, denied
    cross_tenant: bool = False
    target_tenant_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AuditQuery:
    """Query parameters for audit search"""
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    event_types: Optional[List[AuditEventType]] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    severity: Optional[AuditSeverity] = None
    resource: Optional[str] = None
    outcome: Optional[str] = None
    limit: int = 100
    offset: int = 0


class AuditTrail:
    """
    Manages audit trail for multi-tenant environments.

    Features:
    - Comprehensive event logging
    - Cross-tenant access tracking
    - Search and filtering
    - Retention management
    - Compliance reporting
    """

    def __init__(
        self,
        retention_days: int = 365,
        enable_encryption: bool = False
    ):
        self.retention_days = retention_days
        self.enable_encryption = enable_encryption

        # Event storage (in production, would use database)
        self._events: List[AuditEvent] = []
        self._event_index: Dict[str, Set[int]] = {
            "tenant": {},
            "user": {},
            "type": {}
        }

        # Statistics
        self._stats = {
            "total_events": 0,
            "events_by_type": {},
            "events_by_tenant": {},
            "cross_tenant_events": 0
        }

    def log_event(
        self,
        event_type: AuditEventType,
        tenant_id: str,
        action: str,
        resource: str,
        user_id: Optional[str] = None,
        severity: AuditSeverity = AuditSeverity.INFO,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
        request_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        outcome: str = "success",
        target_tenant_id: Optional[str] = None
    ) -> AuditEvent:
        """
        Log an audit event.

        Args:
            event_type: Type of event
            tenant_id: Tenant ID
            action: Action performed
            resource: Resource affected
            user_id: Optional user ID
            severity: Event severity
            ip_address: Optional client IP
            user_agent: Optional client user agent
            session_id: Optional session ID
            request_id: Optional request ID
            details: Additional event details
            outcome: Event outcome
            target_tenant_id: For cross-tenant events

        Returns:
            Created AuditEvent
        """
        event_id = self._generate_event_id()

        event = AuditEvent(
            event_id=event_id,
            event_type=event_type,
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            resource=resource,
            severity=severity,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
            request_id=request_id,
            details=details or {},
            outcome=outcome,
            cross_tenant=target_tenant_id is not None and target_tenant_id != tenant_id,
            target_tenant_id=target_tenant_id
        )

        # Store event
        self._events.append(event)
        event_idx = len(self._events) - 1

        # Update indexes
        self._index_event(event, event_idx)

        # Update statistics
        self._update_stats(event)

        logger.debug(
            f"Logged audit event: {event_type.value} for tenant {tenant_id}, "
            f"action: {action}, resource: {resource}"
        )

        return event

    def _generate_event_id(self) -> str:
        """Generate unique event ID"""
        timestamp = datetime.utcnow().timestamp()
        return f"audit_{hashlib.md5(str(timestamp).encode()).hexdigest()[:16]}"

    def _index_event(self, event: AuditEvent, idx: int) -> None:
        """Index event for fast lookups"""
        # Tenant index
        if event.tenant_id not in self._event_index["tenant"]:
            self._event_index["tenant"][event.tenant_id] = set()
        self._event_index["tenant"][event.tenant_id].add(idx)

        # User index
        if event.user_id:
            if event.user_id not in self._event_index["user"]:
                self._event_index["user"][event.user_id] = set()
            self._event_index["user"][event.user_id].add(idx)

        # Type index
        type_key = event.event_type.value
        if type_key not in self._event_index["type"]:
            self._event_index["type"][type_key] = set()
        self._event_index["type"][type_key].add(idx)

    def _update_stats(self, event: AuditEvent) -> None:
        """Update event statistics"""
        self._stats["total_events"] += 1

        # By type
        type_key = event.event_type.value
        self._stats["events_by_type"][type_key] = \
            self._stats["events_by_type"].get(type_key, 0) + 1

        # By tenant
        self._stats["events_by_tenant"][event.tenant_id] = \
            self._stats["events_by_tenant"].get(event.tenant_id, 0) + 1

        # Cross-tenant
        if event.cross_tenant:
            self._stats["cross_tenant_events"] += 1

    def log_data_access(
        self,
        tenant_id: str,
        resource: str,
        action: str,
        user_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> AuditEvent:
        """Log a data access event"""
        return self.log_event(
            event_type=AuditEventType.DATA_ACCESS,
            tenant_id=tenant_id,
            action=action,
            resource=resource,
            user_id=user_id,
            details=details
        )

    def log_data_modification(
        self,
        tenant_id: str,
        resource: str,
        action: str,
        old_value: Optional[Any] = None,
        new_value: Optional[Any] = None,
        user_id: Optional[str] = None
    ) -> AuditEvent:
        """Log a data modification event"""
        details = {
            "old_value": old_value,
            "new_value": new_value
        }
        return self.log_event(
            event_type=AuditEventType.DATA_MODIFICATION,
            tenant_id=tenant_id,
            action=action,
            resource=resource,
            user_id=user_id,
            severity=AuditSeverity.WARNING,
            details=details
        )

    def log_cross_tenant_access(
        self,
        source_tenant: str,
        target_tenant: str,
        action: str,
        resource: str,
        user_id: Optional[str] = None,
        allowed: bool = False
    ) -> AuditEvent:
        """Log a cross-tenant access attempt"""
        return self.log_event(
            event_type=AuditEventType.CROSS_TENANT_ACCESS,
            tenant_id=source_tenant,
            action=action,
            resource=resource,
            user_id=user_id,
            severity=AuditSeverity.WARNING if allowed else AuditSeverity.ERROR,
            target_tenant_id=target_tenant,
            outcome="allowed" if allowed else "denied"
        )

    def log_policy_violation(
        self,
        tenant_id: str,
        policy: str,
        resource: str,
        action: str,
        details: Optional[Dict[str, Any]] = None
    ) -> AuditEvent:
        """Log a policy violation"""
        violation_details = {"policy": policy}
        if details:
            violation_details.update(details)

        return self.log_event(
            event_type=AuditEventType.POLICY_VIOLATION,
            tenant_id=tenant_id,
            action=action,
            resource=resource,
            severity=AuditSeverity.ERROR,
            details=violation_details,
            outcome="denied"
        )

    def search(self, query: AuditQuery) -> List[AuditEvent]:
        """
        Search audit events.

        Args:
            query: Search query parameters

        Returns:
            List of matching events
        """
        results = self._events

        # Filter by tenant
        if query.tenant_id:
            tenant_indices = self._event_index["tenant"].get(query.tenant_id, set())
            results = [self._events[i] for i in tenant_indices]

        # Filter by user
        if query.user_id:
            user_indices = self._event_index["user"].get(query.user_id, set())
            if query.tenant_id:
                # Intersect with tenant results
                results = [e for e in results if self._events.index(e) in user_indices]
            else:
                results = [self._events[i] for i in user_indices]

        # Filter by event type
        if query.event_types:
            type_indices = set()
            for et in query.event_types:
                type_indices.update(self._event_index["type"].get(et.value, set()))
            results = [e for e in results if self._events.index(e) in type_indices]

        # Filter by time range
        if query.start_time:
            results = [e for e in results if e.timestamp >= query.start_time]
        if query.end_time:
            results = [e for e in results if e.timestamp <= query.end_time]

        # Filter by severity
        if query.severity:
            results = [e for e in results if e.severity == query.severity]

        # Filter by resource
        if query.resource:
            results = [e for e in results if query.resource in e.resource]

        # Filter by outcome
        if query.outcome:
            results = [e for e in results if e.outcome == query.outcome]

        # Sort by timestamp (newest first)
        results = sorted(results, key=lambda e: e.timestamp, reverse=True)

        # Apply pagination
        return results[query.offset:query.offset + query.limit]

    def get_event(self, event_id: str) -> Optional[AuditEvent]:
        """Get an event by ID"""
        for event in self._events:
            if event.event_id == event_id:
                return event
        return None

    def get_tenant_events(
        self,
        tenant_id: str,
        limit: int = 100
    ) -> List[AuditEvent]:
        """Get all events for a tenant"""
        indices = self._event_index["tenant"].get(tenant_id, set())
        events = [self._events[i] for i in indices]
        return sorted(events, key=lambda e: e.timestamp, reverse=True)[:limit]

    def get_user_events(
        self,
        user_id: str,
        limit: int = 100
    ) -> List[AuditEvent]:
        """Get all events for a user"""
        indices = self._event_index["user"].get(user_id, set())
        events = [self._events[i] for i in indices]
        return sorted(events, key=lambda e: e.timestamp, reverse=True)[:limit]

    def get_cross_tenant_events(self, limit: int = 100) -> List[AuditEvent]:
        """Get all cross-tenant events"""
        cross_tenant = [e for e in self._events if e.cross_tenant]
        return sorted(cross_tenant, key=lambda e: e.timestamp, reverse=True)[:limit]

    def get_events_by_type(
        self,
        event_type: AuditEventType,
        limit: int = 100
    ) -> List[AuditEvent]:
        """Get events by type"""
        indices = self._event_index["type"].get(event_type.value, set())
        events = [self._events[i] for i in indices]
        return sorted(events, key=lambda e: e.timestamp, reverse=True)[:limit]

    def get_summary(
        self,
        tenant_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get audit summary statistics.

        Args:
            tenant_id: Optional tenant filter
            start_time: Optional start time
            end_time: Optional end time

        Returns:
            Summary statistics
        """
        events = self._events

        if tenant_id:
            events = [e for e in events if e.tenant_id == tenant_id]
        if start_time:
            events = [e for e in events if e.timestamp >= start_time]
        if end_time:
            events = [e for e in events if e.timestamp <= end_time]

        summary = {
            "total_events": len(events),
            "events_by_type": {},
            "events_by_severity": {},
            "events_by_outcome": {},
            "cross_tenant_count": 0,
            "unique_users": set(),
            "unique_resources": set()
        }

        for event in events:
            # By type
            type_key = event.event_type.value
            summary["events_by_type"][type_key] = \
                summary["events_by_type"].get(type_key, 0) + 1

            # By severity
            sev_key = event.severity.value
            summary["events_by_severity"][sev_key] = \
                summary["events_by_severity"].get(sev_key, 0) + 1

            # By outcome
            summary["events_by_outcome"][event.outcome] = \
                summary["events_by_outcome"].get(event.outcome, 0) + 1

            # Cross-tenant
            if event.cross_tenant:
                summary["cross_tenant_count"] += 1

            # Unique users/resources
            if event.user_id:
                summary["unique_users"].add(event.user_id)
            summary["unique_resources"].add(event.resource)

        # Convert sets to counts
        summary["unique_users"] = len(summary["unique_users"])
        summary["unique_resources"] = len(summary["unique_resources"])

        return summary

    def get_timeline(
        self,
        tenant_id: str,
        interval_minutes: int = 60,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Get event timeline for a tenant.

        Args:
            tenant_id: Tenant ID
            interval_minutes: Time interval in minutes
            start_time: Optional start time
            end_time: Optional end time

        Returns:
            List of time buckets with event counts
        """
        if not start_time:
            start_time = datetime.utcnow() - timedelta(hours=24)
        if not end_time:
            end_time = datetime.utcnow()

        events = [e for e in self._events if e.tenant_id == tenant_id]

        timeline = []
        current = start_time

        while current < end_time:
            bucket_end = current + timedelta(minutes=interval_minutes)

            bucket_events = [
                e for e in events
                if current <= e.timestamp < bucket_end
            ]

            timeline.append({
                "start_time": current.isoformat(),
                "end_time": bucket_end.isoformat(),
                "count": len(bucket_events),
                "by_type": self._count_by_field(bucket_events, "event_type"),
                "by_severity": self._count_by_field(bucket_events, "severity")
            })

            current = bucket_end

        return timeline

    def _count_by_field(self, events: List[AuditEvent], field: str) -> Dict[str, int]:
        """Count events by a field"""
        counts: Dict[str, int] = {}
        for event in events:
            value = getattr(event, field)
            key = value.value if hasattr(value, 'value') else str(value)
            counts[key] = counts.get(key, 0) + 1
        return counts

    def cleanup_old_events(self) -> int:
        """Remove events older than retention period"""
        cutoff = datetime.utcnow() - timedelta(days=self.retention_days)

        initial_count = len(self._events)
        self._events = [e for e in self._events if e.timestamp >= cutoff]
        removed = initial_count - len(self._events)

        # Rebuild indexes
        self._rebuild_indexes()

        logger.info(f"Cleaned up {removed} old audit events")
        return removed

    def _rebuild_indexes(self) -> None:
        """Rebuild all indexes"""
        self._event_index = {"tenant": {}, "user": {}, "type": {}}

        for idx, event in enumerate(self._events):
            self._index_event(event, idx)

    def export_events(
        self,
        tenant_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        format: str = "json"
    ) -> str:
        """
        Export audit events for a tenant.

        Args:
            tenant_id: Tenant ID
            start_time: Optional start time
            end_time: Optional end time
            format: Export format (json, csv)

        Returns:
            Exported data as string
        """
        events = [e for e in self._events if e.tenant_id == tenant_id]

        if start_time:
            events = [e for e in events if e.timestamp >= start_time]
        if end_time:
            events = [e for e in events if e.timestamp <= end_time]

        if format == "json":
            export_data = [
                {
                    "event_id": e.event_id,
                    "event_type": e.event_type.value,
                    "action": e.action,
                    "resource": e.resource,
                    "timestamp": e.timestamp.isoformat(),
                    "severity": e.severity.value,
                    "user_id": e.user_id,
                    "ip_address": e.ip_address,
                    "outcome": e.outcome,
                    "details": e.details
                }
                for e in events
            ]
            return json.dumps(export_data, indent=2)

        elif format == "csv":
            lines = ["event_id,event_type,action,resource,timestamp,severity,user_id,outcome"]
            for e in events:
                lines.append(
                    f"{e.event_id},{e.event_type.value},{e.action},{e.resource},"
                    f"{e.timestamp.isoformat()},{e.severity.value},{e.user_id or ''},{e.outcome}"
                )
            return "\n".join(lines)

        raise ValueError(f"Unsupported format: {format}")

    def get_compliance_report(
        self,
        tenant_id: str,
        framework: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Generate a compliance report for a tenant.

        Args:
            tenant_id: Tenant ID
            framework: Compliance framework (e.g., "SOC2", "GDPR", "HIPAA")
            start_time: Optional start time
            end_time: Optional end time

        Returns:
            Compliance report
        """
        events = [e for e in self._events if e.tenant_id == tenant_id]

        if start_time:
            events = [e for e in events if e.timestamp >= start_time]
        if end_time:
            events = [e for e in events if e.timestamp <= end_time]

        report = {
            "tenant_id": tenant_id,
            "framework": framework,
            "generated_at": datetime.utcnow().isoformat(),
            "period": {
                "start": start_time.isoformat() if start_time else "all",
                "end": end_time.isoformat() if end_time else "now"
            },
            "summary": {
                "total_events": len(events),
                "data_access_events": len([e for e in events if e.event_type == AuditEventType.DATA_ACCESS]),
                "data_modification_events": len([e for e in events if e.event_type == AuditEventType.DATA_MODIFICATION]),
                "policy_violations": len([e for e in events if e.event_type == AuditEventType.POLICY_VIOLATION]),
                "cross_tenant_events": len([e for e in events if e.cross_tenant])
            },
            "findings": []
        }

        # Check for concerning patterns
        violations = [e for e in events if e.event_type == AuditEventType.POLICY_VIOLATION]
        if violations:
            report["findings"].append({
                "severity": "high",
                "finding": f"{len(violations)} policy violations detected",
                "details": [v.event_id for v in violations[:10]]
            })

        cross_tenant = [e for e in events if e.cross_tenant and e.outcome == "allowed"]
        if cross_tenant:
            report["findings"].append({
                "severity": "medium",
                "finding": f"{len(cross_tenant)} cross-tenant accesses allowed",
                "details": [e.event_id for e in cross_tenant[:10]]
            })

        return report

    def get_metrics(self) -> Dict[str, Any]:
        """Get audit trail metrics"""
        return {
            **self._stats,
            "storage_size": len(self._events),
            "oldest_event": min(e.timestamp for e in self._events).isoformat() if self._events else None,
            "newest_event": max(e.timestamp for e in self._events).isoformat() if self._events else None
        }
