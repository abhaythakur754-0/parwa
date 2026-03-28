# Resource Optimizer - Week 50 Builder 1
# Resource optimization and management

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import uuid


class ResourceType(Enum):
    CPU = "cpu"
    MEMORY = "memory"
    STORAGE = "storage"
    CONNECTION = "connection"
    THREAD = "thread"


class OptimizationAction(Enum):
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    CLEANUP = "cleanup"
    REBALANCE = "rebalance"


@dataclass
class ResourceUsage:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    resource_type: ResourceType = ResourceType.CPU
    allocated: float = 0.0
    used: float = 0.0
    available: float = 0.0
    utilization_percent: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class OptimizationPlan:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    resource_type: ResourceType = ResourceType.CPU
    action: OptimizationAction = OptimizationAction.SCALE_UP
    current_value: float = 0.0
    target_value: float = 0.0
    reason: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    applied: bool = False


class ResourceOptimizer:
    """Optimizes resource usage"""

    def __init__(self):
        self._usage: List[ResourceUsage] = []
        self._plans: Dict[str, OptimizationPlan] = []
        self._config: Dict[ResourceType, Dict[str, float]] = {
            ResourceType.CPU: {"min": 1, "max": 100, "target_utilization": 70.0},
            ResourceType.MEMORY: {"min": 256, "max": 16384, "target_utilization": 75.0}
        }
        self._metrics = {"total_optimizations": 0, "by_action": {}}

    def record_usage(
        self,
        resource_type: ResourceType,
        allocated: float,
        used: float
    ) -> ResourceUsage:
        """Record resource usage"""
        utilization = (used / allocated * 100) if allocated > 0 else 0

        usage = ResourceUsage(
            resource_type=resource_type,
            allocated=allocated,
            used=used,
            available=allocated - used,
            utilization_percent=utilization
        )

        self._usage.append(usage)
        return usage

    def analyze_and_optimize(
        self,
        resource_type: ResourceType
    ) -> Optional[OptimizationPlan]:
        """Analyze usage and create optimization plan"""
        recent = [u for u in self._usage if u.resource_type == resource_type][-10:]
        if not recent:
            return None

        avg_utilization = sum(u.utilization_percent for u in recent) / len(recent)
        config = self._config.get(resource_type, {})
        target = config.get("target_utilization", 70.0)

        if avg_utilization > target + 20:
            plan = OptimizationPlan(
                resource_type=resource_type,
                action=OptimizationAction.SCALE_UP,
                current_value=avg_utilization,
                target_value=target,
                reason=f"High utilization: {avg_utilization:.1f}%"
            )
        elif avg_utilization < target - 30:
            plan = OptimizationPlan(
                resource_type=resource_type,
                action=OptimizationAction.SCALE_DOWN,
                current_value=avg_utilization,
                target_value=target,
                reason=f"Low utilization: {avg_utilization:.1f}%"
            )
        else:
            return None

        self._plans.append(plan)
        self._metrics["total_optimizations"] += 1
        action_key = plan.action.value
        self._metrics["by_action"][action_key] = self._metrics["by_action"].get(action_key, 0) + 1

        return plan

    def apply_plan(self, plan_id: str) -> bool:
        """Apply an optimization plan"""
        for plan in self._plans:
            if plan.id == plan_id:
                plan.applied = True
                return True
        return False

    def get_plan(self, plan_id: str) -> Optional[OptimizationPlan]:
        """Get a plan by ID"""
        for plan in self._plans:
            if plan.id == plan_id:
                return plan
        return None

    def get_current_usage(
        self,
        resource_type: ResourceType
    ) -> Optional[ResourceUsage]:
        """Get current resource usage"""
        recent = [u for u in self._usage if u.resource_type == resource_type]
        return recent[-1] if recent else None

    def get_metrics(self) -> Dict[str, Any]:
        return self._metrics.copy()
