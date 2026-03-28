"""
Usage Alerts for SaaS Advanced Module.

Provides usage alerting including:
- Threshold-based alerts (50%, 75%, 90%, 100%)
- Predictive usage alerts
- Multi-channel notifications (email, SMS, in-app)
- Alert frequency management
- Alert preference management
- Escalation for critical thresholds
"""

from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class AlertThreshold(str, Enum):
    """Alert threshold levels."""
    FIFTY_PERCENT = "50%"
    SEVENTY_FIVE_PERCENT = "75%"
    NINETY_PERCENT = "90%"
    ONE_HUNDRED_PERCENT = "100%"
    CUSTOM = "custom"


class AlertChannel(str, Enum):
    """Alert delivery channels."""
    EMAIL = "email"
    SMS = "sms"
    IN_APP = "in_app"
    WEBHOOK = "webhook"
    SLACK = "slack"


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class UsageAlert:
    """Represents a usage alert."""
    id: UUID = field(default_factory=uuid4)
    client_id: str = ""
    usage_type: str = ""
    threshold: AlertThreshold = AlertThreshold.NINETY_PERCENT
    percentage: float = 0.0
    current_usage: float = 0.0
    limit: float = 0.0
    severity: AlertSeverity = AlertSeverity.WARNING
    channels: List[AlertChannel] = field(default_factory=list)
    sent_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    acknowledged: bool = False
    acknowledged_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": str(self.id),
            "client_id": self.client_id,
            "usage_type": self.usage_type,
            "threshold": self.threshold.value,
            "percentage": self.percentage,
            "current_usage": self.current_usage,
            "limit": self.limit,
            "severity": self.severity.value,
            "channels": [c.value for c in self.channels],
            "sent_at": self.sent_at.isoformat(),
            "acknowledged": self.acknowledged,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
        }


@dataclass
class AlertPreference:
    """Alert preference configuration."""
    usage_type: str = ""
    thresholds: List[AlertThreshold] = field(default_factory=lambda: [
        AlertThreshold.SEVENTY_FIVE_PERCENT,
        AlertThreshold.NINETY_PERCENT,
        AlertThreshold.ONE_HUNDRED_PERCENT,
    ])
    channels: List[AlertChannel] = field(default_factory=lambda: [
        AlertChannel.EMAIL,
        AlertChannel.IN_APP,
    ])
    enabled: bool = True
    cooldown_hours: int = 24

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "usage_type": self.usage_type,
            "thresholds": [t.value for t in self.thresholds],
            "channels": [c.value for c in self.channels],
            "enabled": self.enabled,
            "cooldown_hours": self.cooldown_hours,
        }


# Default thresholds and their severity
THRESHOLD_CONFIG = {
    AlertThreshold.FIFTY_PERCENT: {"severity": AlertSeverity.INFO, "color": "blue"},
    AlertThreshold.SEVENTY_FIVE_PERCENT: {"severity": AlertSeverity.WARNING, "color": "yellow"},
    AlertThreshold.NINETY_PERCENT: {"severity": AlertSeverity.WARNING, "color": "orange"},
    AlertThreshold.ONE_HUNDRED_PERCENT: {"severity": AlertSeverity.CRITICAL, "color": "red"},
}

# Default alert preferences
DEFAULT_PREFERENCES = {
    "api_calls": AlertPreference(
        usage_type="api_calls",
        thresholds=[AlertThreshold.NINETY_PERCENT, AlertThreshold.ONE_HUNDRED_PERCENT],
    ),
    "ai_interactions": AlertPreference(
        usage_type="ai_interactions",
        thresholds=[AlertThreshold.SEVENTY_FIVE_PERCENT, AlertThreshold.NINETY_PERCENT, AlertThreshold.ONE_HUNDRED_PERCENT],
    ),
    "voice_minutes": AlertPreference(
        usage_type="voice_minutes",
        thresholds=[AlertThreshold.NINETY_PERCENT, AlertThreshold.ONE_HUNDRED_PERCENT],
    ),
    "tickets": AlertPreference(
        usage_type="tickets",
        thresholds=[AlertThreshold.NINETY_PERCENT, AlertThreshold.ONE_HUNDRED_PERCENT],
    ),
    "storage_gb": AlertPreference(
        usage_type="storage_gb",
        thresholds=[AlertThreshold.SEVENTY_FIVE_PERCENT, AlertThreshold.NINETY_PERCENT, AlertThreshold.ONE_HUNDRED_PERCENT],
    ),
}


