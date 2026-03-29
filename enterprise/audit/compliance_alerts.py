# Compliance Alerts - Week 49 Builder 5
# Compliance alert system

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from enum import Enum
import uuid


class AlertPriority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(Enum):
    PENDING = "pending"
    SENT = "sent"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


@dataclass
class Alert:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    name: str = ""
    message: str = ""
    priority: AlertPriority = AlertPriority.MEDIUM
    status: AlertStatus = AlertStatus.PENDING
    source: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    recipients: List[str] = field(default_factory=list)
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    sent_at: Optional[datetime] = None


class ComplianceAlerts:
    """Compliance alert system"""

    def __init__(self):
        self._alerts: Dict[str, Alert] = {}
        self._handlers: List[Callable] = []
        self._metrics = {
            "total_alerts": 0,
            "sent_alerts": 0,
            "acknowledged_alerts": 0,
            "by_priority": {}
        }

    def create_alert(
        self,
        tenant_id: str,
        name: str,
        message: str,
        priority: AlertPriority = AlertPriority.MEDIUM,
        source: str = "",
        recipients: Optional[List[str]] = None
    ) -> Alert:
        """Create a compliance alert"""
        alert = Alert(
            tenant_id=tenant_id,
            name=name,
            message=message,
            priority=priority,
            source=source,
            recipients=recipients or []
        )

        self._alerts[alert.id] = alert
        self._metrics["total_alerts"] += 1

        pri_key = priority.value
        self._metrics["by_priority"][pri_key] = self._metrics["by_priority"].get(pri_key, 0) + 1

        return alert

    def register_handler(self, handler: Callable) -> None:
        """Register an alert handler"""
        self._handlers.append(handler)

    async def send_alert(self, alert_id: str) -> bool:
        """Send an alert"""
        alert = self._alerts.get(alert_id)
        if not alert:
            return False

        for handler in self._handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(alert)
                else:
                    handler(alert)
            except Exception:
                pass

        alert.status = AlertStatus.SENT
        alert.sent_at = datetime.utcnow()
        self._metrics["sent_alerts"] += 1
        return True

    def acknowledge_alert(
        self,
        alert_id: str,
        acknowledged_by: str
    ) -> bool:
        """Acknowledge an alert"""
        alert = self._alerts.get(alert_id)
        if not alert:
            return False

        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_by = acknowledged_by
        alert.acknowledged_at = datetime.utcnow()
        self._metrics["acknowledged_alerts"] += 1
        return True

    def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an alert"""
        alert = self._alerts.get(alert_id)
        if not alert:
            return False

        alert.status = AlertStatus.RESOLVED
        return True

    def get_alert(self, alert_id: str) -> Optional[Alert]:
        return self._alerts.get(alert_id)

    def get_alerts_by_tenant(
        self,
        tenant_id: str,
        status: Optional[AlertStatus] = None
    ) -> List[Alert]:
        alerts = [a for a in self._alerts.values() if a.tenant_id == tenant_id]
        if status:
            alerts = [a for a in alerts if a.status == status]
        return alerts

    def get_critical_alerts(self, tenant_id: str) -> List[Alert]:
        """Get all unresolved critical alerts"""
        return [
            a for a in self._alerts.values()
            if a.tenant_id == tenant_id
            and a.priority == AlertPriority.CRITICAL
            and a.status in [AlertStatus.PENDING, AlertStatus.SENT]
        ]

    def get_metrics(self) -> Dict[str, Any]:
        return self._metrics.copy()


import asyncio
