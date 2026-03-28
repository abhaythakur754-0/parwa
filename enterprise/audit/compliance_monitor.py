# Compliance Monitor - Week 49 Builder 5
# Real-time compliance monitoring

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from enum import Enum
import uuid


class MonitorStatus(Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPED = "stopped"


class CheckResult(Enum):
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"


@dataclass
class MonitorCheck:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    name: str = ""
    check_type: str = ""
    result: CheckResult = CheckResult.PASS
    score: float = 100.0
    details: Dict[str, Any] = field(default_factory=dict)
    checked_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Monitor:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    name: str = ""
    status: MonitorStatus = MonitorStatus.ACTIVE
    checks: List[MonitorCheck] = field(default_factory=list)
    last_check: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


class ComplianceMonitor:
    """Real-time compliance monitoring"""

    def __init__(self):
        self._monitors: Dict[str, Monitor] = {}
        self._check_handlers: Dict[str, Callable] = {}
        self._metrics = {
            "total_monitors": 0,
            "total_checks": 0,
            "passed_checks": 0,
            "failed_checks": 0
        }

    def create_monitor(
        self,
        tenant_id: str,
        name: str
    ) -> Monitor:
        """Create a compliance monitor"""
        monitor = Monitor(tenant_id=tenant_id, name=name)
        self._monitors[monitor.id] = monitor
        self._metrics["total_monitors"] += 1
        return monitor

    def register_check_handler(
        self,
        check_type: str,
        handler: Callable
    ) -> None:
        """Register a check handler"""
        self._check_handlers[check_type] = handler

    def run_check(
        self,
        monitor_id: str,
        check_type: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Optional[MonitorCheck]:
        """Run a compliance check"""
        monitor = self._monitors.get(monitor_id)
        if not monitor:
            return None

        handler = self._check_handlers.get(check_type)
        if not handler:
            return None

        try:
            result_data = handler(parameters or {})
            check = MonitorCheck(
                tenant_id=monitor.tenant_id,
                name=f"{check_type} check",
                check_type=check_type,
                result=CheckResult.PASS if result_data.get("pass", False) else CheckResult.FAIL,
                score=result_data.get("score", 0),
                details=result_data
            )
        except Exception as e:
            check = MonitorCheck(
                tenant_id=monitor.tenant_id,
                name=f"{check_type} check",
                check_type=check_type,
                result=CheckResult.FAIL,
                score=0,
                details={"error": str(e)}
            )

        monitor.checks.append(check)
        monitor.last_check = datetime.utcnow()
        self._metrics["total_checks"] += 1

        if check.result == CheckResult.PASS:
            self._metrics["passed_checks"] += 1
        else:
            self._metrics["failed_checks"] += 1

        return check

    def get_monitor(self, monitor_id: str) -> Optional[Monitor]:
        return self._monitors.get(monitor_id)

    def get_monitors_by_tenant(self, tenant_id: str) -> List[Monitor]:
        return [m for m in self._monitors.values() if m.tenant_id == tenant_id]

    def pause_monitor(self, monitor_id: str) -> bool:
        monitor = self._monitors.get(monitor_id)
        if not monitor:
            return False
        monitor.status = MonitorStatus.PAUSED
        return True

    def resume_monitor(self, monitor_id: str) -> bool:
        monitor = self._monitors.get(monitor_id)
        if not monitor:
            return False
        monitor.status = MonitorStatus.ACTIVE
        return True

    def get_compliance_score(self, monitor_id: str) -> float:
        """Get compliance score for a monitor"""
        monitor = self._monitors.get(monitor_id)
        if not monitor or not monitor.checks:
            return 100.0

        passed = len([c for c in monitor.checks if c.result == CheckResult.PASS])
        return (passed / len(monitor.checks)) * 100

    def get_metrics(self) -> Dict[str, Any]:
        return self._metrics.copy()
