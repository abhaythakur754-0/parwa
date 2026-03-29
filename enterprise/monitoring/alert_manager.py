"""
Alert Manager Module - Week 53, Builder 2
Alert management system for monitoring
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
import logging
import threading
import uuid

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertStatus(Enum):
    """Alert status"""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SILENCED = "silenced"


@dataclass
class Alert:
    """Alert data class"""
    name: str
    severity: AlertSeverity
    message: str
    source: str = ""
    status: AlertStatus = AlertStatus.ACTIVE
    alert_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    labels: Dict[str, str] = field(default_factory=dict)
    annotations: Dict[str, str] = field(default_factory=dict)
    value: float = 0.0
    threshold: float = 0.0

    def acknowledge(self, user: str = "") -> None:
        """Acknowledge the alert"""
        self.status = AlertStatus.ACKNOWLEDGED
        self.acknowledged_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def resolve(self) -> None:
        """Resolve the alert"""
        self.status = AlertStatus.RESOLVED
        self.resolved_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "name": self.name,
            "severity": self.severity.value,
            "message": self.message,
            "source": self.source,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "value": self.value,
            "threshold": self.threshold,
        }


class AlertManager:
    """
    Main alert management system.
    """

    def __init__(self, max_alerts: int = 10000):
        self.max_alerts = max_alerts
        self.alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self._silences: Dict[str, Dict[str, Any]] = {}
        self._handlers: List[Callable] = []
        self._lock = threading.Lock()

    def create_alert(
        self,
        name: str,
        severity: AlertSeverity,
        message: str,
        source: str = "",
        value: float = 0.0,
        threshold: float = 0.0,
        labels: Optional[Dict[str, str]] = None,
    ) -> Alert:
        """Create a new alert"""
        alert = Alert(
            name=name,
            severity=severity,
            message=message,
            source=source,
            value=value,
            threshold=threshold,
            labels=labels or {},
        )

        with self._lock:
            # Check if silenced
            if self._is_silenced(alert):
                alert.status = AlertStatus.SILENCED

            self.alerts[alert.alert_id] = alert
            self.alert_history.append(alert)

            # Enforce max alerts
            if len(self.alert_history) > self.max_alerts:
                self.alert_history = self.alert_history[-self.max_alerts:]

        # Notify handlers
        self._notify_handlers(alert)

        logger.info(f"Created alert: {name} ({severity.value})")
        return alert

    def get_alert(self, alert_id: str) -> Optional[Alert]:
        """Get alert by ID"""
        return self.alerts.get(alert_id)

    def get_active_alerts(self) -> List[Alert]:
        """Get all active alerts"""
        return [
            a for a in self.alerts.values()
            if a.status == AlertStatus.ACTIVE
        ]

    def get_alerts_by_severity(self, severity: AlertSeverity) -> List[Alert]:
        """Get alerts by severity"""
        return [
            a for a in self.alerts.values()
            if a.severity == severity
        ]

    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert"""
        alert = self.alerts.get(alert_id)
        if alert:
            alert.acknowledge()
            self._notify_handlers(alert)
            return True
        return False

    def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an alert"""
        alert = self.alerts.get(alert_id)
        if alert:
            alert.resolve()
            self._notify_handlers(alert)
            return True
        return False

    def add_handler(self, handler: Callable[[Alert], None]) -> None:
        """Add an alert handler"""
        self._handlers.append(handler)

    def _notify_handlers(self, alert: Alert) -> None:
        """Notify all handlers"""
        for handler in self._handlers:
            try:
                handler(alert)
            except Exception as e:
                logger.error(f"Alert handler error: {e}")

    def create_silence(
        self,
        matcher: Dict[str, str],
        duration_seconds: int,
        reason: str = "",
    ) -> str:
        """Create a silence rule"""
        silence_id = str(uuid.uuid4())[:8]
        with self._lock:
            self._silences[silence_id] = {
                "id": silence_id,
                "matcher": matcher,
                "ends_at": datetime.utcnow() + timedelta(seconds=duration_seconds),
                "reason": reason,
            }
        return silence_id

    def _is_silenced(self, alert: Alert) -> bool:
        """Check if alert matches any silence"""
        now = datetime.utcnow()
        for silence in self._silences.values():
            if silence["ends_at"] < now:
                continue
            if self._matches(alert, silence["matcher"]):
                return True
        return False

    def _matches(self, alert: Alert, matcher: Dict[str, str]) -> bool:
        """Check if alert matches matcher"""
        for key, value in matcher.items():
            if alert.labels.get(key) != value:
                return False
        return True

    def get_statistics(self) -> Dict[str, Any]:
        """Get alert statistics"""
        with self._lock:
            return {
                "total_alerts": len(self.alerts),
                "active": len(self.get_active_alerts()),
                "by_severity": {
                    s.value: len(self.get_alerts_by_severity(s))
                    for s in AlertSeverity
                },
                "silences": len(self._silences),
            }

    def clear_resolved(self, older_than_hours: int = 24) -> int:
        """Clear old resolved alerts"""
        cutoff = datetime.utcnow() - timedelta(hours=older_than_hours)
        count = 0
        with self._lock:
            to_remove = [
                aid for aid, a in self.alerts.items()
                if a.status == AlertStatus.RESOLVED and a.resolved_at and a.resolved_at < cutoff
            ]
            for aid in to_remove:
                del self.alerts[aid]
                count += 1
        return count
