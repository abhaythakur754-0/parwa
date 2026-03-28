"""
Replication Monitor for Cross-Region Replication.

Monitors replication status:
- Monitor replication status
- Alert on replication lag >500ms
- Track replication queue depth
- Monitor replication errors
- Health dashboard
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class Region(str, Enum):
    """Available regions."""
    EU = "eu-west-1"
    US = "us-east-1"
    APAC = "ap-southeast-1"


class HealthStatus(str, Enum):
    """Health status of replication."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class AlertConfig:
    """Configuration for alerts."""
    lag_threshold_ms: int = 500
    queue_depth_threshold: int = 1000
    error_rate_threshold: float = 0.05
    alert_cooldown_seconds: int = 60


@dataclass
class ReplicationAlert:
    """Replication alert."""
    alert_id: str
    alert_type: str
    region: Optional[Region]
    message: str
    severity: str
    timestamp: datetime = field(default_factory=datetime.now)
    acknowledged: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "alert_id": self.alert_id,
            "alert_type": self.alert_type,
            "region": self.region.value if self.region else None,
            "message": self.message,
            "severity": self.severity,
            "timestamp": self.timestamp.isoformat(),
            "acknowledged": self.acknowledged
        }


@dataclass
class RegionHealth:
    """Health status of a region's replication."""
    region: Region
    status: HealthStatus
    lag_ms: int
    queue_depth: int
    error_rate: float
    last_successful_replication: Optional[datetime]
    message: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "region": self.region.value,
            "status": self.status.value,
            "lag_ms": self.lag_ms,
            "queue_depth": self.queue_depth,
            "error_rate": self.error_rate,
            "last_successful_replication": self.last_successful_replication.isoformat() if self.last_successful_replication else None,
            "message": self.message
        }


