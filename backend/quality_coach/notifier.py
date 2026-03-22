"""
Quality Notifier for Real-Time Quality Alerts.

Provides real-time alerts when quality scores drop below thresholds.

Features:
- Alert on low quality scores
- Notify managers of issues
- Configure quality alert thresholds
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
import uuid

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class AlertType(str, Enum):
    """Types of quality alerts."""
    LOW_QUALITY = "low_quality"
    CRITICAL_QUALITY = "critical_quality"
    ACCURACY_DROP = "accuracy_drop"
    EMPATHY_DROP = "empathy_drop"
    EFFICIENCY_DROP = "efficiency_drop"
    TREND_DECLINE = "trend_decline"


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AlertThresholds:
    """Quality alert thresholds."""
    low_quality: float = 50.0
    critical_quality: float = 25.0
    accuracy_drop: float = 20.0  # Drop from previous
    empathy_drop: float = 20.0
    efficiency_drop: float = 20.0


@dataclass
class QualityAlert:
    """Quality alert record."""
    alert_id: str
    alert_type: AlertType
    severity: AlertSeverity
    interaction_id: str
    company_id: str
    score: float
    threshold: float
    message: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    acknowledged: bool = False
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None


class QualityNotifier:
    """
    Real-time Quality Alert System.

    CRITICAL: Fires alerts when quality drops below thresholds.

    Features:
    - Alert on low quality scores
    - Notify managers of issues
    - Configurable thresholds

    Example:
        notifier = QualityNotifier()
        result = await notifier.alert_low_quality("interaction_123", 35.0)
    """

    # Default thresholds
    DEFAULT_THRESHOLDS = AlertThresholds()

    def __init__(
        self,
        thresholds: Optional[AlertThresholds] = None
    ) -> None:
        """
        Initialize Quality Notifier.

        Args:
            thresholds: Custom alert thresholds
        """
        self.thresholds = thresholds or self.DEFAULT_THRESHOLDS
        self._alerts: Dict[str, QualityAlert] = {}
        self._company_thresholds: Dict[str, AlertThresholds] = {}
        self._managers: Dict[str, List[str]] = {}

        logger.info({
            "event": "quality_notifier_initialized",
            "low_quality_threshold": self.thresholds.low_quality,
            "critical_quality_threshold": self.thresholds.critical_quality
        })

    async def alert_low_quality(
        self,
        interaction_id: str,
        score: float,
        company_id: str = "default",
        scores: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Alert on low quality score.

        CRITICAL: Fires real-time alert when score is low.

        Args:
            interaction_id: Interaction identifier
            score: Overall quality score
            company_id: Company identifier
            scores: Detailed scores (accuracy, empathy, efficiency)

        Returns:
            Dict with alert result
        """
        alert_id = f"alert_{uuid.uuid4().hex[:8]}"
        thresholds = self._company_thresholds.get(company_id, self.thresholds)

        logger.info({
            "event": "quality_alert_check",
            "alert_id": alert_id,
            "interaction_id": interaction_id,
            "score": score,
            "thresholds": {
                "low": thresholds.low_quality,
                "critical": thresholds.critical_quality
            }
        })

        # Determine alert type and severity
        if score < thresholds.critical_quality:
            alert_type = AlertType.CRITICAL_QUALITY
            severity = AlertSeverity.CRITICAL
        elif score < thresholds.low_quality:
            alert_type = AlertType.LOW_QUALITY
            severity = AlertSeverity.WARNING
        else:
            # No alert needed
            return {
                "success": True,
                "alert_fired": False,
                "reason": "Score above threshold",
                "score": score,
                "threshold": thresholds.low_quality
            }

        # Create alert
        message = self._generate_alert_message(
            alert_type, interaction_id, score, thresholds
        )

        alert = QualityAlert(
            alert_id=alert_id,
            alert_type=alert_type,
            severity=severity,
            interaction_id=interaction_id,
            company_id=company_id,
            score=score,
            threshold=thresholds.low_quality if alert_type == AlertType.LOW_QUALITY else thresholds.critical_quality,
            message=message
        )

        self._alerts[alert_id] = alert

        # Notify managers
        await self._notify_managers(company_id, alert)

        logger.warning({
            "event": "quality_alert_fired",
            "alert_id": alert_id,
            "alert_type": alert_type.value,
            "severity": severity.value,
            "interaction_id": interaction_id,
            "score": score
        })

        return {
            "success": True,
            "alert_fired": True,
            "alert_id": alert_id,
            "alert_type": alert_type.value,
            "severity": severity.value,
            "interaction_id": interaction_id,
            "score": score,
            "threshold": alert.threshold,
            "message": message,
            "created_at": alert.created_at.isoformat()
        }

    def _generate_alert_message(
        self,
        alert_type: AlertType,
        interaction_id: str,
        score: float,
        thresholds: AlertThresholds
    ) -> str:
        """Generate alert message."""
        if alert_type == AlertType.CRITICAL_QUALITY:
            return (
                f"CRITICAL: Interaction {interaction_id} has quality score "
                f"{score:.1f} (below {thresholds.critical_quality} threshold). "
                f"Immediate review required."
            )
        else:
            return (
                f"WARNING: Interaction {interaction_id} has low quality score "
                f"{score:.1f} (below {thresholds.low_quality} threshold). "
                f"Review recommended."
            )

    async def _notify_managers(
        self,
        company_id: str,
        alert: QualityAlert
    ) -> None:
        """Notify managers of alert."""
        managers = self._managers.get(company_id, [])

        if not managers:
            logger.info({
                "event": "no_managers_configured",
                "company_id": company_id
            })
            return

        for manager_id in managers:
            await self.notify_manager(company_id, {
                "alert_id": alert.alert_id,
                "manager_id": manager_id,
                "alert_type": alert.alert_type.value,
                "severity": alert.severity.value,
                "message": alert.message
            })

    async def notify_manager(
        self,
        company_id: str,
        issue: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Notify a manager of a quality issue.

        Args:
            company_id: Company identifier
            issue: Issue details

        Returns:
            Dict with notification result
        """
        manager_id = issue.get("manager_id", "unknown")

        logger.info({
            "event": "manager_notified",
            "company_id": company_id,
            "manager_id": manager_id,
            "alert_type": issue.get("alert_type")
        })

        # In production, this would send email/slack/push notification
        notification = {
            "notification_id": f"notif_{uuid.uuid4().hex[:8]}",
            "manager_id": manager_id,
            "company_id": company_id,
            "issue": issue,
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "channel": "email"  # Could be email, slack, push, etc.
        }

        return {
            "success": True,
            "notification": notification
        }

    async def setup_alerts(
        self,
        company_id: str,
        thresholds: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Setup quality alert thresholds for a company.

        Args:
            company_id: Company identifier
            thresholds: Threshold values

        Returns:
            Dict with setup result
        """
        custom_thresholds = AlertThresholds(
            low_quality=thresholds.get("low_quality", 50.0),
            critical_quality=thresholds.get("critical_quality", 25.0),
            accuracy_drop=thresholds.get("accuracy_drop", 20.0),
            empathy_drop=thresholds.get("empathy_drop", 20.0),
            efficiency_drop=thresholds.get("efficiency_drop", 20.0)
        )

        self._company_thresholds[company_id] = custom_thresholds

        logger.info({
            "event": "quality_alerts_configured",
            "company_id": company_id,
            "thresholds": thresholds
        })

        return {
            "success": True,
            "company_id": company_id,
            "thresholds": {
                "low_quality": custom_thresholds.low_quality,
                "critical_quality": custom_thresholds.critical_quality,
                "accuracy_drop": custom_thresholds.accuracy_drop,
                "empathy_drop": custom_thresholds.empathy_drop,
                "efficiency_drop": custom_thresholds.efficiency_drop
            }
        }

    def add_manager(
        self,
        company_id: str,
        manager_id: str
    ) -> None:
        """Add a manager to receive alerts."""
        if company_id not in self._managers:
            self._managers[company_id] = []
        if manager_id not in self._managers[company_id]:
            self._managers[company_id].append(manager_id)

    def remove_manager(
        self,
        company_id: str,
        manager_id: str
    ) -> None:
        """Remove a manager from alerts."""
        if company_id in self._managers:
            if manager_id in self._managers[company_id]:
                self._managers[company_id].remove(manager_id)

    async def acknowledge_alert(
        self,
        alert_id: str,
        acknowledged_by: str
    ) -> Dict[str, Any]:
        """
        Acknowledge an alert.

        Args:
            alert_id: Alert to acknowledge
            acknowledged_by: Who acknowledged it

        Returns:
            Dict with acknowledgment result
        """
        alert = self._alerts.get(alert_id)

        if not alert:
            return {
                "success": False,
                "error": f"Alert {alert_id} not found"
            }

        alert.acknowledged = True
        alert.acknowledged_at = datetime.now(timezone.utc)
        alert.acknowledged_by = acknowledged_by

        logger.info({
            "event": "alert_acknowledged",
            "alert_id": alert_id,
            "acknowledged_by": acknowledged_by
        })

        return {
            "success": True,
            "alert_id": alert_id,
            "acknowledged": True,
            "acknowledged_at": alert.acknowledged_at.isoformat(),
            "acknowledged_by": acknowledged_by
        }

    def get_alerts(
        self,
        company_id: Optional[str] = None,
        severity: Optional[AlertSeverity] = None,
        acknowledged: Optional[bool] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get alerts with optional filters.

        Args:
            company_id: Filter by company
            severity: Filter by severity
            acknowledged: Filter by acknowledgment status
            limit: Maximum results

        Returns:
            List of alerts
        """
        alerts = list(self._alerts.values())

        if company_id:
            alerts = [a for a in alerts if a.company_id == company_id]
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        if acknowledged is not None:
            alerts = [a for a in alerts if a.acknowledged == acknowledged]

        alerts = sorted(alerts, key=lambda a: a.created_at, reverse=True)

        return [
            {
                "alert_id": a.alert_id,
                "alert_type": a.alert_type.value,
                "severity": a.severity.value,
                "company_id": a.company_id,
                "interaction_id": a.interaction_id,
                "score": a.score,
                "threshold": a.threshold,
                "message": a.message,
                "acknowledged": a.acknowledged,
                "created_at": a.created_at.isoformat()
            }
            for a in alerts[:limit]
        ]

    def get_unacknowledged_count(
        self,
        company_id: Optional[str] = None
    ) -> int:
        """Get count of unacknowledged alerts."""
        alerts = list(self._alerts.values())

        if company_id:
            alerts = [a for a in alerts if a.company_id == company_id]

        return sum(1 for a in alerts if not a.acknowledged)

    def get_status(self) -> Dict[str, Any]:
        """Get notifier status."""
        return {
            "total_alerts": len(self._alerts),
            "unacknowledged_count": self.get_unacknowledged_count(),
            "companies_with_custom_thresholds": len(self._company_thresholds),
            "default_thresholds": {
                "low_quality": self.thresholds.low_quality,
                "critical_quality": self.thresholds.critical_quality
            }
        }


def get_quality_notifier(
    thresholds: Optional[AlertThresholds] = None
) -> QualityNotifier:
    """
    Get a QualityNotifier instance.

    Args:
        thresholds: Optional custom thresholds

    Returns:
        QualityNotifier instance
    """
    return QualityNotifier(thresholds=thresholds)
