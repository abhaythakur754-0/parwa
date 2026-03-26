"""
Alert Manager for Auto-Rollback.

Manages multi-channel alerts:
- Email alerts
- Slack alerts
- PagerDuty integration
- Alert severity levels
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from enum import Enum
import logging
import json

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertChannel(Enum):
    """Available alert channels."""
    EMAIL = "email"
    SLACK = "slack"
    PAGERDUTY = "pagerduty"
    WEBHOOK = "webhook"
    LOG = "log"


@dataclass
class Alert:
    """An alert."""
    alert_id: str
    title: str
    message: str
    severity: AlertSeverity
    channel: AlertChannel
    timestamp: datetime = field(default_factory=datetime.now)
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "alert_id": self.alert_id,
            "title": self.title,
            "message": self.message,
            "severity": self.severity.value,
            "channel": self.channel.value,
            "timestamp": self.timestamp.isoformat(),
            "acknowledged": self.acknowledged,
            "acknowledged_by": self.acknowledged_by,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "metadata": self.metadata,
        }


class AlertManager:
    """
    Manages alerts for the auto-rollback system.

    Features:
    - Multi-channel alerts (email, Slack, PagerDuty)
    - Alert severity levels
    - Alert aggregation
    - Escalation rules
    - Alert history
    """

    DEFAULT_ESCALATION_RULES = {
        AlertSeverity.INFO: {"channels": [AlertChannel.LOG], "delay_seconds": 0},
        AlertSeverity.WARNING: {"channels": [AlertChannel.LOG, AlertChannel.SLACK], "delay_seconds": 0},
        AlertSeverity.ERROR: {"channels": [AlertChannel.LOG, AlertChannel.SLACK, AlertChannel.EMAIL], "delay_seconds": 0},
        AlertSeverity.CRITICAL: {"channels": [AlertChannel.LOG, AlertChannel.SLACK, AlertChannel.EMAIL, AlertChannel.PAGERDUTY], "delay_seconds": 0},
    }

    def __init__(
        self,
        escalation_rules: Optional[Dict[AlertSeverity, Dict[str, Any]]] = None,
        slack_webhook: Optional[str] = None,
        pagerduty_key: Optional[str] = None,
        email_recipients: Optional[List[str]] = None
    ):
        """
        Initialize the alert manager.

        Args:
            escalation_rules: Custom escalation rules
            slack_webhook: Slack webhook URL
            pagerduty_key: PagerDuty integration key
            email_recipients: List of email recipients
        """
        self.escalation_rules = escalation_rules or self.DEFAULT_ESCALATION_RULES
        self.slack_webhook = slack_webhook
        self.pagerduty_key = pagerduty_key
        self.email_recipients = email_recipients or []

        # Alert tracking
        self._alert_history: List[Alert] = []
        self._alert_counter: int = 0
        self._channel_handlers: Dict[AlertChannel, Callable] = {
            AlertChannel.LOG: self._send_log_alert,
        }

    def register_channel_handler(self, channel: AlertChannel, handler: Callable):
        """Register a custom handler for an alert channel."""
        self._channel_handlers[channel] = handler

    def create_alert(
        self,
        title: str,
        message: str,
        severity: AlertSeverity = AlertSeverity.WARNING,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Alert:
        """
        Create and send an alert.

        Args:
            title: Alert title
            message: Alert message
            severity: Alert severity
            metadata: Additional metadata

        Returns:
            Created Alert
        """
        self._alert_counter += 1
        alert_id = f"alert_{self._alert_counter}"

        # Get channels for this severity
        escalation = self.escalation_rules.get(severity, {})
        channels = escalation.get("channels", [AlertChannel.LOG])

        # Send to all channels
        for channel in channels:
            alert = Alert(
                alert_id=alert_id,
                title=title,
                message=message,
                severity=severity,
                channel=channel,
                metadata=metadata or {}
            )

            self._send_alert(alert)
            self._alert_history.append(alert)

        logger.info(f"Created alert {alert_id}: [{severity.value}] {title}")

        return Alert(
            alert_id=alert_id,
            title=title,
            message=message,
            severity=severity,
            channel=channels[0] if channels else AlertChannel.LOG,
            metadata=metadata or {}
        )

    def _send_alert(self, alert: Alert):
        """Send alert through appropriate channel."""
        handler = self._channel_handlers.get(alert.channel)

        if handler:
            try:
                handler(alert)
            except Exception as e:
                logger.error(f"Failed to send alert via {alert.channel.value}: {e}")
        else:
            logger.warning(f"No handler registered for channel {alert.channel.value}")

    def _send_log_alert(self, alert: Alert):
        """Send alert to logs."""
        log_level = {
            AlertSeverity.INFO: logger.info,
            AlertSeverity.WARNING: logger.warning,
            AlertSeverity.ERROR: logger.error,
            AlertSeverity.CRITICAL: logger.critical,
        }.get(alert.severity, logger.info)

        log_level(f"[ALERT] {alert.title}: {alert.message}")

    def send_slack_alert(self, alert: Alert) -> bool:
        """
        Send alert to Slack.

        Args:
            alert: Alert to send

        Returns:
            True if successful
        """
        if not self.slack_webhook:
            logger.warning("Slack webhook not configured")
            return False

        # In production, would use requests to post to Slack
        logger.info(f"Would send Slack alert: {alert.title}")
        return True

    def send_pagerduty_alert(self, alert: Alert) -> bool:
        """
        Send alert to PagerDuty.

        Args:
            alert: Alert to send

        Returns:
            True if successful
        """
        if not self.pagerduty_key:
            logger.warning("PagerDuty key not configured")
            return False

        # In production, would use PagerDuty API
        logger.info(f"Would send PagerDuty alert: {alert.title}")
        return True

    def send_email_alert(self, alert: Alert) -> bool:
        """
        Send alert via email.

        Args:
            alert: Alert to send

        Returns:
            True if successful
        """
        if not self.email_recipients:
            logger.warning("No email recipients configured")
            return False

        # In production, would send via email service
        logger.info(f"Would send email alert to {len(self.email_recipients)} recipients")
        return True

    def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        """
        Acknowledge an alert.

        Args:
            alert_id: Alert to acknowledge
            acknowledged_by: Who acknowledged it

        Returns:
            True if found and acknowledged
        """
        for alert in self._alert_history:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                alert.acknowledged_by = acknowledged_by
                alert.acknowledged_at = datetime.now()
                logger.info(f"Alert {alert_id} acknowledged by {acknowledged_by}")
                return True

        return False

    def get_alert_history(
        self,
        severity: Optional[AlertSeverity] = None,
        limit: int = 50
    ) -> List[Alert]:
        """
        Get alert history.

        Args:
            severity: Filter by severity
            limit: Max alerts to return

        Returns:
            List of alerts
        """
        alerts = self._alert_history

        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        return alerts[-limit:]

    def get_unacknowledged_alerts(self) -> List[Alert]:
        """Get all unacknowledged alerts."""
        return [a for a in self._alert_history if not a.acknowledged]

    def get_stats(self) -> Dict[str, Any]:
        """Get alert statistics."""
        severity_counts = {}
        for alert in self._alert_history:
            sev = alert.severity.value
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        return {
            "total_alerts": len(self._alert_history),
            "unacknowledged": len(self.get_unacknowledged_alerts()),
            "by_severity": severity_counts,
            "configured_channels": {
                "slack": self.slack_webhook is not None,
                "pagerduty": self.pagerduty_key is not None,
                "email": len(self.email_recipients) > 0,
            }
        }


def get_alert_manager(
    slack_webhook: Optional[str] = None
) -> AlertManager:
    """
    Factory function to create an alert manager.

    Args:
        slack_webhook: Optional Slack webhook URL

    Returns:
        Configured AlertManager instance
    """
    return AlertManager(slack_webhook=slack_webhook)