class ReplicationMonitor:
    """
    Monitors replication status.

    Features:
    - Monitor replication status
    - Alert on replication lag >500ms
    - Track replication queue depth
    - Monitor replication errors
    - Health dashboard
    """

    def __init__(
        self,
        alert_config: Optional[AlertConfig] = None
    ):
        """
        Initialize the replication monitor.

        Args:
            alert_config: Alert configuration
        """
        self.alert_config = alert_config or AlertConfig()
        self._alerts: List[ReplicationAlert] = []
        self._region_health: Dict[Region, RegionHealth] = {}
        self._alert_cooldowns: Dict[str, datetime] = {}

        # Initialize default health for all regions
        for region in Region:
            self._region_health[region] = RegionHealth(
                region=region,
                status=HealthStatus.HEALTHY,
                lag_ms=0,
                queue_depth=0,
                error_rate=0.0,
                last_successful_replication=datetime.now(),
                message="Initialized"
            )

    def update_region_stats(
        self,
        region: Region,
        lag_ms: int,
        queue_depth: int,
        error_rate: float,
        last_successful: Optional[datetime] = None
    ) -> RegionHealth:
        """
        Update stats for a region.

        Args:
            region: Region to update
            lag_ms: Current replication lag
            queue_depth: Current queue depth
            error_rate: Current error rate
            last_successful: Time of last successful replication

        Returns:
            Updated RegionHealth
        """
        # Determine health status
        status = HealthStatus.HEALTHY
        message = "All systems operational"

        if lag_ms > self.alert_config.lag_threshold_ms:
            status = HealthStatus.DEGRADED
            message = f"Replication lag high: {lag_ms}ms"
            self._check_alert("high_lag", region, f"Lag {lag_ms}ms exceeds threshold")

        if queue_depth > self.alert_config.queue_depth_threshold:
            status = HealthStatus.DEGRADED
            message = f"Queue depth high: {queue_depth}"
            self._check_alert("high_queue", region, f"Queue depth {queue_depth} exceeds threshold")

        if error_rate > self.alert_config.error_rate_threshold:
            status = HealthStatus.UNHEALTHY
            message = f"Error rate high: {error_rate:.1%}"
            self._check_alert("high_errors", region, f"Error rate {error_rate:.1%} exceeds threshold")

        health = RegionHealth(
            region=region,
            status=status,
            lag_ms=lag_ms,
            queue_depth=queue_depth,
            error_rate=error_rate,
            last_successful_replication=last_successful or self._region_health[region].last_successful_replication,
            message=message
        )

        self._region_health[region] = health

        if status != HealthStatus.HEALTHY:
            logger.warning(f"Region {region.value} health: {status.value} - {message}")

        return health

    def _check_alert(self, alert_type: str, region: Region, message: str) -> None:
        """Check and potentially create an alert."""
        key = f"{alert_type}:{region.value}"

        # Check cooldown
        if key in self._alert_cooldowns:
            if datetime.now() - self._alert_cooldowns[key] < timedelta(seconds=self.alert_config.alert_cooldown_seconds):
                return

        # Create alert
        alert_id = f"alert-{datetime.now().strftime('%Y%m%d%H%M%S')}-{alert_type}"

        severity = "warning"
        if alert_type == "high_errors":
            severity = "critical"

        alert = ReplicationAlert(
            alert_id=alert_id,
            alert_type=alert_type,
            region=region,
            message=message,
            severity=severity
        )

        self._alerts.append(alert)
        self._alert_cooldowns[key] = datetime.now()

        logger.warning(f"ALERT [{severity}]: {message}")

    def get_region_health(self, region: Region) -> RegionHealth:
        """Get health for a specific region."""
        return self._region_health.get(region)

    def get_all_health(self) -> Dict[Region, RegionHealth]:
        """Get health for all regions."""
        return self._region_health.copy()

    def get_overall_status(self) -> HealthStatus:
        """Get overall replication health status."""
        statuses = [h.status for h in self._region_health.values()]

        if HealthStatus.UNHEALTHY in statuses:
            return HealthStatus.UNHEALTHY
        elif HealthStatus.DEGRADED in statuses:
            return HealthStatus.DEGRADED
        return HealthStatus.HEALTHY

    def get_alerts(
        self,
        acknowledged: Optional[bool] = None,
        severity: Optional[str] = None
    ) -> List[ReplicationAlert]:
        """
        Get alerts.

        Args:
            acknowledged: Filter by acknowledged status
            severity: Filter by severity

        Returns:
            List of alerts
        """
        alerts = self._alerts

        if acknowledged is not None:
            alerts = [a for a in alerts if a.acknowledged == acknowledged]

        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        return alerts

    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert."""
        for alert in self._alerts:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                logger.info(f"Alert {alert_id} acknowledged")
                return True
        return False

    def clear_acknowledged_alerts(self) -> int:
        """Clear all acknowledged alerts."""
        initial_count = len(self._alerts)
        self._alerts = [a for a in self._alerts if not a.acknowledged]
        return initial_count - len(self._alerts)

    def detect_lag_anomaly(self, region: Region, threshold_ms: int = 500) -> bool:
        """
        Detect if lag is above threshold.

        Args:
            region: Region to check
            threshold_ms: Lag threshold

        Returns:
            True if lag exceeds threshold
        """
        health = self._region_health.get(region)
        if health and health.lag_ms > threshold_ms:
            logger.warning(
                f"Lag anomaly detected for {region.value}: "
                f"{health.lag_ms}ms > {threshold_ms}ms"
            )
            return True
        return False

    def get_dashboard_data(self) -> Dict[str, Any]:
        """
        Get data for health dashboard.

        Returns:
            Dashboard data dictionary
        """
        return {
            "overall_status": self.get_overall_status().value,
            "regions": {
                region.value: health.to_dict()
                for region, health in self._region_health.items()
            },
            "active_alerts": len([a for a in self._alerts if not a.acknowledged]),
            "critical_alerts": len([a for a in self._alerts if a.severity == "critical" and not a.acknowledged]),
            "last_updated": datetime.now().isoformat()
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get monitor statistics."""
        return {
            "total_alerts": len(self._alerts),
            "unacknowledged_alerts": len([a for a in self._alerts if not a.acknowledged]),
            "healthy_regions": len([h for h in self._region_health.values() if h.status == HealthStatus.HEALTHY]),
            "degraded_regions": len([h for h in self._region_health.values() if h.status == HealthStatus.DEGRADED]),
            "unhealthy_regions": len([h for h in self._region_health.values() if h.status == HealthStatus.UNHEALTHY])
        }


def get_replication_monitor() -> ReplicationMonitor:
    """Factory function to create a replication monitor."""
    return ReplicationMonitor()
