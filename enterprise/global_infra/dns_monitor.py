# DNS Monitor - Week 51 Builder 5
# DNS health monitoring

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
import uuid


class MonitorStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class CheckType(Enum):
    TCP = "tcp"
    HTTP = "http"
    HTTPS = "https"
    DNS = "dns"


@dataclass
class HealthCheck:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    check_type: CheckType = CheckType.HTTPS
    target: str = ""
    port: int = 443
    interval_seconds: int = 30
    timeout_seconds: int = 10
    threshold: int = 3
    enabled: bool = True
    last_check: Optional[datetime] = None
    last_status: MonitorStatus = MonitorStatus.UNKNOWN
    consecutive_successes: int = 0
    consecutive_failures: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class HealthCheckResult:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    check_id: str = ""
    status: MonitorStatus = MonitorStatus.UNKNOWN
    response_time_ms: float = 0.0
    status_code: Optional[int] = None
    message: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class DNSAlert:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    check_id: str = ""
    status: MonitorStatus = MonitorStatus.UNHEALTHY
    message: str = ""
    acknowledged: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)


class DNSMonitor:
    """Monitors DNS health and endpoints"""

    def __init__(self):
        self._checks: Dict[str, HealthCheck] = {}
        self._results: List[HealthCheckResult] = []
        self._alerts: List[DNSAlert] = []
        self._metrics = {
            "total_checks": 0,
            "total_executions": 0,
            "healthy": 0,
            "unhealthy": 0,
            "alerts_raised": 0
        }

    def create_check(
        self,
        name: str,
        check_type: CheckType,
        target: str,
        port: int = 443,
        interval_seconds: int = 30,
        timeout_seconds: int = 10,
        threshold: int = 3
    ) -> HealthCheck:
        """Create a health check"""
        check = HealthCheck(
            name=name,
            check_type=check_type,
            target=target,
            port=port,
            interval_seconds=interval_seconds,
            timeout_seconds=timeout_seconds,
            threshold=threshold
        )
        self._checks[check.id] = check
        self._metrics["total_checks"] += 1
        return check

    def delete_check(self, check_id: str) -> bool:
        """Delete a health check"""
        if check_id in self._checks:
            del self._checks[check_id]
            return True
        return False

    def execute_check(
        self,
        check_id: str,
        status: MonitorStatus = MonitorStatus.HEALTHY,
        response_time_ms: float = 0.0,
        status_code: Optional[int] = None,
        message: str = ""
    ) -> Optional[HealthCheckResult]:
        """Execute and record a health check"""
        check = self._checks.get(check_id)
        if not check or not check.enabled:
            return None

        result = HealthCheckResult(
            check_id=check_id,
            status=status,
            response_time_ms=response_time_ms,
            status_code=status_code,
            message=message
        )

        self._results.append(result)
        self._metrics["total_executions"] += 1

        # Update check state
        check.last_check = datetime.utcnow()
        check.last_status = status

        if status == MonitorStatus.HEALTHY:
            check.consecutive_successes += 1
            check.consecutive_failures = 0
            self._metrics["healthy"] += 1
        else:
            check.consecutive_failures += 1
            check.consecutive_successes = 0
            self._metrics["unhealthy"] += 1

            # Raise alert if threshold exceeded
            if check.consecutive_failures >= check.threshold:
                self._raise_alert(check_id, status, message)

        return result

    def _raise_alert(
        self,
        check_id: str,
        status: MonitorStatus,
        message: str
    ) -> DNSAlert:
        """Raise a health alert"""
        alert = DNSAlert(
            check_id=check_id,
            status=status,
            message=message
        )
        self._alerts.append(alert)
        self._metrics["alerts_raised"] += 1
        return alert

    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert"""
        for alert in self._alerts:
            if alert.id == alert_id and not alert.acknowledged:
                alert.acknowledged = True
                return True
        return False

    def get_check(self, check_id: str) -> Optional[HealthCheck]:
        """Get check by ID"""
        return self._checks.get(check_id)

    def get_check_by_name(self, name: str) -> Optional[HealthCheck]:
        """Get check by name"""
        for check in self._checks.values():
            if check.name == name:
                return check
        return None

    def get_results(
        self,
        check_id: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[HealthCheckResult]:
        """Get health check results"""
        results = self._results

        if check_id:
            results = [r for r in results if r.check_id == check_id]
        if since:
            results = [r for r in results if r.timestamp >= since]

        return results[-limit:]

    def get_alerts(
        self,
        acknowledged: Optional[bool] = None,
        limit: int = 100
    ) -> List[DNSAlert]:
        """Get alerts"""
        alerts = self._alerts

        if acknowledged is not None:
            alerts = [a for a in alerts if a.acknowledged == acknowledged]

        return alerts[-limit:]

    def get_unacknowledged_alerts(self) -> List[DNSAlert]:
        """Get all unacknowledged alerts"""
        return [a for a in self._alerts if not a.acknowledged]

    def enable_check(self, check_id: str) -> bool:
        """Enable a health check"""
        check = self._checks.get(check_id)
        if not check:
            return False
        check.enabled = True
        return True

    def disable_check(self, check_id: str) -> bool:
        """Disable a health check"""
        check = self._checks.get(check_id)
        if not check:
            return False
        check.enabled = False
        return True

    def get_enabled_checks(self) -> List[HealthCheck]:
        """Get all enabled checks"""
        return [c for c in self._checks.values() if c.enabled]

    def get_checks_by_status(self, status: MonitorStatus) -> List[HealthCheck]:
        """Get all checks with a given status"""
        return [c for c in self._checks.values() if c.last_status == status]

    def get_overall_health(self) -> MonitorStatus:
        """Get overall system health"""
        if not self._checks:
            return MonitorStatus.UNKNOWN

        checks = list(self._checks.values())
        statuses = [c.last_status for c in checks]

        if all(s == MonitorStatus.HEALTHY for s in statuses):
            return MonitorStatus.HEALTHY
        elif any(s == MonitorStatus.UNHEALTHY for s in statuses):
            return MonitorStatus.UNHEALTHY
        elif any(s == MonitorStatus.DEGRADED for s in statuses):
            return MonitorStatus.DEGRADED
        else:
            return MonitorStatus.UNKNOWN

    def get_availability(
        self,
        check_id: str,
        hours: int = 24
    ) -> float:
        """Calculate availability percentage"""
        since = datetime.utcnow() - timedelta(hours=hours)
        results = self.get_results(check_id, since)

        if not results:
            return 0.0

        healthy_count = sum(
            1 for r in results if r.status == MonitorStatus.HEALTHY
        )
        return (healthy_count / len(results)) * 100

    def get_avg_response_time(
        self,
        check_id: str,
        hours: int = 24
    ) -> float:
        """Get average response time"""
        since = datetime.utcnow() - timedelta(hours=hours)
        results = self.get_results(check_id, since)

        if not results:
            return 0.0

        return sum(r.response_time_ms for r in results) / len(results)

    def cleanup_old_results(self, hours: int = 168) -> int:
        """Remove old results (default 7 days)"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        initial = len(self._results)
        self._results = [r for r in self._results if r.timestamp >= cutoff]
        return initial - len(self._results)

    def get_metrics(self) -> Dict[str, Any]:
        """Get monitor metrics"""
        return {
            **self._metrics,
            "overall_health": self.get_overall_health().value,
            "active_checks": len(self.get_enabled_checks()),
            "unacknowledged_alerts": len(self.get_unacknowledged_alerts())
        }
