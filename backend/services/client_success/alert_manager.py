"""
Alert Manager Service

Manages health alerts for clients including health score drops,
inactivity alerts, accuracy drops, and configurable thresholds.
Supports multi-channel notifications.
"""
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import logging
import asyncio

logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertType(str, Enum):
    """Types of health alerts."""
    HEALTH_SCORE_DROP = "health_score_drop"
    INACTIVITY = "inactivity"
    ACCURACY_DROP = "accuracy_drop"
    RESPONSE_TIME_HIGH = "response_time_high"
    RESOLUTION_RATE_LOW = "resolution_rate_low"
    ENGAGEMENT_LOW = "engagement_low"
    CHURN_RISK = "churn_risk"


@dataclass
class AlertThreshold:
    """Configuration for an alert threshold."""
    alert_type: AlertType
    threshold_value: float
    comparison: str  # "below", "above", "drop_by"
    severity: AlertSeverity
    enabled: bool = True


@dataclass
class HealthAlert:
    """A health alert for a client."""
    alert_id: str
    client_id: str
    alert_type: AlertType
    severity: AlertSeverity
    title: str
    message: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NotificationChannel:
    """Configuration for a notification channel."""
    name: str
    enabled: bool
    handler: Optional[Callable] = None


class AlertManager:
    """
    Manage health alerts for all clients.

    Provides:
    - Health score drop alerts
    - Inactivity alerts
    - Accuracy drop alerts
    - Configurable thresholds
    - Multi-channel notifications (email, in-app, SMS)
    """

    # Default alert thresholds
    DEFAULT_THRESHOLDS = [
        AlertThreshold(AlertType.HEALTH_SCORE_DROP, 60.0, "below",
                      AlertSeverity.WARNING),
        AlertThreshold(AlertType.HEALTH_SCORE_DROP, 40.0, "below",
                      AlertSeverity.CRITICAL),
        AlertThreshold(AlertType.INACTIVITY, 3, "above",
                      AlertSeverity.WARNING),  # days inactive
        AlertThreshold(AlertType.ACCURACY_DROP, 75.0, "below",
                      AlertSeverity.WARNING),
        AlertThreshold(AlertType.ACCURACY_DROP, 60.0, "below",
                      AlertSeverity.CRITICAL),
        AlertThreshold(AlertType.RESPONSE_TIME_HIGH, 4.0, "above",
                      AlertSeverity.WARNING),
        AlertThreshold(AlertType.RESOLUTION_RATE_LOW, 70.0, "below",
                      AlertSeverity.WARNING),
        AlertThreshold(AlertType.ENGAGEMENT_LOW, 40.0, "below",
                      AlertSeverity.WARNING),
    ]

    def __init__(self):
        """Initialize alert manager."""
        self._thresholds: Dict[AlertType, List[AlertThreshold]] = {}
        self._alerts: List[HealthAlert] = []
        self._notification_channels: Dict[str, NotificationChannel] = {}
        self._alert_counter = 0

        # Initialize default thresholds
        for threshold in self.DEFAULT_THRESHOLDS:
            self.add_threshold(threshold)

        # Initialize default notification channels
        self._setup_default_channels()

    def _setup_default_channels(self) -> None:
        """Set up default notification channels."""
        self._notification_channels = {
            "email": NotificationChannel("email", True),
            "in_app": NotificationChannel("in_app", True),
            "sms": NotificationChannel("sms", False),
            "slack": NotificationChannel("slack", False),
        }

    def add_threshold(self, threshold: AlertThreshold) -> None:
        """
        Add or update an alert threshold.

        Args:
            threshold: AlertThreshold configuration
        """
        if threshold.alert_type not in self._thresholds:
            self._thresholds[threshold.alert_type] = []

        # Remove existing threshold with same type and value
        self._thresholds[threshold.alert_type] = [
            t for t in self._thresholds[threshold.alert_type]
            if t.threshold_value != threshold.threshold_value
        ]

        self._thresholds[threshold.alert_type].append(threshold)
        logger.info(f"Added threshold: {threshold.alert_type.value} at {threshold.threshold_value}")

    def check_health_alerts(
        self,
        client_id: str,
        health_score: float,
        previous_score: Optional[float] = None
    ) -> List[HealthAlert]:
        """
        Check for health score alerts.

        Args:
            client_id: Client identifier
            health_score: Current health score
            previous_score: Previous health score for drop detection

        Returns:
            List of triggered alerts
        """
        alerts = []

        # Check absolute score thresholds
        score_thresholds = self._thresholds.get(AlertType.HEALTH_SCORE_DROP, [])
        for threshold in sorted(score_thresholds, key=lambda t: t.threshold_value):
            if not threshold.enabled:
                continue

            if health_score < threshold.threshold_value:
                alert = self._create_alert(
                    client_id=client_id,
                    alert_type=AlertType.HEALTH_SCORE_DROP,
                    severity=threshold.severity,
                    title=f"Health Score Alert: {client_id}",
                    message=f"Health score ({health_score:.1f}) is below threshold ({threshold.threshold_value})",
                    metadata={"current_score": health_score, "threshold": threshold.threshold_value}
                )
                alerts.append(alert)

        # Check for significant drop
        if previous_score is not None:
            drop = previous_score - health_score
            if drop >= 10:  # Significant drop threshold
                alert = self._create_alert(
                    client_id=client_id,
                    alert_type=AlertType.HEALTH_SCORE_DROP,
                    severity=AlertSeverity.WARNING if drop < 20 else AlertSeverity.CRITICAL,
                    title=f"Health Score Drop: {client_id}",
                    message=f"Health score dropped by {drop:.1f} points (from {previous_score:.1f} to {health_score:.1f})",
                    metadata={"drop": drop, "previous_score": previous_score}
                )
                alerts.append(alert)

        return alerts

    def check_inactivity_alert(
        self,
        client_id: str,
        last_activity: datetime
    ) -> Optional[HealthAlert]:
        """
        Check for inactivity alert.

        Args:
            client_id: Client identifier
            last_activity: Timestamp of last activity

        Returns:
            HealthAlert if triggered, None otherwise
        """
        thresholds = self._thresholds.get(AlertType.INACTIVITY, [])
        days_inactive = (datetime.utcnow() - last_activity).days

        for threshold in sorted(thresholds, key=lambda t: t.threshold_value):
            if not threshold.enabled:
                continue

            if days_inactive > threshold.threshold_value:
                return self._create_alert(
                    client_id=client_id,
                    alert_type=AlertType.INACTIVITY,
                    severity=threshold.severity,
                    title=f"Inactivity Alert: {client_id}",
                    message=f"No activity for {days_inactive} days",
                    metadata={"days_inactive": days_inactive}
                )

        return None

    def check_accuracy_alert(
        self,
        client_id: str,
        accuracy: float,
        previous_accuracy: Optional[float] = None
    ) -> List[HealthAlert]:
        """
        Check for accuracy alerts.

        Args:
            client_id: Client identifier
            accuracy: Current accuracy rate
            previous_accuracy: Previous accuracy for drop detection

        Returns:
            List of triggered alerts
        """
        alerts = []

        # Check absolute thresholds
        thresholds = self._thresholds.get(AlertType.ACCURACY_DROP, [])
        for threshold in sorted(thresholds, key=lambda t: t.threshold_value):
            if not threshold.enabled:
                continue

            if accuracy < threshold.threshold_value:
                alert = self._create_alert(
                    client_id=client_id,
                    alert_type=AlertType.ACCURACY_DROP,
                    severity=threshold.severity,
                    title=f"Accuracy Alert: {client_id}",
                    message=f"Accuracy ({accuracy:.1f}%) is below threshold ({threshold.threshold_value}%)",
                    metadata={"current_accuracy": accuracy, "threshold": threshold.threshold_value}
                )
                alerts.append(alert)

        # Check for significant drop
        if previous_accuracy is not None:
            drop = previous_accuracy - accuracy
            if drop >= 5:  # 5% drop threshold
                alert = self._create_alert(
                    client_id=client_id,
                    alert_type=AlertType.ACCURACY_DROP,
                    severity=AlertSeverity.WARNING if drop < 10 else AlertSeverity.ERROR,
                    title=f"Accuracy Drop: {client_id}",
                    message=f"Accuracy dropped by {drop:.1f}% (from {previous_accuracy:.1f}% to {accuracy:.1f}%)",
                    metadata={"drop": drop, "previous_accuracy": previous_accuracy}
                )
                alerts.append(alert)

        return alerts

    def check_response_time_alert(
        self,
        client_id: str,
        avg_response_time: float
    ) -> Optional[HealthAlert]:
        """
        Check for response time alert.

        Args:
            client_id: Client identifier
            avg_response_time: Average response time in hours

        Returns:
            HealthAlert if triggered, None otherwise
        """
        thresholds = self._thresholds.get(AlertType.RESPONSE_TIME_HIGH, [])
        for threshold in thresholds:
            if not threshold.enabled:
                continue

            if avg_response_time > threshold.threshold_value:
                return self._create_alert(
                    client_id=client_id,
                    alert_type=AlertType.RESPONSE_TIME_HIGH,
                    severity=threshold.severity,
                    title=f"Response Time Alert: {client_id}",
                    message=f"Average response time ({avg_response_time:.1f}h) exceeds threshold ({threshold.threshold_value}h)",
                    metadata={"response_time": avg_response_time, "threshold": threshold.threshold_value}
                )

        return None

    def check_all_alerts(
        self,
        client_id: str,
        health_data: Dict[str, Any]
    ) -> List[HealthAlert]:
        """
        Check all alert conditions for a client.

        Args:
            client_id: Client identifier
            health_data: Dict with health metrics

        Returns:
            List of all triggered alerts
        """
        all_alerts = []

        # Health score alerts
        health_alerts = self.check_health_alerts(
            client_id=client_id,
            health_score=health_data.get("health_score", 0),
            previous_score=health_data.get("previous_health_score")
        )
        all_alerts.extend(health_alerts)

        # Accuracy alerts
        accuracy_alerts = self.check_accuracy_alert(
            client_id=client_id,
            accuracy=health_data.get("accuracy", 0),
            previous_accuracy=health_data.get("previous_accuracy")
        )
        all_alerts.extend(accuracy_alerts)

        # Response time alert
        response_alert = self.check_response_time_alert(
            client_id=client_id,
            avg_response_time=health_data.get("avg_response_time", 0)
        )
        if response_alert:
            all_alerts.append(response_alert)

        # Inactivity alert
        if "last_activity" in health_data:
            inactivity_alert = self.check_inactivity_alert(
                client_id=client_id,
                last_activity=health_data["last_activity"]
            )
            if inactivity_alert:
                all_alerts.append(inactivity_alert)

        return all_alerts

    def _create_alert(
        self,
        client_id: str,
        alert_type: AlertType,
        severity: AlertSeverity,
        title: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> HealthAlert:
        """
        Create and store a new alert.
        """
        self._alert_counter += 1
        alert_id = f"alert_{self._alert_counter:06d}"

        alert = HealthAlert(
            alert_id=alert_id,
            client_id=client_id,
            alert_type=alert_type,
            severity=severity,
            title=title,
            message=message,
            metadata=metadata or {}
        )

        self._alerts.append(alert)
        logger.warning(f"Alert created: [{severity.value}] {title} - {message}")

        return alert

    async def send_notifications(
        self,
        alert: HealthAlert,
        channels: Optional[List[str]] = None
    ) -> Dict[str, bool]:
        """
        Send alert notifications through configured channels.

        Args:
            alert: HealthAlert to send
            channels: Optional list of specific channels to use

        Returns:
            Dict mapping channel name to success status
        """
        channels_to_use = channels or list(self._notification_channels.keys())
        results = {}

        for channel_name in channels_to_use:
            channel = self._notification_channels.get(channel_name)
            if not channel or not channel.enabled:
                results[channel_name] = False
                continue

            try:
                # Simulate notification sending
                success = await self._send_to_channel(channel_name, alert)
                results[channel_name] = success
                logger.info(f"Alert {alert.alert_id} sent via {channel_name}")
            except Exception as e:
                logger.error(f"Failed to send alert via {channel_name}: {e}")
                results[channel_name] = False

        return results

    async def _send_to_channel(
        self,
        channel_name: str,
        alert: HealthAlert
    ) -> bool:
        """
        Send alert to a specific channel.
        """
        # Simulate async notification sending
        await asyncio.sleep(0.1)  # Simulate network delay

        # In production, this would call actual notification services
        notification_payload = {
            "alert_id": alert.alert_id,
            "client_id": alert.client_id,
            "severity": alert.severity.value,
            "title": alert.title,
            "message": alert.message,
            "timestamp": alert.timestamp.isoformat(),
        }

        logger.debug(f"Sending to {channel_name}: {notification_payload}")
        return True

    def acknowledge_alert(
        self,
        alert_id: str,
        acknowledged_by: str
    ) -> Optional[HealthAlert]:
        """
        Acknowledge an alert.

        Args:
            alert_id: Alert identifier
            acknowledged_by: User who acknowledged

        Returns:
            Updated HealthAlert if found, None otherwise
        """
        for alert in self._alerts:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                alert.acknowledged_by = acknowledged_by
                alert.acknowledged_at = datetime.utcnow()
                logger.info(f"Alert {alert_id} acknowledged by {acknowledged_by}")
                return alert

        return None

    def get_active_alerts(
        self,
        client_id: Optional[str] = None,
        severity: Optional[AlertSeverity] = None
    ) -> List[HealthAlert]:
        """
        Get active (unacknowledged) alerts.

        Args:
            client_id: Optional filter by client
            severity: Optional filter by severity

        Returns:
            List of active alerts
        """
        alerts = [a for a in self._alerts if not a.acknowledged]

        if client_id:
            alerts = [a for a in alerts if a.client_id == client_id]

        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        return sorted(alerts, key=lambda a: a.timestamp, reverse=True)

    def get_alert_history(
        self,
        client_id: Optional[str] = None,
        days: int = 30
    ) -> List[HealthAlert]:
        """
        Get alert history.

        Args:
            client_id: Optional filter by client
            days: Number of days to look back

        Returns:
            List of historical alerts
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        alerts = [a for a in self._alerts if a.timestamp >= cutoff]

        if client_id:
            alerts = [a for a in alerts if a.client_id == client_id]

        return sorted(alerts, key=lambda a: a.timestamp, reverse=True)

    def configure_channel(
        self,
        channel_name: str,
        enabled: bool,
        handler: Optional[Callable] = None
    ) -> None:
        """
        Configure a notification channel.

        Args:
            channel_name: Channel to configure
            enabled: Whether channel is enabled
            handler: Optional custom handler function
        """
        self._notification_channels[channel_name] = NotificationChannel(
            name=channel_name,
            enabled=enabled,
            handler=handler
        )
        logger.info(f"Configured channel {channel_name}: enabled={enabled}")

    def get_alert_summary(self) -> Dict[str, Any]:
        """
        Get summary of alerts.
        """
        active = self.get_active_alerts()

        severity_counts = {}
        for severity in AlertSeverity:
            severity_counts[severity.value] = len([
                a for a in active if a.severity == severity
            ])

        return {
            "total_alerts": len(self._alerts),
            "active_alerts": len(active),
            "acknowledged_alerts": len(self._alerts) - len(active),
            "by_severity": severity_counts,
            "clients_with_alerts": len(set(a.client_id for a in active)),
        }
