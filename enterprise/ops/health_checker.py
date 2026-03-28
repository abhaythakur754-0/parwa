# Health Checker - Week 50 Builder 3
# Health check automation

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
import uuid


class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class CheckType(Enum):
    HTTP = "http"
    TCP = "tcp"
    DATABASE = "database"
    CUSTOM = "custom"


@dataclass
class HealthCheck:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    check_type: CheckType = CheckType.HTTP
    target: str = ""
    timeout_seconds: int = 30
    interval_seconds: int = 60
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class HealthCheckResult:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    check_id: str = ""
    status: HealthStatus = HealthStatus.UNKNOWN
    response_time_ms: float = 0.0
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    checked_at: datetime = field(default_factory=datetime.utcnow)


class HealthChecker:
    """Automated health checking system"""

    def __init__(self):
        self._checks: Dict[str, HealthCheck] = {}
        self._results: List[HealthCheckResult] = []
        self._status_cache: Dict[str, HealthStatus] = {}
        self._metrics = {
            "total_checks": 0,
            "total_executions": 0,
            "healthy": 0,
            "unhealthy": 0,
            "degraded": 0
        }

    def register_check(
        self,
        name: str,
        check_type: CheckType,
        target: str,
        timeout_seconds: int = 30,
        interval_seconds: int = 60
    ) -> HealthCheck:
        """Register a health check"""
        check = HealthCheck(
            name=name,
            check_type=check_type,
            target=target,
            timeout_seconds=timeout_seconds,
            interval_seconds=interval_seconds
        )
        self._checks[check.id] = check
        self._metrics["total_checks"] += 1
        return check

    def execute_check(
        self,
        check_id: str,
        status: HealthStatus = HealthStatus.HEALTHY,
        response_time_ms: float = 0.0,
        message: str = "",
        details: Optional[Dict[str, Any]] = None
    ) -> Optional[HealthCheckResult]:
        """Execute and record a health check"""
        check = self._checks.get(check_id)
        if not check or not check.enabled:
            return None

        result = HealthCheckResult(
            check_id=check_id,
            status=status,
            response_time_ms=response_time_ms,
            message=message,
            details=details or {}
        )

        self._results.append(result)
        self._status_cache[check_id] = status
        self._metrics["total_executions"] += 1

        if status == HealthStatus.HEALTHY:
            self._metrics["healthy"] += 1
        elif status == HealthStatus.UNHEALTHY:
            self._metrics["unhealthy"] += 1
        elif status == HealthStatus.DEGRADED:
            self._metrics["degraded"] += 1

        return result

    def get_check(self, check_id: str) -> Optional[HealthCheck]:
        """Get health check by ID"""
        return self._checks.get(check_id)

    def get_check_by_name(self, name: str) -> Optional[HealthCheck]:
        """Get health check by name"""
        for check in self._checks.values():
            if check.name == name:
                return check
        return None

    def get_current_status(self, check_id: str) -> HealthStatus:
        """Get current cached status"""
        return self._status_cache.get(check_id, HealthStatus.UNKNOWN)

    def get_all_statuses(self) -> Dict[str, HealthStatus]:
        """Get all current statuses"""
        return self._status_cache.copy()

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
            results = [r for r in results if r.checked_at >= since]

        return results[-limit:]

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

    def get_overall_health(self) -> HealthStatus:
        """Get overall system health"""
        if not self._status_cache:
            return HealthStatus.UNKNOWN

        statuses = list(self._status_cache.values())

        if all(s == HealthStatus.HEALTHY for s in statuses):
            return HealthStatus.HEALTHY
        elif any(s == HealthStatus.UNHEALTHY for s in statuses):
            return HealthStatus.UNHEALTHY
        elif any(s == HealthStatus.DEGRADED for s in statuses):
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.UNKNOWN

    def get_metrics(self) -> Dict[str, Any]:
        return {
            **self._metrics,
            "overall_health": self.get_overall_health().value,
            "active_checks": len([c for c in self._checks.values() if c.enabled])
        }

    def cleanup_old_results(self, hours: int = 24) -> int:
        """Remove old results"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        initial = len(self._results)
        self._results = [r for r in self._results if r.checked_at >= cutoff]
        return initial - len(self._results)
