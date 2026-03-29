"""
Comprehensive Audit Logging for Week 54 Advanced Security Hardening.

This module provides tamper-proof audit logging capabilities with support for
querying, exporting, and integrity verification of audit events.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any, Callable
from datetime import datetime, timedelta
import hashlib
import json
import hmac
import os
from functools import wraps


class AuditLevel(Enum):
    """Audit log severity levels."""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class AuditAction(Enum):
    """Common audit actions."""
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    CREATE = "CREATE"
    READ = "READ"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    EXPORT = "EXPORT"
    IMPORT = "IMPORT"
    ACCESS = "ACCESS"
    MODIFY = "MODIFY"
    ADMIN = "ADMIN"
    SECURITY = "SECURITY"


@dataclass
class AuditEvent:
    """
    Represents a single audit event.
    
    Attributes:
        event_id: Unique identifier for the event
        timestamp: When the event occurred
        user: User who performed the action
        action: Action that was performed
        resource: Resource that was affected
        result: Result of the action (SUCCESS, FAILURE, etc.)
        level: Severity level of the event
        details: Additional details about the event
        ip_address: IP address of the user
        user_agent: User agent string
        session_id: Session identifier
        correlation_id: Correlation ID for tracing
        previous_hash: Hash of the previous event (for tamper-proofing)
        signature: HMAC signature of the event
    """
    event_id: str
    timestamp: datetime
    user: str
    action: str
    resource: str
    result: str
    level: AuditLevel = AuditLevel.INFO
    details: Dict[str, Any] = field(default_factory=dict)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    session_id: Optional[str] = None
    correlation_id: Optional[str] = None
    previous_hash: Optional[str] = None
    signature: Optional[str] = None
    
    def compute_hash(self) -> str:
        """Compute hash of the event for tamper-proofing."""
        event_data = {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "user": self.user,
            "action": self.action,
            "resource": self.resource,
            "result": self.result,
            "level": self.level.value,
            "details": self.details,
            "previous_hash": self.previous_hash
        }
        event_json = json.dumps(event_data, sort_keys=True)
        return hashlib.sha256(event_json.encode()).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "user": self.user,
            "action": self.action,
            "resource": self.resource,
            "result": self.result,
            "level": self.level.value,
            "details": self.details,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "session_id": self.session_id,
            "correlation_id": self.correlation_id,
            "previous_hash": self.previous_hash,
            "signature": self.signature
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuditEvent":
        """Create event from dictionary."""
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        data["level"] = AuditLevel(data["level"])
        return cls(**data)


class AuditLogger:
    """
    Comprehensive audit logging system with tamper-proof capabilities.
    
    Provides methods for logging events, querying events, exporting logs,
    and verifying log integrity.
    
    Attributes:
        events: List of all logged events
        signing_key: Key used for HMAC signatures
    """
    
    def __init__(self, signing_key: Optional[str] = None):
        """
        Initialize the audit logger.
        
        Args:
            signing_key: Optional key for signing events. If not provided,
                        a random key will be generated.
        """
        self.events: List[AuditEvent] = []
        self.signing_key = signing_key or os.urandom(32).hex()
        self._last_hash: Optional[str] = None
        self._event_counter = 0
    
    def _generate_event_id(self) -> str:
        """Generate a unique event ID."""
        self._event_counter += 1
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        return f"AUDIT-{timestamp}-{self._event_counter:06d}"
    
    def _sign_event(self, event: AuditEvent) -> str:
        """Sign an event with HMAC."""
        event_hash = event.compute_hash()
        signature = hmac.new(
            self.signing_key.encode(),
            event_hash.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def log(
        self,
        user: str,
        action: str,
        resource: str,
        result: str,
        level: AuditLevel = AuditLevel.INFO,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> AuditEvent:
        """
        Log an audit event.
        
        Args:
            user: User who performed the action
            action: Action that was performed
            resource: Resource that was affected
            result: Result of the action
            level: Severity level
            details: Additional details
            ip_address: IP address of the user
            user_agent: User agent string
            session_id: Session identifier
            correlation_id: Correlation ID for tracing
            
        Returns:
            The created AuditEvent
        """
        event = AuditEvent(
            event_id=self._generate_event_id(),
            timestamp=datetime.utcnow(),
            user=user,
            action=action,
            resource=resource,
            result=result,
            level=level,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
            correlation_id=correlation_id,
            previous_hash=self._last_hash
        )
        
        # Sign the event
        event.signature = self._sign_event(event)
        self._last_hash = event.compute_hash()
        
        self.events.append(event)
        return event
    
    def log_event(self, event: AuditEvent) -> AuditEvent:
        """
        Log a pre-constructed audit event.
        
        Args:
            event: The event to log
            
        Returns:
            The logged event with signature
        """
        event.previous_hash = self._last_hash
        event.signature = self._sign_event(event)
        self._last_hash = event.compute_hash()
        self.events.append(event)
        return event
    
    def query_events(
        self,
        user: Optional[str] = None,
        action: Optional[str] = None,
        resource: Optional[str] = None,
        level: Optional[AuditLevel] = None,
        result: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[AuditEvent]:
        """
        Query audit events with filters.
        
        Args:
            user: Filter by user
            action: Filter by action
            resource: Filter by resource
            level: Filter by severity level
            result: Filter by result
            start_time: Filter events after this time
            end_time: Filter events before this time
            limit: Maximum number of events to return
            
        Returns:
            List of matching events
        """
        filtered = self.events.copy()
        
        if user:
            filtered = [e for e in filtered if e.user == user]
        if action:
            filtered = [e for e in filtered if e.action == action]
        if resource:
            filtered = [e for e in filtered if e.resource == resource]
        if level:
            filtered = [e for e in filtered if e.level == level]
        if result:
            filtered = [e for e in filtered if e.result == result]
        if start_time:
            filtered = [e for e in filtered if e.timestamp >= start_time]
        if end_time:
            filtered = [e for e in filtered if e.timestamp <= end_time]
        
        # Sort by timestamp descending
        filtered.sort(key=lambda e: e.timestamp, reverse=True)
        
        if limit:
            filtered = filtered[:limit]
        
        return filtered
    
    def get_event_by_id(self, event_id: str) -> Optional[AuditEvent]:
        """Get an event by its ID."""
        for event in self.events:
            if event.event_id == event_id:
                return event
        return None
    
    def get_events_by_user(self, user: str) -> List[AuditEvent]:
        """Get all events for a specific user."""
        return [e for e in self.events if e.user == user]
    
    def get_events_by_resource(self, resource: str) -> List[AuditEvent]:
        """Get all events for a specific resource."""
        return [e for e in self.events if e.resource == resource]
    
    def get_events_by_level(self, level: AuditLevel) -> List[AuditEvent]:
        """Get all events with a specific severity level."""
        return [e for e in self.events if e.level == level]
    
    def get_failed_events(self) -> List[AuditEvent]:
        """Get all failed events."""
        return [e for e in self.events if e.result == "FAILURE"]
    
    def get_critical_events(self) -> List[AuditEvent]:
        """Get all critical level events."""
        return self.get_events_by_level(AuditLevel.CRITICAL)
    
    def export_logs(
        self,
        format: str = "json",
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> str:
        """
        Export audit logs to a specific format.
        
        Args:
            format: Export format (json, csv)
            start_time: Export events after this time
            end_time: Export events before this time
            
        Returns:
            Exported logs as a string
        """
        events = self.query_events(start_time=start_time, end_time=end_time)
        
        if format == "json":
            return json.dumps(
                [e.to_dict() for e in events],
                indent=2
            )
        elif format == "csv":
            lines = ["event_id,timestamp,user,action,resource,result,level"]
            for event in events:
                lines.append(
                    f"{event.event_id},{event.timestamp.isoformat()},"
                    f"{event.user},{event.action},{event.resource},"
                    f"{event.result},{event.level.value}"
                )
            return "\n".join(lines)
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def verify_integrity(self) -> Dict[str, Any]:
        """
        Verify the integrity of the audit log chain.
        
        Returns:
            Dictionary with verification results
        """
        if not self.events:
            return {
                "valid": True,
                "events_checked": 0,
                "errors": []
            }
        
        errors = []
        previous_hash = None
        
        for i, event in enumerate(self.events):
            # Check hash chain
            if event.previous_hash != previous_hash:
                errors.append({
                    "event_id": event.event_id,
                    "error": "Hash chain broken",
                    "expected": previous_hash,
                    "actual": event.previous_hash
                })
            
            # Verify signature
            expected_signature = hmac.new(
                self.signing_key.encode(),
                event.compute_hash().encode(),
                hashlib.sha256
            ).hexdigest()
            
            if event.signature != expected_signature:
                errors.append({
                    "event_id": event.event_id,
                    "error": "Invalid signature"
                })
            
            previous_hash = event.compute_hash()
        
        return {
            "valid": len(errors) == 0,
            "events_checked": len(self.events),
            "errors": errors
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about the audit log."""
        if not self.events:
            return {
                "total_events": 0,
                "by_level": {},
                "by_action": {},
                "by_user": {},
                "by_result": {}
            }
        
        by_level: Dict[str, int] = {}
        by_action: Dict[str, int] = {}
        by_user: Dict[str, int] = {}
        by_result: Dict[str, int] = {}
        
        for event in self.events:
            by_level[event.level.value] = by_level.get(event.level.value, 0) + 1
            by_action[event.action] = by_action.get(event.action, 0) + 1
            by_user[event.user] = by_user.get(event.user, 0) + 1
            by_result[event.result] = by_result.get(event.result, 0) + 1
        
        return {
            "total_events": len(self.events),
            "by_level": by_level,
            "by_action": by_action,
            "by_user": by_user,
            "by_result": by_result,
            "first_event": self.events[0].timestamp.isoformat() if self.events else None,
            "last_event": self.events[-1].timestamp.isoformat() if self.events else None
        }
    
    def clear_events(self) -> int:
        """
        Clear all events (use with caution).
        
        Returns:
            Number of events cleared
        """
        count = len(self.events)
        self.events.clear()
        self._last_hash = None
        self._event_counter = 0
        return count
    
    def rotate_logs(self, max_events: int = 10000) -> int:
        """
        Rotate logs by removing oldest events if count exceeds max_events.
        
        Args:
            max_events: Maximum number of events to keep
            
        Returns:
            Number of events removed
        """
        if len(self.events) <= max_events:
            return 0
        
        events_to_remove = len(self.events) - max_events
        self.events = self.events[events_to_remove:]
        
        # Reset hash chain for first event
        if self.events:
            self.events[0].previous_hash = None
            self._last_hash = self.events[-1].compute_hash()
        
        return events_to_remove


def audit_log(
    action: str,
    resource: str,
    logger: AuditLogger,
    level: AuditLevel = AuditLevel.INFO
) -> Callable:
    """
    Decorator for automatic audit logging of functions.
    
    Args:
        action: Action name for the log
        resource: Resource name for the log
        logger: AuditLogger instance
        level: Severity level
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = kwargs.get("user", "system")
            result = "SUCCESS"
            details = {}
            
            try:
                output = func(*args, **kwargs)
                details["function"] = func.__name__
                return output
            except Exception as e:
                result = "FAILURE"
                details["error"] = str(e)
                raise
            finally:
                logger.log(
                    user=user,
                    action=action,
                    resource=resource,
                    result=result,
                    level=level,
                    details=details
                )
        
        return wrapper
    return decorator
