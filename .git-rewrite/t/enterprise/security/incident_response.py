"""
Enterprise Security - Incident Response
Incident response for enterprise security
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum
import uuid


class IncidentStatus(str, Enum):
    NEW = "new"
    INVESTIGATING = "investigating"
    CONTAINED = "contained"
    RESOLVED = "resolved"
    CLOSED = "closed"


class IncidentSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentType(str, Enum):
    SECURITY_BREACH = "security_breach"
    DATA_LEAK = "data_leak"
    MALWARE = "malware"
    PHISHING = "phishing"
    DDOS = "ddos"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    OTHER = "other"


class SecurityIncident(BaseModel):
    """Security incident"""
    incident_id: str = Field(default_factory=lambda: f"inc_{uuid.uuid4().hex[:8]}")
    title: str
    description: str
    incident_type: IncidentType = IncidentType.OTHER
    severity: IncidentSeverity = IncidentSeverity.MEDIUM
    status: IncidentStatus = IncidentStatus.NEW
    client_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    assigned_to: Optional[str] = None
    resolved_at: Optional[datetime] = None
    timeline: List[Dict[str, Any]] = Field(default_factory=list)

    model_config = ConfigDict()


class IncidentResponse:
    """
    Incident response management for enterprise clients.
    """

    def __init__(self):
        self.incidents: Dict[str, SecurityIncident] = {}

    def create_incident(
        self,
        title: str,
        description: str,
        client_id: str,
        incident_type: IncidentType = IncidentType.OTHER,
        severity: IncidentSeverity = IncidentSeverity.MEDIUM
    ) -> SecurityIncident:
        """Create a new incident"""
        incident = SecurityIncident(
            title=title,
            description=description,
            client_id=client_id,
            incident_type=incident_type,
            severity=severity
        )
        incident.timeline.append({
            "action": "created",
            "timestamp": datetime.utcnow().isoformat()
        })
        self.incidents[incident.incident_id] = incident
        return incident

    def update_status(
        self,
        incident_id: str,
        new_status: IncidentStatus,
        notes: Optional[str] = None
    ) -> Optional[SecurityIncident]:
        """Update incident status"""
        if incident_id not in self.incidents:
            return None

        incident = self.incidents[incident_id]
        old_status = incident.status
        incident.status = new_status
        incident.updated_at = datetime.utcnow()

        incident.timeline.append({
            "action": f"status_changed: {old_status} -> {new_status}",
            "timestamp": datetime.utcnow().isoformat(),
            "notes": notes
        })

        if new_status == IncidentStatus.RESOLVED:
            incident.resolved_at = datetime.utcnow()

        return incident

    def assign(self, incident_id: str, assignee: str) -> bool:
        """Assign incident to someone"""
        if incident_id not in self.incidents:
            return False

        incident = self.incidents[incident_id]
        incident.assigned_to = assignee
        incident.timeline.append({
            "action": f"assigned_to: {assignee}",
            "timestamp": datetime.utcnow().isoformat()
        })
        return True

    def add_notes(self, incident_id: str, notes: str, author: str) -> bool:
        """Add notes to incident"""
        if incident_id not in self.incidents:
            return False

        self.incidents[incident_id].timeline.append({
            "action": "notes_added",
            "notes": notes,
            "author": author,
            "timestamp": datetime.utcnow().isoformat()
        })
        return True

    def get_client_incidents(self, client_id: str) -> List[SecurityIncident]:
        """Get all incidents for a client"""
        return [i for i in self.incidents.values() if i.client_id == client_id]

    def get_open_incidents(self) -> List[SecurityIncident]:
        """Get all open incidents"""
        return [i for i in self.incidents.values() if i.status not in [IncidentStatus.RESOLVED, IncidentStatus.CLOSED]]

    def get_incidents_by_severity(self, severity: IncidentSeverity) -> List[SecurityIncident]:
        """Get incidents by severity"""
        return [i for i in self.incidents.values() if i.severity == severity]
