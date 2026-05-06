"""
Health Aggregator Module - Week 53, Builder 1
Health status aggregation for system monitoring
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set
import logging
import threading

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status enum"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class Severity(Enum):
    """Severity level"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class HealthCheck:
    """Individual health check result"""
    name: str
    status: HealthStatus
    message: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    details: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "duration_ms": self.duration_ms,
        }


@dataclass
class HealthDependency:
    """Health dependency definition"""
    name: str
    required: bool = True
    weight: float = 1.0


@dataclass
class ComponentHealth:
    """Health status of a component"""
    component: str
    status: HealthStatus
    checks: List[HealthCheck] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    last_check: Optional[datetime] = None
    uptime_percent: float = 100.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_healthy(self) -> bool:
        return self.status == HealthStatus.HEALTHY

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "component": self.component,
            "status": self.status.value,
            "checks": [c.to_dict() for c in self.checks],
            "dependencies": self.dependencies,
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "uptime_percent": self.uptime_percent,
        }


@dataclass
class SystemHealth:
    """Overall system health"""
    status: HealthStatus
    components: Dict[str, ComponentHealth] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    issues: List[str] = field(default_factory=list)

    @property
    def healthy_count(self) -> int:
        return sum(1 for c in self.components.values() if c.is_healthy)

    @property
    def total_count(self) -> int:
        return len(self.components)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "status": self.status.value,
            "healthy_count": self.healthy_count,
            "total_count": self.total_count,
            "timestamp": self.timestamp.isoformat(),
            "issues": self.issues,
            "components": {k: v.to_dict() for k, v in self.components.items()},
        }


