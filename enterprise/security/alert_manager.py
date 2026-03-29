"""
Enterprise Security - Alert Manager
Security alert management for enterprise
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum
import uuid


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class SecurityAlert(BaseModel):
    """Security alert"""
    alert_id: str = Field(default_factory=lambda: f"alert_{uuid.uuid4().hex[:8]}")
    title: str
    description: str
    severity: AlertSeverity = AlertSeverity.WARNING
    status: AlertStatus = AlertStatus.OPEN
    source: str = "system"
    client_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict()


class AlertManager:
    """
    Manage security alerts for enterprise clients.
    """

    def __init__(self):
        self.alerts: Dict[str, SecurityAlert] = {}
        self.handlers: Dict[AlertSeverity, List[Any]] = {s: [] for s in AlertSeverity}

    def create_alert(
        self,
        title: str,
        description: str,
        severity: AlertSeverity = AlertSeverity.WARNING,
        source: str = "system",
        client_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> SecurityAlert:
        """Create a new alert"""
        alert = SecurityAlert(
            title=title,
            description=description,
            severity=severity,
            source=source,
            client_id=client_id,
            metadata=metadata or {}
        )
        self.alerts[alert.alert_id] = alert

        # Trigger handlers
        for handler in self.handlers[severity]:
            handler(alert)

        return alert

    def acknowledge(self, alert_id: str, acknowledged_by: str) -> bool:
        """Acknowledge an alert"""
        if alert_id not in self.alerts:
            return False

        alert = self.alerts[alert_id]
        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_at = datetime.utcnow()
        alert.acknowledged_by = acknowledged_by
        return True

    def resolve(self, alert_id: str) -> bool:
        """Resolve an alert"""
        if alert_id not in self.alerts:
            return False

        alert = self.alerts[alert_id]
        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = datetime.utcnow()
        return True

    def dismiss(self, alert_id: str) -> bool:
        """Dismiss an alert"""
        if alert_id not in self.alerts:
            return False

        self.alerts[alert_id].status = AlertStatus.DISMISSED
        return True

    def register_handler(self, severity: AlertSeverity, handler: Any) -> None:
        """Register a handler for alerts of a specific severity"""
        self.handlers[severity].append(handler)

    def get_open_alerts(self, client_id: Optional[str] = None) -> List[SecurityAlert]:
        """Get all open alerts"""
        alerts = [a for a in self.alerts.values() if a.status == AlertStatus.OPEN]
        if client_id:
            alerts = [a for a in alerts if a.client_id == client_id]
        return alerts

    def get_alerts_by_severity(self, severity: AlertSeverity) -> List[SecurityAlert]:
        """Get alerts by severity"""
        return [a for a in self.alerts.values() if a.severity == severity]

    def get_summary(self) -> Dict[str, int]:
        """Get alert summary"""
        summary = {s.value: 0 for s in AlertSeverity}
        for alert in self.alerts.values():
            if alert.status == AlertStatus.OPEN:
                summary[alert.severity.value] += 1
        return summary