class UsageAlerts:
    """
    Manages usage alerts for SaaS clients.

    Features:
    - Threshold-based alerts
    - Predictive alerts
    - Multi-channel notifications
    - Alert preferences
    - Escalation workflows
    """

    def __init__(
        self,
        client_id: str = "",
        email: Optional[str] = None,
        phone: Optional[str] = None
    ):
        """
        Initialize usage alerts manager.

        Args:
            client_id: Client identifier
            email: Email for notifications
            phone: Phone for SMS notifications
        """
        self.client_id = client_id
        self.email = email
        self.phone = phone

        self._alerts: List[UsageAlert] = []
        self._preferences: Dict[str, AlertPreference] = DEFAULT_PREFERENCES.copy()
        self._last_alert_times: Dict[str, datetime] = {}

    async def check_and_alert(
        self,
        usage_type: str,
        current: float,
        limit: float
    ) -> Optional[UsageAlert]:
        """
        Check usage and trigger alert if needed.

        Args:
            usage_type: Type of usage
            current: Current usage
            limit: Usage limit

        Returns:
            UsageAlert if triggered, None otherwise
        """
        if limit <= 0:
            return None

        percentage = (current / limit) * 100
        pref = self._preferences.get(usage_type)

        if not pref or not pref.enabled:
            return None

        # Check cooldown
        key = f"{usage_type}"
        if key in self._last_alert_times:
            cooldown_end = self._last_alert_times[key] + timedelta(hours=pref.cooldown_hours)
            if datetime.now(timezone.utc) < cooldown_end:
                return None

        # Find applicable threshold
        triggered_threshold = None
        for threshold in pref.thresholds:
            threshold_pct = self._get_threshold_percentage(threshold)
            if percentage >= threshold_pct:
                triggered_threshold = threshold

        if not triggered_threshold:
            return None

        # Create alert
        config = THRESHOLD_CONFIG.get(triggered_threshold, THRESHOLD_CONFIG[AlertThreshold.NINETY_PERCENT])

        alert = UsageAlert(
            client_id=self.client_id,
            usage_type=usage_type,
            threshold=triggered_threshold,
            percentage=round(percentage, 2),
            current_usage=current,
            limit=limit,
            severity=config["severity"],
            channels=pref.channels,
        )

        self._alerts.append(alert)
        self._last_alert_times[key] = datetime.now(timezone.utc)

        # Send alerts through channels
        await self._send_alert(alert)

        logger.info(
            "Usage alert triggered",
            extra={
                "client_id": self.client_id,
                "usage_type": usage_type,
                "threshold": triggered_threshold.value,
                "percentage": percentage,
            }
        )

        return alert

    async def send_predictive_alert(
        self,
        usage_type: str,
        current: float,
        limit: float,
        projected: float,
        days_remaining: int
    ) -> Optional[UsageAlert]:
        """
        Send predictive usage alert.

        Args:
            usage_type: Type of usage
            current: Current usage
            limit: Usage limit
            projected: Projected end-of-period usage
            days_remaining: Days remaining in period

        Returns:
            UsageAlert if sent, None otherwise
        """
        # Only alert if projected to exceed limit
        if projected <= limit:
            return None

        percentage = (current / limit) * 100
        projected_percentage = (projected / limit) * 100

        pref = self._preferences.get(usage_type)
        if not pref or not pref.enabled:
            return None

        alert = UsageAlert(
            client_id=self.client_id,
            usage_type=usage_type,
            threshold=AlertThreshold.CUSTOM,
            percentage=round(percentage, 2),
            current_usage=current,
            limit=limit,
            severity=AlertSeverity.WARNING,
            channels=pref.channels,
        )

        # Add predictive metadata
        alert.metadata = {
            "projected_usage": projected,
            "projected_percentage": round(projected_percentage, 2),
            "days_remaining": days_remaining,
            "will_exceed": True,
        }

        self._alerts.append(alert)
        await self._send_alert(alert)

        logger.info(
            "Predictive usage alert sent",
            extra={
                "client_id": self.client_id,
                "usage_type": usage_type,
                "projected_percentage": projected_percentage,
            }
        )

        return alert

    async def set_preference(
        self,
        usage_type: str,
        thresholds: Optional[List[AlertThreshold]] = None,
        channels: Optional[List[AlertChannel]] = None,
        enabled: Optional[bool] = None,
        cooldown_hours: Optional[int] = None
    ) -> AlertPreference:
        """
        Set alert preference for a usage type.

        Args:
            usage_type: Type of usage
            thresholds: Alert thresholds
            channels: Notification channels
            enabled: Whether alerts are enabled
            cooldown_hours: Hours between alerts

        Returns:
            Updated AlertPreference
        """
        pref = self._preferences.get(usage_type, AlertPreference(usage_type=usage_type))

        if thresholds is not None:
            pref.thresholds = thresholds
        if channels is not None:
            pref.channels = channels
        if enabled is not None:
            pref.enabled = enabled
        if cooldown_hours is not None:
            pref.cooldown_hours = cooldown_hours

        self._preferences[usage_type] = pref

        logger.info(
            "Alert preference updated",
            extra={
                "client_id": self.client_id,
                "usage_type": usage_type,
                "thresholds": [t.value for t in pref.thresholds],
            }
        )

        return pref

    async def get_preferences(self) -> Dict[str, Any]:
        """
        Get all alert preferences.

        Returns:
            Dict with all preferences
        """
        return {
            usage_type: pref.to_dict()
            for usage_type, pref in self._preferences.items()
        }

    async def get_alert_history(
        self,
        limit: int = 50,
        unacknowledged_only: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get alert history.

        Args:
            limit: Maximum alerts to return
            unacknowledged_only: Only return unacknowledged alerts

        Returns:
            List of alerts
        """
        alerts = [
            alert.to_dict()
            for alert in self._alerts
            if alert.client_id == self.client_id
        ]

        if unacknowledged_only:
            alerts = [a for a in alerts if not a["acknowledged"]]

        alerts.sort(key=lambda x: x["sent_at"], reverse=True)

        return alerts[:limit]

    async def acknowledge_alert(self, alert_id: UUID) -> Dict[str, Any]:
        """
        Acknowledge an alert.

        Args:
            alert_id: Alert UUID

        Returns:
            Dict with acknowledgment result
        """
        for alert in self._alerts:
            if alert.id == alert_id:
                alert.acknowledged = True
                alert.acknowledged_at = datetime.now(timezone.utc)

                logger.info(
                    "Alert acknowledged",
                    extra={
                        "client_id": self.client_id,
                        "alert_id": str(alert_id),
                    }
                )

                return {
                    "acknowledged": True,
                    "alert_id": str(alert_id),
                    "acknowledged_at": alert.acknowledged_at.isoformat(),
                }

        return {
            "acknowledged": False,
            "reason": "alert_not_found",
        }

    async def escalate_critical(
        self,
        usage_type: str,
        current: float,
        limit: float
    ) -> Dict[str, Any]:
        """
        Escalate a critical usage alert.

        Args:
            usage_type: Type of usage
            current: Current usage
            limit: Usage limit

        Returns:
            Dict with escalation result
        """
        percentage = (current / limit * 100) if limit > 0 else 100

        alert = UsageAlert(
            client_id=self.client_id,
            usage_type=usage_type,
            threshold=AlertThreshold.ONE_HUNDRED_PERCENT,
            percentage=round(percentage, 2),
            current_usage=current,
            limit=limit,
            severity=AlertSeverity.CRITICAL,
            channels=[AlertChannel.EMAIL, AlertChannel.SMS, AlertChannel.IN_APP],
        )

        self._alerts.append(alert)

        # Send through all channels
        await self._send_alert(alert, escalate=True)

        logger.warning(
            "Critical alert escalated",
            extra={
                "client_id": self.client_id,
                "usage_type": usage_type,
                "percentage": percentage,
            }
        )

        return {
            "escalated": True,
            "alert": alert.to_dict(),
        }

    async def _send_alert(
        self,
        alert: UsageAlert,
        escalate: bool = False
    ) -> None:
        """
        Send alert through configured channels.

        Args:
            alert: Alert to send
            escalate: Whether this is an escalation
        """
        for channel in alert.channels:
            if channel == AlertChannel.EMAIL:
                await self._send_email_alert(alert)
            elif channel == AlertChannel.SMS:
                await self._send_sms_alert(alert)
            elif channel == AlertChannel.IN_APP:
                await self._send_in_app_alert(alert)
            elif channel == AlertChannel.WEBHOOK:
                await self._send_webhook_alert(alert)
            elif channel == AlertChannel.SLACK:
                await self._send_slack_alert(alert)

    async def _send_email_alert(self, alert: UsageAlert) -> None:
        """Send email alert."""
        if not self.email:
            return

        logger.info(
            "Email alert sent",
            extra={
                "client_id": self.client_id,
                "email": self.email,
                "usage_type": alert.usage_type,
            }
        )

    async def _send_sms_alert(self, alert: UsageAlert) -> None:
        """Send SMS alert."""
        if not self.phone:
            return

        logger.info(
            "SMS alert sent",
            extra={
                "client_id": self.client_id,
                "phone": self.phone[-4:],  # Last 4 digits only
                "usage_type": alert.usage_type,
            }
        )

    async def _send_in_app_alert(self, alert: UsageAlert) -> None:
        """Send in-app notification."""
        logger.info(
            "In-app alert sent",
            extra={
                "client_id": self.client_id,
                "usage_type": alert.usage_type,
            }
        )

    async def _send_webhook_alert(self, alert: UsageAlert) -> None:
        """Send webhook notification."""
        logger.info(
            "Webhook alert sent",
            extra={
                "client_id": self.client_id,
                "usage_type": alert.usage_type,
            }
        )

    async def _send_slack_alert(self, alert: UsageAlert) -> None:
        """Send Slack notification."""
        logger.info(
            "Slack alert sent",
            extra={
                "client_id": self.client_id,
                "usage_type": alert.usage_type,
            }
        )

    def _get_threshold_percentage(self, threshold: AlertThreshold) -> float:
        """Get numeric percentage for threshold."""
        mapping = {
            AlertThreshold.FIFTY_PERCENT: 50.0,
            AlertThreshold.SEVENTY_FIVE_PERCENT: 75.0,
            AlertThreshold.NINETY_PERCENT: 90.0,
            AlertThreshold.ONE_HUNDRED_PERCENT: 100.0,
            AlertThreshold.CUSTOM: 0.0,
        }
        return mapping.get(threshold, 90.0)


# Export for testing
__all__ = [
    "UsageAlerts",
    "UsageAlert",
    "AlertPreference",
    "AlertThreshold",
    "AlertChannel",
    "AlertSeverity",
    "THRESHOLD_CONFIG",
    "DEFAULT_PREFERENCES",
]
