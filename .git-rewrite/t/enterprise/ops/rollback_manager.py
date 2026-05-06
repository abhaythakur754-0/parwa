# Rollback Manager - Week 50 Builder 3
# Automated rollback system

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import uuid


class RollbackStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class RollbackPoint:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    deployment_id: str = ""
    version: str = ""
    snapshot_data: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Rollback:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    deployment_id: str = ""
    rollback_point_id: str = ""
    status: RollbackStatus = RollbackStatus.PENDING
    reason: str = ""
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    steps_completed: int = 0
    total_steps: int = 5
    created_at: datetime = field(default_factory=datetime.utcnow)


class RollbackManager:
    """Manages automated rollbacks"""

    def __init__(self):
        self._rollback_points: Dict[str, RollbackPoint] = {}
        self._rollbacks: Dict[str, Rollback] = {}
        self._metrics = {
            "total_rollbacks": 0,
            "successful": 0,
            "failed": 0,
            "rollback_points_created": 0
        }

    def create_rollback_point(
        self,
        deployment_id: str,
        version: str,
        snapshot_data: Optional[Dict[str, Any]] = None
    ) -> RollbackPoint:
        """Create a rollback point before deployment"""
        point = RollbackPoint(
            deployment_id=deployment_id,
            version=version,
            snapshot_data=snapshot_data or {}
        )
        self._rollback_points[point.id] = point
        self._metrics["rollback_points_created"] += 1
        return point

    def initiate_rollback(
        self,
        deployment_id: str,
        rollback_point_id: str,
        reason: str = ""
    ) -> Optional[Rollback]:
        """Initiate a rollback"""
        point = self._rollback_points.get(rollback_point_id)
        if not point:
            return None

        rollback = Rollback(
            deployment_id=deployment_id,
            rollback_point_id=rollback_point_id,
            reason=reason
        )
        self._rollbacks[rollback.id] = rollback
        self._metrics["total_rollbacks"] += 1
        return rollback

    def start_rollback(self, rollback_id: str) -> bool:
        """Start rollback execution"""
        rollback = self._rollbacks.get(rollback_id)
        if not rollback or rollback.status != RollbackStatus.PENDING:
            return False
        rollback.status = RollbackStatus.IN_PROGRESS
        rollback.started_at = datetime.utcnow()
        return True

    def complete_rollback_step(self, rollback_id: str) -> bool:
        """Complete a rollback step"""
        rollback = self._rollbacks.get(rollback_id)
        if not rollback or rollback.status != RollbackStatus.IN_PROGRESS:
            return False
        rollback.steps_completed += 1
        if rollback.steps_completed >= rollback.total_steps:
            rollback.status = RollbackStatus.COMPLETED
            rollback.completed_at = datetime.utcnow()
            self._metrics["successful"] += 1
        return True

    def fail_rollback(self, rollback_id: str) -> bool:
        """Mark rollback as failed"""
        rollback = self._rollbacks.get(rollback_id)
        if not rollback:
            return False
        rollback.status = RollbackStatus.FAILED
        self._metrics["failed"] += 1
        return True

    def get_rollback_point(self, point_id: str) -> Optional[RollbackPoint]:
        """Get rollback point by ID"""
        return self._rollback_points.get(point_id)

    def get_rollback(self, rollback_id: str) -> Optional[Rollback]:
        """Get rollback by ID"""
        return self._rollbacks.get(rollback_id)

    def get_rollback_points_for_deployment(self, deployment_id: str) -> List[RollbackPoint]:
        """Get all rollback points for a deployment"""
        return [
            p for p in self._rollback_points.values()
            if p.deployment_id == deployment_id
        ]

    def get_latest_rollback_point(self, deployment_id: str) -> Optional[RollbackPoint]:
        """Get the latest rollback point for a deployment"""
        points = self.get_rollback_points_for_deployment(deployment_id)
        if not points:
            return None
        return max(points, key=lambda p: p.created_at)

    def get_metrics(self) -> Dict[str, Any]:
        return self._metrics.copy()

    def cleanup_old_points(self, days: int = 30) -> int:
        """Remove old rollback points"""
        cutoff = datetime.utcnow() - __import__('datetime').timedelta(days=days)
        to_remove = [
            pid for pid, point in self._rollback_points.items()
            if point.created_at < cutoff
        ]
        for pid in to_remove:
            del self._rollback_points[pid]
        return len(to_remove)
