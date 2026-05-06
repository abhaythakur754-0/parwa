"""
Incident Manager Module - Week 53, Builder 3
Incident management system for monitoring
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
import logging
import uuid

logger = logging.getLogger(__name__)


class IncidentSeverity(Enum):
    """Incident severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentStatus(Enum):
    """Incident status"""
    OPEN = "open"
    INVESTIGATING = "investigating"
    IDENTIFIED = "identified"
    MONITORING = "monitoring"
    RESOLVED = "resolved"


@dataclass
class IncidentEvent:
    """Event in incident timeline"""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    event_type: str = ""
    message: str = ""
    user: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Incident:
    """Incident data class"""
    incident_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str = ""
    description: str = ""
    severity: IncidentSeverity = IncidentSeverity.MEDIUM
    status: IncidentStatus = IncidentStatus.OPEN
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    assignee: str = ""
    team: str = ""
    timeline: List[IncidentEvent] = field(default_factory=list)
    alerts: List[str] = field(default_factory=list)
    tags: Dict[str, str] = field(default_factory=dict)
    impact: str = ""
    root_cause: str = ""

    def add_event(
        self,
        event_type: str,
        message: str,
        user: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> IncidentEvent:
        """Add event to timeline"""
        event = IncidentEvent(
            event_type=event_type,
            message=message,
            user=user,
            metadata=metadata or {},
        )
        self.timeline.append(event)
        self.updated_at = datetime.utcnow()
        return event

    def to_dict(self) -> Dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "title": self.title,
            "severity": self.severity.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "assignee": self.assignee,
            "impact": self.impact,
        }


class IncidentManager:
    """
    Main incident management system.
    """

    def __init__(self, max_incidents: int = 10000):
        self.max_incidents = max_incidents
        self.incidents: Dict[str, Incident] = {}
        self._callbacks: List[Callable] = []
        self._lock = False

    def create_incident(
        self,
        title: str,
        description: str = "",
        severity: IncidentSeverity = IncidentSeverity.MEDIUM,
        assignee: str = "",
        team: str = "",
        impact: str = "",
        tags: Optional[Dict[str, str]] = None,
    ) -> Incident:
        """Create a new incident"""
        incident = Incident(
            title=title,
            description=description,
            severity=severity,
            assignee=assignee,
            team=team,
            impact=impact,
            tags=tags or {},
        )

        incident.add_event(
            event_type="created",
            message=f"Incident created: {title}",
        )

        self.incidents[incident.incident_id] = incident
        self._notify_callbacks(incident)

        logger.info(f"Created incident: {incident.incident_id}")
        return incident

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        """Get incident by ID"""
        return self.incidents.get(incident_id)

    def update_status(
        self,
        incident_id: str,
        status: IncidentStatus,
        user: str = "",
    ) -> bool:
        """Update incident status"""
        incident = self.incidents.get(incident_id)
        if not incident:
            return False

        old_status = incident.status
        incident.status = status
        incident.updated_at = datetime.utcnow()

        if status == IncidentStatus.RESOLVED:
            incident.resolved_at = datetime.utcnow()

        incident.add_event(
            event_type="status_change",
            message=f"Status changed from {old_status.value} to {status.value}",
            user=user,
        )

        self._notify_callbacks(incident)
        return True

    def acknowledge(
        self,
        incident_id: str,
        user: str = "",
    ) -> bool:
        """Acknowledge an incident"""
        incident = self.incidents.get(incident_id)
        if not incident:
            return False

        incident.acknowledged_at = datetime.utcnow()
        incident.add_event(
            event_type="acknowledged",
            message=f"Incident acknowledged by {user}",
            user=user,
        )

        self._notify_callbacks(incident)
        return True

    def assign(
        self,
        incident_id: str,
        assignee: str,
        user: str = "",
    ) -> bool:
        """Assign incident to someone"""
        incident = self.incidents.get(incident_id)
        if not incident:
            return False

        incident.assignee = assignee
        incident.add_event(
            event_type="assigned",
            message=f"Assigned to {assignee}",
            user=user,
        )

        self._notify_callbacks(incident)
        return True

    def add_note(
        self,
        incident_id: str,
        note: str,
        user: str = "",
    ) -> bool:
        """Add a note to incident"""
        incident = self.incidents.get(incident_id)
        if not incident:
            return False

        incident.add_event(
            event_type="note",
            message=note,
            user=user,
        )

        return True

    def link_alert(
        self,
        incident_id: str,
        alert_id: str,
    ) -> bool:
        """Link an alert to incident"""
        incident = self.incidents.get(incident_id)
        if not incident:
            return False

        if alert_id not in incident.alerts:
            incident.alerts.append(alert_id)

        return True

    def get_open_incidents(self) -> List[Incident]:
        """Get all open incidents"""
        return [
            i for i in self.incidents.values()
            if i.status != IncidentStatus.RESOLVED
        ]

    def get_by_severity(self, severity: IncidentSeverity) -> List[Incident]:
        """Get incidents by severity"""
        return [
            i for i in self.incidents.values()
            if i.severity == severity
        ]

    def get_by_assignee(self, assignee: str) -> List[Incident]:
        """Get incidents by assignee"""
        return [
            i for i in self.incidents.values()
            if i.assignee == assignee
        ]

    def resolve(
        self,
        incident_id: str,
        root_cause: str = "",
        user: str = "",
    ) -> bool:
        """Resolve an incident"""
        incident = self.incidents.get(incident_id)
        if not incident:
            return False

        incident.root_cause = root_cause
        incident.resolved_at = datetime.utcnow()
        incident.status = IncidentStatus.RESOLVED

        incident.add_event(
            event_type="resolved",
            message=f"Incident resolved. Root cause: {root_cause}",
            user=user,
        )

        self._notify_callbacks(incident)
        return True

    def add_callback(self, callback: Callable) -> None:
        """Add a callback for incident updates"""
        self._callbacks.append(callback)

    def _notify_callbacks(self, incident: Incident) -> None:
        """Notify all callbacks"""
        for callback in self._callbacks:
            try:
                callback(incident)
            except Exception as e:
                logger.error(f"Incident callback error: {e}")

    def get_statistics(self) -> Dict[str, Any]:
        """Get incident statistics"""
        open_count = len(self.get_open_incidents())
        resolved_count = sum(
            1 for i in self.incidents.values()
            if i.status == IncidentStatus.RESOLVED
        )

        # Calculate MTTR (Mean Time To Resolve)
        resolved_incidents = [
            i for i in self.incidents.values()
            if i.resolved_at
        ]
        if resolved_incidents:
            mttr = sum(
                (i.resolved_at - i.created_at).total_seconds()
                for i in resolved_incidents
            ) / len(resolved_incidents)
        else:
            mttr = 0

        return {
            "total_incidents": len(self.incidents),
            "open": open_count,
            "resolved": resolved_count,
            "by_severity": {
                s.value: len(self.get_by_severity(s))
                for s in IncidentSeverity
            },
            "mttr_seconds": mttr,
        }