class HealthHistory:
    """
    Tracks health history for uptime calculations.
    """

    def __init__(self, max_entries: int = 1000):
        self.max_entries = max_entries
        self._history: Dict[str, List[tuple]] = {}
        self._lock = threading.Lock()

    def record(
        self,
        component: str,
        status: HealthStatus,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Record health status"""
        with self._lock:
            if component not in self._history:
                self._history[component] = []

            self._history[component].append((
                timestamp or datetime.utcnow(),
                status,
            ))

            # Enforce max entries
            if len(self._history[component]) > self.max_entries:
                self._history[component] = self._history[component][-self.max_entries:]

    def get_uptime(
        self,
        component: str,
        window_seconds: int = 3600,
    ) -> float:
        """Calculate uptime percentage"""
        with self._lock:
            history = self._history.get(component, [])
            if not history:
                return 100.0

            cutoff = datetime.utcnow() - timedelta(seconds=window_seconds)
            recent = [(ts, s) for ts, s in history if ts > cutoff]

            if not recent:
                return 100.0

            healthy_count = sum(
                1 for _, s in recent
                if s == HealthStatus.HEALTHY
            )

            return (healthy_count / len(recent)) * 100

    def get_history(
        self,
        component: str,
        limit: int = 100,
    ) -> List[tuple]:
        """Get health history"""
        with self._lock:
            history = self._history.get(component, [])
            return history[-limit:]


class HealthAggregator:
    """
    Main health aggregation engine.
    """

    def __init__(self):
        self.components: Dict[str, ComponentHealth] = {}
        self.history = HealthHistory()
        self._dependency_graph: Dict[str, List[str]] = {}
        self._status_weights: Dict[HealthStatus, int] = {
            HealthStatus.HEALTHY: 0,
            HealthStatus.DEGRADED: 1,
            HealthStatus.UNHEALTHY: 2,
            HealthStatus.UNKNOWN: 3,
        }
        self._lock = threading.Lock()

    def register_component(
        self,
        name: str,
        dependencies: Optional[List[str]] = None,
    ) -> None:
        """Register a component for health tracking"""
        with self._lock:
            if name not in self.components:
                self.components[name] = ComponentHealth(
                    component=name,
                    status=HealthStatus.UNKNOWN,
                    dependencies=dependencies or [],
                )
                self._dependency_graph[name] = dependencies or []

    def unregister_component(self, name: str) -> bool:
        """Unregister a component"""
        with self._lock:
            if name in self.components:
                del self.components[name]
                del self._dependency_graph[name]
                return True
            return False

    def update_health(
        self,
        component: str,
        check: HealthCheck,
    ) -> None:
        """Update component health"""
        with self._lock:
            if component not in self.components:
                self.register_component(component)

            comp = self.components[component]
            comp.checks.append(check)
            comp.last_check = check.timestamp

            # Keep only recent checks
            if len(comp.checks) > 100:
                comp.checks = comp.checks[-100:]

            # Determine component status
            comp.status = self._determine_status(component, check)

            # Record in history
            self.history.record(component, comp.status)

            # Update uptime
            comp.uptime_percent = self.history.get_uptime(component)

    def _determine_status(
        self,
        component: str,
        check: HealthCheck,
    ) -> HealthStatus:
        """Determine overall component status"""
        # Check dependencies
        deps = self._dependency_graph.get(component, [])
        for dep in deps:
            dep_health = self.components.get(dep)
            if dep_health and dep_health.status == HealthStatus.UNHEALTHY:
                return HealthStatus.DEGRADED

        return check.status

    def add_check(
        self,
        component: str,
        name: str,
        status: HealthStatus,
        message: str = "",
        details: Optional[Dict[str, Any]] = None,
    ) -> HealthCheck:
        """Add a health check to a component"""
        check = HealthCheck(
            name=name,
            status=status,
            message=message,
            details=details or {},
        )
        self.update_health(component, check)
        return check

    def get_health(self, component: str) -> Optional[ComponentHealth]:
        """Get health for a component"""
        return self.components.get(component)

    def get_system_health(self) -> SystemHealth:
        """Get overall system health"""
        with self._lock:
            # Determine overall status
            worst_status = HealthStatus.HEALTHY
            issues = []

            for name, comp in self.components.items():
                if self._status_weights.get(comp.status, 0) > self._status_weights.get(worst_status, 0):
                    worst_status = comp.status

                if comp.status == HealthStatus.UNHEALTHY:
                    issues.append(f"{name}: unhealthy")
                elif comp.status == HealthStatus.DEGRADED:
                    issues.append(f"{name}: degraded")

            return SystemHealth(
                status=worst_status,
                components=dict(self.components),
                issues=issues,
            )

    def get_dependency_order(self) -> List[str]:
        """Get components in dependency order (topological sort)"""
        visited: Set[str] = set()
        order: List[str] = []

        def visit(name: str):
            if name in visited:
                return
            visited.add(name)

            for dep in self._dependency_graph.get(name, []):
                visit(dep)

            order.append(name)

        for component in self.components:
            visit(component)

        return order

    def propagate_health(self) -> None:
        """Propagate health status through dependency graph"""
        order = self.get_dependency_order()

        for component in order:
            comp = self.components.get(component)
            if not comp:
                continue

            # Check if any dependency is unhealthy
            for dep in comp.dependencies:
                dep_comp = self.components.get(dep)
                if dep_comp and dep_comp.status == HealthStatus.UNHEALTHY:
                    if comp.status == HealthStatus.HEALTHY:
                        comp.status = HealthStatus.DEGRADED

    def get_summary(self) -> Dict[str, Any]:
        """Get health summary"""
        system = self.get_system_health()

        return {
            "overall_status": system.status.value,
            "healthy_count": system.healthy_count,
            "total_count": system.total_count,
            "issues": system.issues,
            "components": {
                name: {
                    "status": comp.status.value,
                    "uptime": comp.uptime_percent,
                }
                for name, comp in self.components.items()
            },
        }

    def get_component_status(self, component: str) -> Optional[HealthStatus]:
        """Get status of a specific component"""
        comp = self.components.get(component)
        return comp.status if comp else None

    def is_healthy(self, component: Optional[str] = None) -> bool:
        """Check if component or system is healthy"""
        if component:
            comp = self.components.get(component)
            return comp.is_healthy if comp else False

        return self.get_system_health().status == HealthStatus.HEALTHY

    def reset(self, component: Optional[str] = None) -> None:
        """Reset health status"""
        with self._lock:
            if component:
                if component in self.components:
                    self.components[component].status = HealthStatus.UNKNOWN
                    self.components[component].checks.clear()
            else:
                for comp in self.components.values():
                    comp.status = HealthStatus.UNKNOWN
                    comp.checks.clear()


class HealthCheckRegistry:
    """
    Registry for health check functions.
    """

    def __init__(self, aggregator: HealthAggregator):
        self.aggregator = aggregator
        self._checkers: Dict[str, callable] = {}

    def register(
        self,
        component: str,
        checker: callable,
    ) -> None:
        """Register a health checker"""
        self._checkers[component] = checker
        self.aggregator.register_component(component)

    async def run_check(self, component: str) -> HealthCheck:
        """Run a health check"""
        checker = self._checkers.get(component)
        if not checker:
            return HealthCheck(
                name=component,
                status=HealthStatus.UNKNOWN,
                message="No checker registered",
            )

        try:
            import asyncio
            result = checker()
            if asyncio.iscoroutine(result):
                result = await result

            if isinstance(result, HealthCheck):
                self.aggregator.update_health(component, result)
                return result
            elif isinstance(result, dict):
                check = HealthCheck(
                    name=component,
                    status=HealthStatus(result.get("status", "healthy")),
                    message=result.get("message", ""),
                    details=result.get("details", {}),
                )
                self.aggregator.update_health(component, check)
                return check

            return HealthCheck(
                name=component,
                status=HealthStatus.HEALTHY,
            )

        except Exception as e:
            check = HealthCheck(
                name=component,
                status=HealthStatus.UNHEALTHY,
                message=str(e),
            )
            self.aggregator.update_health(component, check)
            return check

    async def run_all_checks(self) -> Dict[str, HealthCheck]:
        """Run all registered health checks"""
        import asyncio
        tasks = {
            component: self.run_check(component)
            for component in self._checkers
        }

        results = {}
        for component, task in tasks.items():
            results[component] = await task

        return results
